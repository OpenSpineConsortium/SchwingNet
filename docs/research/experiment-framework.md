# The experiment framework: every part of training a plug-and-play piece, and the loop that optimises them

Source: the project thread "Build plug-and-play training experiment framework", 2026-10-24, on the
owner's words of 2026-10-24 07:51 UTC ("getting something i can build on to continually optimize
both which samples i use, which architectures, which denoising, augmentation, ect as plug and play
pieces") and the owner's question of 08:14 UTC with the upload of arXiv 2610.28410v1 (Shen and
Unberath, "A Multi-Agent Framework for Automated Machine Learning with Evidence-based Planning for
Medical Image Analysis", MedicalMLOmni, 20 October 2026): "why not use one of the packages in this
paper? or can i fit into one of the blocks?". Confidential with the rest of this repository. Issue
#207, pull request #208; it follows #203 (the first seven blocks) and #206 (the warm start). No grid
job, fetch or training was started; every test here runs on the synthetic catalog on a CPU.

## 1. The loop, in four commands

The framework is the blocks of src/schwingnet/blocks.py and four commands of tools/block_sweep.py.
A piece of training is a part; a way of doing it is a name; a run names one choice per part on the
command line of tools/flow.py, `--block KEY=VALUE`, and naming none is version 1's training to the
bit. The loop that optimises them is:

1. `python3 tools/block_sweep.py parts`: every part, its names and version 1's choice, the one list
   of the plug-in points (section 2). A new way of doing a part appears here the moment it is
   added, since the table is read from the code.
