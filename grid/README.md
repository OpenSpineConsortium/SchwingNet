# The X-ray data chain on the grid

One paste in the grid's shell fetches the open X-ray datasets of docs/research/xray-datasets-missing.md and the data platform's own unfetched sources onto the data root, turns each X-ray copy into a bank in the builders' format, ingests every bank into a content-hashed shard, and rebuilds the read-only catalog with its split check (docs/research/data-catalog.md). Nothing here runs on the login node: the two submit scripts call sbatch, df and awk and nothing else, and every byte moves inside a Slurm job on the reqp partition with --qos=requeue, each stage chained with afterany so a failed source strands nothing behind it. Written 2026-10-21 for issue #38; no job has run yet, so every number below is what the lists state and nothing is measured.

## What to check first

1. The volume's free space, which both submit scripts read themselves and refuse to exceed minus a 5 TB margin (5 TB, not 1, because acquisition_fetch.sh stops its own job under 5 TB free): `df -h /rs/rs_grp_oschome`. The X-ray chain states 21 GB where a size is known (CathAction 14.2, IPCAI 6.7) and ten entries state none (NIH ChestX-ray14, 42 GB, is skipped until its URLs and md5s are copied from the Box page into the entry; LUMOS, 46.4 GB, is fetched once, by the platform chain as zenodo_lumos, and banked from that landing); the platform chain states 1,489 GB, of which AbdomenAtlas 2.0 Mini is 620, STOIC2021 240, LIDC-IDRI 123 and VSDFullBody 116; the opt-in MIMIC-CXR-JPG alone is about 570 GB and CT-RATE 21.3 TB, each its own line below and never in a chain.
2. The checkout on the grid: `cd ~/SchwingNet && git pull` (another path goes in `SCHWINGNET=<path>`), with the pixi environment installed there once (`pixi install --locked`, which gives stages 2 and 3 pydantic, beartype and icontract; `pixi install --locked -e train-cpu` as well, which adds Pillow, so a JPEG, TIFF or BMP set can be banked: the submit script prefers .pixi/envs/train-cpu/bin/python when it exists, else .pixi/envs/default/bin/python, else python3, which stage 2 then reports as lacking pydantic). The hf-get helper runs under the data platform's acq environment (/rs/rs_grp_oschome/go2432/envs/acq/bin/python), which holds huggingface_hub.
3. The helpers' clone: `~/spinesurg-ct-nnunet` at main (data_platform/reacquire/reacquire.py, tools/acquisition_fetch.py, slurm/acquisition_fetch.sh), and its acq environment at /rs/rs_grp_oschome/go2432/envs/acq (idc-index, s5cmd, gdown; `bash ~/spinesurg-ct-nnunet/slurm/acquisition_submit.sh env` makes it where it is missing).
4. Tokens, each in a file only you can read, never on a command line: the Kaggle token as a line `KAGGLE_API_TOKEN=...` in `~/.fluorocap/credentials.env` (mode 600; the RSNA 2022 fetch used the same file) for kaggle_scoliosis_yolov5 and rsna_rspect_pe; PhysioNet's sign-in as `machine physionet.org login <you> password <...>` in `~/.netrc` (mode 600) for the opt-in list; a Hugging Face token as `HF_TOKEN=...` in `~/.hf/token.env` (mode 600) for CADS and CT-RATE; the RSNA RATIC presigned link, good until 2026-10-28 02:38 UTC, as the one line of `~/.rsna/ratic_link` (mode 600). `chmod 600` each; the jobs refuse a file anyone else can read.
5. The "to confirm" fields: grid/fetch-xray.json lists per entry what to read on its page (the licence, a record number, a download link), and grid/banks/<id>.json stops stage 2 for that source until each field spelled "to confirm" is filled in. Two X-ray entries fetch nothing until their link is in the file (vfss2022, isbi2015_cephalograms) and one until its Zenodo record number is (vertxnet_nhanes2_labels); the chain skips them with one line and goes on.

## The paste

```
cd ~/SchwingNet && git pull && df -h /rs/rs_grp_oschome && bash grid/run-platform-fetch.sh && bash grid/run-xray-chain.sh
```

That submits the data platform's chain (25 jobs, one per source, each afterany on the one before) and the X-ray chain (three jobs: fetch, bank and ingest, catalog), prints every job id with its dependency and an ETA, and writes them to grid/LAST_RUN.txt. The two chains are independent and run side by side. `squeue -u $USER` watches them; the X-ray stages each write one report, grid/logs/01-fetch-STAGE-REPORT.md, 02-bank-ingest-STAGE-REPORT.md and 03-catalog-STAGE-REPORT.md, and each platform job logs to grid/logs/dp_fetch_<id>_<job>.out with a README.yaml written at its landing. Add `--only <id,id>` to either script for a part, `--credentialed` to the X-ray chain for the PhysioNet opt-in list, `--gated` to the platform chain for the granted gated sources (CADS CT-TRI, RSNA RATIC, RSPECT), and `SBATCH=echo` in front of either for a dry run that submits nothing.

