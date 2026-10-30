#!/bin/bash
#SBATCH --cpus-per-task=4
#SBATCH --mem=50G
#SBATCH --time=06:00:00
# The gold tier 3 completion's TotalSegmentator arm: the C2 and the sacrum an admitted study's release
# does not draw (data/gold3-ct/admission.json, complete), drawn by TotalSegmentator 2.18.0 on the
# study's own CT and kept as a machine arm beside the release's masks where they lie where the
# release's own levels say they should (tools/gold3_totalseg_grid.py), on the owner's word of
# 2026-10-30 08:54 UTC ("Add sacrum and c2 w total seg") and his count. grid/gate.sh's word
# `totalseg complete` queues it as job submit's gpu class, once; the next send prints its report.
#
# The job Slurm starts is the driver: it holds the checkout, checks the data root and the fetched
# weight zips (fetch totalseg_weights), unpacks the zips once into the weights folder on the lab
# volume, makes the environment and then starts flows/launch.py totalseg (flows/totalseg.py,
# TotalsegFlow), held to the completion's frozen PREREG (docs/research/gold3-ct/completion/PREREG.md),
# whose one working step runs this script again with SCHWINGNET_FLOW_STEP=1 for the work, the body
# below: the PREREG checked against its hash, then the tool's prepare, run, check and report. The
# launcher resumes the newest run of the same words and code that did not finish, and run skips a
# study whose masks are already there, so a job cut short and sent again carries on. The job ends
# with the body's exit, unless it ended 0 and the flow did not, when the job's exit is the launcher's,
# as every launched flow's job's is.
#
# TotalSegmentator goes into a throwaway virtual environment on the lab volume, made from the
# train-gpu environment with its site packages (torch and Metaflow among them) and kept for a rerun
# under a name that carries the pin (grid/venv.sh), so the repository takes no new dependency and
# pixi.lock is never touched. It never downloads: TOTALSEG_WEIGHTS_PATH names the unpacked zips and
# TOTALSEG_HOME_DIR a config with usage statistics off. Nothing trains. The job's own files go to
# $TOTALSEG_ROOT (the masks under ts/, the kept arm files under arm/, records.jsonl, REPORT.md); the
# report is logs/TOTALSEG-complete.md: store and file names only, no path under the data root. Not
# requeued (--no-requeue from the gate). The checkout holds still while the job lasts (grid/logs/HOLD,
# as a benchmark's does), and a job whose checkout moved anyway is failed, since its report names
# the commit it began on.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
RS=${RS_ROOT:-$LAB/go2432}
TIERS=${TIERS:-$RS/ruleclass/tiers}
VERSE_MASKS=${VERSE_MASKS:-$DATA/verse_masks_2026_10_29/masks}
TS_ROOT=${TS_ROOT:-$DATA/totalsegmentator_v300}
ENHANCE_CT=${ENHANCE_CT:-$DATA/aws_enhance_pet_ct/raw}
ENHANCE_LABELS=${ENHANCE_LABELS:-$DATA/aws_enhance_pet_labels/raw}
OUT=${TOTALSEG_ROOT:-$RS/gold3-totalseg}
WEIGHTS=$OUT/weights
ZIPS=$DATA/totalseg_weights/raw
CPUS=${SLURM_CPUS_PER_TASK:-4}
# The flow's step runs this script again for the work; the job Slurm starts runs the driver.
BODY=${SCHWINGNET_FLOW_STEP:-}
# TotalSegmentator's newest release on PyPI when this line was written (2026-10-30).
TS_PIN="TotalSegmentator==2.18.0"
REPORT=$REPO/grid/logs/TOTALSEG-complete.md
# The body's exit, which it leaves here for the driver: the launcher's own exit is the flow's verdict.
RC_FILE=$OUT/COMPLETE_RC
mkdir -p "$REPO/grid/logs" "$OUT"
cd "$REPO" || exit 2
export PYTHONNOUSERSITE=1 WANDB_MODE=disabled HF_HUB_OFFLINE=1
export TOTALSEG_WEIGHTS_PATH=$WEIGHTS TOTALSEG_HOME_DIR=$OUT/home
export TRITON_LIBCUDA_PATH=${TRITON_LIBCUDA_PATH:-/.singularity.d/libs}
# The report's lines go to its part file first and the job's log after: the body's log is the flow's
# pipe, which a TERM that ends the flow's step closes, and a write to it then must not keep a line from the file.
report() { echo "- $*" >> "$REPORT.part"; echo "- $*"; }
# shellcheck source=grid/venv.sh
. "$REPO/grid/venv.sh"

