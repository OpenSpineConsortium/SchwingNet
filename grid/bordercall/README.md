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

The literature survey behind the statistical reporting here -- what mathematical problem this is, and what software does and does not exist for it -- is committed at `research/solver-survey-2026-10-26/` (start at its `INDEX.md`). `CHECKPOINT_2026-10-26.md` records the state of the work, and `HANDOFF.md` has a numbered plan for running the measure-set study on the Wayne State grid, which needs no CT and no label access. The neighbour-identity study, naming a vertebra from the field of view around it (the target among the visible bodies, on the owner's word of 2026-10-26, with naming from the neighbours alone kept as the obscured case) and asking whether one radiographic plane holds the information, is answered in `docs/NEIGHBOUR_IDENTITY_RESULTS.md` from `records/neighbour-2026-10-26/`. Which vertebrae of a normal spine can be identified best, and by what (the field's width, the plane, the measures, abstention, the patient's size), framed from Kunkel 2010's prediction equations, is answered in `docs/LEVEL_IDENTIFIABILITY_RESULTS.md` from `records/identify-2026-10-26/`. Whether any formula, function or network of the measurements of 1 to n consecutive bodies names a vertebra exactly, and which weaker statements (its region, the side of a border, a run of levels) a field can make nearly certainly, is answered in `docs/EXACT_IDENTIFICATION_RESULTS.md` from `records/exact-2026-10-26/`. Five slides on that answer, for a CNS talk or a NeurIPS oral, are built from the same record by `python run.py exact-slide-figures` (a NeurIPS set of seven figure panels and a results-only CNS set of six, each panel drawn at the exact inches its deck gives it) and `python slides/make_exact_slides.py` (both decks, every figure, word and equation an element of its own; the NeurIPS equations native PowerPoint mathematics with their LaTeX kept as alternative text; the CNS deck results only, with no equation and no method word anywhere in the file; both marked confidential until built with `--public`); see `records/README.md` and HANDOFF step 10, which lists what the results-only talk cuts and what the TTO must read first. A white paper sets the exact rule against the labeller upstream of LevelCheck, the Johns Hopkins registration that copies a labelled CT's levels onto the radiograph: where those labels come from and what each source says about being wrong, what the rule can prove and what the published counts can bound, how the rule's posterior is carried through the registration onto every overlaid label, how it runs on one or two C-arm views with no CT, and a randomized browser study of surgeons using either aid, with its analysis plan and power. It is `docs/SCHWINGCHECK_LEVELCHECK.md`; its new computations are `python run.py second-opinion`, `python run.py whitepaper-checks` and `python run.py study-power`, recorded in `records/whitepaper-2026-10-26/` (HANDOFF step 11, which lists what the TTO must read first).

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
python run.py covariance                                      # what the literature can and cannot supply
python run.py covariance --sweep --out ../records/covariance-sweep.json
python run.py enumerate --shard 0 --of 16 --out out/shard_0.json   # every subset, sharded
python run.py enumerate --gather out/shard_*.json --out out/gathered.json
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

## The reference table and the papers

`bordercall/reference/panjabi_full_spine.csv`, used by default: **296 rows over C2-C7,
T1-T12 and L1-L5**, every linear dimension of the body, canal and pedicle tables of all three
papers. The PDFs themselves are in `bordercall/reference/papers/`, with a README naming which
table and page each value came from.

| Measure | Panjabi | Levels |
|---|---|---|
| `endplate`, `endplate_depth` | EPWu, EPDu | C3-L5 |
| `endplate_lower`, `endplate_lower_depth` | EPWl, EPDl | C2-L5 |
| `h_post` | VBHp | C3-L5 |
| `canal_w`, `canal_ap` | SCW, SCD | C2-L5 |
| `pedicle`, `pedicle_h` (and `_left` / `_right`) | PDW, PDH | C2-L5 |

Rebuild with `python reference/build_panjabi.py`. It carries two checks and fails on either:
T11/T12 against an earlier independent transcription, and the pedicle means against the
lumbar paper's own prose ("the width was initially 8.6 mm at L1, then decreased to 8.2 at
L2"). That second check caught a real error in the inherited data: `h_post` L1 carried a
standard error of 0.92, which is `canal_w` L1's, one table away. The table reads 1.03.

Both 1991 papers are scans with **no text layer**, so every value was read from rendered page
images; automatic text extraction of the thoracic canal table interleaves rows and columns
and must not be parsed.

Dispersion is always the **standard error**; the population SD is `sem*sqrt(12)`. Drawing the
SEM as an SD gives an interval 3.5x too narrow. C2 has no upper end-plate row -- the dens
occupies it -- so `endplate`, `endplate_depth` and `h_post` start at C3. There is **no
anterior body height** in these papers.

Supply your own with `--reference FILE`, columns `measure, level, mean, sem, n` (or `sd`).
`--no-reference` draws none.

## Taking these measurements on a SPINEPS segmentation

`bordercall/SPINEPS_MAPPING.md` and `bordercall/spineps_map.py`.

```bash
python spineps_map.py --table                                  # the mapping, then stop
python spineps_map.py --subregion sub.nii.gz --instance inst.nii.gz --out measures.csv
```

With VERIDAH labelling, SPINEPS's instance identifiers **already are** the VerSe-native
scheme this package uses -- 1 C1, 2-7 C2-C7, 8-19 T1-T12, 28 T13, 20-25 L1-L6, 26 sacrum --
so no remapping is needed. Without VERIDAH the instance labels are arbitrary indices and mean
nothing anatomically.

Six of Panjabi's structures have their own SPINEPS subregion label and are measured as
geometric extents. **The pedicle does not.** SPINEPS labels the whole posterior arch as 41
`Arcus_Vertebrae` and never isolates the pedicle, so PDW and PDH are **refused** rather than
approximated: an extent of 41 is not a pedicle width, and returning one would be a finite,
plausible, wrong number. The mapping doc names the two honest ways to get it.

## The between-measure correlation: `covariance`

Synthetic columns draw each measure's departure from its published mean **independently**.
Real vertebrae do not work that way -- a wide body tends to come with a deep one -- so
independence hands the classifier more information than it would really have, and **every
accuracy this package reports at the default is an upper bound.**

No published source gives the within-patient value. `run.py covariance` shows the search
rather than asserting a number:

- Panjabi's tables could only hide it in the **ratio rows**, since a mean of per-specimen
  ratios carries a covariance and a ratio of means does not. All three two-decimal rows
  reproduce `mean(a)/mean(b)` to within 0.0044 against a 0.005 rounding tolerance. They are
  ratios of means. The thoracic row is printed to one decimal and is reported as
  **uninformative** rather than counted either way. And n = 12: a correlation from twelve
  specimens has a 95 % interval of roughly 0.00 to 0.84.
- **Kunkel et al. (J Anat 2010;216:320) is the near miss worth knowing about.** Alone in the
  lineage they regress each parameter on *another parameter* rather than on level, with R²
  up to 0.982 -- the exact shape of relation wanted. But each of their data points is the
  **mean at one level across the 12 cadavers**, so the fit runs over sixteen level means, not
  over individuals. Reading a within-patient correlation out of it is the ecological fallacy,
  in the direction that inflates.

So `r` is swept, not assumed. `--sweep` reruns the whole measure-set comparison across
r = 0.0 … 0.9, drawing fresh columns at every point, selecting on one seed and scoring on
another so the chosen measure set is scored on columns the choice never saw.

**r is unidentified, not merely unknown**, so a single accuracy is the wrong object to
report. Nothing in the available data can pin r down, which is Manski's situation exactly,
and the right report is an **identified set** -- the values the quantity takes as r ranges
over everything it could be -- with an **Imbens-Manski** interval rather than a naive
`[min - 2 se, max + 2 se]`, which over-covers because only one end can bind at a time:

```
cervico-thoracic C7/T1
  baseline_3 accuracy in [0.4150, 0.4225]   (Imbens-Manski 95 % [0.3977, 0.4398])
  spineps_7  accuracy in [0.6950, 0.7100]   (Imbens-Manski 95 % [0.6795, 0.7253])
  difference [+0.2750 at r=0.40, +0.2925 at r=0.00], IM 95 % [+0.2521, +0.3152]
  worst case over r: +0.2750 +/- 0.0138  (20.0 s.e. from zero)

thoraco-lumbar T12/L1
  difference [+0.1154 at r=0.40, +0.1262 at r=0.90], IM 95 % [+0.0934, +0.1481]
  worst case over r: +0.1154 +/- 0.0130  (8.9 s.e. from zero)
```

**The accuracy is not identified; the conclusion drawn from it is.** The identified set of
the difference lies entirely above zero at both junctions, so the *size* of the gain stays
unknown while its *direction* is known exactly: seven measures beat three whatever r turns
out to be. That is the strongest honest claim available when a parameter cannot be measured,
and it is a statement about the **sign**, not about the value -- so quote the worst case over
r and the interval, never the r = 0 figure alone. If a future comparison's sign *does* turn
over inside the set, the command says so and names the crossing r instead of picking a
winner.

Recorded in `records/covariance-sweep.json`. `--from-json` re-reports from that record
without re-running the sweep, so a change to the reporting is checked against a fixed run
rather than a fresh draw that moves underneath it.

### What the grid can be hiding, and why refining it is not the check

min and max over a grid are a **relaxation** of min and max over the interval: dropping the
off-grid r enlarges what is being minimised over, so the reported worst case is an
**overestimate** of the true one -- the unsafe direction for any claim resting on it. The gap
is bounded by `L * h / 2` and is unbounded without an `L`.

**Refining the grid is not a reliable check on its own.** On a profile with a narrow dip
between points, successive refinements can return the identical wrong value and falsely
confirm; and Monte Carlo noise biases the same quantity the other way, growing as the grid
thickens, so agreement between a coarse and a fine grid is not evidence either. So the
command measures the assumption instead of asserting it:

```
how much the grid can be hiding, measured rather than assumed:
spineps_7  NOT monotone in r, |slope| <= 0.0333, grid gap L*h/2 = 0.0033 (0.3 MC s.e.)
           the measured slope 0.0333 is below the noise floor 0.1373, so this
           run cannot see a slope -- it has not shown there is none
```

**A is measurably not monotone in r**, which is the opposite of what this file asserted
before it was measured. What saves the conclusion is not monotonicity but the size of the
margin: the grid gap is a fraction of one Monte Carlo standard error, while the sign clears
zero by 8.9 (T12/L1) to 20.0 (C7/T1) standard errors. The margin dwarfs both error terms by
twenty- to sixty-fold. That is the argument to make; the monotonicity argument is not
available and should not be repeated.

The measured `L` is a secant estimate from the same grid, so it is a **lower** bound on the
true `sup |A'|` and the gap it reports is indicative, not certified. Certifying it needs an
independent bound on A's derivative in r, which this package does not have and does not
claim. `--r-grid 0,0.1,0.2,...,0.9` runs a finer grid when that matters.

### Does the interval actually cover? Measured, not assumed

The Imbens-Manski construction has a documented small-sample under-coverage, and Stoye (2009)
argues the result "implicitly assumes superefficient estimation of a nuisance parameter", so
it is pointwise valid but not uniformly so. On top of that, this package estimates the
endpoints by taking min and max over a grid of noisy Monte Carlo values, which is **not** how
the formula assumes they arrive. So `covariance.coverage_check()` measures coverage against a
known truth. At 20,000 trials, a true set of [0.40, 0.45] and se = 0.01:

| regime | covers the true value |
|---|---|
| unbiased endpoints, at the lower end | **0.9515** ± 0.0015 |
| unbiased endpoints, at the upper end | **0.9520** ± 0.0015 |
| min/max over a 6-point noisy grid, true minimum | 0.9916 ± 0.0006 (over-covers) |
| min/max over a 6-point noisy grid, true maximum | 0.9925 ± 0.0006 (over-covers) |
| **the same, with a 0.02 dip hidden between grid points** | **0.4242** ± 0.0035 |

The formula is right. The pipeline is conservative when the grid can see the extremum,
because the min of noisy values sits below the true min. And **a dip of 0.02 -- two accuracy
points, far too small to notice in a printed table -- takes coverage from 0.95 to 0.42.**
That is the measured reason monotonicity or a Lipschitz bound is load-bearing rather than a
formality, and the reason the accuracy interval here is reported as uncertified.

**The sign conclusion is a different matter and survives this.** Breaking coverage of the
accuracy takes a dip of about 0.02; overturning the sign would take one the size of the
margin, which is 0.1154 to 0.2750 -- five to fourteen times larger, and grossly visible. A
test asserts that ratio, so it fails if a future run erodes the margin toward the dip size
that is enough to break the interval.

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
| `covariance.py` | the between-measure correlation: what the literature supplies, the exchangeable draw, the sweep that shows the conclusion survives it, the partial-identification reporting (identified set, Imbens-Manski interval, sign invariance), the measured grid error and coverage check, and exhaustive subset enumeration |
| `disagree.py` | the count, the ribs and the circular arm where the shape disagrees with the name |
| `panjabi.py` | synthetic columns from Panjabi's tables, with the phenotypes and their twins |
| `junction.py` | the junction named from the shape profile, fitted on the tables alone |
| `junction_figures.py` | the five junction figures from a recorded run, with their CSV, caption and `FIGURES.md` |
| `exact_slide_figures.py` | the figure panels of the exact-rule slides from the recorded `exact` run, a NeurIPS set and a results-only CNS set (`cns/`), each panel at the inches its deck gives it, with their CSV, caption and one `FIGURES.md` per set |
| `second_opinion.py` | what the exact rule says about a registration's answer one level off, on the exact study's scoring columns, for the white paper |
| `study_power.py` | the power, size and critical values of the white paper's randomized reader study, by simulation, for the two-arm design and the three-arm design (`run_three`) |
| `whitepaper_checks.py` | the within-one Bayes rule, and anomalous columns scored by the count from C2, for the white paper |
| `records/` | the recorded `panjabi` runs the figures and slides are drawn from |
| `slides/` | the CNS junction slides, and the exact-rule slides for the CNS or NeurIPS, each built from a record and its figures |
| `synth_corpus.py` | a made-up corpus in the grid job's layout, to run the commands on |
| `reference/` | the Panjabi tables and the script that builds them |
| `render_anchors.py` | the 3-D phenotype gallery |
| `testdata/` | the fixture `selftest` runs against |

`HANDOFF.md` is the short version, with what the method has already found.
