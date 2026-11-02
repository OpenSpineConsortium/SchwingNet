# Pre-registration: the QA loop with external real arms and the sacral anchor

Covers: qa_ext_smoke=d58f65d180c861477f95337f0ac407ac76f04adaa1779592c4f327a20a35a205, qa_ext=d0b6930b215772ecda5f9591a3e19c72d3b7f695a4d9584282e23334c8ab6831

Source: the local session of 1 November 2026, on the owner's asks of that evening: "mix in some real fluoro into the validation stage of the 2D landmarks to make sure the landmarks aren't synthetic artifacts"; asked whether more paired CT and X-ray sets were held, "Do it all", "start with deep fluro and then move onto cobra"; and "look for sacral landmarks as finding the anchor is necessary to the counting based verification". The protocol is the Lab Recipe ("Pre-register and freeze") and the owner's rule of 2026-10-29 that every deep learning job on the grid runs on a launched flow under a frozen pre-registration. Label: confidential-method; the landmark direction stays private.

This file is frozen. It was written before any job of its plans was queued on the grid. Its two plans are covered by their bytes on the line above. Every departure after the freeze goes in DEVIATIONS.md beside this file, dated, with its reason.

## 1. What this design is

The QA loop's design, docs/research/qa-loop/PREREG.md as frozen with sha256 c588988049e1c983ee551f9d5c1177f0b8c7db8083bf2dfd73bea6a656e9da55, is adopted whole: its question, population and inputs, checkpoints and bars, controller, failures and verdict, analysis plan and known limits (its sections 1 to 6) hold here word for word, together with the loop's DEVIATIONS.md item 1 (C-ArmLSpine's masks read whole). That file is frozen and never edited, so this design is a file of its own, run by the flow under the kind qaloop_ext (flows/qaloop_ext.py, grid/qaloop_ext.sbatch).

The question it adds: are the fingerprint's landmarks, and the count's anchor, real structures on real X-rays of other people, other devices and other centres, or artefacts of the phantoms and of one C-arm?

## 2. The external real arms

Two further sets of real X-rays with a registered CT, built by tools/realx_pairs.py into the pair format the loop already reads and placed under the data root (realx/deepfluoro, realx/cobra), each with a manifest naming every person, its part and the reason for every person not read.

- DeepFluoro (Grupp 2020): six cadaveric lower torsos on a Siemens Cios Fusion C-arm, with ground-truth poses from 2D/3D registration, as the realxray export of 2026-09-21 converted them (data/realxray/deepfluoro: each frame as attenuation with its K and extrinsic in the CT's LPS frame, checked against the shipped 2D labels). On 1 November: 3 specimens built, 190 frames; the export's test specimen (18-1109) held out; 2 specimens left out, on which the two labellers name no two consecutive levels alike.
- COBRA2026 (Thummerer 2026), Elekta XVI centres A to D, as the realxray export v3 of 2026-09-23 converted them (data/realxray/cobra_elekta_v3: 24 kV projections a case from the machine's geometry, the CT-to-projection axis map confirmed case by case by edge NCC). On 1 November: 66 cases built, 1,584 frames; the export's 27 test cases held out; 57 left out: 50 because the transitional screen (data/cobra2026/lstv) does not call the column ordinary, L1 to L5 above the sacrum (32 unreadable, the field cut above L1; 8 T13; 4 L6; 2 four lumbar; 4 with no call), since the real arm names the typical column; 5 the export excluded; 2 with no two consecutive levels named alike. Every case is of one living radiotherapy patient.

For both: each person's vertebrae are TotalSegmentator's masks on the CT; the levels are the longest consecutive stretch, two or more, that TotalSegmentator and SPINEPS name alike; the oracle places its eighteen landmarks on them read whole, they are taken to LPS and projected through each frame's pose brought to the loop's 512 pixels (a frame that is not square centred on a square canvas first). Every external person serves the gates alone (part validation): no external frame chooses a landmark, sets the presence floor or trains the network, as the real-frame sets are test only by the harvest directive. A built set that changes is a deviation: every round records each manifest's sha256.

## 3. What the gates read, and what is recorded beside them

- The real naming gate and the presence gate read the C-ArmLSpine validation persons' frames and every external frame together, at the loop's bars, and steer the controller as in the loop.
- Recorded beside them, steering nothing: each source's own real naming and presence at the same bars (so a source that fails is seen even where the pooled gate passes; COBRA holds most of the frames), and the sacral anchor.
- The sacral anchor: four points on the top of S1 read from the sacrum mask alone (tools/qaloop_samples.py, sacral_points): along the column's axis from the sacrum's centroid to the lowest lumbar body's, the promontory (the most anterior voxel within 6 mm of the sacrum's top), the centre of that top slab, and the two alae (the farthest voxels to either side within 25 mm of the top). On every gate frame where three or more fall inside the frame, the mean percentile of their edge strength against points drawn inside their own outline; the anchor is shown where the share of such frames at or above 0.6 has its Wilson lower bound at or above 0.6, the presence gate's bars. It is reported for all real gate frames and for each source.

## 4. Leakage and the held-out test

C-ArmLSpine is dealt as in the loop: the persons of data/splits/test-persons.json are never read, the rest by data/splits/rule.json's hash, training persons to the selection and validation persons to the gates; no person is in two parts (the audit of 1 November: 112 training and 13 validation persons read, 0 test, 0 in both). DeepFluoro's held-out specimen and COBRA's held-out cases are never read by any round. The controller steers on the gates, so every real gate number of this loop is a validation number; the test, once, after the loop ends, is the C-ArmLSpine test persons and the two held-out external parts, under this design and no other.

## 5. Known limits

Beyond those of the loop's PREREG section 6:
- Lumbosacral only: the external sets show L2 to S1 at most; nothing here speaks to the thoracic or cervical spine.
- COBRA's projections come from a radiotherapy kV imager, not an intraoperative C-arm; DeepFluoro is cadaveric and shows mostly the pelvis, the lumbar bodies at the frame's top edge.
- The level truth is two automatic labellers agreeing; no person read these levels. In DeepFluoro they agree on few levels.
- The sacral points are geometric definitions on a mask, not points an anatomist placed, and an edge at a point is evidence of a structure there, not of which structure it is.
- COBRA's frames dominate the pooled gates; the per-source results are recorded for that reason, and no claim about the C-arm is made from COBRA alone.

## 6. Freeze

`sha256sum PREREG.md > PREREG.md.sha256` in this folder, both committed with the plans the Covers line names; the launcher refuses a run whose PREREG or plan moved (exit 90), and the job script checks the hash on its node before it reads anything.

First frozen on 2026-11-01, before any job of these plans was queued on the grid.
