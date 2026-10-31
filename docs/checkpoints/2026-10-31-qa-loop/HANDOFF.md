# Handoff of 2026-10-31: the QA loop and its gold arm

Source: the thread "Build self-propelling QA Metaflow pipeline", claude.ai project symphony_3, on the owner's order of 2026-10-31 14:24 UTC to push every thread's state for another account and local work, no adversarial review. Confidential: it stays in SchwingNet, and the landmark and phantom direction stays private.

## 1. What exists

- The QA loop (merged on main before this handoff): QaloopFlow, flows/qaloop.py, tools/qaloop_round.py, tools/qaloop_gates.py, tools/qaloop_report.py, plans grid/qaloop/qa_smoke.json and qa_loop.json, the frozen docs/research/qa-loop/PREREG.md, the training watch (loss, held Dice and distance every check, insane answers stop the loop, training rests after 50 epochs with no gain), Metaflow cards pushed to the branch cards for the control panel's Pipelines tab. Where it stands: docs/research/qa-loop/README.md.
- The transformer kind qaloop_tx (plan qa_transformer, #529, merged) belongs to the thread "Try a transformer-based vertebra model"; it may be sent once the base smoke below ends in exit 0.
- The gold arm, on this branch and not yet on main: the kind qaloop_gold (QaloopGoldFlow, flows/qaloop_gold.py), the X-ray stage tools/gold_xray.py, three gates over gold tier 3 and gold tier 4 tier by tier (gold naming, gold span, gold presence), plans grid/qaloop/qa_gold_smoke.json and qa_gold.json, grid/qaloop_gold.sbatch and the word `qaloop qa_gold_smoke` / `qaloop qa_gold`, the frozen docs/research/qa-loop-gold/PREREG.md with DEVIATIONS.md items 1 to 3 and README.md. Also docs/research/spineps-fine-tuning-audit.md. The description for its pull request is gold-pr-body.md beside this file.

## 2. Branch and pull request

- Branch claude/project-thread-k5hy7k, pull request SchwingNet #530. It began as one change (QALOOP_PARTITION to `galhp,gmsap`, so a link takes whichever of the L40S or H200 cards frees first) and now carries the gold arm and this handoff on top. The partition list needs hpcworker #57 (framework 29) merged and the grid's copy updated (grid-accounts.yml job update) before any qaloop send; until then a send of the list may be refused by hpcworker.
- The board asked to bring main in (main at 9541284) and lists overlaps with #533, #416, #420 and #468 on grid/gate.sh, tests/test_gate.py and docs/research/README.md.
- Tests run in the container on this branch: tests/test_gold_xray.py (32), tests/test_qaloop_report.py (14) and the gold gate word test in tests/test_gate.py pass under /tmp's mfvenv (numpy, scipy, jax, nibabel, metaflow); run `bash scripts/check.sh` in a scratch copy before marking ready.

## 3. On the grid

- Chain 40903176: the base smoke `qaloop qa_smoke` at commit c6af8cd, one link, pending on galhp.
- Chain 40903197: the base loop `qaloop qa_loop` at commit e16ca41, links 40903197, 40903199, 40903201, 40903203, 40903205, 40903207, pending on galhp; Slurm's estimate was 01:00 on 1 November by the grid's clock.
- Both were queued before #530; once #530 and hpcworker #57 are in and the grid updated, cancel both (`cancel <job>` words) and send `qaloop qa_smoke` and `qaloop qa_loop` again so the links can take gmsap too. Reports: grid/logs/QALOOP-<plan>.md on the grid's checkout, every later send of the word prints it; runs under the gate's QALOOP_ROOT/<plan>/<chain>.
- Gold tier 4's records: /rs/rs_grp_oschome/go2432/gold4-totalseg/records.jsonl once the merge job 40902777 ends (the phantoms thread owns that run). `qaloop qa_gold` refuses until it exists; `qaloop qa_gold_smoke` uses stand-ins for a tier with no data.

## 4. The gold arm's review: what is fixed and what is open

A review of the gold arm on 2026-10-31 found eight things. Fixed on this branch: (1) a level whose body the oracle placed in part (two of six real L5s missing the two back-wall points) counted as read: now unread and counted, DEVIATIONS.md item 3, with a test that fails without it; (7) the report said every tier's CTs were found under the data root: now it names each tier's source; (8) the gate word did not check that the masks sit in the plan's Vertebrae folders: it does now, tested. Open, not verified further (the checkers ran out of the account's limit):

- (2, medium) Gold span asks cells with no anchor and with the bottom anchor, but a tier whose held-out runs give no bottom-anchored cell is judged on its no-anchor cells alone (tools/qaloop_round.py gold_gates; tools/qaloop_gates.py fingerprint_gate reports missing only when the arm has no cell). PREREG section 4's "as an arm the fingerprint's gate asks with no cell does" reads as arm level, so the code may be the frozen rule; at least the result should name the anchors it judged and the report say when the bottom anchor had none. Making it missing per anchor would likely stop the smoke: of its two held-out gold 3 persons one has L5 unread, the other gave 2 anchored runs at 8 frames a view and the smoke draws 2.
- (3, medium) The guard that keeps one person out of both tiers is an exact string match (tools/gold_xray.py cases_for, gold4_cases); data/splits/aliases.json declares no aliases. Check whether gold tier 4's records can hold an ENHANCE.PET person spelled otherwise (tools/gold3_census.py near 707 names PETCT_; tools/gold4_totalseg_grid.py forms person_key near 314).
- (4, low-medium) Gold presence whose held-out radiographs all read NaN fails instead of lacking its data (gold_gates' gold_presence branch). Fix in the gold branch only: no finite frame mean means missing. The base loop's presence gate behaves the same on real frames and is frozen under its own PREREG.
- (5, low) frozen_cases (tools/qaloop_round.py) chooses the case list afresh when the kept file cannot be read; it should do so only when there is no file, and stop the round otherwise.
- (6, low) The gold pools in round 0 use the plan's workers, not measured memory; run_pool retries with fewer workers when one is killed.

## 5. Next steps, in order

1. Merge main into the branch, run check.sh, fix what it finds.
2. hpcworker #57: re-run its checks, merge on green; then fill #530's body from gold-pr-body.md with the partition change, the review summary of section 4 as its "## Adversarial review" section, mark ready, merge on green; then grid-accounts.yml job update.
3. Cancel and resend the base smoke and loop (section 3). Tell the transformer thread, or send `qaloop qa_transformer`, once the smoke ends in exit 0.
4. Decide and fix findings 2 to 6, then send `qaloop qa_gold_smoke`; send `qaloop qa_gold` only after the smoke ends in exit 0 and gold tier 4's records are final.
5. Not built: warping gold CTs onto columns drawn from the latent prior (needs its own design and PREREG); the NMDID rolling pipeline waits on the owner's word.

## 6. Nothing left elsewhere

The six ENHANCE.PET CTs read in the container lived in the session's scratch space, were never committed and are not needed: the grid holds the release under the data root and the smoke reads it there. The scratch probe scripts measured only what DEVIATIONS.md and README.md record.
