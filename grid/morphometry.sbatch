#!/bin/bash
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=24:00:00
# bordercall's morphometry engine over the gold tier 3 masks (the thread "Extract morphometrics
# from gold tier 3 CT"; the owner's count of 2026-10-29 15:19 UTC: two CPU jobs, one a set, and of
# 2026-10-30 14:33 UTC: one more a set on the merged engine, MORPHOMETRY_RERUNS in grid/gate.sh).
# grid/gate.sh's word `morphometry <set>` queues it as the batch class with SET, enhance or
# verse, in the environment:
#   enhance  every ENHANCE.PET vertebra label map under the data root's aws_enhance_pet_labels
#   verse    VerSe's 374 int16 copies the carry grid/carry/verse_masks_2026_10_29.txt landed, and
#            then, in the same job, TotalSegmentator's admitted subjects (data/gold3-ct/admission.json,
#            member totalsegmentator, verdict admitted): each one's structure masks taken from the
#            Zenodo release under the data root's totalsegmentator_v300 and stacked into one int16
#            volume in VerSe's ids by `screening int16`, then measured as VerSe's are
#
# The engine is the pinned copy under grid/bordercall/ (tools/bordercall_vendor.py): PYTHONPATH
# points there, so `python -m morphometry`, `-m scanimport` and `-m screening` import the copy
# grid/bordercall/VENDORED records, and the code stamp morphometry prints names the run. Each set
# writes under $MORPHOMETRY_ROOT/<set> on the lab volume, the root the gate hands it, whose kept/<job>/
# holds a whole earlier run's rows the gate set aside before a rerun and is read by no step here:
# masks/, a folder of symlinks named <id>.nii.gz, since the engine reads one folder of masks;
# rows/<id>.csv and rows.csv from the measuring run; facts.jsonl and verdicts.csv from the
# generalised screening, whose failure is reported and not fatal, since the measuring is the
# count's purpose; totalseg/ the same for TotalSegmentator's subjects. The report,
# grid/logs/MORPHOMETRY-<set>.md, carries aggregates alone, counts, medians, paths, bytes and
# digests, and never a row of a study, since the rows stay on the grid
# (docs/research/gold3-ct/README.md); a level's median is shown only over five studies or more.
# It names the interpreter's Python, numpy, scipy and nibabel and the engine's code stamp, and holds
# each run's joined rows to that stamp and to the run's own count of the studies it chose: a run whose
# worker died ends 0 with the files it found, an earlier engine's among them where they were not set
# aside, so rows that are not the run's whole fail the set and no join reads them.
#
# The interpreter is the first with numpy, scipy and nibabel. screening also needs icontract and
# beartype, which no grid environment holds, so where the interpreter lacks them a throwaway venv
# under the set's folder takes those two pins with --system-site-packages, used for the screening
# steps only; where that fails too the screening steps are skipped and the report says so. The
# checkout holds still while the job lasts (grid/logs/HOLD, as a benchmark's does), and a job whose
# checkout moved anyway is failed, since its report names the commit it began on. Not requeued
# (--no-requeue from the gate).
set -uo pipefail
SET=${SET:-}
case "$SET" in enhance|verse) ;; *) echo "morphometry: SET is enhance or verse"; echo "SN_MORPHOMETRY_RC=64"; exit 64 ;; esac
REPO=${SCHWINGNET:-$HOME/SchwingNet}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
RS=${RS_ROOT:-$LAB/go2432}
GRID_DATA=/rs/rs_grp_oschome/go2432/data
DATA_ROOT=${DATA_ROOT:-$GRID_DATA}
CPUS=${SLURM_CPUS_PER_TASK:-4}
REPORT=$REPO/grid/logs/MORPHOMETRY-$SET.md
OUT=${MORPHOMETRY_ROOT:-$RS/morphometry}/$SET
ENGINE=$REPO/grid/bordercall
ICONTRACT_PINS="icontract==2.7.3 beartype==0.23.1"
mkdir -p "$REPO/grid/logs" "$OUT"
cd "$REPO" || exit 2
export PYTHONNOUSERSITE=1 PYTHONPATH=$ENGINE
# One thread a process: the measuring and the screening each fork a worker a CPU, so numpy's BLAS
# and OpenMP pools inside every worker would oversubscribe the node CPUS-fold.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
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
  echo "SN_MORPHOMETRY_RC=$rc"
  exit "$rc"
}
started_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
echo "# morphometry $SET: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${started_at:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"
[ -n "$started_at" ] || { report "FAILED: the checkout at $REPO names no commit"; finish 2; }
HOLD=$REPO/grid/logs/HOLD
echo "${SLURM_JOB_ID:-$$} $started_at" > "$HOLD"
unhold() { [ "$(awk '{ print $1; exit }' "$HOLD" 2>/dev/null)" != "${SLURM_JOB_ID:-$$}" ] || rm -f "$HOLD"; }
trap unhold EXIT
trap 'exit 143' TERM

