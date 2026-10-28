#!/bin/bash
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=12:00:00
# The DRR domain-gap study (tools/domain_gap.py, docs/research/drr-domain-gap/README.md) in three
# steps on the grid's GPU nodes. The owner cancelled the study's one job (Slurm 40802322, bench
# flexray_drr_gap: four CPUs beside a V100 for statistics that are bound by the CPU) at 2026-10-27
# 17:51 UTC with "cancel and shard requesting h200 / see the beethoven protocol for doing so", and
# added "make sure you are logging, and I want to see a visual representation of what is happening";
# at 2026-10-28 00:23 UTC the owner asked for 16 shards ("shard it to more gpus like 16") and dropped the
# H200 ("you can drop the requirement for h200 unless its a memory problem"). Memory is measured on
# a smaller card for prepare alone: the first send ran its render, images and features on a 16 GB
# V100. A shard's sixteen workers share one card for the MMD's permutations alone, which no run has
# measured on a small card, so a test the card has no room for runs with numpy on the CPU, its
# permutations drawn the same (tools/domain_gap.py, mmd_where_it_fits; DEVIATIONS.md item 9).
# grid/gate.sh's word `bench flexray_drr_gap` queues the three as job submit's gpu class on whichever
# of its partitions frees first, with STEP naming the step as BENCH names a benchmark to
# grid/bench.sbatch:
#
#   prepare  every stage of the study up to the features, as `run` did, then the analysis cut into
#            units (analysis/units.json, analysis/heads/, last analysis/PREPARED.json); one job
#   shard    one task of an array of DRR_GAP_TASKS (grid/gate.sh), afterany prepare: each claims
#            units atomically under analysis/claims/, beats while it works, takes over a stale claim,
#            tests its GPU before its first unit and stops after three failures in a row
#   merge    afterany the array: the join (results.json, the figures, summary.txt) and the report
#
# The Lab Recipe's rules it follows (artifacts/the-lab-recipe-1t2gvp/index.md): every step checks the
# frozen PREREG.md against its hash before it reads anything, and stops with exit 90 where it moved
# ("Pre-register and freeze"); every step runs one copy of the code, which prepare takes at the
# commit it starts on, so no step holds grid/logs/HOLD and the checkout may move under the study, as
# the anomaly route's pack stage runs ("Code and environment"); an empty or missing input stops a
# step with its own message and exit code, under set -uo pipefail and never set -e; the steps wait
# afterany and each reads a file to tell whether the one before it did its part (rule 3), and one
# whose input is not ready says so and exits 0 (rule 9); scratch and TMPDIR under /dev/shm, removed
# on exit (rule 4); results on the lab volume (rule 5); the array's claims, beats, stale takeover,
# GPU self-test and failure streak are the tool's (rule 8); never requeued (rule 10).
#
# Logging: the tool keeps <out>/PROGRESS.txt current, which the busy refusal of the word prints and
# the status word shows as its section "bench flexray_drr_gap, progress" while the study runs, its
# last lines the newest of the run log, which every step of the tool writes as it goes, line by line
# with the time (the owner's ask of 2026-10-28 00:23 UTC, "make sure there is realtime logging in
# the CLAIMS/REPORT"); each step's own lines go to <out>/analysis/steps/ (prepare.md,
# shard-<task>.md, merge.md), each tool's whole output to a log in the run folder. Only the merge
# writes the report, logs/BENCH-flexray_drr_gap.md: prepare's lines first, whose first line names
# prepare's job and the commit as grid/gate.sh's bench_job_of and bench_failed_on_older_code read
# them, a line per shard task, the merge's lines, the summary and the run log, at most 50 lines of
# it with the units' quarter marks, which tools/report.py carries into the CLAIM report. Only
# summary.txt, five record lines and at most 80 lines of numbers and group names, and the run log,
# lines of times, steps, nodes, cards, counts and unit names, leave the grid, each line through
# grid/redact.sed; the plan, results.json, RUNLOG.txt with the line of every unit this chain did
# and the logs name files or hold more and stay in the run folder, the owner's alone (umask 077);
# the figures go to W&B where the grid's key is found.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
BENCH_ROOT=${BENCH_ROOT:-$LAB/go2432/bench}
MODELS=${MODELS:-$LAB/go2432/models}
STEP=${STEP:-}
# The study's packages over train-gpu's torch, in a throwaway environment on the lab volume (grid/venv.sh).
DRR_GAP_PIN="flexray[train]==1.0.2 nanodrr==0.1.5 scikit-learn==1.9.1 umap-learn==0.5.12 numpy==2.4.6"
# What prepare copies at its commit and every step runs: the tools and the packages they import, the
# study's groups and the frozen split, the container and environment scripts, the masking filter,
# and the pre-registration with its hash.
CODE_PATHS=(tools src vendor data/domain_gap data/splits grid/box.sh grid/venv.sh grid/redact.sed
  docs/research/drr-domain-gap/PREREG.md docs/research/drr-domain-gap/PREREG.md.sha256)
