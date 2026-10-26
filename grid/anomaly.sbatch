#!/bin/bash
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=02:00:00
# One stage of the SPINEPS to FleXray anomaly route (#398, the owner's word and count of 2026-10-25
# 21:22 UTC: seven jobs, two CPU and five GPU, docs/research/spineps-anomaly-route.md). grid/gate.sh's
# word `anomaly <stage>` queues it with STAGE, the stage, in the environment, as the class the stage
# names and with the job options the stage asks (grid/gate.sh, anomaly_options). Built so far:
#
#   select  the CT finder scored again on the grid's own copy of the VerSe screen against the frozen
#           holdout (data/splits/anomaly-holdout.json), and the selection: every read or two-labeller
#           variant person of the transitional registry and of each anomaly harvest collection, the
#           held-out and disputed persons refused, the paired real-frame persons kept for testing, and
#           normal counts drawn by the holdout's rank until variants are 30 percent (tools/anomaly_route.py)
#   timing  the paired CTs that lack a VERIDAH-named SPINEPS mask, listed from the records of the four
#           test-only sets (COBRA2026, C-ArmLSpine, DeepFluoro, LUMOS), and SPINEPS timed on ten of them,
#           drawn by rank among those that already have a NIfTI, through spinesurg-ct-nnunet's runner in
#           the grid's own spineps conda environment as its slurm/spineps_cases.sh ran it; the estimate
#           for the production array closes the report and asks nothing, since that array is not
#           approved (tools/anomaly_timing.py). Step 0 is chapter 21's GPU self-test: a node whose card
#           the environment's torch 2.6 cu124 build cannot run (Blackwell, ymh3 and ymh4) is left with
#           exit 4 before a CT is staged, and the gate queues the stage again at the same commit.
#
# Standard library Python only in the tools, run with the train-cpu environment's interpreter inside
# the container (PYDRV, grid/bin/train-cpu-python); SPINEPS itself runs on the node in the spineps
# conda environment (CONDA_SH, SPINEPS_ENV), with the models under SPINEPS_SEGMENTOR_MODELS. What a
# stage writes stays on the lab volume under $ANOMALY_ROOT/<stage>/; the report, logs/ANOMALY-<stage>.md,
# carries only counts, seconds and digests, and the next `anomaly <stage>` prints it. Not requeued
# (--no-requeue from the gate). The checkout holds still while the stage lasts, as for a benchmark
# (grid/logs/HOLD), and a stage whose checkout moved anyway is failed, since its report names the
# commit it began on.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
ANOMALY_ROOT=${ANOMALY_ROOT:-$LAB/go2432/anomaly}
# The anomaly harvest's own records: the transitional registry and the VerSe screen, as the
# spinesurg-ct-nnunet clone on the grid holds them (its branch L6_Class), and its SPINEPS runner.
SSN=${SSN:-$HOME/spinesurg-ct-nnunet}
REGISTRY=$SSN/SchwingNet/results/transitional_registry
PYDRV=${PYDRV:-$REPO/grid/bin/train-cpu-python}
STAGE=${STAGE:-}
case "$STAGE" in select|timing) ;; *) echo "anomaly: STAGE is select or timing (the other stages are not built yet)"; echo "SN_ANOMALY_RC=64"; exit 64 ;; esac
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
WORK=""
cleanup() { [ -z "$WORK" ] || rm -rf "$WORK"; unhold; }
trap cleanup EXIT
trap 'exit 143' TERM

stage_select() {
  local holdout screen frozen here harvests
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
}

