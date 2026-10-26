#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=12:00:00
# The bordercall corpus and its answer: which vertebral junction the shape of the bone names most
# robustly, in normal and anomalous spines, on every full-spine SPINEPS mask the grid holds (the
# owner's prompt of 2026-10-25 23:48 UTC and count of 23:56 UTC: two CPU jobs, a pilot over a few
# hundred countable cases, then the full corpus). grid/gate.sh's word `bordercall <stage>` queues it
# as the batch class with STAGE, pilot or full, in the environment.
#
# Steps, each written to $OUT/<stage>/ on the lab volume and summarised into the report:
#   0. bordercall's selftest (the published CTSpinoPelvic1K numbers from the bundled fixture), so a
#      copy whose model drifted scores nothing
#   1. tools/bordercall_corpus.py build: every census row with a SPINEPS mask, in a fixed order, read,
#      a raw mask relabelled through its centroid file by spinesurg-ct-nnunet's guard, the column
#      counted from C2 and written as a label volume in bordercall's scheme; the ribs read from the
#      census's Moller arm for the phenotype; the pilot stops after the first few hundred countable
#   2. bordercall scheme, measure, phenotype (its own, as a cross-check of the count), border and
#      breakout at T12/L1 and at C7/T1, sweep over every candidate border, the figures the owner
#      asked for, the Panjabi models on the corpus (panjabi-corpus), and the disagreement arms
#      (count, ribs, circular) at both junctions
#
# Nothing is segmented and nothing trains; a mask is never re-run. The interpreter is the SPINEPS
# environment's, which has numpy, scipy, nibabel and matplotlib. The checkout holds still while the
# job lasts (grid/logs/HOLD, as a benchmark's does), and a job whose checkout moved anyway is
# failed, since its report names the commit it began on. Not requeued (--no-requeue from the gate).
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
RS=${RS_ROOT:-$LAB/go2432}
TIERS=${TIERS:-$RS/ruleclass/tiers}
MOLLER=${MOLLER:-$RS/ruleclass/arms/moller_fast}
SSN=${SSN:-$HOME/spinesurg-ct-nnunet}
export SSN
BORDERCALL_ROOT=${BORDERCALL_ROOT:-$RS/bordercall}
STAGE=${STAGE:-}
case "$STAGE" in pilot|full) ;; *) echo "bordercall: STAGE is pilot or full"; echo "SN_BORDERCALL_RC=64"; exit 64 ;; esac
PILOT_LIMIT=${PILOT_LIMIT:-300}
PILOT_SCAN=${PILOT_SCAN:-4000}
CPUS=${SLURM_CPUS_PER_TASK:-4}
REPORT=$REPO/grid/logs/BORDERCALL-$STAGE.md
OUT=$BORDERCALL_ROOT/$STAGE
BC=$REPO/grid/bordercall/bordercall
mkdir -p "$REPO/grid/logs" "$OUT"
cd "$REPO" || exit 2
export PYTHONNOUSERSITE=1 MPLBACKEND=Agg
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
echo "# bordercall $STAGE: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${started_at:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"
[ -n "$started_at" ] || { report "FAILED: the checkout at $REPO names no commit"; finish 2; }
HOLD=$REPO/grid/logs/HOLD
echo "${SLURM_JOB_ID:-$$} $started_at" > "$HOLD"
unhold() { [ "$(awk '{ print $1; exit }' "$HOLD" 2>/dev/null)" != "${SLURM_JOB_ID:-$$}" ] || rm -f "$HOLD"; }
trap unhold EXIT
trap 'exit 143' TERM

# The interpreter: the first that imports everything bordercall needs.
PY=""
for cand in "${BORDERCALL_PYTHON:-}" "$HOME/mambaforge/envs/spineps/bin/python" "$RS/envs/spineps212/bin/python" \
            "$REPO/.pixi/envs/train-cpu/bin/python" "$(command -v python3)"; do
  [ -n "$cand" ] && [ -x "$cand" ] || continue
  if "$cand" -c "import numpy, scipy, nibabel, matplotlib" >/dev/null 2>&1; then PY=$cand; break; fi
done
[ -n "$PY" ] || { report "FAILED: no interpreter with numpy, scipy, nibabel and matplotlib (tried the SPINEPS environments and train-cpu)"; finish 2; }
report "interpreter: $PY ($("$PY" -c 'import sys; print(sys.version.split()[0])'))"
[ -d "$TIERS" ] || { report "FAILED: no census tier lists at $TIERS"; finish 2; }
[ -d "$MOLLER" ] || report "NOTE: no Moller rib arm at $MOLLER; every phenotype will be unknown"
[ -f "$SSN/tools/spineps_ids.py" ] || report "NOTE: no $SSN/tools/spineps_ids.py; every raw-id mask is set aside"
[ -f "$BC/run.py" ] || { report "FAILED: no vendored bordercall at $BC (tools/bordercall_vendor.py)"; finish 2; }
report "bordercall copy: $(head -n 1 "$REPO/grid/bordercall/VENDORED" 2>/dev/null | cut -c1-120)"

