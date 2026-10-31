# Whole-spine CT online: what the public sites hold against what the grid holds

Source: the thread "Catalogue online whole-spine CT data" of the symphony project, 2026-10-31, the owner's ask of 00:55 UTC ("start catalagoing what is available on the internet at thsoe sites"), scoped by the coordinator to CT and PET/CT whose field shows C2 to the sacrum, with counts, sizes, licences, access and per-person covariates, set against the grid's holdings. Cataloguing only: nothing was downloaded but IDC's public index files (a few hundred MB of parquet into the thread's container). Confidential, like the rest of SchwingNet.

## 1. Answer

Most of what the open archives hold with a whole-spine field is already on the grid. Of the 2,852 IDC persons whose CT reaches 60 cm or more, 2,195 are in collections the grid holds (FDG-PET-CT-Lesions, PSMA-PET-CT-Lesions, ACRIN-NSCLC-FDG-PET and 32 more); the rest, 657 persons in about 155 GB, sit in 28 IDC collections the data platform planned or excluded, and by the held collections' yield perhaps 200 to 250 of them would pass rule 3. Outside IDC, three sources are worth more than all of that:

1. NMDID, the New Mexico Decedent Image Database: about 15,000 whole-body post-mortem CTs (1 mm, 2010 to 2017, over 50 TB) with about 60 per-person fields, living height and weight, age, sex, ancestry, cause of death, implants and bone density among them. Free, by registration with an institutional address and a research request a committee reviews. The data platform excluded it for a DUA that forbids derivative works (excluded_nmdid in data/reproduce/sources.json); the owner's word of 2026-10-31 that licences do not matter reopens it. It is the only source here with height and weight for every person and the only large normal-anatomy one.
2. autoPET's longitudinal CT (Task 2 of autoPET IV and V): 300 melanoma patients from Tuebingen, a baseline and a follow-up CT each, skull base to mid-femur, 54 GB of NIfTI on fdat (doi:10.57754/FDAT.qwsry-7t837). Not in the records. Skull base to mid-femur should hold C2's foot and the sacrum; whether its persons overlap FDG-PET-CT-Lesions, also Tuebingen melanoma, is not stated and must be checked by person before any split.
3. The two gated parts of CADS (hf_cads_unique): CT-TRI, 586 trauma CTs in 83.4 GB, and VISCERAL's whole-body sets, 167 CTs in 39.9 GB, by registration on Hugging Face.

## 2. How IDC was counted

IDC v25's own index (the idc-index package 0.13.4, its index, ct_index and volume_geometry_index tables, read 2026-10-31) gives every CT series' slice count, spacing and orientation. A series counted when IDC calls it a regularly spaced 3-D volume, axial, not a localizer, with slices 5 mm apart or closer; its field is (slices - 1) times the spacing. A person counts when any series reaches 60 cm, or 70 cm. C2's foot to the sacrum's top is about 55 to 60 cm in an adult, so 60 cm is a necessary length, not proof: a 70 cm chest-abdomen-pelvis that starts at the lung apex misses C2.

The calibration is the census (data/gold3-ct/members.json, census.gold4, job 40870542): the 39 IDC collections the grid holds have 873 persons at 70 cm or more by this count and 1,297 at 60 cm, and the census admitted 439 IDC persons as gold 4 by rule 3 (with 4 border cases) from the 2,950 IDC masks it read. So roughly half of the 70 cm persons, or a third of the 60 cm persons, pass, with the caveat that the census read masks only for the rows the harvest chose.

Per collection, idc-candidates.csv beside this file gives: the grid's record of it (on_disk, planned, excluded, or not in records), persons at 60 and 70 cm, studies at 60 cm, the GB of the longest such series per study (what one fetch would take), the median field, whether the collection has PET, its licence, the share of series with age and sex in the DICOM header, which covariates IDC's clinical tables carry (height, weight, BMI, age, sex), and the main scanner makers.

## 3. IDC collections not on the grid with a whole-spine field

From idc-candidates.csv, the ones worth a fetch, persons at 60 cm (at 70 cm), GB:

| Collection | Record | Persons | GB | PET | Licence | Covariates |
|---|---|---|---|---|---|---|
| nsclc_radiogenomics | planned | 196 (192) | 28.3 | yes | CC BY 3.0 | age, sex, weight |
| ct_lymph_nodes | excluded | 156 (36) | 51.2 | no | CC BY 3.0 | DICOM age, sex |
| soft_tissue_sarcoma | excluded | 49 (49) | 6.9 | yes | CC BY 3.0 | age, sex |
| tcga_lusc and tcga_luad | excluded | 42 (39) | 6.6 | yes | CC BY 3.0 | height, weight, BMI, age, sex |
| nsclc_radiomics_genomics | excluded | 31 (31) | 3.6 | no | CC BY-NC 3.0 | age, sex |
| spinal_multiple_myeloma_seg | planned | 26 (0) | 15.7 | no | CC BY 4.0 | DICOM age, sex |
| cc_tumor_heterogeneity | excluded | 22 (22) | 11.2 | yes | CC BY 4.0 | DICOM age, sex |
| spine_mets_ct_seg | planned | 22 (10) | 5.9 | no | CC BY 4.0 | height, weight, BMI, age, sex |
| nsclc_radiomics_interobserver1 | excluded | 22 (22) | 2.0 | no | CC BY-NC 3.0 | age, sex; likely the same persons as nsclc_radiomics |
| c4kc_kits | excluded | 17 (7) | 2.1 | no | CC BY 3.0 | age, sex |
| cptac_luad, cptac_lscc | planned | 24 (20) | 7.5 | yes | CC BY 4.0 | height, weight, BMI, age, sex |

