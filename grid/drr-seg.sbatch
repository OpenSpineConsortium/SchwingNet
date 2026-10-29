#!/bin/bash
#SBATCH --cpus-per-task=4
#SBATCH --mem=50G
#SBATCH --time=12:00:00
# MOOSE's masks for the CTs the DRR domain-gap study will render (docs/research/drr-domain-gap/README.md):
# the study's choice of CTs (tools/domain_gap.py plan, rendering nothing) and MOOSE on exactly those
# (tools/flexray_render.py segment, moosez's Python entry on the fetched model zips, never a
# download), written under the data root's moose in moosez's own layout, so that the study reads
# existing masks for both segmenters and runs no segmenter itself. The gate word
# `bench flexray_drr_seg` queues it as job submit's gpu class, sent before the study's prepare where
# MOOSE's masks are missing; it was a branch of the bench script until the owner's rule of
# 2026-10-29 that every deep learning job on the grid runs on a launched flow, under a frozen
# PREREG, with a progress page.
#
# The job Slurm starts is the driver: it holds the checkout, checks the inputs, makes the
# environment and then starts flows/launch.py drr_seg (flows/drr_seg.py, DrrSegFlow), held to the
# study's frozen PREREG.md, whose one working step runs this script again with SCHWINGNET_FLOW_STEP=1
# for the work, the body below. The launcher resumes the newest run of the same words and code that
# did not finish, so a job cut short and sent again carries its run on; no subject's masks are
# written again, since the choice of CTs ignores MOOSE's masks and the segment subcommand runs only
# the models each chosen subject still lacks (flows/drr_seg.py says how, and what a cut leaves). The
# job ends with the segmentation's exit, unless it ended 0 and the flow did not, when the job's exit
# is the launcher's, as every launched flow's job's is; where the launcher resumed a run whose
# finished segment step Metaflow cloned, the flow's 0 is the masks' (driver).
#
# The model's package goes into a throwaway virtual environment on the lab volume, made from the
# train-gpu environment with its site packages (torch and Metaflow among them) and kept for a rerun
# under a name that carries the pins (grid/venv.sh), so the repository takes no new dependency and
# pixi.lock is never touched. Nothing trains. The job's own files go to $BENCH_ROOT/flexray_drr_seg/;
# the report is logs/BENCH-flexray_drr_seg.md, which the next send of the word prints. Not requeued
# (--no-requeue from the gate). The checkout holds still while the job lasts, as for a version 1
# run: grid/logs/HOLD names this job and the commit, the gate's side skips its fast-forward while
# the file is there, the gate clears a hold whose job Slurm no longer holds, and each run that holds
# it waits for the others (the gate's checkout_holders). The commit is read again at the end, and a
# job whose checkout moved anyway is failed, since its report names the commit it began on.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
BENCH_ROOT=${BENCH_ROOT:-$LAB/go2432/bench}
BENCH=flexray_drr_seg
# The flow's step runs this script again for the work; the job Slurm starts runs the driver.
BODY=${SCHWINGNET_FLOW_STEP:-}
# moosez's newest release on PyPI when this line was written (2026-10-26); its README calls it MOOSE 3.2.
MOOSE_PIN="moosez==3.2.2"
# The job runs MOOSE but chooses its CTs through tools/flexray_render.py, which loads
# tools/render_blocks.py, and that imports fxr.drr at the top; fxr.drr imports nanodrr, which
# flexray keeps among its train extras. With MOOSE alone the plan stopped at the import (job
# 40790826), so the job's environment carries both, pinned as the study's DRR_GAP_PIN pins them.
SEG_PIN="$MOOSE_PIN flexray==1.0.2 nanodrr==0.1.5"
REPORT=$REPO/grid/logs/BENCH-$BENCH.md
OUT=$BENCH_ROOT/$BENCH
# The body's exit, which it leaves here for the driver: the launcher's own exit is the flow's verdict.
RC_FILE=$OUT/SEGMENT_RC
mkdir -p "$REPO/grid/logs" "$OUT"
cd "$REPO" || exit 2
export PYTHONNOUSERSITE=1 WANDB_MODE=disabled HF_HUB_OFFLINE=1
# Triton builds a small C helper with gcc and -lcuda on its first GPU call, and under Apptainer's --nv
# the driver's libraries sit in /.singularity.d/libs (the bench script's job 40781587).
export TRITON_LIBCUDA_PATH=${TRITON_LIBCUDA_PATH:-/.singularity.d/libs}
# The report's lines go to its part file first and the job's log after: the body's log is the flow's
# pipe, which a TERM that ends the flow's step closes, and a write to it then must not keep a line from the file.
report() { echo "- $*" >> "$REPORT.part"; echo "- $*"; }
# shellcheck source=grid/venv.sh
. "$REPO/grid/venv.sh"

