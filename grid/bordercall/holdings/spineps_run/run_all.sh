#!/bin/bash
# Runs SPINEPS one CT a process over a job list of run_spineps.py's, in its order, skipping CTs already
# on their grid, then once more over those that failed, each CT's exit written to OUT/exits.txt. It
# starts no CT after STOP_AFTER seconds (4800 unless set), so it ends inside a cloud session's two-hour
# limit for a background command and never cuts a CT off midway; run it again to go on. It first waits
# for any SPINEPS run already going, and before each CT while OUT/PAUSE stands, so a reader of whole
# masks can run alone. MALLOC_ARENA_MAX=2 keeps glibc from giving each of torch's threads an arena of
# its own, which changes no number and lowers the peak. PYTHON is the environment SPINEPS 2.1.2 is
# installed in, SPINEPS_SEGMENTOR_MODELS the folder of its models, FOLD_PATCH_DIR where fold_patch.py
# keeps the spine-finding step's folds.
#
#     run_all.sh JOBS.json OUT
set -u
JOBS=$1 OUT=$2
HERE=$(cd "$(dirname "$0")" && pwd)
STOP_AFTER=${STOP_AFTER:-4800}
PYTHON=${PYTHON:-python3}
export MALLOC_ARENA_MAX=2 SPINEPS_SEGMENTOR_MODELS FOLD_PATCH_DIR=${FOLD_PATCH_DIR:-$OUT}
start=$(date +%s)
while pgrep -f "run_spineps.py" > /dev/null; do sleep 15; done
ids=$("$PYTHON" -c "import json, sys; print(' '.join(j['id'] for j in json.load(open(sys.argv[1]))))" "$JOBS")
for pass in 1 2; do
  for id in $ids; do
    [ -e "$OUT/$id/ctgrid/input.json" ] && continue
    if [ $pass = 1 ] && grep -q "^$id exit [^0]" "$OUT/exits.txt" 2>/dev/null; then continue; fi
    while [ -e "$OUT/PAUSE" ]; do sleep 15; done
    if [ $(( $(date +%s) - start )) -gt "$STOP_AFTER" ]; then echo "stopped before $id"; exit 0; fi
    "$PYTHON" -W ignore "$HERE/run_spineps.py" "$JOBS" "$OUT" "$id" 4 >> "$OUT/run.log" 2>&1
    echo "$id exit $? $(date -u +%H:%M) pass $pass" >> "$OUT/exits.txt"
  done
done
echo "all done"
