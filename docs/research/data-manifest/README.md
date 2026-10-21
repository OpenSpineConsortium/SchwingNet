# The sample index: every held file, its metadata and its labels, in one queryable file

Source: the thread "3D CT priors for 2D detection", 2026-10-21, on the owner's asks of 21:27 UTC
("you should have more details than just how many datasets I have, I want you to write a grid job
that inspects and creates a more detailed manifest or annotated vs annotated, the size, data
format, and any other relevant data") and 21:28 UTC ("I definitely want you to be able to pair
each sample with variables like through a query able database to get any Dicom header data or any
sample specific metadata"). He named NHANES II as the large unannotated X-ray set the screener
(issue #64) runs over. Confidential, this repository only.

## Where it stands

Built, not yet run: tools/sample_index.py, grid/samples.sbatch and grid/run-samples.sh, tested on
synthetic sets (tests/test_sample_index.py, the DICOM part in the train-cpu environment). It runs
through the Beethoven gate once the word `samples` is there (asked of the thread that owns the
gate's new words, beside #72); its answer, MANIFEST.md, is copied here when it comes back.

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
