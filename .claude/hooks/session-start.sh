#!/usr/bin/env bash
# Runs at the start of every Claude Code session, from .claude/settings.json.
# What it prints becomes part of the session's context: how far this checkout
# is ahead of and behind the default branch, and the top of the board. The
# board is the file STATE.md on the branch "board", rewritten by
# .github/workflows/board.yml, so it is read from origin/board and never from
# the checkout (docs/agents/STATE.md here only describes it). The hook never
# fails the session: every path ends in exit 0, each fetch is cut off after
# ten seconds, and the output stays under about 130 lines. It also puts the
# commit-msg hook of tools/usage.py in place, silently, so each commit the
# session makes carries what the session spent since its last one, for the
# field metrics (docs/setup/metrics.md, What the work cost); usage.py
# leaves a clone's own commit-msg hook alone, and does nothing while the
# metrics switch is off.

set -u

root="${CLAUDE_PROJECT_DIR:-$PWD}"
cd "$root" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# The branch origin/HEAD points at, else the one the template was set up with.
default_branch() {
  local ref
  if ref=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null); then
    printf '%s\n' "${ref#origin/}"
  else
    printf '%s\n' "main"
  fi
}

# A fetch that cannot hang the session: ten seconds where timeout exists.
# The arguments say what to fetch; none means the remote's own branches.
fetch_origin() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 10 git fetch --quiet origin "$@" >/dev/null 2>&1
  else
    git fetch --quiet origin "$@" >/dev/null 2>&1
  fi
}

python3 tools/usage.py install >/dev/null 2>&1 || true

default=$(default_branch)
upstream="origin/$default"
branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || printf 'unknown')

if fetch_origin; then
  fetched="fetched"
else
  fetched="origin not reached; counts are from the last fetch"
fi
# The board branch by name, since a clone made for one branch would not
# fetch it otherwise; no board yet, or no remote, is not a failure.
fetch_origin +refs/heads/board:refs/remotes/origin/board || true

if git rev-parse --verify --quiet "$upstream" >/dev/null 2>&1; then
  counts=$(git rev-list --left-right --count "HEAD...$upstream" 2>/dev/null || printf '? ?')
  ahead=${counts%%[[:space:]]*}
  behind=${counts##*[[:space:]]}
  printf 'Branch %s: %s ahead of and %s behind %s (%s).\n' "$branch" "$ahead" "$behind" "$upstream" "$fetched"
  if [ "$behind" != "0" ] && [ "$behind" != "?" ]; then
    printf 'Rebase on %s before pushing; the board will say "main moved" otherwise.\n' "$upstream"
  fi
else
  printf 'Branch %s; %s is not known here (%s).\n' "$branch" "$upstream" "$fetched"
fi

if git rev-parse --verify --quiet refs/remotes/origin/board >/dev/null 2>&1 \
   && board=$(git show origin/board:STATE.md 2>/dev/null); then
  printf '\nThe board (origin/board:STATE.md, as last fetched), first 120 lines:\n'
  printf '%s\n' "$board" | head -n 120
else
  printf '\nThe board has not been written yet: origin has no branch "board" (the first run of .github/workflows/board.yml makes it).\n'
fi

exit 0
