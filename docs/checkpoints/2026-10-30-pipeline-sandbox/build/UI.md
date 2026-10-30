# UI brief (tools/sandbox/ui.js, page.css, shell.html)

Read SPEC.md first. The page is one self-contained file; ui.js runs after engine.js inside one script element,
with `SANDBOX_DATA` and `SandboxEngine` global. Plain JavaScript (ES2017 is fine), no library, no fetch, no
external resource, ASCII only (write a non-ASCII character as a \u escape inside a JS string, never raw),
LF endings. Text from data or from the viewer reaches the DOM through textContent only; innerHTML is used
only for the glyph library's own SVG strings.

## Look (keep pipeline.html's)

Copy pipeline.html's tokens exactly (light on :root; dark redefined under
`@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {...} }` and again under
`:root[data-theme="dark"]`, each with color-scheme: dark), its body padding
(`padding-left: max(16px, env(safe-area-inset-left, 0px))` and the right one), its job tags (cpu, gpu, none,
file, phase), cards, deck shadow, detail panel (sticky 380px column from 980px wide; bottom sheet below that,
with a Close button and Escape), decision-card look for the summary tiles, glyph stroke classes, and phone
rules at 640px. Fonts: system stacks only:
`--display: "Iowan Old Style", "Palatino Linotype", Georgia, serif; --body: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; --mono: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace`.
Add tokens you need (e.g. --bad for an error badge, --ghost) to both themes. The page never scrolls
sideways at 400px: the board scrolls inside its own container.

## Layout (shell.html is the static markup; ui.js fills it)

- header: eyebrow `SchwingNet / pipeline sandbox / a plan: nothing runs from this page`, h1 `Pipeline sandbox`,
  a lede of two sentences (what it is; that runs go only through a request the owner approves with a job count),
  and a legend of the job tags.
- toolbar (a wrapping row of buttons): New, Templates (a select listing DATA.templates by name), Auto-layout,
  Undo, Redo, Import a block, Copy spec, and the request button (its label follows the route: "Request this
  run" / "Request these N runs" on the experiment route, "Request this pipeline" on the pipeline route).
- palette: a strip above the board with one tab per stage (contract.stages) and the blocks of that stage as
  chips (glyph at 28px + title); a search box filters all blocks by title, id and summary. Clicking a chip adds
  the block: to the right of the selected node and connected to it when the block accepts its first output,
  else at the first free spot. A chip can also be dragged onto the board. Planned and pending blocks carry a
  small tag ("planned", "pending #483"); imported blocks carry "imported".
- the board (left column, min-width 0): a scrollable container (overflow auto, height about 62vh, touch-action
  none on the stage) holding a stage div (position relative, sized to its content plus 400px of room to the right
  and below) with an SVG edge layer under absolutely positioned node cards.
- the detail panel (right column / bottom sheet), aria-live polite.
- below the board: "How to read this" (a details element with a short glossary: block, port, type, fan,
  route, job, digest) and a footer: `Confidential with the repository. Nothing here is a result, and no job is
  sent from this page.`

## Node cards and edges

A card is about 232px wide: the glyph at 64px on the left; on the right the stage label (mono, accent), the
title (600), the summary (13px muted, two lines max) and the job tag. Input handles: one dot per input port on
the left edge, evenly spaced, with the port name in a title attribute; output handles on the right edge the
same way. A card with error problems shows a small badge with their count (amber outline); a varied node (its
combinations or fan above 1) draws the deck shadow and an `x<fan>` badge; a planned or pending block's card has
a dashed border; the selected card has the accent border (aria-current). Cards are buttons-like: tabindex 0,
role "group", aria-label = title; Enter or a click selects.

Edges are cubic curves in the SVG from the output handle to the input handle, with an arrowhead and a small
mono label at the curve's middle: `SandboxEngine.typeSummary(type)` shortened to about 36 characters, the full
text in a <title>. An edge whose input type has a "type" problem is drawn in --amber with a dashed stroke.

## Holding to the right of a node (the centrepiece; make it feel instant)

- Grow zone of a node: x from its right edge + 6 to its right edge + 260, y from its top - 30 to its bottom
  + 30, in stage coordinates, minus any area another card covers.
- The anchor is "the nearest left node": among nodes whose right edge is left of the pointer and whose
  vertical band (top - 30 .. bottom + 30) holds the pointer's y, the one whose right-edge midpoint is nearest
  the pointer; it is computed from cached card rectangles (stage coordinates) that are rebuilt only after a
  layout change, never by reading the DOM inside pointermove.
- pointermove is handled once per animation frame (requestAnimationFrame). When the pointer rests (moves less
  than 6px) in a grow zone for 140ms, a ghost card appears where the new node would go: x = anchor.right + 72,
  y = the anchor's y, or the first free 20px-grid slot below it if a card is there. The ghost shows the top
  prediction (`SandboxEngine.predict`) with its glyph and title at 70% opacity and a ring (an SVG circle with a
  stroke-dashoffset transition, or a conic-gradient) that fills over 480ms; when it is full the node is
  committed. Moving more than 6px restarts the dwell (and re-anchors); leaving every grow zone hides the ghost.
- Beside the ghost, a suggestion strip lists the top 5 predictions (glyph, title, the `why` line in muted
  text), the current one highlighted. While the ghost shows: the mouse wheel or ArrowUp / ArrowDown moves to the
  next or previous suggestion and restarts the ring; keys 1-5 pick and commit at once; Enter or a click on the
  ghost commits; a click on a strip entry commits that block; Escape cancels and suppresses the ghost until the
  pointer leaves the zone. While the ghost shows, the wheel must not scroll the board (preventDefault on a
  non-passive wheel listener only while a ghost is up).
- Press and hold (pointerdown in a grow zone, any pointer type) starts the ring at once; lifting before it fills
  cancels on touch and keeps the hover dwell on a mouse. A tap or a click in a grow zone commits the top
  prediction at once.
- Committing: add a node of that block at the ghost's place with default params, add an edge from the anchor's
  first output to the new node's first input that accepts it, select the new node, recompute (propagate,
  compile) and redraw only what changed, record the transition in the viewer's history (anchor block -> new
  block, saved in localStorage under `schwingnet.sandbox.v1`), and push an undo step. The pointer now rests on
  the new card, so a new dwell starts only when the pointer moves to its right: one card per hold.
