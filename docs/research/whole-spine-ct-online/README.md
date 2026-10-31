# Whole-spine CT online: what the public sites hold against what the grid holds

Source: the thread "Catalogue online whole-spine CT data" of the symphony project, 2026-10-31, the owner's ask of 00:55 UTC ("start catalagoing what is available on the internet at thsoe sites"), scoped by the coordinator to CT and PET/CT whose field shows C2 to the sacrum, with counts, sizes, licences, access and per-person covariates, set against the grid's holdings. Cataloguing only: nothing was downloaded but IDC's public index files (a few hundred MB of parquet into the thread's container) and, in the recheck of 01:15 UTC, TCIA's and NBIA's public listings and NMDID's public documentation PDFs. Confidential, like the rest of SchwingNet.

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

Checked 2026-10-31 through each site's page where the container reached it. The first pass could not reach TCIA, NMDID or PMC; the recheck of 01:15 UTC, with the container's full internet access, read TCIA and NMDID directly (sections 4a and 4b), and the NMDID line below is corrected from its own pages.

| Source | What | Whole spine | Size | Access | Licence | Covariates | On the grid |
|---|---|---|---|---|---|---|---|
| NMDID (nmdid.unm.edu) | over 15,000 post-mortem whole-body CTs, deaths 2010 to 2017, about 10,000 images each, 1 mm at 0.5 mm | yes, but for adults over two acquisitions (section 4b) | over 50 TB, 150 million DICOM images | registration with an institutional e-mail, then a research request a committee reviews | custom DUA (excluded_nmdid says it forbids derivative works) | about 60 fields: age, sex, ancestry, living height and weight, cadaver weight and length, cause of death, implants, bone density, scan settings | no |
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

## 4a. TCIA collections IDC does not mirror

