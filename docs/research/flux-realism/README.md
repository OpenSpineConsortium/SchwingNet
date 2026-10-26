# The Flux realism programme: FluXray reproduced, measured and finetuned

Source: the thread "Finetune Flux Realism for X-rays", 2026-10-25 to 2026-10-26, the owner's ask of 2026-10-25 23:2x UTC ("find and implement CSAIL's trained version of Flux realism ... reproducibly create a finetuned instance of Flux realism which generates numerically indistinguishable X-rays as the HF dataset, you can iterate on, address these issues particularly resolution"), with the FleXray paper's source (arXiv 2609.26756v2, uploaded by the owner on 2026-10-26 00:28 UTC) read as the record. Confidential-method: this file names what the project renders, measures and trains; the public side (what CSAIL released, the recipe as published, the licences, the tooling) is symphony-template's docs/research/flux-realism-for-xrays-2026-10-25.md.

Where it stands: the code is written and tested (schwingnet.realism, tools/realism.py, grid/realism.sbatch, the gate word `realism <stage>`, the fetch rows); nothing has run on the grid and no count has been given. The owner's word and count are asked for once, as a decision card, with the recommendation in section 7.

## 1. What exists and what does not

There is no CSAIL-trained realism model. The paper's "Enhanced DRRs is a dataset of DRRs pre-rendered from MOOSE and refined with the diffusion model flux.2-klein-9b" means, by its own appendix (main.tex, the section labelled appendix-dataengine-enhanced-drrs), that FLUX.2 klein-9B was run as released, zero-shot, "requires no task-specific fine-tuning". What is released and what is not:

| Released | Where | Licence |
| --- | --- | --- |
| FleXray's weights, five members (flux000, flux025, flux0375 the flagship, flux050, flux075) | VictorButoi/flexray (the fetch row hf_flexray_weights) | CC BY-NC 4.0 |
| FluXray, the enhanced DRRs: 138,063 images at 256 by 256 as float16 in a ThunderDB, masks, samples.csv with each image's pose (y, z, alpha; x, beta, gamma zero) | VictorButoi/flexray-data, folder FluXray/ (the fetch row hf_flexray_data, 19 GB) | CC BY-NC 4.0 as a collection |
| The code: fxr.drr's renderer, the MOOSE label profile, the inference canvas | pip flexray 1.0.2, MIT | MIT |
| The CTs FluXray was rendered from: ENHANCE.PET 1.6k, 1,683 whole-body CTs with MOOSE labels | the public bucket enhance-pet-1-6k (the fetch rows aws_enhance_pet_ct, 177 GB, and aws_enhance_pet_labels, 2.5 GB) | CC BY 4.0 for three sites, CC BY-NC 4.0 for two; the strictest binds the set |

Not released: the edit script and its seeds; the edits at 1024 pixels (only the 256-pixel downsample is stored); the filter's U-Net, "trained only on raw DRRs" (FleXray's flux000 member, trained on 0 percent enhanced DRRs but on real X-rays too, is the nearest public stand-in); the FLUX.2 klein-9B weights themselves are Black Forest Labs' (black-forest-labs/FLUX.2-klein-9B, FLUX Non-Commercial License, a click-through on the hub).

## 2. The recipe as a record

schwingnet.realism.FLUXRAY holds the paper's settings field by field, and recipe_problems says in words when a recipe leaves what exists:

| Field | The paper | Ours |
| --- | --- | --- |
| model | flux.2-klein-9b | klein-9b where its weights are landed, else klein-4b (Apache-2.0), named in the report |
| steps, guidance, dtype | 4, 1.0, bfloat16 | the same |
| prompt | five sentences, verbatim in realism.PROMPT | the same, byte for byte |
| poses | 90: y in {650, 900, 1150} mm, z in {-300 ... 200} mm, alpha in {0, +-45, +-90} degrees; x, beta, gamma zero | read from samples.csv and checked against the grid (tools/realism.py poses); a recorded pose off the grid is reported, never rendered |
| intrinsics | SDD 1250 mm, 0.6 mm pixels, 1024 by 1024, isocentre at the volume's centre, default attenuation | the same, through fxr.drr.render_drr with the CT's own MOOSE labels projected as exact masks |
| foreground filter | edited pixels zeroed where the raw DRR is below 0.05 | the same |
| paired filter | delta = SoftDice(raw) - SoftDice(flux) per pose group, kept when delta is at most 2 median - q0.02 ("empty labels ignored and background included"), about 4 percent dropped | the same rule (realism.keep_cutoff, realism.kept), the soft Dice over the channels with any truth plus a background channel read as what no channel claims, scored by the flux000 member in place of the unreleased raw-only U-Net; the share dropped is reported against the paper's 4 percent |
| seeds | not given | realism.seed_for(subject, pose, arm): a digest, so a rerun draws the same noise, and a second arm draws another |
| stored size | 256 | our edits are kept at the render's size (1024) and brought to 256 only for the comparison |

