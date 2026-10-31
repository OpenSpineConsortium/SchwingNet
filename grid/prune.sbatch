#!/bin/bash
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=12:00:00
# One step of a pruning list the owner chose (tools/prune.py; the owner's choice of 2026-10-31,
# issue #515), queued by the gate word `prune <list>`: plan records each raw folder's files and
# bytes and deletes nothing; delete removes a folder only when it still matches its plan. The
# report goes to logs/PRUNE-<list>.plan.md or logs/PRUNE-<list>.done.md, which the next send prints.
#   PRUNE_LIST   the list's name, a file grid/prune/<list>.txt
#   PRUNE_MODE   plan or delete
#   PRUNE_DATA   the data root
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
list=${PRUNE_LIST:?PRUNE_LIST names the list}
mode=${PRUNE_MODE:?PRUNE_MODE is plan or delete}
data=${PRUNE_DATA:?PRUNE_DATA names the data root}
export PYTHONNOUSERSITE=1
mkdir -p logs
echo "PRUNE start $list $mode $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-}"
if [ "$mode" = plan ]; then
  "$PYDRV" "$REPO/tools/prune.py" plan --list "$REPO/grid/prune/$list.txt" --data "$data" \
    --out "logs/PRUNE-$list.plan.json" --report "logs/PRUNE-$list.plan.md"
else
  "$PYDRV" "$REPO/tools/prune.py" delete --list "$REPO/grid/prune/$list.txt" --data "$data" \
    --plan "logs/PRUNE-$list.plan.json" --report "logs/PRUNE-$list.done.md"
fi
rc=$?
echo "PRUNE_RC=$rc $(date '+%F %T')"
exit $rc
