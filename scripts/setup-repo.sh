#!/usr/bin/env bash
# Set up the GitHub side of a repository made from this template, in one
# command.
#
# "Use this template" copies files and nothing else: the new repository has
# no branch rules, none of the toggles, no labels, no secret and no
# variable, and GitHub lets only a person with admin rights set them.
# docs/setup/github.md says what each setting is for and
# docs/setup/owner-checklist.md gathers every step; this script does the
# GitHub steps through the GitHub CLI, so they are one run instead of seven
# settings pages. Run it once on your own computer, from a clone, with gh
# signed in (gh auth login) as a user with admin rights on the repository. A
# cloud session cannot run it: gh is installed there, but its GitHub proxy
# refuses gh's GraphQL commands and the session has no admin rights. Running
# it again does nothing twice: a ruleset that exists is skipped, a toggle
# that is on stays on, a label is updated in place. In a crowd repository
# (docs/setup/crowdsourcing.md), whose variable CLAUDE_CROWD is true or
# whose docs/project.md says crowd mode is on, it stops before any write,
# and so it does when it cannot read the variable: it would turn auto-merge
# on and can store a subscription token, and crowd mode keeps both off;
# scripts/crowd.py setup is that repository's one command instead.
#
# What it does, in order, one line of output per step:
#   1. finds the repository (the argument, or the clone's remote) and its
#      default branch, and stops when crowd mode is on there, or when it
#      cannot tell;
#   2. creates the ruleset docs/setup/ruleset-main.json unless one of that
#      name is already listed for the repository; on GitHub Free a private
#      repository's ruleset is written but not enforced (docs/setup/tiers.md),
#      and the script says so when the repository is private; then pins
#      its check "check" to GitHub Actions, once Actions has reported that
#      check on the default branch, so a commit status anyone with write
#      access sets cannot stand in for it (run it again after the first
#      pull request's check to pin a new copy), and turns "Require
#      branches to be up to date" off where the ruleset has it on;
#   3. turns on "Automatically delete head branches" and "Allow auto-merge"
#      (auto-merge does nothing until a pull request asks for it, and team
#      mode needs it), and adds the repository topic symphony, the sign on
#      the repository's page that it is set up, which the front door's run
#      sets too and the Symphony browser extension reads to show "Ready
#      for Symphony" in place of "Migrate to Symphony";
#   4. turns on secret scanning, then push protection, which GitHub accepts
#      only once scanning is on; where the plan or the visibility offers
#      neither (a Free organization's private repository has no Secret
#      Protection) it prints why and carries on, and a gh older than 2.65,
#      which lacks the two flags, is reported as that and not as the plan;
#   5. turns on "Allow GitHub Actions to create and approve pull requests"
#      unless it is on already, keeping the token's default permissions as
#      they are: the weekly protocol update and the "Add a worker" form
#      open their pull requests with GITHUB_TOKEN, and while it is off they
#      offer an issue or a link instead; where the organization or its
#      enterprise holds it off, it prints GitHub's answer and where an
#      owner turns it on, and carries on;
#      then makes the environment token-store, limited to the default
#      branch, unless the repository has one of that name, so only the
#      default branch's Token workflow ever holds the SymphonyBoard App's
#      token there (Symphony Setup makes it in an adoption too);
#      then turns on GitHub Pages with GitHub Actions as its source and
#      sets the variable SYMPHONY_DOCS to pages, so
#      .github/workflows/docs.yml publishes the living documentation site
#      (docs/learn/README.md) from its next run on the default branch,
#      readable only by the repository's readers unless it is public; a
#      Pages site the repository has already is left as it is, and where
#      the plan offers no Pages, or no limited one for a repository that
#      is not public, it says so and goes on;
#   6. creates or updates the labels, read from LABELS in
#      tools/template_init.py, so the list lives in one place;
#   7. sets each repository variable given as --var NAME=VALUE; the one
#      this repository reads is CLAUDE_ALLOWED_TOOLS (docs/setup/claude-action.md),
#      since its workers are files, not variables (docs/agents/WORKERS.md);
#   8. with --token, stores the repository secret CLAUDE_CODE_OAUTH_TOKEN:
#      you run `claude setup-token` in another terminal and paste the token
#      at gh's hidden prompt. The token is never on a command line, never in
#      a file and never in this script's output: gh reads it without echo
#      (or from standard input when no terminal is attached), encrypts it on
#      your machine and sends only the sealed value. Without --token the
#      step prints the alternative, /install-github-app in Claude Code;
#   9. reads GitHub's own list of the errors in .github/CODEOWNERS and
#      prints each one, since a line GitHub cannot resolve (an
#      organization's name, a user or a team without Write) asks nobody for
#      review and says so nowhere else; it changes nothing, the fix is a
#      pull request (docs/setup/github.md, section 7).
#
# Usage: bash scripts/setup-repo.sh [OWNER/NAME] [--var NAME=VALUE]... [--token]
set -euo pipefail
cd "$(dirname "$0")/.."

