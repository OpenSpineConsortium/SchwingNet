#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
# The auto-anatomist screen (docs/research/autoanatomist-screen/PREREG.md): every arm of a plan
# under grid/screens/ trained at every seed on the plan's gold tier 3 CTs, one trial on one card,
# each read on the plan's validation CTs every few epochs, then the join, which reads every trial's
# entry and decides each arm against the null (src/schwingnet/autoanatomist_screen.py). The owner
# asked on 2026-10-30 for training on the gold tier 3 set on the grid and an evaluation of the
# annealer, every arm a block screened in parallel on short runs; grid/gate.sh's word
# `autoanatomist <plan>` queues it with PART naming the part:
#
#   series  every trial of the plan one after another on one card, then the join on the same node;
#           one GPU job, for a plan laid out as a series (the smoke, the owner's one short GPU smoke
#           of 2026-10-30 03:20 UTC)
#   trial   one task of a GPU array, a trial each, for a plan laid out as an array
#   join    afterany the array, on a CPU node: the join and the report
#
# Every part runs on a launched flow (the owner's rule of 2026-10-29): this driver does what must be
# done on the node, copies the code at the commit the gate sent, makes the trial's environment and
# starts flows/launch.py autoanatomist from the copy, whose run is held to the frozen PREREG and
# whose join writes the screen's CLAIM 2024 and REFORMS report (flows/autoanatomist.py). Every part
# of one send works in one folder, $AUTOANATOMIST_ROOT/<plan>/<chain>/, the chain being the send's
# array or series job, so no send reads what another left; the part that runs the join, the series
# or the join, writes the report, logs/AUTOANATOMIST-<plan>.md, and the next send prints it.
#
# The Lab Recipe's rules it follows (artifacts/the-lab-recipe-1t2gvp/index.md): the code is a copy
# of the gate's commit (git archive with its COPY.txt record), so no part holds grid/logs/HOLD and
# the checkout may move under the screen; the trials of an array share the copy, made once under a
# name of its own and renamed into place, and the environment, made once under a lock; the frozen
# PREREG.md is checked against its hash before anything is read (exit 90); a missing input stops a
# part with its own message and exit, under set -uo pipefail and never set -e; scratch and TMPDIR
# under /dev/shm, removed on exit; results on the lab volume, the folder the owner's alone (umask
# 077); never requeued (--no-requeue from the gate). The trial's packages go into a throwaway
# environment over train-gpu's Python 3.11 (grid/venv.sh), never into pixi.lock: they are
# schwingnet.autoanatomist_screen.PINS, which the trial holds its environment to and
# tests/test_gate.py holds the line below to.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
ROOT=${AUTOANATOMIST_ROOT:-$LAB/go2432/autoanatomist}
# The kind the parts run as, with its frozen PREREG's folder and its flow's class: autoanatomist, the
# first screen, unless grid/autoanatomist2.sbatch, the second screen's job script, names autoanatomist2,
# whose runs are held to a PREREG of their own (flows/registry.txt, flows/autoanatomist2.py).
KIND=${AUTOANATOMIST_KIND:-autoanatomist}
case "$KIND" in
  autoanatomist) STUDY_DIR=docs/research/autoanatomist-screen FLOW_CLASS=AutoanatomistFlow ;;
  autoanatomist2) STUDY_DIR=docs/research/autoanatomist-screen2 FLOW_CLASS=Autoanatomist2Flow ;;
  *) echo "autoanatomist: AUTOANATOMIST_KIND is autoanatomist or autoanatomist2, not $KIND; nothing ran"; echo "SN_AUTOANATOMIST_RC=64"; exit 64 ;;
