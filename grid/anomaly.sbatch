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
#   pack    the selection and the holdout resolved to CTs and masks (the release masks of VerSe and
#           CTSpinoPelvic1K, else the existing relabelled SPINEPS copies, passed through spinesurg-ct-nnunet's
#           spineps_ids.py check --strict in the spineps conda environment; never TotalSegmentator, the
#           owner's word of 2026-10-26), every mask rewritten to the 28 canonical ids (tools/nifti_label.py),
#           countable and complete measured per CT, the splits with the frozen validation rule
#           (data/splits/anomaly-validation.json) and the G3 exclusion, and FleXray's two whole-volume
#           packages under the landing $DATA/flexray_pack (schwingnet_spine for the complete masks,
#           schwingnet_spine_partial for the rest) by fxr-dataset pack in a venv of grid/venv.sh
#           (tools/anomaly_pack.py). The admission under the size rule (grid/size-rule.sh) comes before
#           any byte lands, and a refusal is exit 5, which the gate queues again at the same commit.
#           This stage holds no HOLD: it runs from a copy of its code under $ANOMALY_ROOT/pack, so the
#           checkout may move under it, which its report notes.
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
case "$STAGE" in select|timing|pack) ;; *) echo "anomaly: STAGE is select, timing or pack (the other stages are not built yet)"; echo "SN_ANOMALY_RC=64"; exit 64 ;; esac
# The pack stage's switches, each a committed default flipped by pull request, since a gate word
# carries no option: the G3 split that names the transitional val and test persons, whether a test
# or holdout row that cannot be packed stops the stage, the collections whose counts the owner does
# not trust as ground truth (2026-10-26 00:16 UTC: CTSpinoPelvic1K), and the packager's pins.
G3_SPLIT=${G3_SPLIT:-$HOME/split_final.json}
ALLOW_PARTIAL_TEST=${ALLOW_PARTIAL_TEST:-no}
DISTRUST=${DISTRUST:-ctsp}
PACK_PIN="flexray==1.0.2 h5py thunderpack nibabel"
REPORT=$REPO/grid/logs/ANOMALY-$STAGE.md
OUT=$ANOMALY_ROOT/$STAGE
mkdir -p "$REPO/grid/logs" "$OUT"
cd "$REPO" || exit 2
export PYTHONNOUSERSITE=1
report() { echo "- $*" | tee -a "$REPORT.part"; }
finish() {
  local rc=$1 ended_at
  ended_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
  if [ "$ended_at" != "$started_at" ] && [ "${RAN_FROM_COPY:-}" = yes ]; then
    report "NOTE: the checkout moved from ${started_at:0:7} to ${ended_at:0:7} during the stage, which ran from its own copy of the code at ${started_at:0:7}, so its results stand"
  elif [ "$ended_at" != "$started_at" ]; then
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
RAN_FROM_COPY=""
# The pack stage copies its code first and never holds the checkout; the others run the checkout's.
if [ "$STAGE" = pack ]; then RAN_FROM_COPY=yes; else echo "${SLURM_JOB_ID:-$$} $started_at" > "$HOLD"; fi
unhold() { [ "$RAN_FROM_COPY" = yes ] || [ "$(awk '{ print $1; exit }' "$HOLD" 2>/dev/null)" != "${SLURM_JOB_ID:-$$}" ] || rm -f "$HOLD"; }
WORK=""
ADMITTED_JOB=""
settle_pack() {  # the pack's admission is settled once the stage ends, however it ends (grid/size-rule.sh)
  [ -n "$ADMITTED_JOB" ] && declare -F settle_admission > /dev/null || return 0
  settle_admission flexray_pack "$ADMITTED_JOB"
  ADMITTED_JOB=""
}
cleanup() { [ -z "$WORK" ] || rm -rf "$WORK"; settle_pack; unhold; }
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

pack_tool() {  # the stage's own copy of tools/anomaly_pack.py under the train-cpu interpreter
  "$PYDRV" "$CODE/tools/anomaly_pack.py" "$@"
}
pack_step() {  # pack_step NAME ARGS...: one step of the tool, its section kept as $OUT/<name>.md, its error line reported
  local name=$1
  shift
  pack_tool "$@" > /dev/null 2> "$OUT/$name.err" \
    || { report "FAILED: the $name step ($(tail -n 1 "$OUT/$name.err" | cut -c1-200))"; finish 1; }
}
pack_test_gate() {  # pack_test_gate WHEN [MASKS]: a test or holdout row that cannot be packed stops the stage unless allowed
  local n
  n=$(pack_tool testgate --rows "$OUT/rows.csv" ${2:+--masks "$2"} 2> /dev/null) || { report "FAILED: the test gate could not be read after the $1"; finish 1; }
  if [ "$n" = 0 ]; then
    report "test gate after the $1: 0 test/holdout rows unresolved or refused"
  elif [ "$ALLOW_PARTIAL_TEST" = yes ]; then
    report "test gate after the $1: $n test/holdout rows unresolved or refused, allowed (ALLOW_PARTIAL_TEST=yes)"
  else
    report "FAILED: $n test/holdout rows cannot be packed after the $1 (ALLOW_PARTIAL_TEST=yes lets the stage go on without them)"
    finish 1
  fi
}
folder_bytes() {  # folder_bytes FOLDER: what a folder holds by du, 0 where it cannot be read
  local bytes
  bytes=$(du -sb "$1" 2>/dev/null | cut -f1)
  echo "${bytes:-0}"
}
pack_box() {  # pack_box ARGS...: the packager's interpreter inside the container
  bash "$CODE/grid/box.sh" "$PACK_VENV/bin/python" "$@"
}
pack_one() {  # pack_one DATASET: fxr-dataset pack of one manifest into its package, resumed by digest, checked once
  local dataset=$1 manifest=$OUT/manifest-$1.yml pkg_dir=$LANDING/$1/thunder_dbs package=$LANDING/$1/thunder_dbs/v1 digest bytes rc pid
  [ -f "$manifest" ] || { report "package $dataset: no sample, nothing packed"; return 0; }
  digest=$(sha256sum < "$manifest" | cut -c1-16)
  if [ -d "$package" ] && [ "$(cat "$OUT/packed-$dataset.sha256" 2>/dev/null)" = "$digest" ]; then
    # Packed from this very manifest already: pack ran its own check on the package then, and a kept
    # package is checked again here, since the packager checks only what it writes.
    pack_box -m fxr.datasets check "$package" > "$OUT/check-$dataset.log" 2>&1 \
      || { report "FAILED: check of $dataset failed, exit $? ($(wc -l < "$OUT/check-$dataset.log") log lines)"; finish 1; }
    report "package $dataset: kept, manifest sha256 $digest, check ok"
    return 0
  fi
  if [ -d "$package" ]; then
    bytes=$(folder_bytes "$package")
    rm -rf "$package"
    report "package $dataset rebuilt: $bytes bytes removed"
  fi
  rm -f "$OUT/packed-$dataset.sha256"
  mkdir -p "$pkg_dir" || { report "FAILED: the package folder of $dataset could not be made under the landing"; finish 2; }
  SECONDS=0
  # In the background and waited for, so Slurm's TERM before the wall time (hpcworker sends it 120 s
  # ahead) reaches the packager, its temp folder and the admission's settling at once; a foreground
  # child would hold the signal past the kill wait.
  pack_box -m fxr.datasets pack "$manifest" "$package" > "$OUT/pack-$dataset.log" 2>&1 &
  pid=$!
  # shellcheck disable=SC2064
  trap "kill -TERM $pid 2>/dev/null; wait $pid 2>/dev/null; rm -rf '$pkg_dir'/.v1.fxr-pack-* '$pkg_dir'/.v1.fxr-backup-*; report 'TERMINATED: Slurm ended the stage inside the pack of $dataset, whose package is removed with its temp folder'; finish 143" TERM
  wait "$pid"
  rc=$?
  trap 'exit 143' TERM
  PACK_SECONDS=$(( PACK_SECONDS + SECONDS ))
  [ "$rc" = 0 ] || { report "FAILED: pack of $dataset exited $rc ($(wc -l < "$OUT/pack-$dataset.log") log lines)"; finish 1; }
  echo "$digest" > "$OUT/packed-$dataset.sha256"
  report "package $dataset: packed in $SECONDS s, manifest sha256 $digest"
}
project_one() {  # project_one DATASET: the manifest's stored labels compile into the 63-label model space before a GPU is spent on them
  local manifest=$OUT/manifest-$1.yml
  [ -f "$manifest" ] || return 0
  pack_box -c 'from fxr.datasets.remap import compile_training_label_remap_from_stored_labels as compile_remap
import json, sys, yaml
manifest = json.load(open(sys.argv[1]))
labels = yaml.safe_load(open(sys.argv[3]))["labels"]
compile_remap("schwingnet_spine_v1", manifest["dataset_name"], {int(k): v for k, v in manifest["stored_labels"].items()}, labels, config_root=sys.argv[2])' \
    "$manifest" "$CODE/grid/flexray/configs" "$CODE/grid/flexray/configs/models/schwingnet_spine_v1.yml" > "$OUT/projection-$1.log" 2>&1 \
    || { report "FAILED: the stored labels of $1 do not compile into the model labels ($(wc -l < "$OUT/projection-$1.log") log lines)"; finish 1; }
  report "projection $1: ok"
}

stage_pack() {
  local holdout=data/splits/anomaly-holdout.json validation=data/splits/anomaly-validation.json
  local selection=$ANOMALY_ROOT/select/selection.csv conda_sh=${CONDA_SH:-$HOME/mambaforge/etc/profile.d/conda.sh}
  local guard_tool=$SSN/tools/spineps_ids.py home=${PACK_HOME:-$HOME} name folder orphans bytes rc dataset rewrite_seconds
  LANDING=$DATA/flexray_pack
  PACK_SECONDS=0
  for name in holdout validation selection conda_sh guard_tool G3_SPLIT; do
    [ -f "${!name}" ] || { report "FAILED: the stage's input $name is not there (the gate names where each is read from)"; finish 2; }
  done
  report "selection: sha256 $(sha256sum < "$selection" | cut -c1-16), $(($(wc -l < "$selection") - 1)) rows"
  # Step 1: the code the stage runs is copied under its own folder and run from there, so the gate's
  # fast-forward of the checkout, which no HOLD stops here, changes nothing a later step reads.
  CODE=$OUT/code-${started_at:0:7}
  rm -rf "$CODE"
  mkdir -p "$CODE/tools" "$CODE/grid" \
    && cp tools/anomaly_pack.py tools/nifti_label.py tools/anomaly_route.py "$CODE/tools/" \
    && cp grid/venv.sh grid/box.sh grid/size-rule.sh "$CODE/grid/" && cp -r grid/flexray "$CODE/grid/flexray" \
    || { report "FAILED: the stage's code could not be copied under its folder"; finish 2; }
  # Step 2: the packager's environment, FleXray with thunderpack and nibabel beside train-gpu's torch.
  # shellcheck source=grid/venv.sh
  . "$CODE/grid/venv.sh"
  if [ -z "${PACK_VENV:-}" ]; then
    PACK_VENV=$(venv_for "$PACK_PIN") || { report "FAILED: the environment for $PACK_PIN could not be made"; finish 1; }
  fi
  pack_box -c 'import thunderpack, nibabel, fxr.datasets.cli' > "$OUT/probe.log" 2>&1 \
    || { report "FAILED: the pack environment lacks thunderpack, nibabel or fxr ($(wc -l < "$OUT/probe.log") log lines)"; finish 1; }
  report "environment: $PACK_PIN"
  # Step 3: every row resolved to its CT and mask; a test or holdout row that resolves to nothing stops the stage.
  pack_step rows rows --selection "$selection" --holdout "$holdout" --data "$DATA" --home "$home" \
    --registry "$REGISTRY/registry.csv" --harvest "$DATA/anomaly_harvest" --out "$OUT" --segmenter "${SEGMENTER:-spineps}"
  pack_test_gate rows
  # Step 4: the guard over every SPINEPS mask, in the spineps conda environment where its reader lives.
  pack_step guard-list guard-list --rows "$OUT/rows.csv" --out "$OUT"
  if [ -s "$OUT/guard-list.txt" ]; then
    # shellcheck disable=SC1090
    source "$conda_sh" && conda activate "${SPINEPS_ENV:-spineps}" || { report "FAILED: conda activate ${SPINEPS_ENV:-spineps} from the node's conda"; finish 2; }
    # xargs splits a long list over several runs, so the verdict is read from the lines, never from one exit
    xargs -a "$OUT/guard-list.txt" -d '\n' "${SPINEPS_PYTHON:-python}" "$guard_tool" check --strict > "$OUT/guard.txt" 2>&1
    conda deactivate 2>/dev/null || true
  else
    : > "$OUT/guard.txt"
  fi
  report "guard: $(wc -l < "$OUT/guard-list.txt") SPINEPS masks checked, $(grep -c '^OK   ' "$OUT/guard.txt") listed OK, $(grep -c '^FAIL ' "$OUT/guard.txt") refused"
  # Step 5: the landing swept of a packager's temp folders, then the admission before any byte lands
  # (grid/size-rule.sh, as grid/unpack.sbatch decides): what every ok row lands less the masks already
  # written, never a package, held while Slurm holds this job and settled when it ends.
  mkdir -p "$LANDING" || { report "FAILED: the landing flexray_pack could not be made under the data root"; finish 2; }
  orphans=0; bytes=0
  for folder in "$LANDING"/*/thunder_dbs/.v1.fxr-pack-* "$LANDING"/*/thunder_dbs/.v1.fxr-backup-*; do
    [ -d "$folder" ] || continue
    bytes=$(( bytes + $(folder_bytes "$folder") )); orphans=$(( orphans + 1 ))
    rm -rf "$folder"
  done
  report "orphans: $orphans folders, $bytes bytes removed"
  VOLUME=${VOLUME:-$LAB}
  # shellcheck source=grid/size-rule.sh
  . "$CODE/grid/size-rule.sh"
  # The rule reads the quota's attributes with the node's own python where getfattr is missing, as
  # grid/unpack.sbatch does, never the container's, which may not see the volume's attributes.
  if [ "${SIZE_RULE_STAND_INS:-}" = yes ]; then RULE_PYTHON=${XATTR_PYTHON:-$PYDRV}
  elif command -v python3 > /dev/null 2>&1; then RULE_PYTHON=python3
  else RULE_PYTHON=$PYDRV; fi
  # The size is read by the tool first, so a tool that fell over is a failure at this commit and never
  # reads as a refusal for room, which the gate would queue again at the same commit.
  pack_tool size --rows "$OUT/rows.csv" --landing "$LANDING" > "$OUT/size.txt" 2> "$OUT/size.err" \
    || { report "FAILED: the size step ($(tail -n 1 "$OUT/size.err" | cut -c1-200))"; finish 1; }
  report "size: $(head -n 1 "$OUT/size.txt" | sed 's/^- //' | cut -c1-200)"
  mark_queued flexray_pack "${SLURM_JOB_ID:-$$}"
  size_and_admit flexray_pack cat "$OUT/size.txt" > "$OUT/admission.log" 2>&1
  rc=$?
  tail -n 1 "$OUT/admission.log" > "$OUT/admission.txt"
  report "admission: $(cut -c1-300 "$OUT/admission.txt")"
  [ "$rc" = 0 ] || { report "the size rule refused the pack, so nothing was written; the gate queues the stage again at the same commit once there is room"; finish 5; }
  ADMITTED_JOB=${SLURM_JOB_ID:-$$}
  # Step 6: the masks rewritten to the canonical ids under the landing, a mask written once kept.
  mkdir -p "$LANDING/masks"
  SECONDS=0
  pack_step rewrite rewrite --rows "$OUT/rows.csv" --guard "$OUT/guard.txt" --masks "$LANDING/masks" --out "$OUT"
  rewrite_seconds=$SECONDS
  pack_test_gate masks "$OUT/masks.csv"
  # Step 7: the splits, the training list and the route check that no held-out or disputed person trains.
  pack_step split split --rows "$OUT/rows.csv" --masks "$OUT/masks.csv" --g3 "$G3_SPLIT" --validation "$validation" \
    --out "$OUT" --distrust "$DISTRUST" --uncounted "${UNCOUNTED:-pack}"
  pack_step trainval trainval --splits "$OUT/splits.csv" --out "$OUT"
  "$PYDRV" "$CODE/tools/anomaly_route.py" check --holdout "$holdout" --list "$OUT/trainval.csv" > "$OUT/check-route.txt" 2>&1 \
    || { report "FAILED: $(head -n 1 "$OUT/check-route.txt" | sed 's/ in .*//' | cut -c1-200)"; finish 1; }
  report "route check: $(head -n 1 "$OUT/check-route.txt" | sed 's/ in .*//' | cut -c1-200)"
  # Steps 8 to 10: a manifest, a package and the projection check per dataset.
  for dataset in schwingnet_spine schwingnet_spine_partial; do
    pack_step "manifest-$dataset" manifest --splits "$OUT/splits.csv" --masks "$OUT/masks.csv" --rows "$OUT/rows.csv" \
      --dataset "$dataset" --hu=-1000,2000 --out "$OUT"
  done
  ln -sfn "$LANDING" "$OUT/landing"
  for dataset in schwingnet_spine schwingnet_spine_partial; do
    pack_one "$dataset"
    project_one "$dataset"
  done
  settle_pack
  for dataset in schwingnet_spine schwingnet_spine_partial; do
    [ -d "$LANDING/$dataset/thunder_dbs/v1" ] && report "pack: $dataset $(folder_bytes "$LANDING/$dataset/thunder_dbs/v1") bytes on disk"
  done
  report "masks: $(folder_bytes "$LANDING/masks") bytes on disk; seconds: rewrite $rewrite_seconds, pack $PACK_SECONDS"
  # The sections, cut so the whole report stays inside the 200 lines the gate word reprints.
  for name in rows masks splits; do
    [ -f "$OUT/$name.md" ] && { echo; head -n 30 "$OUT/$name.md"; } >> "$REPORT.part"
  done
  for name in guard-list trainval manifest-schwingnet_spine manifest-schwingnet_spine_partial; do
    [ -f "$OUT/$name.md" ] && { echo; head -n 8 "$OUT/$name.md"; } >> "$REPORT.part"
  done
  finish 0
}

"stage_$STAGE"