case "$STEP" in prepare|shard|merge) ;; *) echo "drr-gap: STEP is prepare, shard or merge"; echo "SN_BENCH_RC=64"; exit 64 ;; esac
OUT=$BENCH_ROOT/flexray_drr_gap
ANALYSIS=$OUT/analysis
STEPS=$ANALYSIS/steps
REPORT=$REPO/grid/logs/BENCH-flexray_drr_gap.md
# The checkout's filter until a step has its copy of the code, the copy's after.
REDACT=$REPO/grid/redact.sed
WORKERS=${SLURM_CPUS_PER_TASK:-16}
mkdir -p "$REPO/grid/logs" "$OUT" || exit 2
# venv_for builds with pixi, which needs the checkout's pixi.toml where it runs; every tool runs from the copy.
cd "$REPO" || exit 2
# The run folder is the owner's alone: the plan names files and person keys, and every log of the
# study is written there too.
umask 077
chmod 700 "$OUT"
mkdir -p "$STEPS" "$ANALYSIS/logs" || exit 2
export PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1
# Triton builds a small C helper with gcc and -lcuda on its first GPU call, and under Apptainer's --nv
# the driver's libraries sit in /.singularity.d/libs (grid/bench.sbatch, job 40781587).
export TRITON_LIBCUDA_PATH=${TRITON_LIBCUDA_PATH:-/.singularity.d/libs}
W=/dev/shm/${USER:-$(id -un)}_drrgap_${SLURM_JOB_ID:-x}_${SLURM_ARRAY_TASK_ID:-0}
mkdir -p "$W" || exit 2
trap 'rm -rf "$W"' EXIT
trap 'exit 143' TERM
export TMPDIR=$W

