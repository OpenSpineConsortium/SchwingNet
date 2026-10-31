#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
# TotalSegmentator's vertebrae on the gold tier 4 CTs (docs/research/gold4-totalseg/PREREG.md): every
# CT the census found showing C2's foot and the sacrum's top in the collections no release draws,
# segmented by TotalSegmentator 2.18.0 and set beside the census's SPINEPS mask of it
# (tools/gold4_totalseg_grid.py), on the owner's word of 2026-10-31 00:55 UTC, "you can start the
# totalsegmentator segmentation of those scans currently on the grid". grid/gate.sh's word
# `totalseg gold4` queues it with PART naming the part:
#
#   run    one task of a GPU array: the CTs in one fixed order, each task starting at a place of its
#          own and claiming a CT before it runs it, so the tasks share the list with no plan
#   merge  afterany the array, on a CPU node: every CT's record, the counts and the report
#
# Every part runs on a launched flow (the owner's rule of 2026-10-29): this driver does what must be
# done on the node, copies the code at the commit the gate sent and starts flows/launch.py
# gold4_totalseg from the copy, whose run is held to the frozen PREREG (flows/gold4_totalseg.py).
# Every part of one send works under $GOLD4_ROOT/chains/<chain>/, the chain being the send's array
# job, so no send reads another's claims; the CTs' own records and label maps (units/, labels/) lie
# beside the chains and outlive them, so a send again carries on where the last one stopped. The
# merge writes the report, logs/TOTALSEG-gold4.md, and the next send prints it.
#
# The Lab Recipe's rules it follows, as the auto-anatomist screen's job does
# (grid/autoanatomist.sbatch): the code is a copy of the gate's commit (git archive with its COPY.txt
# record), so no part holds grid/logs/HOLD and the checkout may move under the run; the tasks share
# the copy, made once under a name of its own and renamed into place, and the environment, made once
# under a lock; the frozen PREREG.md is checked against its hash before anything is read (exit 90); a
# missing input stops a part with its own message and exit, under set -uo pipefail and never set -e;
# scratch and TMPDIR under /dev/shm, removed on exit; results on the lab volume, in a folder the
# owner's alone (umask 077), since the records name CTs and person keys; never requeued
# (--no-requeue from the gate). TotalSegmentator runs in the throwaway environment over train-gpu's
# Python that the gold tier 3 completion made (grid/venv.sh; the same pin, so it is made already),
# and reads the two weight parts that job unpacked on the lab volume, so nothing downloads and
# pixi.lock is never touched.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
RS=${RS_ROOT:-$LAB/go2432}
ROOT=${GOLD4_ROOT:-$RS/gold4-totalseg}
# The census job 40870542's detail of its part gold4 (tools/gold3_census.py), whose rows are the
# candidates, and the ruleclass tier lists, whose rows name each SPINEPS mask's CT.
CENSUS=${GOLD4_CENSUS:-$RS/gold3_census/40870542/gold4.json}
TIERS=${GOLD4_TIERS:-$RS/ruleclass/tiers}
# The weight parts totalseg complete unpacked (grid/totalseg-complete.sbatch, unpack_weights): the
# vertebrae part, Dataset292, and the 6 mm model it crops with, Dataset298, each marked UNPACKED.
WEIGHTS=${GOLD4_WEIGHTS:-$RS/gold3-totalseg/weights}
STUDY_DIR=docs/research/gold4-totalseg
FLOW_CLASS=Gold4TotalsegFlow
# TotalSegmentator's environment, the completion's to the byte (grid/totalseg-complete.sbatch's
# TS_PIN), so venv_path finds the one already made on the lab volume; the tool's SEGMENTER says the
# same (tests/test_gold4_totalseg_grid.py holds the two equal), so a new pin changes the code the
# tool counts a CT's failures at.
TS_PIN="TotalSegmentator==2.18.0"
# What every part runs, copied at the gate's commit: the tools and the packages they import, the flows
# and the launcher with their registry, the frozen split and the report's checklists the launcher's
# stages read, the licence register, the locked environment the run's code is named by, the
# container and environment scripts, this script, the masking filter, and the pre-registration with
# its hash.
CODE_PATHS=(tools src vendor flows data/splits data/reporting data/licences.json pixi.toml pixi.lock
  grid/box.sh grid/venv.sh grid/redact.sed grid/totalseg-gold4.sbatch
  "$STUDY_DIR/PREREG.md" "$STUDY_DIR/PREREG.md.sha256")
# The copy's record of its commit and files (tools/run_code.py and flows/launch.py, COPY_RECORD).
COPY_RECORD=COPY.txt
PART=${PART:-}
COMMIT=${GOLD4_COMMIT:-}
TASK=${SLURM_ARRAY_TASK_ID:-0}
TASKS=${GOLD4_TASKS:-}
# The chain: a task's array, and for the merge the array the gate hands it.
case "$PART" in
  run) CHAIN=${SLURM_ARRAY_JOB_ID:-} ;;
  merge) CHAIN=${RUN_JOB:-} ;;
  *) CHAIN="" ;;
