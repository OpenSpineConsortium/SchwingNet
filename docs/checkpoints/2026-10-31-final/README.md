# Final handoff of 2026-10-31: the project symphony_3 moves to a local Claude Code session

Source: the thread "Hand off project for local continuation", claude.ai project symphony_3, on the owner's order of 2026-10-31 14:24 UTC ("push all threads states to git for another account to continue ... make sure no files are left behind ... I plan on running this project locally from now on"). It is the entry point for the next account and builds on docs/checkpoints/2026-10-30-final/README.md; where they differ, this file holds. Confidential: it stays in this private repository. No secret, token or credential is in it. No adversarial review was run, on the owner's word.

## 0. Read this first

1. This file, then [memory/MEMORY.md](memory/MEMORY.md) (the claude.ai project memory, every linked fact file beside it), then the handoff of the piece of work you pick up (section 2).
2. Clone the four private repositories side by side: OpenSpineConsortium/SchwingNet, bordercall, symphony-template and spine-program. Each has a CLAUDE.md with a "Continuing locally" section.
3. The owner's standing rules (memory/): merge your own pull request once CI is green, never wait for him (greg-merges-without-asking.md); grid jobs need no word (grid-use-not-restricted.md), the size rule holds; nothing public, sign nothing on the patent (provisional-patent-filed-2026-10-30.md); no usage credits; never run archived code; test before pushing; be frugal with tokens.
4. GitHub Actions minutes were reloaded on 2026-10-31; the billing failure that refused every job from about 06:20 to 14:00 UTC is over, so the grid words through symphony-template's grid-accounts.yml run again. Locally, the owner can also ssh to the grid and run `cd ~/SchwingNet && git pull && bash grid/gate.sh <word>` (the login node runs only bash and Slurm submission; every computation is a job).

## 1. The owner's words that set this handoff

- 2026-10-31 04:18 UTC, going to sleep: full authority to push, merge and decide; training running in the Metaflow pipeline with loss tracking, sanity checks, continue only while improving (memory/training-runs-continue-only-on-progress.md).
- 14:24 UTC: the order quoted above. 14:40 UTC: be frugal, finish the handoffs.

## 2. The threads and where each stands

Every thread hit the account's usage limit at about 09:44 UTC and was asked at 14:25 UTC to push its own handoff. Branches and PRs below are as of 14:45 UTC; a thread that pushed later adds its own checkpoint under docs/checkpoints/2026-10-31-<topic>/.