# --- the body: the flow's step ------------------------------------------------------------------
tool() {  # tool NAME ARGS...: the tool's subcommand, its output kept under $OUT/NAME.txt, its tail reported on failure
  local name=$1 rc; shift
  bash grid/box.sh "$VENV/bin/python" tools/gold3_totalseg_grid.py "$name" "$@" > "$OUT/$name.txt" 2>&1; rc=$?
  [ "$rc" = 0 ] || report "$name ended $rc: $(tail -n 3 "$OUT/$name.txt" | sed -r -f grid/redact.sed | tr '\n' ' ' | cut -c1-300)"
  return "$rc"
}
body() {
  local rc=0 ran=0
  rm -f "$RC_FILE"
  trap 'trap "" PIPE; exit 143' TERM
  ( cd docs/research/gold3-ct/completion 2>/dev/null && sha256sum -c --status PREREG.md.sha256 ) \
    || { report "STOP: PREREG.md changed since the freeze"; body_end 90; }
  VENV=$(venv_ready "$TS_PIN") || { report "FAILED: the environment for $TS_PIN is not whole, though the driver made it"; body_end 1; }
  # 1. the studies and their files
  tool prepare --admission data/gold3-ct/admission.json --tiers "$TIERS" --ts-root "$TS_ROOT" --enhance-ct "$ENHANCE_CT" \
    --enhance-labels "$ENHANCE_LABELS" --verse-masks "$VERSE_MASKS" --out "$OUT" || body_end 1
  report "prepare: $(tail -n 1 "$OUT/prepare.txt")"
  # 2. TotalSegmentator on each CT that lacks its masks; a failure on one CT is kept and the rest run
  tool run --out "$OUT" --weights "$WEIGHTS" --device gpu --threads "$CPUS" || ran=$?
  report "run: $(tail -n 1 "$OUT/run.txt")"
  # 3. and 4. every target checked against the release's own levels, then the report
  tool check --out "$OUT" || body_end 1
  report "check: $(tail -n 1 "$OUT/check.txt")"
  tool report --out "$OUT" || body_end 1
  sed 's/^/    /' "$OUT/report.txt" >> "$REPORT.part"
  report "the masks, the kept arm files and the records are under the lab volume's gold3-totalseg/ (ts/, arm/, records.jsonl)"
  [ "$ran" = 0 ] || rc=$ran
  body_end "$rc"
}
body_end() {  # body_end RC: the body's exit, left for the driver, then the step's exit with RC
  echo "$1" > "$RC_FILE"
  exit "$1"
}

