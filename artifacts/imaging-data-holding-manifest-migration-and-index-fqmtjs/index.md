# Imaging data holding: manifest, migration and index

Oct 8, 2026 · @greg

The holding is 212 imaging sources in five families, every one now carded with its origin, its re-acquisition recipe and its defects; the move to the Ceph volume has started with the pilot batch, and students will read everything except the two sets held under a data-use agreement.

## What the holding is

Three projects, CTSpinoPelvic1K, the SchwingNet level-identification work and the spine-detector, collected spine imaging from public releases, built their own releases and render banks on top of it, and harvested published fluoroscopy. The manifest cards 212 sources; 116 are on disk today, 23 are planned fetches, 7 are gated behind a form, and 58 were ranked and excluded.

| Family | What it covers | Sources | On disk | Planned | Gated | Excluded |
| --- | --- | --: | --: | --: | --: | --: |
| A | The CT releases the project was built on, their nnU-Net datasets and CT render banks | 31 | 30 | 0 | 0 | 0 |
| B | The anomaly-harvest CT acquisitions ranked by the acquisition plan | 144 | 56 | 23 | 7 | 58 |
| C | Real X-ray and fluoroscopy with 3-D truth or pose | 12 | 12 | 0 | 0 | 0 |
| D | Plain-film and harvested 2-D corpora and their banks | 24 | 17 | 0 | 0 | 0 |
| E | The disk map; one source carded only here (PolyPose synthetic) | 1 | 1 | 0 | 0 | 0 |

By modality, over the 116 on disk (a source can hold several): CT 80, synthetic renders 19, plain film 14, fluoroscopy 9, angiographic fluoroscopy 4, cone-beam CT 3, video 2, MR 1, mixed 1, unknown 1.

Where it sits, as of 7 October 2026: home, the Panasas volume with a 4,295 GB soft quota, held 4,050 GB in 2.9 million files; the Ceph volume, 20 TB, held about 6 TB. The full cards, with every count's file, are in `spinesurg-ct-nnunet/data_platform/DATA_MANIFEST.md`.

## Where it came from

Every source is a public release or was synthesised from one; no patient was imaged for this work. The table holds the principal sources; the manifest cards all 212 with the file behind each number. Dates are when the lab acquired the copy, not when the images were taken.

