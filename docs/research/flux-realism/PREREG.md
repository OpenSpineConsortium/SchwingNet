# Pre-registration: FluXray reproduced from ENHANCE.PET by the paper's zero-shot edit

Source: the thread "Reproduce the FluXray dataset", 2026-10-29, on the owner's count of 02:35 UTC (three fetches, aws_enhance_pet_ct, aws_enhance_pet_labels and hf_flux2_klein_9b, and two GPU jobs, the edit and then the statistics, each after the one before it ends in exit 0) and on his words of 02:39 and 02:41 UTC that every deep learning job on the grid runs on the block-based Metaflow pipeline (flows/) under a frozen pre-registration with the CLAIM and REFORMS report enforced; the protocol is the Lab Recipe (artifacts/the-lab-recipe-1t2gvp/index.md, "Pre-register and freeze"). Label: confidential-method, as the programme's README.

This file is frozen. It is the design the reproduction runs under, written in the Lab Recipe's seven parts before any image was rendered or edited and before any number of the study was read: on 2026-10-29 only the three fetches had been sent (Slurm jobs 40860402, 40860413 and 40860425), no GPU job had been sent, and no earlier run of the edit or the statistics exists. Where README.md beside this file, section 4, differs from it, this file governs. Every departure from FleXray's recipe that the design makes is in DEVIATIONS.md beside it, under its first heading; every departure from this file after the freeze goes there too, dated, with its reason.

## 1. The question

When this project renders FluXray's own CTs at FluXray's own recorded poses and edits each render zero-shot with FLUX.2 klein-9B by the paper's recipe and filter, are the kept edits indistinguishable from FluXray's released images of the same CT and pose?

## 2. Population and inputs

- The paper: FleXray (arXiv 2609.26756v2), whose appendix on the enhanced DRRs is the recipe; schwingnet.realism.FLUXRAY holds it field by field (README section 2), and the frozen block below fixes it by value, the prompt by its sha256.
- FluXray: the folder FluXray/ of the Hugging Face dataset VictorButoi/flexray-data (the fetch row hf_flexray_data), 138,063 images at 256 by 256 in a ThunderDB with samples.csv, each sample's subject and pose; read through FleXray's own split reader (fxr 1.0.2).
- The CTs and their truth: ENHANCE.PET 1.6k (Science Data Bank doi:10.57760/sciencedb.34150; the public bucket enhance-pet-1-6k, imaging-data/images/CT and imaging-data/ground-truth, the fetch rows aws_enhance_pet_ct and aws_enhance_pet_labels), the CTs and MOOSE labels FluXray was rendered from. The Vertebrae, Ribs and Peripheral-Bones labels are packed into FleXray's MOOSE profile (grid/enhance-pet-labels.json, the bucket's labels.json).
- The edit model: black-forest-labs/FLUX.2-klein-9B (the fetch row hf_flux2_klein_9b), the model the paper names; no other klein stands in, and the run refuses where it has not landed.
- The filter and the flexray feature space: FleXray's released weights (VictorButoi/flexray, the fetch row hf_flexray_weights), member flux000. The ImageNet feature space: torchvision's ResNet-18 weights, resnet18-f37072fd.pth.
- Files and hashes: the data had not landed at the freeze, so the hashes are taken at the start of the run, before any GPU work, by `tools/realism.py inputs`: the sha256 of every file of the klein weights, of the FleXray bundle and of the ThunderDB, of samples.csv and of the ResNet weights, and the versions of the pinned packages, refused where a pin differs; each CT's and each truth file's sha256 is written beside each render in the render's manifest. The inputs record's own sha256 is in the run's record.
- Eligibility: a FluXray subject is eligible where it has at least one sample in the ThunderDB at a pose on the paper's grid, a landed CT and a landed Vertebrae truth file. Exclusions, each counted in the run's record: samples whose recorded pose is off the paper's 90-pose grid or off axis (x, beta or gamma not zero), since the paper used none; samples samples.csv names that the ThunderDB lacks, since FluXray's image of them cannot be read; subjects with no landed CT or vertebra truth, since they cannot be rendered. Fewer than the plan's 100 eligible subjects refuses the run before any GPU work.
- The draw: 100 eligible subjects by schwingnet.realism.draw with the draw seed and the purpose `subject`, a rank by sha256 that no other subject's presence moves; for each drawn subject, 4 of its eligible samples by the same seed and the purpose `pose|<subject>`; so 400 samples. Each render is edited in two seed arms, the seed of each schwingnet.realism.seed_for(subject, grid pose, arm), so 800 edits. The subjects are worked in shards of 10, one shard a step of the flow, which changes no number.

