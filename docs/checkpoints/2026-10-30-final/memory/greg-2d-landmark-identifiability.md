---
name: greg-2d-landmark-identifiability
description: greg's direction of 2026-10-30 02:33 to 02:41 UTC: 3-D landmarks projected onto 2-D synthetics with their labels (forward), 2-D functions of a landmark with its neighbours mapped to the original label (backward), never back into 3-D
metadata:
  type: project
---

greg, 2026-10-30 (thread "Plan evaluating latent shape priors against explainable metrics"): 02:33 UTC "placing landmarks on a 2d xray which can be operated on in 2d space ... let you classify the seemingly flattened flat xrays according to higher dimensional properties"; 02:39 UTC "find landmarks which exist in 2d which when operated on with other nearby landmarks uniquely identify the vertebra bearing them"; 02:41 UTC "use those landmarks in 3d projected onto 2d synthetics to figure this out, like a forward backward mapping, landmarks projected from 3d to 2d and 2d landmarks projected from 2d to the original label, not back into 3d".

**Why:** the goal is level identification on fluoroscopy with human-understandable features; the gold tier 3 CTs with the engine's exported line ends plus project.py give labelled 2-D landmark sets with no radiograph, so the search for identifying 2-D functions can run before any real film is read.

**How to apply:** section 14 of bordercall research_notes/latent-shape-prior-evaluation/README.md (branch claude/project-thread-2akdys): forward projection of named, labelled ends; a forward selection over 2-D functions of a landmark with its neighbours, scored by named right under the exact rule and a discriminative classifier, leave-persons-out, per rib class; the output a ranked list of landmarks and functions, no 3-D reconstruction, no network. Not started; needs project.py's camera, the view=2d block and the stage 1 export keeping every end's name and label. See [[owner-rules]].
