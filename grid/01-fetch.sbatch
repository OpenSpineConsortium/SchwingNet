#!/bin/bash
#SBATCH --job-name=xr_fetch
#SBATCH --partition=reqp
#SBATCH --qos=requeue
#SBATCH --requeue
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=4-00:00:00
#SBATCH --output=logs/%x_%j.out
# Stage 1 of the X-ray chain: fetch every open set of grid/fetch-xray.json to the data root
# (tools/fetch_sources.py --run). Compute nodes have internet; the login node runs nothing, so
# this is submitted by grid/run-xray-chain.sh with -D <repo>/grid, where logs/ exists. A requeue
# keeps the job id and the helpers resume their .part files. The report is
# logs/01-fetch-STAGE-REPORT.md beside this log. FETCH_ARGS carries --only and --credentialed.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
FETCH_ARGS=${FETCH_ARGS:-}
export PYTHONNOUSERSITE=1 TMPDIR=${TMPDIR_OVERRIDE:-/rs/rs_grp_oschome/go2432/tmp}
mkdir -p logs "$TMPDIR"
echo "XR_FETCH start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-} restart ${SLURM_RESTART_COUNT:-0}: $FETCH_ARGS"
# shellcheck disable=SC2086
"$PYDRV" "$REPO/tools/fetch_sources.py" --run --python "$PYDRV" --report logs/01-fetch-STAGE-REPORT.md $FETCH_ARGS
rc=$?
echo "XR_FETCH_RC=$rc $(date '+%F %T')"
exit $rc
