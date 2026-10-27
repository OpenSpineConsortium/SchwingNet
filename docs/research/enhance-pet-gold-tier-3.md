# ENHANCE.PET 1.6k in the evidence tiers

Source: the thread "Finish scan import and tier counts" of the symphony project, 27 October 2026, for the owner's queue of 09:44 UTC that day, item 7: "see how much gold tier 3 data i have, including checking this source, https://registry.opendata.aws/enhance-pet-1-6k/". Confidential: this note never leaves SchwingNet. The same finding is kept in bordercall's holdings/gold-tier-3.md.

## What was read

Read on 27 October 2026: the registry page; the public bucket enhance-pet-1-6k's listing; its two small metadata files, CT-details.xlsx (72,738 bytes) and labels.json (3,605 bytes); MOOSE's DATA_CARD.md on GitHub; and the paper, Ferrara D et al., "Sharing a whole-/total-body [18F]FDG-PET/CT dataset with CT-derived segmentations: an ENHANCE.PET initiative", Scientific Data 2026, doi:10.1038/s41597-026-07218-y. When it was read, the paper was an advance online publication, so its volume and article number (13, 869) are not yet final.

Then, on the owner's word, the masks themselves were read in the thread's cloud container: the 1,597 vertebra masks (381,439,888 bytes, approved at 16:05 UTC) and the 1,597 rib masks (312,882,241 bytes, approved at 17:41 UTC), with the CTs of three studies for their repair. Nothing went to the grid, and the container does not keep them; the bucket is public, so the read can be made again.

## What the bucket holds

| What | Count | Bytes |
| --- | --- | --- |
| Studies | 1,597 | |
| AutoPET Challenge | 1,014 | |
| University Hospital Leipzig | 384 | |
| Azienda Ospedaliero Universitaria Careggi | 199 | |
| Vertebra masks, imaging-data/ground-truth/Vertebrae | 1,597 files | 381,439,888 |
| Rib masks, imaging-data/ground-truth/Ribs | 1,597 files | 312,882,241 |
| CT and PET volumes, imaging-data/images | 3,194 files | 250,202,834,785 |
| The whole release as one zip | 1 file | 252,535,308,736 |

The paper and the data card count 1,683 studies. The other 86 are UC Davis's, which are in Science Data Bank and not in the bucket. CT-details.xlsx carries their rows blank, and the registry page counts 1,597.

The vertebra group, clin_ct_vertebrae, names C1 to C7 (ids 1 to 7), T1 to T12 (8 to 19), L1 to L6 (20 to 25), the hips (26 and 27) and the sacrum (28). It has no T13. Ids 1 to 25 are VerSe's, and ids 26 to 28 are not, so a mask read as VerSe would give a sacrum, a coccyx and a T13 where there are two hips and a sacrum. The slices are 3 mm in 1,168 studies, 2 mm in 177, 5 mm in 180, 3.75 mm in 19 and 1 mm in 52.

## The tier its masks reach

MOOSE, seven nnU-Net models retrained site by site, drew the masks first. Then, by the paper's Methods, a medical student verified and corrected each scan, a second student reviewed the first, and a radiology resident and a nuclear medicine resident reviewed both. The abstract calls the readers physicians in training. The paper does not give the share of scans that needed a correction.

A mask a person checked or refined is a person's annotation under the owner's tiers, as TotalSegmentator's refined masks are. So every ENHANCE.PET study whose field runs from C2 to the sacrum is gold 3. The corpus-tiers sort (pull request #420, row scidb_enhance_pet_1_6k) calls these masks machine output, and that row needs this correction.

## How many are whole

The rule is the one the TotalSegmentator count used: C2 and the sacrum each present with at least 200 voxels, and every level between them present. The owner widened it at 17:10 UTC for spines whose lowest lumbar body meets the sacrum with no L5 label between: "these should absolutely not be excluded they may be examples of sacralization anomalies if the sacrum is view!" Those are kept.

| | autoPET | Leipzig | Careggi | All |
| --- | --- | --- | --- | --- |
| Studies in the bucket | 1,014 | 384 | 199 | 1,597 |
| Whole, C2 to the sacrum | 979 | 379 | 199 | 1,557 |
| of them, every level from C2 to L5 named | 953 | 369 | 195 | 1,517 |
| of them, no L5 label above the sacrum | 26 | 10 | 4 | 40 |
| Whole ones that name an L6 | 45 | 16 | 7 | 68 |
| No C2 in the field | 35 | 2 | 0 | 37 |
| Left out for a skipped or scrambled label, then repaired | 0 | 3 | 0 | 3 |

