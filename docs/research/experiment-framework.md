# The experiment framework: every part of training a plug-and-play piece, and the loop that optimises them

Source: the project thread "Build plug-and-play training experiment framework", 2026-10-24, on the
owner's words of 2026-10-24 07:51 UTC ("getting something i can build on to continually optimize
both which samples i use, which architectures, which denoising, augmentation, ect as plug and play
pieces") and the owner's question of 08:14 UTC with the upload of arXiv 2610.28410v1 (Shen and
Unberath, "A Multi-Agent Framework for Automated Machine Learning with Evidence-based Planning for
Medical Image Analysis", MedicalMLOmni, 20 October 2026): "why not use one of the packages in this
paper? or can i fit into one of the blocks?". Confidential with the rest of this repository. Issue
#207, pull request #208; it follows #203 (the first seven blocks) and #206 (the warm start), and
#211 (the owner's word of 15:56 UTC, "can you insert these monai packages?") added monai to the
train environment and three of its networks as architecture names (section 3). No grid job, fetch
or training was started; every test here runs on the synthetic catalog on a CPU.

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
   headline where one was measured. It reads train/checkpoint.json, train/metrics.jsonl and the latency headline
   evaluate/latency.json, a timing measured on test frames and no score, never
   evaluate/results.json: the
   choice of the next plan is made from the validation part, and the test part is read once for the
   chosen run (docs/research/retraining-plan.md, section 4). A run whose record cannot be read
   stops the ledger naming it, so a folder written halfway names itself. The next plan is step 2
   again.

Adding a piece is a name in its part's tuple in src/schwingnet/blocks.py and a function in that
part's table in tools/train_blocks.py, plus the one place that part keys by name where it has
one: HEADS and FEATURES entries for an architecture (its head's parameter prefix, which the
ImageNet loader and backbone_lr_scale read, and its stages deepest first, which the prior head
hooks), a place in AUGMENT_ORDER for an augment change (augment applies
the order's names, so one outside it would be accepted and never applied), a branch in `_keeps`
for a samples choice. tests/test_train_blocks.py fails when a table, HEADS, FEATURES or
AUGMENT_ORDER and its tuple disagree, tests/schwingnet/test_blocks.py holds the pure side under the gate's
contracts, and tools/train.py calls only the tables, so it never changes for a new piece. A new
part is a field on Blocks with a default that is version 1's choice and either its tuple entered
in CHOICES, which `problems` checks and `parts` prints, or, for a setting with a range, its
range in words in SETTINGS and its line in `problems`; test_blocks.py holds that every field is
in one of the two, and `parts` lists it from there (the adversarial review of #208 found the
earlier wording, "two lines" and "`parts` lists it by itself", short of all three).

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
| architecture | resnet18, resnet34, resnet50, mobilenet-v3-small, efficientnet-b0, densenet121, se-resnet50, se-resnext50 | resnet18 |
| denoise | none, gaussian, median | none |
| prior | none, level-map | none |
| prior_weight | the prior loss's weight beside the level loss, above 0, with prior=level-map | 0.0 |

The table is `python3 tools/block_sweep.py parts` at this commit; the command, not this page, is
the record once a piece is added.

## 3. The three parts this change adds, and the decisions in them

- **samples: which training crops a run sees.** `only-sources` and `drop-sources` take the
  catalog's source names (`sources=carmlspine,vindr_spinexr`, the catalog's own ids); `cap-per-person` keeps the first N crops of
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
  wider and deeper; mobilenet-v3-small is the latency candidate, about a thirtieth of resnet18's
  multiply-adds at the same input (5.5 against 148 million at 64 px, 56 against 1,814 at 224 px,
  convolutions and linear layers counted with forward hooks; torchvision publishes 0.06 against
  1.81 GFLOPS); efficientnet-b0 sits between, at about a fifth. Each entry builds the network
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
  replacement of those modules is one more function if a grid run ever needs a CPU rerun. Since
  #211 three of MONAI's networks are names too, built in two dimensions with the 27-way head:
  densenet121 (about 1.6 times resnet18's multiply-adds, 231 million at 64 px, in 7 million
  parameters, fewer than any resnet; only mobilenet-v3-small, 1.5 million, and efficientnet-b0,
  4.0 million, are smaller), se-resnet50 (317 million: resnet50 in its Caffe layout, the stride
  in each stage's 1x1 convolution where torchvision's resnet50 strides in the 3x3, with a
  squeeze-and-excitation gate on every block, so fewer than torchvision's resnet50's 334 despite
  the gates, since the strided 3x3 runs on a quarter of the positions) and se-resnext50 (348
  million: the same gates on ResNeXt's 32x4d bottlenecks, twice as wide, their 3x3 convolutions
  in 32 groups of 4 and carrying the stride, as torchvision's resnets do, which is why it costs
  more and not less); none carries dropout, so they reproduce on any device, and monai is
  imported only when one of them is built, so a run of a torchvision name never
  loads it. densenet121 reads torchvision's densenet121 ImageNet file in either of its spellings
  (the published file's "norm.1", a saved state_dict's "norm1"), mapped to MONAI's names as
  MONAI's own loader maps the published file; the two SE networks read a file in MONAI's own
  names only, since their published ImageNet weights live on a third-party site in another
  naming, so a sweep that includes them starts every run from scratch, since `plan` refuses a
  sweep that mixes an ImageNet start with none (section 1, step 2) and carries no --init; a run
  from a parent is tools/flow.py run --init by hand. SENet154, which section 4 named, is left out
  at about five times resnet50's multiply-adds (Hu et al. 2018, Table 3), and MONAI's EfficientNet
  family too, since torchvision's efficientnet-b0 stands for it.
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
  environment is a re-lock of pixi.lock made on purpose (pixi.toml's header; the training stack
  as a pixi feature is docs/research/retraining-plan.md, section 3.5). The train feature holds,
  among others, torchvision, Pillow, numpy, matplotlib, metaflow, onnx, pydicom with its pylibjpeg
  decoders and wandb, torch through the cpu and cuda features, and monai since #211, one noarch
  package the lock took with nothing else moving.

