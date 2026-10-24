#!/bin/bash
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:20:00
# The lab volume's readout as a compute node reads it (the owner's yes of 2026-10-24 to the probe
# that docs/research/lab-volume-room.md in symphony-template asks for after SchwingNet #191): the
# size rule decides in the fetch and unpack jobs, on compute nodes, while the status word reads the
# volume on the login node, so a node whose CephFS mount had its root at the volume would read no
# quota above it. Queued by the gate word `nodequota`, it prints the same readout the status word
# does, with each folder above the volume up to the root of the node's mount, to
# logs/NODEQUOTA.md, which the next `nodequota` prints. It reads and writes nothing on the volume.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
VOLUME=${VOLUME:-/rs/rs_grp_oschome}
export PYTHONNOUSERSITE=1
# shellcheck source=grid/size-rule.sh
. "$REPO/grid/size-rule.sh"
# A compute node may have no getfattr; the job's own python reads the attributes there, as
# grid/unpack.sbatch does, unless a test says so.
if [ "${SIZE_RULE_STAND_INS:-}" = yes ]; then
  RULE_PYTHON=${XATTR_PYTHON:-$PYDRV}
else
  RULE_PYTHON=$PYDRV
fi
mkdir -p logs
echo "NODEQUOTA start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-}"
{
  echo "# The lab volume as compute node $(hostname) reads it, $(date -u '+%F %T') UTC, job ${SLURM_JOB_ID:-}"
  # The words name no folder but the volume, as the status word's do; every folder above is named
  # by how far above the volume it lies.
  quota_readout "$VOLUME" "Lab Volume Disk Usage on a compute node, $VOLUME (CephFS quota; 1 gb = 10^9 bytes)"
  echo "readout exit $?"
  echo "Above the volume, whatever the rule decides, each folder by how far above the volume it lies:"
  above_words "$VOLUME" | sed 's/^/  /'
} > logs/NODEQUOTA.md.part 2>&1
rc=$?
mv logs/NODEQUOTA.md.part logs/NODEQUOTA.md && chmod 644 logs/NODEQUOTA.md
echo "NODEQUOTA_RC=$rc $(date '+%F %T')"
exit $rc
