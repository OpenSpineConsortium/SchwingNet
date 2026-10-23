# The sample index: every held file, its metadata and its labels, in one queryable file

Source: the thread "3D CT priors for 2D detection", 2026-10-21, on the owner's asks of 21:27 UTC
("you should have more details than just how many datasets I have, I want you to write a grid job
that inspects and creates a more detailed manifest or annotated vs annotated, the size, data
format, and any other relevant data") and 21:28 UTC ("I definitely want you to be able to pair
each sample with variables like through a query able database to get any Dicom header data or any
sample specific metadata"). He named NHANES II as the large unannotated X-ray set the screener
(issue #64) runs over. Confidential, this repository only.

## Where it stands

Run once, on 2026-10-22, through the gate word `samples` (grid/run-samples.sh): the plan (job
40702274), 64 scan tasks of 8 to 97 minutes each (array 40702275), the merge (40702276, 5 h 9 min,
which wrote samples.sqlite and then failed in the report's json.dumps on a None key, fixed in #114)
and the manifest alone (40703320, 4 h 56 min). The manifest is MANIFEST.md beside this file: 140
groups, 7,008,826 files, 7.3 TB. The gate's status shows it whole since #122.

What the first run says, read with the registry (data/sources/) for each source's region, since
the markdown manifest carries no body part; the JSON on the grid does, for DICOM sets:

- X-ray films with level or landmark truth, by region. Cervical: CSXA 4,963 films (4,962 with a
  sidecar), Aariz cephalograms 1,000 (C2 to C4 shapes). Thoracic: AASCE 609 landmarked films (the
  BoostNet copy is the same films). Lumbar: BUU-LSPINE 3,600 AP and 3,603 lateral films with
  end-plate lines (the scan counts 14,551 annotated of 19,754 image files under its folder, crops
  and renders among them) and its 2000 relabel (2,000 of 4,000 JPEG), C-ArmLSpine 299 spot frames
  (297 annotated). Across regions, unsplit here: NHANES II 17,073 films (the registry says 543
  carry landmarks, 364 persons; the scan finds a sidecar beside every film, which is the JSON and
  NPY the landmark pipeline wrote, not truth), VinDr-SpineXR 10,466 DICOM (lesion boxes, no
  levels; cervical, thoracic and lumbar studies), Spinal-AI2024 20,001 JPEG (10,346 with a
  sidecar), FluoroCap 361,567 panels (pseudo-labels only).
- X-ray without truth, usable for the screener and self-supervision: NHANES II 16,531 films,
  FluoroCap 322,914 panels, fluoro_video_clips 726,614 frames (690,554 without a sidecar),
  C-ArmLSpine 51,429 DICOM frames beyond the spots, DeepFluoro vendor frames 94,566 (pelvis),
  KUB-StoneX 6,810 (frontal lumbar and pelvis, no spine labels). The chest sets (NIH ChestX-ray14,
  Open-i, VinDr-PCXR) and FracAtlas are on the volume only as archives or a record, not unpacked.
- Real AP and lateral pairs: BUU-LSPINE's 3,600 people, lumbar; none above the lumbar spine.
- X-ray with a CT or a model of the same subject, nine sets by the owner's count of 2026-10-22: held,
  C-ArmLSpine 149 cases (CBCT), COBRA 692 cases of projections (cobra2026, 6,920 image files; the
  bank 1,337), DeepFluoro 6 specimens, Ljubljana 18 frames, the Geneva hip phantom 116 frames (its
  phantom CT and gold poses ship; the unseen-device test); not fetched, LUMOS 1,620 lumbar films with 280 CTs (no pose), the IPCAI 2025
  femur set, the IEEE DataPort pig lower limb (7 projections, CT, CBCT, matrices) and Veriserum's
  knee implant frames; and a tenth found the same evening, the digital twin's cadaver of arXiv
  2412.08020 (80 Loop-X frames registered to 4 CTs, mid-femur to T2, the fetch word
  ipcai2025_robotic_xray_drive). The spine ones are lumbar and lumbosacral except that cadaver, the
  one real C-arm pair above L1; the others tune the registration code. Which ships vertebra masks and what ITK-SNAP must add is the table in
  docs/research/benchmarks-to-beat.md, section 5.
- Segmented CT: CTSpine1K 1,005 (whole spine), VerSe 374 series (on the volume as versefusion,
  4,325 image files, 1,652 with labels), TotalSegmentator v2.0.1 1,631 and v3.0.0 1,936 scans,
  CTSpinoPelvic1K 802 volumes (2,052 image files, 1,006 with labels; lumbosacral, L6 flagged),
  CTPelvic1K 178 (163 with labels), RibFrac 660, PENGWIN 680 (203 with labels; pelvic fracture),
  RSNA 2022 cervical 2,019 studies (189 GB, still zipped), the spine metastasis set (35,527
  DICOM), anomaly_harvest_b 14,909 NIfTI (6,670 with labels).
- Derived corpora, counted but not sources: or_ready (66,153 images, 808 GB), multisource_banks
  (52,653), spine_detector_corpus (268,441), devcorpus (40,529), realxray (23,582), rare_class and
  fluorogen_synthetic (renders), xrspinopelvic1k (6,421 DRRs).

The next run should split NHANES II, VinDr-SpineXR and FluoroCap by region: the JSON manifest
already counts each DICOM group's body parts and views, and markdown() in tools/sample_index.py
can print them as a second table; a PNG set's region comes from its sidecar rows, which the
sample_meta view answers on the grid.

## What it reads

- Roots: every raw location of a source data/reproduce/sources.json holds on disk, every lab path
  a registry record under data/sources/ names, and every folder of the data root that is not a
  tool's own (no leading underscore), named `unmapped:<folder>` where no record names it. A file
  belongs to the deepest root that holds it; a root inside another is walked once, with it.
- Each file: size, time, the format from its first bytes (DICOM, PNG, JPEG, JPEG 2000, TIFF,
  NIfTI, NRRD, MetaImage, HDF5 and MATLAB, NumPy, MP4, MKV and AVI, the archives, pickle, the
  tables), and the width, height, depth, frames, channels and bits its header gives. A pickle is
  never unpickled.
- DICOM (pydicom, never the pixels): every header element, sequences to two levels, kept whole for
  each projection image (CR, DX, RF, XA and the like) and for the first slice of each CT, MR or PET
  series, whose other slices point to it (ALL_SLICES=1 keeps every slice whole); the common fields
  (modality, view, body part, maker, model, kVp, sex, age in years, pixel spacing, the UIDs,
  PatientID) are columns of the file table too.
- Tables and JSON that came with a source: every row as cells (CSV, TSV, the first sheet of an
  XLSX, a JSON list of objects, a COCO file's images with their annotation counts and categories,
  one JSON object flattened), two million rows a table at most.

## The joins

- A cell names a sample when its value, reduced to a key (lower case, the last path part, suffixes
  off, leading zeros off a number), is the sample's name, a run of five or more digits in it, or a
  DICOM sample's SOP, series or study UID or PatientID, and no more than twenty files carry that
  key. The link records which way it met (name, digits, sop_uid and so on), so a query can trust
  the strict ones only.
- A sample is annotated when an annotation file (a mask, a label or landmark file, a pickle, an
  XML, anything under a folder named for labels) has its stem once words such as label, mask or seg
  are taken out, in its own root (stem) or another (stem-elsewhere), or when it is linked to a row
  of a table whose columns hold coordinates, classes or levels, or to a COCO file's images. The
  manifest sets the data platform's own word on each source's labels beside the scan's count.

## The database

samples.sqlite, under the data root's _samples/<run>/, never leaves the grid, since it holds
paths, UIDs and PatientID. Tables: root, file, dicom (file_id, tag, keyword, vr, value), tab and
cell (the sidecar rows), key, link and annotation. Views: sample (file with its root's sources),
sample_meta (each sample's linked cells), sample_header (each sample's DICOM elements, its own or
its series'). Some queries:

    -- NHANES II films, annotated or not, with their size
    SELECT annotated, COUNT(*), SUM(size) FROM sample
    WHERE sources LIKE '%nhanes2%' AND role = 'image' GROUP BY annotated;

    -- every lateral DICOM film of a woman in her fifties, with its maker and kVp
    SELECT path, manufacturer, kvp FROM file
    WHERE format = 'dicom' AND view IN ('LL', 'LATERAL') AND patient_sex = 'F'
      AND age_years >= 50 AND age_years < 60;

    -- any header element of a sample, by keyword
    SELECT f.path, h.value FROM sample_header h JOIN file f ON f.id = h.file_id
    WHERE h.keyword = 'AcquisitionDeviceProcessingDescription';

    -- every variable a sidecar table gives a sample
    SELECT m.col, m.value FROM sample_meta m JOIN file f ON f.id = m.file_id
    WHERE f.name = '<file name>' AND m.via IN ('name', 'sop_uid');

## What leaves the grid

MANIFEST.json and MANIFEST.md, per root group: files, bytes, counts and bytes by format and role,
images annotated and not, the range of widths and heights, distinct series and patients, the
fifteen commonest modalities, views, body parts, makers and sexes, age in decades, how many files
fill each of sixty DICOM keywords, and each table's kind, row count, column names and how many
samples it links. No file name, path below a root, UID, ID or value of a row leaves.

## Limits

- Matching by name finds what a dataset's own files say; NHANES II's demographic variables live in
  NCHS's public survey files, linked by the respondent's sequence number, and come in only once
  those files are on the volume beside the films.
- A key carried by more than twenty files names none of them, so a table keyed by a common word
  links nothing; a run of digits can meet the wrong file, and its link says digits.
- An archive is listed, never opened; a set held only as a zip counts as one file until unpacked.