What does fit a block (Inferred):

- MONAI's transforms map one to one onto the augment names: RandAffine onto box-jitter,
  RandAdjustContrast onto intensity, RandGaussianSmooth onto blur, RandGaussianNoise onto noise.
  The torch versions here already do the same in a few lines each, seeded by the run's own
  generator, so there is nothing to gain by swapping them.
- MONAI's classification networks (DenseNet121, SENet154, its EfficientNet family) are each one
  more architecture name: one function in ARCHITECTURES and one HEADS entry, once monai is in the
  train environment's lock. #208 left it unmade, since no part of version 1 asked for one and the
  lock is changed on purpose; #211 made it on the owner's word for DenseNet121, SEResNet50 and
  SEResNext50 (section 3), which was the whole change as said, plus the name mapping of
  torchvision's densenet file.

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
4. Done in #211 on the owner's word: monai in the lock and three of its networks as names
   (section 3). The next MONAI pieces, if a run asks for them, are two of its transforms that the
   augment names lack, RandCoarseDropout for the instruments that occlude a vertebra in theatre
   and RandHistogramShift for a device's response curve, each one augment name seeded from the
   run's generator.
5. The prior block's rung of the reverse ablation (section 6): the render shards of #59 with
   their level maps, prior=level-map against prior=none on the same catalog, once the owner
   gives the word and the count for the renders.

## 6. The prior block: the 3D truth projected onto the 2D frame as a second supervision (#228)

