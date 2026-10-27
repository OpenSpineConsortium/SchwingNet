---
name: bordercall-state
description: bordercall's layout since 2026-10-27 (README.md and TODO.md on top, everything older under archive/), where the rule, records, decks and white paper copy are, and SchwingNet's pinned copy
metadata:
  type: project
---

On 2026-10-27 the owner asked for the README to stop "throwing me off" (05:17 UTC) and for the experiments not yet run to wait for the next account in a TODO file (05:24 UTC). Main 7015802:

- README.md: only the exact Bayes rule that is implemented (SchwingCheck in the white paper): the problem, the rule, its guarantees, the seven measures, the record's 0-7 measures x 1-22 bodies tables, the robust table worlds, limits, how to run it, how to add a measure, references (Panjabi x3, Benzel x2, statistics).
- TODO.md: the owner's order (item P first and alone, then item 5, then the rest), items 0-7 (1 schwingcheck/ package, 2 measures as objects, 3 the validation grid, 4a-4e experiments with gaps and missing measures, 5 gold data and a CT population table, 6 anomalous places and a real prior, 7 predictive to generative). None started.
- archive/ (bb86584, git mv, unchanged): the package archive/bordercall/ (exact.py the rule, panjabi.py the generator, neighbour.py, covariance.py SPINEPS_7, junction.py, spineps_map.py and SPINEPS_MAPPING.md, reference/ with build_panjabi.py, panjabi_full_spine.csv and the three scanned papers), records/ (exact-2026-10-26, neighbour-2026-10-26, identify-2026-10-26, panjabi-2026-10-26 for the junction figures, whitepaper-2026-10-26), docs/ (NEIGHBOUR_IDENTITY_STUDY/RESULTS, LEVEL_IDENTIFIABILITY_RESULTS, EXACT_IDENTIFICATION_RESULTS, SCHWINGCHECK_LEVELCHECK.md), slides/ (exact/ CNS and NeurIPS decks, junction_slides.pptx/.pdf, their make_*.py), tests/, HANDOFF.md and CHECKPOINT_2026-10-26.md.
- Every older bordercall path in notes and handoffs now starts with archive/. Tests: `cd archive && python3 -m unittest discover -s tests` (222, pass).
- SchwingNet's pinned copy is grid/bordercall/ at bordercall 6938a2e (older than the exact rule; the approved pilot runs it); a new copy is `python3 tools/bordercall_vendor.py copy <clone>/archive` in SchwingNet.
- The white paper "SchwingCheck and LevelCheck" is the owner's Claude Doc https://claude.ai/artifact/4VwMe9CKMX87s4jiEJBpRE on the old account; archive/docs/SCHWINGCHECK_LEVELCHECK.md is its ASCII copy at revision 189, so another account works from the copy until the owner shares the Doc. SchwingNet #416 (textbook chapter 36) carries it verbatim; never edit the paper's section there.
- The project symphony's shared files exact-slides/ and junction-slides/ are byte for byte in archive/slides/ and archive/records/panjabi-2026-10-26/.

**Why:** old paths in every handoff point at the top level and break without the archive/ prefix.
**How to apply:** work item P in archive/bordercall; do not start TODO items other than P. See [[priority-panjabi-first]], [[findings-naming]].
