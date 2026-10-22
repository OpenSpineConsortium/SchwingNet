# Sample manifest: the first census run (2026-10-22)

Source: the thread "Census, Any-View table and report fix", 2026-10-22, the gate's status of
20:00 UTC showing logs/SAMPLES-STAGE-REPORT.md of the run under _samples/ stamped 20261021-225857
(plan job 40702274, scan array 40702275 of 64 tasks, the manifest by job 40703320 after the merge
40702276 wrote samples.sqlite and failed in its report, fixed in #114). Aggregates only, as the
report writes them; "unmapped <folder>" is a folder of the data root that no manifest or registry
record names, and "[hidden]" is a source id of 32 characters or more that the gate's own mask takes
for a token. A group is a root with the sources it serves; a group that lists several sources is a
bank or a build tree they share, not a sum of them.


| sources | files | size | images | annotated | unannotated | main formats | manifest says |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| unmapped or_ready | 368455 | 808.3 GB | 66153 | 14361 | 51792 | json 225923, png 60557, txt 32222 |  |
| cobra2026 | 19593 | 718.1 GB | 6920 | 0 | 6920 | other 8423, metaimage 6228, xml 3786 | two_labeller,pseudo |
| abdomenatlas3_mini | 9264 | 531.4 GB | 9262 | 0 | 9262 | nifti-gz 9262, json 1, other 1 | two_labeller |
| unmapped versefusion | 33535 | 383.7 GB | 4325 | 1652 | 2673 | json 12613, npy 10103, nifti-gz 5032 |  |
| tcia_fdg_pet_ct_lesions | 511084 | 366.8 GB | 510182 | 903 | 509279 | dicom 509282, other 901, nifti-gz 900 | two_labeller |
| unmapped multisource_banks | 208029 | 316.0 GB | 52653 | 48838 | 3815 | json 89320, png 52465, npy 35141 |  |
| anomaly_harvest_b | 1063032 | 303.4 GB | 14909 | 6670 | 8239 | nifti-gz 911055, json 81287, other 37159 |  |
| unmapped aws_stoic2021 | 2034 | 246.1 GB | 2000 | 366 | 1634 | metaimage 2000, other 33, json 1 |  |
| fluoro_video_clips | 731573 | 222.4 GB | 726614 | 36060 | 690554 | png 726329, json 1496, csv 1328 |  |
| idc_tier1 | 3509 | 215.7 GB | 2669 | 2620 | 49 | nifti-gz 3507, json 1, other 1 | two_labeller |
| unmapped fluorocap | 379127 | 203.9 GB | 363067 | 40010 | 323057 | png 338361, jpeg 24700, pdf 9758 |  |
| fluorocap | 372577 | 201.9 GB | 361567 | 38653 | 322914 | png 336861, jpeg 24700, pdf 9758 | pseudo |
| unmapped rsna_2022_cspine | 4 | 189.4 GB | 0 | 0 | 0 | zip 2, other 1, csv 1 |  |
| unmapped ctspinopelvic1k | 12685 | 188.8 GB | 2052 | 1006 | 1046 | npy 4598, json 4379, nifti-gz 2438 |  |
| panorama | 2240 | 181.1 GB | 2238 | 2161 | 77 | nifti-gz 2238, json 1, other 1 | two_labeller |
| ctspine1k | 2020 | 151.2 GB | 1005 | 1005 | 0 | nifti-gz 2010, json 2, other 2 | expert |
| ribfrac | 750 | 146.1 GB | 660 | 660 | 0 | nifti-gz 732, zip 12, csv 3 | release_labels,expert,two_labeller |
| unmapped nhanes2_cdc_films | 49548 | 128.9 GB | 17073 | 17073 | 0 | tiff 17073, json 16237, npy 16234 |  |
| amos22 | 3067 | 95.6 GB | 2824 | 802 | 2022 | nifti-gz 2824, other 239, json 2 | two_labeller |
| unmapped polypose | 118395 | 81.8 GB | 1328 | 228 | 1100 | other 107947, symlink 3937, txt 1643 |  |
| unmapped ctsp_april | 1623 | 80.9 GB | 351 | 351 | 0 | nifti-gz 1504, other 97, json 14 |  |
| pengwin2026 | 1022 | 77.8 GB | 680 | 203 | 477 | metaimage 680, nifti-gz 340, json 1 | two_labeller |
| carmlspine,carmlspine_sweeps | 274849 | 74.8 GB | 128060 | 297 | 127763 | json 143992, png 125525, nifti-gz 2981 | two_labeller |
| unmapped vindr_spinexr | 47641 | 70.9 GB | 10466 | 2811 | 7655 | json 23816, npy 13346, png 10466 |  |
| kidney_thoraxabdomen | 432 | 70.7 GB | 430 | 215 | 215 | metaimage 215, nifti-gz 215, json 1 | two_labeller |
| nlst_pilot | 89865 | 68.5 GB | 89863 | 16636 | 73227 | dicom 89363, nifti-gz 500, json 1 | two_labeller |
| deepfluoro_vendor | 94626 | 67.7 GB | 94602 | 36 | 94566 | dicom 91359, jpeg 3243, other 16 | none |
| idc_covid_19_ny_sbu | 122272 | 60.2 GB | 122272 | 22014 | 100258 | dicom 122272 | two_labeller |
| idc_psma_pet_ct_lesions | 119632 | 58.8 GB | 119632 | 21535 | 98097 | dicom 119632 | two_labeller |
| unmapped spine_detector_corpus | 530722 | 55.8 GB | 268441 | 264883 | 3558 | txt 255883, jpeg 232470, png 35971 |  |
| idc_pediatric_ct_seg | 108019 | 53.0 GB | 0 | 0 | 0 | dicom 108019 | two_labeller |
| unmapped cathaction | 24 | 52.3 GB | 0 | 0 | 0 | other 16, zip 4, json 3 |  |
| unmapped kub_stonex | 9648 | 51.5 GB | 6810 | 4026 | 2784 | png 9630, pdf 6, csv 6 |  |
| unmapped totalsegmentator_v300 | 232276 | 48.8 GB | 1936 | 0 | 1936 | nifti-gz 228799, json 1736, npy 1735 |  |
| waw_tace | 856 | 43.9 GB | 854 | 228 | 626 | nifti-gz 854, json 1, other 1 | two_labeller |
| unmapped nih_chestxray14 | 14 | 42.0 GB | 0 | 0 | 0 | gzip 12, json 1, other 1 |  |
| unmapped totalsegmentator_v201 | 153322 | 39.6 GB | 1631 | 0 | 1631 | nifti-gz 146936, json 2824, npy 2330 |  |
| vindr_spinexr | 10475 | 36.0 GB | 10466 | 10466 | 0 | dicom 10466, html 4, txt 2 | release_labels,pseudo |
| deepfluoro,deepfluoro_vendor | 19 | 35.6 GB | 0 | 0 | 0 | other 9, zip 8, pdf 1 | none |
| cobra2026,cobra_elekta,cobra_total,cobra_varian | 11062 | 35.0 GB | 1337 | 695 | 642 | nifti-gz 5624, json 2556, other 1237 | two_labeller,pseudo |
| idc_eay131 | 65202 | 34.7 GB | 65202 | 11758 | 53444 | dicom 65202 | two_labeller |
| unmapped buu_lspine_3600 | 46723 | 32.8 GB | 19754 | 14551 | 5203 | txt 12550, png 12550, csv 7206 |  |
| unmapped pengwin_task2_xrays | 6 | 32.6 GB | 0 | 0 | 0 | json 2, other 2, zip 1 |  |
| curvas | 284 | 27.9 GB | 70 | 0 | 70 | nifti-gz 280, other 2, zip 1 | two_labeller |
| idc_lung_pet_ct_dx | 56646 | 27.8 GB | 56646 | 10324 | 46322 | dicom 56646 | two_labeller |
| idc_mediastinal_lymph_node_seg | 48770 | 23.9 GB | 48770 | 8955 | 39815 | dicom 48770 | two_labeller |
| aasce2019_boostnet,buu_lspine_2000,buu_lspine_3600,buu_lspine_v1_smoke,csxa_cervical_xray_atlas,[hidden],mendeley_5jdfdgp762,nhanes2_cdc_films,nhanes2_zenodo_landmarks,spinal_ai2024,spine_detector_corpus,vindr_spinexr | 8812 | 23.8 GB | 5756 | 788 | 4968 | png 3438, jpeg 3347, other 858 | pseudo; release_labels; release_labels,pseudo |
| deep_psma | 1507 | 22.6 GB | 1100 | 0 | 1100 | nifti-gz 800, jpeg 300, other 206 | two_labeller |
| carmlspine | 59609 | 21.7 GB | 59609 | 8180 | 51429 | dicom 59609 | two_labeller |
| quadra_hc | 966 | 19.0 GB | 192 | 48 | 144 | nifti-gz 960, xlsx 4, json 1 | two_labeller |
| barts_crl | 222 | 18.9 GB | 220 | 212 | 8 | nifti-gz 220, json 1, other 1 | two_labeller |
| dysphagiabank | 95 | 18.2 GB | 0 | 0 | 0 | mp4 87, other 3, txt 2 |  |
| unmapped idc_spine_mets_ct_seg | 35531 | 17.4 GB | 0 | 0 | 0 | dicom 35527, other 2, json 1 |  |
| idc_rider_lung_pet_ct | 35229 | 17.3 GB | 35229 | 6295 | 28934 | dicom 35229 | two_labeller |
| unmapped devcorpus | 99553 | 17.0 GB | 40529 | 39506 | 1023 | jpeg 40529, txt 39684, json 9555 |  |
| curvas_pdacvi | 875 | 15.7 GB | 109 | 0 | 109 | nifti-gz 873, json 1, other 1 | two_labeller |
| aortaseg60 | 310 | 14.8 GB | 60 | 55 | 5 | other 189, nifti-gz 120, json 1 | two_labeller |
| idc_acrin_nsclc_fdg_pet | 29541 | 14.7 GB | 29541 | 5239 | 24302 | dicom 29541 | two_labeller |
| ctpelvic1k | 180 | 13.8 GB | 178 | 163 | 15 | nifti-gz 178, json 1, other 1 | expert,two_labeller |
| unmapped fig6 | 108412 | 13.0 GB | 14904 | 5291 | 9613 | json 54164, symlink 22135, txt 16963 |  |
| unmapped ctspinopelvic1k_build_tree | 3340 | 9.9 GB | 0 | 0 | 0 | nifti-gz 2022, json 1262, other 40 |  |
| idc_cptac_ucec | 19942 | 9.8 GB | 19942 | 3670 | 16272 | dicom 19942 | two_labeller |
| idc_tcga_blca | 19484 | 9.6 GB | 19484 | 3479 | 16005 | dicom 19484 | two_labeller |
| idc_cptac_pda | 18952 | 9.4 GB | 18952 | 3369 | 15583 | dicom 18952 | two_labeller |
| idc_cmb_lca | 18851 | 9.3 GB | 18851 | 3365 | 15486 | dicom 18851 | two_labeller |
| idc_tcga_kirc | 18869 | 9.3 GB | 18869 | 3430 | 15439 | dicom 18869 | two_labeller |
| buu_lspine_2000,xrspinopelvic1k | 20269 | 9.0 GB | 230 | 13 | 217 | txt 8439, symlink 8428, other 2817 | pseudo; release_labels |
| unmapped spineps | 41571 | 8.2 GB | 0 | 0 | 0 | json 15507, nifti-gz 14527, symlink 11412 |  |
| unmapped fluorogen_synthetic | 30035 | 7.9 GB | 3001 | 1628 | 1373 | json 13500, npy 13495, png 3001 |  |
| unmapped buu_lspine_2000 | 8002 | 7.5 GB | 4000 | 2000 | 2000 | jpeg 4000, csv 4000, zip 1 |  |
| idc_cptac_ccrcc | 13242 | 7.4 GB | 13242 | 2394 | 10848 | dicom 13242 | two_labeller |
| ctpelvic1k,ctspine1k,ctspinopelvic1k_build_tree,tcia_ct_colonography | 4541 | 7.2 GB | 175 | 3 | 172 | other 3205, nifti-gz 821, png 172 | expert; expert,two_labeller; none; release_labels,pseudo,reviewed,expert |
| idc_cptac_stad | 13485 | 6.6 GB | 13485 | 2455 | 11030 | dicom 13485 | two_labeller |
| idc_midrc_ricord_1a | 14964 | 6.2 GB | 14964 | 2639 | 12325 | dicom 14964 | two_labeller |
| unmapped ipcai2025_xray_ct | 4 | 6.2 GB | 0 | 0 | 0 | json 2, zip 1, other 1 |  |
| csi2014 | 42 | 6.2 GB | 40 | 20 | 20 | metaimage 20, nifti-gz 20, json 1 | two_labeller |
| idc_tcga_stad | 12189 | 6.0 GB | 12189 | 2197 | 9992 | dicom 12189 | two_labeller |
| unmapped aariz | 4005 | 5.9 GB | 1000 | 1000 | 0 | json 3001, jpeg 471, png 370 |  |
| idc_colorectal_liver_metastases | 11967 | 5.9 GB | 11967 | 2156 | 9811 | dicom 11967 | two_labeller |
| idc_ctpred_sunitinib_pannet | 11689 | 5.7 GB | 11689 | 2132 | 9557 | dicom 11689 | two_labeller |
| unmapped [hidden] | 711 | 5.7 GB | 236 | 0 | 236 | json 238, jpeg 236, npy 236 |  |
| unmapped rare_class | 44243 | 5.4 GB | 12225 | 11694 | 531 | json 15974, npy 15713, png 12432 |  |
| idc_covid_19_ar | 10729 | 5.3 GB | 10729 | 1917 | 8812 | dicom 10729 | two_labeller |
| idc_varepop_apollo | 10376 | 5.1 GB | 10376 | 1916 | 8460 | dicom 10376 | two_labeller |
| idc_cmb_crc | 10256 | 5.0 GB | 10256 | 1802 | 8454 | dicom 10256 | two_labeller |
| deepfluoro | 76 | 4.9 GB | 0 | 0 | 0 | other 48, zip 14, gzip 12 |  |
| deepfluoro_h5 | 76 | 4.9 GB | 0 | 0 | 0 | other 48, zip 14, gzip 12 | release_labels,two_labeller |
| idc_hcc_tace_seg | 9717 | 4.8 GB | 9717 | 1825 | 7892 | dicom 9717 | two_labeller |
| idc_tcga_lihc | 9429 | 4.6 GB | 9429 | 1667 | 7762 | dicom 9429 | two_labeller |
| unmapped xrspinopelvic1k | 32097 | 4.3 GB | 6421 | 5 | 6416 | png 12837, npy 12824, json 6416 |  |
| idc_pelvic_reference_data | 8540 | 4.2 GB | 8540 | 1554 | 6986 | dicom 8540 | two_labeller |
| bern_myelography | 174 | 4.1 GB | 49 | 17 | 32 | other 57, mp4 54, jpeg 49 |  |
| unmapped verse_2d_projections | 16 | 4.1 GB | 0 | 0 | 0 | zip 12, json 2, other 1 |  |
| spinesac | 5566 | 4.0 GB | 3674 | 385 | 3289 | dicom 2763, txt 1155, png 872 | release_labels |
| idc_anti_pd_1_lung | 8055 | 4.0 GB | 8055 | 1437 | 6618 | dicom 8055 | two_labeller |
| idc_cptac_cm | 8020 | 3.9 GB | 8020 | 1484 | 6536 | dicom 8020 | two_labeller |
| idc_tcga_ucec | 7900 | 3.9 GB | 7900 | 1443 | 6457 | dicom 7900 | two_labeller |
| unmapped csxa_cervical_xray_atlas | 9945 | 3.4 GB | 4963 | 4962 | 1 | json 4966, png 4959, other 8 |  |
| idc_adrenal_acc_ki67_seg | 6729 | 3.3 GB | 0 | 0 | 0 | dicom 6729 | two_labeller |
| unmapped spinal_ai2024 | 36761 | 3.1 GB | 20001 | 10346 | 9655 | jpeg 20000, json 8360, npy 8358 |  |
| unmapped nhanes2_zenodo_landmarks | 1106 | 3.1 GB | 0 | 0 | 0 | json 545, npy 543, npz 16 |  |
| unmapped realxray | 134806 | 3.1 GB | 23582 | 17949 | 5633 | symlink 67981, json 24025, png 23761 |  |
| idc_cptac_sar | 4971 | 2.9 GB | 4971 | 898 | 4073 | dicom 4971 | two_labeller |
| implant_ct_synthetic | 74 | 2.8 GB | 24 | 0 | 24 | json 26, nifti-gz 24, symlink 24 | pseudo |
| idc_pancreatic_ct_cbct_seg | 5614 | 2.8 GB | 5614 | 1010 | 4604 | dicom 5614 | two_labeller |
| idc_acrin_flt_breast | 5341 | 2.6 GB | 5341 | 932 | 4409 | dicom 5341 | two_labeller |
| idc_cmb_brca | 4909 | 2.4 GB | 4909 | 964 | 3945 | dicom 4909 | two_labeller |
| idc_tcga_esca | 4738 | 2.3 GB | 4738 | 878 | 3860 | dicom 4738 | two_labeller |
| idc_tcga_ov | 4687 | 2.3 GB | 4687 | 879 | 3808 | dicom 4687 | two_labeller |
| idc_cmb_mml | 4407 | 2.2 GB | 4407 | 768 | 3639 | dicom 4407 | two_labeller |
| idc_cmb_mel | 4074 | 2.0 GB | 4074 | 706 | 3368 | dicom 4074 | two_labeller |
| [hidden] | 3397 | 1.7 GB | 3397 | 656 | 2741 | dicom 3397 | two_labeller |
| unmapped open_i_chest | 4 | 1.3 GB | 0 | 0 | 0 | gzip 2, json 1, other 1 |  |
| unmapped mendeley_5jdfdgp762 | 4003 | 1.2 GB | 717 | 698 | 19 | symlink 1413, json 1070, jpeg 714 |  |
| geneva_hip | 485 | 1.0 GB | 256 | 234 | 22 | other 178, metaimage 137, tiff 116 | release_labels,two_labeller |
| idc_cmb_ov | 1983 | 998.2 MB | 1983 | 382 | 1601 | dicom 1983 | two_labeller |
| aasce | 2612 | 780.5 MB | 903 | 609 | 294 | symlink 965, jpeg 903, mat 611 |  |
| unmapped aasce2019_boostnet | 916 | 714.9 MB | 0 | 0 | 0 | json 458, npy 457, npz 1 |  |
| unmapped devcorpus_arc | 13075 | 687.9 MB | 6558 | 0 | 6558 | jpeg 6517, json 6510, png 41 |  |
| unmapped ctsp0533_repair | 619 | 576.2 MB | 579 | 1 | 578 | dicom 577, other 18, symlink 10 |  |
| verse19_20,versefusion | 288 | 460.1 MB | 0 | 0 | 0 | other 276, text 6, csv 2 | expert; expert,pseudo |
| unmapped realxray_work | 248 | 309.8 MB | 98 | 0 | 98 | nifti-gz 132, npz 38, json 24 |  |
| ljubljana_2d3d_gs | 181 | 292.3 MB | 18 | 0 | 18 | txt 76, other 64, png 18 | release_labels |
| unmapped kaggle_scoliosis_yolov5 | 2 | 225.2 MB | 0 | 0 | 0 | zip 1, json 1 |  |
| carmlspine_sweeps | 907 | 132.9 MB | 302 | 301 | 1 | json 303, png 302, txt 301 |  |
| aasce2019_boostnet | 1853 | 120.3 MB | 634 | 608 | 26 | json 611, txt 608, png 608 | release_labels |
| unmapped gallery | 472 | 100.9 MB | 404 | 8 | 396 | png 404, npz 62, json 5 |  |
| unmapped figure1 | 94 | 26.1 MB | 74 | 58 | 16 | png 74, npz 16, json 4 |  |
| unmapped tcia_ct_colonography | 3 | 11.7 MB | 0 | 0 | 0 | pickle 1, json 1, txt 1 |  |
| unmapped inventory | 34 | 7.2 MB | 0 | 0 | 0 | other 9, png 8, txt 6 |  |
| unmapped vindr | 3 | 1.5 MB | 0 | 0 | 0 | json 1, other 1, txt 1 |  |
| unmapped d815_repair | 11 | 1003.5 KB | 0 | 0 | 0 | other 8, json 3 |  |
| unmapped outline_conv | 486 | 73.4 KB | 0 | 0 | 0 | txt 243, symlink 243 |  |
| unmapped fracatlas | 15 | 32.1 KB | 0 | 0 | 0 | other 11, json 3, text 1 |  |
| unmapped buu_lspine_v1_smoke | 77 | 6.9 KB | 0 | 0 | 0 | symlink 77 |  |
| unmapped validation_ts | 70 | 4.2 KB | 0 | 0 | 0 | symlink 70 |  |
| unmapped vindr_pcxr | 1 | 412 B | 0 | 0 | 0 | json 1 |  |
| ctspinopelvic1k,mendeley_5jdfdgp762,ribfrac,rsna_2022_cspine,totalsegmentator_v201,totalsegmentator_v300 | 6 | 401 B | 0 | 0 | 0 | symlink 6 | expert,pseudo,reviewed; pseudo,reviewed; release_labels; release_labels,expert,two_labeller |
| unmapped canine_thoracic_vhs | 1 | 243 B | 0 | 0 | 0 | json 1 |  |
| unmapped fraiwan_spine_xray | 1 | 241 B | 0 | 0 | 0 | json 1 |  |