STEP_FILE=""
report() { echo "- $*" | tee -a "$STEP_FILE"; }
step_end() {  # step_end RC: the step's exit line, last in its file, then the job's exit with RC
  report "exit $1 at $(date -u '+%F %T') UTC"
  echo "SN_BENCH_RC=$1"
  exit "$1"
}
gpu_line() {  # the first GPU nvidia-smi names, with its memory and driver, or nothing
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -n 1
}
prereg_frozen() {  # the copy's PREREG.md is the one frozen with its hash (Lab Recipe, "Pre-register and freeze")
  ( cd "$CODE/docs/research/drr-domain-gap" 2>/dev/null && sha256sum -c --status PREREG.md.sha256 )
}
study_venv() {  # the study's environment, made by the copy's grid/venv.sh, into venv
  # shellcheck source=grid/venv.sh
  . "$CODE/grid/venv.sh"
  venv=$(venv_for "$DRR_GAP_PIN")
}
ready_venv() {  # the study's environment where a step made it whole, into venv, building nothing
  # shellcheck source=grid/venv.sh
  . "$CODE/grid/venv.sh"
  venv=$(venv_ready "$DRR_GAP_PIN")
}
tool_argv() {  # the command that runs the copy's tools/domain_gap.py in the study's environment, inside the container
  # The copy is no checkout, so the run record's commit, its clean tree (git archive writes the
  # commit as it is) and the environment's pins come from here (tools/domain_gap.py, git_state and
  # record_lines), the pins spelled with spaces since the grid's filter rewrites an "=". env and
  # box.sh each exec the next, so the command's process is the container's starter.
  TOOL_ARGV=(env SN_GIT_HEAD="$started_at" SN_GIT_DIRTY=no SN_PINS="${DRR_GAP_PIN//==/ } over the train-gpu torch"
    bash "$CODE/grid/box.sh" "$venv/bin/python" "$CODE/tools/domain_gap.py")
}
study_tool() {  # study_tool VERB ARG...: the tool, for a verb that takes seconds
  tool_argv
  "${TOOL_ARGV[@]}" "$@"
}
TOOL=""
TOOL_GRACE=60
study_tool_waited() {  # study_tool_waited VERB ARG...: the tool for a step's long verb, in the background and waited on
  # job submit asks Slurm for TERM to the batch shell alone two minutes before the time limit
  # (--signal=B:TERM@120, hpcworker's framework/lib/jobs.sh), which a shell running a command in the
  # foreground holds until the command ends; a shell in wait runs its trap at once, and the step's
  # trap passes the TERM on (tool_stop), so the tool's own run log line says how it ended.
  local rc
  tool_argv
  "${TOOL_ARGV[@]}" "$@" &
  TOOL=$!
  wait "$TOOL"; rc=$?
  TOOL=""
  return "$rc"
}
tool_stop() {  # the TERM passed on to a waited tool, and up to TOOL_GRACE seconds for it to write its closing line and end
  local waited=0
  [ -n "$TOOL" ] || return 0
  kill -TERM "$TOOL" 2>/dev/null
  while kill -0 "$TOOL" 2>/dev/null && [ "$waited" -lt "$TOOL_GRACE" ]; do sleep 1; waited=$((waited + 1)); done
}
last_line_of() {  # last_line_of LOG: a log's last line, masked and cut, for a report line
  tail -n 1 "$1" 2>/dev/null | sed -r -f "$REDACT" | cut -c1-160
}
code_of() {  # the copy of the code prepare made and named in analysis/CODE, and its commit, into CODE and started_at
  CODE=$(cat "$ANALYSIS/CODE" 2>/dev/null)
  started_at=$(cat "$ANALYSIS/COMMIT" 2>/dev/null)
  [ -n "$CODE" ] && [ -d "$CODE" ] && [ -n "$started_at" ] || return 1
  REDACT=$CODE/grid/redact.sed
}
prepare_job() {  # the job prepare's step file names on its first line, read as grid/gate.sh's bench_job_of reads a report's
  sed -n '1s/.*: job \([0-9][0-9]*\) .*/\1/p' "$STEPS/prepare.md" 2>/dev/null
}
prepared_here() {  # prepare's step file is this chain's: the gate hands the shards and the merge prepare's job as PREPARE_JOB
  # An earlier chain's file is still there when this chain's prepare never started (a job it waited
  # on failed, or it was cancelled), and must not be read as this one's.
  [ -f "$STEPS/prepare.md" ] || return 1
  [ -z "${PREPARE_JOB:-}" ] || [ "$(prepare_job)" = "$PREPARE_JOB" ]
}
prepare_ended_well() {  # prepare's step file ends in exit 0
  [[ "$(tail -n 1 "$STEPS/prepare.md" 2>/dev/null)" =~ ^-\ exit\ 0\  ]]
}
weights_dir() {  # the FleXray bundle the fetch landed: the folder that holds ensemble.json, as grid/bench.sbatch finds it
  dirname "$(find "$DATA/hf_flexray_weights/raw" -maxdepth 3 -name ensemble.json -print -quit 2>/dev/null)"
}
samples_index() {  # the sample index the gate checked (INDEX), else the newest whole run's, as grid/gate.sh names it in CURRENT
  local out=${SAMPLES_OUT:-$DATA/_samples} current
  [ -z "${INDEX:-}" ] || { echo "$INDEX"; return; }
  current=$(cat "$out/CURRENT" 2>/dev/null)
  [ -n "$current" ] && echo "$out/$current/samples.sqlite"
}
mask_state() {  # mask_state NAME: where a segmenter's masks are, or that their folder is not there
  local name=$1
  if [ -d "$DATA/$name" ]; then echo "$name in $DATA/$name"
  elif [ "$name" = moose ]; then echo "$name absent, no $DATA/$name (bench flexray_drr_seg makes them)"
  else echo "$name absent, no $DATA/$name"; fi
}

