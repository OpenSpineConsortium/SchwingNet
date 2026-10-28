#!/bin/bash
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=02:00:00
# One reading list's papers fetched onto the grid (grid/literature_fetch.py; the owner's word of
# 2026-10-27 23:00 UTC: Elsevier on the key route and a fetch that runs as a grid job, reads the key
# from a file only he can read and keeps the text on the grid), queued by the gate word
# `literature <list>`. It runs under the size rule (grid/size-rule.sh) as a fetch does: the plan asks
# each source what it holds and bounds every file by the size its server states, or a cap, and the
# job lands a byte only once that fits the room left under the lab volume's quota after what the
# running fetches owe. The landing is literature_<list> under the data root, 0700, every file 0600,
# so only the owner's account reads Elsevier's text. The report goes to logs/LITERATURE-<list>.md,
# which the next `literature <list>` prints; it names papers and sources, never a key or a text, and
# is 0600, as the landing is, since it names the papers of confidential work.
# The tool is copied before it runs, so a checkout the gate moves meanwhile changes nothing.
#   LIST_ID   the list, grid/literature/<LIST_ID>.csv
set -uo pipefail
umask 077
REPO=${SCHWINGNET:-$HOME/SchwingNet}
id=${LIST_ID:?LIST_ID names the list}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
VOLUME=${VOLUME:-/rs/rs_grp_oschome}
ACQ_ENV=${ACQ_ENV:-/rs/rs_grp_oschome/go2432/envs/acq}
landing_id=literature_$id
REPORT=$REPO/grid/logs/LITERATURE-$id.md
export PYTHONNOUSERSITE=1
# shellcheck source=grid/size-rule.sh
. "$REPO/grid/size-rule.sh"
mkdir -p "$REPO/grid/logs"
report() { echo "- $*" >> "$REPORT.part"; }
finish() {
  report "exit $1 at $(date -u '+%F %T') UTC"
  mv "$REPORT.part" "$REPORT" && chmod 600 "$REPORT"
  echo "SN_LITERATURE_RC=$1"
  exit "$1"
}
# Slurm's warning before its time limit, or a scancel, still ends the report, so the next send prints it.
trap 'finish 143' TERM
started_at=$(git -C "$REPO" rev-parse --short=7 HEAD 2>/dev/null || echo unknown)
echo "# literature $id: job ${SLURM_JOB_ID:-none} on $(hostname), commit $started_at, $(date -u '+%F %T') UTC" > "$REPORT.part"
echo "LITERATURE start $id $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-}"
list=$REPO/grid/literature/$id.csv
[ -f "$list" ] || { report "FAILED: no list grid/literature/$id.csv at this commit"; finish 2; }

# The interpreter: a test's, only under LITERATURE_STAND_INS=yes, else the acquisition environment's,
# which the fetches run natively on a compute node with its own certificates, else the train-cpu
# environment's inside the container.
PY="" test_py=""
[ "${LITERATURE_STAND_INS:-}" = yes ] && test_py=${LITERATURE_PYTHON:-}
for cand in "$test_py" "$ACQ_ENV/bin/python" "$REPO/grid/bin/train-cpu-python"; do
  [ -n "$cand" ] && [ -x "$cand" ] || continue
  if "$cand" -c 'import sys, ssl; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then PY=$cand; break; fi
done
[ -n "$PY" ] || { report "FAILED: no Python 3.8 or later with ssl (tried the acquisition and train-cpu environments)"; finish 2; }
# The size rule reads the quota's attributes with the same interpreter where the node has no
# getfattr, unless a test says otherwise (grid/size-rule.sh, #180).
if [ "${SIZE_RULE_STAND_INS:-}" = yes ]; then RULE_PYTHON=${XATTR_PYTHON:-$PY}; else RULE_PYTHON=$PY; fi

work=$(mktemp -d "${TMPDIR:-/tmp}/literature.XXXXXX") || { report "FAILED: no private folder for the tool"; finish 2; }
trap 'rm -rf "$work"' EXIT
cp "$REPO/grid/literature_fetch.py" "$list" "$work/" || { report "FAILED: the tool or the list could not be copied"; finish 2; }

if ! size_and_admit "$landing_id" "$PY" "$work/literature_fetch.py" plan --list "$work/$id.csv" --landing "$DATA/$landing_id"; then
  report "refused by the size rule or the plan failed; nothing landed (the job's log says which)"
  finish 4
fi
report "admitted under the size rule: $(head -c 300 "$DATA/$landing_id/meta/SIZE" 2>/dev/null | awk '{ print $3 " bytes at most" }')"
"$PY" "$work/literature_fetch.py" fetch --landing "$DATA/$landing_id" --report "$REPORT.part"
finish $?
