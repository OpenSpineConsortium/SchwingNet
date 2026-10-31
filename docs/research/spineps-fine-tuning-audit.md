# Fine-tune SPINEPS on the gold tier, or train a segmenter of our own

Source: the thread "Build self-propelling QA Metaflow pipeline", 31 October 2026, the owner's questions of 01:16 to 01:29 UTC that day: whether SPINEPS is the only anomaly-aware CT spine code, and whether to fine-tune its CT weights on the gold tier 3 masks to make the segmenter NMDID needs. The answer came from an audit run in the thread at about 05:00 UTC: readers of SPINEPS's code at its public head and of its released CT weights (the checkpoints read as files, never unpickled), a planner, two adversarial checkers on each of ten claims and a critic, whose corrections this note takes in. Confidential with the rest of this repository.

## The answer

No to both. SPINEPS is not the only anomaly-aware CT spine code: Payer's public VerSe 2020 code locates 26 levels, T13 and L6 among them, and ships its training code; Hofmann's VertebralBodiesCT models carry optional T13 and L6 bodies; TotalSegmentator's total_v3 and MOOSE write an L6 and no T13, so their L6 means a 25th body above the sacrum; and CTSpinoPelvic1K is a dataset whose v11 has L6 but neither T13 nor S1. The prior-art table's "no L6" for TotalSegmentator is out of date.

And do not start from SPINEPS's weights. Train one nnU-Net v2 ResEnc L from random initialisation on the 28 canonical ids, the sacrum as one union, with the latent prior's test reserve, the test persons and the anomaly holdout left out; let a decoder anchored at C2 and the sacrum name the levels; and keep SPINEPS unchanged as the comparator, scored only where it ran. This is the order docs/research/whole-spine-ct-online/README.md section 7 already recommends: one segmenter on gold tier 3, then VSDFullBody for post-mortem CT, then NMDID.

## Why not SPINEPS's weights

