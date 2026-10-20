#!/usr/bin/env bash
# Set up a repository made from this template from a browser tab alone: a
# GitHub Codespace on the repository runs this script, so the steps that
# needed gh and claude on a computer of your own (scripts/setup-repo.sh and
# scripts/tokens.py) run in the Codespace's terminal, and every sign-in they
# ask for opens in a tab of the browser the Codespace runs in.
#
#   bash scripts/codespace.sh install   what .devcontainer/devcontainer.json
#                                       runs once when the Codespace is made:
#                                       Claude Code; the Codespace's terminal
#                                       then starts the setup by itself the
#                                       first time it opens (its profile)
#   bash scripts/codespace.sh           the setup: a GitHub sign-in of your
#                                       own, the repository's settings, then
#                                       the token wizard, one account at a time
#
# Why a sign-in of your own: the token a Codespace is given (GITHUB_TOKEN)
# reaches only its repository's contents, so it can set no ruleset, no
# repository setting and no organization secret. gh is signed in again, in
# the browser with a one-time code, as you; that sign-in stays in this
# Codespace and goes when you delete it; the Tokens page's one press hands
# over its own sign-in instead (token_only). The Claude token is never on the
# screen or in a file: tokens.py catches what claude setup-token prints and
# hands it to gh, which seals it for GitHub, as on a computer of your own.
set -euo pipefail
# a stop is never silent: the terminal says where, and how to start again
trap 'echo "Symphony setup stopped at line $LINENO of scripts/codespace.sh; run: bash scripts/codespace.sh" >&2' ERR

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DONE_MARK="$HOME/.symphony-setup-started"
SCOPES="repo,workflow,admin:org"

install() {
  # a Codespace's folder may belong to another user than the one its
  # terminals run as, and git then refuses to read it ("dubious ownership")
  git config --global --add safe.directory "$ROOT"
  if ! command -v claude >/dev/null 2>&1; then
    npm install -g @anthropic-ai/claude-code
  fi
}

github_sign_in() {
  # the Codespace's own token would win over a sign-in, so gh is run without it
  if as_you gh auth status >/dev/null 2>&1; then
    echo "gh is signed in as you already."
    return
  fi
  echo "Sign in to GitHub as yourself: gh shows a one-time code and opens github.com/login/device in a tab."
  as_you gh auth login --web --git-protocol https --scopes "$SCOPES"
}

# The repository this Codespace is on: GitHub names it in GITHUB_REPOSITORY,
# so nothing depends on the clone's remote, and the clone's origin otherwise.
repository() {
  if [[ "${GITHUB_REPOSITORY:-}" =~ ^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$ ]]; then
    echo "$GITHUB_REPOSITORY"
    return
  fi
  git -C "$ROOT" remote get-url origin 2>/dev/null | sed -E -n 's#^.*github\.com[:/]([^/]+/[^/]+)/?$#\1#p' | sed 's/\.git$//'
}

# Where the tokens go, as tokens.py takes it: an organization's secrets seen
# by this repository, or a personal account's repository's own.
token_place() {
  local repo=$1 kind
  kind=$(as_you gh api "repos/$repo" --jq .owner.type)
  if [ "$kind" = "Organization" ]; then
    echo "--org ${repo%%/*} --repos ${repo#*/}"
  else
    echo "--repo $repo"
  fi
}

# gh as you: never with the Codespace's own GITHUB_TOKEN, and with the sign-in the
# Tokens page handed over where it did (HANDOVER, set in token_only alone)
HANDOVER=""
as_you() {
  if [ -n "$HANDOVER" ]; then
    env -u GITHUB_TOKEN GH_TOKEN="$HANDOVER" "$@"
  else
    env -u GITHUB_TOKEN -u GH_TOKEN "$@"
  fi
}

# The control panel's Tokens page starts this Codespace with
# .devcontainer/token/devcontainer.json, which sets SYMPHONY_SETUP=token: the
# setup is then one account into the next free slot and nothing else, the
# repository's settings left alone and no question asked. Where the page
# could, it handed over its own GitHub sign-in as your Codespaces secret
# SYMPHONY_GITHUB_HANDOVER, which only your Codespaces on this repository see
# and which the page deletes once the slot is saved; gh then works with it and
# asks for no code. Otherwise gh signs in here as you, with a one-time code.
token_only() {
  local repo=$1
  echo "Symphony: a Claude token for the next free slot of $repo, as the Tokens page asked."
  HANDOVER=${SYMPHONY_GITHUB_HANDOVER:-}
  if [ -n "$HANDOVER" ] && ! as_you gh api user --jq .login >/dev/null 2>&1; then
    echo "The sign-in the Tokens page handed over no longer works; signing in here instead."
    HANDOVER=""
  fi
  [ -n "$HANDOVER" ] || github_sign_in
  echo "Now sign in to claude.ai in the tab that opens, as the account for the new slot, and press Authorize."
  # shellcheck disable=SC2046 # the place is two or four words, split on purpose
  as_you python3 scripts/tokens.py $(token_place "$repo") add
  echo "Done: the Tokens page sees the new slot within a few seconds. You can close this tab."
}

# The setup task can open before the Codespace's postCreateCommand has put
# Claude Code in place, so it waits for it a while.
wait_for_claude() {
  local tries=0
  until command -v claude >/dev/null 2>&1; do
    [ "$tries" -eq 0 ] && echo "Waiting for Claude Code to finish installing..."
    tries=$((tries + 1))
    if [ "$tries" -gt 60 ]; then
      echo "Claude Code is not installed yet; run 'bash scripts/codespace.sh install', then 'bash scripts/codespace.sh'." >&2
      exit 1
    fi
    sleep 5
  done
}

setup() {
  cd "$ROOT"
  wait_for_claude
  git config --global --get-all safe.directory 2>/dev/null | grep -qx "$ROOT" || git config --global --add safe.directory "$ROOT"
  local repo place
  repo=$(repository)
  if [ -z "$repo" ]; then
    echo "This Codespace does not say which repository it is on; run: bash scripts/codespace.sh OWNER/NAME" >&2
    exit 1
  fi
  if [ "${SYMPHONY_SETUP:-}" = "token" ]; then
    token_only "$repo"
    return
  fi
  echo "Symphony setup for $repo: its GitHub settings, then its Claude tokens. Ctrl-C stops it; run 'bash scripts/codespace.sh' to start again."
  github_sign_in
  echo
  echo "== 1 of 2: the repository's settings (the ruleset, auto-merge, the labels, scanning)"
  as_you bash scripts/setup-repo.sh "$repo" || echo "The settings stopped at the line above; the tokens come next."
  echo
  echo "== 2 of 2: Claude tokens, one account at a time"
  # shellcheck disable=SC2046 # the place is two or four words, split on purpose
  as_you python3 scripts/tokens.py $(token_place "$repo")
  echo "Done. Run 'bash scripts/codespace.sh' to do it again, and delete this Codespace when you have finished:"
  echo "https://github.com/codespaces"
}

case "${1:-}" in
  install) install ;;
  "") setup ;;
  # the terminal profile in .devcontainer/ runs this in every new terminal;
  # the setup starts by itself only in the first
  auto) [ -e "$DONE_MARK" ] && exit 0; touch "$DONE_MARK"; setup ;;
  */*) GITHUB_REPOSITORY=$1 setup ;;
  -h|--help) sed -n '2,22p' "${BASH_SOURCE[0]}" ;;
  *) echo "usage: bash scripts/codespace.sh [install | OWNER/NAME]" >&2; exit 2 ;;
esac
