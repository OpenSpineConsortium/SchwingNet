# The plan, version 2: the data workflow first, one model that works, evaluation visible from the first frame

Source: the thread "SchwingNet video demo plan", 2026-10-20, the owner's words of that afternoon, which replace version 1's premise (version 1 is this file as merged by #14, at commit fb04389 of main, merged by #14 as c343cdc; its audit list and its data table are carried below where they still hold). Facts come from OpenSpineConsortium/spine-program (folder 01_carm_level_detection unless another is named) and Gregory-Schwing-MD-PhD/spinesurg-ct-nnunet, branch L6_Class (`ssn:`), read on 2026-10-20. Every number names its file; "not recorded" means the record is silent. This file is confidential with the rest of this repository (docs/project.md).

## 0. What the owner said, and what it changes

In the owner's words: "i dont give a shit about comparing to a shabbily done baseline, what i care about is building an extensible workflow that wont have to be rerun from scratch when i add more datasets; the well done version of this workflow should be considered the first version"; "focus more on the data workflow creation before job creation and seeds"; "I anticipate collecting more instances of the rare classes, and I want my datasets to be such that I can seamlessly add them without relaunching epochs, so I can iteratively improve the network as I annotate data"; "extreme effort should be taken to expose evaluation of the model from start all the way to perfection on a real image, so I can believe that my work is improving over time, in addition to obvious wandb"; "clearly don't do ensembles of models before training one to work and serve as a baseline"; "the goal becomes low latency, high accuracy vertebral classification on fluoroscopic videos or images"; Dr Tech is to be provided scans automatically, but not yet.

So, against version 1:

- The reported stack is not the baseline and no paired comparison with it is a deliverable. The first model this workflow trains to work is version 1 of SchwingNet; everything after is measured against it, on the same frozen test persons, in one table that grows a row per version.
- Nothing is run from scratch when data is added: a dataset is a shard, appended; a training run starts from the last checkpoint and sees the new shards; a full retrain is a named, deliberate step, never the default.
- One model per stage, one seed. Seeds, folds and ensembles are a later, optional study (section 8), never before version 1 works.
- Evaluation is a product of the workflow, not a step at the end: the same real frames are scored and drawn at every checkpoint from the untrained network to the final one, so the improvement is a sequence of pictures and a table over time, in W&B and on a page of this repository.
- The audit (version 1's section 3) does not go away: it becomes the checks that run when a shard is ingested, so a leak is refused at the door instead of found afterwards.

## 1. The goal, and what done is

Low-latency, high-accuracy vertebral classification on fluoroscopic video or images: given a frame or a stream of frames, name each visible vertebra (C1 to the sacrum) within the frame budget of section 5 on the devices it measures (no machine of a surgeon's room is measured; the only CPU figure is 3,350 ms per frame, DATA.md 203), and keep naming them as the C-arm moves.

Done, for this plan:

1. A dataset is added by one pull request (its registry file and Split record) and one incremental run; no epoch already run is run again.
2. Version 1 of SchwingNet: one detector, one encoder, one head, trained to work on the registry as it stands, with its card (weights hash, the shards it saw, the commit, the clean-tree flag).
3. The evaluation page: the witness frames drawn at every checkpoint, the per-level and per-source numbers with intervals at every version, the latency per version, all from one command and visible in W&B and on the repository's docs site (members only).
4. The latency: measured per model version on the H200 and on a CPU, with an ONNX export whose outputs match PyTorch's on the witness frames.
5. The talk's material: the recorded sweep with the overlay and the latency on screen (docs/project.md keeps the podium a recording), and the figures from the evaluation page; results, not methods, before the provisional is filed on 30 October.

The dates in section 9 are targets. What falls off first if time runs short is in section 9 too; what does not fall off is items 1 to 3.

## 2. COBRA, answered

COBRA2026 is not fluoroscopy of the spine. It is 692 public pelvic cone-beam CT cases from radiotherapy (467 Elekta, 225 Varian), each a set of 2D X-ray projections taken around the patient, 375,618 projections in all, with a registered planning CT (DATA.md 124-127; version 1's data table). The projections look like single fluoroscopic frames of the pelvis and lumbosacral junction; they are not video, and the sacrum is defined on 18.2 % of 609 test frames (grants/aidas_2027/RECORD.md 76); how far up the spine a projection reaches is not recorded. Today 145 Elekta cases are in a frame bank and the sacrum detector trains on 118 of them (110 train, 8 validation), 3,094 frames with DeepFluoro (DATASET_USAGE.md 36-42).

Does it help? For the sacrum anchor, yes: it is the only large real-projection source with a pelvis, and the sacrum is the count's anchor. For naming vertebrae across the spine, no: its levels are not labelled and it holds nothing cervical or thoracic. So in this plan COBRA is one shard among the detector's sources, ingested when the registry reaches the detector, and nothing of the whole-spine goal waits on it. "Use it whole" (version 1, decision 2) becomes: ingest the Elekta and Varian cases that are not embargoed as one shard each, keyed by case, with the sacrum label projected from the planning CT, when the detector's turn comes.

## 3. The data workflow

The record's banks today are monolithic: one bank is one build (`ssn:slurm/allspine_v9_bank.sh` runs make_context_crops.py over every source at once), a new source means a new bank and a new training from its first epoch, and the leaks of version 1's section 3 came from banks rebuilt by hand (NHANES twice, FluoroCap in, VinDr per image). The workflow replaces the bank with a registry of shards.

### 3.1 The registry

One file per source under `data/registry/<source>.json`, in the repository, with: the source's name and licence; where it is on the grid (never a copy here); the identity level, one of beethoven-research's `SplitLevel` members by name (patient, study, cadaver, source_volume; splits.py 40-46): patient for the films and for COBRA, keyed cobra:<case> with centres D, F and G stripped (LEAKAGE.md 4), cadaver for DeepFluoro, source_volume for the renders and the rule that makes a person key from the source's own metadata, in writing (identity from metadata first, the file name last; spine-program CLAUDE.md rule 9); the access and IRB status line (BUILD_PLAN's G4 row; "not stated" blocks a clinical source); and the list of its shards. The registry is read by the flow and by the tests, and `bash scripts/check.sh` fails on a file that does not hold together.

### 3.2 Shards

A shard is the unit of ingestion: one directory on the grid, `shards/<source>/<ingest date>-<content hash>/`, holding source items only, frames and their labels in the format the detectors' trainer reads (PNG and YOLO-style label files), a `MANIFEST.json` with the sha256 of every file, the person key of every item as the study-local pseudonym and never an identifier (PHI stays on the grid; the manifest's counts reach this repository and the page), the class count per level, and the commit of the code that made it. The encoder's crops are not source data: make_context_crops.py cuts them with a detector (`ssn:slurm/allspine_v9_bank.sh` 24-28), so a retrained detector makes every crop stale. Crops are therefore derived artifacts, keyed by the source shard's hash and the detector's version, made by a flow step and recorded on the run's card, never ingested. A shard is never rewritten; a correction is a new shard that supersedes it by name in the registry. So:

- Adding a dataset, or a week's annotations of rare classes, appends a shard. The registry's class-count table shows what it added (how many L6, how many T13) before any job runs.
- A bank is the list of shards a run reads, recorded on the run's card. Two runs that read the same list read the same bytes, by hash.
- The leak checks run at ingestion: the person-key chain (LEAKAGE.md's content-hash chain, CHK-6 and CHK-7, never run on the real corpus until now) over the new shard against every shard already registered, in a CPU job. A shard is either a training shard or a test shard: an item of a test person (3.3) goes only to a test shard, read by the evaluate step and never by a trainer, which is how the owner's new annotations of the rare classes land, since the only real L6 persons the record holds are the test persons case42, case121 and case136 (STATUS.md 130); an item of a person no shard holds falls to train or validation by the hash; a shard that mixes test persons with others, or carries a source the directives exclude (FluoroCap, D1), is refused and never registered. The hash split rests on the chain: a person under two keys (a CT and its renders; COBRA's 5,013 duplicates, LEAKAGE.md 5.3) is one person only once the chain has joined the keys, so no shard is registered before its chain run is green.

### 3.3 Splits that extend

The split is by person key, decided by a hash of the key with a salt and a ratio the registry states, so a person added later falls into train or validation the same way whoever ingests them, with no reshuffle; the test persons are a frozen list in the repository (`data/splits/test-persons.json`), extended only by an explicit pull request, never by the hash. Resuming from a checkpoint makes every later model's ancestry the whole shard history, so an extension may name only a person no training shard has ever held (LEAKAGE.md 11-15: no ancestor may have seen them); naming any other forces a `rebase` (3.4), and a superseding shard that re-keys a person cannot move them across the hash boundary once a checkpoint saw them. The hash does not stratify: a rare class's persons, or DeepFluoro's six cadavers, can all fall to one side, so the registry reports each level's persons per split and a class whose validation side is empty is assigned by hand in the registry file, recorded, before its first training run; that is also how the owner sees when a class has enough test persons to report with an interval. The validation set grows with each shard, so only the test rows of section 4's table are comparable across versions; the validation rows say which shards they cover. Each source's Split record (beethoven-research's `Split`, `shared_groups`, `disjoint`) is a test in this repository that fails on a shared group.

### 3.4 Training that resumes

Each stage (detector, encoder, head) has a checkpoint registry: `models/<stage>/<version>.json` with the weights' sha256, the shard list it saw, the epochs, the parent version, the commit and clean-tree flag. An incremental run starts from the latest checkpoint and trains for a bounded number of epochs over all shards with the new ones oversampled (rehearsal, so the old classes are not forgotten); the validation witness frames (section 4) after every epoch are what say whether it helped and which epoch is kept, and the test frames are never read for that choice. A run from declared public weights (ImageNet for the encoder, COCO for the detectors, as realxray_train.py 170 starts them) over every shard is the `rebase` step, run on purpose (the first version 1 is one; a change of architecture or crop size is another), and the card says which it was. The trainers stay the record's scripts (`ssn:tools/train_level_classifier.py`, `realxray_train.py`, `head_mixed_length.py`), called by path at a named commit, never refactored: each already takes a starting checkpoint (`--init`, train_level_classifier.py 355 and realxray_train.py 170; `--init-head`, head_mixed_length.py 225), which is the resume, and each reads one bank, so this repository's wrapper assembles the bank from the shard list (an index or links, never a copy) and passes `--init`, then writes the card. Whether `--init` restores the optimizer or only the weights, and whether a resume re-reads the whole bank, is not recorded; the wrapper measures both on the first run.

### 3.5 The flow

Metaflow with a Slurm adapter (Beethoven's D3; nothing of it exists yet, beethoven-agents pixi.toml 9-11), built here first as a pixi feature of this repository, under beethoven-qa's gate for its pure parts: `ingest` (a shard from a source, the leak checks), `split_check`, `train` per stage, `evaluate`, `latency`, `cards`. Every step submits one sbatch, never runs on the login node, polls no faster than every 60 s, and records job id, partition, QoS, wall time, GPU-hours and preemptions beside its result (spine-program CLAUDE.md rule 7; beethoven-agents CLAUDE.md). A step that fails is resumed from its last artifact (Metaflow's `resume`), and the data a step reads is named by shard hashes, so a resumed run reads the same bytes.

## 4. Evaluation visible from the first frame

Three views, all written by the `evaluate` step from one command, so the page and W&B never disagree:

1. **The witness frames.** Two fixed sets of real frames, chosen once and frozen. The validation witness set, 24 C-ArmLSpine frames of validation persons across the lumbar levels, is drawn and scored at every epoch and chooses the checkpoint. The test witness set, 24 C-ArmLSpine frames of test persons, the three L6 cases (case42, case121, case136; STATUS.md 130) and 8 frames of each sweep (case134, and case39 once its export with level names exists; it has none today), is drawn at every checkpoint but read only at a version boundary, never to choose one, since selection on test persons counts as seeing them (LEAKAGE.md, section 1). A film row per region (cervical, thoracic) joins the test set only after the v9 films are re-keyed and a `rebase` from declared weights, since every CSXA, BUU and NHANES person today is in the v9 base's training or selection set; it is not in the first strip. Each frame is drawn with the detector's boxes and the predicted name beside the true one, as one strip per frame over the checkpoints, from the untrained network at epoch 0 onward. W&B gets the strips as media; the docs page shows the latest and the whole sequence as a video per frame. This is the picture of the work improving.
2. **The table over time.** Per version and per checkpoint: naming accuracy per level and per source with Wilson intervals on person-keyed n (the eval gate's rule, `ssn:tools/eval_gate.py`, kept), detection recall, the confusion matrix per level, and "what the last shard changed" (the same numbers on the run before and after it). The transitional stratum is its own rows, never pooled.
3. **The sweep.** The causal tracker over case134 and case39 at every version, with the CLEAR-MOT numbers and the latency, and the overlay recording, which is the talk's demo.

Every row stamps the version, the shard list hash, the commit and the clean-tree flag; a dirty tree is refused. The page is the repository's docs site, members only as the owner chose on 2026-10-20 (whether GitHub Pages restricts a private site on this plan is not yet measured; until it is, the page is read from the repository); nothing of the method leaves before 30 October.

## 5. Latency

Measured per model version, never claimed from an old run (runtime_cost.json does not exist, DATA.md 206-209; the "17 ms" is banned, DATA.md 336-337): `cine_latency.py` on an H200 and on a CPU with 8 threads, for the four models (the two detectors, the encoder, the head) and the whole frame path; an ONNX export of each stage with a parity check on the witness frames; the frame budget is the sweep's own rate, about 10.3 fps, so 97 ms per frame end to end (demo-plan.md, section 1). TensorRT and a browser player (onnxruntime-web) are after version 1, each with its own parity run.

## 6. What stays from version 1

- The audit's findings (version 1, section 3) are the ingestion checks of 3.2 and the Split tests of 3.3; nothing of the old fold banks is reused, since every shard is made from the sources again under the registry.
- The data table (version 1, section 4) is the list of sources to register, in this order: C-ArmLSpine (the test persons and the sweeps first, frozen), then the v9 films and renders re-keyed by person, DeepFluoro by cadaver, COBRA by case for the detector, the synthetic L6 renders; RSNA cervical CT and the public clips after version 1, on the owner's word.
- The spend table (version 1, section 7) stands as the catalogue of scripts and partitions; the jobs that run are section 8's, and none starts without the owner's word and number.

## 7. Dr Tech

Later. The workflow leaves the hook: a `review` shard type whose items are frames waiting for a second read, written by the evaluate step for the transitional stratum, and a step that packages them for a reader under the owner's data agreement. It sends nothing until the owner says so, and the engine never sends frames itself (version 1, decision 7, kept).

## 8. The order of work and the tasks

1. #10, retitled: the registry, the shards and the splits (sections 3.1 to 3.3), with the ingestion checks and the Split tests; C-ArmLSpine and the sweeps registered first. CPU jobs only.
2. #9: the leak checks as code (the person-key chain, CHK-6, CHK-7) inside `ingest`, under the gate.
3. #11: the flow with the Slurm adapter and the resuming trainer wrappers (3.4, 3.5), dry-run on one epoch.
4. #12: the evaluate step, the witness frames, W&B and the docs page (section 4).
5. Version 1: one run of each stage, `rebase`, on the registry as it stands; its card and its page.
6. #13: latency and the ONNX parity, the recording.
7. After version 1: incremental runs as annotations arrive; seeds, folds and ensembles as a study of their own; RSNA, the clips, Dr Tech.

## 9. Schedule, and what the owner decides

| By | Lands |
| --- | --- |
| Fri 23 Oct | the registry and the first shards (C-ArmLSpine, the sweeps); the Split tests green; the chain (CHK-6, CHK-7) started on the real corpus, its first run ever, as a CPU job |
| Sun 25 Oct | the v9 films re-keyed and registered; the evaluate step drawing the witness frames at epoch 0; the flow's dry run, or, where the flow is late, the record's sbatch scripts run by hand under the registry, which is the fallback for every step below |
| Wed 28 Oct | version 1 trained (one run per stage, 8 h detector, 14 h encoder, 10 h head, each after the owner's word and number); the page and W&B, members only |
| Thu 29 Oct | latency and ONNX parity; the recorded sweep with the overlay |
| Fri 30 Oct | the provisional filed (the owner's) |
| Mon 2 Nov | the talk |

Falls off first if time runs short: the thoracic and cervical film rows of the witness set, the CPU latency, the ONNX export. Does not fall off: the registry, version 1, the witness page.

Decisions the owner still owns, each with its default, which runs unless he says otherwise:

1. Weights and Biases: project SchwingNet, private, in offline mode on the compute node and synced from the owner's own computer from a copy of the run directories, so no key is held by the repository or the grid; the key as a repository secret, read by a grid.yml job, only on the owner's word in his own words; default offline.
2. The witness set as section 4 lists it; default as listed.
3. The identity level per source as the registry files will state it (person for films, cadaver for DeepFluoro, case for COBRA, source volume for renders); default as stated.
4. The word and the number of jobs for each step of section 8, given when that step is ready; nothing is submitted before it.

## 10. Future directions

- Veterinary medicine (the owner, 2026-10-20): the workflow takes a species the way it takes a dataset. The pig lower-limb CT, CBCT and planar images of Goswami 2020 (a 2D/3D registration phantom with no spine, not the LevelCheck study the record once named; open on IEEE DataPort, and seven zips in spine-program's archive) are the first veterinary source record in data/sources/ and tune the registration code only; the canine thoracic radiographs (canine_thoracic_vhs) are the first veterinary set with a spine, and a registry shard keyed by animal as a person is keyed would train and test the same stages with no change to the flow. Nothing of it starts before version 1.
- The source registry (data/sources/, docs/research/datasets-inventory.md, #23) is the catalogue the shard registry of task #10 points at: each shard names its source id, so a source's licence and reach travel with every frame cut from it.