RULESET=docs/setup/ruleset-main.json
SECRET=CLAUDE_CODE_OAUTH_TOKEN

usage() {
  cat <<'EOF'
Usage: bash scripts/setup-repo.sh [OWNER/NAME] [--var NAME=VALUE]... [--token]

Sets up the GitHub side of a repository made from this template: the
default branch's ruleset, delete-branch-on-merge, auto-merge, secret
scanning with push protection, the setting that lets GitHub Actions open
pull requests, GitHub Pages built by Actions, the labels, the variables
asked for and, with --token, the secret CLAUDE_CODE_OAUTH_TOKEN; then
prints any line of
.github/CODEOWNERS GitHub cannot resolve. Needs the GitHub CLI signed in
(gh auth login) with admin rights on the repository. In crowd mode (the
variable CLAUDE_CROWD is true, or docs/project.md says crowd mode is on)
it changes nothing: run python3 scripts/crowd.py setup instead. It
changes nothing either when it cannot read that variable.

  OWNER/NAME        the repository; by default the one this clone's
                    remote points at
  --var NAME=VALUE  set a repository variable; repeatable. The variable
                    this repository reads: CLAUDE_ALLOWED_TOOLS
                    (docs/setup/claude-action.md); its workers are files
                    under .github/symphony/workers/ (docs/agents/WORKERS.md)
  --token           store the secret CLAUDE_CODE_OAUTH_TOKEN from a hidden
                    prompt: run `claude setup-token` in another terminal
                    first and paste what it prints
  -h, --help        this text
EOF
}

die() {
  printf 'setup-repo: %s\n' "$1" >&2
  exit "${2:-1}"
}

REPO=""
VARIABLES=()
TOKEN=no
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --var) [ $# -ge 2 ] || die "--var needs NAME=VALUE" 2; VARIABLES+=("$2"); shift 2 ;;
    --var=*) VARIABLES+=("${1#--var=}"); shift ;;
    --token) TOKEN=yes; shift ;;
    -*) usage >&2; die "unknown option $1" 2 ;;
    *) [ -z "$REPO" ] || die "one repository at a time: $REPO and $1" 2; REPO="$1"; shift ;;
  esac
done
for pair in ${VARIABLES[@]+"${VARIABLES[@]}"}; do
  case "$pair" in
    [A-Za-z_]*=*) ;;
    *) die "--var takes NAME=VALUE, not $pair" 2 ;;
  esac
done

