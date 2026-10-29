# Gold tier 3: what is held, and what ENHANCE.PET 1.6k adds

Confidential with the rest of this repository. Written on 27 October 2026 for the owner's queue of 09:44 UTC, item 7: "see how much gold tier 3 data i have, including checking this source, https://registry.opendata.aws/enhance-pet-1-6k/".

Gold tier 3 is a whole spine, C2 to the sacrum in one study, in one modality, with a person's annotation. A mask a person drew, checked or refined counts as a person's; a machine's mask never raises a tier.

## Held now: 159 persons

Nothing held is gold 1 or gold 2. Gold 3 is 159 persons, counted from the release masks:

- TotalSegmentator, 142 persons. These are v3 subjects whose release masks hold C2 to L5 and the sacrum with at least 200 voxels each and no metal. The count may rise to 156 once the 14 subjects that the level or metal rule dropped are read. The masks are model output refined by hand, which the rule counts as a person's annotation. If the owner reads them as machine labels, these persons move to gold 4.
- VerSe, 17 persons, whose expert masks run from C1 or C2 into the lower lumbar spine with the lumbosacral junction in the field. VerSe labels no sacrum, so a look at each field on the grid must confirm the sacrum.

The source is SchwingNet's corpus-tiers draft (pull request #420, data/corpus-tiers/sources.json, whose rows add to 452 before the same persons in several copies are counted once). That thread is paused, and nothing here changes it.

## ENHANCE.PET 1.6k

What the public bucket enhance-pet-1-6k holds, read from its listing and its two small metadata files (CT-details.xlsx, 72,738 bytes; labels.json, 3,605 bytes) on 27 October 2026. Then, on the owner's word, the masks themselves were read in the thread's cloud container: the 1,597 vertebra masks (approved at 16:05 UTC) and the 1,597 rib masks (approved at 17:41 UTC), with the CTs of three studies for their repair. Nothing went to the grid, and the container does not keep them; the bucket is public, so the read can be made again.

| What | Count | Bytes |
| --- | --- | --- |
| Studies in the bucket | 1,597 | |
| AutoPET Challenge | 1,014 | |
| University Hospital Leipzig | 384 | |
| Azienda Ospedaliero Universitaria Careggi | 199 | |
| Vertebra masks, imaging-data/ground-truth/Vertebrae | 1,597 files | 381,439,888 |
| Rib masks, imaging-data/ground-truth/Ribs | 1,597 files | 312,882,241 |
| CT and PET volumes, imaging-data/images | 3,194 files | 250,202,834,785 |

The paper and the data card count 1,683 studies. The other 86 are UC Davis's, which are in Science Data Bank and not in the bucket. CT-details.xlsx carries their 86 rows blank, and the registry page counts 1,597 studies.

The vertebra masks name every body separately: C1 to C7 (ids 1 to 7), T1 to T12 (8 to 19), L1 to L6 (20 to 25), the two hips (26, 27) and the sacrum (28). There is an L6 and no T13. By CT-details.xlsx the slices are 3 mm thick in 1,168 studies, 2 mm in 177, 5 mm in 180, 3.75 mm in 19 and 1 mm in 52; the one row left, Leipzig study 1213, gives 0.98 mm, which is its pixel spacing, though its NIfTI slices are 3 mm apart. In the NIfTI files the slices lie 0.7 to 5 mm apart, the 1 mm ones 0.7 mm apart.

### How the masks were made, and the tier they reach

The paper is Ferrara D et al., "Sharing a whole-/total-body [18F]FDG-PET/CT dataset with CT-derived segmentations: an ENHANCE.PET initiative", Scientific Data 2026;13:869, doi:10.1038/s41597-026-07218-y, an advance online publication when read. MOOSE, seven nnU-Net models retrained site by site, drew the masks first. Then, by its Methods, a medical student verified and corrected each scan, a second student reviewed the first, and a radiology resident and a nuclear medicine resident reviewed both. The abstract calls the readers physicians in training. The paper does not say what share of scans needed a correction.

By the owner's rule these are a person's masks: checked and refined by people, as TotalSegmentator's are. So every ENHANCE.PET study whose field holds C2 to the sacrum is gold 3. SchwingNet's tiers draft calls them machine output (its row scidb_enhance_pet_1_6k). The paper says otherwise, and that row needs correcting when the tiers work resumes.

### How many are whole

