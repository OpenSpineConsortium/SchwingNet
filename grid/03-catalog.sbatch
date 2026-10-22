#!/bin/bash
#SBATCH --job-name=xr_catalog
#SBATCH --partition=reqp
#SBATCH --qos=requeue
#SBATCH --requeue
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x_%j.out
# Stage 3 of the X-ray chain: rebuild the read-only catalog from every shard manifest under
# the data root (tools/catalog.py build, each source's chain at its head alone, since stage 2
# supersedes a shard whose bank grew) and run the REFORMS split check on the new version.
# A build whose bytes equal the latest version is reported as not new and leaves the store as it
# was. The report is logs/03-catalog-STAGE-REPORT.md. DATA_ROOT and STORE can be overridden.
#
# One build at a time, from the listing of the manifests to the split check (issue #80): start's
# first catalog, the X-ray chain's, a fetch's and v1's can be queued together and start in any
# order. tools/catalog.py's own lock keeps the store whole whatever happens, but a build that
# listed the manifests before another job's shards were written, and landed after the build that
# held them, would make a CURRENT that leaves them out, and a split check of "the newest version"
# could read another job's build. So the job takes $STORE/BUILD.lock (flock, which util-linux
# gives every node) before it lists anything and keeps it to the end, checks the version its own
# build made, writes $STORE/checked/<file> once that check passes (grid/v1-version.sh reads it),
# and writes its report only once it holds the lock, since every catalog job writes the same
# report file. BUILD_LOCK_WAIT bounds the wait, inside the job's wall time.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
DATA_ROOT=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
STORE=${STORE:-$DATA_ROOT/_catalog}
REPORT=logs/03-catalog-STAGE-REPORT.md
COMMIT=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo 0000000)
WAIT=${BUILD_LOCK_WAIT:-39600}
export PYTHONNOUSERSITE=1 TMPDIR=${TMPDIR_OVERRIDE:-${DATA_ROOT:+$DATA_ROOT/_tmp}}
TMPDIR=${TMPDIR:-/rs/rs_grp_oschome/go2432/tmp}
mkdir -p logs "$TMPDIR" "$STORE"
# The marker grid/v1-version.sh reads: the version passed the split check at this commit, against
# these test persons and this rule, so a version checked before the freeze changed is not run on.
# Written whole and then renamed, so a reader never sees half of it.
mark() {  # mark FILE
  local marker=$STORE/checked/$1
  mkdir -p "$STORE/checked" || return 1
  { echo "commit $COMMIT"
    echo "test-persons $(sha256sum < "$REPO/data/splits/test-persons.json" | cut -d' ' -f1)"
    echo "rule $(sha256sum < "$REPO/data/splits/rule.json" | cut -d' ' -f1)"
  } > "$marker.new" && mv -f "$marker.new" "$marker"
}
echo "XR_CATALOG start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-}"
exec 8>> "$STORE/BUILD.lock"
if ! flock -w "$WAIT" 8; then
  echo "another catalog build held $STORE/BUILD.lock for $WAIT s; nothing built"
  echo "XR_CATALOG_RC=1 $(date '+%F %T')"
  exit 1
fi
echo "XR_CATALOG lock $(date '+%F %T')"
{
  echo "# Stage 3, catalog: $(date '+%F %T'), job ${SLURM_JOB_ID:-none}"
  echo
} > "$REPORT"
args=()
while IFS= read -r manifest; do
  args+=(--manifest "$manifest")
done < <(find "$DATA_ROOT" -mindepth 4 -maxdepth 4 -path '*/shards/*/MANIFEST.json' 2>/dev/null | sort)
if [ "${#args[@]}" = 0 ]; then
  echo "- no MANIFEST.json under $DATA_ROOT/*/shards/: nothing to build" >> "$REPORT"; cat "$REPORT"
  echo "XR_CATALOG_RC=1 $(date '+%F %T')"; exit 1
fi
echo "- manifests read: $(( ${#args[@]} / 2 ))" >> "$REPORT"
rc=0
version=""
if out=$("$PYDRV" "$REPO/tools/catalog.py" build --store "$STORE" --code-commit "$COMMIT" --drop-superseded "${args[@]}" 2>&1); then
  echo "$out"; echo "- build: $out" >> "$REPORT"
  version=$(echo "$out" | sed -n 's/.*"version": *\([0-9][0-9]*\)[,}].*/\1/p' | tail -n 1)
  file=$(echo "$out" | sed -n 's/.*"file": *"\(catalog-[0-9]*-[0-9a-f]*\.sqlite\)".*/\1/p' | tail -n 1)
  [ -n "$version" ] && [ -n "$file" ] || { echo "- the build named no version; nothing is checked" >> "$REPORT"; rc=1; }
else
  echo "$out"; echo "- build refused: $(echo "$out" | tail -n 1)" >> "$REPORT"; rc=1
fi
if [ "$rc" = 0 ]; then
  if out=$("$PYDRV" "$REPO/tools/catalog.py" split-check "$STORE" --version "$version" 2>&1); then
    echo "$out"; echo "- split-check of version $version: disjoint (the full answer is in the log)" >> "$REPORT"
    mark "$file" || { echo "- the split-check marker for version $version could not be written" >> "$REPORT"; rc=1; }
  else
    echo "$out"; echo "- split-check of version $version FAILED: $(echo "$out" | tail -n 1); no training step reads this version" >> "$REPORT"; rc=1
  fi
fi
cat "$REPORT"
echo "XR_CATALOG_RC=$rc $(date '+%F %T')"
exit $rc