- Keyboard: with a card focused, Shift+ArrowRight opens the ghost for it (same ring, strip and keys).
- No candidate (a report output, or nothing accepts the type): the ghost shows "nothing follows here" and no
  ring.
- Budget: a pointermove with no change must cost well under 1ms; committing a node with 30 nodes on the board
  must redraw in under 16ms. Keep the DOM per card small and reuse elements.

## Other interactions

- Drag a card by its body to move it (a 20px grid snap); its edges follow live (update only its edges' paths).
- Connect: drag from an output handle to an input handle; while dragging, input handles that accept the type
  glow and the others dim; dropping on an accepting or a non-accepting handle both connect (a non-accepting one
  then shows its problem); an input already connected is replaced. Dropping on empty board cancels.
- Select a card: the panel shows the node. Delete or Backspace (when no input field has focus) removes the
  selected node and its edges, with an undo step.
- Undo / Redo: Ctrl or Cmd + Z, Ctrl or Cmd + Shift + Z, and the toolbar buttons; at least 100 steps of the whole
  spec (layout included).
- Auto-layout: columns by longest path from a source, rows in node order, 300px x 150px cells.
- Templates select: loads the template (as a new spec; its layout is used); `#<template id>` in location.hash
  on load picks a template too. New: an empty board with a hint "pick a source from the palette, then hold the
  pointer to the right of it".
- State: the current spec, the imported blocks and the history are saved in localStorage
  `schwingnet.sandbox.v1` on every change (each read and write in try/catch; the page works without it). On
  load: the saved spec if any, else the template `experiment_v1`.

## The detail panel

With a node selected: eyebrow = the stage title; the title in --display 21px; Close (sheet only); the job tag;
the big glyph (up to 300px); `does`; "takes" (each input: its name, its pattern in words, the incoming type
summary or "not connected"); "gives" (each output: the type summary); for a model or checkpoint output,
`SandboxEngine.resolveText` ("adapts to the data: ..."); the params editor: a choice as a row of segmented buttons
(`.seg` with aria-pressed), an int or float as an input type=number with min/max/step, a bool as a checkbox, a
set as checkboxes in option order, names as a text input (comma separated); each param with vary true gets a
small "vary" toggle that turns its editor into a text input "values separated by /" (e.g. `resnet18/resnet34`),
parsed by kind; every edit re-runs propagate and compile at once and redraws. Then: the data card for a source
(origin, where, count, persons, split, held out, licence, from); lineage (sources, licence, persons, parts) from
the first output type; resources (job class, hours per task, fan, submissions this node makes, where it runs
today: today.status with its word / flow / note in words: live = "requestable now (experiment route)",
word = "the gate word <word> runs it", flow = "runs inside <flow>", pending = "built on <note>, not merged",
planned = "not built yet; waits for the pipeline route"); the node's problems as a list; a Remove button.

With nothing selected: the pipeline summary: the name (an input), the digest's first 12 hex with a Copy button
for the whole digest, the route verdict ("Experiment route: ready, N request(s)" or "Plan only: <the why lines>"),
tiles (GPU submissions, GPU tasks, GPU-hours, CPU submissions, nodes), the plan rows as a compact table
(node, block, class, submissions x tasks, hours, today), all problems, and the request buttons.

## Actions tied to buttons (no alert, confirm or prompt anywhere)

- Request (experiment route, ready): one `<a target="_blank" rel="noopener">` per request with its title, href =
  the request's url, opening the prefilled experiment issue; above them one line: "Each opens a prefilled issue;
  the experiment workflow checks it and answers with the gate word; nothing runs until you click that word with
  its job count." When the page is framed (window.parent !== window), clicking also posts to the parent
  `{"type": "schwingnet.open", "href": url, "label": "Request this run: " + title}` and, on any change of the
  first request, `{"type": "schwingnet.experiment", command, recipe, blocks, named, epochs, seed, hours,
  issueUrl, title, body, ok, problems, repo, workflow: "experiment.yml", ref: "main", inputs: {recipe, epochs,
  seed, hours, blocks}, label, fallbackUrl}` in the shape tools/experiments_panel.py posts; listen only to
  messages whose source is window.parent (type schwingnet.dispatch.result: show its ok or error in a note).
- Request (pipeline route): a link opening `https://github.com/OpenSpineConsortium/SchwingNet/issues/new?` with
  the compile's pipeline_issue title and body (URLSearchParams); when the url would pass 7500 characters, the
  link's body is the first three lines plus "The spec is too long for a link; paste it from the page's Copy
  spec." and a Copy spec button sits beside it. A line beside it: "Nothing answers this issue yet; the pipeline
  route waits on the owner's word."
- Copy spec: copies the canonical JSON (navigator.clipboard.writeText inside the click; on failure show the text
  in a selected read-only textarea in the panel).
- Import a block: an in-page dialog (a section that opens over the board, not window.prompt): a textarea and a
  file input (FileReader) for a block.json; "Check" runs `SandboxEngine.checkManifest` and lists every problem
  with its code; the list of requirements (contract.requirements) is shown beside it; "Add to the palette" is
  enabled only with no problem and adds the block (badge "imported, not in the repository"), saved in
  localStorage; a "How to make it runnable" note with a Copy button: "Put block.json as
  tools/sandbox/blocks/<id>.json, its code as tools/sandbox/blocks/<id>.py (a module docstring and def
  run(inputs, params, context)), its test as tests/test_sandbox_block_<id>.py, then run python3
  tools/pipeline_sandbox.py check-block tools/sandbox/blocks/<id>.json and open a pull request; a pipeline that
  uses it runs only after that pull request merges." An imported block whose id equals a built-in block's is
  refused. A pipeline using an imported block compiles normally but its plan row's today reads "imported: not
  in the repository".

## The glyph library

A table `GLYPHS = { name: function () { return "<svg elements>"; }, ... }` with every name of contract.glyphs
(SPEC.md section 9), each drawing the operation in the 120 x 72 box in pipeline.html's style (reuse its
helpers arrow, c and vertebra, and reuse its drawings where they fit: train, calibrate, evaluate, report,
foreach for the deck, features, smoke). draw(name) falls back to `fallback` for an unknown name and never
throws. Gradients, if any, need unique ids per drawing.

## Test hooks (for the browser test)

`window.sandbox = {graph(), load(templateId), grow(anchorId, blockId), suggestions(anchorId), compile(), digest(),
problems(), reset(), select(nodeId)}`: graph returns a deep copy of the spec; grow adds blockId (or the top
prediction when blockId is absent) to the right of anchorId as a committed hold would, and returns the new id.
