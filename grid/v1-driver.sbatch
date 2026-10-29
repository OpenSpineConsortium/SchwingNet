#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=24:00:00
# The version 1 run on real frames (issue #53, SchwingNet's item 4): tools/flow.py on the catalog's
# current version, its train and evaluate steps run in this job on the GPU Slurm gave it, inside the
# container (grid/box.sh). flow.py's slurm mode would submit each step with sbatch, which the
# container does not hold, so the flow runs in local mode here with the train-gpu environment, and
# this job is the one Slurm job the run costs. flow.py refuses a dirty checkout and a catalog whose
# split check fails, records the run under RUNS, and pushes each step's W&B run as the step ends.
# grid/gate.sh queues it through hpcworker's job submit as the gpu class (grid/hpcw.sh, issue #77),
# whose partitions, QoS and one GPU the site profile gives, as Beethoven for VS Code submits a GPU
# job; this header holds no partition or QoS line, since one guessed here was refused (issue #74).
# Not requeued (--no-requeue): a requeued job would start a second run beside the first. The report
# names the GPU.
# The report is logs/v1-driver-STAGE-REPORT.md: the GPU, the run directory and the W&B lines.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
DATA_ROOT=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
STORE=${STORE:-$DATA_ROOT/_catalog}
RUNS=${RUNS:-/rs/rs_grp_oschome/go2432/runs}
WEIGHTS=${WEIGHTS:-/rs/rs_grp_oschome/go2432/models/resnet18-f37072fd.pth}
EPOCHS=${EPOCHS:-20}
SEED=${SEED:-1}
# Absolute, since the job changes to the checkout before it runs the flow.
REPORT=$REPO/grid/logs/v1-driver-STAGE-REPORT.md
mkdir -p "$REPO/grid/logs" "$RUNS"
report() { echo "- $*" | tee -a "$REPORT"; }
fail() { report "FAILED: $*"; echo "SN_V1_RC=1"; exit 1; }
echo "# Version 1 run: $(date '+%F %T'), job ${SLURM_JOB_ID:-none} on $(hostname), commit $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null)" > "$REPORT"
cd "$REPO" || fail "no checkout at $REPO"
# The run's code holds still while it lasts, from before it chooses its catalog version: flow.py
# records the commit at the start and runs its later steps from this checkout, so grid/logs/HOLD
# names this job and the commit, the gate's side skips its fast-forward while the file is there, and
# the gate clears a hold whose job Slurm no longer holds. The commit is read again at the end, and
# a run whose checkout moved is not used.
started_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
HOLD=$REPO/grid/logs/HOLD
echo "${SLURM_JOB_ID:-$$} $started_at" > "$HOLD"
unhold() { [ "$(awk '{ print $1; exit }' "$HOLD" 2>/dev/null)" != "${SLURM_JOB_ID:-$$}" ] || rm -f "$HOLD"; }
trap unhold EXIT
trap 'exit 143' TERM
# The version grid/v1-version.sh chooses, as the gate's v1 word asked it (issue #80): the newest that
# holds both of C-ArmLSpine's parts and every C-ArmLSpine shard now on the volume, with a split-check
# marker for today's test persons and rule. CURRENT is the newest version of all, and a catalog job
# that listed the manifests before C-ArmLSpine's shards were written can land after it.
# The name from stdout alone, so a warning on stderr never becomes part of the path.
why=$(mktemp)
chosen=$(bash grid/v1-version.sh "$STORE" "$DATA_ROOT" "$REPO" 2> "$why") \
  || fail "no catalog version to run on: $(head -n 1 "$why") (the C-ArmLSpine ingest and a catalog build first; 'v1' submits them)"
rm -f "$why"
CATALOG=$STORE/versions/$chosen
newest=$(cat "$STORE/CURRENT" 2>/dev/null)
[ "$newest" = "$chosen" ] || report "CURRENT names ${newest:-nothing}; the run takes $chosen, the newest that qualifies"
[ -s "$WEIGHTS" ] || fail "no ImageNet weights at $WEIGHTS (the weights job first)"
# The split check again, on the chosen file itself, here where python runs: the marker says it
# passed, and this says it still does before any frame is read.
number=$(echo "$chosen" | sed -n 's/^catalog-0*\([0-9][0-9]*\)-.*/\1/p')
bash grid/box.sh pixi run --locked python tools/catalog.py split-check "$STORE" --version "$number" > /dev/null 2>&1 \
  || fail "the split check of version $number failed; no run reads it"
report "catalog: $CATALOG (split check passed); weights: $(basename "$WEIGHTS"); epochs $EPOCHS, seed $SEED"
report "GPU: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -n 1 || echo 'nvidia-smi gave nothing')"
said=$(bash grid/box.sh pixi run --locked -e train-gpu python -c "import torch; print('torch', torch.__version__, 'cuda available', torch.cuda.is_available())" 2>&1 | tail -n 1)
report "in the container: $said"
out=$(mktemp "$REPO/grid/logs/v1-flow-${SLURM_JOB_ID:-$$}.XXXXXX")
# The run is a launched flow, as every deep learning job on the grid is (the owner's rule of
# 2026-10-29, flows/registry.txt): flows/launch.py refuses it with exit 90 unless
# docs/research/v1-demo/PREREG.md is the one frozen, resumes the newest run of the same words, code,
# catalog and weights that did not finish, and its V1Flow runs tools/flow.py in local mode, then
# writes and checks the run's CLAIM 2024 and REFORMS report and draws the run's progress page under
# the datastore's progress/ folder.
# The launcher runs in the background and is waited on, as grid/sweep-driver.sbatch's is, so job
# submit's TERM two minutes before the limit, or a person's INT, is heard at once: a shell holds a
# trapped signal while a command runs in its foreground. The trap passes TERM on to the launcher,
# which passes it to every process of its flow, closes the run's page and exits 143, and the
# pipeline is waited on again; tee ignores both signals, so the launcher's last lines reach $out.
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
  bash grid/box.sh pixi run --locked -e train-gpu python flows/launch.py v1 --max-workers 1 -- \
    --catalog "$CATALOG" --out "$RUNS" --environment train-gpu --epochs "$EPOCHS" --seed "$SEED" --weights "$WEIGHTS" &
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
grep -h 'V1Flow: report ' "$out" | tail -n 1 | while IFS= read -r line; do report "${line#*V1Flow: }"; done
[ -z "$run_dir" ] || [ ! -f "$run_dir/evaluate/results.md" ] || { echo; echo "## The test part"; cat "$run_dir/evaluate/results.md"; } >> "$REPORT"
run=$(grep '"successful":' "$out" | tail -n 1)
report "Metaflow: ${run:-the launcher named no run}"
report "launcher exited $rc"
ended_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
if [ "$ended_at" != "$started_at" ]; then
  report "FAILED: the checkout moved from ${started_at:0:7} to ${ended_at:0:7} during the run, so a later step may have run the newer code while RUN.json names the older; this run is not used, and v1 runs again"
  [ "$rc" != 0 ] || rc=3
fi
echo "SN_V1_RC=$rc"
exit "$rc"