2. `python3 tools/block_sweep.py plan --catalog ... --out ... --epochs ... --base KEY=VALUE --vary
   KEY=V1/V2`: the tools/flow.py command of every combination, the number of runs and jobs and the
   GPU-hours they ask for. It submits nothing; the owner reads the count and gives the word, as
   docs/project.md requires of every grid job. An ImageNet file is one architecture's, so
   `--weights [ARCHITECTURE=]FILE` is given once per architecture the sweep names (a bare file
   is resnet18's), each command carries its own, and a sweep in which one run would start from
   ImageNet and another from nothing is refused, since its rows would compare the start and not
   the block; the grid holds resnet18's file alone today (grid/gate.sh), so a sweep over
   architecture fetches the others first or starts every run from scratch.
3. The runs, each one tools/flow.py run: RUN.json from a clean tree first, train, evaluate, the
   witness frames drawn at every epoch, checkpoint.json recording the blocks, the parent and the
   counts of crops seen and offered, and MODEL.md saying the same in words.
4. `python3 tools/block_sweep.py ledger <runs folder>`: every run under the folder, found by its
   train/checkpoint.json however deep and behind links, in one table: the blocks that differ from
   version 1, the training crops the samples block kept of those offered (a --max-frames cap
   told apart, so a dry run's cut is never read as a block's), the parent run, or its file with
   its hash, the best epoch, the validation accuracy
   with its Wilson interval, the balanced accuracy, the validation witness score and the latency
   headline where one was measured. It reads validation and latency only, never evaluate/: the
   choice of the next plan is made from the validation part, and the test part is read once for the
   chosen run (docs/research/retraining-plan.md, section 4). A run whose record cannot be read
   stops the ledger naming it, so a folder written halfway names itself. The next plan is step 2
   again.

Adding a piece is two lines: a name in its part's tuple in src/schwingnet/blocks.py and a function
in that part's table in tools/train_blocks.py. tests/test_train_blocks.py fails when a table and
its tuple disagree, tests/schwingnet/test_blocks.py holds the pure side under the gate's contracts,
and tools/train.py calls only the tables, so it never changes for a new piece. A new part is a
field on Blocks with a default that is version 1's choice, a tuple, a table, and its line in
`problems` where it has a range; `parts` lists it by itself.

## 2. The parts, as of this change

| part | choices | version 1 |
|---|---|---|
| normalise | none, imagenet | none |
| augment | any of box-jitter, intensity, blur, noise, comma-separated, or none | none |
| optimiser | adam, adamw | adam |
| weight_decay | a finite number, 0 or more, with optimiser=adamw | 0.0 |
| schedule | constant, cosine | constant |
| warmup_epochs | whole epochs, 0 or more | 0 |
| backbone_lr_scale | above 0 and at most 1 | 1.0 |
| sampler | uniform, balanced | uniform |
| loss_weights | none, inverse-frequency | none |
| select | accuracy, balanced-accuracy | accuracy |
| samples | all, only-sources, drop-sources, cap-per-person | all |
| sources | the catalog's sources, comma-separated, with samples=only-sources or drop-sources | none |
| per_person | crops kept per person, 1 or more, with samples=cap-per-person | 0 |
| architecture | resnet18, resnet34, resnet50, mobilenet-v3-small, efficientnet-b0 | resnet18 |
| denoise | none, gaussian, median | none |

The table is `python3 tools/block_sweep.py parts` at this commit; the command, not this page, is
the record once a piece is added.

## 3. The three parts this change adds, and the decisions in them

- **samples: which training crops a run sees.** `only-sources` and `drop-sources` take the
  catalog's source names (`sources=carmlspine,vindr`); `cap-per-person` keeps the first N crops of
  each person in the catalog's order, which is by frame hash and then level, fixed and arbitrary,
  so a cap is the same crops in every run and nothing random enters the choice. The validation
  part is never cut: every run of a comparison scores the same crops, or the comparison says
  nothing. A setting that would act on nothing (sources with samples=all, per_person with
  only-sources) is refused in words, since it is most likely a mistake, and so is a source the
  catalog's train part does not hold, since the cut it names would otherwise be recorded and
  never made (the adversarial review of #208). checkpoint.json and the card record the crops the
  block kept of the crops offered, and apart from them what a dry run's --max-frames cap took, so
  the ledger shows a run that saw fewer crops beside one that saw them all and credits no block
  with a cap; the validation count says whether the whole part was read; and a samples block
  that leaves no crop stops the run before any tensor is made. A licence recipe (data/recipes/, tools/licences.py) cuts the catalog before any
  of this; samples cuts within the catalog a run was given.
- **architecture: the backbone.** resnet18 is version 1; resnet34 and resnet50 are the same family
  wider and deeper; mobilenet-v3-small is the latency candidate, about a tenth of resnet18's
  multiply-adds at the same input; efficientnet-b0 sits between. Each entry builds the network
  with a 27-way head of its own (HEADS in tools/train_blocks.py names the head's parameters, so
  the ImageNet file loads without it and backbone_lr_scale gives the rest a smaller rate), and an
  ImageNet file of another network is refused in words, whether its names or its shapes differ.
  Every reader builds the model from the checkpoint's record (train.model_for): the evaluator, the
  latency tool, the chain evaluation and the ONNX export follow a run's architecture without a
  flag, and a checkpoint from before the blocks existed is resnet18 as before. One thing the
  resnets lack: mobilenet-v3-small's classifier holds a Dropout and efficientnet-b0 Dropout and
  StochasticDepth, torchvision's own, which in training draw from the device's global generator
  (seeded by seed_everything) and not from the run's CPU generator the blocks draw from, so a
  run of those two reproduces on the same kind of device, a resnet run on any; a seeded
  replacement of those modules is one more function if a grid run ever needs a CPU rerun.
- **denoise: a filter inside the model.** gaussian (one spread, 0.7 pixels) and median (3 by 3)
  are forward pre-hooks registered before the normalise hook, so the crop is filtered and then
  scaled inside the model and whatever calls the model, including the ONNX export the latency
  measurement runs, sees the same crop the trainer saw. The median is nine shifted views sorted
  along a new axis, since the TorchScript exporter carries slices and a sort where it carries no
  median op; the test exports every architecture with the median filter and ImageNet scaling and
  compares ONNX Runtime with PyTorch. A wider gaussian is a new name, never a setting, so a run's
  record names its filter whole.
- **The warm start inherits them.** A run that starts from a parent checkpoint (--init, #206) must
  share the parent's architecture, denoise and normalise, since the weights are only right for the
  network they were trained in and for the input it saw; the trainer refuses the rest in words,
  naming the block that differs.

## 4. MedicalMLOmni (arXiv 2610.28410) set beside this framework

What the paper is, from its sections 1 to 3: a multi-agent AutoML system in which a Qwen3-30B agent
reads a task description, profiles the data, searches a frozen PubMed and arXiv snapshot for
published configurations, scores them, writes a plan (task agent, architecture, loss,
hyperparameters, a performance threshold), generates the data-processing, training and validation
code, runs it in a network-isolated sandbox with up to five debugging retries, and, when the
validation metric misses the threshold, spawns parallel HPO agents that each adjust one category
(architecture, augmentation, regularisation, learning-rate schedule) from further retrieval and are
aggregated by confidence. Its implementation layers are MONAI for vision tasks, LLaMA-Factory for
text and AutoGluon-Multimodal for fusion; its baselines are nnU-Net, Auto3DSeg, MedNeXt, AutoKeras,
AutoGluon, MLZero and AutoM3L; its benchmarks are 3D segmentation, visual question answering and
multimodal fusion. The paper gives no code link.

Why none of its packages replaces the blocks (Inferred, from the paper's text and this
repository's rules):

- The task differs. Nothing in the paper targets a 2D classification of fluoroscopy crops under a
  latency budget (97 ms, docs/memory/latency-and-the-recorded-sweep.md); Auto3DSeg is 3D
  segmentation, AutoGluon and AutoKeras are general-purpose and are the weakest rows of its own
  tables.
- The record rule differs. Here every number is reproduced by tools/flow.py from a commit, a
  catalog hash and a seed (docs/project.md), and the gate proves the pure code. A system that
  writes the training code per run and retries it is the opposite design: the code that produced
  a number is a transcript, not a commit.
- Dependencies are an issue first (.claude/rules/writing.md), and a new package in the train
  environment is a re-lock of pixi.lock made on purpose (docs/research/retraining-plan.md,
  section 5). The train feature holds torch, torchvision, Pillow, numpy, matplotlib, onnx and
  pydicom; MONAI is not in it.

What does fit a block (Inferred):

- MONAI's transforms map one to one onto the augment names: RandAffine onto box-jitter,
  RandAdjustContrast onto intensity, RandGaussianSmooth onto blur, RandGaussianNoise onto noise.
  The torch versions here already do the same in a few lines each, seeded by the run's own
  generator, so there is nothing to gain by swapping them.
- MONAI's classification networks (DenseNet121, SENet154, its EfficientNet family) would each be
  one more architecture name: one function in ARCHITECTURES and one HEADS entry, once monai is in
  the train environment's lock. That is the whole change. It is not made here, since no part of
  version 1 asks for one of them yet and the lock is changed on purpose.

What is worth taking (Inferred): the structure of its HPO. Its agents each own one category, and
the categories (architecture, augmentation, regularisation, schedule) are parts of
src/schwingnet/blocks.py by other names; its aggregation is a choice among proposals from a
record. The ledger of section 1 is that record, and `plan` is what a proposal looks like. The
natural next step is a planner, a Symphony worker that reads the ledger and
docs/research/benchmarks-to-beat.md and proposes the next sweep as a `plan` command on its issue,
one block varied at a time, with the owner's word and count still standing between the plan and
the grid, as docs/project.md requires. The paper's own ablation says planning and retrieval
together were about half its gain and parallel HPO the rest (its Table 5, Dice 0.883 to 0.910 over
eight segmentation benchmarks), so the loop is worth having even without the retrieval.

## 5. What is next, in order

1. The version 1 rebase on the real catalog with the blocks the owner names, on the owner's word
   and count (docs/research/training-review.md, section 1, puts imagenet normalise and augment
   first); its ledger row is the baseline every later row is read against.
2. One sweep per part, one block varied at a time, each planned with `plan` and read with
   `ledger`: samples (cap-per-person at two or three counts, to see whether the many frames of
   one person help or merely repeat), architecture (mobilenet-v3-small against resnet18 for the
   latency row), denoise (median against none on the noisiest source).
3. The planner worker of section 4, once two or three ledger rows exist to read.
4. MONAI entries in ARCHITECTURES, if a sweep points at a network torchvision lacks, as an issue
   that re-locks the train environment.
