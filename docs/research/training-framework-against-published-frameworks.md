# SchwingNet's plug-and-play training framework beside ClassyVision and the frameworks big tech has published

Source: the thread "Compare lab's X-ray learning to SchwingNet", 2026-10-25, issue #276, on the owner's question of 2026-10-25 01:39 UTC: "also how does my approach workflow compare to something like this or other big tech published frameworks", with the link github.com/benjamindkilleen/ClassyVision. Confidential with the rest of this repository, since it describes the project's training method. The framework is the one docs/research/experiment-framework.md describes: src/schwingnet/blocks.py, tools/train_blocks.py, tools/train.py, tools/flow.py and tools/block_sweep.py at main 633a2d6.

Grades: Measured is this repository's code as read at that commit; Published is the named project's own page or documentation; Inferred is reasoned here. ClassyVision's page was read on 2026-10-25; the other frameworks are described from their public documentation as this session knows it and were not re-read, so their rows are Inferred where they go beyond the one line each project says of itself.

## 1. What the link is

github.com/benjamindkilleen/ClassyVision is Killeen's fork of facebookresearch/ClassyVision, with the upstream README and no change the page shows (Published). Meta archived ClassyVision on 1 July 2024: "Classy Vision is no longer actively maintained"; its last stable release is 0.7.0, tested with PyTorch 2.0 (Published, the upstream page). Its design: a training run is a task (ClassificationTask) that composes a model, a dataset, a loss, an optimiser and hooks, each registered by name and built from a JSON config, later through Hydra (Published). The fork says the lab tried a Meta framework at some point; nothing read shows they train FluoroSAM or SyntheX on it (FluoroSAM's code is its own, SyntheX's a TransUNet) (Inferred).

## 2. The same idea, many times over

Every framework below solves the owner's ask, "plug and play pieces", the same way: a part of training is an interface, a way of doing it is a name in a registry, and a run is a configuration that names one choice per part. SchwingNet's blocks are that pattern (Measured: CHOICES in blocks.py, the function tables in train_blocks.py). So the question is not whether the design is sound, which the big frameworks confirm, but what each adds and what SchwingNet adds that they lack.

| Framework (owner) | Registry and config | Sweeps and search | Record of a run | Status |
| --- | --- | --- | --- | --- |
| ClassyVision (Meta) | registered task, model, loss, optimiser, hooks; JSON, then Hydra | none of its own | logs and checkpoints | archived 2024 (Published) |
| Detectron2 (Meta) | registries, then LazyConfig (Python objects as config) | none of its own | the config dumped beside the checkpoint | maintained slowly (Inferred) |
| MMEngine / OpenMMLab (Shanghai AI Lab, SenseTime) | a Registry for every part, Python config files with inheritance | none of its own | the merged config written to the work dir | active (Inferred) |
| PyTorch Lightning (Lightning AI) | LightningModule and Trainer, callbacks; LightningCLI from type hints | through Optuna or Ray | loggers of choice | active (Inferred) |
| Hydra (Meta) | composable YAML config groups, overrides `key=value` on the command line | multirun over a grid, sweeper plugins (Optuna, Ax) | the composed config saved per run | active (Inferred) |
| timm (Hugging Face) | `create_model` by name over hundreds of backbones | none | none | active (Inferred) |
| MONAI Bundle and Auto3DSeg (NVIDIA and the MONAI consortium) | bundle configs; Auto3DSeg generates and tunes algorithms | Auto3DSeg's HPO | bundle metadata | active (Inferred) |
| nnU-Net (DKFZ) | no plug-ins by design: a fingerprint of the data sets the configuration | fixed rules, five folds | plans files | active, the medical reference (Inferred) |
| Metaflow (Netflix) | steps of a flow, not training parts | foreach fan-out | every artefact versioned, resume | active; SchwingNet runs its steps as Metaflow steps (Measured: pixi.toml, docs/memory/the-data-catalog.md) |
| Ray Tune, Optuna, W&B Sweeps (Anyscale, Preferred Networks, Weights and Biases) | none; they call your trainer | Bayesian, bandit and early-stopping search | trial tables | active (Inferred) |
| TFX and Vertex AI Pipelines (Google) | components of a pipeline | Vizier for search | ML Metadata lineage | active (Inferred) |

## 3. Where SchwingNet's framework is ahead of all of them

Each is a property of this repository's code, Measured at 633a2d6, set against the frameworks above, Inferred where it says they lack it.