| Source | Modality | Origin | Route | Acquired | Contents | Annotation |
| --- | --- | --- | --- | --- | --- | --- |
| TCIA CT COLONOGRAPHY | CT, prone and supine | TCIA, doi 10.7937/K9/TCIA.2015.NWTESAY1, CC BY 3.0 | NBIA by series id, CTSpinoPelvic1K download scripts | April 2026 | 825 patients, 3,451 series | none from the release |
| CTSpinoPelvic1K | CT | the lab's own release, Zenodo v11 10.5281/zenodo.22797014 | built from COLONOG, CTSpine1K and CTPelvic1K | v10 7 Sept 2026, v11 18 Sept 2026 | 802 records, 422 supine, 377 prone, 3 decubitus | expert per-level vertebrae, ribs, sacrum, hips, femora |
| CTSpine1K | CT | HF alexanderdann/CTSpine1K, CC BY-NC-SA 4.0 | HF LFS with sha256 | by 25 April 2026, Ceph copy 23 Sept 2026 | 1,005 volumes from four collections | expert vertebra labels |
| CTPelvic1K | CT | Zenodo 4588403 | Zenodo | by 25 April 2026 | dataset 2 and the clinical sets | pelvic labels |
| VerSe 2019 and 2020, VerSeFusion | CT | Sekuboyina 2021, Loeffler 2021 | VerSe nodes, then unified | 12 to 13 May 2026 | 374 scans, 355 patients; 10 VerSe'20 series never downloaded | expert vertebra masks, L6 and T13 variants |
| TotalSegmentator v2.0.1 and v3.0.0 | CT | Zenodo 10047292 and the v3 record | Zenodo zip | 14 and 19 Sept 2026 | 1,228 and 1,939 subjects | release organ and vertebra labels |
| RSNA 2022 cervical spine | CT | Kaggle challenge | zip, 203 GB | 19 Sept 2026 | 2,019 studies | fracture labels; used by nothing |
| RibFrac | CT | MICCAI 2020, CC BY-NC 4.0 | zips under home | 19 Sept 2026 | 660 chest CTs | rib fracture labels |
| 39 IDC collections, FDG-PET-CT-Lesions, AbdomenAtlas 3.0 Mini, AMOS22, NLST pilot and ten late Zenodo sets | CT | NCI IDC v24, TCIA, Hugging Face, Zenodo | tools/acquisition\_fetch.py, catalogue-verified | 23 to 27 Sept 2026 | about 16,900 CTs on disk of 18,873 listed | two-labeller transitional screen |
| C-ArmLSpine | fluoroscopy and CBCT | Zenodo 10.5281/zenodo.22768651, CC BY 4.0 | Zenodo | 21 Sept 2026 | 149 sessions, 299 spot frames, 602 sweep projections, 149 CBCTs | levels by two automatic labellers, registered poses |
| DeepFluoro | fluoroscopy | JHU, H5 release and vendor deposit doi 10.7281/T1/C304HZ | JHU Dataverse through a browser-like client | 20 to 22 Sept 2026 | 366 frames, 6 cadaveric pelves, three copies | CT and pose per frame |
| COBRA2026 | CBCT projections | Zenodo 10.5281/zenodo.21322350, CREATIS Girder, CC BY-NC 4.0 | tools/cobra\_fetch.py per case | 21 to 23 Sept 2026 | 692 public cases, 375,618 projections, 771 GB | planning CT registered, geometry per projection |
| Geneva hip, Ljubljana 2D-3D-GS, SpineSAC | fluoroscopy, radiograph | Yareta; lit.fe.uni-lj.si; Google Drive | HTTP; local zip; tools/spinesac\_fetch.py | 21 Sept 2026 | phantom and cadaver gold standards | poses; SpineSAC has no licence and no bone truth |
| CSXA | plain film, lateral cervical | public repository | archive | 1 to 9 Sept 2026 | 4,963 films | per-vertebra, released |
| BUU-LSPINE | plain film, AP and lateral | Burapha University, EULA | web download | 9 Sept 2026 | 3,600 patients, 7,200 films, plus the 2000 and 400 sets | endplate lines L1 to S1 |
| NHANES II | plain film, lateral | CDC films; Zenodo landmark set | HTTP loop | 9 to 23 Sept 2026 | 17,073 films; 543 landmarked | landmarks on 543 |
| VinDr-SpineXR | plain film | PhysioNet, named-person DUA | credentialed download | 7 to 10 Sept 2026 | 10,466 images in 5,000 studies | lesion boxes, not levels |
| AASCE/BoostNet, Mendeley 5jdfdgp762, IEEE lateral 236, Spinal-AI2024 | plain film and synthetic | open mirrors, Mendeley, IEEE DataPort | tools/thoracic\_xr\_fetch.py and HTTP | by 16 Sept 2026 | 609 labelled; 714; 236; 20,000 synthetic | corners or landmarks; none on the 236 |
| FluoroCap | published fluoroscopy reproductions | literature and web harvest | the harvest routes | 13 to 18 Sept 2026 | 316 GB; dropped from training, kept as a test set | none |
| XRSpinoPelvic1K | plain film renders and BUU sets | the lab's own, private | local | June to August 2026 | 32 GB | the lab's labels |

## Re-acquiring all of it programmatically

One driver, `data_platform/reacquire/reacquire.py`, reads the machine-readable source list and, for one source id or all of them, prints or runs the exact commands that fetch that source again and the checks that prove the copy complete. It is a dry run by default and executes only inside a Slurm job; on the login node it refuses and prints the sbatch line instead.

