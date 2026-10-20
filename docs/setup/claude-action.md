# Turning on @claude in issues and pull requests

Writing @claude on an issue, a pull request or a review runs a Claude Code
session in Actions (.github/workflows/claude.yml): it reads CLAUDE.md and
the rules like every other session, answers, fixes, or takes the work the
comment asks for. The same secret runs the workers registered to run in
Actions and the coordinator workflow (both below). Until the one secret
below exists, each of these workflows says so in its run and does nothing
more, so nothing here is required. In crowd mode
(docs/setup/crowdsourcing.md) none of this page applies: the repository
holds no Claude token, and the workflows never start while the repository
variable CLAUDE_CROWD is true.

## No API billing

The workflow authenticates with a subscription OAuth token, not an API
key: runs draw on the main account's Claude plan (Pro, Max, Team or
Enterprise) and bill nothing. That keeps the project's rule intact; the
token lives only in the repository's Actions secrets, which are settings,
not repository content, so the rule that no file holds a credential holds
too.

## Steps, once, by the main account

One OAuth flow does everything: on a machine where Claude Code is signed
in to the main account, run `/install-github-app`, pick this repository,
and approve the browser flow it opens. It installs the Claude GitHub App
and writes the repository secret CLAUDE_CODE_OAUTH_TOKEN itself, so no
token is ever copied by hand. The workflow is already on
{{DEFAULT_BRANCH}}; the next @claude mention runs it.

Or run `python3 scripts/tokens.py main` from a clone with gh signed in:
it runs `claude setup-token` for you behind a terminal of its own, keeps
the token out of sight and stores it as the secret through gh, and the
same wizard stores every account of yours as a slot of the pool a
benchmark in Actions runs on (docs/setup/claude-tokens.md).

By hand, where neither is at hand:

1. Run `claude setup-token` and approve it in the browser. It prints a
   token good for about a year and saves it nowhere.
2. Put the token in the repository secret CLAUDE_CODE_OAUTH_TOKEN, under
   https://github.com/{{REPO}}/settings/secrets/actions.

## What a run costs

- A run spends the main account's own usage: the five-hour window and the
  weekly limit, shared with that account's interactive sessions and
  routines. The workflow caps each run (--max-turns, a job timeout), but
  mentions are still deliberate asks, not decoration.
- The main token's tile on the control panel's Tokens tab (the variable
  SYMPHONY_CLAUDE_SETTINGS) sets the model, effort and fallback model of
  every run, the assistant's included; with none set, Claude's own
  defaults hold (docs/setup/claude-tokens.md). A stronger model or a higher
  effort spends more of the window on each question.
- Keep usage credits off on the main account unless overage billed at API
  rates is wanted; with them on, a run past the limits bills quietly.
- A pull request from a fork gets no secrets, so @claude does not run
  there; an account working in this repository pushes claim branches, not
  forks (docs/agents/PROTOCOL.md).

## The assistant issue

The control panel, the site's page that drives a Symphony repository as
the signed-in person (docs/memory/the-control-panel.md), asks through an
issue: once per repository and person it opens "Assistant: <login>",
labelled assistant, whose body says what the page is, and each question
is a comment on it with the page's state in a fenced block, which the
page polls for the answer. The page's side is not built yet; until it is,
a person opens the same issue by hand, labels it assistant, asks on it
with a comment that mentions @claude, and reads the answer on the issue.
The label is not one template-init makes: the six it makes are the claim
protocol's own list, held to the vendored library by the checks, so the
page makes the label before it puts it on the issue, or a person makes
it once at https://github.com/{{REPO}}/labels, any colour, since the
workflow reads only the name.

claude.yml tells the issue apart by that label alone, on an issue and
never a pull request, so a comment on it that says @claude, or its
opening with @claude in the body or title, runs the same job on the same
token, in the same five-hour window, with the step's settings changed:

- Ten turns in place of fifty.
- A tool list that only reads: Read, Glob, Grep, git log, git show, git
  diff, git branch and git ls-files, gh issue view and list, gh pr view
  and list, gh run list and gh run view. Reading runs needs actions: read
  on the token the action mints for gh, which carries none unless the
  step asks (its docs/configuration.md, Enabling GitHub Actions Access),
  so the step asks through additional_permissions for the assistant
  alone; gh pr checks, which needs checks: read as well, is left out.
  git fetch and sed are left out because each runs a program it is handed
  (fetch's --upload-pack, sed's e command), and the board needs no fetch,
  since the checkout brings every branch; Read takes a line range, and
  cat needs no rule.
- A deny list, since a deny holds over every allow, the repository's own
  .claude/settings.json included, which the action loads too: Edit,
  Write, MultiEdit and NotebookEdit; git add, git commit and git rm,
  which the action's tag mode allows whatever the allow list says; the
  action's own push script, scripts/git-push.sh under the action's path,
  the one push the tag mode allows, denied by a wildcard for that path, so
  the empty branch the action makes never reaches origin and its end-of-run
  commit, which it makes only for a branch that is on origin, never
  happens; and git fetch, sed, python3 and bash, each a way to run a
  program, the two scripts the repository's settings allow among them.
- The permission mode set back to default: the action's tag mode runs
  in acceptEdits, which approves edits and the file commands mkdir, touch,
  rm, mv, cp and sed inside the checkout with no rule at all, while in
  default mode whatever no rule allows is refused, the run having nobody
  to ask. The action takes the last --permission-mode it is given.
