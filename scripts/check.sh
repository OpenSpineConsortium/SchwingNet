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

# The project's own checks go here: its linter, its test runner, its build.

echo "checks ok"
