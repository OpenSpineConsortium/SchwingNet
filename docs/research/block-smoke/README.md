# The block smoke test: every combination decided, every route run

Source: the thread "Build plug-and-play training experiment framework", 2026-10-24, the owner's asks of 21:11 to 21:20 UTC ("smoke test all possible combinations of the blocks on the grid", "start with whatever combinations will cover all possible routes of data through the workflow", "make sure i know that any combination of the blocks within fundamental constraints like incompatibility will work for any of the datasets i have available, and natively the annotated and unannotated datasets will be passed appropriately"), the owner's choice of 22:12 UTC (three GPU jobs and up to three CPU jobs) and of 22:27 UTC (Metaflow's resume used and enforced). Issue #252. Confidential with the rest of this repository.

## Where it stands

The tooling is built and tested on a CPU (issue #252); no grid job of the smoke has run yet. The jobs, each on the owner's word and count of 22:12 UTC:

| Job | Gate word | What it proves |
| --- | --- | --- |
| GPU 1 | `sweep synthetic` | every route on the synthetic bank with level maps, the prior's among them, and the two source cuts that keep a strict part of the labelled crops, since the bank's labelled cases are split between two sources |
| GPU 2 | `sweep real` | every route but the prior's and the source cuts that keep a strict part of the labelled crops, on catalog version 1 of C-ArmLSpine, real frames |
| CPU 1 and 2 | `bank vindr_spinexr` | VinDr-SpineXR banked and ingested, then the catalog rebuilt with it |
| GPU 3 | `sweep two_source` | the same plan on the two-source catalog: the unannotated source feeds the level stage nothing, and a cut to it alone is refused |

Then the six trials of the design note, `sweep trials`, once the owner has seen the smoke and given the count.

The source cuts that keep a strict part of the labelled crops run on the synthetic catalog alone. Its labelled bank's last third of cases is ingested as a render's source (the VerSe projections' registry id, a train-side render route) and the rest as C-ArmLSpine's, so `samples=only-sources` and `samples=drop-sources` with `sources=@first-labelled`, the first labelled source of several, keep one labelled source's crops or the other's. Catalog version 1 and the two-source catalog hold one labelled source, C-ArmLSpine, so there the check calls those four rows not applicable, saying why: a cut to the only labelled source keeps every crop or none. In the covering array itself `only-sources` names every labelled source (`@labelled`), so it trains on every catalog and keeps every crop.

The synthetic catalog is built by `tools/block_sweep.py synthetic` under `/rs/rs_grp_oschome/go2432/smoke/synthetic/catalog/`, each build in a folder of its own under `builds/`, which `SYNTHETIC.json` names once the build is whole. The record holds the arguments and the hashes of the tools, rules, split files and registry entries that make the catalog, so `sweep synthetic` finds the catalog again while they are the same and builds it afresh, removing the folder it replaces, when any of them differs; a build cut short leaves a folder no record names, which the next build removes.

## How the argument is made

docs/research/experiment-framework.md, section 7: a static check decides every named combination from the catalog's facts and trains nothing, and a covering set of runs checks on the GPU that each run does what the check predicted. A row that does not match is a bug.

## What this folder will hold

- `<plan>/`: each plan's results.json and RESULTS.md as the sweep left them in its state folder on the grid (`/rs/rs_grp_oschome/go2432/smoke/<plan>/<commit 7>-<catalog sha256 8>/`), with CHECK.json and CHECK-ALL.md, the check's verdicts for that catalog.
- `runs/<plan>/<slug>/`: each finished row, copied by `tools/flow.py record`, so the experiments panel of the textbook's chapter 35 and the evaluation page read it like any other run.

The trained weights stay on the grid. Nothing here is a number about SchwingNet until a row of the real catalog is recorded, and a smoke row trains three epochs, so its accuracy says that the route works, not how well.