The owner's ask of 2026-10-24: a 3D prior for training the 2D network, "3d classified voxels
directly mapped onto 2D X-rays by deterministic registration", as one of the reverse-ablation
steps, since it is in the owner's words the gold standard for supervised learning and should
teach the network how the 3D bones collapse into the 2D image. VertebralDiffusion, which the
owner pointed at, holds no such code (the note of #212, docs/research/vertebral-diffusion.md: it is a 3D generator template, with no
projection, registration or 2D training), so the piece is built here from the project's own plan
(docs/research/ct-priors-for-2d-detection.md, items 3 and 4; docs/research/xr-from-3d/README.md,
workstream E's fourth layer, "a head predicts an anatomy map ... supervised exactly by the
renders, the CT's segmentation projected").

- **What the data carries.** A frame may bring a projected level map: a PNG of the frame's own
  size, one byte per pixel, 0 where no vertebra is and 1 to 27 for the catalog's levels in order,
  made by the render's own geometry (projector `render`) or by a pose registered to a real frame
  (`registered`). A bank names it in the frame's meta (`level_map`, a path inside the bank, and
  `level_map_from`); tools/ingest.py decodes it with the standard library, since it runs where no
  image library is, holds it to the frame's size and the codes and each chunk to its checksum, so a
  map it keeps is one the trainer's image library reads, and copies it into the shard at
  its own content address beside the frame; the manifest's item carries its path, digest,
  projector and labeller (schwingnet.catalog.LevelMap, manifest schema 2; a manifest whose items
  carry no map is still written as schema 1, byte for byte as before, so every shard on the grid
  reads as unchanged); the catalog's item row gained level_map and level_map_from, null for a
  frame without one (catalog schema 2). The synthetic bank writes a map for about three frames in
  four (a seeded draw at --map-share 0.75, from a generator of its own so a seed's frames are what
  they were), so the dry run exercises the block and the crops without a map beside it.
