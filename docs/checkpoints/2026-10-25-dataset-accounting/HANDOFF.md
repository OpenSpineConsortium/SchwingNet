# Handoff: dataset chooser, grid accounting and held fluoroscopy (2026-10-25)

Written at the owner's checkpoint of 2026-10-25 09:46 UTC (weekly limit at 92 percent), so that another account can continue. The research lives in docs/research/, and this page only points to it.

## Goal

The owner's goal, in their words of 04:14 UTC: "an automated process, deterministic if possible, for choosing datasets to use to both train a network and be able to test it with sufficient power on normal spines, in the fluoroscopic domain". The owner added three asks:

- whether thoracic and cervical fluoroscopy is held;
- whether every set maps to a known dataset and matches its paper;
- at 04:53 UTC, "make sure every dataset on the grid maps to a task ... on the repo which has all those, for accounting purposes" (OpenSpineConsortium/spine-datasets).

## Done

- The chooser: tools/choose_data.py and data/choice/ (#291, #292); docs/research/dataset-chooser.md.
- Every spine-datasets record names its task (spine-datasets #331, accounting issues #254 to #329).
- The folder report: tools/folder_report.py and grid/folders.sbatch, through the gate word `folders`, made to run and to read whole (#296 to #301). Its last run was grid job 40780668. No page is left on the grid, so another `folders` send queues a new job, which needs the owner's word.
- grid/folders.json in spine-datasets: all 110 data-root folders, each with its records or its task (#333 to #368). This is spine-datasets #369, merged.
- The answer to the thoracic and cervical question, and six records set beside their papers: docs/research/held-fluoroscopy-by-region.md (#302, merged).
- The inclusion audit and the recipe page from the full census (2026-10-25, 11:34 UTC ask): spine-datasets docs/research/dataset-inclusion-audit.md (spine-datasets #370) and Figure 16.1, docs/textbook/figures/16/dataset-recipe.html, whose new section The ledger lists every record on the grid or not and the folders that are no dataset's (this repository's pull request from docs/recipe-ledger-2026-10-25). The census: 111 folders, 14.04 TB; 112 of 166 records on the grid; 52 kept sets held in 8.63 TB, 43 to obtain. The project files storage/dataset-inclusion-audit.md and storage/dataset-recipe.html are the same text.

## Open

1. spine-datasets #370 and this repository's recipe-ledger pull request: check that both merged; if not, merge once green (the org's owner-approval ruleset leaves auto-merge blocked, so merge directly). The memory line on the test_crowd_check flake applies to spine-datasets.
7. cadica, scidb_mtddh and veterinary_pig_levelcheck: their records say held but the census finds no folder in the data root; find where they are, or correct the records.
2. spine-datasets #360, #363 and the other open `unrecorded` tasks (spinal_ai2024, mendeley_5jdfdgp762, spinesac, fluorocap, ieee_dataport_lateral_fullspine_236): write each record from its paper and source page, then close the task. SchwingNet's data/sources/<id>.json holds a start for four of them.
3. spine-datasets #368: name the 17 GB data-root folder the readout masks. Any grid listing works, as long as it does not pass through symphony-template tools/grid_accounts.py, which masks runs of 32 or more name characters as [hidden].
4. Settle the two count gaps in the research note: NHANES II (17,073 TIFF against 16,531 in the record) and KUB StoneX (6,810 images against 2,570 radiographs).
5. Re-run tools/choose_data.py once the new records land. The chooser reads only records, so held sets with no record stay invisible to it until then.
6. Older items from earlier in the thread, still waiting on the owner: the NLST decision card, the storage.sh traceback, and the moves to the 4 TB home.

## How to work here

- One read-only grid job only on the owner's word, with the count. Send `status` before any resend, and read results yourself from symphony-template's branch `grid` (logs/job-<job>.json). The readout keeps a job's last 400 lines.
- Never quote or export anything of SchwingNet; the research stays in this repository.
- One PR per change, `bash scripts/check.sh` first (in a scratch worktree here), and merge once green on the owner's standing permission.

## First prompt for the next account

"Continue the dataset accounting handoff in SchwingNet docs/checkpoints/2026-10-25-dataset-accounting/HANDOFF.md: confirm spine-datasets #370 and the recipe-ledger pull request merged, then write the records for the five unrecorded held sets (spine-datasets tasks with the label todo from #333 to #368), each from its paper, and re-run tools/choose_data.py. No grid job without my word and the count."