1. Naming nothing is version 1 to the bit. Blocks' defaults are version 1's training, so every recorded run stays reproducible as pieces are added; the big frameworks version their defaults across releases and a config written for one release can train differently on the next.
2. Incoherent runs are refused in words before a tensor exists: a setting that acts on nothing, a source the train part lacks, an ImageNet file of another network, a sweep that mixes ImageNet and scratch starts so its rows would compare the start and not the block. Hydra and the registries accept any well-typed config.
3. The record is scientific, not only operational: RUN.json from a clean tree first, the catalog's hash, the person-keyed split, the leak checks before training, the licence recipe and PROVENANCE.json, every number a ResultRow with its Wilson interval, the crops kept against the crops offered. The closest is TFX's lineage and Metaflow's artefacts, which record what ran but not whether a number may be quoted.
4. The ledger reads only the validation part. block_sweep.py ledger never opens evaluate/results.json, so the choice of the next sweep cannot see the test part, which is read once for the chosen run. No framework above enforces that; Ray Tune and W&B Sweeps will optimise any metric they are given, the test set's included.
5. A person stands between the plan and the compute. `plan` prints the commands, runs and GPU-hours and submits nothing, as docs/project.md requires; the search tools start trials on their own.
6. Design by contract under a prover: blocks.py's pure side runs under beartype and beethoven-qa's contracts, proved by CrossHair in the gate. None of the frameworks above proves its config logic.
7. Witness frames from epoch 0: the same real frames drawn by every checkpoint, so a run can be seen learning, not only scored.

## 4. Where it is behind

1. Breadth. One task (27-way crop classification), one data loader, eight backbones; timm has hundreds, MMEngine and Detectron2 cover detection and segmentation, which the detector stage version 1 lacks will need (Measured for SchwingNet).
2. Search. The sweep is a grid, one block varied at a time; there is no Bayesian search, no early stopping of bad trials and no multi-fidelity schedule (Measured). Optuna or Ray Tune would find a good corner of a large space in fewer GPU-hours, at the cost of point 5 above unless their trials are planned and approved in batches (Inferred).
3. Scale of training. No mixed precision, no distributed data parallel, no torch.compile in tools/train.py (Measured, by search of the file). Lightning gives all three by a flag. For 64-px crops on one GPU this costs little today; for a detector on whole frames it will (Inferred).
4. Extension cost. A new piece is a name in a tuple in blocks.py, a function in a table in train_blocks.py and, for some parts, an entry in HEADS, FEATURES or AUGMENT_ORDER, held together by tests (Measured). A decorator registry, as MMEngine's or ClassyVision's, puts the name and the function in one place (Inferred). The split exists for a reason, the pure side under the prover with no torch, so the fix is a check, which exists, not a merge (Measured: tests/test_train_blocks.py).
5. Config files. Choices live on the command line as `--block KEY=VALUE`; there are no composable config files (Measured). Hydra's groups would let a named recipe ("v1-imagenet-aug") be one word; the plan command fills part of that role (Inferred).
6. Community and survival. One maintainer and one project; ClassyVision's archiving shows that even a Meta framework dies when its team moves, so the risk is real both ways (Published for ClassyVision; Inferred for the rest).

## 5. What to take, and what to leave

- Leave ClassyVision: archived, image classification only, and nothing in it that blocks.py lacks (Inferred).
- Do not adopt Lightning, MMEngine or Detectron2 wholesale for version 1: each would replace tools/train.py, whose parity with version 1 is what makes the recorded runs reproducible, and each is a new dependency, an issue first (.claude/rules/writing.md).
- Worth taking, in this order, each as an issue first:
  1. An Optuna-style search as a planner, not a runner: it proposes the next batch of `plan` commands from the ledger, the owner still gives the word and count. This is the planner worker experiment-framework.md section 4 already names, with a search algorithm inside it.
  2. timm for the architecture part, when a sweep asks for more backbones than torchvision and MONAI give: one HEADS and FEATURES entry per model, as now.
  3. Mixed precision and channels-last in tools/train.py behind a block whose default is off, so version 1 stays bit-exact.
  4. For the detector stage, MMDetection's or Detectron2's model zoo as the architecture source, wrapped by the same blocks, with the flow, the record and the ledger unchanged.
- The big frameworks solve how to swap parts; the part they do not solve, and this framework does, is whether the number a swap produced may be believed. That is the thing to keep when pieces of theirs come in (Inferred).

## 6. Read

github.com/benjamindkilleen/ClassyVision and github.com/facebookresearch/ClassyVision (2026-10-25); docs/research/experiment-framework.md; src/schwingnet/blocks.py, tools/train_blocks.py and tools/train.py at 633a2d6; pixi.toml. The other frameworks were not re-read for this note.
