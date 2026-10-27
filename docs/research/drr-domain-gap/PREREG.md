# Pre-registration: FleXray's DRRs beside every held X-ray corpus

Source: the thread "Compare synthetic FluXray against real fluoroscopy", 2026-10-27, on the owner's word of 17:51 UTC that the study be sharded on the H200 nodes "see the beethoven protocol for doing so", the protocol being the Lab Recipe (artifacts/the-lab-recipe-1t2gvp/index.md, "Pre-register and freeze"). Label: confidential-results, as the study's README.

This file is frozen. It is the design the study ran under from its first send, written down in the Lab Recipe's seven parts: every part below was already fixed in docs/research/drr-domain-gap/README.md, sections 1 to 5, at commit 6658f3a4b84b463a5ba58d9134f4e892f7c302cd (2026-10-27 15:40 UTC; the file's blob 9de6a933f21aba115d7f536ef743a21162bdcdf7, its sha256 b3dcb44bbb2f12900a261e580b1cbe4d893ce2580badb10487ceddec6aa467a7), which is the full text and which this file only restates; those sections, the groups file and the study's code are the same at 38e5533a31d027185036e78b641c4e6f763403ae, the commit of the study's first send. No number of the study had been read when it was written: the one study job sent before it, Slurm job 40802322, was cancelled at 17:52 UTC on the owner's word before it wrote results.json or a summary. Every departure from it is in DEVIATIONS.md beside it, dated, with its reason.

## 1. The question

How far are FleXray's synthetic DRRs from real X-rays, plain film and intra-operative fluoroscopy, and is that distance larger than the distance between two real corpora; and does this project's own rendering of FleXray's recipe reproduce FleXray's own?

## 2. Population and inputs

- The groups: data/domain_gap/groups.json, version 1, salt `schwingnet-drr-gap-v1`, 23 groups in three families (synthetic, fluoroscopy, film), its sha256 92a1640b70f1b6c64120fdf2838a2a28bdc807fc823ec36e2dc61c490ca1a0fe at the commit above. Each group takes at most 1,000 images, chosen person by person in the salted order with a cap a person; the five frozen test persons of data/splits/test-persons.json are left out of every group.
- The render groups: seven, rendered in the job from the same held CTs of TotalSegmentator v2.0.1 (four views each), differing only by their recipe and engine (README section 2.2); the CTs chosen once in the salted order among those with masks under every segmenter the groups read (README section 2.1). MOOSE's masks are those bench flexray_drr_seg (Slurm job 40799505) wrote; SPINEPS's are the existing masks on the grid, never re-run; segmenter none reads no mask.
- The real corpora: the held corpora the sample index lists, by group, as the groups file names them.
- Exclusions, each with its reason, are README section 2's list (fluoro_video_clips by its record, fluorocap, carmlspine_sweeps, spinesac and mendeley_5jdfdgp762 by their records, COBRA, ljubljana_2d3d_gs, the undecodable videos and the unpacked archives). A group with fewer than 20 decoded images is left out; one with fewer than five persons is plotted and never tested.
- Every image is decoded, windowed to its own 0.5 and 99.5 percentiles, cut to the centre square of 0.9 of its shorter side and resized to 256 (README section 3).

## 3. The measurements

Three feature spaces: flexray (FleXray's flux0375, the spatial mean of the input to the last instance norm of its deepest encoder block), imagenet (torchvision's ResNet-18, its 512 pooled features) and physics (the handcrafted measures of README section 3). The primary reading is inversion-invariant, each image's feature the mean of the image's and its inverse's; FleXray's space is read as stored too, as a secondary reading.

Per space and reading, features standardised: the logistic C2ST AUC (scaler, PCA to 64, C 1; five person-grouped folds stratified by label) with a 1,000-draw person-cluster bootstrap interval and, against each family and in the replication pairs, a 100-permutation person-level p; the 15-nearest-neighbour C2ST AUC; the unbiased MMD with a Gaussian kernel at the median distance and a 1,000-permutation person-level p; FD64 and KID64 in the first 64 principal components; precision, recall, density and coverage; silhouette, neighbour purity, each group's neighbour share in each family and the nearest real corpus of each synthetic group; the maps (PCA, t-SNE at perplexity 30 and UMAP with 30 neighbours on PCA-50, and LDA, labelled supervised) from at most 600 images a group, each but LDA with its trustworthiness. Contrasts: every synthetic group against each real group and each pooled family (300 images from each testable real group), every pair of real groups, pooled fluoroscopy against pooled film, the six pairs of README section 2.2, and the split-half null of every group with 40 persons or more. Benjamini-Hochberg runs over every MMD p of a space and over its C2ST permutation p-values. The seed is 0.

## 4. The hypotheses and their bars

- Primary endpoints, in the flexray space, inversion-invariant: the logistic C2ST AUC of flexray_drr, of flexray_drr_ct and of fluxray where fetched, against pooled fluoroscopy and against pooled film, each with its interval; and FD64 of each against each family divided by the median FD64 between that family's own real corpora (the gap ratio, 1 meaning as far as two real corpora are from each other).
- The words, printed beside each primary number: "indistinguishable" where the AUC's lower bound is at most 0.6; "closer than two real corpora" where the lower bound is below the median AUC of the family's real pairs; "separable" otherwise.
- The replication: "replicated" for the two worded pairs (flexray_replica against flexray_reference; fluxray_raw against fluxray_raw_reference) where the logistic AUC's lower bound is at most 0.6 and the MMD's q is at least 0.05, "not replicated" otherwise; the study's verdict is the first pair's word in the flexray space's inversion-invariant reading.
- The bar of 0.6 was fixed by the study's design on 2026-10-25, before any number; it is neither a published value nor the result of a power calculation (DEVIATIONS.md, item 6).

## 5. What counts as failure

- Of the pipeline: a split-half null whose AUC interval excludes 0.5. The pipeline then leaks, and the corresponding real-versus-synthetic number is not read; the sentence is "the split-half null of <group> in <space> found a difference, so its contrasts are not read".
- Of the replication: the verdict "not replicated". The sentence is "this project's blocks did not reproduce FleXray's own renders of its recipe: the classifier told them apart (AUC lower bound <x>) or the MMD did (q <y>)", and every comparison read through the blocks is then a comparison of this project's renders, not FleXray's.
- Of realism: a primary endpoint worded "separable". The sentence is "FleXray's <group> renders are separable from real <family> (AUC <a>, interval <lo> to <hi>; gap ratio <r>)".

## 6. The analysis plan

Everything else is secondary and read as description: the four groups that exist for the replication alone have their contrasts with the real corpora read as secondary, and so is every pair in the imagenet and physics spaces, worded or not. Nothing is read blind, since no person reads an image; the words are computed by src/schwingnet/domain_gap.py from the numbers and printed by the summary, so no reader chooses them. The known limits are README section 5's, listed before the run.

## 7. Freeze

Frozen on 2026-10-27 by the session of the thread named above, from the commit named above, before any number of the study was read. No further edits: a departure goes in DEVIATIONS.md, and a second design is a new file with its own freeze.