- **What the trainer does.** `prior=level-map` with `prior_weight` above 0 (the two go together,
  and a weight with no prior or a prior with no weight is refused) puts a head on one of the
  backbone's feature maps, the deepest that keeps eight cells across the crop: FEATURES in
  tools/train_blocks.py lists each architecture's stages deepest first (layer4 to layer1 for the
  resnets, slices of features for the others) and PriorHead picks by one forward of a blank crop at
  the run's size, layer1 at 32 pixels, layer2 at 64, layer3 at 128 and 14 by 14 cells of layer3 at
  224, refusing in words a crop too small for eight cells (and a crop the architecture cannot
  forward at all, as MONAI's densenet121 cannot a 16-pixel one). The last map before the pooling,
  where the first build of this change read, is 1 by 1 on a 32-pixel crop and 2 by 2 on a 64-pixel
  one for every architecture, one cell or four blended positions that cannot say where a level
  falls; the review of this change found the first smoke run's head, on that one cell at 32
  pixels, had learnt to say background at every pixel, its pixel accuracy of 0.48 being the
  background's share, which that stage and a single accuracy could not show. The head is one
  1 by 1 convolution to 28 classes, each cell repeated over the pixels it covers (nearest, since the
  bilinear upsample's backward is on torch's list of kernels that differ run to run on CUDA and the
  nearest one's is not) and scored by cross-entropy against the crop's map, cut and resized nearest
  as the crop is cut, every pixel of a crop whose frame has no map ignored; the stage and its cells
  are recorded as prior_stage and prior_cells in checkpoint.json and on the card's Prior line. The
  loss is the level loss plus prior_weight times the map loss. The
  box jitter moves the map with its crop, sampled nearest so a map stays level codes, and the
  intensity changes leave it; the crops come out as they would without maps, so a run with and
  one without the prior see the same pictures. The head is training-only: best.pt, train.model_for,
  the evaluator, the latency measurement and the ONNX export carry the 27-way classifier alone,
  unchanged, and the head's weights go to prior_head.pt beside best.pt with their digest in
  checkpoint.json. metrics.jsonl carries train_prior_loss, validation_map_pixel_accuracy and
  validation_map_body_accuracy per epoch, the second over every labelled pixel and the third over
  the vertebral pixels alone (codes 1 to 27), which a head that says background everywhere scores
  0 on while its pixel accuracy is the background's share, so the two apart tell learning from
  collapse; both are counted on the forward the validation prediction makes, so the validation
  tensor is forwarded once an epoch for the prediction and the tally (the witness frames,
  validation crops the Witness holds as tensors of its own, are the one other forward). With the
  prior on, train_loss (metrics.jsonl, checkpoint.json, the
  accuracy curve and the evaluation page's column) is the level loss plus prior_weight times the
  map loss, which the card says, so the column is not the control run's level loss. The counts
  train_with_map and validation_with_map say how many crops carried a map, and
  the card's Prior line says what the head read and at what weight. A run that names the prior on
  a catalog whose train part has no map is refused in words, since the head would learn from
  nothing and the record would say the prior was on.
- **Why a map, and why a head.** The map is what the 3D truth gives exactly and what a box
  loses: where each body's projection falls and how neighbours overlap at the angle the frame was
  taken at, which is the collapse from 3D to 2D the owner wants learnt. Per-pixel supervision asks
  the backbone to keep location in its features; the classifier then reads features that were
  made to know where the levels are. A head rather than a change to the classifier, because the
  exported model must stay the classifier the latency row measures, and because this is an
  ablation step: the same run with `prior=none` is the control. The anchors of item 3 (the twelfth
  ribs, the S1 endplate, the iliac crests) are the next name under the same part, `prior=anchors`
  with a head of its own, once a render carries them.
- **Where the maps come from.** None exist yet. C-ArmLSpine's truth was projected from each
  case's CBCT, but the builders kept boxes alone; the renders of #59 carry a map by construction;
  COBRA's registered planning CTs (#127) give maps for real frames. Rendering is a grid job and
  waits for the owner's word and the count, as every job does. Until then the block is tested on
  the synthetic bank, a dry run and no result. The first smoke run of this change (60 frames, two
  epochs, 32-pixel crops, the head on the last feature map) took the head's pixel accuracy to
  0.48, which the review showed to be the background's share: the head said background at every
  pixel, and one accuracy over a single cell (the last map is 1 by 1 at 32 pixels) could not
  tell. After the fix (the head on the deepest stage with eight cells, layer2 at 64 pixels; the
  vertebral-pixel accuracy beside the pixel one) a 12-epoch run on 238 synthetic frames (240
  written with the bank's seed 3, the two that repeat a frame's bytes taken out before the
  ingest; 805 training crops, 576 of them with a map, 69 validation crops, the trainer's seed 1,
  prior_weight 0.5, box jitter and intensity, no schedule) took the head's validation
  pixel accuracy from 0.08 untrained to 0.84 and its vertebral-pixel accuracy from 0.13 to 0.80
  at its best epoch, and the prior loss from 1.96 to 0.46, while the classifier's validation
  accuracy reached 0.986 (balanced 0.99) against 0.913 (0.83) for the same run with prior=none.
  Both curves swing from epoch to epoch on so few frames, and bright rectangles say nothing of
  real frames, so the number that counts is the ablation on the render shards.
- **In the reverse ablation.** The block is the shape head of the leave-one-out row "minus the
  shape head" in docs/research/benchmarks-to-beat.md, section 4: the run on the render shards with
  `prior=level-map` against the same run with `prior=none`. The build-up rung "renders with
  projected anchors" is run with `prior=level-map` until `prior=anchors` exists, since its own head
  is the anchors' and is not built. The pair is two plans, since the weight rule refuses a plan
  that holds `prior=none` beside a weight above 0: `python3 tools/block_sweep.py plan --base
  prior=level-map --base prior_weight=0.5 ...` for the rung and the same command with no prior
  words for the control, which is version 1's row; `ledger` reads both. (`--vary` separates values
  with `/`, so `--vary prior_weight=0.1/0.5` under `--base prior=level-map` plans the weights.)

## 7. The smoke test: every combination decided, every route run, the pipeline on Metaflow (#252)

The owner's asks of 2026-10-24, 21:11 to 21:20 UTC: smoke every combination of the blocks on the
grid, or the combinations that cover every route of data through the workflow; keep the results
in their go2432 folder at a path that follows from the configuration; resume preprocessing from
the latest step that reuses the most, enforced where the workflow software does it natively; and
know that any combination within the fundamental incompatibilities works on any dataset held,
annotated and unannotated sets passed on as they should be. At 22:12 UTC the owner chose three GPU
jobs and up to three CPU jobs for it, and at 22:27 UTC that Metaflow, installed and chosen in
October but used by no flow, be the engine whose resume is enforced. The results are kept under
docs/research/block-smoke/.

- **Two halves of one argument.** Running all 393,216 named combinations (the ten named parts,
  12,288 combinations with the samples cut counted as its four choices, times the 32 subsets of
  the five augment names) is neither possible nor needed. `python3 tools/block_sweep.py check
  --catalog FILE --all` decides every one of them at each crop size its rules were measured at on
  every architecture, 32, 64, 96 and 128 pixels, from the catalog's own facts, training nothing:
  it runs, or it is refused for a stated reason; any other size it refuses in words. Only the samples cut,
  the prior and the crop size can change a verdict, since every other part is a separate hook
  that acts on whatever crops it is given, so the check counts by those three and multiplies.
  Then a covering set of runs, `cover`, exercises on the GPU every option of every part and every
  pair of parts that interact in the code, and each run's outcome is set against the check's
  prediction for it; a mismatch is a bug, flagged in the results and failing the flow. Parts that
  share no code cannot hide a bug between them, so covering every interacting pair covers every
  route.
- **The cover.** Two halves, the prior off and the level-map prior on, each a greedy covering
  array over seventeen factors (architecture, crop size, denoise, normalise, the samples cut,
  optimiser, schedule, warm-up, backbone rate, sampler, loss weights, selection, and each of the
  five augment names on or off) holding every value of every factor and every pair of (denoise, normalise),
  (sampler, loss weights), (optimiser, schedule) and (schedule, warm-up). Each half closes with
  two rows of version 1's training at 64 pixels that cut to one labelled source of several,
  `samples=only-sources` and `samples=drop-sources` with `sources=@first-labelled`, which train
  on a strict part of the labelled crops where the catalog's train part holds two labelled
  sources, as the synthetic catalog's does, and are not applicable, saying why, where it holds
  one, as catalog version 1 and the two-source catalog do; in the array itself only-sources names
  every labelled source (`@labelled`), so the array trains on every catalog. Across the two halves
  every architecture, size, samples cut, augment name and backbone rate meets both prior values,
  which are the prior's interactions. After the cover come the route rows: one run from the
  ImageNet file, two warm starts from a cover row (one adding the prior), and the four refusals
  the check predicts (a cut that leaves no crop, a cut to the unannotated source alone, a warm
  start across architectures, a warm start that also names weights). `--strict` gives the full
  pairwise array instead, offered for when it is asked for.
- **Annotated and unannotated sets, natively.** Ingest keeps a box with no trusted level as a
  frame fact and drops it as a label, and a frame with no labelled box yields no crop, so an
  unannotated source such as VinDr-SpineXR enters the catalog and feeds the level stage nothing.
  The check and the plans name the kinds as placeholders, `@labelled`, `@unlabelled` and
  `@first-labelled` (the first by name of two or more labelled sources, and none where the train
  part holds one), resolved against each catalog, so the same plan proves on the two-source catalog that the
  crops equal the annotated source's alone and that a cut to the unannotated source alone is
  refused as leaving nothing.
- **The plans.** grid/sweeps/synthetic.json (the synthetic bank with level maps, its labelled
  cases split between C-ArmLSpine's route and a render's under the VerSe projections' id, the
  only place the prior route and the cuts to one labelled source of several run today), real.json (catalog version 1 of C-ArmLSpine, chosen by grid/v1-version.sh --alone so that no
  other source has frames in train or validation), two_source.json
  (the catalog with VinDr-SpineXR banked beside it) and trials.json (the six trial arms of
  the design note), each the output of a block_sweep command, committed and regenerated byte for
  byte by a test, so a plan is a function of the code.
- **Predictable folders.** The run id was the hash of the commit, the catalog and the start, so
  no run could be found again from its configuration. It is now the hash of the code the run
  executes, the catalog and the run's configuration, written once to CONFIGURATION.json; a legacy
  RUN.json still validates. The code is tools/run_code.py's digest of the tracked files a run
  executes, listed by kind with the reason for each file left out and checked by
  tests/test_run_code.py against the imports, tools and scripts the code reaches, and not the
  commit: main merges many times a day, and of its 88 merges from 22 to 25 October 10 changed a
  file a sweep runs, so a run named by its commit could not be carried on after the other 78.
  RUN.json records the code's digest beside the commit the run first started on, which holds
  that code. A sweep's state is `<smoke root>/<plan>/<code 8>-<catalog sha256 8>/`, the code
  part naming the code the rows run and the plan file's bytes, so `tools/block_sweep.py state`
  prints it from the plan, the catalog and the checkout before anything runs, with
  `-e<N>` after it where the sweep was asked for N epochs in place of the plan's, each row
  under its slug, `<architecture>-<size>px-<8 hex of the row's configuration>`, with results.json,
  RESULTS.md and PROGRESS.txt at the state's root. On the grid the smoke root is
  /rs/rs_grp_oschome/go2432/smoke.
- **Resume, natively.** Three Metaflow flows carry the pipeline: BankFlow (bank then ingest, a
  branch per source), CatalogFlow (the catalog and its marker, one step since the build lock is
  held throughout) and SweepFlow (prepare, the rows with no parent as one foreach, the warm starts
  as a second, then the results). One launcher, flows/launch.py, starts them all: it names a run
  by a key of the flow, the code it runs, the parameters and what it reads beyond them (bank's
  recipes and raw copies, the sweep's plan), and before it starts a new run it resumes
  the newest run of that key that did not succeed, with Metaflow's own `resume`, which clones
  every finished step and every finished branch of a foreach and reruns only the rest (measured
  here with Metaflow 2.19.39 after an exception and after a SIGKILL, as a Slurm timeout kills a
  job). grid/02-bank-ingest.sbatch and grid/03-catalog.sbatch hand themselves to the launcher
  inside every Slurm job, so no grid route skips it, while a direct call, as the tests make, runs
  the stage as before. Inside a row, a run cut short resumes from its last epoch: the trainer
  writes train/last.pt after every epoch and `--resume` ends bit-identical on a CPU to a run that
  went through, and the flow resumes a row from its folder. A start holds the folder by a lock on
  <run>/.lock and the trainer holds train/.lock, so a second start of a row still running is
  refused in words; a row counts as finished only once it wrote FINISHED.json, its last file,
  after the ledger row and the report; a resume is held to the sha256 of its catalog, ImageNet
  file and parent, and an unreadable last.pt is moved aside to last.pt.unreadable and the row
  trains again from epoch 0.
- **What Metaflow does not cover.** Resume continues a run that did not finish; reuse across two
  finished runs, a catalog rebuilt on a new commit or an ingest on a new date, stays with the
  tools' own content addressing, whose gaps are issue #260. The fetch, stage 1, resumes its own
  downloads by its .part files.
- **Live views.** Each row's Metaflow card refreshes every fifteen seconds from the trainer's
  metrics, read with `python flows/sweep.py card server` on the grid; W&B carries each step live
  where the grid has the key; and the status word prints each plan's PROGRESS.txt right after the space tally, before
  anything its 400 lines could cut.
- **Two fixes the cover found before any GPU ran.** A training batch of one crop raises in
  BatchNorm at 32 pixels for every architecture (densenet121 at 48 too), so a last batch of one
  crop now joins the batch before it where a probe shows the model cannot train on one; nothing
  changes where it can, so version 1's training is unchanged to the bit. And the strong block,
  below.
- **The strong block.** `augment=strong` is SyntheX's strong domain randomisation (Gao, Killeen
  et al., Nat Mach Intell 5:294, 2023) with the transforms FluoroSAM adds (Killeen et al., MICCAI
  2025): up to two transforms a crop from sixteen, among them inversion, impulse noise, affine,
  contrast curves, blurs, box corruption, dropout, sharpen, emboss, pooling, multiply, a
  piecewise warp, Gaussian contrast, windowing and CLAHE, each drawn from the run's own
  generator, the two geometric ones moving the level maps. What the papers randomise, what the
  blocks had and lacked, and the caveat that their training is sim-to-real while this one is real
  frames is docs/research/strong-domain-randomisation.md.
