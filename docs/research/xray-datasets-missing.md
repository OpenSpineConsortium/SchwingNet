# X-ray datasets not yet in the registry

Source: the thread "SchwingNet video demo plan", 2026-10-21, the owner's question: "I feel like
there were way more X-ray datasets I'm missing". Written by a research subagent in a cloud
session, from the 60 records under data/sources/ (read in full: id, name, link, what, status),
docs/research/datasets-inventory.md, docs/research/datasets-reproduce.md (the 211-record
manifest map), spine-program's 10_data_platform_grid/docs/XRAY_DATASET_USAGE.md, and web
searches on 2026-10-21. The cloud container resolves almost no dataset host (zenodo.org,
huggingface.co, physionet.org, data.mendeley.com, nature.com, pmc.ncbi.nlm.nih.gov,
grand-challenge.org, arxiv.org, github pages and the university hosts all answered ENOTFOUND),
so every count and licence below comes from search-result text or from the writer's prior
knowledge, and "to confirm on the page" marks what the owner reads on the page before asking.
Radiopaedia was not fetched and is not listed: its record (radiopaedia) already holds the
application.

## What the registry already holds, so it is not repeated here

Plain films: AASCE/BoostNet, BUU-LSPINE (and the Mendeley 5jdfdgp762 relabel), CSXA, NHANES II
(annotated and unannotated), VinDr-SpineXR, IEEE DataPort lateral 236, Spinal-AI2024, LUMOS,
TVGH-SpineXR. Fluoroscopy and C-arm: C-ArmLSpine and its sweeps, DeepFluoro, Ljubljana
2D-3D-GS, Geneva hip phantom, SpineSAC, Balgrist, SX-Stitch, the Bournemouth cervical and lumbar
QF sets, Maastricht cervical cine, Bern myelography, the swallow corpora (DysphagiaBank,
Pittsburgh), IRI-VFI, the coronary angiography sets (CADICA, ARCADE, XCAD, AngioCAD), the
YouTube and journal-video requests, Konica DDR. Projections with a registered CT: COBRA2026.
CT and renders: VerSe, CTSpine1K, CTPelvic1K, RibFrac, CTSpinoPelvic1K, TotalSegmentator, RSNA
2022 cervical, the anomaly-harvest CTs, FluoroGen, FluoroCap. The 211-record manifest also
cards CSI 2014, the Glocker SpineWeb 3 CT (excluded), PENGWIN 2026 CT and MedPelvis3D, but none
of those is 2D.

## Candidates not in the registry

Priority: A, spine with level or vertebra labels; B, spine without labels; C, other-region
radiographs or fluoroscopy for device and exposure diversity. "Access" says what one must sign
or click, as far as it could be read.

