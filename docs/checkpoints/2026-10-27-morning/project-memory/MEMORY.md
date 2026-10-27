# symphony (symphony_3 pickup, 2026-10-25 evening)  -  project memory

## OWNER'S PRIORITY FOR THE NEXT ACCOUNT (2026-10-27 05:48 UTC, in force until the owner says otherwise)
- Work on NOTHING except fleshing out Panjabi: extract every remaining measure and table from all three Panjabi papers, beyond what SPINEPS can measure, and test how more measures improve naming accuracy (top of bordercall TODO.md). Next after that: gold tier 1/2/3 data for segmentation-based empirical testing of the Bayesian generator. The audit thread was asked at 05:48 UTC to write this into the restart page. Steps: bordercall TODO.md item P (main 7015802); detail in [next-account-priority-panjabi](next-account-priority-panjabi.md).

## NEIGHBOUR-IDENTITY STUDY: DONE 2026-10-26 06:20 UTC (owner's absolute priority of 05:44 UTC)
- On bordercall main (17683b1, now under archive/): docs/NEIGHBOUR_IDENTITY_RESULTS.md. Neighbours alone name a vertebra 52% exact / 84% within one; t13 worst (count-convention shift); 0.018 ms per window; both planes beat AP by 8-9 points.
- Field-of-view arm (441457a): 37% one body to 83.5% at nine (99% within one); edge-names artefact documented, fix left for next run.
- Level identifiability (docs/LEVEL_IDENTIFIABILITY_RESULTS.md): best-named C7, T1; T12 near the bottom; levers: field width, both planes, size known, pedicle rows.
- Exact identification (00f969f, docs/EXACT_IDENTIFICATION_RESULTS.md): Bayes rule is the ceiling; exact 47/73/86/96/99.7% from 1/3/5/9/15 bodies; names at 0.99 right 99.78% from 3; premise (table) is the weak point.
- Owner's rule (2026-10-26 06:31 UTC): NO arbitrary constraints on naming; target's own measures permitted; a series of solutions, each reported per phenotype.
- Synthetic phenotypes: four_lumbar, six_lumbar, t13, lumbar_rib, no_rib_t12 (50/50 blend).

