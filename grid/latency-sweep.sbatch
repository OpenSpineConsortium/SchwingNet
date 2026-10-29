#!/bin/bash
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:30:00
# grid/run-latency-sweep.sh queues it through hpcworker's job submit (grid/hpcw.sh, issue #77): the
# probe and the CPU job as the batch class, the GPU job and the sweeps as the gpu class on gmsap,
# whose QoS and GPU the site profile gives; the header holds only what every part needs at most.
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
#
# The three parts that run the network are launched flows, as every deep learning job on the grid
# is (the owner's rule of 2026-10-29, flows/registry.txt): each job, and each task of the sweep
# array, starts its own run of flows/launch.py latency with its part and the run directory, which
# refuses it with exit 90 unless docs/research/latency-and-sweep/PREREG.md is the one frozen and
# covers the part, resumes the newest run of the same words, code, checkpoint, catalog and sweep
# input that did not finish, and whose LatencyFlow runs the same tools in the same order as this
# script did, checks the parity rule again from the run directory's files, checks the run's CLAIM
# 2024 and REFORMS report and draws the run's progress page under the datastore's progress/ folder.
# The job's exit is the launcher's: the flow's verdict, 0 only where the part ran to its end, its
# parity rule held and the report is current. The probe runs no network and stays as it was.
# Each network part's report is logs/latency-<part>-STAGE-REPORT.md (latency-sweep-<task>- for a
# sweep task): the run directory, the GPU, the launcher's decision, the flow's checks, the
# Metaflow run and the launcher's exit.
set -euo pipefail
REPO=${SCHWINGNET:-$HOME/SchwingNet}
PART=${PART:?PART is gpu, cpu, sweep or probe}
THREADS=${THREADS:-8}
FRAMES=${FRAMES:-300}
cd "$REPO"
export PYTHONNOUSERSITE=1
echo "SN_LATENCY $PART start $(date '+%F %T') on $(hostname) job ${SLURM_JOB_ID:-} task ${SLURM_ARRAY_TASK_ID:-} commit $(git rev-parse --short HEAD)"

# The launcher's words for a network part, and the environment its python comes from: train-gpu
# on the GPU, train-cpu for the CPU arms, as each tool ran before.
env=train-gpu label=$PART words=()
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
  gpu|cpu)
    : "${RUN:?RUN is the run directory}" "${CATALOG:?CATALOG is the catalog the run was trained from}"
    [ "$PART" = gpu ] || env=train-cpu
    words=(--part "$PART" --run-dir "$RUN" --catalog "$CATALOG" --threads "$THREADS" --frames "$FRAMES")
    ;;
  sweep)
    : "${RUN:?RUN is the run directory}" "${SWEEPS:?SWEEPS lists name:frames:boxes}"
    read -r -a sweeps <<< "$SWEEPS"
    one=${sweeps[${SLURM_ARRAY_TASK_ID:-0}]}
    label=sweep-${SLURM_ARRAY_TASK_ID:-0}
    words=(--part sweep --run-dir "$RUN" --sweep "$one" --sweep-runtime "${SWEEP_RUNTIME:-onnxruntime}"
           --box-source "${BOX_SOURCE:-truth}")
    ;;
  *) echo "PART must be gpu, cpu, sweep or probe, not $PART"; exit 64 ;;
esac
if [ "$PART" = probe ]; then
  echo "SN_LATENCY $PART end $(date '+%F %T')"
  exit 0
fi

mkdir -p "$REPO/grid/logs"
REPORT=$REPO/grid/logs/latency-$label-STAGE-REPORT.md
report() { echo "- $*" | tee -a "$REPORT"; }
echo "# Latency $label: $(date '+%F %T'), job ${SLURM_JOB_ID:-none} on $(hostname), commit $(git rev-parse --short HEAD 2>/dev/null)" > "$REPORT"
report "run directory: $RUN"
[ "$PART" != sweep ] || report "sweep: ${one%%:*}"
[ "$env" != train-gpu ] || report "GPU: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | head -n 1 || echo 'nvidia-smi gave nothing')"
out=$(mktemp "$REPO/grid/logs/latency-flow-${SLURM_JOB_ID:-$$}${SLURM_ARRAY_TASK_ID:+-$SLURM_ARRAY_TASK_ID}.XXXXXX")
started_at=$(git rev-parse HEAD 2>/dev/null || true)
# The Metaflow datastore is the launcher's default on the grid; the paths are absolute, as
# grid/run-latency-sweep.sh passes them, so the flow's steps read them wherever Metaflow runs them.
# The launcher runs in the background and is waited on, as grid/sweep-driver.sbatch's is, so job
# submit's TERM two minutes before the limit, or a person's INT, is heard at once: a shell holds a
# trapped signal while a command runs in its foreground. The trap passes TERM on to the launcher,
# which passes it to every process of its flow, closes the run's page and exits 143, and the
# pipeline is waited on again; tee ignores both signals, so the launcher's last lines reach $out.
# set -e would end the wait's subshell at the launcher's own failing exit before it is written down,
# so from here every exit is read and reported rather than raised.
set +e
launcher_pid=$(mktemp) launcher_rc=$(mktemp)
stopped="" signalled=""
stop_launcher() {
  local pid
  stopped=1 signalled=1
  pid=$(cat "$launcher_pid" 2>/dev/null)
  [ -z "$pid" ] || kill -TERM "$pid" 2>/dev/null
}
trap stop_launcher TERM INT
{
  pixi run --locked -e "$env" python flows/launch.py latency --max-workers 1 -- "${words[@]}" &
  echo "$!" > "$launcher_pid"
  wait "$!"
  echo "$?" > "$launcher_rc"
} 2>&1 | (trap '' TERM INT; exec tee "$out") &
piped=$!
again=1
while [ -n "$again" ]; do
  signalled=""
  wait "$piped"
  again=$signalled
done
trap 'exit 143' TERM
trap - INT
rc=$(cat "$launcher_rc" 2>/dev/null)
# No status where the launcher's own shell was killed, which only Slurm's TERM to the whole job does.
[ -n "$rc" ] || { [ -n "$stopped" ] && rc=143 || rc=1; }
rm -f "$launcher_pid" "$launcher_rc"
decision=$(grep -m 1 '"decision":' "$out")
report "launcher: ${decision:-it printed no decision line}"
grep -h 'LatencyFlow: end: ' "$out" | while IFS= read -r line; do report "${line#*LatencyFlow: end: }"; done
run=$(grep '"successful":' "$out" | tail -n 1)
report "Metaflow: ${run:-the launcher named no run}"
report "launcher exited $rc"
ended_at=$(git rev-parse HEAD 2>/dev/null)
if [ "$ended_at" != "$started_at" ]; then
  report "FAILED: the checkout moved from ${started_at:0:7} to ${ended_at:0:7} during the part, so a tool may have run the newer code while the launcher's key names the older; these files are not used, and the word runs the part again"
  [ "$rc" != 0 ] || rc=3
fi
echo "SN_LATENCY $PART end $(date '+%F %T')"
echo "SN_LATENCY_RC=$rc"
exit "$rc"
