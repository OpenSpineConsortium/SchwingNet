---
name: paired-ct-fluoro-exception
description: greg 2026-10-31: paired CT-to-fluoro/X-ray data is the only exception to his full-spine (C2 to sacrum) rule; never prune it
metadata:
  type: feedback
  modified: 2026-10-31T01:14:07.794Z
---

On 2026-10-31 at 01:13 UTC greg wrote: "paired CT to fluoro data is the only exception to my full spine rule". He said it while checking the grid pruning list, worried that COBRA (cobra2026, CBCT projections) was on it. It wasn't.

**Why:** paired CT and fluoroscopy data is scarce and drives the 2D/3D work, even when the CT is not a full spine.

**How to apply:** when choosing datasets to keep, delete or fetch, keep every CT paired with fluoroscopy or X-ray (COBRA, DeepFluoro, C-ArmLSpine, Ljubljana 2D/3D, PolyPose and similar) whatever its field of view. Every other CT must show C2 to the sacrum to count. The pruning of 2026-10-31 (spine-datasets#377, SchwingNet#513) removed only unpaired chest-only and no-spine CTs. See [[grid-use-not-restricted]].
