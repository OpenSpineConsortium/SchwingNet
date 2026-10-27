#!/bin/bash
#SBATCH --cpus-per-task=4
#SBATCH --mem=50G
#SBATCH --time=12:00:00
# One benchmark of a public spine or pelvis X-ray model, as its authors published it (issue #287,
# the owner's word and count of 2026-10-25: three GPU jobs, docs/research/public-spine-and-pelvis-models-to-benchmark.md).
# grid/gate.sh's word `bench <name>` queues it as the gpu class with BENCH, the name, in the environment:
#
#   flexray_carmlspine  FleXray's open weights name the level of each C-ArmLSpine truth box (tools/bench_public.py)
#   flexray_deepfluoro  FleXray's Dice on DeepFluoro against its published 0.916
#   xvr_deepfluoro      xvr's published DeepFluoro models through xvr's own register and evaluate scripts,
#                       against its published 1.1 mm median mTRE
#   flexray_drr_gap     the DRR domain-gap study (tools/domain_gap.py, docs/research/drr-domain-gap/README.md):
#                       FleXray's recipe through this project's render blocks and through FleXray's own
#                       code, beside every held real X-ray corpus and FluXray, with the replication test,
#                       the CTs labelled by SPINEPS's existing masks (the production segmenter) and by
#                       MOOSE's (the replication's, the owner's word of 2026-10-26), which flexray_drr_seg
#                       makes; only its summary.txt leaves the grid, each line through grid/redact.sed
#   flexray_drr_seg     the study's choice of CTs (tools/domain_gap.py plan, rendering nothing) and MOOSE
#                       on exactly those (tools/flexray_render.py segment, moosez's Python entry on the
#                       fetched model zips, never a download), written under the data root's moose in
#                       moosez's own layout; sent before flexray_drr_gap, which reads the masks
#
# The public package goes into a throwaway virtual environment on the lab volume, made from the
# train-gpu environment with its site packages (torch among them) and kept for a rerun under a name
# that carries the pins, so the repository takes no new dependency and pixi.lock is never touched.
# Nothing trains. Results go to $BENCH_ROOT/<name>/; the report is logs/BENCH-<name>.md, which the
# next `bench <name>` prints. Not requeued (--no-requeue from the gate): a second start would score twice.
# The checkout holds still while the benchmark lasts, as for a version 1 run: grid/logs/HOLD names
# this job and the commit, the gate's side skips its fast-forward while the file is there, the gate
# clears a hold whose job Slurm no longer holds, and each run that holds it waits for the others
# (grid/gate.sh, checkout_holders). The commit is read again at the end, and a benchmark whose
# checkout moved anyway is failed, since its report names the commit it began on.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
DATA=${DATA_ROOT:-/rs/rs_grp_oschome/go2432/data}
LAB=${LAB_VOLUME:-/rs/rs_grp_oschome}
BENCH_ROOT=${BENCH_ROOT:-$LAB/go2432/bench}
BENCH=${BENCH:-}
FLEXRAY_PIN="flexray==1.0.2 h5py"
XVR_COMMIT=1abc2af07efa5b5a6c3576525a79de1f9b3e9f81
XVR_PIN="git+https://github.com/eigenvivek/xvr.git@$XVR_COMMIT pandas click tqdm"
DRR_GAP_PIN="flexray[train]==1.0.2 nanodrr==0.1.5 scikit-learn==1.9.1 umap-learn==0.5.12 numpy==2.4.6"
# moosez's newest release on PyPI when this line was written (2026-10-26); its README calls it MOOSE 3.2.
MOOSE_PIN="moosez==3.2.2"
# The segmentation job runs MOOSE but chooses its CTs through tools/flexray_render.py, which loads
# tools/render_blocks.py, and that imports fxr.drr at the top; fxr.drr imports nanodrr, which
# flexray keeps among its train extras. With MOOSE alone the plan stopped at the import
# (job 40790826), so the job's environment carries both, pinned as DRR_GAP_PIN pins them.
SEG_PIN="$MOOSE_PIN flexray==1.0.2 nanodrr==0.1.5"
case "$BENCH" in flexray_carmlspine|flexray_deepfluoro|xvr_deepfluoro|flexray_drr_gap|flexray_drr_seg) ;; *) echo "bench: BENCH is one of flexray_carmlspine, flexray_deepfluoro, xvr_deepfluoro, flexray_drr_gap, flexray_drr_seg"; echo "SN_BENCH_RC=64"; exit 64 ;; esac
REPORT=$REPO/grid/logs/BENCH-$BENCH.md
OUT=$BENCH_ROOT/$BENCH
mkdir -p "$REPO/grid/logs" "$OUT"
cd "$REPO" || exit 2
export PYTHONNOUSERSITE=1 WANDB_MODE=disabled HF_HUB_OFFLINE=1
# Triton builds a small C helper with gcc and -lcuda on its first GPU call. Under Apptainer's --nv
# the driver's libraries sit in /.singularity.d/libs rather than where ldconfig looks, and xvr's
# registration failed there on every subject (job 40781587), so Triton is told where they are.
export TRITON_LIBCUDA_PATH=${TRITON_LIBCUDA_PATH:-/.singularity.d/libs}
report() { echo "- $*" | tee -a "$REPORT.part"; }
finish() {
  local rc=$1 ended_at
  ended_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
  if [ "$ended_at" != "$started_at" ]; then
    report "FAILED: the checkout moved from ${started_at:0:7} to ${ended_at:0:7} during the benchmark, so a later step may have run the newer code while this report names the older; its results are not used"
    [ "$rc" != 0 ] || rc=3
  fi
  report "exit $rc at $(date -u '+%F %T') UTC"
  mv "$REPORT.part" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_BENCH_RC=$rc"
  exit "$rc"
}
started_at=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
echo "# bench $BENCH: job ${SLURM_JOB_ID:-none} on $(hostname), commit ${started_at:0:7}, $(date -u '+%F %T') UTC" > "$REPORT.part"
[ -n "$started_at" ] || { report "FAILED: the checkout at $REPO names no commit"; finish 2; }
HOLD=$REPO/grid/logs/HOLD
echo "${SLURM_JOB_ID:-$$} $started_at" > "$HOLD"
unhold() { [ "$(awk '{ print $1; exit }' "$HOLD" 2>/dev/null)" != "${SLURM_JOB_ID:-$$}" ] || rm -f "$HOLD"; }
trap unhold EXIT
trap 'exit 143' TERM
report "GPU: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -n 1 || echo 'nvidia-smi gave nothing')"

