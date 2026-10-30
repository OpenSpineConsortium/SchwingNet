#!/bin/bash
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
# The gold tier 3 correlation prior: one CPU job that fits, per population, how one person's body and
# end-plate measures move together across levels and measures, from the rows the two morphometry sets
# wrote (greg's direction of 2026-10-30, thread "Train on randomized spine phantoms";
# grid/prior/gold3_prior.py says what it reads and leaves out). grid/gate.sh's word `morphometry prior`
# queues it as the batch class; the next send prints its report.
#
# It reads the rows under $MORPHOMETRY_ROOT and writes only under its own folder, $MORPHOMETRY_ROOT/prior/<job>:
# the priors as JSON (two correlation matrices and counts each, no person) and report.lines, which
# grid/logs/MORPHOMETRY-prior.md carries with no path. It runs from its own copy of grid/prior/ and of
# the records it reads (data/gold3-ct and data/splits), taken from git's objects at the commit the gate
# sent it from (PRIOR_COMMIT), so it holds no checkout. Its interpreter is the first of the SPINEPS
# environment in the owner's home, the lab's spineps212 and the system's python3 that imports numpy on
# Python 3.8 or later (PRIOR_PYTHON, which the gate never sets, comes first for a test).
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
RS=${RS_ROOT:-$LAB/go2432}
MORPHOMETRY=${MORPHOMETRY_ROOT:-$RS/morphometry}
COMMIT=${PRIOR_COMMIT:-}
RESTARTS=${SLURM_RESTART_COUNT:-0}
REPORT=$REPO/grid/logs/MORPHOMETRY-prior.md
OUT=$MORPHOMETRY/prior/${SLURM_JOB_ID:-$$}
umask 077
mkdir -p "$REPO/grid/logs" "$OUT"
export PYTHONNOUSERSITE=1
# Every line after "FAILED:" is worded with no quote, slash, file name or long number, since the gate
# withholds a reason that could quote a value (grid/report-shapes.awk).
report() { echo "- $*" >> "$REPORT.part"; }
finish() {
  report "exit $1 at $(date -u '+%F %T') UTC"
  mv "$REPORT.part" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_PRIOR_RC=$1"
  exit "$1"
}
error_kind() {  # error_kind FILE: the class of the error a traceback's last line names, a plain word, or nothing
  local kind
  kind=$(tail -n 1 "$1" 2>/dev/null | sed -r -n 's/^([A-Za-z_][A-Za-z0-9_.]*)(: .*)?$/\1/p' | sed 's/.*\.//')
  [[ $kind =~ ^[A-Za-z_][A-Za-z0-9_]{0,39}$ ]] || return 0
  [[ $kind =~ [0-9]{5}|[0-9A-Fa-f]{8} ]] && return 0
  echo "$kind"
}
child=""
interrupted() {
  if [ -n "$child" ]; then
    kill -TERM "$child" 2>/dev/null
    wait "$child" 2>/dev/null
  fi
  report "FAILED: ended by a signal during the fit; a requeue of this job runs the fit again from the start"
  finish 143
}
trap interrupted TERM
[ "$RESTARTS" -eq 0 ] || [ ! -f "$REPORT.part" ] || mv "$REPORT.part" "$REPORT.part.$RESTARTS"
echo "# morphometry prior: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${COMMIT:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"
[ "$RESTARTS" -eq 0 ] || report "started again by Slurm (restart $RESTARTS) under the same job id; the fit runs from the start"

if [ ! -f "$OUT/code/grid/prior/gold3_prior.py" ]; then
  [ -n "$COMMIT" ] || { report "FAILED: the gate named no commit to copy the code from"; finish 2; }
  mkdir -p "$OUT/code" || { report "FAILED: no room for the copy of the code under the job folder"; finish 2; }
  if ! git -C "$REPO" archive "$COMMIT" grid/prior data/gold3-ct/admission.json data/gold3-ct/verse/series.json \
      data/splits/latent-prior-test-reserve.json data/splits/latent-prior-repeat-groups.json | tar -x -C "$OUT/code"; then
    report "FAILED: the code could not be copied from the commit the gate named"
    finish 2
  fi
  [ -f "$OUT/code/grid/prior/gold3_prior.py" ] && [ -f "$OUT/code/grid/prior/schwingcheck/correlation.py" ] \
    || { report "FAILED: the commit the gate named holds no prior tool"; finish 2; }
fi

PY="" PY_NAME=""
take() {  # take NAME PATH: PATH becomes the interpreter, unless one is taken, where it imports numpy on 3.8 or later
  [ -z "$PY" ] && [ -n "$2" ] && [ -x "$2" ] || return 0
  if "$2" -c "import sys, numpy; sys.exit(sys.version_info < (3, 8))" >/dev/null 2>&1; then PY=$2 PY_NAME=$1; fi
}
take "the one PRIOR_PYTHON names" "${PRIOR_PYTHON:-}"
take "the SPINEPS environment in the home" "$HOME/mambaforge/envs/spineps/bin/python"
take "the lab spineps212 environment" "$RS/envs/spineps212/bin/python"
take "the system python3" "$(command -v python3)"
[ -n "$PY" ] || { report "FAILED: no interpreter that imports numpy on Python 3.8 or later among the SPINEPS environments and the system"; finish 2; }
report "interpreter: $PY_NAME, Python $("$PY" -c 'import sys; print(sys.version.split()[0])'), numpy $("$PY" -c 'import numpy; print(numpy.__version__)')"
report "code: grid/prior and its records from commit ${COMMIT:0:7}; reads the rows only"

began=$(date -u +%s)
"$PY" "$OUT/code/grid/prior/gold3_prior.py" --morphometry "$MORPHOMETRY" --records "$OUT/code/data" --out "$OUT" > "$OUT/fit.out" 2>&1 &
child=$!
wait "$child"
rc=$?
child=""
seconds=$(( $(date -u +%s) - began ))
if { [ "$rc" -eq 0 ] || [ "$rc" -eq 3 ]; } && [ -f "$OUT/report.lines" ]; then
  sed 's/^/- /' "$OUT/report.lines" >> "$REPORT.part"
  report "the fit: done in $seconds s$([ "$rc" -eq 0 ] || echo ", with the failures its FAILED lines name")"
  [ "$rc" -eq 0 ] && finish 0
  finish 1
fi
kind=$(error_kind "$OUT/fit.out")
if [ -n "$kind" ]; then
  report "FAILED: the fit ended after $seconds s with exit $rc, an error of the kind $kind"
else
  report "FAILED: the fit ended after $seconds s with exit $rc, its output naming no error kind"
fi
finish 1
