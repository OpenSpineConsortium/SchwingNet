# VertebralDiffusion (arcadelab), read against the stack

Source: the project thread "Build plug-and-play training experiment framework", 2026-10-24, on the
owner's question of 15:56 UTC: "does this package do anything better than what im doing now?
https://github.com/arcadelab/VertebralDiffusion". Read from a full clone of the repository at its
head, commit 773fc5e of 2025-03-20: its files, configs, tests and history; no paper, report,
release or README of its own was found (a web search on 2026-10-24 returned none). The thread
"Benchmark and priors issues" read the same repository on 2026-10-22 for #70 and wrote it into
docs/research/benchmarks-to-beat.md (section 8) and docs/research/unberath-lab-items-prior-art.md;
this note goes further into the code and corrects one fact there (section 2). Confidential with the
rest of this repository (docs/project.md): it sets the repository beside this project's methods.
Issue #212. Nothing of its code is copied here: the repository carries no LICENSE file of its own,
so its additions are unlicensed, whatever the template and the upstreams it adapts allow.

## 1. The short answer

No. VertebralDiffusion is an unfinished scaffold for an unconditional 3D diffusion model that
generates vertebra volumes from CT. It classifies nothing, detects nothing, denoises no X-ray and
renders none, so it does nothing the level stage, its blocks or the xr-from-3d programme do, better
or worse. The word "diffusion" in its name is the generative process (noise added to a volume and
learned away, 300 steps at a time), not a filter: the denoise block here (gaussian, median, inside
the model) and workstream E's harmonisation are another thing. Its one idea that touches this
project, a learned 3D prior of vertebral shape, belongs to workstream N (rare anatomy made in 3D,
issue #70), where editing segmented CTs keeps the truth exact and a generator would not; and this
project's own record already closed the wider question: whole-CT generation lost once rendered
(5.82 mm against 4.89 for real frames and 4.40 for 2-D diffusion, Rapuri 2026, as
docs/textbook/13-renders-physics-and-the-sim-to-real-gap.md reads it), so no CT generator is
built, and docs/textbook/28-the-ranked-experiment-backlog.md readmits one only if a
vertebra-conditioned generator at higher resolution reverses that. The design the repository
attempts, a 3D VQ-GAN under a 3D diffusion U-Net, is carried maintained and tested by MONAI
(DiffusionModelUNet, VQVAE, AutoencoderKL and its schedulers), which #211 (pull request #213)
brings into the train environment, should that prior ever be wanted (section 4 says what that
still needs).

## 2. What the repository is

- A copy of ashleve/lightning-hydra-template: 442 of the repository's 452 commits are the
  template's (up to bddbc24 of 2023-09-25), its README unchanged, its MNIST example still in
  place. The ten commits of the project's own are by one author ("Rapuris") between 2025-03-04 and
  2025-03-20, titled "new data module", "scaffolding", "notebook", "vqgan", "idk anymore",
  "changes", "diff", "adding diffusion code in hydra format", "error with group size something but
  can't test further bc of mem" and "changes". The two notes of 2026-10-22 call it one commit; the
  clone shows ten, and this pull request corrects them.
- Licence: no LICENSE file. The template's README carries its MIT block ("Copyright (c) 2021
  ashleve"), where the template's own commit e34ccb0 of 2021-10-02 moved it from the file; that
  covers the template's files and says nothing of the additions. The additions adapt three
  upstreams by their own headers: lucidrains' video-diffusion-pytorch, SongweiGe/TATS (whose files
  carry Meta's copyright line) and, through TATS, richzhang's PerceptualSimilarity for the LPIPS
  loss. The one weight file in the repository, src/models/vq_gan_3d/cache/vgg.pth (7,289 bytes),
  is TATS's LPIPS head, not anything trained here; the repository holds no trained weights of its
  own.
- src/models/ddpm/diffusion.py: lucidrains' video-diffusion-pytorch (Ho et al. 2022), its frame
  axis used as the third spatial axis, so Unet3D (dim 128, dim_mults 1, 2, 4, 8, one channel) and
  GaussianDiffusion (image_size 128, num_frames 128, 300 timesteps, cosine schedule, l2 on the
  noise) model a 128 by 128 by 128 volume in pixel space, with an EMA copy kept by
  src/models/diff_module.py; the text conditioning the upstream offers (BERT through torch.hub) is
  present and unused, so the model is unconditional. GaussianDiffusion.forward applies
  `normalize_img`, which maps 0..1 to -1..1, to the batch as the data module hands it over, and
  the data module scales nothing, so it is applied to values that are still Hounsfield units.
- src/models/vq_gan_3d/: a 3D VQ-GAN from TATS (n_codes 2048, embedding 64, downsample 2, 2, 2),
  the pairing Khader et al. 2023 published as medicaldiffusion
  (github.com/FirasGit/medicaldiffusion; named from memory, not read for this note). It is not
  wired in: GaussianDiffusion's loading of a VQ-GAN checkpoint and its encode before the noise and
  decode after the sampling are commented out ("we're not training a vq-gan for now"), so
  `self.vqgan` is always None, whatever the config's `vqgan_ckpt` says. The VQ-GAN that could be
  trained on its own, VQGAN3D (configs/model/vqgan3d.yaml, a Lightning module whose training step
  reads `batch["data"]` and takes Lightning 1's `optimizer_idx`, which Lightning 2, the
  requirement, no longer passes), says three image channels
  for a one-channel CT, and the data module hands it a tensor, not a dictionary; a second wrapper,
  VQGANModule, expecting a dictionary with "image" and "segs", is commented out of
  src/models/__init__.py and has no config.
- src/data/vertebra_datamodule.py: every NIfTI file under a folder of the lab's own disk
  (NMDID-ARCADE, "diffusion_vertebrae_data", one folder per case, a TORSO folder inside; the
  checked-in paths config points at one case's TORSO folder, case-123569, with the whole collection
  commented out beside it), each loaded with nibabel, padded or cropped to 128 cubed with a
  constant, a torchio RandomMotion augmentation in training and no intensity normalisation. The
  split shuffles the file list with `random.shuffle` and no seed of its own, so it is fixed only by
  Lightning's seed_everything where an experiment config sets seed 12345 (train.yaml's seed is
  null), and keeps 20 percent for training, 10 for validation and the rest for test, while its
  docstring says 80, 10 and 10; it is a split by file, so the vertebrae of one case can sit on both
  sides.
