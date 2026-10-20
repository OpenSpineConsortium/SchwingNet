# Symphony compared by domain, and its use cases

Source: the thread "Symphony compared and use cases" in the project symphony2, 2026-10-18,
for the owner's message of 05:08 UTC that day: "the generic powers of the symphony protocol
should be visually compared to the competitors that others may be familiar with in all domains
it can compete" and "some people will fail to understand what this can be used for without
examples/case studies/use cases". The answer is two pages of the site,
https://openspineconsortium.com/symphony/compare.html and
https://openspineconsortium.com/symphony/use-cases.html, built in
OpenSpineConsortium/openspineconsortium.github.io (tools/pages/symphony/compare/ and
use-cases/, styled by assets/css/compare.css). This note records what they claim, why, and
what they may not claim. The coding-agent comparison it rests on is
symphony-versus-competitors.md beside this file, which stays the reference for that domain.

## The general powers

symphony-versus-competitors.md compares Symphony with coding-agent coordinators only. The
owner asked for the protocol's general powers, so the page names six, each a plain restatement
of a rule in docs/agents/PROTOCOL.md that holds for any work that splits into tasks whose
results are files:

1. One taker per task: the claim is the first push of the task's branch (Claim).
2. Stalled work comes back: a claim idle for a day is released and its branch renamed (Release).
3. Overlaps are seen early: claims list their files and the board orders work that meets (Overlaps).
4. Nothing lands unchecked: work lands by pull request through the required check (Finish).
5. No server, flat price: the bookkeeping is Actions jobs with no model call, the AI work a
   Claude plan's subscription token (symphony-versus-competitors.md, claim 2).
6. The record is the work: issues, branches and commits are the state (PROTOCOL.md, opening).

## The seven domains and the familiar tools in each

| Domain | Columns | Where Symphony stands |
| --- | --- | --- |
| Coding agents working together | Copilot coding agent, Claude Code agent teams, GitHub Agentic Workflows, Codex cloud and Devin | The competitors note's domain; the cells condense its tables |
| Tracking a team's work | Jira, Linear, Trello, Asana, GitHub Projects | Complements: the claim, the idle release and the overlaps, with none of their planning screens |
| Automating work across tools | Zapier, Make, n8n, GitHub Actions alone | Complements: the claim and the gate, with one connector, GitHub |
| Revising documents from comments | Word by hand, Google Docs with Gemini, Microsoft 365 Copilot, Overleaf | tools/docx_review.py: one task per document, edits as tracked changes with a reason; early |
| Running a job on a university cluster | ssh and sbatch, Open OnDemand, a self-hosted runner, Globus Compute | The grid runner chain and its ssh gate; early, one cluster; Slurm still schedules |
| Opening a project to volunteers | BOINC, Zooniverse, good first issues, unsorry | Crowd mode; built, no crowd yet |
| Building a team of agents in code | LangGraph, CrewAI, Microsoft Agent Framework, OpenAI Agents SDK | A level up: a worker may be built with any of them |

Each grid gives every cell a mark (yes, partly or only if you build it, no) with a short note,
and ends with "Where they are ahead", so the page says first what a reader who knows the tool
would say. The marks have their own shapes as well as colours, and the grids scroll inside
their box on a phone with the row label held in view.

## What the pages may not claim

The pages keep the rules of symphony-versus-competitors.md (What not to claim) and the
project's holds:

- A comparison of designs, not of results: no coordbench or flowbench number, and no
  speed-up claimed, until the owner lifts the hold of 2026-10-15.
- Each tool's column is read from its own public documents as of October 2026; the page
  says so and asks readers to report a wrong cell. The cells about tools outside the
  competitors note (the trackers, the automation tools, the document tools, the cluster
  tools, BOINC and Zooniverse, the frameworks) are general knowledge checked by an
  adversarial review in this thread, not read at a pinned source, so they are graded
  Reported in the competitors note's sense and are worded at the level of "built in" or
  "if you build it", never a feature count.
- Nothing of the grant and nothing of Beethoven beyond its public pages: the cluster case
  names no university and describes the runner chain only as the template's memory does.
- Status labels on the use cases follow what is merged: works today for the claim, teams,
  workers in Actions, epics and the control panel; early for document revisions (not yet
  proven on a file saved by Word), the Drive and OneDrive sync (tools/drive_sync.py is
  merged; its one sign-in waits on the owner's one-time setup, drive-sync.md), the cluster
  runner (one cluster), crowd mode (no crowd yet) and the account pool (the page's Add box
  waits on a one-time permission). The pool is told as one person's own accounts, never
  shared between people, as the decisions on credentials require.
- The gate is told as it is: work lands through the required check, and the owner merges
  unless a worker is set to auto-merge, so no grid says every change is reviewed.

## Shaped by the owner's four strengths

The owner's message of 05:24 UTC named what the GitHub, Claude Code and Chrome system is good
for: trackable history, shareability, visualization and extensibility. The comparison page
gives them their own band under the six powers, "Why it lives in GitHub, Claude Code and
Chrome". The template for Claude Cowork projects he mentioned is a future goal, not this work.

## The adversarial review

One review pass on 2026-10-18 found, and the pages now fix: the review row overclaimed (an
auto-merge worker lands with no review); the cluster grid called the runner chain
disconnected between jobs and set Symphony against self-hosted runners, which it uses; the
Drive sync was labelled planned though built; the pool was offered to a lab; volunteers
claim only once invited; the trackers all have free tiers; Zapier has a built-in approval
step and Make prices in credits; Codex and Devin can be started by integrations; "after a
day" hid the board's six-hour fallback; the flat plan has five-hour and weekly limits. It
found no leak of grant material, benchmark numbers, Beethoven internals or credentials.

## The case study

"Symphony builds Symphony" tells how this project's own repositories are built, one thread per
piece of work, one branch and one pull request each, merged once green, one owner per shared
file, in words only. It claims that the way of working holds up on real work and says plainly
that it does not show a measured speed-up.

## Open

- The site's navigation thread owns the header and the self-updating docs section; these
  two pages are in SITE under Symphony and are linked from /symphony/.
- The Claude Doc of the competitors note still waits for the owner to share it with this
  account; this note and the pages do not depend on it.
- A cell found wrong is fixed in tools/pages/symphony/compare/body.html, and the domain's
  line above changes with it.