esac
refuse() { echo "totalseg gold4: $*; nothing ran"; echo "SN_GOLD4_TOTALSEG_RC=64"; exit 64; }
case "$PART" in run|merge) ;; *) refuse "PART is run or merge" ;; esac
[[ $COMMIT =~ ^[0-9a-f]{40}$ ]] || refuse "GOLD4_COMMIT is the full commit the gate sent"
case "$TASKS" in ""|0|*[!0-9]*) refuse "GOLD4_TASKS is the array's count of tasks" ;; esac
case "$CHAIN" in ""|*[!0-9]*) refuse "the chain is the send's array job (for the merge, RUN_JOB)" ;; esac
[ "$TASK" -lt "$TASKS" ] 2>/dev/null || refuse "the task $TASK is outside the array's $TASKS tasks"
OUT=$ROOT/chains/$CHAIN
STEPS=$OUT/steps
LOGS=$OUT/logs
REPORT=$REPO/grid/logs/TOTALSEG-gold4.md
mkdir -p "$REPO/grid/logs" || exit 2
# venv_for builds with pixi, which needs the checkout's pixi.toml where it runs; every tool runs from the copy.
cd "$REPO" || exit 2
# The run's folder is the owner's alone: the records name CTs and person keys, and every log is written there.
umask 077
mkdir -p "$STEPS" "$LOGS" || exit 2
chmod 700 "$ROOT"
export PYTHONNOUSERSITE=1 WANDB_MODE=disabled HF_HUB_OFFLINE=1
export TOTALSEG_WEIGHTS_PATH=$WEIGHTS
export TRITON_LIBCUDA_PATH=${TRITON_LIBCUDA_PATH:-/.singularity.d/libs}
W=/dev/shm/${USER:-$(id -un)}_gold4_totalseg_${SLURM_JOB_ID:-$$}_$TASK
mkdir -p "$W" || exit 2
trap 'rm -rf "$W"' EXIT
trap 'exit 143' TERM
# TotalSegmentator's scratch, the resampled CT and its multilabel file, goes here with TMPDIR.
export TMPDIR=$W
job_began=$(date +%s)