| Name | What (modality, region, count, labels) | Link | Licence / access | Why it matters | Priority |
| --- | --- | --- | --- | --- | --- |
| VertXNet extra labels for NHANES II (Mo, Papiez, Chen 2023, Scientific Reports 14:3341, 2024) | Radiographs already on the grid (NHANES II cervical and lumbar laterals); new labels only: 8 landmarks per vertebral body with vertebral identity, and the reference bodies C2 and S1 annotated by radiologists where visible; the Zenodo record is "NHANES II Spinal X-ray with Extra Labels For Reference Vertebral Bodies (C2, S1)", version 1, 2023 | Zenodo record named in the paper's Data availability (DOI not read; the article is doi:10.1038/s41598-023-49923-3) | Zenodo, open; licence to confirm on the page | C2 and S1 are exactly the anchors the level counter needs on NHANES II, whose 543 annotated films carry only C3-C7 and L1-L5; this closes the registry's known NHANES gap at zero imaging cost | A |
| MrOS lateral spine radiographs (Osteoporotic Fractures in Men study) | Lateral thoracic and lumbar films of 5,994 men at six US centres, two visits (2000-2002 and about 4.6 years later); Genant semi-quantitative vertebral fracture grades per vertebra; one deep-learning study used 4,461 subjects and 15,524 films | https://mrosonline.ucsf.edu/ (the study's data request portal; to confirm) | A research data request through the MrOS coordinating centre (an online application with a proposal); the images are not on dbGaP, whose phs000373 covers genotypes; to confirm on the page | The largest lateral spine film set with per-vertebra labels in the public domain of research; older osteoporotic spines, many with compression fractures, the anatomy the C-arm sees in kyphoplasty; Genant grades sit on named levels, so level truth exists | A |
| SOF lateral spine radiographs (Study of Osteoporotic Fractures) | The women's counterpart of MrOS: lateral thoracolumbar films at several visits, about 9,700 women, Genant grading per vertebra; counts to confirm | https://sofonline.ucsf.edu/ (to confirm) | The same kind of request as MrOS; to confirm on the page | As MrOS, for women; together the two cohorts are the largest level-labelled lateral spine film resource that exists | A |
| VerSe 2D projections with soft labels (Zenodo 8115942, "Annotating ambiguous images", 2023) | 2D projections of the central slices of VerSe 19 and 20 vertebrae, with soft labels from proposal-based non-expert annotation; count to confirm (VerSe holds 4,505 vertebrae over 374 scans) | https://zenodo.org/records/8115942 | Zenodo; licence to confirm on the page (VerSe itself is CC BY-SA 4.0) | A ready 2D vertebra set with identity from VerSe, usable as a cheap extra render arm or a sanity check of the project's own VerSe renders; its people are already in the v9 base, so it is train-side only | A |
| PENGWIN 2024 Task 2 synthetic X-rays (Zenodo doi:10.5281/zenodo.10913195; mirror huggingface.co/datasets/MedOtter/PENGWIN_Task2) | 50,000 DeepDRR images with 2D fragment masks from 100 pelvic-fracture CTs at 500 random C-arm poses each; projections 0250-0499 add up to 10 simulated K-wires and screws; pelvis, sacrum and the lower lumbar spine are in field | https://pengwin.grand-challenge.org/ and the Zenodo record | Zenodo, open (CC BY, to confirm on the page); the challenge page lists its terms | The only large public DRR set rendered with real C-arm poses and simulated hardware; pelvic-ring and sacral appearance under instruments is otherwise unrepresented, the lumbosacral junction's neighbourhood, without any patient; no vertebra labels, so level truth would come from the Task 1 CTs (already on the grid as pengwin2026) | B |
| Fraiwan et al., Mendeley xkt857dsxk, "A dataset of scoliosis, spondylolisthesis, and normal vertebrae X-ray images" (2022) | 338 subjects' spine radiographs from King Abdullah University Hospital, Jordan, in three classes (scoliosis, spondylolisthesis, normal), original and resized; views to confirm | https://data.mendeley.com/datasets/xkt857dsxk | Mendeley Data, CC BY 4.0 (Mendeley's default; to confirm on the page) | New people from a Middle-Eastern centre, with spondylolisthesis cases, a sagittal-plane variant the lumbar measurement meets; no vertebra labels, so a pseudo-label or test arm only | B |
| Kaggle "Scoliosis YOLOv5 annotated spine X-ray dataset" (salmankey) | AP spine films with YOLO boxes on vertebrae and curve regions; count, source and whether the people are AASCE's to confirm | https://www.kaggle.com/datasets/salmankey/scoliosis-yolov5-annotated-spine-x-ray-dataset | Kaggle, licence on the page; provenance unstated, so treat as a relabel of a known set until shown otherwise | Boxes per vertebra are level-adjacent truth if the vertebrae are ordered; worthless if it is AASCE re-exported, which a filename or pixel hash check against the AASCE copy on the grid decides | A if new people, else exclude |
| Kaggle "Bone fracture multi-region X-ray data" (bmadushanirodrigo) | 10,580 radiographs in fractured and non-fractured folders over lower limbs, upper limbs, lumbar spine, hips and knees; 481 MB | https://www.kaggle.com/datasets/bmadushanirodrigo/fracture-multi-region-x-ray-data | Kaggle; licence and the images' origin unstated in what was read (many Kaggle fracture sets are scraped from teaching sites), to confirm on the page | A lumbar-spine folder and a hip folder from unknown devices; useful only as an exposure-diversity pool, and only once its origin is shown to be redistributable | C |
| FracAtlas (Abedeen 2023, Scientific Data) | 4,083 musculoskeletal radiographs from three Bangladeshi hospitals (hand, leg, hip, shoulder), 717 with 922 fracture instances; boxes and masks | https://figshare.com/articles/dataset/The_dataset/22363012 (to confirm; also mirrored on Hugging Face as yh0701/FracAtlas_dataset) | CC BY 4.0 | The hip and pelvis films show the sacrum and L5 on a South Asian population and devices the project has not seen; no spine labels | C |
| Hip fracture radiographs in YOLO format (Gonzalez et al., Insights Imaging 2025; IEEE DataPort HUSJaUAFemoralFracture) | AP hip and pelvis films with fracture boxes; count to confirm | https://ieee-dataport.org/documents/husjauafemoralfracture | IEEE DataPort login; "for research purposes only" | Pelvic films from a Spanish centre; lumbosacral junction often in field; exposure diversity | C |
| KUB-StoneX (Daffodil International University HIRL, Bangladesh) | 2,570 AP kidney-ureter-bladder radiographs of 1,703 patients from two hospitals, with pixel-level stone masks and radiomic features | https://hirl.daffodilvarsity.edu.bd/dataset/ | Public per the listing; licence and download route to confirm on the page | A KUB film is a frontal lumbar spine and pelvis radiograph at abdominal exposure: 2,570 AP lumbar views with the iliac crests and the sacrum in field, the frontal counterpart of what the registry lacks in volume; no spine labels | B |
| Aariz cephalometric benchmark (Khalid, Fraz 2023, arXiv:2302.07797; the CEPHA29 challenge at ISBI 2023) | 1,000 lateral cephalograms from 7 devices, 29 landmarks and a cervical vertebral maturation (CVM) stage per film; C2 to C4 are in every image | https://arxiv.org/abs/2302.07797 (the data link is in the paper; to confirm) | Access by request to the authors, to confirm; the ISBI 2015 set (400 cephalograms, 19 landmarks, no CVM) is openly downloadable | Lateral C2-C4 on children and adolescents from seven devices; the CVM stage is a named-vertebra label (C2, C3, C4 shapes), so the top of the cervical counter gets pediatric anchors it has nowhere else | B (A for C2-C4 only) |
| AAOF Craniofacial Growth Legacy Collections | Digitised lateral cephalograms of growth studies, subjects aged 4 to 29, thousands of films across nine collections; no vertebra labels | https://www.aaoflegacycollection.org/ (to confirm) | Open online viewing; bulk download terms to confirm on the page | Longitudinal pediatric cervical spines (C2-C4) on film-era devices; an exposure and age-diversity source | C |
| ReXGradient-160K (Rajpurkar lab and Gradient Health, 2025) | 160,000 chest radiograph studies with reports from 109,487 patients, 79 US sites; several images per study, so laterals are likely included (to confirm) | https://huggingface.co/datasets/rajpurkarlab/ReXGradient-160K | Hugging Face gated: a non-commercial data access and use agreement signed on the page | The newest multi-site chest set; a lateral chest film is a thoracic spine lateral from T1 to about L1, and 79 sites means 79 exposure recipes; the frontal films give the thoracic spine behind the heart | C (B for the laterals) |
| MIMIC-CXR and MIMIC-CXR-JPG (PhysioNet) | 377,110 chest radiographs of 227,835 studies, 65,379 patients, Beth Israel Deaconess; frontal and lateral views (the lateral share is roughly a third, to confirm from the metadata CSV) | https://physionet.org/content/mimic-cxr/2.1.0/ | PhysioNet credentialed access: CITI training and the PhysioNet data use agreement, as VinDr-SpineXR already needed | The largest source of lateral chest films, hence of thoracic spine laterals, free of charge once credentialed; the DUA is one the owner has already signed for VinDr-SpineXR | C (B for the laterals) |
| CheXpert and CheXpert Plus (Stanford AIMI) | 224,316 chest radiographs of 65,240 patients, frontal and lateral; CheXpert Plus adds reports and DICOM | https://stanfordaimi.azurewebsites.net/ (the CheXpert entries) | Stanford AIMI registration and research use agreement, the same portal as INSPECT and Merlin, which the registry already lists as gated | Laterals again, from one centre with many devices; the owner's AIMI account would cover it | C (B for the laterals) |
| PadChest (BIMCV, Alicante) | 160,868 chest radiographs of 67,625 patients, 109 projections including lateral (about 30 percent) and some oblique; labels include 174 findings | https://bimcv.cipf.es/bimcv-projects/padchest/ | A licence form on the page (research use, by request) | European devices and film-era digitised plates; the richest set of non-standard chest projections, which adds oblique thoracic projections | C |
| NIH ChestX-ray14 and the RSNA pneumonia subset | 112,120 frontal chest films of 30,805 patients (RSNA used 30,000 of them) | https://nihcc.app.box.com/v/ChestXray-NIHCC and https://www.kaggle.com/competitions/rsna-pneumonia-detection-challenge | Open (NIH) and Kaggle competition rules (RSNA) | Frontal thoracic spine behind the mediastinum at chest exposure, in volume and with no agreement; no laterals | C |
| VinDr-CXR and VinDr-PCXR (PhysioNet) | 18,000 adult and 9,125 pediatric frontal chest radiographs from two Vietnamese hospitals, radiologist boxes | https://physionet.org/content/vindr-cxr/1.0.0/ and https://physionet.org/content/vindr-pcxr/1.0.0/ | PhysioNet credentialed access, the same route as VinDr-SpineXR (already held) | The same institutions and devices as VinDr-SpineXR, so these add pediatric thoracic spines on known hardware; the PCXR set is the only sizeable public pediatric spine-bearing radiograph source | C |
| BRAX (Brazil) and CANDID-PTX (New Zealand) | 40,967 and 19,237 chest radiographs with labels; BRAX includes laterals (to confirm) | https://physionet.org/content/brax/1.1.0/ and https://auckland.figshare.com/articles/dataset/CANDID-PTX/14173982 | PhysioNet DUA; figshare with a registration form | Two more continents' devices for the thoracic spine background | C |
| Open-i Indiana chest collection | 7,470 chest radiographs of 3,955 studies with reports, frontal and lateral pairs | https://openi.nlm.nih.gov/faq | Open, no agreement | Small but frictionless lateral chest films, good for a quick thoracic-lateral probe before the gated sets arrive | C |
| CathAction (Jianu et al., 2024; AIRVLab) | About 500,000 fluoroscopy frames (600,000 in the 2026 revision) of endovascular catheterisation, animal and phantom, with action labels, collision labels and 25,000 to 40,000 catheter and guidewire masks | https://huggingface.co/datasets/airvlab/CathAction (two zips, 4.35 GB and 9.88 GB) | Hugging Face; licence to confirm on the page | The largest real fluoroscopy frame pool in the open, from clinical C-arms with live instruments; no spine labels and much of it is animal, so it is an exposure, noise and device-domain source, not anatomy | C |
| Guide3D (ACCV 2024; AIRVLab) | More than 8,700 bi-planar fluoroscopic frames of guidewires in a vascular phantom, two guidewires, varied flow | https://airvlab.github.io/guide3d/ | Open per the paper; licence to confirm on the page | Bi-planar real fluoroscopy geometry from one device; phantom only, so domain and calibration value, no anatomy | C |
| Veriserum (ETH Zurich, MICCAI 2025) | About 110,000 dual-plane fluoroscopic images of knee implant phantoms with registered poses, 200 with manual registration | https://movement.ethz.ch/data-repository/veriserum.html (ETH Research Collection doi:10.3929/ethz-b-000701146) | Freely accessible per the authors; licence to confirm on the page | Real flat-panel fluoroscopy of metal implants at scale: the appearance of hardware under real exposure, which the project otherwise has only from simulation; no spine | C |
| WEISS catheter segmentation in fluoroscopy (UCL), OEVRK fluoroscopy data (4TU), Hamlyn 2016 endovascular challenge | Small phantom and in-vivo catheterisation frame sets with binary tool masks (hundreds to a few thousand frames each) | https://rdr.ucl.ac.uk/articles/dataset/WEISS_Catheter_Segmentation_in_Fluoroscopy_Dataset/24624243 ; https://data.4tu.nl/collections/d098b922-829a-4a9b-b6f8-8ca2c189eb8c ; https://hamlyn.doc.ic.ac.uk/Challenge2016 | CC BY (UCL and 4TU, to confirm); the Hamlyn set by registration | Minor device-diversity pools; listed so nobody searches for them again | C |
| VFSS2022 (TIB, doi:10.57702/w1ye2nim; Video-TransUNet) | 440 videofluoroscopic swallow frames with instance masks of the bolus and pharynx; cervical spine in every frame | https://service.tib.eu/ldmservice/dataset/vfss2022-dataset | Open per the listing; licence to confirm on the page | A small labelled cervical fluoroscopy set that the swallow requests in the registry (DysphagiaBank, Pittsburgh) do not yet deliver; no vertebra labels | C |
| Paired X-ray and CT dataset of the IPCAI 2025 paper "Automatic multi-view X-ray/CT registration using bone substructure contours" (Zenodo 15753063) | Real calibrated X-ray images with 5 CT scans, 6.7 GB; the anatomy was not readable from the search text (pelvis or spine, to confirm) | https://zenodo.org/records/15753063 | Zenodo, open; licence to confirm on the page | If it is spine or pelvis, it is one more real C-arm set with a registered CT, the COBRA and DeepFluoro kind, from a fourth device | B if spine, else C |
| Canine lateral thoracic radiographs for vertebral heart size (Mendeley ktx4cj55pn) | 152 lateral thoracic radiographs of dogs, anonymised | https://data.mendeley.com/datasets/ktx4cj55pn | Mendeley Data, CC BY 4.0 (to confirm) | The owner's veterinary direction (2026-10-20): a lateral dog thorax shows T1 to L1 and the VHS method itself counts vertebrae from T4, so this is a first canine thoracic-spine film set; no other public veterinary spine radiograph set was found | B (veterinary) |
| Mendeley DDH hip sets (jf3pv98m9g, Jordan, 354 subjects; 4gvcb6gmh2 AV-DDH, 2,417 infant hip films, updated 2026-03) | Infant and child AP pelvis radiographs with developmental dysplasia labels | https://data.mendeley.com/datasets/jf3pv98m9g and https://data.mendeley.com/datasets/4gvcb6gmh2 | Mendeley Data, CC BY 4.0 (to confirm) | Pediatric pelvis with the lumbosacral junction in field at low exposure; the only sizeable pediatric pelvic film source found | C |
| Roboflow Universe spine X-ray projects (spinefrxnormalvindr and others under rf100-vl) | Object-detection relabels of VinDr-SpineXR (osteophytes, implants, vertebral collapse) | https://universe.roboflow.com/rf100-vl/spinefrxnormalvindr-lt1cn-ryhy | Roboflow; these redistribute VinDr-SpineXR images outside its PhysioNet DUA | Not to be fetched: the pixels are VinDr-SpineXR's, already held under the agreement; the box labels could be read against the held copy if their licence allows, which is doubtful | exclude |
| Hugging Face UniqueData/spine-x-ray | A commercial marketplace sample (under 1,000 JPG and DICOM) across scoliosis, osteoporosis, spondylolisthesis, compression fracture and healthy classes | https://huggingface.co/datasets/UniqueData/spine-x-ray | A paid product; the sample's terms to confirm | Noted so it is not mistaken for an open set; a priced quote would need the owner's word | exclude unless bought |