Read 2026-10-31 from TCIA's own collection and download API (www.cancerimagingarchive.net/api/v1/collections and /downloads, 240 collections and 888 download records) and, for the collections NBIA serves, from NBIA's v2 getSeries under the public guest account (nbia_guest, no log-in of the owner's), set against IDC v25's 179 collections. 150 of TCIA's 240 are in IDC; of the other 90, 34 hold CT or PET radiology. tcia-not-in-idc.csv beside this file lists all 34 with persons, image size, licence, access route, a judgement of whether the field reaches C2 to the sacrum and the evidence for it, and the covariates the page names. None of them is in the grid's records.

The field could not be measured as section 2 measured IDC: TCIA serves the series list of a restricted collection to nobody without its agreement, and for the eleven NCTN/NCORP trial collections the guest account sees only the public RTSTRUCT annotations, not the images. So the judgement comes from the collection pages and, for the trials, from the body parts the annotations name. Worth a request, in order of what the evidence shows:

| Collection | Persons (whole-spine field) | GB | Access | Covariates |
|---|---|---|---|---|
| Healthy-Total-Body-CTs | 30 (30), healthy adults, uEXPLORER total-body CT at 3 or 6 timepoints | 59.0 | TCIA Restricted | age, sex, height, weight, BMI (public) |
| ACRIN-HNSCC-FDG-PET-CT | 260 (about 188 had a whole-body scan, by the page's counts) | 147.8 | TCIA Restricted | age, sex, BMI, public clinical files |
| HNSCC (MD Anderson) | 627 (up to 215, the Head-Neck-CT-Atlas cohort with whole-body PET-CT or abdominal CT) | 309.8 | TCIA Restricted | age, sex; body composition before and after radiotherapy |
| AHOD0831 (pediatric Hodgkin) | 165 (FDG-PET staging, likely most) | 450.2 | NCTN/NCORP Data Archive | age, sex; children, mean age 14 |
| CALGB50303 (DLBCL) | 155 (CT chest, abdomen, pelvis for all, plus PET) | 138.8 | NCTN/NCORP Data Archive | age, sex |
| Anti-PD-1_MELANOMA | 47 (melanoma PET/CT, field not stated) | 98.4 | TCIA Restricted | not stated |
| Head-Neck-PET-CT, Head-Neck Cetuximab | 298 and 111 (FDG-PET/CT, field not stated) | 72.5 and 52.4 | TCIA Restricted | age, sex (Head-Neck-PET-CT) |
| S0819 (stage IV lung) | 1,299 (a minority: annotations reach the pelvis in 80 persons) | 1,820 | NCTN/NCORP Data Archive, with a collaborative agreement | age, sex |
| CT-ORG | 140 (about 9, the CTs of PET-CT exams) | 16.9 | open, CC BY 3.0 | not stated |

The rest of the 34 are brain, head-and-neck radiotherapy CT (RADCURE's 3,346 persons among them: no sacrum), chest, abdomen-only pediatric trials (AREN0532, 0533, 0534, AHEP0731) or MIDI-B, which re-packs other TCIA collections with inserted fake identifiers.

Access: a TCIA Restricted collection needs a TCIA account and the TCIA Restricted License Agreement signed by the owner and his institution, sent to TCIA's help desk, then the NBIA Data Retriever; one agreement covers every restricted collection. The NCTN/NCORP trials are released by NCI's NCTN/NCORP Data Archive on a data request, S0819 and A091105 only with a collaborative agreement. Taking the counts at face value, the restricted and trial collections add perhaps 400 to 700 persons with a whole-spine field in about 1.3 TB, S0819 aside; Healthy-Total-Body-CTs is the only normal-anatomy set and, with NMDID, the only one with height and weight for every person.

## 4b. NMDID, read from its own pages

nmdid.unm.edu answers the container now. The metadata CSV cannot be fetched without an account: the site's steps are register, log in, search, add records to a cart and "Download Metadata", each search returning at most 1,000 records. Registration accepts the Database Access, Sharing and Use Agreement on the registrant's behalf (one year, research or education only, no derivative works, no redistribution, data destroyed or returned on request, New Mexico law), so it is the owner's to do, and this thread did not register. What the public pages give, read 2026-10-31:

- The data dictionary (nmdid.unm.edu/docs/data_dictionary_20240606.pdf): sex, gender, race, ethnicity, age in years and months, living height (cm) and weight (kg), cadaver length and weight, birth weight, scoliosis, congenital malformations of the spine (ICD-10 Q05, Q06, Q67, Q76, Q77), surgery, implants, cancer, radiation therapy, bone density, cause and manner of death, decomposition score, the CT protocol and the time from death to scan, among about 60 fields.
- The CT protocol (docs/CT_OMI_protocol.pdf): an adult (about age 8 and older) is scanned in three acquisitions, head, neck and upper extremities from the vertex to the fingertips with the arms crossed over the abdomen, then the torso from above the clavicles through the ischial tuberosities with the arms lifted, then the lower extremities; a decomposed body splits at the carina and the shoulders. A child under 36 inches is one acquisition, vertex to toes, and a larger child two. Each is reconstructed at 1 mm with 0.5 mm spacing and at 3 mm, in bone and soft-tissue kernels, 512 by 512, in-plane pixels of 0.8 to 1.2 mm.

So for most adults C2 lies in the head-and-neck series and the sacrum in the torso series, taken after the arms were moved: rule 3 holds per person only once the two series are joined, which needs the overlap from the clavicles down to be registered (the head-and-neck series reaching the fingertips, at the abdomen, should overlap the torso series by 30 cm or more). Whether a head-and-neck series alone often reaches the sacrum is not recorded; one downloaded person would settle it.

## 5. The order to fetch, the owner's word of 2026-10-31 01:10 UTC

The owner: "start with NMDID's metadata file, but i want to proceed in order of decreasing size then starting with NMDID after I give you the okay". So the metadata comes first, and the image fetches go largest first, each only after his okay:

1. NMDID's metadata CSV, now (registration only, no image): the per-person covariates for all 15,000, which also let the research request name its inclusion rule. The site answers the container since 01:15 UTC, but the CSV is behind an account whose registration signs the site's DUA, so the owner registers and downloads it (section 4b); nmdid-request.md beside this file holds the steps and a draft of the research request.
2. NMDID's images, over 50 TB, after the owner's okay and the committee's approval, to the grid under the size rule, a few TB at a time.
3. The IDC remainder of section 3, about 155 GB, through the existing reacquire route.
4. CADS's CT-TRI and VISCERAL, 123 GB, after registration.
5. autoPET longitudinal CT, 54 GB, after a person-overlap check against FDG-PET-CT-Lesions.

The TCIA collections of section 4a sit by size between NMDID and the IDC remainder: S0819 1.8 TB (few whole-spine fields), AHOD0831 450 GB, HNSCC 310 GB, ACRIN-HNSCC-FDG-PET-CT 148 GB, CALGB50303 139 GB, Anti-PD-1_MELANOMA 98 GB, Head-Neck-PET-CT 72 GB, Healthy-Total-Body-CTs 59 GB, Head-Neck Cetuximab 52 GB, CT-ORG 17 GB; all but CT-ORG wait on the TCIA Restricted agreement or an NCTN/NCORP request, both the owner's to sign. Where the order is by size alone, the owner's word decides whether a 1.8 TB set with perhaps 80 usable persons keeps its place.

Nothing above has been fetched.

## 6. NMDID as a rolling pipeline, the owner's word of 2026-10-31 01:16 UTC

The owner: "I ONLY HAVE 20 TB SO I WILL HAVE TO BATCH DOWNLOAD NMDID TRAIN ON THE DATA THEN DELETE SOME AND HAVE SOME BEING DOWNLOADED SO ITS A PIPELINE PROCESS FOR DOWNLOADING THE RAW VOLUMES SEGMENTING TRAINING AND THEN DELETING TO MAKE ROOM FOR NEW DATA". NMDID is over 50 TB, about 3 to 4 GB a person, so it never sits on the grid whole. The design, to be built as a launched flow once the committee approves and the owner gives the okay:

- Batches by person, a few TB each (the size rule's room decides the batch, not a fixed number), with one batch downloading while the one before it is segmented and used, and at most two raw batches on disk at once.
- Per batch: fetch the raw DICOM, check it, convert the series to NIfTI, segment it with the census's segmenters (SPINEPS, with TotalSegmentator for C2 and the sacrum as the owner allowed on 2026-10-30), run the rule 3 field test, and keep what is small and lasting: the masks, a spine crop of the CT (the column's bounding box with a margin, int16), the morphometry rows, the covariates from the metadata CSV, and the projections training uses. Only then delete the raw volumes.
- Every kept file and every deleted raw file is recorded by NMDID's person id and sha256, so a deleted volume can be fetched again by id and checked, and a run can say exactly which persons it used.
- Training reads the kept crops and projections, which stay on disk across batches, so later epochs still see the early batches; it does not have to train on raw volumes while they exist. A step that truly needs the full raw CT (a new segmenter, a new render) runs in the batch's window or re-fetches by id.
- The latent-prior test reserve rule applies here as to the gold tier: a held-out set of NMDID persons is drawn once, from the metadata, before the first batch, and no training touches it.

## 7. One dataset for the encoder and decoder, the owner's questions of 01:16 and 01:18 UTC

The owner asked whether to train his own segmenter on the gold tier for NMDID, and said he wants "ONE GIANT DATASET WITH ALL THAT METADATA" for training and testing his encoder and decoder. The thread's recommendation, in order:

1. Train one segmenter on the gold tier 3 CTs first, on the 28 canonical ids with the sacrum as one union mask (the owner's rule of 2026-10-30), with the latent-prior test reserve left out, as a launched flow under its own PREREG. It gives every source one label scheme and does not wait on NMDID. Judge it on held-out human masks, then on VSDFullBody for post-mortem CT.
2. Grow the gold tier store (tools/gold3_ct.py) into the one dataset instead of making a second: every row a person and a study with source, tier, age, sex, height, weight, scanner and kernel, a post-mortem flag, the rule 3 verdict, and each file's segmenter, version and sha256. The census's 1,388 gold 4 enter first, then the IDC remainder, then NMDID.
3. NMDID's metadata in, and an NMDID test reserve drawn from it, before any image.
4. NMDID through the rolling pipeline of section 6 with that segmenter. A machine mask never raises a tier, so NMDID is gold 4 until a person checks it.
