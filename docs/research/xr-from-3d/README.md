# From 3D to X-ray: the consolidated report

Source: the thread "3D CT priors for 2D detection", 2026-10-21, from the owner's asks of 19:49, 20:09, 20:11, 20:12, 20:13 and 20:17 UTC, the last of which was: "All of this should be consolidated into a research report, evaluated for feasibility and prior art, documented as tasks on GitHub, and checkpointed and a handoff written". This is that report, a programme folder whose README says where the work stands. Two notes beside it hold the detail it summarises: docs/research/ct-priors-for-2d-detection.md (eight ranked uses of the segmented CTs) and docs/research/xr-annotation-format.md (the X-ray format, the screening detector, the pseudo-labeller and the covariate census). Confidential with the rest of this repository (docs/project.md): it describes methods, so nothing of it goes to a public place or an external text before the provisional is filed, and no slide names any of it.

## 1. What the owner asked, in his words

- "how i can teach the model what the image looks like in 3d to possible improve 2d image detection? i have a ton of segmented 3d cat scans that idk how to use"
- "it's way easier to label anomalies on cat scan and it can be used as a prior for detecting them in XR ... there are way more ct datasets. Incorporate the idea of this into the workflow"
- "I don't think anyone has stratified and identified spinal anomalies on xray so I'd like to build a detector I can run over my massive unannotated xray dataset. Figure out a good annotation format for XR (corners around bodies most likely)"
- "train a pseudolabeller for the rest of the X-rays based on my limited amount of annotated xray data. Also be checking for pathology metadata or age or anything else I could use as a variable ... in files that came with the dataset, supplementals of the paper, or the image metadata like for dicoms"
- "X-rays across corpuses may vary in the machine used, setting, etc ... a way to denoise the images into just the shape of spines without losing the ability to detect and classify and place landmarks"
- "incorporate the 3D shots of the COBRA dataset which is 360 degree shots of X-rays and a reconstructed ct ... maybe even train something that could convert an X-ray at one angle to another, which could be tested on the few paired lateral and AP X-rays"

## 2. The aim, in one paragraph

Use what 3D gives exactly and 2D gives only by a reader (the order and count of the vertebrae, their corners, the transitional anatomy, the pose of every view) to make the X-ray model name levels correctly on any view and any device, and then run it over the unannotated X-ray collections to find and stratify spinal anomalies, which nobody has done at scale on radiographs. The CTs teach; the X-rays, read in one shared format, test and grow; every number keeps the repository's rules (person-keyed splits, intervals, the stamp, test persons read once).

## 3. The workstreams, with feasibility and prior art

