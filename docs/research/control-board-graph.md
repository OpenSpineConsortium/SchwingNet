# The control board as a dependency graph

The research notes of the thread "Control panel sign-in", written 2026-10-17 after the owner,
with the sign-in working, asked for the next step of the control panel. Every figure names its
source and the day it was read; what was read by a tool rather than by a person is said so. The
companion note on the two products the owner asked to be compared with is
docs/research/conductor-and-agentastic.md.

## The ask

The owner's words, 2026-10-17, in this order:

- "i want something like this where the controlboard is an interactive depedency graph type
  representation of the repository, with direct passthrough of the progress of each point,
  either the claude session's logging/output/the plan/background tasks, at an internal nitty
  gritty progress state for development workers, and github CI, number of preconditions met
  through teh issue depednency, (meaning what has to be solved before a larger issue is marked
  completed), this should be based around the 'epic' hierarchy, and if there are multiple
  'epics' per repo the board should allow focusing on one epic, where all these dependencies
  are rendered as teh graph, or a more zoomed out view where epics are shown connected to each
  other to reach product goals", with microsoft/conductor's dashboard as the picture to start
  from, and "claude integration INTO THE CONTROL BOARD WEBSITE TO PROVIDE ASSISTANCE FOR
  MANAGING WORKFLOWS, NAVIGATING THE PAGE, ECT".
- "Maybe through native integration of github with linear most of this work can be
  professionally handled? at least for the UI".
- "its not a question of whether i should add linear, i know i want it intgegrated, its how can
  i extend the current current protocol to natively integrate linear without necessarily being
  dependent on it, to increase the power of the protocol, the UI abilities, and anything else
  linear provides".
- "Im not sure I want this to be bespoke code, thats my point, look and see if linear or jira
  offers a native UI representation of what im asking for, any then turn to other thirdparty
  apps that extend the two if not", with https://github.com/shdennlin/issue-graph.

So the question this note answers is not "how to build the graph" but "who already draws it,
and how the protocol feeds whoever draws it without depending on them".

## The answer in short

- Nobody draws it natively for GitHub issues. GitHub holds every datum the ask names, on every
  plan for free (sub-issues for the epic hierarchy, "blocked by" relations for the
  preconditions, issue types for epic and task and goal, a per-parent sub-issue progress count,
  blocked issues filtered in projects and the Issues tab), and draws no graph of them. Linear has no issue-level
  dependency graph at all: relations are flags in a sidebar, and its Timeline draws dependency
  lines only between projects. Jira draws the graph the owner described, a map with arrows,
  dependency lines that turn red, progress rolled up the hierarchy and a level above epic, but
  only on Premium, and every Jira view reads Jira issues, so Symphony's queue would first have
  to be mirrored into Jira by code of ours with a Jira token in a secret.
- The one existing tool shaped like the ask is the owner's link, shdennlin/issue-graph: an
  interactive canvas of blocks edges with epics as containers, sub-issue done/total badges and
  live Claude Code sessions drawn from hooks. It reads Linear only, runs as a self-hosted
  Docker image with no authentication, keeps a Linear API key on its host, and resolves a
  branch to an issue only through a Linear team key, which claude/<N> lacks. It fits as a
  per-person canvas on a person's own laptop, not as a shared server of ours.
- The recommendation, from a judged survey of seven routes (below): make GitHub the truth and
  the always-on picture, and make Linear an optional tier on top. One protocol extension serves
  every tier: the coordinator already opens an epic's tasks as native sub-issues; it gains a
  depends_on list per task written as GitHub's native blocked_by, Pick treats a task with an
  open issue it is blocked by as not free, and the board's run computes "preconditions met k
  of n" and writes
  a Dependencies section as Mermaid into STATE.md and into each epic's body, which GitHub
  renders on every plan with no server, no extension and no credential beyond GITHUB_TOKEN. It
  is a static picture redrawn each run, not a pannable canvas, and it is about a hundred lines
  of the board's own code rather than a UI of ours. Linear then adds, for whoever wants it, a
  polished inbox and mobile app over the same issues through its own one-way GitHub Issues
  Sync, project-level dependency lines on its Timeline, a progress graph per epic, and
  issue-graph on a laptop; none of it is needed for the protocol to run.
- Claude in the board stays as it is: @claude on the repository's own subscription token, and
  each person's own Claude Code session on their own login, with Linear's hosted MCP server on
  that person's own Linear OAuth grant. Every other assistant on offer (Linear's coding
  sessions on prepaid credits, Claude Agent for Jira on an Anthropic API key, a Linear agent of
  ours behind a webhook server) is outside the rules.
- What waits on the owner is a list of choices at the end, with the exact link and what to
  click for each step a choice opens. The protocol change is a symphony-protocol release, so it waits for 0.5.1 to be cut and
  for the owner's approval of its release; nothing in this note changes symphony-protocol.

## What each product draws natively, read 2026-10-17