The lines never in a chain, each one job you run or skip:

```
# MIMIC-CXR-JPG, about 570 GB, credentialed: alone, after df shows the room
cd ~/SchwingNet && bash grid/run-xray-chain.sh --credentialed --only mimic_cxr_jpg
# VinDr-CXR (about 180 GB) and VinDr-PCXR (about 30 GB), credentialed, DICOM (banked only once pydicom is locked)
cd ~/SchwingNet && bash grid/run-xray-chain.sh --credentialed --only vindr_cxr,vindr_pcxr
# CT-RATE, 21.3 TB, gated: not before your TB number; the token in ~/.hf/token.env
cd ~/SchwingNet/grid && ID=hf_ct_rate ROUTE=hf-token ARGS='--repo ibrahimhamamci/CT-RATE --repo-type dataset --include .' LICENCE='CC BY-NC-SA 4.0' ACCESS=gated TOKEN_FILE=~/.hf/token.env sbatch -D "$PWD" --job-name=dp_fetch_hf_ct_rate --export=ALL platform-fetch.sbatch
# NLST full, 24,713 subjects, 2.3 TB, refused as it stands by the stopping rule
cd ~/SchwingNet/grid && ID=idc_nlst ROUTE=idc ARGS=nlst LICENCE='CC BY 4.0' ACCESS=open sbatch -D "$PWD" --job-name=dp_fetch_idc_nlst --export=ALL platform-fetch.sbatch
```

## What the X-ray chain does

Stage 1, grid/01-fetch.sbatch (4 days of wall time, requeued on preemption): `tools/fetch_sources.py --run` reads grid/fetch-xray.json and runs one helper per entry, the data platform's own reacquire.py (zenodo-get, which verifies the record's md5 per file; hf-get, which verifies the LFS sha256; http-get, which resumes a .part), Mendeley's public API listed and then http-get per file with the sha256 the API gives, the Kaggle CLI with the token from the file, or wget -r -N -c -np with the login from ~/.netrc for PhysioNet. Every entry lands at /rs/rs_grp_oschome/go2432/data/<id>/raw, the folder its registry entry names; the helper's state is <id>/fetch-state and the record <id>/FETCH.json: what ran, the exit codes, the byte count and the sha256 of every file, computed after the download. A failed entry is reported and the next runs; the stage exits 1 at the end when any failed, and stage 2 still runs on what came.

Stage 2, grid/02-bank-ingest.sbatch: for each recipe grid/banks/<id>.json whose raw folder holds anything, `tools/bank.py --run` writes the bank under <id>/bank (images/train/<stem>.png, meta/<stem>.json with the case, the device, the view and the boxes), then `tools/ingest.py run --bank <bank> --source <id> --kind train --split train --date <today> --code-commit <sha> --person-prefix <prefix>` cuts the shard under <id>/shards/<date>-<12 hex>/. PNG is copied byte for byte, so the shard's name is the raw bytes' content; JPEG, TIFF and BMP convert through Pillow in the train environment; the same bank twice is "already there". The ingest refuses a frozen test person in a train shard and the same bytes under two persons, as docs/research/data-catalog.md says.

Stage 3, grid/03-catalog.sbatch: `tools/catalog.py build --store /rs/rs_grp_oschome/go2432/data/_catalog --manifest <every MANIFEST.json under <data root>/*/shards/*/>` and `split-check` on the new version; a build whose bytes equal the latest is reported as not new. A failed split check exits 1 and no training step reads that version.

Each source's registry entry, data/registry/<id>.json, was written with the chain: the identity level, modality, device class and regions as the sweep read them, every one marked in its notes where the page has not been read, and the person-key rule pointing at the recipe. VertXNet's persons carry the prefix nhanes2, so a NHANES II person is one person across its sources.

## What the platform chain does

grid/run-platform-fetch.sh submits one grid/platform-fetch.sbatch per source of spinesurg-ct-nnunet's data_platform/sources.json at bf1432f that is not on the grid, in this order: STOIC2021 (s3, 240 GB), the two IDC spine collections (spine_mets_ct_seg, spinal_multiple_myeloma_seg), MedPelvis3D, LumVBCanSeg, LUMOS (the version record 18173664, CT zips and the 1,620 radiographs; grid/banks/lumos.json banks the radiographs from this landing, so the record is on disk once), the three TotalSegmentator task sets (fetched into raw with the overlap question written into their README.yaml, out of every split until the authors answer), the TMTV benchmark, the CT Colonography verify run, the cm_spine Google Drive file (gdown into a dated scratch folder under its raw, then file(1) on what came), the ScienceDB probe (curl -I only: whether a login is asked), the VerSe note, the seven other IDC tier-2 collections, UniToChest, VSDFullBody, AbdomenAtlas 2.0 Mini and LIDC-IDRI last. The IDC route writes the collection's manifest from idc-index itself (grid/idc_manifest.py, every CT series of the collection) and hands it to acquisition_fetch.py idc, which verifies each series by its instance count; the zenodo, hf and s3 routes are acquisition_fetch.py's, md5, LFS sha256 and object count, never size alone. Every landing is /rs/rs_grp_oschome/go2432/data/<source id>/raw with a README.yaml as data_platform/LAYOUT.md says, written once and never overwritten.

