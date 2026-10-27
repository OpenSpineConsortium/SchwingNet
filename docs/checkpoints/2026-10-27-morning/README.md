# The morning checkpoint of 2026-10-27: what only the project held, for a new one

Source: the thread "Plan the FleXray audit for #391" in the claude.ai project symphony (chan_014WUU19NHgHPhf7QetT9cbS), written between 04:50 and 05:30 UTC on 2026-10-27 at the owner's words of 04:47 UTC, "YO PLEASE CHECKPOINT ALL SESSIONS AND PUSH ALL FILES AND WRITE A HANDOFF SO A NEW ACCOUNT CAN PICK UP WHERE THESE LEFT OFF!", on the coordinator's word that this thread writes the project-wide pages. The project-wide restart page is symphony-template's docs/research/handoff-2026-10-27-checkpoint-4.md; this folder is its confidential companion and stays in SchwingNet. It follows docs/checkpoints/2026-10-26-morning/, the previous checkpoint's companion, which still holds what it held (the pack stage's design and the facts taken from the FleXray paper among it).

A claude.ai project's shared files, its memory and its threads belong to that project, and a new project sees none of them. Everything below was only there, so it is copied here or matched to its copy in git as it stood at the checkpoint. No secret, token or credential is in this folder, and no career material.

Section 0 was added after the rest, on the owner's word of 05:48 UTC, and it comes before everything below, as section 0 of the restart page does.

## 0. The owner's priority of 05:48 UTC: nothing else until the owner says otherwise

The owner, at 05:48 UTC on 2026-10-27, in the CNS thread: the new account is to "work on nothing else except fleshing out Panjabi until I say otherwise, then it should be on getting gold 1/2/3 tier data for segmentation based empirical testing of this bayesian generator", the Panjabi work being to "extract the rest of the data/tables from all of these three panjabi papers, expanding beyond what is easily measurable on spineps segmentations to see how more measurements improves accuracy". The restart page's section 0 carries the order. This section gives the task in full. Until the owner says otherwise, no other thread is restarted and nothing is sent to the grid.

### Where the plan is

bordercall's main holds it, as of 7015802 (2026-10-27, after the owner's word). Its README.md opens with the priority. Its TODO.md gives the order in the owner's words, then the steps and traps of item P (the Panjabi extraction) and item 5 (the gold data). This section points there and adds only what the restart needs. Where the two differ, bordercall's TODO.md holds for the work.

The CNS thread moved the old repository, unchanged, under archive/ in bordercall's main bb86584. Every older bordercall path, in this folder, in the restart page and in the threads' handoffs, now starts with archive/. The tests run from there: `cd archive && python3 -m unittest discover -s tests`, 222 tests, which pass. SchwingNet's pinned copy under grid/bordercall/ is unaffected. A later copy is taken with `python3 tools/bordercall_vendor.py copy <clone>/archive`.

### The first item: flesh out Panjabi (bordercall; no grid, no CT, no fetch)

- **What is in.** archive/bordercall/reference/build_panjabi.py builds archive/bordercall/reference/panjabi_full_spine.csv from the three scanned papers in archive/bordercall/reference/papers/. The papers are cervical, Spine 1991;16(8):861-869; thoracic, Spine 1991;16(8):888-901; and lumbar, Spine 1992;17(3):299-306. The table has 13 measures over the 23 levels C2 to L5: the upper and lower end-plates' width and depth, the posterior body height, the canal's depth and width, and six pedicle rows.
- **What the rule uses.** The exact Bayes rule (archive/bordercall/exact.py) uses the seven that a SPINEPS mask measures (archive/bordercall/SPINEPS_MAPPING.md). The six pedicle rows are transcribed but unused.
- **What is out.** By the builder's own list: the surface areas, the angular dimensions, the pars interarticularis, the spinous and transverse process tables, the rib articulations and the uncovertebral joints.
- **The work.** The owner wants every remaining measure and table, going past what SPINEPS measures easily. TODO.md item P gives six steps:
  1. Inventory every table in the three papers, saying for each dimension what can read it.
  2. Transcribe from page images in two passes, checking each value the papers state in prose.
  3. Rebuild the table with build_panjabi.py.
  4. Model areas, angles and left/right pairs honestly.
  5. Score how added measures raise naming accuracy, with no enumeration of every subset.
  6. Deliver the record, Benzel-style figures and tests.