# --- the driver: the job Slurm starts -----------------------------------------------------------
finish() {
  local rc=$1 ended_at
  ended_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
  if [ "$ended_at" != "$started_at" ]; then
    report "FAILED: the checkout moved from ${started_at:0:7} to ${ended_at:0:7} during the job, so a later step may have run the newer code while this report names the older; its results are not used"
    [ "$rc" != 0 ] || rc=3
  fi
  report "exit $rc at $(date -u '+%F %T') UTC"
  mv "$REPORT.part" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_TOTALSEG_RC=$rc"
  exit "$rc"
}
zip_missing() {  # the first of the weight zips not whole under the data root's totalseg_weights/raw, by the fetch row's URLs: "<name> missing", "<name> part", "<name> damaged", or "row" where the row was not read
  local urls url file whole
  urls=$(bash grid/run-platform-fetch.sh --args totalseg_weights 2>/dev/null)
  [ -n "$urls" ] || { echo row; return; }
  for url in $urls; do
    file=$ZIPS/${url##*/}
    [ -s "$file" ] || { echo "${url##*/} missing"; return; }
    whole=0; zip_whole "$file" || whole=$?
    case "$whole" in 0) ;; 2) echo "${url##*/} damaged"; return ;; *) echo "${url##*/} part"; return ;; esac
  done
}
zip_whole() {  # zip_whole FILE: 0 where the file ends in a whole end-of-central-directory record, read as Python's zipfile.is_zipfile reads it, and unzip finds every member whole where the node has unzip; 2 where only unzip's test fails
  local size from
  size=$(stat -c %s "$1" 2>/dev/null) && [ "$size" -ge 22 ] || return 1
  from=$(( size > 65558 ? size - 65558 : 0 ))
  tail -c +"$((from + 1))" "$1" | od -An -v -tx1 -w1 | awk '
    function hex(s,  i, v) { v = 0; for (i = 1; i <= length(s); i++) v = v * 16 + index("0123456789abcdef", substr(s, i, 1)) - 1; return v }
    { bytes[NR] = $1 }
    END { for (i = NR - 21; i >= 1; i--) if (bytes[i] bytes[i + 1] bytes[i + 2] bytes[i + 3] == "504b0506" && i + 21 + hex(bytes[i + 21] bytes[i + 20]) == NR) exit 0; exit 1 }' || return 1
  ! command -v unzip > /dev/null 2>&1 || unzip -tq "$1" > /dev/null 2>&1 || return 2
}
unpack_weights() {  # each zip unpacked once into $WEIGHTS/<zip name without .zip>, the folder TotalSegmentator looks for, marked UNPACKED when whole
  local url zip name tmp inner
  for url in $(bash grid/run-platform-fetch.sh --args totalseg_weights 2>/dev/null); do
    zip=$ZIPS/${url##*/}; name=${url##*/}; name=${name%.zip}
    [ ! -f "$WEIGHTS/$name/UNPACKED" ] || continue
    tmp=$WEIGHTS/.unpack-$name
    rm -rf "$tmp" "$WEIGHTS/$name"; mkdir -p "$tmp" || return 1
    if command -v unzip > /dev/null 2>&1; then unzip -q "$zip" -d "$tmp" || return 1
    else "$VENV/bin/python" -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$zip" "$tmp" || return 1; fi
    # the zip holds the Dataset folder itself, or its members at the top: either way the folder is named as TotalSegmentator looks for it
    if [ -d "$tmp/$name" ]; then mv "$tmp/$name" "$WEIGHTS/$name" || return 1; rm -rf "$tmp"
    else inner=$(find "$tmp" -mindepth 1 -maxdepth 1 -type d -name 'Dataset*' | head -n 1)
         if [ -n "$inner" ] && [ "$(find "$tmp" -mindepth 1 -maxdepth 1 | wc -l)" = 1 ]; then mv "$inner" "$WEIGHTS/$name" || return 1; rm -rf "$tmp"
         else mv "$tmp" "$WEIGHTS/$name" || return 1; fi
    fi
    touch "$WEIGHTS/$name/UNPACKED"
  done
}
LAUNCHER=""
STOP_GRACE=80
launcher_stop() {  # the TERM passed on to the launcher, which passes it to the flow, then up to STOP_GRACE seconds for it to end
  local waited=0
  [ -n "$LAUNCHER" ] || return 0
  kill -TERM "$LAUNCHER" 2>/dev/null
  while kill -0 "$LAUNCHER" 2>/dev/null && [ "$waited" -lt "$STOP_GRACE" ]; do sleep 1; waited=$((waited + 1)); done
}
driver() {
  local zip rc said
  started_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
  echo "# totalseg complete: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${started_at:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"
  [ -n "$started_at" ] || { report "FAILED: the checkout at $REPO names no commit"; finish 2; }
  HOLD=$REPO/grid/logs/HOLD
  echo "${SLURM_JOB_ID:-$$} $started_at" > "$HOLD"
  trap unhold EXIT
  # Cut short, the job writes no report; the run it began is resumed by the next send of the word.
  trap 'launcher_stop; exit 143' TERM
  report "GPU: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -n 1 || echo 'nvidia-smi gave nothing')"
  # The inputs first, since the gate's check may be hours old by the time the job starts; the
  # weights are the fetched zips, and a zip not there fails the job by name rather than let the
  # segmenter download it.
  [ -d "$TIERS" ] || { report "FAILED: no census tier lists at the ruleclass tiers folder, which name each VerSe series' CT"; finish 2; }
  [ -d "$VERSE_MASKS" ] || report "NOTE: no int16 copies of VerSe's masks on the data root; every VerSe study will be left out"
  [ -d "$TS_ROOT" ] || report "NOTE: no totalsegmentator_v300 on the data root; every TotalSegmentator study will be left out"
  [ -d "$ENHANCE_CT" ] && [ -d "$ENHANCE_LABELS" ] || report "NOTE: ENHANCE.PET's CTs or labels are not on the data root; its study will be left out"
  zip=$(zip_missing)
  case "$zip" in
    "") ;;
    row) report "FAILED: the row totalseg_weights of the platform fetch was not read, so no zip can be named"; finish 2 ;;
    *" part") report "FAILED: ${zip% part} under $ZIPS is not a whole zip (a part still landing or cut short, which a resend of fetch totalseg_weights resumes)"; finish 2 ;;
    *" damaged") report "FAILED: ${zip% damaged} under $ZIPS is whole by its record but unzip finds a member damaged: delete it in the grid's shell and resend fetch totalseg_weights, which lands it again"; finish 2 ;;
    *) report "FAILED: no ${zip% missing} under $ZIPS (fetch totalseg_weights first)"; finish 2 ;;
  esac
  VENV=$(venv_for "$TS_PIN") || { report "FAILED: the environment for $TS_PIN could not be made"; finish 1; }
  mkdir -p "$WEIGHTS" "$TOTALSEG_HOME_DIR"
  # usage statistics off before the segmenter's first import writes its own config
  [ -f "$TOTALSEG_HOME_DIR/config.json" ] || printf '{"totalseg_id": "schwingnet-gold3", "send_usage_stats": false, "prediction_counter": 0}\n' > "$TOTALSEG_HOME_DIR/config.json"
  unpack_weights || { report "FAILED: a weight zip could not be unpacked into $WEIGHTS"; finish 1; }
  report "environment: $TS_PIN; weights: $WEIGHTS (from $ZIPS); CTs and release masks read from the data root; masks written under $OUT/ts"
  rm -f "$RC_FILE"
  bash grid/box.sh "$VENV/bin/python" flows/launch.py totalseg --max-workers 1 -- --out "$OUT" --weights "$WEIGHTS" &
  LAUNCHER=$!
  wait "$LAUNCHER"; rc=$?
  LAUNCHER=""
  said=$(cat "$RC_FILE" 2>/dev/null)
  case "$said" in
    ""|*[!0-9]*)
      [ "$rc" != 0 ] || { report "segment: the flow ended 0 and this job's body left no exit: the launcher resumed a run whose finished segment step Metaflow cloned, so the masks and the report are that run's"; finish 0; }
      report "FAILED: the launcher ended $rc and the body left no exit (a refusal of the launcher's, or a fault of the flow; the job's log says which)"
      finish "$rc" ;;
    0) [ "$rc" = 0 ] || report "FAILED: the body ended 0, but its flow ended $rc: its end failed after the work (the job's log and the run's page say why); the masks and records stand"
       finish "$rc" ;;
    *) finish "$said" ;;
  esac
}
unhold() { [ "$(awk '{ print $1; exit }' "$HOLD" 2>/dev/null)" != "${SLURM_JOB_ID:-$$}" ] || rm -f "$HOLD"; }

if [ -n "$BODY" ]; then body; else driver; fi