Two of these are deviations, named in every report: the filter's model and the seeds. A third is a choice: the CTs. FluXray's samples.csv names subjects; whether its subject ids are ENHANCE.PET's study numbers (0001 to 1683) is checked when the data lands (tools/realism.py poses lists the subjects; a subject with no CT is passed over and counted).

## 3. Resolution first

FluXray exists at 256 pixels and FleXray reads at 256 pixels (its inference canvas), while the edit ran at 1024. What that costs, from realism.measurement_rows, with the source at each of the three heights and the detector at 1250 mm:

| pixels | SOD mm | magnification | pixel at the isocentre mm | a 45 mm endplate in pixels | one pixel of rise in degrees |
| --- | --- | --- | --- | --- | --- |
| 256 | 650 | 1.923 | 1.248 | 36 | 1.59 |
| 256 | 900 | 1.389 | 1.728 | 26 | 2.20 |
| 256 | 1150 | 1.087 | 2.208 | 20 | 2.86 |
| 1024 | 650 | 1.923 | 0.312 | 144 | 0.40 |
| 1024 | 900 | 1.389 | 0.432 | 104 | 0.55 |
| 1024 | 1150 | 1.087 | 0.552 | 82 | 0.70 |

So the review's second limitation ("released masks 256 by 256 too coarse for measurement") is a number: a lumbar endplate at 256 pixels is 20 to 36 pixels wide and one pixel of rise is 1.6 to 2.9 degrees, above the degree a Cobb or a disc angle is read to; at 1024 it is 0.4 to 0.7 degrees. Three consequences for the design:

