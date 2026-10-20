---
name: control-panel-foot-tasks
description: How the control panel's foot (#msg) carries long work (workflow runs, the token sign-in) and the phone rules the mobile pass of 2026-10-19 set; read before touching say(), msgTask, dispatch, addByActions or control.css's phone media query
metadata:
  type: project
  modified: 2026-10-19T05:05:00.000Z
---

Control panel sign-in thread, 2026-10-19 (site #78 merged; symphony-app #39: checks P1-P22, mutants p01-p33 in signin.test.mjs, all killed; P20 pool lend, P21 Token workflow in the org's home repo, P22 side-panel width).

- say(text, warn) writes the plain line at the foot and removes everything there except live task boxes; msgTask(title) makes a box (.msgtask, data-state live/done/failed) with title, run link, line, steps, log tail, a step area (links, the code box) and a button bar; task.end() ends it and drops plain notes; task.refuse(text) drops the box and says a plain message (a start GitHub refused). A new task calls say('') first, so finished boxes go. msgTasksDrop() on sign-out.
- A workflow button (dispatch, dispatchAgents) reads newestRunId first, posts the dispatch for the account captured at press time (var account = shownLogin; the read before it may name one, check I13), then findRun polls runs (event=workflow_dispatch, 2 min max, first look after 2 s) and followRunSteps polls jobs every 6 s (15 min max), reads each ended job's log once (Accept header removed, raw, last 12 lines, ##[group] lines dropped). Lines say "Starting...", "Queued on main; ...", "Running; its steps show here as GitHub lists them.", "Finished: success, in 1 min 35 s." (the box names the task). The panel and assistant suites wait for "Queued on main".
- GitHub gives a job's log only after the job ends: while it runs the foot shows step names and states only. Tell greg this when he asks for live log lines.
- The token sign-in speaks through a task box (signInView over msgTask): the claude.ai link #tk-open (msgtask__go), the code box #tk-code, "Send the code", Stop; "Save and sign in" closes the dialog at once; Clear hides a live box, the Sign-in waiting tile shows it again.
- Phone (max-width 900px or max-height 520px): the deck gets overflow-x: clip (overflow-x: hidden on html unsticks the sticky status line, measured), zoom 1 and no zoom buttons, rail edge fades (data-more from railEdges), run rows as cards, token tiles in two columns, #msg flex 1 1 100%. Desktop #msg is flex 1 1 0 so a long message never pushes Clear under the zoom buttons.
- Refresh holds: holdStage() keeps .console__stage's min-height through loadRepo on a phone (20 s safety timer); graphReset(..., reading=true) holds the chart box; only the newest hold's release lets go (data-held); every end path releases.
- Run following: findRun/followRunSteps retry a failed read up to RUN_FAILS (3) in a row; findRun prefers the signed-in person's own run; a run left when the page changes repository says so; titles name the repository; a second Add Token while one saves is refused (tokenAdding).
- A media query adds no specificity: a phone override must come after the rule it overrides in control.css.
- Playwright suites: open(opts) in signin.test.mjs takes opts.viewport and opts.mobile; the server on 8077 must serve the site checkout; run-mutants.sh needs SITE set to the checkout too; delete mutants/*.json.log before scripts/check.sh, and end every mutant .json with a newline (json.dump writes none).
- .tkside (and #nb-side) take the phone column below 900px or 520px high; above, a kept width is capped at 50%.

**Why:** greg asked that a button's dialog answer at once, the foot flash and carry GitHub's run output, and that the phone stop panning and jumping.
**How to apply:** new long work goes through msgTask, never a dialog that waits; a refusal before a start is say(), not a failed box; keep the phone CSS after the zoom rule.
