# Metaflow cards in the control panel

Source: the thread "Build self-propelling QA Metaflow pipeline", 2026-10-31, on the owner's words of 04:11 and 04:12 UTC ("expose the html pages associated with a metaflow pipeline run instance to controlpanel as a tab", "and embed them into the control panel nicely"). Read from Metaflow 2.19.39's own card files, made by the QA loop's smoke runs in a cloud session. Confidential with the rest of this repository (docs/project.md).

A Metaflow run's pages are its cards: each step decorated with `@card` leaves one HTML page per task, and the QA loop's steps leave one per round, refreshed while the round trains. The control panel's Pipelines tab shows them. This note says where Metaflow keeps a card, what a card is made of, and why the panel reads them from a branch of this repository rather than from the grid.

## Where a card is kept

Under the flow's datastore, `<datastore>/.metaflow/mf.cards/<Flow>/runs/<run>/steps/<step>/tasks/<task>/`:

- `cards/<name>.html`, the page, about 1.1 MB, almost all of it Metaflow's card viewer (one JavaScript bundle, the same in every card of a version). Its data is one line, `window.__MF_DATA__["<id>"] = "<base64>"`, whose base64 decodes to the card's JSON: `{"metadata": {...}, "components": [{"type": "page", "contents": [...]}]}`, a few kilobytes for the loop's round card. `<title>` carries the task's pathspec.
- `runtime/<name>.data.json`, beside it while the task moves the card: `{"reload_token": ..., "data": {<component id>: <component>}, "created_on": ...}`, each updated component in full by its id. The token is "final" once the task has ended; any other token means the card is still live.

The name is the card's type and id with a hash, so a reader lists the folder rather than guessing it.

## Why a branch

The grid sits behind the university's VPN and its sign-in, and the panel is a page in the viewer's browser that reads GitHub as the viewer; nothing of ours serves the grid's files, and nothing should. A branch of this private repository carries the cards to the panel with the access the repository already has: whoever may read SchwingNet may read the cards, and nobody else.

The grid gate's word `cards <kind>` (grid/gate.sh) makes the branch `cards`: for the kind's flow, as flows/registry.txt names it, it takes the newest three runs that have cards and writes, in a git copy on the lab volume,

- `<kind>.json`, the index: the kind, the flow, the gate word that refreshes it (`schwingnet-cards-<kind>`), and each run with its cards (step, task, name, file, live) or, for a card held back, why;
- `<kind>/<run>/<step>-<task>-<name>.json`, each card as its data alone, `{"card": <card JSON>, "runtime": <runtime JSON or null>}`;
- `template.html`, the viewer page once, its data's base64 replaced by the marker `__MF_PAYLOAD__` and its title made plain.

The page's code is kept once because it is 99 percent of every card and the same in all of them; a run of forty rounds would otherwise carry forty copies of it. The word pushes the branch with the owner's own sign-in on the grid, fast forward, and pushes nothing when the cards have not changed, so a send that finds nothing new leaves no commit.

## What leaves the grid

Only the cards' data, masked by the same rules as the gate's status lines: the data root's path, a source's person key (`name:key`), long hexadecimal runs, DICOM UIDs and the shapes of tokens are replaced before the data is written. A card whose data names a DICOM tag or element (PatientID, StudyInstanceUID and the like) is held back whole and listed in the index with the reason, since a card is free text a step writes and a mask that misses one form would publish it. The tests in tests/test_gate.py hold both.

## How the panel shows a card

The tab lists the kinds on the branch, then a kind's runs and their cards. To show a card it reads `template.html` and the card's file, merges the runtime components into the card's components by id (the update a live card would get from its task), puts the merged JSON, base64 encoded, where the marker stands, and shows the page in a frame sandboxed to scripts alone, so the viewer's code runs without the panel's origin, its storage or its sign-in. Refresh sends the index's gate word through the grid route, and the tab reads the branch again once the gate has pushed.

## Not yet measured

How the round card reads with a real loop's data, and how long the branch takes to reach the panel after a round ends, are measured once the loop's first rounds write their cards on the grid. The route needs the word in hpcworker's gate list and symphony-template's grid route before it can be sent.
