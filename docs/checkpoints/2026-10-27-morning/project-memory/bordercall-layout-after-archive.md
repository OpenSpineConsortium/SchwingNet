---
name: bordercall-layout-after-archive
description: Since 2026-10-27 bordercall's top level holds only README.md (the exact Bayes rule, SchwingCheck) and TODO.md (future work for the next account); everything older is under archive/, unchanged
metadata:
  type: project
  modified: 2026-10-27T05:32:59.573Z
---

On 2026-10-27 at 05:17 UTC the owner asked for bordercall's README to stop "throwing me off": move the existing repository into an archive directory and rewrite the README to expose only the Bayes rule that is implemented. At 05:24 UTC the owner said the experiments not yet run (bodies with gaps, gaps the reader does not know about, measures missing at random) are for the NEXT account and belong in a TODO file with the rest of the future work, not run now.

- Layout: README.md (method, seven measures, adding a measure, the record's 0-7 measures x 1-22 bodies tables, limits, references: Panjabi x3, Benzel x2, statistics), TODO.md (items 0-7: lift the rule into schwingcheck/, wrap each measurement as one object, the validation grid, experiments 4a-4e, a CT population table, anomalous places and a real prior, predictive-to-generative programme), archive/ (the whole old repo, moved by git mv).
- Tests now run from archive/: `cd archive && python3 -m unittest discover -s tests` (222 tests).
- SchwingNet's tools/bordercall_vendor.py copy needs `<clone>/archive` as its argument now; the pinned grid copy (6938a2e) is unaffected.

**Why:** the next account starts from TODO.md; old paths in notes (bordercall/exact.py, records/...) now live under archive/.
**How to apply:** prefix old bordercall paths with archive/; do not run the TODO experiments unless the owner asks again. See [[cns-white-paper-thread-state]].