With `--gated`: CADS (parts CT-TRI first, VISCERAL as a second run with `--include VISCERAL*`), RSNA RATIC through its presigned link read from the file into a curl config, and RSPECT through Kaggle. CT-RATE and NLST full are printed, never submitted.

The 10 VerSe'20 series never downloaded (verse020, 112, 139, 141, 151, 202, 235, 251, 257, 290) need the VerSeFusion clone on the grid, whose slurm/download_raw.sh is the osf_verse route: the chain prints that note and `python3 -I ~/spinesurg-ct-nnunet/data_platform/reacquire/reacquire.py --grid verse19_20` gives the line once the clone is there.

## Your hand only

- Stanford AIMI Merlin and INSPECT: sign in and accept the research-use agreement at https://stanfordaimi.azurewebsites.net/datasets/60b9c7ff-877b-48ce-96c3-0194c8205c40 (Merlin also at https://stanford.redivis.com/datasets/exfv-e8h3kvfhs); the portal issues a time-limited Azure Blob URL for AzCopy, which then goes in a file for a curl-link job as RATIC's does.
- MAGIC-CT (Zenodo): the record's data-use application with CITI proof, yours to file; the files download without a gate afterwards.
- TVGH-SpineXR: IEEE DataPort access for doi:10.21227/x6bb-7r75 (https://ieee-dataport.org/).
- SX-Stitch and Balgrist ex-vivo: the letters docs/data_requests/SX-Stitch_request.md and docs/outreach/balgrist_data_request_2026-09-21.md in spinesurg-ct-nnunet, to the authors (the cine letters went on 2026-10-20).
- BUU-LSPINE's full set behind its EULA.
- MrOS and SOF (https://mrosonline.ucsf.edu/, https://sofonline.ucsf.edu/): the research data requests the sweep ranks first.
- PhysioNet: the agreement per project (vindr-cxr, vindr-pcxr, mimic-cxr-jpg) under your account before their opt-in lines run.

## Re-running one source

- Fetch again: `bash grid/run-xray-chain.sh --only <id>` (the helpers resume their .part files and skip verified units) or `bash grid/run-platform-fetch.sh --only <id>`.
- Bank and ingest again after a recipe was filled in: `cd ~/SchwingNet/grid && ONLY=<id> PYDRV=$HOME/SchwingNet/.pixi/envs/default/bin/python sbatch -D "$PWD" --export=ALL 02-bank-ingest.sbatch`, then `sbatch -D "$PWD" --export=ALL 03-catalog.sbatch`. A bank already written is kept where its bytes are the same; a raw file that changed under a stem is refused by name, since a changed raw copy is your call.
- The dry run of any of it: `SBATCH=echo bash grid/run-xray-chain.sh` in the grid's shell (bash only); `python3 tools/fetch_sources.py --only <id>` and `python3 tools/bank.py --recipe grid/banks/<id>.json` (a plan, nothing written) on your laptop or inside an interactive job (`srun -p reqp --qos=requeue --pty bash`), since the login node kills python by name.

## What the chain does not do

- No DICOM: pydicom is not in pixi.lock, so LUMOS's radiographs, VinDr-CXR and VinDr-PCXR are fetched and refused by stage 2 with that message; a change of its own locks pydicom and teaches tools/bank.py the pixel array.
- No gated set without its agreement and no credential of yours in any file of this repository: the credentialed and gated lines run only when you name them and their token file is in place.
- Nothing deleted, ever: a fetch resumes, a bank keeps what matches, a shard that exists is "already there", and a catalog version is never rewritten.
- No training step: the split check is the last thing the chain runs.
- No guessing: a recipe field spelled "to confirm" stops that source, an entry whose link is not in the list is skipped with one line, and the Kaggle scoliosis set is banked only after its sha256 list in FETCH.json is compared with the AASCE copy on the grid (the two paths are in its entry); a match means no new person and the source is left out; NIH ChestX-ray14's twelve URLs stay under urls_unverified until the Box page's batch_download_zips.py has been copied into the entry.
- Nothing measured: every size is what a page or a card states, and the ETA is one hour per 20 GB, a guess until the first log says otherwise.