| What the ask names | GitHub (Free and up) | Linear | Jira Cloud |
|---|---|---|---|
| Epic hierarchy | Sub-issues, 100 per parent, 8 levels, GA 2025-04-09; issue types per organization (25), Free and up | Parent and sub-issues, no stated depth, nested lists since 2026-02-05; projects and initiatives above them (sub-initiatives Enterprise) | Epic, Story, Subtask; a level above Epic (Initiative) is Premium |
| Dependencies between tasks | "Blocked by" and "blocking", GA 2025-08-21, 50 per type, in the sidebar; blocked issues shown in projects and the Issues tab through the filters is:blocked, is:blocking, blocked-by: and blocking: | Relations blocked by, blocks, related, duplicate, as flags in the sidebar; once the blocker is done the relation becomes "Related" | Issue links (blocks, is blocked by) listed in the issue view; a Jira admin turns linking on |
| A graph of tasks | None in any view; the Projects roadmap draws no lines (its layout page names none); Mermaid in Markdown is rendered natively since 2022 | None anywhere ("Individual issues cannot be viewed on the timeline"); project-to-project lines on the Timeline since 2024-08-08 | Dependency lines between dated bars on the basic timeline (Free and up, both items need start and due dates); the Dependencies view, "work items in a map layout with arrows", the Program board and badges or lines on the plan timeline are Premium |
| Preconditions met, k of n | Readable from the API (issueDependenciesSummary: blockedBy against totalBlockedBy; GraphQL), not shown anywhere | Not shown; lists only | Not shown; progress rolls up by resolved children, points or time (Premium plans) |
| Per-node progress | Sub-issue progress field (done of total) in Projects tables; the issue's Development section links its pull request and checks | Project graph (scope, started, completed, predicted finish), milestone percentages, initiative health; nothing on a sub-issue's parent | Progress bar per parent on the timeline; roll-ups in Premium plans |
| An agent's live state | Only what the agent writes: comments, the claude[bot] progress comment, commits, the Actions run log | Agent sessions per issue (states pending, active, awaitingInput, error, complete, stale; thought, action, response, elicitation activities; a plan checklist; an Open button) for an agent that posts through the Agents API | Agents as assignees (GA May 2026, Standard and up with Rovo); updates as comments |
| An assistant in the page | @claude through claude.yml on the repository's own token; Copilot's chat exists on Copilot Free with monthly limits and more on paid plans (not re-read this session) | Linear Agent chat, included in every plan since 2026-03-24; coding sessions on prepaid AI credits (paid plans) | Rovo on credits (Standard and up); Claude Agent for Jira on an Anthropic API key |
| Cost | $0 | Free: 250 issues, 2 teams; Basic $10 per user per month billed yearly; Business $16; Enterprise custom | Free: 10 users; Standard $8.48 per user per month and Premium $15.56 as read on 2026-10-17 (the page renders nothing to the session's tools; secondary pages of 2026 quote $7.91 and $14.54 billed yearly, so the owner confirms on the page) |
| Credential it needs of ours | None beyond the person's login and GITHUB_TOKEN in Actions | Its GitHub App holds the GitHub grant on Linear's side (read and write on code, issues, pull requests, actions and workflows); anything of ours writing to Linear from Actions needs a Linear token as a secret | GitHub for Atlassian holds the GitHub grant on Atlassian's side; a mirror of ours needs a Jira token as a secret |

Sources: GitHub's docs in the github/docs repository (creating-issue-dependencies.md,
adding-sub-issues.md, about-parent-issue-and-sub-issue-progress-fields.md,
customizing-the-roadmap-layout.md, creating-diagrams.md) and its changelog of 2025-08-21;
Linear's docs (issue-property, timeline, project-dependencies, project-graph, initiatives,
parent-and-sub-issues, github, developers/agent-interaction, linear-agent, coding-sessions,
pricing); Atlassian's pricing page, the basic-roadmaps and advanced-roadmaps guides, the
Dependencies report page's description (its body did not render to the fetcher) and the
progress-tracking page. The prices are the day's list prices.

## The third-party tools

shdennlin/issue-graph, read from the clone of 2026-10-14 (commit 9cbbbe5, version 2.0.0 of
2026-10-10, MIT, one author, 99 test files, five ADRs): a Bun and Hono server with SQLite and a
React Flow canvas laid out by dagre. It polls Linear's GraphQL API with a workspace personal API
key kept in its own database (cache 900 seconds by default, a Linear webhook makes it near-live)
and draws six views: dependency (blocks edges, chain isolation), mix (buckets by a label group),
project (Linear projects as containers, cross-project edges highlighted, Linear's own progress and
health in a panel), milestone, design-doc (checkbox progress from OpenSpec or Spectra files under a
server-local path) and workstreams (a stored pipeline of stages). Sub-issues are violet edges on
demand and a done/total badge on every parent card. Its Claude Code plugin (hooks on SessionStart,
UserPromptSubmit, PostToolUse, Notification, Stop and SessionEnd) reports a session's branch,
status and phase to the server, which draws the session on the issue's card as active, waiting or
blocked and forgets it fifteen minutes after the last heartbeat; an eighteen-tool MCP server lets
a session walk the blocks chain, claim the next unblocked member of a workstream and record
progress, writing only issue-graph's own tables. What it cannot show: GitHub issues, labels,
branches or the board (a GitHub backend is an unbuilt "Later, likely" roadmap item), CI checks
(a field declared automatic that nothing fetches yet, so only hand-attached ones appear),
Actions jobs, a session's log. What it costs to run: a Docker host, the
Linear key on that host, an authenticating layer in front (the app ships none and its server
listens on 0.0.0.0; only its Compose file publishes the port on 127.0.0.1), a tunnel for the webhook and the hooks, and a change to its branch resolver, which
finds an issue only through a Linear team key in the branch name.

