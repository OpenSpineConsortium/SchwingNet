#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
# One sweep of the block smoke test (issue #252): the plan grid/sweeps/$PLAN.json, run on the GPU
# Slurm gave this job by the Metaflow flow flows/sweep.py, which flows/launch.py starts or resumes.
# The launcher is the one way a sweep runs, so a sweep cut short is continued by Metaflow's own
# resume, every finished row cloned and the cut row run on from its last epoch; tools/block_sweep.py
# is never run here alone. grid/gate.sh's word `sweep <plan>` queues this job through hpcworker's
# job submit as the gpu class (grid/hpcw.sh, issue #77), whose site profile gives the partitions,
# the QoS and one GPU, so this header holds no partition, QoS or output line. Not requeued
# (--no-requeue): the word sent again after a cut sweep ends resumes it, and a requeue racing that
# word would start a second launcher on the same flow run.
#
# The catalog is the plan's: "synthetic" is built once under SMOKE by tools/block_sweep.py synthetic
# and found there afterwards; "v1" is the version grid/v1-version.sh chooses for the version 1 run;
# "with:<source>" the same, holding that source's train part too. The split check runs again on the
# chosen file before the flow reads a frame, as grid/v1-driver.sbatch does. The results land in the
# state folder SMOKE/<plan>/<commit 7>-<catalog sha256 first 8>/, the path tools/block_sweep.py
# prepare makes, computed the same way here so the report names it without asking python.
# The report is logs/sweep-<plan>-STAGE-REPORT.md: the GPU, the state folder, the launcher's
# decision, RESULTS.md's headline, the W&B lines and the Metaflow run.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PLAN=${PLAN:-}
DATA_ROOT=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
STORE=${STORE:-$DATA_ROOT/_catalog}
SMOKE=${SMOKE:-/rs/rs_grp_oschome/go2432/smoke}
MODELS=${MODELS:-/rs/rs_grp_oschome/go2432/models}
WEIGHTS=${WEIGHTS:-$MODELS/resnet18-f37072fd.pth}
# The plan's name reaches a file name below, so it is an id before anything is written.
case "$PLAN" in
  ""|*[!a-z0-9_]*) echo "sweep: PLAN is a plan's name under grid/sweeps/, lower-case letters, digits and _; nothing ran"; echo "SN_SWEEP_RC=2"; exit 2 ;;
esac
PLAN_FILE=$REPO/grid/sweeps/$PLAN.json
# Absolute, since the job changes to the checkout before it runs the launcher.
REPORT=$REPO/grid/logs/sweep-$PLAN-STAGE-REPORT.md
mkdir -p "$REPO/grid/logs" "$SMOKE"
report() { echo "- $*" | tee -a "$REPORT"; }
fail() { report "FAILED: $*"; echo "SN_SWEEP_RC=1"; exit 1; }
echo "# Sweep $PLAN: $(date '+%F %T'), job ${SLURM_JOB_ID:-none} on $(hostname), commit $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null)" > "$REPORT"
cd "$REPO" || fail "no checkout at $REPO"
[ -f "$PLAN_FILE" ] || fail "no plan grid/sweeps/$PLAN.json at this commit"
# The checkout holds still while the sweep lasts, as for the version 1 run: grid/logs/HOLD names
# this job and the commit, the gate's side skips its fast-forward while the file is there, and the
# gate clears a hold whose job Slurm no longer holds. The commit is read again at the end, and a
# sweep whose checkout moved is not used.
started_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
[ -n "$started_at" ] || fail "the checkout at $REPO names no commit, and the state folder is named by one"
HOLD=$REPO/grid/logs/HOLD
echo "${SLURM_JOB_ID:-$$} $started_at" > "$HOLD"
unhold() { [ "$(awk '{ print $1; exit }' "$HOLD" 2>/dev/null)" != "${SLURM_JOB_ID:-$$}" ] || rm -f "$HOLD"; }
trap unhold EXIT
trap 'exit 143' TERM

# tools/block_sweep.py writes a plan with indent 1 and sorted keys, so its own keys are the lines
# one space in; its name, not the file's, names the plan's folder under SMOKE, as prepare names it.
plan_key() { sed -n "s/^ \"$1\": \"\\([^\"]*\\)\",\\{0,1\\}\$/\\1/p" "$PLAN_FILE" | head -n 1; }
catalog_kind=$(plan_key catalog)
name=$(plan_key plan)
case "$name" in ""|.*|*[!a-z0-9_.-]*) fail "grid/sweeps/$PLAN.json names no plan a folder can be named by ('$name')" ;; esac

