#!/bin/bash
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=02:00:00
# What each unmapped folder of the data root holds (tools/folder_report.py, #296; the owner's yes
# of 2026-10-25 to one read-only job): queued by the gate word `folders`, it reads the newest whole
# sample index read-only, and the first lines of the README and notes files near each folder's top,
# and writes logs/FOLDERS-<n>.md, aggregates and folder names only, which the next sends print one
# page at a time. It writes nothing on the volume.
#   FOLDERS_DB  the samples.sqlite the gate found
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PYDRV=${PYDRV:-python3}
db=${FOLDERS_DB:?FOLDERS_DB names the sample index}
export PYTHONNOUSERSITE=1
mkdir -p logs
rm -f logs/FOLDERS-*.md
echo "FOLDERS start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-}"
"$PYDRV" "$REPO/tools/folder_report.py" --db "$db" --out logs/FOLDERS.md 2> logs/FOLDERS.err
rc=$?
if [ "$rc" != 0 ]; then
  # A failure becomes the one page, so the next send prints why and queues no job of its own.
  rm -f logs/FOLDERS-*.md
  { echo "## the folder report failed (exit $rc, job ${SLURM_JOB_ID:-})"; echo; tail -n 40 logs/FOLDERS.err; } > logs/FOLDERS-1.md
fi
cat logs/FOLDERS.err >&2
chmod 644 logs/FOLDERS-*.md
echo "FOLDERS_RC=$rc $(date '+%F %T')"
exit $rc
