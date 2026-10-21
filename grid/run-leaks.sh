#!/bin/bash
# Submit the leak checks (issue #9) as a Slurm array of fingerprint tasks, one per shard, and the
# join after it (bash 4.2; the login node runs nothing but sbatch, find and this script):
#   1. grid/04-leaks.sbatch       one task per shard under <data root>/*/shards/*/, %K at a time
#   2. grid/05-leaks-join.sbatch  CHK-6 and CHK-7 over every fingerprint (afterany:1)
# The shard list is written first, to <out>/runs/<stamp>/shards.txt, and is what the array
# indexes and the join checks it covered; LEAKS.json and LEAKS.md land beside it.
#
#   bash grid/run-leaks.sh                                    # every shard on the volume
#   NEW=carmlspine/2026-10-21-0123456789ab bash grid/run-leaks.sh   # one new shard against the rest
#   CONCURRENCY=32 bash grid/run-leaks.sh                     # 32 array tasks at once (16 unless said)
#   SBATCH=echo bash grid/run-leaks.sh                        # dry run: print the submissions
#   OUTSIDE_SLURM=1 DATA_ROOT=<root> bash grid/run-leaks.sh   # off the grid: the tasks, then the join, here
#
# DATA_ROOT (the grid's data root unless set), LEAKS_OUT (<data root>/_leaks), DECLARED
# (data/splits/aliases.json) and PYDRV (the train-cpu environment, since the fingerprint needs
# numpy and Pillow) can be overridden. A list longer than MAX_ARRAY (1000, Slurm's usual
# MaxArraySize less one) is refused with the count, since sbatch would refuse it anyway.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
SBATCH=${SBATCH:-sbatch}
DATA_ROOT=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
LEAKS_OUT=${LEAKS_OUT:-$DATA_ROOT/_leaks}
CONCURRENCY=${CONCURRENCY:-16}
MAX_ARRAY=${MAX_ARRAY:-1000}
NEW=${NEW:-}
DECLARED=${DECLARED:-$REPO/data/splits/aliases.json}
OUTSIDE_SLURM=${OUTSIDE_SLURM:-}
if [ -z "${PYDRV:-}" ]; then
  if [ -x "$REPO/.pixi/envs/train-cpu/bin/python" ]; then PYDRV=$REPO/.pixi/envs/train-cpu/bin/python
  else PYDRV=python3; fi
fi
[ -f "$REPO/tools/leaks.py" ] || { echo "no $REPO/tools/leaks.py: is SCHWINGNET the checkout?"; exit 2; }
[ -d "$DATA_ROOT" ] || { echo "no data root $DATA_ROOT"; exit 2; }
mkdir -p "$LEAKS_OUT/runs" "$LEAKS_OUT/fingerprints" "$REPO/grid/logs"
# A folder of its own for each run, even two started in one second, so one never overwrites the
# shard list another's array is still reading.
RUN=$(mktemp -d "$LEAKS_OUT/runs/$(date '+%Y%m%d-%H%M%S')-XXXX") || exit 2
LIST=$RUN/shards.txt
# -L and the trailing slash follow a data root or a source folder that is a symbolic link, as a
# source kept on another volume would be; without them find lists none of its shards, and the
# join, which checks only the list, would pass without having seen them.
find -L "$DATA_ROOT/" -mindepth 4 -maxdepth 4 -path '*/shards/*/MANIFEST.json' 2>/dev/null \
  | sed -e 's|/MANIFEST.json$||' -e 's|//*|/|g' | sort > "$LIST"
count=$(wc -l < "$LIST" | tr -dc '0-9')
if [ "$count" = 0 ]; then
  echo "refusing: no MANIFEST.json under $DATA_ROOT/*/shards/; nothing to check"; exit 64
fi
if [ "$count" -gt "$MAX_ARRAY" ]; then
  echo "refusing: $count shards is more than one array of $MAX_ARRAY takes; split the list by hand"; exit 64
fi
echo "shards: $count listed in $LIST"
export SCHWINGNET="$REPO" PYDRV LEAKS_LIST="$LIST" LEAKS_OUT LEAKS_RUN="$RUN" DECLARED NEW

if [ -n "$OUTSIDE_SLURM" ]; then
  # Off the grid: the array's tasks one after another, then the join, each as Slurm would run it.
  cd "$REPO/grid" || exit 2
  for task in $(seq 0 $((count - 1))); do
    SLURM_ARRAY_TASK_ID=$task bash 04-leaks.sbatch
  done
  bash 05-leaks-join.sbatch
  exit $?
fi

submit() {  # submit [sbatch options...] SCRIPT: prints the job id; a dry run prints the line instead
  local out
  if [ "$SBATCH" != sbatch ]; then
    echo "would submit: sbatch --parsable -D $REPO/grid $*" >&2; echo "DRY$(basename "${@: -1}" | cut -c2)"; return 0
  fi
  out=$("$SBATCH" --parsable -D "$REPO/grid" "$@") || { echo "sbatch failed: $out" >&2; return 1; }
  echo "$out" | tail -n 1 | cut -d';' -f1
}
j1=$(submit --array=0-$((count - 1))%"$CONCURRENCY" --export=ALL "$REPO/grid/04-leaks.sbatch") || exit 1
# Both or neither: an array whose join was refused would write fingerprints nobody reads.
j2=$(submit --dependency=afterany:"$j1" --export=ALL "$REPO/grid/05-leaks-join.sbatch") \
  || { "${SCANCEL:-scancel}" "$j1" && echo "cancelled the fingerprint array $j1, since its join was refused" >&2; exit 1; }
echo "$(date '+%F %T') leaks fingerprint=$j1 join=$j2 shards=$count new=${NEW:-none} run=$RUN pydrv=$PYDRV" \
  | tee -a "$REPO/grid/LAST_RUN.txt"
echo "submitted: 4 fingerprint array $j1 ($count tasks, $CONCURRENCY at a time) -> 5 join $j2 (afterany)"
echo "watch: squeue -u \$USER; the report: $REPO/grid/logs/05-leaks-STAGE-REPORT.md; the rows: $RUN/LEAKS.md"
