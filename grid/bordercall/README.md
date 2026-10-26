# bordercall

Name a vertebral border from the shape of the bone, with no count from C2.

A vertebra is normally identified by counting down from C2. On a scan that does not contain
C2 — which is most of them — that cannot be done, and at a transitional border the name is a
reader's call. This asks a different question: does the **shape** of the bone put the border
in the right place, and where does it fail?

Label volumes in, numbers and conference figures out. No CT needed, no training corpus
needed, no GPU. The model is a logistic regression written out, because the question is
whether the shape carries the border at all; if hand-built features on a linear model
separate it, a network will do better.

## Install

```bash
pip install numpy scipy nibabel matplotlib
```

Python 3.9+. That is the whole dependency list.

## Run

```bash
cd bordercall

# 1. Is the identifier map right for this corpus?   NOT OPTIONAL
python run.py scheme --labels /path/to/labels

# 2. Does this copy still reproduce the published answer?   NOT OPTIONAL
python run.py selftest

# 3. Everything else
python run.py all --labels /path/to/labels --outdir out/
```

`all` runs measure → phenotype → border → breakout → figures. The pieces separately:

```bash
python run.py measure   --labels LABELS --out levels.csv      # geometry, the slow step
python run.py phenotype --labels LABELS --out phenotype.csv   # ribs and counts
python run.py border    --levels levels.csv --above T12 --below L1
python run.py breakout  --levels levels.csv --phenotype phenotype.csv
python run.py sweep     --levels levels.csv --phenotype phenotype.csv
python run.py plot      --levels levels.csv --phenotype phenotype.csv --measure endplate
python run.py disagree  --levels levels.csv --phenotype phenotype.csv --above T12 --below L1
python run.py panjabi                                         # Panjabi's tables alone, no corpus
python run.py panjabi-corpus --levels levels.csv --phenotype phenotype.csv
python run.py synth-corpus --out out/synth                    # a made-up corpus to run the rest on
```

Any adjacent pair works: `--above C7 --below T1`, `--above L5 --below L6`. Narrow what gets
measured with `BORDERCALL_LEVELS=T11,T12,L1,L2,L3,L4,L5` in front of `measure`.

## The two commands not to skip

**`scheme`** prints the identifiers in your volumes against the map in `scheme.py` and stops
if they disagree. A wrong map does not raise — it returns a finite, plausible, wrong number.
On its first real run this check found that a local dataset copy still carried a retired
identifier and was a version older than assumed. If it complains, edit `scheme.py` and
nothing else.

**`selftest`** re-derives three published answers from the bundled fixture
(`testdata/ctspinopelvic1k_level_gradients.csv`, 802 records): adjacent-pair AUC 0.988,
whole-span 0.998, junction placement 95.1%. It fails past 0.004. Seconds to run, and the only
thing between you and a silently changed model.

## Which border is most robust — `sweep`

`border` answers one junction and `breakout` splits one junction by phenotype. `sweep` asks
the question those two cannot: across the candidate junctions, **which one holds up when the
spine is not typical.**

```
RANKED BY THE WORST ANOMALOUS PHENOTYPE, not by the corpus figure
  border           n   overall   typical     worst  worst class
  T12/L1         713     95.0%     95.0%     90.0%  Six lumbar vertebrae
  ...
```

It ranks on the **worst-scoring anomalous phenotype**, not on the corpus figure. Ranking on
the corpus figure picks the border with the most ordinary spines in it, which is the opposite
of the question: a method that names the border in 97 % of typical columns and 29 % of the
ones a surgeon would actually get wrong is accurate, not robust. The corpus and typical
figures print beside it so the gap is visible. A class under `--min-class` (10) is not ranked
and reads as "no failures seen".

Candidates are C6/C7, C7/T1, T1/T2, T11/T12, T12/L1, L1/L2, L5/L6. A pair whose levels the
corpus does not carry is skipped, so the same command serves a lumbar-only and a whole-spine
run.

## Ground truth means a count from C2

A verified vertebral name comes from counting down from C2. A record without C2 cannot supply
one — its border name is a reader's call, and a disagreement with it means nothing.

`phenotype` records `countable` per case, and **`sweep` scores only countable records** and
says how many it set aside. On a corpus with no C2 at all it refuses outright:

```
STOP. No record in this corpus contains C2, so no border name here is a
verified count -- it is a reader's call, and a disagreement with it means
nothing.
```

`--allow-uncountable` overrides it and every number is then marked provisional. The dataset
this method was built on is itself uncountable — abdominopelvic CT, no C2 — which is why its
95 % is reported against *labels*, not against a verified count.

## Where the shape disagrees with the name: `disagree`

On a corpus counted from C2, `disagree` reports three things at one border and the difference
between them is the point. Against the **count's** names: the out-of-fold accuracy, the
disagreements by class with their denominators, and how many of the disagreements fall in a
counted anomaly (four or six lumbar identifiers, a thirteenth rib-bearing body, no rib on the
twelfth), which is the question CTSpinoPelvic1K could not answer. Against the **ribs**, an
independent reading (the census's rib table sets the lowest rib-bearing body to T12, or the
first to T1): the names shifted, the model refitted out of fold and scored against them, and
how many of the count's disagreements the ribs side with. And the **circular** arm, the
disagreements relabelled to the model's own call, refitted and scored, printed beside the rib
arm so the rib arm can be read against it: it proves nothing, and it is never reported alone.

