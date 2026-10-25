# The Unberath and Killeen lab's X-ray learning, read against SchwingNet, and the five papers to benchmark against

Source: the thread "Compare lab's X-ray learning to SchwingNet", 2026-10-25, issue #276, on the owner's ask of 2026-10-25 01:38 UTC: "the common themes of the XR learning on these papers and their dependence on synthetic data, how their approaches fare on benchmarked real xray data, and their approaches to ensuring there is no loss of domain between synthetic and real xrays, how they are training XRay AI, and any contradictions between my findings and theirs, and a general scope of their workflow, datasets used, and approaches and philosophies of the lab, find the 5 papers you should benchmark against". The papers are those of the two Google Scholar profiles the owner sent at 01:38 UTC (user ids 1bd5mdIAAAAJ and QX7AvxUAAAAJ), with github.com/benjamindkilleen sent at 01:39 UTC. Confidential with the rest of this repository: it sets the project's results beside a competitor's, so nothing of it leaves before the provisional is filed.

Grades are those of docs/research/xr-from-3d/README.md section 3: Measured is this project's own record, Reported a project result read from a note or artifact whose result file was not read here, Published shown in the source named, Inferred reasoned here.

## 0. Which lab, and what was read

- Google Scholar, Scopus, OpenAlex, Semantic Scholar and arxiv.org refused this container and the owner's machine's proxy alike, so the two profiles themselves were not read. The lab is read as Mathias Unberath's ARCADE lab at Johns Hopkins with Benjamin D. Killeen, its most prolific X-ray author, from the GitHub link the owner sent and the two profiles' context (Inferred; the owner should say if either profile is someone else). Killeen moved to TUM's CAMP chair as a postdoc in September 2025 and advises Semaphor Surgical since January 2026 (Published, his TUM page).
- Killeen's record was read from dblp's mirror (20 entries to 2024) and the 2025 to 2026 papers this repository already holds. Every paper's numbers below come either from a read made for this note or from the notes named beside it, which read the papers themselves: docs/research/drr-realism-against-our-results.md (SyntheX, DeepDRR, Rapuri 2026, Pelphix, the twin), docs/research/benchmarks-to-beat.md and docs/research/flepp-and-killeen-critique.md (FluoroSAM and the twin), docs/research/unberath-lab-items-prior-art.md (seven Unberath items and the patents). New here: FleXray (Butoi, Gopalakrishnan, Guttag, Dalca, Dey, arXiv 2609.26756, MIT), which scores FluoroSAM on real benchmarks the lab never ran, and ClassyVision's status (section 8 points to the framework note).

## 1. The common themes

1. In silico first. The lab's stated thesis is that simulation is the enabling technology for interventional X-ray AI, because real intraoperative X-rays with labels are scarce and cannot be collected at the poses and in the numbers learning needs (Published: SyntheX's abstract; Killeen et al., "In silico simulation: a key enabling technology for next-generation intelligent surgical systems", Progress in Biomedical Engineering 2023, title and venue only).
2. Truth by construction. Every label is a CT segmentation projected through the render's geometry, so masks, landmarks and poses are exact and free; the segmentations themselves are TotalSegmentator's (Published: FluoroSAM v3 Methods; SyntheX Methods).
3. One renderer, grown for eight years: DeepDRR (2018), polyenergetic, multi-material, scatter and noise, then mesh tools and the sampling of poses and tools for FluoroSeg (Published: Unberath 2019; FluoroSAM v3).
4. Randomise rather than translate. Strong intensity-space randomisation over a realistic render beats learned image translation (CycleGAN, ADDA) and is the lab's chosen bridge to real frames (Published: SyntheX Table 1).
5. Pelvis and orthopaedic trauma first, with Greg Osgood: landmarks, fracture fixation corridors, surgical phase, K-wire placement; spine appears as vertebroplasty planning and as classes inside FluoroSAM (Published: dblp list; Inigo et al. 2025).
6. From perception to autonomy: the images exist to drive a robotic C-arm (Loop-X), first by geometry, then by language ("Take a shot!", IJCARS 2024; the language-promptable digital twin, arXiv 2412.08020), and to choose the next view (US 12,268,533 B2) (Published).
7. Foundation models and language: FluoroSAM, a Segment-Anything model trained from scratch on about three million renders with text, point and mask prompts (Published: arXiv 2403.08059, MICCAI 2025).
8. People in the loop: user studies of trust, explanation and registration quality assurance (Cho, Taylor, Unberath, MICCAI 2026) and VR cross-training (Killeen 2024) (Published, abstracts).
9. Generative data as the next step: diffusion in 3D (VertebralDiffusion, NMDID crops) and in 2D (Rapuri, Ko, Killeen, Taylor, Unberath, arXiv 2606.21414), so as to need fewer CTs (Published).
10. Open artefacts: DeepDRR, FluoroSeg (CC BY-NC-SA 4.0), FluoroSAM's weights, the twin's cadaver archive (Published: the repositories and Zenodo records, benchmarks-to-beat.md sections 1 and 6).

