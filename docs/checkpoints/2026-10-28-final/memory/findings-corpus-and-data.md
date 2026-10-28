---
name: findings-corpus-and-data
description: What data is held by greg's gold and silver tiers (two counts of gold 3), the gold tier 3 dataset and greg's open disagreement, the closed cohorts, pending sources, licences and data rules
metadata:
  type: project
---

Sources: the restart kit's FINDINGS.md section 9; SchwingNet docs/research/gold3-ct/README.md and #443's handoff (docs/checkpoints/2026-10-28-gold3-ct-handoff/HANDOFF.md on its branch); docs/research/full-spine-corpora-with-reader-counted-variants.md; docs/research/project-status-2026-10-28.md section 7. The tiers are in [[owner-science-rules]].

- Gold 1 and 2: none held; fourteen closed cohorts carry per-case reader counts over both junctions, none open (Lodz 2026, Jeonbuk 2020, the VERIDAH-labelled TUM CT and NAKO MRI, Tatara 2021, Sabri 2025 among them). Letters only once greg names cohorts; he sends them.
- Gold 3 has two counts that measure different things. 159 (TotalSegmentator 142, VerSe 17) counts persons whose whole spine and a person's masks sit on the grid together. Up to 1,637, the gold tier 3 dataset (#437, tools/gold3_ct.py, private page Gold Tier 3 CT), also counts ENHANCE.PET's 1,557 whole studies (865 to 1,478 persons), whose MOOSE masks four people corrected, read from the public bucket; their masks are not on the data root (the copy carried at 18:31 UTC matches no CT, and members.json says not held).
- greg's disagreement, 2026-10-28 17:08 UTC: "I DISAGREE THAT ONLY 17 VERSE SHOULS BE INCLUDED AND NO TOTALSEGMENTATOTR BUT ILL HANDLE THAT ON THE NEXT ACCOUTN". The pools: VerSe 355 persons (374 series, 76 holding C2, 325 with neuroradiologist reads); TotalSegmentator v3 1,935 persons (142 clean, 156 with C2 and the sacrum, 70 with Hofmann's reads, 286 under 18). His admission rule is open.
- Gold 4 about 1,929; silver 2 848 (COBRA, C-ArmLSpine, DeepFluoro, one cadaver); the SPINEPS census 21,622 CTs of 21,603 people, how many count from C2 unknown until the pilot runs. The tier sorter is SchwingNet #420 (draft) with the word `census tiers` (1 CPU, not counted).
- ENHANCE.PET classes from two masks agreeing: normal 90.3%; L6 with 12 ribs 50; L6 with 13 ribs 14; four lumbar 28; eleven ribs 33; no reader verdict yet.
- Not truth: CTSpinoPelvic1K's 802 abdominopelvic CTs, none countable from C2.
- Pending: Radiopaedia (approval 202610-9517, by hand only, never by script); Setting Scoliosis Straight and the Harms Study Group (greg's follow-up in his Outlook Drafts); Exeter and Bournemouth (passed to the Breens on 2026-10-26).
- Licences per site: of ENHANCE.PET, autoPET's 979 studies CC BY-NC, Leipzig's 379 and Careggi's 199 CC BY; TotalSegmentator CC BY; VerSe CC BY-SA or CC BY, unsettled; FluXray, FleXray's weights and COBRA non-commercial; data/licences.json classes every set.
- Rules: every fetch sized exactly first and refused whole past the quota; CT-RATE (21.3 TB) never without greg's terabytes; VinDr-SpineXR under WSU IRB HPR 2026-330; dataset letters from greg's Wayne State Outlook, tagged [XR/CT Imaging Research], as drafts he sends, saying nothing of models or training; returns searched in Junk Email too.

**Why:** gold-tier work starts from these counts, and the census, the letters and the fetches each need greg's word.
**How to apply:** count a person once; never raise a tier with a machine mask; name which gold 3 count a sentence means. See [[grid-words-and-counts]].
