#!/usr/bin/env bash
# The project's fast checks, run by CI (.github/workflows/ci.yml, the job
# "check" that branch protection requires) and by hand before a pull
# request. The documents come first because they are the Claude project's
# instructions and memory: a broken import or a stray secret is a broken
# project. Add the project's own lines where marked below.
set -eu
cd "$(dirname "$0")/.."

python3 tools/check_docs.py
# The claim protocol's copy must be byte for byte what tools/VENDORED
# records: a change to it is made in OpenSpineConsortium/symphony-protocol and
# arrives by that repository's sync pull request in the template, or by its
# scripts/vendor.py in a repository made from it, so a hand edit fails here.
# A hand edit that rewrote VENDORED to match passes this line and fails
# tests/test_vendored.py, which compares the copy with the library itself
# in the clone SDLC_PROTOCOL names (CI clones it; .github/workflows/ci.yml).
python3 tools/sdlc_protocol/vendoring.py verify tools
# bordercall's copy under grid/bordercall/ must be what grid/bordercall/VENDORED
# records: a change is made in OpenSpineConsortium/bordercall and brought here
# by tools/bordercall_vendor.py copy, never edited in the copy (the grid's job
# runs it, and has no token for the private repository).
python3 tools/bordercall_vendor.py check
# Every worker's file under .github/symphony/workers/ must hold together
# (docs/agents/WORKERS.md): a misspelt setting or a name that is no label
# fails here, before the workflows that read the registry would.
python3 tools/workers.py check
# Every agent under .claude/agents/ and its line in .github/symphony/agents.json
# must hold together (docs/agents/AGENTS.md), and an imported agent must be
# the file it was when it came, so a hand edit is a choice, not an accident.
python3 tools/agents.py check
# The lessons under docs/learn/ are run, command by command, and their
# outputs compared with the pages; every module and script must carry the
# documentation the Reference page is made from, and each lesson's notebook
# must match its lesson (tools/living_docs.py).
python3 tools/living_docs.py test
python3 tools/living_docs.py check
python3 -m unittest discover -s tests -v
# The workflows (issue #248; docs/research/rust-coordinator.md, section 8):
# actionlint type-checks every expression against the contexts its event
# carries and runs shellcheck over every run: block, at warning and above;
# zizmor audits them for security, offline, at medium and above. Their
# settings are .github/actionlint.yaml and .github/zizmor.yml. CI installs
# both pinned by hash; a local check runs each only where it is installed.
if command -v actionlint >/dev/null 2>&1; then
  SHELLCHECK_OPTS=--severity=warning actionlint
else
  echo "actionlint is not installed here; CI runs it"
fi
if command -v zizmor >/dev/null 2>&1; then
  zizmor --quiet --offline --config .github/zizmor.yml --min-severity medium .github/workflows
else
  echo "zizmor is not installed here; CI runs it"
fi

# A pinned copy of OpenSpineConsortium/beethoven-qa (docs/setup/beethoven-qa.md)
# is checked by its own command, which runs only in the locked pixi
# environment the copy's gate needs (icontract, beartype, pydantic); this
# script adds no dependency, so where pixi is not on the path it says so
# and leaves the copy to the repository's own gate lane, which runs it
# under pixi on GitHub's machines (beethoven-qa's docs/CONSUMING.md, step 5).
if [ -f vendor/beethoven-qa/ORIGIN ]; then
  if command -v pixi >/dev/null 2>&1 && [ -f pixi.lock ]; then
    pixi run --locked python -m beethoven_qa vendor-check
  else
    echo "beethoven-qa copy at vendor/beethoven-qa ($(sed -n 's/^ref: //p' vendor/beethoven-qa/ORIGIN)); pixi is not here, so its vendor-check runs in the gate lane"
  fi
fi

# The project's own checks go here: its linter, its test runner, its build.
# The dataset inventory is rendered from data/sources/ (tools/sources.py); the page
# and the records must agree. The renderer imports the package, so it runs in the
# locked environment; where pixi is not here the gate lane's test holds the same
# (tests/schwingnet/test_sources.py).
if command -v pixi >/dev/null 2>&1 && [ -f pixi.lock ]; then
  pixi run --locked python tools/sources.py check
