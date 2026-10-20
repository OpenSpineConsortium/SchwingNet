# Symphony against Conductor and Agentastic

The comparison of 2026-10-17, written in the thread "Control panel sign-in" when the owner asked,
with microsoft/conductor's dashboard and agentastic.dev's release notes in hand, "tell me how im
doing compared to them, my strengths and weaknesses". It stands on its own so that the thread
that keeps docs/research/symphony-versus-competitors.md can fold it in; nothing here changes
that note. Each claim is graded as that note grades them: Verified means read in the product's
own code or pages on the day given; Inferred means a reading of ours from what was verified.

## What the two are

Conductor (microsoft/conductor, read from the clone of 2026-10-15 at commit 49af6de) is an
MIT-licensed Python 3.12 command line that runs a multi-agent workflow written in one YAML file:
agents with a prompt, a model and an output schema; routes as Jinja2 conditions evaluated by
code, first match wins, with loop-backs; parallel groups and for_each fan-outs; sub-workflows;
script, MCP, wait, set and terminate steps; human gates and questions. It is version 0.1.42,
"Beta", with 33 changelog entries from 0.1.10 (2026-04-30) to 0.1.42 (2026-10-06), roughly
weekly (its GitHub releases list is unreachable from here, so the count of releases is the
changelog's), about 10,500 test functions in 350 test files, CI on Ubuntu (Python 3.12 and
3.13) and Windows (3.13), and a large dependency surface (typer, rich, pydantic, jinja2,
fastapi, uvicorn, websockets, httpx, opentelemetry, the Copilot SDK, the Anthropic and OpenAI
clients; React 19, React Flow 12 and dagre in the dashboard). The engine is one local process
on the operator's machine, with script steps in Docker and, experimentally, an agent's loop in
an Azure Container Apps session; the dashboard is a per-run FastAPI server
on 127.0.0.1 that keeps the run's whole event history in memory, serves it to a late joiner and
streams it over a WebSocket, drawn by dagre and React Flow with a status border, an elapsed
timer, tokens and cost on every node, a right pane with the rendered prompt, the activity stream
and the structured output, a bottom pane with Log, Activity and Output, deep links into a node,
Stop, Resume, Kill and mid-run guidance. Providers: Copilot (gh auth), OpenAI (a key, in the
source and not in the README's list), Claude's Messages API (a key), and three experimental
ones, a Claude Agent SDK provider that drives the claude CLI and in subscription mode blanks
ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, CLAUDE_CODE_OAUTH_TOKEN and the three cloud backend
selectors in the child and confirms the login with claude auth status, labelling its cost
"API-equivalent estimate", NousResearch Hermes, and Azure Container Apps. Nothing in its source
reads GitHub issues or pull requests; GitHub is reached for workflow registries, plugin sources
cloned by owner/repo, the daily update check and the Copilot credential. (Verified.)

Agentastic (agentastic.dev, read 2026-10-17: the release notes from v0.10.0 of 2026-09-01 to
v0.14.0 of 2026-10-16, the home page, the docs for Manager Agents, Kanban, Tasks, Chat, Issue
Tracking, Providers, Cloud Agents and the dev CLI) is a free, closed-source native macOS IDE
(macOS 14 and up, an iPhone companion, a CLI on macOS, Linux and WSL) that runs any terminal
coding agent (55 definitions, Claude Code among them) in parallel, one git worktree, container,
SSH host or cloud VM each. Progress per agent is a status word (Running, Stopped or Not Running on a
task, Input Needed and a Thinking step in a chat), a pinned plan with a completed/total count, a sub-agent panel with one line per
sub-agent, an edited-files card per turn, and a Kanban board that turns worktrees into cards
grouped by label, each card with branch, status, live diff counts, the pull request number and
relationship badges. Manager Agents (v0.12.0, 2026-09-24) are a persistent agent that writes no
code, holds objectives, sleeps and is woken by a heartbeat (15 minutes to daily), a worker going
idle or failing, mail or a manual run, with events within 45 seconds coalesced into one run;
since v0.14.0 a Manager's feed carries sandboxed HTML cards (charts, tables, checklists, forms)
and it can publish pages that update in place. Its "Provider Pass" (v0.14.0) is a wallet of the
agent's subscriptions and API keys; the cloud-VM path copies the Mac's signed-in Claude Code and
Codex credentials onto a VM at Modal, Fly.io or Vercel Sandbox ("Treat the VM as an
authenticated device"; that the user pays the provider is inferred, the page does not say). The
"Conductor" Agentastic compares itself with is conductor.build, a Mac app at $50 a month, not
microsoft/conductor. (Verified.)

Neither coordinates a repository's issues. Conductor's graph is a workflow definition; its
fleet view lists runs as a table and shows a run's detail as a topology that is deliberately
"not a DAG"; Agentastic has no dependency graph of tasks, only manual worktree links (Depends
On, Blocks, Reviews, Conflicts With, Supersedes) shown as badge counts, no epics, no parent and
child issues, issue tracking built in for Linear and Sentry, and GitHub, GitLab and Forgejo
issues and Notion pages attached to a prompt. Symphony's unit is an issue claimed by a branch, on GitHub, by any number of people
and agents; the three overlap in the dashboard the owner pointed at and nowhere else in their
shape. (Verified for both products; the overlap is Inferred.)

## Head to head

| | Symphony | Conductor | Agentastic |
|---|---|---|---|
| Unit of work | One issue, one branch claude/<N>, one pull request, by any worker | One run of one YAML workflow, one process | One agent in one worktree, container or VM, on one Mac |
| Where state lives | GitHub: issues, labels, claim branches, the board on branch `board`, pull requests; nothing of ours is served but the control panel's stateless sign-in Worker, which keeps no state and no Claude credential (the Apps' webhook server is to be deleted) | In the run's process; the events JSONL and the checkpoints under $TMPDIR/conductor; PID files, dashboard tokens, environments and the bundle cache under ~/.conductor | On the Mac: worktrees, a Manager's Home as a git repository, a SQLite index; optional relay through Agentastic's servers |
| Several people | Yes, by design: every account's sessions, routines and workers in Actions share one repository and one board | No: single user, one machine; "multi-user or team visibility" is a stated non-goal of its fleet view | No: one Mac, one person; sharing is a tunnel or their relay |
| A graph of the work | None drawn today; GitHub holds the hierarchy and can hold the dependencies, which nothing of ours writes yet; the board lists neither (docs/research/control-board-graph.md) | The workflow's own DAG, live, with containers for parallel groups and sub-workflows | None; relationship badges on Kanban cards |
| Live per-node progress | Labels and comments on the issue, the draft pull request and its checks, the Actions run log for a worker in Actions, commit trailers; polled through GitHub's API | Status, elapsed, tokens, cost, context-window bar, the activity stream and the log, streamed over a WebSocket from the process | Status word, plan count, sub-agent lines, diff counts, a Manager's feed and cards |
| Preconditions and gates | A claim is refused by git itself; the required check holds the merge (the QA gate is decided and not built); a blocker label stops everyone; blocked tasks wait on the coordinator | Human gates and questions in the YAML, answered in the terminal or the dashboard; routes decided by code | A Manager's objectives, verified by a command, a plugin query, a report or a model judgment; status claims stay proposals until verified by one of those or confirmed by a person |
| Credentials | In a copy, one secret, the repository's CLAUDE_CODE_OAUTH_TOKEN (the owner's own pool of accounts adds SYMPHONY_CLAUDE_1 to 8); never an API key; each person on their own account | A key per provider in the environment, or gh auth for Copilot, or the claude CLI's own login in subscription mode | A wallet of subscriptions and API keys; signed-in credentials copied to cloud VMs |
| Cost to run | $0: GitHub's free features and Actions minutes, Claude on the subscription | $0 software; the model bills, or the subscription; a machine | $0 app; the model bills; cloud VMs at the user's provider |
| Budget | What the work cost is recorded beside it (Symphony-Usage trailers, usage artifacts, the metrics' ratios); no cap in dollars; a run is bounded by claude.yml's --max-turns 50 and 45-minute timeout; a cap of 10 Claude runs a day per repository is decided (2026-10-13) and not built | budget_usd per run, audit or enforce, with a budget_exceeded event; a priced table per model | A Usage panel at list rates; 100 free messages a day on its own free tier |
| Failure and resume | A claim idle 24 hours is released with its work kept under released/<N>-<sha>; a run in Actions is not resumable; a session checkpoints itself (cswap) | A checkpoint on failure by default, periodic ones when the workflow turns them on; conductor resume continues the same run; replay of any recorded run | Remote and cloud agents keep running on their hosts when the app closes; a Manager wakes when a worker fails or goes idle |
| Assistant in the UI | @claude on the repository's token; a person's own Claude in a browser can drive the panel | Mid-run guidance to the running agent; an MCP server that exposes workflows as tools | Chat with any agent; the Agentastic agent; Managers draw cards and pages |
| Measurement | coordbench on CooperBench's pairs, the field metrics, the profiling programme; results pending the full run | Performance test markers; no benchmark of coordination published in the repository | None published |
| Maturity | Private template, no release yet, one maintainer, tests per tool and a required check; symphony-protocol 0.5.0 awaiting approval | 33 changelog entries, 10,500 tests, CI on Ubuntu and Windows, towncrier changelog, Microsoft's security process | Closed source, weekly releases, no public tests |
| Licence | MIT for the protocol and the plugin; the runtime may take a source-available licence; the hosted parts paid | MIT | The app closed; MIT shown for bundled components |

Every row is Verified against the sources named at the end except the Symphony column's
"measurement" row, whose results are pending, and the maturity row's test counts for Symphony,
which were not counted for this note.

## Where Symphony is stronger, by design

1. It is a coordination protocol for many hands, and the other two are single-user tools. A
   claim is the first push of a branch name, which git refuses a second time; the board is a
   file every account reads; the coordinator releases idle claims and tells overlapping work;
   nothing depends on one machine staying up. Conductor's own fleet design names team
   visibility as a non-goal, and Agentastic's Manager lives in one Mac's Application Support
   folder. (Verified.)
2. No credential of a person is ever copied, and the one thing of ours that is served, the
   control panel's stateless sign-in Worker, holds none. Conductor's dashboard is a server per
   run on the operator's machine; Agentastic copies a signed-in Claude Code login onto a cloud
   VM and keeps a wallet of API keys. A copy of Symphony holds one secret, the repository's own
   subscription token (the owner's own pool of accounts, SYMPHONY_CLAUDE_1 to 8, is more, by
   the owner's decision), and refuses API keys by rule, the checks refusing the shapes of
   secrets, while the advice that the token be an account nobody uses by hand is not enforced;
   crowd mode makes each contributor work on their own account and the project hold nobody's
   credential. (Verified.)
3. The gate is GitHub's, not the tool's word. A pull request lands only when the required check
   is green (the QA gate with a readable report is decided and not built); a worker's claim that
   it is finished is a comment, not a merge. Agentastic states the same principle, status claims
   are proposals until confirmed, but confirms them by a person on one Mac; Conductor's human
   gate is a step in the YAML. (Verified.)
4. The record is in git and is shared. What a session spent, what a run cost, which failures
   happened in which work setting, the research and the memory, all ride in the repository that
   every account clones; Conductor's events JSONL lives under $TMPDIR and its run records under
   one home directory, and Agentastic's Manager Home is one Mac's git repository. (Verified.)
5. It is measured against a benchmark of coordination, with a pre-registered plan, on the same
   tasks Claim Plane's study used (docs/research/outside-code-bases.md); neither product
   publishes a measurement of coordination. The results are pending the full run and nothing
   is claimed from them yet. (Verified that none is published; Symphony's numbers are
   pending.)
6. The adoption of a repository is one press and a merge, with no install on anyone's machine
   beyond Claude Code itself, though running Claude in it then takes the owner's clicks (the
   token secret, the Claude GitHub App, the repository settings) and no adoption by a user is
   measured yet; and the protocol library in a copy never falls behind, since each release comes
   through the copy's own workflow; the rest of a copy's files do fall behind, since the update
   route is parked and the runtime that would replace it is not built. Conductor is a
   curl-and-uv install with a daily update check; Agentastic is a
   Mac app from the store. (Verified.)

## Where Symphony is weaker, today

1. No live view. Conductor streams every event of the run into one screen as it happens,
   with the prompt, the activity and the log beside the node; Agentastic shows a plan count, the
   sub-agents and the diff on every card. Symphony's control panel polls GitHub's API as the
   signed-in person, so what a worker is doing is read from its labels, comments, pushes and
   checks, with the Actions log one click away for a worker in Actions and no log at all for a
   claude.ai session, whose transcript no API exposes. (Verified.)
2. No graph drawn. GitHub holds the hierarchy (the coordinator writes tasks as native sub-issues,
   a convenience whose failure it ignores and which nothing of ours reads back; the protocol's
   own link is the "Epic: #N" line in a task's body and the tasks marker on the epic, team.py)
   and can hold the dependencies, which nothing of ours writes; no view of ours or GitHub's
   draws them, and the board lists overlaps as text. The companion note's recommendation is a
   Mermaid section drawn by the board's run, a static picture, where Conductor has a pannable
   canvas with containers, a minimap and deep links. (Verified.)
3. No budget enforcement and no resume. Conductor caps a run in dollars and stops it, checkpoints
   on every failure and resumes the same run; Symphony records what the work cost beside it, on
   each push for a session's trailer and at the run's end for a worker in Actions, shows it on
   no node, caps nothing yet (a cap of 10 runs a day is decided and not built), and a worker's
   run in Actions that dies is started over from its branch. (Verified.)
4. Latency is unmeasured. A Claude run in Actions answers in tens of seconds to minutes, a figure
   no repository of the project has recorded (docs/checkpoints/2026-10-14c/handoff.md); the
   other two answer in the time the model takes, on the machine in front of the person.
   (Verified that it is unmeasured.)
5. The instructions a run loads are long in the template itself. Every Claude run in Actions
   reads CLAUDE.md whole; the template's is 143 lines and 36 KB, most of it the checkpoint
   block of decisions and constraints that grows with each handoff, which template_init empties
   in a copy (reset_checkpoint_block), so a copy's runs load the short form and only the
   template's own runs the whole; Conductor's AGENTS.md is 114 lines and under 7 KB under a
   12 KiB cap and routes to guides from it, and the Claude Code docs advise a concise CLAUDE.md
   for cost. (Verified for both; the cost of ours is not measured.)
6. Maturity and hands. Conductor has 33 changelog entries, about 10,500 tests and Microsoft's processes
   behind it; Agentastic ships weekly to a store. Symphony is one maintainer's template with no
   public release yet, whose protocol library awaits its 0.5.0 approval, and whose control
   panel is one script of 1,700 lines with a browser check suite in another repository.
   (Verified.)
7. No in-page assistant beyond a box that posts @claude. Conductor takes guidance mid-run and
   exposes workflows as MCP tools; Agentastic has chat with every agent and Managers that draw
   cards. Symphony's assistant design (the companion note) is an issue thread answered by an
   Actions run, bounded by that run's latency and by the daily cap once it is built, because
   the rules allow no model call from the page. (Verified for the products; the design is a
   proposal.)

## What to borrow and what not to

From Conductor, without its server: a typed event catalogue replayed from a full history on
connect and then streamed, which for a static page means polling GitHub's API with conditional
requests and replaying into one store; dagre's top-to-bottom layout with containers for groups
and inline-expandable sub-graphs, if a canvas of ours is ever built; node chips of status,
elapsed and tokens with a hover tooltip; deep links by query string; a status vocabulary derived
from explicit markers and never from timing; and the label "estimate" on every cost figure that
is not a bill, which Symphony's cost page should adopt, since today it says the work is priced
at Anthropic's API list prices. Its subscription mode for the Claude
Agent SDK, which blanks the key, token and cloud-backend variables in the child and checks
claude auth status, is
the same rule Beethoven enforces and is worth citing as a precedent from Microsoft. (Inferred.)

From Agentastic, under the rules: the priority-sorted feed headings (Needs you, Problems,
Objectives, Outputs, Activity) as the control panel's top section, computed from the board, the
labels and the pull requests; the six-colour pull request tag (draft, checks running or changes
requested, failing or closed, passing or approved, open unreviewed, merged) from GitHub's draft,
mergeable, check-rollup and review fields; a completed/total count per epic, which GitHub's
sub-issue progress gives for free; coalescing events within a window before a coordinator run,
which the board's run on every event already approximates; and sandboxed, network-less cards
written by the coordinator to the board branch and rendered by the static panel, never generated
on the site. (Inferred.)

Not to borrow: a wallet of API keys and subscriptions, or any copy of a Claude login onto another
machine; an always-on Manager with a heartbeat, since Symphony has no server and every schedule
is a fallback; a local link table for dependencies, since the graph must come from GitHub so every
account sees one board; an assistant that calls a model from the browser; Conductor's dependency
surface, since the template admits no dependency without an issue. (Inferred from the rules.)

## What not to claim

- Not that Symphony is faster or cheaper than either: no figure of the three is on one scale, and
  Symphony's own latency is unmeasured.
- Not that Conductor or Agentastic cannot coordinate a team: they do not set out to, and a team
  can run either beside a repository; the claim is only that neither holds a shared queue, a
  claim or a merge gate.
- Not that the Mermaid picture matches Conductor's dashboard; it does not, and the companion note
  keeps a canvas of our own as the fallback.
- Not any number from coordbench until the full run is done and the owner lifts the hold.

## Sources

microsoft/conductor at 49af6de (2026-10-15), read from the clone on 2026-10-17: README.md,
pyproject.toml, CHANGELOG.md, AGENTS.md, docs/development (architecture, workflow-engine,
dashboard, providers/claude-agent-sdk), docs/parallel-execution.md, docs/workflow-syntax.md,
docs/fleet.md, docs/dashboard-deep-links.md, docs/telemetry.md, docs/projects (fleet-manager,
web-ui, usability-features), src/conductor/web/server.py, src/conductor/web/frontend/src
(use-websocket.ts, graph-layout.ts, AgentNode.tsx, DetailPanel.tsx, types/events.ts),
src/conductor/engine (pricing.py, usage.py, billing.py), install.sh, the workflows under
.github, and docs/img/web-dashboard.png, viewed. agentastic.dev, read 2026-10-17 by a fetch
tool: /whats-new (113,760 characters, v0.14.0 to v0.10.0), the home page and its FAQ,
/ai-software-factory, /docs/features (manager-agents, kanban, tasks, chat, issue-tracking,
providers), /docs/guides/cloud-agents, /docs/reference/dev-system, /legal/license,
/compare/agentastic-vs-conductor; its privacy page rendered no body to the fetcher. Symphony's
side: this repository at 5d7f60b (docs/agents/PROTOCOL.md, docs/research/control-panel.md,
docs/research/outside-code-bases.md, docs/checkpoints/2026-10-14c/handoff.md, CLAUDE.md) and the
site's assets/js/symphony-panel.js. The reading of the two products was done by parallel
readers of a workflow on 2026-10-17 and condensed here; the strengths, weaknesses and what to
borrow are this note's own.
