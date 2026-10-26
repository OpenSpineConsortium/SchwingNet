---
name: only-full-spine-columns-are-truth
description: The owner trusts only full-spine CTs that run from C2 to the pelvis as truth for vertebral names (2026-10-26 00:16 UTC); the 802 CTSpinoPelvic1K columns are not used for any reported result
metadata:
  type: feedback
  modified: 2026-10-26T00:16:39.940Z
---

On 2026-10-26 at 00:16 UTC the owner wrote, in the thread "Finish CNS slides with junction predictor": "i dont trust the ... 802 CTSP1K CTS I ONLY TRUST FULL SPINE C2 to PELVIS CTS!"

**Why:** a vertebral name is a count from C2; CTSpinoPelvic1K is a lumbar-centred corpus whose level names are readers' calls, so a result scored on it proves nothing about naming. This is bordercall's own countable rule, stated by the owner as a standing preference.

**How to apply:** never report a junction, border or phenotype result from the 802 columns; keep the fixture only for bordercall's selftest of the published pipeline. Every real check of a predictor runs on the grid's countable SPINEPS columns (C2 present, sacrum in view where the count to the pelvis matters), through the `bordercall` grid word. See [[bordercall-grid-count]].
