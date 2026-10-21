#!/bin/bash
#SBATCH --job-name=xr_leakjoin
#SBATCH --partition=reqp
#SBATCH --qos=requeue
#SBATCH --requeue
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x_%j.out
# The leak checks, step 2 of 2 (issue #9): after every task of the fingerprint array (afterany, so
# a task that failed is counted here and not left as a join that never starts), CHK-6 and CHK-7
# over the fingerprint of every shard in LEAKS_LIST (tools/leaks.py join): a shard listed with no
# fingerprint, or one for another manifest, fails the join, as does any frame no key was taken
# from. NEW, when set, checks one new shard against the rest (its name or its folder). LEAKS.json
# and LEAKS.md go to LEAKS_RUN; the report is also logs/05-leaks-STAGE-REPORT.md. The default
# environment is enough; the train-cpu one serves too.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
LEAKS_LIST=${LEAKS_LIST:?LEAKS_LIST names the shard list grid/run-leaks.sh wrote}
LEAKS_OUT=${LEAKS_OUT:?LEAKS_OUT names the folder the fingerprints are in}
LEAKS_RUN=${LEAKS_RUN:-$(dirname "$LEAKS_LIST")}
DECLARED=${DECLARED:-$REPO/data/splits/aliases.json}
NEW=${NEW:-}
REPORT=logs/05-leaks-STAGE-REPORT.md
export PYTHONNOUSERSITE=1
mkdir -p logs
echo "XR_LEAKJOIN start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-}"
files=()
while IFS= read -r shard; do
  [ -n "$shard" ] || continue
  files+=("$LEAKS_OUT/fingerprints/$(basename "$(dirname "$(dirname "$shard")")")__$(basename "$shard").jsonl")
done < "$LEAKS_LIST"
args=(join --fingerprints "${files[@]}" --expect "$LEAKS_LIST" --declared "$DECLARED" --out "$LEAKS_RUN"
      --workers "${SLURM_CPUS_PER_TASK:-1}")
[ -z "$NEW" ] || args+=(--new "$NEW")
out=$("$PYDRV" "$REPO/tools/leaks.py" "${args[@]}" 2>&1)
rc=$?
echo "$out"
{
  echo "# The leak checks: $(date '+%F %T')"
  echo
  echo "- shards listed: ${#files[@]} ($LEAKS_LIST)"
  echo "- join: $(echo "$out" | tail -n 1)"
  echo "- the rows: $LEAKS_RUN/LEAKS.md and LEAKS.json"
  if [ "$rc" = 0 ]; then echo "- PASS: no near-duplicate across the split, no undeclared alias, every frame fingerprinted"
  else echo "- FAIL (exit $rc): no shard of this run is registered, and no training step reads it, until LEAKS.md is read and settled"; fi
} > "$REPORT"
cat "$REPORT"
echo "XR_LEAKJOIN_RC=$rc $(date '+%F %T')"
exit $rc
