---
name: closed-papers-check
description: spine-program synthetic_spine - #239 (blind page reading of the closed papers) and #241 (its open decisions carried out as data/corrected/) both merged by greg on 2026-10-28/29; what is left is greg's word on the public CTSpinoPelvic1K change and a second, independent review
metadata:
  type: project
  modified: 2026-10-29T00:18:22.549Z
---

Both merged by greg: PR #239 (issue #238, the blind page reading, verification/closed_page_reading.csv) on 2026-10-28, and PR #241 (issue #240) on 2026-10-29 00:17:51 UTC, main 621ee19.

#241, on greg's "i want you to figure out those decisions" (2026-10-28 23:03 UTC): synthetic_spine/code/apply_decisions.py writes data/corrected/ (a model reads these) and verification/decisions.csv; the copies under data/ stay the public CTSpinoPelvic1K e887274 bytes, SHA-guarded, and scripts/check.sh runs `apply_decisions.py --check`. README "Decided" 1 to 9 gives each decision with its page:
- 1 four pedicle cohort rows; 2 n is that sex's count (the eight series #239 had not read now read: Abbas 90/90, Amonoo-Kuofi 1982 150/140, 1985 79/43, Chen 43/40 from 430/400 endplates at ten a patient, Duman 277/240, Pierro 302/302, Masharawi 25/25, van der Houwen a dash); Hinck stays in films.
- 3 Yu's own means, Mitra one method; 4 women's rows and printed SDs, Eisenstein's Caucasoid women (n 35); 5 Eisenstein from Table I (n 78); 6 Cizmic's SD over both sexes; 7 Yadav's 6.87 stays.
- 8 the copy's 20 Italian MRI values are not Pierro 2017's at any level, sex or statistic; replaced by its Table 2; their origin not recorded.
- 9 four citations corrected (Abu-Leil for Masharawi, Irie for Otsuki, van der Houwen 2010, Shin 2025).
Numbers come from verification/open_questions_reading.csv (read for #240 beside page images, not blind) or the blind reading.

Left: the same corrections in public CTSpinoPelvic1K morphometrics/ wait for greg's word (HANDOFF item 6); the adversarial review was one reader's by hand (the review agents hit the five-hour limit), and greg said another account may do an independent one; 227 values of the nine PMC-held papers are still unread (HANDOFF item 1).

**Why:** a later thread must not redo the reading or the decisions.
**How to apply:** start from data/corrected/; any upstream change only on greg's word. See [[papers-in-hand]], [[parallel-accounts]].
