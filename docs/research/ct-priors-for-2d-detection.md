# Using the segmented CTs to improve 2D detection and naming

Source: the thread "3D CT priors for 2D detection", 2026-10-21, from the owner's question of 19:49 UTC: "can you look into how i can teach the model what the image looks like in 3d to possible improve 2d image detection? i have a ton of segmented 3d cat scans that idk how to use to improve 2d detction/classification". The project's facts come from this repository's own records (docs/research/demo-plan.md, retraining-plan.md, datasets-inventory.md, datasets-reproduce.md), which quote spine-program's 01_carm_level_detection; the literature was read on 2026-10-21 from the papers' abstracts and project pages, listed in section 6. Every grid cost below is an estimate made here, not a measurement, and every job still goes through the "SchwingNet video demo plan" thread. Confidential with the rest of this repository (docs/project.md): methods, not for any public place or external text.

## 1. The short answer

The CTs are already being used, in one way: they are rendered into synthetic 2D images (DRRs, "renders") whose labels come from the 3D segmentation. The record says what that bought and where it stops:

- Naming transfers from renders. The zero-shot level encoder, whose only intraoperative appearance came from renders, names lateral C-arm frames of a device it never saw at 96.4 % (595 / 617), against 97.4 % fine-tuned on that device (demo-plan.md section 0.3, A2.1, A3.1).
- Detection does not. A renders-only detector finds 0.3 % of vertebrae on C-ArmLSpine at confidence 0.74; other devices' real frames plus renders reach 80.5 %, and 24 frames of the device 84.0 % (A6.9 to A6.12).
- AP naming collapses: 43.7 % zero-shot, a one-level cranial shift (A2.2, A2.8). That is the largest error in the record, and it is a counting error, not an appearance error.
- Rendered material sits unused: FluoroGen's synth_rare renders, 12,929 frames with 1,763 L6 and 86 T13, are in no bank and no reason is written (datasets-inventory.md section 5).

So the question is not whether to use the CTs but which of their other uses close those three gaps. The CTs carry more than appearance: the order of the vertebrae and the spacing between them, the ribs and the sacrum that anchor the count, the exact pose of every projection, and the material that makes a realistic X-ray. Each idea below spends one of those.

## 2. What the project holds in 3D