The rows check: 1,557 whole, 37 without C2 and 3 left out make 1,597. With the three repaired, 1,560 studies are whole.

Of the 40 with no L5 label, 39 have L4 directly above the sacrum: their head-foot extents overlap by 9 to 32.5 mm, as neighbouring bodies do. The fortieth, study 0529, labels the body below L4 as L6, a skipped label and not a short lumbar spine. So 67 of the 68 L6 labels sit below an L5. In 17 whole studies C2 reaches the field's top slice, so its top may be cut off. Ten whole studies have one pair of neighbouring labels out of head-foot order; the rib check on them is below.

## What the ribs say about the unusual lumbar counts

The rib masks were read for the 107 whole studies with an unusual lumbar count (the 39 with L4 above the sacrum, the 67 with an L6 below an L5, and 0529), for the three left out, and for the first 100 whole studies with every level from C2 to L5 and no L6, as controls. For the lowest rib on each side, every rib voxel within 3 mm of the spine is tallied by the label of the spine voxel nearest it, and the label with the most contacts is the one the rib meets. Two separate scripts, bordercall's holdings/count_enhance_pet.py and the thread's own, gave the same rib and the same label on all 420 sides.

| Lowest rib meets | Controls | L4 above the sacrum | L6 below L5 |
| --- | --- | --- | --- |
| rib 12 on T12 | 96 | 24 | 51 |
| rib 11 on T11 | 3 | 8 | 0 |
| rib 11 on T11 on one side, rib 12 on T12 on the other | 0 | 1 | 0 |
| rib 13 on L1 | 0 | 0 | 14 |
| a label one level off | 0 | 2 | 2 |
| no spine label within 3 mm | 1 | 4 | 0 |
| Studies | 100 | 39 | 67 |

In every control whose lowest rib touches the spine, it meets its own vertebra, so the tally can be read. What it says about the variants:

- 24 of the 39 spines with L4 above the sacrum have twelve rib pairs, the lowest on T12. These are the owner's sacralization candidates: an L5 counted into the sacrum, or a column one body short. The ribs cannot tell the two apart. Their sacrum label is a median 151 mm tall against 142.5 mm in the controls, which fits an L5 inside it, but the quartiles overlap (135 to 159 against 135 to 155) and the slices run from 0.7 to 5 mm, so this is not a test.
- 8 of them have eleven rib pairs, the lowest on T11, so their T12 bears no rib, and a ninth, 1186, has eleven ribs on the left and twelve on the right. With 23 bodies above the sacrum, that is the column of study 1134, which the readers named upward from the sacrum and so left T1 unlabelled; here they named downward from C1. The same column carries two sets of names in one release.
- 51 of the 67 L6 spines have twelve rib pairs, the lowest on T12: an S1 freed from the sacrum, or a column one body long. Their sacrum label is a median 135 mm tall (quartiles 125 to 140), shorter than the controls', which fits an S1 outside it, with the same caveat.
- 14 of the 67 have thirteen rib pairs, the thirteenth on the label L1. The scheme has no T13, so the readers named the thirteenth rib-bearing body L1 and needed an L6 at the bottom. By the ribs these columns hold thirteen rib-bearing bodies above five without ribs. Whether the thirteenth is a T13 or an L1 with a lumbar rib is a naming convention; either way, by the ribs, the extra body sits at the thoracolumbar junction and not at the lumbosacral one.
- Five studies are labelling errors, not variants. 0529 calls the body below L4 L6, with no L5, a skipped label. In 0005 and 0245 (L4 above the sacrum) every rib leads on the label one level up, the first rib on C7, so the labels sit one level high from the thorax down and the five lumbar bodies are labelled T12 and L1 to L4. In 0603 (L6) the label T6 holds 10,349 voxels between T5's 34,247 and T7's 46,457, a split piece that pushes every label below it one level down, so its L6 is an L5. In 1336 (L6) the whole run sits one label low from the first rib, which a first rib missing from the rib mask or one cervical label too few would both explain.

