#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
# The QA loop (docs/research/qa-loop/PREREG.md): the auto-anatomist trained round after round on the
# six column classes' phantoms, every round asking six gates (convergence, the anomaly classes decoded
# and encoded, the landmark fingerprint, its presence on C-ArmLSpine's real frames, real naming and
# latency), until every gate passes, a gate lacks its data, no failing gate has a change left in the
# plan's ranges or the measured memory, or the plan's rounds run out (flows/qaloop.py). The owner
# asked on 2026-10-31 for a pipeline with these checkpoints that propels itself until they are met;
# grid/gate.sh's word `qaloop <plan>` queues it as a chain of links, each one GPU job afterany the
# one before:
#
#   link 1    starts the loop's run; the chain is its own job
#   link n    the same words, so the launcher resumes the run at the round the link before was cut
#             in by its time limit; a link that finds the loop ended (ENDED.json) exits at once
#
# Every link runs on a launched flow (the owner's rule of 2026-10-29): this driver does what must be
# done on the node, copies the code at the commit the gate sent, makes the loop's environment and
# starts flows/launch.py qaloop from the copy, whose run is held to the frozen PREREG and whose end
# writes the loop's CLAIM 2024 and REFORMS report. Every link of one send works in one folder,
# $QALOOP_ROOT/<plan>/<chain>/; each adds its lines to the report, logs/QALOOP-<plan>.md.part, and
# the link that sees the loop end renames it logs/QALOOP-<plan>.md, which the next send prints.
#
# The Lab Recipe's rules it follows (artifacts/the-lab-recipe-1t2gvp/index.md): the code is a copy
# of the gate's commit (git archive with its COPY.txt record), so no link holds grid/logs/HOLD and
# the checkout may move under the loop; the environment is made once under a lock; the frozen
# PREREG.md is checked against its hash before anything is read (exit 90); a missing input stops a
# link with its own message and exit, under set -uo pipefail and never set -e; scratch and TMPDIR
# under /dev/shm, removed on exit; results on the lab volume, the folder the owner's alone (umask
# 077); never requeued (--no-requeue from the gate), the next link carrying the run on instead. The
# loop's packages go into a throwaway environment over train-gpu's Python 3.11 (grid/venv.sh): the
# auto-anatomist screen's pins, and xarray with pandas for the phantom's column draw.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
ROOT=${QALOOP_ROOT:-$LAB/go2432/qaloop}
KIND=${QALOOP_KIND:-qaloop}
case "$KIND" in
  qaloop) STUDY_DIR=docs/research/qa-loop FLOW_CLASS=QaloopFlow ;;
  qaloop_tx) STUDY_DIR=docs/research/qa-loop-transformer FLOW_CLASS=QaloopTxFlow ;;
  qaloop_gold) STUDY_DIR=docs/research/qa-loop-gold FLOW_CLASS=QaloopGoldFlow ;;
  *) echo "qaloop: QALOOP_KIND is qaloop, qaloop_tx or qaloop_gold, not $KIND; nothing ran"; echo "SN_QALOOP_RC=64"; exit 64 ;;
esac
# The gold kind also reads gold tier 4's CTs where TotalSegmentator's run keeps their records
# (grid/gate.sh's GOLD4_ROOT, which the gate passes as QALOOP_GOLD4); the other kinds read none.
GOLD4=${QALOOP_GOLD4:-$LAB/go2432/gold4-totalseg}
GOLD_WORDS=()
[ "$KIND" != qaloop_gold ] || GOLD_WORDS=(--gold4 "$GOLD4")
QALOOP_PIN="jax[cuda12]==0.10.2 flax==0.12.8 optax==0.2.8 orbax-checkpoint==0.12.8 numpy==2.4.6 scipy==1.17.1 nibabel==5.3.2 xarray==2025.6.1 pandas==2.3.2"
# What every link runs, copied at the gate's commit: the tools and the packages they import, the
# vendored auto-anatomist package and phantom, the flows and the launcher with their registry, the
# plans, the frozen split, the report's checklists and the licence register, the locked environment
# the run's code is named by, the container and environment scripts, this script, the masking
# filter, the screens' plans, whose rows the gold kind reads gold tier 3's persons from, and the
# pre-registration with its hash.
CODE_PATHS=(tools src vendor flows data/splits data/reporting data/licences.json pixi.toml pixi.lock
  grid/box.sh grid/venv.sh grid/redact.sed grid/qaloop.sbatch grid/autoanatomist grid/qaloop grid/screens
  docs/research/qa-loop/PREREG.md docs/research/qa-loop/PREREG.md.sha256
  "$STUDY_DIR/PREREG.md" "$STUDY_DIR/PREREG.md.sha256")