step_prepare() {
  local gpu weights index imagenet rc
  STEP_FILE=$STEPS/prepare.md
  # A prepare starts the study over: what an earlier chain's steps said, its copy's name and its
  # marker that the analysis was cut into units go first, so no later step of this chain reads them.
  rm -rf "$STEPS" && mkdir -p "$STEPS" || exit 2
  # The earlier chain's run log goes too: the tool clears it only once it runs, and a prepare that
  # stops at a check before it must not leave the merge an earlier chain's lines as this one's.
  rm -f "$ANALYSIS/PREPARED.json" "$ANALYSIS/CODE" "$ANALYSIS/COMMIT" "$OUT/RUNLOG.txt"
  rm -rf "$ANALYSIS/runlog"
  started_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
  echo "# bench flexray_drr_gap: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${started_at:0:7}, $(date -u '+%F %T') UTC" | tee "$STEP_FILE"
  trap 'tool_stop; report "TERMINATED: Slurm ended prepare (its time, or a cancel)"; step_end 143' TERM
  [ -n "$started_at" ] || { report "FAILED: the checkout at $REPO names no commit"; step_end 2; }
  # The code every step runs, copied from the commit as git holds it, so the gate's fast-forward of
  # the checkout, which no HOLD stops, changes nothing a later step reads.
  CODE=$OUT/code-${started_at:0:7}
  rm -rf "$CODE"
  mkdir -p "$CODE" && git -C "$REPO" archive "$started_at" -- "${CODE_PATHS[@]}" | tar -x -C "$CODE" \
    || { report "FAILED: the study's code at ${started_at:0:7} could not be copied under its folder"; step_end 2; }
  { echo "$CODE" > "$ANALYSIS/CODE" && echo "$started_at" > "$ANALYSIS/COMMIT"; } \
    || { report "FAILED: the copy's name could not be written to analysis/CODE"; step_end 2; }
  REDACT=$CODE/grid/redact.sed
  report "code: commit $started_at copied to $CODE, which every step runs; no step holds the checkout"
  prereg_frozen || { report "STOP: PREREG.md changed since the freeze"; step_end 90; }
  report "PREREG.md: as frozen, sha256 $(cut -c1-16 "$CODE/docs/research/drr-domain-gap/PREREG.md.sha256")"
  gpu=$(gpu_line)
  [ -n "$gpu" ] || { report "FAILED: nvidia-smi names no GPU on $(hostname)"; step_end 4; }
  # Any card of the gpu class (the owner's word of 2026-10-28 00:23 UTC), named so each number can be
  # read against the card it ran on.
  report "GPU: $gpu"
  # The study's inputs, each named in the report, since its numbers are read against them. The gate
  # refused the word without them (grid/gate.sh, bench_inputs_missing); a miss here is a samples run
  # or a fetch that moved since, said and failed rather than run on part of the table.
  study_venv || { report "FAILED: the environment for $DRR_GAP_PIN could not be made"; step_end 1; }
  weights=$(weights_dir)
  [ -f "$weights/ensemble.json" ] || { report "FAILED: no ensemble.json under $DATA/hf_flexray_weights/raw"; step_end 2; }
  index=$(samples_index)
  [ -n "$index" ] && [ -f "$index" ] || { report "FAILED: no whole sample index under ${SAMPLES_OUT:-$DATA/_samples} (the gate word samples makes it)"; step_end 2; }
  [ -d "$DATA/totalsegmentator_v201" ] || { report "FAILED: no totalsegmentator_v201 under $DATA, the CTs the render groups draw"; step_end 2; }
  imagenet=$MODELS/resnet18-f37072fd.pth
  [ -s "$imagenet" ] || { report "FAILED: no ImageNet ResNet-18 file at $imagenet (the gate word start fetches it)"; step_end 2; }
  # FluXray is optional: the tool reads it when the fetch has landed it and skips its group with
  # that reason otherwise, so the study never waits for it.
  if [ -d "$DATA/hf_flexray_data/raw" ]; then report "FluXray: read from $DATA/hf_flexray_data/raw"
  else report "FluXray: not on the data root (fetch hf_flexray_data); the study skips its group with that reason"; fi
  # The masks are optional too: a DRR is a projection of the CT alone, so the groups that read no
  # label render without them, and the study skips a group whose segmenter's masks are absent,
  # or held for too few CTs to test a group, with that reason (the owner's word of 2026-10-27).
  report "masks: $(mask_state spineps); $(mask_state moose); a render group whose segmenter's masks are not read, or too few CTs have, is skipped with that reason"
  report "environment: $DRR_GAP_PIN; index: $index; weights: $weights; imagenet: $imagenet"
  study_tool_waited prepare --groups "$CODE/data/domain_gap/groups.json" --data-root "$DATA" --index "$index" --weights "$weights" \
    --imagenet "$imagenet" --out "$OUT" --device cuda --workers "$WORKERS" --frozen "$CODE/data/splits/test-persons.json" \
    --spineps "$DATA/spineps" --moose "$DATA/moose" > "$OUT/prepare.log" 2>&1; rc=$?
  [ "$rc" = 0 ] || { report "FAILED: domain_gap.py prepare ended $rc ($(last_line_of "$OUT/prepare.log"))"; step_end "$rc"; }
  # PREPARED.json is the one file a shard reads to tell that prepare finished (rule 3), so an exit 0
  # that left none is a failure here rather than the array's tasks finding nothing to claim.
  [ -s "$ANALYSIS/PREPARED.json" ] || { report "FAILED: domain_gap.py prepare ended 0 and wrote no analysis/PREPARED.json"; step_end 2; }
  report "prepared: analysis/PREPARED.json written, so the shards claim its units"
  step_end 0
}

