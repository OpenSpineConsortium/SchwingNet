# Project memory (symphony_3, continuing symphony_2)

Handoff index: SchwingNet docs/checkpoints/2026-10-29-final/symphony-2/README.md (on PR #491 branch until merged). symphony_4 threads: docs/checkpoints/2026-10-29-final/README.md.

## OVERRIDE of rule 4 (greg, 2026-10-30 16:59 UTC)
greg: "stop asking me every time you submit a job to the grid and stop making it a big deal." Threads no longer ask greg's word or a job count before each grid job, rerun, or gate allowance. Submit reasonable jobs within the thread's agreed work and just report them. Size rule and common sense still apply.

## memory/MEMORY.md (verbatim)
# The owner's standing rules, as of 2026-10-29

- [owner-rules.md](owner-rules.md): the eight rules every thread of symphony_2 works under.

## memory/owner-rules.md (verbatim)
The owner's standing rules for every thread, gathered on 2026-10-29 for the next account.

1. Never run archived code (bordercall archive/ and the like). Read it for reference only.
2. Test the PyMC and JAX code, and whatever else a change touches, before pushing.
3. Start only the threads the owner names.
4. Every grid job needs the owner's word and the number of jobs, and the size rule still applies. (SUPERSEDED 2026-10-30 16:59 UTC, see override above.)
5. Reports are plots with short notes on how to read them. Never a wall of text.
6. The CTSpinoPelvic1K cross-check is dropped for good.
7. Morphometry phantoms are deferred. Evaluate on real spines.
8. The auto-anatomist's network is a swappable block, and a dummy privileged-information probe model runs first.

- [populations-kept-separate.md](populations-kept-separate.md): greg's rule of 2026-10-29: populations stay separate strata (by author, then sex, race and the like), predictions are meta-analysis style, no large rebenchmark while the populations are volatile; PR 38 holds the predictor side, PR 43 the population register.

## greg's preferences (2026-10-30)
- greg is an ML specialist, not a biostatistician. Present results in Bayesian/ML terms (posteriors, calibration, held-out accuracy, and the like) in a CS-friendly report. Biostat-style plots can stay as a secondary appendix.
- Pick methods by held-out predictive performance with statistical validity; biological realism is not required.
- Talk plainly and say what to do next.
- Gold tier 3 annealer training on the grid is the top goal; start with a fully latent-space approach (his morphometrics code's state is uncertain).
- Demos don't need to be flawless; don't over-review quick work.

## Deferred to the next account (greg, 2026-10-30 03:26 UTC, low on tokens)
- PR 43 (bordercall): merge as it stands.
- Covariate work (covariate effects; predicting covariates from measurements and back, on within-cohort data such as VerSe's 355 patients with age and sex) and PR 43's full naming rerun: do on the next account.
- Yadav 2020 is kept: dropping it made held-out loss worse (PR 38).
- Open question to greg: whether to start a thread integrating the covariate work into bordercall naming, SchwingNet, the CNS talk and the provisional.

- [greg-2d-landmark-identifiability.md](greg-2d-landmark-identifiability.md): greg, 2026-10-30: 3-D landmarks projected onto 2-D synthetics with labels, 2-D functions of a landmark with its neighbours mapped back to the label, never into 3-D; section 14 of bordercall research_notes/latent-shape-prior-evaluation/ (branch claude/project-thread-2akdys).
- [threads-talk-to-each-other.md](threads-talk-to-each-other.md): greg's rule of 2026-10-30 02:37 UTC: parallel threads on shared files keep each other informed directly (file lists, who lands first, the interfaces needed).
- [rule-selection-result-2026-10-30.md](rule-selection-result-2026-10-30.md): the rule chosen by nested leave-one-population-out (bordercall PR 38, a02959f): temperature scaling T = 2 on the plain rule; the ML page https://claude.ai/artifact/13LehVRhuCUB4r4hNC2b3H beside the stats page; reports for greg go in ML terms.
- [greg-screen-arms-in-parallel.md](greg-screen-arms-in-parallel.md): greg, 2026-10-30 02:46 UTC: every arm a block of the Metaflow pipeline, screened in parallel on short 50-epoch runs before any long run; the design questions are the thread's to settle.
- [greg-job-count-latent-prior.md](greg-job-count-latent-prior.md): greg, 2026-10-30 03:20 UTC: 2 CPU, 2 GPU screen, 2 full run, plus 1 short GPU smoke for the latent-prior evaluation; the GPU smoke is the auto-anatomist thread's gold3_latent_smoke, counted once; that thread's annealer screen (2 jobs) has greg's separate yes of 2026-10-30 08:56 UTC; nothing sent until the flow pieces and PREREG exist; the figure is pipeline.html (artifact 8mfLZEEQupfs1wnGFKrASc).
- [greg-patient-sex-is-known.md](greg-patient-sex-is-known.md): greg, 2026-10-30 03:45 UTC: the patient's sex is known at imaging time, so rules and priors condition on it as a given input; shape-to-sex is only a check.
- [latent-prior-test-reserve.md](latent-prior-test-reserve.md): the latent-prior evaluation's frozen test reserve and anomaly-aware parts (584 studies, 85 repeat units, at SchwingNet 3abc2fa; bordercall commit 74f93f6), the first run's 1,060 normal units, the anomaly families, and the annealer pool (982, then 801 confirmed, then 781 eligible).
- [greg-anomaly-aware-splits.md](greg-anomaly-aware-splits.md): greg, 2026-10-30 09:43 UTC: first runs use normal spines only; four lumbar, six lumbar, T13 and rib anomalies are split by family across test and train, never validation; 10:03 UTC: the full run adds the anomaly train part.
- [autoanatomist-screen-ready.md](autoanatomist-screen-ready.md): the screen is merged (SchwingNet 69371c2, bordercall a87e0b3, 2026-10-30 18:05 UTC); greg pre-approved (in the OR) that the session sends `autoanatomist gold3_latent_smoke`, then `autoanatomist gold3_latent_screen` once the smoke ends in exit 0; relays taught by hpcworker #54 and symphony-template #511, then the word `update`.
- [greg-one-session-resynthesizes.md](greg-one-session-resynthesizes.md): greg, 2026-10-30 14:39 UTC: every session finishes its own work and does not read other threads' PRs into its notes; one session he names then resynthesizes and plans.
- Resynthesis inputs (latent-prior planning thread, stopped 14:41 UTC, note at 926bbcd, PR 45 draft finished): PR 38 check() now lists measures_not_on_card (plan section 7 and pin 4801753 stale); PR 38 gold3 scores used the pre-PR-44 engine (job 40878978 at c656299): body/end-plate steps pass, disc and pedicle/canal steps fail (L5 pedicle width 27 mm vs 15 mm, transverse angle -17 deg vs +23 deg); PR 44 wall rework changes 3 of the 32 pool features, so stage 1 export waits for its merge and re-pin (PR 44 head moving, was a9f21fd); PRs 39 and 46 not yet read.
- [gold3-on-bounds-card.md](gold3-on-bounds-card.md): the gold tier 3 join (job 40878978) on the bounds card: steps fail on pedicles (pre-PR-44 engine) and discs (unexplained); reruns wait on greg; greg's 14:39 UTC rule to finish and stop.
- [demo-ask-2026-10-29.md](demo-ask-2026-10-29.md): greg's Colab demo of the anneal on a slider, with a test cell on new phantoms, is bordercall draft PR 48 (branch claude/project-thread-5hj0q5, head 1cb0e6d); link by SHA; GPU and sign-in untried; keep demo work quick.
- [greg-lambda-schedule-fep.md](greg-lambda-schedule-fep.md): greg, 2026-10-30 16:37 UTC: bidirectional or several lambdas from FEP (Lambda-ABF); answered with a figure; adaptive lambda is the best idea; greg chose at 16:52 UTC to build four arms (cyclic, adaptive, split rungs, mid-path restraint) for a second screen after the demo fix, the first screen frozen.
- [totalseg-complete-sent.md](totalseg-complete-sent.md): `totalseg complete` ran as job 40882547 (2026-10-30 15:55 UTC, at SchwingNet 2fe153f) and failed on all 37 studies (tools/profile.py shadows stdlib profile); greg gave one more GPU job for the fixed rerun at 16:49 UTC (TOTALSEG_RERUNS in grid/gate.sh); resend only to read the report.
- [pipeline-sandbox-2026-10-30.md](pipeline-sandbox-2026-10-30.md): greg's browser pipeline builder in SchwingNet (branch claude/project-thread-2akdys), preview https://claude.ai/artifact/EHEHEKDRVbYd4Pnr7zn6Zb; only experiment-route pipelines become requests; the grid side waits on his word.