esac
AUTOANATOMIST_PIN="jax[cuda12]==0.10.2 flax==0.12.8 optax==0.2.8 orbax-checkpoint==0.12.8 numpy==2.4.6 scipy==1.17.1 nibabel==5.3.2"
# What every part runs, copied at the gate's commit: the tools and the packages they import, the
# vendored auto-anatomist package the trial trains with, the flows and the launcher with their
# registry, the plans, the frozen split, the report's checklists and the licence register, the
# locked environment the run's code is named by, the container and environment scripts, this
# script, the masking filter, and the pre-registration with its hash.
CODE_PATHS=(tools src vendor flows data/splits data/reporting data/licences.json pixi.toml pixi.lock
  grid/box.sh grid/venv.sh grid/redact.sed grid/autoanatomist.sbatch grid/autoanatomist grid/screens
  "$STUDY_DIR/PREREG.md" "$STUDY_DIR/PREREG.md.sha256")
# The copy's record of its commit and files (tools/run_code.py and flows/launch.py, COPY_RECORD).
COPY_RECORD=COPY.txt
PART=${PART:-}
PLAN=${PLAN:-}
COMMIT=${AUTOANATOMIST_COMMIT:-}
TASK=${SLURM_ARRAY_TASK_ID:-0}
TASKS=${TRIAL_TASKS:-}
# The chain: the array's job for a trial and for the join the gate hands it, the series' own job.
case "$PART" in
  trial) CHAIN=${SLURM_ARRAY_JOB_ID:-} ;;
  join) CHAIN=${TRIALS_JOB:-} ;;
  *) CHAIN=${SLURM_JOB_ID:-} ;;
esac
refuse() { echo "autoanatomist: $*; nothing ran"; echo "SN_AUTOANATOMIST_RC=64"; exit 64; }
case "$PART" in trial|join|series) ;; *) refuse "PART is trial, join or series" ;; esac
case "$PLAN" in ""|*[!a-z0-9_]*) refuse "PLAN is the name of a plan under grid/screens/" ;; esac
[[ $COMMIT =~ ^[0-9a-f]{40}$ ]] || refuse "AUTOANATOMIST_COMMIT is the full commit the gate sent"
case "$TASKS" in ""|0|*[!0-9]*) refuse "TRIAL_TASKS is the plan's count of trials" ;; esac
case "$CHAIN" in ""|*[!0-9]*) refuse "the chain is the send's Slurm job (for the join, TRIALS_JOB)" ;; esac
[ "$TASK" -lt "$TASKS" ] 2>/dev/null || refuse "the task $TASK is outside the plan's $TASKS trials"
OUT=$ROOT/$PLAN/$CHAIN
STEPS=$OUT/steps
LOGS=$OUT/logs
REPORT=$REPO/grid/logs/AUTOANATOMIST-$PLAN.md
mkdir -p "$REPO/grid/logs" || exit 2
# venv_for builds with pixi, which needs the checkout's pixi.toml where it runs; every tool runs from the copy.
cd "$REPO" || exit 2
# The chain's folder is the owner's alone: the plans name CTs and person keys, and every log is written there.
umask 077
mkdir -p "$STEPS" "$LOGS" || exit 2
chmod 700 "$OUT"
export PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1
W=/dev/shm/${USER:-$(id -un)}_autoanatomist_${SLURM_JOB_ID:-$$}_$TASK
mkdir -p "$W" || exit 2
trap 'rm -rf "$W"' EXIT
trap 'exit 143' TERM
# The trial's scratch, its spine-only label copies and its cache of crops, goes here with TMPDIR.
export TMPDIR=$W
job_began=$(date +%s)

