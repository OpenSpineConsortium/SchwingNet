# Radiopaedia paired cases: a CT and an X-ray of one person, saved by hand

Source: the owner's local Claude Code session of 1 November 2026, on his words that night, "now that i have a radiopaedia license include that as a source for data; either paired ct-xray or just xray". The licence is agreement 202610-9517 (data/sources/radiopaedia.json, docs/memory/radiopaedia-by-hand.md). This page was written without opening the site: no session reaches Radiopaedia by script, so what it says of the case page is what the owner will check by eye, and nothing here fetches, scrapes or automates anything there.

## What is saved so far (1 November 2026)

Nothing yet. On the grid the data root holds no Radiopaedia folder (the two names there with "radio" in them are the IDC lung sets idc_nsclc_radiogenomics and idc_nsclc_radiomics), and nothing named for Radiopaedia lies within three levels of the owner's folder on the lab volume. On this machine's OneDrive the one Radiopaedia folder is Desktop/CTSpinoPelvic1K-1/radiopedia/, which holds a single folder, compression-fracture-with-vertebral-body-stenting, made on 26 September 2026, before the agreement, with no file in it; no folder anywhere in the OneDrive is named by an rID. The registry's radiopaedia_fluoro and radiopaedia_xr have no shard. So every case below is still to be saved.

## How to save a paired case by hand

A case page has the case's text, a viewer with one or more studies, each labelled with its modality (CT, X-ray, fluoroscopy, MRI) and holding one or more series (axial, sagittal, coronal for a CT; frontal and lateral for films), and a citation block that gives the case's rID (its DOI ends in `rID-` and the number). Save the images one at a time with the browser's own Save image command, at a person's pace, as clause 3 of the agreement asks. Where the viewer does not offer an image that way, that image is not saved: no browser extension, download manager, developer-tools copy or anything else that saves a page's images in bulk, since each is a script by another name and the site's refusal of scripts is never got around.

Lay the saved files out by group, then by case, the case folder starting with its rID:

    <saved>/ct/<rID>-<slug>/<series>/<n>.jpg     the CT's slices, one folder per series saved
    <saved>/xr/<rID>-<slug>/<any name>.jpg       the case's plain films
    <saved>/fluoro/<rID>-<slug>/<any name>.jpg   or its fluoroscopy, never both

- A CT slice is named by its one number, the place the viewer gives it in its series (12.jpg, or slice-012.jpg). A name with no number, or with two (the browser's "12 (1).jpg", or "12 of 87.jpg"), is refused, since the order of the stack would be a guess; so are two slices of one number, and the same slice saved under two numbers.
- A series folder is named in letters, digits, - and _ (axial, sagittal, coronal-bone). A CT with one series saved may put its slices straight in the case folder; a case may not mix loose slices with series folders.
- The slices need not be every slice of the series: the numbers keep each one's place, gaps included. For level truth the sagittal series across the midline and the coronal slices that show the ribs and the transverse processes are what a reader needs; a whole axial stack is not.
- One case is one X-ray group. The two banks key a person by their own source (`radiopaedia_xr:<rID>`, `radiopaedia_fluoro:<rID>`), so a case under both would be two persons to the person-keyed split, which could then put one person on both sides of it. Choose the films or the fluoroscopy.
- A CT's scout (the localiser), where a case shows one, is a projection and not a slice: leave it out of ct, and out of xr too for now, since the xr bank is read as film.
- Every file inside a case folder must be a JPEG; Windows' Thumbs.db and desktop.ini there are refused by name, so delete them first.

Then, on the owner's own machine, `python3 tools/radiopaedia_import.py plan --from <saved> --to <out>` reports what it would keep, and `run` writes radiopaedia_ct/, radiopaedia_xr/ and radiopaedia_fluoro/ under `<out>`, each image named by its bytes (a slice by its number and its bytes), with CASES.csv, PAIRS.csv and SHA256SUMS. PAIRS.csv lists every rID held both as a CT and as an X-ray, with its CT series and slices and its X-ray group and frames. The folder reaches the grid as a carried folder (grid/carry/README.md); the films and fluoroscopy are banked and ingested, and leak-checked against every held shard before any frame enters a test split (grid/run-leaks.sh), since public sets reuse Radiopaedia images.

## What a paired case gives, and what it cannot

It gives level truth for the X-ray from the images themselves. A reader counts the CT's vertebrae from an anchor the field shows, C2 counted down or the ribs counted to T12, to the sacrum, and names its transitional anatomy (a lumbosacral transitional vertebra and its Castellvi type, an eleventh or thirteenth rib pair, a cervical rib); then carries that naming to the same person's X-ray through a feature both show, the transitional segment itself, the last rib, a fracture, cement or a screw. That is the case the project's level naming most often gets wrong, and Radiopaedia's teaching cases are rich in it. The truth comes from the images and not from the case text, which matters: the agreement's approval says that multimodal use of case and article text needs Radiopaedia's written confirmation first (data/sources/radiopaedia.json).

A pair is only as good as the CT's field. A CT that shows neither C2 nor enough ribs to know T12 names its levels by the same assumption the X-ray makes, and adds no truth to a transitional case; save those last.

It cannot give landmarks or measurements. Radiopaedia supplies no DICOM: a saved slice is an 8-bit JPEG, windowed by its contributor and at whatever size the site serves, with no voxel spacing, no slice thickness and no distance between slices, so the stack is no volume the morphometry engine (grid/bordercall/morphometry/) can read in millimetres, and its constructions, the plates' corners among them, cannot be built from it. The X-ray is unposed: no pose of its source and detector, no source-to-detector distance, no pixel spacing, and often a different day from the CT. The owner's rule of 29 October 2026 takes corners and landmarks only from the engine's constructions, projected; projecting them onto a Radiopaedia X-ray would need a 2D/3D registration, and that registration needs the CT's spacing, which the JPEG stack lacks. Scaling the stack by an anatomical prior (a mean body depth from Panjabi) would make any measurement taken from it circular, so it is not done. A paired case is therefore level truth and named anomalies at the case level, never projected landmarks and never a Bayesian measurement in millimetres; those stay with DeepFluoro's CTs and the CT corpora.

Radiopaedia's cases are chosen to teach, so they are rich in the rare and say nothing of how common anything is: a result on them is its own row, for the hard cases, never pooled with the held-out C-ArmLSpine, and never read as a prevalence.

## How many cases make a useful test set

The unit is the case, one person, whatever the number of films it holds. By the project's Wilson rule (schwingnet.flow.wilson, 95 percent, the eval gate's interval; the numbers below are its output for these counts):

