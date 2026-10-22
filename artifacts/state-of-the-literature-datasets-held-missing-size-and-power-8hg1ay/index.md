# State of the literature: datasets held, missing, size and power

Oct 8, 2026 · @greg

The data manifest of 212 sources is being cross-referenced against every prior research report and prior-art document on disk, from the dataset sweeps of 18 to 23 September 2026 to the acquisition census, to say which datasets of the field are held, which are missing and why, and how the holding compares in size and statistical power with the published studies.

## What is held, by task

You hold the large open vertebra-labelled spine CT releases the prior research names, the CT fetched to find transitional spines, 9,108 level-labelled real plain films, and exactly one real intraoperative human set with a volume. Counts are the manifest cards' dated counts; the full tables with every citation are in `HANDOFF/LITERATURE_STATE.md`, section 1.

| Task | Held | n on disk | Labels | Gaps inside what is held |
| --- | --- | --- | --- | --- |
| Vertebra-labelled CT | CTSpine1K, VerSe'19 and '20, TotalSegmentator v2.0.1 and v3.0.0, RibFrac, RSNA 2022 cervical, CTSpinoPelvic1K | 1,005; 374 scans; 1,228 and 1,935; 660; 2,019; 802 | expert vertebra masks; TotalSegmentator release labels; fracture labels; the lab's per-level labels | 10 VerSe'20 series never downloaded; VertebralBodiesCT-Labels masks held only as reads on 70 CTs |
| CT with transitional anatomy | the tier-1 acquisition: 39 IDC collections, FDG-PET-CT-Lesions, AbdomenAtlas 3.0 Mini, AMOS22, NLST pilot, ten late Zenodo sets, plus COBRA2026 planning CTs | about 20,280 CTs on disk of the 21,622 the census lists; about 11,770 people whose lumbosacral junction can be counted | two automatic labellers, a registry of calls; no human read | nobody has read them |
| Plain films with level labels | CSXA, BUU-LSPINE, NHANES II landmarked subset, AASCE, Mendeley 5jdfdgp762 | 9,108 labelled real films in the render banks | per-vertebra or endplate labels from the releases | VinDr-SpineXR has lesion boxes only; the IEEE lateral 236 have none |
| Intraoperative frames with 3-D truth or pose | C-ArmLSpine (the one human intraoperative set), DeepFluoro (cadaver), Geneva hip (phantom), Ljubljana (cadaver), SpineSAC (phantom) | 149 cases, 299 spot frames, 602 sweep projections; 366; 116; 18; raw frames of one phantom | levels from two automatic labellers; poses | one C-arm model carries naming truth; no human-read levels |
| CBCT projections with a planning CT | COBRA2026 | 692 cases, 375,618 projections | planning CT registered, geometry per projection | 145 cases in any frame bank; Varian not exported |
| Synthetic rendering sources | the DRR banks from CTSpinoPelvic1K, VerSe, TotalSegmentator, the physics-styled renders, PolyPose, FluoroGen, Spinal-AI2024 | tens of thousands of renders | inherited from the CT labels | derived, not evidence of the field |
| Spondylolisthesis and pathology films | Mendeley 5jdfdgp762, FluoroCap reproductions | 714; 316 GB of harvested panels | corners; none | FluoroCap dropped from training |

## What is missing and why

What is missing that matters most is labelled real intraoperative frames from living patients: every verified set of that kind the literature names is request-only or unreleased, and no drafted request is recorded as sent. The second gap is seven gated CT collections nobody has signed for, of which Merlin alone is expected to add more transitional people than all of tier 1. The full ranked list of 36 missing sets with the step that would get each is section 2 of the file.

