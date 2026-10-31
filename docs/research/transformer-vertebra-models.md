# Transformers for naming and outlining vertebrae with a limited field of view

Source: the thread "Try a transformer-based vertebra model", 2026-10-31, from the owner's ask of 04:41 UTC that night: "also please look into a transformer based approach as they say, transformers are all you need". The literature below is named from the papers as published and read from memory of them in this thread, not fetched anew; every claim about our own code names the file it rests on. Confidential with the rest of this repository (docs/project.md): the landmark and phantom direction stays private, and nothing here goes into any external text.

## 1. The short answer

Two transformer networks now sit in the auto-anatomist's model spot beside the residual U-Net, as one word each: `architecture=transunet` and `architecture=unetr` (bordercall autoanatomist/model.py, ARCHITECTURES; vendored here under grid/autoanatomist/). Both keep the frame every architecture keeps, features at a half, a quarter and an eighth of the crop from either branch, the privileged-information fusion and the residual U-Net's decoder, so a run that names one changes the encoder and nothing else, and the QA loop's gates judge it as they judge the convolutional one. The QA loop plan grid/qaloop/qa_transformer.json, once the loop itself is on main, trains the TransUNet under the same bars.

What the literature supports is narrower than the slogan. For outlining one vertebra in a 3-D crop, transformers have matched well-tuned convolutional networks rather than beaten them, so the per-crop encoder is the weaker place to expect a gain. Where attention has a clear argument is naming: a limited field of view shows a run of a few bodies, and which level each one is depends on all of them together, the gaps, the shapes and whatever anchor is in view. That is a set-to-sequence problem, the kind a transformer over per-vertebra tokens is built for, and section 4 proposes it as the next step.

## 2. What exists

- TransUNet (Chen et al., arXiv 2102.04306, 2021): a convolutional encoder whose deepest features are cut into tokens and passed through transformer layers before a U-Net decoder. The hybrid keeps the convolutions' local detail and gives the bottleneck the whole image's context. Our `transunet` is this in 3-D at the crop's size: three strided residual blocks, then four pre-norm layers over the 6 by 7 by 4 voxels of the eighth scale (168 tokens at the default crop of 48 by 56 by 32 at 2 mm), their output added to the bottleneck.
- UNETR (Hatamizadeh et al., WACV 2022): a plain vision transformer over 3-D patches as the whole encoder, with the skip connections read off intermediate layers and brought up by deconvolutions. Our `unetr` cuts the crop into 8-voxel patches (the same 168 tokens), runs six layers, and reads the half and quarter scales off the second and fourth layers, resized and refined by one residual block each; it is the one of the five architectures that leans least on locality.
- Swin UNETR (Hatamizadeh et al., BrainLes 2021; Tang et al., CVPR 2022, with self-supervised pretraining on unlabelled CT): shifted-window attention, so attention stays local at the fine scales and grows coarser, which scales to large volumes. Its argument is pretraining on many unlabelled CTs; the grid holds those (gold tier 3 and 4), so a pretrained Swin encoder is a later option, not built here, since its windows matter at volumes far larger than our crop.
- nnFormer (Zhou et al., 2021) and the nnU-Net comparison (Isensee et al., "nnU-Net revisited", MICCAI 2024): the second found that, trained and tuned with equal care, convolutional U-Nets matched or beat the transformer segmenters on the 3-D benchmarks it tried. This is the main reason to expect `transunet` and `unetr` to be no better than `residual-unet` at Dice, and why the QA loop judges them on the same bars rather than assuming the gain.
- DETR (Carion et al., ECCV 2020): detection as set prediction, a fixed number of learnt queries each answering one object, matched one-to-one to the truth by the Hungarian algorithm, with no anchors and no non-maximum suppression.
- Spine-Transformers (Tao, Liu and Zheng, Medical Image Analysis, 2022): DETR's idea for spine CT with an arbitrary field of view: one query per vertebral level, so the network answers, for each level, whether it is in view and where, and the levels are named jointly by attention among the queries rather than one by one and then repaired; a second stage segments each found vertebra. It is the closest published match to our problem in 3-D, and its design, levels as queries that attend to one another, is what section 4 carries into 2-D.

## 3. How the two new architectures stand

- Sizes, measured in this thread's container with the default widths 16, 32 and 64: residual-unet 579,230 parameters, transunet 868,766, unetr 906,334 (bordercall autoanatomist/README.md). Attention at 168 tokens costs little; the transformers' extra weights are the layers' projections and the learnt positions.
- The tests: bordercall tests/test_autoanatomist_probe.py holds every architecture to the fusion frame's shapes from both branches, the CT-only path equal to the fused pass at w 0, a session's training with finite losses and one step that lowers the loss; tests/test_autoanatomist_latent.py trains each transformer under the mask objective, the QA loop's, through a session that is saved and loaded with its latents unchanged.
- The learnt positions are tied to the crop's shape: a run that changes the crop makes a new model, as it does for every architecture's bottleneck already. A transformer usually wants more data and a warm-up; the QA loop's controller grows the phantoms as the memory allows, and the plan keeps the residual U-Net's optimiser so that the comparison is the encoder's alone.

## 4. The proposal: a column transformer that names the run jointly

The QA loop's namer today (tools/qaloop_gates.py, on the QA loop's branch) describes each body of a run by its chosen landmarks, its size and its gap to the next, and scores every hypothesis, every placement of k consecutive levels in every column type, by Gaussians per level. That is an explicit generative model, and its strength is that its failures are readable. A column transformer would replace it where it is too rigid:

- Tokens: one per body in view, its landmarks in the run's own frame, its size, the gaps to its neighbours, and later the auto-anatomist's latent for that body; plus learnt anchor tokens for what may or may not be in view (the sacrum, a rib, the frame's edge).
- Attention among the run's tokens with relative positions (one body above, two below), so naming uses all the bodies at once and is unchanged by where the run sits in the frame.
- Output: for each token a distribution over level names, decoded jointly so the names are consecutive (a constrained search over the placements, as the namer does now, or the Hungarian matching of DETR with one query per level as Spine-Transformers does), with the column type as one more output.
- Training data: exactly the fingerprint's runs, phantoms projected through drawn C-arm poses with exact names, which the QA loop already makes, so it needs no new data and is judged by the fingerprint's own bars, cell by cell, against the Gaussian namer as its baseline.
- Latency: a few layers over at most a dozen tokens is far inside the 97 ms budget on a CPU.

Its risk is the one the PREREG's known limits already name: where one frame cannot tell a four-lumbar column from a typical one, no namer can, and a transformer would be more confident and no more right. So it is to be judged on the gate persons with the margins the namer is held to, and its gain claimed only where its Wilson bound passes a cell the Gaussian namer fails.

## 5. What is not done

- No transformer has trained on the grid yet; the plan waits for the QA loop's own pull request and its gate word.
- The column transformer of section 4 is a proposal, not code.
- A Swin encoder with self-supervised pretraining on the gold tier CTs is not built.
- No transformer reads the 2-D frames themselves; the frame-level detector the PREREG names as missing is still missing for every architecture.
