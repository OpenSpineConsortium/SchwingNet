# Pre-registration: the version 1 run on real frames

Source: the thread "Require Metaflow for every grid DL job", 2026-10-29, on the owner's rule of 02:39 UTC that every deep learning job on the grid runs on the block-based Metaflow pipeline under a frozen PREREG with the CLAIM and REFORMS report enforced; the form is the Lab Recipe's (artifacts/the-lab-recipe-1t2gvp/index.md, "Pre-register and freeze"). Confidential with the rest of this repository.

This file is frozen. It writes down, in the Lab Recipe's seven parts, the design the version 1 run was built to: docs/research/retraining-plan.md (version 2, the owner's words of 2026-10-20), sections 0, 1, 3.3, 3.4 and 4; docs/research/v1-demo/README.md, sections "The workflow" and "The grid run"; and the docstrings of tools/train.py and tools/evaluate.py, which state the rules the code holds a run to, all at commit 35a4b6f37e591470865f58cf80bf86254f50d011. Those are the full text, and this file only restates them. Where the run as built departs from the plan, DEVIATIONS.md beside this file says so, dated, with its reason; every later departure goes there too.

One number of a real run was read before this freeze: run e4f7054848f5 (grid job 40702198, commit 8116aae, catalog 1), whose test part scored 21 of 21 crops from 4 persons (docs/research/training-review.md, section 2). Under spine-program's rule 6 that number is calibration, never a result, and it chose nothing in this file.

## 1. The question

How accurately does version 1 of SchwingNet's level stage, one ResNet-18 classifier trained once from ImageNet weights on the C-ArmLSpine frames the catalog holds, name each vertebral body on held-out real fluoroscopy, per level, per source and in the transitional stratum, over the truth boxes; the first row of the table every later version is measured against.

## 2. Population and inputs

- The catalog: the version grid/v1-version.sh chooses (sha256 94c79afd2930743fcacbb3ed52c129928c0b9e6364d4d6091490376105d657dd at the commit above), the newest line of VERSIONS.jsonl that holds both of C-ArmLSpine's parts, train and test, and every C-ArmLSpine shard at the head of its chain, with a split-check marker naming the test persons and the rule as they are now; split-checked again in the job before any frame is read (grid/v1-driver.sbatch). The run names the chosen file by its sha256 in RUN.json.
- The test persons: data/splits/test-persons.json (sha256 4c57462fb8d4fa4591fb73d10e506957b5f00f66c25c2e7f07731f2f073cb59d) under the split rule data/splits/rule.json (sha256 4f26dbc75ea43b3cb8605204b343e6144f9e99b027654e6f126158e4ba3634c3): the frozen list, extended only by a pull request; every other person falls to train or validation by the salted hash of its person key (plan, section 3.3).
- The weights: the ImageNet ResNet-18 file resnet18-f37072fd.pth, named in the run's configuration by its sha256 (plan, section 3.4: the first version 1 is a rebase from declared public weights).
- The configuration, as grid/v1-driver.sbatch gives it to tools/flow.py: the level stage, 20 epochs, seed 1, crops of 64 pixels, every crop (no --max-frames), no block named, which is version 1's training (src/schwingnet/blocks.py), the train-gpu environment, one GPU.
- Exclusions: none beyond the split rule. The test part is never read by the trainer; FluoroCap and the leaked banks are in no catalog shard (plan, section 3.2).

## 3. The measurements

- Per epoch, epoch 0 the untrained network included: the training loss and the validation accuracy with its interval, per level, per source and for the transitional stratum, in train/metrics.jsonl; the validation witness frames drawn whole (tools/train.py).
- The kept checkpoint: the epoch with the best accuracy on the whole validation part, never on the witness frames alone and never epoch 0 (tools/train.py).
- On the test part, read once after training (tools/evaluate.py): naming accuracy over the truth boxes as correct of n, with its 95 percent Wilson interval and the persons behind it, over all levels, per level and per source, the transitional stratum (T13, L6) apart and never pooled; the confusion matrix; the test witness frames drawn over every kept epoch, which choose nothing.
- Every number stamped with the run id, the commit, the clean-tree flag and the catalog's sha256 (RUN.json), and the run's CLAIM 2024 and REFORMS report (tools/report.py), written after its last step and checked by the flow's end step.

