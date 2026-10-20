#!/bin/bash
# The mutation check of the grid runner's review of 2026-10-16 (wsu-grid-and-github-actions.md
# beside this file, "How the fixes were proven"): each mutation undoes one fix in a copy of an
# hpcworker checkout, and that copy's tools/tests/test_grid_runner.sh must fail on every one.
#
#   bash docs/research/wsu-grid-and-github-actions-mutations.sh <hpcworker checkout>
#
# It exits 0 when every mutation applies and is caught, and 1 when one is caught by no check or no
# longer applies; after a change to tools/grid_runner.sh the second means the fix's text moved, and
# the mutation is brought up to date with it, never the test loosened. The checkout itself is
# never changed: each mutation runs in a copy under a temporary folder, removed at the end.
set -u
SRC=${1:?usage: wsu-grid-and-github-actions-mutations.sh <hpcworker checkout>}
if [ ! -f "$SRC/tools/grid_runner.sh" ] || [ ! -f "$SRC/tools/tests/test_grid_runner.sh" ]; then
  echo "not an hpcworker checkout with the grid runner: $SRC" >&2
  exit 2
fi
WORK=$(mktemp -d) || exit 2
trap 'rm -rf "$WORK"' EXIT
result=0

run() { # NAME OLD NEW: the one occurrence of OLD in tools/grid_runner.sh becomes NEW, then the tests run
  local name=$1 old=$2 new=$3 copy="$WORK/$1" out fails
  mkdir "$copy" && (cd "$SRC" && tar --exclude=.git -cf - .) | tar -C "$copy" -xf -
  if ! python3 - "$copy/tools/grid_runner.sh" "$old" "$new" <<'EOF'
import sys
path, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path).read()
if text.count(old) != 1:
    sys.exit(1)
open(path, "w").write(text.replace(old, new))
EOF
  then
    echo "NOT APPLIED  $name"
    result=1
    return
  fi
  out=$(cd "$copy" && bash tools/tests/test_grid_runner.sh 2>&1)
  fails=$(printf '%s\n' "$out" | grep -c '^FAIL')
  if [ "$fails" -eq 0 ]; then
    echo "UNCAUGHT     $name"
    result=1
  else
    printf 'caught       %-20s %3s checks fail, the first: %s\n' "$name" "$fails" \
      "$(printf '%s\n' "$out" | grep -m1 '^FAIL' | sed 's/^FAIL *//')"
  fi
}

run version-tail-1 "grep -xE '[0-9]+\.[0-9]+\.[0-9]+' | tail -1)" "tail -1 | tr -d '[:space:]')"
run no-scrub 'APPTAINER_*|SINGULARITY_*|APPTAINERENV_*|SINGULARITYENV_*) unset "$v";;' 'NOTHING_*) unset "$v";;'
run no-env-false ' --env ACTIONS_RUNNER_PRINT_LOG_TO_STDOUT=false' ''
run no-nv 'case "$GRES" in *gpu*) NV=(--nv);; esac' ':'
run no-third-stop 'if [ "$n" -ge 3 ]; then stop_chain' 'if [ "$n" -ge 99 ]; then stop_chain'
run no-served 'chain_served() { rm -f "$CHAIN/failures"; }' 'chain_served() { :; }'
run squeue-ignored '|| { log "squeue did not say whether an earlier run of this job queued the next one; none is queued"; return 1; }' '|| true'
run gh-error-as-public '*) chain_failed "gh could not read the repository'"'"'s visibility"; return 1;;' '*) stop_chain "the repository is public"; return 1;;'
run update-retries 'stop_chain "the runner asks for a newer version than the image'"'"'s $IMAGE_VERSION: tools/grid_runner.sh --install, then --start"
          end_state=stopped; ended=1; break;;' 'sleep 5; continue;;'
run nojob-counted '[ "$RC" = 0 ] && ! busy && RC=nojob' ':'
run creds-linger 'rm -f "$HOME_DIR/.runner" "$HOME_DIR/.credentials" "$HOME_DIR/.credentials_rsaparams"' ':'

exit "$result"
