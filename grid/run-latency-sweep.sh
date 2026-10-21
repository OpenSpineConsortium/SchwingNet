#!/bin/bash
# Submit issue #13's grid jobs for one or more runs of the level stage, each run's jobs side by side
# (the login node runs nothing but sbatch and this script):
#   probe   reqp, 10 minutes, no GPU: what the raw case134 and case39 sweeps are on disk
#   gpu     gmsap, 1 GPU: ONNX export, parity of each arm against PyTorch on the CPU, latency PyTorch
#           and ONNX Runtime on the GPU
#   cpu     reqp --qos=requeue, 8 threads: latency PyTorch and ONNX Runtime on CPU (afterany:gpu)
#   sweep   gmsap, 1 GPU each, an array of one task per sweep given (afterany:gpu)
#
#   bash grid/run-latency-sweep.sh --probe
#   bash grid/run-latency-sweep.sh --catalog <catalog.sqlite> <run dir> [<run dir> ...] \
#        [--sweep case134:bank=/rs/rs_grp_oschome/go2432/data/realxray/carmlspine_sweep]
#        [--sweep <name>:<frames>:<boxes.jsonl>]
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
# Paths are made absolute before the cd below, since the jobs start in the checkout; a comma would
# split sbatch's --export and a colon a sweep's name:frames:boxes, so either is refused.
plain() { case "$1" in *,*|*:*) echo "$1: a path with a comma or a colon cannot be passed to the jobs"; exit 64 ;; esac; }
absolute() { plain "$1"; [ -e "$1" ] || { echo "$1: not there"; exit 2; }; (cd "$(dirname "$1")" && printf '%s/%s' "$(pwd -P)" "$(basename "$1")"); }
[ -n "$CATALOG" ] && CATALOG=$(absolute "$CATALOG")
for i in "${!RUNS[@]}"; do RUNS[$i]=$(absolute "${RUNS[$i]}") || exit $?; done
for one in "${SWEEPS[@]}"; do
  colons=${one//[^:]/}
  [ ${#colons} -le 2 ] || { echo "$one: name:frames:boxes or name:bank=<folder>, with no other colon"; exit 64; }
  case "$one" in *,*) echo "$one: a comma cannot be passed to the jobs"; exit 64 ;; esac
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
  submit probe --partition=reqp --qos=requeue --cpus-per-task=1 --mem=2G --time=00:10:00 \
    --job-name=sn_probe --export=ALL,PART=probe,SCHWINGNET="$REPO" latency-sweep.sbatch >/dev/null || exit 1
fi
if [ ${#RUNS[@]} -gt 0 ] && [ -z "$CATALOG" ]; then echo "--catalog names the runs' catalog"; exit 64; fi
for run in "${RUNS[@]}"; do
  [ -f "$run/RUN.json" ] && [ -f "$run/train/best.pt" ] || { echo "$run: no RUN.json and train/best.pt"; exit 2; }
  common="ALL,SCHWINGNET=$REPO,RUN=$run,CATALOG=$CATALOG"
  gpu=$(submit "gpu $run" --gres=gpu:1 --export="$common,PART=gpu" latency-sweep.sbatch) || exit 1
  # afterany: the CPU arms and the sweeps need only the export, and each refuses an arm whose
  # parity did not pass, so a failed GPU arm never holds them back
  submit "cpu $run" --dependency=afterany:"$gpu" --partition=reqp --qos=requeue --cpus-per-task=8 \
    --mem=16G --time=01:00:00 --export="$common,PART=cpu,THREADS=8" latency-sweep.sbatch >/dev/null || exit 1
  if [ ${#SWEEPS[@]} -gt 0 ]; then
    submit "sweep $run" --dependency=afterany:"$gpu" --gres=gpu:1 --array=0-$(( ${#SWEEPS[@]} - 1 )) \
      --export="$common,PART=sweep,SWEEPS=${SWEEPS[*]}" latency-sweep.sbatch >/dev/null || exit 1
  fi
done
echo "job ids in grid/$out; squeue -u \$USER watches them"
