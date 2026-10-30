# DATA brief: contract.json, the block manifests and the templates

Read SPEC.md first (sections 3-9 and 12-13 are your format). Every fact in a manifest's text or card comes from
a file in /home/user/SchwingNet (cite paths in `card.from` for sources, and keep `today` and `implemented_by`
true: every path in implemented_by must exist on this branch). Write plain, short English. No number you cannot
point to a file for: write "not recorded" instead. ASCII only.

The maps of the current pipeline, already checked, are in
/tmp/claude-0/-home-user/206a277d-964b-5bb3-aa9c-da388af0178c/scratchpad/map/ (map_blocks.json, check_blocks.json,
map_grid.json, check_grid.json, map_door.json, map_panel.json, check_panel.json, map_look.json): read them before
the code; they cite file:line for every fact below.

Facts to build on (verify each where you use it):
- Training blocks: src/schwingnet/blocks.py (18 fields, CHOICES, SETTINGS, problems(), RULES). Version 1 defaults:
  normalise none, augment [], optimiser adam, weight_decay 0, schedule constant, warmup_epochs 0,
  backbone_lr_scale 1, sampler uniform, loss_weights none, select accuracy, samples all, sources [], per_person 0,
  architecture resnet18, denoise none, prior none, prior_weight 0, segmenter spineps.
  Choices: normalise none|imagenet; optimiser adam|adamw; schedule constant|cosine; sampler uniform|balanced;
  loss_weights none|inverse-frequency; select accuracy|balanced-accuracy; samples all|only-sources|drop-sources|
  cap-per-person; architecture resnet18|resnet34|resnet50|mobilenet-v3-small|efficientnet-b0|densenet121|
  se-resnet50|se-resnext50; denoise none|gaussian|median; prior none|level-map; augment any of
  box-jitter|intensity|blur|noise|strong. Rules: weight_decay > 0 only with adamw; prior_weight > 0 iff
  prior=level-map; sources non-empty iff samples only-sources or drop-sources; per_person >= 1 iff
  samples=cap-per-person; 0 < backbone_lr_scale <= 1. Hidden bound: warmup_epochs at most 100000 (lr_factor,
  blocks.py:331-333); counts at most 6 digits.
- The experiment route (the one live route): an issue labelled experiment (tools/experiments_panel.py issue_body),
  .github/workflows/experiment.yml, the owner's click on the gate word schwingnet-experiment-<issue>, one GPU job
  grid/experiment-driver.sbatch -> flows/launch.py experiment under docs/research/experiments/PREREG.md. It takes
  recipe, epochs 1..200, seed, hours (0, 48], and the block words. Only resnet18 runs (the grid holds only its
  ImageNet file; the driver refuses others); the crop size is the trainer's default 64 (no --size is passed);
  the catalog version is chosen by grid/v1-version.sh. Train and evaluate run in the same GPU job.
- Crops: tools/train.py crops each labelled box to size x size grey (convert("L")) and repeats to 3 channels for
  the network; --size defaults to 64. Levels: 27 classes (src/schwingnet/catalog.py LEVELS: C1-C7, T1-T13,
  L1-L6, sacrum).
