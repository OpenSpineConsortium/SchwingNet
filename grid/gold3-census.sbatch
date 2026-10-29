#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=24:00:00
# The gold tier census: one CPU job that reads what the grid holds and segments nothing (the owner's tap
# of 2026-10-29 12:26 UTC on "Send the 1 CPU job now": "The gate word's PR is merged once green and 1 CPU
# job is sent that reads only and segments nothing"; docs/research/gold3-ct/README.md section 7).
# grid/gate.sh's word `census gold3` queues it once as the batch class; the next send prints its report.
#
# Parts, each `tools/gold3_census.py <part>`, in this order, each writing <part>.json (what stays on the
# grid) and <part>.lines (what the report carries) under $OUT:
#   ts142    the older list of 142 TotalSegmentator subjects beside rule 3's admitted
#   autopet  autoPET's CTs in FDG-PET-CT-Lesions matched to ENHANCE.PET's studies by their grids
#   gold4    the field test over the census's SPINEPS masks, counts by collection
#   extent   TotalSegmentator's CTs read whole: their own padded planes, the field test again
#   held     the members' files on the data root against the sums recorded in the repository
# A part that fails is reported and the next one still runs, since each reads its own files.
#
# The job runs from its own copy of the tool, tools/gold3_field.py and data/gold3-ct/ under $OUT/code,
# taken from git's objects at the commit the gate sent it from (CENSUS_COMMIT), so it reads no working
# tree, takes no hold on the checkout and runs the code the owner's tap covered however the checkout
# moves while it waits. The interpreter is train-cpu's (numpy, no nibabel) inside the container where
# its environment is made, else the first of the SPINEPS environments' and the system's that imports
# numpy.
#
# The batch class is the requeue QoS, whose jobs a higher priority can stop and start again, so the job
# is requeueable (the class's default, which keeps the one job id): started again, it finds its folder
# by that id, keeps every part already done and runs the rest. Slurm's warning before the wall time, a
# preemption and a cancel all arrive as TERM: the part running is stopped, what it had written is kept,
# and the report says during which part the job ended.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
RS=${RS_ROOT:-$LAB/go2432}
DATA=${DATA_ROOT:-$RS/data}
CENSUS_ROOT=${CENSUS_ROOT:-$RS/gold3_census}
CPUS=${SLURM_CPUS_PER_TASK:-4}
PARTS=${CENSUS_PARTS:-ts142 autopet gold4 extent held}
COMMIT=${CENSUS_COMMIT:-}
RESTARTS=${SLURM_RESTART_COUNT:-0}
REPORT=$REPO/grid/logs/CENSUS-gold3.md
OUT=$CENSUS_ROOT/${SLURM_JOB_ID:-$$}
mkdir -p "$REPO/grid/logs" "$OUT"
chmod 700 "$CENSUS_ROOT" "$OUT" 2>/dev/null
export PYTHONNOUSERSITE=1
# Every line after "FAILED:" is worded with no quote, slash, file name or long number, since the gate
# withholds a reason that could quote a value (grid/report-shapes.awk); tests/test_gate.py holds them to it.
report() { echo "- $*" >> "$REPORT.part"; }
finish() {
  report "exit $1 at $(date -u '+%F %T') UTC"
  mv "$REPORT.part" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_CENSUS_RC=$1"
  exit "$1"
}
part=none child=""
interrupted() {
  if [ -n "$child" ]; then
    kill -TERM "$child" 2>/dev/null
    wait "$child" 2>/dev/null
  fi
  [ ! -f "$OUT/$part.lines" ] || sed 's/^/- /' "$OUT/$part.lines" >> "$REPORT.part"
  report "FAILED: ended by a signal during $part; the parts done are kept, and a requeue of this job carries on after them"
  finish 143
}
trap interrupted TERM
if [ "$RESTARTS" -gt 0 ]; then
  # Started again by Slurm under the same job id: the report so far is taken up where it stopped.
  [ ! -f "$REPORT" ] || [ -f "$REPORT.part" ] || mv "$REPORT" "$REPORT.part"
  echo "# census gold3: job ${SLURM_JOB_ID:-none} started again (restart $RESTARTS) on $(hostname), $(date -u '+%F %T') UTC" >> "$REPORT.part"
else
  echo "# census gold3: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${COMMIT:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"
fi

# The copy the parts run from, taken from git at the gate's commit, kept across a restart.
if [ ! -f "$OUT/code/tools/gold3_census.py" ]; then
  [ -n "$COMMIT" ] || { report "FAILED: the gate named no commit to copy the code from"; finish 2; }
  mkdir -p "$OUT/code" || { report "FAILED: no room for the copy of the code under the census folder"; finish 2; }
  if ! git -C "$REPO" archive "$COMMIT" tools/gold3_census.py tools/gold3_field.py data/gold3-ct | tar -x -C "$OUT/code"; then
    report "FAILED: the code could not be copied from the commit the gate named"
    finish 2
  fi
  [ -f "$OUT/code/tools/gold3_census.py" ] && [ -f "$OUT/code/tools/gold3_field.py" ] && [ -d "$OUT/code/data/gold3-ct" ] \
    || { report "FAILED: the commit the gate named holds no census tool, field test or gold 3 records"; finish 2; }
fi

PY=""
for cand in "${PYDRV:-$REPO/grid/bin/train-cpu-python}" "$HOME/mambaforge/envs/spineps/bin/python" \
            "$RS/envs/spineps212/bin/python" "$(command -v python3)"; do
  [ -n "$cand" ] && [ -x "$cand" ] || continue
  if "$cand" -c "import numpy" >/dev/null 2>&1; then PY=$cand; break; fi
done
[ -n "$PY" ] || { report "FAILED: no interpreter that imports numpy among train-cpu, the SPINEPS environments and the system"; finish 2; }
report "interpreter: $(basename "$PY"), Python $("$PY" -c 'import sys; print(sys.version.split()[0])'), numpy $("$PY" -c 'import numpy; print(numpy.__version__)')"
report "code: the tool, the field test and the gold 3 records from commit ${COMMIT:0:7}; nothing segmented, nothing trained"

failed=0
for part in $PARTS; do
  if [ -f "$OUT/$part.lines" ] && [ -f "$OUT/$part.json" ]; then
    report "$part: done before this restart, its lines above"
    continue
  fi
  began=$(date -u +%s)
  # Run in the background and waited for, so a TERM reaches the trap at once and not when the part ends.
  "$PY" "$OUT/code/tools/gold3_census.py" "$part" --data "$DATA" --rs "$RS" --home "$HOME" --out "$OUT" \
       --workers "$CPUS" > "$OUT/$part.out" 2>&1 &
  child=$!
  wait "$child"
  rc=$?
  child=""
  if [ "$rc" -eq 0 ] && [ -f "$OUT/$part.lines" ]; then
    sed 's/^/- /' "$OUT/$part.lines" >> "$REPORT.part"
    report "$part: done in $(( ($(date -u +%s) - began) / 60 )) min"
  else
    failed=1
    # the error's kind alone, since its message may name a path; the whole output stays under the census folder
    report "FAILED: $part ended after $(( ($(date -u +%s) - began) / 60 )) min with exit $rc, $(tail -n 1 "$OUT/$part.out" 2>/dev/null | cut -d: -f1 | tr -cd 'A-Za-z0-9_ ' | cut -c1-80)"
  fi
done
finish "$failed"
