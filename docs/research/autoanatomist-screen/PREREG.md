# Pre-registration: the auto-anatomist screen on gold tier 3 CTs

Covers: gold3_latent_smoke=ef107b9e47cedc8d7444df987129b976dda8948c117f358c2c9e8c8df680fd0f, gold3_latent_screen=d5f45f74beb10aac5d16dfb1ee75598416ebbdabd89c448f00e79b7726c0d3b9

Source: the thread "Restart the auto-anatomist probe", 2026-10-30, on the owner's words that day: "please just get me to a point where i am training on this gold tier 3 dataset on the grid and can start evaluating performance of the annealer", "start with one of the fully latent space approaches", every arm "a block" of the Metaflow pipeline evaluated "as many in parallel as possible on short 50 epoch runs", and his count of 03:20 UTC (two CPU, two GPU screen and two full-run jobs for the latent shape priors, plus one short GPU smoke, which this screen's smoke is, counted once); the protocol is the Lab Recipe (artifacts/the-lab-recipe-1t2gvp/index.md, "Pre-register and freeze") and the owner's rule of 2026-10-29 that every deep learning job on the grid runs on a launched flow under a frozen pre-registration. Label: confidential-method.

This file is frozen. It is the design the screen runs under, written before any trial was sent: on 2026-10-30 no job of the screen had been queued and no number of it read. Its two plans, grid/screens/gold3_latent_smoke.json and grid/screens/gold3_latent_screen.json, are covered by their bytes on the line above, so a plan written again is another design. Every departure after the freeze goes in DEVIATIONS.md beside this file, dated, with its reason.

## 1. The question

The auto-anatomist trains two encoders of one network, one reading a CT crop and one reading privileged channels (the target vertebra's mask and every vertebra's), fused as F = (1 - w) F_ct + w F_mask; under objective=mask its decoder gives the two masks back and a head names the level, so nothing is measured anywhere and the network's bottleneck is the latent a shape prior is fit on later (grid/autoanatomist/autoanatomist/README.md). The annealer takes the privileged channels down a ladder as lambda goes from 0 to 1, until they are a function of the CT alone, and hands the decoder from the mask branch to the CT branch as w goes from 1 to 0. The question: on real CTs, does a network trained with an anneal outline vertebrae from the CT alone better than the same network trained on the CT alone from its first step, and which placement of the two ramps does best?

## 2. Population and inputs

- Rows: ENHANCE.PET studies of the gold tier 3 store (data/gold3-ct/, docs/research/gold3-ct/README.md) that are normal, confirmed by their masks, allowed for training, held out of nothing and with their CT on the grid (tools/autoanatomist_plan.py, eligible). The CTs and label maps are the data root's aws_enhance_pet_ct and aws_enhance_pet_labels, read as they are.
- Persons and parts: a person is a study, and its part is the one data/splits/rule.json gives it (salt schwingnet-2026-10-21, validation share 0.1); no person on a list of schwingnet.autoanatomist_screen.TEST_LISTS is read, and the test part is never read (each plan's test: off). The flow refuses a plan whose rows leave the rule or stand on a test list.
- The screen's rows: the first 96 training persons and the first 24 validation persons by their own hash under the salt schwingnet-autoanatomist-subset-2026-10-30, one study each; the smoke's are the first 3 and the first 1 of the same order.
- Levels: C3 to L6 as ENHANCE.PET numbers them (labels 3 to 25), each level of a study one crop of 48 by 56 by 32 voxels at 2 mm about its mask's centroid with a fixed jitter per row; every other label (C1, C2, the sacrum, the hips) is taken out of the label map before the crop is cut, so the every-vertebra channel holds the named levels alone.
- The network: the vendored package at grid/autoanatomist/ (bordercall, VENDORED), residual-unet at its default widths, objective=mask, naming=off, the plans' fixed words; a trial's environment holds schwingnet.autoanatomist_screen.PINS and the trial refuses any other (exit 3).

## 3. The measurements

At each reading (every 5 epochs of the screen's 50, every 10 of the smoke's 150, and always after the last), every validation crop is read by the CT-only path, the decoder at w 0 with no mask (train.evaluate_masks): the mean symmetric surface distance of the target vertebra's mask in millimetres (a crop with no surface on either side counts as the crop's longest side, and the count of such crops is kept), the hard Dice of the target's mask, the centroid error in millimetres and the share of crops named right. The primary measure is the mean surface distance at the last reading, the plans' measure distance_mm; the others are reported beside it and decide nothing. Each trial also writes its training loss by epoch, the seconds per crop, its latents per crop and its saved session.

## 4. The hypotheses and their bars

Arms (the screen): lambda_then_w (lambda's ramp, then w's), joint (both over lambda's span), w_first (the spans swapped) and the null (schedule fixed, lambda 1 and w 0 throughout: the CT branch alone from the first step, the privileged channels never seen as anything but the CT), each at seeds 1 and 2, eight trials of 50 epochs. For each annealed arm, H: it beats the null. The bar is schwingnet.autoanatomist_screen.decide: an arm beats the null when every one of its seeds' final validation distance_mm is below every one of the null's. With two seeds a side, an arm no different from the null passes by chance one time in six (both of its two finals below both of the null's, of the six orders of four exchangeable values), so a pass selects an arm for a longer run under a pre-registration of its own, and is never itself reported as an effect.

The smoke (an anneal and the null, one seed, 3 training CTs and 1 validation CT, 150 epochs, two trials in series on one card, then the join) tests the code path on the grid and times a crop on a GPU; nothing it measures is read as a result, and it answers no hypothesis.

## 5. What counts as failure

A trial that writes no entry, or one that does not hold (schwingnet.autoanatomist_screen.entry_problems), is shown failed with its reason and never dropped; an arm with a failed trial on either side is undecided, not passed. The screen is sent only after the smoke's two trials and its join end in exit 0; a smoke whose join reports any failed trial stops the screen until the cause is fixed. A trial whose card JAX does not see stops before it trains (exit 4).

## 6. The analysis plan

The join (tools/autoanatomist_join.py) reads every trial's entry, writes DECISION.json with the rule, each arm's finals and its verdict, the curves of distance_mm at each reading per trial, the finals per arm, and a summary; the flow's end writes RECORD.json and the screen's CLAIM 2024 and REFORMS report (tools/report.py --study autoanatomist-screen). No number is tuned on the validation part beyond the decision above, and no other measure, reading or seed is chosen after the fact.

Known limits, stated before the run:
- The crops are centred on each level's true centroid, so the screen measures outlining and naming given where a vertebra is, never finding it.
- A person is a study: ENHANCE.PET's autoPET part holds 1,014 studies of 900 persons (docs/research/gold3-ct/README.md), and no record here matches its studies to persons, so one person's two scans can sit in training and in validation, and the validation figures may be kinder than a new person's would be.
- One population, ENHANCE.PET, and one network size; nothing is claimed beyond them, and populations stay separate strata.
- Each reading is a mean over every validation crop, all levels together; the by-level figures are kept in each trial's readings and decide nothing.

## 7. Freeze

`sha256sum PREREG.md > PREREG.md.sha256` in this folder, both committed with the two plans the Covers line names; the launcher refuses a run whose PREREG or plan moved (exit 90), and every part checks the hash on its node before it reads anything.
