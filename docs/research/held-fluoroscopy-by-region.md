# Held fluoroscopy by region, and the records checked against their papers

Source: the thread "Choose datasets for a powered normal-spine test", 2026-10-25. It answers the owner's question of 04:41 UTC: "surely I have some thoracic and cervical fluoro? how did you make that determination? do all these datasets map to a specific known dataset ... can they be verified against their papers for what they contain?" The evidence is:

- tools/folder_report.py over the newest sample index (grid job 40780668, read whole through the gate word `folders` after #301);
- the status word of the same day;
- the dataset records of OpenSpineConsortium/spine-datasets (datasets/*.json), whose counts come from each set's paper or source page.

Confidential, like every note here: this repository only.

## How the earlier answer was made, and what was wrong with it

The chooser (dataset-chooser.md) reads the registry under data/registry/. It counts a set as fluoroscopy, and finds its region, only from the set's record. A held folder that no record names was invisible to it: 56 groups of the sample index were "unmapped". So "no thoracic or cervical fluoroscopy" meant "none that a record names". It was not a reading of the volume. The folder report now reads every folder.

## What the volume holds, by region

The report counts files whose path names fluoroscopy (fluoro, C-arm, cine, intra-op) or a region (cervical, thoracic). A path name is a lead, not a label. No figure below is a level-labelled count unless it says so.

Real fluoroscopy pixels, by folder:

- carmlspine: 149 lumbar intraoperative cases, with spot frames and two rotational sweeps. Levels come from each case's CBCT. Lumbar only.
- deepfluoro_vendor and deepfluoro_h5: pelvis, 6 subjects. No spine levels.
- fluorocap: 361,567 images (PNG and JPEG) cut from published figures, 202 GB. 293 paths name the thoracic spine and 163 the cervical. The project's rule keeps it out of training and lets it be a test set at most. Its regions are not labelled.
- external/fluoro_video: public clips (Bern, PMC, Wikimedia Commons, YouTube re-encodes), 245 GB. 18 of the 70 YouTube entries show live fluoroscopy, 9 of them cervical. None names a level, and the YouTube copies are unpermitted until a request is answered. Screening only.
- cathaction: about 500,000 frames of endovascular catheterisation, largely animal and phantom, in two zips. No spine.

Cervical with levels, but no pixels:

- bournemouth_cervical_qf (realxray/bournemouth_qf): 252 lateral flexion and extension sequences from 63 people. The deposit holds level-named corner tracks, C0 to T1, on every frame, and no pixels. The cine is requested. When it arrives, it is the one cervical fluoroscopy set with levels on every frame.

Thoracic and cervical on radiographs only:

- aasce2019_boostnet and thoracic_xr: AP whole-spine films, corners T1 to L5.
- csxa_cervical_xray_atlas and aariz: cervical films. Aariz covers C2 to C4 by maturation stage only.
- vindr_spinexr, nhanes2_cdc_films and spinal_ai2024: films.
- spine_detector_corpus: 11,375 paths that name the cervical spine.

Derived, from the held CTs and films:

- or_ready/wholespine: 12,950 PNG frames, 750 paths naming the cervical spine. Built, not acquired.
- multisource_banks: 2,575 paths naming the cervical spine and 1,516 the thoracic.
- rare_class and devcorpus: DRR banks.

The answer, then: no thoracic or cervical spine fluoroscopy with level labels is held. The closest are three:

- Bournemouth's cervical tracks, waiting on their cine;
- FluoroCap's figures, private and a test set at most;
- the nine cervical clips, screening only.

A powered fluoroscopy test of normal thoracic or cervical spines cannot be cut from what is held today. Bournemouth's cine, at 63 people, is the nearest step.

## Every folder maps to a record or a task

The report's first table lists the 87 folders the index holds files of. The status word adds 23 more of 5 GB or over that the index holds none of, idc_nlst (3.2 TB) among them. All 110 are in spine-datasets grid/folders.json (spine-datasets #369):

- 77 name their records.
- 12 derived banks, 14 working folders and 2 empty folders each name an accounting task.
- 5 held sets have no record yet: spinal_ai2024, mendeley_5jdfdgp762, spinesac, fluorocap and ieee_dataport_lateral_fullspine_236. Each has an open task to write its record.

One folder of about 17 GB has a name the readout masks (32 or more characters) and is held by its task until it can be named. Two caveats about the totals:

- The two lists sum to 14,039 GB against the status word's 14,509 GB, the gap being the index counting less than the volume inside folders it holds.
- A folder under 5 GB that the index skipped would be missed.

## The records against their papers

The report's image counts, set beside the counts each record takes from its paper or source page:

| set | the record (paper or source) | on the grid | reading |
| --- | ---: | ---: | --- |
| aariz | 1,000 cephalograms | 1,000 images | matches |
| buu_lspine (3,600 release) | 7,203 films | 7,204 JPEG | one more |
| vindr_spinexr | 10,466 images | 10,466 PNG in its bank | matches |
| csxa | 4,963 images | 4,959 PNG, 4,963 JSON | four images short |
| nhanes2_unannotated | 16,531 films | 17,073 TIFF | 542 more |
| kub_stonex | 2,570 radiographs | 6,810 images, 9,630 PNG | more than the paper; masks or crops likely |

The leads to settle: why NHANES II holds 542 more films than its record, and what kub_stonex's extra images are. Each goes to its record's task in spine-datasets. The other held sets were not set against a paper here. Their records name the paper, and the check is one table row each once their image counts are read.