## Naming the junction from Panjabi's tables alone: `panjabi`

`junction.py` names the cervicothoracic (C7/T1) and thoracolumbar (T12/L1) junctions in a
window of consecutive bodies from the **shape profile** down the window, fitted on no CT at
all: `panjabi.py` draws synthetic columns from Panjabi's published means and spreads (a patient
size, a spine-wide tilt, per-level noise, and the lumbosacral and thoracolumbar phenotypes as
re-namings and blends of the same table), and the model is read off the table.

Two arms. The **profile template** scores every naming an 11-13 thoracic, 4-6 lumbar column
allows for an n-level window, each measure's log-likelihood with a free offset per measure (a
patient's size and the measurement convention both cancel), and places the junction by the
posterior over cuts. The **local rule** is a logistic regression on the log ratios of each
level to its neighbours at one and two levels, the ablation: the T12/L1 step is small beside
the per-level spread, so it is weak there, and it says so. `explain` prints, per measure, the
log-likelihood gap between the best naming and the runner-up, which is the explanation a slide
shows.

The truth every table scores against is the count's: the 19th body from C2 is L1 whatever
its shape or its rib, so a thoracic-shaped body in that place (a rib-bearing L1, which a rib
reading calls a thirteenth thoracic vertebra) and a lumbar-shaped 18th body (a rib-less T12)
are shape hypotheses the template carries at the count's cut, and the rib reading names those
columns one level apart (`panjabi.py`, `Column.cut(..., truth="ribs")`). `blend_sweep` scores
one set of calls both ways. The posterior takes a flat prior over where the cut falls (the
namings of one cut are averaged, not summed), so a cut is not favoured for having more ways to
be named.

On synthetic columns (`python run.py panjabi`, three measures a CT mask gives, windows of 5 to
12 levels, 500 per class) the template names C7/T1 exactly in 85 windows of 100 and within one
level in 97, T12/L1 exactly in 59 to 68 and within one level in 88 to 92, the same for every
phenotype within the intervals; a lumbosacral twin (the same column with four or six lumbar
bodies, whole) changes either call in fewer than 1 in 100; as the thoracolumbar transitional
body (TLTV) blends from its own shape to its neighbour's, the count's junction is still named
exactly in 53 to 67 of 100 and within one in 83 to 92, while the same calls score 6 to 21
against the rib naming: the hard case is the convention, which the shape cannot choose, not the
shape. Those are numbers about Panjabi's tables and the generator, not about a spine:
`panjabi-corpus` runs the same two models on a measured corpus counted from C2, by phenotype,
with bordercall's own model fitted on that corpus out of fold printed beside them as the
ceiling, and only that table is a result. Adding the canal depth, which Panjabi gives and a CT
mask gives too, lifts the synthetic C7/T1 figure to 89 and T12/L1 to 68 to 74.

`panjabi-figures` draws the five figures (the profile, one posterior, the width curve, the
twins, the blend) from a run's JSON, every number read and none typed, in the style of a
textbook's line figures: black ink on white, a serif face, series told apart by line and
marker and never by hue, panel letters, and the column drawn to Panjabi's millimetres. Beside
each PDF and PNG it writes the CSV of the numbers drawn and the caption, and one `FIGURES.md`
with the hash of the run, the reference and the code, so a figure can be checked against its
numbers and rebuilt byte for byte. The runs the figures come from are kept under `records/`
(its README says what made each), and `slides/make_junction_slides.py` builds the six CNS
slides from a record and its figures on the deck's own template, with a check that no word of
the confidential work is on a slide or in a note:

```bash
python run.py panjabi-figures --json records/panjabi-2026-10-26/three-measures/panjabi_junction.json --outdir figures/junction
python slides/make_junction_slides.py --template /path/to/deck.pptx --out out/junction_slides.pptx --figures figures/junction
```

`synth-corpus` writes a made-up corpus in the layout SchwingNet's grid job writes (the count's
names, the rib reading, the fabricated anterior height and transverse-process span the
published model needs), so every command downstream of `measure` can be run end to end with no
CT. Nothing from it is a finding.

## Reading the output

One corpus number will mislead you. On CTSpinoPelvic1K the corpus figure is 95%, and broken
out by phenotype:

| Class | In field | Correct | |
|---|---|---|---|
| Rib on a lumbar body | 14 | 5 | **35.7%** |
| No rib on the last thoracic | 10 | 5 | **50.0%** |
| Six lumbar vertebrae | 18 | 16 | 88.9% |
| Four lumbar identifiers | 6 | 6 | 100% |
| Typical column | 665 | 645 | 97.0% |

Two populations averaged together. Always run `breakout`, and read a class of fewer than
about twenty cases as "no failures seen" rather than as an accuracy.

