# Strong domain randomisation: what SyntheX and FluoroSAM randomise and what the strong block takes

Source: the thread "Build plug-and-play training experiment framework", 2026-10-24, the owner's question of 22:29 UTC ("what part are they missing?") about the design note's trial arm 2, which named "the part of SyntheX's and FluoroSAM's randomisation the blocks have". Read from the papers themselves: SyntheX, Gao, Killeen et al., "Synthetic data accelerates the development of generalizable learning-based algorithms for X-ray image analysis", Nature Machine Intelligence 5(3):294-308, 2023 (doi 10.1038/s42256-023-00629-1, read on PubMed Central as PMC10959504, Methods); FluoroSAM, Killeen et al., MICCAI 2025, paper 5042 (papers.miccai.org/miccai-2025/paper/5042_paper.pdf). arxiv.org is unreachable from the cloud session, so the preprints were not read.

## What the two papers randomise

SyntheX trains on images rendered from CT and tests on real X-rays, and randomises at two levels.

- **The simulation:** the viewing geometry per task (for the hip, translation of 50 mm left and right and 20 mm up and down; for the robotic tool, a source-to-isocentre distance of 600 to 900 mm; for COVID-19, rotations of 5 degrees about each axis and a distance of 350 to 650 mm, with a shear of the CT), and the physics: its realistic renderer, DeepDRR, models the full spectrum, signal-dependent and readout noise and detector saturation, against a naive mono-energetic one and a heuristic thresholding.
- **The image, regular set**, applied at every iteration: Gaussian noise of spread 0.005 to 0.1 of the intensity range, gamma 0.7 to 1.3, and a random square crop of 90 percent.
- **The image, strong set**, of which "up to two" are concatenated per iteration: inversion (max minus x); impulse, pepper or salt noise on 10 percent of pixels; a random affine warp with translation, rotation, shear and scale; linear, log or sigmoid contrast; Gaussian blur of spread 3 and average blur of kernel 2 to 7; boxes corrupted with large noise; dropout of 1 to 10 percent of pixels or of one rectangle of 2 to 5 percent of the image; sharpening; embossing, "the sharpened version added rather than blended"; average, max, min or median pooling; a multiply of 50 to 150 percent or a brightness change; and a random piecewise affine distortion.

FluoroSAM follows SyntheX ("following [7, 12], we apply strong domain randomization") and names coarse dropout, inversion, blurring, Gaussian contrast adjustment, random windowing and CLAHE histogram equalisation. Its simulation samples random and near-standard C-arm views, the fully random ones within 60 degrees of the anterior direction, and its network reads three channels, the second and third windowed by a K-means clustering of the pixel values.

## What the blocks had, and what they lacked

The four augment blocks before this change (tools/train_blocks.py) are box-jitter (a shift of up to 6 percent and a resize of up to 8 percent), intensity (gamma 0.7 to 1.4, linear contrast 0.8 to 1.2, brightness 0.08), blur (a Gaussian under one pixel) and noise (spread growing with the square root of the signal, up to 0.04). They match SyntheX's regular set in kind and stay deliberately mild, "each a picture the C-arm could give". Of the strong set they had nothing: no inversion, impulse noise, rotation or shear, log or sigmoid contrast, heavy blur, box corruption, dropout, sharpening, embossing, pooling, multiply or piecewise warp, and none of FluoroSAM's Gaussian contrast, random windowing or CLAHE.

The simulation side does not carry over: it shapes images rendered from CT, and SchwingNet's level stage trains on real frames.

## The strong block

The fifth augment block, `strong`, takes the image-level strong set of both papers. Per crop it draws how many of the transforms to apply, none, one or two, and which, every draw from the run's own generator on the CPU so a run reproduces on any device. The two geometric ones, the affine and the piecewise warp, move a crop's level map with it. SyntheX's transform names match the augmenters of the imgaug library, though the paper does not say it used imgaug; where SyntheX names a transform but gives no range, the block takes imgaug's default for the augmenter of that name, and tools/train_blocks.py says which range is the paper's and which is imgaug's.

## The caveat the trials carry

Both papers use the strong set to carry training on simulated images to real ones. SchwingNet's trials train and test on real C-arm frames, so the strong block there is a test of robustness, not a reproduction of either paper's setting, and trial arm 2 cites the papers for the transforms, not for an expected gain.