TASK=${SLURM_ARRAY_TASK_ID:-0}
GPU=""
shard_end() {  # shard_end RC [WHY]: the task's one line, its step file whole, then the job's exit with RC
  echo "- shard $TASK: job ${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-none}}_$TASK on $(hostname), GPU ${GPU:-none named}, exit $1 at $(date -u '+%F %T') UTC${2:+: $2}" \
    | tee "$STEP_FILE"
  echo "SN_BENCH_RC=$1"
  exit "$1"
}
step_shard() {
  local log rc
  STEP_FILE=$STEPS/shard-$TASK.md
  log=$ANALYSIS/logs/shard-$TASK.log
  GPU=$(gpu_line)
  GPU=${GPU%%,*}
  trap 'tool_stop; shard_end 143 "Slurm ended the task (its time, or a cancel)"' TERM
  # Each worker is one thread: the tool runs WORKERS of them, and a BLAS pool in each would ask the
  # node for WORKERS times its CPUs.
  export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
  # Rule 9: a task whose input is not ready says so and exits 0, and the merge reports why.
  if ! code_of || [ ! -f "$ANALYSIS/PREPARED.json" ] || ! prepared_here; then
    shard_end 0 "nothing to claim, since prepare did not finish (no analysis/PREPARED.json, or no copy of the code, from this chain's prepare)"
  fi
  prereg_frozen || shard_end 90 "STOP: PREREG.md changed since the freeze"
  study_venv || shard_end 1 "FAILED: the environment for $DRR_GAP_PIN could not be made"
  study_tool_waited shard --out "$OUT" --task "$TASK" --tasks "${SLURM_ARRAY_TASK_COUNT:-1}" --workers "$WORKERS" --device cuda > "$log" 2>&1
  rc=$?
  [ "$rc" = 0 ] && shard_end 0
  shard_end "$rc" "$(last_line_of "$log")"
}

