# Latency, ONNX parity and the recorded sweep (task #13)

Source: the thread "SchwingNet latency and ONNX", 2026-10-21, from the owner's list of 13:13 UTC (item 5, "Latency, ONNX and the recorded sweep (#13)") and issue #13; the plan is docs/research/demo-plan.md, sections 1 and W6, and docs/research/retraining-plan.md, section 5. Confidential, this repository only: nothing here is public until the provisional is filed, and the talk shows results, not methods.

## Where it stands

Built and measured on the synthetic-bank dry-run model in a cloud container, so it runs the moment the version 1 model exists on the grid. No grid job has run for it yet; the jobs are below. No number here says anything about SchwingNet on fluoroscopy: the model read synthetic crops and the CPU is the container's.

## What the code does

- `src/schwingnet/latency.py`, under the gate's contracts: a percentile is nearest rank, so every p95 a slide shows is a frame that was measured; the budget is one frame interval of C-ArmLSpine's sweeps, 1000 / 10.3 = 97.1 ms, written 97 ms, and "real-time" means the p95 is strictly under it; parity is every predicted level equal and every softmax probability within 1e-5 of PyTorch's, on at least one crop.
- `src/schwingnet/sweep.py`, under the same contracts: the causal tracker. A box joins the track it overlaps most (intersection over union at least 0.3, greedy, highest first, ties by index), the track's probabilities are a moving average with weight 0.5 on the new frame, a track unseen for three frames ends, and a track whose best level is under 0.5 shows "?". It reads only the frames so far, so the recording is what a live run would have shown.
- `tools/latency.py export | parity | measure`: the level stage to ONNX (opset 17, a variable batch axis, onnx's checker), parity on validation crops (never test crops) written to `onnx/parity.json` with the ONNX file's sha256, and the frame path timed one frame at a time: crop and resize every box, the forward pass, the softmax, the tracker's step, each part timed, the model resident and warmed up, acquisition and decode excluded as the plan's claim says. ONNX Runtime is refused unless parity passed for that same file. Each arm writes `latency/<arm>.json`; `evaluate/latency.json` holds the fastest arm whose parity holds, under the keys the evaluation page of #12 reads (`ms_per_frame_median`, `ms_per_frame_p95`, `frames`, `device`, `batch`).
- `tools/sweep.py run`: a recorded sweep (a folder of frames or a .npy stack, and one JSON line of boxes per frame) through the same frame path, deeper-than-8-bit frames windowed from the 1st to the 99th percentile inside the timed path; the overlay draws each track's box, level and probability or "?", and in the corner the frame counter, the gantry angle, this frame's compute time, the p95 so far against 97 ms, the run, the runtime and device, and where the boxes came from. It writes `overlay/`, `sweep.jsonl`, `summary.json` (latency, and where the boxes carry truth levels the accuracy with Wilson intervals overall, per 15 degrees of gantry angle, and frame alone with no tracker, so the summary says what the tracker added or cost), a contact sheet and `sweep.mp4` (ffmpeg) or `sweep.gif`. `tools/sweep.py synthetic` writes a sweep in that format from one person's catalog frames, for the tests and the dry run.
- `grid/run-latency-sweep.sh` and `grid/latency-sweep.sbatch`: below.

Version 1 has no detector stage, so a sweep's boxes are truth boxes and the overlay says "boxes: truth" on every frame; `--box-source detector` is for when a detector exists.

## The dry run (2026-10-21, container, 4 CPU cores)

Model: run 2553f50346d4, the level stage trained 3 epochs on a synthetic catalog (653 frames, commit e4d4964, from scratch). Files under `dry-run/`.

| what | value |
|---|---|
| ONNX export | opset 17, onnx 1.23.2, torch 2.14.1 |
| parity | 64 validation crops of 5 persons; max probability difference 1.9e-6; labels equal; passed |
| PyTorch, 4 threads | p50 17.7 ms, p95 26.0 ms per frame (300 frames, 3.6 boxes a frame); model 16.2 ms of it |
| ONNX Runtime, 4 threads | p50 9.4 ms, p95 14.6 ms; model 7.9 ms, crop 0.5 ms, tracker 0.9 ms |
| sweep (12 synthetic frames of case134) | p50 10.6 ms, p95 15.3 ms; overlay, contact sheet and MP4 written |

The synthetic sweep's frames are unrelated pictures, not a moving C-arm, so the tracker joins boxes that are not the same vertebra and lowers accuracy there (29/46 with the tracker against 38/46 frame alone); that is why the summary reports both, and the real sweeps decide whether the tracker stays at these settings. The contact sheet is `dry-run/sweep-contact.png`.

## The grid jobs

From the grid's shell, in the checkout (`cd ~/SchwingNet && git pull && pixi install --locked -e train-gpu && pixi install --locked -e train-cpu`):

1. The probe, now, needing nothing else: `bash grid/run-latency-sweep.sh --probe`. One job on reqp, 1 CPU, 2 GB, 10 minutes: for case134 and case39 under /rs/rs_grp_oschome/go2432/data/carmlspine/unpacked/C-ArmLSpine it lists how many files, their suffixes, the folders and the first files' sizes, so the sweep's reader is told the format (folder of images or a stack) before anything runs on it. The answer goes into this file.
2. Per model version, once the version 1 run exists: `bash grid/run-latency-sweep.sh --catalog <catalog.sqlite> <run dir> [<run dir> ...] [--sweep case134:<frames>:<boxes.jsonl> --sweep case39:<frames>:<boxes.jsonl>]`. Each run directory gets, in parallel with the others: a GPU job on gmsap (1 GPU, 8 CPUs, 32 GB, 1.5 h requested: export, parity on CPU and GPU, latency with PyTorch and ONNX Runtime on the H200), a CPU job after it on reqp with --qos=requeue (8 threads, 16 GB, 1 h: the plan's "CPU with 8 threads" arm), and an array of one GPU task per sweep after it (1.5 h requested each). Job ids go to grid/LAST_LATENCY.txt.

Resource estimate for one model version with both sweeps: 3 GPU jobs and 1 CPU job, at most 4.5 GPU-hours requested; expected use well under 1 GPU-hour (the export and parity take seconds, 330 timed frames take under a minute on a CPU here, and a sweep of 301 frames at 1024 x 1024 is bounded by writing 301 PNGs and one MP4, minutes). The onnxruntime CUDA build in the lock is 1.31.0 for CUDA 12.9; if the H200 nodes' driver is older, the GPU job's ONNX Runtime arm fails with a provider error and the PyTorch arm and the CPU job still stand.

What the sweeps still need, which is not in this repository: each sweep's frames in order and one line of boxes per frame (unit or pixel boxes, truth levels, gantry angle). docs/research/demo-plan.md, W4, says case134's export with corners exists in spine-program's 01_carm_level_detection and case39 needs poses (4 GPU shards); whoever holds them writes the boxes file in the format at the top of tools/sweep.py.

## Not done here

TensorRT and a browser player come after version 1 (issue #13). FP16 is not measured: it changes the outputs and would need its own parity and accuracy run. The four legacy models of the reported stack (docs/research/demo-plan.md, W6) are not timed here; version 1 has one stage, and each later stage is exported and gated the same way.