## Sets looked for and not found public

- A scoliosis radiograph release newer than AASCE 2019 and Spinal-AI2024: every 2024 to 2026
  Cobb-angle paper read used AASCE plus a private hospital set; the Penn EOS AP set (SpineTK,
  Radiology AI 2023) is "available from the corresponding author on request", and the Inserm
  SKELETON EOS cohort is a closed epidemiological database. An EOS request to Penn is the one
  EOS route found.
- A public spine X-ray challenge after AASCE 2019: none on grand-challenge.org that the search
  reached; VerSe 2019 and 2020 and RSNA 2022 are CT, SPIDER and the RSNA 2024 lumbar challenge
  are MRI.
- A public pedicle-screw or spinal-implant radiograph set: none; the implant boxes in
  VinDr-SpineXR remain the only labelled hardware.
- A public cervical spine fracture or flexion-extension radiograph set: none beyond CSXA and the
  Bournemouth and Maastricht cine already recorded.
- The VERTE-X cohort (Severance Hospital, 26,299 lateral spine radiographs of 9,276 patients,
  JBMR 2023) and the KURE external set: no data availability statement was readable; a request
  to the corresponding author (Kyoung Min Kim) is possible but nothing suggests the images are
  shared.
- The UK Biobank DXA vertebral fracture assessment images (lateral spine DXA of tens of
  thousands of participants): a different modality at a different exposure, reachable only by a
  UK Biobank application with a fee; listed here as a known resource, not recommended before
  MrOS and SOF, which are radiographs.
