# Requested experiments: one combination of data and blocks a run

Source: the thread "Require Metaflow for every grid DL job", 2026-10-29, on the owner's rule of 02:39 UTC that every deep learning job on the grid runs on the block-based Metaflow pipeline under a frozen PREREG with the CLAIM and REFORMS report enforced. Confidential with the rest of this repository.

The gate's word `experiment <issue>` runs one combination a person asked for on an issue labelled experiment: .github/workflows/experiment.yml checks the issue's lines and records them as `<issue>.request` on the branch experiments, and the word, once the owner sends it, runs the request as one GPU job (grid/experiment-driver.sbatch). How a request is made, checked and recorded is docs/research/experiments-panel.md; the blocks a request may name are docs/research/experiment-framework.md, section 2.

Since 2026-10-29 the job starts the run through the launcher as the flow `experiment` (flows/experiment.py, ExperimentFlow): its start holds the run to PREREG.md in this folder, its one step runs `tools/flow.py run` with the request's recipe, epochs, seed, hours and blocks, and its end writes and checks the run's CLAIM 2024 and REFORMS report and draws the run's progress page under the Metaflow datastore's progress/ folder (flows/README.md). The launcher's key holds the request's bytes beside the catalog's and the weights', so a request edited after a run started is a run of its own.

- PREREG.md: the design every requested run is built to, frozen before any run of the word: an estimate with no accuracy bar, as the owner chose on 2026-10-29 at 03:23 UTC, the request being the run's registered configuration; no requested combination is chosen over another by its test numbers.
- DEVIATIONS.md: where a run as built departs from it, dated; empty of entries until one does.

## Where it stands

No run of the word has been made. The word waits for the owner's word and count, as every grid job does (docs/project.md), and for the first request answered on a real issue (docs/research/experiments-panel.md, section 7).