- **The baseline.** These are the exact study's numbers on the seven measures (archive/docs/EXACT_IDENTIFICATION_RESULTS.md):
  - The Bayes rule names 47.3, 73.1, 85.7, 96.1 and 99.7 percent of fields exactly, from 1, 3, 5, 9 and 15 bodies.
  - On a table estimated from twelve spines, names given at 0.99 from three bodies are right 95.5 percent of the time.
- **What the identifiability study found** (archive/docs/LEVEL_IDENTIFIABILITY_RESULTS.md): the pedicle rows separate the lumbar levels most. L5's isolation distance goes from 0.87 to 2.23, and L4's from 0.75 to 1.85.
- **Rules.**
  - Report each solution for the anomalous phenotypes too. This is the owner's rule of 06:31 UTC on 2026-10-26: no arbitrary constraints, and a series of solutions.
  - No grid job, fetch or training is approved for this item.
  - Every result is synthetic until item 5.

### The second item, only when the owner says so: gold 1, 2 and 3 data (bordercall's TODO.md item 5)

**The tiers.** The owner set them at 03:06 UTC on 2026-10-27; they are recorded in project-memory/corpus-tiers-census.md.

- Gold means one study shows C2 to the sacrum.
- Tier 1 is a real CT paired with a real X-ray of the same person, with a human annotation on at least one.
- Tier 2 is the same pair with no human annotation.
- Tier 3 is a CT or an X-ray alone, with a human annotation.
- A machine mask never raises a tier.

**What was held at the checkpoint.** Each person is counted once, and the counts are estimates until the census runs:

- gold 1: none;
- gold 2: none;
- gold 3: 159 persons (TotalSegmentator 142, VerSe 17).

**The steps, when the owner says so.**

1. Finish the tiers thread's drafts, SchwingNet #420 and symphony-template #500, from claude/project-thread-cdwl0r. Their handoff is docs/checkpoints/2026-10-27-corpus-tiers/HANDOFF.md on that branch.
2. Ask the owner once, on a decision card, for the census: one CPU job, not yet counted.
3. Follow up the pending sources:
   - Radiopaedia: approval 202610-9517, mostly silver 3, fetched by hand and never by script.
   - Setting Scoliosis Straight and the Harms Study Group: gold 3 and silver 3 expected. The owner's follow-up is in the owner's Outlook Drafts.
   - Exeter and Bournemouth: silver 3.
