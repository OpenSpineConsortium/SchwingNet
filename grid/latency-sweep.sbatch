#!/bin/bash
#SBATCH --job-name=sn_latency
#SBATCH --partition=gmsap
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:30:00
#SBATCH --output=logs/%x_%A_%a.out
# The GPU is asked for on sbatch's command line (--gres=gpu:1), never here, so the probe and the
# CPU job, submitted from the same file, ask for none.
# Issue #13: one part of the latency, ONNX and sweep work on one run of the level stage, chosen by
# PART (and, for a sweep array, by SLURM_ARRAY_TASK_ID over SWEEPS). grid/run-latency-sweep.sh
# submits it four ways and says which; by hand:
#   PART=gpu    the ONNX export, its parity on validation crops (CPU and the GPU), then the frame
#               path's latency with PyTorch and with ONNX Runtime on this node's GPU
#   PART=cpu    the frame path's latency with PyTorch and ONNX Runtime on THREADS CPU threads,
#               after PART=gpu (it needs the export and its parity)
#   PART=sweep  one recorded sweep per array task: SWEEPS is "name:frames:boxes ..." or
#               "name:bank=<bank folder> ...", run through ONNX Runtime on the GPU with the overlay
#               recording
#   PART=probe  what the raw sweeps and the case134 export are on disk (counts, suffixes, sizes,
#               PNG dimensions, the export's meta keys and levels), never a DICOM header
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
    # Counts, suffixes, sizes and image dimensions only: the raw sweeps are DICOM whose headers
    # carry a real PatientID, so no header is ever read or printed here.
    python3 - "${SWEEP_ROOT:-/rs/rs_grp_oschome/go2432/data/carmlspine/unpacked/C-ArmLSpine}" \
      "${SWEEP_BANK:-/rs/rs_grp_oschome/go2432/data/realxray/carmlspine_sweep}" ${CASES:-case134 case39} <<'PY'
import collections, json, os, struct, sys
root, bank, cases = sys.argv[1], sys.argv[2], sys.argv[3:]
def files_under(top, case):
    out = []
    for d, _, names in os.walk(top):
        rel = os.path.relpath(d, top).split(os.sep)
        for n in names:
            if case in rel or n.startswith((case + "_", case + ".", case + "-")):
                out.append(os.path.join(d, n))
    return sorted(out)
def png_size(path):
    with open(path, "rb") as f:
        head = f.read(26)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height, depth, colour = struct.unpack(">IIBB", head[16:26])
    return f"{width}x{height}, {depth}-bit, colour type {colour}"
for case in cases:
    raw = files_under(root, case)
    print(f"raw {case}: {len(raw)} files under {root}")
    print("  suffixes:", dict(collections.Counter(os.path.splitext(h)[1].lower() or "(none)" for h in raw).most_common()))
    for d, n in collections.Counter(os.path.dirname(h) for h in raw).most_common(6):
        print(f"  {n:6d}  {d}")
    sizes = collections.Counter(os.path.getsize(h) for h in raw)
    print("  commonest sizes in bytes:", sizes.most_common(3))
    images = [h for h in files_under(os.path.join(bank, "images"), case) if h.endswith(".png")]
    print(f"bank {case}: {len(images)} PNG frames under {bank}/images")
    if images:
        print("  first:", os.path.basename(images[0]), png_size(images[0]), "| last:", os.path.basename(images[-1]))
        meta = os.path.join(bank, "meta", os.path.basename(images[0])[:-4] + ".json")
        if os.path.isfile(meta):
            with open(meta) as f:
                m = json.load(f)
            boxes = m.get("boxes", [])
            print("  meta keys:", sorted(m), "| view:", m.get("view"), "| boxes:", len(boxes),
                  "| box keys:", sorted(boxes[0]) if boxes else None, "| levels:", [b.get("level") for b in boxes])
        print("  frames with meta:", sum(os.path.isfile(os.path.join(bank, "meta", os.path.basename(i)[:-4] + ".json")) for i in images))
PY
    ;;
  gpu)
    # Each arm stands alone: a parity that fails stops that arm's timing (tools/latency.py refuses
    # it) and not the others'; the job exits 1 at the end when any step failed, and says which.
    : "${RUN:?RUN is the run directory}" "${CATALOG:?CATALOG is the run's catalog}"
    py train-gpu tools/latency.py export --run "$RUN"
    failed=""
    for arm in "onnxruntime cpu" "onnxruntime cuda" "torch cuda"; do
      set -- $arm
      py train-gpu tools/latency.py parity --run "$RUN" --catalog "$CATALOG" --runtime "$1" --device "$2" --threads "$THREADS" || failed="$failed parity-$1-$2"
    done
    for runtime in torch onnxruntime; do
      py train-gpu tools/latency.py measure --run "$RUN" --catalog "$CATALOG" --runtime "$runtime" --device cuda --frames "$FRAMES" || failed="$failed measure-$runtime-cuda"
    done
    [ -z "$failed" ] || { echo "SN_LATENCY gpu failed:$failed"; exit 1; }
    ;;
  cpu)
    : "${RUN:?RUN is the run directory}" "${CATALOG:?CATALOG is the run's catalog}"
    failed=""
    for runtime in torch onnxruntime; do
      py train-cpu tools/latency.py measure --run "$RUN" --catalog "$CATALOG" --runtime "$runtime" --device cpu --threads "$THREADS" --frames "$FRAMES" || failed="$failed measure-$runtime-cpu"
    done
    [ -z "$failed" ] || { echo "SN_LATENCY cpu failed:$failed"; exit 1; }
    ;;
  sweep)
    : "${RUN:?RUN is the run directory}" "${SWEEPS:?SWEEPS lists name:frames:boxes}"
    read -r -a sweeps <<< "$SWEEPS"
    one=${sweeps[${SLURM_ARRAY_TASK_ID:-0}]}
    IFS=: read -r name frames boxes <<< "$one"
    if [ "${frames#bank=}" != "$frames" ]; then
      # name:bank=<folder>: the case's frames and boxes from a bank in the builders' format
      input="$RUN/sweep-input/$name"
      py train-gpu tools/sweep.py from-bank --bank "${frames#bank=}" --case "$name" --out "$input"
      frames=$input/frames boxes=$input/boxes.jsonl
    fi
    py train-gpu tools/sweep.py run --run "$RUN" --frames "$frames" --boxes "$boxes" --name "$name" \
      --runtime "${SWEEP_RUNTIME:-onnxruntime}" --device cuda --box-source "${BOX_SOURCE:-truth}"
    ;;
  *) echo "PART must be gpu, cpu, sweep or probe, not $PART"; exit 64 ;;
esac
echo "SN_LATENCY $PART end $(date '+%F %T')"
