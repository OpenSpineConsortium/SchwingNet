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
# the data root (tools/catalog.py build) and run the REFORMS split check on the new version.
# A build whose bytes equal the latest version is reported as not new and leaves the store as it
# was. The report is logs/03-catalog-STAGE-REPORT.md. DATA_ROOT and STORE can be overridden.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
DATA_ROOT=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
STORE=${STORE:-$DATA_ROOT/_catalog}
REPORT=logs/03-catalog-STAGE-REPORT.md
COMMIT=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo 0000000)
export PYTHONNOUSERSITE=1
mkdir -p logs
echo "XR_CATALOG start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-}"
{
  echo "# Stage 3, catalog: $(date '+%F %T')"
  echo
} > "$REPORT"
args=()
while IFS= read -r manifest; do
  args+=(--manifest "$manifest")
done < <(find "$DATA_ROOT" -mindepth 4 -maxdepth 4 -path '*/shards/*/MANIFEST.json' 2>/dev/null | sort)
if [ "${#args[@]}" = 0 ]; then
  echo "- no MANIFEST.json under $DATA_ROOT/*/shards/: nothing to build" >> "$REPORT"; cat "$REPORT"; exit 1
fi
echo "- manifests read: $(( ${#args[@]} / 2 ))" >> "$REPORT"
rc=0
if out=$("$PYDRV" "$REPO/tools/catalog.py" build --store "$STORE" --code-commit "$COMMIT" "${args[@]}" 2>&1); then
  echo "$out"; echo "- build: $out" >> "$REPORT"
else
  echo "$out"; echo "- build refused: $(echo "$out" | tail -n 1)" >> "$REPORT"; rc=1
fi
if [ "$rc" = 0 ]; then
  if out=$("$PYDRV" "$REPO/tools/catalog.py" split-check "$STORE" 2>&1); then
    echo "$out"; echo "- split-check: disjoint (the full answer is in the log)" >> "$REPORT"
  else
    echo "$out"; echo "- split-check FAILED: $(echo "$out" | tail -n 1); no training step reads this version" >> "$REPORT"; rc=1
  fi
fi
cat "$REPORT"
echo "XR_CATALOG_RC=$rc $(date '+%F %T')"
exit $rc