## 4. The hypotheses and their bars

None is tested, as the owner chose on 2026-10-29 at 03:23 UTC, asked whether version 1 and the experiments are pre-registered as estimates with no accuracy bar since no file sets one. Version 1 is the first model this workflow trains to work, and what it measures is the baseline every later version is measured against on the same frozen test persons (plan, section 0); the plan sets no accuracy bar for it, no published value applies, since the owner set the comparison with the reported stack aside (plan, section 0), and no power calculation was made. Its numbers are estimates, each with its interval and its n. The one numeric bar the plan holds, 97 ms a frame end to end (section 5), is the latency word's, under a pre-registration of its own.

## 5. What counts as failure

- The run cannot be run or recorded: a dirty tree, a split that is not disjoint, a catalog or weights file whose bytes are not the ones the record names, or a step that exits other than 0 once retried. The flow fails, the launcher exits other than 0, and the run's progress page shows the step that failed with its last line, "tools/flow.py run exited <code>: <its last line>" where tools/flow.py failed; no number of it is quoted.
- tools/flow.py ended without finishing the run: the verdict is 1, with the line "<run>: no FINISHED.json, so tools/flow.py did not finish the run" on the page.
- The run's CLAIM 2024 and REFORMS report, as tools/flow.py left it, is not what the run's files give, or cannot be written or does not check once written: the verdict is 1, with one of these lines on the page: "<run>: NOT CURRENT as the run wrote it, so written anew; why: <the check's words>", "<run>: NOT CURRENT as the run wrote it, and not written anew; why: <the check's words>", "<run>: NOT WRITTEN at the end; why: <the tool's words>" or "<run>: NOT CURRENT once written at the end; why: <the check's words>". A stale report is written anew where the tool can write it, so the folder holds the current one; the verdict stays 1.
- A stale report of work done before this Metaflow run began, a run resumed after tools/flow.py had finished, is no failure: it says only that tools/report.py or its inputs changed since, which no key names. It is written anew with the line "<run>: written anew under the report tool as it is now, its work done before this run began; <its counts>; it was not current, why: <the check's words>".
- A checkout that moved during the run: the run is not used and runs again (grid/v1-driver.sbatch).
- An item the report counts as missing is shown and is not a failure of the run; `tools/report.py check --complete` stays the gate before any number is published (docs/research/run-report.md).

## 6. The analysis plan

The checkpoint is chosen on the validation part before the test part is read; the test part is read once, by the evaluator, after training is over, and the test witness frames are drawn at that version boundary and choose nothing, since selection on test persons counts as seeing them (plan, section 4). Every interval is a Wilson interval on the person-keyed n, as the eval gate's rule says. Per-level and per-source rows are description; a level with too few test persons to carry an interval is reported with its n and never pooled to reach one. Nothing is read blind, since no person reads an image. The run's verdict is computed by flows/v1.py from the run's end and its report, so no reader chooses it.

## 7. Freeze

Frozen on 2026-10-29 by the thread named above, from the commit named above, before any run of version 1 under this file: `sha256sum PREREG.md > PREREG.md.sha256` in this folder, both committed. Frozen again the same day, before this file was merged and before any run had used the first freeze, after the thread's own review: section 5 now names the lines the flow's end step and its page give, which the first freeze worded as sentences no code writes, and says that a stale report of work done before the Metaflow run began is written anew and is no failure. No further edits: a departure goes in DEVIATIONS.md beside it, and a second design, a bar the owner sets among them, is a new file with its own freeze.
