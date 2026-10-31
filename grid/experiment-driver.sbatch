#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=24:00:00
# One requested combination of data and blocks: an issue labelled experiment, answered by
# .github/workflows/experiment.yml and recorded as <issue>.request on the branch experiments, run as
# the launched flow experiment (flows/experiment.py), which runs tools/flow.py with the request's
# recipe, blocks, epochs, seed and hours on the catalog's qualifying version, its train and evaluate
# steps in this job on the GPU Slurm gave it, inside the container (grid/box.sh), as v1-driver.sbatch
# runs version 1. grid/gate.sh's word `experiment <issue>` queues it
# through hpcworker's job submit as the gpu class, with REQUEST (the file the gate fetched from the branch)
# and ISSUE in the environment, after checking the lines' shapes; this job checks the values themselves
# against the checkout's own blocks module and recipes (tools/experiments_panel.py check --request) before
# anything is read, so a request that no longer holds at this commit fails here and trains nothing. Not
# requeued (--no-requeue): a requeued job would start a second run beside the first. The header's 24 hours
# are the floor: the gate asks for the request's hours with the evaluation's quarter and an hour more (--time)
# when that is longer, since the training, the evaluation and the checks all run in this one job.
# The report is logs/experiment-<issue>-STAGE-REPORT.md: the request, the GPU, the launcher's decision, the run
# directory, the W&B lines, the run's report line, the Metaflow run and the launcher's exit.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
DATA_ROOT=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
STORE=${STORE:-$DATA_ROOT/_catalog}
RUNS=${RUNS:-/rs/rs_grp_oschome/go2432/runs}
WEIGHTS=${WEIGHTS:-/rs/rs_grp_oschome/go2432/models/resnet18-f37072fd.pth}
REQUEST=${REQUEST:-}
ISSUE=${ISSUE:-}
case "$ISSUE" in ''|*[!0-9]*) echo "experiment-driver: ISSUE is the issue's number, digits alone"; echo "SN_EXPERIMENT_RC=1"; exit 1 ;; esac
# Absolute, since the job changes to the checkout before it runs the flow.
REPORT=$REPO/grid/logs/experiment-$ISSUE-STAGE-REPORT.md
mkdir -p "$REPO/grid/logs" "$RUNS"
report() { echo "- $*" | tee -a "$REPORT"; }
fail() { report "FAILED: $*"; echo "SN_EXPERIMENT_RC=1"; exit 1; }
echo "# Experiment #$ISSUE: $(date '+%F %T'), job ${SLURM_JOB_ID:-none} on $(hostname), commit $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null)" > "$REPORT"
cd "$REPO" || fail "no checkout at $REPO"
[ -n "$REQUEST" ] && [ -s "$REQUEST" ] || fail "no request file at ${REQUEST:-nothing}; the gate's word experiment $ISSUE fetches it from the branch experiments"
# The request's lines, each with the shape the workflow writes (bash 4.2 on the grid); the values are
# checked against the blocks module below, where python runs.
RECIPE=none EPOCHS="" SEED="" HOURS="" BLOCKS=() n=0
while IFS= read -r line || [ -n "$line" ]; do
  n=$((n + 1)); [ $n -le 40 ] || fail "the request has more than 40 lines"
  case "$line" in *[!A-Za-z0-9._,=:\ -]*) fail "line $n of the request holds a character outside letters, digits and . _ , = : -" ;; esac
  case "$line" in
    "recipe: "*) RECIPE=${line#recipe: } ;;
    "epochs: "*) EPOCHS=${line#epochs: } ;;
    "seed: "*) SEED=${line#seed: } ;;
    "hours: "*) HOURS=${line#hours: } ;;
    "block: "*) BLOCKS+=("${line#block: }") ;;
    *) fail "line $n of the request is not one the gate takes: $(printf '%s' "$line" | cut -c1-60)" ;;
  esac