1. Routes: NCI IDC through s5cmd from the public buckets, TCIA NBIA by series, Hugging Face by LFS file with the Hub's sha256, Zenodo by record with the record's md5, public S3 buckets, the CREATIS Girder warehouse for COBRA, the JHU Dataverse for DeepFluoro, Google Drive for SpineSAC, plain HTTP for the film sets.
2. Verification: an archive counts as landed only when its checksum matches the repository's; a DICOM series only when its instance count matches the catalogue; NIfTI volumes are opened and read. Size alone is never the test, because CTSpinoPelvic1K CT 0533 once shipped truncated with a plausible size.
3. Resuming: every download goes to a `.part` file with an HTTP range resume and is renamed only after its check; a complete file that fails its hash is set aside as `.bad`. A preempted job does not submit its child jobs twice.
4. Gated sources print their manual steps and never run: VinDr-SpineXR needs the PhysioNet credentialed DUA, BUU-LSPINE its EULA, RSNA 2022 the Kaggle rules, and seven family-B collections stand behind a form.
5. The CTSpinoPelvic1K release itself rebuilds from TCIA by SeriesInstanceUID with the release's own `fetch_from_tcia.py`, into a fresh tree, verified over all 802 CTs.

Tests: 28 of 28 pass on the planning side; the live routes have not been exercised from this driver, only from the original tools they wrap.

## Where it goes

Everything lands under `/rs/rs_grp_oschome/go2432/data/<source_id>/` with the role folders `raw`, `converted`, `derived`, `labels` and `meta`, one folder per upstream release named by its source id, and a `README.yaml` in each stating what it is, where it came from, its licence and its annotation status. Code stays on home; data goes to Ceph. Folders already on Ceph keep their names because running chains and tools name them.

1. Ids stay as the release writes them, zero-padded where the release is. Volumes are never reoriented on write. Derived banks live under the source they were rendered from; a bank of several sources goes under `multisource_banks`.
2. Restricted sources, VinDr-SpineXR under its PhysioNet agreement and BUU-LSPINE under its EULA, and every bank that holds their pixels, are copied owner-only.
3. Links that must survive are handled, not rewritten: the nnU-Net container-path links stay as they are, the 802 CTs that are hard-linked between two trees move as one group in one rsync, and relative links that leave their folder are flagged before the move.

The procedure for each batch, every step a job on a compute node, never the login node:

1. Pre-flight: a read-only inventory of each item, its links and hard links, whether the target exists, and the running jobs that name it.
2. Copy: `rsync -aH --partial` into the target; a rerun resumes.
3. Verify: every path present, every size equal, every link resolving where it resolved before, every hard-link group intact, and a stratified sample of files hashed on both sides. The two hashed roots of the paper's data manifest are re-checked with its own tool.
4. Cut over: the home original is renamed to `<path>.pre-ceph` and a symlink is left at the old path, so every script that names the home path keeps working.
5. Finalize, after a look: the `.pre-ceph` copy is compared with the Ceph copy again, in full for anything irreplaceable or under 50 GB, and only then deleted. That is the step that frees home quota.
6. Publish: the source's `README.yaml` is placed and the batch is indexed into the database; folders not under an agreement are opened to read for approved students.

Rollback before finalize is a rename back. The plan, the batch files and the job scripts are in `data_platform/plan/`.

## Migration status

The pilot batch verified on 8 October 2026 at 02:37: DeepFluoro, 76 files, 5.27 GB, every file hashed equal on both sides, at 59.6 MB/s over one stream. Its cut-over is queued, and the copy jobs for the next seven batches are queued behind it. Sizes are the plan's dated estimates until the census replaces them; the batches whose home copies were already reclaimed will report their items absent and finish at once.

