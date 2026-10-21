# An annotation format for spine X-rays: four corners per body, the column called once

Source: the thread "3D CT priors for 2D detection", 2026-10-21, from the owner's ask of 20:11 UTC: "I don't think anyone has stratified and identified spinal anomalies on xray so I'd like to build a detector I can run over my massive unannotated xray dataset. Figure out a good annotation format for XR (corners around bodies most likely) based on the preponderance of the annotations of X-rays currently". The project's datasets come from the registry and the inventory (docs/research/datasets-inventory.md, xray-datasets-missing.md); the outside facts from the datasets' pages and papers read on 2026-10-21, listed in section 6. Confidential with the rest of this repository (docs/project.md).

## 1. The answer

Four corners per vertebral body, in a fixed order, each with its level name and a visibility flag; the box is computed from the corners and never stored beside them; the column's count (T12L5, T12L6, T13L5 and so on) and the transitional findings are recorded once per image, not per body; every annotation names its reader. Exported as COCO keypoints, four keypoints per body, which the common tools read and write natively.

## 2. What the existing X-ray sets use

| Set | Held? | What each body carries |
| --- | --- | --- |
| AASCE 2019 (BoostNet) | yes, 609 labelled AP films | four corners of each of 17 bodies, T1 to L5, 68 points per film |
| BUU-LSPINE | requested | the upper and lower edge lines of each lumbar body, as CSV points (each line's two ends are two corners), with the LSTV call per patient |
| Spondylolisthesis landmarks (Mendeley 5jdfdgp762, 508 of them BUU's) | yes, 714 films | four corners per body, L3 to S1, as Keypoint R-CNN JSON |
| CSXA lateral cervical | yes, 4,963 films | corners per body, as JSON |
| VertXNet labels on NHANES II | labels to fetch | eight landmarks per body with the level, C2 and S1 as reference bodies |
| The C-arm video deposit in the inventory | geometry only | level-named corner tracks C0 to T1 on every frame |
| Kaggle scoliosis YOLOv5 | to confirm | a box per vertebra, no corners |
| VinDr-SpineXR | yes | boxes around lesions, not around bodies |

Corners are the preponderance: every set that marks the bodies themselves marks their corners, or marks more points of which the corners are a part (VertXNet's eight), or marks edge lines whose ends are the corners (BUU). Boxes alone come only from sets made for a detector, and the lesion boxes of VinDr mark findings, not bodies.

## 3. Why corners and not boxes or masks

- A box is the corners' extent, so every corner set is also a box set, and the detectors the stack trains read boxes; the reverse is lost.
- Corners give the measures the anomalies are read by: the endplate angles and so the Cobb angle; the slip of one body on the next (listhesis, its Meyerding grade); the anterior, middle and posterior heights and so wedge and crush (Genant's grades); the tilt of the column on the frame.
- Corners are what the CTs give exactly: projecting each body's segmented endplates through a render's geometry yields its four corners with no reader (docs/research/ct-priors-for-2d-detection.md, items 3 and 4), so renders, registered real frames and read films land in one format.
- A mask costs several times the reading time of four clicks, and no held X-ray set carries body masks at scale.

## 4. The format, version 1

One JSON file per image (or one JSON lines file per batch), ASCII, beside the image's sha256, never beside an identifier:

```json
{
  "format": "schwingnet-spine-xr/1",
  "image": {"sha256": "<64 hex>", "width": 2048, "height": 2048,
            "view": "lateral", "modality": "film", "pixel_mm": null},
  "reader": {"id": "r01", "role": "annotator", "time": "2026-10-21T20:00:00Z"},
  "column": {"call": "T12L6", "basis": "counted from C2", "confidence": "sure",
             "lstv": {"present": true, "castellvi": "IIa", "side": "left"},
             "ribs": {"thoracic_pairs": 12, "cervical_rib": false}},
  "bodies": [
    {"level": "L5",
     "corners": [[812.0, 1404.5], [1010.2, 1398.0], [1016.8, 1590.1], [818.4, 1602.7]],
     "visible": [true, true, true, false],
     "findings": []},
    {"level": "L6",
     "corners": [[820.1, 1640.0], [1022.0, 1633.3], [1018.6, 1801.2], [826.0, 1810.9]],
     "visible": [true, true, true, true],
     "findings": [{"kind": "transitional", "detail": "lumbarised S1"}]},
    {"level": "sacrum",
     "corners": [[830.5, 1850.2], [1030.0, 1842.7], null, null],
     "visible": [true, true, false, false],
     "findings": []}
  ]
}
```

The rules:

- Corner order is the same on every view, so a model learns one order: superior-left, superior-right, inferior-right, inferior-left as the image is shown with the head up. On a lateral the left of the image is whichever side faces it; the view field and the orientation the reader saw say which is anterior, and a converter may rotate a frame so that anterior is always left.
- The sacrum carries only its S1 endplate, its first two corners, the inferior two null; the reference bodies a set gives (C2 in VertXNet) carry what the set marks.
- Level names are the level encoder's 27 classes (src/schwingnet/catalog.py LEVELS: C1 to C7, T1 to T13, L1 to L6, sacrum), so T13 and L6 are labels and not notes, and a body the reader cannot name is "?" with its corners kept: a located body of unknown level still teaches detection.
- A corner outside the frame or hidden is null or marked not visible, never guessed; a body cut by the frame's edge keeps the corners it has.
- The box is min and max of the corners present. A set that has only boxes is ingested with corners null and a "box" field, and marked box-only, so no corner loss is computed on it.
- The column call is the image's, recorded once: the count of thoracic and lumbar bodies, what the count started from (C2, the first rib, the sacrum), and the reader's confidence (sure, likely, cannot tell). It is what the counting prior's column odds are made of (ct-priors-for-2d-detection.md, item 1) and what the screening detector is scored on.
- Findings are a short closed list, extended only by a reviewed change: transitional (lumbarised S1, sacralised L5, rib-bearing L1, T13), lstv with Castellvi's type I to IV and its side, hemivertebra, butterfly vertebra, block vertebra (with the level it is fused to), wedge or fracture (Genant 0 to 3), listhesis (Meyerding 1 to 5; also computed from the corners), cervical rib, implant. A finding the list does not hold is "other" with a sentence, so it is counted and the list grows from real cases.
- Every annotation names its reader, and a second reader writes a second file, never an edit: two readers' calls on one image are the transitional stratum's two-reader truth (retraining-plan.md), and a disagreement is data.

COCO keypoints is the export (category "vertebral body", four named keypoints, the level and findings as attributes), since CVAT and Label Studio read and write it and the keypoint detectors train on it; YOLO-pose is a second export for the Ultralytics trainers. The JSON above is the record, the exports are made from it.

## 5. The screening detector over the unannotated films

1. Converters bring every held corner set into the format: AASCE's 68 points (17 bodies, T1 to L5), the spondylolisthesis set's Keypoint R-CNN JSON, CSXA's corner JSON, VertXNet's eight points reduced to the four corners, BUU's edge lines once it arrives; each source keeps its registry record and its persons' split (retraining-plan.md section 3).
2. The renders add the anomalies with exact truth: a CT called T12L6 or T13L5 renders AP and lateral films whose bodies carry the format's corners and the column call (ct-priors-for-2d-detection.md, the section on anomalies labelled on CT).
3. The detector is a box-and-four-keypoint model over the 27 levels, its per-body posteriors decoded as one column by the counting prior, so its answer per film is a column call with odds and the per-body findings.
4. It runs over the unannotated films as a grid array job. A film whose most likely column is not T12L5 with odds past the margin, or where the decoder abstains, or where a body finding fires, goes to a reader, ranked by how sure the model is, so the readers' time goes where the anomalies are; the readers write the same format, and their confirmed films come back as new shards, which is how the rare classes grow (retraining-plan.md 3.2).
5. What is reported is the stratified prevalence: per collection, per view, per age band where the record has one, each column and finding with its interval, from confirmed reads only, and the model's screening yield (confirmed per film sent to a reader) beside it.

Which films are "the massive unannotated X-ray dataset" is the owner's to name; the candidates the inventory lists are the 16,531 digitised NHANES II films without landmarks, the chest sets (ChestX-ray14, MIMIC-CXR-JPG, VinDr-CXR and PCXR, where the thoracic spine is in every frame) and the films the owner holds outside the registry.

## 6. The pseudo-labeller (the owner, 2026-10-21 20:12 UTC)

"I'd also want to train a pseudolabeller for the rest of the X-rays based on my limited amount of annotated xray data." The detector of section 5 is first a teacher that labels the rest, by a loop that keeps the labels honest:

1. The teacher trains on everything with truth: the corner sets of section 5 step 1, the owner's own annotations, and the renders with exact truth. Each source keeps its person split, so the teacher's validation and test numbers are on persons it never saw.
2. It labels the unannotated films in a grid array job. A film's labels are kept only where three checks agree: the model is confident per body, its answer holds under flips, scales and contrast changes of the same film (test-time augmentation), and the bodies decode as one column the counting prior accepts (docs/research/ct-priors-for-2d-detection.md, item 1). A film that fails any check is not labelled; one where the column is unusual goes to a reader instead (section 5 step 4).
3. Pseudo-labels are written in this format with the reader "model:<run id>" and a confidence per body, as shards of their own, never mixed into a human-read shard, so every later training says how much of its truth was the model's, and a bad round is dropped by name.
4. A student trains on the human truth plus the pseudo-labelled shards, weighted below human truth, and becomes the next teacher only if it beats the teacher on the same human-read validation frames. Two or three rounds is the usual stopping point.
5. Each round a random sample of pseudo-labelled films, a few hundred, is read by a person, and the pseudo-labels' precision per level and per finding is reported with its interval. That number, not the student's score alone, says whether the pseudo-labels can be trusted.
6. Test persons are never pseudo-labelled, and no film of a person already in a test shard enters a pseudo-labelled shard (the leak checks at ingest, retraining-plan.md 3.2).

What it costs: one teacher training (the v1 run's scale, at most 6 GPU-hours on one H200), labelling at the detector's speed, an estimated 50,000 to 100,000 films per GPU-hour at 512 pixels with augmentation, and the reader's sample per round. These are estimates to measure on the first round.

## 7. Variables beside the images (the owner, 2026-10-21 20:12 and 20:13 UTC)

"Be checking for pathology metadata or age or anything else I could use as a variable. Maybe this would be in files that came with the dataset, supplementals of the paper, or the image metadata like for dicoms." Three places, each read its own way:

- DICOM headers: tools/covariates.py reads a seeded sample of each source's headers on the grid, never the pixels, and counts how often age, sex, view, body part, device, kVp, exposure, pixel spacing and the description tags are filled, with age as decade counts and no value per file; tools/bank.py already carries view, device and exposure into each item's record.
- Files that came with the dataset: the same tool lists every CSV, TSV, XLSX and JSON under the source's root with its column names and row count, so a person sees which variables exist without the rows leaving the grid.
- The paper's supplements: read by a session from the inventory's links where the proxy lets it, otherwise by the owner, and recorded in the source's registry record.

What the datasets' own documentation says they carry, to be confirmed by the census before any of it is used (none of this has been read from the files yet):

| Source | Variables documented by the dataset or its paper |
| --- | --- |
| NIH ChestX-ray14 | Data_Entry_2017.csv: patient age, sex, view position, 14 finding labels mined from reports |
| VinDr-SpineXR, VinDr-CXR, VinDr-PCXR | DICOM age and sex where kept; radiologist lesion boxes and image-level findings (osteophytes, disc space narrowing, listhesis, fractures, implants and others for SpineXR) |
| MIMIC-CXR-JPG | metadata CSV (view, study), CheXpert-style findings from reports; age through MIMIC-IV's patients table, under its own agreement |
| NHANES II films | the survey's own files by participant: age, sex, and the survey's health variables; VertXNet's osteophyte and landmark labels |
| AASCE | Cobb angles per film |
| BUU-LSPINE | spondylolisthesis diagnosis and LSTV per patient |
| Aariz | the cervical vertebral maturation stage, a skeletal-age proxy |
| KUB-StoneX | stone masks and radiomic features |
| FracAtlas | fracture labels and masks per film |
| C-ArmLSpine, COBRA, DeepFluoro | device and geometry from the DICOM and the CBCT; no demographics expected |

The census's output (aggregates and column names) comes back to this repository as docs/research/covariates/<source>.json once the job has run; any variable used in a model or a stratum is named in the source's registry record first.

## 8. Sources read

- The AASCE 2019 set: 609 AP films, 17 bodies with four corners each, 68 points per image (arXiv 2001.03187, 1910.14202, 2206.02087).
- BUU Spine Dataset project page (services.informatics.buu.ac.th/spine/): upper and lower edge lines of each lumbar body as CSV points; the Applied Sciences paper of July 2023: 3,600 patients with vertebral position, spondylolisthesis and LSTV truth.
- Spondylolisthesis Vertebral Landmark, Mendeley Data 5jdfdgp762: four corner keypoints per body, L3 to S1, Keypoint R-CNN JSON.
- The project's inventory for CSXA, VertXNet, the C-arm corner tracks, the Kaggle YOLOv5 set and VinDr-SpineXR.
