#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=04:00:00
# One look inside one fetched set (tools/explore.py; the owner's choice of 2026-10-23), queued by
# the gate word `explore <id>`: the listing of its raw folder and zips and, where the gate names a
# set to compare it with, the comparison by name and by content. The report goes to
# logs/EXPLORE-<id>.md, which the next `explore <id>` prints; it holds counts, the set's own folder
# and class names and a few example pairs, never a folder of the volume.
#   EXPLORE_ID       the set's id
#   EXPLORE_RAW      its raw folder
#   EXPLORE_AGAINST  label=folder pairs joined by |, or nothing
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
id=${EXPLORE_ID:?EXPLORE_ID names the set}
raw=${EXPLORE_RAW:?EXPLORE_RAW names its raw folder}
export PYTHONNOUSERSITE=1
mkdir -p logs
args=(--id "$id" --raw "$raw" --out "logs/EXPLORE-$id.md" --workers "${SLURM_CPUS_PER_TASK:-8}")
IFS='|' read -r -a pairs <<< "${EXPLORE_AGAINST:-}"
for pair in ${pairs[@]+"${pairs[@]}"}; do [ -z "$pair" ] || args+=(--against "$pair"); done
echo "EXPLORE start $id $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-}"
"$PYDRV" "$REPO/tools/explore.py" "${args[@]}"
rc=$?
[ "$rc" != 0 ] || chmod 644 "logs/EXPLORE-$id.md"
echo "EXPLORE_RC=$rc $(date '+%F %T')"
exit $rc
