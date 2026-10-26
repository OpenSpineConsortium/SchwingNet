---
name: flexray-fork-facts
description: What the FleXray fork (OpenSpineConsortium/FleXray, pip flexray 1.0.2) is and is not, verified from its code on 2026-10-25, for the #391 audit threads
metadata:
  type: project
  modified: 2026-10-25T20:05:21.905Z
---

Verified 2026-10-25 by parallel readers over /home/claude/flexray (the fork tracks upstream 1.0.2 with no code change of its own):

- One 2D UNet at 256 px, 61 sigmoid channels (60 structures + background); one channel per vertebra C1-L5 + sacrum; no vertebra_l6 or vertebra_t13 channel, and MOOSE/HANSeg drop them to background, so an L6 body was trained as a hard negative for every vertebra channel (CE and Dice).
- Training is 96 percent synthetic: online CT->DRR 0.585 (MOOSE 0.375), FluXray edited DRRs 0.375, four real radiograph sets of extremities at 0.01 each. DeepFluoro is evaluation only; no spine fluoroscopy set (no C-ArmLSpine) anywhere in its configs.
- DRR profile: nanodrr, alpha +-180, beta +-30, FOV 320-576 mm. fxr-render renders raw DRRs + masks without weights (MIT). The FLUX.2 realism edit and ONNX export are NOT in the repo.
- --init-from takes a local bundle dir (no network); --replace-head discards the whole 1x1 head, no row-wise copy; a model label must be in the protocol, so adding channels needs a new protocol YAML plus custom code. Real frames with masks for a few levels work through the partial-label route. WandB must be installed but offline/disabled works. One GPU, one process, no DDP. No hardware or duration statement anywhere.
- Licences: code MIT; weights CC BY-NC 4.0; FluXray CC BY-NC 4.0; redistributed real folders CC BY 4.0.

**Why:** every #391 audit thread (items 6-14) starts from these; re-reading the fork costs an hour of agents.
**How to apply:** cite the plan note symphony-template docs/research/flexray-audit-plan-2026-10-25.md and the confidential companion in SchwingNet docs/research/flexray-audit-companion.md; correct this file if the fork gains code changes. See [[symphony3-project-overview]].
