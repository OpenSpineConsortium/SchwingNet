#!/bin/bash
# Submit issue #13's grid jobs for one or more runs of the level stage, each run's jobs side by side
# (the login node runs nothing but sbatch and this script):
#   probe   reqp, 10 minutes, no GPU: what the raw case134 and case39 sweeps are on disk
#   gpu     gmsap, 1 GPU: ONNX export, parity on CPU and GPU, latency PyTorch and ONNX Runtime on the GPU
#   cpu     reqp --qos=requeue, 8 threads: latency PyTorch and ONNX Runtime on CPU (afterok:gpu)
#   sweep   gmsap, 1 GPU each, an array of one task per sweep given (afterok:gpu)
#
#   bash grid/run-latency-sweep.sh --probe
#   bash grid/run-latency-sweep.sh --catalog <catalog.sqlite> <run dir> [<run dir> ...] \
#        [--sweep case134:<frames>:<boxes.jsonl> --sweep case39:<frames>:<boxes.jsonl>]
#   SBATCH=<a fake that prints a number> bash grid/run-latency-sweep.sh ...   # a dry run, as the test does
#
# Several run directories submit one set each, in parallel: latency is per model version. A sweep
# is submitted only where its frames and boxes are given, since version 1 has no detector and its
# boxes are the sweep's truth boxes, written by whoever holds them (docs/research/latency-and-sweep.md).
# Job ids go to grid/LAST_LATENCY.txt and the logs to grid/logs/.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
SBATCH=${SBATCH:-sbatch}
CATALOG=""; PROBE=0; RUNS=(); SWEEPS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --probe) PROBE=1; shift ;;
    --catalog) CATALOG=$2; shift 2 ;;
    --sweep) SWEEPS+=("$2"); shift 2 ;;
    -*) echo "unknown argument $1"; exit 64 ;;
    *) RUNS+=("$1"); shift ;;
  esac
done
cd "$REPO/grid" || { echo "no $REPO/grid: is SCHWINGNET the checkout?"; exit 2; }
mkdir -p logs
out=LAST_LATENCY.txt
: > "$out"
submit() { # name, then sbatch's arguments; prints and records the job id
  local name=$1; shift
  local said id
  said=$("$SBATCH" --parsable "$@") || { echo "$name: sbatch refused"; return 1; }
  id=${said%%;*}
  echo "$name $id" | tee -a "$out" >&2
  printf '%s' "$id"
}
if [ "$PROBE" = 1 ]; then
  submit probe --partition=reqp --qos=requeue --gres=none --cpus-per-task=1 --mem=2G --time=00:10:00 \
    --job-name=sn_probe --export=ALL,PART=probe,SCHWINGNET="$REPO" latency-sweep.sbatch >/dev/null || exit 1
fi
if [ ${#RUNS[@]} -gt 0 ] && [ -z "$CATALOG" ]; then echo "--catalog names the runs' catalog"; exit 64; fi
for run in "${RUNS[@]}"; do
  [ -f "$run/RUN.json" ] && [ -f "$run/train/best.pt" ] || { echo "$run: no RUN.json and train/best.pt"; exit 2; }
  common="ALL,SCHWINGNET=$REPO,RUN=$run,CATALOG=$CATALOG"
  gpu=$(submit "gpu $run" --export="$common,PART=gpu" latency-sweep.sbatch) || exit 1
  submit "cpu $run" --dependency=afterok:"$gpu" --partition=reqp --qos=requeue --gres=none --cpus-per-task=8 \
    --mem=16G --time=01:00:00 --export="$common,PART=cpu,THREADS=8" latency-sweep.sbatch >/dev/null || exit 1
  if [ ${#SWEEPS[@]} -gt 0 ]; then
    submit "sweep $run" --dependency=afterok:"$gpu" --array=0-$(( ${#SWEEPS[@]} - 1 )) \
      --export="$common,PART=sweep,SWEEPS=${SWEEPS[*]}" latency-sweep.sbatch >/dev/null || exit 1
  fi
done
echo "job ids in grid/$out; squeue -u \$USER watches them"