| thread | state | branch / PR | next step |
|---|---|---|---|
| Resynthesize morphometry and run the reruns | all three reruns done, exit 0, code stamp 1cee7ea83e4c28db: enhance 40900765 (1,597 studies), verse 40902026 (VerSe 374, TotalSegmentator 159), covariates 40902924. New rows /rs/rs_grp_oschome/go2432/morphometry/<set>/, old rows under kept/<old job>/. No jobs running | SchwingNet #532 (claude/project-thread-3gegnw): docs/checkpoints/2026-10-31-morphometry-reruns/HANDOFF.md | plot old rows against new (grid job); refit the correlation prior on the new rows |
| Continue Bayesian synthetic validation (gold tier 3 completion) | done: #505, #510 merged; bounds card rescored, bordercall #66 merged (TotalSegmentator passes 0.91; autoPET 0.87, 4 steps short; L5 pedicle read for only 86 autoPET adults; no pedicle sagittal angle on the new engine) | none open | republish the ML page with the new numbers; fix the two engine gaps |
| Finish the auto-anatomist screen | first screen (40888943, join 40888945): exit 0, no arm beats the null. Second smoke 40900847 exit 0. Second screen 40902102: 10 of 12 trials done at 05:30 UTC, last two (restraint) waited for a galhp card; report not read | bordercall #48, SchwingNet #506 merged; the thread was writing its handoff at 14:25 UTC | `autoanatomist gold3_latent_screen2` status, read the report, record the verdict |
| Train on randomized spine phantoms (gold 4, X-ray plan, prior) | gold 4 TotalSegmentator array 40902775, merge 40902777 (579 of at most 1,328 CTs done by 05:19, none failed); X-ray plan filed as bordercall #67 with stages #68 to #75 and six owner decisions with defaults; prior refit (40903052) reproduced records/prior-2026-10-31; the measure part stays held | SchwingNet #533 (claude/project-thread-dazoi0): docs/checkpoints/2026-10-31-gold4-xray-prior/HANDOFF.md; the prior check is specified in docs/research/gold3-prior-check/ (SPEC.md, READING.md), not built | send `totalseg gold4` to read the report (records at /rs/rs_grp_oschome/go2432/gold4-totalseg/records.jsonl); build grid/prior/prior_check.py from SPEC.md, freeze READING.md, send `morphometry prior`; stage 0 (#68) can start; work bordercall #67 |
| Build self-propelling QA Metaflow pipeline | gold arm built (tools/gold_xray.py, QaloopGoldFlow), smoke on six real gold 3 CTs exit 0 locally; review finding 1 and 7 fixed, findings 2 to 6 under check; QA smoke chain 40903176 queued on galhp | SchwingNet #530 draft (claude/project-thread-k5hy7k); the gold arm was committed locally on that thread, pushed only if the thread reached it after 14:25 | merge hpcworker #57 and #530; resend the QA loop; push and merge the gold PR; send `qaloop qa_gold_smoke` |
| Try a transformer-based vertebra model | TransUNet and UNETR in the auto-anatomist (bordercall #65), plan qa_transformer as kind qaloop_tx (SchwingNet #529), all merged | none open | after the QA smoke ends 0, send `qaloop qa_transformer` (memory/qaloop-transformer-plan.md) |
| Prune unused grid datasets | rounds 1 to 4 done, about 7.76 TB freed; last job retire 40903280 (idc_ldct 863 GB, medpelvis3d 31 GB) sent 05:50 UTC, result not read | none open; records in project-files/grid-pruning/ | read 40903280's result with `status`; summary to the owner |
| Fetch Radiopaedia fluoroscopy under licence | site refuses scripts (406); allowlist request sent to license@radiopaedia.org 02:21 UTC; import tool for hand-saved cases merged (#517) | none open | wait for Radiopaedia's answer or the owner's zip of saved cases (memory/radiopaedia-licence.md) |
| Resolved earlier: Resume from final checkpoint; Finish pipeline sandbox and latent-prior plan (#504 merged); Explain the vertebral level patent email; Catalogue online whole-spine CT data (#512); Recheck TCIA whole-spine collections; Remove owner approval from PR merges (#524, symphony-template #513, spine-program #245) | done | none | none |

Other open pull requests, older and not driven by any live thread: SchwingNet #468 (realism edit), #420 (gold and silver tiers), #416 (textbook chapter 36); bordercall #42 (README rewrite); symphony-template #500 (tiers note). Leave them as drafts unless the owner picks one up.

## 3. What is on the grid

- Gold 4 TotalSegmentator: array 40902775, merge 40902777, /rs/rs_grp_oschome/go2432/gold4-totalseg/ (PREREG docs/research/gold4-totalseg/).
- Auto-anatomist second screen 40902102 (galhp).
- QA smoke chain 40903176 (galhp), state unknown.
- Prune retire 40903280.
- Morphometry: nothing running; rows under /rs/rs_grp_oschome/go2432/morphometry/.
- Read everything at once with the word `status` (grid-accounts.yml, job=schwingnet-status; answer on symphony-template branch grid at logs/job-<job>.json), or on the grid with `bash ~/SchwingNet/grid/gate.sh status`.

## 4. What else is here

- memory/: the claude.ai project memory of 2026-10-31 14:25 UTC, MEMORY.md and 19 fact files, verbatim.
- project-files/: the project's shared folder: grid-pruning/, nmdid/ (the NMDID request), patent-ownership/ (conception timeline), and patent-ownership/ is confidential: never public, sign nothing. The five uploads of the shared folder are not in git, since beethoven-qa's security scan cannot read binary files: the provisional filing 66174-0372 (ADS, coversheet, drawings, application .docx; the owner holds it from WSU's e-mail of 2026-10-30), Meng et al. 2020 'Learning a Statistical Full Spine Model from Partial Observations', the Scientific Data descriptor 'Dataset of Finite Element Models of Normal and Deformed Thoracolumbar Spine' with its virtual cohort supplement (.docx), and Frontiers in Bioengineering 2024, doi 10.3389/fbioe.2024.1384599. The papers are public and fetched again from their publishers.

## 5. A first prompt for the local session

"Read SchwingNet docs/checkpoints/2026-10-31-final/README.md and memory/MEMORY.md beside it, and the CLAUDE.md of each of the four repositories. Then run the grid word status and read the four outstanding results: the gold 4 TotalSegmentator merge 40902777, the auto-anatomist second screen 40902102, the QA smoke 40903176 and the prune job 40903280. Report them to me in five lines, then continue section 2's next steps in order, merging each pull request yourself once CI is green. Be frugal: no subagents, no adversarial review unless I ask."
