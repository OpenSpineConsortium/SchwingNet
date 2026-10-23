#!/usr/bin/env bash
# The tree the synthesis's reads start from: main, with the records the open synthesis pull
# request changes laid on it, so a run builds on what earlier runs read and nobody has merged yet.
# Only the files a join writes are laid (outputs, below), and only from the pull request the App
# opened: the tools that then run are main's, so no unmerged code runs in a job that holds the
# App's key, and a pull request that changes anything else, a tool or a brief, is named foreign and
# not built on. The pull request's branch is always one commit on main, made again by each run that
# writes to it, so a push to it never carries another change of main's, a workflow file's least of
# all, which the App's token may not push. Run in a checkout of SchwingNet with its whole history;
# leaves it at the tree, committed. Prints name=value lines for GITHUB_OUTPUT:
#   main       the main commit the tree is made on
#   start      the pull request's head the tree takes its records from, or empty
#   pr         that pull request's number, and branch its branch, or both empty
#   conflict   the pull request's number where its records no longer go onto main cleanly
#   foreign    the pull request's number where it changes a file no join writes
#   rejected   the pull request's number where owner-ok failed on its head, as it does when the
#              owner presses Reject
#   tree       the tree's hash, and synthesis a hash of the records in it
#
# Usage, with GH_TOKEN able to read the repository, its pull requests and their checks, and
# SYNTH_APP the slug of the App that opens the pull request (empty adopts none):
#   synth_base.sh look REPO        main is the checkout's HEAD, and the pull request the open one
#   synth_base.sh again REPO START main is the checkout's HEAD, and the records START's, as the
#                                  look printed it (empty for none), so a later job of the run
#                                  makes the look's tree again and can compare it
#   synth_base.sh now REPO         main is origin's main as it is now, and the pull request the
#                                  one open now, for the join to write onto
#   synth_base.sh publish REPO JOINED MAIN
#                                  prints tree=, MAIN's tree with the records of the commit
#                                  JOINED in place of MAIN's, for the commit the join pushes
set -euo pipefail

mode=$1
repo=$2
auth="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)"
name_rule='^synthesis/[A-Za-z0-9._-]+$'
bot=${SYNTH_APP:+${SYNTH_APP}[bot]}
patch=$(mktemp)
trap 'rm -f "$patch"' EXIT

# The files synth.py join writes, and nothing else: the records, the pages rendered from them and
# the stamp. A folder stands for every file under it.
outputs=(
  artifacts/_synthesis/inventory.json
  artifacts/_synthesis/inventory.md
  artifacts/_synthesis/clusters.md
  artifacts/_synthesis/contradictions.md
  artifacts/_synthesis/contradictions
  artifacts/_synthesis/concepts.md
  artifacts/_synthesis/work/out/inventory-history.json
  artifacts/_synthesis/work/out/clustering.json
  artifacts/_synthesis/work/out/contradictions-merged.json
  artifacts/_synthesis/work/out/numbers-partial.json
  artifacts/_synthesis/work/out/verdict-quotes.json
  artifacts/_synthesis/work/out/state.json
  artifacts/_synthesis/work/out/concepts.json
)

fetch() {
  git -c http.extraheader="$auth" fetch --quiet --no-tags origin "$@"
}

commit_as_bot() {
  git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
    commit --quiet --no-verify -m "$1"
}

