---
name: gold3-full-spine-rule2
description: Gold tier 3 CT rule 2 (every CT whose field shows C2 to the sacrum): SchwingNet #451 merged 2026-10-29, counts, lists to complete, the grid card
metadata:
  type: project
  modified: 2026-10-29T12:23:51.002Z
---

Thread "Complete gold tier 3 full-spine CT" (symphony_4).

- SchwingNet #451 (branch claude/project-thread-3vxvxq) MERGED 2026-10-29 ~12:30 UTC, main a555855; #443 went in with it (GitHub marked it merged). bordercall PR 25 merged earlier at 6c63bf0; VerSe read at bordercall 4a6cd72.
- Two adversarial review rounds, both written into #451's body. Round 2 added: one missing name is a skip only when the neighbours' centres stand at most 1.4 x the median of the study's 4 nearest adjacent drawn pairs (C1, C2, sacrum left out), two in a row always added; a drawn sacrum with the last lumbar running on to the field's foot is border; a level is cut only within the plane's tilt over 40 mm (LEVEL_SPAN_MM), the plane on padded TotalSegmentator grids read where cord and column stop.
- Counts: gold 3 = 1,726 = ENHANCE.PET 1,557 (plus 3 gold 4) + VerSe 18 (all need the sacrum, verse607 C2 too) + TotalSegmentator 151 (145 whole, 6 to complete: s1411 [T12], s1532 [T6-T9], s1593 [T8,T10-L1,L4,L5,sacrum], s1606 [T4-T6,L4,L5,sacrum], s1890 [T7-T9], s2065 [T11,L4,L5]). 11 border cases (silver 3 until a person looks): ENHANCE.PET 1379, verse018/033/255/531/558/559/561/588/593, s1597. Lists are the "complete" field of data/gold3-ct/admission.json.
- The lists were sent to the thread "Read the rest of VerSe's masks", which does the C2/sacrum completion in the cloud (machine-arm PR after #451).
- One decision card posted ~12:35 UTC for README section 7's single CPU grid job (gold 4 over 17,198 SPINEPS masks, held hashes, autoPET match plus the 142 list, padded extents); recommended waiting for the attorney. Nothing went to the grid.
- Deferred to that job: padded CTs' own image extent; child-sized masks under the 200-voxel floor.

- RULE 3, greg's words 2026-10-29 12:58 UTC: "If the top of the sacrum is visible that is acceptable, which I believe is all of them but check" and "Same for the bottom c2". So: a drawn sacrum is in view however little of it the field holds; an undrawn one is in view when the table puts its top above the field's foot (no 20 mm of S1); an undrawn C2 is in view when the table puts C2's FOOT under the field's top; the C2 sliver rule stays (C2's bottom sits on C3's top). Probe: gold 3 1,726 -> 1,733 (ENHANCE.PET 1,558 with 1379; VerSe 21 with verse559/561/588; TotalSegmentator 154 with s1018, s1171, s1597); looks 11 -> 6 (verse018, 033, 255, 531, 558, 593). Being written as rule version 3 in tools/gold3_field.py.
- 12:26 UTC greg tapped "Send the 1 CPU job now" (count: 1 CPU job, reads only): gate word `census gold3` (hpcworker and symphony-template already admit `schwingnet census <id>`; SchwingNet main has no census word, #420 is a draft with `census tiers`), job grid/gold3-census.sbatch + tools/gold3_census.py (numpy-only NIfTI reader on train-cpu via PYDRV): gold 4 over the census tier lists ($RS/ruleclass/tiers/tier1.tsv, tier2.tsv), held hashes, autoPET match + the 142 list, padded TS CT extents. ENHANCE.PET's labels and CTs DID land on the grid 2026-10-29 02:56 UTC (jobs 40860402, 40860413). Never send it twice.

See [[gold3-ct-dataset]], [[owner-science-rules]], [[grid-words-and-counts]], [[repo-mechanics]].

- 2026-10-29 14:30-15:00 UTC: #459 (rule 3) MERGED at e9b1b19. Census word built: SchwingNet draft PR #463 (branch claude/project-thread-w3vnfv; job grid/gold3-census.sbatch, tools/gold3_census.py; reader byte-identical to nibabel facts on 1,596 ENHANCE.PET masks). greg asked a checkpoint at 14:25 (handoff section 6 written in docs/checkpoints/2026-10-29-gold3-full-spine/HANDOFF.md on #463), then CANCELLED it at 14:53: "Just continue all without handing off but please use the grid where appropriate". Next: adversarial review, merge, then send `census gold3` ONCE (job schwingnet-census-gold3), read status first. Overlaps: #420 (census tiers word, also a word_census) and #461 (NEW_SCRIPTS one-line conflict in tests/test_gate.py). Card on joining VerSe's split scans still open.

- 2026-10-29 17:30 UTC: greg's words "WTF PLEASE PUSH ALL WORK AND CHECKPOINT AND WRITE HANDOFFS NOW!" (17:22) and "DUDE STOP ALL ADVERSARIAL REVIEW AND PUSH THIS SHIT!" (17:27): the review workflow was stopped, SchwingNet #463 pushed at f59a1c0 (main 28f0387 merged in, the 13 first-round review findings fixed, fixture tests/fixtures/gold3-census-grids.json committed), handoff section 7 of docs/checkpoints/2026-10-29-gold3-full-spine/HANDOFF.md. Left: CI, two README rows (the job is now requeueable), the unwritten tests, write "## Adversarial review" into the body, mark ready, merge, then send `census gold3` once and record the counts. The census job was never sent. The VerSe split-scan card is still open.