## 2. How much rests on synthetic data

| Paper | Trained on | Real data in training | Real test |
| --- | --- | --- | --- |
| DeepDRR (Unberath, MICCAI 2018; IJCARS 2019) | renders of CTs | none | 78 frames, two cadaveric torsos, Cios Fusion |
| SyntheX (Gao, Killeen et al., Nature Machine Intelligence 2023) | renders of the six DeepFluoro specimens' own CTs at the real poses; scaled arm adds 20 NMDID CTs | none in the Sim2Real arms; the control is real | 366 frames of six cadavers leave one out, plus 60 of a seventh on a Loop-X |
| Pelphix (Killeen, MICCAI 2023) | simulated sequences | none | one cadaver study |
| FluoroSAM (Killeen, MICCAI 2025) | FluoroSeg, 2,953,257 renders of 1,621 NMDID CTs, from scratch | none | 1,741 masks of one Loop-X cadaver; 1,131 real chest X-rays |
| Digital twin (Killeen, arXiv 2412.08020) | FluoroSAM | none | 80 frames of one cadaver, 46 viewpoints |
| Rapuri et al. (arXiv 2606.21414, 2026) | DRRs, 3D-diffusion CT DRRs, 2D view-conditioned diffusion | the 2D diffusion model learns from projected segmentations | DeepFluoro's 366 frames, six-fold |

(Published, through the notes of section 0.) The pattern is total: in every paper of the record read, the network that is scored on real frames saw no real frame of the task in training, the real data being the test alone (Inferred from the table). The one place real frames enter is SyntheX's control, which is the yardstick, not the method.

## 3. How their approaches fare on benchmarked real X-ray data

- On their own benchmark, DeepFluoro (366 frames, six cadavers, one Siemens Cios Fusion, Grupp et al. 2020), the lab's renders reach parity with real training for hip landmarks and large-structure segmentation: 6.44 against 6.46 mm, Dice 0.80 against 0.79; scaled, 5.95 mm and Dice 0.86 (SyntheX Table 1; Published). Rapuri 2026 on the same frames: real 4.89 mm, DRRs of the real CTs 7.83, 2D diffusion 4.40 at the confident end; at the high-coverage end every arm, real-trained included, errs by 9.7 to 25 mm (Published).
- Off their own benchmark, FluoroSAM does worse than its own paper suggests. FleXray, an independent MIT group, scores it on held-out public sets: on AASCE's Cobb-angle task (218 real spine radiographs) FluoroSAM gives a mean absolute error of 31.82 degrees with 42 failures, against FleXray's 5.13 and none, TotalSegmentator2D's 6.38 and PAXray's 24.94 (Published, arXiv 2609.26756). FleXray reaches Dice 0.915 on DeepFluoro, above an in-domain nnU-Net's 0.866, so the lab's own benchmark is now passed by a model the lab did not make (Published).
- At the level, the lab's models fail on real frames. On the twin's cadaver FluoroSAM by name gives Dice 0.21, 0.16 and 0.25 for L3, L4 and L5 with centroid errors of 49 to 54 mm, against 0.68 for the lower lumbar vertebrae as one group, and the paper writes that one image "may not provide enough visual context to distinguish between similar vertebrae levels" (arXiv 2412.08020, Table 1 and Section 4.1; Published).
- Recognition did not reach parity either: Pelphix 99.2 percent on simulation, 71.7 percent on the cadaver, the rebuttal conceding "a notable sim-to-real gap" (Published).
- Where real data is plentiful, the lab itself says renders lose: COVID-19 lesions 85.03 against 93.95 percent, Sim2Real "hardly matches Real2Real performance for use cases where abundant real data exist" (SyntheX; Published).
- The test populations are small and cadaveric throughout: six cadavers on one device for the benchmark, one cadaver for the spine (Published). No living patient's fluoroscopy appears in any scored row read here (Inferred from the table of section 2).

