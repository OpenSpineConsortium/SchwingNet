
# Symphony as one versioned runtime that every copy calls

Design, read only, 2026-10-13. Measured at symphony-template a1d9695, symphony-start eac10fb, symphony-protocol cf3bdb0 (v0.4.0), spine-program 4b9a6fc. GitHub's documentation was read from github/docs `main` on raw.githubusercontent.com (paths given as `gh:<path>`), Claude Code's from code.claude.com/docs/en (`cc:<page>`). Drafts and simulations are under `/tmp/claude-0/-home-user/3dc8ab18-0f0b-58a6-80b3-e06fe3b0d17b/scratchpad/central/` (`copy/`, `central/`, `sim/`, `e2e/`). The whole design is also at `/tmp/claude-0/-home-user/3dc8ab18-0f0b-58a6-80b3-e06fe3b0d17b/scratchpad/central/design.md`.

## The answer in one paragraph

All of Symphony's logic moves into one public repository: symphony-protocol, which already holds the library and is already public, renamed `OpenSpineConsortium/symphony` before the first caller ships. It publishes eight reusable workflows behind one dispatcher, `symphony.yml`, and one composite action, `run`, with commands. Everything runs on the runner's python3 and the standard library. A whole-template copy then holds 38 files and about 1,070 lines instead of 145 files and 28,436 lines. A protocol-only copy holds 8 files and about 370 lines instead of 28 files and 7,776. The only executable things left in a copy are three thin workflow files (one for protocol only) and a 116-line bash bootstrap for the Claude Code hooks. Copies call the moving major tag `@v1` by default, so a release reaches every copy at its next event with no pull request; cautious copies pin a commit and take each release from Dependabot. The text Claude must read from the repository (PROTOCOL.md, the skills, the rules, the routine prompts) stays in the copy, and a central text-sync job keeps it current by pull request. Five things go away: vendoring into copies, protocol.yml, template-init in copies, the parked update route, and the sync's pull request to the template. The price is one owner decision: the runtime becomes public under the MIT terms copies already get, and only the template repository's history, research and internal notes stay private.

Decisions the design needs from the owner, worded for the decisions block:

- Decision: Symphony's runtime (the library, the template's tools, every workflow and the copy skeleton) is public under MIT in OpenSpineConsortium/symphony; the template repository, its history, its issues and its research stay private.
- Decision: copies call `@v1`, the moving major tag; a new major is made only for a change to what a copy's own workflow file must say.
- Decision: a release (the immutable tag and the move of `v1`) waits for one approval in the environment `release`, from an account no Claude session is signed in with.

## 0. What the copies look like today, measured

