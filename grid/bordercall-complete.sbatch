#!/bin/bash
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=08:00:00
# The gold tier 3 completion: the levels an admitted CT's release does not draw (data/gold3-ct/
# admission.json, complete), taken from the census's SPINEPS mask of the same CT where bordercall's
# matcher finds one whole body there, and written as a machine arm beside the release's masks, on the
# owner's count of 2026-10-29 15:22 UTC (one CPU job on the grid, "Read the census's existing SPINEPS
# masks"). grid/gate.sh's word `bordercall complete` queues it as the batch class.
#
# Steps, each written to $OUT on the lab volume and summarised into the report:
#   0. the matcher's own tests from the vendored copy, so an environment whose numpy, scipy or nibabel
#      reads a mask otherwise adds nothing
#   1. tools/gold3_complete_grid.py prepare: each study's census row, its SPINEPS masks relabelled
#      where they carry raw ids and brought onto the release's grid, jobs.json for the matcher
#   2. holdings.fullspine_complete over jobs.json: records.jsonl, facts.jsonl and masks/ under
#      $OUT/matcher/, each mask named by its own sha256
#   3. tools/gold3_complete_grid.py report: the counts, a line per study and every refusal's reason
#
# Nothing is segmented and nothing trains; SPINEPS is never run. The interpreter is the SPINEPS
# environment's, which has numpy, scipy and nibabel. The checkout holds still while the job lasts
# (grid/logs/HOLD, as a benchmark's does), and a job whose checkout moved anyway is failed, since its
# report names the commit it began on. Not requeued (--no-requeue from the gate). No path under the
# data root is written into the report: the tool writes store and file names only.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
RS=${RS_ROOT:-$LAB/go2432}
DATA_ROOT=${DATA_ROOT:-$RS/data}
TIERS=${TIERS:-$RS/ruleclass/tiers}
SSN=${SSN:-$HOME/spinesurg-ct-nnunet}
export SSN
VERSE_MASKS=${VERSE_MASKS:-$DATA_ROOT/verse_masks_2026_10_29/masks}
TS_ROOT=${TS_ROOT:-$DATA_ROOT/totalsegmentator_v300}
BORDERCALL_ROOT=${BORDERCALL_ROOT:-$RS/bordercall}
CPUS=${SLURM_CPUS_PER_TASK:-4}
REPORT=$REPO/grid/logs/BORDERCALL-complete.md
OUT=$BORDERCALL_ROOT/complete
BC=$REPO/grid/bordercall
mkdir -p "$REPO/grid/logs" "$OUT"
cd "$REPO" || exit 2
export PYTHONNOUSERSITE=1 PYTHONPATH=$BC
report() { echo "- $*" | tee -a "$REPORT.part"; }
finish() {
  local rc=$1 ended_at
  ended_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
  if [ "$ended_at" != "$started_at" ]; then
    report "FAILED: the checkout moved from ${started_at:0:7} to ${ended_at:0:7} during the job, so a later step may have run newer code while this report names the older; its results are not used"
    [ "$rc" != 0 ] || rc=3
  fi
  report "exit $rc at $(date -u '+%F %T') UTC"
  mv "$REPORT.part" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_BORDERCALL_RC=$rc"
  exit "$rc"
}
started_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
echo "# bordercall complete: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${started_at:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"
[ -n "$started_at" ] || { report "FAILED: the checkout at $REPO names no commit"; finish 2; }
HOLD=$REPO/grid/logs/HOLD
echo "${SLURM_JOB_ID:-$$} $started_at" > "$HOLD"
unhold() { [ "$(awk '{ print $1; exit }' "$HOLD" 2>/dev/null)" != "${SLURM_JOB_ID:-$$}" ] || rm -f "$HOLD"; }
trap unhold EXIT
trap 'exit 143' TERM

# The interpreter: the first that imports everything the matcher needs.
PY=""
for cand in "${BORDERCALL_PYTHON:-}" "$HOME/mambaforge/envs/spineps/bin/python" "$RS/envs/spineps212/bin/python" \
            "$REPO/.pixi/envs/train-cpu/bin/python" "$(command -v python3)"; do
  [ -n "$cand" ] && [ -x "$cand" ] || continue
  if "$cand" -c "import numpy, scipy, nibabel" >/dev/null 2>&1; then PY=$cand; break; fi
done
[ -n "$PY" ] || { report "FAILED: no interpreter with numpy, scipy and nibabel (tried the SPINEPS environments and train-cpu)"; finish 2; }
report "interpreter: $PY ($("$PY" -c 'import sys; print(sys.version.split()[0])'))"
[ -d "$TIERS" ] || { report "FAILED: no census tier lists at the ruleclass tiers folder"; finish 2; }
[ -d "$VERSE_MASKS" ] || report "NOTE: no int16 copies of VerSe's masks on the data root; every VerSe study will be left out"
[ -d "$TS_ROOT" ] || report "NOTE: no totalsegmentator_v300 on the data root; every TotalSegmentator study will be left out"
[ -f "$SSN/tools/spineps_ids.py" ] || report "NOTE: no spineps_ids.py in the spinesurg-ct-nnunet clone; every raw-id mask is left out"
[ -f "$BC/holdings/fullspine_complete.py" ] || { report "FAILED: no vendored matcher at grid/bordercall/holdings/ (tools/bordercall_vendor.py)"; finish 2; }
report "bordercall copy: $(head -n 1 "$REPO/grid/bordercall/VENDORED" 2>/dev/null | cut -c1-120)"

step() {  # step NAME COMMAND...: run it, keep its output under $OUT/NAME.txt, report its tail on failure
  local name=$1; shift
  echo "## $name: $*" >> "$OUT/steps.log"
  if "$@" > "$OUT/$name.txt" 2>&1; then return 0; fi
  report "FAILED at $name: $(tail -n 3 "$OUT/$name.txt" | tr '\n' ' ' | cut -c1-300)"
  return 1
}

# 0. the matcher's tests pass in this environment, or nothing below is trusted
step selftest "$PY" -m unittest holdings.tests.test_fullspine_complete holdings.tests.test_fullspine_facts || finish 1
report "selftest: $(grep -E '^(Ran|OK)' "$OUT/selftest.txt" | tr '\n' ' ')"

# 1. the census's masks for the studies to complete, onto the release grids
step prepare "$PY" tools/gold3_complete_grid.py prepare --admission data/gold3-ct/admission.json --facts data/gold3-ct \
  --tiers "$TIERS" --verse-masks "$VERSE_MASKS" --ts-root "$TS_ROOT" --out "$OUT" --ssn "$SSN" --python "$PY" || finish 1
report "prepare: $(tail -n 1 "$OUT/prepare.txt")"

# 2. the matcher over them
if [ "$("$PY" -c "import json; print(len(json.load(open('$OUT/jobs.json'))['studies']))")" = 0 ]; then
  report "STOP: no study could be prepared, so the matcher has nothing to read (the inventory below says why)"
else
  step match "$PY" -m holdings.fullspine_complete "$OUT/jobs.json" "$OUT/matcher" --workers "$CPUS" || finish 1
  report "matcher: $(tail -n 1 "$OUT/match.txt")"
fi

# 3. the report
step summary "$PY" tools/gold3_complete_grid.py report --out "$OUT" || finish 1
sed 's/^/    /' "$OUT/summary.txt" >> "$REPORT.part"
report "the records, the completed facts rows and the masks are under the lab volume's bordercall/complete/matcher/; the prepared inputs under bordercall/complete/prepared/"
finish 0