# venv_for, the throwaway environment on the lab volume, lives in grid/venv.sh since the anomaly
# route's pack stage makes one too (#391).
# shellcheck source=grid/venv.sh
. "$REPO/grid/venv.sh"
failure_of() {  # the first compiler or linker error in a log, else its last line, in one short line
  { grep -m 1 -E '(: (fatal )?error:|cannot find -l|undefined reference)' "$1" || tail -n 1 "$1"; } | cut -c1-240
}
weights_dir() {  # the FleXray bundle the fetch landed: the folder that holds ensemble.json
  dirname "$(find "$DATA/hf_flexray_weights/raw" -maxdepth 3 -name ensemble.json -print -quit 2>/dev/null)"
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
  # grid/gate.sh's check again, where the job runs, since the gate's may be hours old by the time
  # the job starts: the url route lands each zip under its final name while curl resumes it and
  # leaves a part there when a download is cut short (grid/platform-fetch.sbatch, fetch_url), which
  # [ -s ] passes and the unpack would die on. The node may have no python3, so awk and coreutils
  # read the record; unzip, where it is there, tests every member's CRC too, which tells a zip
  # resumed across two uploads of the asset, whole by its record, from a sound one.
  local size from
  size=$(stat -c %s "$1" 2>/dev/null) && [ "$size" -ge 22 ] || return 1
  from=$(( size > 65558 ? size - 65558 : 0 ))
  tail -c +"$((from + 1))" "$1" | od -An -v -tx1 -w1 | awk '
    function hex(s,  i, v) { v = 0; for (i = 1; i <= length(s); i++) v = v * 16 + index("0123456789abcdef", substr(s, i, 1)) - 1; return v }
    { bytes[NR] = $1 }
    END { for (i = NR - 21; i >= 1; i--) if (bytes[i] bytes[i + 1] bytes[i + 2] bytes[i + 3] == "504b0506" && i + 21 + hex(bytes[i + 21] bytes[i + 20]) == NR) exit 0; exit 1 }' || return 1
  ! command -v unzip > /dev/null 2>&1 || unzip -tq "$1" > /dev/null 2>&1 || return 2
}
samples_index() {  # the sample index the gate checked (INDEX), else the newest whole run's, as grid/gate.sh names it in CURRENT
  local out=${SAMPLES_OUT:-$DATA/_samples} current
  [ -z "${INDEX:-}" ] || { echo "$INDEX"; return; }
  current=$(cat "$out/CURRENT" 2>/dev/null)
  [ -n "$current" ] && echo "$out/$current/samples.sqlite"
}