STEP_FILE=""
report() { echo "- $*" >> "$STEP_FILE"; echo "- $*"; }
step_end() {  # step_end RC: a trial's exit line, last in its file, then the job's exit with RC
  trap '' TERM
  report "exit $1 at $(date -u '+%F %T') UTC"
  echo "SN_AUTOANATOMIST_RC=$1"
  exit "$1"
}
report_end() {  # report_end RC: the report's exit line, then the report renamed into place, kept beside the steps, and the job's exit with RC
  trap '' TERM
  report "exit $1 at $(date -u '+%F %T') UTC"
  cp "$STEP_FILE" "$STEPS/join.md" 2>/dev/null
  mv "$STEP_FILE" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_AUTOANATOMIST_RC=$1"
  exit "$1"
}
part_end() { if [ "$PART" = trial ]; then step_end "$1"; else report_end "$1"; fi; }
gpu_line() {  # the first GPU nvidia-smi names, with its memory and driver, or nothing
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -n 1
}
prereg_frozen() {  # the copy's PREREG.md is the one frozen with its hash (Lab Recipe, "Pre-register and freeze")
  ( cd "$CODE/$STUDY_DIR" 2>/dev/null && sha256sum -c --status PREREG.md.sha256 )
}
copy_code() {  # the chain's copy of the code at the gate's commit, into CODE, made once whichever part comes first
  # The tasks of an array start together: each extracts under a name of its own and renames it into
  # place, which only the first rename does, the others' copies of the same commit going away.
  local made=$OUT/.code-${COMMIT:0:7}.${SLURM_JOB_ID:-$$}_$TASK
  CODE=$OUT/code-${COMMIT:0:7}
  [ -f "$CODE/$COPY_RECORD" ] && return 0
  rm -rf "$made"
  mkdir -p "$made" && git -C "$REPO" archive "$COMMIT" -- "${CODE_PATHS[@]}" | tar -x -C "$made" \
    && { echo "$COMMIT"; git -C "$REPO" -c core.quotePath=false ls-tree -r --name-only "$COMMIT" -- "${CODE_PATHS[@]}"; } > "$made/$COPY_RECORD" \
    || { rm -rf "$made"; return 1; }
  mv -T "$made" "$CODE" 2>/dev/null || rm -rf "$made"
  [ -f "$CODE/$COPY_RECORD" ]
}
venv_once() {  # venv_once PINS: venv_for under a lock, since venv_for removes and rebuilds a half-made environment in place
  local lock waited=0 rc
  lock=$(venv_path "$1").lock
  mkdir -p "$(dirname "$lock")" || return 1
  until mkdir "$lock" 2>/dev/null; do
    venv_ready "$1" && return 0
    # A lock an hour old is a builder Slurm killed; the next waiter takes it over.
    [ -z "$(find "$lock" -maxdepth 0 -mmin +60 2>/dev/null)" ] || rmdir "$lock" 2>/dev/null
    [ "$waited" -lt 3600 ] || return 1
    sleep 15
    waited=$((waited + 15))
  done
  venv_for "$1"
  rc=$?
  rmdir "$lock" 2>/dev/null
  return "$rc"
}
study_venv() {  # the trial's environment, made by the copy's grid/venv.sh, into venv
  # shellcheck source=grid/venv.sh
  . "$CODE/grid/venv.sh"
  venv=$(venv_once "$AUTOANATOMIST_PIN")
}
jax_on_gpu() {  # the environment's JAX sees a card, so a trial never trains on the CPU unawares
  bash "$CODE/grid/box.sh" "$venv/bin/python" -c 'import jax, sys; sys.exit(jax.default_backend() != "gpu")' > "$LOGS/jax-$TASK.log" 2>&1
}
node_ready() {  # node_ready gpu|cpu: the copy, the freeze, the plan, the card and the environment, before any flow
  copy_code || { report "FAILED: the code at ${COMMIT:0:7} could not be copied under $OUT"; part_end 2; }
  report "code: commit $COMMIT copied to $CODE, which every part of the chain runs"
  prereg_frozen || { report "STOP: PREREG.md changed since the freeze"; part_end 90; }
  report "PREREG.md: as frozen, sha256 $(cut -c1-16 "$CODE/$STUDY_DIR/PREREG.md.sha256")"
  [ -f "$CODE/grid/screens/$PLAN.json" ] || { report "FAILED: no grid/screens/$PLAN.json at ${COMMIT:0:7}"; part_end 2; }
  if [ "$1" = gpu ]; then
    # The card is read here, on the node, and not inside the container, whose nvidia-smi only --nv brings in.
    gpu=$(gpu_line)
    [ -n "$gpu" ] || { report "FAILED: nvidia-smi names no GPU on $(hostname)"; part_end 4; }
    report "GPU: $gpu"
  else
    export JAX_PLATFORMS=cpu
  fi
  study_venv || { report "FAILED: the environment for $AUTOANATOMIST_PIN could not be made"; part_end 1; }
  report "environment: $AUTOANATOMIST_PIN over train-gpu's Python"
  if [ "$1" = gpu ]; then
    jax_on_gpu || { report "FAILED: JAX in the environment sees no GPU ($(tail -n 1 "$LOGS/jax-$TASK.log" | cut -c1-160))"; part_end 4; }
  fi
}