# The copy's record of its commit and files (tools/run_code.py and flows/launch.py, COPY_RECORD).
COPY_RECORD=COPY.txt
PLAN=${PLAN:-}
COMMIT=${QALOOP_COMMIT:-}
LINK=${QALOOP_LINK:-1}
LINKS=${QALOOP_LINKS:-1}
# The chain: the first link's own job, which the gate hands every later link.
CHAIN=${QALOOP_CHAIN:-${SLURM_JOB_ID:-}}
refuse() { echo "qaloop: $*; nothing ran"; echo "SN_QALOOP_RC=64"; exit 64; }
case "$PLAN" in ""|*[!a-z0-9_]*) refuse "PLAN is the name of a plan under grid/qaloop/" ;; esac
[[ $COMMIT =~ ^[0-9a-f]{40}$ ]] || refuse "QALOOP_COMMIT is the full commit the gate sent"
case "$CHAIN" in ""|*[!0-9]*) refuse "the chain is the first link's Slurm job (QALOOP_CHAIN)" ;; esac
case "$LINK:$LINKS" in *[!0-9:]*|:*|*:) refuse "QALOOP_LINK and QALOOP_LINKS are whole numbers" ;; esac
[ "$LINK" -ge 1 ] && [ "$LINK" -le "$LINKS" ] || refuse "the link $LINK is outside the chain's $LINKS"
OUT=$ROOT/$PLAN/$CHAIN
STEPS=$OUT/steps
LOGS=$OUT/logs
REPORT=$REPO/grid/logs/QALOOP-$PLAN.md
mkdir -p "$REPO/grid/logs" || exit 2
# venv_for builds with pixi, which needs the checkout's pixi.toml where it runs; every tool runs from the copy.
cd "$REPO" || exit 2
# The chain's folder is the owner's alone: the pairs' cache holds frames of real persons.
umask 077
mkdir -p "$STEPS" "$LOGS" || exit 2
chmod 700 "$OUT"
export PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1
W=/dev/shm/${USER:-$(id -un)}_qaloop_${SLURM_JOB_ID:-$$}
mkdir -p "$W" || exit 2
trap 'rm -rf "$W"' EXIT
trap 'exit 143' TERM
export TMPDIR=$W

if [ -f "$OUT/ENDED.json" ]; then
  # The loop ended in an earlier link, which wrote the report; this link has nothing to carry on.
  echo "qaloop $PLAN: link $LINK of $LINKS of chain $CHAIN: the loop ended in an earlier link ($OUT/ENDED.json); nothing ran"
  echo "SN_QALOOP_RC=0"
  exit 0
fi

