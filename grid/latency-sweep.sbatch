#!/bin/bash
#SBATCH --job-name=sn_latency
#SBATCH --partition=gmsap
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:30:00
#SBATCH --output=logs/%x_%A_%a.out
# Issue #13: one part of the latency, ONNX and sweep work on one run of the level stage, chosen by
# PART (and, for a sweep array, by SLURM_ARRAY_TASK_ID over SWEEPS). grid/run-latency-sweep.sh
# submits it four ways and says which; by hand:
#   PART=gpu    the ONNX export, its parity on validation crops (CPU and the GPU), then the frame
#               path's latency with PyTorch and with ONNX Runtime on this node's GPU
#   PART=cpu    the frame path's latency with PyTorch and ONNX Runtime on THREADS CPU threads,
#               after PART=gpu (it needs the export and its parity)
#   PART=sweep  one recorded sweep per array task: SWEEPS is "name:frames:boxes name:frames:boxes",
#               run through ONNX Runtime on the GPU with the overlay recording
#   PART=probe  what the raw sweeps are on disk (counts, suffixes, one frame's size and type),
#               so their reader is told the format before anything runs on them
# RUN is the run directory tools/flow.py made (RUN.json, train/best.pt); CATALOG the catalog it
# was trained from. Every output lands in the run directory: onnx/, latency/<arm>.json,
# evaluate/latency.json and sweep/<name>/. Nothing is downloaded; the node needs no internet.
set -euo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PART=${PART:?PART is gpu, cpu, sweep or probe}
THREADS=${THREADS:-8}
FRAMES=${FRAMES:-300}
cd "$REPO"
export PYTHONNOUSERSITE=1
echo "SN_LATENCY $PART start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-} task ${SLURM_ARRAY_TASK_ID:-} commit $(git rev-parse --short HEAD)"
py() { pixi run --locked -e "$1" python "${@:2}"; }

case "$PART" in
  probe)
    for case_ in ${CASES:-case134 case39}; do
      python3 - "${SWEEP_ROOT:-/rs/rs_grp_oschome/go2432/data/carmlspine/unpacked/C-ArmLSpine}" "$case_" <<'PY'
import collections, os, sys
root, case = sys.argv[1], sys.argv[2]
def mine(path):
    parts = os.path.relpath(path, root).split(os.sep)
    return any(p == case or p.startswith((case + "_", case + ".", case + "-")) for p in parts)
hits = [os.path.join(d, n) for d, _, names in os.walk(root) for n in names if mine(os.path.join(d, n))]
print(f"{case}: {len(hits)} files under {root}")
by = collections.Counter(os.path.splitext(h)[1].lower() for h in hits)
print("  suffixes:", dict(by.most_common()))
dirs = collections.Counter(os.path.dirname(h) for h in hits)
for d, n in dirs.most_common(8):
    print(f"  {n:6d}  {d}")
for h in sorted(hits)[:3]:
    print(f"  first: {h}  {os.path.getsize(h)} bytes")
PY
    done
    ;;
  gpu)
    : "${RUN:?RUN is the run directory}" "${CATALOG:?CATALOG is the run's catalog}"
    py train-gpu tools/latency.py export --run "$RUN"
    py train-gpu tools/latency.py parity --run "$RUN" --catalog "$CATALOG" --device cpu
    py train-gpu tools/latency.py parity --run "$RUN" --catalog "$CATALOG" --device cuda
    for runtime in torch onnxruntime; do
      py train-gpu tools/latency.py measure --run "$RUN" --catalog "$CATALOG" --runtime "$runtime" --device cuda --frames "$FRAMES"
    done
    ;;
  cpu)
    : "${RUN:?RUN is the run directory}" "${CATALOG:?CATALOG is the run's catalog}"
    for runtime in torch onnxruntime; do
      py train-cpu tools/latency.py measure --run "$RUN" --catalog "$CATALOG" --runtime "$runtime" --device cpu --threads "$THREADS" --frames "$FRAMES"
    done
    ;;
  sweep)
    : "${RUN:?RUN is the run directory}" "${SWEEPS:?SWEEPS lists name:frames:boxes}"
    read -r -a sweeps <<< "$SWEEPS"
    one=${sweeps[${SLURM_ARRAY_TASK_ID:-0}]}
    IFS=: read -r name frames boxes <<< "$one"
    py train-gpu tools/sweep.py run --run "$RUN" --frames "$frames" --boxes "$boxes" --name "$name" \
      --runtime onnxruntime --device cuda --box-source "${BOX_SOURCE:-truth}"
    ;;
  *) echo "PART must be gpu, cpu, sweep or probe, not $PART"; exit 64 ;;
esac
echo "SN_LATENCY $PART end $(date '+%F %T')"
