# Panjabi's measurements on a SPINEPS segmentation

How the reference values in `reference/panjabi_full_spine.csv` are taken on a real
segmentation, so a cohort can be held against the cadaveric series rather than against
nothing.

[SPINEPS](https://github.com/Hendrik-code/spineps) (Möller, TUM; Apache-2.0) emits two
masks. The **subregion** mask names parts of a vertebra; the **instance** mask says which
vertebra each voxel belongs to. Between them they carry most of the structures Panjabi
measured on dry bone.

```bash
python spineps_map.py --table                                  # the mapping, then stop
python spineps_map.py --subregion sub.nii.gz --instance inst.nii.gz --out measures.csv
```

## The identifiers already agree — no remapping

With **VERIDAH** labelling, SPINEPS writes:

| SPINEPS | Structure | `scheme.py` |
|---|---|---|
| 1 | C1 | 1 |
| 2–7 | C2–C7 | 2–7 |
| 8–19 | T1–T12 | 8–19 |
| 28 | T13 | 28 |
| 20 | L1 | 20 |
| 21–25 | L2–L6 | 21–25 |
| 26 | Sacrum | 26 |

Identifier for identifier, that is the VerSe-native scheme this package already uses, so a
SPINEPS+VERIDAH instance mask needs no translation. `100+X` is the disc below vertebra X and
`200+X` its endplate; this package ignores both.

**Without VERIDAH the instance labels are arbitrary indices** and carry no anatomy. Run
`run.py scheme` on them and it will say so. Do not assume index 20 is L1 in an unlabelled
instance mask.

## What maps

| Panjabi | What he measured | SPINEPS label | How it is taken here |
|---|---|---|---|
| EPWu / EPDu | upper end-plate width, depth | 52 `Vertebral_Body_Endplate_Superior` | lateral / AP extent |
| EPWl / EPDl | lower end-plate width, depth | 53 `Vertebral_Body_Endplate_Inferior` | lateral / AP extent |
| VBHp | body height at the posterior wall | 49 `Vertebra_Corpus_border` | median column height in the posterior 20 % |
| SCW / SCD | canal width, depth | 61 `Spinal_Canal` | lateral / AP extent |
| TPW | transverse process span | 43 + 44 `Costal_Process_*` | tip-to-tip lateral extent |
| SPL | spinous process length | 42 `Spinosus_Process` | body centroid to farthest spinous voxel |

**A maximum extent is not always a diameter.** For the end-plates and the canal, the chord
Panjabi named *is* the maximum extent in that axis, so an extent is faithful. For **VBHp it
is not**: that is the height at the posterior wall, not the tallest column anywhere in the
body, and the two part company in a wedged or collapsed vertebra — which is precisely where
the measurement earns its keep. It is taken in a posterior slab here, never as a maximum.

## What does not map: the pedicle

**SPINEPS has no pedicle label.** It labels the whole posterior arch as 41
`Arcus_Vertebrae`, which contains the laminae, the articular process bases and the pedicles
together. The extent of 41 is not a pedicle width and is not related to one by any constant.

`spineps_map.py` **refuses** to emit PDW or PDH rather than approximate them. Returning the
arch's extent under a pedicle name would be a finite, plausible, wrong number — the failure
this programme keeps meeting, and the reason `scheme.py` exists.

Two honest ways to get it, when it is needed:

1. **Find the waist geometrically.** The pedicle is the narrowest cross-section on the path
   from the body (49) to the arch (41). Walk posteriorly from the body–arch junction in thin
   slabs and take the minimum cross-sectional area; its principal axes are PDW and PDH. This
   is a real method and needs validating against a series before its numbers are quoted.
2. **Use a segmenter that labels the pedicle.** Then map its label here and the measurement
   becomes an extent like the others.

Until one of those is done, the pedicle rows of the reference table have nothing on the
segmentation side to compare with. They are kept in the CSV because the papers publish them
and the next piece of work may supply the other half.

## Reading a result against the reference

`reference/panjabi_full_spine.csv` gives `mean` and `sem` per measure per level, from C2 to
L5. Two things to get right:

- **Dispersion is a STANDARD ERROR.** The population SD is `sem * sqrt(12)`. A reference band
  is `mean ± 1.96 × sem × sqrt(12)`. Drawing the standard error itself gives an interval 3.5×
  too narrow, and every cohort then looks aberrant for a reason that is arithmetic rather
  than anatomical. `plots.py` already does this conversion; anything else must too.
- **The cohorts are not alike.** Twelve embalmed cadaveric spines against a living cohort on
  CT. A systematic offset is expected and is not evidence that either is wrong.

## What the reference does not contain

- **No anterior body height.** These papers publish VBHp only. Pairing it with an anterior
  height measured off a segmentation compares two different things.
- **C2 has no upper end-plate row** — the dens occupies it — so `endplate`, `endplate_depth`
  and `h_post` start at C3 while the canal and pedicle rows run from C2.
- Surface areas, angular dimensions, pars interarticularis, rib articulations and the
  uncovertebral joints are in the papers and are not transcribed. The PDFs are in
  `reference/papers/` so they can be read when something needs them.

## Validation still owed

The measurements above were checked against published **lumbar** norms only. The measurement
code states that end-plate width, canal width and transverse-process span do not transfer to
thoracic levels. The reference table now carries Panjabi's cervical and thoracic values
precisely so that check can be made: take each measure on a segmented cohort at C2–C7 and
T1–T12, compare with the table, and report the offset before quoting any cervical or
thoracic number as a finding.