tail_lines=12  # how much of what the tool said the report carries: its last lines, or the whole summary
case "$BENCH" in
  flexray_carmlspine|flexray_deepfluoro)
    venv=$(venv_for "$FLEXRAY_PIN") || { report "FAILED: the environment for $FLEXRAY_PIN could not be made"; finish 1; }
    weights=$(weights_dir)
    [ -f "$weights/ensemble.json" ] || { report "FAILED: no ensemble.json under $DATA/hf_flexray_weights/raw"; finish 2; }
    report "weights: $weights; environment: $FLEXRAY_PIN"
    if [ "$BENCH" = flexray_carmlspine ]; then
      bank=$DATA/realxray/carmlspine
      said=$(bash grid/box.sh "$venv/bin/python" tools/bench_public.py flexray-carmlspine --weights "$weights" --bank "$bank" --out "$OUT" 2>&1); rc=$?
    else
      h5=$(find "$DATA/deepfluoro_h5/raw" -name '*.h5' -size +1M -print -quit 2>/dev/null)
      [ -n "$h5" ] || { report "FAILED: no DeepFluoro .h5 under $DATA/deepfluoro_h5/raw"; finish 2; }
      said=$(bash grid/box.sh "$venv/bin/python" tools/bench_public.py flexray-deepfluoro --weights "$weights" --h5 "$h5" --out "$OUT" 2>&1); rc=$?
    fi ;;
  xvr_deepfluoro)
    venv=$(venv_for "$XVR_PIN") || { report "FAILED: the environment for xvr at $XVR_COMMIT could not be made"; finish 1; }
    models=$(find "$DATA/hf_xvr_models/raw" -path '*/deepfluoro/finetuned/subject01.pth' -print -quit 2>/dev/null)
    [ -n "$models" ] || { report "FAILED: no deepfluoro/finetuned/subject01.pth under $DATA/hf_xvr_models/raw"; finish 2; }
    [ -f "$DATA/hf_xvr_data/raw/deepfluoro/subject01/volume.nii.gz" ] || { report "FAILED: no deepfluoro/subject01/volume.nii.gz under $DATA/hf_xvr_data/raw"; finish 2; }
    work=$OUT/xvr
    if [ ! -d "$work/.git" ]; then
      rm -rf "$work"; git clone -q https://github.com/eigenvivek/xvr.git "$work" || { report "FAILED: xvr could not be cloned"; finish 1; }
    fi
    git -C "$work" checkout -q "$XVR_COMMIT" || { report "FAILED: xvr has no commit $XVR_COMMIT"; finish 1; }
    ln -sfn "$DATA/hf_xvr_data/raw" "$work/experiments/data"
    ln -sfn "${models%/deepfluoro/finetuned/subject01.pth}" "$work/experiments/models"
    report "xvr: $XVR_COMMIT; models: ${models%/deepfluoro/finetuned/subject01.pth}"
    # The arguments of xvr's experiments/scripts/deepfluoro/register/finetuned.sh at that commit, one subject at a time.
    rc=0
    for n in 01 02 03 04 05 06; do
      s=subject$n; dest=experiments/results/deepfluoro/finetuned/$s
      ( cd "$work" && rm -rf "$dest" && mkdir -p "$dest" && \
        bash "$REPO/grid/box.sh" "$venv/bin/xvr" register model \
          --files experiments/data/deepfluoro/$s/xrays/*.dcm --ckpt experiments/models/deepfluoro/finetuned/$s.pth \
          --imagepath experiments/data/deepfluoro/$s/volume.nii.gz --labelpath experiments/data/deepfluoro/$s/mask.nii.gz \
          --warp experiments/data/deepfluoro/$s/warp.txt --labels 1 2 3 4 7 --scales 24 12 6 \
          --n-itrs 500 500 500 --patience 10 10 10 --crop 100 --linearize --savepath "$dest" ) > "$OUT/register-$s.log" 2>&1 \
        || { report "$s: register failed ($(failure_of "$OUT/register-$s.log"))"; rc=1; }
    done
    ( cd "$work" && bash "$REPO/grid/box.sh" "$venv/bin/python" experiments/evaluate.py --dataset deepfluoro --result finetuned \
        --main "$OUT/registration.csv" --device cuda ) > "$OUT/evaluate.log" 2>&1 \
      || { report "FAILED: xvr's evaluate.py ($(tail -n 1 "$OUT/evaluate.log" | cut -c1-160))"; finish 1; }
    said=$(bash grid/box.sh "$venv/bin/python" tools/bench_public.py xvr-summary --csv "$OUT/registration.csv" --out "$OUT" 2>&1) || rc=1 ;;
  flexray_drr_gap)
    # The study's inputs, each named in the report, since its numbers are read against them. The gate
    # refused the word without them (grid/gate.sh, bench_inputs_missing); a miss here is a samples run
    # or a fetch that moved since, said and failed rather than run on part of the table.
    venv=$(venv_for "$DRR_GAP_PIN") || { report "FAILED: the environment for $DRR_GAP_PIN could not be made"; finish 1; }
    weights=$(weights_dir)
    [ -f "$weights/ensemble.json" ] || { report "FAILED: no ensemble.json under $DATA/hf_flexray_weights/raw"; finish 2; }
    index=$(samples_index)
    [ -n "$index" ] && [ -f "$index" ] || { report "FAILED: no whole sample index under ${SAMPLES_OUT:-$DATA/_samples} (the gate word samples makes it)"; finish 2; }
    [ -d "$DATA/totalsegmentator_v201" ] || { report "FAILED: no totalsegmentator_v201 under $DATA, the CTs the render groups draw"; finish 2; }
    # The masks of both segmenters: the render groups' CTs are chosen among those with masks under
    # each, so a missing folder would render nothing (the gate refused the word without them).
    [ -d "$DATA/spineps" ] || { report "FAILED: no spineps under $DATA, the production segmenter's masks"; finish 2; }
    [ -d "$DATA/moose" ] || { report "FAILED: no moose under $DATA, the replication's masks (bench flexray_drr_seg makes them)"; finish 2; }
    imagenet=${MODELS:-$LAB/go2432/models}/resnet18-f37072fd.pth
    [ -s "$imagenet" ] || { report "FAILED: no ImageNet ResNet-18 file at $imagenet (the gate word start fetches it)"; finish 2; }
    # FluXray is the one optional input: the tool reads it when the fetch has landed it and skips its
    # group with that reason otherwise, so the study never waits for it.
    if [ -d "$DATA/hf_flexray_data/raw" ]; then report "FluXray: read from $DATA/hf_flexray_data/raw"
    else report "FluXray: not on the data root (fetch hf_flexray_data); the study skips its group with that reason"; fi
    report "environment: $DRR_GAP_PIN; index: $index; weights: $weights; imagenet: $imagenet; masks: $DATA/spineps, $DATA/moose"
    # The run folder is the owner's alone: the plan names files and person keys, and the run's own
    # output goes there too, since only summary.txt leaves the grid.
    umask 077; chmod 700 "$OUT"
    bash grid/box.sh "$venv/bin/python" tools/domain_gap.py run --groups data/domain_gap/groups.json --data-root "$DATA" \
      --index "$index" --weights "$weights" --imagenet "$imagenet" --out "$OUT" --device cuda \
      --frozen data/splits/test-persons.json --spineps "$DATA/spineps" --moose "$DATA/moose" > "$OUT/run.log" 2>&1; rc=$?
    [ "$rc" = 0 ] || { report "FAILED: domain_gap.py run ended $rc ($(tail -n 1 "$OUT/run.log" | sed -r -f grid/redact.sed | cut -c1-160))"; finish "$rc"; }
    # The summary, at most 80 lines of numbers and group names, each through the filter the gate word
    # status applies to every log line, and the report carries it whole.
    said=$(bash grid/box.sh "$venv/bin/python" tools/domain_gap.py summary --out "$OUT" 2>&1 | sed -r -f grid/redact.sed); rc=$?
    tail_lines=80 ;;
  flexray_drr_seg)
    # MOOSE's masks for the CTs the study will render, so that flexray_drr_gap reads existing masks
    # for both segmenters and runs no segmenter itself. The inputs first, since the gate's check
    # may be hours old by the time the job starts; the weights are the fetched zips, read in place,
    # and a zip not there fails the job by name rather than let moosez download it.
    [ -d "$DATA/totalsegmentator_v201" ] || { report "FAILED: no totalsegmentator_v201 under $DATA, the CTs the render groups draw"; finish 2; }
    [ -d "$DATA/spineps" ] || { report "FAILED: no spineps under $DATA, the masks the choice of CTs is made among"; finish 2; }
    zip=$(moose_zip_missing)
    case "$zip" in
      "") ;;
      row) report "FAILED: the row moose_weights of grid/run-platform-fetch.sh was not read, so no zip can be named"; finish 2 ;;
      *" part") report "FAILED: ${zip% part} under $DATA/moose_weights/raw is not a whole zip (a part still landing or cut short, which a resend of fetch moose_weights resumes)"; finish 2 ;;
      *" damaged") report "FAILED: ${zip% damaged} under $DATA/moose_weights/raw is whole by its record but unzip finds a member damaged (a download resumed across two uploads of the asset, say): delete it in the grid's shell and resend fetch moose_weights, which lands it again"; finish 2 ;;
      *) report "FAILED: no ${zip% missing} under $DATA/moose_weights/raw (fetch moose_weights first)"; finish 2 ;;
    esac
    venv=$(venv_for "$SEG_PIN") || { report "FAILED: the environment for $SEG_PIN could not be made"; finish 1; }
    report "environment: $SEG_PIN; weights: $DATA/moose_weights/raw; CTs: $DATA/totalsegmentator_v201; masks: $DATA/moose"
    # The choice of CTs, made as the study makes it but before any MOOSE mask exists, to
    # render-subjects.json in this job's own folder (the plan's log stays there too, under umask 077
    # as the study's does, though it names TotalSegmentator subjects alone).
    ( umask 077; chmod 700 "$OUT"
      bash grid/box.sh "$venv/bin/python" tools/domain_gap.py plan --groups data/domain_gap/groups.json --data-root "$DATA" \
        --out "$OUT" --frozen data/splits/test-persons.json --spineps "$DATA/spineps" --moose "$DATA/moose" > "$OUT/plan.log" 2>&1 ); rc=$?
    [ "$rc" = 0 ] || { report "FAILED: domain_gap.py plan ended $rc ($(tail -n 1 "$OUT/plan.log" | sed -r -f grid/redact.sed | cut -c1-160))"; finish "$rc"; }
    [ -s "$OUT/render-subjects.json" ] || { report "FAILED: domain_gap.py plan wrote no render-subjects.json under $OUT"; finish 2; }
    # MOOSE on exactly those CTs, through the segment subcommand's own plan (which subjects still
    # lack masks, which models), the masks landing under the data root's moose in moosez's layout.
    said=$(bash grid/box.sh "$venv/bin/python" tools/flexray_render.py segment --segmenter moose --ct-root "$DATA/totalsegmentator_v201" \
      --subjects "$OUT/render-subjects.json" --weights "$DATA/moose_weights/raw" --out "$DATA/moose" 2>&1 | sed -r -f grid/redact.sed); rc=$?
    # The segment subcommand prints its plan and its record as JSON (every subject, the data root's
    # paths, each zip's bytes) and ends with one plain line, the subjects run, the models, the files
    # found and not found and where they were written: the report carries that line alone, since the
    # JSON's last lines are closing brackets, and the whole stays in the job's log; a run that failed
    # keeps its last lines, the refusal or the traceback's end.
    [ "$rc" != 0 ] || tail_lines=1 ;;
esac
echo "$said"
report "results: $OUT"
echo "$said" | tail -n "$tail_lines" | sed 's/^/  /' >> "$REPORT.part"
finish "$rc"
