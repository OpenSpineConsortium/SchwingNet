# Dataset licences and training recipes

Written by `python3 tools/licences.py render` from data/licences.json and data/recipes/; do not edit by hand.
A class reads the licence's words (tools/licences.py); whether a trained network is a derivative is for counsel.

## Classes

| Class | Datasets | Owner-reviewed |
|---|---|---|
| open | 25 | 4 |
| share-alike | 2 | 0 |
| non-commercial | 18 | 0 |
| agreement | 31 | 0 |
| no-derivatives | 3 | 0 |
| unknown | 40 | 0 |

## Recipes over the trainable sources (data/registry/)

yes: the recipe takes the source now; after review: its class fits, and the recipe takes it once the owner confirms the class; -: never under this licence.

| Source | Class | Reviewed | commercial-share-alike | commercial | non-commercial | research-internal |
|---|---|---|---|---|---|---|
| aariz | open | owner 2026-10-23 | yes | yes | yes | yes |
| bimcv_covid19 | agreement | rule | - | - | - | yes |
| canine_thoracic_vhs | unknown | rule | - | - | - | - |
| carmlspine | open | owner 2026-10-23 | yes | yes | yes | yes |
| carmlspine_sweeps | open | owner 2026-10-23 | yes | yes | yes | yes |
| cathaction | unknown | rule | - | - | - | - |
| fracatlas | unknown | rule | - | - | - | - |
| fraiwan_spine_xray | unknown | rule | - | - | - | - |
| isbi2015_cephalograms | unknown | rule | - | - | - | - |
| kaggle_fracture_multiregion | unknown | rule | - | - | - | - |
| kaggle_scoliosis_yolov5 | unknown | rule | - | - | - | - |
| kub_stonex | open | owner 2026-10-23 | yes | yes | yes | yes |
| lumos | non-commercial | rule | - | - | yes | yes |
| mimic_cxr_jpg | agreement | rule | - | - | - | yes |
| nih_chestxray14 | unknown | rule | - | - | - | - |
| open_i_chest | unknown | rule | - | - | - | - |
| padchest | agreement | rule | - | - | - | yes |
| pengwin_task2_xrays | unknown | rule | - | - | - | - |
| radiopaedia_fluoro | non-commercial | rule | - | - | yes | yes |
| radiopaedia_xr | non-commercial | rule | - | - | yes | yes |
| verse_2d_projections | unknown | rule | - | - | - | - |
| vertxnet_nhanes2_labels | unknown | rule | - | - | - | - |
| vfss2022 | unknown | rule | - | - | - | - |
| vindr_cxr | agreement | rule | - | - | - | yes |
| vindr_pcxr | agreement | rule | - | - | - | yes |
| vindr_spinexr | agreement | rule | - | - | - | yes |

## Every dataset

