---
name: corpus-tiers-census
description: The owner's gold/silver evidence tiers of 2026-10-27, the sorter tools/corpus_tiers.py and grid word `census tiers` (1 CPU job, not yet approved) on SchwingNet branch claude/project-thread-cdwl0r
metadata:
  type: project
  modified: 2026-10-27T05:20:00.000Z
---

The owner's tiers (message of 2026-10-27 03:06 UTC): gold = one study shows C2 to the sacrum, silver = partial. 1 = real CT paired with real X-ray of the same person, human annotation on at least one; 2 = the pair, no human annotation; 3 = CT or X-ray alone, with human annotation (the thread's reading of "paired or"); 4 = alone, no annotation. A person counts once, at the best tier. Machine masks (SPINEPS, VERIDAH), reports that only mention a level, DRRs and Flux-edited DRRs never raise a tier. Real C-arm frames are partial, so a CT plus frames is at best silver 1.

Where it lives: SchwingNet data/corpus-tiers/sources.json (per-source table), tools/corpus_tiers.py (census, report, table, power), grid/census.sbatch, grid/gate.sh word `census tiers` -> symphony-template grid-accounts.yml word `schwingnet-census-tiers`; research page docs/research/corpus-tiers/README.md; memory docs/memory/the-corpus-tiers.md. Public-safe method note: symphony-template docs/research/corpus-evidence-tiers-2026-10-27.md.

Conversions are counted apart, never pooled: SPINEPS 4 -> 3 machine/provisional; Flux DRR 3 -> 1 only after the domain-gap test passes; review or SchwingCheck 3 -> 1 needs a person confirming.

Pending sources: Radiopaedia (approval 202610-9517, by hand, mostly silver 3), Setting Scoliosis Straight / Harms Study Group (Michelle Marks, mmarks@ssshsg.org; owner already replied 2026-10-23; follow-up draft in the owner's Outlook Drafts; images held centrally, no CT, expected gold 3 / silver 3), Exeter/Bournemouth (Fiona Mellor handed to Alan and Alex Breen 2026-10-26; ~1,180 partial fluoroscopy events with corner templates, silver 3).

CHECKPOINT 2026-10-27 ~05:20 UTC (owner's word 04:47): SchwingNet draft #420 and symphony-template draft #500, branch claude/project-thread-cdwl0r, both pushed. Handoff: SchwingNet docs/checkpoints/2026-10-27-corpus-tiers/HANDOFF.md. Held persons counted once: gold1 0, gold2 0, gold3 159 (TotalSegmentator 142, VerSe 17), gold4 about 1,929 (estimates until the census), silver2 848 (COBRA, C-ArmLSpine, DeepFluoro, one cadaver). Left: apply the consistency lens's adjudicated verdicts (data/corpus-tiers/work/critics.json, two conflicts to settle first), check.sh in a throwaway copy, adversarial review in both bodies, mark ready, then one decision card for the census CPU job.

**Why:** the owner wants experiment power calculated from gold data only where possible.
**How to apply:** the census job needs the owner's word and count (asked once as a decision card); send only after the SchwingNet PR merges and an `update`, with a status read first. See [[owner-trusts-only-c2-countable-spines]] and [[only-full-spine-columns-are-truth]].