Feasibility is graded on three counts: the data is held (H), requested (R) or missing (M); the effort in working days; and the evidence, Measured (the project's own record), Published (the method shown elsewhere on a related task) or Inferred (reasoned here, not shown). Grid costs are estimates made here unless marked measured.

| # | Workstream | Data | Effort | Grid (estimate) | Evidence | Before 2 Nov? |
| --- | --- | --- | --- | --- | --- | --- |
| A | Counting prior from CT at decode | H | 1 to 2 | 1 to 2 CPU-h | Inferred; CRF priors in CT Published | yes, built |
| B | Bank the rare-class renders | H | 0.5 | 1 CPU-h | Measured that renders carry naming | yes |
| C | AP and oblique renders with projected anchors | H | 2 to 3 | 1 to 3 GPU-h render, 6 GPU-h fine-tune | Published (Bier 2018, SyntheX) | yes |
| D | COBRA: real projections labelled from the planning CT | H | 3 to 5 | 3 to 6 GPU-h, 50 to 100 CPU-h | Published geometry; Measured for C-ArmLSpine | partly |
| E | Device and setting harmonisation that keeps shape | H | 3 to 7 | 10 to 20 GPU-h | Published (SyntheX randomisation, GDCE, shape-conditioned normalisation) | the cheap half |
| F | Anomalies labelled on CT as the prior | H, census | 1 to 3 | small | Inferred | the prior part |
| G | The X-ray annotation format and converters | H, R | 2 to 3 | none | Published practice (AASCE, BUU, CSXA) | yes |
| H | Screening detector over the unannotated films | H | 5 to 10 | an array job per collection | Inferred | no |
| I | Pseudo-labeller (teacher and student) | H | 5 to 10 | 6 GPU-h per round | Published practice | no |
| J | Covariate census and supplements | H | 1 to 2 | 1 CPU-h per source | none needed | yes, built |
| K | Multi-view 3D-aware pretraining | H | 7 to 10 | 20 to 50 GPU-h | Published on DRRs only | no |
| L | View translation, AP to lateral | H | 10 to 15 | 20 to 50 GPU-h | Published (XraySyn, DL-GIPS, X2CT-GAN, Diff2CT) | no |
| M | Physics renderer and its ablation | H | 3 to 5 | 10 to 20 GPU-h | Published (DeepDRR) | no |
| N | Rare anatomy made in 3D | H | 7 to 10 | modest | Inferred | no |
| O | Gold masks on the paired CT and X-ray sets, verified, projected and registered | H | 5 to 10, plus the readers' hours | an array job per set, then small | Published (TotalSegmentator, DiffDRR); Measured for C-ArmLSpine's projection | step 1 and the first cases |

A, B, C, F, G and J are in the two notes beside this one; O, the owner's ask of 2026-10-22, is docs/research/benchmarks-to-beat.md section 5 and issue #127, and that note sets the benchmarks the whole programme is measured against; A, G's format and J's tool are built. What follows is the three the owner added last, E, D and L, written out, and then the order.

### E. Device and setting differences without losing shape

The problem: films and frames differ by device, kVp, dose, detector, the vendor's own processing (unsharp masking, equalisation, LUTs), collimation and grids; none of it is anatomy, all of it moves pixels, and the record already shows the cost: a detector with no frame of the test device finds 7.0 % of bodies (A8.1). The owner's ask is to strip that to "just the shape of spines" without losing detection, naming or landmarks. Four layers, cheapest first, each measured by leave-one-device-out accuracy (train without a device, test on it), which is the held-out-device design the record already uses:

1. Read the image as the device meant it. DICOM carries the modality and VOI LUTs and says whether an image is "for processing" or "for presentation"; applying them, and keeping the raw where it exists, removes part of the vendor difference with no learning at all (tools/bank.py already reads the headers; the census of J says which sources carry which tags). Native first.
2. Randomise what is not anatomy during training, so no setting is special: contrast curves, gamma, noise at several doses, blur, emulated unsharp masking and edge enhancement, grid lines, collimation edges, burnt-in text. SyntheX's evidence is that strong randomisation over a realistic simulator generalises to real clinical X-rays. Cheap, and it can go in before the talk.
3. Correct the global intensity mapping per device, as GDCE does: a learned smooth monotone curve per source that maps its images toward a reference, which by construction moves no edge and so cannot move a corner. The cross-vendor paper's tasks were breast density and pneumonia; whether it helps vertebrae is to measure.
4. Make shape a target, not the only input. A head predicts an anatomy map, per-level soft body masks and corner heatmaps, supervised exactly by the renders (the CT's segmentation projected) and by the corner sets; detection and naming read the image and the map together. This is the owner's "just the shape" made safe: forcing the network through the map alone (a bottleneck) would throw away what shape does not hold, the rib heads, the pedicles, the texture of a transitional body, so the bottleneck is tried only as an ablation and kept only if it loses no accuracy and no corner precision on validation. Segmentation-conditioned normalisation (shape held fixed while appearance is normalised) is the published version of the same idea, in MRI and OCT.

A device-adversarial loss (features from which the device, read from the DICOM header, cannot be predicted) is the fifth option; it needs the device label per image, which J provides, and it is tried after the four above because it can also erase real differences between populations.

Feasibility: layers 1 and 2 are a few days and fit before the talk; 3 is a week; 4 shares its head with C's anchors and G's corners, so it costs little once those exist.

### D. COBRA's full rotations

What COBRA holds (its dataset paper, arXiv 2607.20037, and the challenge page): raw CBCT projections around the patient, their acquisition geometry, the clinical CBCT reconstruction and the planning CT, deformably aligned reference CTs and simulated projections, 867 patients from six centres (the challenge page says seven) on Elekta and Varian, about 950 GB; 692 cases in training, which is what the project's record counts. Its licence is CC BY-NC 4.0, non-commercial, which matters for a product and the patent: whether a model trained on it may be used commercially is the lawyer's question, already on the owner's list for COBRA (session checkpoint, remaining task 7).

Five uses, in order of value:

1. Exact level labels on real frames. The planning CT (or the aligned reference) is segmented, TotalSegmentator labels the vertebrae and the sacrum, and each segmentation is projected through each projection's stored geometry. Every lumbosacral body on every frame gets its level and its four corners with no reader: the format of G, on real X-rays, at a scale no reader could reach. This is item 4 of the CT note.
2. Real sweeps. Each case is a continuous rotation, so it trains and tests what the demo shows, naming that holds as the view turns, and gives the per-angle curve on real frames beyond C-ArmLSpine's two sweeps.
3. Paired simulation and reality. The release's simulated projections from the aligned CT at the same geometry sit beside the real projections: the same anatomy at the same pose, real and simulated, which is the one kind of pair that measures the simulation gap directly and trains the harmonisation of E (layer 3 or 4) on it.
4. Real multi-view pairs for K and L: two projections of one patient a known angle apart.
5. A 3D prior per case for registration research (LevelCheck-style), though the product's goal is CT-free.

Limits: the field of view is the pelvis and the lumbosacral junction (the sacrum is defined on 18.2 % of 609 test frames, retraining-plan.md section 2), so COBRA teaches the low lumbar levels and the sacral anchor, not the thoracic or cervical spine; radiotherapy CBCT projections are not fluoroscopy, though they are the same physics. Feasibility: the geometry is given, so use 1 is engineering, not research; the check is a person looking at a sample of projected corners.

### L. Turning one view into another

The owner's idea: a model that turns an X-ray at one angle into another, tested on the few films that come as AP and lateral pairs.

Prior art: XraySyn (AAAI 2021) synthesises novel views from a single radiograph through CT priors, simulated training and fine-tuning on real radiographs; DL-GIPS (Medical Image Analysis 2022) lifts a view's geometry features to 3D and projects them to the new angle, shown on the lungs; X2CT-GAN (CVPR 2019) and its spine versions reconstruct a CT from two orthogonal films, Diff2CT (arXiv 2408.09731) with a diffusion model on the spine, which reports sharp vertebral boundaries but weaker voxel agreement and that a single X-ray did worst. Nothing found does AP to lateral on the spine with real paired films.

Feasibility, honestly: from one AP film, depth is missing, so a synthesised lateral is the model's guess of the anatomy it cannot see, and an anomaly seen only in the lateral (a listhesis, a wedge) cannot be recovered from an AP where it does not show. So:

- The output that matters is structured, not pixels: from the AP, predict the lateral's corners and levels (cross-view label transfer), trained on DRR pairs (unlimited, exact) and COBRA's real rotation pairs, and scored against a reader's corners on the real pair. That tells whether the AP holds the information at all.
- Pixel synthesis comes second, as an auxiliary task that makes the encoder carry 3D shape (a consistency loss between a view and its synthesised partner), never as an image shown to a person as if it were a film.
- The test set is real pairs of one person and one visit: VinDr-SpineXR's studies that hold both views (held; how many is for J's census to count), BUU-LSPINE's AP and lateral of 3,600 patients (held: 3,600 AP and 3,603 lateral films, data/sources/buu_lspine.json; corrected 2026-10-22, the first version of this report called it requested, and no weight trained on it leaves the grid until the owner has read its licence), and any of the owner's own. The pairs are test persons for this task and kept out of its training.

Feasibility is the lowest of the set: 2 to 3 weeks and a real chance that the structured transfer is only as good as the counting prior already makes the AP. It is after the talk and after D.

## 4. The order

Before the talk (2 November), what can move a number: A (built, waiting on the grid), B, C, E layers 1 and 2, with G and J built so the readers and the census can start. Then D, the largest lever after the talk, then H and I together (the screener is the pseudo-labeller's teacher), E layers 3 and 4, K and M, and L and N last. The results go on slides as results only.

## 5. Where it stands (2026-10-21, about 20:30 UTC)

- Merged or in review: PR #55, the CT note.
- Built in this thread, in review together: src/schwingnet/chain.py with tests/schwingnet/test_chain.py (the decoder), tools/chain_stats.py (the CT prior, readers' CT column calls through --columns), tools/chain_eval.py (classifier against decoder, settings from validation only), tools/covariates.py (the census), the two notes and this report. The decoder's dry run on the synthetic catalog with an untrained model: 14 / 68 against 11 / 68 for the crops alone; that is a test of the plumbing, not a result.
- Not run: no grid job from this thread. The CT prior job, the covariate census and the evaluator over version 1 go through the "SchwingNet video demo plan" thread; the CT roots on the grid (TotalSegmentator v2 and v3, VerSe, CTSpinoPelvic1K) are named in spinesurg-ct-nnunet's data platform, which this session cannot read, so the first job lists them.
- The GitHub tasks are the issues of the epic named in section 6.

## 6. The tasks on GitHub

The parent issue is #56, "From 3D to X-ray: priors, the anomaly screener and the X-ray format", left without the epic label so the coordinator workflow spends no Claude run planning what is planned here; its sub-issues are A #57, B #58, C #59, D #60, E #61, F #62, G #63, H #64, I #65, J #66, K #67, L #68, M #69, N #70, each labelled todo with its acceptance test.

## 7. Sources read

- Gao, Killeen et al., SyntheX, arXiv 2206.06127; Unberath et al., DeepDRR, MICCAI 2018, arXiv 1803.08606; Bier et al., MICCAI 2018, arXiv 1803.08608; Gopalakrishnan and Golland, DiffDRR, CLIP 2022.
- "Learning to Harmonize Cross-vendor X-ray Images by Non-linear Image Dynamics Correction" (GDCE), arXiv 2504.10080.
- Segmentation-conditioned normalisation and one-shot style harmonisation, MRI and OCT, as summarised by the search of 2026-10-21 (PMC10472922, PMC8294062); not read in full.
- COBRA2026 dataset paper, arXiv 2607.20037; cobra2026.grand-challenge.org; Zenodo doi:10.5281/zenodo.21322350.
- XraySyn, AAAI 2021; DL-GIPS, Medical Image Analysis 2022 (arXiv 2504.11953 a related version); X2CT-GAN, CVPR 2019, arXiv 1905.06902; Diff2CT, arXiv 2408.09731; the spine X2CT-GAN adaptations PMC10744485 and PMC9139385.
- LevelCheck (Lo et al., Spine 2015) and the I-STAR clinical study; the FCN and CRF vertebra labelling paper, arXiv 2108.06554.
- AASCE (arXiv 2001.03187), the BUU Spine Dataset page and its Applied Sciences paper, Mendeley 5jdfdgp762.
