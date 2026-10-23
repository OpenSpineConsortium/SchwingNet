#!/bin/bash
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=02:00:00
# The deletion of one fetched set's download archives (tools/dropzip.py; the owner's word of
# 2026-10-23), queued by the gate word `dropzip <id>`: each zip under its raw folder is deleted
# only when every file in it sits unpacked beside it at the same size. The report goes to
# logs/DROPZIP-<id>.md, which the next `dropzip <id>` prints.
#   DROPZIP_ID   the set's id
#   DROPZIP_RAW  its raw folder
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
id=${DROPZIP_ID:?DROPZIP_ID names the set}
raw=${DROPZIP_RAW:?DROPZIP_RAW names its raw folder}
export PYTHONNOUSERSITE=1
mkdir -p logs
echo "DROPZIP start $id $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-}"
"$PYDRV" "$REPO/tools/dropzip.py" --id "$id" --raw "$raw" --out "logs/DROPZIP-$id.md"
rc=$?
[ "$rc" != 0 ] || chmod 644 "logs/DROPZIP-$id.md"
echo "DROPZIP_RC=$rc $(date '+%F %T')"
exit $rc