- 30 paired cases all named right give 0.886 to 1.000, so 30 cannot yet show better than 90 percent.
- 35 is the fewest that can show better than 90 percent, and only when every case is right; better than 95 percent needs 73 all right.
- At 90 percent named right, 50 cases give 0.786 to 0.957 and 100 give 0.826 to 0.945; at that rate the lower bound first passes 80 percent between 60 cases (0.799) and 80 (0.815).

So a first paired test set worth reporting is about 50 cases, of which the transitional ones are a stratum of their own read by two readers, as the project's transitional stratum is; 100 makes a 90 percent result an interval about 0.12 wide. Any case meant for the test set is frozen as a test person (data/splits/test-persons.json, by pull request, as C-ArmLSpine's L6 persons are) before any run trains on the bank, and its shard is cut apart from the rest with ingest's --kind test --persons frozen, since the catalog refuses a train shard that holds a frozen test person (tools/catalog.py, refuse_mixed_shard).

## Which cases to save first

1. Transitional vertebrae with a CT and a film of one person: the site's own search for lumbosacral transitional vertebra, sacralisation, lumbarisation, Castellvi, Bertolotti syndrome, thoracolumbar transitional vertebra, supernumerary or hypoplastic twelfth rib, cervical rib. These name levels on a CT and an X-ray of one person, the question the project exists for.
2. Fractures with both: compression, burst and Chance fractures, and vertebroplasty or kyphoplasty, whose cement marks one level in both images, so the CT's naming reaches the film with no doubt at that level (the empty folder on the OneDrive was such a case).
3. Scoliosis and segmentation anomalies: scoliosis with whole-spine films, hemivertebra, butterfly and block vertebrae, Klippel-Feil, whose counts differ from the usual and whose films span long fields.
4. Postoperative spines with screws or a fusion on both, and the fluoroscopy cases first identified (rID 24796, 90103, 21585 and four fluoroscopy-guided injections) wherever they carry a CT.

## What is still needed

- No registry entry or bank recipe for the ct group. data/registry/ and grid/banks/ hold 2-D frame sources (their modalities are cr, dx, rf, xa, render and a CBCT projection; none is a CT), and the project's CT store (tools/gold3_ct.py) holds volumes with their spacing and label maps; a JPEG stack fits neither, so the slices land as raw files beside the films and are read by a person.
- A readers' file for the paired cases, not built yet: per case its rID, the CT's counting anchor, the count of lumbar-type vertebrae, the transitional anatomy and its type, and per X-ray image (by its sha256 prefix) the levels the reader carries onto it, with a second reader for the transitional stratum; the bank's label kinds draw boxes, so the levels would enter as a case-level truth column rather than as boxes.
- The owner's saving, and his word on which cases are frozen for test before the first bank.
