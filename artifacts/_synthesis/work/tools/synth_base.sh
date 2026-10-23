#!/usr/bin/env bash
# The tree the synthesis's reads start from: main, with the changes the open synthesis pull
# request makes to artifacts/_synthesis/ laid on it, so a run builds on what earlier runs read and
# nobody has merged yet. The pull request's branch is always one commit on main, made again by
# each run that writes to it, so a push to it never carries another change of main's, a workflow
# file's least of all, which the App's token may not push. Run in a checkout of SchwingNet with its
# whole history; leaves it at the tree, committed. Prints name=value lines for GITHUB_OUTPUT:
#   main       the main commit the tree is made on
#   start      the pull request's head the tree takes its changes from, or empty
#   pr         that pull request's number, and branch its branch, or both empty
#   conflict   the pull request's number where its changes no longer go onto main cleanly
#   tree       the tree's hash, and synthesis the hash of its artifacts/_synthesis/
#
# Usage, with GH_TOKEN able to read the repository and its pull requests:
#   synth_base.sh look REPO        main is the checkout's HEAD, and the pull request the open one
#   synth_base.sh again REPO START main is the checkout's HEAD, and the changes START's, as the
#                                  look printed it (empty for none), so a later job of the run
#                                  makes the look's tree again and can compare it
#   synth_base.sh now REPO         main is origin's main as it is now, and the pull request the
#                                  one open now, for the join to write onto
set -euo pipefail

mode=$1
repo=$2
auth="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)"
name_rule='^synthesis/[A-Za-z0-9._-]+$'
patch=$(mktemp)
trap 'rm -f "$patch"' EXIT

fetch() {
  git -c http.extraheader="$auth" fetch --quiet --no-tags origin "$@"
}

commit_as_bot() {
  git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
    commit --quiet --no-verify -m "$1"
}

open_pr() {
  local found
  found=$(gh api "repos/$repo/pulls?state=open&base=main&sort=created&direction=asc&per_page=100" \
    --jq "[.[] | select(.head.repo.full_name == \"$repo\" and (.head.ref | startswith(\"synthesis/\")))][0] | [.number, .head.ref, .head.sha] | @tsv")
  pr=$(cut -f1 <<<"$found")
  branch=$(cut -f2 <<<"$found")
  start=$(cut -f3 <<<"$found")
  if [ -n "$branch" ] && ! [[ $branch =~ $name_rule ]]; then
    echo "the synthesis pull request #$pr has a branch name this script does not take" >&2
    exit 1
  fi
}

# Lay start's changes to artifacts/_synthesis/ since it left main onto main, as one commit.
rebuild() {
  git checkout --quiet --detach "$main"
  conflict=''
  if [ -z "$start" ]; then
    return
  fi
  if ! [[ $start =~ ^[0-9a-f]{40}$ ]]; then
    echo "the start is not a commit hash: $start" >&2
    exit 1
  fi
  fetch "$start"
  git diff --full-index --binary "$(git merge-base "$main" "$start")" "$start" -- artifacts/_synthesis >"$patch"
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
  *)
    echo "usage: synth_base.sh look|again|now REPO [START]" >&2
    exit 2
    ;;
esac
rebuild

echo "main=$main"
echo "start=$start"
echo "pr=$pr"
echo "branch=$branch"
echo "conflict=$conflict"
echo "tree=$(git rev-parse 'HEAD^{tree}')"
echo "synthesis=$(git rev-parse HEAD:artifacts/_synthesis)"