# The interpreter: the first that imports what the engine needs.
PY=""
for cand in "${MORPHOMETRY_PYTHON:-}" "$HOME/mambaforge/envs/spineps/bin/python" "$RS/envs/spineps212/bin/python" \
            "$REPO/.pixi/envs/train-cpu/bin/python" "$(command -v python3)"; do
  [ -n "$cand" ] && [ -x "$cand" ] || continue
  if "$cand" -c "import numpy, scipy, nibabel" >/dev/null 2>&1; then PY=$cand; break; fi
done
[ -n "$PY" ] || { report "FAILED: no interpreter with numpy, scipy and nibabel (tried the SPINEPS environments and train-cpu)"; finish 2; }
versions() {  # the versions of Python and of the three packages the engine measures with, each "not read" where its import fails
  "$PY" - <<'PYEOF' 2>/dev/null || echo "versions not read"
import importlib, sys
parts = ["Python " + sys.version.split()[0]]
for name in ("numpy", "scipy", "nibabel"):
    try:
        parts.append("%s %s" % (name, importlib.import_module(name).__version__))
    except Exception:
        parts.append("%s not read" % name)
print(", ".join(parts))
PYEOF
}
# The engine's walls and pedicles are read through scipy's linear programs, whose answers at tolerance can
# move with its version, so the report names the versions beside the code stamp.
report "interpreter: $PY ($(versions)) for the measuring"
[ -f "$ENGINE/morphometry/__main__.py" ] || { report "FAILED: no vendored morphometry at $ENGINE (tools/bordercall_vendor.py)"; finish 2; }
report "bordercall copy: $(head -n 1 "$ENGINE/VENDORED" 2>/dev/null | cut -c1-120)"
# The stamp the engine gives its own code, which every row it writes carries: the report names it and
# measure holds the rows to it, so a report never names an engine its rows were not measured by.
STAMP=$("$PY" -c 'from morphometry.__main__ import code_stamp; print(code_stamp())' 2>/dev/null | tail -n 1)
[[ $STAMP =~ ^[0-9a-f]{16}$ ]] || { report "FAILED: the engine gave no code stamp of the plain form, so no row could be tied to the code that measured it"; finish 2; }
report "code stamp: $STAMP"

# The screening interpreter: the same one where it has the contracts' packages, else a throwaway
# venv beside the set's outputs with exactly those two pins, else none and the screening is skipped.
PYS=""
screening_python() {
  if "$PY" -c "import icontract, beartype" >/dev/null 2>&1; then echo "$PY"; return 0; fi
  if [ ! -f "$OUT/env/READY" ]; then
    rm -rf "$OUT/env"
    # shellcheck disable=SC2086
    "$PY" -m venv --system-site-packages "$OUT/env" > "$OUT/env.log" 2>&1 \
      && "$OUT/env/bin/pip" install $ICONTRACT_PINS >> "$OUT/env.log" 2>&1 \
      && "$OUT/env/bin/python" -c "import icontract, beartype" >> "$OUT/env.log" 2>&1 || return 1
    printf '%s\n' "$ICONTRACT_PINS" > "$OUT/env/READY"
  fi
  echo "$OUT/env/bin/python"
}
if PYS=$(screening_python); then
  if [ "$PYS" = "$PY" ]; then report "screening interpreter: the same, which has icontract and beartype"
  else report "screening interpreter: $PYS, a throwaway venv on the measuring interpreter with $ICONTRACT_PINS"; fi
