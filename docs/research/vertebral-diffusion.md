# VertebralDiffusion (arcadelab), read against the stack

Source: the project thread "Build plug-and-play training experiment framework", 2026-10-24, on the
owner's question of 15:56 UTC: "does this package do anything better than what im doing now?
https://github.com/arcadelab/VertebralDiffusion". Read from a clone of the repository at its head,
commit 773fc5e of 2025-03-20, its files, configs and history; no paper, report, release or
README of its own was found (a web search on 2026-10-24 returned none). Confidential with the rest
of this repository (docs/project.md): it sets the repository beside this project's methods. Issue
#212. Nothing of its code is copied here: the repository carries no LICENSE file of its own, so
its additions are unlicensed, whatever the template and the two upstreams it adapts allow.

## 1. The short answer

No. VertebralDiffusion is an unfinished scaffold for an unconditional 3D diffusion model that
generates vertebra volumes from CT. It classifies nothing, detects nothing, denoises no X-ray and
renders none, so it does nothing the level stage, its blocks or the xr-from-3d programme do, better
or worse. The word "diffusion" in its name is the generative process (noise added to a volume and
learned away, 300 steps at a time), not a filter: the denoise block here (gaussian, median, inside
the model) and workstream E's harmonisation are another thing. Its one idea that touches this
project, a learned 3D prior of vertebral shape, belongs to workstream N (rare anatomy made in 3D,
issue #70), where editing segmented CTs keeps the truth exact and a generator would not; and the
design it attempts, a 3D VQ-GAN under a 3D diffusion U-Net, is carried maintained and tested by
MONAI (DiffusionModelUNet, VQVAE, AutoencoderKL and its schedulers), which #211 brings into the
train environment, should that prior ever be wanted.

## 2. What the repository is

- A copy of ashleve/lightning-hydra-template (442 of its 452 commits, its README unchanged, its
  MNIST example still in place) with ten commits of the project's own by one author between
  2025-03-04 and 2025-03-20, the last three titled "idk anymore", "error with group size something
  but can't test further bc of mem" and "changes".
- src/models/ddpm/diffusion.py: lucidrains' video-diffusion-pytorch (Ho et al. 2022), its frame axis
  used as the third spatial axis, so Unet3D (dim 128, dim_mults 1, 2, 4, 8, one channel) and
  GaussianDiffusion (image_size 128, num_frames 128, 300 timesteps, cosine schedule, l2 on the
  noise) model a 128 by 128 by 128 volume in pixel space, with an EMA copy; the text conditioning
  the upstream offers (BERT through torch.hub) is present and unused, so the model is unconditional.
- src/models/vq_gan_3d/: a 3D VQ-GAN from TATS (n_codes 2048, embedding 64, downsample 2, 2, 2),
  the pairing Khader et al. 2023 published as medicaldiffusion. It is not wired: the diffusion's
  encode and decode through it are commented out ("we're not training a vq-gan for now"), its
  Lightning module is not exported from src/models, that module's step expects a dictionary batch
  with "image" and "segs" that the dataset does not produce, and its config says three image
  channels for a one-channel CT.
- src/data/vertebra_datamodule.py: every NIfTI file under a folder of the lab's own disk
  (NMDID-ARCADE, "diffusion_vertebrae_data", one folder per case, a TORSO folder inside), each
  loaded with nibabel, padded or cropped to 128 cubed with a constant, a torchio RandomMotion
  augmentation in training, and `normalize_img`, which maps 0..1 to -1..1, applied to values that
  are still Hounsfield units. The split shuffles the file list (seeded by the experiment's
  seed_everything) and keeps 20 percent for training, 10 for validation and the rest for test,
  while its docstring says 80, 10 and 10; it is a split by file, so the vertebrae of one case can
  sit on both sides.
- Training: batch size 1 ("12 orig"), gradient accumulation 1, no mixed precision, 10 to 100
  epochs; the default callbacks watch `val/acc`, which the diffusion module never logs (it logs
  `val/loss`). No checkpoint, sample, metric, figure or evaluation is in the repository; the tests
  are the template's MNIST tests and one that opens the lab's data path.

## 3. Beside this project, part by part

| This project | VertebralDiffusion | Better here, there, or neither |
| --- | --- | --- |
| The level stage: a 2D crop classifier on fluoroscopy, 27 levels, a latency budget of 97 ms, every part a block (docs/research/experiment-framework.md) | No classifier, no 2D path, no X-ray; a 3D generator of unlabeled volumes | Neither: not the same task |
| denoise: gaussian or median inside the model, carried by the ONNX export; workstream E, harmonisation that keeps shape | A denoising diffusion model, which is a generator; its sampling takes 300 U-Net passes per volume | Neither: a different meaning of the word |
| Workstream N (#70): rare anatomy (L6, T13, sacralised L5) made by editing segmented CTs, labels exact by construction | An unconditional generator could make plausible shapes with no level, no anomaly on demand and no truth; a conditional one would need labels to train on and a reader to verify each sample | Here: the truth is the point of N |
| Workstreams C, K and M: renders of the held, segmented CTs (DeepDRR's physics), thousands of real shapes | More shapes could be sampled, at a GPU cost per volume that the author's own notes put beyond the memory at hand | Here: the real shapes are held already |
| Workstreams L and P: generative translation of views, named with Diff2CT, XraySyn, DL-GIPS | Nothing conditional, nothing 2D; the upstream it adapts is a video model | Neither: it would be built from MONAI's components, not from this |
| The record: RUN.json from a clean tree, catalog hash, person-keyed splits, the gate's contracts, every number a ResultRow with its interval | Hydra output folders and an optional logger; a file-level split; no evaluation code | Here |
| Dependencies: torch, torchvision, MONAI since #211, each locked on purpose | lightning, hydra, torchio, nibabel, einops, rotary-embedding-torch, an unpinned requirements file | Here, by the project's own rule |

## 4. What, if anything, to take

Nothing to insert. Two things to remember:

- If a learned 3D shape prior is ever wanted for N or P, it is built here from MONAI's generative
  components (the former MONAI Generative Models, in monai 1.5: DiffusionModelUNet, VQVAE,
  AutoencoderKL, DDPMScheduler and DDIMScheduler, in two or three dimensions), under this
  repository's rules, trained only on the owner's word and count. The design VertebralDiffusion
  reaches for is the one those components implement; the repository itself is not a start.
- The repository is public and unlicensed, so it is described here and nothing of it is copied.
