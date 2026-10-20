#!/bin/bash
# Run every part of the deep lane but the searches in the main checkout, at its HEAD.
set -euo pipefail
cd /home/claude/symphony-protocol
test -z "$(git status --porcelain -- . ':!validation/runs')" || { echo "the checkout is not clean"; exit 1; }
rm -rf validation-out
mkdir validation-out
sha=$(git rev-parse --short HEAD)
echo "started $(date -u +%Y-%m-%dT%H:%M:%SZ) at $sha with python3.12 $(python3.12 -c 'import platform; print(platform.python_version())'), $(git --version), $(nproc) processors" > validation-out/started.txt
python3.12 scripts/validate.py deep --only soak,gate,git,guard,conformance --jobs 3 --out validation-out > validation-out/run.log 2> validation-out/progress.log < /dev/null
echo "exit $?"
cat validation-out/started.txt
tail -3 validation-out/run.log
