---
name: closed-papers-check
description: spine-program #238 / PR #239 (synthetic_spine's values checked against a blind page reading of the closed papers, Eisenstein 1977 from his own page) is ready, check green, and waits for greg's word; its decisions are his
metadata:
  type: project
---

spine-program PR #239 (issue #238, branch claude/238, head 2b7d62d), ready since 2026-10-28 10:32 UTC, its required check "check" green. greg's rule of 2026-10-27 22:20 UTC: "Do not merge without my word." The organization's ruleset asks for a review, which his admin bypass passes. Before he merges, one adversarial review of the last commit (2b7d62d) is still owed; its fourth review round was not run before the wrap-up.

What it adds: synthetic_spine/verification/closed_page_reading.csv (6,454 rows read blind from page images: 4,281 table cells, 129 numbers from the text, 144 figure labels) and code/check_closed_reading.py, run by scripts/check.sh. Of the 203 values those papers carry, 190 agree with their own papers; each of the other 13 is reproduced by a calculation or another paper's table. Olsewski 1990 and Robertson 2000 are settled. Eisenstein 1977, uploaded by greg at 18:54 UTC, was read from his own page: all five values agree with his Table I (Caucasoid men, L1 to L5, 23, 24, 23, 24, 26 mm); he measured 443 adult skeletons of the Raymond Dart Collection with a vernier caliper, so the level table's "dry bone" is right; his Summary's 433 is a misprint; he is the sole author.

Decisions waiting for greg (synthetic_spine README and HANDOFF.md, and the PR body): four wrong cohort rows in the pedicle table; what n holds in a series split by sex (now the whole sample in every sex's row); whether the Yu 2015 and Mitra 2002 rows should hold other values; the women's columns Ahmed, Chaudhary and Alonge print and the tables leave out; whether to cite Eisenstein's own table and call the series primary, name the Caucasoid men in the cohort, and hold 78 or a dash in n. greg's "chowdureey" is Chaudhary 2015, which exists; issue #238 still says it does not.

**Why:** a later thread must neither redo the reading nor merge #239 without greg.
**How to apply:** wait for his word; carry any decision into the copied tables only under a new claim. The datamining account's #237 meets this work in synthetic_spine ([[parallel-accounts]]). See [[papers-in-hand]].
