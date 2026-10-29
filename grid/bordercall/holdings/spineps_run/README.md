# SPINEPS on CPU, for the gold tier 3 completion

The scripts that ran SPINEPS 2.1.2's CT models in a cloud container on 2026-10-29, on the owner's word
of 03:32 UTC ("segment the c2 and sacrums which are on ct volumes they just lack the masks and convert
them all to gold tier 3 data") and his choice at 04:23 UTC to run them there rather than wait for the
grid. They make the segmenter's masks that holdings/fullspine_complete.py reads; nothing here decides
which of SPINEPS's levels is kept. Confidential, like the rest of this repository: no CT or mask is
here, only how they were made.

| file | what it does |
| --- | --- |
| verse_ct_get.py | downloads the VerSe CTs a list names from OSF, each checked against its listed size |
| verse_ct_jobs.json | that list for the CTs fetched: id, release, file name, size, OSF link |
| ts_get.py | fetches chosen TotalSegmentator v3 subjects' CT and spine masks from the release zip by byte range, each file checked against the zip's central directory (a JSON list of its entries: name, offset, csize, usize, method) and its CRC |
| run_spineps.py | runs SPINEPS on one CT of a job list ({"id", "ct", "release"}), into OUT/id/, and writes its vertebra and subregion masks on the whole CT's grid under OUT/id/ctgrid/ with input.json saying how the CT went in |
| vibeseg_alone.py, fold_patch.py | SPINEPS's spine-finding step (VIBESeg) run first in a process of its own, holding one of its three folds' logits in memory at a time; its mask is SPINEPS's own bit for bit (on verse255, run both ways, no voxel of 38,398,530 differed) |
| run_all.sh | runs run_spineps.py one CT a process over a job list, then once more over the CTs that failed, and stops before starting a CT after STOP_AFTER seconds, so a run is resumed by starting it again |
| make_complete_jobs.py | the matcher's JOBS.json from SchwingNet's admission.json and facts: each study whose admission asks for levels, or holds its head end for a look, and whose masks SPINEPS has written |
| segmenter.json | the record copied into every row the matcher writes: SPINEPS's version, its models' folders and weights' sha256, the packages, how it was run |

## Why it runs the way it does

The container has 4 CPUs and 14.3 GB of memory. SPINEPS's spine-finding step holds a 73-class
prediction of the whole field, and on a 37 x 37 x 42 cm field it took 12 GB and was killed, so
run_spineps.py first cuts the CT to the box the release's own levels occupy, widened by 60 mm in the
plane and 200 mm along the head-foot axis, where C2 and the sacrum lie when the release does not draw
them. A CT whose slices are thicker than its pixels is resampled to 1 mm isotropic with cubic
interpolation, since SPINEPS's CT model refuses it, and the masks are resampled back nearest-neighbour;
input.json says which. The instance model runs one cutout at a time (four at a time took 13.8 GB).
From verse766 on, the spine-finding step ran alone first, since beside SPINEPS's three models already
loaded it passed the container's memory for verse108, verse649 and verse766; input.json's fold_patch
says so for each CT that ran this way, and verse561's spine-finding mask, made by SPINEPS's own process
at 12:18 UTC before fold_patch existed and reused after, says only that a mask an earlier run left was
reused.

## Running it

    PYTHON=<SPINEPS environment>/bin/python SPINEPS_SEGMENTOR_MODELS=<models> holdings/spineps_run/run_all.sh JOBS.json OUT

A CT took 10 to 35 minutes on 4 threads (607 to 2,057 seconds over the ten whose times the run's log
holds) at a peak of 11.6 to 13.0 GB. On the grid the census's SPINEPS masks are read instead, and
SPINEPS is never run there again (the owner's rule: SPINEPS's masks already on the grid are reused,
never re-run).