- Training: batch size 1 ("12 orig"), gradient accumulation 1, no mixed precision, 10 to 100
  epochs; the default callbacks watch `val/acc`, which the diffusion module never logs (it logs
  `train/loss`, `val/loss` and `test/loss`), so the checkpoint and early-stopping callbacks have
  nothing to read. The author's commit message of 2025-03-15 says the run stopped on memory. No
  checkpoint, sample, metric, figure or evaluation beyond the loss is in the repository.
- Tests and requirements: the template's tests, with five of the six training tests commented out
  and the MNIST data-module test rewritten to open the lab's data path; the requirements and
  environment files are the template's unchanged (hydra pinned, torch bounded below), naming none
  of torchio, nibabel, einops, einops_exts, rotary-embedding-torch, imageio, SimpleITK or monai,
  which the code imports.

## 3. Beside this project, part by part

| This project | VertebralDiffusion | Better here, there, or neither |
| --- | --- | --- |
| The level stage: a 2D crop classifier on fluoroscopy, 27 levels, a latency budget of 97 ms, every part a block (docs/research/experiment-framework.md) | No classifier, no 2D path, no X-ray; a 3D generator of unlabeled volumes | Neither: not the same task |
| denoise: gaussian or median inside the model, carried by the ONNX export; workstream E, harmonisation that keeps shape | A denoising diffusion model, which is a generator; its sampling takes 300 U-Net passes per volume | Neither: a different meaning of the word |
| Workstream N (#70): rare anatomy (L6, T13, sacralised L5) made by editing segmented CTs, labels exact by construction | An unconditional generator could make plausible shapes with no level, no anomaly on demand and no truth; a conditional one would need labels to train on and a reader to verify each sample | Here: the truth is the point of N |
| Workstreams C, K and M: renders of the held, segmented CTs (DeepDRR's physics), thousands of real shapes; the record says whole-CT generation lost once rendered (section 1) | More shapes could be sampled, at a GPU cost per volume that the author's own commit message puts beyond the memory at hand | Here: the real shapes are held already |
| Workstreams L and P: generative translation of views, named with Diff2CT, XraySyn, DL-GIPS | Nothing conditional, nothing 2D; the upstream it adapts is a video model | Neither: it would be built from MONAI's components, not from this |
| The record: RUN.json from a clean tree, catalog hash, person-keyed splits, the gate's contracts, every number a ResultRow with its interval | Hydra output folders and an optional logger; a file-level split; callbacks watching a metric never logged; no evaluation code | Here |
| Dependencies: torch, torchvision, MONAI since #211, each locked on purpose | lightning, hydra, torchio, nibabel, einops, rotary-embedding-torch, an unpinned requirements file that names half of them | Here, by the project's own rule |

## 4. What, if anything, to take

Nothing to insert. Three things to remember:

- If a learned 3D shape prior is ever wanted for N or P, it is built here from MONAI's generative
  components (the former MONAI Generative Models, in monai 1.5: DiffusionModelUNet, VQVAE,
  AutoencoderKL, DDPMScheduler and DDIMScheduler, in two or three dimensions), under this
  repository's rules, trained only on the owner's word and count. The design VertebralDiffusion
  reaches for is the one those components implement; the repository itself is not a start. One
  more re-lock would come first: in the environment #211 locks, VQVAE builds, but
  DiffusionModelUNet and AutoencoderKL raise MONAI's OptionalImportError for einops, which is not
  in the lock (an issue first, .claude/rules/writing.md).
- The condition under which a generator comes back is written: a vertebra-conditioned generator at
  higher resolution that reverses the rendered-frame loss (docs/textbook/28, the backlog). The
  author of the commits and the author of Rapuri 2026 (arXiv 2606.21414, read for
  docs/research/lumbosacral-to-cervical-extrapolation.md) may be the same person; the paper was
  not read as this repository's code, and nothing here rests on that.
- The repository is public and unlicensed, so it is described here and nothing of it is copied.
