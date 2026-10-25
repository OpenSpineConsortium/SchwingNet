# Workflow brief of 2026-10-25

Source: the project thread "Build workflow state and synthetic XR artifact", 2026-10-25, on the owner's ask of 12:50 UTC for one page with the state of the block workflow, the packaging plan, the dataset selector rerun with unheld sets counted as obtainable, the number, angles and methods of synthetic X-rays projected from masks, the videos in the census, and the AI Scientist loop. The page is the private artifact https://claude.ai/artifact/VAur1wartsVQR6a1rJj4P9. It was built from main 26e7e7b, the project files smoke/design.md and storage/, and symphony-template #471. Confidential with the rest of this repository: it sets out methods, so nothing of it goes to a public place before the provisional is filed.

## 1. What is new here

Only two things on the page are new. The rest is gathered from the notes named in each section.

### The selector rerun

tools/choose_data.py was run in a scratch copy, with every record whose reach is get, gated or embargoed read as held, and excluded or none left out. The settings were unchanged (research-internal, half-width 0.05 at 95 percent, expected accuracy 0.5, so 381 people; 12 device persons to training). 117 records were read and nothing was committed.

| Run | Test persons | Short by | Training sets | Held sets excluded |
| --- | --- | --- | --- | --- |
| Held only (the committed CHOICE.json) | 132 | 249 | 25 | 26 |
| Unheld counted, test groups fluoro | 266 (C-ArmLSpine 132, Vanderbilt THA 134) | 115 | 46 | 65 |
| The same, test groups fluoro and video | 640 | 0 | 46 | 65 |

The third row closes the gap only through Pittsburgh's 323 swallow patients, whose level truth is two landmarks (C2 and C4). The chooser reads that as "read", which is more than it is. Without Pittsburgh the total is 317, so the test is still 64 short. Six video records with level truth give no person count (Bern, Jefferson, Maastricht, Neurosurgical Focus, Procedure Guide, Radiopaedia), so they add nothing until they are counted.

Of the 65 excluded, 35 are excluded for an unknown licence. That makes the licence file the largest lever on the choice. Those 35 include the held fluoroscopy clips, CathAction, FluoroCap, Spinal AI 2024, the VerSe projections and the FluoroGen rare renders. 29 have no level truth and no use as a render source, and 1 is the demo sweeps.

### A count and angle table for mask-projected renders

The notes give the methods and the evidence: ct-priors-for-2d-detection.md items 2, 3 and 8, lumbosacral-to-cervical-extrapolation.md section 5, drr-realism-against-our-results.md, xr-from-3d/ and textbook chapter 13. None of them sets one combined table. The page proposes one, built from their figures. Counts it marks as estimates are arithmetic, not measurement.

- Poses: 100 per CT (ct-priors item 3), weighted to where naming collapses. AP is 25 poses: orbital 0 plus or minus 20 degrees by cranial-caudal minus 30 to plus 30. The obliques are 18: orbital plus or minus 30, 45 and 60 by minus 15, 0 and plus 15. Lateral is 15: orbital 90 plus or minus 15 by minus 10, 0 and plus 10. A random fill of 42 covers orbital plus or minus 90 by cranial-caudal plus or minus 30, the range of FluoroSAM's real test. Every pose is rendered at a spot field, and the whole-spine tier adds a long field. The bins are to be matched to C-ArmLSpine's measured angle bins, which the notes name but do not tabulate.
- Tiers:
  - T0 banks FluoroGen's 12,929 rare renders, once their licence is classified.
  - T1 is about 100,000 lumbosacral frames (1,000 volumes by 100 poses, 1 to 3 GPU-hours).
  - T2 is up to about 800,000 whole-spine frames (about 4,000 volumes by 100 poses by two fields, an estimate; 20 to 50 GPU-hours with translation; #135).
  - T3 is the physics ablation, three arms on a subset of T1 (10 to 20 GPU-hours). DeepDRR would be a new dependency, so it needs an issue first.
  - T4 is population-matched: DeepFluoro's own CTs at the 366 real poses plus or minus 2.5 degrees, and COBRA at its solved geometry. It measures the residual.
- Expected value, from the record: renders carry naming (96.4 percent zero-shot lateral), not detection (0.3 percent renders-only). So they are made for AP, oblique, cervical and thoracic naming, level maps and anchors, mixed with real frames.

## 2. The videos

26 records sit in the video group, and SX-Stitch's translated series makes 27 sequence records. Four are held: carmlspine_sweeps, fluoro_video_clips, dysphagiabank and cathaction. Only carmlspine_sweeps carries level truth with a paired volume. The page recommends running on case134, the recorded demo, which is never trained on. Bern myelography is the only cranio-caudal travelling sequence found, and it has to be requested.

## 3. State at the time of writing

- #253 is merged (6046dd8).
- The grid's status of 11:13 UTC lists no sweep or bank job, so the smoke has not been dispatched. There were 4,422 GB of room for a new fetch.
- #293 is open and not started.
- The AI Scientist plan's six decisions wait on the owner.
