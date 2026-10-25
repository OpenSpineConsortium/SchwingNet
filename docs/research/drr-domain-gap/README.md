# FleXray's DRRs beside every held X-ray corpus: maps and separation tests

The thread "Compare FleXray DRRs to real X-ray corpora", 2026-10-25, on the owner's ask of that day: "please plot the synthetix flexray DRRs alongside all the other Xray corpuses both plain film and fluoro in a tsne plot or other dimension reduction visualizations and do other statistical tests for separation that machine learning experts would do". Label: confidential-results. The design below is what the code does and may be described in public by its method alone (symphony-template's docs/research/drr-domain-gap-method-2026-10-25.md); the numbers it produces, which corpora it found separable and by how much, stay in this private repository, beside the FleXray audit (#391, docs/research/flexray-audit-companion.md), whose items 6 to 11 this study informs.

Where it stands: the code and its tests are written (tools/domain_gap.py, tools/domain_gap_stats.py, tools/flexray_render.py, src/schwingnet/domain_gap.py, data/domain_gap/groups.json) and nothing has run on the grid. It runs as one GPU job, the gate word `bench` with the id `flexray_drr_gap` (grid/bench.sbatch), once the owner gives the word and the count; FluXray, FleXray's own FLUX-edited DRR set, joins it only after the one fetch the audit plan already names (item 6, flexray-data), and is skipped with its reason until then. Section 6 is filled from the job's summary when it comes back.

## 1. The question, and what a reviewer would ask of the answer

How far are FleXray's synthetic DRRs from real X-rays, plain film and intra-operative fluoroscopy, and is that distance larger than the distance between two real corpora? A map alone answers neither: t-SNE draws clusters for any two sets with a consistent difference, however small, and its distances between clusters mean nothing. So the maps are drawn, as asked, and every claim is carried by a test with an interval and a calibration:

- a classifier two-sample test (C2ST): a classifier trained to tell the sets apart, scored out of fold with every person wholly on one side of each split, its AUC with a person-cluster bootstrap interval and a person-level permutation p-value;
- a kernel test: the unbiased MMD with a Gaussian kernel at the median distance, with a person-level permutation p-value;
- the generative-model distances, Frechet distance and KID, read in each space's first 64 principal components (FD64, KID64) so that every space is compared at the same dimension and with a stable covariance;
- precision, recall, density and coverage (Naeem et al. 2020), which say whether the synthetic images lie inside the real manifold and how much of it they cover, the two ways a renderer can fail;
- silhouette and neighbour purity of the groups, the share of each group's neighbours in each family, and which real corpus a classifier trained on the real corpora alone calls each synthetic group;
- the calibration: each group with at least 40 persons split in two by person, and every test run on the two halves, where it must find nothing. A split-half AUC whose interval excludes 0.5 means the pipeline leaks and the corresponding real-versus-synthetic number is not read.

## 2. The groups

data/domain_gap/groups.json, version 1, salt `schwingnet-drr-gap-v1`. Each group takes at most 1,000 images, chosen person by person in a salted order with a cap a person, so a corpus with many images of few persons cannot outweigh the others; the five frozen test persons of data/splits/test-persons.json are left out of every group.

| family | group | what it is | person |
| --- | --- | --- | --- |
| synthetic | flexray_drr | FleXray raw DRRs rendered in the job from held TotalSegmentator v2.0.1 CTs with FleXray's own nanodrr pose profile (250 CTs, four views each) | CT subject |
| synthetic | fluxray | FluXray, FleXray's FLUX.2-edited DRRs, read with FleXray's own ThunderDB reader once fetched | record subject |
| synthetic | ts_drr_project | the project's own DRRs of the same TotalSegmentator CTs (rare_class), so the pair with flexray_drr isolates the renderer | CT subject |
| synthetic | devcorpus | the project's device-pose renders, styled | CT subject |
| synthetic | fluorogen | the project's SDXL-styled synthetic frames | file |
| fluoroscopy | carmlspine_spots | C-ArmLSpine AP and lateral spot frames, one mobile C-arm | case |
| fluoroscopy | deepfluoro | DeepFluoro vendor fluoroscopy, cadaver pelvis | DICOM patient |
| fluoroscopy | geneva_hip | Geneva resin hip phantom (one subject: plotted, never tested) | one |
| film | vindr_spinexr | VinDr-SpineXR radiographs | DICOM study |
| film | buu_lspine | BUU lumbar radiographs (the 3600 release) | patient number |
| film | aasce | AASCE whole-spine AP | file |
| film | nhanes2 | NHANES II scanned lateral films, 16-bit | file |
| film | csxa | CSXA lateral cervical films | file |
| film | kub_stonex | KUB abdominal films | file |
| film | ieee_lateral | IEEE DataPort standing lateral whole-spine films | file |
| film | lumos | LUMOS lumbar radiographs, from its bank where built | patient number |
| film | aariz | Aariz cephalograms, skull with C2 to C4 | file |

Left out, each with its reason: fluoro_video_clips (its record allows tracker screening only, never training or a slide; a C2ST trains a classifier and the maps are figures), fluorocap (literature figure panels of mixed content, not X-ray corpora), carmlspine_sweeps (the frozen demo sweeps), spinesac and mendeley_5jdfdgp762 (reach excluded by their records), COBRA (linac CBCT projections in MetaImage, which nothing in the job reads, and not a C-arm), ljubljana_2d3d_gs (18 frames, under the 20 a group needs), the video files of dysphagiabank and bern_myelography (no decoder; a new dependency would be an issue first), and the archives never unpacked (nih_chestxray14, open_i_chest, ipcai2025_xray_ct, cathaction). A group whose files are its persons ("file") is flagged in the summary, since a grouped split then holds only files apart.

## 3. From file to feature

Every image, synthetic or real, takes the same path: decoded to floats (DICOM through its modality LUT, MONOCHROME1 turned bone-bright, a cine's middle frame; 16-bit PNG and TIFF at their depth), windowed to its own 0.5 and 99.5 percentiles as the bank does, cut to the centre square of 0.9 of its shorter side and resized to 256 with an area filter. Cutting a square rather than padding one keeps a pad's flat border, which only non-square images would carry, from telling the corpora apart.

Three feature spaces, so that no finding rests on one encoder's view:

- flexray: FleXray's flagship member (flux0375) at its own preprocessing, the spatial mean of the input to the last instance norm of its deepest encoder block. The output of an affine instance norm has the norm's learned shift as its spatial mean for every input, so pooling the block's output would give one vector for every image.
- imagenet: torchvision's ResNet-18 with ImageNet weights, its 512 pooled features, the conventional FID-style space.
- physics: handcrafted measures a renderer gets wrong first: the intensity histogram, the radial power spectrum's shape, the gradient histogram, the noise (a robust spread of the Laplacian at two scales and their ratio), local contrast, the shares near black and near white, the share of strong edges.

Fluoroscopy is often shown bone-dark and DRRs bone-bright, which any encoder separates at once. The primary reading is therefore inversion-invariant: each space's feature of an image is the mean of its features of the image and of its inverse. FleXray's space is also read as stored, as a secondary reading, to show how much of the gap polarity alone carries.

## 4. The analysis, and what was fixed before any number was seen

Per space: features standardised; the maps (PCA, t-SNE at perplexity 30 on PCA-50, UMAP with 30 neighbours on PCA-50, and LDA, which is supervised and labelled so), each but LDA with its trustworthiness against PCA-50, from at most 600 images a group; every synthetic group against each real group and against each pooled real family (300 images from each testable real group, so no one corpus outweighs the rest); every pair of real groups; pooled fluoroscopy against pooled film; the split-half nulls. The classifiers are logistic regression (scaler, PCA to 64, C 1) and 15 nearest neighbours, five person-grouped folds stratified by label; 1,000 bootstrap draws; 100 permutations of the C2ST against each family, 1,000 of the MMD everywhere. A group with fewer than 20 decoded images is left out, and one with fewer than five persons is plotted and never tested. Benjamini-Hochberg runs over every MMD p-value of a space and over its C2ST permutation p-values.

Primary endpoints, fixed now: in the flexray space, inversion-invariant, the logistic C2ST AUC of flexray_drr, and of fluxray once fetched, against pooled fluoroscopy and against pooled film, each with its interval; and FD64 of each against each family divided by the median FD64 between that family's own real corpora (the gap ratio, 1 meaning as far as two real corpora are from each other).

The words, fixed now and printed beside each primary number: "indistinguishable" where the AUC's lower bound is at most 0.6; "closer than two real corpora" where the lower bound is below the median AUC of the family's real pairs; "separable" otherwise. Everything else is secondary and read as description.

## 5. Limits known before the run

- The corpora differ in more than their realism: anatomy (cervical films, a hip phantom, cephalograms, abdomen), devices, eras and formats (JPEG re-exports, 16-bit scans, DICOM). A real-versus-real AUC near 1 is the expected baseline for many pairs, which is why the gap ratio and the words compare the synthetic distance with the real-real one rather than with chance.
- The renders follow FleXray's own pose profile, mostly frontal arcs over a wide field; the real spot frames are narrow and centred on the lumbar spine. The map shows the gap the renderer's own settings make, not one tuned to match the held frames.
- Persons are files in seven groups; their within-group test splits are by file.
- DeepFluoro has six specimens, so its intervals are wide.

## 6. Results

Not run yet.

## 7. How to run it

The grid job: the gate word `bench` with the id `flexray_drr_gap` (grid/bench.sbatch, grid/README.md), one GPU job on train-gpu with a pip environment built at job time (`flexray[train]==1.0.2 nanodrr==0.1.5 scikit-learn==1.9.1 umap-learn==0.5.12 numpy==2.4.6`), reading the sample index under `_samples/<CURRENT>/samples.sqlite`, FleXray's bundle under hf_flexray_weights/raw and torchvision's ResNet-18 file, writing under the job's run folder (umask 077). What leaves the grid is summary.txt, at most 80 lines of numbers and group names that the bench report carries; the figures and the map coordinates go to W&B (project SchwingNet, private) where the grid's key is found, and stay on the grid with results.json and the plan, which names files.

Locally: `python tools/domain_gap.py run --groups data/domain_gap/groups.json --data-root <root> --index <samples.sqlite> --weights <bundle> --imagenet <resnet18.pth> --out <dir>`; `python -m unittest tests/test_domain_gap_run.py tests/test_domain_gap_stats.py tests/test_flexray_render.py` in an environment with numpy, torch, scikit-learn and FleXray.