From datasets-inventory.md section 5 (counts are the records'):

| Set | Size | Labels | Note |
| --- | --- | --- | --- |
| CTSpinoPelvic1K (own release v11) | 802 CTs | vertebra, sacrum, pelvis; 18 L6 cases flagged | the render banks today; CC BY-NC-SA |
| TotalSegmentator v2 and v3 | 1,228 and 1,935 scans | whole body, ribs included | v3 has 142 whole-spine subjects; CC BY 4.0 |
| VerSe 19 and 20 | 374 series, 355 subjects | vertebra labels | renders in the v9 base |
| CTSpine1K, CTPelvic1K | 1,005 and 172 CTs | partial | transitional registry only |
| RSNA 2022 cervical fracture | 2,019 studies | C1, C2, C7 anchors | never unpacked |
| Anomaly harvest (family B) | 56 sources on disk | census counts | the rare-class source in 3D |
| COBRA (Elekta, Varian) | 692 cases, 375,618 real CBCT projections | planning CT registered | lumbosacral; projections are real X-rays with known geometry |
| DeepFluoro | 6 cadavers, 19 CTs, 2,659 vendor frames | from the CT | 2,293 vendor frames unused |
| IPCAI 2025 X-ray with CT | 5 CTs with calibrated real X-rays | to confirm | registered in data/registry, not fetched |
| C-ArmLSpine | 149 cases, one CBCT each | level truth already projected from the CBCT | the test device; never a training source for the test persons |

Where the segmentations themselves live (holding.sqlite under the data platform's index, the derived/ folders on Ceph) is recorded in spinesurg-ct-nnunet's data_platform, which this session cannot read; the first job of item 3 below lists them before anything is rendered.

## 3. The ranked plan

Ranked by what it should do to the talk's numbers per day of work. Items 1 to 3 fit before 2 November; items 4 to 8 come after. Each lands as its own task and pull request, the renders and statistics as train-side shards through the registry (retraining-plan.md section 3), never with a test person, and every comparison is made on the validation witness frames, with the frozen test persons read only for the final row.

### 1. A counting prior from 3D at decode time (no training)

What: fit, from the segmented CTs, the ordered chain of vertebrae with the distributions of each level's height and of the gap to its neighbour, as ratios that a projection preserves to first order, plus how often the chain is 4, 5 or 6 lumbar and 11, 12 or 13 thoracic. At inference the detector's boxes and the encoder's per-box level posteriors are decoded jointly as one ordered sequence (a Viterbi pass over the levels) instead of box by box, with the anchors that are visible (sacrum, last rib-bearing vertebra) as strong evidence. A one-level shift of the whole column then costs the decoder unless the anchors and the ratios support it.

Why first: it targets the AP collapse directly, which is a whole-column shift, needs no training and no new frames, costs microseconds per frame inside the 97 ms budget, and can be measured on the posteriors the stack already dumps (`level_prototype.py --dump-posterior`, demo-plan.md W4). The closest published analogue is a CRF with an anatomical prior over FCN likelihood maps in CT, which pushed CT labelling near the ceiling (section 6); none was found on radiographs, so this is untested on the project's kind of image and the validation frames decide.

Effort: 1 to 2 days. Grid: one CPU job reading every segmentation's centroids and extents, about 1 to 2 hours on 32 cores; the decode over the dumped posteriors runs in minutes. Risk: the prior can force a confident wrong answer on transitional spines, so the decoder abstains (the "?" the overlay already shows) when the 4/5/6-lumbar hypotheses are close, and the transitional stratum is reported apart.

### 2. Bank the rare-class renders already made

What: FluoroGen synth_rare (12,929 frames; 1,763 L6, 86 T13) and the synthetic L6 arm of CTSpinoPelvic1K (18 spines by 3 seeds) become train-side shards keyed by source volume, after the person-key chain proves no source CT is a test person's.

Why: the record holds three real L6 persons and they are all frozen test persons (retraining-plan.md 3.2), so any L6 the model learns before the talk comes from 3D. It costs no rendering. The scope keeps the synthetic anomaly arm's measurement apart from the real one, and that holds: these frames train, they are never scored as real.

Effort: half a day plus the leak checks (grid/run-leaks.sh). Grid: the bank and leak jobs, about an hour of CPU. Risk: the FluoroGen frames are diffusion-styled (SDXL with a Canny ControlNet and a fluoroscopy LoRA, datasets-reproduce.md), so a styled frame can disagree with its own label at the edges; the witness frames show whether it helps or hurts, and it is dropped if it hurts.

### 3. Pose-targeted renders with projected anchors, for AP and oblique

What: render new frames from CTSpinoPelvic1K and the TotalSegmentator v3 whole-spine subjects along the arc where naming collapses (AP and the obliques toward it, matched to C-ArmLSpine's angle bins but never to its persons), and carry down from 3D more than a box per vertebra: a per-pixel level map, a centroid per vertebra, and the anchors (the twelfth ribs from TotalSegmentator's rib labels, the S1 endplate, the iliac crests). Fine-tune version 1 from its checkpoint on them with an auxiliary head that predicts the anchors, so the network is taught where the count starts on views where the sacrum or the ribs are faint.

Why: AP views lose the lateral cues the encoder relies on; the anchors are what a radiologist counts from on an AP, and only the 3D labels give them for free and exactly. Training that resumes from a checkpoint with new shards is how the plan already grows (retraining-plan.md 3.4). Bier et al. trained landmark detection on simulated pelvis views over 120 by 90 degrees around AP and applied it to clinical images without retraining (section 6), which is the same move for anchors.

Effort: 2 to 3 days. Grid: rendering about 100,000 frames (1,000 volumes by 100 poses) is an estimated 1 to 3 GPU-hours on one H200 with a GPU renderer, dominated by reading volumes; the fine-tune is within the v1 run's 6 GPU-hour bound. Dependency: a GPU renderer (DiffDRR, MIT-licensed, PyTorch) or the project's own renderer from spinesurg-ct-nnunet; DiffDRR would be a new dependency, which the writing rule wants proposed as an issue first, so the project's renderer is the default and the issue is opened only if it is too slow.

### 4. Real frames with exact labels, from CTs registered to real projections

What: where a real X-ray comes with its own CT, the CT's segmentation projected through the X-ray's geometry labels the real frame exactly, which is how C-ArmLSpine's truth was made. COBRA is the large case: 692 cases of real CBCT projections with a registered planning CT, so a segmentation of the planning CT (TotalSegmentator) projected through the scanner's known geometry labels every lumbosacral vertebra on 375,618 real frames with no human reading. DeepFluoro's 2,293 unused vendor frames and IPCAI 2025's calibrated X-rays follow the same way, by 2D/3D registration where the geometry is not stored (the LevelCheck method, section 6).

Why: the record's clearest lesson is that detection needs real frames, and this is the only route to many real frames with level labels without a reader. It also feeds the sacrum anchor of items 1 and 3.

Effort: 3 to 5 days, most of it checking the projection on a sample by eye. Grid: segmentation of 692 planning CTs, an estimated 3 to 6 GPU-hours; projection, CPU-bound, an estimated 50 to 100 CPU-hours spread as an array job. Risk: COBRA covers only the pelvis and lumbosacral junction (the sacrum is in 18.2 % of its test frames, retraining-plan.md section 2), so it helps the low lumbar levels and the anchor, not the thoracic or cervical spine.

### 5. A physics renderer with strong randomisation

What: render with a physics model (material decomposition, scatter, quantum noise, detector response, as DeepDRR does) and randomise everything that is not anatomy (energy, scatter, noise, contrast, field of view, collimation, simulated hardware), as SyntheX did, and compare three arms on the validation frames: the current styled renders, plain DRRs and physics renders.

Why: the renders-only detector's 0.3 % may be the renderer's fault and not synthetic data's. DeepDRR's authors found networks trained on physics DRRs beat those trained on naive DRRs on real cadaver C-arm images (p < 0.01), and SyntheX found models trained only on realistic simulation with strong randomisation matched or beat models trained on precisely matched real data, for hip imaging, tool detection and lesion segmentation. Neither is the spine, so the ablation is the evidence, not the papers.

Effort: 3 to 5 days. Grid: 10 to 20 GPU-hours for the renders and three short fine-tunes. A new dependency (DeepDRR), so an issue first. After the talk.

### 6. Pretraining that knows the views are of one 3D object

What: before or beside supervised training, teach the encoder that two renders of the same vertebra from different angles are the same thing (a multi-view contrastive objective over DRR pairs), and add heads that predict 3D quantities the render knows exactly: the gantry angles, the depth order of the vertebrae. A predicted gantry angle also lets the decoder of item 1 and the tracker condition on view.

Why: view invariance is what fails between lateral and AP. A 2025 paper builds the same pipeline (multi-view contrastive backbone on DRRs, then localisation and identification) and validates on VerSe; its real-image results were not visible in what was read.

Effort: 1 to 2 weeks. Grid: 20 to 50 GPU-hours. After the talk.

### 7. Self-training on unlabelled real fluoroscopy

What: the model trained on renders and real labelled frames labels unlabelled real frames (COBRA projections outside item 4's labels, the non-test C-ArmLSpine sweeps' frames, the held video clips), keeps the confident ones that agree across consecutive frames of a sweep, and trains on them. The 3D chain of item 1 vets each pseudo-label: a sequence the prior rejects is dropped.

Why: it uses real appearance without a reader. Effort about a week; grid 20 to 40 GPU-hours. After the talk; the frozen test persons' frames are never pseudo-labelled.

### 8. Rare anatomy made in 3D

What: edit the segmented CTs before rendering, adding or removing a lumbar segment, a thirteenth rib, a sacralised L5, to make transitional spines with exact truth. Extends the synthetic anomaly arm, scored apart from the real one as the scope requires. Effort 1 to 2 weeks; grid modest. After the talk.

### The anomalies are labelled on CT and carried to X-ray (the owner, 2026-10-21 20:09 UTC)

The owner's words: "it's way easier to label anomalies on cat scan and it can be used as a prior for detecting them in XR. Also it's probably easier to find anomalies in ct and there are way more ct datasets. Incorporate the idea of this into the workflow." So a transitional spine is called once, on CT, where the whole column is seen and counted from C2 down, and that call feeds every X-ray step that follows:

- The counting prior (item 1) takes readers' CT calls, one row per scan (scan, column such as T12L5, T12L6 or T13L5, reader), through tools/chain_stats.py --columns. A call names the column even where the segmentation is cut short, so the odds of each column come from every scan a reader called, and the spacing laws of the transitional pairs (L6 to the sacrum, T13 to L1) come from the very CTs that show them.
- The renders (items 3 and 8) carry the call down: a CT called T12L6 renders frames whose labels say L6 exactly, so the X-ray model meets the anomaly with truth it could never get from a film.
- The anomaly harvest's census (datasets-inventory.md section 5, 144 CT sources screened, 56 on disk) is the first source of calls, the owner's reads the second, a second reader's the third; disagreements are kept as such and a scan two readers call differently is left out of the odds.
- The X-ray screening detector the owner asked for next (docs/research/xr-annotation-format.md) is trained on the same calls through the renders and on X-rays annotated in that format, and its finds on the unannotated films go back to readers for confirmation.

One caution the decoder's settings answer: a collection gathered because it holds anomalies inflates their odds. The odds should come from collections screened whole (the census counts every scan it screened, anomalous or not), and the abstain margin is set on validation frames, where too high an L6 odds shows as wrong L6 calls.

### Not recommended now

- Reconstructing 3D from the 2D frame at inference (X2CT-style): it adds latency and a second model for a labelling task the decoder of item 1 does more cheaply.
- Registering the patient's own preoperative CT at inference (LevelCheck as a product): accurate in its clinical studies but needs that CT and seconds per frame; a possible "CT available" mode later, outside the CT-free goal.
- Full CT-RATE: out by the owner's rule, and the CTs on disk are already more than items 1 to 8 can use.

## 4. For the talk

Results, not methods: a slide may show the AP accuracy before and after, the per-angle curve on the sweeps, the L6 cases named or abstained, and the latency, each with its interval and result file; nothing of items 1 to 8 is named on a slide before the provisional is filed. What can plausibly change a number by 2 November is items 1 to 3; the rest is the plan after it.

## 5. What needs the owner

- Which of items 1 to 3 to run before the talk (the recommendation is all three, in that order).
- Whether DiffDRR or DeepDRR may be added if the project's renderer is too slow (an issue first, per the writing rule).
- Grid jobs need no number (the owner, 2026-10-21 13:14 UTC), but they are submitted through the "SchwingNet video demo plan" thread.

## 6. Sources read

- Gao, Killeen et al., "SyntheX: Scaling Up Learning-based X-ray Image Analysis Through In Silico Experiments", arXiv 2206.06127 (2022), and its PMC version PMC10959504.
- Unberath et al., "DeepDRR, a Catalyst for Machine Learning in Fluoroscopy-guided Procedures", MICCAI 2018, LNCS 11073:98-106, arXiv 1803.08606; the physics-versus-naive DRR result is from the group's follow-up on cadaver C-arm images as summarised in the abstract.
- Bier et al., "X-ray-transform Invariant Anatomical Landmark Detection for Pelvic Trauma Surgery", MICCAI 2018, arXiv 1803.08608.
- Gopalakrishnan and Golland, "Fast Auto-Differentiable Digitally Reconstructed Radiographs for Solving Inverse Problems in Intraoperative Imaging", CLIP workshop at MICCAI 2022; the software DiffDRR (github.com/eigenvivek/diffdrr).
- Lo et al., LevelCheck, Spine 2015 (20 patients, correct labelling), and the I-STAR group's clinical study of 398 radiographs; Johns Hopkins BME news pages.
- Ahmad, Ali and Jung, multi-view learning for vertebrae identification in DRRs, 2025 (Kyungpook National University's research portal; real-image evaluation not visible in the abstract).
- "Pushing the limits of an FCN and a CRF towards near-ideal vertebrae labelling" (TU Dresden, arXiv 2108.06554), the anatomical-prior CRF in CT.
- A 2022 multi-view, multi-slot network labelling vertebrae on AP and lateral intraoperative images at 88.3 %, found by search and not read in full.
