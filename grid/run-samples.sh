#!/bin/bash
# Submit the sample index (tools/sample_index.py; the owner's asks of 2026-10-21 21:27 and 21:28
# UTC) as three Slurm steps of grid/samples.sbatch, queued through hpcworker's job submit
# (grid/hpcw.sh; bash 4.2; the login node runs nothing else):
#   1. plan     the roots and the units                      (one task)
#   2. scan     SAMPLES_TASKS array tasks, CONCURRENCY at once (afterok:1)
#   3. merge    samples.sqlite and the manifest               (afterany:2, so a task that failed
#               leaves its finished units in, and the done lines say what is missing)
# Each run is a folder of its own, SAMPLES_OUT/<stamp>; RESUME=<stamp> runs the scan and merge
# again in an earlier one, where each task skips the units it finished.
#
#   bash grid/run-samples.sh                     # submit, printing "<step>: job <id>" lines
#   bash grid/run-samples.sh report              # the newest whole run's MANIFEST.md
#   HPCW_DRY=1 bash grid/run-samples.sh          # dry run: print the submissions
#
# On the login node it runs bash, hpcworker and coreutils only. The index holds DICOM header values and
# sidecar rows that can be PHI, so every file it writes is the owner's alone (umask 077, the run
# folders mode 700); only MANIFEST.md, counts per source, goes on to grid/logs and the gate's status.
#   OUTSIDE_SLURM=1 DATA_ROOT=<root> bash grid/run-samples.sh   # off the grid: every step here
#
# ALL_SLICES=1 writes every slice's whole DICOM header, not one per series.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
DATA_ROOT_DEFAULT=/rs/rs_grp_oschome/go2432/data
SAMPLES_OUT=${SAMPLES_OUT:-${DATA_ROOT:-$DATA_ROOT_DEFAULT}/_samples}
SAMPLES_TASKS=${SAMPLES_TASKS:-64}
CONCURRENCY=${CONCURRENCY:-32}
OUTSIDE_SLURM=${OUTSIDE_SLURM:-}
SAMPLES_ARGS=""
[ "${ALL_SLICES:-}" != 1 ] || SAMPLES_ARGS="--all-slices"
if [ -z "${PYDRV:-}" ]; then
  if [ -x "$REPO/.pixi/envs/train-cpu/bin/python" ]; then PYDRV=$REPO/.pixi/envs/train-cpu/bin/python
  else PYDRV=python3; fi
fi
[ -f "$REPO/tools/sample_index.py" ] || { echo "no $REPO/tools/sample_index.py: is SCHWINGNET the checkout?"; exit 2; }

if [ "${1:-}" = report ]; then
  current=$(cat "$SAMPLES_OUT/CURRENT" 2>/dev/null)
  [ -n "$current" ] && [ -f "$SAMPLES_OUT/$current/MANIFEST.md" ] || { echo "no whole run under $SAMPLES_OUT yet"; exit 2; }
  echo "## $SAMPLES_OUT/$current"
  head -n 180 "$SAMPLES_OUT/$current/MANIFEST.md"
  exit 0
fi
[ $# -eq 0 ] || { echo "refusing: run-samples.sh takes no argument but report"; exit 64; }

umask 077
mkdir -p "$SAMPLES_OUT" "$REPO/grid/logs" && chmod 700 "$SAMPLES_OUT"
if [ -n "${RESUME:-}" ]; then
  RUN=$SAMPLES_OUT/$RESUME
  [ -f "$RUN/units.tsv" ] || { echo "refusing: $RUN has no units.tsv to resume"; exit 2; }
else
  RUN=$(mktemp -d "$SAMPLES_OUT/$(date '+%Y%m%d-%H%M%S')-XXXX") || exit 2
fi
export SCHWINGNET="$REPO" PYDRV SAMPLES_RUN="$RUN" SAMPLES_TASKS SAMPLES_ARGS

if [ -n "$OUTSIDE_SLURM" ]; then
  cd "$REPO/grid" || exit 2
  [ -n "${RESUME:-}" ] || bash samples.sbatch plan || exit 1
  for task in $(seq 0 $((SAMPLES_TASKS - 1))); do SLURM_ARRAY_TASK_ID=$task bash samples.sbatch scan || exit 1; done
  bash samples.sbatch merge
  exit $?
fi

# Every step through hpcworker's job submit as a batch job (grid/hpcw.sh, issue #77); HPCW_DRY=1
# prints the submissions and queues nothing.
# shellcheck source=grid/hpcw.sh
. "$REPO/grid/hpcw.sh"
plan_dep=()
if [ -z "${RESUME:-}" ]; then
  plan=$(hpcw_submit samples_plan batch --cpus 2 --mem 8G --time 06:00:00 -- samples.sbatch plan) || exit 1
  echo "samples_plan: job $plan"
  plan_dep=(--after "$plan:ok")
fi
scan=$(hpcw_submit samples_scan batch ${plan_dep[@]+"${plan_dep[@]}"} --array "0-$((SAMPLES_TASKS - 1))%$CONCURRENCY" \
  -- samples.sbatch scan) || { [ -z "${plan:-}" ] || "${SCANCEL:-scancel}" "$plan"; exit 1; }
echo "samples_scan: job $scan"
merge=$(hpcw_submit samples_merge batch --after "$scan:any" --cpus 4 --mem 64G -- samples.sbatch merge) \
  || { "${SCANCEL:-scancel}" ${plan:-} "$scan"; exit 1; }
echo "samples_merge: job $merge"
echo "$(date '+%F %T') samples plan=${plan:-resumed} scan=$scan merge=$merge run=$RUN" | tee -a "$REPO/grid/LAST_RUN.txt"
echo "the manifest: $RUN/MANIFEST.md once the merge ends; 'bash grid/run-samples.sh report' prints it"
