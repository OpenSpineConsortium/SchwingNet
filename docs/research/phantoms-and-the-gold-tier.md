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
