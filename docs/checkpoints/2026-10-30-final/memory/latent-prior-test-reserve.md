---
name: latent-prior-test-reserve
description: The frozen test reserve and anomaly-aware parts of the latent-prior evaluation (bordercall draw_test_reserve.py, commit 74f93f6, 584 studies, 85 repeat units, at SchwingNet 3abc2fa) and the person-split interface with the auto-anatomist thread
metadata:
  type: project
  modified: 2026-10-30T10:51:25.286Z
---

Since 2026-10-30, the latent-prior evaluation thread (bordercall PR 45, research_notes/latent-shape-prior-evaluation/reserve/)
has carried draw_test_reserve.py and its outputs. Commit 74f93f6 (v6) holds greg's anomaly rule (see [[greg-anomaly-aware-splits]]).
The outputs are the persons the evaluation may test. The auto-anatomist annealer screen (SchwingNet PR 483) leaves them out
of train and validation, so arm F may start from its checkpoint.

Figures at SchwingNet 3abc2fa (export sha256 ac95c7c1...):
- Reserve: 584 studies, sha256 cd9ddfed....
- Repeat groups: 85 units of 203 studies, sha256 a45797c3....
- Both files have been byte-identical since v4.
- 1,738 studies form 1,620 units. At 0.2: 327 test, 167 validation, 1,091 train; 32 doubt; 3 held.
- First run (normal only): 1,060 units / 1,157 studies. At 0.2: 204 test, 124 validation, 732 train. At 0.3: 325 / 124 / 611.
- Anomaly families, drawn units test/train at 0.2:
  - four lumbar: 10/16
  - six lumbar: 10/36 (14/32 at 0.3)
  - T13: 8/9
  - rib anomaly: 16/19
- TotalSegmentator l6 is "six_lumbar_by_names" (1/2), kept apart.
- 2 holdouts are tested in no stratum: verse549 and verse547.
- verse573 (no_l5) is test but outside the first run.

The rule of record is the docstring:
- Probable repeat scans form one unit, built by union-find over ENHANCE.PET facts using three volume/spacing/rib links.
- Strata are member:class:call_by_names. Each stratum sits inside one family and is drawn by rank (test or train, never validation).
- Doubt comes before holdout.
- The reserve is the test part at 0.3 plus the hash band [0.1, 0.4). The checks pass on every draw (14 of them).

Interface with the auto-anatomist thread:
- Persons are compared by the export person string.
- Each group is kept in one part.
- Both files are pinned by sha256.
- The annealer pool:

| Count | Total | Train | Validation |
|---|---|---|---|
| Normal ENHANCE.PET off both lists, any status | 982 | 828 | 154 |
| After removing 181 candidates the masks have not confirmed | 801 | 671 | 130 |
| After removing 20 studies whose unit's part differs | 781 | 657 | 124 |

- The 781 is the PREREG's eligible count.
- On 2026-10-30 that thread confirmed nothing needs refreezing.
- Arm F starts from the annealer checkpoint only if the reserve sha256 matches and no test person was trained on.

**Why:** review rounds (seven in all) found leaks through repeat scans, a missed fallback band, mixed anatomies, and miscounted holdouts. See [[greg-job-count-latent-prior]].

**How to apply:** a new export (a new SchwingNet commit) needs a rerun and a new sha256 before either PREREG freezes. The evaluation never redraws its test part from a later export.