## 4. How they keep the domain from being lost between renders and real frames

1. Physics: spectrum, learned material decomposition, scatter, quantum and readout noise, detector saturation (DeepDRR). On real frames physics took landmark error from 78.2 to 24.7 mm, still about four times its synthetic error; the polychromatic step was significant and scatter was not (Unberath 2019; Published).
2. Strong randomisation: inversion, impulse noise, affine, contrast, blur, box corruption, dropout, sharpen and emboss, pooling, multiply, distortion, up to two at once (SyntheX); in FluoroSeg's code a k-means mixture window, random inversion, CLAHE or two to four of blur, sharpen, contrast, a Gaussian non-uniform contrast, fog, dropout and channel shuffle (Published; benchmarks-to-beat.md section 3). It is intensity-space only: no detector model, no vendor processing, no collimation or table (Published, by absence).
3. Scale and pose density: 10,000 renders in SyntheX, three million in FluoroSeg, 500 views per CT at plus or minus 2.5 degrees in Rapuri 2026, the densest arm being the best (Published).
4. Population match: the controlled SyntheX arm renders the test cadavers' own CTs at the real frames' poses, so the arms differ "in only the realism of the simulation" (Published). This is the strongest single lever and the one the lab's headline result leans on (Inferred, from drr-realism-against-our-results.md section 4).
5. Domain adaptation tried and set aside: CycleGAN 6.62 mm and ADDA 6.41 against 6.44 for randomisation alone (Published).
6. Generative appearance as the next bridge: 2D diffusion conditioned on projected segmentations (Rapuri 2026). FleXray, outside the lab, instead edits DRRs with a general image editor (FLUX.2) toward clinical appearance and reports appearance randomisation as most of its transfer gain (Published).
7. What none of them does: train on real frames of other devices, hold a device out, or report per-device processing (Published, by absence; Inferred as a gap).

## 5. How they train X-ray AI: the workflow, the datasets and the philosophy

Workflow (Published, the papers of section 2): CTs (NMDID decedents, TotalSegmentator, internal torso scans) segmented by TotalSegmentator; DeepDRR renders at poses sampled around a C-arm model, with tool meshes inserted; labels projected through the geometry; strong randomisation in the loader; a TransUNet (SyntheX) or a SAM-style model trained from scratch (FluoroSAM); tested on DeepFluoro and one or two cadavers on a Loop-X; then used downstream for registration, view planning and robot control.

Datasets: DeepFluoro (Grupp 2020, real, the benchmark); NMDID (decedent CT); TotalSegmentator (CT and its labels); 844 internal torso CTs (FluoroSAM v2 only); QaTa-COV19 and a 1,131-image chest set (Candemir 2014) for the chest; cadaver Loop-X archives of their own (Published).