## CHECKPOINT 2026-10-27 04:47 UTC (owner's word: "checkpoint all sessions ... write a handoff so a new account can pick up")
- Restart page for any account: symphony-template docs/research/handoff-2026-10-27-checkpoint-4.md (#501, merged 05:24 UTC as ba7341a), with the first prompt for a new project; it replaces checkpoint-3. Confidential companion: SchwingNet docs/checkpoints/2026-10-27-morning/ (#421 and #422, merged 05:23 UTC as 77b10b3). Anomaly route handoff anomaly-route.md there; see [[anomaly-route-thread-state]].
- Review findings: anomaly timing job 40785227 FAILED (exit 1, report unread), so pack waits; no realism grid word passes hpcworker's gate yet (JOBS_RE lacks realism: hpcworker PR, then `update`); `update` needed only before the bordercall word.
- Owner's open steps (from checkpoint-3, still open): (1) textbook door: GitHub App "SchwingNet door", custom connector named GitHub, then `git pull` and `python -X utf8 tools/textbook_publish.py local --url https://claude.ai/artifact/XYY2CdsjvyRfxQfYq2EkkV`; (2) accept FLUX licence at https://huggingface.co/black-forest-labs/FLUX.2-klein-9B; (3) new account: Microsoft 365 connector; (4) TTO check before showing junction slides. Only item not in git: the owner's uploaded FleXray paper source.

## Owner and goal
- Owner: greg (GitHub Gregory-Schwing-MD-PhD). Lab objective: SchwingNet issue #391, FleXray audit first (items 6-11), then integration (12-14); item 15 (licence/patent) is the owner's decision, never a blocker.
- Owner is impatient with questions: on "idk" take the recommended option; ask only where a rule needs the owner's own word and count (grid job, fetch, training, release), once, as a decision card. Never give the owner a step that only moves or edits text. Owner steps: numbered, exact link, what to click.
- Ground truth (2026-10-26 00:16 UTC): CTSpinoPelvic1K CTs NOT trusted; only full-spine C2-to-pelvis CTs count.
- Segmentation (00:17/00:26 UTC): SPINEPS for production, reuse existing grid masks; MOOSE only replicating FleXray; segmenter is a configurable block (DRR thread owns it); label schemes handled correctly.
- Figures look like Benzel's, reproducible code. No OneDrive uploads; figures live in bordercall.
- Textbook: no owner step ever; the reader loads live, "like a front door into a repo".
- Every restarted thread reads: the newest checkpoint page; its own handoff; SchwingNet board (`git fetch origin +refs/heads/board:refs/remotes/origin/board && git show origin/board:STATE.md`). symphony-template has NO board branch.

## Threads (all stopped at the 2026-10-27 04:47 checkpoint)
- Plan the FleXray audit for #391 (cmsg_014WUU19NHgHPhf7QetT9cbS4U5VtLZVXcLDjRSqWXkfxJ): writes restart pages; select ran (40785048); timing failed; corpus search: 14 cohorts, none open.
- Compare FleXray DRRs to real X-ray corpora (cmsg_014WUU19NHgHPhf7QetT9cbSBA775A5CPNAFT3bnoF53ko): see [[drr-comparison-grid-count]].
- Finish CNS slides with junction predictor (cmsg_014WUU19NHgHPhf7QetT9cbSNtWnkmT2ipWai44F9gCLyG): see [[cns-white-paper-thread-state]] and [[bordercall-layout-after-archive]]. Grid bordercall pilot approved, unsent.
- Let readers open the live front door (cmsg_014WUU19NHgHPhf7QetT9cbSVnV3YqVLU3sQSTQATH5g98): see [textbook-reader-this-project](textbook-reader-this-project.md).
- Finetune Flux Realism for X-rays (cmsg_014WUU19NHgHPhf7QetT9cbSAe6wnnSqEmg92SHjFbih8K): see [[flux-realism-thread-state]].
- Sort the corpus into gold and silver tiers (cmsg_014WUU19NHgHPhf7QetT9cbS3GeNy2kWCf2yhSrDLkVBnG): see [[corpus-tiers-census]].
- Add fetch size readers for #163: DONE, resolved.

## Standing rules (beyond project instructions)
- Never copy SchwingNet content to a public place; bordercall under the same rule until the filing; no career material in git.
- Merge PRs once green on standing permission; SchwingNet requires check, gate, standards, owner-ok. Mark a SchwingNet PR ready in a call of its own.
- SchwingNet check.sh only in a throwaway copy; pre-push gate can take 30 min, refuses untracked files.
- Grid: read logs/job-schwingnet-status.json on symphony-template branch grid before any send; never send twice for one read.
- Cloud sessions: Workflow agents capped at 2; arxiv.org blocked; FleXray paper source uploaded (file_01Q7GHf6Q9QVnLhFFJuA34Pa).
- docs.yml builds only when the owner starts it.

## Grid counts
- APPROVED: anomaly route 15 jobs (select done; timing failed; then pack, render, figure, tune, eval; f1..f4 later); #391 item 13 test 1 GPU + 1 CPU; two benchmark reruns unsent; bordercall 2 CPU (pilot, then full); DRR comparison 2 fetches (done) + 2 GPU; Flux Realism 5 fetches + 4 GPU (unsent). SPINEPS production array NOT approved.
- WAITING (ask once as decision card): rest of #391 audit: 1 fetch, 5 GPU, 3 CPU; census tiers 1 CPU.

## Facts threads rely on
- FleXray fork = upstream 1.0.2: 2D UNet 256 px, 61 channels, no L6/T13; FLUX.2 edit not in repo; code MIT, weights/FluXray CC BY-NC 4.0. FluXray = 138,063 edited DRRs from 1,597 MOOSE-segmented ENHANCE.PET CTs x 90 poses.
- #391 answers: window = exposure field in bodies; sweep 0.5-4 in quarter steps; "the other one" = arXiv 2412.08020's 80 cadaver frames.
- SPINEPS on the grid: env `spineps` and /rs/rs_grp_oschome/go2432/envs/spineps212; models ~/spineps_models; spinesurg-ct-nnunet branch L6_Class run_spineps.sh. No rib mask.
- Outlook tag [XR/CT Imaging Research]; drafts only.

## Repos / paths
- Project repos: SchwingNet, bordercall, symphony-template. FleXray attached when needed.
- [anomaly-pack-stage-design](anomaly-pack-stage-design.md); [beethoven-qa-10-pyproject-by-key](beethoven-qa-10-pyproject-by-key.md); [actions-billing-block-2026-10-26](actions-billing-block-2026-10-26.md) (resolved); [corpus-tiers-census](corpus-tiers-census.md); [cns-white-paper-thread-state](cns-white-paper-thread-state.md); [bordercall-layout-after-archive](bordercall-layout-after-archive.md).