4. Look for gold 1 and 2 in the FleXray audit's corpus search, docs/research/flexray-audit-companion.md: 14 cohorts with per-case counts over both junctions, none open. Letters are drafted once the owner names cohorts, and the owner sends them.
5. Run the test itself, as item 5 says. The approved bordercall pilot (two CPU jobs, SchwingNet's `bordercall` gate word, unsent) measures the existing SPINEPS masks counted from C2 (docs/memory/bordercall-on-the-grid.md). Send it only when this item starts, after one `update` and a status read, pilot first. Score the rule built on the CT table on held-out whole patients.

Only spines countable from C2 are truth (the owner, 00:16 UTC on 2026-10-26).

## 1. What is in this folder

- project-memory/: the project's memory, every file, copied word for word except that characters outside ASCII are written as ASCII (a long dash as ` - `, a middle dot as `.`, HTML-escaped angle brackets as the brackets), since the checks hold docs/ to ASCII. MEMORY.md is the index as the coordinator last kept it, rewritten shortly after 05:48 UTC: the owner's priority at its top, the studies, the checkpoint, the owner and goal, every thread, the standing rules, the grid counts, the facts threads rely on and the repositories. It is a summary; the owner's words are kept word for word in the files beside it, and the current sent state is in anomaly-route-thread-state.md, drr-comparison-grid-count.md and flux-realism-thread-state.md here and in the restart page's sections 2 and 3, which hold where they differ. The links [[grid-counts]] and [[symphony-project-memory]] in four of the files name sections of MEMORY.md, not files. The next project's coordinator reads every file, not only those MEMORY.md names, and writes into the new project's memory whatever still holds.
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

- Plan the FleXray audit for #391: anomaly-route.md in this folder, on main since #421.
- Compare FleXray DRRs to real X-ray corpora: docs/checkpoints/2026-10-27-drr-comparison/HANDOFF.md on claude/project-thread-d14v3r (#418, a draft), after docs/checkpoints/2026-10-26-drr-comparison/HANDOFF.md on main; the research is docs/research/drr-domain-gap/README.md.
- Finish CNS slides with junction predictor: docs/checkpoints/2026-10-27-cns-junction/README.md and review-findings.md on claude/project-thread-7qoboa (#416, a draft: textbook chapter 36 carrying the white paper), after docs/checkpoints/2026-10-26-cns-junction/README.md on main; bordercall's HANDOFF.md steps 7 to 11 carry the studies, and its docs/SCHWINGCHECK_LEVELCHECK.md the paper.
- Let readers open the live front door (once "Stage the textbook for this project"): docs/checkpoints/2026-10-27-door-for-readers/HANDOFF.md on claude/project-thread-24opi2 (#419, a draft), with the site's draft OpenSpineConsortium/openspineconsortium.github.io#147; the owner's own door's steps are docs/checkpoints/2026-10-26-front-door/HANDOFF.md on main.
- Finetune Flux Realism for X-rays: docs/checkpoints/2026-10-26-flux-realism/HANDOFF.md on main, whose section "State at the second checkpoint" (#417, merged at the checkpoint) holds.
- Sort the corpus into gold and silver tiers: docs/checkpoints/2026-10-27-corpus-tiers/HANDOFF.md on claude/project-thread-cdwl0r (#420, a draft; the work files a new account needs to finish are under data/corpus-tiers/work/), with symphony-template #500's public method note.
- Add fetch size readers for #163: done; docs/research/exact-fetch-sizes.md holds the two things still unverified.

## 4. The owner's words, where they are kept

Word for word in the files of project-memory/ (all of them, not only those MEMORY.md names; the owner's words of 00:16, 00:17, 00:26 and 01:17 UTC are in owner-trusts-only-c2-countable-spines.md, segmenter-block.md, only-full-spine-columns-are-truth.md and figures-look-like-benzel.md, the DRR choices of 04:15 and 04:31 UTC in drr-comparison-grid-count.md), and the CNS thread's rules on the white paper in its docs/checkpoints/2026-10-27-cns-junction/README.md: the rules of 2026-10-26 (ground truth only from columns countable from C2, 00:16 UTC; SPINEPS for production and the segmenter as a block, 00:17 and 00:26 UTC; Benzel's figures, 01:17 UTC; the live door, 00:13 and 00:18 UTC; no OneDrive, 02:48 and 02:55 UTC; no arbitrary constraints on the naming problem and a series of solutions, 06:31 UTC), the gold and silver tiers (2026-10-27 03:06 UTC), beethoven-qa 10.0.0 everywhere (03:08 and 03:09 UTC), the Actions budget raised (03:10 UTC), the CNS thread's rules on the white paper, and the checkpoint words above. The approved grid counts and what was sent are in the restart page's section 3, which holds over MEMORY.md's older "Grid counts".

## 5. The first prompt for the next project

The restart page's section 1 carries it, and that copy holds if the two ever differ; this is the same text as of the pull request that added section 0 to both pages, kept here so the folder stands on its own:

```
You are picking up the "symphony" project from an earlier project, perhaps on another Claude account. First read docs/research/handoff-2026-10-27-checkpoint-4.md in OpenSpineConsortium/symphony-template on main, section 0 first: it is my priority and it overrides the rest of that page. Then, in order:
1. Write this project's instructions yourself: section 0 of the checkpoint-4 page at the very top; then section 2 of symphony-template's docs/research/handoff-2026-10-25.md, verbatim, with its line "No API key or Claude credential anywhere." replaced by the key rule in that page's section 0, and the goal line of its section 11, step 3; then the standing rules of section 4 of the checkpoint-4 page (not its one-off decisions of 2026-10-27). Attach OpenSpineConsortium/FleXray, OpenSpineConsortium/bordercall, OpenSpineConsortium/hpcworker and OpenSpineConsortium/openspineconsortium.github.io with add_repo, and the other repositories the Repos line of that section 2 lists when a thread needs one.
2. Read SchwingNet's docs/checkpoints/2026-10-27-morning/README.md on main, section 0 first, and write into this project's memory whatever in its project-memory/ folder still holds.
3. Start one thread, for the first item of section 0 alone: fleshing out Panjabi in bordercall, told to read section 0 of both pages, then bordercall's README.md and TODO.md, item P. Start no other thread and restart none of section 2's threads until I say otherwise. When I do, the second item of section 0 comes next, and section 2's threads come back only on my word.
Send nothing to the grid while the first item is the work, since it needs none; after that, send only the counts section 3 records as approved, each word once and only after reading the grid's status record, and ask me for any other count once, as a decision card. Never give me a step that only moves or edits text. When I answer idk, take the option you recommend. Do not copy anything from SchwingNet or bordercall into a public place, and put no career material in git.
```
