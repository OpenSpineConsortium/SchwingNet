# Pre-registration: the latency word's network parts

Source: the thread "Require Metaflow for every grid DL job", 2026-10-29, on the owner's rule of 02:39 UTC that every deep learning job on the grid runs on the block-based Metaflow pipeline under a frozen PREREG with the CLAIM and REFORMS report enforced; the form is the Lab Recipe's (artifacts/the-lab-recipe-1t2gvp/index.md, "Pre-register and freeze"). Confidential with the rest of this repository.

Covers: gpu, cpu, sweep

This file is frozen. It writes down, in the Lab Recipe's seven parts, the design the latency word's three network parts are built to: docs/research/demo-plan.md, sections 1 and 2 (W6); docs/research/retraining-plan.md (version 2, the owner's words of 2026-10-20), section 5; docs/research/latency-and-sweep/README.md, sections "What the code does" and "The grid jobs"; and the docstrings of src/schwingnet/latency.py, src/schwingnet/sweep.py, tools/latency.py and tools/sweep.py, which state the rules the code holds a part to, all at commit 28f0387aaa0be8d72559742c822eeba1def7f4be. Those are the full text, and this file only restates them. The parts are gpu, cpu and sweep, each one job of grid/run-latency-sweep.sh, the sweep one task of its array per recorded sweep; the probe runs no network and is no part of this design. Where a part as built departs from them, DEVIATIONS.md beside this file says so, dated, with its reason.

No latency of a SchwingNet model on the grid had been measured when this file was frozen: the only grid job of the word, the probe (Slurm job 40697708, 2026-10-21), counts files and runs no network, and the README's dry run timed a model trained on the synthetic bank in a cloud container, which says nothing about SchwingNet on fluoroscopy and chose nothing here. No timing or sweep job has run, since each waits for the version 1 run.

## 1. The question

For one run directory of the level stage that has finished training, a version 1 run first: does every runtime the talk may show give the reference's outputs on the same crops, and how long does the frame path take per frame on each runtime and device, against the 97 ms budget of one frame of C-ArmLSpine's recorded sweeps; and what does the frame path show, frame by frame and causally, over a recorded C-arm sweep, with its latency and, where the sweep's boxes carry levels, its naming accuracy.

## 2. Population and inputs

- The run directory: one that tools/flow.py made and whose training finished (RUN.json, train/checkpoint.json and train/best.pt), refused otherwise, as grid/run-latency-sweep.sh refuses it before it submits; its checkpoint named by its sha256 in the launcher's key and in every parity file.
- The catalog: the one the run was trained from, named by its sha256 in the launcher's key.
- Parity crops: the validation part's labelled crops, never the test part's: the crops of the run's validation witness frames first and whole, then the part's other crops in the catalog's order, up to 64 (tools/latency.py parity).
- Timed frames: the test part's labelled frames, each once in the catalog's order and repeated as needed, read for their pixels and their boxes only, since no accuracy is computed from a timed frame; 30 frames of warm-up first and excluded, then 300 timed (tools/latency.py measure, FRAMES in the job).
- Sweeps: a recorded sweep given as a folder of frames and one JSON line of boxes per frame, or as a bank in the builders' format, which tools/sweep.py from-bank turns into that input; the first is C-ArmLSpine case134 from its export under the data root's realxray/carmlspine_sweep (301 frames of 1024 x 1024, 8-bit). Version 1 has no detector, so a sweep's boxes are truth boxes, and the overlay says so on every frame. case39 has no poses and so no boxes, and has no sweep here.
- The arms: PyTorch on the CPU in float32 is the reference. The gpu part checks the parity of ONNX Runtime on the CPU, ONNX Runtime on the GPU and PyTorch on the GPU against it, after exporting the checkpoint to ONNX (opset 17), and times PyTorch and ONNX Runtime on the GPU, an H200 on gmsap. The cpu part times PyTorch and ONNX Runtime on 8 CPU threads. A sweep runs through ONNX Runtime on the GPU unless the job names PyTorch.
- Exclusions: none beyond the split rule the catalog already holds. No test crop enters a parity check, and no frame of the test part is scored by these parts.

## 3. The measurements

- Parity, per arm, written to onnx/parity-<runtime>-<device>.json: whether every predicted level equals the reference's, the largest absolute difference of a softmax probability, the crops and persons it read, how many witness frames came first, and the checkpoint's and, for ONNX Runtime, the ONNX file's sha256.
- Latency, per arm whose parity holds, written to latency/<arm>.json: the per-frame compute of the frame path, every box cropped and resized, the forward pass, the softmax and the tracker's step, one frame at a time with the model resident and warmed up, acquisition, file read, decode and display excluded; p50, p95 and p99 by nearest rank, so every percentile is a frame that was measured; each part of the path timed; the device by name.
- The headline, evaluate/latency.json: the fastest arm by p95 whose parity holds when it is written.
- Per sweep, under sweep/<name>/: the overlay of every frame, sweep.jsonl, a contact sheet, the video, and summary.json with the frame path's latency over the sweep and, where the boxes carry levels, the naming accuracy over the truth boxes as correct of n with its 95 percent Wilson interval, overall, per 15 degrees of gantry angle and frame alone with no tracker.
- Every file stamped with the run id and the commit of RUN.json; each part's verdict and its lines in metaflow/latency-<part>.json in the run directory, with the Metaflow run and its page; and the run's CLAIM 2024 and REFORMS report (tools/report.py), checked by each part's end step.

## 4. The hypotheses and their bars

- Parity, the rule before any number: an arm holds parity where every predicted level equals the reference's and every softmax probability is within 1e-5 of it, on at least one validation crop, for this checkpoint and, for ONNX Runtime, this ONNX file. No latency is written or shown for an arm that does not hold it.
- The budget: 97 ms, one frame interval of C-ArmLSpine's sweeps at 10.3 frames per second, rounded down. An arm is called real-time only where its p95 is strictly under 97 ms; an arm at or over it is reported with its numbers and called not real-time. The budget decides the word a slide may use, never whether a part succeeded.
- The sweep's accuracy is description, with no bar: it is shown with its n and its interval, beside the frame-alone figure, so the tracker's effect is seen and not chosen.

## 5. What counts as failure

- A part that cannot run: a run directory that has not finished training, a word the flow does not take, or a part no frozen PREREG covers. The flow fails, or the launcher refuses it with exit 90, and no number of it is quoted.
- A tool that does not run to its end. A failed export or a failed conversion of a sweep's bank stops its part, and each tool after it is shown as "<tool>: NOT RUN, why: an earlier tool stopped the part". A failed parity or timing stops only its own arm and is shown as "<tool>: FAILED, exit <code>, why: <its last line>". Either makes the part's verdict 1.
- A rule that does not hold on the files the part leaves, checked by the flow's end step from the run directory alone, beside the tools' own refusals: "parity <runtime> on <device>: DOES NOT HOLD, why: ...", "<arm>: TIMED NOTHING, why: ...", "<arm>: A LATENCY WITHOUT PARITY, why: ...", "<arm>: NOT READ, why: ...", "headline: NONE, why: ...", "headline: NOT READ, why: ...", "sweep <name>: NOTHING RECORDED, why: ...", "sweep <name>: A LATENCY WITHOUT PARITY, why: ..." or "sweep <name>: NOT READ, why: ...". Any of them makes the part's verdict 1.
- The run's CLAIM 2024 and REFORMS report not current: the parts write nothing the report reads, so its report is the one the run's own end step left, and the lines are those of stage.claim_report, "<run>: NOT CURRENT as an earlier run wrote it, and not written anew; why: ...", "<run>: NOT WRITTEN at the end; why: ..." or "<run>: NOT CURRENT once written at the end; why: ...", each making the verdict 1; where when the Metaflow run began cannot be read, the report is held to the part as if the run's work were its own, and a stale one gives "<run>: NOT CURRENT as the run wrote it, so written anew; why: ..." with the verdict 1. A report made stale since by a change to tools/report.py or its inputs is written anew under the tool as it is now, with the line "<run>: written anew under the report tool as it is now, its work done before this run began; ...", and is no failure.
- A checkout that moved during a part: its files are not used, and the word runs the part again (grid/latency-sweep.sbatch).
- An arm that holds parity and is not real-time is no failure: it is a result.

## 6. The analysis plan

Parity is checked on the validation part, before any arm is timed; the test part's frames are only timed, never scored, so no choice here reads a test label. The headline is the fastest arm whose parity holds, by p95, ties by the arm's name; a slide quotes it with its device, its p50 and p95, "batch 1, models resident, excluding acquisition, decode and display", and the word real-time only under the bar of section 4. A sweep's accuracy is reported with its n and its Wilson interval, overall and per 15 degrees, never pooled with the test table of the run's evaluation and never used to choose the tracker's settings for the talk. FP16 and TensorRT change the outputs and are not measured here; each would be a design with its own parity and accuracy run, and its own PREREG. Each part's verdict is computed by flows/latency.py from its tools' exits, its files and its report, so no reader chooses it.

## 7. Freeze

Frozen on 2026-10-29 by the thread named above, from the commit named above, before any part ran under it: `sha256sum PREREG.md > PREREG.md.sha256` in this folder, both committed. No further edits: a departure goes in DEVIATIONS.md beside it, and a second design, an arm or a runtime this file does not name, is a new file with its own freeze.