The rule is the one the TotalSegmentator count used: C2 and the sacrum each present with at least 200 voxels, and every level between them present. At 17:10 UTC the owner answered the thread's line on "the 42 studies missing one level (40 lack only L5) and C2 at the field's edge": "these should absolutely not be excluded they may be examples of sacralization anomalies if the sacrum is view!" The 42 are the 40 with no L5 label and two with a thoracic label skipped, 1134 (no T1) and 1347 (no T9). The 40 are kept in the count below, so the rule excepts an absent L5, and so are the 17 whole studies whose C2 reaches the field's top slice. 1134 and 1347 were at first left out with 1283. At 17:42 UTC the owner asked for the three to be repaired rather than thrown away, and they are kept, repaired, as the test set below. They stay at gold 4 and outside the 1,557 because their published level names are wrong, and the names that fix them come from the ribs by rule or from MOOSE, not from a person.

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

Of the 40 with no L5 label, 39 have L4 directly above the sacrum: their head-foot extents overlap by 9 to 32.5 mm, as neighbouring bodies do. A reviewer of the count script showed that head-foot overlap alone can mislead: with their L5 label taken away, 74 of the 1,450 strict spines with no L6 would still show L4 overlapping the sacrum by 5 mm or more, since a steep lumbosacral junction stacks the bodies' extents. So the shortest 3-D distance between the L4 label and the sacrum label was measured too. In all 39 the two labels touch, 0.7 to 1.2 mm apart, one voxel; across a labelled L5 in 100 controls L4 never comes nearer the sacrum than 2.3 mm (median 15.0 mm), while L5 touches it in every one. So no body without a label lies between L4 and the sacrum in any of the 39. Four strict spines carry an L5 label under a quarter of L4's voxels (0179, 0213, 0270 and 1240, with 1,036 to 8,531 voxels): L4 touches the sacrum in 0270 and 1240 and comes within 2.5 mm of it in 0179 and 0213, inside the controls' range, so these may be short lumbar spines with a piece labelled L5 and are listed for a look. The fortieth, study 0529, labels the body below L4 as L6, a skipped label and not a short lumbar spine. So 67 of the 68 L6 labels sit below an L5. In 17 whole studies C2 reaches the field's top slice, so its top may be cut off. Ten whole studies have neighbouring labels out of head-foot order, one pair in each and two in 0040 (T1 and T2, T6 and T7), eleven pairs in all; the rib check on them is below.

### What the ribs say about the unusual lumbar counts

The rib masks were read for the 107 whole studies with an unusual lumbar count (the 39 with L4 above the sacrum, the 67 with an L6 below an L5, and 0529), for the three left out, and for the first 100 whole studies with every level from C2 to L5 and no L6, as controls. For the lowest rib on each side, every rib voxel within 3 mm of the spine is tallied by the label of the spine voxel nearest it, and the label with the most contacts is the one the rib meets. Two separate scripts, holdings/count_enhance_pet.py and the thread's own, gave the same rib and the same label on all 420 sides.

| Lowest rib meets | Controls | L4 above the sacrum | L6 below L5 |
| --- | --- | --- | --- |
| rib 12 on T12 | 96 | 24 | 51 |
| rib 11 on T11 | 3 | 8 | 0 |
| rib 11 on T11 on one side, rib 12 on T12 on the other | 0 | 1 | 0 |
| rib 13 on L1 | 0 | 0 | 14 |
| a label one level off | 0 | 2 | 2 |
| no spine label within 3 mm | 1 | 4 | 0 |
| Studies | 100 | 39 | 67 |

A study is placed by the side or sides whose lowest rib touches the spine, and goes under no spine label within 3 mm only when neither side does. Nine are read on one side only: 6 of the 24 in the row rib 12 on T12 for L4 above the sacrum (0530, 0703, 0704, 0755, 1028 and 1190), 1 of the 51 in that row for L6 below L5 (0914) and 2 of the 14 in the row rib 13 on L1 (0575 and 1592). The side read rests on a single contact voxel in 0703 and 0704 and on 5 in 0575, and 1578 rests on 2 contact voxels on one side and 1 on the other. In the column for L4 above the sacrum 14 of the 78 sides touch no label within 3 mm, against 2 of the controls' 200, so that column is thinner than its counts look.

In every control whose lowest rib touches the spine, it meets its own vertebra, so the tally can be read. What it says about the variants:

