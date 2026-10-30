#!/bin/bash
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
# The gold tier 3 morphometry beside each person's sex and age: one CPU job that joins the rows the two
# morphometry sets measured with the persons they belong to and writes the aggregates a sex and age
# analysis starts from (the thread "Extract morphometrics from gold tier 3 CT", 2026-10-30;
# tools/gold3_covariates.py says where each person, sex and age comes from). grid/gate.sh's word
# `morphometry covariates` queues it once as the batch class, on the owner's count, once both sets'
# reports stand and ended 0; the next send prints its report a page at a time.
#
# It reads, and writes only under its own folder: the rows of both sets under $MORPHOMETRY_ROOT
# (enhance/rows.csv, verse/rows.csv, verse/totalseg/rows.csv), the census's map of autoPET's studies to
# their PETCT keys (AUTOPET, the census job's autopet.json), the sample index (INDEX, samples.sqlite) for
# autoPET's DICOM sex, age, weight and height, VerSeFusion's demographics table (VERSE_DEMOGRAPHICS), the
# TotalSegmentator release's meta.csv under the data root, and the headers of ENHANCE.PET's CTs, read to
# find again the one CT off its mask's grid. The joined per-person tables, persons.csv and joined.csv,
# stay in $MORPHOMETRY_ROOT/covariates/<job>, made 0700 with every file in it 0600 (umask 077), and
# never leave the grid; the report, grid/logs/MORPHOMETRY-covariates.md, carries the aggregates of
# report.lines alone, and no path: the interpreter by its name, the code by its commit.
#
# The job runs from its own copy of the tool, the census's NIfTI reader beside it and data/gold3-ct/,
# taken from git's objects at the commit the gate sent it from (COVARIATES_COMMIT), so it reads no
# working tree, takes no hold on the checkout and runs the code the owner's count covered however the
# checkout moves while it waits. The interpreter is the first of train-cpu's, the SPINEPS environments'
# and the system's that imports numpy and sqlite3.
#
# The batch class is the requeue QoS, so the job is requeueable: started again under the same job id,
# it keeps its copy of the code and runs the join again from the start, which writes every file anew,
# beginning a fresh report. Slurm's warning before the wall time, a preemption and a cancel arrive as
# TERM: the join is stopped and the report says so.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
RS=${RS_ROOT:-$LAB/go2432}
DATA=${DATA_ROOT:-$RS/data}
MORPHOMETRY=${MORPHOMETRY_ROOT:-$RS/morphometry}
AUTOPET=${AUTOPET:-}
INDEX=${INDEX:-}
VERSE_DEMOGRAPHICS=${VERSE_DEMOGRAPHICS:-$HOME/VerSeFusion/configs/verse_demographics.csv}
CPUS=${SLURM_CPUS_PER_TASK:-4}
COMMIT=${COVARIATES_COMMIT:-}
RESTARTS=${SLURM_RESTART_COUNT:-0}
REPORT=$REPO/grid/logs/MORPHOMETRY-covariates.md
OUT=$MORPHOMETRY/covariates/${SLURM_JOB_ID:-$$}
umask 077
mkdir -p "$REPO/grid/logs" "$OUT"
chmod 700 "$MORPHOMETRY/covariates" "$OUT" 2>/dev/null
export PYTHONNOUSERSITE=1
# Every line after "FAILED:" is worded with no quote, slash, file name or long number, since the gate
# withholds a reason that could quote a value (grid/report-shapes.awk); tests/test_gate.py holds them to it.
report() { echo "- $*" >> "$REPORT.part"; }
finish() {
  report "exit $1 at $(date -u '+%F %T') UTC"
  mv "$REPORT.part" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_COVARIATES_RC=$1"
  exit "$1"
}
child=""
interrupted() {
  if [ -n "$child" ]; then
    kill -TERM "$child" 2>/dev/null
    wait "$child" 2>/dev/null
  fi
  report "FAILED: ended by a signal during the join; a requeue of this job runs the join again from the start"
  finish 143
}
trap interrupted TERM
# A restart begins a fresh report, the one a stopped run left set aside under its restart's number.
[ "$RESTARTS" -eq 0 ] || [ ! -f "$REPORT.part" ] || mv "$REPORT.part" "$REPORT.part.$RESTARTS"
echo "# morphometry covariates: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${COMMIT:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"
[ "$RESTARTS" -eq 0 ] || report "started again by Slurm (restart $RESTARTS) under the same job id; the join runs from the start"

