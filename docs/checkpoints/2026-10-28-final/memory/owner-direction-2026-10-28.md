---
name: owner-direction-2026-10-28
description: greg's direction of 2026-10-28 19:07-19:08 UTC, his own prompts verbatim - Bayesian morphometric rule, his 2,000 labelled CTs, a visualisable low-latency auto-anatomist, a segmentation degradation ladder to HU thresholding, survival through eDRR + Flux realism into fluoroscopy
metadata:
  type: project
---

greg, thread "Synthesize project status across accounts", 2026-10-28: 19:07 UTC a Google AI Mode share link (sessions cannot read it: a robot check; never scrape), "see the direction i want to go in the attached link"; 19:08 UTC he pasted the whole conversation. His own prompts, verbatim:
1. "how to go from a bayesian generator on synthetic data of per level spine vertebrae to a classifier which converts an instance segmentations of the spinal vertebra on a 3d ct to a semantic segmentation"
2. "the synethetic data is specifc morphometric dimensions that i dont have automatically converted into code"
3. "but some of these are too sophisticate measurements to simply program, i wanted a neural network to learn to make the measurements on a 3d semantically segmented spine"
4. "i have 2000 instances of spines with real-world training labels i just dont know or want to figure out how to best program makign the measurements on them"
5. "i dont want it to invent features, i know these features work in a bayesian generator appoach and i want to stay in the bayesian statistical domain"
6. "so the two absulte requriements is to be able to visualize what the learned autoanatomist thinks each measurement looks like on the 3d instance segmentation and that it is low latency"
7. "can you please formulate the problem such that it is a iterative decrease in the segmentation method sophistication starting a perfectly annotated and decreasing all the way to HU thresholding, with gradient based loss of information to show how the model trained to make the morphological measurements degrades in performance as less detail is provided in the underlying segmentation? the goal is for the segmentation method to transition into automatic deep learning free techniques which still providing enough context for teh bayesian network morphological measurement performance to survive degradation"
8. "assuming i possess a way to perfectly convert a 3d ct scan to the 2d fluoroscopic xray domain, propagating labels if they they exist in 3d, ensure the model(s) survives in this domain as well, this can either proceed as a parallel degradation process or a unified gradient backpropagation"
9. "no im using the enhanced drr followed by flux realism as my Dimensionality Projection Operator"
10. "i dont mind if training is high latency, i jsut care about inference"

The machine-written answers beside them proposed active shape models with fixed vertex landmarks and linear measurement heads, Viterbi/HMM sequence decoding, a five-tier degradation ladder, and an amortised encoder trained offline on eDRR+Flux images; their figures (1.2 mm, under 20 ms) are invented and the earlier work they name is unread. How each part sets against what exists: docs/research/project-status-2026-10-28.md, section 5 (three premises conflict with the record).

**Why:** this is how greg means his CT data and the synthetic rule to meet; the next threads are planned from it.
**How to apply:** "auto-anatomist" = the measurement maker; keep it Bayesian and interpretable, inference fast, training cost free. Related: [[clinical-reread]], [[item-p-state]], [[owner-science-rules]].
