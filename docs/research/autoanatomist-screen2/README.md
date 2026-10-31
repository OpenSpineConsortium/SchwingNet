# The auto-anatomist's second screen: where it stands

Source: the thread "Finish the auto-anatomist screen", 30 October 2026, carrying on "Restart the auto-anatomist probe" (docs/checkpoints/2026-10-30-final/autoanatomist/HANDOFF.md, section 4). Confidential with the rest of this repository.

The second screen asks whether one of four changes to the anneal, which the owner chose on 2026-10-30 at 16:52 UTC, outlines vertebrae from the CT alone better than the first screen's lambda-then-w anneal: cyclic (the anneal twice), adaptive (lambda moved by the error's own slope), overlapping rungs of the ladder, and a restraint mid-anneal; the CT branch alone runs beside them. Its design is PREREG.md beside this file, frozen before any send and before any number of the first screen was read.

- Why a kind of its own: the first screen's PREREG is frozen and is never edited, and the registry holds one frozen PREREG per kind (flows/registry.txt). So the second screen runs the first screen's flow as the kind autoanatomist2 (flows/autoanatomist2.py), with a job script of its own (grid/autoanatomist2.sbatch, which runs grid/autoanatomist.sbatch at the sent commit as that kind), and its report is the first screen's, restating this PREREG for a chain whose record names its sha256 (tools/autoanatomist_report.py, DESIGN2).
- The plans: grid/screens/gold3_latent_smoke2.json, the anneal and its four changes, one seed, five short trials in series on one card on the first smoke's four CTs; and grid/screens/gold3_latent_screen2.json, six arms at two seeds, twelve trials of 50 epochs on the first screen's 96 training and 24 validation CTs, every arm read against lambda_then_w. Both take their rows from the first screen's committed plans (tools/autoanatomist_plan.py write --plan, rows_of).
- The code: the vendored package under grid/autoanatomist/ at the bordercall commit that carries the four arms (bordercall PR 48), each a block that changes nothing where it is not named, so a later send of the first screen trains as it did.
- The grid word: `autoanatomist gold3_latent_smoke2`, then `autoanatomist gold3_latent_screen2` (grid/gate.sh, AUTOANATOMIST2_PLANS). The gate sends the second smoke only once the first screen's report ends in exit 0, and the second screen only once the second smoke's does (AUTOANATOMIST_AFTER).

Where it stands on 30 October 2026: built and frozen, nothing sent yet; counted in AUTOANATOMIST_COUNTED since the owner lifted his hold on grid jobs at 23:03 UTC. The copy under grid/autoanatomist is bordercall 0300f20, PR 48 as merged. The second smoke is sent once the first screen's report ends in exit 0, and the second screen once the second smoke's does.

## The verdict, 31 October 2026

Both sent and both ended 0: the second smoke (40900847) and the second screen, twelve trials (array 40902102, all exit 0, the last two on galhp after a wait) and the join (40902104, at commit ab8826a, held to PREREG.md sha256 e5f4d06ca2657736), read by the owner's local session from grid/logs/AUTOANATOMIST-gold3_latent_screen2.md. Against lambda_then_w by the bar of section 3 (every seed's final validation distance below every one of the null's):

- cyclic beats the null: selected for a longer run under a pre-registration of its own, never reported as an effect;
- ct_only beats the null: the CT branch alone ends below the anneal, as the first screen's null suggested;
- adaptive, overlapping and restraint do not.

Five arms against one null at two seeds a side make a chance pass likely, so the two passes are leads, not findings. The figures (curves.png, finals.png) and the CLAIM and REFORMS report are under /rs/rs_grp_oschome/go2432/autoanatomist/gold3_latent_screen2/40902102/.
