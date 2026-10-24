# Concepts the synthesis has settled, and where every text stands

The figures the synthesis has settled, and every text checked against them.

A concept is a figure and the words that say what it is a figure of. Two kinds are kept in work/out/concepts.json. A dataset count comes from a record under data/sources/: its name gives the aliases a text calls the set by (work/aliases.json replaces them where the name gives none or the wrong ones), and each count is a figure with the noun that counts it. A settled figure comes from a number verdict of the contradictions record that put two values on one quantity: its anchors are the rarer words its two quotes share, with the quantity's words that either quote carries, and each value is current, superseded or open by the verdict. updated-later makes current the side whose figure the ruling's hint carries, else the later page by the inventory's dates; same-number-restated makes both current; a confirmed contradiction, cannot-tell or an updated-later whose later side neither says leaves both open. A settled figure is used only when its own two quotes pass the rule it is checked by, so one whose evidence the rule does not recognise is listed and not used.

Every artifact's text, every research note under docs/research/ and each dataset record's own words are then rid of e-mail addresses and phone numbers, as extract.py rids an artifact's, scrubbed of what the folder's rule keeps out of the records (redact.py) and read passage by passage, so that no passage, no words a check keeps and no check's key holds any of it, whole or cut; a check's key therefore changes with those patterns, and `synth.py rekey` carries the stamp's word over such a change. In a passage that names a dataset, each figure goes to the nearest name within 160 characters, or to every name equally near: equal to one of those sets' counts it agrees, and where a count's noun follows it, it is rounded when it is that count written with fewer digits and differs when it is within a tenth of it (a thirtieth for a size). A dataset record's own words are checked against its own counts the same way. A passage that carries at least two of a settled figure's anchors, half of their weight by rarity, and one of its values written the same way or rounded agrees, is superseded or is open as that value is; a passage in the figure's own two artifacts is its evidence and is not checked. Nothing here judges: a check is a script's match, for a person or a skeptic to read.

Rendered on 2026-10-24 from 277 texts by work/tools/synth.py concepts, or by the join of a run of .github/workflows/synthesis.yml that read something. That workflow checks every text against the ledger daily, on Run workflow and on a push a person or an App makes that changes an artifact, a research note or a dataset record, and the issue labelled synthesis lists what each run found that the stamp of 2026-10-24 had not seen. Edit the records and render again rather than editing this file.

## Summary

- Dataset counts: 175, from 86 records under data/sources/.
- Settled figures: 63, 33 used and 30 not used (listed at the end).
- Checks: 802 agrees, 3 rounded, 3 superseded, 52 open, 24 differs.

## Dataset counts

Each record's counts with the lines that give one of them otherwise; the lines that agree are counted, not listed.

No text is checked against the counts of these records, since their names give none the rule reads; a record's names added under its id in work/aliases.json, by pull request, are checked from the next run on:

- coronary_angiography: Coronary angiography sets (CADICA, ARCADE, XCAD, AngioCAD) (cadica_patients, arcade_images, xcad_images, angiocad_patients)
- fluoro_video_clips: Public fluoroscopy clips on the grid (size_gb)
- implant_ct_synthetic: Synthetic hardware CTs: implant_ct (CTSP, deleted), implant_verse, implant_ts (implant_verse_subjects, implant_verse_volumes, implant_verse_size_gb, implant_ts_subjects, implant_ts_volumes, implant_ts_size_gb)
- jefferson_drg: Jefferson Neurosurgery DRG stimulation video (Hines 2020) (videos)
- maastricht_cervical: Maastricht UMC+ cervical flexion-extension cine (van Santbrink 2026) (recordings)
- procedure_guide: The Procedure Guide (Puranik) live fluoroscopy clips (clips)
- sof_lateral_spine: SOF lateral spine radiographs (Study of Osteoporotic Fractures) (women_about)
- veriserum: Veriserum (ETH Zurich, MICCAI 2025) (images_about)
- veterinary_pig_levelcheck: Veterinary: pig lower limb CT, CBCT and planar images (Goswami 2020, IEEE DataPort) (size_mb)

### Aariz cephalometric benchmark (Khalid, Fraz 2023) and the ISBI 2015 cephalograms (aariz_cephalograms)

Called 'isbi 2015'; counts films 1000, devices 7, landmarks 29, isbi_2015_films 400, zip_bytes 2098209792; 27 lines agree.

### AASCE / BoostNet whole-spine films (aasce)

Called 'aasce', 'boostnet'; counts labelled_films 609, challenge_test_films 98, thoracic_test_films 608; 28 lines agree.

### STOIC2021 training (AWS Open Data) (aws_stoic2021)

Called 'stoic2021'; counts subjects 2000, size_gb 240; 9 lines agree.