# The catalog the plan names, as a file under a store's versions/ with its number, which the split
# check takes. The name from stdout alone, so a warning on stderr never becomes part of the path.
why=$(mktemp)
case "$catalog_kind" in
  synthetic)
    said=$(bash grid/box.sh pixi run --locked python tools/block_sweep.py synthetic --into "$SMOKE/synthetic/catalog" 2> "$why") \
      || fail "the synthetic catalog was not built: $(tail -n 1 "$why")"
    CATALOG=$(printf '%s\n' "$said" | sed -n 's/.*"catalog": *"\([^"]*\)".*/\1/p' | tail -n 1)
    reused=$(printf '%s\n' "$said" | sed -n 's/.*"reused": *\(true\|false\).*/\1/p' | tail -n 1)
    [ -n "$CATALOG" ] && [ -f "$CATALOG" ] || fail "tools/block_sweep.py synthetic named no catalog file"
    report "catalog: the synthetic one ($([ "$reused" = true ] && echo "found under the smoke folder" || echo "built now"))"
    ;;
  v1|with:*)
    source=""
    case "$catalog_kind" in with:*) source=${catalog_kind#with:} ;; esac
    chosen=$(bash grid/v1-version.sh "$STORE" "$DATA_ROOT" "$REPO" ${source:+"$source"} 2> "$why") \
      || fail "no catalog version to run on: $(head -n 1 "$why") (the gate's v1 word${source:+ or bank $source} makes one)"
    CATALOG=$STORE/versions/$chosen
    newest=$(cat "$STORE/CURRENT" 2>/dev/null)
    [ "$newest" = "$chosen" ] || report "CURRENT names ${newest:-nothing}; the sweep takes $chosen, the newest that qualifies"
    ;;
  *) fail "grid/sweeps/$PLAN.json names no catalog the sweep knows ('$catalog_kind'; synthetic, v1 or with:<source>)" ;;
esac
rm -f "$why"
store=$(dirname "$(dirname "$CATALOG")")
number=$(basename "$CATALOG" | sed -n 's/^catalog-0*\([0-9][0-9]*\)-[0-9a-f]*\.sqlite$/\1/p')
[ -n "$number" ] && [ "$(basename "$(dirname "$CATALOG")")" = versions ] \
  || fail "the catalog $(basename "$CATALOG") is no version file under a store's versions/"
# The split check again, on the chosen file itself, here where python runs: the synthetic store's
# test persons are the frozen ones too, so it is checked as the real one is.
bash grid/box.sh pixi run --locked python tools/catalog.py split-check "$store" --version "$number" > /dev/null 2>&1 \
  || fail "the split check of version $number failed; no sweep reads it"
report "catalog: $CATALOG (version $number, split check passed)"

commit7=$(git -C "$REPO" rev-parse --short=7 HEAD 2>/dev/null)
digest=$(sha256sum < "$CATALOG" | cut -c1-8)
STATE=$SMOKE/$name/$commit7-$digest
report "state folder: $STATE"
report "GPU: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -n 1 || echo 'nvidia-smi gave nothing')"
said=$(bash grid/box.sh pixi run --locked -e train-gpu python -c "import torch; print('torch', torch.__version__, 'cuda available', torch.cuda.is_available())" 2>&1 | tail -n 1)
report "in the container: $said"
# The ImageNet file only where it is there: a plan row that names weights with no file for its
# architecture is "not applicable" in the check, and the flow records it so.
weights=()
if [ -s "$WEIGHTS" ]; then
  weights=(--weights "resnet18=$WEIGHTS")
  report "weights: $(basename "$WEIGHTS")"
else
  report "weights: none at $WEIGHTS, so the rows that start from it are not applicable"
fi

out=$(mktemp "$REPO/grid/logs/sweep-flow-${SLURM_JOB_ID:-$$}.XXXXXX")
# The Metaflow datastore is the launcher's default on the grid; the plan by its absolute path, so the
# flow's steps read it from wherever Metaflow runs them.
bash grid/box.sh pixi run --locked -e train-gpu python flows/launch.py sweep --max-workers 1 -- \
  --plan "$PLAN_FILE" --catalog "$CATALOG" --out "$SMOKE" --environment train-gpu ${weights[@]+"${weights[@]}"} 2>&1 | tee "$out"
rc=${PIPESTATUS[0]}
decision=$(grep -m 1 '"decision":' "$out")
report "launcher: ${decision:-it printed no decision line}"
if [ -f "$STATE/RESULTS.md" ]; then
  # The headline, the lines before the table; the table itself stays in the state folder.
  sed -n '/^|/q; /./p' "$STATE/RESULTS.md" | head -n 8 | while IFS= read -r line; do report "results: $line"; done
else
  report "results: no RESULTS.md in the state folder"
fi
[ -f "$STATE/PROGRESS.txt" ] && grep '^wandb ' "$STATE/PROGRESS.txt" | head -n 4 | while IFS= read -r line; do report "W&B: ${line#wandb }"; done
run=$(grep '"successful":' "$out" | tail -n 1)
report "Metaflow: ${run:-the launcher named no run}"
report "launcher exited $rc"
ended_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
if [ "$ended_at" != "$started_at" ]; then
  report "FAILED: the checkout moved from ${started_at:0:7} to ${ended_at:0:7} during the sweep, so a later row may have run the newer code while the state folder names the older; this sweep is not used, and the word runs it again"
  [ "$rc" != 0 ] || rc=3
fi
echo "SN_SWEEP_RC=$rc"
exit "$rc"