- The edit stage renders and edits at 1024 and keeps the edits at 1024; only the comparison with FluXray drops to 256, since nothing larger of FluXray exists.
- The measurement study (tools/realism.py measure, run in the edit stage) reads each lumbar body's superior endplate angle from the exact 1024 mask and from its 256 block-majority copy, and reports the difference; it is the floor any 256-pixel segmentation stands on, read from truth rather than from a model.
- A LoRA whose target is FluXray trains at 256, since its targets are 256 (tools/realism.py pairs takes the target's size and never upsamples); a LoRA whose target is the teacher (our own klein-9b edits at 1024) or real X-rays trains at 1024. The plan's target field says which, and the report names the size.

## 4. The measurement

The owner's words, "numerically indistinguishable", are made a pre-registered test rather than a picture. Every set is brought to FleXray's canvas (zero-padded to a square, bilinear resize to 256, the 0.5 and 99.5 percentile window, as fxr's preprocessing does) and read in three feature spaces:

- physics: what a radiographer would read, handcrafted (intensity histogram, radial power spectrum, gradient statistics, noise, local contrast), 57 numbers;
- flexray: the flux000 member's channel probabilities and areas, FleXray's own reading;
- imagenet: a ResNet-18's pooled features from torchvision's published weights (resnet18-f37072fd.pth under $MODELS, left out with a note where the file is absent).

In each space, between set A (ours) and set B (FluXray): a two-sample classifier test (5-nearest-neighbour scores with the sample's own subject left out, the AUC with a bootstrap interval over subjects and a permutation p with subjects permuted whole), an RBF MMD at the median bandwidth with its permutation p, and Frechet and kernel distances on 64 pooled principal components; set B against its own split halves gives the null every number is read against. The MMD's p-values are read at their Benjamini-Hochberg q over the spaces, as the DRR domain-gap study (#401) reads them, so one space's rejection among three counts at the family's level. realism.verdict turns the interval and the q into one of four words per space: separable (the interval's low end above 0.6), matched (q at least 0.05 and the interval's high end no above FluXray's own split halves), indistinguishable (q at least 0.05, the low end at most 0.6), undecided (the tests disagree); the worst word over the spaces heads the report. Where two sets share sample names (our raw DRR and FluXray's enhanced one at the same subject and pose), the paired metrics are added: PSNR, a global SSIM and the phase-correlation shift, which say whether the geometry is the paper's before anything about texture is read.

The review's limitations 3 to 5, in the design:

- 3, high probability is not correctness: no probability is trusted as truth anywhere; the filter's Dice is against exact masks projected from the CT's labels, and in the flexray space the probabilities are features of the image, not judgements of it.
- 4, segmentation is not endplate detection: the measurement study reads endplate angles from the exact masks at both sizes (section 3), so the floor is known before any model is asked to find an endplate; the comparison asks nothing of a segmentation.
- 5, eight-pass test-time augmentation gave no gain: the edit runs in two seed arms; arm 0 against arm 1 is a second null, and a verdict that changes with the arm is reported as undecided rather than as a result.

## 5. The adapter

The pre-registered plan is schwingnet.realism.LoraPlan: base klein-base-4b (black-forest-labs/FLUX.2-klein-base-4B, Apache-2.0, undistilled, so the adapter is the project's to keep and to sell), rank 16, alpha 16, learning rate 1e-4, 2000 steps at batch 1, resolution 1024 or the pairs' size, AdamW 8-bit, cosine schedule, a save every 250 steps, seed 20261025; lora_problems says in words when a plan leaves what the trainer takes. The trainer is ostris/ai-toolkit (MIT) at commit 73ebae13a468942ded8b47991b5d56eeeea25c36, its edit-LoRA path (arch flux2_klein_4b, a control folder beside the target folder, the prompt as every caption), run as `python run.py <config>` from the configuration realism.lora_config writes. The pairs are the training split's subjects alone (tools/realism.py split: 70 percent of the subjects by a seed, by subject and never by image), and every number of the adapter is read on the evaluation split's subjects.

Three targets, in the plan's target field: fluxray, FluXray's own image of the same subject and pose, the owner's ask, trained at 256; teacher, our own klein-9b zero-shot edit at 1024, which keeps the resolution and asks whether a 4B base with an adapter reproduces the 9B's edit; real, the project's own real frames, which needs no FluXray and is the one that matters for the clinic, left for the owner's word on which frames.

## 6. The grid

The word is `realism <stage>` (grid/gate.sh, grid/realism.sbatch, each stage one GPU job, 12 hours at most, never requeued, the checkout held while it runs):

| stage | what it does | inputs it is refused without |
| --- | --- | --- |
| edit | poses from samples.csv; the subject split; raw DRRs of REALISM_SUBJECTS (100) subjects at REALISM_PER_SUBJECT (4) poses each with exact masks; the klein edit in REALISM_ARMS (2) seed arms; the paired filter; FluXray's images of the same subjects exported; the endplate measurement | klein weights (hf_flux2_klein_4b or hf_flux2_klein_9b), hf_flexray_weights, hf_flexray_data, aws_enhance_pet_ct, aws_enhance_pet_labels |
| stats | the metric suite of the kept zero-shot edits and of the raw DRRs against FluXray | the edit stage's report ending in exit 0 |
| lora | the pairs of the training split, the configuration, one LoRA on klein-base-4b, the evaluation split edited through it (REALISM_TARGET fluxray or teacher; REALISM_BASE_STEPS 28 and REALISM_BASE_GUIDANCE 4.0 for the undistilled base, the two numbers to tune) | the edit report; hf_flux2_klein_base_4b |
| eval | the metric suite of the LoRA edit and of the zero-shot edit against FluXray on the evaluation split | the lora report |

Each report, logs/REALISM-<stage>.md, carries counts, the verdict words, digests and the commit; the next send of the same word prints it and queues nothing, so each stage runs once on the owner's word. The public packages (diffusers 0.42.0, transformers 5.20.2, accelerate 1.15.0, peft 0.21.2, safetensors 0.8.0, huggingface_hub 2.3.0, flexray 1.0.2, lmdb 3.0.0, nibabel 5.3.2) go into a throwaway environment beside train-gpu's, never into pixi.lock; the trainer's requirements into one of their own.

## 7. Counts, for the owner's word

Nothing below runs without the owner's word and the number. Every fetch reads its exact size from its source before a byte lands and is refused whole when it would pass the quota (grid/size-rule.sh); the figures here are the sources' own.

Recommended: six fetches and four GPU jobs.

- fetch hf_flux2_klein_4b (about 17 GB by the hub's file list, Apache-2.0) and fetch hf_flexray_data (19 GB, the FluXray folder alone; the DRR domain-gap study #401 asks for the same row, so it goes once, whichever thread sends it);
- fetch aws_enhance_pet_ct (177 GB) and fetch aws_enhance_pet_labels (2.5 GB), the public bucket, no token;
- fetch hf_flux2_klein_base_4b (about 17 GB, Apache-2.0), for the lora stage;
- fetch hf_flux2_klein_9b (about 30 GB, FLUX Non-Commercial License): only after the owner has accepted the licence on the model's hub page under the account whose token the grid holds, since the hub refuses the download otherwise; the edit stage runs with the 4B where the 9B is absent and says so;
- realism edit, realism stats, realism lora, realism eval: four GPU jobs, in that order, each once the one before it has ended in exit 0.

Not recommended now: a full-scale run (every FluXray subject, 138,063 edits), which is the paper's own compute and adds nothing to the verdict a hundred subjects give; a LoRA on klein-base-9b (hf_flux2_klein_base_9b), until the 4B's verdict is read.

## 8. Licences, for the owner's decision (item 15 of #391), never a blocker

- FLUX.2 klein-9B and klein-base-9B: the FLUX Non-Commercial License, which covers the weights and the outputs made with them for non-commercial use; a model trained on those outputs inherits the question. FLUX.2 klein-4B and klein-base-4B: Apache-2.0, no such question.
- FluXray: CC BY-NC 4.0 as a collection. An adapter trained with FluXray's images as targets is a derivative work of them and is non-commercial; so is a network trained on FluXray, which is why no FluXray image enters a SchwingNet network (the fetch row says so).
- ENHANCE.PET 1.6k: three sites CC BY 4.0 (Leipzig, Careggi, UC Davis), two CC BY-NC 4.0 (autoPET, Tuebingen), by the bucket's CT-details.xlsx; as one set it is non-commercial (data/licences.json, class non-commercial since this pull request), and DRRs, edits and adapters made from it are too, unless a per-site split keeps the three open sites apart, which the render can do by study id once CT-details.xlsx is read.
- The teacher target, our own klein-9b edits: outputs of a non-commercial model. The real target: the project's own frames, under their own agreements (docs/research/training-data-licences.md).
- The commercial path, if the owner wants one: klein-base-4b as the base, the three open ENHANCE.PET sites as the CTs, the teacher replaced by klein-4b's own zero-shot edits, and FluXray used only to measure, never to train.

## 9. How to run, and what comes back

In order, each on the owner's word: the fetches (section 7), then `realism edit`, `realism stats`, `realism lora`, `realism eval` through the grid gate (symphony-template's grid-accounts.yml, action job, the words schwingnet-realism-edit and so on). Each report comes back as logs/REALISM-<stage>.md: the edit report carries the counts of poses, subjects, renders, edits, kept and dropped edits (against the paper's 4 percent) and the measurement table; the stats and eval reports carry one table per comparison, the AUC with its interval, the null's high end, the MMD's p and q, the Frechet and kernel distances and the verdict word per space, and the paired PSNR, SSIM and shift where the names match. The same tool runs on a workstation with a GPU from a clone, with the same files.

## 10. Open questions, to be answered by the first reports

- Whether FluXray's subject ids are ENHANCE.PET's study numbers, and how many of its subjects have a CT and all three truth files in the bucket.
- Whether the flux000 member's filter drops about 4 percent, as the paper's raw-only U-Net did; a very different share means the stand-in reads differently and the kept set is not FluXray's.
- Whether the raw DRRs pair with FluXray's images to the pixel (the shift column): a shift says the geometry differs before the texture does.
- The undistilled base's inference settings for the adapter (REALISM_BASE_STEPS, REALISM_BASE_GUIDANCE), to be read from the first lora report.
