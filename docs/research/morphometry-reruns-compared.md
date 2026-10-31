# The morphometry reruns set beside the rows they replaced

Source: the owner's local Claude Code session of 31 October 2026, carrying on the morphometry handoff (docs/checkpoints/2026-10-31-morphometry-reruns/HANDOFF.md, Next 1). The numbers are the report of the grid word `morphometry compare`, job 40906766 at commit 6613dc5 (grid/logs/MORPHOMETRY-compare.md on the grid); compare.csv and one SVG a population are under the morphometry root's compare/40906766. Aggregates only; the rows stay on the grid.

## What was compared

Each population's new rows (engine bordercall 9c85de1, code stamp 1cee7ea83e4c28db; jobs 40900765 and 40902026) against the rows they replaced (bordercall 16f7b40, code stamp 81e732f142d3aa16; jobs 40872077 and 40877151, kept under kept/<job>/), paired by study, level and key. Every study was measured on both sides: ENHANCE.PET 1,591, VerSe 373, TotalSegmentator 159. About a quarter of the paired values moved by more than one percent (24.0, 25.6 and 24.7 percent).

## What held

Every body, end-plate, canal, height, facet, transverse process, alignment and pelvic measure is unchanged to the bit: 0.0 percent of pairs moved, no value gone or new (endplate, endplate_depth, body_w_mid, body_d_mid, canal_w, canal_ap, h_post, tp_span and the rest). So the correlation prior's five measures, and the CNS slide's body and canal lines (spine-program #251), read the same on either engine.

## What moved, as bordercall #44 meant it to

- The pedicles: width, height, area and chord moved at 72 to 97 percent of pairs, most in the neck (median change -60 to -95 percent at C5 to C7, where the old engine read the transverse foramen's bar as the pedicle) and at L5 (-30 to -50 percent).
- The pedicle's transverse angle moved at 99 percent of pairs (-70 to -86 percent at T9 and T10).
- The interpedicular distance moved at half the pairs by a few percent (T2 to T5, -1 to -8 percent); its greatest width at two thirds (L4 +18 percent).
- The end-plate inclinations changed definition (+100 to +300 percent), the disc heights in the upper thorax rose (+50 to +130 percent at T4 to T7 posterior), and the foramen height moved most at C5-C6 and C7-T1.

## The two gaps the rows show

- **The pedicle is read far less often.** About a third of the pedicle readings are gone on the new engine (ENHANCE.PET width: 12,244 gone, 76 new, 21,637 paired; VerSe: 1,098 gone, 7 new; TotalSegmentator: 1,268 gone, 5 new), at every level, not at L5 alone. This is the bounds card's "L5 pedicle read for only 86 autoPET adults" (bordercall #66) seen whole.
- **The pedicle's sagittal angle is all but gone.** ENHANCE.PET keeps 4 paired values of 6,472, VerSe none worth reading, TotalSegmentator none (459 gone).

Both are the engine's (bordercall morphometry/pedicle.py), the next step the gold tier 3 completion handoff names; neither changes a measure the prior or the slides read.
