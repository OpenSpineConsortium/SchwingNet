# A recipe for the final dataset

Source: the thread "Fit datasets under the 20 TB cap", 2026-10-25, on the owner's ask of 03:48 UTC: "can i get an artefact with some assistance and what different results, papers, and benchmarks, including my own research tell me about including these different datasets to get me a recipe for a final dataset handcrafted to reach me goal of limited FOV classification anywhere on the spine robust to anomaly, rotation, acquistion machine, and domain". Issue #289. It builds on spine-datasets' inclusion audit of the same night (spine-datasets docs/research/dataset-inclusion-audit.md, spine-datasets#250), which classified all 166 records against the owner's three automatic rules. It was written from the notes named beside each line, read at main 12f3ae0; no paper, grid job or fetch was read for it. The interactive form is Figure 16.1 (docs/textbook/figures/16/dataset-recipe.html). Confidential with the rest of this repository (docs/project.md): it names methods.

## 1. The goal, split into five demands

The goal is to name the vertebral level on a limited-field X-ray anywhere from C1 to the sacrum, robust to anomaly, rotation, acquisition machine and domain. Each of those is a demand on the dataset, and each is answered by different sets:

- R, anywhere with a limited field: anatomy at every level, the anchors that let a spot frame be counted, and tests in every region.
- A, anomaly: transitional spines, rib-count variants, lesions, fractures and metal, labelled.
- O, rotation: real rotations and AP and lateral pairs of one person.
- M, acquisition machine: real frames from as many classes of device as can be had.
- D, domain: renders that look like the clinic, and a population that matches the patients.

## 2. What the evidence says, demand by demand

Grades as state-of-knowledge.md defines them: Measured is this project's own record, Published is shown in a paper, Inferred is reasoned.

| Demand | Finding | Grade | Where it rests | What it asks of the dataset |
| --- | --- | --- | --- | --- |
| R | Lateral naming on an unseen C-arm reaches 96.4 % (595 of 617) zero-shot, from renders | Measured | state-of-knowledge.md row 1 | CT with good level truth is the core |
| R | 5 of 6 real spine pairs stop at L1; one cadaver reaches T2; no cervical pair exists | Measured | state-of-knowledge.md section 4 | cervical and thoracic truth comes from CT renders and films, with tests kept apart |
| R | A spot frame of T7 shows neither C2 nor S1; every whole-spine method counts from a visible end | Inferred | lumbosacral-to-cervical-extrapolation.md section 1 | render and crop at spot field; keep the sets that show the anchors |
| R | Cervical naming 69 % and 92 % at two sites; thoracic weakest in most tables | Published | lumbosacral-to-cervical-extrapolation.md section 3 | weight toward the regions with least real truth |
| R | Render-trained labelling reached 88.3 % on real Long-Film images (Huang 2022) | Published | lumbosacral-to-cervical-extrapolation.md section 3 | whole-spine renders work at long field; spot field is open |
| A | The only real persons with an L6 are three frozen test persons | Measured | state-of-knowledge.md section 1 | the anomaly stratum is CT |
| A | TotalSegmentator has no L6 and shifts labels on lumbarisation; junction Dice falls 29 points (the owner's CTSpinoPelvic1K audit) | Published | lumbosacral-to-cervical-extrapolation.md section 3 | automatic masks enter after the column count is read |
| A | With anomaly labels in training 96 to 97 % of count anomalies are found; without, 22 to 26 % of thoracic ones (VERIDAH) | Published | lumbosacral-to-cervical-extrapolation.md section 3 | keep every set that carries anomalies, however small |
| A | 12,929 rare-class renders (1,763 L6, 86 T13) sit in no bank | Measured | ct-priors-for-2d-detection.md section 1 | bank them (#58) before buying more |
| O | AP naming 43.7 % zero-shot, a one-level cranial shift | Measured | state-of-knowledge.md row 2 | a counting error: the counting prior (#57) and anchors (#59), not more AP images |
| O | No paper reports naming by angle | Inferred | state-of-knowledge.md row 17 | keep real rotations: COBRA, C-ArmLSpine's sweeps, the moved C-arm series |
| O | A synthesised lateral guesses depth; an anomaly seen only on the lateral cannot come back | Inferred | xr-from-3d/README.md section L | keep real AP and lateral pairs as the view-transfer test |
| M | No frame of the device 7.0 %; 24 frames 84.0 %; 95 % of the plateau by 10 to 12 frames | Measured | state-of-knowledge.md row 4 | breadth of devices beats depth |
| M | Renders alone detect 0.3 %; with other devices' real frames 80.5 % | Measured | state-of-knowledge.md rows 3 and 4 | real frames from several devices are required |
| M | One renderer 11.7 mm, four with randomisation 6.4 mm (Grimm 2021) | Published | lumbosacral-to-cervical-extrapolation.md section 2 | keep a second renderer's output (PENGWIN task 2) |
| M | Siemens against Ziehm on lumbar specimens: no clear difference (Jecklin 2024) | Published | lumbosacral-to-cervical-extrapolation.md section 1 | spread across device classes matters more than within one |
| D | Renders of DeepFluoro's own CTs found its sacrum on 90 to 97 % of frames; living-CT renders 64 to 77 % | Measured | drr-realism-against-our-results.md | match the render population to the patients |
| D | After translation a vertebra gap stays: about three times the registration error, about 0.07 Dice | Published | lumbosacral-to-cervical-extrapolation.md section 2 | fit the correction on pairs and keep real frames per device |
| D | FleXray: Cobb MAE 5.13 on AASCE, Dice 0.915 on DeepFluoro; FluoroSAM 31.82 with 42 failures on AASCE | Published | arcade-lab-x-ray-learning-against-schwingnet.md section 2 | keep AASCE and DeepFluoro as the field's external tests |
| D | COBRA's projections are linac CBCT, not C-arm | Inferred | xr-from-3d/README.md section D | keep C-arm pairs beside it |
| D | Registration to the patient's CT names levels at 99.3 to 100 %, at 7 to 26 s a frame (LevelCheck) | Published | benchmarks-to-beat.md section 2 | registration-labelled real frames (#60) are the cheapest exact truth on a new device |

## 3. The recipe

Nine rules follow from the table. They set what each stratum is for; they do not set proportions, since no synthetic-to-real ratio has been swept (state-of-knowledge.md section 6) and the block sweep's samples block (#202) is where those are tried.

1. Real frames from many devices. Keep every real C-arm and fluoroscopy set with labels, however small, and seek new devices first.
2. Anatomy from CT, C1 to S1. Keep the read CT sets (VerSe, CTSpinoPelvic1K, CTSpine1K, CTPelvic1K, CSI 2014) and the whole-spine ones (TotalSegmentator, the post-mortem whole bodies, RSNA cervical). Read the column count, ribs included, before any render, and count each person once across the overlapping sets (CTSpine1K and CTSpinoPelvic1K share 526 scans).
3. Anomalies labelled, not inferred. Keep every CT carrying a transitional spine, a rib-count variant, a lesion, a fracture or metal, and the anomaly harvest's tier-1 collections, whose level calls give the counting prior its odds.
4. Rotation from real rotations, with the AP shift fixed by counting, not by more AP images.
5. Spot field on purpose: crop to a spot field as well as the long field, and test with and without an anchor in view.
6. A render population that matches: prefer living-patient CT, use more than one renderer, randomise everything that is not anatomy.
7. The correction fitted where pairs exist (DeepFluoro, Ljubljana, COBRA, C-ArmLSpine above a pose-quality bar); that it carries above L1 is untested.
8. Tests held out by person and by device. Cervical: CSXA and NHANES II re-keyed out of the v9 base, Aariz, Bournemouth's tracks. Thoracic: AASCE, the twin's cadaver, MrOS and SOF once obtained. Lumbar: C-ArmLSpine's test persons. Unseen device: Geneva.
9. Drop what the spine is incidental to: chest radiograph collections, and abdominal or chest CT with no spine labels and no harvest calls. NLST is worth a stratified subset with every harvested anomaly, not all 24,713 people.

Applied to the 166 records, the figure's recommendation keeps 76 sets (3.49 TB held), leaves 33 to the owner (2.26 TB held), drops 28 (1.89 TB held), asks for 12 not yet held and defers 17. Two kinds of set the audit called candidates or flagged turn out to earn a place by these rules: the coronary and swallow fluoroscopy, which give the chest's scatter and the mandible over C2 on real frames, the appearance no lumbosacral pair holds (Inferred); and RibFrac's rib labels, since ribs are the thoracic anchors and eleven or thirteen ribs are count anomalies.

## 4. Gaps no held set fills

| Gap | What would fill it |
| --- | --- |
| No cervical C-arm frame with the patient's CT exists anywhere searched | the owner's own cervical and thoracic captures with the CT; the LevelCheck cohort (178 patients, cervical to lumbar) |
| One specimen is the only real C-arm pair above L1 | the digital twin's cadaver as a thoracic test, never training |
| No thoracic real truth at scale is held | MrOS and SOF, about 15,700 people with grades per named level |
| Real cervical fluoroscopy is held as tracks without pixels | Bournemouth's cine, Maastricht, Pittsburgh's swallow clips |
| C-ArmLSpine's poses are unmeasured | reprojection distance on held-out landmarks (#127) |
| No synthetic-to-real ratio was swept | the samples block of the block sweep (#202) |

## 5. What this note does not settle

The calls are a reading of the evidence, not a measured result: which strata actually move naming on a real frame is what the ablation ladder (#131) and the block sweep measure. Licences are flagged, not decided: COBRA, DeepFluoro, LUMOS, CTSpinoPelvic1K and Ljubljana carry non-commercial or no-derivatives terms, and which a product may rest on is the lawyer's question already on the owner's list.