is_output() {
  local path=$1 out
  for out in "${outputs[@]}"; do
    if [ "$path" = "$out" ] || [[ $path == "$out"/* ]]; then
      return 0
    fi
  done
  return 1
}

# The oldest open pull request the App opened from a synthesis/ branch of this repository; one
# anybody else opened is no run's, whatever its branch is called.
open_pr() {
  local found=''
  if [ -n "$bot" ]; then
    found=$(gh api "repos/$repo/pulls?state=open&base=main&sort=created&direction=asc&per_page=100" \
      --jq "[.[] | select(.head.repo.full_name == \"$repo\" and .user.login == \"$bot\" and (.head.ref | startswith(\"synthesis/\")))][0] | [.number, .head.ref, .head.sha] | @tsv")
  fi
  pr=$(cut -f1 <<<"$found")
  branch=$(cut -f2 <<<"$found")
  start=$(cut -f3 <<<"$found")
  if [ -n "$branch" ] && ! [[ $branch =~ $name_rule ]]; then
    echo "the synthesis pull request #$pr has a branch name this script does not take" >&2
    exit 1
  fi
}

# Whether owner-ok's latest run on the pull request's head failed: the owner turned it down, or
# the gate could not pass it, and either way no run builds on it until a person has looked.
turned_down() {
  local conclusions
  conclusions=$(gh api "repos/$repo/commits/$start/check-runs?check_name=owner-ok&filter=latest&per_page=100" \
    --jq '[.check_runs[].conclusion] | map(select(. != null)) | join(" ")')
  [[ " $conclusions " == *" failure "* ]]
}

# Lay start's records, as they changed since it left main, onto main as one commit.
rebuild() {
  git checkout --quiet --detach "$main"
  conflict=''
  foreign=''
  rejected=''
  if [ -z "$start" ]; then
    return
  fi
  if ! [[ $start =~ ^[0-9a-f]{40}$ ]]; then
    echo "the start is not a commit hash: $start" >&2
    exit 1
  fi
  fetch "$start"
  local base path
  base=$(git merge-base "$main" "$start")
  while IFS= read -r -d '' path; do
    if ! is_output "$path"; then
      echo "the synthesis pull request #${pr:-?} changes $path, which no join writes, so its records are not laid on main" >&2
      foreign=${pr:-unknown}
      return
    fi
  done < <(git diff --name-only -z --no-renames "$base" "$start")
  if [ -n "$pr" ] && turned_down; then
    rejected=$pr
    return
  fi
  git diff --full-index --binary --no-renames "$base" "$start" -- "${outputs[@]}" >"$patch"
  if [ ! -s "$patch" ]; then
    return
  fi
  if git apply --3way --index "$patch" >/dev/null 2>&1; then
    commit_as_bot "The synthesis's unmerged reads, on main"
  else
    git reset --quiet --hard "$main"
    conflict=${pr:-unknown}
  fi
}

# A hash of the records a tree holds, by their paths and blobs, so a join can tell whether the
# records it read are still the ones on main and in the open pull request.
records_hash() {
  git ls-tree -r --full-tree "$1" -- "${outputs[@]}" | sha256sum | cut -d' ' -f1
}

case $mode in
  look)
    main=$(git rev-parse HEAD)
    open_pr
    ;;
  again)
    main=$(git rev-parse HEAD)
    start=${3:-}
    pr=''
    branch=''
    ;;
  now)
    fetch "+refs/heads/main:refs/remotes/origin/main"
    main=$(git rev-parse refs/remotes/origin/main)
    open_pr
    ;;
  publish)
    joined=$3
    main=$4
    index=$(mktemp)
    rm -f "$index"
    export GIT_INDEX_FILE=$index
    git read-tree "$main"
    git rm -r -q -f --cached --ignore-unmatch -- "${outputs[@]}"
    git ls-tree -r --full-tree "$joined" -- "${outputs[@]}" | git update-index --index-info
    echo "tree=$(git write-tree)"
    rm -f "$index"
    exit 0
    ;;
  *)
    echo "usage: synth_base.sh look|again|now REPO [START], or publish REPO JOINED MAIN" >&2
    exit 2
    ;;
esac
rebuild

echo "main=$main"
echo "start=$start"
echo "pr=$pr"
echo "branch=$branch"
echo "conflict=$conflict"
echo "foreign=$foreign"
echo "rejected=$rejected"
echo "tree=$(git rev-parse 'HEAD^{tree}')"
echo "synthesis=$(records_hash HEAD)"
