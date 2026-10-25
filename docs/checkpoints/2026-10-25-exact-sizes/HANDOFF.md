# Handoff: exact sizes for every X-ray set, so the size rule admits them (#163, 2026-10-25)

Written 2026-10-25 about 22:40 UTC from the project thread working #163, at the owner's checkpoint of 22:35 UTC: "PLEASE CHECKPOINT IMMEDIATELY WHERE YOU ARE, PUSH ALL FILES TO GIT, WRITE A HANDOFF I CAN PICK UP, GIVE INSTRUCTIONS ON HOW TO RESTART!". The work is on the branch claude/163, draft pull request #400. No fetch, grid job or training was sent, and none is sent by this work: every fetch it admits still waits for the owner's word and count (the owner's comment on #163).

## Goal

Issue #163 as written, on the owner's go of 2026-10-25 21:09 UTC ("10. go"):

1. Size readers for gdown, Kaggle and Redivis, so the size rule admits them instead of refusing them.
2. Exact per-set sizes for the X-ray chain (grid/01-fetch.sbatch, tools/fetch_sources.py): each set lands whole or not at all.
3. The bank stage counted against the room: the rule holds room for the bank before the bank job starts.

Done is #400 merged with its check green.

## Done

- Part 1, commit 75f349e on claude/163 (pushed): grid/fetch_size.py reads gdown, Kaggle (competition and dataset) and Redivis sizes before their clients run, through grid/platform-fetch.sbatch. Its tests are tests/test_fetch_size.py, tests/test_redivis_fetch.py and SizeRuleTest.test_drive_kaggle_and_redivis_are_sized_before_their_clients_run.
- Parts 2 and 3, in the commit this handoff rides in:
  - grid/admit.sh (new): the size rule's words for the X-ray fetch job, set by set. They are admit, unpack, refuse, landed and settle. A set's need includes its bank's budget, from the format of grid/banks/ID.json: twice the set for PNG and DICOM, six times for JPEG, TIFF and BMP, nothing for a recipe still "to confirm".
  - tools/fetch_sources.py: with --admit, each set is sized from its source after its plan is expanded and before its first byte lands:
    - http-get, by its server, with --bytes then handed on;
    - zenodo-get, by the record's listing, with what it verified kept;
    - hf-get, by the hub's tree;
    - the Kaggle client, by the API's storage location;
    - PhysioNet's wget, by the API's main_storage_size, its SHA256SUMS.txt (sized by wget --spider) and robots.txt.
    Each zip's members are sized by its central directory. A compressed tar is decided again once it has landed (the "unpack" mark). A set whose size cannot be read is refused. The report lists "Refused by the size rule". In a Slurm job, a run without --admit is refused.
  - grid/01-fetch.sbatch passes `--admit "bash $REPO/grid/admit.sh"` in a Slurm job.
  - grid/run-xray-chain.sh no longer refuses on the list's guessed sums. It reports the room and records `<fetch job> sets <utc> <bank job>` in grid/logs/XRAY_SIZES.txt.
  - grid/size-rule.sh:
    - owed_by_running takes a SET, so a job deciding set by set still counts its other sets.
    - A "hold" mark lets a landed set's bank room pass to the chain's bank job.
    - bank_budget is new.
    - unconfirmed_fields, recipe_format and bank_factor moved here from grid/gate.sh.
  - grid/02-bank-ingest.sbatch: the chain's bank job decides each recipe in its bank step against the room, with its own hold set aside and every other hold still counted. It settles the recipe once the ingest has run or the bank has failed.
- Tests, all passing locally on 2026-10-25 at about 22:30 UTC:
  - tests/test_xray_chain.py: 115, with the new AdmitTest and SizedFetchTest classes.
  - tests/test_gate.py: 106, with the new test_the_chains_bank_job_decides_each_recipe_in_its_bank_step_against_its_hold.
  - tests/test_flows.py.
  - tests/test_physionet_answers.py.

## Open, in order

1. Docs and memory, in #400:
   - grid/README.md line 39 still says gdown, Kaggle and Redivis are refused until #163, and that the X-ray chain is checked at submit. Rewrite it to say each set is decided in the fetch job by grid/admit.sh.
   - docs/memory/the-size-rule.md and its line in docs/memory/MEMORY.md need the same correction: gdown, Kaggle and Redivis are sized, the X-ray sets are admitted one by one with their banks, and a hold passes to the bank job.
   - Add the new files to the list in docs/agents/claims/163.md.
2. `bash scripts/check.sh` in a throwaway clone (docs/memory/run-the-checks-in-a-throwaway-copy.md), then CI on #400.
3. An adversarial review of the diff. Its findings go into the PR body under "## Adversarial review".
4. Finish: delete docs/agents/claims/163.md and write the body's review section. Then mark the PR ready in a call of its own (docs/memory/mark-a-pull-request-ready-on-its-own.md), and merge once green under the standing permission.
5. A generic research note in symphony-template under docs/research/, with its README line, on how each service states a file's size before download:
   - Zenodo's listing, the Hugging Face tree, a one-byte range request;
   - Kaggle's storage redirect;
   - PhysioNet's main_storage_size and wget --spider;
   - a zip's central directory.
   It must carry nothing of SchwingNet.

## How to restart

1. Open a session on OpenSpineConsortium/SchwingNet. Fetch and check out the branch:
   ```
   git fetch origin claude/163
   git checkout -B claude/163 origin/claude/163
   ```
   Read the board as CLAUDE.md says.
2. First prompt: "Continue #163 on branch claude/163 (draft PR #400) from docs/checkpoints/2026-10-25-exact-sizes/HANDOFF.md: do its Open list in order, merge once green, and send no fetch or grid job."
3. Run the touched suites: `python3 -m unittest tests.test_xray_chain tests.test_gate tests.test_flows tests.test_physionet_answers tests.test_fetch_size tests.test_redivis_fetch`.
4. Push with the repository's pixi on PATH (`export PATH="$HOME/.pixi/bin:$PATH"`). The pre-push hook runs the gate for about five minutes and refuses a tree with anything uncommitted.