# The copy the join runs from, taken from git at the gate's commit, kept across a restart.
if [ ! -f "$OUT/code/tools/gold3_covariates.py" ]; then
  [ -n "$COMMIT" ] || { report "FAILED: the gate named no commit to copy the code from"; finish 2; }
  mkdir -p "$OUT/code" || { report "FAILED: no room for the copy of the code under the job folder"; finish 2; }
  if ! git -C "$REPO" archive "$COMMIT" tools/gold3_covariates.py tools/gold3_census.py tools/gold3_field.py data/gold3-ct \
      | tar -x -C "$OUT/code"; then
    report "FAILED: the code could not be copied from the commit the gate named"
    finish 2
  fi
  [ -f "$OUT/code/tools/gold3_covariates.py" ] && [ -f "$OUT/code/tools/gold3_census.py" ] && [ -d "$OUT/code/data/gold3-ct" ] \
    || { report "FAILED: the commit the gate named holds no join tool, census reader or gold 3 records"; finish 2; }
fi

PY=""
for cand in "${PYDRV:-$REPO/grid/bin/train-cpu-python}" "$HOME/mambaforge/envs/spineps/bin/python" \
            "$RS/envs/spineps212/bin/python" "$(command -v python3)"; do
  [ -n "$cand" ] && [ -x "$cand" ] || continue
  if "$cand" -c "import numpy, sqlite3" >/dev/null 2>&1; then PY=$cand; break; fi
done
[ -n "$PY" ] || { report "FAILED: no interpreter that imports numpy and sqlite3 among train-cpu, the SPINEPS environments and the system"; finish 2; }
report "interpreter: $(basename "$PY"), Python $("$PY" -c 'import sys; print(sys.version.split()[0])'), numpy $("$PY" -c 'import numpy; print(numpy.__version__)')"
report "code: the join tool, the census reader and the gold 3 records from commit ${COMMIT:0:7}; reads only, the per-person tables stay in the job folder"

began=$(date -u +%s)
# Run in the background and waited for, so a TERM reaches the trap at once and not when the join ends.
"$PY" "$OUT/code/tools/gold3_covariates.py" --morphometry "$MORPHOMETRY" --autopet "$AUTOPET" --index "$INDEX" \
     --verse-demographics "$VERSE_DEMOGRAPHICS" --data "$DATA" --out "$OUT" --workers "$CPUS" > "$OUT/join.out" 2>&1 &
child=$!
wait "$child"
rc=$?
child=""
minutes=$(( ($(date -u +%s) - began) / 60 ))
# 0 is a whole join, 3 a join whose report says what failed in its own FAILED lines; both wrote report.lines.
if { [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; } && [ -f "$OUT/report.lines" ]; then
  sed 's/^/- /' "$OUT/report.lines" >> "$REPORT.part"
  report "the join: done in $minutes min$([ "$rc" -eq 0 ] || echo ", with the failures its FAILED lines name")"
  [ "$rc" -eq 0 ] && finish 0
  finish 1
fi
# the error's kind alone, since its message may name a path; the whole output stays in the job folder
report "FAILED: the join ended after $minutes min with exit $rc, $(tail -n 1 "$OUT/join.out" 2>/dev/null | cut -d: -f1 | tr -cd 'A-Za-z0-9_ ' | cut -c1-80)"
finish 1
