---
name: literature-keys
description: Where greg's Elsevier key, institutional token and Semantic Scholar key live (organization secrets), the one test fetch of 2026-10-28 and its results, and the open Elsevier 403
metadata:
  type: project
---

greg, 2026-10-27 22:46 UTC: ELSEVIER_API_KEY, ELSEVIER_INSTTOKEN and later S2_API_KEY are OpenSpineConsortium organization Actions secrets. He once pasted their values into a thread in plain text: never quote that message, never write any value anywhere. At 23:00 UTC he declined reissuing them and gave his word for the key route, one grid-job fetch, one test of each, and a list of the papers the fetch cannot get. The secrets' access was set to Selected repositories ("done all 3", 2026-10-28 00:58 UTC).

Built and merged: hpcworker #51 (gate words key elsevier -> ~/.elsevier/token.env, key s2 -> ~/.s2/token.env), symphony-template #507 (grid-accounts.yml action=key name=elsevier|s2), SchwingNet #435, #438, #440 (the grid word literature synthetic_spine; landing /rs/rs_grp_oschome/go2432/data/literature_synthetic_spine/ with INDEX.md; Elsevier's files read by a session only on greg's word; docs/research/literature-on-the-grid.md).

Keys sent 2026-10-28 01:00 and 01:01 UTC, spending greg's one send of each. The test fetch, job 40819848 (01:04 UTC): 17 of 42 got, 3 held, 22 not got. Elsevier answered 403 for both its papers, open-access shin2024 included, before any rights check: either the token is not bound to this key or the key is not enabled for ScienceDirect, perhaps until the text-and-data-mining amendment; greg was to ask Elsevier (case 260924-003406). Semantic Scholar gave 429 on 4 keyed lookups; the fetch now retries 6 times. Every paper was later had by other routes ([[papers-in-hand]]).

**Why:** sessions cannot list secrets, and the run's results are not otherwise in one place.
**How to apply:** never resend keys or refetch without greg's new word and count, and the hold ([[hold-and-wrap-up]]). Related: [[grid-words-and-counts]].
