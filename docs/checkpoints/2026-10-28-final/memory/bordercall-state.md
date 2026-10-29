---
name: bordercall-state
description: bordercall's layout and pull requests at 2026-10-28 21:25 UTC (main 08b1a23; drafts PR 20 and PR 21), where the rule, records, decks and the white paper copy are, and SchwingNet's pinned copy
metadata:
  type: reference
---

Main 08b1a23 (PR 19, 2026-10-28 18:33 UTC). Top level: README.md (the exact Bayes rule), TODO.md (item P and items 0 to 7), and the folders:
- schwingcheck/: the rule and generator on xarray data, the PyMC rewrite, the measures, the build-up study (PRs 7, 9, 14, 15, 18); README.md "The build-up study"; requirements-schwingcheck.txt.
- scanimport/ (six CT label schemes, X-ray corners, raw CT and mask-free import; PRs 8, 13), combinations/ (PR 10), coarse/ (PR 11), holdings/ (gold-tier-3.md, PR 12; ENHANCE.PET recount and facts, PRs 16, 17): built by greg's other account on 2026-10-27 and 28; none imports schwingcheck; scanimport writes fields in `schwingcheck name`'s CSV format.
- research_notes/cadaver-power/ (PR 19). research_notes/clinical-reread/ arrives with PR 21.
- archive/ (bb86584): the older package archive/bordercall/ (exact.py the rule, panjabi.py the generator, covariance.py, junction.py, spineps_map.py, reference/ with Panjabi's papers and build_panjabi.py), records/, docs/ (EXACT_IDENTIFICATION_RESULTS, NEIGHBOUR_IDENTITY_RESULTS, LEVEL_IDENTIFIABILITY_RESULTS, SCHWINGCHECK_LEVELCHECK.md), slides/, tests/, HANDOFF.md.

Open: draft PR 20, the chain of levels ([[item-p-state]]), branch claude/project-thread-tbg4jw, head ede955b, with greg's seven decisions written into its TODO.md; draft PR 21, the clinical reread ([[clinical-reread]]), branch claude/project-thread-y719tr, head 0d4b49b. The branch claude/project-thread-rr7in4 holds the old project's shared folder carried to the grid; it can go once nobody needs a fresh landing from it.

- SchwingNet's pinned copy is grid/bordercall/ at bordercall 6938a2e (26 October, older than the exact rule); the approved pilot runs it. A new copy is `python3 tools/bordercall_vendor.py copy <clone>/archive` in SchwingNet.
- The white paper "SchwingCheck and LevelCheck" is greg's Claude Doc on the old account; archive/docs/SCHWINGCHECK_LEVELCHECK.md is its ASCII copy at revision 189, so another account works from the copy. SchwingNet #416 carries it verbatim; never edit the paper's section there.
- bordercall TODO.md's line "never use TotalSegmentator, for this work" needs changing to match decision 2 ([[decisions-2026-10-28]]).

**Why:** old paths in every handoff point at the top level and break without the archive/ prefix, and two drafts are open.
**How to apply:** check open PRs before editing; old paths start with archive/. See [[repo-mechanics]].