# --- the body: the flow's step ------------------------------------------------------------------
body() {
  local venv said rc tail_lines=12
  rm -f "$RC_FILE"
  trap 'trap "" PIPE; exit 143' TERM
  # The frozen PREREG checked against its hash before the work, as the study's own steps check it,
  # since the masks are the study's input and their choice of CTs is the study's.
  ( cd docs/research/drr-domain-gap 2>/dev/null && sha256sum -c --status PREREG.md.sha256 ) \
    || { report "STOP: PREREG.md changed since the freeze"; body_end 90; }
  venv=$(venv_ready "$SEG_PIN") || { report "FAILED: the environment for $SEG_PIN is not whole, though the driver made it"; body_end 1; }
  # The choice of CTs, made as the study makes it but before any MOOSE mask exists, to
  # render-subjects.json in this job's own folder (the plan's log stays there too, under umask 077
  # as the study's does, though it names TotalSegmentator subjects alone).
  ( umask 077; chmod 700 "$OUT"
    bash grid/box.sh "$venv/bin/python" tools/domain_gap.py plan --groups data/domain_gap/groups.json --data-root "$DATA" \
      --out "$OUT" --frozen data/splits/test-persons.json --spineps "$DATA/spineps" --moose "$DATA/moose" > "$OUT/plan.log" 2>&1 ); rc=$?
  [ "$rc" = 0 ] || { report "FAILED: domain_gap.py plan ended $rc ($(tail -n 1 "$OUT/plan.log" | sed -r -f grid/redact.sed | cut -c1-160))"; body_end "$rc"; }
  [ -s "$OUT/render-subjects.json" ] || { report "FAILED: domain_gap.py plan wrote no render-subjects.json under $OUT"; body_end 2; }
  # MOOSE on exactly those CTs, through the segment subcommand's own plan (which subjects still
  # lack masks, which models), the masks landing under the data root's moose in moosez's layout.
  said=$(bash grid/box.sh "$venv/bin/python" tools/flexray_render.py segment --segmenter moose --ct-root "$DATA/totalsegmentator_v201" \
    --subjects "$OUT/render-subjects.json" --weights "$DATA/moose_weights/raw" --out "$DATA/moose" 2>&1 | sed -r -f grid/redact.sed); rc=$?
  # The segment subcommand prints its plan and its record as JSON (every subject, the data root's
  # paths, each zip's bytes) and ends with one plain line, the subjects run, the models, the files
  # found and not found and where they were written: the report carries that line alone, since the
  # JSON's last lines are closing brackets, and the whole stays in the job's log; a run that failed
  # keeps its last lines, the refusal or the traceback's end.
  [ "$rc" != 0 ] || tail_lines=1
  echo "$said"
  report "results: $OUT"
  echo "$said" | tail -n "$tail_lines" | sed 's/^/  /' >> "$REPORT.part"
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
  echo "SN_BENCH_RC=$rc"
  exit "$rc"
}
moose_zip_missing() {  # the first of MOOSE's model zips not whole under the data root's moose_weights/raw, by the fetch row's URLs: "<name> missing", "<name> part", "<name> damaged", or "row" where the row was not read
  local urls url file whole
  urls=$(bash grid/run-platform-fetch.sh --args moose_weights 2>/dev/null)
  [ -n "$urls" ] || { echo row; return; }
  for url in $urls; do
    file=$DATA/moose_weights/raw/${url##*/}
    [ -s "$file" ] || { echo "${url##*/} missing"; return; }
    whole=0; zip_whole "$file" || whole=$?
    case "$whole" in 0) ;; 2) echo "${url##*/} damaged"; return ;; *) echo "${url##*/} part"; return ;; esac
  done
}
zip_whole() {  # zip_whole FILE: 0 where the file ends in a whole end-of-central-directory record, read as Python's zipfile.is_zipfile reads it, and unzip finds every member whole where the node has unzip; 2 where only unzip's test fails
  # The gate's check again, where the job runs, since the gate's may be hours old by the time the
  # job starts: the url route lands each zip under its final name while curl resumes it and leaves a
  # part there when a download is cut short (the platform fetch's fetch_url), which [ -s ] passes
  # and the unpack would die on. The node may have no python3, so awk and coreutils read the record;
  # unzip, where it is there, tests every member's CRC too, which tells a zip resumed across two
  # uploads of the asset, whole by its record, from a sound one.
  local size from
  size=$(stat -c %s "$1" 2>/dev/null) && [ "$size" -ge 22 ] || return 1
  from=$(( size > 65558 ? size - 65558 : 0 ))
  tail -c +"$((from + 1))" "$1" | od -An -v -tx1 -w1 | awk '
    function hex(s,  i, v) { v = 0; for (i = 1; i <= length(s); i++) v = v * 16 + index("0123456789abcdef", substr(s, i, 1)) - 1; return v }
    { bytes[NR] = $1 }
    END { for (i = NR - 21; i >= 1; i--) if (bytes[i] bytes[i + 1] bytes[i + 2] bytes[i + 3] == "504b0506" && i + 21 + hex(bytes[i + 21] bytes[i + 20]) == NR) exit 0; exit 1 }' || return 1
  ! command -v unzip > /dev/null 2>&1 || unzip -tq "$1" > /dev/null 2>&1 || return 2
}
LAUNCHER=""
# How long the driver waits, after passing Slurm's TERM on to the launcher, for the flow to end:
# Slurm's warning comes two minutes before the time limit.
STOP_GRACE=80
keep_segment_record() {  # the record an earlier segmentation left beside the masks, kept in this job's folder, since the segment subcommand writes its own over it
  local record=$DATA/moose/SEGMENT.json kept
  [ -f "$record" ] || return 0
  kept=$OUT/SEGMENT-before-job-${SLURM_JOB_ID:-none}.json
  if ( umask 077; cp "$record" "$kept" ); then report "kept: the masks' earlier SEGMENT.json as $kept, since this run writes its own"
  else report "NOTE: the masks' earlier SEGMENT.json could not be kept as $kept"; fi
}
launcher_stop() {  # the TERM passed on to the launcher, which passes it to the flow, then up to STOP_GRACE seconds for it to end
  local waited=0
  [ -n "$LAUNCHER" ] || return 0
  kill -TERM "$LAUNCHER" 2>/dev/null
  while kill -0 "$LAUNCHER" 2>/dev/null && [ "$waited" -lt "$STOP_GRACE" ]; do sleep 1; waited=$((waited + 1)); done
}
driver() {
  local zip venv rc said
  started_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
  echo "# bench $BENCH: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${started_at:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"
  [ -n "$started_at" ] || { report "FAILED: the checkout at $REPO names no commit"; finish 2; }
  HOLD=$REPO/grid/logs/HOLD
  echo "${SLURM_JOB_ID:-$$} $started_at" > "$HOLD"
  trap unhold EXIT
  # Cut short, the job writes no report, as before it ran on a flow; the run it began is resumed
  # by the next send of the word.
  trap 'launcher_stop; exit 143' TERM
  report "GPU: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -n 1 || echo 'nvidia-smi gave nothing')"
  # The inputs first, since the gate's check may be hours old by the time the job starts; the
  # weights are the fetched zips, read in place, and a zip not there fails the job by name rather
  # than let moosez download it.
  [ -d "$DATA/totalsegmentator_v201" ] || { report "FAILED: no totalsegmentator_v201 under $DATA, the CTs the render groups draw"; finish 2; }
  [ -d "$DATA/spineps" ] || { report "FAILED: no spineps under $DATA, the masks the choice of CTs is made among"; finish 2; }
  zip=$(moose_zip_missing)
  case "$zip" in
    "") ;;
    row) report "FAILED: the row moose_weights of the platform fetch was not read, so no zip can be named"; finish 2 ;;
    *" part") report "FAILED: ${zip% part} under $DATA/moose_weights/raw is not a whole zip (a part still landing or cut short, which a resend of fetch moose_weights resumes)"; finish 2 ;;
    *" damaged") report "FAILED: ${zip% damaged} under $DATA/moose_weights/raw is whole by its record but unzip finds a member damaged (a download resumed across two uploads of the asset, say): delete it in the grid's shell and resend fetch moose_weights, which lands it again"; finish 2 ;;
    *) report "FAILED: no ${zip% missing} under $DATA/moose_weights/raw (fetch moose_weights first)"; finish 2 ;;
  esac
  venv=$(venv_for "$SEG_PIN") || { report "FAILED: the environment for $SEG_PIN could not be made"; finish 1; }
  report "environment: $SEG_PIN; weights: $DATA/moose_weights/raw; CTs: $DATA/totalsegmentator_v201; masks: $DATA/moose"
  keep_segment_record
  # The launcher and the flow run in that environment, which carries train-gpu's Metaflow; the flow's
  # step leaves the body's exit in RC_FILE, and the launcher's own is the flow's verdict, or the
  # flow's own code where it failed.
  rm -f "$RC_FILE"
  bash grid/box.sh "$venv/bin/python" flows/launch.py drr_seg --max-workers 1 -- --out "$OUT" --masks "$DATA/moose" &
  LAUNCHER=$!
  wait "$LAUNCHER"; rc=$?
  LAUNCHER=""
  said=$(cat "$RC_FILE" 2>/dev/null)
  case "$said" in
    ""|*[!0-9]*)
      # No exit and a flow that ended 0: the launcher resumed a run whose segment step had ended 0,
      # which Metaflow cloned rather than ran again, since the verdict is 0 only where it ended 0.
      [ "$rc" != 0 ] || { report "segment: the flow ended 0 and this job's segmentation left no exit: the launcher resumed a run whose finished segment step Metaflow cloned, so the masks are that run's"; finish 0; }
      report "FAILED: the launcher ended $rc and the segmentation left no exit (a refusal of the launcher's, or a fault of the flow; the job's log says which)"
      finish "$rc" ;;
    0) [ "$rc" = 0 ] || report "FAILED: the segmentation ended 0, but its flow ended $rc: its end failed after the work (the job's log and the run's page say why); the masks it wrote stand"
       finish "$rc" ;;
    *) finish "$said" ;;
  esac
}
unhold() { [ "$(awk '{ print $1; exit }' "$HOLD" 2>/dev/null)" != "${SLURM_JOB_ID:-$$}" ] || rm -f "$HOLD"; }

if [ -n "$BODY" ]; then body; else driver; fi