step() {  # step NAME COMMAND...: run it, keep its output under $OUT/NAME.txt, report its tail on failure
  local name=$1; shift
  echo "## $name: $*" >> "$OUT/steps.log"
  if "$@" > "$OUT/$name.txt" 2>&1; then return 0; fi
  report "FAILED at $name: $(tail -n 3 "$OUT/$name.txt" | tr '\n' ' ' | cut -c1-300)"
  return 1
}
lines() {  # lines FILE [N]: a file's first N lines into the report, indented
  local n=${2:-40}
  head -n "$n" "$1" | sed 's/^/    /' >> "$REPORT.part"
}

# 0. the published numbers reproduce from this copy, or nothing below is trusted
step selftest "$PY" "$BC/run.py" selftest || finish 1
report "selftest: $(tail -n 1 "$OUT/selftest.txt")"

# 1. the corpus: every SPINEPS mask with C2, named by the count
build=(build --tiers "$TIERS" --moller "$MOLLER" --out "$OUT" --workers "$CPUS")
[ "$STAGE" != pilot ] || build+=(--limit "$PILOT_LIMIT" --scan "$PILOT_SCAN")
step build "$PY" tools/bordercall_corpus.py "${build[@]}" || finish 1
report "corpus built (tools/bordercall_corpus.py build; corpus.csv, phenotype.csv and labels/ under $OUT):"
"$PY" tools/bordercall_corpus.py report --out "$OUT" > "$OUT/build_summary.txt" 2>&1
lines "$OUT/build_summary.txt" 45
countable=$("$PY" - "$OUT/corpus.csv" <<'EOF'
import csv, sys
print(sum(1 for r in csv.DictReader(open(sys.argv[1], encoding="utf-8")) if r["countable"] == "1"))
EOF
)
if [ "${countable:-0}" = 0 ]; then
  report "STOP: no countable case (no mask with C2 among the rows read), as the owner's step 2 asks; nothing is measured"
  finish 4
fi

# 2. bordercall itself, over the label tree
step scheme "$PY" "$BC/run.py" scheme --labels "$OUT/labels" --n 3 || finish 1
report "scheme: $(tail -n 3 "$OUT/scheme.txt" | head -n 1 | cut -c1-160)"
step measure "$PY" "$BC/run.py" measure --labels "$OUT/labels" --out "$OUT/levels.csv" --jobs "$CPUS" || finish 1
report "measured: $(grep -m1 'measured' "$OUT/measure.txt" | sed 's/^ *//')"
step phenotype_bc "$PY" "$BC/run.py" phenotype --labels "$OUT/labels" --out "$OUT/phenotype_bc.csv" || finish 1
report "bordercall's own phenotype over the tree (ids only, no ribs): $(grep -m1 countable "$OUT/phenotype_bc.txt" | sed 's/^ *//')"
for pair in "T12 L1 thoracolumbar" "C7 T1 cervicothoracic"; do
  set -- $pair
  step "border_$3" "$PY" "$BC/run.py" border --levels "$OUT/levels.csv" --above "$1" --below "$2" || true
  report "border $1/$2 (count names, countable corpus, out of fold):"
  grep -E "vertebrae from|AUC|junction placed" "$OUT/border_$3.txt" | sed 's/^/    /' >> "$REPORT.part"
  step "breakout_$3" "$PY" "$BC/run.py" breakout --levels "$OUT/levels.csv" --phenotype "$OUT/phenotype.csv" --above "$1" --below "$2" || true
  report "breakout $1/$2 by rib phenotype (denominators are cases with the border in view and ribs read):"
  sed -n '/class/,/^$/p' "$OUT/breakout_$3.txt" | head -n 9 | sed 's/^/    /' >> "$REPORT.part"
  step "disagree_$3" "$PY" "$BC/run.py" disagree --levels "$OUT/levels.csv" --phenotype "$OUT/phenotype.csv" --above "$1" --below "$2" || true
  report "disagreements $1/$2: the count, the ribs and the circular arm:"
  grep -v '^$' "$OUT/disagree_$3.txt" | head -n 14 | sed 's/^/    /' >> "$REPORT.part"
  mkdir -p "$OUT/figures/$3"
  for m in endplate canal_w; do
    step "plot_${3}_$m" "$PY" "$BC/run.py" plot --levels "$OUT/levels.csv" --phenotype "$OUT/phenotype.csv" \
      --measure "$m" --above "$1" --below "$2" --outdir "$OUT/figures/$3" || true
  done
done
step sweep "$PY" "$BC/run.py" sweep --levels "$OUT/levels.csv" --phenotype "$OUT/phenotype.csv" --min-class 10 || true
report "sweep (every candidate border, ranked by its worst anomalous class of 10 or more cases):"
grep -v '^$' "$OUT/sweep.txt" | head -n 24 | sed 's/^/    /' >> "$REPORT.part"
step panjabi "$PY" "$BC/run.py" panjabi-corpus --levels "$OUT/levels.csv" --phenotype "$OUT/phenotype.csv" --outdir "$OUT/panjabi" || true
report "Panjabi models on the corpus (fitted on the table, never on a CT; both junctions, by phenotype):"
grep -v '^$' "$OUT/panjabi.txt" | head -n 40 | sed 's/^/    /' >> "$REPORT.part"
report "figures: $(ls "$OUT"/figures/*/*.pdf 2>/dev/null | wc -l) PDF under $OUT/figures/ (thoracolumbar/, cervicothoracic/)"
report "every step's full output is under $OUT/<step>.txt; the tables above are their first lines"
finish 0