| Batch | What | Items | Estimated GB | State on 8 Oct 2026 | Job |
| --- | --- | --: | --: | --- | --- |
| B00 | DeepFluoro H5, the pilot | 1 | 6.2 | cut over; finalize pending | 40580054, 40580666 |
| B01 | TCIA CT COLONOGRAPHY raw DICOM and NIfTI | 5 | 1,057 | done: the two raw trees were already reclaimed; three metadata files moved and cut over | 40580667 |
| B02 | CTSpinoPelvic1K working copy and build tree, one hard-link group | 30 | 291 | cut over: the 802 CTs and labels (196 GB), the build archives and one label file now live on Ceph with symlinks at the old paths; 25 of 30 items had already been reclaimed | 40580668 |
| B03 | Home copies of CTSpine1K and CTPelvic1K | 2 | 226 | done: both home copies were already reclaimed; the Ceph copies of CTSpine1K and CTPelvic1K stand |  |
| B04 | Plain-film raw corpora and the spine-detector datasets | 13 | 302 | copy queued | 40580669 |
| B05 | XRSpinoPelvic1K data | 3 | 4.7 | waits for B04 |  |
| B06 | VerSe, VerSeFusion and the VerSe render banks | 14 | 383 | verified, all 14 items (VerSeFusion data, vf\_813, the VerSe render banks, implant\_verse); cut-over queued | 40580670 |
| B07 | TotalSegmentator v2.0.1 and v3.0.0 and their banks | 5 | 211 | copy queued | 40580671 |
| B08 | RSNA 2022 cervical, RibFrac zips, spondy\_landmark | 3 | 203 | cut over: the 203 GB RSNA zip and 79 GB of RibFrac zips on Ceph, symlinks at the old paths | 40580672 |
| B09 | FluoroCap and FluoroGen | 7 | 316 | copy queued | 40580673 |
| B10 | Single-source derived banks | 64 | 80 | waits for B02, B04, B06, B07 |  |
| B11 | Banks of several sources, review packs, identity tables | 64 | 176 | waits for B10 |  |
| B13 | nnU-Net results, ablations, bench: results, not imaging | 3 | 627 | not started; Greg decides |  |
| B14 | The fifteen formerly unidentified home entries, identified 8 Oct: six imaging items move (Mendeley 5jdfdgp762 set, the v11 build workspace, the 10 Sept spinopelvic test copies with their scripts, the June QC archive, the BUU renders); nine stay (code, documents, simulation files, the token file) | 9 |  | verified, all nine items; cut-over queued, then the folders open to students with the v11 workspace and the BUU renders kept owner-only |  |

Each batch is cut over as soon as its copy verifies, and finalized, which deletes the home copy, only after a second comparison. The live state is `data_platform/plan/runs/<batch>/STATUS` on the grid.

## What the census settled

The Ceph walk finished on 8 October 2026 at 02:49; the home walk is still running in two jobs, one inside FluoroCap since 23:17 the night before and one through the rest, so the home figures below are partial. Sizes are apparent bytes.

| Finding | Number | What it changes |
| --- | --- | --- |
| The Ceph volume holds 7.7 TB in 5.66 million files, of which `data/` is 5.33 TB | 7,691 GB | more than the 6 TB reported by df-ceph; the difference is apparent versus allocated bytes |
| Non-imaging work on Ceph: the u251 RNA-seq and multi-omics folders | 2,205 GB | outside this plan; it is where a third of Ceph's use sits |
| The largest imaging folders already on Ceph: or\_ready 868 GB, COBRA2026 809 GB, IDC 706 GB, AbdomenAtlas 3.0 Mini 571 GB, FDG-PET-CT-Lesions 394 GB, anomaly\_harvest 326 GB, external 263 GB, PANORAMA 194 GB | 4,131 GB | they stay where they are and get their README.yaml |
| The home copy of CTSpinoPelvic1K's build data was reclaimed: `~/CTSpinoPelvic1K` is 7.7 GB in 4,541 files, not the 1.9 TB of September | 7.7 GB | batches B01 to B03 shrink to what remains |
| `~/data/CTSpinoPelvic1K`, the 802 CTs and labels, is 196 GB and is now the only home copy, since the tree it was hard-linked from isis gone | 196 GB | it moves as its own item, no longer as a hard-link group |
| Home `data/` is 624 GB: RSNA 2022 zip 203 GB, CTSpinoPelvic1K 196 GB, TotalSegmentator v3 90 GB, RibFrac zips 79 GB, TotalSegmentator v2 56 GB | 624 GB | batches B07 and B08 are sized |
| VerSeFusion on home is 195 GB, larger than the 139 GB of September | 195 GB | batch B06 is sized |
| Results on home: ablate 202 GB, bench 36 GB; the nnU-Net results are still to be walked | 238 GB so far | batch B13 awaits a decision |
| Still to be walked: FluoroCap, spine-detector, spinesurg-ct-nnunet, nhanes\_pseudo, vindr\_pseudo and the rest of the lowercase entries |  | these hold the other 2 TB of home's 4,050 GB |

