#!/bin/bash
#SBATCH --job-name=xr_bank
#SBATCH --partition=reqp
#SBATCH --qos=requeue
#SBATCH --requeue
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=2-00:00:00
#SBATCH --output=logs/%x_%j.out
# Stage 2 of the X-ray chain: for each recipe grid/banks/<id>.json, turn the raw copy into a
# bank (tools/bank.py --run) and ingest the bank into a content-hashed shard
# (tools/ingest.py run, superseding the source's current shard where the bank grew, so a raw
# copy that came in parts is counted once by the catalog). A recipe still spelled "to confirm", a raw folder not fetched, or a
# format the bank tool refuses (DICOM until pydicom is locked) is one line in the report and the
# loop goes on; the stage exits non-zero at the end when any source failed. PYDRV must hold
# pydantic, beartype and icontract (the repository's pixi environment). ONLY narrows the loop to
# a space-separated list of ids. The report is logs/02-bank-ingest-STAGE-REPORT.md. Off the grid
# (issue #40) DATA_ROOT puts each source's raw, bank and shards under <root>/<id>/ in place of the
# recipe's and the registry's paths, and BANKS names another recipe folder, so a test runs the
# stage on a filled-in copy of a recipe without touching the shipped one.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
ONLY=${ONLY:-}
DATA_ROOT=${DATA_ROOT:-}
BANKS=${BANKS:-$REPO/grid/banks}
DATE=$(date '+%F')
COMMIT=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo 0000000)
REPORT=logs/02-bank-ingest-STAGE-REPORT.md
export PYTHONNOUSERSITE=1 TMPDIR=${TMPDIR_OVERRIDE:-${DATA_ROOT:+$DATA_ROOT/_tmp}}
TMPDIR=${TMPDIR:-/rs/rs_grp_oschome/go2432/tmp}
mkdir -p logs "$TMPDIR"
echo "XR_BANK start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-} commit $COMMIT"
{
  echo "# Stage 2, bank and ingest: $(date '+%F %T')"
  echo
  echo "Code commit $COMMIT, ingest date $DATE; one line per recipe under grid/banks/."
  echo
} > "$REPORT"
failed=0
for recipe in "$BANKS"/*.json; do
  id=$(basename "$recipe" .json)
  if [ -n "$ONLY" ] && ! echo " $ONLY " | grep -q " $id "; then continue; fi
  raw=$("$PYDRV" -c "import json,sys; print(json.load(open(sys.argv[1]))['raw'])" "$recipe")
  bank=$("$PYDRV" -c "import json,sys; print(json.load(open(sys.argv[1]))['bank'])" "$recipe")
  prefix=$("$PYDRV" -c "import json,sys; r=json.load(open(sys.argv[1])); print(r.get('person_prefix', r['id']))" "$recipe")
  root_args=()
  if [ -n "$DATA_ROOT" ]; then
    raw=$DATA_ROOT/$id/raw; bank=$DATA_ROOT/$id/bank; root_args=(--grid-root "$DATA_ROOT/$id")
  fi
  echo "== $id: $(date '+%F %T')"
  if [ ! -d "$raw" ] || [ -z "$(ls -A "$raw" 2>/dev/null)" ]; then
    echo "- $id: skipped, nothing fetched under $raw" >> "$REPORT"; continue
  fi
  if ! out=$("$PYDRV" "$REPO/tools/bank.py" --recipe "$recipe" --raw "$raw" --bank "$bank" --run 2>&1); then
    echo "$out"; echo "- $id: bank refused: $(echo "$out" | tail -n 1)" >> "$REPORT"; failed=1; continue
  fi
  echo "$out"
  if ! out=$("$PYDRV" "$REPO/tools/ingest.py" run --bank "$bank" --source "$id" --kind train --split train \
        --date "$DATE" --code-commit "$COMMIT" --person-prefix "$prefix" --supersedes latest "${root_args[@]}" 2>&1); then
    echo "$out"; echo "- $id: ingest refused: $(echo "$out" | tail -n 1)" >> "$REPORT"; failed=1; continue
  fi
  echo "$out"
  shard=$(echo "$out" | "$PYDRV" -c "import json,sys; d=json.load(sys.stdin); print(d['shard'], d['outcome'], d['frames_kept'], 'frames,', d['persons'], 'persons,', d['labels'], 'labels')")
  echo "- $id: $shard" >> "$REPORT"
done
{
  echo
  if [ "$failed" = 0 ]; then echo "Every recipe that had a raw copy was banked and ingested."; else echo "Some recipes failed; the lines above say which, the log logs/xr_bank_${SLURM_JOB_ID:-}.out says why."; fi
  echo "A recipe spelled 'to confirm' is filled in from the page and this stage is run again for that id: ONLY=<id> sbatch -D $REPO/grid $REPO/grid/02-bank-ingest.sbatch"
} >> "$REPORT"
cat "$REPORT"
echo "XR_BANK_RC=$failed $(date '+%F %T')"
exit $failed