- The file .github/symphony/assistant.md appended to the system prompt
  through the CLI's --append-system-prompt-file, which the action passes
  through untouched. The file says what the page is, what to read, how to
  answer and the few lines of a reply the page acts on: the reads it
  does by itself (focus, open, filter, show, tab) and the changes it
  offers as buttons the person presses (run, give, merge, task, ask).

The job's permissions stay as they are: the tools, not the token, are
what keeps the assistant read-only. A question that asks for a change is
answered with what the person would do and where, never done; where the
panel has a button for that change, the answer names it in its symphony
block, and the page shows it as a button that runs only when the person
presses it, as the person, through the panel's own handler. Claude in
Chrome is not needed for this, and the run never writes. No run has
been made with these settings yet, so the first answer should show it
followed the file, and its run log a refusal should the session try the
push script, a file command or git fetch; if not, the flags are the
first thing to check, the wildcard deny of the push script and the
permission mode first. tests/test_claude_assistant.py pins each setting,
reading the workflow as text and running nothing.

A question costs one Actions run, tens of seconds to a few minutes (no
figure is measured yet), on the main account's usage like any mention.
The workflow sets no concurrency group, so two people asking at once are
two runs on the same window, and ten turns reached is a failed run,
which the comment says ("Claude encountered an error"), not a shorter
answer. On a public repository the issue and its answers are public.

Who may ask: the action answers only a GitHub user whose permission on
the repository is admin or write (checkActorWritePermissions in its
src/github/validation/permissions.ts, read on 2026-10-17; the maintain
role passes by the API's legacy permission field, which is not verified).
Anyone else, read or triage access among them, gets a failed run and no
reply, since the check runs before any comment is posted, and a bot is
refused unless the workflow's allowed_bots names it, which this one does
not. The page should check the person's permission before it offers the
assistant.

To change the vocabulary, edit .github/symphony/assistant.md; the page's
side, in the site repository, must match it, since the page executes
only the lines it knows. Nothing here needs a new secret or variable.

## Workers in Actions, optional

A worker in Actions is one file under .github/symphony/workers/ that says
"runs": "actions" (docs/agents/WORKERS.md), and
.github/symphony/workers/README.md lists its settings. Add one with the
"Add a worker" issue form,
https://github.com/{{REPO}}/issues/new?template=worker.yml, whose
workflow opens the pull request that adds the file where the repository
lets GitHub Actions open pull requests ("Allow GitHub Actions to create
and approve pull requests" under Settings, Actions, General, which
scripts/setup-repo.sh and the front door's Setup App turn on;
docs/setup/github.md, section 8), and otherwise answers with the link
that opens it in one press; or add the file by hand in a pull request of
its own. Once it merges,
.github/workflows/workers.yml runs every such worker on this token, one
run per worker, in parallel: every six hours, whenever an issue is
queued or given to one of them, and again while a worker still has
work, up to the "rounds" its file allows in a row. Before any Claude
session starts, a cheap step on GitHub's own token (tools/team.py) deals
the open work among them, by area first, so no two race for one issue
and a worker with nothing to do costs seconds of a runner and no plan
usage. Each worker's model and turns per run come from its file. Run the
workflow from its own page with "Run workflow", naming one worker or
none for all, to try it once; delete a worker's file by pull request to
stop it. A worker whose file says "lands": "auto-merge" turns on
auto-merge for its finished pull request, which needs "Allow
auto-merge" under Settings, General; turning off "Require branches to be
up to date" in the default branch's rules saves a run per worker each
time another lands. Give each worker its own name, after its job: a
routine and a worker in Actions under one name would each take the
other's claims for their own.

## The coordinator workflow

The same token runs the part of the coordinator that needs judgement,
.github/workflows/coordinator.yml (docs/agents/WORKERS.md); the board's
own run does the rest, releasing idle claims and telling open work that
overlaps, on GitHub's token alone. Label an issue epic and Claude plans
it into tasks that each own their files, given to the registered workers
whose area fits, or to the open queue where none is registered, and
starts the workers in Actions; the epic then loses the label todo, and
the board lists each task given to a worker under "Given to workers",
out of the Queue, so nobody else takes it. A worker that labels its task
blocked calls the coordinator to settle what it needs. When an epic's
last task closes, the coordinator checks the default branch as a whole,
since every task can pass alone while the whole fails, and fixes what the
pieces broke together on a pull request that lands by auto-merge, so
"Allow auto-merge" is needed here too. Every week it runs the
coordinator prompt, docs/agents/routines/coordinator.md, which splits
requests into issues and tidies the shared memory. Nothing turns it on
but the token, and no coordinator routine is needed beside it.

CLAUDE_ALLOWED_TOOLS, a repository variable, replaces the tools the
sessions of claude.yml, workers.yml and coordinator.yml may use when a
project's checks need more than git, gh, python3 and scripts/check.sh;
the workers themselves are files, not variables. Every worker in
Actions and the coordinator draw on the main account's one usage window,
so three workers in Actions spend it about three times as fast as one
session, and a Max plan suits several of them better than Pro.

## Keeping the token

Treat the token like a password: it is the main account's subscription.
It expires after about a year; run `claude setup-token` again and replace
the secret. To turn @claude off, delete the secret, and the workflow is a
quiet no-op again, as are the workers in Actions and the coordinator
workflow, which run on the same secret.