## 3. The measurements

- The render: fxr.drr.render_drr at the pose's source height y, table offset z and rotation alpha, SDD 1250 mm, 0.6 mm pixels, 1024 by 1024, the isocentre at the volume's centre, the CT clamped to -1000 to 2000 HU with air at or below -900 HU set to -1000, 500 samples a ray; the MOOSE labels projected as exact masks at the same pose.
- The edit: Flux2KleinPipeline with klein-9B, 4 steps, guidance 1.0, bfloat16, the paper's prompt byte for byte, the edited pixels zeroed where the raw render is below 0.05, at 1024.
- The paired filter: the flux000 member's soft Dice of each edit and of its raw render against the exact masks at FleXray's 256-pixel canvas, over the channels with any truth and a background channel; within each grid pose, delta = SoftDice(edit) - SoftDice(raw), and an edit is kept where delta is at least 2 x median - q0.98 of its pose group (schwingnet.realism.keep_cutoff), over every shard's edits at once.
- The comparison images: every set brought to FleXray's canvas, zero-padded to a square, resized to 256 by Pillow's bilinear filter and windowed to its own 0.5 and 99.5 percentiles.
- The feature spaces, three: physics, handcrafted (a 32-bin intensity histogram, a 16-band radial power spectrum, gradient statistics, noise and local contrast); flexray, the flux000 member's channel probabilities and areas; imagenet, ResNet-18's 512 pooled features.
- In each space, between set A and set B, features standardised together: a two-sample classifier test, the 5-nearest-neighbour score of each image with every image of its own subject left out of its neighbours in both sets, its AUC with a 200-draw bootstrap interval over subjects and a 200-permutation p with labels shuffled within each subject both sets hold and whole subjects moved among the rest; the unbiased MMD with a Gaussian kernel at the median distance on 64 principal components, with a 200-permutation p under the same shuffle; FD64 and KID64 on the same 64 components (KID over 10 subsets of 100). The seed of the statistics is 20261029.
- The nulls: set B's subjects dealt into two halves against each other; and, where set A holds two seed arms, arm 0 against arm 1.
- The paired readings, where a sample is in both sets: PSNR, a global SSIM and the phase-correlation shift in pixels at 256.
- The comparisons, two: the kept edits against FluXray's images of the 400 drawn samples (the primary), and the raw renders of the same 400 samples against the same FluXray images (the positive control and the geometry check). The kept edits are also read arm by arm against FluXray.
- Recorded and described, not tested: the share of edits the filter drops, against the paper's about 4 percent; each lumbar body's superior endplate angle from the exact 1024 mask and from its 256 block-majority copy (tools/realism.py measure).

## 4. The hypotheses and their bars

- The primary hypothesis: the kept edits are not separable from FluXray in any space. Each space's word is schwingnet.realism.verdict over its AUC interval and its MMD q (Benjamini-Hochberg over the three spaces): separable where the AUC's lower bound is above 0.6; matched where the MMD's q is at least 0.05 and the AUC's upper bound is no higher than the larger of 0.5 and FluXray's split-half upper bound; indistinguishable where the q is at least 0.05 and the lower bound at most 0.6; undecided where the two tests disagree. A space whose seed arms, each read alone with its own q over the spaces, give different words is undecided (schwingnet.realism.arm_verdict); so is a space whose split-half null or arm null is itself separable (schwingnet.realism.through_nulls). The kept edits' word is the worst over the spaces.
- The positive control: the raw renders are separable from FluXray in at least one space, the edit being what FluXray adds to a render.
- The replication's one word, schwingnet.realism.replication_word: not reproduced where the kept edits are separable in a space; untestable where they are not and the raw renders are separable in no space; reproduced where the kept edits are matched or indistinguishable in every space and the control is separable; undecided otherwise.
- The geometry: the median phase-correlation shift between each raw render and FluXray's image of the same sample is at most 1 pixel at 256 (schwingnet.realism.GEOMETRY_SHIFT_PX), which is 1.2 to 2.2 mm at the isocentre by the source height.
- The bars of 0.6 on the AUC's lower bound and 0.05 on the MMD's q are conventions fixed by this programme's design on 2026-10-25 and 2026-10-26 and shared with the DRR domain-gap study, before any number; the 1-pixel bar of the geometry is one pixel of FleXray's canvas; none is a published value or the result of a power calculation, and 100 subjects is the plan's figure of 2026-10-26, not a powered size (DEVIATIONS.md).