else
  PYS=""
  report "NOTE: no interpreter with icontract and beartype and the venv under $OUT/env could not be made ($(tail -n 2 "$OUT/env.log" 2>/dev/null | tr '\n' ' ' | cut -c1-200)); the screening steps are skipped"
fi

STEPS=$OUT
step() {  # step NAME COMMAND...: run it, keep its output under $STEPS/NAME.log, report its tail on failure
  local name=$1; shift
  echo "## $name: $*" >> "$STEPS/steps.log"
  if "$@" > "$STEPS/$name.log" 2>&1; then return 0; fi
  report "FAILED at $name: $(tail -n 3 "$STEPS/$name.log" | tr '\n' ' ' | cut -c1-300)"
  return 1
}
digest_line() {  # digest_line FILE: its path, bytes and sha256, or that it is missing
  if [ -f "$1" ]; then echo "$1 ($(stat -c %s "$1") bytes, sha256 $(sha256sum < "$1" | cut -c1-64))"; else echo "$1 (not written)"; fi
}
link_masks() {  # link_masks DIR < paths: DIR/<id>.nii.gz -> each path, the id its name without .nii.gz
  local f id
  mkdir -p "$1"
  while read -r f; do
    [ -n "$f" ] || continue
    id=$(basename "$f" .nii.gz)
    ln -sfn "$f" "$1/$id.nii.gz"
  done
}
level_table() {  # level_table ROWS.csv: per level, the rows with h_post_inset and the medians of three keys over five studies or more, as a table
  "$PY" - "$1" <<'PYEOF'
import csv, math, sys
from collections import defaultdict
KEYS = ("h_ant", "h_post_inset", "body_index_ant_post")
# A median of fewer studies than the join's least cell would print a value one or two studies set, in a
# report that leaves the grid, so such a level shows its count alone.
LEAST = 5
ORDER = [*("C%d" % i for i in range(1, 8)), *("T%d" % i for i in range(1, 14)), *("L%d" % i for i in range(1, 7)), "S1", "sacrum"]
values = defaultdict(lambda: defaultdict(list))
with open(sys.argv[1], newline="", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        if row.get("key") not in KEYS:
            continue
        try:
            v = float(row["value"])
        except (TypeError, ValueError):
            continue
        if math.isfinite(v):
            values[row["level"]][row["key"]].append(v)
def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2) if n else float("nan")
def shown(xs, form):
    return form % median(xs) if len(xs) >= LEAST else "-"
levels = sorted(values, key=lambda l: (ORDER.index(l) if l in ORDER else len(ORDER), l))
print("    | level | n (h_post_inset) | median h_ant | median h_post_inset | median body_index_ant_post |")
print("    |---|---|---|---|---|")
for level in levels:
    n = len(values[level]["h_post_inset"])
    print("    | %s | %d | %s | %s | %s |" % (level, n, shown(values[level]["h_ant"], "%.2f"), shown(values[level]["h_post_inset"], "%.2f"), shown(values[level]["body_index_ant_post"], "%.3f")))
PYEOF
}
rows_whole() {  # rows_whole ROWS.csv RUN.log: "whole N" where the rows are the run's whole, N studies each once under the report's code stamp, else "not whole: " and why
  "$PY" - "$1" "$2" "$STAMP" <<'PYEOF'
import csv, re, sys
from collections import defaultdict
rows_path, log_path, stamp = sys.argv[1:4]
problems = []
try:
    log = open(log_path, encoding="utf-8", errors="replace").read()
except OSError:
    log = ""
count = re.search(r"^(\d+) studies chosen, \d+ to measure, code ([0-9a-f]{16})$", log, re.M)
if not count:
    problems.append("the run printed no count of the studies it chose under a code stamp")
elif count.group(2) != stamp:
    problems.append("the run measured under another code stamp than the report names")
if re.search(r"^a worker died", log, re.M):
    problems.append("a worker died during the run, so some studies it chose were not measured by it")
codes = defaultdict(set)
try:
    with open(rows_path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            notes = codes[row["study"]]
            if row["key"] == "code" and row["level"] == "study":
                notes.add(row["note"])
except (OSError, KeyError, csv.Error):
    problems.append("the joined rows could not be read")
foreign = sum(1 for notes in codes.values() if notes != {stamp})
if foreign:
    problems.append("%d studies of the joined rows carry no code stamp or another" % foreign)
if count and len(codes) != int(count.group(1)):
    problems.append("the joined rows hold %d studies where the run chose %s" % (len(codes), count.group(1)))
print("not whole: " + "; ".join(problems) if problems else "whole %d" % len(codes))
PYEOF
}
measure() {  # measure NAME MASKS SCHEME OUTDIR: morphometry run over MASKS into OUTDIR, its aggregates into the report; 1 where it failed
  local name=$1 masks=$2 scheme=$3 out=$4 began rc first errors whole
  mkdir -p "$out"
  STEPS=$out
  began=$(date +%s)
  step run "$PY" -m morphometry run --masks "$masks" --scheme "$scheme" --out "$out" --workers "$CPUS"
  rc=$?
  STEPS=$OUT
  first=$(grep -m1 'studies chosen' "$out/run.log" 2>/dev/null)
  errors=$(grep -c 'flag:error' "$out/rows.csv" 2>/dev/null || true)
  report "$name: $(ls "$masks" 2>/dev/null | wc -l) masks linked; ${first:-the run printed no count}; ${errors:-0} studies flagged error; $(( $(date +%s) - began )) s wall; its lines in $out/run.log"
  report "$name rows: $(digest_line "$out/rows.csv")"
  # A run whose worker died still joins every chosen study's file it finds and ends 0, an earlier
  # engine's files among them where they were not set aside, so the rows are held to the run's own
  # count and to the report's code stamp before they are reported as measured; rows that are not the
  # run's whole fail the set, and its level table is not drawn from them.
  whole=$(rows_whole "$out/rows.csv" "$out/run.log" 2>/dev/null)
  [ -n "$whole" ] || whole="not whole: the check of the rows gave no answer"
  case "$whole" in
    "whole "*)
      report "$name rows: ${whole#whole } studies, every one under the code stamp the report names, as many as the run chose" ;;
    *)
      report "$name rows FAILED: not a whole run (${whole#not whole: }), so they are not used"
      return 1 ;;
  esac
  if [ -f "$out/rows.csv" ]; then
    report "$name per level (rows with h_post_inset, medians over values that parse as finite, each where 5 or more studies give one, - otherwise):"
    level_table "$out/rows.csv" >> "$REPORT.part" 2>&1 || report "  the level table could not be read"
  fi
  return "$rc"
}
screen() {  # screen NAME OUTDIR facts-options...: screening facts then whole into OUTDIR; failures reported, never fatal
  local name=$1 out=$2; shift 2
  [ -n "$PYS" ] || { report "$name screening: skipped (no interpreter with icontract and beartype)"; return 0; }
  STEPS=$out
  step facts "$PYS" -m screening facts "$@" --out "$out/facts.jsonl" --workers "$CPUS" || true
  step whole "$PYS" -m screening whole --facts "$out/facts.jsonl" --out "$out/verdicts.csv" || true
  STEPS=$OUT
  report "$name facts: $(digest_line "$out/facts.jsonl")"
  report "$name verdicts: $(digest_line "$out/verdicts.csv")"
  if [ -f "$out/verdicts.csv" ]; then
    report "$name verdict counts:"
    "$PY" - "$out/verdicts.csv" <<'PYEOF' >> "$REPORT.part" 2>&1 || report "  the verdict column could not be read"
import csv, sys
from collections import Counter
with open(sys.argv[1], newline="", encoding="utf-8") as fh:
    counts = Counter(row.get("verdict", "") for row in csv.DictReader(fh))
for verdict, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
    print("    %6d %s" % (n, verdict or "(blank)"))
PYEOF
  fi
}
admitted_ids() {  # admitted_ids MEMBER FILE: the ids data/gold3-ct/admission.json admits for MEMBER, one a line into FILE
  "$PY" - "$REPO/data/gold3-ct/admission.json" "$1" "$2" <<'PYEOF'
import json, sys
studies = json.load(open(sys.argv[1], encoding="utf-8"))["studies"]
ids = sorted(s["id"] for s in studies if s.get("member") == sys.argv[2] and s.get("verdict") == "admitted")
open(sys.argv[3], "w", encoding="utf-8").write("".join(i + "\n" for i in ids))
print(len(ids))
PYEOF
}
extract_segmentations() {  # extract_segmentations ZIP ID DIR: the subject's segmentations/ members out of the release's zip into DIR
  if command -v unzip > /dev/null 2>&1; then
    unzip -q -o "$1" "Totalsegmentator_dataset_v300/$2/segmentations/*" -d "$3" > /dev/null 2>&1
  else
    "$PY" - "$1" "$2" "$3" <<'PYEOF'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    prefix = "Totalsegmentator_dataset_v300/%s/segmentations/" % sys.argv[2]
    names = [n for n in z.namelist() if n.startswith(prefix)]
    z.extractall(sys.argv[3], names)
    sys.exit(0 if names else 1)
PYEOF
  fi
}

