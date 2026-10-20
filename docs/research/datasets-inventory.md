# What SchwingNet can train and test on: the datasets, grouped

Source: the thread "SchwingNet video demo plan", 2026-10-20, from spine-program's 01_carm_level_detection/docs/handoff/DATASET_USAGE.md (sections 2.1 to 2.3), docs/handoff/LEAKAGE.md, and 10_data_platform_grid's DATA_MANIFEST.md (211 sources carded), read that day. Counts are the record's; "not recorded" means the record is silent. Three columns matter for the plan: what it is, whether it carries level truth, and whether you can reach it.

Legend: HAVE = on the grid now; GET = public, not yet fetched or needs a form; GATED = behind a data-use agreement or a login the project does not hold; NONE = does not exist publicly.

## 1. Real intraoperative fluoroscopy (the target domain)

| Source | What it is | Level truth | Reach | Status in the record |
| --- | --- | --- | --- | --- |
| C-ArmLSpine (Surgio-B51) | 149 lumbar cases, 299 spot frames, 149 CBCT, 2 rotational sweeps of 301 frames (case134, case39) | yes, lumbar, from the CBCT; 3 real L6 cases | HAVE, CC BY 4.0 | the test set and the demo; never trained on in the zero-shot arm |
| DeepFluoro (Cios Fusion) | 6 cadavers, 366 H5 frames plus a 2,659-frame vendor deposit, with CTs | pelvis and lower lumbar from the CT | HAVE, CC BY-NC-SA | the sacrum detector; 2,293 vendor frames unused |
| Geneva hip (BV Pulsera) | 116 frames, one phantom | pelvis | HAVE | the unseen-device test |
| Ljubljana 2D-3D-GS (PIXIUM) | 18 frames, one cadaver L1 to L5, with CT and pose | yes, up to 90 level boxes possible | HAVE | parameters read, no truth bank built |
| SpineSAC | 5,490 frames, six C-arms, sawbones | none (masks empty on sawbone CT); no licence stated | HAVE, unusable | 0 frames scored |
| Bournemouth cervical | 252 sequences, 63 people, corner tracks at 15 fps, no pixels in the public file | geometry only | HAVE (.mat); the DICOM cine is one of the 14 requests below | tracker test only |
| Public clips (YouTube, PMC) | 262.8 GB, 18 clips with live fluoroscopy, one CC-licensed | almost never named | HAVE, mostly unlicensed | private tracker evaluation only, never training or a slide |
| SX-Stitch intraoperative C-arm series (Li 2024) | intraoperative series | would have levels | GET: request drafted 2026-09-19, never sent | |
| Balgrist ex-vivo lumbar CT plus C-arm (Jecklin) | cadaver CT plus C-arm | yes, from the CT | GET: request drafted 2026-09-21, never sent | |
| 14 fluoroscopy cine requests of 2026-09-26 (Bournemouth DICOM cine, Maastricht, Bern, Pittsburgh and others) | cine sequences | varies | GET: drafted, none sent | |
| Real cervical or thoracic intraoperative frames with level truth | | | NONE public | the gap; your own captures with a preoperative CT are the way |

## 2. Real projections with a registered CT (the COBRA kind)

| Source | What it is | Level truth | Reach | Status |
| --- | --- | --- | --- | --- |
| COBRA2026 Elekta | 467 public cases, kV projections around a supine pelvic patient, planning CT registered | whatever you segment on the CT: sacrum today, L5 and L6 possible | HAVE all 467; CC BY-NC 4.0 (non-commercial) | 145 cases in a bank, 24 frames each; the rest never exported |
| COBRA2026 Varian | 225 public cases | same | HAVE; geometry solved 2026-09-23 | no bank built, no frame looked at |
| COBRA embargoed | 175 cases | same | GATED until 2032-03-01 | |

## 3. Plain films (2D, lateral or AP radiographs)