Philosophy (Inferred from sections 1 to 4): data scarcity is the binding constraint, so the lab invests in the generator and not the collection; exact synthetic truth is preferred to noisy real labels; a single general model prompted by language is the goal, not a narrow task model; and validation is a cadaver study at the scale of a feasibility demonstration, with the clinical system (robot, voice, view planning) as the end. Its own limits are stated plainly in SyntheX ("may not accurately reflect all of the variability one may expect during image-based surgery") but no paper read holds a device or a living population out (Published for the quote; Inferred for the rest).

## 6. Contradictions between the owner's findings and theirs

| # | Theirs | The owner's | A contradiction? |
| --- | --- | --- | --- |
| 1 | Realistic renders with strong randomisation train as well as real frames (SyntheX) | Renders alone detect 0.3 percent of C-ArmLSpine's bodies at confidence 0.74 and 31.7 at 0.25, against 80.5 with other devices' real frames (Reported, STATUS.md A6.12) | Apparent, not real: SyntheX is matched population, large distinctive structures, a few hundred real frames as the control and a cadaver test; ours is living CTs, every body, thousands of real frames and an unseen clinical device. Where we matched their design (renders of DeepFluoro's own CTs) we matched their transfer, 90 to 97 percent sacrum recall (Reported, a record) (drr-realism-against-our-results.md) |
| 2 | One image may not tell similar vertebral levels apart (the twin, Dice 0.04) | The reported stack names lateral levels from one frame at 96.4 percent (595 of 617) on an unseen C-arm, its encoder's fluoroscopic appearance from renders alone (Reported, demo-plan.md 0.3 and 8.3) | Yes, the sharpest one. Their failure is a segmenter prompted by a level's name with no count; ours counts from an anchor. It refutes their reading that the frame lacks the information, not their number (Inferred). Caveat: over detected bodies, 88.0 percent with the 59 misses counted wrong, and AP is 43.7 percent (Reported) |
| 3 | Adding renders at scale helps (SyntheX scaled arm, Dice 0.86 over 0.79) | Styled renders added to real frames cut detection from 80.5 to 63.1 percent (Reported, STATUS.md A6.11) | Yes, on its face. Their added renders are of decedent CTs into a renders-only arm; ours were added to a real-frame arm whose real frames already set the domain (Inferred). Untested in their design |
| 4 | Learned translation adds nothing over randomisation | Refiners and the Fourier low-band swap sat inside the 26-point seed spread; SDXL img2img unusable | Agree (Published, Reported) |
| 5 | Physics is necessary | Physics explains about 86 percent of a real frame's variance, the calibrated renderer about 90, and renders still fail detection on a new device | Agree: necessary, not sufficient (Published, Reported) |
| 6 | 2D diffusion can stand in for real frames (Rapuri 2026) | FluoroGen, SDXL with a Canny ControlNet, gave no usable strength and was cancelled at 12,896 images (Reported) | Partial. Different methods: theirs is trained on projected segmentations and conditioned on view; ours was a general model steered by edges. Theirs is pelvis landmarks on six cadavers (Inferred) |
| 7 | Real labelled X-rays are too scarce to train on | The project holds about 850 real cases and 438,000 frames; the gap is in level labels, not frames (Measured, flepp-and-killeen-critique.md section 5) | A difference of premise: for the spine, real frames exist and the labels are the cost (Inferred) |
| 8 | TotalSegmentator's labels are truth | TotalSegmentator has no L6 and shifts one level on lumbarisation; the owner's audit puts transitional spines at about 4 percent of CTSpinoPelvic1K (Reported, the owner's NeurIPS 2026 poster) | Yes for any level claim built on their labels, FluoroSAM's included. SchwingNet's own truth leans on the same labeller (flepp-and-killeen-critique.md section 5) |

Where the owner's findings are weaker: version 1 has no real result yet, names inside truth boxes, and its test part is five persons of a device it trains on (Measured; flepp-and-killeen-critique.md section 5). Each row above is the reported stack's, not version 1's.

## 7. The five papers to benchmark against

Chosen for SchwingNet's task, naming vertebral levels on real fluoroscopy from one frame, and for what each benchmark can be run on now. The ARCADE record has no level-naming paper, so two of the five are models to beat head to head and three are recipes or data to beat on our task.

1. FluoroSAM (Killeen, Wang, Zhang, Armand, Taylor, Dreizin, Osgood, Unberath; MICCAI 2025; arXiv 2403.08059). The only model of theirs that answers a level, its weights released (2.5 GB; benchmarks-to-beat.md section 6 says where they stand on the grid). Benchmark: rung 0 of #131, FluoroSAM by text, by a count from its sacrum mask, and by two points, scored as naming accuracy per level on the same C-ArmLSpine frames as version 1, each row with its localisation stated.
2. The language-promptable digital twin (Killeen, Suresh, Gomez, Inigo, Bailey, Unberath; arXiv 2412.08020). The only published per-level number of the lab on real fluoroscopy (L3 to L5, Dice 0.16 to 0.25, 49 to 54 mm), and its cadaver archive is released. Benchmark: SchwingNet on their 80 frames, scored by their metric (centroid error per level) beside naming accuracy, so the comparison is on their data and not only ours.
3. SyntheX (Gao, Killeen, Hu, Grupp, Taylor, Armand, Unberath; Nature Machine Intelligence 5:294-308, 2023). The lab's central claim. Benchmark: workstream M, issue #69, as drr-realism-against-our-results.md section 5 states it: their physics and strong randomisation on our task and held-out device, parity defined before the run. It decides contradictions 1 and 3.
4. Rapuri, Ko, Killeen, Taylor, Unberath, "2D Versus 3D Diffusion for In Silico Training of Interventional X-ray AI Models" (arXiv 2606.21414, 2026). The lab's current direction, and the claim (contradiction 6) that generated 2D frames can replace real ones. Benchmark: their protocol on DeepFluoro reproduced for the sacrum and the count, then a view-conditioned 2D diffusion arm on our level task, against the calibrated renders.
5. DeepDRR (Unberath, Zaech, Gao et al.; MICCAI 2018, IJCARS 14(9):1517-1528, 2019). The renderer under all four. Benchmark: DeepDRR renders against this project's calibrated renderer from the same CTs and poses, scored first by variance explained on DeepFluoro's real frames and then by detection on C-ArmLSpine, so a render result is never a renderer confound.

Next in line, not chosen: Pelphix (recognition, not localisation), "Take a shot!" and the autonomous acquisition system (control, not perception), Inigo, Killeen et al. 2025 (one known vertebra's reconstruction from biplane X-rays), US 12,268,533 B2 (a patent, read for counsel in unberath-lab-items-prior-art.md). Outside the lab, FleXray (arXiv 2609.26756) belongs beside FluoroSAM in rung 0 as the stronger general X-ray segmenter, and Huang 2022 (Uneri, Siewerdsen, Johns Hopkins) is the nearest published level labeller trained on renders (lumbosacral-to-cervical-extrapolation.md section 3).

None of these benchmarks is run by this note. Each that needs the grid waits for the owner's word and count.

## 8. The training framework beside ClassyVision and others

The owner's second question of 01:39 UTC is docs/research/training-framework-against-published-frameworks.md.

## 9. Read, and not read

Read on 2026-10-25: Killeen's TUM CAMP page; dblp's mirror of Killeen's record (dblp1.uni-trier.de, pid 249/5517); arXiv 2609.26756 (FleXray) in HTML; the Pith summary of arXiv 2606.21414; the Johns Hopkins engineering news item on Pelphix; github.com/benjamindkilleen/ClassyVision and github.com/facebookresearch/ClassyVision. Everything else through the notes of section 0, which name their own reads.

Not read: the two Google Scholar profiles, Scopus and Unberath's full publication list (each refused); the in silico simulation review beyond its title; the full texts of "Take a shot!" and the autonomous acquisition paper; FleXray's per-dataset appendix.
