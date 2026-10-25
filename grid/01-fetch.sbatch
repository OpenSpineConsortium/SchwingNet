#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=4-00:00:00
# Stage 1 of the X-ray chain: fetch every open set of grid/fetch-xray.json to the data root
# (tools/fetch_sources.py --run). Compute nodes have internet; the login node runs nothing, so
# this is submitted by grid/run-xray-chain.sh in <repo>/grid, where logs/ exists. A requeue
# keeps the job id and the helpers resume their .part files. The report is
# logs/01-fetch-STAGE-REPORT.md. FETCH_ARGS carries --only and --credentialed.
# Off the grid (a container testing the chain, issue #40) the same script runs with bash:
# DATA_ROOT names another data root, OUTSIDE_SLURM=1 lifts the tool's refusal of a shell with no
# job, and REACQUIRE names the helper where ~/spinesurg-ct-nnunet is not there (the repository's
# copy data/reproduce/reacquire/reacquire.py is the same file and is the tool's own fallback).
# In a Slurm job each set is sized from its source and admitted whole, with its bank, or refused
# whole by the owner's size rule before its first byte lands (grid/admit.sh, issue #163); a set
# refused lands nothing, the next one is decided in turn, and the report says which were refused.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
FETCH_ARGS=${FETCH_ARGS:-}
[ -z "${DATA_ROOT:-}" ] || FETCH_ARGS="$FETCH_ARGS --data-root $DATA_ROOT"
[ "${OUTSIDE_SLURM:-0}" != 1 ] || FETCH_ARGS="$FETCH_ARGS --outside-slurm"
ADMIT=()
if [ -n "${SLURM_JOB_ID:-}" ] && [ "${OUTSIDE_SLURM:-0}" != 1 ]; then
  export PYDRV SCHWINGNET="$REPO"
  ADMIT=(--admit "bash $REPO/grid/admit.sh")
fi
[ -z "${REACQUIRE:-}" ] || FETCH_ARGS="$FETCH_ARGS --reacquire $REACQUIRE"
# The grid's temp folder unless the run names its own root, whose _tmp then serves, since mkdir
# on the grid's path fails anywhere else and a TMPDIR that is no directory breaks every tempfile.
export PYTHONNOUSERSITE=1 TMPDIR=${TMPDIR_OVERRIDE:-${DATA_ROOT:+$DATA_ROOT/_tmp}}
TMPDIR=${TMPDIR:-/rs/rs_grp_oschome/go2432/tmp}
mkdir -p logs "$TMPDIR"
echo "XR_FETCH start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-} restart ${SLURM_RESTART_COUNT:-0}: $FETCH_ARGS"
# shellcheck disable=SC2086
"$PYDRV" "$REPO/tools/fetch_sources.py" --run --python "$PYDRV" --report logs/01-fetch-STAGE-REPORT.md \
  ${ADMIT[@]+"${ADMIT[@]}"} $FETCH_ARGS
rc=$?
echo "XR_FETCH_RC=$rc $(date '+%F %T')"
exit $rc
