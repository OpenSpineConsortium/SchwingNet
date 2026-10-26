# The morning checkpoint of 2026-10-26: what only the project held, for a new one

Source: the thread "Plan the FleXray audit for #391" in the claude.ai project symphony (chan_014WUU19NHgHPhf7QetT9cbS), written between 03:05 and 03:30 UTC on 2026-10-26 at the owner's words of 03:01 UTC, "please push as much as possible now im running out of tokens then write a handoff for checkpointing asap!", and 03:02 UTC, "and makesure all files needed to continue in antoher account's new project are pushed to git". The project-wide restart page is symphony-template's docs/research/handoff-2026-10-26-checkpoint-3.md; this folder is its confidential companion and stays in SchwingNet. It follows docs/checkpoints/2026-10-25-evening/, the previous checkpoint's companion, which still holds what it held.

A claude.ai project's shared files, its memory and its threads belong to that project, and a new project sees none of them. Everything below was only there, so it is copied here as it stood at the checkpoint. No secret, token or credential is in this folder, and no career material.

## 1. What is in this folder

- project-memory/: the project's memory, every file, copied word for word except that characters outside ASCII are written as ASCII (a long dash as ` - `, a middle dot as `.`, HTML-escaped angle brackets as the brackets), since the checks hold docs/ to ASCII. MEMORY.md is the index the coordinator kept; it lists every thread, its state, the approved and sent grid counts, the owner's rules of the night word for word, the repositories and paths. The next project's coordinator reads it first and writes into the new project's memory whatever still holds.
- anomaly-route.md: this thread's own handoff, the SPINEPS to FleXray anomaly route of #391: where each stage stands, which jobs were sent, and the next session's steps in order.
- pack-stage-design.md: the design the pack stage (#410) was built from, read-only, with the review's findings folded in; the render, figure and tune stages build on its sections 7 to 11 and on project-memory/anomaly-pack-stage-design.md.
- flexray-paper-facts.md: what the pack and tune stages need from the FleXray paper (arXiv 2609.26756v2), read from the LaTeX source the owner uploaded at 00:28 UTC, which is not in git (section 2).

## 2. The project's shared files and uploads at the checkpoint, and where each is now

- junction-slides/ (the CNS slides thread): junction_slides.pptx and .pdf, five figures as PDF, PNG, CSV and caption with FIGURES.md, the records folder and junction_figures_and_records.zip. FIGURES.md names the record they were drawn from, records/panjabi-2026-10-26/three-measures/panjabi_junction.json (sha256 dd768950...), and the code, both on OpenSpineConsortium/bordercall's main since its pull request #1 merged (aa31c7a). At the checkpoint the CNS thread was committing the deck, the figures, the CSVs, the records and the zip's contents to bordercall on the owner's word of 03:02 UTC, with a HANDOFF.md there and a checkpoint page under docs/checkpoints/ here, in its own pull request. If its push did not land, the figures and the slides are rebuilt from the record by the commands in bordercall's records/README.md (`python run.py panjabi-figures ...`, then slides/make_junction_slides.py). The OneDrive upload of the figures was stopped on the owner's word (02:48 and 02:55 UTC) and is not resumed.
- textbook/ (the textbook thread): the staged copy of the book (CURRENT.json, book-<hash>.json and .bin, 86 MB), the design the owner rejected on 2026-10-26 (00:13 and 00:18 UTC: no owner step ever, the reader a live front door into the repository). The live door, tools/front_door.html, reads main and the board through the viewer's own GitHub connector (#405, #408, #409), so the staged copy is nothing a new project needs; `python3 tools/textbook_reader.py stage` makes one again where one is wanted.
- uploads/ (the owner's upload of 00:28 UTC, "HERE IS THE FLEXRAY PAPEAR FOR YOUR REFERENCE"): the LaTeX source of arXiv 2609.26756v2 as a 19.9 MB tar.gz, public at arXiv, which the cloud sessions cannot reach (the proxy refuses arxiv.org). It is not copied into git, since it is a third party's paper; flexray-paper-facts.md holds what the stages took from it, and symphony-template's docs/research/flexray-audit-plan-2026-10-25.md what the plan took. A thread that needs the whole paper asks the owner to upload it again, once.

Nothing else was in the project's files. The other threads' handoffs are in git on their branches (section 3). The grid's own files (the selection, the harvest, the logs) are on the grid, as always, and the owner's CNS deck v13 is on the owner's computer only, as docs/checkpoints/2026-10-25-evening/README.md says.

## 3. The threads' handoffs, by path

- Plan the FleXray audit for #391: anomaly-route.md in this folder (branch claude/project-thread-x16ebc, pull request #410, until it merges).
- Compare FleXray DRRs to real X-ray corpora: docs/checkpoints/2026-10-26-drr-comparison/HANDOFF.md on claude/project-thread-7ltron (#401, a draft; the public method note is symphony-template #493).
- Finish CNS slides with junction predictor: bordercall's HANDOFF.md and the checkpoint page the thread's pull request adds under docs/checkpoints/ here; bordercall #1 and SchwingNet #404 merged; hpcworker #50 and symphony-template #495 open.
- Stage the textbook for this project: docs/checkpoints/2026-10-26-front-door/HANDOFF.md on claude/project-thread-24opi2 (#409, ready, auto-merge armed), with the owner's remaining steps for the door in order.
- Finetune Flux Realism for X-rays: docs/checkpoints/2026-10-26-flux-realism/HANDOFF.md on claude/project-thread-vd6p1l (#406, ready, auto-merge armed).
- Add fetch size readers for #163: done; #400 merged (570e6c7) and #163 closed; the two things still unverified are in docs/research/exact-fetch-sizes.md.

## 4. The owner's words of the night, where they are kept

Word for word in project-memory/MEMORY.md and the files it names: the ground-truth rule (00:16 UTC: only full-spine CTs countable from C2 to the pelvis), the segmentation rule (00:17 and 00:26 UTC: SPINEPS for production reusing the masks on the grid, MOOSE only to replicate FleXray's dataset, the segmenter a configurable block, the label difference handled everywhere), the figure rule (01:17 UTC: Benzel's style, the code committed and runnable from recorded inputs), the textbook rule (00:13 and 00:18 UTC: no owner step ever, a live door into the repository), the OneDrive stop (02:48 and 02:55 UTC), and the checkpoint words above. The approved grid counts and what was sent are in MEMORY.md's "Grid counts" and in symphony-template's restart page, section 3.

## 5. The first prompt for the next project

The restart page's section 1 carries it; this is the same text, kept here so the folder stands on its own:

```
You are picking up the "symphony" project from an earlier project, perhaps on another Claude account. First read docs/research/handoff-2026-10-26-checkpoint-3.md in OpenSpineConsortium/symphony-template, on main, or on the branch claude/project-thread-x16ebc until its pull request merges. Then, in order:
1. Write this project's instructions yourself: section 2 of symphony-template's docs/research/handoff-2026-10-25.md, verbatim, with its line "No API key or Claude credential anywhere." replaced by the key rule in that page's section 0, the goal line of its section 11, step 3, at the top, and the owner's rules of 2026-10-26 from section 4 of the checkpoint-3 page after it. Attach OpenSpineConsortium/FleXray, OpenSpineConsortium/bordercall and OpenSpineConsortium/hpcworker with add_repo, and the other repositories that page lists when a thread needs one.
2. Read SchwingNet's docs/checkpoints/2026-10-26-morning/README.md (on the branch claude/project-thread-x16ebc until SchwingNet #410 merges), and write into this project's memory whatever in its project-memory/ folder still holds.
3. Start one thread for each open thread in section 2 of the checkpoint page, each told to restart from its own handoff as that section says.
Send nothing to the grid beyond the counts section 3 of the checkpoint page records as approved, each word once and only after reading the grid's status record, and ask me for any other count once, as a decision card. Never give me a step that only moves or edits text. When I answer idk, take the option you recommend. Do not copy anything from SchwingNet or bordercall into a public place, and put no career material in git.
```
