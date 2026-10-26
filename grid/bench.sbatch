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
case "$BENCH" in flexray_carmlspine|flexray_deepfluoro|xvr_deepfluoro) ;; *) echo "bench: BENCH is one of flexray_carmlspine, flexray_deepfluoro, xvr_deepfluoro"; echo "SN_BENCH_RC=64"; exit 64 ;; esac
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
esac
echo "$said"
report "results: $OUT"
echo "$said" | tail -n 12 | sed 's/^/  /' >> "$REPORT.part"
finish "$rc"
