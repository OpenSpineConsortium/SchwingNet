#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=1-00:00:00
# The sample index (tools/sample_index.py), one script for its three steps, named by the one
# argument grid/run-samples.sh gives it:
#   plan    the roots (every raw location the manifest holds, every registry path, every folder of
#           the data root) and the units the array shares out, into SAMPLES_RUN
#   scan    one task of the array: every SAMPLES_TASKS-th unit from SLURM_ARRAY_TASK_ID, each
#           committed with its done line, so a task the partition requeues redoes nothing
#   merge   the parts into SAMPLES_RUN/samples.sqlite, the joins, then MANIFEST.json and
#           MANIFEST.md (aggregates only), which also becomes logs/SAMPLES-STAGE-REPORT.md and,
#           once whole, SAMPLES_OUT/CURRENT names this run
# PYDRV is the train-cpu environment, since the DICOM headers need pydicom.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
SAMPLES_RUN=${SAMPLES_RUN:?SAMPLES_RUN names the run folder grid/run-samples.sh made}
SAMPLES_TASKS=${SAMPLES_TASKS:-64}
SAMPLES_ARGS=${SAMPLES_ARGS:-}
step=${1:?plan, scan or merge}
export PYTHONNOUSERSITE=1
# The index can hold PHI (header values, sidecar rows): the owner's alone.
umask 077
mkdir -p logs
tool=$REPO/tools/sample_index.py
echo "SAMPLES $step start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-} task ${SLURM_ARRAY_TASK_ID:-}"
case "$step" in
  plan)
    "$PYDRV" "$tool" roots --out "$SAMPLES_RUN/roots.tsv" ${DATA_ROOT:+--data-root "$DATA_ROOT"} \
      && "$PYDRV" "$tool" units --roots "$SAMPLES_RUN/roots.tsv" --out "$SAMPLES_RUN/units.tsv" ;;
  scan)
    # shellcheck disable=SC2086
    "$PYDRV" "$tool" scan --run "$SAMPLES_RUN" --task "${SLURM_ARRAY_TASK_ID:?one task of the array}" \
      --tasks "$SAMPLES_TASKS" --workers "${SLURM_CPUS_PER_TASK:-8}" $SAMPLES_ARGS ;;
  merge)
    "$PYDRV" "$tool" merge --run "$SAMPLES_RUN" > "$SAMPLES_RUN/merge.out" \
      && cp "$SAMPLES_RUN/MANIFEST.md" logs/SAMPLES-STAGE-REPORT.md && chmod 644 logs/SAMPLES-STAGE-REPORT.md \
      && basename "$SAMPLES_RUN" > "$(dirname "$SAMPLES_RUN")/CURRENT" ;;
  *) echo "samples.sbatch: '$step' is not plan, scan or merge"; exit 64 ;;
esac
rc=$?
echo "SAMPLES_RC=$rc $step $(date '+%F %T')"
exit $rc