When the home walk ends, the plan is regenerated from the census, the batch table in this report is replaced with measured sizes, and the fifteen unidentified entries are looked at.

## Student access

Every approved student reads the whole holding except the two sets held under an agreement. Access rides on the lab's existing gate: an approved AccessID gets a named entry on the volume root, which the access service keeps in step with approvals every 15 minutes, and below the gate the data folders are readable by others. `go2432/` and `go2432/data/` already carry read and traverse for others.

| Who | What they can read | How |
| --- | --- | --- |
| Approved students | every source folder under `data/` that is not restricted, including the CT releases, the anomaly-harvest CTs, the real X-ray and fluoroscopy sets, the plain-film corpora and the render banks | the named entry on the volume root, then read permission for others on each folder, applied as each batch is cut over |
| Approved students | the index database and each folder's `README.yaml` | the same, under `data/index/` |
| Nobody but the owner | VinDr-SpineXR, held under a named-person PhysioNet data-use agreement, and BUU-LSPINE, whose EULA forbids redistribution, and every bank that holds their pixels | mode 0700 from the first byte of the copy |
| Group oschome only | nothing extra: the group holds two people and is C&IT's to change |  |

The two restricted sets stay closed until their agreements say otherwise; a student who needs them applies for their own credentialed access, and the index still lists them so the holding reads as one. The first pass ran on 8 October 2026 at 06:29 over the folders already on Ceph: 53 opened, VinDr closed, and a file sampled from every opened folder read back as readable by others. Each cut-over from here applies the same policy to its batch.

## Decisions only Greg can make

The plan moves everything and deletes nothing beyond the verified home copies. Each row below is a choice the plan leaves open; the migration does not wait on them.

