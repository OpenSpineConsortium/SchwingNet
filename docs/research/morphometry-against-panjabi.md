# The engine's body and canal chords against Panjabi, and what was wrong with them

Source: the owner's local Claude Code session of 31 October 2026, on his words that evening: plot Panjabi's values beside Benzel and the gold tiers, look for errors in the measuring code behind the gaps, fix them by a published method, and "i want all the spine within 1 mm of panjabi"; then, of the canal, "why am I not doing a more robust approach like the radiology patent on canal finding?". Aggregates only; the rows stay on the grid. Panjabi's means and standard errors are bordercall schwingcheck/data/panjabi_long.csv.

## How it was checked

A calibration harness ran the engine (bordercall at 3c43361, the code that measured the gold tier rows) on 89 real studies, 48 ENHANCE.PET, 21 VerSe and 20 TotalSegmentator, and read each candidate definition beside the engine's own on the same vertebrae; renders of the body's slabs and of the CT in each vertebra's frame showed what each reading takes in. Then the chosen readings ran over every full spine, one CT a person (grid job 40906993). The harness, its aggregator and the profile are in spine-program CNS/not_all_spines/generator/ (grid/ and figs_v17_6min/).

## What was wrong

- It was not the labels. ENHANCE.PET's, VerSe's (hand-corrected), TotalSegmentator's and gold tier 4's masks gave the same numbers within about a millimetre, and so did slices of up to 1.25, up to 2.5 and over 2.5 mm (profile job 40906866).
- The end-plate width took in whatever the label fuses to the plate's edge. In the neck the uncinate processes rise from the upper plate's posterolateral edge and the costal roots of the transverse processes join the body's side; in the thorax the pedicles' bases and the rib heads' facets stand at the posterolateral corners; at L5 the transverse processes' roots do. scanimport's end-plate slab took the extent of all of it, and read EPWu 4 to 6 mm over Panjabi at C3 to C6 and at T10 to L3, 11 at L5 and 14 at T1, while its depth read within about a millimetre.
- The neck's body was not a body. anatomy.clip_to_foramina found the foramen transversarium closed in 1 to 11 per cent of cervical vertebrae; otherwise it cut the body at the canal's side walls and a millimetre beyond, so the body's width was the canal's plus two millimetres, and where it found the foramina its cut took in the costal roots (27 to 35 mm).
- The canal was read on the label's hole. The ring closes in one to three slabs in the neck and at L5, so the pedicles were found on both sides in about 1 per cent of neck vertebrae and the interpedicular distances fell back to the hole's width through its middle; and the label's boundary narrows the hole. The neck's canal read 19 to 21 mm wide where Panjabi's SCW is 23 to 26.

## The fixes (bordercall morphometry/plates.py and morphometry/ct_canal.py)

