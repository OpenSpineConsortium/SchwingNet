# The morning checkpoint of 2026-10-27: what only the project held, for a new one

Source: the thread "Plan the FleXray audit for #391" in the claude.ai project symphony (chan_014WUU19NHgHPhf7QetT9cbS), written between 04:50 and 05:30 UTC on 2026-10-27 at the owner's words of 04:47 UTC, "YO PLEASE CHECKPOINT ALL SESSIONS AND PUSH ALL FILES AND WRITE A HANDOFF SO A NEW ACCOUNT CAN PICK UP WHERE THESE LEFT OFF!", on the coordinator's word that this thread writes the project-wide pages. The project-wide restart page is symphony-template's docs/research/handoff-2026-10-27-checkpoint-4.md; this folder is its confidential companion and stays in SchwingNet. It follows docs/checkpoints/2026-10-26-morning/, the previous checkpoint's companion, which still holds what it held (the pack stage's design and the facts taken from the FleXray paper among it).

A claude.ai project's shared files, its memory and its threads belong to that project, and a new project sees none of them. Everything below was only there, so it is copied here or matched to its copy in git as it stood at the checkpoint. No secret, token or credential is in this folder, and no career material.

## 1. What is in this folder

- project-memory/: the project's memory, every file, copied word for word except that characters outside ASCII are written as ASCII (a long dash as ` - `, a middle dot as `.`, HTML-escaped angle brackets as the brackets), since the checks hold docs/ to ASCII. MEMORY.md is the index the coordinator kept: every thread and its state, the approved and sent grid counts, the owner's rules word for word with their times, the repositories and paths. The next project's coordinator reads it first and writes into the new project's memory whatever still holds.
- anomaly-route.md: this thread's own handoff, the SPINEPS to FleXray anomaly route of #391: where each stage stands (the timing job failed and its report is unread), what a resend of the timing word does, and the next session's steps in order.

## 2. The project's shared files and uploads at the checkpoint, and where each is now

- exact-slides/ (the CNS slides thread): exact_slides_cns.pptx and .pdf, exact_slides_neurips.pptx and .pdf. The same four files, byte for byte (checked by sha256 at the checkpoint), are on OpenSpineConsortium/bordercall's main under slides/exact/, with the code and the equations that build them.
- junction-slides/ (the CNS slides thread): the six junction slides as .pptx and .pdf, the five figures with their CSVs and captions, the records and the zip of both. They are on bordercall's main since its pull request #2 (slides/junction_slides.pptx, the figures and records/panjabi-2026-10-26/), and the commands in bordercall's records/README.md rebuild them from the record.
- handoff/drr-comparison-2026-10-26.md: an early copy of the DRR comparison thread's handoff of 2026-10-26; the fuller version is docs/checkpoints/2026-10-26-drr-comparison/HANDOFF.md on main, and the newer one is that thread's docs/checkpoints/2026-10-27-drr-comparison/HANDOFF.md (section 3).
- textbook/: the staged copy of the book (86 MB), the design the owner rejected on 2026-10-26 (no owner step ever, a live front door into the repository). Nothing needs it; `python3 tools/textbook_reader.py stage` makes one again where one is wanted.
- uploads/, the owner's uploads, read by the threads and not copied into git, since all but the last are third parties' papers:
  - 2026-10-26 00:28 UTC, the LaTeX source of the FleXray paper (arXiv 2609.26756v2, 19.9 MB); what the stages took from it is docs/checkpoints/2026-10-26-morning/flexray-paper-facts.md.
  - 2026-10-26 08:21 UTC, Kunkel and colleagues, "Prediction equations for human thoracic and lumbar vertebral morphometry", J. Anat. 2010, 216, 320-328 (doi 10.1111/j.1469-7580.2009.01187.x); what bordercall took from it is in its docs/LEVEL_IDENTIFIABILITY_RESULTS.md.
  - 2026-10-26 21:31 UTC, Manbachi and colleagues, "Clinical Translation of the LevelCheck Decision Support Algorithm for Target Localization in Spine Surgery" (Ann Biomed Eng, PMC author manuscript); De Silva and colleagues, "Utility of the LevelCheck algorithm for decision support in vertebral localization" (Spine, 2016, PMC author manuscript); and that study's supplementary questionnaire (a Word file). The white paper and chapter 36 cite them.
  - 2026-10-27 03:06 UTC, Radiopaedia's outcome letter on the non-commercial use of its content for machine learning (approval 202610-9517). Its terms are recorded in data/sources/radiopaedia.json by the tiers thread's pull request #420 (section 3) and in project-memory/corpus-tiers-census.md; the letter itself is the owner's correspondence and stays in the owner's mail.
  A thread that needs one of these whole asks the owner to upload it again, once.

Nothing else was in the project's files. The white paper's live text is the owner's Claude Doc "SchwingCheck and LevelCheck" (https://claude.ai/artifact/4VwMe9CKMX87s4jiEJBpRE), which belongs to the owner's account; bordercall's docs/SCHWINGCHECK_LEVELCHECK.md is its copy at revision 189. The owner's CNS deck v13 is on the owner's computer only, as docs/checkpoints/2026-10-25-evening/README.md says, and the Outlook drafts are in the owner's mailbox.

## 3. The threads' handoffs, by path

- Plan the FleXray audit for #391: anomaly-route.md in this folder (branch claude/project-thread-x16ebc until its pull request merges).
- Compare FleXray DRRs to real X-ray corpora: docs/checkpoints/2026-10-27-drr-comparison/HANDOFF.md on claude/project-thread-d14v3r (#418, a draft), after docs/checkpoints/2026-10-26-drr-comparison/HANDOFF.md on main; the research is docs/research/drr-domain-gap/README.md.
- Finish CNS slides with junction predictor: docs/checkpoints/2026-10-27-cns-junction/README.md and review-findings.md on claude/project-thread-7qoboa (#416, a draft: textbook chapter 36 carrying the white paper), after docs/checkpoints/2026-10-26-cns-junction/README.md on main; bordercall's HANDOFF.md steps 7 to 11 carry the studies, and its docs/SCHWINGCHECK_LEVELCHECK.md the paper.
- Let readers open the live front door (once "Stage the textbook for this project"): docs/checkpoints/2026-10-27-door-for-readers/HANDOFF.md on claude/project-thread-24opi2 (#419, a draft), with the site's draft OpenSpineConsortium/openspineconsortium.github.io#147; the owner's own door's steps are docs/checkpoints/2026-10-26-front-door/HANDOFF.md on main.
- Finetune Flux Realism for X-rays: docs/checkpoints/2026-10-26-flux-realism/HANDOFF.md, section "State at the second checkpoint", on claude/project-thread-vd6p1l (#417, marked ready at the checkpoint), the rest of the page on main.
- Sort the corpus into gold and silver tiers: docs/checkpoints/2026-10-27-corpus-tiers/HANDOFF.md on claude/project-thread-cdwl0r (#420, a draft; the work files a new account needs to finish are under data/corpus-tiers/work/), with symphony-template #500's public method note.
- Add fetch size readers for #163: done; docs/research/exact-fetch-sizes.md holds the two things still unverified.

## 4. The owner's words, where they are kept

Word for word in project-memory/MEMORY.md and the files it names: the rules of 2026-10-26 (ground truth only from columns countable from C2, 00:16 UTC; SPINEPS for production and the segmenter as a block, 00:17 and 00:26 UTC; Benzel's figures, 01:17 UTC; the live door, 00:13 and 00:18 UTC; no OneDrive, 02:48 and 02:55 UTC; no arbitrary constraints on the naming problem and a series of solutions, 06:31 UTC), the gold and silver tiers (2026-10-27 03:06 UTC), beethoven-qa 10.0.0 everywhere (03:08 and 03:09 UTC), the Actions budget raised (03:10 UTC), the CNS thread's rules on the white paper, and the checkpoint words above. The approved grid counts and what was sent are in MEMORY.md's "Grid counts" and in the restart page's section 3.

## 5. The first prompt for the next project

The restart page's section 1 carries it; this is the same text, kept here so the folder stands on its own:

```
You are picking up the "symphony" project from an earlier project, perhaps on another Claude account. First read docs/research/handoff-2026-10-27-checkpoint-4.md in OpenSpineConsortium/symphony-template, on main, or on the branch claude/project-thread-x16ebc until its pull request merges. Then, in order:
1. Write this project's instructions yourself: section 2 of symphony-template's docs/research/handoff-2026-10-25.md, verbatim, with its line "No API key or Claude credential anywhere." replaced by the key rule in that page's section 0, the goal line of its section 11, step 3, at the top, and the owner's rules from section 4 of the checkpoint-4 page after it. Attach OpenSpineConsortium/FleXray, OpenSpineConsortium/bordercall, OpenSpineConsortium/hpcworker and OpenSpineConsortium/openspineconsortium.github.io with add_repo, and the other repositories that page lists when a thread needs one.
2. Read SchwingNet's docs/checkpoints/2026-10-27-morning/README.md (on the branch claude/project-thread-x16ebc until its pull request merges), and write into this project's memory whatever in its project-memory/ folder still holds.
3. Start one thread for each open thread in section 2 of the checkpoint-4 page, each told to restart from its own handoff as that section says.
Send nothing to the grid beyond the counts section 3 of the checkpoint-4 page records as approved, each word once and only after reading the grid's status record, and ask me for any other count once, as a decision card. Never give me a step that only moves or edits text. When I answer idk, take the option you recommend. Do not copy anything from SchwingNet or bordercall into a public place, and put no career material in git.
```