None of these readings changes the whole-spine count, which needs only C2, the sacrum and an unbroken run of labels between them. They do change what the release can be trusted for: of the 107 unusual lumbar counts, 5 are labelling errors and 14 are thirteen-rib columns whose extra body the names put at the bottom of the lumbar spine, so a level name in these masks needs the ribs read beside it. The five errors, and four more found by the same check among ten whole studies whose labels are out of head-foot order (0816 and 1273 clearly, 0040 and 1463 weakly), are listed with the three repaired studies in the test set below. None of the nine has been repaired.

## The three left out, repaired, and kept as a test set

Three Leipzig studies were left out at first because a label was skipped or scrambled. The owner asked at 17:42 UTC that they be repaired with the model that drew the masks rather than thrown away, and at 17:54 UTC: "dont forget these 3 because i want to use them as a test of SchwingCheck's ability to correct segmentations".

The model was MOOSE's clin_ct_vertebrae, the published release (459,374,233 bytes, its sha256 recorded with the test set), run on CPU in the container on each CT cut to a box around its spine. The ribs decided each case, since the rib masks were checked by the same readers: every rib voxel within 3 mm of the spine is tallied by the label of the spine voxel nearest it, and in a correct mask rib k leads on Tk.

- 1347 labels a body between T8 and T10 as T1, a second piece far below T1's own body, and has no T9. That piece is T9: both ninth ribs meet it, all 24 ribs then lead on their own Tk, and MOOSE's rerun puts T9 in the same place.
- 1134 has no T1 label, which looks like a skip, but the spine has only 11 rib pairs. Its bodies are T1 to T11, L1 to L5 and the sacrum, 23 from C1 to L5, and with T2 to T12 renamed T1 to T11 all 22 ribs lead on their own Tk. It is a real count variant. MOOSE's rerun got it wrong by forcing twelve thoracic labels, splitting one body into two.
- 1283 scrambles T3 to T11. MOOSE's rerun, with 6 stray pieces of 1,176 voxels given to the body they touch, puts twelve thoracic bodies in order; 23 of 24 ribs then lead on their own Tk and one is a tie.

MOOSE's model was trained on all 1,683 studies with their published labels, these three included, so its rerun is not independent of them; the ribs are the independent check. The repaired 1283 is a machine's mask, and the repaired 1134 and 1347 are the readers' voxels under names a rule moved, so all three stay at gold 4 until a person checks them. The CTs, the published and repaired masks, MOOSE's output, the scripts and the hashes are in the Claude project's files, in the folder enhance-pet-repair, whose README sets the test out. It also lists the nine studies the rib check found mislabelled or likely so, with their tallies, none of them repaired. MOOSE's rerun also read the first sacral segment of 1347 as an L6 where the readers did not; the ribs cannot settle that, so the junction stays open.

## How many persons, and what it adds to what is held

Gold 3 from this set is the 1,557 whole studies whose labels are the readers' as published. AutoPET's 979 whole studies are 865 to 900 persons: the 1,014 studies are 900 persons (Gatidis S et al., Scientific Data 2022;9:601), so at most 114 studies repeat a person, and 35 of the 1,014 are not whole. Leipzig's and Careggi's 578 whole studies carry no person id, so they are at most 578 persons. The set gives at most 1,478 gold 3 persons, and at least 865.

AutoPET's CTs are already held as FDG-PET-CT-Lesions (docs/research/data-manifest/MANIFEST.md), at gold 4 in the tiers sort, which guessed 720 of its 900 persons whole. The masks show 865 to 900. Those persons move to gold 3 once ENHANCE.PET's masks sit beside the held CTs on the grid and each mask is matched to its CT by the shape and affine its NIfTI carries. The copy is a fetch that waits for the owner's word, and the match has not been tried. Leipzig's and Careggi's CTs are not held: the 581 whole ones, the repaired three included, take 45,207,300,328 bytes (35,545,685,343 for Leipzig's 382 and 9,661,614,985 for Careggi's 199), read from the bucket's listing of imaging-data/images/CT/ on 27 October 2026.

The count is made again by bordercall's holdings/count_enhance_pet.py, which reads the masks from a folder and prints every number above; the same finding is in bordercall's holdings/gold-tier-3.md.