- **Size.** I simulated an adoption into an empty repository (`sim/`, with the front door's own `scripts/adopt.py apply`, template a1d9695).
  - Mode new lands 145 files, 28,436 lines, 1,785,294 bytes: 11 workflows (1,755 lines), `tools/` 33 files (9,820 lines: the vendored library 4,955, the template's tools 4,847), `scripts/` 3,357, `tests/` 20 files 8,396, `docs/` 54 files.
  - Mode existing lands 28 files, 7,776 lines, 362,927 bytes (`sim/manifest-existing.json`).
- **Drift has already broken adoptions.**
  - A protocol-only adoption made today copies only `tools/metrics.py` and `.github/workflows/metrics.yml` (`symphony-start scripts/adopt.py:117`, `METRICS_FILES`).
  - But the template's `metrics.py` imports `economics`, which imports `usage` (`symphony-template tools/metrics.py:90`, `tools/economics.py:29`).
  - Running the landed script in the simulation fails with `ModuleNotFoundError: No module named 'economics'`.
  - So every protocol-only adoption since symphony-template#57 (2026-10-12 13:56Z) has a metrics workflow whose script fails at import.
- **The front door's own code names the problem.**
  - `adopt.py:119-122`: "A repository keeps the script it was adopted with, since no later change of the template reaches it".
  - `README.md:48`: "no later change reaches your repository by itself".
  - The checkpoint (`.claude/session.md:59-62`): copies made before 2026-10-12 "get only the library, by protocol.yml's weekly pull request ... but not workers.yml, coordinator.yml, the form or the usage recording".
- **At least three generations are live after five days.**
  - OpenSpineConsortium/sdlc-template-test is at 76853d7 (2026-10-09). It has three workflows (board, ci, template-init) and no vendored library.
  - spine-program adopted the protocol only, on 2026-10-12 at 01:09Z (fd49afa).
    - Its `tools/VENDORED` says `sdlc-protocol 0.2.0 f530a66`, not 0.3.x as the brief has it; `vendoring.py verify` passes on 15 files.
    - It has no protocol.yml, so nothing will ever update it. It still uses the label `account:main`.
    - Its METRICS.json of 2026-10-12 carries none of the newer keys (by_setting, economics, coordination).
    - Its CLAUDE.md:150 says "the push guard is the symphony plugin's and runs in local sessions only".
  - Copies made after 2026-10-12 carry protocol.yml.
- **Cloud sessions cannot get Symphony from a plugin.** The Claude Code docs (`cc:cloud-environments`, "What carries over") say:
  - "Plugins and marketplaces declared in your repo's .claude/settings.json: No ... A cloud session doesn't install the plugins a repository turns on".
  - "Your repo's .claude/settings.json hooks: Yes".
  - That is why spine-program has no guard in the cloud, and why the hooks below stay wired in the repository.

## 1. Packaging

### 1.1 Both: reusable workflows for the jobs, one composite action for the code

Each form is forced where it is used:

- **The required check has to stay a job of the copy's own file.**
  - GitHub names a reusable workflow's job `<job name> / <reusable job name>`, and a plain workflow's job `<job name>` (`gh:content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules.md`).
  - Every copy's ruleset requires the context `check` (`docs/setup/ruleset-main.json`, applied by the Setup App, `symphony-start scripts/setup.py`).
  - So ci.yml keeps a job named `check`, and that job runs the composite action.
- **Everything else needs jobs, which only a reusable workflow has.**
  - The template's workflows need matrices (workers), several jobs (coordinator: route, plan, unblock, integrate, tidy), job-level concurrency, timeouts, per-job permissions and secrets.
  - A composite action "cannot contain jobs" and "cannot use secrets", and its log is one step; a reusable workflow's "every job and step is logged separately" (`gh:content/actions/concepts/workflows-and-actions/reusing-workflow-configurations.md`, comparison table).
  - "The secrets context is not available for composite actions" (`gh:.../contexts.md`).
- **Copies keep `on:` and `permissions:`; the central side keeps the rest.**
  - A job that calls a reusable workflow may only use `name, uses, with, secrets, strategy, needs, if, concurrency, permissions` (`gh:content/actions/reference/workflows-and-actions/reusing-workflow-configurations.md`, "Supported keywords").
  - So there is no `runs-on`, no `timeout-minutes`, no `env`, and workflow-level `env` is not propagated.
- **The copy's context flows through.**
  - "The github context is always associated with the caller workflow. The called workflow is automatically granted access to github.token" (same page).
  - "For reusable workflows, the variables from the caller workflow's repository are used" (`gh:.../variables.md`).
  - "If the called workflow uses actions/checkout, the action checks out the contents of the repository that hosts the caller workflow" (concept page).
  - So the central workflows see the copy's event, variables, registry and switches, and work on the copy.

### 1.2 Where it lives: symphony-protocol, renamed `symphony`

The runtime goes into symphony-protocol, not into a new repository beside it:

- It is already the public half of Symphony: CI on Python 3.12, a release workflow that tags `vX.Y.Z` from `sdlc_protocol/__init__.py` (`.github/workflows/release.yml`), and the App's sync to the other consumers.
- Most of the tools it receives import the library (`metrics.py:91-92`, `add_worker.py:40`, the five shims). In one repository a protocol change is one pull request and one release. Today it is five steps: a library PR, a release, the sync PR into the template, the template's own workflow or tool PR, then protocol.yml in each copy.
- No new repository has to be made, which the session's proxy refuses anyway (constraint in the template's CLAUDE.md).

Layout:

```
OpenSpineConsortium/symphony           (symphony-protocol, renamed before v1.0.0)
  sdlc_protocol/          the library, unchanged; still vendored into coordbench, the plugin, the App
  runtime/                the template's tools: cli.py (one entry), metrics, economics, usage, crowd_check,
                          add_worker, fill (was template_init), docs_check, edit_check, marked_section,
                          text_sync (new), migrate (new), crowd.py and setup-repo.sh as commands
  run/action.yml          the composite action: input command, python3 -I on runtime/cli.py
  .github/workflows/      symphony.yml (the dispatcher copies call), board.yml, sync.yml, metrics.yml,
                          workers.yml, coordinator.yml, add-worker.yml, queue.yml, claude.yml (all
                          workflow_call), plus this repository's own ci.yml, release.yml, sync.yml
  copy/                   the copy skeleton, with placeholders: the thin callers, scripts/symphony.sh,
                          the session text, the issue forms, the rulesets the Setup App applies
  spec/PROTOCOL.md        the one protocol text, rendered into copy/docs/agents/PROTOCOL.md
  docs/                   the public pages that were template docs: metrics, crowdsourcing, setup, start
  tests/                  the library's tests and the template's tests (8,396 lines) together
```

Rename it now, while no copy calls it yet. Nothing has shown that `uses:` follows a renamed repository, so callers should name the final name from the start. Without the rename, replace `symphony` with `symphony-protocol` in the three callers and in the bootstrap's `url` line, four lines in all.

The alternative, a new repository that vendors the library, keeps two release lines. A library change would reach copies only after a sync PR into the runtime and a second release. That is today's two-hop problem, kept.

### 1.3 Versions, and how copies stay current

- **`vX.Y.Z`: an immutable release for every version.** Its tag "cannot be moved, and cannot be deleted while the release exists", and tags of immutable releases cannot be reused even if the repository is deleted and recreated (`gh:content/code-security/concepts/supply-chain-security/immutable-releases.md`).
- **`v1`: a moving major tag with no release tied to it.** This is the documented pattern for an action that also uses immutable releases (`gh:content/actions/how-tos/create-and-publish-actions/using-immutable-releases-and-tags-to-manage-your-actions-releases.md`). The release job moves it after approval (section 5).
- **`main` is the canary channel.** Only the canary repositories call it.
- **Default for copies: `@v1`.**
  - A compatible release reaches every copy at its next run, with no pull request and no Dependabot. That ends the "older copies" problem for everything the central side holds.
  - Copies already work this way with GitHub's and Anthropic's actions. The template's workflows use `actions/checkout@v7` 15 times, `upload-artifact@v7` 6 times and `anthropics/claude-code-action@v1` 6 times, and the writing rule says "pinned to a major tag" (`.claude/rules/writing.md:6`).
- **Opt-in for a cautious copy: pin `@<40-hex> # v1.4.0` in the three callers and let Dependabot propose each release.**
  - Dependabot keeps "references to actions ... and reusable workflows used inside workflows" current, and updates the comment on the same line (`gh:content/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/auto-update-actions.md`, `gh:data/reusables/actions/dependabot-version-updates-actions-caveats.md`).
  - It can group the three into one pull request and wait a cooldown first; `cooldown` is supported for github-actions (`gh:content/code-security/reference/supply-chain-security/dependabot-options-reference.md`).
  - Its pull requests run with a read-only GITHUB_TOKEN and no Actions secrets (`gh:content/code-security/reference/supply-chain-security/dependabot-on-actions.md`), which is all the check needs.

```yaml
# .github/dependabot.yml, pinned mode only
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    cooldown:
      default-days: 3
    groups:
      symphony:
        patterns: ["OpenSpineConsortium/symphony*"]
```

- **A new major (`v2`) only when a copy's own file must change:** a new trigger, a new permission, a new secret or a new dispatch input. The callers below grant the union of everything the template does today, so v1 should hold for a long time. When v2 comes, Dependabot proposes the new ref, and the front door's upgrade (section 6) rewrites the files.

### 1.4 How a central job gets its own code, at its own commit

A reusable workflow from another repository does not check out its own files. Inside the central workflows, `uses: $/run` and `uses: $/.github/workflows/<x>.yml` resolve "against the repository of the file it appears in, not the repository that called it", "at the running commit" (`gh:content/actions/reference/workflows-and-actions/workflow-syntax.md`, "`$/path/to/action`"; `gh:data/reusables/actions/uses-keyword-example.md`). This gives three things:

- A workflow and the code it runs are always one release.
- The runtime lands in the runner's action folder, outside the workspace, where a Claude session in the job can neither move nor commit it.
- The six `cp tools/usage.py "$RUNNER_TEMP/usage.py"` steps of today's workflows are no longer needed.

The documented fallback, if `$/` misbehaves in practice, is to check out `${{ job.workflow_repository }}` at `${{ job.workflow_sha }}` (`gh:.../contexts.md`, "Example usage of job context workflow identity").

## 2. Where every piece goes

### 2.1 The eleven workflows

| Today in the copy | Lines | Goes to | In the copy afterwards |
| --- | --- | --- | --- |
| board.yml | 176 | central `board.yml` (job board), routed by the dispatcher | `symphony.yml` |
| tidy.yml | 54 | central `board.yml`, job tidy on `issues.closed` | `symphony.yml` |
| metrics.yml | 204 | central `metrics.yml`; the push trigger on the switch file becomes a test of `github.event.commits` | `symphony.yml` |
| workers.yml | 180 | central `workers.yml`; it dispatches `symphony.yml -f job=workers` for the next round | `symphony.yml` |
| coordinator.yml | 408 | central `coordinator.yml` | `symphony.yml` |
| add-worker.yml | 134 | central `add-worker.yml` | `symphony.yml` |
| queue.yml | 50 | central `queue.yml` (crowd mode) | `symphony.yml` |
| claude.yml | 88 | central `claude.yml` | thin `claude.yml`, 31 lines, whole template only |
| ci.yml | 133 | the check's code goes into the action; the library clone and the vendoring check are dropped | thin `ci.yml`, 66 lines |
| protocol.yml | 229 | dropped; nothing is vendored into a copy | none |
| template-init.yml | 99 | dropped from copies; its fill runs where the copy is made (the front door's staging, or `bash scripts/symphony.sh init` for a copy made by hand) | none |

The copy gets one dispatcher caller, not seven, so a job added later also reaches old copies; only the triggers and permissions are fixed by the copy's file. Today an `issues.labeled` event starts four workflows (board, coordinator, workers, queue). Afterwards it starts one Symphony run, whose routing is evaluated without a runner.

Two workflows stay apart from the dispatcher:

- **The check**, because a skipped run must never count as the check. That is why ci.yml filters branches at the trigger (its own header says so).
- **@claude**, because its comment triggers are chatty and only whole-template copies hold a Claude token.

### 2.2 The tools, the scripts and the tests

| Today | Lines | Goes to |
| --- | --- | --- |
| tools/sdlc_protocol/ (17 files), tools/VENDORED | 4,973 | stays the library in the central repository; no longer copied into copies |
| board.py, team.py, workers.py, check_protocol.py, guard_push.py | 162 (shims) | dropped; the runtime calls the library directly |
| metrics.py, economics.py, usage.py | 3,066 | runtime/ (commands `metrics`, `usage-actions`, `usage-hook`, `usage-trailer`) |
| crowd_check.py, marked_section.py | 532 | runtime/ (`check` holds the crowd guard; `queue`; `checkpoint`) |
| template_init.py | 441 | runtime/fill, used by the front door and by `symphony.sh init` |
| add_worker.py | 163 | runtime/ (command `add-worker`) |
| check_docs.py, check_edit.py | 303 | runtime/ (`check`, `check-edit`) |
| protocol_update.py | 180 | dropped; its PR-or-issue logic is generalised into `text_sync` |
| scripts/crowd.py | 3,001 | runtime/; the owner runs `bash scripts/symphony.sh crowd setup ORG/NAME` |
| scripts/setup-repo.sh | 329 | runtime/; `bash scripts/symphony.sh setup-repo`, and the Setup App's path as today |
| scripts/check.sh | 27 | stays, 15 lines: `bash scripts/symphony.sh check`, then the project's own checks |
| tests/ (20 files) | 8,396 | the central repository's tests; the copy holds none |

### 2.3 The library, the checks, CLAUDE.md, the protocol text, the plugin and the data

- **The library** stays a library. coordbench (its arm imports `sdlc_protocol.gate` and `adapters.bare_git`, `coordbench/arms/sdlc/arm.py:86-87`), the plugin (`guard.py`) and the App (`claims.py`, `protocol_check.py`) keep taking it through the sync. The template leaves `ecosystem.json`.
- **The checks.** The action's `check` runs what `scripts/check.sh` and ci.yml ran: the document checks, `workers check`, the protocol check on a pull request, and the crowd guard fed by the copy's `values` job. Three things go with the vendored copy: `vendoring.py verify`, `tests/test_vendored.py` and the CI clone of the library.
- **CLAUDE.md** stays the copy's, about 40 lines. It imports `@docs/project.md`, `@docs/agents/PROTOCOL.md` and `@docs/memory/MEMORY.md`. Its Symphony section says three things:
  - the code is the release `.github/workflows/symphony.yml` names, and changes there, never here;
  - the hooks are `scripts/symphony.sh`;
  - run `bash scripts/check.sh` before a pull request.
- **docs/agents/PROTOCOL.md must stay a file in the repository.**
  - CLAUDE.md imports it into every session, and it is 14.6 KB (the template's) or 18.2 KB (the library's spec).
  - A SessionStart hook's output is capped at 10,000 characters; past the cap Claude gets only a path and a preview (`cc:hooks`, "capped at 10,000 characters"). So the hook cannot carry it.
  - The two texts become one, `spec/PROTOCOL.md`, rendered with the copy's names.
- **The text sync.**
  - The other text sessions read from files also stays in the copy: the three skills, `/board`, `.claude/rules/board.md`, `docs/agents/WORKERS.md`, `claims/README.md`, the two routine prompts, the four issue forms and `scripts/symphony.sh`. Cloud sessions load the repository's `.claude/skills/`, `commands/` and `rules/`, but not its plugins (`cc:cloud-environments`).
  - A central job, `sync`, runs every six hours inside the dispatcher and keeps these files current:
    - It renders the release's `copy/` text with the copy's names and compares it with the copy's default branch.
    - It replaces only files whose content still equals what the last release wrote, which `.github/symphony/copy.json` records by sha256. A file someone edited is kept and named in the pull request.
    - It opens or updates one pull request from `symphony/text`, then dispatches ci.yml on the branch, since GITHUB_TOKEN's push starts no workflow. Where Actions may not open pull requests, it opens an issue with the link instead.
  - This is protocol.yml's tested mechanism (`tools/protocol_update.py`), generalised and held centrally.
- **The hooks.** `.claude/settings.json` wires four hooks to `scripts/symphony.sh` (written out below). The bootstrap keeps the release once under `$(git rev-parse --git-common-dir)/symphony/<sha>`, so nothing of it can be committed. The runtime then does what `.claude/hooks/session-start.sh`, `guard_push.py`, `usage.py hook` and `check_edit.py` do today.
- **The plugin** stays for repositories that hold no Symphony files. Its hooks stand down where the project's settings already wire `scripts/symphony.sh`, so no session gets two guards. The bootstrap's guard follows the rule of symphony-marketplace#10 (merged 2026-10-13): when the guard cannot run, it refuses every command that may push and lets the rest through.
- **What stays the repository's data**, read by the central side as data:
  - `.github/symphony/workers/*.json` (the registry);
  - `.github/symphony-metrics` (the sharing switch) and `.github/symphony-adopt` (the sweep's opt-out);
  - the variables `CLAUDE_CROWD`, `SDLC_METRICS`, `CLAUDE_ALLOWED_TOOLS`;
  - the secrets `CLAUDE_CODE_OAUTH_TOKEN`, `COORDINATOR_TRIGGER_URL`, `COORDINATOR_TRIGGER_TOKEN`;
  - the labels, the branches `board` and `metrics`, `docs/project.md`, `docs/agents/OWNERSHIP.md`, `docs/memory/` and `.claude/session.md`.

### 2.4 The thin callers, written out

`.github/workflows/symphony.yml` (70 lines, 2,500 bytes), the same file for both kinds:

```yaml
name: Symphony

# Everything Symphony runs here comes from one versioned workflow,
# OpenSpineConsortium/symphony's .github/workflows/symphony.yml: the board
# with the coordinator's releases and overlaps, branch tidying, the text
# sync, the field metrics, the workers in Actions, the coordinator's
# planning, the "Add a worker" form and, in crowd mode, the queue's gate.
# This file says only when to run, the most the token may do and which
# secrets to hand over, by name; what runs is the release the ref names, so
# a new release reaches this repository with no change here. Each job of
# the central workflow asks for less than the permissions below, never more.
# The three schedules are part of the interface the central workflow
# routes by: keep their text as it is. No logic belongs here.

on:
  push:
  create:
  delete:
  pull_request:
    types: [opened, synchronize, reopened, closed]
  issues:
    types: [opened, edited, closed, reopened, labeled, unlabeled]
  schedule:
    - cron: "17 */6 * * *"
    - cron: "43 3 * * *"
    - cron: "29 5 * * 1"
  workflow_dispatch:
    inputs:
      job:
        description: "board, sync, metrics, workers or coordinator; empty runs the board"
        required: false
        default: ""
      event:
        description: "For the coordinator: labeled to plan an epic, closed to integrate it, tidy for the weekly duties"
        required: false
        default: ""
      issue:
        description: "For the coordinator: the epic's or the task's issue number"
        required: false
        default: ""
      worker:
        description: "For the workers: one worker to run; empty runs every worker in Actions"
        required: false
        default: ""
      round:
        description: "For the workers: how many rounds this worker has run in a row"
        required: false
        default: "1"

permissions:
  contents: write
  pull-requests: write
  issues: write
  actions: write
  checks: read
  id-token: write

jobs:
  symphony:
    uses: OpenSpineConsortium/symphony/.github/workflows/symphony.yml@v1
    with:
      job: ${{ inputs.job || '' }}
      event: ${{ inputs.event || '' }}
      issue: ${{ inputs.issue || '' }}
      worker: ${{ inputs.worker || '' }}
      round: ${{ inputs.round || '1' }}
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
      COORDINATOR_TRIGGER_URL: ${{ secrets.COORDINATOR_TRIGGER_URL }}
      COORDINATOR_TRIGGER_TOKEN: ${{ secrets.COORDINATOR_TRIGGER_TOKEN }}
```

Why the file looks like this:

- **Secrets are named, never inherited.** `secrets: inherit` "can be used to pass secrets across repositories within the same organization, or across organizations within the same enterprise" (`gh:.../workflow-syntax.md`, `jobs.<job_id>.secrets.inherit`). An outside copy cannot use it, and three named secrets is also the least the central side should get.
- **The permissions are the union of today's eleven workflows.** If a calling job names none, the called workflow gets the repository's default permissions, and the called workflow can only lower what it is given (`gh:.../reusing-workflow-configurations.md`). Naming any permission sets all the others to `none` (`gh:.../workflow-syntax.md`, `permissions`).
- **The schedules are routed by their text.** `github.event.schedule` holds the cron that fired (`gh:data/reusables/repositories/actions-scheduled-workflow-example.md`).
- **`vars` may be passed in `with:`.** The availability table in `gh:.../contexts.md` lets `jobs.<job_id>.with.<with_id>` use `github, needs, strategy, matrix, inputs, vars`. The central side reads the copy's variables itself anyway.

`.github/workflows/ci.yml` (66 lines, 2,627 bytes), whole template. The job keeps the name the rulesets require:

```yaml
name: Checks

# The check named "check", which the default branch's ruleset requires.
# Symphony's part runs from the versioned action: the documents that are
# this project's instructions and memory, the registry of workers, a
# claude/<issue> pull request against the claim protocol, and crowd mode's
# rules. Then this project's own scripts/check.sh. The job stays a job of
# this file, named check, because a job of a reusable workflow would be
# reported as "check / <job>" and the ruleset would wait for "check"
# forever. values names the secrets that reach the repository by name only,
# inside GitHub's expressions, so the job that runs this repository's code
# holds no secret. The claim branches are left out of the push trigger,
# since their pull request runs the check and a skipped run must never
# stand in for the check.

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review, converted_to_draft, edited]
  push:
    branches-ignore: ["claude/**", "symphony/**", "symphony-protocol/**", "crowd/setup", "metrics"]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  values:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    outputs:
      secrets: ${{ steps.names.outputs.secrets }}
    steps:
      - name: Name the Claude secrets that reach this repository
        id: names
        env:
          SET_CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN != '' }}
          SET_ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY != '' }}
          SET_COORDINATOR_TRIGGER_URL: ${{ secrets.COORDINATOR_TRIGGER_URL != '' }}
          SET_COORDINATOR_TRIGGER_TOKEN: ${{ secrets.COORDINATOR_TRIGGER_TOKEN != '' }}
          SET_SDLC_APP_PRIVATE_KEY: ${{ secrets.SDLC_APP_PRIVATE_KEY != '' }}
        run: |
          names=$(env | sed -n 's/^SET_\([A-Z_]*\)=true$/\1/p' | sort | tr '\n' ' ')
          echo "set: ${names:-none}"
          echo "secrets=${names% }" >> "$GITHUB_OUTPUT"

  check:
    needs: values
    if: ${{ !cancelled() }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: OpenSpineConsortium/symphony/run@v1
        with:
          command: check
          secrets-set: ${{ needs.values.outputs.secrets }}
          values-result: ${{ needs.values.result }}
          crowd: ${{ vars.CLAUDE_CROWD }}
          old-switches: ${{ vars.CLAUDE_WORKER != '' || vars.CLAUDE_TEAM != '' }}
      - name: This project's own checks
        env:
          SYMPHONY_CHECKED: "true"
        run: if [ -f scripts/check.sh ]; then bash scripts/check.sh; fi
```

The `values` job stays in the copy, for two reasons:

- Only expressions over the copy's own `secrets` can tell which secrets exist; GITHUB_TOKEN has no secrets permission (see the list in `gh:.../workflow-syntax.md`).
- The job that runs the repository's code must not name a secret (the template's ci.yml header).

Its five names are part of the v1 interface.

`.github/workflows/claude.yml` (31 lines, 899 bytes), whole template, or added by hand where @claude is wanted:

```yaml
name: Claude

# @claude on an issue, a pull request or a review starts a Claude Code
# session on this repository's own Claude token, the secret
# CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`, which bills no API.
# What the session may do, its turn cap, the crowd-mode gate and the usage
# record the field metrics read are the central workflow's; this file says
# when to run, the most the token may do and the one secret to hand over.

on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
  pull_request_review:
    types: [submitted]
  issues:
    types: [opened, assigned]

permissions:
  contents: write
  pull-requests: write
  issues: write
  actions: read
  id-token: write

jobs:
  claude:
    uses: OpenSpineConsortium/symphony/.github/workflows/claude.yml@v1
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

### 2.5 The bootstrap and the hooks, written out

`scripts/symphony.sh` (116 lines, 5,349 bytes). Tested in `e2e/` against a local fake release, these all held:

- It resolves an annotated moving tag to its commit, fetches it at depth 1 and checks the commit.
- A moved `v1` reaches the next session start.
- When the release cannot be fetched, session start keeps the runtime it already had.
- With nothing kept:
  - a push is refused (exit 2);
  - `ls` passes;
  - `check` fails;
  - `check` under `SYMPHONY_CHECKED=true` passes.
- A `python3` that is only a stub (exits 0, prints nothing) makes the guard refuse pushes instead of letting them through.
- `git status` stays clean.

From this cloud session, resolving and fetching a real moving tag (`actions/checkout` `v4`) worked, and so did `git ls-remote` of a public repository not attached to the session.

```bash
#!/usr/bin/env bash
# The one door to Symphony on a machine or in a Claude Code session: the
# hooks in .claude/settings.json, scripts/check.sh and the skills call it as
# `bash scripts/symphony.sh COMMAND [ARGUMENTS]`. No rule of Symphony's is
# here. It finds the release this repository runs, the ref that
# .github/workflows/symphony.yml calls, keeps that release once under the
# git directory, never in the work tree, so nothing of it is ever committed,
# and hands it the command. The hooks that run before every tool call use
# what session-start kept and reach the network only for a push. When the
# push guard cannot run, for want of the runtime or of a working Python
# 3.12, it refuses every command that may push and lets the rest through,
# as the plugin's guard does since symphony-marketplace#10; the usage hook
# and the edit check let everything through. session-start prints the
# board even without the runtime; check fails without it, since a check
# that did not run must not pass. Every fetch is cut off after twenty
# seconds.

set -u
url="https://github.com/OpenSpineConsortium/symphony"
command="${1:-}"
[ $# -gt 0 ] && shift
root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
if ! gitdir="$(git -C "$root" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"; then
  [ "$command" = check ] && { echo "symphony: not a git checkout, or git older than 2.31; the checks did not run" >&2; exit 1; }
  exit 0
fi
cache="$gitdir/symphony"

limit() { if command -v timeout >/dev/null 2>&1; then timeout 20 "$@"; else "$@"; fi; }

# The ref the caller names: a commit, a release tag or the moving major tag.
pinned_ref() {
  sed -n 's#.*OpenSpineConsortium/symphony/\.github/workflows/symphony\.yml@\([^[:space:]]*\).*#\1#p' \
    "$root/.github/workflows/symphony.yml" 2>/dev/null | head -n 1
}

# The commit behind the ref: the ref itself when it is one, else the tag's
# commit, peeled when the tag is annotated.
resolve() {
  ref="$1"
  if printf '%s' "$ref" | grep -Eqx '[0-9a-f]{40}'; then printf '%s\n' "$ref"; return 0; fi
  [ -n "$ref" ] || return 1
  limit git ls-remote --tags "$url" "$ref" "$ref^{}" 2>/dev/null | awk -v t="refs/tags/$ref" \
    '$2 == t "^{}" {peeled = $1} $2 == t {plain = $1} END {if (peeled != "") print peeled; else if (plain != "") print plain}'
}

# The runtime at that commit, fetched once, checked to be that commit, and
# kept only with a Python that can run it.
fetch() {
  sha="$1"
  if [ ! -f "$cache/$sha/.complete" ]; then
    mkdir -p "$cache" || return 1
    tmp="$cache/.incoming-$$"
    rm -rf "$tmp"
    if ! { git init --quiet "$tmp" && limit git -C "$tmp" fetch --quiet --depth 1 "$url" "$sha" &&
           git -C "$tmp" -c advice.detachedHead=false checkout --quiet FETCH_HEAD &&
           [ "$(git -C "$tmp" rev-parse HEAD)" = "$sha" ] && touch "$tmp/.complete"; }; then
      rm -rf "$tmp"
      return 1
    fi
    rm -rf "${cache:?}/$sha" && mv "$tmp" "$cache/$sha" || return 1
  fi
  [ "$(python3 -c 'import sys; print(int(sys.version_info >= (3, 12)))' 2>/dev/null)" = 1 ] || return 1
  printf '%s\n' "$sha" > "$cache/current"
}

# kept: what the last fetch left, with no network. fresh: the pinned ref
# now. any: what was kept, else fresh.
runtime() {
  if [ "$1" != fresh ] && [ -f "$cache/current" ]; then
    sha="$(cat "$cache/current")"
    if [ -f "$cache/$sha/.complete" ]; then printf '%s\n' "$cache/$sha"; return 0; fi
  fi
  [ "$1" = kept ] && return 1
  sha="$(resolve "$(pinned_ref)")" && [ -n "$sha" ] && fetch "$sha" && printf '%s\n' "$cache/$sha"
}

board_only() {
  limit git -C "$root" fetch --quiet origin +refs/heads/board:refs/remotes/origin/board >/dev/null 2>&1
  printf 'Symphony could not be fetched from %s, or python3 is not Python 3.12 or later:\n' "$url"
  printf 'until it can be, the push guard refuses every push in this session.\n'
  printf '\nThe board (origin/board:STATE.md), first 120 lines:\n'
  git -C "$root" show origin/board:STATE.md 2>/dev/null | head -n 120 || printf 'The board has not been written yet.\n'
}

case "$command" in
  session-start)
    if dir="$(runtime fresh)" || dir="$(runtime kept)"; then
      exec python3 -I "$dir/runtime/cli.py" session-start "$@"
    fi
    board_only
    exit 0 ;;
  guard)
    payload="$(cat)"
    case "$payload" in *push*) mode=any ;; *) mode=kept ;; esac
    if dir="$(runtime "$mode")"; then
      printf '%s' "$payload" | python3 -I "$dir/runtime/cli.py" guard "$@"
      status=$?
      case "$status" in 0 | 2) exit "$status" ;; esac
    fi
    if [ "$mode" = any ]; then
      echo "Symphony's push guard could not run here (no runtime from $url, or no Python 3.12), so no push goes through; run bash scripts/symphony.sh session-start once it can." >&2
      exit 2
    fi
    exit 0 ;;
  usage-hook | usage-trailer | check-edit)
    dir="$(runtime kept)" || exit 0
    exec python3 -I "$dir/runtime/cli.py" "$command" "$@" ;;
  "")
    echo "usage: bash scripts/symphony.sh COMMAND [ARGUMENTS]; 'help' lists the commands" >&2
    exit 2 ;;
  *)
    if [ "$command" = check ] && [ "${SYMPHONY_CHECKED:-}" = true ]; then exit 0; fi
    dir="$(runtime any)" || { echo "symphony: the runtime could not be fetched from $url, or python3 is older than 3.12" >&2; exit 1; }
    exec python3 -I "$dir/runtime/cli.py" "$command" "$@" ;;
esac
```

`.claude/settings.json` (the drafted file is 55 lines, 1,229 bytes; shown compacted):

```json
{
  "permissions": {
    "allow": [
      "Bash(git fetch:*)", "Bash(git show:*)", "Bash(git status:*)", "Bash(git diff:*)",
      "Bash(git log:*)", "Bash(git branch:*)", "Bash(git rev-parse:*)", "Bash(git ls-files:*)",
      "Bash(bash scripts/check.sh)", "Bash(bash scripts/symphony.sh:*)"
    ]
  },
  "hooks": {
    "SessionStart": [{"hooks": [{"type": "command",
      "command": "bash \"$CLAUDE_PROJECT_DIR\"/scripts/symphony.sh session-start", "timeout": 60}]}],
    "PreToolUse": [{"matcher": "Bash", "hooks": [
      {"type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR\"/scripts/symphony.sh guard"},
      {"type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR\"/scripts/symphony.sh usage-hook"}]}],
    "PostToolUse": [{"matcher": "Edit|Write", "hooks": [
      {"type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR\"/scripts/symphony.sh check-edit"}]}]
  }
}
```

`scripts/check.sh` (15 lines) runs `set -eu`, `cd "$(dirname "$0")/.."` and `bash scripts/symphony.sh check`, then the project's own lines, then `echo "checks ok"`.

The session-start hook installs the commit-msg hook, which calls `bash scripts/symphony.sh usage-trailer "$1"`. So a commit made with no session open still gets its usage trailer from the same release.

## 3. What a copy holds afterwards

### 3.1 Whole template: 38 files, about 1,070 lines, about 90 KB

Today: 145 files, 28,436 lines, 1,785,294 bytes. Sizes below are as filled by the template's own init at a1d9695, the drafted files, or estimates (marked est.).

| Files | Lines | Bytes | Kind |
| --- | --- | --- | --- |
| .github/workflows/symphony.yml, ci.yml, claude.yml | 167 | 6,026 | thin callers |
| scripts/symphony.sh, scripts/check.sh | 131 | 5,927 | bootstrap; project checks |
| .claude/settings.json | 55 | 1,229 | hooks to the bootstrap |
| .github/symphony/copy.json | 25 | 1,123 | what the last release wrote (sha256 per synced file) |
| docs/agents/PROTOCOL.md, WORKERS.md, claims/README.md, routines/worker.md, routines/coordinator.md | 219 | 37,501 | synced text |
| .claude/skills/claim, remember, checkpoint; .claude/commands/board.md; .claude/rules/board.md | 72 | 11,637 | synced text |
| .github/ISSUE_TEMPLATE/config.yml, task.yml, blocker.yml, worker.yml; .github/symphony/workers/README.md | 161 | 6,781 | synced text (forms GitHub reads from the copy) |
| CLAUDE.md, README.md (est.), docs/project.md, docs/agents/OWNERSHIP.md, docs/memory/MEMORY.md (est.) and one starting fact (est.), .claude/session.md, .claude/rules/memory.md, writing.md | 169 | 17,597 | the project's own |
| .github/CODEOWNERS, PULL_REQUEST_TEMPLATE.md, dependabot.yml, symphony-metrics, .editorconfig, .gitattributes, .gitignore | 70 | 1,943 | data and settings |

Gone from the copy:

- `tools/` (33 files), `tests/` (20), `scripts/crowd.py` and `scripts/setup-repo.sh`;
- eight of the eleven workflows, and `.claude/hooks/session-start.sh`;
- `docs/setup/` (17 files, 192 KB), `docs/start/` (11, 120 KB), `docs/history/` (6, 181 KB) and `docs/agents/STATE.md`;
- ten of the eleven memory facts, which are facts about the runtime.

The setup and start pages become the runtime's public `docs/`, linked by URL from the copy's text. The history stays private in the template.

### 3.2 Protocol only: 8 files and 2 merges, 369 lines, 34 KB

Today: 28 files, 7,776 lines, 362,927 bytes.

- `.github/workflows/symphony.yml` (70)
- `scripts/symphony.sh` (116)
- `.github/symphony/copy.json` (25)
- `.github/symphony-metrics` (1)
- `docs/agents/PROTOCOL.md` (107, the spec, as today)
- `docs/agents/claims/README.md` (23)
- `.claude/skills/claim/SKILL.md` (17)
- `.claude/commands/board.md` (10)
- Merged, never overwritten: one section in CLAUDE.md (about 8 lines) and the hooks block in `.claude/settings.json` (about 45 lines).

As today, a protocol-only copy gets no ci.yml and no required check (`setup.py` drops the rule in mode existing, `scripts/setup.py:240-246`). A narrower variant of the caller, for a copy that will never run Claude in Actions, drops `id-token: write` and the Claude secret; v1 accepts both forms.

### 3.3 What the front door's adoption becomes

Both kinds, in order:

1. **Unchanged:** parse the form or take the sweep's ids, name and mask the repository, and mint the App's token for the repository.
2. **Fetch the release.** `git ls-remote --tags https://github.com/OpenSpineConsortium/symphony v1 'v1^{}'` gives the commit, and `git fetch --depth 1` takes it; the runtime is public, so no token is needed. This replaces adopt-run.yml lines 281-329: the private template's read-only token, its checkout, its revocation and the fetch of the protocol's text.
3. **Build the files.**
   - Mode new copies all of `copy/` and fills the placeholders with `runtime/cli.py fill --repo ... --default-branch ... --owner-type ... --creator ...` (the template's init, moved). A file the repository already has is replaced, as today. `copy.json` is written.
   - Mode existing copies the eight files above, writes none over a file of theirs, and merges the CLAUDE.md section and the hooks.
   - The units and the heuristics about which script landed go (`PROTOCOL_FILES`, `METRICS_FILES`, `UNITS`, `LIBRARY_UNIT`, `BREAKDOWN_KEY`, `ACTIONS_PATH`, `adopt.py:103-181`). The copy holds no script a workflow runs, and the pull request can name the exact release.
4. **Commit and open, as today.** Commit as the App on `symphony/adopt`, apply the settings with the Setup App, open the pull request, make the labels and, in mode new, the setup issue. The only change: the ruleset and the labels come from the release (`copy/` and `sdlc_protocol.labels`).

The adoption pull request falls from 145 or 28 files to 38 or 8, every one of them readable in public before anyone installs the App.

## 4. Privacy and the private template

What GitHub allows:

- **Only a public runtime reaches outside copies.** A public caller can use only public workflows. A private caller can use private ones only when "the settings for that repository allow it to be accessed". The access setting reaches only "repositories owned by" the same user or organization, or, for internal and private ones, the same enterprise (`gh:.../reusing-workflow-configurations.md`, access table; `gh:content/actions/how-tos/reuse-automations/share-with-your-organization.md`, `share-across-private-repositories.md`, `share-with-your-enterprise.md`).
- **Even a private runtime would not be secret from the copies that run it.** "Outside collaborators on the other repositories can indirectly access the private repository ... can view logs", and the runner gets "a scoped installation token ... with read access to the repository" to download it (`gh:data/reusables/actions/outside-collaborators-actions.md`, `scoped-token-note.md`).
- **The copies already hold the runtime's files today, under MIT** ("the files in the pull request are yours", `symphony-start README.md:48` and `:96`), in private and public repositories alike.

| Option | What becomes public | Cost |
| --- | --- | --- |
| **A. Public runtime, private template (recommended)** | The library (already public), the template's tools and tests, the workflows, the action, the copy skeleton, the runtime docs | The runtime can be read without adopting. The decision "free to use is not free access to the source" narrows to what stays private: the template repository's history, issues, branches, research (`docs/history/`, about 181 KB), its decisions block and checkpoints, plus symphony-app and the release kit. Nothing reaches the public that an adopter does not already receive. The front door's rule that nothing of the template is printed becomes moot for adoption, since the adoption no longer reads the template; the masking of repositories given by ids stays. |
| B. Private or internal runtime, the organization only | Nothing new | Only OpenSpineConsortium's own repositories can call it. Every outside copy keeps today's model, so two systems are maintained and the old-copies problem stays for everyone else. |
| C. Public byte code only | The workflows, the action, the session text (YAML and text cannot be hidden) | `.pyc` is tied to one Python minor version, so runners need `actions/setup-python` and machines need one build per local Python (3.12 to 3.14), as cswap does with a wheel per version. Adopters cannot audit code that holds their write token and Claude token, while GitHub's guidance is to "audit the source code of the action" (`gh:content/actions/reference/security/secure-use.md`). Byte code can be decompiled anyway. |
| D. The owner's own Actions run everything with the App's token | Nothing | GitHub hosts nothing a webhook can reach, so the board would run on a schedule only, never on events (the template's constraint). The App would need lasting write access to every installation, where its privacy statement says it reads METRICS.json and JUDGE.json and nothing else. The owner pays the compute. The coordinator's comments would come from the App's bot instead of `github-actions[bot]`, the releasing bot the library names (`sdlc_protocol/claims.py:39`). |

**Field metrics keep their shape.**

- The copy's own workflow, on the copy's GITHUB_TOKEN, still computes METRICS.json, and the App still reads only the branch `metrics`.
- What changes: a new key now reaches every copy at once, at the release that adds it.
- So the rule already in the decisions block (a key is listed in PRIVACY.md and live before the collector keeps it) becomes a release gate. The runtime's tests hold METRICS.json's keys to a list stamped with the privacy statement's version.
- The switch `.github/symphony-metrics` stays the copy's, and every release honours it (also tested).
- Publishing the metrics code also lets anyone check what is computed.

**Crowd mode keeps its shape.**

- The `values` job and the guard are in the required check.
- The dispatcher's Claude jobs carry `vars.CLAUDE_CROWD != 'true'`, and the queue's gate runs only while it is true.
- The callers pass `CLAUDE_CODE_OAUTH_TOKEN`, which a crowd repository cannot hold: the guard fails while it exists.
- crowd.py becomes a runtime command its owner runs with their own gh. Its audit's `WORKFLOWS_NEEDED` (`scripts/crowd.py`: ci, board, queue and tidy) becomes the three callers.

## 5. Security

Each copy runs the owner's code with its own GITHUB_TOKEN, capped by the caller's permissions, and with the three secrets it names.

| Question | Answer |
| --- | --- |
| Pinning | `@v1` by default; `@<sha> # vX.Y.Z` with Dependabot (grouped, three-day cooldown) for a copy that wants each release reviewed. Inside the central workflows, `$/` ties every job to the workflow's own commit. The central workflows pin their own dependencies (actions/checkout, cache, upload-artifact, claude-code-action) by commit with Dependabot, because every copy runs them. GitHub's workflow lockfile would also cover them ("A reusable workflow is covered by the lockfile of the repository where it is defined", `gh:content/actions/concepts/security/workflow-dependency-lockfiles.md`), but it is in public preview and needs a gh extension, so it is a new dependency and an issue first. |
| Who can publish | Merging to main publishes nothing. `release.yml` waits in the environment `release`: "a job cannot access environment secrets until one of the required reviewers approves it". On every plan, a public repository gets required reviewers and deployment branches, and administrators' bypass can be switched off (`gh:content/actions/reference/workflows-and-actions/deployments-and-environments.md`). After the approval the job creates the immutable `vX.Y.Z` and moves `v1`, with a token held only in that environment. A tag ruleset restricts creating, updating and deleting `v*` to that identity (`gh:.../available-rules-for-rulesets.md`, Restrict creations, updates, deletions). Cloud sessions cannot push a tag at all ("the proxy rejects ... pushes of anything other than a branch, such as a tag", `cc:cloud-environments`). The approver should be an account no Claude session holds: a session acting with the owner's token could otherwise approve its own release through the REST API. |
| Protection of the central repository | A ruleset on main (pull request, required checks, no force push, no deletion) and on tags `v*`. Immutable releases on. "Allow GitHub Actions to create and approve pull requests" off. Workflows read-only by default. Approval of fork runs for outside contributors. The App's key for the sync moves into an environment limited to main. Private vulnerability reporting and SECURITY.md. Canary repositories call `@main` for at least a day before an approval. |
| What a compromised release could do | Until it is rolled back, in every copy on `@v1`, at that copy's next event: write any branch the copy's rulesets leave open; open, label and close issues and pull requests; merge a pull request once the required check passes, where that check is the release's own code and the template's rulesets require no review, by decision; dispatch workflows; mint OIDC tokens. An OIDC token from a called workflow carries the caller's `repository` and `sub`; only `job_workflow_ref` names the called workflow (`gh:content/actions/how-tos/secure-your-work/security-harden-deployments/oidc-with-reusable-workflows.md`). So a cloud role trusting `repo:<copy>:*` would trust the release. It could exfiltrate `CLAUDE_CODE_OAUTH_TOKEN` and the routine trigger, and spend the copy's minutes and plan. On a person's machine, it would run with their credentials at the next session start. |
| What it cannot do | Change any copy's workflow files, because GITHUB_TOKEN has no workflows permission (the list in `gh:.../workflow-syntax.md`; `template-init.yml:11`); so it cannot rewrite its own pin or persist there. Change settings or rulesets (no administration). Read other secrets, which are never inherited. Touch other repositories (the token is the copy's). The required check never holds a secret, because composite actions have no secrets context. |
| How it is bounded | A human gate on every release, from a session-free account. The canary on `@main`. Immutable `vX.Y.Z`. Rollback for all moving-tag copies by moving `v1` back, one command, effective at their next run. Per-job permissions below the caller's cap, held by a test against a checked-in list so any widening shows in review. Secrets named only in the steps that use them. A copy's choice of SHA pinning, which the bootstrap honours on machines too. The narrower protocol-only caller, without `id-token` and the Claude secret. Copies with cloud OIDC trust should key it on `job_workflow_ref`, or pin by commit. |
| Compared with today | Copies already run moving major tags of GitHub and Anthropic with the same token and the same Claude secret, and protocol.yml already arms auto-merge on each library release in a copy. The change is that OpenSpineConsortium, whose code copies already run, becomes a third publisher of a moving tag, this time behind an approval gate. |

## 6. Migration

In order, each step leaving everything that already exists working:

1. **Decide** the three decisions above, and rename symphony-protocol to symphony. Both are the owner's: the session's proxy refuses renames.
2. **Build the runtime** in the central repository:
   - `runtime/` with the template's tools and tests, `run/action.yml`, the reusable workflows, `copy/`, `text_sync`, `migrate`, and `release.yml` with the environment.
   - Drop the template from `ecosystem.json`.
   - Change the board's line "Rewritten by .github/workflows/board.yml" (`sdlc_protocol/board.py:670`) on purpose, as a rendered string; the template's fixture pins it.
3. **Canary.**
   - Move OpenSpineConsortium/sdlc-template-test to the thin callers on `@main`. It is an internal repository, and internal callers may use public workflows (the access table). Add a new protocol-only canary beside it.
   - Measure:
     - the check's name is `check`;
     - `$/` resolves;
     - the dispatcher routes each event correctly;
     - a GITHUB_TOKEN text-sync pull request gets its check;
     - Dependabot opens one grouped pull request on a pinned canary;
     - claude-code-action's OIDC exchange accepts a job defined in another organization's reusable workflow. The action posts the OIDC token to `api.anthropic.com/api/github/github-app-token-exchange` and has a refusal code `workflow_not_found_on_default_branch` (`anthropics/claude-code-action@v1 src/github/token.ts`). If it refuses, the central jobs pass `github_token` instead, and pull requests opened by sessions are then the token's own (see the note after this list).
4. **Release v1.0.0.**
5. **The template itself becomes a copy.**
   - It drops its vendored library, tools, tests, protocol.yml and template-init.yml, and calls `@main` as the permanent canary.
   - Its setup and start pages move to the runtime's `docs/`; `docs/history/`, its decisions block and its checkpoints stay.
   - It stops being a GitHub template repository, since the front door is the one way in, and its own board then runs like any copy's.
6. **The front door.**
   - adopt.py and adopt-run.yml read the public release (section 3.3).
   - README.md's section "The template stays private" says what is public and what is not.
   - A new kind, Upgrade, on the form (installation or name, as today) runs `runtime/cli.py migrate` and opens the pull request as the App, which already holds `workflows: write` on installations that adopted.
   - The steps that read the private template go, and so does the test that needs a checkout of it (`tests/test_real_template.py`, `SDLC_TEMPLATE`).
7. **Existing copies.** `migrate` removes a runtime file only when its bytes equal a known template or library version; the runtime ships sha256 lists made once from the private history (hashes only, never content). It keeps and names every edited file, writes the callers, the bootstrap and `copy.json`, and leaves data alone.
   - **spine-program** (protocol only, 0.2.0, `account:main`; branches `board`, `main` and `metrics` only; 28 open issues and pull requests; no claim branch today):
     - It removes 21 files: the 15 library files and VENDORED (which `verify` matches), `tools/board.py` and `tools/metrics.py`, and board.yml, metrics.yml and tidy.yml.
     - It adds symphony.yml, symphony.sh and copy.json, and merges the hooks into `.claude/settings.json`.
     - It keeps spine-program's own skills, which match no known hash.
     - The pull request must say what changes from 0.2.0: idle claims are released after 24 hours with a comment, overlapping work is told, and METRICS.json gains by_setting, economics and coordination (all listed in privacy statement version 3). `account:main` keeps working, since the library reads it as a worker label.
     - It also gets the push guard in cloud sessions for the first time.
   - **Copies with protocol.yml:** a last vendored library release, through their own protocol.yml, makes their board say "this copy can move to the central runtime" with the upgrade's link. Then the upgrade.
   - The test repositories (sdlc-template-test, sdlc-start-test) are migrated or made anew.
   - How many outside copies exist is not yet measured: the proxy refuses the App's installation endpoints.
8. **coordbench:** nothing changes beyond the library's repository name in its docs. Its arm keeps vendoring `sdlc_protocol` through the sync.
9. **The plugin** keeps vendoring `guard.py` through the sync, keeps the wrapper symphony-marketplace#10 gave it (merged 2026-10-13), and stands down where a project wires `scripts/symphony.sh`.
10. **symphony-app:** unchanged. It vendors `claims.py` and `protocol_check.py`, and the collector is untouched.

Some pull requests are still opened with GITHUB_TOKEN: the text sync, "Add a worker", and sessions if the OIDC fallback is needed. These meet GitHub's new rule: a pull request a workflow opens with GITHUB_TOKEN gets its `pull_request` runs "in an approval-required state" (`gh:data/reusables/actions/actions-do-not-trigger-workflows.md`). Two documented facts carry them through:

- `workflow_dispatch` "always creates workflow runs", and the central jobs dispatch ci.yml on the branch.
- "Required status checks do not take workflow, matrix, or event trigger types into account" (`troubleshooting-rules.md`).

Not yet measured: whether the approval-required run's pending check on the same head holds the merge. The canary has to show it.

## 7. What it removes, counted

| | Whole template, today -> after | Protocol only, today -> after |
| --- | --- | --- |
| Files | 145 -> 38 | 28 -> 8 (+2 merged) |
| Lines | 28,436 -> about 1,070 | 7,776 -> 369 |
| Bytes | 1,785,294 -> about 90,000 | 362,927 -> 34,008 |
| Workflows | 11 files, 1,755 lines -> 3 files, 167 lines | 3 files, 434 lines -> 1 file, 70 lines |
| Python and bash the copy runs | 57 files, 21,650 lines (tools, scripts, tests, the hook) -> 2 files, 131 lines | 20 files, 7,192 lines -> 1 file, 116 lines |
| Workflow runs on one `issues.labeled` | 4 (board, coordinator, workers, queue) -> 1 Symphony run, plus nothing for claude.yml | 1 -> 1 |

Mechanisms that go:

1. **Vendoring into copies:** the 17-file copy and VENDORED, `vendoring.py verify` in check.sh, `tests/test_vendored.py` (388 lines), the library clone in ci.yml, and the five shims (162 lines).
2. **protocol.yml:** the workflow (229 lines), `tools/protocol_update.py` (180) and its tests (312), with their weekly run and pull request in every copy.
3. **template-init in copies:** the workflow (99 lines, one job on every push to the default branch for the copy's life) and the `.template/PENDING` gates in board, metrics and protocol.
4. **The parked update route** for existing copies (the checkpoint's remaining task 3): a release is the update.
5. **The sync's pull request into the template,** its `downstream (symphony-template)` leg, and that leg's App token for reading an internal repository.
6. **The front door's private read:** about 49 lines of adopt-run.yml, the staging of 147 private files per run, and about 190 lines of adopt.py's per-file units and landed-script heuristics, with the tests that pin them.
7. **The six steps** that copy `tools/usage.py` aside before Claude runs.
8. **Two protocol texts** (the template's `docs/agents/PROTOCOL.md` and the library's spec) become one.
9. **The whole class of drift bug** shown in section 0: a workflow landing without the module its script imports.

What it adds, once and centrally:

- the dispatcher (about 105 lines, drafted in `central/.github/workflows/symphony.yml`);
- the action (64 lines, `central/run/action.yml`);
- `runtime/cli.py` as one entry;
- the text sync (protocol_update's logic, generalised);
- `migrate`;
- the release gate and the canary.

In each copy, it adds the 116-line bootstrap and a 25-line `copy.json`.

## Appendix: the central routing, drafted

`central/.github/workflows/symphony.yml` parses but has not been run. Each job calls a workflow of the same commit with `$/` and hands it only the secrets it uses:

```yaml
on:
  workflow_call:
    inputs:
      job: {type: string, required: false, default: ""}
      event: {type: string, required: false, default: ""}
      issue: {type: string, required: false, default: ""}
      worker: {type: string, required: false, default: ""}
      round: {type: string, required: false, default: "1"}
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: {required: false}
      COORDINATOR_TRIGGER_URL: {required: false}
      COORDINATOR_TRIGGER_TOKEN: {required: false}
jobs:
  board:
    if: >-
      contains(fromJSON('["push", "create", "delete", "pull_request", "issues"]'), github.event_name)
      || (github.event_name == 'schedule' && github.event.schedule == '17 */6 * * *')
      || (github.event_name == 'workflow_dispatch' && (inputs.job == '' || inputs.job == 'board'))
    permissions: {contents: write, pull-requests: write, issues: write}
    uses: $/.github/workflows/board.yml        # board, coordinator's releases, tidy on issues.closed
    secrets:
      COORDINATOR_TRIGGER_URL: ${{ secrets.COORDINATOR_TRIGGER_URL }}
      COORDINATOR_TRIGGER_TOKEN: ${{ secrets.COORDINATOR_TRIGGER_TOKEN }}
  sync:
    if: (github.event_name == 'schedule' && github.event.schedule == '17 */6 * * *') || (github.event_name == 'workflow_dispatch' && inputs.job == 'sync')
    permissions: {contents: write, pull-requests: write, issues: write, actions: write}
    uses: $/.github/workflows/sync.yml
  metrics:
    if: >-
      (github.event_name == 'schedule' && github.event.schedule == '43 3 * * *')
      || (github.event_name == 'push' && github.ref_name == github.event.repository.default_branch
          && (contains(toJSON(github.event.commits), '.github/symphony-metrics')
              || contains(toJSON(github.event.commits), '.github/sdlc-metrics')))
      || (github.event_name == 'workflow_dispatch' && inputs.job == 'metrics')
    permissions: {contents: write, pull-requests: read, issues: read, checks: read, actions: read}
    uses: $/.github/workflows/metrics.yml
  workers:
    if: >-
      vars.CLAUDE_CROWD != 'true' && (
      (github.event_name == 'schedule' && github.event.schedule == '17 */6 * * *')
      || (github.event_name == 'issues' && github.event.action == 'labeled'
          && !contains(github.event.issue.labels.*.name, 'claimed')
          && (github.event.label.name == 'todo' || github.event.label.name == 'blocker'
              || startsWith(github.event.label.name, 'worker:')))
      || (github.event_name == 'workflow_dispatch' && inputs.job == 'workers'))
    permissions: {contents: write, pull-requests: write, issues: write, checks: read, actions: write, id-token: write}
    uses: $/.github/workflows/workers.yml
    with: {worker: "${{ inputs.worker }}", round: "${{ inputs.round }}"}
    secrets: {CLAUDE_CODE_OAUTH_TOKEN: "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"}
  coordinator:
    if: >-
      vars.CLAUDE_CROWD != 'true' && (
      (github.event_name == 'issues' && github.event.action == 'labeled' && github.event.label.name == 'epic')
      || (github.event_name == 'issues' && github.event.action == 'labeled' && github.event.label.name == 'blocked'
          && contains(github.event.issue.body, 'Epic: #'))
      || (github.event_name == 'issues' && github.event.action == 'closed' && contains(github.event.issue.body, 'Epic: #'))
      || (github.event_name == 'schedule' && github.event.schedule == '29 5 * * 1')
      || (github.event_name == 'workflow_dispatch' && inputs.job == 'coordinator'))
    permissions: {contents: write, pull-requests: write, issues: write, actions: write, id-token: write}
    uses: $/.github/workflows/coordinator.yml
    with: {event: "${{ inputs.event }}", issue: "${{ inputs.issue }}"}
    secrets: {CLAUDE_CODE_OAUTH_TOKEN: "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"}
  add-worker:
    if: >-
      github.event_name == 'issues' && (github.event.action == 'opened' || github.event.action == 'edited')
      && github.event.issue.state == 'open'
      && contains(github.event.issue.body, '### Where it runs') && contains(github.event.issue.body, '### How its pull requests land')
    permissions: {contents: write, pull-requests: write, issues: write, actions: write}
    uses: $/.github/workflows/add-worker.yml
  queue:
    if: >-
      vars.CLAUDE_CROWD == 'true' && github.event_name == 'issues'
      && ((github.event.action == 'labeled' && (github.event.label.name == 'todo' || github.event.label.name == 'blocker'))
          || ((github.event.action == 'opened' || github.event.action == 'edited')
              && (contains(github.event.issue.labels.*.name, 'todo') || contains(github.event.issue.labels.*.name, 'blocker'))))
    permissions: {contents: read, issues: write, actions: write}
    uses: $/.github/workflows/queue.yml
```

The central jobs inside those workflows keep the template's conditions word for word:

- **Board:** `is_template == false`, a push only to the default branch, no fork's pull request. It adds `github.actor != 'dependabot[bot]'`, since Dependabot's runs have a read-only token. Its concurrency group is `symphony-board`.
- **Workers:** concurrency per worker.
- **Coordinator:** concurrency per epic, with each job asking `route` again when its turn comes.
- **Metrics:** the fork and template guards.

Nesting is three levels (copy, dispatcher, workflow) of the ten allowed, and 8 of the 50 reusable workflows one file may reach (`gh:.../reusing-workflow-configurations.md`, Limitations). The composite action every central job runs, `central/run/action.yml`, reads its inputs only through `env:`, takes `github.token` as its default token, and runs `python3 -I "$GITHUB_ACTION_PATH/../runtime/cli.py" action`.

Not yet measured, to settle in the canary before v1.0.0:

- the OIDC exchange from a reusable workflow;
- `$/` across organizations in practice;
- the approval-required run against the dispatched check;
- Dependabot's grouping pattern;
- the bootstrap's start-up time in a cloud session (one depth-1 fetch of about 2 MB of files);
- whether a SessionStart output with a long board stays under the 10,000-character cap, a risk today's hook has too.

---

# Critique of the runtime design


**Verdict.** Centralizing Symphony is feasible and worth doing. GitHub documents everything the design relies on:
- `$/` resolves "against the repository of the file it appears in ... at the running commit" (gh:content/actions/reference/workflows-and-actions/workflow-syntax.md:741-749).
- The job's workflow identity (`job.workflow_repository`, `job.workflow_sha`) is available (contexts.md:385-388).
- Workflows can nest ten levels deep, and one file can reach up to 50 reusable workflows (reusing-workflow-configurations.md, Limitations).
- Dependabot updates reusable-workflow refs (dependabot-version-updates.md:64).

As drafted, though, the design has four problems:
1. Three unknowns could sink the Claude jobs, the narrow caller and the check on bot-opened pull requests.
2. It understates the blast radius. Every machine follows the moving tag, a bad release can persist after rollback, and the front door would run release code in the job that holds both Apps' private keys.
3. It reverses a recorded owner decision on privacy. A public repository that holds only releases would not.
4. Setup for adopters is not simpler. Only the pull request gets smaller.

**Sources.**
- github/docs main at 602021b (2026-10-12), cloned to `/tmp/claude-0/-home-user/3dc8ab18-0f0b-58a6-80b3-e06fe3b0d17b/scratchpad/central/critique/ghdocs` and cited as `gh:<path>`.
- anthropics/claude-code-action `v1` = 1d6de8c, at `/tmp/claude-0/-home-user/3dc8ab18-0f0b-58a6-80b3-e06fe3b0d17b/scratchpad/central/critique/cca/repo`.
- Claude Code docs as the design fetched them, under `/tmp/claude-0/-home-user/3dc8ab18-0f0b-58a6-80b3-e06fe3b0d17b/scratchpad/central/docs/` and cited as `cc:`.
- symphony-start is now at 8a25210, which is newer than the eac10fb the design measured.

## 1. Feasibility: measure these before building

**1. [blocker] claude-code-action may succeed while doing nothing.**
- On a "workflow validation" refusal, the action logs a warning, sets `skipped_due_to_workflow_validation_mismatch=true` and returns success (src/github/token.ts:24-26, 125-137; src/entrypoints/run.ts:178-183).
- The server's own message, quoted in the action's tests, is: "The workflow file must exist and have identical content to the version on the repository's default branch" (test/token.test.ts:75).
- Nobody documents which file it checks when the job is defined in OpenSpineConsortium/symphony. If it is the job's own file (`job_workflow_ref`), that file is not on the copy's default branch. It may also be compared with the runtime's `main`, which differs from `v1` whenever `main` has moved ahead.
- Then every worker, coordinator and @claude run in every copy goes green and does nothing. workers.yml's "Go another round" step, gated on `steps.claude.outcome == 'success'` (/home/user/sdlc-template/.github/workflows/workers.yml:162), would keep re-dispatching up to the worker's round limit.
- **Fix:**
  - Measure first, both with `v1 == main` and with `main` ahead.
  - Every central job treats that output as a failure.
  - The fallback `github_token` loses checks on what Claude pushes: GITHUB_TOKEN pushes start no workflow, and its pull requests' runs wait for approval (gh:data/reusables/actions/actions-do-not-trigger-workflows.md). Each Claude job would then have to dispatch ci.yml itself.
  - Keep the Claude jobs out of v1 until this is answered.

**2. [high] Nested permissions and the interface are frozen.**
- The docs say a called workflow's token "can be only downgraded (not elevated)", and that nested workflows can have only "the same or more restrictive" permissions (reusing-workflow-configurations.md).
- From GitHub's error messages as users report them (not in the docs; measure): the run fails at startup with "The nested job ... is requesting ..., but is only allowed ...". The check runs when the run is created, so jobs whose `if:` is false count too.
- Then the design's "narrower variant ... drops `id-token: write` ... v1 accepts both forms" (section 3.2) fails on every event, because the dispatcher's workers and coordinator jobs request `id-token: write`.
- Any v1.x release that widens a central job's permissions stops every copy.
- The same freeze applies to inputs and secrets: v1 may add optional ones but must never remove one a caller passes.
- **Fix:**
  - One dispatcher per caller shape. The protocol-only dispatcher has no `id-token` job.
  - A test, per shape, that each job's permissions fit inside that shape's grant.
  - A CI job in the runtime that calls each dispatcher through each caller shape on every pull request, so startup failures show up there and not in copies.

**3. [high] One broken file breaks every event in every copy.**
- GitHub: "A workflow that contains nested reusable workflows will fail if any of the nested workflows is inaccessible to the initial caller workflow."
- Every event resolves all eight called workflows. Today a bad queue.yml breaks only crowd queueing.
- **Fix:**
  - Canaries run every route, with a bake period before `v1` moves.
  - Write down the rollback. After moving `v1` back, "Re-running all jobs ... will use the reusable workflow from the specified reference", while re-running failed jobs reuses the bad commit (gh:data/reusables/actions/partial-reruns-with-reusable.md).

**4. [medium] Two runs named `check` on one head.**
- Pull requests that GITHUB_TOKEN opens or updates get approval-required `pull_request` runs (actions-do-not-trigger-workflows.md).
- Runs waiting for approval longer than 30 days "expire and are marked as failed" (gh:content/actions/how-tos/manage-workflow-runs/approve-runs-from-forks.md).
- The text-sync and "Add a worker" pull requests would carry that pending `check` run beside the dispatched one.
- "Required status checks do not take workflow, matrix, or event trigger types into account" (troubleshooting-rules.md:40). Which of two same-named runs counts, and what an expired one does, is not documented.
- **Fix:** measure it. Better, open those pull requests with an App token (item 22).

**5. [medium] Set permissions on the calling job.**
- The docs say: "If `jobs.<job_id>.permissions` is not specified in the calling job, the called workflow will have the default permissions."
- A new personal repository's default is read-only contents and packages (managing-github-actions-settings-for-a-repository.md).
- The callers set permissions at workflow level only. Repeat them on the calling job, and run a canary in a personal repository with the restricted default.

## 2. Security: how bad, and how bounded

**6. [high] Every machine follows the moving tag.**
- session-start resolves the ref fresh (`runtime fresh`, section 2.5). So every contributor's machine runs whatever `v1` points at, at their next session, with no change in any copy.
- Hooks run "with your full user permissions" (cc:hooks.md:4107). Claude Code's trust is over settings.json, which never changes here.
- SessionStart stdout is "added as context that Claude can see and act on" (cc:hooks.md:810). A bad release can instruct every session directly, around the reviewed text sync.
- In crowd mode, this bypasses the code-owner review the crowd ruleset requires on exactly these paths (docs/setup/ruleset-crowd.json:19; scripts/crowd.py:120-125).
- **Fix:**
  - The bootstrap never resolves a moving ref. It runs only the exact commit in `.github/symphony/copy.json`, which only the reviewed text-sync pull request changes.
  - It verifies that commit is a `vX.Y.Z` tag target before running it (item 11).
  - Background Actions jobs may follow `v1`. The required check and machines follow the reviewed pin.

**7. [high] "Cannot persist" is wrong.**
- In a whole-template copy, the Setup App ticks "Allow GitHub Actions to create and approve pull requests" (/home/user/sdlc-start/PRIVACY.md:258-260).
- There, with the caller's contents, pull-requests and actions write, a bad release can:
  1. open a pull request that changes `scripts/symphony.sh` or `.claude/settings.json` (not workflow files);
  2. dispatch ci.yml on it, so its own check code reports green;
  3. merge it, because ruleset-main.json requires no review (`required_approving_review_count: 0`, `require_code_owner_review: false`).
- From then on every machine runs the attacker's bootstrap, even after `v1` moves back. `actions: write` also lets it delete its own run logs.
- **Fix:**
  - Add code owners on the Symphony-managed paths (`.claude/`, `scripts/symphony.sh`, `.github/`) and turn on `require_code_owner_review` in the main ruleset. Bot-authored pull requests then need one click from the owner, and sessions rarely touch those paths.
  - This changes the decision "the rulesets require no review" for those paths, so it is the owner's call.
  - Without it, say plainly that a bad `v1` can write any non-workflow file on every copy's default branch.

**8. [high] The front door would run release code beside both private keys.**
- adopt-run.yml is one job (`adopt`, /home/user/sdlc-start/.github/workflows/adopt-run.yml:104-106).
  - It names `SDLC_APP_PRIVATE_KEY` at lines 137, 205 and 288.
  - It names `SDLC_SETUP_APP_PRIVATE_KEY` at lines 473, 495, 512 and 566.
  - It runs template code in the same job at line 713.
- The design points this job at `v1` and runs `runtime/cli.py fill` there (section 3.3).
- The template's own rule applies: "GitHub hands a job's runner the value of every secret the job names ... code that runs on that runner can read it" (/home/user/sdlc-template/.github/workflows/ci.yml:54).
- SymphonyBoard holds Contents, Pull requests, Issues, Checks and Workflows write on every installation (PRIVACY.md:23-30). That includes workflow files, which the design says a bad release cannot reach.
- **Fix:**
  - Stage the files in a job that names no secret, from an exact release commit pinned in symphony-start (never `v1`).
  - Hand the staged tree over as an artifact. The job holding the keys runs nothing from the release.
  - Worth doing now: the job already runs private template code beside the keys.

**9. [medium] The check shares a workspace with central code.**
- ci.yml runs `run@v1`, then `bash scripts/check.sh`, in one job. Central code can rewrite the project's checks before they run.
- **Fix:** separate `symphony` and `project` jobs, with `check` as a small job that needs both and fails unless both succeeded.

**10. [medium] The release gate does not fit a one-person organization.**
- "An account no Claude session is signed in with" is not available:
  - GitHub's terms allow one free account. A machine account "can only be used for running a machine" (gh:content/site-policy/github-terms/github-terms-of-service.md:84-86).
  - "Prevent self-review" needs a second person (deployments-and-environments.md:28).
- Cloud sessions act on attached repositories with "your real credentials substituted" (cc:cloud-environments.md:251-253).
- The proxy refuses *pushing* a tag. It does not stop creating or moving one through the REST API. So "Cloud sessions cannot push a tag at all" does not stop a session from moving `v1`.
- **Fix:**
  - A tag ruleset on `v*` whose only bypass is a dedicated release App, with its key only in the `release` environment.
  - The owner approves in the web UI.
  - Never attach the runtime repository to a session with write access.
  - Measure whether the token sessions act with can call the pending-deployments endpoint.
  - A second human is the only real two-person gate.

**11. [medium] Pins and keys.**
- **SymphonyBoard's key in the runtime repository.** It is set on symphony-protocol or as an organization secret with `--visibility all` (docs/setup/owner-checklist.md:346-357), and it mints tokens for every installation. Use a separate App, installed only on the organization's own repositories, for the library sync.
- **Commits that live only in a fork (sometimes called "imposter commits").** GitHub's lockfiles check that a commit "must exist within a branch of the source repository" (gh:content/actions/concepts/security/workflow-dependency-lockfiles.md). Plain SHA pins do not. A pull request could swap a pin for a fork's commit and keep a convincing `# v1.4.0` comment. That fork commits can be fetched by SHA through the parent is known behavior but should be measured.
  - Verify every pin against `git ls-remote --tags` before running it.
- **The settings.json allow list.** The proposed settings.json allows `Bash(bash scripts/symphony.sh:*)`. That pre-approves `setup-repo` and `crowd setup`, which change GitHub settings with the person's own gh credentials. Today the allow list holds only checks and read-only git. Allow `bash scripts/symphony.sh check` only.

**The bound.**
- With the fixes in items 6-11, a bad release reaches only the background jobs' GITHUB_TOKEN, until `v1` moves back.
- Without them, it reaches every copy's default branch, every contributor's machine, and both Apps' keys, and it persists.

## 3. Privacy

**12. [needs the owner's decision] Publishing reverses a recorded decision.**
- The decision reads: "'Free to use' is not 'free access to the source' ... sdlc-start, which holds no file of it" (/home/user/sdlc-template/CLAUDE.md:43).
- The owner's message of 2026-10-13 approves centralizing. It does not say to publish.
- Outside copies can call only public workflows (access table), so the runtime's code must be readable.
- Much of it already is. Adopted files are MIT-licensed and may sit in public repositories (/home/user/sdlc-start/README.md:49). docs/history (181 KB of research) is copied into every whole-template adoption today (`/tmp/claude-0/-home-user/3dc8ab18-0f0b-58a6-80b3-e06fe3b0d17b/scratchpad/central/sim/newtarget/docs/history`).
- What would be new is public *development*: issues, pull requests, commit messages with Claude-Session links, and the tests.
- **Fix: a public repository that holds only releases.**
  - Development stays in the private template, which calls its own workflows locally and is the first canary.
  - An approved release job pushes one commit per release to the public repository: runtime, workflows, action and copy skeleton. No tests, no history, no decisions block.
  - It tags an immutable `vX.Y.Z` and moves `v1`.
  - The public repository has no sessions or pull requests, which also shrinks the attack surface in item 10.

**13. [medium] Metrics consent.**
- Adopters were told "no later change reaches your repository by itself" (README.md:49).
- With `v1`, a new METRICS.json key reaches every copy, and the `metrics` branch is public in public repositories.
- PRIVACY.md's "Changes" section (:252-255) only publishes new versions; adopters are not asked again.
- **Fix:**
  - Each copy records the statement version it accepted (for example `on 4` in `.github/symphony-metrics`).
  - The runtime writes only that version's keys.
  - A newer version reaches a copy with its text-sync pull request.

## 4. Crowd mode, the front door and existing copies

**14. Crowd mode.**
- Item 6 applies.
- Crowd setup sets `can_approve_pull_request_reviews: False` (scripts/crowd.py:1100). GITHUB_TOKEN cannot open pull requests there, so the text sync always falls back to an issue, and crowd text falls behind the runtime.
- The workflow audit (`WORKFLOWS_NEEDED`, crowd.py:97, 2204-2209) and the code-owner probes (`OWNER_PROBES`) must cover the new caller, the bootstrap and copy.json.
- **Fix:**
  - Crowd mode requires exact pins everywhere: Dependabot for the CI pins, copy.json for machines.
  - The audit fails on a moving ref.

**15. Existing copies.**
- The new Upgrade kind and `migrate` are the parked update route under another name.
- Copies whose owner uninstalled the App can be upgraded only by hand.
- The number of copies is not measured. The sweep can count them without naming any.
- spine-program is frozen at sdlc-protocol 0.2.0, with board, metrics and tidy and no protocol.yml (/home/user/spine-program/tools/VENDORED). Migrate it first, by hand.

## 5. Callers, schedules, concurrency and cost

**16. Renames break every copy.**
- GitHub "does not support redirects for actions or reusable workflows ... any workflows using that action with the previous name will fail" (gh:data/reusables/actions/actions-redirects-workflows.md). This is documented, not "nothing has shown".
- Repositories here were renamed on 2026-10-11, and an LLC is planned.
- **Fix:**
  - The organization and repository names become part of v1.
  - If a rename is ever forced, put forwarding workflows at the old name. That adds one nesting level (4 of 10).

**17. Schedules routed by cron text.**
- The workers move from `43 */6` (workers.yml:37) to the board's `17 */6`.
- Editing a cron in a copy silently stops that route.
- **Fix:**
  - An unknown cron runs the board and the workers.
  - Keep the workers on their own cron.

**18. Cost of the six-hourly sync.**
- Each job is billed at a minimum of one minute: GitHub rounds "each job ... up to the nearest whole minute" (gh:content/billing/reference/actions-runner-pricing.md:14).
- That is about 120 minutes a month per private copy, the cost the board's own header warns about (board.yml:70-74).
- **Fix:** run the sync daily, or inside the board job.

**19. Smaller caller and concurrency fixes.**
- **One workflow turns everything on or off.** Today you can disable Workers or Metrics alone. Add `vars.SYMPHONY_OFF`, checked in each route's `if:` (vars are allowed there, contexts.md:100).
- **runs-on is not a caller keyword.** Use `runs-on: ${{ vars.SYMPHONY_RUNNER || 'ubuntu-latest' }}` (contexts.md:103).
- **Org policies:**
  - The policy "Require actions to be pinned to a full-length commit SHA" rejects `run@v1`. "Reusable workflows can still be referenced by tag" (gh:data/reusables/actions/actions-use-policy-settings.md).
  - Organizations that allow-list actions must add `OpenSpineConsortium/symphony`.
  - A copy that adopts a lockfile stops following `v1`.
- **Concurrency:**
  - Never use `${{ github.workflow }}` in central groups: it is the caller's name (reusing reference, note).
  - Add groups for sync and metrics. Today: metrics.yml:80-82, protocol.yml:54-56.
  - Take the re-dispatch target from `github.workflow_ref` instead of hardcoding `symphony.yml`.
- **Skipped checks.** Every pull request event lists six or more skipped dispatcher jobs as checks. Cosmetic.

**20. [medium] CRLF in the bootstrap blocks every Bash call on Windows.**
- A bash script with CRLF line endings fails to parse and exits with code 2. A PreToolUse hook that exits 2 "Blocks the tool call" (cc:hooks.md:823-825, 933-937).
- Reproduced: `/tmp/claude-0/-home-user/3dc8ab18-0f0b-58a6-80b3-e06fe3b0d17b/scratchpad/central/critique/crlf.sh` printed "syntax error near unexpected token" and exited 2.
- spine-program has no .gitattributes, and protocol-only adoptions add none.
- **Fix:**
  - Merge `scripts/symphony.sh text eol=lf` into .gitattributes.
  - Move the bootstrap to `.github/symphony/`, out of the project's own `scripts/`.
- The same latent risk exists today in symphony-marketplace: it has no .gitattributes, and plugins/sdlc/scripts/guard.sh is a bash hook. Not measured.

**21. [low] Race in the bootstrap.**
- Worktrees share one cache, and `rm -rf "${cache:?}/$sha" && mv "$tmp" "$cache/$sha"` deletes a finished runtime another session may be running from.
- **Fix:** keep the first finished copy and discard the second.

## 6. Text sync

**22. GitHub-token pull requests fit poorly.**
- They need approval to run (item 4).
- A new personal repository by default does not let workflows "create or approve pull requests" (managing-github-actions-settings-for-a-repository.md). Sweep adoptions and crowd repositories leave that off.
- A copy that edits a synced file never receives it again.
- Hooks in a merged `.claude/settings.json` never sync.
- **Fix: a fleet sync in symphony-start, built like the sweep.**
  - A scheduled run uses SymphonyBoard's token to open one update pull request per adopted repository.
  - App-opened pull requests trigger normal check runs, and the App's Workflows write covers caller migrations and settings.json.
  - Its public log names repositories only by id.
  - PRIVACY.md must say the App opens update pull requests before it does.
  - Project-specific additions go in sibling files (for example `docs/agents/PROTOCOL.local.md`), so managed files stay managed.

**23. Releases that tighten the check, and text that lags.**
- A release that makes `check` stricter turns every copy red at once. New rules should warn for one release before they fail.
- A protocol change that sessions must follow is a major version, or the runtime keeps reading both forms, as the library already does for `account:` and `agent:`.
- session-start prints one line when the copy's text is behind its runtime.

## 7. Does it simplify setup?

**Not for adopters.** The steps stay the same: install two Apps, press Create, merge (README "Adopt it in three steps"), plus the Claude token for the whole template. What improves is the pull request: 145 files become 38 (or 28 become 8), and template-init's job on every push goes away.

**New costs:**
- Organizations with action allow-lists must allow the runtime.
- Organizations that require SHA pins cannot use `run@v1`.
- Every machine needs the network for its first fetch.
- The owner's own setup grows: rename, release App, tag ruleset, environment, immutable releases, canaries.

**The simplification this design makes possible but does not take:** protocol-only as "add one file".
- The first run makes the labels and the board, and offers the remaining files as a branch plus an issue. GITHUB_TOKEN can push a branch even where it may not open a pull request.
- Nothing is shared until the App is installed ("A repository without the App is never read", docs/setup/metrics.md:314).

## 8. Statements in the design that are stale or wrong

- **section 0 (protocol-only metrics fail at import).** Fixed for new adoptions by symphony-start#37 (ef90b86, merged 2026-10-13 05:18Z). Adoptions made between #57 and #37 keep the broken workflow, which is the drift problem itself. Protocol-only adoptions now also bring economics.py and usage.py.
- **Renames.** Already covered: it is documented, not "nothing has shown" (item 16).
- **Tags, persistence, "v1 accepts both forms".** "Cloud sessions cannot push a tag" (item 10), "cannot persist" (item 7) and "v1 accepts both forms" (item 2) are corrected above.
- **"A Claude session in the job can neither move nor commit it."** The default `Bash(python3:*)` (workers.yml:139, claude.yml:68) can rewrite any file on the runner. This is no stronger than today's RUNNER_TEMP copy.

## 9. What to build first

0. **Owner decisions.** Reworded:
   - Publish releases only, not development.
   - The moving tag drives background Actions jobs only; the check, the hooks and every job holding a Claude token run a reviewed pin.
   - A release moves `v1` only through a dedicated release App, approved in the web UI.
1. **A one-day spike with a toy runtime**, so nothing private is published. Put it on a branch of the already-public symphony-protocol, called from:
   - sdlc-template-test (internal, organization);
   - Gregory-Schwing-MD-PhD/test-non-org (public, personal);
   - a private personal repository.

   Measure:
   - items 1, 2, 4 and 5;
   - `$/` across owners;
   - Dependabot's SHA-plus-comment update;
   - fetching a fork's commit by SHA.

   Items 1 and 2 decide the shape of everything after.
2. **Board, tidy and metrics only.** No Claude token and no `id-token`. Add the release App, tag ruleset and immutable releases, plus a protocol-only canary. Migrate spine-program by hand.
3. **Safety pieces.** The pinned bootstrap (copy.json, tag-verified), the split check job, the per-shape permission test, and the CI job that calls its own dispatchers.
4. **Front door.** The secret-free staging job (worth doing now), then the fleet sync, then Upgrade.
5. **The Claude jobs last**, in their own pinned caller, once item 1 is answered.