stack_one() {  # stack_one ID: the subject's structure masks stacked into one int16 volume in VerSe's ids; its verdict under $TS/stacked/
  local id=$1 log
  log=$TS/int16/$id.log
  mkdir -p "$TS/int16"
  if [ -z "$extracted" ] && [ ! -d "$subjects/$id/segmentations" ]; then
    extract_segmentations "$zip" "$id" "$TS/raw" || { echo "$id: no segmentations in the zip" > "$log"; echo missing > "$TS/stacked/$id.verdict"; return 0; }
  fi
  [ -d "$subjects/$id/segmentations" ] || { echo "$id: no segmentations folder" > "$log"; echo missing > "$TS/stacked/$id.verdict"; return 0; }
  # A stack an earlier job made is kept as it is and counted as that job's, whose lines are its own
  # log's, so this job writes no log for it.
  if [ -f "$TS/masks/$id.nii.gz" ] && [ -f "$TS/manifests/$id.json" ]; then echo reused > "$TS/stacked/$id.verdict"; return 0; fi
  if "$PYS" -m screening int16 --labels "$subjects/$id" --scheme totalseg --out "$TS/masks/$id.nii.gz" --manifest "$TS/manifests/$id.json" > "$log" 2>&1; then
    echo stacked > "$TS/stacked/$id.verdict"
  else
    rm -f "$TS/masks/$id.nii.gz" "$TS/manifests/$id.json"; echo failed > "$TS/stacked/$id.verdict"
  fi
}