else
  echo "data/sources/ against docs/research/datasets-inventory.md: pixi is not here, so the gate lane checks it"
fi

# The reproduction page (docs/research/datasets-reproduce.md) is rendered from the registry,
# data/reproduce/map.json and the copied manifest by tools/reproduce_table.py, standard library: the
# page must match its inputs, every registry record must be in the map, and the copies must carry
# the SHA-256 that data/reproduce/SHA256SUMS records.
python3 tools/reproduce_table.py check

# Every dataset's licence is classified in data/licences.json and every recipe under data/recipes/
# holds together (tools/licences.py, standard library): a record or registry source with no entry,
# a licence line changed since it was classified, a class looser than the rule's without the
# owner's reading, or data/LICENCES.md not what the facts render, fails here.
python3 tools/licences.py check

# The claims register (docs/textbook/claims.json, chapter 33) must hold together (tools/claims_rank.py,
# standard library): every claim an item bears on exists, every grade is one of the four and each
# claim's grade is its weakest link, no item waits on an item that is not there or on itself.
python3 tools/claims_rank.py check

# Ask the book (tools/rag.py, standard library): the questions of docs/textbook/rag/questions.json
# must hold together (at least 30, each answered by chapters of the book, a figure only one with a
# record) and version 1 of the book's search must reach the floor they write for its recall at 5 and
# its mean reciprocal rank, so an edit that breaks the search fails here, not in a reader's hands.
python3 tools/rag.py check

# The evaluation page (docs/research/evaluation/README.md) is written from the recorded runs under
# docs/research/v1-demo/runs/ by tools/eval_page.py, standard library: a run recorded without the
# page written again, or a page edited by hand, fails here.
python3 tools/eval_page.py check

# The experiments panel (docs/textbook/figures/35/experiments.html, .json and .svg) is written from
# the same recorded runs, the recipes and the blocks by tools/experiments_panel.py, standard library:
# a run recorded without the panel written again (python3 tools/experiments_panel.py write), or a
# page edited by hand, fails here.
python3 tools/experiments_panel.py check

# Every recorded run carries its report (REPORT.md, claim.json, reforms.json), written by
# tools/report.py from the run's files and data/reporting/study.json, standard library: a run
# recorded without its report, or a study answer changed without the reports written again
# (python3 tools/report.py write-recorded), fails here.
python3 tools/report.py check-recorded

# Every deep learning job on the grid runs on a flow flows/launch.py starts, under a frozen PREREG
# (the owner's rule of 2026-10-29): flows/registry.txt lists the flows, and flows/stage_registry.py,
# standard library, fails here on a line whose flow class, job script or PREREG does not hold, a
# PREREG edited since its PREREG.md.sha256 froze it among them.
python3 flows/stage_registry.py check
# The same freeze held by git, since a PREREG.md edited with its PREREG.md.sha256 written again passes the
# line above: no PREREG.md or PREREG.md.sha256 that origin/main holds under docs/research/ may change, and a
# DEVIATIONS.md beside a frozen one only grows. CI checks out a pull request's merge commit one commit deep,
# so there it fetches main one commit deep first; a clone with no origin/main skips it with a line.
python3 flows/stage_registry.py frozen

# The textbook's storage panel (docs/textbook/figures/22/, chapter 22) is drawn by tools/storage_panel.py from
# the committed snapshot of spine-datasets' feed, standard library: a snapshot refreshed without the page built
# again, or a page edited by hand, fails here.
python3 tools/storage_panel.py check

# The gold tier 3 CT dataset (data/gold3-ct/, docs/research/gold3-ct/) is held by tools/gold3_ct.py, standard
# library: a facts row that breaks its schema, ENHANCE.PET classes that no longer give the note's table, or
# STATS.md, QA.md or page-data.json not written again from the committed files (python3 tools/gold3_ct.py
# stats, qa, page) fails here; while the facts are not committed it passes with a note.
python3 tools/gold3_ct.py check

echo "checks ok"