done < "$REQUEST"
case "$EPOCHS" in ''|*[!0-9]*) fail "epochs is not a whole number: ${EPOCHS:-missing}" ;; esac
case "$SEED" in ''|*[!0-9]*) fail "seed is not a whole number: ${SEED:-missing}" ;; esac
case "$HOURS" in ''|*[!0-9.]*) fail "hours is not a number: ${HOURS:-missing}" ;; esac
blocks_text="${BLOCKS[*]+${BLOCKS[*]}}"
report "request #$ISSUE: recipe $RECIPE, epochs $EPOCHS, seed $SEED, hours $HOURS, blocks ${blocks_text:-none (version 1)}"
# Every requested combination starts from ImageNet, as version 1 does, and the grid holds the ResNet-18
# file alone, so a request for another architecture waits for its file rather than failing at its first
# epoch after the queue (flows/experiment.py refuses it again in its start).
for block in ${BLOCKS[@]+"${BLOCKS[@]}"}; do
  case "$block" in
    architecture=resnet18) ;;
    architecture=*) fail "${block}: no ImageNet file for it on the grid, so the request waits for one" ;;
  esac
done
# The run's code holds still from before the request is checked to the run's end, as v1-driver.sbatch
# holds it, so no gate word fast-forwards the checkout between the check and the run: grid/logs/HOLD names this job and
# the commit, the gate's side skips its fast-forward while the file is there, and the gate clears a hold
# whose job Slurm no longer holds. The commit is read again at the end, and a run whose checkout moved is
# not used.
started_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
HOLD=$REPO/grid/logs/HOLD
{ flock -w 60 9 2>/dev/null || :; echo "${SLURM_JOB_ID:-$$} $started_at" >> "$HOLD"; } 9>>"$HOLD.lock"
unhold() { { flock -w 60 9 2>/dev/null || :; [ ! -f "$HOLD" ] || { awk -v me="${SLURM_JOB_ID:-$$}" '$1 != me' "$HOLD" > "$HOLD.tmp"; if [ -s "$HOLD.tmp" ]; then mv -f "$HOLD.tmp" "$HOLD"; else rm -f "$HOLD" "$HOLD.tmp"; fi; }; } 9>>"$HOLD.lock"; }
trap unhold EXIT
trap 'exit 143' TERM
# The values against this checkout's recipes and blocks, inside the container, before any frame is read.
said=$(bash grid/box.sh pixi run --locked python tools/experiments_panel.py check --request "$REQUEST" 2>&1) \
  || fail "the request does not hold against src/schwingnet/blocks.py and data/recipes/ at this commit: $(printf '%s\n' "$said" | grep '^refused' | tr '\n' ' ')"
# The version grid/v1-version.sh chooses, as for the version 1 run (issue #80): the newest that holds both
# of C-ArmLSpine's parts and every C-ArmLSpine shard now on the volume, with a split-check marker for
# today's test persons and rule. The name from stdout alone, so a warning on stderr never becomes part of the path.
why=$(mktemp)
chosen=$(bash grid/v1-version.sh "$STORE" "$DATA_ROOT" "$REPO" 2> "$why") \
  || fail "no catalog version to run on: $(head -n 1 "$why") (the C-ArmLSpine ingest and a catalog build first; 'v1' submits them)"
rm -f "$why"
CATALOG=$STORE/versions/$chosen
newest=$(cat "$STORE/CURRENT" 2>/dev/null)
[ "$newest" = "$chosen" ] || report "CURRENT names ${newest:-nothing}; the run takes $chosen, the newest that qualifies"
[ -s "$WEIGHTS" ] || fail "no ImageNet weights at $WEIGHTS (the weights job first)"
# The split check again, on the chosen file itself, here where python runs.
number=$(echo "$chosen" | sed -n 's/^catalog-0*\([0-9][0-9]*\)-.*/\1/p')
bash grid/box.sh pixi run --locked python tools/catalog.py split-check "$STORE" --version "$number" > /dev/null 2>&1 \
  || fail "the split check of version $number failed; no run reads it"
