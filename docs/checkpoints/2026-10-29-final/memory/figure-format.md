---
name: figure-format
description: greg's default look for line graphs (the schwingcheck README build-up figure) and Benzel style for anatomical graphs
metadata:
  type: feedback
  modified: 2026-10-28T22:58:31.082Z
---

Line graphs default to the format of schwingcheck/README.md's figure under "Naming as the measures are added"
(records/curve-2026-10-28/figures/curve_accuracy.png, drawn by schwingcheck/curve_report.py's style()): black ink on
white, serif type, panels lettered A, B, C in bold with a short title beside the letter, axes on two sides only,
ticks outward, no grid, no colour; series told apart by line (dotted, dashed, solid) and marker (open triangle, open
square, filled circle), a boxed legend, a reference as a thin dotted line, the seven SPINEPS measures as crosses.
Anatomical graphs (a measure down the column by level, the column drawn) are drawn in Benzel's textbook style, as
archive/bordercall/junction_figures.py draws its profiles.

**Why:** greg, 2026-10-28 22:54 UTC: "use it much more, as the default for line graph plotting, of course for
anantomical type graphs use Benzel format graphs". He worried the README's own figures are stale; the chain-of-levels
thread was refreshing them.

**How to apply:** in a Claude Doc, draw the chart as a widget that reproduces this format (serif, ink via the text
token so dark mode still reads, line and marker per series, lettered panels) so it stays live; in a repository, draw
with curve_report.style() and commit the PDF, PNG, CSV and caption from a record. See [[owner-working-style]].
