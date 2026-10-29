---
name: owner-science-rules
description: greg's standing scientific and confidentiality rules since 2026-10-25 (C2-countable truth, SPINEPS and the segmenter block, a second arm never pooled, no arbitrary constraints, stay Bayesian, Benzel figures, evidence tiers, results not method)
metadata:
  type: feedback
---

Word for word with times in SchwingNet docs/checkpoints/2026-10-27-morning/project-memory/.

- Truth (2026-10-26 00:16 UTC): "I ONLY TRUST FULL SPINE C2 to PELVIS CTS!" A level name is a count from C2; the 802 CTSpinoPelvic1K columns are used for no reported result. Rows without C2 (or C1) and the sacrum are reported apart, never pooled.
- Segmentation (00:17 and 00:26 UTC): SPINEPS for production, reusing existing grid masks, never re-run, never TotalSegmentator; MOOSE only to replicate FleXray's dataset; the segmenter is a configurable block (key `segmenter`, values `spineps`, `moose`; src/schwingnet/segmenters.py); label schemes mapped correctly (SPINEPS in the VerSe alphabet C1..L5 = 1..24, L6 25, sacrum 26, coccyx 27, T13 28; MOOSE via FleXray's configs/datasets/MOOSE.yml, L6 = 83, no T13). A segmenter runs only as its own stage with his count. Since 2026-10-28 20:40 UTC masks other segmenters released (ENHANCE.PET, TotalSegmentator) may feed a second arm, never pooled with SPINEPS ([[decisions-2026-10-28]], item 2).
- Naming (2026-10-26 06:31 UTC): no arbitrary constraints; the target's own measures are allowed; a series of solutions, each one's accuracy per phenotype.
- Bayesian (2026-10-28 19:08 UTC, [[owner-direction-2026-10-28]]): no invented features, stay in the Bayesian domain; the auto-anatomist must be visualisable and fast at inference; training cost does not matter.
- Figures (2026-10-26 01:17 UTC): like Benzel's (clean anatomical line art, labelled levels, restrained plots), drawn by committed code from recorded inputs; in a deck, 3D renders over sideways bar charts. No OneDrive uploads; figures live in the repositories.
- Tiers (2026-10-27 03:06 UTC): gold = one study shows C2 to the sacrum, silver = partial; 1 real CT paired with a real X-ray of the same person, human annotation on at least one; 2 the pair, no annotation; 3 one modality with human annotation; 4 alone, none. A person counts once, at the best tier. Machine masks, level-only reports, DRRs and Flux-edited DRRs never raise a tier; real C-arm frames are partial. Power from gold data where possible.
- Confidentiality: SchwingNet's and bordercall's notes never leave them; results may be shown, the method may not, until greg says otherwise. His text wins in the white paper; corrections only as narrow, checked edits.
- Textbook: no owner step ever; the reader loads the repository live, never a staged copy.
- Data: every fetch sized exactly first; Radiopaedia never by script; CT-RATE never without his terabytes; usage credits never used; no PDF or page text in git; never get around a robot check.

**Why:** each came from a correction; each was a mistake a thread made or nearly made.
**How to apply:** check every result, figure and claim against them before a pull request.
