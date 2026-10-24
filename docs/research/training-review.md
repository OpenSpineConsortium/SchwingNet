# The level stage's training, reviewed, and where the end-to-end workflow stands

Source: the project thread "Improve SchwingNet training and review end-to-end status", 2026-10-24, from the owner's question of 03:08 UTC ("can i improve my model training portion of the code and an update on where the functionality of the end to end workflow stands"). Read from main at b9d63fd, the issues and pull requests of this repository, and the grid's last status answer (symphony-template's branch grid, logs/job-schwingnet-status.json, request room-after-191, 2026-10-24 02:17 UTC). Confidential, this repository only, as docs/project.md says.

No grid job, training or Claude run was started for this note. Every suggestion that would move a number waits for the owner's word; the two changes this thread made move none (part 3).

## 1. The training code, and what would improve it

The trainer is tools/train.py (430 lines): the level stage of docs/research/retraining-plan.md, section 3.4, a torchvision resnet18 with a 27-way head over 64 x 64 crops of the truth boxes, Adam at a fixed 1e-3, plain cross-entropy, one seed, every epoch's weights kept, the best epoch chosen on the whole validation part, witness frames drawn every epoch and W&B written offline. The record around it is strong: RUN.json before any step, a refused dirty tree, the split check, Wilson intervals on every number, the test part read once. The model side is the plain first version the owner asked for ("clearly don't do ensembles of models before training one to work"), and that is where the room is.

In order of what each is expected to buy, the first six change training results and wait for the owner's word; the rest do not.

### Changes that move results (proposed, not made)

1. **Train on the boxes it will be given.** Every crop is cut from an exact truth box with a fixed 15 percent pad (`PAD`, `crop_pixels`), but the demo's boxes come from a tracker and later a detector, which are never exact. A random jitter of each box's centre and size, a few percent of its height, is the one augmentation that matches a known shift between training and use. Beside it, intensity changes the C-arm actually makes: gamma and contrast, blur, and Poisson noise at fluoroscopic dose. Never a vertical flip or a large rotation, which change what cranial means. Today the trainer has no augmentation at all.
2. **Normalise the input the way the ImageNet weights expect.** With `--weights` the network starts from ImageNet, which was trained on inputs scaled by ImageNet's mean and spread per channel; here each crop is grey in 0..1, copied to three channels, with no normalisation. The first layers then see inputs off what they learned on. One line in `load_crops` (or a fixed first layer) fixes it; it changes every number, so it is a version change.
3. **A schedule and weight decay.** Adam at a constant 1e-3, no decay and no warm-up, is the setting most likely to make the curve jump. The synthetic dry run cd37124c487d shows it: validation 0.879, then 0.394, 0.462 and 0.996 while the training loss kept falling (docs/research/evaluation/README.md), the pattern of a step too large for the batch-norm statistics to follow. AdamW with weight decay, a short linear warm-up and a cosine decay, and when starting from ImageNet a smaller rate for the backbone than the new head, is the standard cure. The witness strips will show whether it holds on real frames.
4. **The rare levels.** The head names 27 levels; the data hold mostly L1 to L5, and the transitional levels (T13, L6) are the point of the work. Plain cross-entropy and plain accuracy let the common levels decide both the loss and the chosen checkpoint. Class-balanced sampling or loss weights, and a balanced accuracy (or the transitional stratum) logged beside accuracy and used to break ties, keep the rare levels from being traded away. The plan's oversampling of new shards at an incremental run (section 3.4) is the same idea.
5. **Context, not a crop alone.** One body at 64 pixels cannot tell L2 from L3 by itself; the record's largest error is a whole-column shift (src/schwingnet/chain.py's docstring, from demo-plan.md section 0.3). The counting prior fixes this at decode time. The model can be given it too: a wider crop holding the neighbours, or the frame's bodies in order as one sequence for a small sequence model over the crop features. This is a version 2 change, after version 1 has a real baseline.
6. **Crop size.** 64 pixels from a frame near 1024 is a strong reduction; 96 or 128 is worth one comparison on the validation witness frames once a real run exists. It is a `rebase` by the plan's word.

### Changes that keep every number (two made, the rest ready on the owner's word)

7. **Training that resumes (plan section 3.4) is not built.** The goal says a dataset is added by one incremental run with no epoch run twice, but tools/train.py has no `--init`, saves no optimiser or random state, and there is no `models/<stage>/<version>.json` registry. Saving the optimiser, the epoch and the random state with each epoch's weights, an `--init <parent checkpoint>` that the card and the record name as the parent, and the registry file would build it; a fresh run's numbers would not change. It is the largest gap between the code and the goal, and its design (what the parent record holds, how the run id names a parent) is the owner's to approve first.
8. **Decode each frame once.** `load_crops` decoded the whole frame again for every body on it, several times per frame. Made in this thread (part 3).
9. **Reproducible on the GPU.** `torch.use_deterministic_algorithms(True, warn_only=True)` only warns where cuBLAS is not deterministic, which it is not on CUDA unless `CUBLAS_WORKSPACE_CONFIG` is set before CUDA starts; so a grid run today is not repeatable to the bit, while the record says the same commit, catalog and seed reproduce it. Made in this thread (part 3).
10. **Memory.** Every crop is held three times, `repeat(1, 3, 1, 1)` copying the grey channel; at 100,000 crops of 64 pixels that is about 4.9 GB where 1.6 GB would do. Expanding to three channels at batch time removes it; the tools that call `load_crops` (evaluate, latency, chain_eval) expect three real channels, so it is a small change across four files, worth making when the real catalog grows.
11. **Speed on the H200s.** Mixed precision (bfloat16) and channels-last memory would cut the time per epoch; they change the last digits, so they belong with a version change, not before.
12. **What the card records.** The learning rate, the device's name and the torch and CUDA versions belong in metrics.jsonl and MODEL.md beside the seed, so a reader sees what made the numbers.

