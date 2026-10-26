# Exact fetch sizes: what was verified for the size rule's readers (#163)

Source: the project thread "Add fetch size readers for #163", 2026-10-26, from the adversarial review of pull request #400 and the research made for it. The generic account of how each service states a file's size before a download, with its sources, is symphony-template's docs/research/file-size-before-download.md; this note keeps what is this repository's own.

## Verified

- PhysioNet's project API: `GET https://physionet.org/api/v1/projects/<slug>/versions/<version>/` answered live on 2026-10-26 with main_storage_size and compressed_storage_size, so PHYSIONET_API in tools/fetch_sources.py is the path that answers. The review's finding that the published-project path might be another was settled by that request.
- redivis-python 0.21.1, read from its source: Export takes (id, *, table, query, upload, properties) and make_request takes (*, method, path, query, payload, ...), the shapes grid/redivis_fetch.py calls; File.path and Directory.path exist, and Directory.download lands each file at the destination under its path relative to the directory's; a file fetched again is streamed over in place, so a partial file saves what it holds, as still_to_land counts.
- gdown 6.4.2 writes the whole file into a temporary beside the output and renames it over what is there, so a resend needs all of it; the kaggle 2.2.5 client names a competition's archive from the final address of the download, after every redirect, which grid/fetch_size.py follows too since the review; huggingface_hub resumes a .incomplete file.
- The stages' container (grid/box.sh: an Apptainer sandbox with the lab volume and /dev/shm bound) has no squeue, no Slurm configuration and no munge socket, so the size rule cannot decide inside it. grid/01-fetch.sbatch runs tools/fetch_sources.py under the node's own Python (FETCH_PYTHON, else the acq environment's) and grid/02-bank-ingest.sbatch decides the chain's recipes before it execs the launcher; the helpers and the bank tool still run under PYDRV. Read from the scripts; not yet run on the grid.

## Not verified from the container

- Whether academictorrents.com answers a one-byte range request for a .torrent with a length; tools/fetch_sources.py counts TORRENT_BOUND (64 MB) for the file where it does not, since fetch_torrent reads it whole whatever the server says.
- The shape of Kaggle's redirect for a competition's download-all: whether the API's Location is the storage object itself or another kaggle.com address first. The reader names the landing from the final address either way.
- Whether Redivis's export answer states a size before the export has finished, and whether it deduplicates or bills the exports the size read and the download each build.
- That the acq environment's Python on the grid is 3.9 or later, which tools/fetch_sources.py needs; grid/01-fetch.sbatch checks and, where it is not, refuses the job with nothing fetched. The first fetch the owner sends settles it.

## What the review changed

The review of #400 found 21 points, each checked by skeptics; the pull request's body lists them with what was done. Beyond the container finding above: a set refused or failed on a requeued job settles the admission its first run gave it; a set on disk whole, whose hold the chain's bank job keeps, is not decided again on a requeue; a hold's base is the larger of what the landing shows and the admission's base with the set's bytes, since CephFS folds the last bytes into ceph.dir.rbytes with a lag of seconds; an admission another live job holds on a set is refused, never written over; an answer cut short and a reader's unforeseen failure refuse one set in place of ending the run; OUTSIDE_SLURM=1 no longer lifts the rule inside a job; the gate's fetch word waits for an unpacking, a look or a deletion of zips in the set, and its unpack word for the chain's bank job.
