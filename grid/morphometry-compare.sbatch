#!/bin/bash
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=02:00:00
# The morphometry rows of the reruns of 2026-10-31 set beside the rows they replaced: one CPU job that
# reads each set's new rows and its newest kept/<job>/ rows and writes, per population, measure and
# level, how far the values moved (grid/morphometry_compare.py says what it reads and writes). The
# rows never leave the grid; the aggregates, the grid of changes as SVG and report.lines do.
# grid/gate.sh's word `morphometry compare` queues it as the batch class; the next send prints its report.
#
# It reads the rows under $MORPHOMETRY_ROOT and writes only under $MORPHOMETRY_ROOT/compare/<job>, from
# its own copy of grid/morphometry_compare.py taken from git's objects at the commit the gate sent it
# from (COMPARE_COMMIT), so it holds no checkout. Its interpreter is the first Python 3.8 or later of
# COMPARE_PYTHON (which the gate never sets; a test's), the SPINEPS environment in the owner's home and
# the system's python3; the tool needs the standard library alone.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
RS=${RS_ROOT:-$LAB/go2432}
MORPHOMETRY=${MORPHOMETRY_ROOT:-$RS/morphometry}
COMMIT=${COMPARE_COMMIT:-}
REPORT=$REPO/grid/logs/MORPHOMETRY-compare.md
OUT=$MORPHOMETRY/compare/${SLURM_JOB_ID:-$$}
umask 077
mkdir -p "$REPO/grid/logs" "$OUT"
export PYTHONNOUSERSITE=1
# Every line after "FAILED:" is worded with no quote, slash, file name or long number, since the gate
# withholds a reason that could quote a value (grid/report-shapes.awk).
report() { echo "- $*" >> "$REPORT.part"; }
finish() {
  report "exit $1 at $(date -u '+%F %T') UTC"
  mv "$REPORT.part" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_COMPARE_RC=$1"
  exit "$1"
}
trap 'report "FAILED: ended by a signal; send the word again to compare from the start"; finish 143' TERM
echo "# morphometry compare: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${COMMIT:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"

if [ ! -f "$OUT/code/grid/morphometry_compare.py" ]; then
  [ -n "$COMMIT" ] || { report "FAILED: the gate named no commit to copy the code from"; finish 2; }
  mkdir -p "$OUT/code" && git -C "$REPO" archive "$COMMIT" grid/morphometry_compare.py | tar -x -C "$OUT/code" \
    || { report "FAILED: the code could not be copied from the commit the gate named"; finish 2; }
fi

PY=""
for candidate in "${COMPARE_PYTHON:-}" "$HOME/mambaforge/envs/spineps/bin/python" "$(command -v python3)"; do
  [ -n "$candidate" ] && [ -x "$candidate" ] || continue
  "$candidate" -c "import sys; sys.exit(sys.version_info < (3, 8))" >/dev/null 2>&1 && { PY=$candidate; break; }
done
[ -n "$PY" ] || { report "FAILED: no Python 3.8 or later among the SPINEPS environment and the system"; finish 2; }
report "code: grid/morphometry_compare.py from commit ${COMMIT:0:7}, Python $("$PY" -c 'import sys; print(sys.version.split()[0])'); reads the rows only"

began=$(date -u +%s)
"$PY" "$OUT/code/grid/morphometry_compare.py" --morphometry "$MORPHOMETRY" --out "$OUT" > "$OUT/compare.out" 2>&1
rc=$?
seconds=$(( $(date -u +%s) - began ))
if { [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; } && [ -f "$OUT/report.lines" ]; then
  sed 's/^/- /' "$OUT/report.lines" >> "$REPORT.part"
  report "the comparison: done in $seconds s; compare.csv and one SVG a population under the morphometry root's compare/${SLURM_JOB_ID:-$$}"
  [ "$rc" -eq 0 ] && finish 0
  finish 1
fi
report "FAILED: the comparison ended after $seconds s with exit $rc"
finish 1
