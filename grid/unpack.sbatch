#!/bin/bash
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=1-00:00:00
# The unpacking of one fetched set's download zips beside themselves (tools/unpack.py; the owner's
# word of 2026-10-23 for RSPECT), queued by the gate word `unpack <id>`. It runs under the size rule
# (grid/size-rule.sh): tools/unpack.py size reads what the unpacked files will take from the zips'
# central directories, and the job starts writing only when that fits the room left under the lab
# volume's quota after what the running fetches owe, holding that room while Slurm holds the job.
# The report goes to logs/UNPACK-<id>.md, which the next `unpack <id>` prints.
#   UNPACK_ID   the set's id
#   UNPACK_RAW  its raw folder
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
id=${UNPACK_ID:?UNPACK_ID names the set}
raw=${UNPACK_RAW:?UNPACK_RAW names its raw folder}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
VOLUME=${VOLUME:-/rs/rs_grp_oschome}
# A compute node may have no getfattr; the job's own python reads the quota's attributes there,
# never one the environment it was sent from names, unless a test says so (grid/size-rule.sh, #180).
if [ "${SIZE_RULE_STAND_INS:-}" = yes ]; then
  XATTR_PYTHON=${XATTR_PYTHON:-$PYDRV}
else
  XATTR_PYTHON=$PYDRV
fi
export PYTHONNOUSERSITE=1
# shellcheck source=grid/size-rule.sh
. "$REPO/grid/size-rule.sh"
mkdir -p logs
echo "UNPACK start $id $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-}"
if ! size_and_admit "$id" "$PYDRV" "$REPO/tools/unpack.py" size --raw "$raw"; then
  echo "UNPACK_RC=4 $(date '+%F %T')"
  exit 4
fi
"$PYDRV" "$REPO/tools/unpack.py" unpack --id "$id" --raw "$raw" --out "logs/UNPACK-$id.md"
rc=$?
[ "$rc" != 0 ] || chmod 644 "logs/UNPACK-$id.md"
echo "UNPACK_RC=$rc $(date '+%F %T')"
exit $rc
