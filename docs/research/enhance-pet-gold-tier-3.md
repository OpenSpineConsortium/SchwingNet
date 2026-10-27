# ENHANCE.PET 1.6k in the evidence tiers

Source: the thread "Finish scan import and tier counts" of the symphony project, 27 October 2026, for the owner's queue of 09:44 UTC that day, item 7: "see how much gold tier 3 data i have, including checking this source, https://registry.opendata.aws/enhance-pet-1-6k/". Confidential: this note never leaves SchwingNet. The same finding is kept in bordercall's holdings/gold-tier-3.md.

## What was read

Read on 27 October 2026: the registry page; the public bucket enhance-pet-1-6k's listing; its two small metadata files, CT-details.xlsx (72,738 bytes) and labels.json (3,605 bytes); MOOSE's DATA_CARD.md on GitHub; and the paper, Ferrara D et al., "Sharing a whole-/total-body [18F]FDG-PET/CT dataset with CT-derived segmentations: an ENHANCE.PET initiative", Scientific Data 2026, doi:10.1038/s41597-026-07218-y. When it was read, the paper was an advance online publication, so its volume and article number (13, 869) are not yet final. No image or mask was downloaded.

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

## How many persons, and what is held already

AutoPET's 1,014 studies are 900 persons (Gatidis S et al., Scientific Data 2022;9:601), and their CTs are held as FDG-PET-CT-Lesions (docs/research/data-manifest/MANIFEST.md), at gold 4 in the sort. The study table gives Leipzig's and Careggi's 583 studies a study number and no person id. So at most 1,483 persons could come from the set.

How many of them are whole is not known. A count needs one read of the vertebra masks, 381,439,888 bytes, applying the rule the TotalSegmentator count used: C2 and the sacrum each present with at least 200 voxels, and every level between them present. That read is a fetch and waits for the owner's word. If each autoPET mask can be matched to its held CT by the shape and affine its NIfTI carries, the whole ones among the 900 held persons move from gold 4 to gold 3 with no new CT. The match has not been tried.
