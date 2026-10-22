#!/bin/bash
# Submit issue #13's grid jobs for one or more runs of the level stage, each run's jobs side by side
# through hpcworker's job submit (grid/hpcw.sh; the login node runs nothing but hpcworker and this
# script), each job a class whose partitions and QoS the site profile gives:
#   probe   batch, 10 minutes, no GPU: what the raw case134 and case39 sweeps are on disk
#   gpu     gpu on gmsap, 1 GPU: ONNX export, parity of each arm against PyTorch on the CPU,
#           latency PyTorch and ONNX Runtime on the GPU
#   cpu     batch, 8 threads: latency PyTorch and ONNX Runtime on CPU (afterany:gpu)
#   sweep   gpu on gmsap, 1 GPU each, an array of one task per sweep given (afterany:gpu)
#
#   bash grid/run-latency-sweep.sh --probe
#   bash grid/run-latency-sweep.sh --catalog <catalog.sqlite> <run dir> [<run dir> ...] \
#        [--sweep case134:bank=/rs/rs_grp_oschome/go2432/data/realxray/carmlspine_sweep]
#        [--sweep <name>:<frames>:<boxes.jsonl>]
#   HPCW_DRY=1 bash grid/run-latency-sweep.sh ...   # a dry run: print the submissions
#
# Several run directories submit one set each, in parallel: latency is per model version. A sweep
# is submitted only where its frames and boxes are given, since version 1 has no detector and its
# boxes are the sweep's truth boxes, written by whoever holds them (docs/research/latency-and-sweep.md).
# Job ids go to grid/LAST_LATENCY.txt and each job's output to hpcworker's log folder for the project.
set -uo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
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
# Paths are made absolute before the cd below, since the jobs start in the checkout; a comma once
# split sbatch's --export and a colon splits a sweep's name:frames:boxes, so either is refused.
# Their refusals go to stderr, since absolute runs inside $(...), where stdout is the path.
plain() { case "$1" in *,*|*:*) echo "$1: a path with a comma or a colon cannot be passed to the jobs" >&2; exit 64 ;; esac; }
absolute() { plain "$1"; [ -e "$1" ] || { echo "$1: not there" >&2; exit 2; }; (cd "$(dirname "$1")" && printf '%s/%s' "$(pwd -P)" "$(basename "$1")"); }
[ -n "$CATALOG" ] && CATALOG=$(absolute "$CATALOG")
for i in "${!RUNS[@]}"; do RUNS[$i]=$(absolute "${RUNS[$i]}") || exit $?; done
for one in ${SWEEPS[@]+"${SWEEPS[@]}"}; do
  colons=${one//[^:]/}
  [ ${#colons} -le 2 ] || { echo "$one: name:frames:boxes or name:bank=<folder>, with no other colon"; exit 64; }
  case "$one" in *,*) echo "$one: a comma cannot be passed to the jobs"; exit 64 ;; esac
done
cd "$REPO/grid" || { echo "no $REPO/grid: is SCHWINGNET the checkout?"; exit 2; }
mkdir -p logs
out=LAST_LATENCY.txt
# A GPU job is job submit's gpu class, whose QoS and GPU request the site profile gives (issue #74:
# a GPU partition with no QoS was refused). The partition is narrowed to gmsap, not the class's
# three, since the retraining plan measures latency on the H200 (docs/research/retraining-plan.md,
# item 4) and gmsap holds the H200 nodes; each latency record still names the GPU it ran on
# (tools/latency.py, "device").
H200=(--partition gmsap)
: > "$out"
# shellcheck source=grid/hpcw.sh
. "$REPO/grid/hpcw.sh"
submit() { # submit LABEL NAME CLASS [K=V...] [job submit options...]: prints and records the job id
  local label=$1 id
  shift
  id=$(hpcw_submit "$@") || { echo "$label: hpcworker refused"; return 1; }
  echo "$label $id" | tee -a "$out" >&2
  printf '%s' "$id"
}
if [ "$PROBE" = 1 ]; then
  submit probe latency_probe batch PART=probe SCHWINGNET="$REPO" --cpus 1 --mem 2G --time 00:10:00 \
    -- latency-sweep.sbatch >/dev/null || exit 1
fi
if [ ${#RUNS[@]} -gt 0 ] && [ -z "$CATALOG" ]; then echo "--catalog names the runs' catalog"; exit 64; fi
for run in ${RUNS[@]+"${RUNS[@]}"}; do
  [ -f "$run/RUN.json" ] && [ -f "$run/train/checkpoint.json" ] && [ -f "$run/train/best.pt" ] || { echo "$run: has not finished training (no RUN.json, train/checkpoint.json or train/best.pt)" >&2; exit 2; }
  common=(SCHWINGNET="$REPO" RUN="$run" CATALOG="$CATALOG")
  gpu=$(submit "gpu $run" latency_gpu gpu "${common[@]}" PART=gpu "${H200[@]}" -- latency-sweep.sbatch) || exit 1
  # afterany: the CPU arms and the sweeps need only the export, and each refuses an arm whose
  # parity did not pass, so a failed GPU arm never holds them back
  submit "cpu $run" latency_cpu batch "${common[@]}" PART=cpu THREADS=8 --after "$gpu:any" --cpus 8 \
    --mem 16G --time 01:00:00 -- latency-sweep.sbatch >/dev/null || exit 1
  if [ ${#SWEEPS[@]} -gt 0 ]; then
    submit "sweep $run" latency_sweep gpu "${common[@]}" PART=sweep SWEEPS="${SWEEPS[*]}" --after "$gpu:any" \
      "${H200[@]}" --array "0-$(( ${#SWEEPS[@]} - 1 ))" -- latency-sweep.sbatch >/dev/null || exit 1
  fi
done
echo "job ids in grid/$out; the gate word status follows them"