- Its CT semantic network predicts subregions, not levels: the v2.0.0 release's network (Dataset512, which SPINEPS 2.1.x fetches) has 20 classes, the processes, the body and its border, the dens, the end plates, the sacral parts, the disc and metal; the v1.4.2 release's (Dataset511, which SPINEPS 2.0.0 fetched, and which made some of the census's masks) has 17 with no end plates. The gold tier's whole-vertebra masks can supervise only unions of those classes, so the network can be neither fine-tuned nor retrained on its own task from them.
- A head of 28 ids could be grafted on, since nnU-Net's pretrained weights carry everything but the segmentation layers, but the weights load only into SPINEPS's own plans, and its 3,000 training cases are 750 unnamed sources seen four times each. Under the rule that unknown is not clean and a leaked initialisation is fixed by retraining, never disclosed (spine-program's rules 5 and 9), nothing initialised from them could call a reserve person held out.
- Its instance network reads only the semantic map, never the CT, and is redundant once each level is a class of its own.
- VERIDAH, its labeller, has a level head of 24 classes, C1 to L5, with T13 trained as T12; in the CT path T13 and L6 arise only from repeat moves with every penalty 0.0, and it ships no runnable training code. On VerSe the lab measured it finding 36 of 83 L6 (36 of its 38 L6 calls right), its T13 calls right 4 of 16 and its four-lumbar calls 2 of 20 (docs/research/spineps-anomaly-route.md).

## The route

1. Freeze a PREREG before any training, as every deep learning job here runs on a launched flow (docs/memory/every-deep-learning-job-runs-on-a-launched-flow.md), with the owner's choices below written in it.
2. Split by person with data/splits/rule.json, reusing tools/autoanatomist_plan.py's checks rather than a new splitter: the rule's part, both test lists, the repeat units, and no study whose part differs from its unit's. Before any send, check the autoPET repeat units against the census's PETCT person keys, which the split never used.
3. Convert to nnU-Net's raw layout with the code's own maps, tools/gold3_ct.py's ENHANCE_TO_CANONICAL and tools/anomaly_pack.py's VERSE_TO_CANONICAL; never reorient a label alone; set every level a machine arm added and every undrawn region to ignore. Recount each converted column against its recorded call and render one study per member and anomaly class.
4. Plan with nnUNetPlannerResEncL, the planner SPINEPS used, and train one 3d_fullres model from random initialisation, no pretrained weights from any checkpoint whose training persons are unnamed (TotalSegmentator's and MOOSE's included), on a card of 24 GB or more (galhp's L40S), mirroring only left and right, since the stock trainer mirrors all three axes and flips the column's order. No ensemble or cascade until this one model works.
5. Take instances from the prediction, one component a class, split, merged and kept by the census's decode rules, each with its centroid, height and mean softmax computed inside the prediction step: nnU-Net's saved probabilities, a float map per class per CT, would not fit 20 TB for NMDID.
6. Name the levels with a decoder built from the auto-anatomist's naming layer (grid/autoanatomist/autoanatomist/naming.py) and fitted as grid/prior/gold3_prior.py fits, on training persons only, with an eleven-thoracic column and a column with both T13 and L6 added; not from src/schwingnet/chain.py, which never ran on real data and reports a runner-up from too few paths, nor tools/chain_stats.py, which reads no ENHANCE.PET and cannot leave persons out. Keep the voxel T13 and L6 classes only if they fire on validation; else the decoder carries the anomalies.
7. Score once on the reserve per member and anomaly class, the column call and each body's name first and Dice second, with Wilson intervals and nothing pooled; then run the frozen segmenter on VSDFullBody, tuning nothing from it, and only then NMDID, its own reserve drawn from its metadata before any image.

## The comparator

SPINEPS's masks the census already holds, scored only on the reserve studies it ran on: a run that failed counts as a miss, and a study it never ran on (the 194 Leipzig and Careggi rows) is reported apart as not run. The weights that made each mask are recorded and masks of different weights never pooled. No SPINEPS number is held out on any person, so a win for the new model reads as conservative, most of all on VerSe, which SPINEPS's own group made. A fresh SPINEPS run waits for the owner's word, since his rule is that SPINEPS is never re-run.

## Risks

- Few anomalies to learn from: outside the reserve, ENHANCE.PET keeps 18 six-lumbar studies with twelve ribs, 6 with thirteen, 12 four-lumbar, 9 with eleven ribs, 1 with thirteen ribs and 2 with asymmetric ribs, by the audit's checked count; the lab's earlier L6 voxel class never learned L6 from 12 to 18 cases.
- The truth is not independent of a machine: ENHANCE.PET's masks began as MOOSE drafts a person corrected, so Dice favours a model trained on them; level identity, not Dice, decides.
- Domain: the gold tier is living CT, mostly PET/CT with slices up to 2.5 mm, and NMDID is post-mortem CT whose adults are two acquisitions to join before the count from C2.
- Leakage not settled: Leipzig's and Careggi's studies carry no person id, so those reserve rows are held out only as far as anatomy tells.
- Licence: ENHANCE.PET's strictest site licence is CC BY-NC 4.0 (data/licences.json), so the segmenter is non-commercial unless a commercial catalog is cut; NMDID's agreement forbids derivative works, which bears on keeping its masks.

## The owner's calls

- The convention that names the thoracolumbar junction in the targets: true ribs, VERIDAH's own definition and the only way ENHANCE.PET supplies a T13, or the names as drawn; the two differ in about 50 ENHANCE.PET studies.
- Whether his own segmenter replaces SPINEPS as the production value of the segmenter block for NMDID, against his rule of 2026-10-26 that production runs use SPINEPS.
- Whether SPINEPS may run once more on the reserve as a second comparator.

## Not settled

Whether ENHANCE.PET's sacrum mask holds the coccyx or a fused transitional body, which decides what the sacrum as one union means; whether NMDID's head-and-neck and torso acquisitions share a frame; whether VSDFullBody carries level labels; and who the persons behind SPINEPS's and VERIDAH's training data are, which only their authors can say.
