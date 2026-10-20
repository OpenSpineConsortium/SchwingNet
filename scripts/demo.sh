#!/usr/bin/env bash
# Show the claim protocol working, on this machine, in about a second: no
# network, no GitHub sign-in, no Claude account and no key of any kind.
# docs/start/capabilities.md walks through what each part prints, and
# .devcontainer/demo/devcontainer.json runs it in a Codespace.
#
#   bash scripts/demo.sh          every part, in order
#   bash scripts/demo.sh race     two workers push the same claim branch
#   bash scripts/demo.sh guard    the push guard judges six pushes
#   bash scripts/demo.sh board    the board rendered from a snapshot
#
# Why a local bare repository stands in for GitHub: a claim is the first
# push of claude/<issue>, and what refuses the second is git's own rule that
# a push may not replace a branch with history it does not contain. A bare
# repository on disk applies the same rule GitHub does, so the race below is
# the real mechanism and not a simulation of it. Everything it makes lives
# in one temporary folder, deleted when the script ends, and it never reads
# or writes your own git configuration.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WORK=$(mktemp -d "${TMPDIR:-/tmp}/symphony-demo.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

# git reads none of the person's settings, and no background maintenance
# outlives the temporary folder
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_DATE="2026-10-20T09:00:00Z" GIT_COMMITTER_DATE="2026-10-20T09:00:00Z"
# git does not hand these to the receive-pack a local push starts, so
# make_origin sets receive.autogc in the bare repository's own config too
export GIT_CONFIG_COUNT=4
export GIT_CONFIG_KEY_0=gc.auto GIT_CONFIG_VALUE_0=0
export GIT_CONFIG_KEY_1=gc.autoDetach GIT_CONFIG_VALUE_1=false
export GIT_CONFIG_KEY_2=maintenance.auto GIT_CONFIG_VALUE_2=false
export GIT_CONFIG_KEY_3=maintenance.autoDetach GIT_CONFIG_VALUE_3=false

heading() {
  printf '\n== %s ==\n\n' "$1"
}

say() {
  printf '%s\n' "$*"
}

quiet_git() {
  git -C "$1" "${@:2}" >/dev/null 2>&1
}

make_origin() {
  git init --quiet --bare --initial-branch=main "$WORK/origin.git"
  quiet_git "$WORK/origin.git" config receive.autogc false
  git init --quiet --initial-branch=main "$WORK/seed"
  printf '# demo\n' >"$WORK/seed/README.md"
  quiet_git "$WORK/seed" add README.md
  quiet_git "$WORK/seed" -c user.name=owner -c user.email=owner@example.invalid commit -m "First commit"
  quiet_git "$WORK/seed" remote add origin "$WORK/origin.git"
  quiet_git "$WORK/seed" push origin main
}

clone_as() {
  local name=$1
  git clone --quiet "$WORK/origin.git" "$WORK/$name" 2>/dev/null
  quiet_git "$WORK/$name" config user.name "$name"
  quiet_git "$WORK/$name" config user.email "$name@example.invalid"
}

# The first commit of a claim branch adds the claim file and nothing else
# (docs/agents/PROTOCOL.md, Claim).
write_claim() {
  local name=$1 issue=$2
  quiet_git "$WORK/$name" switch --quiet --no-track -c "claude/$issue" origin/main
  mkdir -p "$WORK/$name/docs/agents/claims"
  cat >"$WORK/$name/docs/agents/claims/$issue.md" <<EOF
# Claim: #$issue

- Issue: https://github.com/octo/widgets/issues/$issue
- Worker: $name
- Branch: claude/$issue

## Plan

$name's plan for #$issue.

## Files to touch

- src/widget.py
EOF
  quiet_git "$WORK/$name" add docs/agents/claims
  quiet_git "$WORK/$name" commit -m "Claim #$issue"
}

push_claim() {
  local name=$1 issue=$2
  if git -C "$WORK/$name" push --quiet origin "claude/$issue" 2>"$WORK/push.err"; then
    say "  $name: push of claude/$issue accepted, so #$issue is $name's"
  else
    say "  $name: push of claude/$issue refused by origin:"
    sed -n 's/^/      /; /rejected/p' "$WORK/push.err"
    say "  so $name picks another issue; nobody overwrote anybody"
  fi
}

race() {
  heading "1. Two workers claim issue #7 at the same moment"
  make_origin
  clone_as alice
  clone_as bob
  say "Both workers branch claude/7 from main and commit a claim file naming themselves."
  write_claim alice 7
  write_claim bob 7
  say "Both push. Whoever reaches origin first holds the claim:"
  push_claim alice 7
  push_claim bob 7
  say ""
  say "What origin holds now:"
  git -C "$WORK/alice" fetch --quiet origin
  git -C "$WORK/alice" show origin/claude/7:docs/agents/claims/7.md | sed -n 's/^- Worker: /  claude\/7 is held by: /p'
}

guard_says() {
  local clone=$1 command=$2 reason status=0
  local payload
  payload=$(printf '{"cwd": "%s", "tool_input": {"command": "%s"}}' "$WORK/$clone" "$command")
  reason=$(printf '%s' "$payload" | python3 "$ROOT/tools/guard_push.py" 2>&1) || status=$?
  # exit code 2 is the hook's refusal; anything else but 0 is the guard
  # failing to run, which must never read as a refusal
  case $status in
    0) say "  allowed  $command" ;;
    2) say "  REFUSED  $command"; say "           $reason" ;;
    *) say "  the guard could not run (exit $status): $reason" >&2; exit 1 ;;
  esac
}

guard() {
  heading "2. The push guard judges each push before it runs"
  [ -d "$WORK/bob" ] || { make_origin; clone_as alice; clone_as bob; write_claim alice 7; push_claim alice 7 >/dev/null; write_claim bob 7; }
  say "Claude Code runs tools/guard_push.py before every shell command a session"
  say "types; exit code 2 stops the command. Here it judges six from bob's clone:"
  say ""
  guard_says bob "git push origin main"
  guard_says bob "git push --force origin claude/7"
  guard_says bob "git push origin +claude/7"
  guard_says bob "git push origin claude/07"
  quiet_git "$WORK/bob" fetch origin
  say ""
  say "  bob fetches, and now git itself would take a lease onto alice's claim,"
  say "  since bob's copy of origin/claude/7 matches origin. The guard reads both"
  say "  claim files first:"
  guard_says bob "git push --force-with-lease origin claude/7"
  say ""
  write_claim bob 8 2>/dev/null || true
  guard_says bob "git push origin claude/8"
}

board() {
  heading "3. The board, rendered from a snapshot of a repository"
  say "board.yml runs this on every issue, push and pull request event, against"
  say "GitHub's API; --dry-run reads the same facts from tests/fixtures/board.json."
  say ""
  python3 "$ROOT/tools/board.py" --dry-run "$ROOT/tests/fixtures/board.json"
}

case "${1:-all}" in
  race) race ;;
  guard) guard ;;
  board) board ;;
  all) race; guard; board ;;
  *) say "usage: bash scripts/demo.sh [race|guard|board]" >&2; exit 64 ;;
esac