The failures are directional, and that is the part worth trusting. Every one runs the way the
ribs do: a vertebra carrying a rib is called thoracic, one without is called lumbar. The
classifier never sees a rib — its features are body and canal measures — so the ribs are an
independent check. Against them: sensitivity 62.5%, specificity 97.0%, precision 41.7%.

## The figures

`plot` writes a PDF and a PNG. **Use the PDF** in a slide or a poster: vector, text stays text
(`pdf.fonttype 42`), no blurring on a projector.

- `levels_<measure>` — every case, one violin per level, published reference interval over it.
- `classes_<measure>` — one panel per phenotype over the typical column in grey, with the
  per-class accuracy in each title.

Conventions, all deliberate: **vertebral body class on the y axis, cranial at the top, the
measurement on the x axis**, which is the axis order of the morphometry plates a spine
audience has read for thirty years. Anomalous classes are points rather than violins below
`--violin-min` (40), because a violin over fourteen cases draws a density through almost
nothing. `--scale 1.3` for a poster.

## The reference table

`bordercall/reference/panjabi_full_spine.csv`, used by default: 108 rows over **C2–C7, T1–T12
and L1–L5** for end-plate width, posterior body height, canal width, canal depth and pedicle
width, from

- Panjabi et al., *Cervical human vertebrae*, Spine 1991;16(8):861–869, Tables 2–4
- Panjabi et al., *Thoracic human vertebrae*, Spine 1991;16(8):888–901, Tables 3–5
- Panjabi et al., *Human lumbar vertebrae*, Spine 1992;17(3):299–306

Both 1991 papers are scans with **no text layer**, so every value was read from rendered page
images; automatic text extraction of the thoracic canal table interleaves rows and columns and
must not be parsed. `build_panjabi.py` re-checks its own T11/T12 against an earlier
independent transcription and fails on a disagreement.

Dispersion is always the **standard error** as printed; the population SD is `sem*sqrt(12)`.
Drawing the SEM as if it were an SD gives an interval 3.5× too narrow. C2 has no upper
end-plate row — the dens occupies it — so `endplate` and `h_post` start at C3.

Supply your own with `--reference FILE`, columns `measure, level, mean, sem, n` (or `sd`).
`--no-reference` draws none.

## Traps

1. **The identifier map is assumed, not detected.** Run `scheme` first.
2. **Only the lumbar measurements are validated.** End-plate width, canal width and
   transverse-process span were checked against published lumbar norms, and the measurement
   code states that those comparisons do not transfer to thoracic levels. Widening the range
   makes the code run over a whole spine; it does not make the numbers validated there. Until
   each measure is checked against a published series at your levels, a cervical or
   upper-thoracic result is a pipeline test, not a finding.
3. **The last lumbar level is withheld for end-plate and pedicle width.** The body is isolated
   by cutting at the anterior wall of the canal, and there the transverse processes arise in
   front of that cut, so the cut keeps them. A property of the measurement, not of one cohort.
   `--no-withhold` overrides.
4. **The per-case normalisation is the whole method.** Every measure is divided by that case's
   own median across its levels. Lumbar vertebrae are simply bigger than thoracic ones; raw
   millimetres teach a classifier size, which says nothing at a border where the two
   neighbours are nearly the same size.
5. **Folds are grouped by case.** Two vertebrae from one patient are not independent.

## If your corpus has C2

It can answer what the originating dataset could not. A rib on L1 may be a thirteenth thoracic
vertebra above five lumbar ones, or a rudimentary rib on a true L1 — different columns, the
same rib, and only a count from C2 separates them.

A warning on how to test it: relabelling the disagreements to the model's own prediction and
re-scoring is **circular**, because the target has moved to where the model already points.
That arm reached 0.9998 against a 0.9880 baseline. Relabelling by an *independent* criterion
(the ribs) reached 0.9916, about a third as far. Always put the circular arm beside the honest
one.

## Files

| File | What it is |
|---|---|
| `run.py` | the CLI |
| `scheme.py` | the identifier map, in one place, with its check |
| `measure_levels.py` | label volumes → wide per-level table |
| `phenotype.py` | label volumes → per-case phenotype, from the labels alone |
| `border.py` | features, grouped-CV logistic regression, border evaluation |
| `plots.py` | the two conference figures |
| `sweep.py` | every candidate border ranked by its worst anomalous class |
| `disagree.py` | the count, the ribs and the circular arm where the shape disagrees with the name |
| `panjabi.py` | synthetic columns from Panjabi's tables, with the phenotypes and their twins |
| `junction.py` | the junction named from the shape profile, fitted on the tables alone |
| `junction_figures.py` | the five junction figures from a recorded run, with their CSV, caption and `FIGURES.md` |
| `records/` | the recorded `panjabi` runs the figures and slides are drawn from |
| `slides/` | the CNS slides built from a record and its figures |
| `synth_corpus.py` | a made-up corpus in the grid job's layout, to run the commands on |
| `reference/` | the Panjabi tables and the script that builds them |
| `render_anchors.py` | the 3-D phenotype gallery |
| `testdata/` | the fixture `selftest` runs against |

`HANDOFF.md` is the short version, with what the method has already found.