The rest are under ten persons each. Every IDC collection is open, no registration, fetched with s5cmd from IDC's public buckets (the route data/reproduce already uses). spinal_multiple_myeloma_seg's long fields are lumbar-centred (LSPINE) and probably miss C2. IDC lists FDG-PET-CT-Lesions as CC BY 4.0 while fdat's NIfTI copy says CC BY-NC 4.0.

Height and weight per person: the clinical tables of the ACRIN, TCGA and CPTAC collections carry them (the csv's clinical_table_covariates); elsewhere the DICOM tags PatientSize and PatientWeight may hold them, which idc-index does not carry and IDC's BigQuery table dicom_all does (a query needs a Google Cloud billing project, which this container has not).

IDC also carries TotalSegmentator's segmentations of NLST (26,194 persons, CC BY 4.0, doi:10.5281/zenodo.8347011), chest only, so no sacrum.

## 4. Other sites

Checked 2026-10-31 through each site's page where the container reached it; TCIA's own site and API, NMDID's site and PMC refused this container, so their lines come from search results and the records, and TCIA's limited-access collections, which IDC does not mirror, are not counted here.

| Source | What | Whole spine | Size | Access | Licence | Covariates | On the grid |
|---|---|---|---|---|---|---|---|
| NMDID (nmdid.unm.edu) | about 15,000 post-mortem whole-body CTs, 1 mm, with scouts | yes, whole body | over 50 TB, DICOM | registration with an institutional e-mail, then a research request a committee reviews | custom DUA (excluded_nmdid says it forbids derivative works) | about 60 fields: age, sex, ancestry, living height and weight, cadaver weight and length, cause of death, implants, bone density, scan settings | no |
| autoPET longitudinal CT (fdat, doi:10.57754/FDAT.qwsry-7t837) | 300 melanoma patients, baseline and follow-up CT | skull base to mid-femur | 54 GB, NIfTI | open | not stated on the challenge page | not stated | no |
| CADS gated parts (Hugging Face) | CT-TRI 586 trauma CTs; VISCERAL 167 | trauma CT often whole-body; VISCERAL whole-body by design | 83.4 GB and 39.9 GB | registration | per component | not recorded | no (gated) |
| AbdomenAtlas 2.0 Mini (hf_abdomenatlas2_0_mini) | 10,135 CTs | mostly abdomen; the 3.0 Mini held gave 641 of 5,771 | not recorded | open | CC BY-NC-SA 4.0 | not recorded | planned |
| ENHANCE.PET 1.6k (doi:10.57760/sciencedb.34150) | 1,683 FDG-PET/CT studies | whole and total body | not recorded | open | CC BY 4.0 and CC BY-NC 4.0 by site | age, sex per study; the gold tier's anchor | held (1,558 gold 3) |
| FDG-PET-CT-Lesions (TCIA doi:10.7937/gkr0-xv29; fdat) | 1,014 studies, 900 persons | skull base to mid-thigh | 330.6 GB zip on fdat | open | CC BY-NC 4.0 on fdat | age, sex, diagnosis (fdg_metadata.csv) | held |
| PSMA-PET-CT-Lesions (autoPET III) | 597 studies, 378 persons | skull base to mid-thigh | 95.7 GB in IDC | open | CC BY 4.0 | DICOM age, sex | held |
| DeepPSMA (doi:10.5281/zenodo.15281784) | 100 patients, PSMA and FDG | mostly vertex to thighs | not recorded | open | not stated | not stated | held (42 gold 4) |
| QUADRA_HC (Zenodo 16364694) | 48 healthy controls, test and retest | total body | 20.2 GB | open | CC BY 4.0 | not on the page | held (47 gold 4) |
| VSDFullBody (Zenodo 8270365) | post-mortem whole-body CT, Bern and Zurich | yes | not recorded | open | CC BY-NC-SA 3.0 CH | not listed | held |
| SAROS (Sci Data 2024, doi:10.1038/s41597-024-03337-6) | sparse region and body-part labels on about 900 TCIA whole-body CTs | yes | labels only | open | not read (PMC refused) | from the TCIA collections | images mostly in held IDC collections |
| PETWB-REP (Shanghai) | 490 patients, FDG-PET/CT and reports | whole body | not stated | not stated | not stated | "structured clinical metadata", not listed | no |
| AutoPET-RG-Lym (Hugging Face jwppku) | lymphoma PET/CT with report text, built on autoPET | whole body | not read | not read | not read | not read | its images are FDG-PET-CT-Lesions, held |

Not whole spine, so left out: CT-RATE, INSPECT, LIDC and NLST (chest), Merlin, AMOS, RSNA abdominal trauma, KiTS, FLARE and the other abdomen sets (no C2), RSNA cervical (no sacrum), HECKTOR and the head-and-neck PET/CT sets.

## 5. The order to fetch, the owner's word of 2026-10-31 01:10 UTC

The owner: "start with NMDID's metadata file, but i want to proceed in order of decreasing size then starting with NMDID after I give you the okay". So the metadata comes first, and the image fetches go largest first, each only after his okay:

1. NMDID's metadata CSV, now (registration only, no image): the per-person covariates for all 15,000, which also let the research request name its inclusion rule. The site refuses this container and wants an institutional log-in, so the owner registers and downloads it; nmdid-request.md beside this file holds the steps and a draft of the research request.
2. NMDID's images, over 50 TB, after the owner's okay and the committee's approval, to the grid under the size rule, a few TB at a time.
3. The IDC remainder of section 3, about 155 GB, through the existing reacquire route.
4. CADS's CT-TRI and VISCERAL, 123 GB, after registration.
5. autoPET longitudinal CT, 54 GB, after a person-overlap check against FDG-PET-CT-Lesions.

Nothing above has been fetched.
