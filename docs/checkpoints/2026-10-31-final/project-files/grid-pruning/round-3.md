# Grid pruning, round 3: everything outside greg's four classes

Source: thread "Prune unused grid datasets", 2026-10-31 02:11 UTC. greg's words: "I want all these datasets GONE EXCEPT FOR
FLUOROSCOPIC XRAY, GOLD TIER 3/4 and paired CT-XRay data; YOU CAN ALSO KEEP THE PLAIN FILM XRAY; BUT ALL THE REST OF IT GOES".

Sizes are from spine-datasets' storage feed (snapshot of 2026-10-24, SchwingNet docs/textbook/figures/22/storage-plan.json).
"Gold 4" is the SPINEPS census of 2026-10-29 (SchwingNet data/gold3-ct/members.json, census.gold4.by_collection): a CT
collection is kept when the census admitted at least one study from it.

## Removed in this round (storage request dispatched 02:20 UTC), 723 GB

| set | GB | why it goes |
| --- | ---: | --- |
| rsna_2022_cervical | 203.3 | CT of the neck only, not gold 3 or 4 |
| ctspinopelvic1k | 202.7 | CT, census admitted 0 of 801 (the consortium's own release; it stays on Zenodo and Hugging Face) |
| ctspine1k | 162.4 | CT, census admitted 0 of 216 |
| nlst_pilot | 73.5 | chest CT, census admitted 0 of 489 |
| pengwin_task2_xrays | 35.0 | synthetic X-rays of the pelvis, not fluoroscopy or film |
| barts_crl | 20.3 | CT, census admitted 0 of 208 |
| ctpelvic1k | 14.8 | CT, census admitted 0 |
| csi2014 | 6.6 | CT, census admitted 0 of 20 |
| verse_2d_projections | 4.4 | synthetic projections of VerSe, not fluoroscopy or film |

## Already going

- Round 1, spine-datasets #377: 10 chest-only and no-spine CTs, 2.3 TB.
- Round 2, the prune word: idc_nlst, hf_abdomenatlas2_0_mini, a second zenodo_unitochest copy and hf_rexgradient_160k, 4.2 TB.

## Kept

- VSD full-body (252 GB): greg's choice of 02:19 UTC, kept as the post-mortem validation set for the NMDID pipeline.
- Fluoroscopy: C-ArmLSpine, DeepFluoro, LUMOS, Ljubljana 2D/3D, Geneva hip, CathAction, DysphagiaBank (videofluoroscopy).
- Paired CT and X-ray: COBRA, IPCAI 2025 femur, the veterinary pig set.
- Plain film: NHANES II (both), VinDr-SpineXR, BUU-LSPINE, CSXA, AASCE, KUB-StoneX, NIH ChestX-ray14, Aariz, MTDDH.
- Gold 3: ENHANCE.PET (with tcia_fdg_pet_ct_lesions, its autoPET source), VerSe, TotalSegmentator.
- Gold 4: AbdomenAtlas 3 mini, PANORAMA, QUADRA_HC, CURVAS, CURVAS-PDACVI, DEEP-PSMA, AortaSeg-60, AMOS22, WAW-TACE,
  kidney_thoraxabdomen, PENGWIN 2026, RibFrac, and the IDC collections the census read (439 gold 4 people among them; the
  repository holds no count per IDC collection, so none is removed until one is read).

## Not decided yet

- The 9.9 TB of derived files (banks, renders, archives, run outputs) on the lab volume: the read-only survey of
  the volume by folder (grid word storage-survey) was sent at 02:15 UTC, and a list follows from it.