SUMMARY=""
RUN_LOG_LINES=50  # what the report carries of the run log (tools/domain_gap.py, RUNLOG_REPORT)
RUN_LOG_WHY="since the study's environment could not be made"  # each branch that ends before reading it says its own
run_log() {  # the run log as the report carries it, each line through the filter and indented, or why there is none
  local lines
  if [ -z "${venv:-}" ]; then
    echo "- run log: not read, $RUN_LOG_WHY"
    return 0
  fi
  lines=$(study_tool runlog --out "$OUT" 2>/dev/null | LC_ALL=C tr -cd '\12\40-\176' | sed -r -f "$REDACT" | head -n "$RUN_LOG_LINES")
  if [ -z "$lines" ]; then
    echo "- run log: none, since no step of the tool wrote a line of it"
    return 0
  fi
  echo "- run log, UTC: each step's lines as it wrote them while it ran, with the units' quarter marks"
  printf '%s\n' "$lines" | sed 's/^/  /'
}
shard_tasks() {  # how many tasks the array had: SHARD_TASKS from the gate, else the shard files there are
  case "${SHARD_TASKS:-}" in
    ""|*[!0-9]*) find "$STEPS" -maxdepth 1 -name 'shard-*.md' 2>/dev/null | wc -l ;;
    *) echo "$SHARD_TASKS" ;;
  esac
}
shard_lines() {  # one line per task of the array, its own or one saying it left none
  local task
  for task in $(seq 0 $(( $(shard_tasks) - 1 ))); do
    if [ -s "$STEPS/shard-$task.md" ]; then head -n 1 "$STEPS/shard-$task.md"
    else echo "- shard $task: left no line (it never started, or Slurm ended it before it could write one)"; fi
  done
}
merge_finish() {  # merge_finish RC [summary]: the report composed from every step's file and renamed into place, then the job's exit with RC
  local rc=$1 ended
  ended="$(date -u '+%F %T') UTC"
  {
    cat "$STEPS/prepare.md"
    ! prepare_ended_well || shard_lines
    cat "$STEP_FILE"
    if [ "${2:-}" = summary ]; then
      echo "- results: $OUT"
      printf '%s\n' "$SUMMARY" | head -n 85 | sed 's/^/  /'
    fi
    run_log
    echo "- exit $rc at $ended"
  } > "$REPORT.part"
  echo "- exit $rc at $ended" >> "$STEP_FILE"
  mv "$REPORT.part" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_BENCH_RC=$rc"
  exit "$rc"
}
step_merge() {
  local rc now
  STEP_FILE=$STEPS/merge.md
  : > "$STEP_FILE"
  # Cut short, the merge writes no report, so the next send of the word queues the study again.
  trap 'tool_stop; report "TERMINATED: Slurm ended the merge (its time, or a cancel), so no report is written"; step_end 143' TERM
  report "merge: job ${SLURM_JOB_ID:-none} on $(hostname)"
  if ! prepared_here; then
    # No report either: one would stand at this commit and keep the word from queueing the study
    # again, where a prepare that never ran said nothing worth keeping.
    report "FAILED: prepare${PREPARE_JOB:+ (job $PREPARE_JOB)} left no step file: it never started (a job it waited on failed, or it was cancelled), so no report is written and the next send of the word queues the study again"
    step_end 2
  fi
  if ! prepare_ended_well; then
    rc=$(tail -n 1 "$STEPS/prepare.md" | sed -n 's/^- exit \([0-9][0-9]*\) at .*/\1/p')
    [ -n "$rc" ] || { report "prepare left no exit line: Slurm ended it before it finished (its time or its memory, or a cancel); its log is $OUT/prepare.log"; rc=1; }
    report "the shards and the merge ran nothing of the study, since prepare did not end in exit 0"
    # The run log says how far prepare got: read with the environment prepare made, where it made it
    # whole and the copy's PREREG.md is still the frozen one, which every step checks before it
    # reads anything; nothing is built for it here.
    venv=""
    if ! code_of; then RUN_LOG_WHY="since prepare named no copy of the code to read it with"
    elif ! prereg_frozen; then RUN_LOG_WHY="since the copy's PREREG.md is not the one frozen"
    elif ! ready_venv; then venv=""; RUN_LOG_WHY="since prepare made no environment to read it with"
    fi
    merge_finish "$rc"
  fi
  RUN_LOG_WHY="since the merge stopped before it read the run folder"
  code_of || { report "FAILED: prepare ended well but analysis/CODE names no copy of the code"; merge_finish 2; }
  prereg_frozen || { report "STOP: PREREG.md changed since the freeze"; merge_finish 90; }
  RUN_LOG_WHY="since the study's environment could not be made"
  now=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
  [ "$now" = "$started_at" ] \
    || report "NOTE: the checkout is at ${now:0:7} now; every step ran from the copy at ${started_at:0:7}, so the results stand"
  study_venv || { report "FAILED: the environment for $DRR_GAP_PIN could not be made"; merge_finish 1; }
  study_tool_waited merge --out "$OUT" --groups "$CODE/data/domain_gap/groups.json" > "$ANALYSIS/logs/merge.log" 2>&1; rc=$?
  [ "$rc" = 0 ] || { report "FAILED: domain_gap.py merge ended $rc ($(last_line_of "$ANALYSIS/logs/merge.log"))"; merge_finish "$rc"; }
  # The summary, five record lines and at most 80 of numbers and group names, each through the filter the gate word
  # status applies to every log line, and the report carries it whole.
  SUMMARY=$(study_tool summary --out "$OUT" 2>&1 | sed -r -f "$REDACT"); rc=$?
  printf '%s\n' "$SUMMARY"
  merge_finish "$rc" summary
}

"step_$STEP"
