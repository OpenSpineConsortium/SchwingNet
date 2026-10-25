#!/bin/bash
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=02:00:00
# One stage of the SPINEPS to FleXray anomaly route (#398, the owner's word and count of 2026-10-25
# 21:22 UTC: seven jobs, two CPU and five GPU, docs/research/spineps-anomaly-route.md). grid/gate.sh's
# word `anomaly <stage>` queues it with STAGE, the stage, in the environment, as the class the stage
# names. Built so far:
#
#   select  the CT finder scored again on the grid's own copy of the VerSe screen against the frozen
#           holdout (data/splits/anomaly-holdout.json), and the selection: every read or two-labeller
#           variant person of the transitional registry and of each anomaly harvest collection, the
#           held-out and disputed persons refused, the paired real-frame persons kept for testing, and
#           normal counts drawn by the holdout's rank until variants are 30 percent (tools/anomaly_route.py)
#
# Standard library Python only, run with the train-cpu environment's interpreter inside the
# container (PYDRV, grid/bin/train-cpu-python). The selection list stays on the lab volume under
# $ANOMALY_ROOT/<stage>/; the report, logs/ANOMALY-<stage>.md, carries only counts and digests, and
# the next `anomaly <stage>` prints it. Not requeued (--no-requeue from the gate). The checkout holds
# still while the stage lasts, as for a benchmark (grid/logs/HOLD), and a stage whose checkout moved
# anyway is failed, since its report names the commit it began on.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
ANOMALY_ROOT=${ANOMALY_ROOT:-$LAB/go2432/anomaly}
# The anomaly harvest's own records: the transitional registry and the VerSe screen, as the
# spinesurg-ct-nnunet clone on the grid holds them (its branch L6_Class).
SSN=${SSN:-$HOME/spinesurg-ct-nnunet}
REGISTRY=$SSN/SchwingNet/results/transitional_registry
PYDRV=${PYDRV:-$REPO/grid/bin/train-cpu-python}
STAGE=${STAGE:-}
case "$STAGE" in select) ;; *) echo "anomaly: STAGE is select (the other stages are not built yet)"; echo "SN_ANOMALY_RC=64"; exit 64 ;; esac
REPORT=$REPO/grid/logs/ANOMALY-$STAGE.md
OUT=$ANOMALY_ROOT/$STAGE
mkdir -p "$REPO/grid/logs" "$OUT"
cd "$REPO" || exit 2
export PYTHONNOUSERSITE=1
report() { echo "- $*" | tee -a "$REPORT.part"; }
finish() {
  local rc=$1 ended_at
  ended_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
  if [ "$ended_at" != "$started_at" ]; then
    report "FAILED: the checkout moved from ${started_at:0:7} to ${ended_at:0:7} during the stage, so a later step may have run the newer code while this report names the older; its results are not used"
    [ "$rc" != 0 ] || rc=3
  fi
  report "exit $rc at $(date -u '+%F %T') UTC"
  mv "$REPORT.part" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_ANOMALY_RC=$rc"
  exit "$rc"
}
started_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
echo "# anomaly $STAGE: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${started_at:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"
[ -n "$started_at" ] || { report "FAILED: the checkout at $REPO names no commit"; finish 2; }
HOLD=$REPO/grid/logs/HOLD
echo "${SLURM_JOB_ID:-$$} $started_at" > "$HOLD"
unhold() { [ "$(awk '{ print $1; exit }' "$HOLD" 2>/dev/null)" != "${SLURM_JOB_ID:-$$}" ] || rm -f "$HOLD"; }
trap unhold EXIT
trap 'exit 143' TERM

holdout=data/splits/anomaly-holdout.json
screen=$REGISTRY/verse/screened.csv
[ -f "$holdout" ] || { report "FAILED: no $holdout at this commit"; finish 2; }
[ -f "$screen" ] || { report "FAILED: no VerSe screen at $screen (the spinesurg-ct-nnunet clone at $SSN)"; finish 2; }
[ -f "$REGISTRY/registry.csv" ] || { report "FAILED: no transitional registry at $REGISTRY/registry.csv"; finish 2; }
# The holdout was drawn from the clone's committed screen; a grid copy that differs is reported, not used silently.
frozen=$("$PYDRV" -c 'import json, sys; print(json.load(open(sys.argv[1]))["inputs"]["screen"]["sha256"])' "$holdout" 2>/dev/null)
here=$(sha256sum < "$screen" | cut -d' ' -f1)
if [ "$frozen" = "$here" ]; then report "the VerSe screen is the one the holdout was drawn from (${here:0:12})"
else report "NOTE: the grid's VerSe screen (${here:0:12}) is not the one the holdout was drawn from (${frozen:0:12}); the score below reads the grid's"; fi
harvests=$(find "$DATA/anomaly_harvest" -mindepth 2 -maxdepth 2 -name rows.csv 2>/dev/null | wc -l)
report "anomaly harvest collections with a rows.csv: $harvests under $DATA/anomaly_harvest"

"$PYDRV" tools/anomaly_route.py score --screen "$screen" --holdout "$holdout" > "$OUT/score.md" 2> "$OUT/score.err" \
  || { report "FAILED: the score ($(tail -n 1 "$OUT/score.err" | cut -c1-200))"; finish 1; }
"$PYDRV" tools/anomaly_route.py select --registry "$REGISTRY/registry.csv" --harvest "$DATA/anomaly_harvest" --holdout "$holdout" \
  --out "$OUT" > "$OUT/selection.md" 2> "$OUT/select.err" \
  || { report "FAILED: the selection ($(tail -n 1 "$OUT/select.err" | cut -c1-200))"; finish 1; }
"$PYDRV" tools/anomaly_route.py check --holdout "$holdout" --list "$OUT/selection.csv" > "$OUT/check.txt" 2>&1 \
  || { report "FAILED: $(head -n 1 "$OUT/check.txt" | cut -c1-200)"; finish 1; }
report "selection: $OUT/selection.csv, sha256 $(sha256sum < "$OUT/selection.csv" | cut -c1-16), $(($(wc -l < "$OUT/selection.csv") - 1)) CTs; $(cat "$OUT/check.txt")"
{ echo; cat "$OUT/score.md"; echo; cat "$OUT/selection.md"; } >> "$REPORT.part"
finish 0