# The launcher, started from the copy and waited on, so Slurm's TERM, two minutes before the time
# limit, reaches the trap at once and is passed on (launcher_stop).
LAUNCHER=""
LAUNCH_RC=""
LAUNCH_LOG=""
# How long the driver waits, after passing the TERM on, for the launcher to end: the launcher gives
# the flow's processes 60 s before it kills them (flows/launch.py, STOP_GRACE_SECONDS).
STEP_GRACE=80
launch_run() {  # launch_run NAME WORDS...: one run of the flow from the copy, its output in logs/launch-NAME.log and the job's log
  local follower
  LAUNCH_LOG=$LOGS/launch-$1.log
  shift
  : > "$LAUNCH_LOG"
  # Every path is absolute: the flow reads a relative one from the folder the launcher started in,
  # the checkout here, which may move under the screen, and the plan is the copy's.
  env SCHWINGNET="$CODE" bash "$CODE/grid/box.sh" "$venv/bin/python" "$CODE/flows/launch.py" "$KIND" --max-workers 1 -- \
    --plan "$CODE/grid/screens/$PLAN.json" --chain "$CHAIN" --out "$ROOT" "$@" >> "$LAUNCH_LOG" 2>&1 &
  LAUNCHER=$!
  tail -n +1 --pid="$LAUNCHER" -f "$LAUNCH_LOG" 2>/dev/null &
  follower=$!
  wait "$LAUNCHER"
  LAUNCH_RC=$?
  LAUNCHER=""
  wait "$follower" 2>/dev/null
}
launcher_stop() {  # the TERM passed on to the launcher, then up to STEP_GRACE seconds for it to end
  local waited=0
  [ -n "$LAUNCHER" ] || return 0
  kill -TERM "$LAUNCHER" 2>/dev/null
  while kill -0 "$LAUNCHER" 2>/dev/null && [ "$waited" -lt "$STEP_GRACE" ]; do sleep 1; waited=$((waited + 1)); done
}
flow_said() {  # flow_said LOG: the launcher's decision, then the flow's own lines, the last 20, found by their head wherever the line begins
  local decision
  decision=$(grep -m 1 '"decision":' "$1" 2>/dev/null)
  report "launcher: ${decision:-it printed no decision line} (exit $LAUNCH_RC)"
  # Metaflow's runtime heads each line a task prints with its time and [run/step/task (pid N)].
  sed -n 's/^\([^[]*\[[^]]*\] \)\{0,1\}AutoanatomistFlow: //p' "$1" 2>/dev/null | tail -n 20 | while IFS= read -r line; do report "$line"; done
}
page_of() {  # page_of LOG: where the run's progress page lies, from the datastore the decision names and the run the last line names
  local root id
  root=$(grep -m 1 '"decision":' "$1" 2>/dev/null | sed -n 's/.*"root": *"\([^"]*\)".*/\1/p')
  id=$(grep '"successful":' "$1" 2>/dev/null | tail -n 1 | sed -n "s/.*\"run\": *\"$FLOW_CLASS\\/\\([0-9A-Za-z_-]*\\)\".*/\\1/p")
  echo "${root:-(the datastore the launcher names)}/progress/$FLOW_CLASS/${id:-<run>}/index.html"
}
trial_line() {  # trial_line T: how trial T of this chain ended, from its step file
  local file=$STEPS/trial-$1.md last
  [ -f "$file" ] || { echo "trial $1: no step file, so it never started (cancelled, or a job it waited on failed)"; return; }
  last=$(tail -n 1 "$file")
  case "$last" in
    "- exit "*) echo "trial $1: ${last#- }; $(grep -m 1 '^- trial .*: exit ' "$file" | sed 's/^- //')" ;;
    *) echo "trial $1: its step file has no exit line, so Slurm ended it past its TERM (its time or its memory)" ;;
  esac
}
join_said() {  # what the join's run left: its lines, the summary it wrote in this job, the figures and the page
  local summary=$OUT/SUMMARY.md
  flow_said "$LAUNCH_LOG"
  if [ "$(stat -c %Y "$summary" 2>/dev/null || echo 0)" -ge "$job_began" ]; then
    { echo; echo "### SUMMARY.md"; echo; cat "$summary"; echo; } >> "$STEP_FILE"
  else
    report "SUMMARY.md: not written by this job (the join did not reach its end)"
  fi
  report "figures: $OUT/join/curves.png and finals.png, the CLAIM and REFORMS report $OUT/REPORT.md (Open OnDemand's Files app)"
  report "progress page: $(page_of "$LAUNCH_LOG")"
}