# The check's pin and the up-to-date rule: one line each, and one PUT only
# where the ruleset needs either change. The pin is made only where GitHub
# Actions has reported "check" on the default branch and the ruleset does
# not name a source for it yet. "Require branches to be up to date" is
# turned off wherever it is on, since every merge then made each other
# ready pull request behind, its check run again on a branch that changed
# nothing it touched, and a copy made before the shipped rulesets dropped
# it keeps it until this runs. Every failure is reported and the run goes on.
ACTIONS_APP=15368
# One read for the step: GitHub's body on standard output, and on a failure
# gh's first line of standard error alone, since gh prints a refused call's
# body on standard output too.
pin_read() {
  local error answer
  error=$(mktemp)
  if answer=$(gh api "$@" 2>"$error"); then
    rm -f "$error"
    printf '%s' "$answer"
  else
    head -n 1 "$error"
    rm -f "$error"
    return 1
  fi
}
pin_check() {
  local name=$1 id rulesets reported ruleset body answer status pin pinned strict changed
  # The repository's own rulesets alone: an organization's ruleset of the
  # same name is listed too by default, and only its owners edit it.
  if ! rulesets=$(pin_read "repos/$REPO/rulesets?includes_parents=false&per_page=100"); then
    echo "check pin: not changed (could not list the rulesets: $rulesets)"
    echo "up-to-date rule: not changed (could not list the rulesets)"
    return 0
  fi
  id=$(printf '%s' "$rulesets" | python3 -c 'import json, sys
try:
    rulesets = json.load(sys.stdin)
except ValueError:
    rulesets = []
print(next((str(r["id"]) for r in rulesets if isinstance(r, dict) and r.get("name") == sys.argv[1]), ""))' "$name") || id=""
  if [ -z "$id" ]; then
    echo "check pin: not changed (the repository has no ruleset \"$name\" of its own; an organization's ruleset is pinned by its owners under the organization's Settings, Rules)"
    echo "up-to-date rule: not changed (no ruleset \"$name\" of the repository's own; an organization's is changed by its owners)"
    return 0
  fi
  pin=""
  if ! reported=$(pin_read "repos/$REPO/commits/$DEFAULT_BRANCH/check-runs?check_name=check&per_page=100" \
      --jq "[.check_runs[] | select(.app.id == $ACTIONS_APP)] | length"); then
    pin="check pin: not changed (could not read the default branch's checks: $reported)"
    reported=0
  elif [ "$reported" = "0" ] || [ -z "$reported" ]; then
    pin="check pin: not yet; GitHub Actions has not reported \"check\" on $DEFAULT_BRANCH, so run this again after the first pull request's check"
    reported=0
  fi
  if ! ruleset=$(pin_read "repos/$REPO/rulesets/$id"); then
    echo "${pin:-check pin: not changed (could not read the ruleset: $ruleset)}"
    echo "up-to-date rule: not changed (could not read the ruleset: $ruleset)"
    return 0
  fi
  status=0
  changed=$(mktemp)
  # The script prints the new body, or nothing where nothing changes, and
  # on standard error the two words that say what it changed.
  body=$(printf '%s' "$ruleset" | python3 -c 'import json, sys
ruleset, app, reported = json.load(sys.stdin), int(sys.argv[1]), sys.argv[2] != "0"
rules = [rule for rule in ruleset.get("rules") or [] if rule.get("type") == "required_status_checks"]
checks = [check for rule in rules for check in (rule.get("parameters") or {}).get("required_status_checks") or []
          if check.get("context") == "check"]
pinned = reported and any(not check.get("integration_id") for check in checks)
strict = any((rule.get("parameters") or {}).get("strict_required_status_checks_policy") for rule in rules)
for check in checks if pinned else []:
    check["integration_id"] = check.get("integration_id") or app
for rule in rules if strict else []:
    rule["parameters"]["strict_required_status_checks_policy"] = False
print("pinned" if pinned else "same", "unstrict" if strict else "same", file=sys.stderr)
if pinned or strict:
    keys = ("name", "target", "enforcement", "conditions", "rules", "bypass_actors")
    json.dump({key: ruleset[key] for key in keys if key in ruleset}, sys.stdout)' "$ACTIONS_APP" "$reported" 2>"$changed") || status=$?
  read -r pinned strict <"$changed" || true
  rm -f "$changed"
  if [ "$status" != 0 ]; then
    echo "${pin:-check pin: not changed (the ruleset GitHub gave back could not be read)}"
    echo "up-to-date rule: not changed (the ruleset GitHub gave back could not be read)"
    return 0
  fi
  [ -n "$pin" ] || [ "$pinned" = pinned ] || pin="check pin: already pinned, or the ruleset requires no check named \"check\""
  if [ -z "$body" ]; then
    echo "$pin"
    echo "up-to-date rule: off already"
    return 0
  fi
  if answer=$(printf '%s' "$body" | gh api --method PUT "repos/$REPO/rulesets/$id" --input - --silent 2>&1); then
    [ "$pinned" = pinned ] && pin="check pin: \"check\" now requires GitHub Actions as its source"
    echo "$pin"
    if [ "$strict" = unstrict ]; then echo "up-to-date rule: turned off"; else echo "up-to-date rule: off already"; fi
  else
    [ "$pinned" = pinned ] && pin="check pin: not changed ($answer); pick GitHub Actions as the check's source under https://github.com/$REPO/settings/rules/$id"
    echo "$pin"
    if [ "$strict" = unstrict ]; then
      echo "up-to-date rule: not changed ($answer); untick \"Require branches to be up to date before merging\" under https://github.com/$REPO/settings/rules/$id"
    else
      echo "up-to-date rule: off already"
    fi
  fi
}

# 1. The repository and its default branch, in one call. gh reads the
# clone's remote when no repository is named.
if [ -n "$REPO" ]; then
  view=$(gh repo view "$REPO" --json nameWithOwner,defaultBranchRef,visibility --jq '[.nameWithOwner, .defaultBranchRef.name, .visibility] | @tsv')
else
  view=$(gh repo view --json nameWithOwner,defaultBranchRef,visibility --jq '[.nameWithOwner, .defaultBranchRef.name, .visibility] | @tsv')
fi
IFS=$'\t' read -r REPO DEFAULT_BRANCH VISIBILITY <<<"$view"
VISIBILITY=$(printf '%s' "$VISIBILITY" | tr '[:upper:]' '[:lower:]')
printf 'repository: %s (default branch %s, %s)\n' "$REPO" "$DEFAULT_BRANCH" "$VISIBILITY"

# Crowd mode keeps auto-merge off and holds no Claude token, and the steps
# below turn auto-merge on and can store one, so they never run there. Two
# signs say crowd mode: this clone's docs/project.md, whose mode line only
# the owner's review changes, and the variable CLAUDE_CROWD. A 404, no such
# variable, is the ordinary case; any other failure to read it (a token
# without the right to read variables, a rate limit, the network) leaves
# the mode unknown, and the script stops rather than guess; GitHub compares
# the value without case, and so does this.
crowd_refusal="scripts/setup-repo.sh would turn auto-merge on and can store a subscription token; run python3 scripts/crowd.py setup $REPO instead, which keeps both off"
if grep -q '^- Crowd mode: on\.' docs/project.md 2>/dev/null; then
  die "crowd mode is on in this clone's docs/project.md: $crowd_refusal"
fi
read_error=$(mktemp)
if [ "${SYMPHONY_SETTINGS_APP:-}" = 1 ] && [ -n "${SYMPHONY_CROWD_VARIABLE+set}" ]; then
  # The Settings workflow reads the variable from its own vars context,
  # which needs no permission, and hands it here, set but empty where the
  # repository has none.
  crowd="$SYMPHONY_CROWD_VARIABLE"
  rm -f "$read_error"
elif crowd=$(gh api "repos/$REPO/actions/variables/CLAUDE_CROWD" --jq .value 2>"$read_error"); then
  rm -f "$read_error"
elif grep -q '(HTTP 404)' "$read_error"; then
  crowd=""
  rm -f "$read_error"
elif [ "${SYMPHONY_SETTINGS_APP:-}" = 1 ]; then
  # The Settings workflow runs this with the App's token, whose
  # installation may not have accepted Variables yet: there the mode is
  # unknown, so auto-merge alone, the one setting crowd mode keeps off that
  # this run would make, is left off, and nothing else waits on it (the
  # workflow never stores a token).
  printf 'crowd mode: unknown (could not read the variable CLAUDE_CROWD: %s), so auto-merge is left as it is\n' "$(head -n 1 "$read_error")"
  rm -f "$read_error"
  crowd="" CROWD_UNKNOWN=yes
else
  reason=$(head -n 1 "$read_error")
  rm -f "$read_error"
  die "could not read the variable CLAUDE_CROWD ($reason), so whether crowd mode is on is unknown and nothing was changed; run this again with a login that can read the repository's variables, or, in a crowd repository, run python3 scripts/crowd.py setup $REPO instead"
fi
if [ "$(printf '%s' "$crowd" | tr '[:upper:]' '[:lower:]')" = "true" ]; then
  die "crowd mode is on (the variable CLAUDE_CROWD is true): $crowd_refusal"
fi

# The Settings workflow's weekly and visibility runs (SYMPHONY_SETTINGS_RECHECK)
# make only what a plan or a visibility may have held back, the
# environment and the Pages site, both made only when missing: a ruleset
# is written on any plan and starts to hold by itself once the plan or the
# visibility allows, and the toggles, the topic, scanning and the Actions
# box are left as the owner may have set them since.
RECHECK=no
[ "${SYMPHONY_SETTINGS_RECHECK:-}" = 1 ] && RECHECK=yes
if [ "$RECHECK" = yes ]; then
  echo "recheck: only the environment and Pages, where they are missing"
fi
if [ "$RECHECK" = no ]; then

# 2. The ruleset, from the file the docs ship, unless its name is already
# listed. GitHub would make a second ruleset of the same name, so the check
# is this script's job.
name=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["name"])' "$RULESET")
# A refusal is reported and the run goes on, as the steps below do, since
# one refused setting is no reason to leave the others undone.
if ! existing=$(gh api "repos/$REPO/rulesets" --jq '.[].name' 2>&1); then
  printf 'ruleset "%s": not created (could not list the rulesets: %s); import %s under https://github.com/%s/settings/rules\n' \
    "$name" "$(head -n 1 <<<"$existing")" "$RULESET" "$REPO"
elif grep -Fxq -- "$name" <<<"$existing"; then
  printf 'ruleset "%s": exists, skipped\n' "$name"
elif answer=$(gh api --method POST "repos/$REPO/rulesets" --input "$RULESET" --silent 2>&1); then
  printf 'ruleset "%s": created from %s\n' "$name" "$RULESET"
else
  printf 'ruleset "%s": not created (%s); import %s under https://github.com/%s/settings/rules\n' \
    "$name" "$(head -n 1 <<<"$answer")" "$RULESET" "$REPO"
fi
if [ "$VISIBILITY" = "private" ]; then
  echo "  note: on GitHub Free a private repository's ruleset is written but not enforced (docs/setup/tiers.md)"
fi

# 2b. The pin. A required check named by its context alone takes a commit
# status of that name from anyone with write access, whatever CI said, so
# the check "check" is pinned to GitHub Actions, the app its check runs
# report under. GitHub takes the pin only once that app has reported the
# check in the repository, so a new copy is pinned by a run of this script
# after its first pull request's check; until then the step says so. The
# same PUT turns "Require branches to be up to date" off in a ruleset that
# has it on, as a copy made before the shipped rulesets dropped it does.
pin_check "$name"

# 3. The two toggles under General. Both are idempotent PATCHes; where gh's
# own command is refused, as it can be for an App's token, the same PATCH
# goes through the REST API before the refusal is reported.
toggles=(--delete-branch-on-merge --enable-auto-merge)
fields=(-F delete_branch_on_merge=true -F allow_auto_merge=true)
said="delete head branches on merge, allow auto-merge"
if [ "${CROWD_UNKNOWN:-}" = yes ]; then
  toggles=(--delete-branch-on-merge) fields=(-F delete_branch_on_merge=true) said="delete head branches on merge"
fi
if gh repo edit "$REPO" "${toggles[@]}" 2>/dev/null \
   || answer=$(gh api --method PATCH "repos/$REPO" --silent "${fields[@]}" 2>&1); then
  echo "general: $said: on"
else
  printf 'general: %s: not changed (%s); tick them under https://github.com/%s/settings\n' "$said" "$(head -n 1 <<<"$answer")" "$REPO"
fi
# The topic keeps the ones already there: --add-topic appends.
if answer=$(gh repo edit "$REPO" --add-topic symphony 2>&1); then
  echo "topic symphony: added"
else
  printf 'topic symphony: not added (%s); add it under About on https://github.com/%s\n' "$(head -n 1 <<<"$answer")" "$REPO"
fi

# 4. Secret scanning, then push protection. A failure here is the plan or
# the visibility, not the script, so it is reported and the run goes on;
# except "unknown flag", which is a gh older than 2.65.0, the first release
# with these two flags (a distribution's package often is), and blaming the
# plan for that would leave scanning off for good.
old_gh() {
  printf '%s: this gh (%s) predates the flag; install gh 2.65 or later (https://github.com/cli/cli/blob/trunk/docs/install_linux.md) and run this again\n' "$1" "$(gh --version | head -n 1)"
}
# gh asks GraphQL whether the caller administers the repository before
# these two, which an App's token may be told no to; the REST PATCH is the
# same setting, tried before the refusal is reported.
scanning() {
  gh repo edit "$REPO" "$1" 2>&1 \
    || gh api --method PATCH "repos/$REPO" --silent -f "security_and_analysis[$2][status]=enabled" 2>/dev/null
}
if answer=$(scanning --enable-secret-scanning secret_scanning); then
  echo "secret scanning: on"
  if answer=$(scanning --enable-secret-scanning-push-protection secret_scanning_push_protection); then
    echo "push protection: on"
  elif grep -q "unknown flag" <<<"$answer"; then
    old_gh "push protection"
  else
    printf 'push protection: not available here (%s); turn it on by hand if the plan offers it\n' "$(tr '\n' ' ' <<<"$answer")"
  fi
elif grep -q "unknown flag" <<<"$answer"; then
  old_gh "secret scanning"
else
  printf 'secret scanning: not available here (%s); a Free organization'"'"'s private repository has no Secret Protection, docs/setup/github.md section 5\n' "$(tr '\n' ' ' <<<"$answer")"
fi

# 5. "Allow GitHub Actions to create and approve pull requests" (Settings,
# Actions, General, Workflow permissions), off in a new repository unless
# its organization has it on. .github/workflows/protocol.yml and
# add-worker.yml open their pull requests with GITHUB_TOKEN, which GitHub
# refuses while it is off, so they offer an issue or a link instead. The
# same setting lets a workflow approve a pull request, which counts only
# where a ruleset or a branch protection rule requires a review, and
# docs/setup/ruleset-main.json requires none. GitHub sets it together with
# the token's default permissions, so the PUT sends those back as they
# were read and nothing else changes; an answer that does not say them as
# the REST description gives them, "read" or "write" beside a JSON
# boolean, sends nothing, since a guess could widen the token. An
# organization, or the enterprise above it, can hold it off for its
# repositories, and GitHub then answers 409; only an owner there, or in
# the organization someone with the "Manage organization Actions
# policies" permission, can change that, so, as in the step above, a
# refusal is reported with where to change it and the run goes on. gh
# prints GitHub's answer to a refused call on standard error and the body
# on standard output, so the answer is read from standard error alone.
WORKFLOW_SETTING="workflow permissions: allow GitHub Actions to create and approve pull requests"
# The read's two fields on one line, such as "read false", or exit 1 when
# the answer does not hold both with those types.
READ_WORKFLOW_PERMISSIONS='
import json, sys
try:
    answer = json.load(sys.stdin)
except ValueError:
    sys.exit(1)
fields = answer if isinstance(answer, dict) else {}
permissions = fields.get("default_workflow_permissions")
can_approve = fields.get("can_approve_pull_request_reviews")
if permissions not in ("read", "write") or not isinstance(can_approve, bool):
    sys.exit(1)
print(permissions, "true" if can_approve else "false")
'
workflow_setting_refused() {
  local answer=${1//$'\n'/ } organization=${REPO%%/*} owner_type
  if grep -q "unknown flag" <<<"$answer"; then
    old_gh "workflow permissions"
  elif grep -q '(HTTP 409)' <<<"$answer"; then
    # Only an organization has the settings page named below; a personal
    # account's repository, or one whose owner cannot be read, gets
    # GitHub's answer and its own page.
    owner_type=$(gh api "repos/$REPO" --jq .owner.type 2>/dev/null || true)
    if [ "$owner_type" = Organization ]; then
      printf '%s: held off by the policy of %s or its enterprise (%s); an owner of %s turns it on under https://github.com/organizations/%s/settings/actions, Workflow permissions, or, where the enterprise sets it, an owner of the enterprise under its Policies, Actions; then run this again\n' \
        "$WORKFLOW_SETTING" "$organization" "$answer" "$organization" "$organization"
    else
      printf '%s: held off by a policy above this repository (%s); turn it on under https://github.com/%s/settings/actions, Workflow permissions, once that page allows it, then run this again\n' \
        "$WORKFLOW_SETTING" "$answer" "$REPO"
    fi
  else
    printf '%s: not changed (%s); turn it on by hand under https://github.com/%s/settings/actions, Workflow permissions, with admin rights on the repository\n' \
      "$WORKFLOW_SETTING" "$answer" "$REPO"
  fi
}
refusal=$(mktemp)
if ! workflow_answer=$(gh api "repos/$REPO/actions/permissions/workflow" 2>"$refusal"); then
  workflow_setting_refused "$(<"$refusal")"
elif ! permissions=$(python3 -c "$READ_WORKFLOW_PERMISSIONS" <<<"$workflow_answer"); then
  workflow_setting_refused "GitHub's answer did not say the token's default permissions, so nothing was sent back"
else
  read -r default_permissions can_approve <<<"$permissions"
  if [ "$can_approve" = true ]; then
    echo "$WORKFLOW_SETTING: on already"
  elif gh api --method PUT "repos/$REPO/actions/permissions/workflow" --silent \
         -f default_workflow_permissions="$default_permissions" -F can_approve_pull_request_reviews=true 2>"$refusal"; then
    echo "$WORKFLOW_SETTING: on"
  else
    workflow_setting_refused "$(<"$refusal")"
  fi
fi
rm -f "$refusal"

fi

# 5b. The environment token-store, limited to the default branch. The Token
# workflow (.github/workflows/token.yml) saves a lent Claude token there
# with the SymphonyBoard App's key, and GitHub would make the environment
# on its first run open to every branch, so a workflow pushed to any branch
# could run the job that holds the App's token. An environment of that name
# the repository has already is left as it is; a refusal is reported with
# the page to make it on, and the run goes on.
STORE=token-store
store_refused() {
  printf 'environment %s: not made (%s); make it at https://github.com/%s/settings/environments/new and, under Deployment branches and tags, choose %s alone\n' \
    "$STORE" "$(head -n 1 <<<"$1")" "$REPO" "$DEFAULT_BRANCH"
}
refusal=$(mktemp)
# An empty repository has no default branch, and read then shifts the
# visibility into its place, so the branch must look like one.
if [ -z "$VISIBILITY" ] || ! git check-ref-format --branch "$DEFAULT_BRANCH" >/dev/null 2>&1; then
  echo "environment $STORE: not made, since the default branch is not known yet; run this again after the first commit"
elif gh api "repos/$REPO/environments/$STORE" --silent 2>"$refusal"; then
  echo "environment $STORE: exists, left as it is"
elif ! grep -q '(HTTP 404)' "$refusal"; then
  store_refused "$(<"$refusal")"
elif ! gh api --method PUT "repos/$REPO/environments/$STORE" --silent \
       -F 'deployment_branch_policy[protected_branches]=false' \
       -F 'deployment_branch_policy[custom_branch_policies]=true' 2>"$refusal"; then
  store_refused "$(<"$refusal")"
elif ! gh api --method POST "repos/$REPO/environments/$STORE/deployment-branch-policies" --silent \
       -f name="$DEFAULT_BRANCH" -f type=branch 2>"$refusal"; then
  # the environment stands with no branch allowed, so nothing runs there
  # until the rule is added by hand
  printf 'environment %s: made with no branch allowed (%s); open https://github.com/%s/settings/environments, press %s and, under Deployment branches and tags, add %s\n' \
    "$STORE" "$(head -n 1 "$refusal")" "$REPO" "$STORE" "$DEFAULT_BRANCH"
else
  echo "environment $STORE: made, $DEFAULT_BRANCH only"
fi
rm -f "$refusal"

# 5c. GitHub Pages, built by GitHub Actions, for the living documentation
# site: docs.yml deploys it where Pages is set to that source and the
# variable SYMPHONY_DOCS is pages, and its token cannot turn Pages on itself
# (creating a site needs admin rights). The script makes the site and sets
# the variable together. A site the repository has already, from a branch
# or from Actions, is left as it is and the variable unset, since the owner
# may publish something else there and docs.yml would deploy over it. On an
# internal or private repository the new site is limited to the people who
# can read the repository; where GitHub will not limit it (only Enterprise
# plans can), the site is removed again rather than left open to anyone. A
# refusal is reported with the page to set it on, and the run goes on.
pages_refused() {
  printf 'pages: not turned on (%s); open https://github.com/%s/settings/pages and, under Build and deployment, choose GitHub Actions as the source, then set the repository variable SYMPHONY_DOCS to pages\n' \
    "$(head -n 1 <<<"$1")" "$REPO"
}
# A limit GitHub accepted is read back before the site counts as limited,
# so a plan that takes the PUT and keeps the site open is caught.
pages_limited() {
  gh api --method PUT "repos/$REPO/pages" --silent -F public=false || return 1
  local public
  public=$(gh api "repos/$REPO/pages" --jq .public) || return 1
  if [ "$public" != false ]; then
    echo "GitHub took the limit, but the site still reads as public" >&2
    return 1
  fi
}
# A site that deploys from Actions and has never been published is the one
# an earlier run made before it could set the variable, since nothing else
# has deployed there, so it takes the variable now; any other site may be
# the owner's own and is left alone.
pages_found() {
  if [ "$1" != "workflow never" ] || [ -n "${SYMPHONY_DOCS_VARIABLE:-}" ]; then
    echo "pages: a site is there already, left as it is; docs.yml publishes the documentation site there only once the repository variable SYMPHONY_DOCS is pages"
  elif ! gh variable set SYMPHONY_DOCS --repo "$REPO" --body pages 2>"$refusal"; then
    printf 'pages: on, built by GitHub Actions and never published, but the variable SYMPHONY_DOCS was not set (%s); set it to pages at https://github.com/%s/settings/variables/actions\n' \
      "$(head -n 1 "$refusal")" "$REPO"
  else
    echo "pages: on, built by GitHub Actions and never published, so the variable SYMPHONY_DOCS is set to pages; docs.yml publishes the documentation site on its next run on $DEFAULT_BRANCH"
  fi
}
refusal=$(mktemp)
if [ "$RECHECK" = yes ] && [ -n "${SYMPHONY_DOCS_VARIABLE:-}" ]; then
  # SYMPHONY_DOCS is written once Pages is on, so set means decided: a site
  # the owner removed since is not put back.
  echo "pages: left as it is, since the variable SYMPHONY_DOCS is set"
elif site=$(gh api "repos/$REPO/pages" --jq '[.build_type, (.status // "never")] | join(" ")' 2>"$refusal"); then
  pages_found "$site"
elif ! grep -q '(HTTP 404)' "$refusal"; then
  pages_refused "$(<"$refusal")"
elif ! gh api --method POST "repos/$REPO/pages" --silent -f build_type=workflow 2>"$refusal"; then
  pages_refused "$(<"$refusal")"
elif [ "$VISIBILITY" != public ] && ! pages_limited 2>"$refusal"; then
  if gh api --method DELETE "repos/$REPO/pages" --silent 2>/dev/null; then
    removed="removed again"
  else
    removed="and could not be removed again, so turn it off at https://github.com/$REPO/settings/pages"
  fi
  printf 'pages: not turned on, since GitHub would not limit the site of this %s repository to its readers (%s) and it would be open to anyone; the site was %s; set it by hand at https://github.com/%s/settings/pages if that is meant\n' \
    "$VISIBILITY" "$(head -n 1 "$refusal")" "$removed" "$REPO"
elif ! gh variable set SYMPHONY_DOCS --repo "$REPO" --body pages 2>"$refusal"; then
  printf 'pages: turned on, built by GitHub Actions, but the variable SYMPHONY_DOCS was not set (%s); set it to pages at https://github.com/%s/settings/variables/actions\n' \
    "$(head -n 1 "$refusal")" "$REPO"
else
  echo "pages: turned on, built by GitHub Actions; docs.yml publishes the documentation site on its next run on $DEFAULT_BRANCH"
fi
rm -f "$refusal"

if [ "$RECHECK" = yes ]; then
  exit 0
fi

# 6. The labels, from the one list in tools/template_init.py. --force
# updates a label that exists instead of failing on it.
while IFS=$'\t' read -r label color description; do
  if answer=$(gh label create "$label" --repo "$REPO" --color "$color" --description "$description" --force 2>&1); then
    printf 'label %s: created or updated\n' "$label"
  else
    printf 'label %s: not made (%s)\n' "$label" "$(head -n 1 <<<"$answer")"
  fi
done < <(python3 -c '
import sys
sys.path.insert(0, "tools")
from template_init import LABELS
for name, color, description in LABELS:
    print(name, color, description, sep="\t")
')

# 7. The variables asked for.
if [ ${#VARIABLES[@]} -eq 0 ]; then
  echo "variables: none asked for (--var NAME=VALUE; docs/setup/claude-action.md names them)"
fi
for pair in ${VARIABLES[@]+"${VARIABLES[@]}"}; do
  gh variable set "${pair%%=*}" --repo "$REPO" --body "${pair#*=}"
  printf 'variable %s: set\n' "${pair%%=*}"
done

# 8. The secret, from gh's own hidden prompt; nothing is echoed or saved.
if [ "$TOKEN" = yes ]; then
  echo "In another terminal, run: claude setup-token"
  echo "Approve it in the browser, copy the token it prints, and paste it at the prompt below."
  echo "Nothing you paste is shown or saved; gh encrypts it on this machine before it is sent."
  gh secret set "$SECRET" --repo "$REPO"
  printf 'secret %s: set\n' "$SECRET"
else
  printf 'secret %s: skipped; run again with --token, or run /install-github-app in Claude Code, which installs the app and stores the secret in one OAuth flow (docs/setup/claude-action.md)\n' "$SECRET"
fi

# 9. GitHub's reading of .github/CODEOWNERS, after the secret's prompt so
# its lines are the last on the screen. A failed read (no such file on the
# default branch) is reported, not fatal: everything above is done.
if errors=$(gh api "repos/$REPO/codeowners/errors" --jq '.errors[] | "  line \(.line): \(.kind): \(.source)"' 2>&1); then
  if [ -z "$errors" ]; then
    echo "code owners: GitHub resolves every owner in .github/CODEOWNERS"
  else
    echo "code owners: GitHub cannot resolve these lines of .github/CODEOWNERS, so they ask nobody for review; name a user or a team with Write instead (docs/setup/github.md, section 7)"
    printf '%s\n' "$errors"
  fi
else
  printf 'code owners: could not read GitHub'"'"'s list (%s); open .github/CODEOWNERS on GitHub, which marks the lines it cannot resolve\n' "$(tr '\n' ' ' <<<"$errors")"
fi
