---
name: schwingnet-check-in-a-cloud-container
description: Running SchwingNet's scripts/check.sh in a cloud container: use a scratch copy, install beartype in a venv, and read CI's check and gate jobs as the authority for pixi-only steps.
metadata:
  type: project
  modified: 2026-10-25T19:48:57.219Z
---

SchwingNet's `bash scripts/check.sh` run in a cloud container (no pixi, Python 3.13) on 2026-10-25: every step passed except seven tests in tests/test_bank_depth.py, which errored with ModuleNotFoundError beartype (tools/ingest.py imports catalog, which imports beartype). With beartype installed in a scratch venv those seven skip cleanly; with beartype and icontract both installed (`python3 -m venv --system-site-packages`, then pip install beartype icontract) they run and pass (checked 2026-10-25 21:45 UTC). The steps that need pixi (beethoven-qa vendor-check, tools/sources.py check) print a line and leave the work to CI's gate lane. The steps after the tests (reproduce_table, licences, claims_rank, rag, eval_page, experiments_panel, report, storage_panel checks) take about a minute and pass.

**Why:** the repo memory run-the-checks-in-a-throwaway-copy says check.sh can leave a clone dirty, and the container lacks the locked environment, so a local red is often the environment, not the branch.

**How to apply:** clone the branch into the scratchpad (`git clone --no-hardlinks /home/claude/SchwingNet <scratch>` then fetch the remote-tracking ref and check it out), run check.sh there, re-run tests/test_bank_depth with beartype in a venv if it errors, and treat CI's check job and gate job as the verdict for the pixi-only steps. Related: [[symphony3-project-overview]].