part_trial() {
  STEP_FILE=$STEPS/trial-$TASK.md
  echo "# autoanatomist $PLAN trial $TASK of $TASKS: job ${CHAIN}_$TASK on $(hostname), commit ${COMMIT:0:7}, $(date -u '+%F %T') UTC" > "$STEP_FILE"
  trap 'launcher_stop; report "TERMINATED: Slurm ended the trial (its time limit, or a cancel)"; step_end 143' TERM
  node_ready gpu
  launch_run "trial-$TASK" --part trial --task "$TASK" --tasks "$TASKS" --data "$DATA"
  flow_said "$LAUNCH_LOG"
  report "progress page: $(page_of "$LAUNCH_LOG")"
  step_end "$LAUNCH_RC"
}
part_series() {
  local t
  STEP_FILE=$REPORT.part
  echo "# autoanatomist $PLAN: job $CHAIN on $(hostname), commit ${COMMIT:0:7}, $(date -u '+%F %T') UTC" > "$STEP_FILE"
  trap 'launcher_stop; report "TERMINATED: Slurm ended the series (its time limit, or a cancel)"; report_end 143' TERM
  node_ready gpu
  report "series: the plan's $TASKS trials one after another on this card, then the join; folder $OUT"
  for ((t = 0; t < TASKS; t++)); do
    launch_run "trial-$t" --part trial --task "$t" --tasks "$TASKS" --data "$DATA"
    report "trial $t: launcher exited $LAUNCH_RC; $(sed -n 's/^\([^[]*\[[^]]*\] \)\{0,1\}AutoanatomistFlow: \(trial .*: exit .*\)/\2/p' "$LAUNCH_LOG" | head -n 1)"
  done
  launch_run join --part join --tasks "$TASKS"
  join_said
  report_end "$LAUNCH_RC"
}
part_join() {
  local t
  STEP_FILE=$REPORT.part
  echo "# autoanatomist $PLAN: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${COMMIT:0:7}, $(date -u '+%F %T') UTC; the join of the trials' array $CHAIN" > "$STEP_FILE"
  trap 'launcher_stop; report "TERMINATED: Slurm ended the join (its time limit, or a cancel)"; report_end 143' TERM
  for ((t = 0; t < TASKS; t++)); do report "$(trial_line "$t")"; done
  node_ready cpu
  launch_run join --part join --tasks "$TASKS"
  join_said
  report_end "$LAUNCH_RC"
}

"part_$PART"