STEP_FILE=$REPORT.part
report() { echo "- $*" >> "$STEP_FILE"; echo "- $*"; }
link_end() {  # link_end RC: the link's exit line; the report renamed into place where the loop ended in this link; the job's exit with RC
  trap '' TERM
  report "exit $1 at $(date -u '+%F %T') UTC"
  if [ -f "$OUT/ENDED.json" ] || [ "$LINK" -ge "$LINKS" ]; then
    cp "$STEP_FILE" "$STEPS/report.md" 2>/dev/null
    mv "$STEP_FILE" "$REPORT" && chmod 644 "$REPORT"
  fi
  echo "SN_QALOOP_RC=$1"
  exit "$1"
}
gpu_line() {  # the first GPU nvidia-smi names, with its memory and driver, or nothing
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -n 1
}
prereg_frozen() {  # the copy's PREREG.md is the one frozen with its hash (Lab Recipe, "Pre-register and freeze")
  ( cd "$CODE/$STUDY_DIR" 2>/dev/null && sha256sum -c --status PREREG.md.sha256 )
}
copy_code() {  # the chain's copy of the code at the gate's commit, into CODE, made once by the first link
  local made=$OUT/.code-${COMMIT:0:7}.${SLURM_JOB_ID:-$$}
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
loop_venv() {  # the loop's environment, made by the copy's grid/venv.sh, into venv
  # shellcheck source=grid/venv.sh
  . "$CODE/grid/venv.sh"
  venv=$(venv_once "$QALOOP_PIN")
}
jax_on_gpu() {  # the environment's JAX sees a card, so the loop never trains on the CPU unawares
  bash "$CODE/grid/box.sh" "$venv/bin/python" -c 'import jax, sys; sys.exit(jax.default_backend() != "gpu")' > "$LOGS/jax-$LINK.log" 2>&1
}
pairs_said() {  # where the real pairs stand under the data root, in words that name no case
  local root
  root=$DATA/$(sed -n 's/^    "root": "\([a-z0-9_]*\)",\{0,1\}$/\1/p' "$CODE/grid/qaloop/$PLAN.json" | head -n 1)
  if [ -f "$root/levels.json" ]; then
    echo "the C-ArmLSpine pairs under the data root's $(basename "$root") folder"
  else
    echo "no C-ArmLSpine pairs under the data root (no $(basename "$root")/levels.json), so the plan's stand-ins or none"
  fi
}
node_ready() {  # the copy, the freeze, the plan, the card and the environment, before any flow
  copy_code || { report "FAILED: the code at ${COMMIT:0:7} could not be copied under $OUT"; link_end 2; }
  report "code: commit $COMMIT copied to $CODE, which every link of the chain runs"
  prereg_frozen || { report "STOP: PREREG.md changed since the freeze"; link_end 90; }
  report "PREREG.md: as frozen, sha256 $(cut -c1-16 "$CODE/$STUDY_DIR/PREREG.md.sha256")"
  [ -f "$CODE/grid/qaloop/$PLAN.json" ] || { report "FAILED: no grid/qaloop/$PLAN.json at ${COMMIT:0:7}"; link_end 2; }
  report "pairs: $(pairs_said)"
  # The card is read here, on the node, and not inside the container, whose nvidia-smi only --nv brings in.
  gpu=$(gpu_line)
  [ -n "$gpu" ] || { report "FAILED: nvidia-smi names no GPU on $(hostname)"; link_end 4; }
  report "GPU: $gpu"
  loop_venv || { report "FAILED: the environment for $QALOOP_PIN could not be made"; link_end 1; }
  report "environment: $QALOOP_PIN over train-gpu's Python"
  jax_on_gpu || { report "FAILED: JAX in the environment sees no GPU ($(tail -n 1 "$LOGS/jax-$LINK.log" | cut -c1-160))"; link_end 4; }
}

# The launcher, started from the copy and waited on, so Slurm's TERM, two minutes before the time
# limit, reaches the trap at once and is passed on (launcher_stop).
LAUNCHER=""
LAUNCH_RC=""
LAUNCH_LOG=$LOGS/launch-$LINK.log
# How long the driver waits, after passing the TERM on, for the launcher to end: the launcher gives
# the flow's processes 60 s before it kills them (flows/launch.py, STOP_GRACE_SECONDS).
STEP_GRACE=80
launch_run() {  # one run of the flow from the copy, its output in logs/launch-<link>.log and the job's log
  local follower
  : > "$LAUNCH_LOG"
  # Every path is absolute: the flow reads a relative one from the folder the launcher started in,
  # the checkout here, which may move under the loop, and the plan is the copy's.
  env SCHWINGNET="$CODE" bash "$CODE/grid/box.sh" "$venv/bin/python" "$CODE/flows/launch.py" "$KIND" --max-workers 1 -- \
    --plan "$CODE/grid/qaloop/$PLAN.json" --chain "$CHAIN" --out "$ROOT" --data "$DATA" ${GOLD_WORDS[@]+"${GOLD_WORDS[@]}"} \
    >> "$LAUNCH_LOG" 2>&1 &
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
flow_said() {  # the launcher's decision, then the flow's own lines, the last 30, found by their head wherever the line begins
  local decision
  decision=$(grep -m 1 '"decision":' "$LAUNCH_LOG" 2>/dev/null)
  report "launcher: ${decision:-it printed no decision line} (exit $LAUNCH_RC)"
  # Metaflow's runtime heads each line a task prints with its time and [run/step/task (pid N)].
  sed -n "s/^\\([^[]*\\[[^]]*\\] \\)\\{0,1\\}$FLOW_CLASS: //p" "$LAUNCH_LOG" 2>/dev/null | tail -n 30 | while IFS= read -r line; do report "$line"; done
}
page_of() {  # where the run's progress page lies, from the datastore the decision names and the run the last line names
  local root id
  root=$(grep -m 1 '"decision":' "$LAUNCH_LOG" 2>/dev/null | sed -n 's/.*"root": *"\([^"]*\)".*/\1/p')
  id=$(grep '"successful":' "$LAUNCH_LOG" 2>/dev/null | tail -n 1 | sed -n "s/.*\"run\": *\"$FLOW_CLASS\\/\\([0-9A-Za-z_-]*\\)\".*/\\1/p")
  echo "${root:-(the datastore the launcher names)}/progress/$FLOW_CLASS/${id:-<run>}/index.html"
}
rounds_said() {  # each round's last line of progress so far, for a link the time limit cut
  local file
  for file in "$OUT"/rounds/*/PROGRESS.txt; do
    [ -f "$file" ] || continue
    report "round $(basename "$(dirname "$file")"): $(tail -n 1 "$file" | LC_ALL=C tr -cd '\40-\176' | cut -c1-200)"
  done
}

echo "# qaloop $PLAN: link $LINK of $LINKS, job ${SLURM_JOB_ID:-none} on $(hostname), commit ${COMMIT:0:7}, $(date -u '+%F %T') UTC; chain $CHAIN" >> "$STEP_FILE"
trap 'launcher_stop; report "TERMINATED: Slurm ended link $LINK (its time limit, or a cancel)"; rounds_said; [ "$LINK" -lt "$LINKS" ] && report "the next link carries the loop on from the round it was cut in"; link_end 143' TERM
node_ready
report "loop: link $LINK of $LINKS; folder $OUT"
launch_run
flow_said
if [ -f "$OUT/SUMMARY.md" ] && [ -f "$OUT/ENDED.json" ]; then
  { echo; echo "### SUMMARY.md"; echo; cat "$OUT/SUMMARY.md"; echo; } >> "$STEP_FILE"
  report "the CLAIM and REFORMS report: $OUT/REPORT.md (Open OnDemand's Files app)"
else
  report "the loop did not end in this link"
  rounds_said
fi
report "progress page: $(page_of)"
link_end "$LAUNCH_RC"