- SpineWeb: its host spineweb.digitalimaginggroup.ca no longer resolves (a Slicer forum thread
  reports the same), so its numbered datasets other than 16 (AASCE) could not be re-read; the
  Wayback Machine is the way to list them.
- A public KUB set other than KUB-StoneX, a public veterinary spine radiograph set other than
  the Mendeley canine thoracic set, and a public dynamic digital radiography (Konica DDR) set:
  none found.
- PediaSHF-DX, named in one search summary as a pediatric figshare set: no record of that name
  was found; it is not listed above.

## Registry records that look incomplete against what was found

- nhanes2_annotated and nhanes2_unannotated: the VertXNet Zenodo record adds radiologist
  landmarks with vertebral identity and the reference bodies C2 and S1 to the NHANES II films;
  the records say nothing of it, and the manifest's `nhanes_pseudo` directory of 16,234
  pseudo-labelled films could be checked against those labels.
- mendeley_5jdfdgp762: the record counts 714 films; the Mendeley page as summarised in search
  says 698 (one reading) or 716 (another) sagittal lumbar films, 508 of them BUU-LSPINE's, with
  boxes and four corners per vertebra from L3 to S1, published 20 June 2025 (version 1). The
  count and the version on the page should be read and the record corrected; the record's claim
  that "about 500 are BUU people" matches the 508.