| Missing set | What it would add | Why it is missing | The step |
| --- | --- | --- | --- |
| LevelCheck cohort (178 CTs, 398 radiographs), Vanderbilt (146 patients), Huashan (140), PUMCH (43), SX-Stitch (1,032 frames) and the other real intraoperative sets | labelled real operating-room frames from living patients, the one thing no public release gives | request-only or unreleased | send the drafted requests in docs/data\_requests; none is recorded as sent |
| Merlin | expected 1,260 transitional people at the low prior, more than tier 1's 831 | gated behind a form | sign; the form is named in the acquisition plan section 7 |
| The six other gated CT collections | 1,791 to 3,848 expected transitional people in total with Merlin | gated | forms |
| Spine-Mets-CT-SEG (54), Spinal-Multiple-Myeloma-SEG (67), LumVBCanSeg (185), MedPelvis3D (99) | new vertebra-labelled or lumbar CT people | planned for tier 2, held by the plan's stopping rule 4 | run tier 2 once tier 1's priors are measured |
| LUMOS (280 CTs with radiographs) | paired CT and radiograph | deferred: a zipped-DICOM route is not written | write the route in tools/acquisition\_fetch.py |
| Glocker spine CT (125 patients, 242 scans) | labelled CT | excluded by its no-derivatives licence under rule 3 | none under the rules |
| TCIA CMB-MML and CMB-AML XA frames | open interventional frames with same-patient CT | not fetched; only one patient shows a spine procedure and none carry labels | low value; fetch only for a demonstration |
| NIT Warangal (9 patients) | public level-named centroid files; real frames only as 8-bit copies in overlay images | partially public | fetch the centroid files; ask for the frames |
| The 10 VerSe'20 series, the BoostNet 128 labelled test films, the empty CM Spine Drive download | completing sets already held | never downloaded, never reached the bank, empty download | fetch by name from the VerSe node; rebuild aasce\_drr; retry the Drive file |
| TVGH-SpineXR | lateral films | anonymous access refused | credentialed request |

## Size against the comparable studies

One verdict per task. The ratio is this holding's n over the study's n; every study n is as recorded in the research file it came from, and the 48-row table with each source is section 3 of the file.

| Task | Comparable study | Study n | This holding | Ratio | Verdict |
| --- | --- | --- | --- | --- | --- |
| Radiograph level identification | VertXNet (Chen 2024); Kim 2024; BUU-LSPINE (Klinwichit 2023) | 1,183 images; 150 films; 7,200 films | 9,108 level-bank films | 7.7; 61; 1.3 | Larger. Accuracy cannot be ranked: no published plain-film naming accuracy is metric-comparable, and the whole-film task is saturated (the model and the count-from-sacrum rule both score 99.96 % on 520 films). |
| C-arm naming | VDVM (Zhang 2023); MVMS (Huang 2022) | 31 test images; 100 O-arm films, 13 cadavers | 296 frames, 148 cases | 9.6; 3.0 | Larger test, one device, no readers. The best number, 98.2 % (606 of 617 lateral vertebrae), is on one device with automatic truth. |
| C-arm detection | Spine Vision (Rao 2024) | 578 images, 3 C-arms, test 20 | 778 mobile C-arm frames, 3 C-arms, held-out-device test 56 | 1.35 | Comparable size, lower recall with the device held out: 80.5 % against Rao's in-domain 0.964. |
| Registration | LevelCheck (De Silva 2016) | 398 radiographs, 178 CTs | 296 frames, 148 cases | 0.74 | Smaller. |
| Human readers | Manbachi 2018 | 62 radiographs, 5 surgeons | no reader study | none | Smaller: nothing against five surgeons. |
| 2-D LSTV | Kwak 2025 | 3,116 films, 1,941 LSTV; test 195 | 147 real positives; 128 anomalous test films | 0.08; 0.66 | Smaller, and worse: 49.9 % on anomalous film windows against 89.9 % on ordinary films. 2-D TLTV is zero on both sides. |
| CT labelling with anomalies | VerSe (Sekuboyina 2021); VERIDAH (Möller 2026); TotalSegmentator (Wasserthal 2023) | 355 patients; 1,536 CTs; 1,204 CTs | 802 patients; 129 count-changing transitional persons | 2.3; 0.52; 0.67 | Comparable. 86 of the 110 L6 persons are VerSe's own, so beyond VerSe the holding adds 24. No CT L6 identification rate from the current model is recorded. |
| Prevalence | Paik 2013; Hanhivaara 2020; Doo 2020 | 8,280; 3,855; 1,340 | 1,113 CT spines with both junction flags | 0.13; 0.29; 0.83 | Smaller than the large series and not a prevalence sample: VerSe is enriched by design and CTSpinoPelvic1K is a colonography cohort aged 50 and over. |