- Each end plate on its own layer and its front half (plate_w, plate_d and their lower twins): the slab reaches no more than half a voxel layer past the plate's plane, and the width is the widest row over the front half of the depth, each row the run of cells through its middle. Every appendage above stands on the back half or above the plate.
- The canal on the CT (canal_w_ct, canal_ap_ct), as the published canal finders do it (Radnostics US 8,891,848; Yao 2006): the canal's soft tissue flood-filled from a seed 5 mm behind the body below 200 HU, the dense-bone floor of the published heuristic pipelines, in planes 0.5 mm apart through the body, kept only where bone encloses it; the width the widest row through the seed's column (Panjabi's SCW), the depth the midline run (SCD), each the median over the enclosed planes. It needs no ring in the label, and the label's boundary does not enter.

## Where it stands against Panjabi, every full spine (mm, ours minus Panjabi; grid job 40906993)

2,290 spines, one CT a person (1,440 ENHANCE.PET, 21 VerSe, 159 TotalSegmentator, 670 gold tier 4); the canal on the CT is read where the CT is on the grid (all but VerSe's 21), 1,387 to 2,156 a level.

| | C3 | C4 | C5 | C6 | C7 | T1 | T2 | T4 | T7 | T10 | T12 | L1 | L2 | L3 | L4 | L5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| canal width, CT | +0.6 | -0.7 | -0.4 | -1.2 | -0.6 | +0.1 | -0.3 | -0.3 | -1.0 | -0.2 | +1.8 | +1.6 | +1.0 | +0.6 | +0.4 | -0.8 |
| canal depth, CT | -1.5 | -3.7 | -3.3 | -4.1 | 0.0 | +1.1 | +1.7 | +0.4 | -0.3 | +1.6 | +2.0 | +0.7 | +1.5 | +2.2 | +0.8 | -0.3 |
| upper plate width | +6.4 | +4.9 | +5.4 | +5.3 | +1.1 | -0.1 | +2.2 | +1.5 | +2.2 | +4.5 | +2.1 | +1.9 | +2.2 | +2.6 | +2.0 | +0.5 |
| upper plate depth | -0.1 | +0.3 | +1.7 | +2.2 | +1.6 | +0.1 | +0.7 | +1.2 | +2.3 | +2.7 | 0.0 | -0.6 | 0.0 | +0.3 | -0.2 | -1.3 |
| lower plate width | +0.8 | +1.5 | +0.4 | +0.7 | -0.6 | -0.5 | +3.2 | +1.3 | +2.7 | +3.7 | +0.9 | +2.6 | +2.5 | +2.3 | +2.7 | +0.4 |
| lower plate depth | +3.3 | +3.3 | +2.5 | +2.6 | +3.4 | +0.6 | +0.3 | +0.7 | +1.7 | +1.3 | -0.7 | -1.8 | -0.3 | +0.6 | +2.2 | +2.1 |

The canal's width on the CT is within about a millimetre of Panjabi's at 13 of 16 levels from C3 to L5 (the label's hole read 3 to 6 mm narrow in the neck), the upper plate's depth at 11. The plate widths are 1.5 to 2.6 mm over his through most of the thorax and the lumbar spine, the lower plate's within a millimetre in the neck.

SPINEPS's subregions, which the census holds for autoPET and gold tier 4, were tried for the body (job 40908618, 60 studies): its corpus label on CT takes in more, not less, reading the neck's upper plate 10 to 15 mm and the lumbar plates 4 to 6 mm over Panjabi with scanimport's slab, and 2 to 4 with the plate rule. SPINEPS is trained on MRI; on CT its corpus is not the bone's outline, so segmenting again with it would not give the bodies.

## What 1 mm against Panjabi can and cannot mean

- Panjabi's means come from 12 cadavers. Their 95 per cent margins (1.96 SEM) are 0.7 to 2.6 mm on these chords, so a population mean within 1 mm of his is a finer bar than his own means hold.
- The published series disagree with him by more than 1 mm. On the bounds card (bordercall research_notes/synthetic-validation/records/bounds/bounds.csv) a dry-bone series puts the neck's canal at 19 to 21 mm wide and 10 to 11 deep, and the living CT series put the lumbar canal 15 to 17 mm deep where Panjabi has 17.5 to 19.7, and the lumbar end plate 28 to 31 deep where he has 34 to 35.
- What is left, and why: the neck's canal depth reads 2 to 4 mm under Panjabi on the CT as on the label, at every source; CT series of the neck read it 13 to 15 mm, so this is his cadavers against a CT population, not the code. The upper plate's width in the neck still takes in the uncinate processes, which stand on the plate's own layer in a whole-vertebra label; separating them needs a label of the body (SPINEPS's subregions, which the census holds for gold tier 4) or an edge model on the CT. T10 to T12 still read 2 to 4 mm wide on both plates, where the rib heads articulate on the body itself.
- So the slide draws what is measured by the definitions above and says where it is not yet; no number is calibrated to Panjabi.