- aasce: the Kaggle scoliosis YOLOv5 set may be a relabel of the same films; if its hashes match
  the AASCE copy, the record should say so, so nobody counts them as new people.
- vindr_spinexr: the Roboflow rf100-vl relabels (osteophytes, surgical implants, vertebral
  collapse) exist outside the DUA; the record could note them as not to be fetched.
- coronary_angiography and fluoro_video_clips: CathAction (about 500,000 frames) and Guide3D
  dwarf the angiography sets the record lists; if the purpose is a real-fluoroscopy exposure
  pool with no DUA, CathAction is the larger candidate and belongs in the same record or beside
  it.
- pediatric_iri: the IEEE DataPort licence line the record could not read still could not be
  read from this container.
- tvgh_spinexr: unchanged; IEEE DataPort still answered nothing from here.
- veterinary_pig_levelcheck: the Mendeley canine thoracic set is the only other veterinary
  radiograph source found and could be recorded beside it under the veterinary direction.
- pengwin2026 (manifest only, no registry record): the challenge's Task 2 X-ray release (50,000
  DeepDRR images with hardware) is a 2D product of the CTs already on the grid and deserves a
  record of its own if it is fetched.

## What is not known

Every licence marked "to confirm on the page" was not read. No count above was verified against
a file listing. Whether ReXGradient-160K and BRAX include lateral views, what anatomy the Zenodo
15753063 X-rays show, whether the Kaggle scoliosis and multi-region fracture sets redistribute
other people's images, and the exact MrOS and SOF image counts and request steps, are the first
things to read when the owner opens the pages. Nothing here was fetched, and no request was
sent.
