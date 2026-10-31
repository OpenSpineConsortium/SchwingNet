---
name: xray-stage-flexray-chain
description: greg's 2026-10-31 01:40 UTC ask to chain FleXray after the shape decoder for a low-latency limited-FOV C-arm classifier, and the staged design recommended
metadata:
  type: project
  modified: 2026-10-31T01:41:35.634Z
---

2026-10-31 01:40 UTC, greg: chain FleXray into the latent shape model so it "decodes directly to X-ray", for his low-latency, limited field of view classifier (possibly Bayesian, open to non-Bayesian). The goal restated: fingerprints that reliably identify a vertebra in a C-arm-sized view, unambiguously and in real time, intraoperatively.

Recommended in the thread (01:4x UTC), no answer from greg yet:
- Train in stages, keep each differentiable, fine-tune end to end last.
- Stage 1: the shape encoder/decoder alone, on the gold tier with covariates, checked on held-out CTs.
- Stage 2: phantoms. A whole spine is drawn from the latent prior with its cross-level correlations, and a real gold tier CT is warped onto it (a mesh alone renders bone on black). It is rendered through FleXray at C-arm geometry and field sizes. Labels are exact, since nanodrr splits rays by label.
- Stage 3: the fast classifier is the only thing in the OR (the 97 ms budget).
- End to end only for (a) the classifier loss steering the sampler toward hard shapes and poses, and (b) render-and-compare when the fast posterior is ambiguous. From scratch it learns renderer artifacts: the DRR domain gap study tells every DRR set from real fluoroscopy, AUC lower bounds 0.82-1.00.
- Bayesian layer: a level posterior with the counting prior (T13/L6/LSTV odds) and the correlation prior. Phantoms with exact truth measure the smallest C-arm window that names a level unambiguously (the span test).

2026-10-31 01:43 UTC, greg asked whether the real annotated fluoroscopy should be kept for validation. Answered yes:
- Lock the test split by person before anything trains, and keep those people's CTs out of the shape model and the phantoms (a render inherits its CT's person).
- Take a separate validation slice by person, used only for checkpoint choice, posterior calibration and the "unsure" threshold, and the realism settings. Everything else is chosen on phantoms.
- No real frame in training at first. Fine-tune on a third person-disjoint slice only if the zero-shot validation score requires it.
- Spread the transitional cases across the splits and report them separately.
The frame counts are not yet read.

2026-10-31 09:37 UTC: the plan is filed in bordercall as #67 (the umbrella, no labels), stages 0 to 7 as its sub-issues #68 to #75, after two fact-check passes and a consistency pass. #67 ends with six owner decisions, each with the default the plan follows until greg answers: a hashed 0.3 test share added (salt not chosen); all three real L6 persons stay in test, transitional strata calibrated on phantoms; no model reads Radiopaedia; no stage 5 bar, so no smallest field is read; no fine-tune bar, so nothing is fine-tuned; render and compare offline only. Two points no body settles: whether the Surgio-B51 hold covers its SID and SOD (#70), and whether the automatic labeller counts as a first reader (#74).

**Why:** this is the path from [[phantom-templates-open-models]] and [[correlation-prior-2026-10-30]] to greg's ultimate goal (landmarks that uniquely identify each vertebra in 2D).

**How to apply:** work the plan from bordercall #67 (private; the #51 direction is not in the provisional); a stage is taken through its own sub-issue, and an owner decision changes #67 first. Nothing of it goes public.