Transitional test size against what it buys:

| Quantity | Here | Comparator |
| --- | --- | --- |
| Test persons with no error needed for a Wilson lower bound of 90 % on exact level | 35 (pre-stated target) |  |
| Carriers with no miss needed for 85 % variant sensitivity | 22 (pre-stated target) |  |
| At-risk CT test persons (L6 43, sacralised L5 or four lumbar 5, T13 3) | 51 (bound 93.0 % if all correct) | VERIDAH's CT test anomaly scans, never printed, 54 to 63 inferred; VerSe'20 hidden phase 19 |
| Validation and test transitional persons inside the current encoder's training | 92 of 97 |  |
| Verified real-frame transitional test persons | 0; the 7 COBRA2026 two-labeller at-risk persons are unverified (best-case bound 64.6 %) | Kwak's test: 195 LSTV films |

## Power

Every powered statement so far rests on planning accuracies of 95 to 99 % that no transitional measurement supports. The measured transitional figures put every transitional test at or near zero power: render L6 recall 56.1 to 72.4 %, L6 named 44.9 % with no anchor on anomalous films, 49.9 % on anomalous film windows. The one comparison already decided at its n is held-out-device against same-device detection on one device (28 cases, 8 better and 0 worse). Device-level claims cannot be tested with 4 devices, because the smallest two-sided sign-flip P is 0.125. Paper 1's 90 % target needs 35 error-free at-risk persons and paper 2's primary hypothesis needs 19, while 7 unverified real at-risk persons exist and the 51 CT test persons sit mostly in the encoder's training lineage. The 97.6 % LevelCheck reader figure cannot be exceeded at any reachable n.

| Comparison | n today | Power today | n for 80 % power |
| --- | --- | --- | --- |
| Device-level gain of fitted cards over uncalibrated physics | 4 devices, 24 folds | 0 at alpha 0.05 whatever the effect; fold-level P 0.00023 | at least 6 devices; no calculation on file |
| Held-out-device against same-device detection | 28 cases, 8 to 0 | decided: Holm P 0.0078 | across devices: no calculation |
| Synthetic-to-real ratio | no sweep run | none | no calculation; the inputs are listed in the file |
| Naming on transitional against ordinary spines | 10 L6 render persons, 0 T13 | not computed | 19 per arm at design effect 1, 74 at design effect 4 (3.84 to 4.47 measured) |
| Count against count plus morphology (paper 2) | none scored | runs only with 6 discordant persons | no calculation |
| L6 detection, variant sensitivity lower bound 85 % | 43 CT test persons, 49 of 54 in the training lineage; 3 real | 0.36 to 0.93 at a true 95 to 99 %; never at the measured 72.4 % | 22 to 74 carriers with no miss; 347 at a true 90 % |
| T13 detection, the same target | 3 CT test persons, 0 real | 0, below the 22-carrier floor | about 55 T13 people under the 50/10/40 split |
| Paper 1 exact level, lower bound 90 % | 51 CT at-risk; 7 real unverified; 0 verified | 0.07 to 0.60 at a true 95 to 99 %; 0 at 7 | 53 to 217 |
| LevelCheck H1, at-risk persons, superiority over 82.2 % | 7 real (n\_min 19); 51 CT as a secondary analysis | 0 on real frames; 0.24 to 0.998 on CT at 90 to 99 % | 38 to 162 |
| LevelCheck H2, superiority over 97.6 % | as H1 | 0 below 152 persons at any accuracy | 708 at a true 99 %; never at 98 % |
| LevelCheck H6, ordinary spines, non-inferiority to 92.6 % | at most 51 ordinary real persons, 13 with a reference | 0.07 to 0.60 at 51; 0 at 13 (n\_min 48); about 0 with the frozen detectors | 73 to 210 |
| A 99 % selective-accuracy claim | 2,956 answered held-out renders | not a power calculation | about 298 answered cases; 2,673 for class-conditional 99 % at 27 classes |
| Wrong-level events under the QI protocol | not applicable | powered to estimate, not to detect a change | tens of thousands of cases |