Other Linear tools: Linear's integration directory lists no roadmap, Gantt or dependency-graph
app (Screenful, $39 to $399 a month, draws charts and sub-issue roll-up tables; Roadmark a
shareable project timeline; Count AI-built analyses). The open-source ones draw static pictures
from a personal API key: aspiers/linear-tools (Graphviz, "quick and dirty hack"),
EndangeredMassa/linear-pert (Mermaid), herval/linear-gantt (Plotly), KSiig/linear-planner
(a Gantt with the key in the browser), a linear-visualize Claude Code skill (Graphviz). Linear
renders Mermaid in text fields since 2025-11-20, so any of them pastes into a Linear document.
Cyrus (Apache-2.0, in Linear's directory) makes Claude Code a Linear agent from a machine of
one's own, on a Claude subscription or an API key, and Linear's own bridge
(linear/claude-managed-agents-demo) runs on an Anthropic API key.

Jira apps, all reading Jira through Atlassian's framework and none reading GitHub: Links
Hierarchy (Kintosoft, 909 installs), Links Explorer (Optimizory, 227), Dependency Map for Jira
(FindOut, 337), Dependency Mapper (Quirk, 273), Structure by Tempo (12,712; dependencies only in
its Advanced edition), BigPicture (10,494; free to 10 users), Easy Agile Programs (707), and
three new ones with one or two installs each. GitHub for Atlassian (free, by Atlassian) shows
branches, commits, pull requests, Actions runs as builds and deployments on a Jira issue when the
Jira key is in the branch, commit or pull request title; it carries no issues, so an issue sync
is a paid connector (Unito, Exalate) or a mirror of ours.

GitHub-side tools: Zenhub (Marketplace app; Free for 2 repositories, 250 issues and 50 users;
Teams $4.99 per user per month yearly) draws dependency lines between epics on its roadmap and
blocked icons on its board from relations of its own, not GitHub's.
maxim-lobanov/build-issue-dependencies-graph (MIT, 8 stars) is an Action that writes a Mermaid
graph into an epic's body from the issues the epic lists, not from native blocked_by (that it
reads task lists and "Depends on:" lines, and has no releases, was read once and not
re-verified; its README confirms the rest). k-nasa/gid (last release 2022) and moul/depviz (2023) predate GitHub's native
dependencies. steveyegge/beads (MIT, 28,000 stars) is a tracker of its own with a dependency
graph and no GitHub Issues sync. The GitHub Marketplace search for "issue dependency graph"
returned nothing. GitHub's own MCP server has an issue_graph tool in an open pull request
(github/github-mcp-server#1511).

## The routes, judged

Seven routes were written out and scored on 2026-10-17, each with what it covers and misses,
its adapter to the protocol, how a worker in Actions, a routine and a cloud session show up, the
assistant, the cost, the hosting, the lock-in and the effort. The scores are a judge's, out of
ten, and the row says why in a few words.

| Route | Score | Why |
|---|---|---|
| 1. Linear's native views alone, over its GitHub Issues Sync | 4 | No graph of tasks; the sync carries sub-issues, labels, status, assignee, comments and priority but not blocks relations or project membership; Free stops at 250 issues |
| 2. Linear plus issue-graph self-hosted | 5 | The closest canvas to the sketch, but a server of ours with no authentication, a Linear key on the host, a fork of its branch resolver, and nothing from GitHub's side (checks, jobs, the board) |
| 3. Linear plus a directory app or an open-source Linear tool | 3 | Static pictures from alpha-grade tools on a personal key, or charts without a graph for $39 to $399 a month; the same picture is drawn from GitHub directly without Linear |
| 4. Jira native (Plans) with GitHub for Atlassian | 4 | The one first-party map with arrows, on Premium, over a mirror of ours with a Jira token in a secret; the largest build for the least native fit |
| 5. Jira plus a Marketplace graph app | 4.5 | A real interactive map on Standard through a Forge app in the tenant, over the same mirror |
| 6. GitHub-native: sub-issues, blocked_by, issue types, Projects v2, Mermaid drawn by the board | 7.5 | Every datum native on every plan for $0; the picture is static, redrawn each board run, and the generator is a hundred lines of the board's own code |
| 7. Route 6 with Linear as an optional one-way mirror and issue-graph as a per-person canvas | 8 | The whole ask on GitHub, Linear as an extension that writes nothing and can be switched off, an interactive canvas for whoever wants one on their own machine |

Route 7 is the recommendation. Two earlier passes of the same question, run before the owner
said "not bespoke code", had recommended a graph page of Symphony's own on the static site,
extending the control panel with GitHub's API as the signed-in person (hierarchy, blocked_by,
preconditions per node, the claim's plan, the draft pull request's checks, the run log for Claude
in Actions, an @claude pane); that route is kept here only as the fallback if the Mermaid picture
proves too plain, since it is the one route that puts a session's log beside its node, and it is
the one the owner set aside.