rc=0
case "$SET" in
  enhance)
    find "$DATA_ROOT/aws_enhance_pet_labels/raw" -path '*Vertebrae*' -name '*.nii.gz' 2>/dev/null | sort > "$OUT/inputs.txt"
    [ -s "$OUT/inputs.txt" ] || { report "FAILED: no vertebra label map under $DATA_ROOT/aws_enhance_pet_labels/raw (fetch aws_enhance_pet_labels first)"; finish 2; }
    link_masks "$OUT/masks" < "$OUT/inputs.txt"
    measure "ENHANCE.PET" "$OUT/masks" enhance "$OUT" || rc=1
    screen "ENHANCE.PET" "$OUT" --masks "$OUT/masks" --scheme enhance --member enhance_pet
    ;;
  verse)
    one=$(find "$DATA_ROOT/verse_masks_2026_10_29" -name '*.nii.gz' -print -quit 2>/dev/null)
    [ -n "$one" ] || { report "FAILED: no int16 mask under $DATA_ROOT/verse_masks_2026_10_29 (fetch verse_masks_2026_10_29 first)"; finish 2; }
    find "$(dirname "$one")" -maxdepth 1 -name '*.nii.gz' | sort > "$OUT/inputs.txt"
    link_masks "$OUT/masks" < "$OUT/inputs.txt"
    measure "VerSe" "$OUT/masks" verse "$OUT" || rc=1
    screen "VerSe" "$OUT" --masks "$OUT/masks" --scheme verse --member verse
    # TotalSegmentator's admitted subjects, in the same job: stacked into int16 volumes in VerSe's ids first
    TS=$OUT/totalseg
    mkdir -p "$TS/masks" "$TS/manifests" "$TS/raw"
    count=$(admitted_ids totalsegmentator "$TS/ids.txt" 2>/dev/null) || count=0
    zip=$(find "$DATA_ROOT/totalsegmentator_v300" -name '*.zip' -print -quit 2>/dev/null)
    extracted=$(find "$DATA_ROOT/totalsegmentator_v300" -type d -name segmentations -path '*Totalsegmentator_dataset_v300/*' -print -quit 2>/dev/null)
    if [ "${count:-0}" = 0 ]; then
      report "TotalSegmentator: skipped, data/gold3-ct/admission.json admits no subject of it"
    elif [ -z "$PYS" ]; then
      report "TotalSegmentator: skipped, its masks are stacked by screening int16 and no interpreter has icontract and beartype"
    elif [ -n "$zip" ] || [ -n "$extracted" ]; then
      if [ -n "$extracted" ]; then subjects=$(dirname "$(dirname "$extracted")"); report "TotalSegmentator release: the extracted folder $subjects"
      else subjects=$TS/raw/Totalsegmentator_dataset_v300; report "TotalSegmentator release: $zip, each admitted subject's segmentations/ taken out under $TS/raw"; fi
      # Each subject's stack reads its hundred-odd structure files from the release, so the subjects
      # are stacked CPUS at a time (the owner's word of 2026-10-30 13:37 UTC, after the serial loop
      # had held the verse job for hours): one verdict file a subject under $TS/stacked/, read back
      # into the counts, and a subject stacked by an earlier job is kept as it is and counted apart,
      # its lines in that job's log: $TS/int16.log for the serial loop's (job 40877151's among them),
      # $TS/int16/<id>.log for a parallel job's. The verdicts are this job's own, so an earlier job's go first.
      mkdir -p "$TS/stacked"
      rm -f "$TS"/stacked/*.verdict
      export PYS TS subjects zip extracted
      export -f stack_one extract_segmentations
      grep -v '^$' "$TS/ids.txt" | xargs -P "$CPUS" -I{} bash -c 'stack_one "$1"' _ {}
      stacked=$(cat "$TS"/stacked/*.verdict 2>/dev/null | grep -c '^stacked$' || true)
      reused=$(cat "$TS"/stacked/*.verdict 2>/dev/null | grep -c '^reused$' || true)
      failed=$(cat "$TS"/stacked/*.verdict 2>/dev/null | grep -c '^failed$' || true)
      missing=$(cat "$TS"/stacked/*.verdict 2>/dev/null | grep -c '^missing$' || true)
      report "TotalSegmentator: $count admitted subjects; $stacked stacked into int16 volumes in VerSe's ids by this job (screening int16, manifests under $TS/manifests, $CPUS subjects at a time, the lines in $TS/int16/<id>.log), $reused kept as an earlier job stacked them (its lines in $TS/int16.log or $TS/int16/<id>.log), $failed failed, $missing with no segmentations in the release"
      measure "TotalSegmentator" "$TS/masks" verse "$TS" || rc=1
      screen "TotalSegmentator" "$TS" --masks "$subjects" --scheme totalseg --member totalsegmentator --ids "$TS/ids.txt"
    else
      report "TotalSegmentator: skipped, no zip and no extracted Totalsegmentator_dataset_v300/<id>/segmentations under $DATA_ROOT/totalsegmentator_v300 (fetch totalsegmentator_v300 first); VerSe's part ran"
    fi
    ;;
esac
report "every step's full output is under $OUT/<step>.log (and $OUT/totalseg/<step>.log); only the aggregates above leave the grid"
finish "$rc"
