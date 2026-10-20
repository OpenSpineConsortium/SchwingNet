# Beethoven's worker and Claude projects

The notes of the thread "Beethoven worker opening", written 2026-10-16: what was learned about
how Beethoven's worker on the Wayne State grid meets a Claude project on claude.ai, for item 9 of
the list the owner gave the project chat on 2026-10-15 ("My Beethoven extension fucking opens a
worker in claude code but projects can only be opened in", finished in the thread at 00:28 UTC
on 2026-10-16: "no think what i need to do is have a cloud-enabled claude code session running
based on the grid which has all the features of desktop like projects beta, cloud sessions, and
access tot eh lcoal resources of the grid, so it can develop and test on teh local hardware all
from one session of beethoven"). The fix is Beethoven 21.0.0, pull request
https://github.com/OpenSpineConsortium/beethoven-extension/pull/17; this file keeps the research
behind it, so it accumulates here as the owner asked. Every claim names where it was read; what
was not measured says so.

## The answer

A Claude project cannot take a session the worker started by itself. The worker's link, which
Beethoven opened when the worker came online and on *Open my session*, is a plain Claude Code
session at claude.ai/code. A project reaches a machine only the other way round: the student
asks for the task inside the project (*Work locally* from the + menu beside the message box),
and Claude answers with a card, "Allow Claude to work in a folder on your device", whose *Allow
once* starts that thread on the machine where `claude remote-control` is running
(code.claude.com/docs/en/claude-projects, "Run a thread on your own computer", read 2026-10-16).
So Beethoven now opens the project's page instead and tells the student those three steps; the
worker itself needs no change for that. The project's thread then runs on the compute node, in
the worker's folder, with the grid's tools and hardware: the "develop and test on the local
hardware" part of the owner's goal is what *Work locally* does.

## What the worker is today

From OpenSpineConsortium/hpcworker (framework 18, `framework/jobs/worker.sbatch.tpl`), read on
2026-10-16:

- The worker is a Slurm job that runs `claude remote-control` under tmux inside the lab's
  Apptainer image, which `framework/jobs/build_image.sbatch` pins to one exact Claude Code
  version, 2.1.283 in the README's example. It passes `--name`, `--capacity` and
  `--permission-mode` (`RC_ARGS`); `--spawn` is not passed.
- Before its wall time ends it queues one successor with `sbatch --dependency=afterany`. The
  successor resumes the previous session with `--continue` when `connection.json` is younger
  than the resume window (`RESUME_WINDOW_S`, four hours unless the profile says otherwise,
  `framework/lib/profile.py`), tried once per job; otherwise it registers afresh in the same
  environment.
- Claude Code 2.1.283 refuses `--continue` together with `--spawn`, `--capacity` or
  `--create-session-in-dir` ("--session-id and --continue cannot be used with --spawn,
  --capacity, or --create-session-in-dir", job 40501175, 2026-09-29, quoted in the template), so
  a resume drops `--capacity`.
- The worker writes `status.json` and `connection.json`; the extension reads them through the
  portal and shows the link `connection.json` carries (`environment_url`, the
  `https://claude.ai/code?environment=env_...` form, or since 14.0.0 a resumed session's own
  `https://claude.ai/code/session_...`).

## What claude.ai's documentation says about projects

code.claude.com/docs/en/claude-projects, read 2026-10-16 (the page may change; the labels below
are quoted from it):

- Projects are in beta, on Pro and Max. A project's threads run in Anthropic's cloud unless the
  student runs one on their own computer.
- "Run a thread on your own computer": Claude Code 2.1.280 or later runs `claude remote-control`
  in the folder (the page suggests `--spawn worktree` for a git repository, so each thread gets
  its own worktree); in the project the student chooses *Work locally* from the + menu, which
  tags the message Local; the card "Allow Claude to work in a folder on your device" appears,
  with a Worktree toggle for a git folder; *Allow once* starts the thread there. The thread runs
  in auto mode when that is available.
- The thread pauses while the computer sleeps and stops when `remote-control` quits: the project
  says "Lost contact with your folder", and the way back is to run `remote-control` again in the
  same folder. A Claude Code older than 2.1.280 gives "Claude is out of date on your device".
- A thread cannot run on a device while the organization's "Require trusted devices" is on.
- A session the device started by itself (the worker's link) cannot be added to a project.

The worker's 2.1.283 is above the 2.1.280 minimum, so a project's thread can run on it as the
image stands.

## The owner's goal, feature by feature

- Projects on the grid: yes, through *Work locally*. The project is opened in the browser, the
  work runs on the node. Beethoven's part is to open the right page and say the three steps.
- Cloud sessions: a project's other threads run in Anthropic's cloud containers, not on the grid,
  and reach no grid hardware, file or private repository (a private repository there needs the
  student's own token, which Claude never handles). The project holds both kinds of thread side
  by side; the grid runs the Local ones.
- The settings line "Browser use: Not available in cloud Code sessions, which don't run on this
  computer" (the owner, 00:29 UTC) concerns cloud sessions' use of the browser and has nothing to
  do with the worker; answered so in the thread.
- "All from one session of Beethoven": Beethoven starts and keeps the one worker; the project's
  Local threads come and go on it, each allowed once on its card.

## What Beethoven 21.0.0 changes

Pull request 17 on OpenSpineConsortium/beethoven-extension, merged 2026-10-16 at 09:24 UTC as
87e06c8: Settings takes the project's address (a card *Your project on claude.ai*; a thread's
address is reduced to the project's, a session's or environment link is refused with a sentence
saying what to paste, *Clear* forgets it); with one named, the panel's button is *Open my
project*, on the home and on the "You're online." moment, with "In your project, choose Work
locally from the + menu, write the task, and press Allow once on the card." under it; the tab
Beethoven opens when a worker the student started comes online is the project's page, while that
switch is on, or the project's tab Beethoven opened earlier brought forward, never a second one;
*New session*, *Copy link* and *Phone* keep the worker's own link, and a worker online on a
resumed session's own link keeps an outline *Open my session*; the worker's link and the project's
page each keep a claude.ai tab of their own; a one-time card points at Settings while no project
is named. The address is new browser data and a new kind of page Beethoven opens, so the privacy
statement is version 16 and the agreement version 15, accepted once more. The pull request's
description records the checks; the two adversarial review rounds, finding by finding, and the fit
measurement at the panel's smallest sizes, with its script, are in beethoven-21-reviews.md beside
this file.

## Where it stands, 2026-10-16 at 19:15 UTC

- The website's terms.html and privacy.html, which the site's build renders from the extension's
  LICENSE.txt and PRIVACY.md, show versions 15 and 16 since that morning, and support.html has a
  paragraph on projects (OpenSpineConsortium/openspineconsortium.github.io pull request 21, merge
  07200e6). The site's build needs beethoven-extension, beethoven-vscode, symphony-extension and
  symphony-start cloned beside it.
- The five Chrome Web Store secrets were set on beethoven-extension that day, and a run of
  release.yml started by hand at 18:49 UTC, with upload ticked and publish not, put 21.0.0.108
  (the extension's version and the repository's commit count) in the store as the item's draft.
  It was not yet submitted for review. Submitting it is the owner's: in the store's dashboard
  (https://chrome.google.com/webstore/devconsole, the item, then Submit for review), or by running
  release.yml with upload and publish ticked
  (https://github.com/OpenSpineConsortium/beethoven-extension/actions/workflows/release.yml).
- Whether the repository variable `CWS_ON_PUSH` is set cannot be read from a cloud session. Once it
  says upload, every merge to beethoven-extension's main uploads a new draft; once it says
  publish, every merge is submitted for review, a release to students once Google approves it.

## Not yet measured, and the choices left

- When the Slurm job ends, `remote-control` ends with it and the project says "Lost contact with
  your folder". Whether the successor job's `--continue`, within the four-hour window, brings
  the project's thread back by itself, or the student must ask again with *Work locally*, is not
  yet measured on the grid. A preempted job (the requeue QoS) ends the contact the same way; a
  compute node does not sleep, so the page's sleep rule does not apply.
- `--spawn worktree` would give each of a project's Local threads its own worktree of a git
  folder, but hpcworker does not pass `--spawn`, and 2.1.283 refuses it together with
  `--continue`: the chain's resume and the worktrees cannot both be had on that version. That is
  a choice for hpcworker (pass `--spawn worktree` and register afresh each job, or keep the
  resume), and a follow-up, not part of 21.0.0. A folder that is no git repository has no
  worktree either way.
- Whether the card lets the student pick any folder or only the one `remote-control` was started
  in (the worker's workspace) is not yet measured; the page describes the latter.
- Whether opening a thread inside the project counts as a new load of the tab in Chrome
  (`tabs.onUpdated` "loading") is not yet measured; it decides whether *Open my project* brings
  the project's tab forward or opens another, by the same rule the session's tab has followed
  since 14.0.0.
- Neither adversarial review tried the premise itself, a project refusing the worker's session
  and *Work locally* offering the worker's folder: both rest on the owner's report and the
  documentation page (beethoven-21-reviews.md, What neither round verified), and a first
  project's thread run through *Work locally* on the grid would measure it.
- The owner's account is on Max (the login measured on 2026-09-28), so the projects beta and
  *Work locally* are expected to be there; whether "Require trusted devices" is on for any
  organization of the owner's was not checked.

## Related work

The thread "Symphony on the WSU grid" (item 10 of the same list) builds a different route onto the
same node: a GitHub Actions self-hosted runner started as a Slurm job through hpcworker's tools,
with the logs coming back as artifacts, so Symphony's workflows run on the grid; its second step
is the SSH gate. It does not touch the project's threads and this note does not touch the runner;
the two meet only in hpcworker, each in a pull request of its own.
