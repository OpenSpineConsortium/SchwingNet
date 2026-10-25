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
report() { echo "- $*" | tee -a "$REPORT.part"; }
finish() {
  report "exit $1 at $(date -u '+%F %T') UTC"
  mv "$REPORT.part" "$REPORT" && chmod 644 "$REPORT"
  echo "SN_BENCH_RC=$1"
  exit "$1"
}
echo "# bench $BENCH: job ${SLURM_JOB_ID:-none} on $(hostname), commit $(git rev-parse --short HEAD), $(date -u '+%F %T') UTC" > "$REPORT.part"
report "GPU: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -n 1 || echo 'nvidia-smi gave nothing')"

venv_for() {  # venv_for PINS: a virtual environment holding PINS beside train-gpu's packages, made once
  local key venv
  key=$(printf '%s' "$1" | sha256sum | cut -c1-12)
  venv=$LAB/go2432/.cache/bench/venv-$key
  if [ ! -f "$venv/READY" ]; then
    rm -rf "$venv"
    bash grid/box.sh pixi run --locked -e train-gpu python -m venv --system-site-packages "$venv" || return 1
    # shellcheck disable=SC2086
    bash grid/box.sh "$venv/bin/python" -m pip install --quiet $1 || return 1
    printf '%s\n' "$1" > "$venv/READY"
  fi
  echo "$venv"
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
        || { report "$s: register failed ($(tail -n 1 "$OUT/register-$s.log" | cut -c1-160))"; rc=1; }
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
