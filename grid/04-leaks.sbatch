#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=1-00:00:00
# The leak checks, step 1 of 2 (issue #9): one task of a Slurm array per shard, which writes that
# shard's fingerprint file (tools/leaks.py fingerprint: the store key checked against the manifest,
# the pixel key, the perceptual hash and the 64 x 64 reduction of every frame). grid/run-leaks.sh
# writes the shard list and submits this array and the join after it; the task reads line
# SLURM_ARRAY_TASK_ID + 1 of LEAKS_LIST. The file lands in LEAKS_OUT/fingerprints/ under the
# shard's source and name, and a file already there for the same manifest with no failed frame
# is kept, so a second run redoes nothing; the frames are written a chunk of 1,024 at a time
# beside it (<file>.parts/), so a task the partition requeues decodes only the chunks it had not
# finished. A frame that could not be
# fingerprinted makes the task exit 2 after writing the file; the join, which runs afterany,
# counts it as a failure, since unknown is not clean. PYDRV must hold numpy and Pillow (the
# train-cpu environment).
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
LEAKS_LIST=${LEAKS_LIST:?LEAKS_LIST names the shard list grid/run-leaks.sh wrote}
LEAKS_OUT=${LEAKS_OUT:?LEAKS_OUT names the folder the fingerprints go to}
task=${SLURM_ARRAY_TASK_ID:?this script is one task of an array}
export PYTHONNOUSERSITE=1
mkdir -p logs "$LEAKS_OUT/fingerprints"
shard=$(sed -n "$((task + 1))p" "$LEAKS_LIST")
if [ -z "$shard" ]; then
  echo "no line $((task + 1)) in $LEAKS_LIST"; echo "XR_LEAKPRINT_RC=2"; exit 2
fi
source_id=$(basename "$(dirname "$(dirname "$shard")")")
out=$LEAKS_OUT/fingerprints/${source_id}__$(basename "$shard").jsonl
echo "XR_LEAKPRINT start $(date '+%F %T') on $(hostname) job ${SLURM_ARRAY_JOB_ID:-}_${task}: $shard"
"$PYDRV" "$REPO/tools/leaks.py" fingerprint --shard "$shard" --out "$out" --workers "${SLURM_CPUS_PER_TASK:-1}"
rc=$?
echo "XR_LEAKPRINT_RC=$rc $(date '+%F %T')"
exit $rc