## The Linear extension of the protocol

The principle: GitHub is the truth and the protocol reads and writes GitHub only, as it does
today. Linear reads GitHub through Linear's own integration, which holds its grant on Linear's
side. Anything of ours that writes to Linear is a step behind a variable and a secret, off by
default, and the core never imports it: an optional module, held out of symphony-protocol's main
until 0.5.1 is cut (the thread that carries the protocol fixes toward 0.5.1 is changing main
now), and a core hook, where one is needed, on a branch of its own. The tiers, each usable without the next:

Tier 0, GitHub-native data, the one change the protocol needs. The coordinator's plan schema
(tools/sdlc_protocol/team.py, plan_schema) gains a depends_on list per task, and open_task, which
already links each task under its epic as a native sub-issue (team.py line 589,
adapters/github.py add_sub_issue), writes each dependency as native blocked_by through POST
/repos/{r}/issues/{n}/dependencies/blocked_by with the body {"issue_id": <the blocker's id>},
which GITHUB_TOKEN under issues: write can call: a workflow on the branch claude/graph-setup
added, read and removed one relation on 2026-10-17 (run 39078408191, #132 blocked by #131),
and DELETE .../dependencies/blocked_by/{issue_id} removes one. GraphQL from Actions was not
probed, only its refusal from a cloud session, 403, and nothing here needs it: every REST
issue object carries issue_dependencies_summary (blocked_by, blocking, total_blocked_by,
total_blocking) and sub_issues_summary (total, completed, percent_completed), read on #127 and
#132 the same day. Pick treats a task with an open issue it is
blocked by as not free: GitHub's relation is a third thing beside the label blocker, which
stops everyone, and the label blocked, a holder waiting on a peer, and the clerk's deal
approximates it today with the blocked label and would now read the relation; that changes the
spec's Pick, so spec/PROTOCOL.md and the validation oracle written from its text change with
it. The board's run reads each open epic's sub_issues (one call per open epic) and the blocked_by
list of each task whose summary says total_blocked_by is above zero (one call each), so the
18 open issues here cost four calls for their four epics and none for edges until a plan
writes one, against GITHUB_TOKEN's 1,000 an hour and the count symphony-protocol#38 measured
for a board run; the board's run keeps no reserve today, the one that skips the metrics
breakdown is tools/metrics.py's own, so the section is skipped by the same accounting once the
board's run has it. It computes preconditions met from the summary alone, total_blocked_by
less blocked_by (the open ones) against total_blocked_by, and writes a Dependencies section to STATE.md: one Mermaid
block per open epic, its tasks as nodes colored by label with "k/n" in the label and blocked_by
as arrows, and one block of goals to epics, where a goal is an issue labelled goal, a new label
beside epic, that the epics are sub-issues of; the board keys on labels, as the protocol does
(labels.py EPIC), because issue types exist only on an organization and a copy on a personal
account has none, and two spellings of one fact would need a rule for their disagreement. The
same per-epic block goes into a marked section of the epic's body through the library's own
body writer (team.py's plan_section between its PLAN_MARKER, written by Client.set_body in
adapters/github.py), with one read-modify-write rule for the two writers of one body, the plan
and the graph, so the epic's own page carries its graph. Issue types Goal, Epic and Task, where
the copy is an organization's, are display only, made once at the organization and never read
by the board. All of it is GitHub's data, so Linear's sync carries the hierarchy, GitHub's
Projects show the progress
and the blocked filters, and any later tool (Linear, issue-graph once it has its GitHub backend, the
MCP server's issue_graph tool) reads the same edges.

Tier 1, Linear as a read view, the owner's clicks and no code. A Linear workspace admin who is a
GitHub organization owner installs Linear's GitHub App and turns on GitHub Issues Sync one-way
from the repository to a team, so Linear can never write a protocol label or close a GitHub
issue; two-way sync, one repository per team, is what Linear's own docs call a transition tool.
Within seconds each new issue is in Linear with its title, body, status, assignee, labels
(worker:<name>, todo, claimed, in-review, epic, blocked arrive as Linear labels), sub-issues,
comments and priority. The claim comment with its plan and the "finished; ready to mark" comment
arrive as comments. What the sync does not carry: blocks relations, project membership, the
claim branch, the board, checks. A pull request shows on the Linear issue only when its body or
branch carries the Linear identifier; whether the sync writes that identifier into the GitHub
issue was not verified, so the claim skill would copy a "Linear: KEY-N" line from the issue body
into the pull request body when the line is there, and nothing when it is not.

Tier 2, the mirror step, the owner's choice because it puts a Linear credential in the
repository. With a repository variable SYMPHONY_LINEAR=on and a secret LINEAR_API_KEY (a Linear
personal API key, Settings > Account > Security & Access, restricted to read and write on the one
team), the board's run also mirrors each epic as a Linear project, each blocked_by edge as a
Linear "blocks" relation, and writes the "Linear: KEY-N" line into each issue body, reading the
mapping from the synced Linear issue's GitHub attachment. Without the secret the step does
nothing. This is a Linear credential, not a Claude one, and the rules the owner set name API
keys for models; it is still a credential in a secret, so it is listed as a choice and not taken
by default. With it, Linear's Timeline draws the epic-to-epic lines and issue-graph draws the
arrows; without it, both show hierarchy, status and comments only.

Tier 3, a canvas per person. A person who wants the interactive graph runs issue-graph from its
README on their own laptop against their own Linear key, with no server of ours, no tunnel and
nothing in the repository; their own Claude Code sessions appear on it if they install its plugin
with the local address and a branch rule for claude/<N>. Workers in Actions reach no laptop, so
their presence shows through GitHub's labels and pull requests, as it does today.

Sessions and Linear's API. A person's own Claude Code session reads and writes Linear through
Linear's hosted MCP server (claude mcp add --transport http linear-server
https://mcp.linear.app/mcp) on that person's own OAuth grant, kept in the client's own store;
nothing enters the repository. The claim skill may, where that server is present, set the Linear
relation that mirrors a new blocked_by, which gives tier 2's arrows for that claim without the
secret. A headless run in Actions cannot complete that OAuth, so from Actions only tier 2's key
writes.

What Linear adds to the protocol's power beyond the UI, and what it would cost: (a) agent
sessions, the live pane with states, activities and a plan checklist, which is the closest thing
to the "nitty gritty progress state" the ask names; an agent reaches it as a Linear OAuth
application with actor=app, installed by a workspace admin, and Linear's docs assume a webhook
endpoint of the agent's that answers within 5 seconds, a server of ours; whether a worker in
Actions could instead open its own session by mutation (agentSessionCreateOnIssue exists) and
post activities on a client-credentials app token valid 30 days, with no webhook, is untested;
(b) Loops and Linear Agent automations over the synced issues (Business and up by the changelog
and the pricing cards, Basic and up by the AI credits page; Linear's own pages disagree), which
cannot be triggered by GitHub events; (c) Linear's coding sessions, Claude Code in Linear's cloud on
prepaid AI credits at provider token rates, which the house rules exclude. Of these, only (a) is
worth a test, after 0.5.1, and only if the owner wants an OAuth client secret of a Linear app in
a repository secret.

What stays out: Linear's coding sessions and AI credits; a Linear agent behind a webhook server;
the Claude Managed Agents bridge (ANTHROPIC_API_KEY); Cyrus and Merlin as the way to run Claude
Code; issue-graph as a shared host; Jira, unless a team already lives there (its native map is
Premium per user, its agent needs an Anthropic API key, and its issue sync is a build of ours);
Zenhub, which keeps relations of its own and would have every dependency entered twice.

Where the code goes and when. Tier 0 is a symphony-protocol change (team.py, adapters/github.py,
board.py, the clerk's Pick, spec/PROTOCOL.md and the validation oracle, and their tests) and a
release the owner approves; it waits until 0.5.1 is cut, as the project's channel session asked,
and is then one pull request there by whichever thread holds the protocol work. The template's
parts (docs/setup/github.md for the issue types and the Projects v2 project, docs/setup/linear.md
for tiers 1 to 3, the claim skill's optional "Linear:" line, and the fixture
tests/fixtures/board-STATE.md once the board draws the section) are template pull requests that
need no release. Tier 2's mirror step is an optional module, tools/linear.py
or an optional package of the library that nothing in the core imports, run as a step of
board.yml behind the variable; it is not written until the owner chooses it.

## Claude in the board

The rule that decides it: the only Claude a repository may run is Claude Code in GitHub Actions
on the repository's CLAUDE_CODE_OAUTH_TOKEN, and a person's own Claude on the person's own plan.
So an assistant in the page is a GitHub event the signed-in person raises from the browser, a
run of anthropics/claude-code-action in the repository, and an answer written where the page can
read it back through api.github.com. Four designs were worked out on 2026-10-17 against the
action's own source and docs:

- A, the assistant issue, recommended: the page opens once per repository and person an issue
  "Assistant: <login>" labelled assistant, whose body describes the page and a small command
  vocabulary; each question is a comment "@claude ..." with a visible fenced block of the page's
  state (repository, focus, filter, section), posted as the person, who is signed in with write
  access (claude.yml's condition guards nothing but the "@claude" text; the action itself
  answers only actors with write access: checkActorWritePermissions in
  src/github/validation/permissions.ts of anthropics/claude-code-action, read on its main at
  f27be6b65a4652f08a2ba3cff79114829b588967 on 2026-10-17, passes an actor whose collaborator
  permission is admin or write, and any login ending in [bot], which the action's human check
  (checkHumanActor in src/github/validation/actor.ts) then refuses unless allowed_bots names
  it, both before any comment is posted, and fails the run for anyone else), which
  claude.yml answers on the repository's own token with the action's own progress comment ("Claude Code is working...",
  edited with checkboxes and then the answer); the page polls the issue's comments with
  If-None-Match every 5 seconds for ten minutes and then every 30 seconds (a 304 costs nothing
  against the 5,000 requests an hour), renders claude[bot]'s comment, and executes only a
  read-only vocabulary from a fenced block in the reply (focus an epic, open a pull request,
  filter to blocked, show a board section), showing anything that writes as a button the person
  presses. The issue's body keeps the text "@claude" out of its vocabulary, since claude.yml
  also runs when an issue opens. claude.yml gives the assistant label a turn cap of ten, a
  read-only tool list and an appended system prompt from the file
  .github/symphony/assistant.md. This extends the Ask Claude
  box the panel already has (symphony-panel.js posts @claude comments and issues as the person
  today and does not yet poll for the answer). The template's side is built (claude.yml,
  .github/symphony/assistant.md, docs/setup/claude-action.md, 2026-10-17, symphony-template#165),
  and so is the page's side (the Assistant section of /symphony/control/, 2026-10-18,
  openspineconsortium.github.io#28): it offers the box only where GitHub says the person may write
  and the default branch carries .github/symphony/assistant.md, opens the issue once per repository
  and person on a press and keeps its number in the browser, posts each question as a comment with a
  fenced symphony-state block, reads the issue's comments with If-None-Match until the action's
  "Claude finished" or "Claude encountered an error" header opens the comment (the phrase "Claude
  Code is working" is gone from the comment at Claude's first edit, so it is no sign of anything),
  renders the answer through the board's renderer with off-GitHub links shown as text, and acts on
  the symphony block's five forms. Twenty browser checks against a mocked GitHub are symphony-app's
  signin/panel-checks/e2e2/assistant.test.mjs (symphony-app#18), and the Apps' privacy statement
  version 11 (symphony-start#47) lists the issue, the comments as questions, the reads while waiting
  and the kept number, before the page went live.
- B, a dispatch: an assistant.yml on workflow_dispatch with a question input, the action in
  agent mode with --json-schema, and a step posting the structured output as a check run named
  assistant on the default branch's head (up to 65,535 characters, readable with a plain GET)
  or as an issue comment; needs Actions: read and write on the person's token, has no progress
  comment, prints the question in the run log, and the page must find its run by actor and time
  since the dispatch call returns no run id. The follow-up for a repository that wants no
  assistant issues.
- C, the person's own Claude: the panel is already written so a browsing agent reads and drives
  it (every state a sentence, every action a named button), so Claude in Chrome or a claude.ai
  session the person opens navigates and explains it on the person's own plan; nothing of ours
  sees anything, and there is nothing to build but an "open with your Claude" line and a prompt
  to paste. The page cannot start such a session or show its answer.
- D, out: an Anthropic key in the browser or in the sign-in Worker, an Agent SDK or MCP service
  of ours in the Worker, Copilot's agents, and a GitHub Discussion channel, which the action
  does not trigger on.

The two bounds of A and B: an answer is an Actions run, tens of seconds to minutes (no latency
figure is measured anywhere in the project; the readiness research of 2026-10-14 says so), and
every run would count against the cap of at most 10 Claude runs a day per repository, decided
on 2026-10-13 and not built yet (no workflow reads such a variable), so today nothing caps
them. Two people at once are two runs on the same five-hour window, since
claude.yml sets no concurrency group. On a public repository the assistant issue and the run log
are public.

In Linear, Linear Agent chat (included in every plan) answers over the synced issues and knows
Linear, not Symphony; it cannot read the board, dispatch workers.yml or label an issue the
protocol's way. Linear's hosted MCP server from a person's session (above) is the way a session
reaches Linear.

## What was not measured or not verified

- Whether GitHub honors Mermaid "click" links to issues in a rendered diagram (GitHub sanitizes
  rendered diagrams); if not, the node label carries the number and the board's row carries the
  link. An SVG committed to the branch board and shown from STATE.md is the alternative, common
  practice but not re-verified against a docs page.
- Whether Linear's GitHub Issues Sync writes the Linear identifier into the GitHub issue, and
  whether a pull request that closes a synced GitHub issue appears on the Linear issue without
  the identifier.
- Whether a worker in Actions can drive Linear's agent session pane with no webhook server.
- The latency of a claude.yml run from the comment to the first edit and to the answer.
- Whether GraphQL answers from Actions: only its refusal from a cloud session was seen, and
  nothing in the plan needs it, since REST's issue objects carry both summaries (the write of
  blocked_by from a workflow was verified on 2026-10-17, above).
- Whether the maintain role passes claude-code-action's write check, now read from its source
  (Claude in the board, above): checkActorWritePermissions compares the legacy permission
  field of the collaborator permission endpoint with admin and write, and that GitHub reports
  maintain there as write, and triage as read, is from memory, not from a docs page read in
  this session.
- The form of Linear's settings links (linear.app/<workspace>/settings/...): the page refuses
  the proxy, so the link in the owner's steps is given with the slug to fill in.
- Linear's per-plan check marks did not survive the pricing page's text extraction (the page
  refuses curl through the session's proxy); which plans carry Issue sync and Initiatives is read
  from the plan cards, and the owner should confirm on https://linear.app/pricing.
- The Jira Marketplace apps' per-user prices are on a tab rendered by JavaScript and the
  Marketplace API answers 403 through the proxy; they need a browser.
- GitHub's GraphQL is refused from a cloud session (403, 2026-10-17: "GitHub GraphQL is not
  available from Claude Code sessions; use the REST API"), so issueDependenciesSummary was not
  probed live; REST's blocked_by and sub_issues were, and a relates_to endpoint, which a reader
  reported and neither the docs, the August 2026 changelog listing nor the REST description
  names, answered 404 on symphony-template#1, so only blocked_by and blocking exist.
- Read once by a reader of the survey and not re-read: the Atlassian Marketplace install counts
  of the graph apps, Jira's issue-type hierarchy page and the basic timeline's rule that both
  items need dates, github/github-mcp-server#1511, Conductor's GitHub releases list, and the
  release dates of gid and depviz; github.com's own pages answer 403 through the proxy.

## The owner's choices

Each is a yes or no; the recommendation is marked. Nothing below is started until the owner
answers, except the writing of docs/setup pages, which is harmless.

The owner answered on 2026-10-17: 1 yes, the Mermaid section; 2 yes; 3 open, asking what Linear
would buy beyond its Slack integration; 4, 5 and 9 depend on 3; 6 not settled, but nobody is to be
asked to host a session of their own, so the middle way is the panel's own graph page, drawn in the
browser from GitHub's sub-issues and blocked-by as the signed-in person, which nobody hosts; 7 no to
both; 8 A. What Linear buys beyond Slack is its own views (cycles, projects, a list and a board
over the synced issues) and Linear Agent chat over them; the Slack part alone GitHub's own Slack
app gives without Linear (https://github.com/integrations/slack#readme: a channel subscribes to a
repository's issues, pull requests, commits, releases, deployments, workflow runs, reviews,
comments, branches and discussions, opens an issue with /github open, comments and closes from
the card, and reminds about open pull requests on a schedule; its price is not stated there). So
the recommendation stands at no Linear for now. What follows: choice 1 is a draft pull request in
symphony-protocol held until 0.5.1 is cut, choice 2 is docs/setup/github.md's section 9, choice 8
is one template pull request (claude.yml and .github/symphony/assistant.md) and one site pull
request (the panel's section), and choice 6 comes after 8 as the panel's graph page.

1. The protocol extension (tier 0): depends_on in the coordinator's plan written as native
   blocked_by, Pick reading open blockers, the board's Dependencies section as Mermaid with
   k of n, the epic's marked section. Recommended yes. It is a symphony-protocol release after
   0.5.1 and waits for the owner's click in the environment release, as every release does:
   the run's page under https://github.com/OpenSpineConsortium/symphony-protocol/actions,
   "Review deployments", tick release, "Approve and deploy".
2. Issue types and a Projects v2 project, free, the owner's clicks (steps below). Recommended
   yes: GitHub then shows the hierarchy, the sub-issue progress and the blocked filters today,
   before any release.
3. Linear at all, and on which plan: Free stops at 250 issues and 2 teams (symphony-template
   has 27 issues in all, open and closed, though its numbers run to 148, since pull requests
   share the numbering; each adopted repository would be a team), Basic is $10 per user per month
   billed yearly, Business $16. Recommended: yes on Free for a look, one-way sync only, so
   GitHub stays the truth and Linear writes nothing.
4. Whether Linear's GitHub App may hold read and write on code, issues, pull requests, actions
   and workflows for the organization, which its sync requires, one Linear workspace per
   organization; an organization owner's install. Needed for 3.
5. Whether a Linear personal API key may sit in a repository secret (LINEAR_API_KEY, one team,
   read and write, at https://github.com/OpenSpineConsortium/symphony-template/settings/secrets/actions,
   with the variable SYMPHONY_LINEAR at
   https://github.com/OpenSpineConsortium/symphony-template/settings/variables/actions) so the
   board's run mirrors epics as projects and blocked_by as Linear blocks relations (tier 2).
   Recommended: not yet; without it Linear shows hierarchy, status and
   comments, and the arrows come from a person's session through Linear's MCP server.
6. issue-graph as a per-person canvas on each person's own laptop (recommended; its README at
   https://github.com/shdennlin/issue-graph#readme, the Docker line under Quick Start) or as a
   shared host of the owner's, which means a Docker host, an authenticating layer in front of an app
   with none, the Linear key on that host and a fork of its branch resolver.
7. Jira (https://www.atlassian.com/software/jira/pricing, the Dependencies map on Premium):
   recommended no. Zenhub (https://www.zenhub.com/pricing): recommended no.
8. The assistant: design A (the assistant issue through claude.yml,
   https://github.com/OpenSpineConsortium/symphony-template/blob/main/.github/workflows/claude.yml,
   a template pull request of ours) with C beside it (recommended), or B (a dispatch per
   question), or none.
9. Linear's agent session pane for workers in Actions, which needs a Linear OAuth client secret
   in a repository secret (an application made at
   https://linear.app/<workspace>/settings/api, "Create new" under OAuth applications) and a
   test that it works without a webhook: recommended not yet.

The owner's steps, if 2 and 3 are yes:

1. Issue types: open https://github.com/organizations/OpenSpineConsortium/settings/issue-types,
   press "Create new type" three times, for Goal, Epic and Task, each with a one-line
   description, and leave the defaults (Task, Bug, Feature) as they are.
2. The project: open https://github.com/orgs/OpenSpineConsortium/projects/new, choose Table,
   name it Symphony, press Create; in the table's header press + and under Hidden fields turn on
   Parent issue and Sub-issue progress; in the project's menu choose Workflows and turn on
   "Item closed" to Done and "Pull request merged" to Done; add the repository's issues with
   "Add item" or the Auto-add workflow (one on Free).
3. Linear: in Linear open Settings > Integrations > GitHub
   (https://linear.app/<workspace>/settings/integrations/github, with the workspace's own slug
   in place of <workspace>; the form is not verified, since the page refuses the proxy), press
   Enable, choose the OpenSpineConsortium organization and the repositories, and in the
   same page turn on "GitHub Issues Sync" one-way from each repository to the team; then open
   https://linear.app/pricing and confirm Issue sync is on the Free card.

## Sources and dates

Read 2026-10-17 unless said otherwise. GitHub: the github/docs repository's content files on
raw.githubusercontent.com (the pages named above, the GraphQL schema, the REST index for issue
dependencies, projects and sub-issues), github.blog's changelog of 2025-04-09, 2025-08-21,
2025-09-11 and 2026-06-10 (a reader's entry of 2026-08-20 was not found again), github.com/pricing; probes of this session's token
against OpenSpineConsortium/symphony-template (REST sub_issues and dependencies/blocked_by answer,
GraphQL 403). Linear: linear.app/docs (github, github-to-linear, issue-property, timeline,
project-dependencies, project-graph, project-milestones, initiatives, sub-initiatives,
parent-and-sub-issues, insights, dashboards, mcp, agents, coding-sessions, ai-credits, loops,
linear-agent, api-and-webhooks, billing-and-plans), linear.app/developers (agents,
agent-interaction, aig, oauth-2-0-authentication), linear.app/changelog (2023-12-14, 2024-08-08,
2025-05-20, 2025-07-30, 2025-11-20, 2026-02-05, 2026-02-26, 2026-03-24, 2026-05-27, 2026-06-11,
2026-08-20, 2026-10-08), linear.app/pricing, linear.app/integrations and its agents category,
anthropics/claude-code#12925, linear/claude-managed-agents-demo, ceedaragents/cyrus,
screenful.com/pricing. Jira: atlassian.com/software/jira/pricing, the basic-roadmaps and
advanced-roadmaps guides, learning.atlassian.com's Jira Plans dependencies lesson,
support.atlassian.com (configure-issue-linking, configure-the-issue-type-hierarchy, the
Dependencies report's description), confluence.atlassian.com's progress-tracking page,
atlassian.com/licensing/rovo, the Atlassian community's "Introducing Agents in Jira",
marketplace.atlassian.com listings (github-for-atlassian, claude-agent-for-jira, the graph apps
named above), tempo.io and appfire.com pricing. Tools: the clone of shdennlin/issue-graph at
9cbbbe5 (README, ROADMAP, CHANGELOG, ADRs, src/backend, src/frontend/views,
integrations/claude-code), the GitHub pages of maxim-lobanov/build-issue-dependencies-graph,
k-nasa/gid, moul/depviz, steveyegge/beads, markitx/issue-graph, zenhub.com/pricing and Zenhub's
help on dependencies, github/github-mcp-server#1511. The assistant: anthropics/claude-code-action
(src/modes/detector.ts, src/github/context.ts, src/entrypoints/prepare.ts, src/create-prompt,
action.yml, docs/usage.md, docs/custom-automations.md, docs/security.md, docs/faq.md),
code.claude.com/docs/en/github-actions.md, this repository's .github/workflows/claude.yml and
coordinator.yml, the site's assets/js/symphony-panel.js, docs/checkpoints/2026-10-14c/handoff.md.
The survey and the judging were run as workflows of parallel readers on 2026-10-17; their
outputs were not kept beyond the session, their findings are condensed here, and each fact
above names the page it came from.