## 2. Where the end-to-end workflow stands

The goal (docs/project.md): level naming on intraoperative fluoroscopy, video or frames, low latency and high accuracy, every number reproduced from a record here, a recorded C-arm sweep with overlay and measured latency for the talk of 2 November.

| Stage | State | Evidence |
|---|---|---|
| Datasets onto the grid | Working at scale | 14,063 GB under the data root across about 100 sources; the sample census of 7,008,826 files (docs/research/data-manifest/MANIFEST.md); the size rule counts every quota on the path since #191 |
| Ingest into shards, the versioned catalog, the person-keyed split and its check | Working | tools/ingest.py, tools/catalog.py; grid jobs 40702196 (C-ArmLSpine ingest, 45 s) and 40702197 (catalog, 11 s), both completed 2026-10-22; #79, the ingest reading the view tag and kVp, is claimed and in review with no pull request open |
| Training, the level stage over truth boxes | Ran once on real frames, on a small labelled set | Run e4f7054848f5, grid job 40702198 (v1_driver), 5 min 16 s on one GPU, commit 8116aae, catalog 1 252ba19562cf; the test part scored 21/21 crops from 4 persons (#138). 21 crops cannot carry a claim: its Wilson interval runs from about 0.85 to 1. Inferred, not read: the run that short trained on few labelled C-ArmLSpine frames, since the census counts 8,180 annotated of 59,609 C-ArmLSpine DICOM images and 297 annotated in the PNG export |
| The run's record in this repository | Not done | docs/research/v1-demo/runs/ holds only the two synthetic dry runs; `tools/flow.py record --freeze` was never run for e4f7054848f5, so the evaluation page shows no real run and data/witness/ (the frozen witness frames) does not exist |
| Detector stage | Not built | Every result row says "over truth boxes"; tools/sweep.py takes `--box-source detector` for when one exists |
| Counting prior (CT spacing and counts at decode time) | Code built, not run | src/schwingnet/chain.py, tools/chain_stats.py, tools/chain_eval.py; its grid words wait in pull request #73 (issue #72), then one CPU job on the segmented CTs |
| Latency, ONNX parity, the recorded sweep | Code built and dry-run; grid jobs stuck | tools/latency.py, tools/sweep.py, docs/research/latency-and-sweep/README.md; jobs 40702515 (GPU), 40702516 (CPU) and 40702517 (sweep) for run e4f7054848f5 were still PENDING with no node at 2026-10-24 02:17 UTC, about 46 hours after they were sent; the status word does not print Slurm's pending reason yet (#138's follow-up) |
| Evaluation page and W&B | Working on the dry runs | docs/research/evaluation/README.md, written by tools/eval_page.py; the real run's W&B state is not in the record |
| The patient's own preoperative CT at the operation | No code path | CT enters only as a population prior (the counting prior) and as a source of renders (#59, #69, #70, all todo); no tool registers a patient's CT to their C-arm frames (#127, gold masks on paired CT and X-ray, todo) |

So today the chain runs from datasets to a trained level classifier with a scored test part, on truth boxes, with the record and the page proved on synthetic data. A frame taken off a C-arm cannot yet be named end to end, since no detector supplies the boxes, and the real run is neither recorded nor large enough to quote.

### What is next, in order

1. Read why the three latency jobs wait (`squeue -j 40702515 -o %r`, or the status word once it prints the reason) and fix the request, or cancel and resend on the owner's word.
2. Record run e4f7054848f5 here (`tools/flow.py record --freeze` on the grid, its small files by pull request), so the page shows the first real run and the witness frames freeze.
3. Count the labelled C-ArmLSpine crops the catalog actually holds per part, and decide on the owner's word whether version 1 is retrained on more labelled data before the talk.
4. The training changes of part 1 that the owner approves, as one `rebase` run, compared on the frozen witness frames.
5. The counting prior's grid words (#73) and its one CPU job, then tools/chain_eval.py on the run.
6. A detector, or the sweep shown on truth boxes and said so, which the demo plan already allows.

## 3. What this thread changed

- Pull request 1: `load_crops` decodes each frame once for its run of bodies, keeping only the last frame, with tests/test_train_crops.py holding its output to the per-body crop exactly, frames in order and shuffled; it ran with tests/test_latency_tools.py (17 tests) in a torch 2.14.1 CPU environment.
- Pull request 2: `seed_everything` sets `CUBLAS_WORKSPACE_CONFIG` before CUDA starts, so the deterministic setting holds on the GPU too; on the CPU nothing changes.