| Decision | Options | What the plan does meanwhile |
| --- | --- | --- |
| Delete the regenerable or superseded copies after the move: FluoroCap's youtube frames (181 to 265 GB), the RSNA 2022 zip (203 GB, used by nothing), implant\_verse (187 GB, regenerable), the extracted NHANES pickles (159 GB, regenerable from a 1 GB zip), the scaling-curve subset banks (129 GB, regenerable), the TotalSegmentator zips kept beside their unpacked trees (61 GB), ten superseded crop banks | delete after the Ceph copy verifies, or keep | moves them like everything else; MIGRATION\_PLAN.md section 8 lists all 50 rows with their reasons |
| Batch B13: nnU-Net results, ablations and bench, 627 GB of results rather than imaging | move to Ceph under results, or leave on home | not started |
| VinDr-SpineXR and BUU-LSPINE and every bank holding their pixels | owner-only as copied, or group-readable for the two people in oschome | owner-only |
| Licence conflicts: CTPelvic1K (CC BY or NC), VerSe (CC BY or CC BY-SA), DeepFluoro (CC BY-NC or CC BY-NC-SA), Geneva hip (CC BY-SA or CC BY-NC), Ljubljana (CC BY-NC-ND or a generic link), SpineSAC (none stated) | settle each against the release page before the index marks anything redistributable | the index records both readings and marks redistributable as unknown |
| The 15 formerly unidentified home entries, now identified from their own files on 8 October 2026: spondy\_landmark is the Mendeley 5jdfdgp762 film set (url.txt, files.json with the zip's sha256); s1v11 is the CTSpinoPelvic1K v11 build workspace with the S1 merge scripts, the v11 labels and the Zenodo upload logs; pitest and pdwtest are the label copies behind the 10 September pelvic-incidence and pedicle-width investigations (pi\_ostk2.csv, pdw\_why.py); dis\_renders is five BUU film renders from August; qc.tar.gz is the June build QC images; Multi-View-Vertebra is a cloned MICCAI 2023 reference repository; docs is a February 2026 weak-label document package; 3, 6, ada, output and v are GOMC and CHARMM simulation files from 2023 and 2024; morphdef is an empty scaffold; github is a plain-text access token | rotate and delete the token; approve deleting the empty scaffold and the two label-copy test folders | the imaging items (Mendeley set, v11 workspace, QC archive, renders, test copies) move to their source folders; the code, documents and simulation files stay on home |
| Folders already on Ceph keep their old names (idc, geneva\_hip\_src, ljubljana, thoracic\_xr, ctpelvic1k\_clinic, external) | keep, or rename to the source ids in a later pass | kept, because tools and chains name them |
| Pin the Hugging Face routes to a revision: AbdomenAtlas 3.0 Mini, CTSpine1K and the spinopelvic-seg checkpoints resolve `main` at fetch time | pin now, or accept that a re-acquisition may not be bit-identical | unpinned |
| TotalSegmentator subject aliases: ids s1406 to s1429 in v2.0.1 are byte-identical to different ids in v3.0.0 | build the alias map, or key by release id and accept up to 24 merged or split people | keyed by release id |

## Unknowns and sources

The manifest marks every fact no file records as not recorded rather than guessing. The ones that matter most for the index and the move:

- Patient position is not recorded for TotalSegmentator, VerSe, the non-COLONOG part of CTSpine1K, RibFrac, RSNA 2022, CTPelvic1K and every anomaly-harvest CT; the index reads it from DICOM headers where a header exists and writes unknown elsewhere.
- The exact download day of TCIA CT COLONOGRAPHY (April 2026) and the Hugging Face revisions of CTSpine1K and AbdomenAtlas 3.0 Mini at fetch time.
- The download scripts for TotalSegmentator v2 and v3 and for the RibFrac zips exist only as logs on the grid, not in either repository.
- What `~/data/spondy_landmark` is, and the contents of `VerSeFusion.tar.gz` and the stray file `VerseFusion`.
- Which 101 of the 3,600 IDC series failed conversion, the per-collection screen results that live only on Ceph, and whether the CURVAS zip repair chain succeeded.
- The release imaging dates of most sources; only Barts, Merlin, Ljubljana and C-ArmLSpine carry them.

Sources this report rests on, all in `spinesurg-ct-nnunet`: `data_platform/DATA_MANIFEST.md` and `sources.yaml` (the cards and their 469 cited paths); `docs/DATA_ACCOUNTING.md`, `docs/DATASHEET.md`, `docs/DATA_COMPLETENESS_AUDIT.md`, `docs/CT_INVENTORY.md`, `docs/XRAY_DATASET_USAGE.md`, `docs/RSNAI_DATA_MANIFEST.json`, `SchwingNet/results/transitional_registry/acquisition/` (the acquisition plan and ranking), the fetch tools under `tools/`; in `CTSpinoPelvic1K-1`, `paper/mpda/REPRODUCE.md` and the download scripts; the storage census of 7 and 8 October 2026 under `data/inventory/census_2026-10-07/` on Ceph; `pan_quota` and `df-ceph` read on 7 October 2026.
