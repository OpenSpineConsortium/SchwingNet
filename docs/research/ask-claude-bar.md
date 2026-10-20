# The Ask Claude bar

The notes of the thread "Ask Claude bar" of the claude.ai Project "symphony2", 2026-10-18. The
owner's ask, in his words: "id like the ask claude tab to be similar to the "Messages from the
panel show here" bar which is frozen on the screen so you can have claude actually interact with
the control panel for you, or does that need claude in chrome?" The rest of that message (the
flashing message line, full screen, more graphical tabs, the token box's gear and side panel) went
to the threads that own those parts. The panel's earlier notes are control-panel.md and
control-panel-console.md beside this file; the assistant's design is design A of
control-board-graph.md.

## The answer in short

Claude in Chrome is not needed. The assistant already answers through an issue labelled assistant,
read-only, on the repository's own Claude token (docs/setup/claude-action.md, The assistant issue),
and the page already acted on a fenced `symphony` block at the end of the answer. The block now
carries two kinds of line:

- Reads the page does by itself, as before: `focus #N`, `open #N`, `filter ...`, `show ...`, and a
  new `tab NAME`, which opens one of the console's tabs.
- Changes the page offers as buttons and runs only on the person's press: `run workers|board|
  checks|metrics`, `give #N to NAME`, `merge #N`, `task TITLE` and `ask [#N] PROMPT`. Each button
  says what it does. The press runs the panel's own handler for the same thing (the Command tab's
  launch buttons, the Tasks tab's Give to, the Pull requests tab's Merge), as the person signed in,
  so there is no new write path and the Claude run still writes nothing.

The vocabulary lives in the template's .github/symphony/assistant.md, and
tests/test_claude_assistant.py pins its verbs to the ones the page knows.

## Why buttons and not Claude acting by itself

The answer can be steered by any text the run read, such as an issue anyone may open on a public
repository. A press is the person's word for each change. Three more guards follow from that:

- A button belongs to the answer it came with. Once the page reads the repository again (Refresh,
  another repository, another sign-in), a press does nothing and says so.
- A button runs once; it is disabled after its press.
- `merge #N` only opens the Pull requests tab and arms that row's own Merge. GitHub's merge happens
  on the person's second press, Confirm, which the panel already required, and the button stays
  disabled until the pull request is ready and every check has passed. `task` and `ask` only fill a
  form; the person sends it.

`give` is offered only for an issue the Tasks tab would offer Give to for (the Queue, Given to
workers, Blocked) and only to a registered worker. Anything else is said in words ("Not offered:
...") and no button is drawn.

## Where the bar sits

The console's frame (Control panel redesign, site #51) holds an empty `#cp-askbar`, a direct child
of the console just above the status line, frozen like it and hidden while it is empty or the
person is signed out. symphony-panel.js fills it: the name, the question box (Enter sends, Shift
and Enter is a new line), Ask, Stop watching, Ask again, the state line, and Answer, which opens
the answer again once closed. The answer opens in a drawer laid over the foot of the stage, never
inside the bar, since the bar scrolls inside itself and would clip it. The proposed actions sit at
the top of the drawer, and the `symphony` block is no longer shown as code. Close or Escape shuts
the drawer. The Ask Claude tab stays: it holds "Ask Claude to do it" (@claude on an issue), which
the bar's `ask` button fills, and the help text.

## Checks

symphony-app's signin/panel-checks/e2e2/assistant.test.mjs carries five new checks beside the
twenty earlier ones (check B changed: `merge #9` names an issue, so it is now said as "Not
offered"):

- M: the bar is outside every tab and inside the window on all eleven tabs, with the window never
  moved; it is hidden on the sign-in gate; the drawer opens with the answer and Close, Escape and
  Answer work; Enter sends and Shift and Enter does not.
- N: an answer with every kind of line draws exactly six buttons and writes nothing; each press
  writes exactly what the panel's own button writes (the workflow dispatch, the label, the merge
  only after Confirm, a draft pull request refused in words), a pressed button cannot be pressed
  again, and the drafts fill their forms and write nothing.
- N2: a button kept across a Refresh still runs once; one from before another account signed in
  runs nothing.
- N3: a merge pressed before the checks are read is refused in words and the button comes back.
- N4: the block hidden from the rendered answer is exactly the block acted on; another fenced block
  stays.

The adversarial review before the pull requests found, and the change fixed: every button died on
a Refresh of the same repository; a refused press (checks still being read) lost its button for
good; the regex that hid the block differed from the one that read it, so a block could be acted on
and shown, or hide prose after it; Escape worked only with focus inside the drawer; the Enter that
ends an input method's composition in Safari could send; and the vocabulary said merge was offered
only once checks pass, while the page draws it and refuses on the press. Left as they are: an edit
of the answer within its grace rebuilds the buttons, so one can move under the cursor (merge still
needs Confirm); and the page takes any Bot's comment after the question as the answer, as before.

Two checks failed in the full runs for reasons outside this change: signin.test.mjs's F6 fails on
site master too, and assistant.test.mjs's E2 compares fixed comment times on 2026-10-18 with the
clock, so it fails once that day passes 10:03 UTC.

Six mutants, each run against M, N and the first N2, were all caught: the stale-answer guard removed, the
actions run without a press, a button pressable twice, the merge confirmed by the page, Shift and
Enter sending, and give offered to an unregistered worker.

## What is not measured

No real run of the assistant has answered with the new lines yet, so whether Claude follows the
vocabulary is unmeasured, as for the first version. Two questions are still two runs on the main
account's five-hour window.