The frozen paper-2 endpoint scores a person wrong for a missed body, an unanchored frame or an abstention, not only for a wrong name. On ordinary development frames that endpoint held on 57.0 %, and the fixed COBRA2026 sacrum detector found the sacrum on 3.4 % of frames. Those detectors were replaced before unblinding, and no file recomputes the power under the replacement.

## The transitional count: expected against called

The expectation uses the acquisition plan's priors: any LSTV 9 % low (Hanhivaara 2020) to 18 % high (Nardo 2012); L6 3.2 % and four lumbar 1.6 % (Sun 2025), the two a mask count can call; T13 0.64 to 2.0 %. These are expected values, not calls.

| Block | CTs on disk; lumbosacral-countable people | Expected L6 | Expected four-lumbar | Expected T13 | Called so far |
| --- | --- | --- | --- | --- | --- |
| CTSpinoPelvic1K | 802; 789 | 25 | 13 | 0 (no rib cage in the colonography field) | readers: L6 16 to 18, four lumbar 9, Castellvi-graded 33 against 71 to 142 expected |
| TotalSegmentator v2 | 1,228; 483 | 16 | 8 | 3 to 9 | registry: L6 22, T13 4 |
| COBRA2026 | 692; 435 | 14 | 7 | not computable | one-labeller screen L6 38, T13 45, not trusted; the registry keeps 3 |
| 18 screened acquisition collections | 16,898; about 10,060 | 322 | 161 | 38 to 119 | screen flags L6 303, T13 82, review 1,168; two-labeller L6 21 |
| RibFrac | 660; 0 | 0 | 0 | 3 to 9 | T13 4, single labeller |
| Total, excluding VerSe, C-ArmLSpine and phantoms | about 20,280 of the 21,622 census CTs; about 11,770 people | 377 | 188 | 44 to 138 | registry: L6 146, T13 14 |

What the comparison says:

- CTSpinoPelvic1K sits at or a little below the priors where it was read: L6 2.0 % (Wilson 1.3 to 3.3 %) against 3.2 %, four lumbar 1.1 % against 1.6 %. The Castellvi gap is an unread cohort, not a measured shortfall.
- The COBRA2026 one-labeller screen runs far above the prior (8.7 % L6, and 45 T13 calls on abdominopelvic CTs). The same labeller matched reader truth on 10 of 24 L6 and 0 of 52 T13 in CTSpinoPelvic1K, so it is not trusted.
- The acquisition screens match the expected total at face value, which is not evidence. On 70 outside-labelled CTs the screen found 12 to 17 of 28 L6; a screen with that sensitivity that still flags about as many as expected is carrying false positives.
- T13 is the scarce class everywhere: 44 to 138 expected in the whole holding against about 55 needed, and the low end falls short before any call fails verification.
- L6 is not short in number; verification is. 377 L6 people are expected against the 85 L6 scans in VerSe'20, where 28 in training sufficed to make L6 learnable. No acquired CT has a radiologist read.
- Two acquisition expectations already missed: AMOS kept about a third of its predicted people at 3 mm or thinner, and the NLST pilot's 9.3 % T13 rate was five to fifteen times its prior and wrong. AbdomenAtlas matched its prediction.

