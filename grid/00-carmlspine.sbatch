#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=04:00:00
# C-ArmLSpine's bank ingested as two shards (issue #53): the real X-ray builders' bank at
# realxray/carmlspine is split by case, and its own split does not follow data/splits/test-persons.json,
# which freezes case42, case121, case136, case134 and case39 as test persons, so the bank is read
# whole twice: once keeping every person but the frozen ones (a train shard) and once keeping the
# frozen ones alone (a test shard). tools/ingest.py refuses a train shard that holds a frozen person
# and a test shard that holds anyone else, so the two passes are the rule, not a choice of ours.
# A kind already ingested is skipped: the same bank under a later date would be a second shard of
# the same frames, which the catalog keeps beside the first. No --supersedes, since the two shards
# are siblings and neither replaces the other. The report is logs/00-carmlspine-STAGE-REPORT.md.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
DATA_ROOT=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
BANK=${BANK:-$DATA_ROOT/realxray/carmlspine}
ROOT=$DATA_ROOT/carmlspine
PYDRV=${PYDRV:-$REPO/grid/bin/train-cpu-python}
REPORT=logs/00-carmlspine-STAGE-REPORT.md
COMMIT=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo 0000000)
DATE=$(date '+%F')
export PYTHONNOUSERSITE=1
mkdir -p logs
report() { echo "- $*" | tee -a "$REPORT"; }
echo "# C-ArmLSpine ingest: $(date '+%F %T'), job ${SLURM_JOB_ID:-none} on $(hostname), commit $COMMIT" > "$REPORT"
[ -d "$BANK" ] || { report "FAILED: no bank at $BANK"; echo "SN_CARMLSPINE_RC=1"; exit 1; }
already() {  # already KIND: a shard of that kind is on disk for this source
  grep -lqs "\"kind\": *\"$1\"" "$ROOT"/shards/*/MANIFEST.json 2>/dev/null
}
rc=0
for pass in "train unfrozen" "test frozen"; do
  set -- $pass
  kind=$1 persons=$2
  if already "$kind"; then
    report "$kind ($persons persons): a $kind shard is already under $ROOT/shards; skipped"; continue
  fi
  if out=$("$PYDRV" "$REPO/tools/ingest.py" run --bank "$BANK" --source carmlspine --kind "$kind" \
        --persons "$persons" --date "$DATE" --code-commit "$COMMIT" --grid-root "$ROOT" 2>&1); then
    echo "$out"
    said=$(echo "$out" | "$PYDRV" -c "import json,sys; d=json.load(sys.stdin); print(d['shard'], d['outcome'], d['frames_kept'], 'frames,', d['persons'], 'persons,', d['labels'], 'labels; persons left out:', d.get('persons_left_out'), '; verified:', d.get('verified'))" 2>&1)
    report "$kind ($persons persons): $said"
  else
    echo "$out"; report "$kind ($persons persons) refused: $(echo "$out" | tail -n 1)"; rc=1
  fi
done
echo "SN_CARMLSPINE_RC=$rc"
exit $rc
