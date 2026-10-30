# Pre-registration: the auto-anatomist's second screen on gold tier 3 CTs

Covers: gold3_latent_smoke2=9a3ccee993db5c9783a181bb0b1125a5da7e98090be543be66d35dddde726637, gold3_latent_screen2=bb1f0ad181dd9c7b455af6ce99ae312da28a86d799efe6340cf8cc2d171fb1f1

Source: the thread "Finish the auto-anatomist screen", 2026-10-30, carrying on the thread "Restart the auto-anatomist probe" (docs/checkpoints/2026-10-30-final/autoanatomist/HANDOFF.md, section 4), on the owner's choice of 16:52 UTC that day, "Build 4 arms after the demo" (four changes to the anneal as blocks with tests, and a frozen plan for a second screen, the first screen frozen), his word of 18:05 UTC for whatever a training run on gold tier 3 needs, and his rule of 16:59 UTC that a thread sends the grid jobs of its agreed work without asking each time. The protocol is the Lab Recipe (artifacts/the-lab-recipe-1t2gvp/index.md, "Pre-register and freeze") and the owner's rule of 2026-10-29 that every deep learning job on the grid runs on a launched flow under a frozen pre-registration. Label: confidential-method.

This file is frozen. It is the design the second screen runs under, written before any trial of it was sent and before any number of the first screen was read. It is a kind of its own, autoanatomist2 (flows/registry.txt, flows/autoanatomist2.py, grid/autoanatomist2.sbatch), since the first screen's pre-registration, docs/research/autoanatomist-screen/PREREG.md, is frozen at sha256 29c846c25a46adc19b082a08ef350a8fbf71d810db62b043b55a5873942359a9 and is never edited. Sections 1 to 6 below adopt that file's sections of the same number, by that sha256, except where they and section 8 say otherwise; section 8 is what is new. Its two plans, grid/screens/gold3_latent_smoke2.json and grid/screens/gold3_latent_screen2.json, are covered by their bytes on the line above, so a plan written again is another design. Every departure after the freeze goes in DEVIATIONS.md beside this file, dated, with its reason.

## 1. The question

The network, its objective and its anneal are the first screen's (its section 1). The question here: on real CTs, does a change to the anneal outline vertebrae from the CT alone better than lambda_then_w, the first screen's lambda-then-w anneal, trained in this screen at the same commit? The four changes are section 8's. The screen answers only by which arms pass the bar of section 4; it ranks no arm against another, and an arm that passes goes on to a longer run under a pre-registration of its own.

## 2. Population and inputs

The first screen's section 2, adopted whole: the same rows, taken from the first screen's committed plans (gold3_latent_smoke2 takes gold3_latent_smoke's 3 training and 1 validation persons, gold3_latent_screen2 takes gold3_latent_screen's 96 and 24; tools/autoanatomist_plan.py, rows_of), the same rule, test lists and units of probable repeat scans, which the flow checks again, the same levels and crops, and the same fixed words, float32 in full and environment. The one difference is the code: the vendored package at grid/autoanatomist/ is the bordercall commit that carries the four arms (bordercall PR 48), as grid/autoanatomist/VENDORED records it by every file's sha256, where the first screen's was afe1952.

## 3. The measurements

The first screen's section 3, adopted whole: the readings, the primary measure distance_mm at the last reading, the measures reported beside it and the step's own time.

## 4. The hypotheses and their bars

The arms are section 8's, each at seeds 1 and 2, twelve trials of 50 epochs (2,400 steps), with lambda_then_w as the null every other arm is read against. For each of cyclic, adaptive, overlapping and restraint, H: it beats lambda_then_w. ct_only, the first screen's null under a name of its own, is read against lambda_then_w the same way, and its pass would say the CT branch alone ends below the anneal. The bar is the first screen's, schwingnet.autoanatomist_screen.decide: an arm beats the null when every one of its seeds' final validation distance_mm is below every one of the null's; with two seeds a side, an arm no different passes by chance at most one time in six. Five arms are read against one null, so a chance pass of some arm is likely: a pass selects an arm for a longer run under a pre-registration of its own and is never reported as an effect.

The second smoke (gold3_latent_smoke2) runs the new words' code on a card and times a crop; nothing it measures is read as a result, and it answers no hypothesis (section 8).

## 5. What counts as failure

The first screen's section 5, adopted whole for every trial and join of this screen, with the order of sends set here: the second smoke is sent only once the first screen's report (logs/AUTOANATOMIST-gold3_latent_screen.md) ends in exit 0, so the first screen's verdict stands before any trial of this one runs, and the second screen only once the second smoke's report ends in exit 0 (AUTOANATOMIST_AFTER in grid/gate.sh). A second smoke whose join reports any failed trial stops the second screen until the cause is fixed.

## 6. The analysis plan

The first screen's section 6, adopted whole, with its known limits, which hold here too; the join, the record and the report are the first screen's (tools/autoanatomist_join.py, flows/autoanatomist2.py, tools/report.py --study autoanatomist-screen, which restates this file for a chain whose record names its sha256). Section 8 adds the second screen's own known limits.

## 7. Freeze

`sha256sum PREREG.md > PREREG.md.sha256` in this folder, both committed with the two plans the Covers line names; the launcher refuses a run whose PREREG or plan moved (exit 90), and every part checks the hash on its node before it reads anything.

First frozen on 2026-10-30, before any job of the second screen was queued and before any number of the first screen was read.

## 8. The second screen

- The arms (gold3_latent_screen2): lambda_then_w, the first screen's lambda-then-w and here the arm every other is read against (its null); cyclic, lambda-then-w twice, each pass in half the steps, going back between the passes to lambda 0.5 and w 0.3; adaptive, w on lambda-then-w's clock and lambda moved every 20 steps from its span's start by the error's own slope on the batch just trained, never behind a floor that reaches lambda 1 a tenth of the steps after lambda's span ends; overlapping, lambda-then-w with each rung of the ladder over half of lambda, a quarter apart, so the target's fade, the blur and the threshold move together in places; restraint, lambda-then-w with an adaptive biasing force at weight 1 that holds the target vertebra's predicted volume, as a share of the crop, towards the clean mask's, scaled by (1 - cos 2 pi lambda) / 2, which is 0 where the mask is whole and where it is gone and greatest half way; and ct_only, the first screen's null under a name of its own, the CT branch alone with lambda 1, w 0 and the feature term's weight 0 throughout. Each new word changes nothing where it is not named (grid/autoanatomist/autoanatomist/README.md, "The second screen's arms") and runs at its default.
- The second smoke (gold3_latent_smoke2): lambda_then_w and the four changes to it, one seed, on the first smoke's three training CTs and one validation CT, 150 epochs (300 steps), five trials in series on one card, then the join. It answers no hypothesis.
- Every arm is read against the lambda_then_w trained in the same screen at the same commit, so no reading crosses commits or screens; the first screen's numbers are never pooled with these.

Known limits of the second screen, beside section 6's, stated before the run:
- The four words run at their defaults, chosen on phantoms in bordercall's tests and tuned on nothing here.
- Under objective=mask the restraint's variable is the target's volume share alone, since no measure is read.
- The adaptive schedule moves lambda by the batches a seed draws, so its path differs from seed to seed by design.
- The feature term of every annealed arm runs to the last step, as in the first screen's section 4, so wherever w stands at 0, in cyclic between its passes as at every arm's end, it distils from a mask branch that takes no gradient.