| Dataset | Class | Commercial | Reviewed | Licence |
|---|---|---|---|---|
| aariz_cephalograms | open | yes | owner 2026-10-23 | CC BY 4.0 (figshare 27986417, doi 10.6084/m9.figshare.27986417; the record's licence field, read from the API on 2026-10-21); Khalid, Fraz et al., Scientific Data 2025, doi 10.1038/s41597-025-05542-3 |
| aasce | agreement | no | rule | by request form (SpineWeb dataset 16); the mirror repository is MIT, the images' reuse terms not recorded |
| anomaly_harvest_b | unknown | unknown | rule | varies by collection |
| aws_stoic2021 | non-commercial | no | rule | CC BY-NC 4.0 |
| balgrist_lumbar | unknown | unknown | rule | not recorded |
| bern_myelography | agreement | no | rule | CC BY 4.0 (the article's videos); native DICOM available on reasonable request under Swiss law |
| bimcv_covid19 | agreement | no | rule | BIMCV's COVID-19+ research use agreement, accepted by the owner on 2026-10-22; no redistribution, the link kept inside the organisation |
| bournemouth_cervical_qf | no-derivatives | no | rule | CC BY 4.0 (the tracks); README.rtf CC BY-ND; the MAID images (OSF z2jby) CC BY-NC 4.0, set on OSF by Marcin Budka on 2026-10-25 |
| bournemouth_lumbar_qf | non-commercial | no | rule | CC BY-NC 4.0 for the MAID images (OSF z2jby), set on OSF by Marcin Budka on 2026-10-25; OSF a27py holds derived tables only |
| buu_lspine | agreement | no | rule | the release's end-user agreement by request form: acknowledgement required, no re-identification, never redistributed |
| cads | agreement | no | rule | a data use agreement (non-commercial) |
| canine_thoracic_vhs | unknown | unknown | rule | Mendeley Data ktx4cj55pn, CC BY 4.0 to confirm on the page |
| carmlspine | open | yes | owner 2026-10-23 | CC BY 4.0, public (Zenodo 22768651); real patients, de-identified by the publisher; covered by the IRB umbrella HPR 2026-269 as public de-identified data |
| carmlspine_sweeps | open | yes | owner 2026-10-23 | CC BY 4.0, public (Zenodo 22768651), the raw CBCT projections of two cases; the same determination as carmlspine |
| cathaction | unknown | unknown | rule | Hugging Face airvlab/CathAction; licence to confirm on the page |
| cervical_thoracic_intraop | unknown | unknown | rule | not recorded |
| chexpert_plus | agreement | no | rule | Stanford AIMI research use agreement, non-commercial |
| cm_spine_drive_file | unknown | unknown | rule | none stated: the paper's data statement and its repository's README name no licence, and the repository has no licence file (read 2026-10-23) |
| cm_spine_garm | unknown | unknown | rule | not recorded |
| cobra_elekta | non-commercial | no | rule | CC BY-NC 4.0 |
| cobra_embargoed | non-commercial | no | rule | CC BY-NC 4.0 |
| cobra_total | non-commercial | no | rule | CC BY-NC 4.0 |
| cobra_varian | non-commercial | no | rule | CC BY-NC 4.0 |
| coronary_angiography | unknown | unknown | rule | varies by set |
| csxa | open | yes | rule | CC BY 4.0 |
| ct_rate | agreement | no | rule | a data use agreement (non-commercial) |
| ctspine1k_ctpelvic1k_ribfrac | non-commercial | no | rule | CTSpine1K derivatives non-commercial |
| ctspinopelvic1k | non-commercial | no | rule | labels CC BY-NC-SA 4.0; the CT images CC BY 3.0 (TCIA) |
| daradia_vertebroplasty | unknown | unknown | rule | unknown |
| deepfluoro | non-commercial | no | rule | CC BY-NC 4.0 by the H5 release's LICENSE, CC BY-NC-SA 4.0 by its datasheet: non-commercial either way |
| dmx_imaging | unknown | unknown | rule | unknown |
| dysphagiabank | agreement | no | rule | non-commercial, by registration |
| faubel_painsource | unknown | unknown | rule | unknown |
| fluoro_video_clips | unknown | unknown | rule | mixed: CC BY (Bern, PMC), unlicensed re-encodes (YouTube) |
| fluorocap | unknown | unknown | rule | the publishers' (figures) |
| fluorogen_synth_rare | unknown | unknown | rule | the project's own |
| fracatlas | unknown | unknown | rule | CC BY 4.0 (Abedeen 2023); the Hugging Face mirror's page to confirm |
| fraiwan_spine_xray | unknown | unknown | rule | Mendeley Data xkt857dsxk, CC BY 4.0 to confirm on the page |
| geneva_hip | share-alike | yes | rule | CC BY-SA 4.0, as the source's page gives it (read 2026-10-23), which also lists a 'Contract on the use of data' and shows none of its terms |
| guide3d | non-commercial | no | rule | CC BY-NC 4.0 (cc-by-nc-4.0, as the Hugging Face dataset airvlab/guide3d's licence line reads, read 2026-10-22) |
| hf_abdomenatlas2_0_mini | non-commercial | no | rule | CC BY-NC-SA 4.0 |
| huashan_intraop_lumbar | agreement | no | rule | by request |
| idc_cptac_lscc | open | yes | rule | CC BY 4.0 |
| idc_cptac_luad | open | yes | rule | CC BY 4.0 |
| idc_ldct_and_projection_data | open | yes | rule | CC BY 4.0 |
| idc_lidc_idri | open | yes | rule | CC BY 3.0 |
| idc_midrc_ricord_1b | non-commercial | no | rule | CC BY-NC 4.0 |
| idc_nlst | open | yes | rule | CC BY 4.0 |
| idc_nsclc_radiogenomics | open | yes | rule | CC BY 3.0 |
| idc_nsclc_radiomics | non-commercial | no | rule | CC BY-NC 3.0 |
| idc_prostate_anatomical_edge_cases | open | yes | rule | CC BY 4.0 |
| idc_spinal_multiple_myeloma_seg | open | yes | rule | CC BY 4.0 |
| idc_spine_mets_ct_seg | open | yes | rule | CC BY 4.0 |
| ieee_dataport_lateral_236 | agreement | no | rule | not recorded; downloaded under an IEEE DataPort subscription |
| implant_ct_synthetic | unknown | unknown | rule | inherits the source terms |
| ipcai2025_xray_ct | agreement | no | rule | Research-Only Dataset License (as the Zenodo page's licence line reads for version 1.0, published 2025-05-20, read 2026-10-22) |
| isbi2015_cephalograms | unknown | unknown | rule | the ISBI 2015 challenge set; licence and link to confirm |
| jefferson_drg | no-derivatives | no | rule | CC BY (YouTube copy); the article text says CC BY-NC-ND while linking CC BY 4.0 |
| kaggle_fracture_multiregion | unknown | unknown | rule | Kaggle; PDDL in the metadata and ODC-By 1.0 in the description; taken on the owner's yes of 2026-10-22 though the source uploads' origin is unstated |
| kaggle_scoliosis_yolov5 | unknown | unknown | rule | Kaggle; the licence on the page to confirm; provenance unstated, so a relabel of AASCE until the hash check says otherwise |
| konica_ddr | unknown | unknown | rule | unknown |
| kub_stonex | open | yes | owner 2026-10-23 | CC BY 4.0 (figshare 32049369, doi 10.6084/m9.figshare.32049369; the record's licence field, read from the API on 2026-10-21); de-identified per the record, IRB REC-FSIT-2025/No: 12732 of Daffodil International University |
| levelcheck_clinical | unknown | unknown | rule | not shared (Johns Hopkins IRB approval expired) |
| ljubljana_2d3d_gs | no-derivatives | no | rule | CC BY-NC-ND, as the source's page gives it (read 2026-10-23); the user guide that comes with the set says the data are used only under an agreement form between the user and the Laboratory of Imaging Technologies, and never redistributed |
| lumos | non-commercial | no | rule | Zenodo 18173664, open, CC BY-NC 4.0 (read on the record 2026-10-21) |
| maastricht_cervical | agreement | no | rule | available on request under privacy restrictions; a Dutch WMO/GDPR data transfer agreement is expected |
| magic_ct | agreement | no | rule | a data use agreement (non-commercial) |
| mayfield_kyphoplasty | unknown | unknown | rule | unknown |
| mendeley_5jdfdgp762 | unknown | unknown | rule | not recorded |
| mendeley_ddh_hips | unknown | unknown | rule | CC BY 4.0 (to confirm on the page) |
| mimic_cxr | agreement | no | rule | PhysioNet Credentialed Health Data License 1.5.0; credentialed, the agreement signed on the page; opt-in only; about 570 GB |
| mros_lateral_spine | agreement | no | rule | an NIA Outgoing Human Data Transfer Agreement signed by the PI and Wayne State's Signing Official: non-profit research on the approved project only, no redistribution, no re-identification, acknowledgement, 12 months renewable, destruction certified at the end |
| mtfi_lumbar_coupling | unknown | unknown | rule | unknown |
| neurosurgical_focus_video | open | yes | rule | CC BY 4.0 |
| nhanes2_annotated | open | yes | rule | CC BY 4.0 |
| nhanes2_unannotated | open | yes | rule | US government work, public domain (NCHS) |
| nih_chestxray14 | unknown | unknown | rule | NIH Clinical Center, open; the Box page's terms to confirm |
| nitw_2d3d_registration | agreement | no | rule | by request |
| open_i_chest | unknown | unknown | rule | Open-i (NLM), open, no agreement; the FAQ's terms to confirm |
| padchest | agreement | no | rule | BIMCV's PadChest research use agreement, accepted by the owner on 2026-10-22; no redistribution, the link kept inside the organisation |
| pediatric_iri | unknown | unknown | rule | not recorded |
| pengwin_task2_xrays | unknown | unknown | rule | Zenodo 10913195, CC BY to confirm; the challenge's terms at https://pengwin.grand-challenge.org/ |
| pittsburgh_swallow | agreement | no | rule | by request |
| procedure_guide | non-commercial | no | rule | CC BY-NC-SA 4.0 (site) |
| radiopaedia | non-commercial | no | rule | CC BY-NC-SA 3.0 (the site); ML use by application |
| rexgradient_160k | agreement | no | rule | a non-commercial data access and use agreement on the Hugging Face page |
| roboflow_vindr_relabels | agreement | no | rule | Roboflow; the images' redistribution is outside VinDr-SpineXR's DUA |
| rsna_2022_cervical | agreement | no | rule | Kaggle competition rules (non-commercial); the terms for derived labels not recorded |
| rsna_ratic | agreement | no | rule | a data use agreement (non-commercial) |
| rsna_rspect | agreement | no | rule | a data use agreement (non-commercial) |
| scidb_enhance_pet_1_6k | non-commercial | no | rule | CC BY 4.0 (Leipzig, Careggi, UC Davis) and CC BY-NC 4.0 (autoPET, Tuebingen) by site, per the bucket's CT-details.xlsx; the strictest binds the set |
| seattle_science_foundation | unknown | unknown | rule | unknown; embedding disabled |
| sof_lateral_spine | agreement | no | rule | an NIA Outgoing Human Data Transfer Agreement signed by the PI and Wayne State's Signing Official: non-profit research on the approved project only, no redistribution, no re-identification, acknowledgement, 12 months renewable, destruction certified at the end |
| spinal_ai2024 | unknown | unknown | rule | not recorded |
| spinesac | unknown | unknown | rule | none stated |
| stanford_aimi_inspect | agreement | no | rule | a data use agreement (non-commercial) |
| stanford_aimi_merlin | agreement | no | rule | a data use agreement (non-commercial) |
| sx_stitch | unknown | unknown | rule | not recorded |
| totalsegmentator | open | yes | rule | CC BY 4.0 |
| tvgh_as_spine | unknown | unknown | rule | not recorded |
| tvgh_spinexr | unknown | unknown | rule | not recorded |
| vanderbilt_tha_fluoro | agreement | no | rule | not recorded; a data use agreement with Vanderbilt is the route |
| veriserum | agreement | no | rule | In Copyright - Non-Commercial Use Permitted (as the ETH Research Collection record's rights line reads, read 2026-10-22) |
| verse | share-alike | yes | rule | CC BY-SA 4.0 |
| verse_2d_projections | unknown | unknown | rule | Zenodo 8115942, open; licence to confirm on the record (VerSe is CC BY-SA 4.0) |
| vertxnet_nhanes2_labels | unknown | unknown | rule | Zenodo, open; licence to confirm on the record (docs/research/xray-datasets-missing.md) |
| veterinary_pig_levelcheck | unknown | unknown | rule | IEEE DataPort open access |
| vfss2022 | unknown | unknown | rule | TIB, doi:10.57702/w1ye2nim; licence to confirm on the page |
| vindr_cxr | agreement | no | rule | PhysioNet Credentialed Health Data License 1.5.0; credentialed, the agreement signed on the page; opt-in only |
| vindr_pcxr | agreement | no | rule | PhysioNet Restricted Health Data License 1.5.0; the data use agreement signed on the page, no CITI training review; opt-in only |
| vindr_spinexr | agreement | no | rule | PhysioNet Restricted Health Data License 1.5.0, credentialed, the owner's named-person agreement; covered by WSU IRB HPR 2026-330 (29 Sep 2026) |
| zenodo_lumvbcanseg | open | yes | rule | CC BY 4.0 |
| zenodo_medpelvis3d | open | yes | rule | CC BY 4.0 |
| zenodo_tmtv_benchmark | open | yes | rule | CC BY 4.0 |
| zenodo_ts_task_hip_implant | open | yes | rule | CC BY 4.0 |
| zenodo_ts_task_liver_lesions | open | yes | rule | CC BY 4.0 |
| zenodo_ts_task_pleural_effusion | open | yes | rule | CC BY 4.0 |
| zenodo_unitochest | open | yes | rule | CC BY 4.0 |
| zenodo_vsd_fullbody | non-commercial | no | rule | Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Switzerland (CC BY-NC-SA 3.0 CH), the Zenodo record 8270365's licence line, read 2026-10-22 |