report "catalog: $CATALOG (split check passed); weights: $(basename "$WEIGHTS")"
report "GPU: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -n 1 || echo 'nvidia-smi gave nothing')"
said=$(bash grid/box.sh pixi run --locked -e train-gpu python -c "import torch; print('torch', torch.__version__, 'cuda available', torch.cuda.is_available())" 2>&1 | tail -n 1)
report "in the container: $said"
out=$(mktemp "$REPO/grid/logs/experiment-$ISSUE-flow-${SLURM_JOB_ID:-$$}.XXXXXX")
# The run is a launched flow, as every deep learning job on the grid is (the owner's rule of
# 2026-10-29, flows/registry.txt): flows/launch.py refuses it with exit 90 unless
# docs/research/experiments/PREREG.md is the one frozen, resumes the newest run of the same words,
# code, request, catalog and weights that did not finish, and its ExperimentFlow runs tools/flow.py
# in local mode with the request's recipe, epochs, seed, hours and blocks, then writes and checks
# the run's CLAIM 2024 and REFORMS report and draws the run's progress page under the datastore's
# progress/ folder. The launcher runs in the background and is waited on, as
# grid/sweep-driver.sbatch's is, so job submit's TERM two minutes before the limit, or a person's
# INT, is heard at once: a shell holds a trapped signal while a command runs in its foreground. The
# trap passes TERM on to the launcher, which passes it to every process of its flow, closes the
# run's page and exits 143, and the pipeline is waited on again; tee ignores both signals, so the
# launcher's last lines reach $out.
launcher_pid=$(mktemp) launcher_rc=$(mktemp)
stopped="" signalled=""
stop_launcher() {
  local pid
  stopped=1 signalled=1
  pid=$(cat "$launcher_pid" 2>/dev/null)
  [ -z "$pid" ] || kill -TERM "$pid" 2>/dev/null
}
trap stop_launcher TERM INT
{
  bash grid/box.sh pixi run --locked -e train-gpu python flows/launch.py experiment --max-workers 1 -- \
    --issue "$ISSUE" --request "$REQUEST" --catalog "$CATALOG" --out "$RUNS" --environment train-gpu \
    --epochs "$EPOCHS" --seed "$SEED" --hours "$HOURS" --weights "$WEIGHTS" --recipe "$RECIPE" --blocks "$blocks_text" &
  echo "$!" > "$launcher_pid"
  wait "$!"
  echo "$?" > "$launcher_rc"
} 2>&1 | (trap '' TERM INT; exec tee "$out") &
piped=$!
again=1
while [ -n "$again" ]; do
  signalled=""
  wait "$piped"
  again=$signalled
done
trap 'exit 143' TERM
trap - INT
rc=$(cat "$launcher_rc" 2>/dev/null)
# No status where the launcher's own shell was killed, which only Slurm's TERM to the whole job does.
[ -n "$rc" ] || { [ -n "$stopped" ] && rc=143 || rc=1; }
rm -f "$launcher_pid" "$launcher_rc"
decision=$(grep -m 1 '"decision":' "$out")
report "launcher: ${decision:-it printed no decision line}"
run_dir=$(sed -n 's/.*"run_dir": "\([^"]*\)".*/\1/p' "$out" | head -n 1)
report "run directory: ${run_dir:-none was made}"
grep -h 'W&B' "$out" | tail -n 3 | while IFS= read -r line; do report "$line"; done
grep -h 'ExperimentFlow: report ' "$out" | tail -n 1 | while IFS= read -r line; do report "${line#*ExperimentFlow: }"; done
[ -z "$run_dir" ] || [ ! -f "$run_dir/evaluate/results.md" ] || { echo; echo "## The test part"; cat "$run_dir/evaluate/results.md"; } >> "$REPORT"
run=$(grep '"successful":' "$out" | tail -n 1)
report "Metaflow: ${run:-the launcher named no run}"
report "launcher exited $rc"
ended_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
if [ "$ended_at" != "$started_at" ]; then
  report "FAILED: the checkout moved from ${started_at:0:7} to ${ended_at:0:7} during the run, so a later step may have run the newer code while RUN.json names the older; this run is not used, and experiment $ISSUE runs again"
  [ "$rc" != 0 ] || rc=3
fi
echo "SN_EXPERIMENT_RC=$rc"
exit "$rc"