| Source | What it is | Level truth | Reach | Status |
| --- | --- | --- | --- | --- |
| CSXA cervical lateral | 4,963 films with corner JSON | cervical, C1 to C7 | HAVE, open | used fully; every person in the v9 base, so not held out until re-keyed |
| BUU-LSPINE lateral | 3,603 films, 3,600 people, end-plate lines | lumbar | HAVE | used; the AP films (3,600) and the 2000 relabel never used, no criterion |
| NHANES II annotated | 543 films, 364 persons, landmarks | lumbar and cervical | HAVE, open | used; counted twice in the old fold banks (a leak the registry ends) |
| NHANES II unannotated | 16,531 films | none; pseudo-labels cut anomalous accuracy 20 points | HAVE | unused by a written criterion |
| VinDr-SpineXR | 10,466 DICOM, 5,000 studies, lesion boxes | no levels | HAVE under a PhysioNet DUA that sits outside IRB determination 2026-269 | dropped; only implant boxes used |
| AASCE / BoostNet | 609 labelled whole-spine films | thoracic, as a test set | HAVE (request-form source) | thoracic test only |
| Mendeley 5jdfdgp762 | 714 films | spondylolisthesis landmarks | HAVE | excluded: about 500 are BUU people redistributed |
| IEEE DataPort lateral 236 | 236 whole-spine laterals | none | HAVE | pseudo-label arm refuted |
| Spinal-AI2024 | 20,000 machine-generated films, 44 synthetic identities | assumed | HAVE | all on train in the G3 split; nothing to hold out |
| TVGH-SpineXR | | | GATED: 403 at a login, access never requested | |
| FluoroCap literature panels | 29,500 figure panels, 72.8 % reproductions, no patient key | pseudo | HAVE | out of training by directive D1; still inside the old fold banks |

## 4. CT collections and their renders (3D truth, synthetic 2D)

| Source | What it is | Level truth | Reach | Status |
| --- | --- | --- | --- | --- |
| CTSpinoPelvic1K | 802 CTs, your own release v11, with vertebra, sacrum and pelvis labels | yes, whole lumbosacral, L6 cases flagged | HAVE, CC BY-NC-SA; TCIA source | the render banks; the synthetic L6 arm (18 spines by 3 seeds) |
| VerSe 19/20 | 374 series, 355 subjects | yes, labelled | HAVE | renders in the v9 base; 10 series never downloaded |
| TotalSegmentator v2 and v3 | 1,228 and 1,935 scans | yes, segmentation | HAVE | renders; v3 is the device corpus (142 whole-spine subjects) |
| RSNA 2022 cervical CT | 2,019 studies, 203 GB | fractures, and the only voxel-anchored C1, C2, C7 source | HAVE the zip; Kaggle rules accepted, never unpacked | a header census refused every study for a junction count; usable for a C2 anchor and cervical renders |
| CTSpine1K, CTPelvic1K, RibFrac | 1,005, 172 and 660 CTs | partial | HAVE | the transitional registry only |
| The anomaly harvest (family B) | 144 CT sources screened for transitional spines: 39 IDC collections (3,499 usable CTs), AbdomenAtlas (7,649), FDG-PET-CT (900), AMOS22 (723), NLST pilot (500) and more | counted by the census pipeline | 56 HAVE, 23 planned, 7 GATED, 58 excluded (licence or no new people) | the rare-class source in 3D |
| FluoroGen synth_rare | 12,929 renders, 1,763 L6 and 86 T13 | exact | HAVE | in no bank, no reason written |

## 5. What this means for the plan

- Real frames with level truth exist only for the lumbar spine (C-ArmLSpine) and the pelvis (DeepFluoro, COBRA). Every cervical and thoracic truth you hold is a film (CSXA, AASCE) or a render (RSNA, VerSe, TotalSegmentator). That is the gap, and no public set fills it; the nine drafted requests (SX-Stitch, Balgrist, the 14 cine requests) are the cheapest next move and none has been sent.
- Rare classes: 3 real L6 persons (all test), 18 L6 CTs in your own release, 1,763 L6 renders, and the harvest's census over thousands of CTs. In 3D you are rich; in real 2D you have three people.
- Two sources are gated for good as the project stands: VinDr (a DUA outside the IRB determination) and the 7 gated harvest collections; TVGH was never asked. LevelCheck is a method (Goswami 2020, 3D-to-2D registration on pig CBCT), not a dataset the record holds; its pig zips sit in the archive, excluded.
- Three licences bind a product: COBRA and DeepFluoro are non-commercial, CTSpinoPelvic1K is non-commercial share-alike. That is a lawyer's question before version 1 depends on them.