## What this rests on, and what is not known

The file behind this page is HANDOFF/LITERATURE\_STATE.md in the spinesurg-ct-nnunet repository. It rests on 114 prior research reports, verified sweeps, prior-art notes, dataset reviews, memory notes and PDFs on disk, each listed with the question it answered, its conclusion as recorded, and how it was verified: voted (a research harness put each claim to three adversarial verifiers, with counts of claims extracted, verified, confirmed and refuted), read from the primary source with no vote, or identifiers checked. Section 7 of the file lists 45 unknowns and 31 places where two files disagree. The ones that change a decision:

| Unknown | Why it matters |
| --- | --- |
| The true person-level transitional naming accuracy of any arm on real frames | Every power row needs it as the effect size; every powered statement so far assumes 95 to 99 %. |
| How many of the 57 field-supported COBRA2026 screen calls are transitional | No human read exists; the labeller's precision on CTSpinoPelvic1K is L6 10 of 24 and T13 0 of 52. |
| Whether any drafted request (SX-Stitch, Balgrist, the 14 cine letters) was sent or answered | They are the only drafted routes to labelled real fluoroscopy. |
| Whether C-ArmLSpine's 148 or 149 cases are that many people, whether they were living, and its ethics approval | It is the only intraoperative human data; files record 149 cases, 148 cases and 120 subjects. |
| Whether tier 1 yields its expected 831 to 1,703 transitional people, and the gated collections theirs | The only route past VERIDAH's CT count; AMOS and the NLST pilot already missed their expectations. |
| Person counts across the acquisition collections after deduplication | Near-duplicates are listed, not merged. |
| What Li 2016, Li 2017 and ABLSpineLevelCheck 2024 report | Any of them could hold a C-arm naming result that overturns the naming-novelty claim; IEEE Xplore was blocked. |
| The patient counts behind VDVM, Rao 2024, SX-Stitch, CM Spine and DAX | The C-arm ratios are in images, not people; Rao's 0.964 may be cadaver and phantom only. |
| Which licence reading is right for CTPelvic1K, VerSe, DeepFluoro, Geneva and Ljubljana | It decides the redistribution column of every derived bank. |
| Whether SyntheX's Dataverse deposit is on disk, and whether the CT Colonography localizers survive on HOME | A matched real-and-render set; a free same-patient projection source. |
| No CT L6 identification rate from the current model, and no human reader study | No CT naming number can be set beside VERIDAH's recall; Manbachi's design has no counterpart. |
| The sampling error of the frozen comparators: 97.6 % has no published denominator and Peh 1999's numerator is assumed | The comparator's own interval is unknown. |

Where two files disagree, the page uses the reading named here:

- VerSe scans with L6: 85 scans (Liebl 2021) against 47 cases (Sekuboyina 2021) and 87 read series. No file has counted from the masks.
- CTSpinoPelvic1K L6: 18 by release label, 16 by the readers' own count, 29 persons in the registry. Seven disagreeing records are out of every truth pool until re-read.
- C-ArmLSpine: 149 cases, 148 cases with 296 frames, or 120 distinct subjects.
- Anomalous-film interior accuracy: 66.0 % over 12 films against 49.9 % over 128. The page uses 49.9 %.
- Transitional persons in all sources: 194, about 190, 202 or 306, by date and definition.
- TotalSegmentator size: 1,204; 1,228 in v2; 1,935 or 1,939 in v3.
- BUU-LSPINE: 3,600 patients and 7,200 films, or 3,600 films from 1,200 patients; 7,204 films are on disk.
- VERIDAH's CT test anomaly scans: 25 and 29 written as counts, 54 by the published rates, 63 by the recall percentages. The paper prints rates only.
- CT transitional test persons: 57, or 51 at risk once the sacralised five-lumbar row is left out. The page uses 51.
- COBRA2026's shape: an older entry said 145 patients, four centres and Elekta only; the verified sweep found 867 patients, six centres and two vendors.
