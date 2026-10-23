#!/bin/bash
# The lab volume's use in the layout of WSU's wsuquota, which reads only the home directory (the
# owner's ask of 2026-10-23): used, free and total under the CephFS quota of /rs/rs_grp_oschome, its
# file count and a bar, then what the admitted fetches still running have yet to land and the room
# that leaves a new fetch. The figures are the folder's own CephFS attributes, read with no walk, the
# same reading the size rule decides by (grid/size-rule.sh), or the folder's size by stat where its
# use reads as no count (#170). Runs on the login node with bash, getfattr, squeue, awk and coreutils
# alone; the gate word status prints the same lines.
#
#   bash ~/SchwingNet/grid/oschome-quota.sh
#
# VOLUME and DATA_ROOT name other folders, SCHWINGNET another checkout. Exit 0, or 2 when the volume
# has no quota that can be read.
set -uo pipefail
REPO=${SCHWINGNET:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
VOLUME=${VOLUME:-/rs/rs_grp_oschome}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
# shellcheck source=grid/size-rule.sh
. "$REPO/grid/size-rule.sh"
quota_readout "$VOLUME" "Lab Volume Disk Usage, $VOLUME (CephFS quota; 1 gb = 10^9 bytes)" || exit 2