- 24 of the 39 spines with L4 above the sacrum have twelve rib pairs, the lowest meeting T12, on both sides in 18 and on one side only in the other 6, the other side's lowest rib coming within 3 mm of no spine label. These are the owner's sacralization candidates: an L5 counted into the sacrum, or a column one body short. The ribs cannot tell the two apart. Their sacrum label is a median 151 mm tall against 142.5 mm in the controls, which fits an L5 inside it, but the quartiles overlap (135 to 159 against 135 to 155) and the masks' slice spacing runs from 0.7 to 5 mm, so this is not a test.
- 8 of them have eleven rib pairs, the lowest on T11, so their T12 bears no rib, and a ninth, 1186, has twelve ribs on the left and eleven on the right. With 23 bodies above the sacrum, those eight are the column of study 1134, which the readers named upward from the sacrum and so left T1 unlabelled; here they named downward from C1. The same column carries two sets of names in one release.
- 51 of the 67 L6 spines have twelve rib pairs, the lowest on T12: an S1 freed from the sacrum, or a column one body long. Their sacrum label is a median 135 mm tall (quartiles 125 to 140), shorter than the controls', which fits an S1 outside it, with the same caveat.
- 14 of the 67 have thirteen rib pairs, the thirteenth on the label L1. The scheme has no T13, so the readers named the thirteenth rib-bearing body L1 and needed an L6 at the bottom. By the ribs these columns hold thirteen rib-bearing bodies above five without ribs, 25 above the sacrum. The ribs cannot say where the extra body arose: a thirteenth thoracic body over a whole sacrum and an L1 carrying a rib over an S1 freed from the sacrum give the same count. Their sacrum label is a median 134 mm tall (quartiles 126 to 147), as short as the twelve-rib L6 spines', which fits an S1 outside it, with the same caveat.
- Three studies carry labelling errors, and two more need the CT:
  - 0529 calls the body below L4 L6, with no L5, a skipped label.
  - In 0245 (L4 above the sacrum) every rib leads on the label one level up, the first pair on C7, so the labels sit one level high from the thorax down and the five lumbar bodies are labelled T12 and L1 to L4.
  - In 0603 (L6) the label T6 holds 10,349 voxels between T5's 34,247 and T7's 46,457, a split piece that pushes every label below it one level down. The column has eleven rib-bearing bodies above six without. Counting from C1, as the readers named the eight eleven-rib columns above, its T12 bears no rib and its L6 is an L5. Named by the ribs, as the repair of 1134 is, its lumbar names stand and only T6 to T12 are one level off.
  - In 0005 (L4 above the sacrum), open, the twelve right ribs lead on the label one level up, the first on C7, but the rib mask has eleven left ribs and each leads on its own label, T1 to T11. At every level left rib k meets the label right rib k+1 meets, so the two sides put ribs on the same bodies and differ only in their numbers. Two readings fit: labels one level high with the left first rib missing from the rib mask, as in 0245, or labels as published with a right cervical rib numbered rib 1, which makes 0005 an eleven-rib column of 23 bodies like the eight above. The right first rib is less than half the size of the right second (2,803 voxels against 6,607, a smaller ratio than in any of the 100 controls), which leans to the cervical rib, while C7's label holds 0.89 of T1's voxels, more than in 93 of the controls but less than any control's T1 against T2, which leans to the shift. Neither settles it; the CT has to.
  - In 1336 (L6), open, every rib, 11 a side, leads on the label one level below its own, and no rib leads on the label T1. Its C1, C2 and C3 are sized and placed as atlas, axis and C3 (voxel ratios C1 to C2 0.81 and C2 to C3 1.42, against the controls' medians of 0.79 and 1.42), and its 25 labels above the sacrum are whole bodies spaced as their neighbours are, with no split piece. So its vertebra mask holds one body more than the usual 24 however the ribs are read: a rib mask without its first ribs leaves the vertebra labels and the L6 right, and the other reading, a body named T1 that bears no rib, is a variant too.

None of these readings changes the whole-spine count, which needs C2, the sacrum and every level between them named, an absent L5 alone excepted. They question one study in it. 0529 is whole by that letter, since L5 is the only label it lacks, and the owner's word of 17:10 UTC was given on the 40 that lack only L5, 0529 among them. By its ribs, though, it skips L5 and names that body L6, as 1347 skips T9 and names that body T1, and 1347 was left out only because the label it skips is not L5. The readings do change what the release can be trusted for: of the 107 unusual lumbar counts, 3 are labelling errors, 2 more (0005 and 1336) need the CT, and 14 are thirteen-rib columns whose names give the thirteenth rib-bearing body a lumbar name, so a level name in these masks needs the ribs read beside it. The three errors, the two open cases and four more found by the same check among ten whole studies whose labels are out of head-foot order (0816 and 1273 clearly, 0040 and 1463 weakly), are listed with the three repaired studies in the test set below. None of the nine has been repaired.

### The three left out, repaired, and kept as a test set

Three Leipzig studies were left out at first because a label was skipped or scrambled. The owner asked at 17:42 UTC that they be repaired with the model that drew the masks rather than thrown away, and at 17:54 UTC: "dont forget these 3 because i want to use them as a test of SchwingCheck's ability to correct segmentations".

The model was MOOSE's clin_ct_vertebrae, the published release (459,374,233 bytes, its sha256 recorded with the test set), run on CPU in the container on each CT cut to a box around its spine. The ribs were the test, since the rib masks were checked by the same readers: every rib voxel within 3 mm of the spine is tallied by the label of the spine voxel nearest it, and in a correct mask rib k leads on Tk. They place every rib-bearing body; they cannot name a body that bears no rib.

- 1347 labels a body between T8 and T10 as T1, a second piece far below T1's own body, and has no T9. That piece is T9: both ninth ribs meet it, all 24 ribs then lead on their own Tk, and MOOSE's rerun puts T9 in the same place.
- 1134 has no T1 label, which looks like a skip, but the spine has only 11 rib pairs and no body without a label: 23 bodies from C1 to L5, eleven bearing ribs above five without. That much the ribs settle, so it is a real count variant. Whether the twelfth body is a ribless T12 or an L1 they cannot settle, and the release names this column both ways: the eight eleven-rib columns above carry a ribless T12 and L1 to L4. The repair names the bodies by their ribs, T1 to T11 and then L1 to L5. With T2 to T12 renamed T1 to T11, all 22 ribs lead on their own Tk, as they would under the other naming too. MOOSE's rerun is wrong under either naming: it split one body into two labels, putting twelve thoracic labels on eleven rib-bearing bodies.
- 1283 scrambles T3 to T11. MOOSE's rerun, with 5 stray pieces of 1,176 voxels given to the body they touch, puts twelve thoracic bodies in order; 23 of 24 ribs then lead on their own Tk, and left rib 3 leads on T2 by 25 contacts to 24 on T3, too close to call.

MOOSE's model was trained on all 1,683 studies with their published labels, these three included, so its rerun is not independent of them; the ribs are the independent check. The repaired 1283 is a machine's mask, and the repaired 1134 and 1347 are the readers' voxels under names a rule moved, so all three stay at gold 4 until a person checks them. The CTs, the published and repaired masks, MOOSE's output, the scripts and the hashes are in the Claude project's files, in the folder enhance-pet-repair, whose README sets the test out. It also lists the nine studies the rib check found mislabelled or likely so, with their tallies, none of them repaired. MOOSE's rerun also read the first sacral segment of 1347 as an L6 where the readers did not; the ribs cannot settle that, so the junction stays open.

### How many persons, and what it adds to what is held

Gold 3 from this set is the 1,557 whole studies whose labels are the readers' as published. AutoPET's 979 whole studies are 865 to 900 persons: the 1,014 studies are 900 persons (Gatidis S et al., Scientific Data 2022;9:601), so at most 114 studies repeat a person, and 35 of the 1,014 are not whole. Leipzig's and Careggi's 578 whole studies carry no person id, so they are at most 578 persons. The set gives at most 1,478 gold 3 persons, and at least 865.

AutoPET's CTs are already held as FDG-PET-CT-Lesions (SchwingNet docs/research/data-manifest/MANIFEST.md), at gold 4 in the tiers sort, which guessed 720 of its 900 persons whole. The masks show 865 to 900. Those persons move to gold 3 once ENHANCE.PET's masks sit beside the held CTs on the grid and each mask is matched to its CT by the shape and affine its NIfTI carries. The copy is a fetch that waits for the owner's word, and the match has not been tried. Leipzig's and Careggi's CTs are not held: the 581 whole ones, the repaired three included, take 45,207,300,328 bytes (35,545,685,343 for Leipzig's 382 and 9,661,614,985 for Careggi's 199), read from the bucket's listing of imaging-data/images/CT/ on 27 October 2026.

The script holdings/count_enhance_pet.py reads the masks from a folder and makes again the whole-spine count by site, the no-L5 overlaps, the persons, the rib pairs, the lowest-rib table of the 210 studies read and the three repaired studies with their tier. It does not make the bucket's sizes, the slice thicknesses, the sacrum heights, the 3-D distances, the CT bytes or the voxel counts quoted for single studies, which were read in the thread; the scripts in the test set's folder enhance-pet-repair make and check the repairs (crop.py, paste_all.py, relabel.py, strays.py, compare.py), the rib tallies of the studies found mislabelled or likely so (oo.py, step.py) and the 3-D distance from L4 to the sacrum (touch.py). SchwingNet keeps the same finding in docs/research/enhance-pet-gold-tier-3.md.

scanimport reads these masks under the label scheme `enhance` (scanimport/schemes.py).
