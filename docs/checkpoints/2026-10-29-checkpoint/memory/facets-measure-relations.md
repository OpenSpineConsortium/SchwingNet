---
name: facets-measure-relations
description: which Panjabi facets-paper angle measures mirror left/right or duplicate another (CAX = -T but one cell), checked 2026-10-27 from bordercall's long table, so step e never scores one measure twice
metadata:
  type: project
---

Checked 2026-10-27 on bordercall's schwingcheck/data/panjabi_long.csv (means, C2-L5, 23 levels), for item P step e:

- Mirrored pairs (right side has the opposite sign to the left at all 23 levels): facet_sag_sup, facet_sag_inf (S), facet_card_y_sup, facet_card_y_inf (CAY). Their raw left/right mean is about 0; mirror (negate) the right side before averaging. All other left/right pairs share sign (PDIt included), so a plain mean is sound.
- Duplicates: CAX (X-card angle) = -T (transverse-plane angle). Superior facets: equal to the printed digit at every level and side but T1 left, Ts 57.7 vs CAXs -47.7 (cell images facets-t6/r06_c02 and facets-t8/r06_c02 confirm the CSV, so it is the paper's own contradiction). Inferior facets: within 0.1 everywhere (four cells off by 0.1). Score T, never CAX; CONTRADICTIONS.md should gain CAX = -T as a check.
- The step e plan in bordercall TODO.md (written 2026-10-27 ~18:05 UTC, landing in one PR with the step b remainder) records both facts.

**Why:** entering a mirrored pair's raw mean or both CAX and T would make the rule overconfident without new information.
**How to apply:** any scoring of facets measures in step e uses these rules; recheck if the table is re-read. Related: [[item-p-state]], [[findings-buildup-and-chain]].