- Recipes: data/recipes/*.json (commercial admits open; commercial-share-alike open, share-alike;
  non-commercial open, share-alike, non-commercial; research-internal open, share-alike, non-commercial,
  agreement, no-derivatives). data/licences.json classes each source.
- Flows (flows/registry.txt): bank, catalog, sweep, v1, experiment, latency, drr_gap, drr_seg, realism, totalseg
  (all on main); autoanatomist only on the unmerged PR #483 (branch claude/project-thread-f0dity, readable with
  git show origin/claude/project-thread-f0dity:<path> if the ref is fetched; else rely on map_blocks.json).
- Gate words (grid/gate.sh WORDS): start status leaks v1 latency fetch explore dropzip unpack nodequota folders
  samples sweep bank experiment bench anomaly bordercall census totalseg realism morphometry literature stop
  cancel. Memory lines in docs/memory/MEMORY.md give the gold tier 3 CT counts (1,733: ENHANCE.PET 1,558, VerSe
  21, TotalSegmentator 154), the morphometry word's sets (enhance, verse), bordercall complete, totalseg
  complete, the realism flow, the DRR study, latency (97 ms budget, ONNX parity).
- Render blocks: src/schwingnet/render_blocks.py (views 1-100, detector 32-1024, ray_samples 16-4000, presets
  default, flexray, physical, physical-ct, fluxray-raw).

## Blocks (ids fixed; write one manifest each; 30 in all)

Use the glyph given. "today" is what runs it now; be exact. Keep `generic` honest about what the code does
today, with `why` saying what it would take to widen it.

Sources (stage source; no input; one output "data"; card required):
- catalog_v1 (glyph catalog): the versioned frame catalog the experiment route trains on; type data
  N,C,H,W with C=1, uint8, targets level, classes 27, parts train/validation/test (person-keyed split under
  data/splits/), persons true, modality mixed, licence uncut. today live, route experiment. experiment {}.
- gold3_ct (ct): the gold tier 3 CT store (1,733 CTs); N,C,D,H,W, C=1, int16, targets mask, classes 28 (the
  canonical ids of the anomaly pack, verify), parts [] (not split), persons true, modality ct, licence uncut.
  today word "census gold3" (verify), experiment null.
- carmlspine_sweeps (video): the held-out C-ArmLSpine fluoroscopy sweeps of the demo (case134, case39); N,T,C,H,W,
  C=1, uint8, targets level, parts [test], held out; today flow (latency), experiment null.
- folder_import (folder): your own folder on the grid, entered as a data card (params for rank 2|3, channels,
  targets, licence class); code planned; today planned (it waits for the bank and catalog steps:
  tools/ingest.py, BankFlow, CatalogFlow); experiment null.
- synthetic_catalog (synthetic): block_sweep's synthetic catalog for smoke tests (600 frames, 40 cases, verify
  in tools/block_sweep.py); N,C,H,W C=1 uint8 level 27 parts all; today flow (sweep, plan synthetic);
  experiment null.

Prepare (stage prepare):
- recipe_cut (recipe): param recipe (choice of the four recipe names), op cut @param.recipe; experiment
  {"recipe": "@param.recipe"}; today live.
- samples_select (samples): params samples, sources (names), per_person (int 0..999999); the four rules as
  rules; experiment blocks samples, sources, per_person; today live.
- crop_boxes (crop): param size (int 32..512, default 64); ops size H and W to @param.size; experiment {"only":
  {"size": [64]}}; generic rank [2] (the trainer crops 2-D boxes); today live.
- normalise (normalise): param normalise none|imagenet; experiment blocks normalise; live.
- denoise (denoise): param denoise none|gaussian|median; experiment blocks denoise; live.
- segment_ct (segment): CT volumes -> the same volumes with masks (targets mask); param segmenter
  spineps|moose|totalsegmentator (verify which exist: the totalseg flow, drr_seg runs MOOSE, SPINEPS masks
  exist); GPU; today flow (drr_seg / totalseg, fixed plans); experiment null.
- render_drr (render): CT volume -> 2-D DRR images (drop_axis D); params views 1..100, detector 32..1024,
  ray_samples 16..4000, preset (the five presets); modality drr; GPU; today flow (drr_gap / drr_seg); null.
- realism_edit (realism): FLUX.2 klein realism edit of DRRs (GPU); today flow (realism, fixed plan);
  experiment null.

Split (stage split):
- split_person (split): unsplit data -> parts train/validation/test by person; params validation_share,
  test_share, salt; code existing where the catalog does it (cite), today flow (catalog); experiment null.
- split_anomaly_aware (splitFamilies): the anomaly-aware split (normal spines first; anomaly families across
  train and test, never validation); code planned; today planned; experiment null.

Augment:
- augment (augment): param augment (set of the five); experiment blocks augment; live.

Model (stage model; input data, output model; `resolve` text required):
- classifier (network): param architecture (the 8), weights imagenet|none; ops kind model, set family
  @param.architecture; experiment {"blocks": {"architecture": "@param.architecture"}, "only": {"architecture":
  ["resnet18"], "weights": ["imagenet"]}}; generic rank [2], channels any, sizes any (adaptive pooling), why:
  2-D torchvision and MONAI nets today, grey tiled to 3 channels; live.
- classifier_3d (network): a 3-D classifier built from the volume's type (MONAI 3-D nets); code planned.
- level_prior_head (prior): model -> model with the training-only level-map head; param weight float above 0;
  experiment blocks {"prior": "level-map", "prior_weight": "@param.weight"}; live.
- annealer_unet (unet): the auto-anatomist network, a swappable block: architecture residual-unet|plain-unet|
  probe, widths, groups (verify the TABLE in map_blocks.json); input data rank 3; today pending (#483).

Train:
- train_classifier (train): input model; output checkpoint (trained true); params optimiser, weight_decay
  (float 0..1), schedule, warmup_epochs (0..100000), backbone_lr_scale (above 0, max 1), sampler,
  loss_weights, select, epochs (1..200, default 20), seed (0..999999999, default 1), hours (0.1..48,
  default 4); rules; reads train and validation; job gpu hours @param.hours; seeded by seed; experiment epochs,
  seed, hours and the blocks fields; live.
- train_annealer (train): the auto-anatomist trial (schedule lambda-then-w|joint|w-first|fixed, objective,
  naming, epochs up to 1000, batch up to 64, seed); array true; today pending (#483).

Calibrate:
- calibrate_temperature (calibrate): temperature scaling fitted on validation; code planned (cite
  bordercall's rule selection only as a note, no number); job none or cpu.

Select (stage select, joins the arms):
- select_on_validation (select): picks one arm by its validation score, never test (the experiments PREREG
  says the next combination is chosen on validation only; tools/block_sweep.py ledger); reads validation.

Evaluate:
- evaluate_heldout (evaluate): checkpoint (+ optional data, a second held-out set) -> metrics with Wilson
  intervals and witness frames (tools/evaluate.py); reads test; job gpu with_upstream true (it runs in the
  training job on the experiment route); experiment {}; live.
- latency_onnx (latency): ONNX parity and measured latency against the 97 ms budget (flows/latency.py);
  today flow (latency word); experiment null.
- domain_gap (gap): the calibrated separation tests of synthetic DRRs against real frames (tools/domain_gap.py,
  drr_gap flow); two data inputs; today flow; experiment null.

Analyse:
- morphometry (morphometry): bordercall's morphometry engine over masks -> a table (axes N,F); CPU; today word
  "morphometry enhance|verse"; experiment null.
- bordercall_naming (naming): naming the levels from C2 over masks (bordercall); CPU; today word "bordercall";
  experiment null.

Report:
- report_claim (report): the CLAIM 2024 and REFORMS report every launched flow writes at its end
  (flows/stage.py, tools/report.py); experiment {}; today live (it rides with every flow).
- wandb_log (wandb): W&B online or offline push (docs/memory/evaluation-and-wandb.md); experiment {}; live.
- model_card (card): the model card MODEL.md (tools/train.py writes it); experiment {}; live.

## Templates (tools/sandbox/templates/<id>.json; `expect` pins what compile must give)

- experiment_v1: catalog_v1 -> crop_boxes -> normalise -> augment -> classifier -> train_classifier ->
  evaluate_heldout -> report_claim, all defaults. Experiment route, ready, 1 request, 1 GPU submission.
- screen_arms: the same chain with augment varied over [] and ["strong"] and train_classifier's optimiser varied
  over adam and adamw, epochs 20 (the owner's rule: every arm a block, screened in parallel on short runs).
  4 requests, 4 GPU submissions.
- latent_prior: the latent shape prior evaluation of pipeline.html, built from blocks: gold3_ct -> morphometry
  -> ... Rebuild pipeline.html's structure as honestly as the blocks allow (read pipeline.html's PIPE and N);
  route pipeline; pin its counts in expect.
- ct_to_xray: gold3_ct -> segment_ct -> render_drr -> realism_edit -> split_person -> crop_boxes -> augment ->
  classifier -> train_classifier -> evaluate_heldout (its second input catalog_v1 for the real test frames) ->
  latency_onnx -> report_claim. Route pipeline.
- drr_gap: gold3_ct -> segment_ct -> render_drr -> domain_gap (second input catalog_v1) -> report_claim.
- morphometry_gold3: gold3_ct -> morphometry -> report_claim (CPU only).
Each template has a layout (x in steps of 300, y in steps of 150, starting 40, 40) and an `about` paragraph.

## contract.json

Write the words: stage titles and what each stage does, kind meanings, probes (SPEC.md section 3), and the 13
requirements in plain words (the import dialog shows them to whoever writes a block).
