---
name: clinical-reread-pr39-state
description: bordercall PR 39 (clinical reread) merged 2026-10-30 10:47 UTC with every judgement decided; follow-up PR 46 (the archive's "embalmed" decision in HANDOFF.md) merged 11:56 UTC; the thread is finished
metadata:
  type: project
  modified: 2026-10-30T09:48:43.375Z
---

All nine prior-art family notes landed on 2026-10-29. On 2026-10-30 the thread "Finish the clinical reread" (project symphony_5) ran review round 5 (record in research_notes/prior-art-measurement/review/), then, on the owner's "Can you decide?", decided the 41 mapping judgements (21 questions), the four validation items and round 4's three open items by one rule (research_notes/paper-tables/validation/README.md, "Decided on 2026-10-30"; review/round-4.md). Effects: Masharawi 2021 facet widths close to differs; Irie 2021 (filed as otsuki2021) pedicle heights close at L1 to L3, widths differ at L4, L5; Busscher 2010 PedA stays close (the pinned-vertex reading was wrong). Commits 3ead9b5, 6d2b113, 2fcc3a3; the PR body carries a "Decided on 2026-10-30" paragraph.

Rerunning the comparison needs xarray: build a throwaway venv from the pinned requirements-schwingcheck.txt subset (numpy, scipy, pandas, xarray, h5netcdf, h5py, matplotlib) and run tools/cross_naming.py (--fields 200 --seed 2026 --processes 4, about 8 minutes) then tools/results.py; no grid job.

**Why:** a later thread would otherwise redo the review, the decisions or the rerun.

**How to apply:** nothing is left for a session. PR 39 merged at head 2fcc3a3 (merge f48fb75); the "embalmed" decision (archive left as written, correction in notes/panjabi1992.md) came after the merge and landed as PR 46, merged 2026-10-30 11:56 UTC. Morphometry (PR 44) is another thread's. See [[owner-rules]].