| Count | Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|---|
| subjects | rounded | 2026 | [docs/research/datasets-inventory.md](../../docs/research/datasets-inventory.md) | 161 | \| STOIC2021 training (AWS Open Data) \| STOIC2021 training set, 2,000 chest CT as MHA on AWS Open Data (s3://stoic2021-training; LICENCE.txt read 2026-09-23), about 240 GB; also inside CADS (gated) and |
| size_gb | differs | 246.1 | [docs/research/data-manifest/MANIFEST.md](../../docs/research/data-manifest/MANIFEST.md) | 22 | \| unmapped aws_stoic2021 \| 2034 \| 246.1 GB \| 2000 \| 366 \| 1634 \| metaimage 2000, other 33, json 1 \|  \| |

### Bournemouth cervical quantitative fluoroscopy (BORDaR 385) (bournemouth_cervical_qf)

Called 'bournemouth cervical'; counts sequences 252, people 63, frames_per_sequence_median 301; 4 lines agree.

### Bournemouth lumbar quantitative fluoroscopy (Breen 2021) (bournemouth_lumbar_qf)

Called 'bournemouth lumbar'; counts subjects 127; 2 lines agree.

### BUU-LSPINE (buu_lspine)

Called 'buu lspine'; counts lateral_films 3603, ap_films 3600, people 3600; 50 lines agree.

### Veterinary: canine lateral thoracic radiographs for vertebral heart size (Mendeley ktx4cj55pn) (canine_thoracic_vhs)

Called 'ktx4cj55pn'; counts radiographs 152; 4 lines agree.

### C-ArmLSpine (Surgio-B51) (carmlspine)

Called 'c armlspine', 'surgio b51'; counts cases 149, spot_frames 299, cbct_volumes 149, size_gb 86.834, l6_cases 3; 54 lines agree.

| Count | Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|---|
| cases | differs | 148 | [or-readiness-ledger](../or-readiness-ledger/) | 22 | Level naming, real OR laterals 98.2% exact level on whole C-ArmLSpine lateral frames, five-fold CV over 148 cases [95.7-100]; 92.9% with three vertebrae in the field, 72.8% with one |
| cases | differs | 148 | [state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay](../state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay/) | 121 | \| Whether C-ArmLSpine's 148 or 149 cases are that many people, whether they were living, and its ethics approval \| It is the only intraoperative human data; files record 149 cases, 148 cases and 120 s |
| cases | differs | 148 | [state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay](../state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay/) | 135 | - C-ArmLSpine: 149 cases, 148 cases with 296 frames, or 120 distinct subjects. |
| spot_frames | differs | 296 | [state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay](../state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay/) | 135 | - C-ArmLSpine: 149 cases, 148 cases with 296 frames, or 120 distinct subjects. |

### C-ArmLSpine CBCT projection sweeps (case134, case39) (carmlspine_sweeps)

Called 'c armlspine cbct', 'case134', 'case39'; counts sweeps 2, projections 602; 6 lines agree.

### CathAction (Jianu et al. 2024, AIRVLab) (cathaction)

Called 'cathaction'; counts frames_about 500000, zip_1_gb 4.35, zip_2_gb 9.88; 20 lines agree.

### CheXpert and CheXpert Plus (Stanford AIMI) (chexpert_plus)

Called 'chexpert', 'chexpert plus'; counts radiographs 224316, patients 65240; 6 lines agree.

### COBRA2026 Elekta (cobra_elekta)

Called 'cobra2026 elekta'; counts cases 467; 1 lines agree.

### COBRA2026 embargoed cases (cobra_embargoed)

Called 'cobra2026'; counts cases 175; 1 lines agree.

### COBRA2026 on the grid, all projections (cobra_total)

Called 'cobra2026'; counts cases 692, projections 375618, size_gb 808.615; 23 lines agree.

### COBRA2026 Varian (cobra_varian)

Called 'cobra2026 varian'; counts cases 225; 1 lines agree.

### Coronary angiography sets (CADICA, ARCADE, XCAD, AngioCAD) (coronary_angiography)

Called ; counts cadica_patients 42, arcade_images 3000, xcad_images 1747, angiocad_patients 413; 8 lines agree.

### CSXA cervical lateral films (csxa)

Called 'csxa'; counts films 4963; 18 lines agree.

| Count | Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|---|
| films | differs | 5,300 | [level-context-ladder-xd7eltc](../level-context-ladder-xd7eltc/) | 203 | { label: "cervical . ~5,300 CSXA + NHANES films", v: 97.7, color: "var(--s3)", note: "levels annotated" }, |

### CTSpinoPelvic1K (the project's own release v11) (ctspinopelvic1k)

Called 'ctspinopelvic1k'; counts ct_volumes 802, l6_cases 18; 31 lines agree.

| Count | Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|---|
| ct_volumes | differs | 782 | [research-directions-from-the-data-holding-kcyckb](../research-directions-from-the-data-holding-kcyckb/) | 186 | \| CTSpine1K \| 1,005 volumes \| expert VerSe-convention masks \| the authors list 24 lumbarisation and 13 sacralisation \| 782 COLONOG volumes are CTSpinoPelvic1K persons \| |
| ct_volumes | differs | 817 | [docs/research/datasets-inventory.md](../../docs/research/datasets-inventory.md) | 140 | \| Synthetic hardware CTs: implant_ct (CTSP, deleted), implant_verse, implant_ts \| project-generated synthetic hardware CTs (tools/make_implant_ct.py over real volumes): implant_ct from CTSpinoPelvic1K |

### DeepFluoro (Cios Fusion) (deepfluoro)

Called 'deepfluoro'; counts specimens 6, h5_frames 366, vendor_frames 2659, size_gb 116.26; 33 lines agree.

### FluoroCap literature panels (fluorocap)

Called 'fluorocap'; counts panels 29500, size_gb 316; 9 lines agree.

| Count | Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|---|
| panels | rounded | 29,484 | [or-readiness-ledger](../or-readiness-ledger/) | 24 | Leakage 0 pairs no test frame is in any training corpus (37,165 films + 29,484 FluoroCap panels + 1,445 yolo_v6f searched); splits disjoint by case; two arm generations now told apart |
| panels | rounded | 29,484 | [or-readiness-ledger](../or-readiness-ledger/) | 43 | \| Real test frames against every external corpus \| \| 0 pairs >= 0.97 against 37,165 film images, 29,484 FluoroCap panels, 1,445 yolo_v6f; FluoroCap's article list has no DeepFluoro / C-ArmLSpine / COB |

### FluoroGen synth_rare renders (fluorogen_synth_rare)

Called 'fluorogen'; counts renders 12929; 4 lines agree.

### FracAtlas (Abedeen 2023, Scientific Data) (fracatlas)

Called 'fracatlas'; counts radiographs 4083, hospitals 3; 3 lines agree.

### Fraiwan spine X-ray set (Mendeley xkt857dsxk) (fraiwan_spine_xray)

Called 'xkt857dsxk'; counts subjects 338, classes 3; 4 lines agree.

### Geneva hip phantom (BV Pulsera) (geneva_hip)

Called 'geneva hip'; counts frames 116; 8 lines agree.

### Guide3D (ACCV 2024, AIRVLab) (guide3d)

Called 'guide3d'; counts frames_over 8700; 4 lines agree.

### AbdomenAtlas 2.0 Mini (10,135 CT) (hf_abdomenatlas2_0_mini)

Called 'abdomenatlas'; counts volumes 10135, size_gb 620.4; 11 lines agree.

### IDC `cptac_lscc` (tier 2) (idc_cptac_lscc)

Called 'cptac lscc'; counts subjects 32, size_gb 8.3; 4 lines agree.

### IDC `cptac_luad` (tier 2) (idc_cptac_luad)

Called 'cptac luad'; counts subjects 32, size_gb 7; 2 lines agree.

### IDC `ldct_and_projection_data` (tier 2) (idc_ldct_and_projection_data)

Called 'ldct and projection data'; counts subjects 99, size_gb 16.5; 4 lines agree.

### IDC `lidc_idri` (tier 2) (idc_lidc_idri)

Called 'lidc idri'; counts subjects 997, size_gb 123.3; 4 lines agree.

### IDC `midrc_ricord_1b` (tier 2) (idc_midrc_ricord_1b)

Called 'midrc ricord 1b'; counts subjects 91, size_gb 7; 2 lines agree.

### NLST, full (tier 2; 500-person pilot fetched) (idc_nlst)

Called '500 person', 'nlst'; counts subjects 24713, size_gb 2305.3, pilot_subjects_fetched 500; 13 lines agree.

### IDC `nsclc_radiogenomics` (tier 2) (idc_nsclc_radiogenomics)

Called 'nsclc radiogenomics'; counts subjects 188, size_gb 28; 4 lines agree.

### IDC `nsclc_radiomics` (tier 2) (idc_nsclc_radiomics)

Called 'nsclc radiomics'; counts subjects 415, size_gb 25.8; 4 lines agree.

### IDC `prostate_anatomical_edge_cases` (tier 2) (idc_prostate_anatomical_edge_cases)

Called 'prostate anatomical edge cases'; counts subjects 131, size_gb 16.6; 4 lines agree.

### IDC `spinal_multiple_myeloma_seg` (tier 2) (idc_spinal_multiple_myeloma_seg)

Called 'spinal multiple myeloma seg'; counts subjects 67, size_gb 33.8; 5 lines agree.

### IDC `spine_mets_ct_seg` (tier 2) (idc_spine_mets_ct_seg)

Called 'spine mets ct seg'; counts subjects 54, size_gb 17.2; 5 lines agree.

| Count | Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|---|
| size_gb | differs | 17.4 | [docs/research/data-manifest/MANIFEST.md](../../docs/research/data-manifest/MANIFEST.md) | 67 | \| unmapped idc_spine_mets_ct_seg \| 35531 \| 17.4 GB \| 0 \| 0 \| 0 \| dicom 35527, other 2, json 1 \|  \| |

### IEEE DataPort lateral whole-spine 236 (ieee_dataport_lateral_236)

Called 'dataport'; counts films 236; 6 lines agree.

### Synthetic hardware CTs: implant_ct (CTSP, deleted), implant_verse, implant_ts (implant_ct_synthetic)

Called ; counts implant_verse_subjects 373, implant_verse_volumes 1119, implant_verse_size_gb 187, implant_ts_subjects 817, implant_ts_volumes 1629, implant_ts_size_gb 39; 8 lines agree.

| Count | Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|---|
| implant_verse_subjects | differs | 355 | [data/sources/implant_ct_synthetic.json](../../data/sources/implant_ct_synthetic.json) | 2 | on_disk_partial in the data platform at bf1432f: implant_ct deleted, implant_verse complete (1,119 = 373 x 3), implant_ts unfinished (355 subjects never processed), cases 0394 and 0405 produced nothin |
| implant_ts_subjects | differs | 799 | [data/sources/implant_ct_synthetic.json](../../data/sources/implant_ct_synthetic.json) | 1 | project-generated synthetic hardware CTs (tools/make_implant_ct.py over real volumes): implant_ct from CTSpinoPelvic1K, 799 subjects and 1,518 volumes, deleted (427 GB); implant_verse 373 subjects, 1, |
| implant_ts_volumes | differs | 1,518 | [data/sources/implant_ct_synthetic.json](../../data/sources/implant_ct_synthetic.json) | 1 | project-generated synthetic hardware CTs (tools/make_implant_ct.py over real volumes): implant_ct from CTSpinoPelvic1K, 799 subjects and 1,518 volumes, deleted (427 GB); implant_verse 373 subjects, 1, |

### IPCAI 2025 paired X-ray and CT set of the distal femur (Flepp 2025, Zenodo 15753063) (ipcai2025_xray_ct)

Called 'ipcai 2025'; counts specimens 5, xrays 50, ct_scans 5, size_gb 6.7; 9 lines agree.

### Kaggle bone fracture multi-region X-ray data (bmadushanirodrigo) (kaggle_fracture_multiregion)

Called 'kaggle bone'; counts radiographs 10580, size_mb 481; 4 lines agree.

### KUB-StoneX (Daffodil International University HIRL) (kub_stonex)

Called 'kub stonex'; counts radiographs 2570, patients 1703, hospitals 2, zip_bytes 20765554562; 14 lines agree.

### Ljubljana 2D-3D-GS (PIXIUM 4600) (ljubljana_2d3d_gs)

Called '2d 3d gs'; counts frames 18; 4 lines agree.

### LUMOS (Zhejiang University) (lumos)

Called 'lumos'; counts patients 803, radiographs 1620, ct_volumes 280, size_gb 46.4; 28 lines agree.

### Maastricht UMC+ cervical flexion-extension cine (van Santbrink 2026) (maastricht_cervical)

Called ; counts recordings 112; 1 lines agree.

### Mendeley 5jdfdgp762 spondylolisthesis films (mendeley_5jdfdgp762)

Called '5jdfdgp762'; counts films 714; 8 lines agree.

| Count | Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|---|
| films | differs | 716 | [data/sources/mendeley_5jdfdgp762.json](../../data/sources/mendeley_5jdfdgp762.json) | 2 | about 500 are BUU people redistributed, so it adds no new person; the Mendeley page as summarised in search (the sweep of 2026-10-21) says 698 (one reading) or 716 (another) sagittal lumbar films, 508 |

### Mendeley DDH hip sets (jf3pv98m9g and 4gvcb6gmh2) (mendeley_ddh_hips)

Called '4gvcb6gmh2', 'jf3pv98m9g'; counts jf3pv98m9g_subjects 354, av_ddh_films 2417; 8 lines agree.

### MIMIC-CXR and MIMIC-CXR-JPG (PhysioNet) (mimic_cxr)

Called 'mimic cxr', 'mimic cxr jpg'; counts radiographs 377110, studies 227835, patients 65379; 13 lines agree.

### MrOS lateral spine radiographs (Osteoporotic Fractures in Men) (mros_lateral_spine)

Called 'mros'; counts men 5994, centres 6; 5 lines agree.

### NHANES II annotated films (nhanes2_annotated)

Called 'nhanes ii'; counts films 543, persons 364; 15 lines agree.

### NHANES II unannotated films (nhanes2_unannotated)

Called 'nhanes ii'; counts films 16531; 7 lines agree.

| Count | Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|---|
| films | differs | 17,075 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 205 | ve long-length images" ( doi.org ), were never released; Veriserum ( arxiv.org ) is ~110,000 real dual-plane frames of knee-implant phantoms with no anatomy; SpineDepth is RGB-D. Real films with nativ |
| films | differs | 17,073 | [imaging-data-holding-manifest-migration-and-index-fqmtjs](../imaging-data-holding-manifest-migration-and-index-fqmtjs/) | 49 | \| NHANES II \| plain film, lateral \| CDC films; Zenodo landmark set \| HTTP loop \| 9 to 23 Sept 2026 \| 17,073 films; 543 landmarked \| landmarks on 543 \| |
| films | differs | 17,073 | [research-directions-from-the-data-holding-kcyckb](../research-directions-from-the-data-holding-kcyckb/) | 59 | \| NHANES II \| 364 persons landmarked; 17,073 films on disk \| none read; the detector boxes a sacrum on 1.8 % of lumbar films \| expert landmarks on 543 \| 16,531 films in no trained bank; entered the ol |
| films | differs | 17,073 | [docs/research/data-manifest/README.md](../../docs/research/data-manifest/README.md) | 27 | (297 annotated). Across regions, unsplit here: NHANES II 17,073 films (the registry says 543 |
| films | differs | 16,234 | [data/sources/nhanes2_unannotated.json](../../data/sources/nhanes2_unannotated.json) | 2 | unused by a written criterion; the VertXNet Zenodo record adds radiologist landmarks with vertebral identity and the reference bodies C2 and S1 to the NHANES II films (record vertxnet_nhanes2_labels, |

### NIH ChestX-ray14 and the RSNA pneumonia subset (nih_chestxray14)

Called 'chestx ray14'; counts films 112120, patients 30805, rsna_subset_films 30000; 9 lines agree.

### Open-i Indiana chest collection (open_i_chest)

Called 'open i indiana'; counts radiographs 7470, studies 3955; 6 lines agree.

### PadChest (BIMCV, Alicante) (padchest)

Called 'padchest'; counts radiographs 160868, patients 67625, projections 109; 13 lines agree.

### IRI-VFI: pediatric interventional radiology image sequences (Chongqing) (pediatric_iri)

Called 'iri vfi'; counts images 95308, sequences 1357; 8 lines agree.

### PENGWIN 2024 Task 2 synthetic X-rays (pengwin_task2_xrays)

Called 'pengwin 2024 task 2'; counts images 50000, cts 100; 5 lines agree.

### Pittsburgh videofluoroscopic swallow corpus (Sejdic, Coyle) (pittsburgh_swallow)

Called 'pittsburgh videofluoroscopic'; counts clips 1500, subjects 335; 2 lines agree.

### The Procedure Guide (Puranik) live fluoroscopy clips (procedure_guide)

Called ; counts clips 4; 1 lines agree.

### ReXGradient-160K (Rajpurkar lab and Gradient Health, 2025) (rexgradient_160k)

Called 'rexgradient 160k'; counts studies 160000, patients 109487, sites 79; 14 lines agree.

### RSNA 2022 cervical spine fracture CT (rsna_2022_cervical)

Called 'rsna 2022'; counts studies 2019, size_gb 203; 17 lines agree.

| Count | Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|---|
| studies | differs | 2026 | [imaging-data-holding-manifest-migration-and-index-fqmtjs](../imaging-data-holding-manifest-migration-and-index-fqmtjs/) | 40 | \| RSNA 2022 cervical spine \| CT \| Kaggle challenge \| zip, 203 GB \| 19 Sept 2026 \| 2,019 studies \| fracture labels; used by nothing \| |
| studies | differs | 2022 | [research-directions-from-the-data-holding-kcyckb](../research-directions-from-the-data-holding-kcyckb/) | 192 | \| RSNA 2022 cervical \| 2,019 studies \| per-level fracture labels \| none \| zip never unpacked; used by nothing \| |
| studies | differs | 2022 | [docs/research/data-manifest/README.md](../../docs/research/data-manifest/README.md) | 52 | RSNA 2022 cervical 2,019 studies (189 GB, still zipped), the spine metastasis set (35,527 |

### ENHANCE.PET 1.6k: whole-/total-body FDG-PET/CT, 1,683 studies (NIfTI) (scidb_enhance_pet_1_6k)

Called 'enhance pet 1 6k', 'fdg pet ct'; counts studies 1683, size_gb 286.3; 8 lines agree.

### Seattle Science Foundation spine videos (seattle_science_foundation)

Called 'seattle science'; counts videos 12; 4 lines agree.

### SOF lateral spine radiographs (Study of Osteoporotic Fractures) (sof_lateral_spine)

Called ; counts women_about 9700; 1 lines agree.

### Spinal-AI2024 (spinal_ai2024)

Called 'spinal ai2024'; counts films 20000; 6 lines agree.

### SpineSAC (spinesac)

Called 'spinesac'; counts frames 5490; 5 lines agree.

### TotalSegmentator v2 and v3 (totalsegmentator)

Called 'totalsegmentator v2'; counts v2_scans 1228, v3_scans 1935; 10 lines agree.

| Count | Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|---|
| v3_scans | differs | 1,936 | [docs/research/data-manifest/README.md](../../docs/research/data-manifest/README.md) | 49 | 4,325 image files, 1,652 with labels), TotalSegmentator v2.0.1 1,631 and v3.0.0 1,936 scans, |

### Veriserum (ETH Zurich, MICCAI 2025) (veriserum)

Called ; counts images_about 110000; 1 lines agree.

### VerSe 19 and 20 (verse)

Called 'verse 19'; counts series 374, subjects 355; 7 lines agree.

### Veterinary: pig lower limb CT, CBCT and planar images (Goswami 2020, IEEE DataPort) (veterinary_pig_levelcheck)

Called ; counts size_mb 205; 1 lines agree.

### VFSS2022 videofluoroscopic swallow frames (TIB) (vfss2022)

Called 'vfss2022'; counts frames 440; 4 lines agree.

### VinDr-CXR (PhysioNet) (vindr_cxr)

Called 'vindr cxr'; counts radiographs 18000, hospitals 2; 3 lines agree.

### VinDr-PCXR (PhysioNet) (vindr_pcxr)

Called 'vindr pcxr'; counts radiographs 9125; 4 lines agree.

### VinDr-SpineXR (vindr_spinexr)

Called 'vindr spinexr'; counts images 10466, studies 5000; 23 lines agree.

### LumVBCanSeg lumbar CT (185, ShengJing Hospital) (zenodo_lumvbcanseg)

Called 'lumvbcanseg'; counts subjects 185, size_gb 10.08; 10 lines agree.

### MedPelvis3D pelvic CT (99, PLA General Hospital) (zenodo_medpelvis3d)

Called 'medpelvis3d'; counts subjects 99, size_gb 15.1; 9 lines agree.

### International TMTV Benchmark, lymphoma FDG PET/CT (60) (zenodo_tmtv_benchmark)

Called 'pet ct', 'tmtv benchmark'; counts subjects 60, size_gb 6.85; 10 lines agree.

### TotalSegmentator task data 'hip_implant' (71 CT) (zenodo_ts_task_hip_implant)

Called 'totalsegmentator'; counts subjects 71, size_gb 9.03; 12 lines agree.

### TotalSegmentator task data 'liver_lesions' (842 CT) (zenodo_ts_task_liver_lesions)

Called 'totalsegmentator'; counts subjects 842, size_gb 38.87; 9 lines agree.

| Count | Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|---|
| subjects | differs | 802 | [state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay](../state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay/) | 55 | \| CT labelling with anomalies \| VerSe (Sekuboyina 2021); VERIDAH (Moller 2026); TotalSegmentator (Wasserthal 2023) \| 355 patients; 1,536 CTs; 1,204 CTs \| 802 patients; 129 count-changing transitional |
| size_gb | differs | 39.6 | [docs/research/data-manifest/MANIFEST.md](../../docs/research/data-manifest/MANIFEST.md) | 51 | \| unmapped totalsegmentator_v201 \| 153322 \| 39.6 GB \| 1631 \| 0 \| 1631 \| nifti-gz 146936, json 2824, npy 2330 \|  \| |

### TotalSegmentator task data 'pleural_pericard_effusion' (600 CT) (zenodo_ts_task_pleural_effusion)

Called 'totalsegmentator'; counts subjects 600, size_gb 8.99; 12 lines agree.

### UniToChest chest CT (623 patients; distributed as slices) (zenodo_unitochest)

Called 'unitochest'; counts subjects 623, size_gb 84.07; 8 lines agree.

### VSDFullBody: post-mortem whole-body CT, forensic institutes Bern and Zurich (zenodo_vsd_fullbody)

Called 'vsdfullbody'; counts subjects 100, size_gb 116.3; 4 lines agree.

## Settled figures

Each number verdict's figures with their status, and the other texts that give one of them.

### Row 0: number of C-ArmLSpine cases scored in the five-fold lateral whole-frame evaluation (98.2%)

confirmed-contradiction; 148 (open, side a); 141 (open, side b); 617 (open, side b); anchors cv, armlspine, fold, lateral, frame, cases; read from [or-readiness-ledger](../or-readiness-ledger/) and [counting-from-the-sacrum](../counting-from-the-sacrum/).

### Row 10: sacrum recall on real DeepFluoro frames, detector trained on renders of DeepFluoro's own CTs

confirmed-contradiction; 96% (open, side a); 98% (open, side a); 90% (open, side b); 97% (open, side b); anchors deepfluoro, finds, cts, trained, detector, sacrum, renders, frames; read from [aidas-seed-grant-proposal](../aidas-seed-grant-proposal/) and [counting-levels-under-fluoroscopy](../counting-levels-under-fluoroscopy/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| open | 96 | [retrospective-fluoroscopy-protocol](../retrospective-fluoroscopy-protocol/) | 189 | Synthetic fluoroscopy from CT does not close this gap: on 366 real C-arm frames of six cadaveric pelves with matching CT and exact pose (the DeepFluoro dataset), a physics renderer explains 80.9% of a |

### Row 12: share of a real DeepFluoro frame's variance explained by the physics renderer alone

updated-later; 80.9% (current, side a); 86% (superseded, side b); 80 (superseded, side b); anchors explains, variance, calibrated, renderer, physics, deepfluoro, frame; read from [aidas-seed-grant-proposal](../aidas-seed-grant-proposal/) and [counting-levels-under-fluoroscopy](../counting-levels-under-fluoroscopy/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| agrees | 80.9 | [retrospective-fluoroscopy-protocol](../retrospective-fluoroscopy-protocol/) | 189 | Synthetic fluoroscopy from CT does not close this gap: on 366 real C-arm frames of six cadaveric pelves with matching CT and exact pose (the DeepFluoro dataset), a physics renderer explains 80.9% of a |

### Row 20: Mendeley spondylolisthesis lateral lumbar image count

confirmed-contradiction; 714 (open, side a); 716 (open, side b); anchors mendeley, buu, lateral, lumbar; read from [fluoroscopy-data-atlas](../fluoroscopy-data-atlas/) and [spine-x-ray-data-handoff-bddbdd](../spine-x-ray-data-handoff-bddbdd/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| open | 716 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 227 | Tier 2, real radiographs with native labels, for the film domain and for the resolution ablation: NHANES II (364 annotated films locally, 544 at NLM, lateral only, 0.174 mm/px, 12-bit; 17,075 unlabell |
| open | 714 | [imaging-data-holding-manifest-migration-and-index-fqmtjs](../imaging-data-holding-manifest-migration-and-index-fqmtjs/) | 51 | \| AASCE/BoostNet, Mendeley 5jdfdgp762, IEEE lateral 236, Spinal-AI2024 \| plain film and synthetic \| open mirrors, Mendeley, IEEE DataPort \| tools/thoracic\_xr\_fetch.py and HTTP \| by 16 Sept 2026 \| 60 |
| open | 716 | [vertebra-detector-field-report-1jljc6](../vertebra-detector-field-report-1jljc6/) | 57 | \| Mendeley 716 standing DR \| \| 2666 \| \| lateral \| \| unknown \| \| Roboflow export; carries no level names, so none were invented. \| |
| open | 716 | [vertebra-detector-field-report-1jljc6](../vertebra-detector-field-report-1jljc6/) | 117 | \| Mendeley 716 standing DR, lumbar \| |
| open | 714 | [docs/research/datasets-inventory.md](../../docs/research/datasets-inventory.md) | 129 | \| Mendeley 5jdfdgp762 spondylolisthesis films \| 714 films with spondylolisthesis landmarks \| landmarks \| EXCLUDED \| about 500 are BUU people redistributed, so it adds no new person; the Mendeley page |
| open | 714 | [docs/research/xr-annotation-format.md](../../docs/research/xr-annotation-format.md) | 15 | \| Spondylolisthesis landmarks (Mendeley 5jdfdgp762, 508 of them BUU's) \| yes, 714 films \| four corners per body, L3 to S1, as Keypoint R-CNN JSON \| |
| open | 716 | [data/sources/mendeley_5jdfdgp762.json](../../data/sources/mendeley_5jdfdgp762.json) | 2 | about 500 are BUU people redistributed, so it adds no new person; the Mendeley page as summarised in search (the sweep of 2026-10-21) says 698 (one reading) or 716 (another) sagittal lumbar films, 508 |

### Row 23: BUU-LSPINE patient count

cannot-tell; 3600 (open, side a); 3600 (open, side b); 1200 (open, side b); anchors lspine, buu, patients; read from [spine-x-ray-data-handoff-bddbdd](../spine-x-ray-data-handoff-bddbdd/) and [state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay](../state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| open | 3,600 | [any-view-spine-plan](../any-view-spine-plan/) | 54 | You have more real pairs than the report assumed. BUU-LSPINE is held: 3,600 people with an AP and a lateral lumbar film each, with end-plate lines. That is on the scale of LatXGen's 2,611 training pai |
| open | 3,600 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 171 | The L1-L5 real-film crops include 3,600 per level from BUU-LSPINE, whose levels are counting-inferred. The corpus decode (D) behind the recall column: 3,294 panels run, 2,528 with a box, 766 with none |
| open | 3,600 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 205 | s and no C1 or T1; and BUU-LSPINE ( mdpi.com ), 3,600 patients whose levels are counting-derived edge lines, with LSTV codes 20/21 in the full set (15 lumbarization, 129 sacralization by the paper's T |
| open | 3,600 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 227 | Tier 2, real radiographs with native labels, for the film domain and for the resolution ablation: NHANES II (364 annotated films locally, 544 at NLM, lateral only, 0.174 mm/px, 12-bit; 17,075 unlabell |
| open | 3,600 | [imaging-data-holding-manifest-migration-and-index-fqmtjs](../imaging-data-holding-manifest-migration-and-index-fqmtjs/) | 48 | \| BUU-LSPINE \| plain film, AP and lateral \| Burapha University, EULA \| web download \| 9 Sept 2026 \| 3,600 patients, 7,200 films, plus the 2000 and 400 sets \| endplate lines L1 to S1 \| |
| open | 3,600 | [research-directions-from-the-data-holding-kcyckb](../research-directions-from-the-data-holding-kcyckb/) | 57 | \| BUU-LSPINE \| 3,600 cases; 7,200 films \| 144 by the flag table; 9 of 15 L6 reads are children \| levels counting-inferred by row order \| EULA, never redistribute; 3,603 laterals sit in v8 and v9 and t |
| open | 3,600 | [research-directions-from-the-data-holding-kcyckb](../research-directions-from-the-data-holding-kcyckb/) | 199 | \| BUU-LSPINE AP films \| 3,600 \| in no bank; no written criterion \| a bank or a one-sentence written exclusion \| |
| open | 3,600 | [docs/research/data-manifest/README.md](../../docs/research/data-manifest/README.md) | 24 | BoostNet copy is the same films). Lumbar: BUU-LSPINE 3,600 AP and 3,603 lateral films with |
| open | 3,600 | [docs/research/data-manifest/README.md](../../docs/research/data-manifest/README.md) | 37 | - Real AP and lateral pairs: BUU-LSPINE's 3,600 people, lumbar; none above the lumbar spine. |
| open | 3,600 | [docs/research/datasets-inventory.md](../../docs/research/datasets-inventory.md) | 104 | \| BUU-LSPINE \| 3,603 lateral and 3,600 AP lumbar radiographs of 3,600 people with end-plate lines, plus the 2000 relabel and a 400 sample \| lumbar \| HAVE \| laterals used; the AP films and the 2000 rel |
| open | 3600 | [docs/research/datasets-reproduce.md](../../docs/research/datasets-reproduce.md) | 572 | - `buu_lspine_3600`: BUU-LSPINE (3600), the full release (Klinwichit et al., Appl Sci 2023;13:8646); kind upstream_release, family D; route `manual`, mode manual; status on_disk. |
| open | 3600 | [docs/research/datasets-reproduce.md](../../docs/research/datasets-reproduce.md) | 585 | - licence: EULA as BUU-LSPINE (3600); not redistributable; access: request_form |
| open | 3600 | [docs/research/datasets-reproduce.md](../../docs/research/datasets-reproduce.md) | 592 | - licence: as BUU-LSPINE (3600); access: open sample under the EULA |
| open | 3600 | [docs/research/datasets-reproduce.md](../../docs/research/datasets-reproduce.md) | 606 | - licence: as BUU-LSPINE (3600); access: request_form |
| open | 3600 | [docs/research/datasets-reproduce.md](../../docs/research/datasets-reproduce.md) | 1590 | - `buu_lspine_3600`: Fill the Google Form at https://services.informatics.buu.ac.th/spine/ and accept the EULA Download BUU-LSPINE(3600) and unpack to raw/buu_full/BUU-LSPINEv1/ |
| open | 3,600 | [docs/research/xr-annotation-format.md](../../docs/research/xr-annotation-format.md) | 14 | \| BUU-LSPINE \| yes, 3,600 AP and lateral pairs (licence unread) \| the upper and lower edge lines of each lumbar body, as CSV points (each line's two ends are two corners), with the LSTV call per patie |
| open | 3,600 | [docs/research/xr-annotation-format.md](../../docs/research/xr-annotation-format.md) | 125 | - BUU Spine Dataset project page (services.informatics.buu.ac.th/spine/): upper and lower edge lines of each lumbar body as CSV points; the Applied Sciences paper of July 2023: 3,600 patients with ver |
| open | 3,600 | [docs/research/xr-from-3d/README.md](../../docs/research/xr-from-3d/README.md) | 80 | - The test set is real pairs of one person and one visit: VinDr-SpineXR's studies that hold both views (held; how many is for J's census to count), BUU-LSPINE's AP and lateral of 3,600 patients (held: |
| open | 3,600 | [docs/research/xray-dataset-requests.md](../../docs/research/xray-dataset-requests.md) | 632 | ## 17. BUU-LSPINE, the full release of 3,600 patients (EULA form) |

### Row 24: BUU-LSPINE sacralization (four-lumbar) cases

confirmed-contradiction; 129 (open, side a); 130 (open, side b); anchors buu, lumbar, cases; read from [fluoroscopy-data-atlas](../fluoroscopy-data-atlas/) and [spine-program-decisions-qqhkqz](../spine-program-decisions-qqhkqz/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| open | 130 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 183 | What removes it: raw VerSe plus fhofmann plus the CTSP1K 18 L6 and 33 Castellvi cases rendered at up to 12 poses each gives about 150 distinct L6 sources within a week of conversion; real positives th |
| open | 129 | [naming-vertebrae-without-an-anchor-3dfzmh](../naming-vertebrae-without-an-anchor-3dfzmh/) | 239 | For real radiographs, BUU-LSPINE ships its authors' own per-study reading of four-lumbar (129) or six-lumbar (15) anatomy, four corner keypoints per body, S1 end-plate corners on laterals, and a pixel |
| open | 129 | [naming-vertebrae-without-an-anchor-3dfzmh](../naming-vertebrae-without-an-anchor-3dfzmh/) | 348 | Figure 6 - geometric detectors, measured. Left: AUC for six-lumbar (n=15) and four-lumbar (n=129) against ordinary, lateral and AP. Right: the Wigh index of the lowest body on 3,456 ordinary lateral f |
| open | 129 | [naming-vertebrae-without-an-anchor-3dfzmh](../naming-vertebrae-without-an-anchor-3dfzmh/) | 440 | \| D1 \| \| BUU keypoints enforce a rigid five-lumbar schema \| \| confirmed (structure) \| \| all 3,600 films carry L1a-L5b + S1a; the anomaly is a per-patient class on the S1a row (129 L4, 15 L6), not a re |
| open | 129 | [naming-vertebrae-without-an-anchor-3dfzmh](../naming-vertebrae-without-an-anchor-3dfzmh/) | 476 | \| BUU schema correction \| \| the "S1a" line promoted to an L6 box on six-lumbar studies (annotators counted down, so L1-L5 keep their names); L5 flagged sacralised on four-lumbar; all 144 barred from t |

### Row 26: AASCE/BoostNet labelled film count

same-number-restated; 609 (current, side a); 481 (current, side a); 128 (current, side a); 98 (current, side a); 609 (current, side b); 481 (current, side b); 98 (current, side b); anchors mirror, challenge, films, labelled; read from [fluoroscopy-data-atlas](../fluoroscopy-data-atlas/) and [schwingnet-data-registry](../schwingnet-data-registry/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| agrees | 609 | [docs/research/datasets-inventory.md](../../docs/research/datasets-inventory.md) | 103 | \| AASCE / BoostNet whole-spine films \| 609 labelled AP whole-spine films (481 BoostNet training + 128 BoostNet test) and 98 challenge-test films whose landmarks the release never published; both copie |
| agrees | 128 | [docs/research/datasets-inventory.md](../../docs/research/datasets-inventory.md) | 103 | ipped by an unsorted-landmark artefact) and the 128 test films never did; a request-form source; the Kaggle scoliosis YOLOv5 set (kaggle_scoliosis_yolov5) may be a relabel of these films: its hashes a |
| agrees | 609 | [docs/research/datasets-inventory.md](../../docs/research/datasets-inventory.md) | 202 | \| AASCE / BoostNet whole-spine films \| `[the lab volume's data root]/thoracic_xr/mirror_zlinzju_ke30_u7_AASCE2019; the 579 at [the lab volume's data root]/aasce2019_boostnet/raw/aasce` \| labelled film |
| agrees | 609 | [docs/research/datasets-reproduce.md](../../docs/research/datasets-reproduce.md) | 551 | - Registry: link https://aasce19.github.io/; grid path `[the lab volume's data root]/thoracic_xr/mirror_zlinzju_ke30_u7_AASCE2019; the 579 at [the lab volume's data root]/aasce2019_boostnet/raw/aasce` |
| agrees | 609 | [docs/research/datasets-reproduce.md](../../docs/research/datasets-reproduce.md) | 557 | - checks: `md5: path ${DEST}/mirror_zlinzju_ke30_u7_AASCE2019/repo.zip, expect fe9430ab5c064c0d102d44810900e612`; `bytes: path ${DEST}/mirror_zlinzju_ke30_u7_AASCE2019/repo.zip, expect 354809072`; `co |
| agrees | 609 | [data/sources/aasce.json](../../data/sources/aasce.json) | 1 | 609 labelled AP whole-spine films (481 BoostNet training + 128 BoostNet test) and 98 challenge-test films whose landmarks the release never published; both copies are on Ceph: the GitHub mirror holds |

### Row 31: NHANES annotated zip size

confirmed-contradiction; 1.2 (open, side a); 1017496285 (open, side b); anchors zip, gb; read from [spine-x-ray-data-handoff-bddbdd](../spine-x-ray-data-handoff-bddbdd/) and [fluoroscopy-data-atlas](../fluoroscopy-data-atlas/).

### Row 38: FluoroCap panel images on disk

updated-later; 11349 (superseded, side a); 19581 (current, side b); 19048 (current, side b); anchors fluorocap, disk, panel, images; read from [fluorocap-corpus-audit-9hjzzs](../fluorocap-corpus-audit-9hjzzs/) and [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/).

### Row 41: FluoroCap Instagram harvest

updated-later; 600 (superseded, side a); 520 (superseded, side a); 1243 (superseded, side a); 1633 (current, side b); 720 (current, side b); anchors instagram, posts, running, images; read from [fluorocap-overnight-report-xnhgdo](../fluorocap-overnight-report-xnhgdo/) and [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/).

### Row 42: FluoroCap video-frame panels

updated-later; 479 (superseded, side a); 2535 (current, side b); anchors video, frames; read from [fluorocap-corpus-audit-9hjzzs](../fluorocap-corpus-audit-9hjzzs/) and [overnight-the-honest-99-kantj8](../overnight-the-honest-99-kantj8/).

### Row 43: VerSeFusion cases carrying an L6 or T13

cannot-tell; 55 (open, side a); 56 (open, side b); 50 (open, side b); anchors versefusion, t13, l6, cases; read from [fluorocap-corpus-audit-9hjzzs](../fluorocap-corpus-audit-9hjzzs/) and [fluorocap-overnight-report-xnhgdo](../fluorocap-overnight-report-xnhgdo/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| open | 56 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 69 | \| L6 \| \| 0 panels labelled; 0 real-film crops \| \| 802 crops from at most 90 distinct cases (56 VerSe + 34 CTSP); 13 in val \| \| CTSP1K 18; VerSe20 85 scans (local VerSeFusion: 54 centroid files ~ 50 sc |
| open | 50 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 183 | The render side has 802 L6 crops from at most 90 distinct cases and 44 T13 crops, giving 46.4% on L6 (40.1% called L5) and 10.2% on T13 (59.2% called T12); the memory that 12x duplication did not move |

### Row 49: CTSpinoPelvic1K cases with a rib on a lumbar vertebra

cannot-tell; 13 (open, side a); 16 (open, side b); anchors rib, lumbar, cases; read from [spinal-border-variants-fye5ef](../spinal-border-variants-fye5ef/) and [overnight-the-honest-99-kantj8](../overnight-the-honest-99-kantj8/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| open | 16 | [fluorocap-overnight-report-xnhgdo](../fluorocap-overnight-report-xnhgdo/) | 131 | 08:14 v2, held out (376 renders scored, 2,281 renders of training cases skipped): normal spines T12 90.8, L4 84.3, L5 82.5, sacrum 100.0. Six-lumbar spines: T12 58.1, L4 47.2, L5 38.9, L6 63.0% single |
| open | 16 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 75 | \| Transitional captions \| \| fluoroscopy arm 22 unique figures (11 flagged animal, plus a cat and a Beagle unflagged; at most 7 possibly human, none hand-read); pathology arm 20 (9 flagged, plus a calf |
| open | 13 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 195 | 8. Field of view and anchors. Boxes were found on 17.3% of known panels; 766 of 3,294 decoded panels have none; "no anchor" is in the top failure groups; the Castellvi and rib cues are out of the fiel |
| open | 16 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 211 | 1 and are invisible on limited fields ( pmc.ncbi.nlm.nih.gov ); in-house, rib length does not separate the 16 lumbar ribs (median 45 mm) from the 98 stump 12th ribs (38 mm), and a 648-subject CT cohor |
| open | 16 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 241 | \| T13, hypoplastic or aplastic 12th rib, lumbar rib, cervical rib \| \| VerSe 6 T13, 90 stump ribs, 18 cervical ribs; CTSP1K 16 lumbar ribs, 98 stump ribs; rib labels 60/61 \| \| Tier 0 thoracolumbar fram |
| open | 13 | [research-directions-from-the-data-holding-kcyckb](../research-directions-from-the-data-holding-kcyckb/) | 187 | \| VerSe and VerSeFusion \| 374 scans of 355 subjects \| expert masks C1 to L6, T13; the Loeffler table by two neuroradiologists \| L6 85 scans, T13 6, sacralised 13, Castellvi II 27, lumbar rib 12 \| `has |
| open | 13 | [state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay](../state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay/) | 96 | \| CTSpinoPelvic1K \| 802; 789 \| 25 \| 13 \| 0 (no rib cage in the colonography field) \| readers: L6 16 to 18, four lumbar 9, Castellvi-graded 33 against 71 to 142 expected \| |
| open | 13 | [docs/research/ct-priors-for-2d-detection.md](../../docs/research/ct-priors-for-2d-detection.md) | 41 | What: fit, from the segmented CTs, the ordered chain of vertebrae with the distributions of each level's height and of the gap to its neighbour, as ratios that a projection preserves to first order, p |

### Row 51: CTSpinoPelvic1K cases with misnumbered ribs before and after correction

updated-later; 16 (open, side a); 24 (open, side b); 16 (open, side b); anchors misnumbered, cases; read from [spinal-border-variants-fye5ef](../spinal-border-variants-fye5ef/) and [rib-anchor-audit-t7wr2h](../rib-anchor-audit-t7wr2h/).

### Row 52: T12 versus L1 vertebrae used for the AUC 0.990 shape test

cannot-tell; 1485 (open, side a); 1486 (open, side b); 798 (open, side b); anchors auc, t12, l1, vertebrae, shape; read from [counting-against-two-anchors-qkktgu](../counting-against-two-anchors-qkktgu/) and [research-directions-from-the-data-holding-kcyckb](../research-directions-from-the-data-holding-kcyckb/).

### Row 55: transitional patients available across all sources

cannot-tell; 194 (open, side a); 190 (open, side a); 202 (open, side a); 306 (open, side a); 376 (open, side b); anchors transitional, patients, sources; read from [state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay](../state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay/) and [vertebral-levels-without-ct-a4rydj](../vertebral-levels-without-ct-a4rydj/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| open | 376 | [naming-vertebrae-without-ct-hjy4vc](../naming-vertebrae-without-ct-hjy4vc/) | 244 | A cross-validation over all 376 transitional patients is running: |
| open | 376 | [naming-vertebrae-without-ct-hjy4vc](../naming-vertebrae-without-ct-hjy4vc/) | 362 | Cross-validation over all 376 transitional patients - the only route to a real transitional number |

### Row 104: number of C-ArmLSpine cases in the five-fold cross-validation behind the 98.2% exact-level figure

confirmed-contradiction; 148 (open, side a); 141 (open, side b); 617 (open, side b); anchors cv, armlspine, fold, lateral, exact, cases; read from [or-readiness-ledger](../or-readiness-ledger/) and [counting-from-the-sacrum](../counting-from-the-sacrum/).

### Row 107: zero-shot AP exact-level accuracy on C-ArmLSpine

updated-later; 37.88% (superseded, side a); 43.7% (current, side b); anchors shot, ap, zero; read from [counting-from-the-sacrum](../counting-from-the-sacrum/) and [any-view-spine-plan](../any-view-spine-plan/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| agrees | 43.7 | [research-directions-from-the-data-holding-kcyckb](../research-directions-from-the-data-holding-kcyckb/) | 101 | 2. The 3-D discrimination at the thoracolumbar junction is coronal. Transverse-process span carries three of the top five standardised weights (minus 1.851 on the 2026-10-08 rerun). On a lateral the p |
| agrees | 43.7 | [docs/research/benchmarks-to-beat.md](../../docs/research/benchmarks-to-beat.md) | 179 | \| The reported stack, context only (spine-program 01_carm_level_detection, 01/STATUS.md; docs/research/demo-plan.md) \| one real frame, no CT \| C-ArmLSpine, held out, zero-shot \| lateral naming 595/617 |
| agrees | 43.7 | [docs/research/ct-priors-for-2d-detection.md](../../docs/research/ct-priors-for-2d-detection.md) | 11 | - AP naming collapses: 43.7 % zero-shot, a one-level cranial shift (A2.2, A2.8). That is the largest error in the record, and it is a counting error, not an appearance error. |
| agrees | 43.7 | [docs/research/demo-plan.md](../../docs/research/demo-plan.md) | 24 | - naming, AP, zero-shot: 276 / 631 = 43.7 % (a one-level cranial shift; A2.2, A2.8); |
| agrees | 43.7 | [docs/research/flepp-and-killeen-critique.md](../../docs/research/flepp-and-killeen-critique.md) | 172 | \| Any angle is not shown \| AP naming zero-shot is 276/631 = 43.7 %, a one-level cranial shift, against 96.4 % lateral. tools/evaluate.py has no per-view stratum yet (Measured by the reported SchwingNe |
| agrees | 43.7 | [docs/research/state-of-knowledge.md](../../docs/research/state-of-knowledge.md) | 18 | \| 2 \| AP naming, zero-shot: 276/631 = 43.7 %, a one-level cranial shift \| Measured (reported stack) \| demo-plan.md section 0 item 3; ct-priors-for-2d-detection.md 1 \| |

### Row 123: best published registration-free vertebra naming accuracy

confirmed-contradiction; 73.3% (open, side a); 88.3% (open, side b); anchors best, registration, naming, free, published; read from [counting-from-the-sacrum](../counting-from-the-sacrum/) and [naming-vertebrae-without-ct-hjy4vc](../naming-vertebrae-without-ct-hjy4vc/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| open | 88.3 | [vertebral-levels-without-ct-a4rydj](../vertebral-levels-without-ct-a4rydj/) | 175 | \| 88.3% - cadaveric long films \| \| the one registration-free, radiograph-only, per-vertebra naming accuracy in the literature \| \| yes \| |

### Row 126: number of Pittsburgh videofluoroscopic swallow clips

same-number-restated; 1518 (current, side a); 2021 (current, side a); 1488 (current, side a); 2024 (current, side a); 1500 (current, side b); anchors fps, swallow, volunteers, clips, patients, lateral; read from [fluoroscopy-data-atlas](../fluoroscopy-data-atlas/) and [schwingnet-data-registry](../schwingnet-data-registry/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| agrees | 2021 | [docs/research/benchmarks-to-beat.md](../../docs/research/benchmarks-to-beat.md) | 174 | \| Zhang, Mao, Coyle and Sejdic 2021, Med Image Anal 74:102218 \| one real frame of a swallow videofluoroscopy, the patient seated lateral, no CT; a two-stage network that finds the region and then fixe |
| agrees | 1,500 | [docs/research/datasets-inventory.md](../../docs/research/datasets-inventory.md) | 80 | \| Pittsburgh videofluoroscopic swallow corpus (Sejdic, Coyle) \| about 1,500 lateral swallow clips at 30 fps captured by video card, 265 patients and 70 volunteers on two machines \| thin: named corner |
| agrees | 1,500 | [data/sources/pittsburgh_swallow.json](../../data/sources/pittsburgh_swallow.json) | 1 | about 1,500 lateral swallow clips at 30 fps captured by video card, 265 patients and 70 volunteers on two machines |

### Row 129: number of COBRA2026 cases/exports

cannot-tell; 150 (open, side a); 145 (open, side b); anchors exports, elekta, cases; read from [fluoroscopy-data-atlas](../fluoroscopy-data-atlas/) and [or-readiness-ledger](../or-readiness-ledger/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| open | 145 | [handoff-schwingnet-ctspinopelvic1k-and-the-imaging-programme-rbcdmf](../handoff-schwingnet-ctspinopelvic1k-and-the-imaging-programme-rbcdmf/) | 43 | **Real C-arm data is barely used.** Of COBRA2026's 692 fetched cases only 145 Elekta cases are in any frame bank and 0 of 225 Varian; 2,293 DeepFluoro vendor frames, the second C-ArmLSpine sweep, the |
| open | 145 | [research-directions-from-the-data-holding-kcyckb](../research-directions-from-the-data-holding-kcyckb/) | 55 | \| COBRA2026 (Elekta XVI, Varian) \| 692 public cases; 3,480 Elekta frames from 145 cases; 225 Varian cases never exported \| planning-CT screen 91 calls (L6 38, T13 45, four lumbar 8); 57 supported by t |
| open | 145 | [docs/research/datasets-inventory.md](../../docs/research/datasets-inventory.md) | 92 | \| COBRA2026 Elekta \| kV projections around supine pelvic radiotherapy patients, 504 x 504 at 0.8 mm, 120 kVp, with the planning CT deformably registered \| whatever is segmented on the CT: the sacrum t |
| open | 145 | [docs/research/datasets-inventory.md](../../docs/research/datasets-inventory.md) | 197 | \| COBRA2026 Elekta \| `[the lab volume's data root]/cobra2026` \| cases 467, in bank 145 \| |
| open | 145 | [docs/research/retraining-plan.md](../../docs/research/retraining-plan.md) | 33 | Today 145 Elekta cases are in a frame bank and the sacrum detector trains on 118 of them (110 train, 8 validation), 3,094 frames with DeepFluoro (DATASET_USAGE.md 36-42). |

### Row 132: number of FluoroCap panel images

updated-later; 29500 (current, side a); 19581 (superseded, side b); 18119 (superseded, side b); anchors panels, figure, panel, images; read from [schwingnet-data-registry](../schwingnet-data-registry/) and [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| superseded | 18,119 | [fluorocap-overnight-report-xnhgdo](../fluorocap-overnight-report-xnhgdo/) | 164 | 07:25 Two verdicts. The CUT translator finished 30 epochs, but its preview shows what it was trained toward: the panel directories as they are, which include MRI slices, a photographed lightbox and an |
| agrees | 29,500 | [research-directions-from-the-data-holding-kcyckb](../research-directions-from-the-data-holding-kcyckb/) | 208 | \| FluoroCap \| 29,500 panels \| dropped by directive; the 200-panel test set does not exist \| annotate about 200 or write it off \| |
| agrees | 29,500 | [docs/research/datasets-inventory.md](../../docs/research/datasets-inventory.md) | 48 | \| FluoroCap literature panels \| 29,500 figure panels harvested from the literature; 72.8 percent are reproductions with no pixel residual \| pseudo, no patient key \| HAVE \| out of training by directive |
| agrees | 29,500 | [data/sources/fluorocap.json](../../data/sources/fluorocap.json) | 1 | 29,500 figure panels harvested from the literature; 72.8 percent are reproductions with no pixel residual |

### Row 133: FluoroCap panel images on disk

updated-later; 11349 (superseded, side a); 19048 (current, side b); anchors disk, panel, images; read from [fluorocap-corpus-audit-9hjzzs](../fluorocap-corpus-audit-9hjzzs/) and [fluorocap-overnight-report-xnhgdo](../fluorocap-overnight-report-xnhgdo/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| agrees | 19,048 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 35 | \| Panel images on disk \| \| 19,581 (18,119 figure panels, 1,096 video, 366 video-medium) \| \| find on ~/FluoroCap; morning report's 19,048 superseded \| |

### Row 136: number of FluoroCap manifest rows

updated-later; 21603 (current, side a); 17486 (superseded, side b); anchors manifest, rows; read from [fluoroscopy-data-atlas](../fluoroscopy-data-atlas/) and [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/).

### Row 138: number of FluoroCap figure panels

updated-later; 17755 (superseded, side a); 18119 (current, side b); anchors panels, figure; read from [fluorocap-overnight-report-xnhgdo](../fluorocap-overnight-report-xnhgdo/) and [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/).

### Row 139: number of FluoroCap video panels

updated-later; 927 (superseded, side a); 1096 (current, side b); anchors medium, panels, video; read from [fluorocap-overnight-report-xnhgdo](../fluorocap-overnight-report-xnhgdo/) and [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/).

### Row 141: Instagram harvest size

updated-later; 1633 (current, side a); 720 (current, side a); 600 (superseded, side b); 520 (superseded, side b); 1243 (superseded, side b); anchors instagram, posts, running, images; read from [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) and [fluorocap-overnight-report-xnhgdo](../fluorocap-overnight-report-xnhgdo/).

### Row 142: number of FluoroCap panels decoded

updated-later; 3294 (superseded, side a); 20700 (current, side b); anchors decoded, panels; read from [fluorocap-corpus-audit-9hjzzs](../fluorocap-corpus-audit-9hjzzs/) and [overnight-the-honest-99-kantj8](../overnight-the-honest-99-kantj8/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| superseded | 3,294 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 171 | The L1-L5 real-film crops include 3,600 per level from BUU-LSPINE, whose levels are counting-inferred. The corpus decode (D) behind the recall column: 3,294 panels run, 2,528 with a box, 766 with none |
| superseded | 3,294 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 195 | 8. Field of view and anchors. Boxes were found on 17.3% of known panels; 766 of 3,294 decoded panels have none; "no anchor" is in the top failure groups; the Castellvi and rib cues are out of the fiel |

### Row 157: median FluoroCap panel short side

updated-later; 231 (superseded, side a); 320 (current, side b); anchors median, short, panel, side; read from [fluorocap-corpus-audit-9hjzzs](../fluorocap-corpus-audit-9hjzzs/) and [fluorocap-overnight-report-xnhgdo](../fluorocap-overnight-report-xnhgdo/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| agrees | 320 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 37 | \| Figure-panel short side \| \| p5/25/50/75/95 = 133/212/320/494/1,043 px; 28.8% < 224; 23.5% >= 512; 5.2% >= 1,024 \| \| panels.jsonl nested w/h, 18,068 panels (51 files on disk have no entry) \| |
| agrees | 320 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 39 | \| Video-panel short side \| \| 180/320/435/640/720 px; 16.2% < 224; none >= 768 (720p source) \| \| PIL header read of 1,095 files; jsonl carries no w/h \| |
| agrees | 320 | [fluorocap-reality-check-czudvb](../fluorocap-reality-check-czudvb/) | 199 | 9. Pixels per vertebra. The median panel has a 320-px short side and a 55-px lumbar vertebra, about 0.55 mm/px: end-plate ~85 px, disc ~19 px, pedicle 13-22 px, a 2-3 mm facet joint 4-5 px; at the p10 |

### Row 171: number of T12 and L1 vertebrae in the T12-versus-L1 shape analysis

cannot-tell; 1485 (open, side a); 1486 (open, side b); 798 (open, side b); anchors auc, t12, l1, vertebrae; read from [counting-against-two-anchors-qkktgu](../counting-against-two-anchors-qkktgu/) and [research-directions-from-the-data-holding-kcyckb](../research-directions-from-the-data-holding-kcyckb/).

### Row 182: accuracy cost of training on pseudo-labels

confirmed-contradiction; 19 (open, side a); 20 (open, side b); anchors anomalous, pseudo, accuracy, points; read from [fluoroscopy-data-atlas](../fluoroscopy-data-atlas/) and [schwingnet-data-registry](../schwingnet-data-registry/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| open | 20 | [naming-vertebrae-without-an-anchor-3dfzmh](../naming-vertebrae-without-an-anchor-3dfzmh/) | 499 | Its number: on 4,026 label-defined State-C windows of real film from all 144 anomalous studies, exact naming is 81.3% [80.0, 82.4] (cross-entropy) and 81.4% (CORN), against 97.3% / 97.4% on ordinary s |
| open | 20 | [docs/research/datasets-inventory.md](../../docs/research/datasets-inventory.md) | 108 | \| NHANES II unannotated films \| 16,531 digitised films without landmarks \| none; pseudo-labels cut anomalous accuracy 20 points \| HAVE \| unused by a written criterion; the VertXNet Zenodo record adds |

### Row 206: sweep chain survival with the detector's own boxes

cannot-tell; 20% (open, side a); 100% (open, side a); 40% (open, side b); anchors survives, detector, instead, boxes, films, chain, sweep; read from [vertebral-levels-without-ct-a4rydj](../vertebral-levels-without-ct-a4rydj/) and [naming-vertebrae-without-ct-hjy4vc](../naming-vertebrae-without-ct-hjy4vc/).

### Row 226: number of coordbench task pairs

updated-later; 42 (superseded, side a); 50 (current, side b); 20 (current, side b); anchors coop, sdlc, coordbench, pre, arms, pairs, registered; read from [symphony-handoff](https://github.com/OpenSpineConsortium/symphony-template/tree/main/artifacts/symphony-handoff/) and [symphony-in-brief-9cdciz](https://github.com/OpenSpineConsortium/symphony-template/tree/main/artifacts/symphony-in-brief-9cdciz/).

| Outcome | Gives | Where | Line | Passage |
|---|---|---|---|---|
| agrees | 50 | [docs/research/symphony-in-brief.md](../../docs/research/symphony-in-brief.md) | 126 | coordbench's run is pre-registered ([PLAN.md](https://github.com/OpenSpineConsortium/coordbench/blob/5e4860e4a2157f4ef14397f877fd9c3dccd81a14/bench/cooperbench/PLAN.md)): 50 pairs from 20 tasks, five |
| agrees | 50 | [docs/research/symphony-in-brief.md](../../docs/research/symphony-in-brief.md) | 126 | The primary test is sdlc against coop on CooperBench's own pass verdict, by an exact McNemar test ([89-112](https://github.com/OpenSpineConsortium/coordbench/blob/5e4860e4a2157f4ef14397f877fd9c3dccd81 |
| agrees | 50 | [docs/research/symphony-in-brief.md](../../docs/research/symphony-in-brief.md) | 156 | 1. **The benchmark.** coordbench's pre-registered run: 50 pairs under five arms, sdlc against coop first. The survey that fixed the pairs is done (tag survey-1, [PLAN.md:19-27](https://github.com/Open |

## Settled figures not used

| Row | Quantity | Verdict | Why not |
|---|---|---|---|
| 3 | frames per C-ArmLSpine CBCT sweep (case134) | confirmed-contradiction | its quote from side b carries too few of its anchors |
| 5 | exact-level naming on a whole lateral C-ArmLSpine frame | cannot-tell | its quote from side b carries too few of its anchors |
| 6 | exact-level naming with one vertebra in the lateral C-arm field | updated-later | its quote from side b carries too few of its anchors |
| 17 | number of registry source records in SchwingNet data/sources | updated-later | its quote from side b carries too few of its anchors |
| 30 | NHANES II annotated vertebra instances | confirmed-contradiction | its quote from side b carries too few of its anchors |
| 34 | real-film vertebra corner corpus size | updated-later | its quote from side a carries too few of its anchors |
| 35 | detector training set and planned retraining size | cannot-tell | its quote from side a carries too few of its anchors |
| 47 | CTSpinoPelvic1K cases with a sixth lumbar vertebra | confirmed-contradiction | its quote from side b carries too few of its anchors |
| 53 | CTSpinoPelvic1K mean sacral slope (SS) | updated-later | its two quotes share fewer than two rarer words |
| 56 | distinct L6 training patients | updated-later | its quote from side a carries too few of its anchors |
| 70 | vertebra detector miss rate on real film | confirmed-contradiction | its two quotes share fewer than two rarer words |
| 71 | duplicated vertebrae from the frame-linking rule | updated-later | its two quotes share fewer than two rarer words |
| 82 | home Panasas volume use against the 4,295 GB quota | updated-later | its quote from side a carries too few of its anchors |
| 83 | images or frames needed from the retrospective PACS pull | confirmed-contradiction | its quote from side a carries too few of its anchors |
| 95 | L6 training cases needed before VerSe algorithms found an L6 | cannot-tell | its quote from side a does not give that side's figure |
| 98 | CSXA images on disk | updated-later | its quote from side b carries too few of its anchors |
| 105 | exact-level naming accuracy on C-ArmLSpine lateral frames for the model fine-tuned on the device | cannot-tell | its quote from side a does not give that side's figure |
| 106 | zero-shot lateral exact-level accuracy on C-ArmLSpine (no C-ArmLSpine data in training) | updated-later | its quote from side a does not give that side's figure |
| 116 | vertebra detector miss rate on real films across confidence thresholds | cannot-tell | its quote from side b carries too few of its anchors |
| 122 | Huang 2022 CT-free vertebra labelling accuracy on cadaver long films | same-number-restated | its quote from side b carries too few of its anchors |
| 134 | FluoroCap panel images on disk | updated-later | its quote from side b carries too few of its anchors |
| 137 | number of FluoroCap journal figure panels | updated-later | its quote from side b does not give that side's figure |
| 145 | number of FluoroCap panels carrying an L6 | updated-later | its two quotes share fewer than two rarer words |
| 150 | captioned FluoroCap panels mentioning a transitional term | cannot-tell | its quote from side b carries too few of its anchors |
| 154 | figure mates agreeing on region (decoder) | confirmed-contradiction | its quote from side b carries too few of its anchors |
| 158 | FluoroCap figure-panel short-side percentiles and size shares | updated-later | its two quotes share fewer than two rarer words |
| 159 | share of FluoroCap panels at or above 512 px | updated-later | its quote from side a carries too few of its anchors |
| 219 | region accuracy of the v2 level model at full coverage | cannot-tell | its quote from side a carries too few of its anchors |
| 239 | number of FluoroCap panels carrying L3 | updated-later | its two quotes share fewer than two rarer words |
| 240 | number of FluoroCap panels carrying the sacrum | updated-later | its two quotes share fewer than two rarer words |
