#!/bin/bash
#SBATCH --job-name=dp_reacquire
#SBATCH --partition=reqp
#SBATCH --qos=requeue
#SBATCH --requeue
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=4-00:00:00
#SBATCH --output=logs/%x_%j.out
# Run reacquire.py inside a compute-node job (compute nodes have internet; the login node must never fetch).
# Slurm opens --output before this script runs, so logs/ must exist in the submit directory first (it is committed
# as logs/.gitkeep; the mkdir below is for a copy that lost it):
#   cd ~/spinesurg-ct-nnunet/data_platform/reacquire && mkdir -p logs
#   sbatch -D "$PWD" --export=ALL,IDS="carmlspine geneva_hip",MODE=--run reacquire.sbatch
#   sbatch -D "$PWD" --export=ALL,IDS="carmlspine",MODE=--verify reacquire.sbatch
#   sbatch -D "$PWD" --export=ALL,IDS="--all --modes run",MODE=--run reacquire.sbatch
# A requeue keeps the job id: reacquire.py then skips the submit-mode commands this job already ran (no duplicate
# child jobs), and the fetch helpers resume their .part files.
# Secrets (HF_TOKEN for gated Hugging Face repos, KAGGLE_API_TOKEN) are passed in the environment by the submitter;
# this script never reads a token file.
set -uo pipefail
IDS=${IDS:?set IDS to one or more source ids, or --all}
MODE=${MODE:---run}
export PYTHONNOUSERSITE=1 TMPDIR=${TMPDIR_OVERRIDE:-/rs/rs_grp_oschome/go2432/tmp}
mkdir -p logs "$TMPDIR"
DRIVER="${DRIVER:-$HOME/spinesurg-ct-nnunet/data_platform/reacquire/reacquire.py}"
PYDRV=${PYDRV:-python3}
[ -f "$DRIVER" ] || { echo "no $DRIVER: commit and push data_platform/, then pull it on the grid"; exit 2; }
echo "DP_REACQUIRE start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-} restart ${SLURM_RESTART_COUNT:-0}: $MODE $IDS"
# shellcheck disable=SC2086
"$PYDRV" "$DRIVER" $MODE $IDS
rc=$?
echo "DP_REACQUIRE_RC=$rc $(date '+%F %T')"
exit $rc
