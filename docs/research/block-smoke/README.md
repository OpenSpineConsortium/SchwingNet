# The block smoke test: every combination decided, every route run

Source: the thread "Build plug-and-play training experiment framework", 2026-10-24, the owner's asks of 21:11 to 21:20 UTC ("smoke test all possible combinations of the blocks on the grid", "start with whatever combinations will cover all possible routes of data through the workflow", "make sure i know that any combination of the blocks within fundamental constraints like incompatibility will work for any of the datasets i have available, and natively the annotated and unannotated datasets will be passed appropriately"), the owner's choice of 22:12 UTC (three GPU jobs and up to three CPU jobs) and of 22:27 UTC (Metaflow's resume used and enforced). Issue #252. Confidential with the rest of this repository.

## Where it stands

The tooling is built and tested on a CPU (issue #252). Two of the GPU jobs have run, as the gate's status word read on 2026-10-29 at 18:38 UTC: `sweep synthetic` (job 40781593, 2026-10-25, state 5a7482d0-7f69ef4c: 27 rows, 23 ran, 4 refused, 0 failed, every row as the check predicted) and `sweep real` (job 40781617, 2026-10-25, state 06601195-44ddbdf5: 27 rows, 10 ran, 12 refused, 5 not applicable, 0 failed), each through flows/launch.py with verdict 0 and launcher exit 0, at commit fc027a6; their results are not yet copied here. The VinDr-SpineXR bank (job 40781621) failed at ingest, so `sweep two_source` (40781628) was cancelled with its catalog build. The jobs, each on the owner's word and count of 22:12 UTC:

| Job | Gate word | What it proves |
| --- | --- | --- |
| GPU 1 | `sweep synthetic` | every route on the synthetic bank with level maps, the prior's among them, and the two source cuts that keep a strict part of the labelled crops, since the bank's labelled cases are split between two sources |
| GPU 2 | `sweep real` | every route but the prior's and the source cuts that keep a strict part of the labelled crops, on catalog version 1 of C-ArmLSpine, real frames |
| CPU 1 and 2 | `bank vindr_spinexr` | VinDr-SpineXR banked and ingested, then the catalog rebuilt with it |
| GPU 3 | `sweep two_source` | the same plan on the two-source catalog: the unannotated source feeds the level stage nothing, and a cut to it alone is refused |

Then the six trials of the design note, `sweep trials`, once the owner has seen the smoke and given the count.

The source cuts that keep a strict part of the labelled crops run on the synthetic catalog alone. Its labelled bank's last third of cases is ingested as a render's source (the VerSe projections' registry id, a train-side render route) and the rest as C-ArmLSpine's, so `samples=only-sources` and `samples=drop-sources` with `sources=@first-labelled`, the first labelled source of several, keep one labelled source's crops or the other's. Catalog version 1 and the two-source catalog hold one labelled source, C-ArmLSpine, so there the check calls those four rows not applicable, saying why: a cut to the only labelled source keeps every crop or none. In the covering array itself `only-sources` names every labelled source (`@labelled`), so it trains on every catalog and keeps every crop.

The synthetic catalog is built by `tools/block_sweep.py synthetic` under `/rs/rs_grp_oschome/go2432/smoke/synthetic/catalog/`, each build in a folder of its own under `builds/`, which `SYNTHETIC.json` names once the build is whole. The record holds the arguments and the hashes of the tools, rules, split files and registry entries that make the catalog, so `sweep synthetic` finds the catalog again while they are the same and builds it afresh, removing the folder it replaces, when any of them differs; a build cut short leaves a folder no record names, which the next build removes.

## Its PREREG

PREREG.md in this folder, frozen on 2026-10-29 by PREREG.md.sha256 before any sweep of the smoke ran, writes the design above in the Lab Recipe's seven parts, as the owner's rule of that day asks of every deep learning job on the grid (flows/README.md). It covers the plans synthetic, real and two_source by their names and the sha256 of their bytes; the gate's word, the launcher and the sweep's start refuse any other plan, the six trials among them, and any of the three made again with other bytes, until a PREREG of their own is frozen. A departure goes in DEVIATIONS.md beside it. Each sweep's run checks the CLAIM 2024 and REFORMS report of every row that ran and keeps a progress page under the Metaflow datastore's progress/ folder.

## How the argument is made

docs/research/experiment-framework.md, section 7: a static check decides every named combination from the catalog's facts and trains nothing, and a covering set of runs checks on the GPU that each run does what the check predicted. A row that does not match is a bug.

## What this folder will hold

- `<plan>/`: each plan's results.json and RESULTS.md as the sweep left them in its state folder on the grid (`/rs/rs_grp_oschome/go2432/smoke/<plan>/<code 8>-<catalog sha256 8>/`, the code part naming the code the rows run and the plan file's bytes, which `tools/block_sweep.py state` prints before anything runs), with CHECK.json and CHECK-ALL.md, the check's verdicts for that catalog. A merge to main that changes neither keeps the folder, so a sweep sent again after it carries its finished rows on; for the synthetic plan, a merge that changes what makes its catalog (the record's files, above) builds a new catalog, whose sha256 names a new folder, so its rows train again on the catalog that code makes. The results page and PROGRESS.txt give each row not applicable, refused or failed its reason, and a sweep sent with another `--environment` or other ImageNet bytes into a folder whose rows ran stops at the first such row, saying so, since those rows' run folders hold the earlier runs; such a sweep takes a smoke root of its own.
- `runs/<plan>/<run id>/`: each finished row, copied by `tools/flow.py record --run <state>/<slug> --into docs/research/block-smoke/runs/<plan>`, which names the copy by the row's run id and adds its line to `runs/LEDGER.md`, so the experiments panel of the textbook's chapter 35 reads it like any other run; the evaluation page reads only docs/research/v1-demo/runs.

The trained weights stay on the grid. Nothing here is a number about SchwingNet until a row of the real catalog is recorded, and a smoke row trains three epochs, so its accuracy says that the route works, not how well.
