---
name: totalseg-rerun-fix-505
description: SchwingNet #505 merged (45370ca) with the totalseg rerun fixes and the full-sacrum rule; rerun sent as job 40896342 at 23:12 UTC
metadata:
  type: project
  modified: 2026-10-30T21:41:00.959Z
---

As of 2026-10-30 ~22:10 UTC (thread "Continue Bayesian synthetic validation", symphony_3):
- SchwingNet #505 (merged 23:11 UTC) fixed the weight-download guard, gpu->cuda for MOOSE, MOOSE rerun file diff, segmenter in reasons, and the gate's .sent mark.
- Sacrum rule (greg, 22:58 UTC): he trusts no segmenter's S1 class; the sacrum is ONE full union mask (sacrum + S1) for every gold tier member, and a TotalSegmentator release's S1 is read as part of its sacrum. Done in #505, DEVIATIONS.md items 2 and 3. #505 ready with auto-merge (merge hold lifted 22:55 UTC: merge own PRs once tests and CI pass).
- The rerun was sent at 2026-10-30 23:12 UTC through the gate at SchwingNet 45370ca: job 40896342 (one GPU job; TOTALSEG_RERUNS complete:40882547 now spent). Resend the word only to read logs/TOTALSEG-complete.md. Greg lifted the grid restriction at 23:03 UTC (except the 14:33 three-job morphometry count).
- bordercall #38 got bordercall main merged in (PR 44, merged 14:30 UTC), synthetic-validation tests 205 pass; its gold tier 3 rescore needs the SchwingNet engine re-pin (on #501, branch claude/project-thread-gv744i, pin ee495d5) then a grid run (no word needed since 23:03 UTC). PR 44 also changed the disc plate rule, so the disc-step failures may move with the re-pin.
- 2026-10-31 01:12 UTC: SchwingNet #510 merged, recording job 40896342's counts in members.json completion.totalseg_arm and gold3-ct README 2c/7. The sacrum was kept in 26/27 VerSe and 1/5 TotalSegmentator; C2 in 4/19 (H1 met, H2 not). s1606's 434-voxel sacrum still needs a look. A members.json change needs `tools/gold3_ct.py stats` and `page` rerun, or CI fails.
Related: [[totalseg-complete-sent]] [[gold3-on-bounds-card]]
- 2026-10-31 06:00 UTC: bordercall #66 merged (1ef008f). It rescores gold tier 3 on the card from covariates job 40902924 (engine at PR 44). TotalSegmentator passes (steps 0.91); autoPET falls 4 steps short (0.87 vs 0.89); pedicle/canal steps 0.81/0.86, up from 0.64/0.70. The new engine prints no pedicle sagittal angle on these masks, and the L5 pedicle is read for 86 people. gold3.py's not_scored now names cells_not_printed. The ML artifact 13LehVRhuCUB4r4hNC2b3H has not been republished.