STEP_FILE=""
report() { echo "- $*" >> "$STEP_FILE"; echo "- $*"; }
step_end() {  # step_end RC: a task's exit line, last in its file, then the job's exit with RC
  trap '' TERM
  report "exit $1 at $(date -u '+%F %T') UTC"
  echo "SN_GOLD4_TOTALSEG_RC=$1"
  exit "$1"
}
report_end() {  # report_end RC: the report's exit line, then the report renamed into place, kept beside the steps, and the job's exit with RC
  trap '' TERM
  report "exit $1 at $(date -u '+%F %T') UTC"
  cp "$STEP_FILE" "$STEPS/merge.md" 2>/dev/null
  mv "$STEP_FILE" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_GOLD4_TOTALSEG_RC=$1"
  exit "$1"
}
part_end() { if [ "$PART" = run ]; then step_end "$1"; else report_end "$1"; fi; }
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
segmenter_venv() {  # TotalSegmentator's environment, made by the copy's grid/venv.sh, into venv
  # shellcheck source=grid/venv.sh
  . "$CODE/grid/venv.sh"
  # What a build prints goes to its log, so venv holds the path venv_ready gives and nothing else.
  venv_once "$TS_PIN" > "$LOGS/venv-$PART-$TASK.log" 2>&1 && venv=$(venv_ready "$TS_PIN")
}
torch_on_gpu() {  # the environment's torch sees a card, so a task never segments on the CPU unawares
  bash "$CODE/grid/box.sh" "$venv/bin/python" -c 'import sys, torch; sys.exit(not torch.cuda.is_available())' > "$LOGS/torch-$TASK.log" 2>&1
}
weights_whole() {  # both weight parts unpacked whole, as the completion's job marks them
  local part
  for part in 292 298; do
    compgen -G "$WEIGHTS/Dataset${part}_*/UNPACKED" > /dev/null || return 1
  done
}
node_ready() {  # node_ready gpu|cpu: the copy, the freeze, the inputs, the card and the environment, before any flow
  copy_code || { report "FAILED: the code at ${COMMIT:0:7} could not be copied under $OUT"; part_end 2; }
  report "code: commit $COMMIT copied to $CODE, which every part of the chain runs"
  prereg_frozen || { report "STOP: PREREG.md changed since the freeze"; part_end 90; }
  report "PREREG.md: as frozen, sha256 $(cut -c1-16 "$CODE/$STUDY_DIR/PREREG.md.sha256")"
  if [ "$1" = gpu ]; then
    # The inputs again, since the gate's check may be hours old by the time the task starts.
    [ -f "$CENSUS" ] || { report "FAILED: no census detail at $CENSUS (the gate word census gold3 writes it)"; part_end 2; }
    [ -d "$TIERS" ] || { report "FAILED: no census tier lists at $TIERS"; part_end 2; }
    weights_whole || { report "FAILED: the weights folder $WEIGHTS holds no whole Dataset292 or Dataset298 (totalseg complete unpacks them)"; part_end 2; }
    # The card is read here, on the node, and not inside the container, whose nvidia-smi only --nv brings in.
    gpu=$(gpu_line)
    [ -n "$gpu" ] || { report "FAILED: nvidia-smi names no GPU on $(hostname)"; part_end 4; }
    report "GPU: $gpu"
  fi
  segmenter_venv || { report "FAILED: the environment for $TS_PIN could not be made"; part_end 1; }
  report "environment: $TS_PIN over train-gpu's Python"
  if [ "$1" = gpu ]; then
    torch_on_gpu || { report "FAILED: torch in the environment sees no GPU ($(tail -n 1 "$LOGS/torch-$TASK.log" | cut -c1-160))"; part_end 4; }
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
  # the checkout here, which may move under the run.
  env SCHWINGNET="$CODE" bash "$CODE/grid/box.sh" "$venv/bin/python" "$CODE/flows/launch.py" gold4_totalseg --max-workers 1 -- \
    --chain "$CHAIN" --out "$ROOT" "$@" >> "$LAUNCH_LOG" 2>&1 &
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
  sed -n 's/^\([^[]*\[[^]]*\] \)\{0,1\}Gold4TotalsegFlow: //p' "$1" 2>/dev/null | tail -n 20 | while IFS= read -r line; do report "$line"; done
}
page_of() {  # page_of LOG: where the run's progress page lies, from the datastore the decision names and the run the last line names
  local root id
  root=$(grep -m 1 '"decision":' "$1" 2>/dev/null | sed -n 's/.*"root": *"\([^"]*\)".*/\1/p')
  id=$(grep '"successful":' "$1" 2>/dev/null | tail -n 1 | sed -n "s/.*\"run\": *\"$FLOW_CLASS\\/\\([0-9A-Za-z_-]*\\)\".*/\\1/p")
  echo "${root:-(the datastore the launcher names)}/progress/$FLOW_CLASS/${id:-<run>}/index.html"
}
task_line() {  # task_line T: how task T of this chain ended, from its step file, with the tool's last line
  local file=$STEPS/task-$1.md last said
  said=$(tail -n 1 "$OUT/tasks/$1.txt" 2>/dev/null | cut -d' ' -f2- | cut -c1-240)
  [ -f "$file" ] || { echo "task $1: no step file, so it never started (cancelled, or a job it waited on failed)"; return; }
  last=$(tail -n 1 "$file")
  case "$last" in
    "- exit "*) echo "task $1: ${last#- }; ${said:-the tool wrote no line}" ;;
    *) echo "task $1: its step file has no exit line, so Slurm ended it past its TERM (its time or its memory); ${said:-the tool wrote no line}" ;;
  esac
}
merge_said() {  # what the merge's run left: its lines, the counts it wrote in this job, and the page
  local counts=$OUT/REPORT.md
  flow_said "$LAUNCH_LOG"
  if [ "$(stat -c %Y "$counts" 2>/dev/null || echo 0)" -ge "$job_began" ]; then
    { echo; echo "### The counts (chains/$CHAIN/REPORT.md)"; echo; cat "$counts"; echo; } >> "$STEP_FILE"
  else
    report "the counts: not written by this job (the merge did not reach its end)"
  fi
  report "progress page: $(page_of "$LAUNCH_LOG")"
}

part_run() {
  STEP_FILE=$STEPS/task-$TASK.md
  echo "# totalseg gold4 task $TASK of $TASKS: job ${CHAIN}_$TASK on $(hostname), commit ${COMMIT:0:7}, $(date -u '+%F %T') UTC" > "$STEP_FILE"
  trap 'launcher_stop; report "TERMINATED: Slurm ended the task (its time limit, or a cancel)"; step_end 143' TERM
  node_ready gpu
  launch_run "task-$TASK" --part run --task "$TASK" --tasks "$TASKS" --census "$CENSUS" --tiers "$TIERS" --weights "$WEIGHTS"
  flow_said "$LAUNCH_LOG"
  report "progress page: $(page_of "$LAUNCH_LOG")"
  step_end "$LAUNCH_RC"
}
part_merge() {
  local t
  STEP_FILE=$REPORT.part
  echo "# totalseg gold4: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${COMMIT:0:7}, $(date -u '+%F %T') UTC; the merge of the array $CHAIN" > "$STEP_FILE"
  trap 'launcher_stop; report "TERMINATED: Slurm ended the merge (its time limit, or a cancel)"; report_end 143' TERM
  for ((t = 0; t < TASKS; t++)); do report "$(task_line "$t" | LC_ALL=C tr -cd '\11\40-\176')"; done
  node_ready cpu
  launch_run merge --part merge
  merge_said
  report_end "$LAUNCH_RC"
}

"part_$PART"