## 5. What counts as failure

- Of the replication: the word "not reproduced". The sentence is "this project's renders of FluXray's CTs, edited by the paper's recipe and filter, are separable from FluXray's images of the same CT and pose in <space> (AUC <a>, interval <lo> to <hi>; MMD q <q>), so the published recipe as read here does not reproduce FluXray".
- Of the test: the word "untestable". The sentence is "the raw renders could not be told from FluXray in any space either, so this test at 400 samples of 100 subjects cannot say whether the edit reproduced FluXray".
- Of the pipeline: a null that is separable. The sentence is "in <space> the <split-half or arm> null was separable (AUC lower bound <x>), so the space's word is undecided and its numbers are not read".
- Of the geometry: a median shift above 1 pixel. The sentence is "the raw renders sit <s> pixels from FluXray's images of the same sample, so the poses or the intrinsics are not the paper's, and every texture comparison is read as one of different views".

## 6. The analysis plan

- Primary: the replication word and the kept edits' table, one row per space, in the stats report of the flow's stats stage. Secondary, read as description: the per-arm words, the raw renders' table, the paired readings, the filter's dropped share against the paper's, and the endplate angles at 1024 and 256.
- Held out: no model is trained in this count, so no set is held out from training; the 70/30 split by subject that tools/realism.py split writes is for a later adapter and changes nothing here. The classifier test's neighbours never include an image of the same subject, in either set, so a CT's own views do not make two sets look alike.
- Blind: no person reads an image; the words are computed by schwingnet.realism from the numbers and printed by the report, so no reader chooses them.
- Not in this count, and not read here: a comparison with real X-rays or fluoroscopy, which is the DRR domain-gap study's; the adapter (the lora and eval stages), which waits for its own count and for its port to the pipeline.
- Known limits, listed before the run: the paper's filter used a U-Net trained on raw DRRs alone, which was not released, and flux000 stands in; the paper gives no seeds; the filter's pose groups hold about 9 edits here against about 1,534 in FluXray, so the q0.98 cut-off is noisier and the dropped share is read against the paper's as description only; FluXray's images were stored at 256, so every comparison is at 256 although the edit runs at 1024.

## 7. Freeze

Frozen on 2026-10-29 by the session of the thread named above, on the branch claude/project-thread-bft0k4, before any image was rendered or edited and before any number of the study was read. No further edits: a departure goes in DEVIATIONS.md, and a second design is a new file with its own freeze. The flow's first step checks this file against PREREG.md.sha256 and refuses with exit 90 where it moved, then checks the block below against schwingnet.realism.frozen_lines() and refuses where the code that runs and this file differ.

```frozen
recipe.model = klein-9b
recipe.steps = 4
recipe.guidance = 1.0
recipe.dtype = bfloat16
recipe.render_pixels = 1024
recipe.render_sdd_mm = 1250.0
recipe.render_spacing_mm = 0.6
recipe.isocentre = volume-centre
recipe.stored_pixels = 256
recipe.foreground_floor = 0.05
recipe.filter_quantile = 0.98
recipe.prompt_sha256 = 59b4507de6d34466a785de4c7e091b1f3554d27b8096c5ea79f45213ea25dfd2
recipe.pose_grid_sha256 = c93125c4bc4eb2525df078e0886a919005e85a7be22d06794a67151d9b1cde01
plan.subjects = 100
plan.poses_per_subject = 4
plan.arms = 2
plan.draw_seed = 20261025
plan.shard_subjects = 10
plan.ray_samples = 500
plan.hu_low = -1000.0
plan.hu_high = 2000.0
plan.air_clamp_hu = -900.0
plan.stats_seed = 20261029
plan.canvas = 256
plan.percentile_low = 0.5
plan.percentile_high = 99.5
plan.physics_bins = 32
plan.radial_bands = 16
plan.pca_components = 64
plan.knn = 5
plan.bootstraps = 200
plan.permutations = 200
plan.kid_subset = 100
plan.kid_repeats = 10
verdict.chance_auc = 0.5
verdict.indistinguishable_auc = 0.6
verdict.mmd_alpha = 0.05
verdict.geometry_shift_px = 1.0
spaces = physics,flexray,imagenet
pins = diffusers==0.42.0 transformers==5.20.2 accelerate==1.15.0 peft==0.21.2 safetensors==0.8.0 huggingface_hub==2.3.0 flexray==1.0.2 lmdb==3.0.0 nibabel==5.3.2
```
