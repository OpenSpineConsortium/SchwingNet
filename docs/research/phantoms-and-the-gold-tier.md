# Phantoms against the gold tier

Source: the symphony_3 thread "Train on randomized spine phantoms", 2026-10-30; the Claude Doc
"Phantoms vs gold tier: assessment and design" (https://claude.ai/artifact/PskhpGyai4yih2vySRzeas).

greg asked whether training only on phantoms with known random parameters, with noise learnt from
real spines, beats training on the about 2,000 gold tier 3 CTs, whose rare anomaly classes are few
after stratification, and proposed keeping the gold tier for population priors with correlations
between levels. The answer of record:

- The correlation prior is the strongest part. The generator assumed its structure (two levels of
  one measure at 0.25, measures uncorrelated); the gold tier can estimate it. Built first, on greg's
  choice: docs/memory/the-correlation-prior.md.
- Phantoms alone add samples, not information about rare classes: a network trained only on draws
  of a model learns that model and cannot beat the rule that made it on rare classes; noise learnt
  from the gold tier is bounded by the same few cases (T13: 9 training units at the 0.2 share).
- bordercall autoanatomist/phantom.py draws no ribs, so T13, lumbar rib and no-rib-T12 phantoms differ
  only in their numbers, not in the anatomy the truth is read from.
- Real spines stay the only test: the latent-prior evaluation's frozen reserve of 584 studies.
- FleXray did not train on about 30 per cent real spine images: every spine label came from real CTs
  projected (47.5 per cent of batches rendered CT sets, 37.5 per cent FluXray), real radiographs were
  4 per cent and showed no spine, and the realism edit was worth at most 0.9 points on C-ArmLSpine
  (docs/research/flexray-audit-companion.md). Its lesson is real anatomy with synthetic variation.
- The record's evidence for a sim-to-real gap: a render-only detector found 71.67 per cent of bodies
  on real film against 99.14 per cent for a film-trained one.

The design left for later, once the prior stands: phantoms that carry the anomalies (ribs on the
primitives, or real normal masks deformed to drawn measures), realism fitted statistically first,
and a screen of real-only, phantom-only, phantom then real, and mixed batches, all scored on the
reserve.

Exact-label landmark phantoms (greg, 2026-10-30 23:21 and 23:30 UTC, same thread). To keep annotator
bias out, greg proposed building realistic vertebra phantoms from Panjabi's quantitative anatomy
(Spine, 1991 and 1992: cervical, thoracic and lumbar) and any open 3D vertebra with landmarks, with
measurement code that is exact by construction, then deforming them toward a mean spine or toward
training spines so a network learns the measurements on real spines without explicit landmarks. The
answer given, with references cited from memory and not yet checked: the closest working precedent is
SynthSeg (Billot 2023), trained only on synthetic images with exact labels and heavy appearance
randomisation; landmarks can also emerge from learnt deformation (VoxelMorph and atlas propagation,
Thewlis 2017, Jakab 2018) or from regressing shape-model parameters (DeepSSM, Bhalodia 2018); a
lumbar statistical shape model is Rasoulian 2013, and BodyParts3D carries an open vertebra mesh. The
flaws: the bias moves into the code's definitions rather than vanishing (explicit and fixed, not
zero); Panjabi gives per-level means and spreads of a small cadaver sample with no correlation, which
is what the gold tier prior adds; labels stay exact only for the phantom or a warp toward the mean,
since a warp onto a real spine makes its landmarks registration estimates; and neither source has
transitional spines or (in our phantom) ribs. The design greg accepted: a parametric vertebra from
Panjabi's landmarks or an open mesh, its parameters never drawn independently but jointly from the
fitted level and measure correlations (correlation.draw_field), rendered with randomised appearance,
the network trained to give the measurements, and checked on real spines with no annotator:
repeat-scan agreement, left-right agreement and the population spread against Panjabi and the gold
tier.

For greg's end goal, naming each vertebra in a 2D fluoroscopic shot of any field of view, one
vertebra's landmarks do not name its level, since neighbours look alike; the information is in how a
visible run changes from level to level, which the correlated prior scores for every placement of the
run, with between-person scale largely cancelling. How sharp that score is has not been measured, and
an extra or missing segment breaks any shape match without a reference bone in view. The additions
proposed: anchors when visible (sacrum, last rib, iliac crests), stitching successive shots so the
field grows to reach an anchor, and registration to a preoperative CT where one exists (LevelCheck,
Siewerdsen's group). The first measurement is the shape-sequence score on phantoms through the
bordercall chain's level posterior.