stage_timing() {
  local smi verdict rc conda_sh runner models cases set failed
  # Step 0, chapter 21's rule 8: the card is read before anything is staged, and a node the spineps
  # environment cannot use is left with exit 4, which the gate reads as "queue it again" (word_anomaly).
  smi=$(nvidia-smi --query-gpu=name,compute_cap --format=csv,noheader 2>/dev/null | head -n 1) \
    || smi=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n 1)
  verdict=$("$PYDRV" tools/anomaly_timing.py gpu --smi "$smi"); rc=$?
  report "$verdict"
  [ "$rc" = 0 ] || finish "$rc"
  conda_sh=${CONDA_SH:-$HOME/mambaforge/etc/profile.d/conda.sh}
  runner=$SSN/benchmark/run_spineps_cases.py
  [ -f "$conda_sh" ] || { report "FAILED: no conda at $conda_sh, which holds the spineps environment"; finish 2; }
  [ -f "$runner" ] || { report "FAILED: no SPINEPS runner at $runner (the spinesurg-ct-nnunet clone at $SSN)"; finish 2; }
  "$PYDRV" tools/anomaly_timing.py inventory --data "$DATA" --work "${REALXRAY_WORK:-$DATA/realxray_work}" --out "$OUT" \
    > "$OUT/inventory.md" 2> "$OUT/inventory.err" \
    || { report "FAILED: the inventory ($(tail -n 1 "$OUT/inventory.err" | cut -c1-200))"; finish 1; }
  "$PYDRV" tools/anomaly_timing.py pick --inventory "$OUT/inventory.csv" --count "${TIMING_COUNT:-10}" --out "$OUT" \
    > "$OUT/pick.md" 2> "$OUT/pick.err" \
    || { report "FAILED: the pick ($(tail -n 1 "$OUT/pick.err" | cut -c1-200))"; finish 1; }
  report "inventory: $OUT/inventory.csv, sha256 $(sha256sum < "$OUT/inventory.csv" | cut -c1-16), $(($(wc -l < "$OUT/inventory.csv") - 1)) CTs"
  # SPINEPS runs on the node as it always has here (spinesurg-ct-nnunet slurm/spineps_cases.sh): the
  # spineps conda environment, the CT models under ~/spineps_models, each CT staged alone under
  # /dev/shm and its masks harvested to the lab volume. The runner exits 2 when a case failed; the
  # stage goes on to the estimate, which counts the failure, and the runner's log, which names cases
  # and paths, stays on the lab volume.
  # shellcheck disable=SC1090
  source "$conda_sh" && conda activate "${SPINEPS_ENV:-spineps}" || { report "FAILED: conda activate ${SPINEPS_ENV:-spineps} from $conda_sh"; finish 2; }
  export SPINEPS_SEGMENTOR_MODELS=${SPINEPS_SEGMENTOR_MODELS:-$HOME/spineps_models}
  models=$SPINEPS_SEGMENTOR_MODELS
  WORK=${TIMING_WORK:-/dev/shm/${USER:-go2432}_${SLURM_JOB_ID:-$$}_anomaly_timing}
  mkdir -p "$WORK" "$OUT/spineps"
  for cases in "$OUT"/cases-*.csv; do
    [ -f "$cases" ] || continue
    set=$(basename "$cases" .csv); set=${set#cases-}
    mkdir -p "$OUT/spineps/$set"
    "${SPINEPS_PYTHON:-python}" "$runner" --cases "$cases" --out_dir "$OUT/spineps/$set" --work "$WORK/$set" \
      --model_semantic "$models/CT_semantic" --model_instance "$models/CT_instance" --model_labeling "$models/ct_labeling" \
      > "$OUT/spineps/$set.log" 2>&1; rc=$?
    if [ "$rc" != 0 ]; then
      failed=$(grep -c '"ok": false' "$OUT/spineps/$set/timing_shard0.jsonl" 2>/dev/null || echo 0)
      report "NOTE: the runner over $set exited $rc with $failed failed cases; its log is $OUT/spineps/$set.log"
    fi
  done
  rm -rf "$WORK"
  "$PYDRV" tools/anomaly_timing.py estimate --timing-dir "$OUT/spineps" --inventory "$OUT/inventory.csv" --gpu "$verdict" \
    > "$OUT/estimate.md" 2> "$OUT/estimate.err"; rc=$?
  { echo; cat "$OUT/inventory.md" "$OUT/pick.md" "$OUT/estimate.md"; } >> "$REPORT.part"
  [ "$rc" = 0 ] || { report "FAILED: no CT finished, so the timing decided nothing ($(tail -n 1 "$OUT/estimate.err" | cut -c1-200))"; finish 1; }
  finish 0
}

"stage_$STAGE"
