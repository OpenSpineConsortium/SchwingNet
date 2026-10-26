# bordercall — handoff

Naming a vertebral border from the shape of the bone, with no count from C2. Ported out of
the CTSpinoPelvic1K thoracolumbar experiment (`03_ctspinopelvic1k_dataset/mdpa/`) with the
corpus and the border taken out as parameters, so it can be pointed at the full-spine
segmented census this folder owns.

## Run this first

```bash
cd 06_transitional_ct_census/code/bordercall
python run.py selftest --levels ../../../03_ctspinopelvic1k_dataset/mdpa/morphometrics/level_gradients.csv
```

It must print **selftest passed**. It re-derives the three published CTSpinoPelvic1K numbers
(adjacent-pair AUC 0.988, whole-span 0.998, junction placement 95.1%) from the released table
and fails if any has moved by more than 0.004. If it fails, the model or the features have
changed and nothing this copy produces is comparable with the published work. Fix that before
measuring anything new.

## Then, on your corpus

```bash
# 1. label volumes -> one wide row per case
python run.py measure --labels /path/to/labels --out levels.csv

# 2. ask whether shape carries a border
python run.py border --levels levels.csv --above T12 --below L1
python run.py border --levels levels.csv --above C7  --below T1
python run.py border --levels levels.csv --above L5  --below L6
```

`measure` writes the full spine by default. Narrow it when you only want part:

```bash
BORDERCALL_LEVELS=T11,T12,L1,L2,L3,L4,L5 python run.py measure --labels ... --out ...
```

## The four traps, in the order they will bite

**1. The identifier map is assumed, not detected.** `measure_levels.py` carries
`VERSE_NAMES`: 1–7 are C1–C7, 8–19 are T1–T12, 20–25 are L1–L6, 28 is T13. If your corpus
numbers its vertebrae any other way, every measurement will come out of the wrong bone and
nothing will raise — this programme has already shipped a release where pelvic incidence was
computed against the wrong map and the only symptom was a quality flag about a structure that
was plainly there. **Before the first measure run, print the identifiers actually present in
three volumes and check them against `VERSE_NAMES` by eye.** CTSpinoPelvic1K's own rule is to
resolve names with `ostk.labels.labels_for(volume)` rather than import a fixed map; if `ostk`
is available on your corpus, use it and make `VERSE_NAMES` follow it.

**2. Only the lumbar measurements are validated.** End-plate width, canal width and
transverse-process span were checked against published lumbar norms. The original file says
in as many words that those comparisons *do not transfer to thoracic levels*; only the height
and wedge columns are meant to be used above L1. Widening the identifier range makes the code
run over a whole spine. It does not make the numbers validated there. The first real piece of
work on a full-spine corpus is to check each measure at the cervical and thoracic levels
against a published series, the same way the lumbar ones were checked. Until then, treat a
cervical or upper-thoracic border result as a pipeline test, not a finding.

**3. The normalisation is the whole method.** Every measure is divided by that case's own
median across its measured levels, and ratios between measures carry no size at all. Lumbar
vertebrae are simply bigger than thoracic ones; a classifier given raw millimetres learns size
and reports a high AUC that says nothing about the border, where the two neighbours are nearly
the same size. If you change the feature builder, keep the normalisation or the numbers stop
meaning what they say.

**4. Folds are grouped by case.** Two vertebrae from one patient are not independent
observations. A random split leaks and inflates everything. `out_of_fold()` groups by case;
keep it that way, and keep any new split grouped too.

## Ground truth means a count from C2, and this corpus has none

Measured on all 802 CTSpinoPelvic1K volumes, 2026-10-25: **0 are countable.** The most
cranial labelled vertebra is T6 in the best case and T8 in the commonest (T8 210, T7 182,
T9 141, T6 121, T10 74, T11 33). It is abdominopelvic CT; C2 is never in the field.

So every number this method reports on that dataset is against the **labels**, which are a
reader's call at the border, and not against a verified count. `phenotype` records
`countable` per case and `sweep` refuses a corpus with none, which was exercised against this
very corpus rather than only against a synthetic case. Use a whole-spine corpus for any claim
about which border is named most robustly.

## What the method already found, so you know what to expect

On CTSpinoPelvic1K (802 abdominopelvic CT, 713 with the border in view):

| | |
|---|---|
| Junction placed at the labelled T12/L1 interspace | 95.0% |
| Typical column | 97.3% (n=656) |
| **Rib on a lumbar body (L1)** | **28.6% (n=14)** |
| **No rib on T12** | **50.0% (n=10)** |
| Six lumbar (L6) | 88.9% (n=18) |
| Four lumbar identifiers | 100% (n=10) |

The corpus average hides the result. Only the two *thoracolumbar* phenotypes break it; the
lumbosacral ones sit at or near the typical column, which is what a thoracolumbar classifier
should do. Expect the same shape of answer at any border: the classes that break it are the
ones whose anomaly is *at that border*.

Every failure runs in the direction the ribs do. A vertebra carrying a rib is called thoracic,
one without is called lumbar; of the 14 spines whose lowest rib-bearing vertebra is L1, ten are
called one level caudal and in every one the vertebra called thoracic is that rib-bearing L1.
Against the rib criterion: sensitivity 62.5%, specificity 97.0%, precision 41.7%.

## The mislabel question, and the trap inside it

Asked and answered in `03_.../mdpa/scripts/test_relabel_hypothesis.py`: if the border vertebra
is misnamed (no C2 to count from), the "failures" are the reader's and relabelling should fit
better. Three arms, each retrained from scratch:

| Labels | Whole span | T12/L1 pair |
|---|---|---|
| reader, as released | 0.9981 | 0.9880 |
| **rib-defined border** | **0.9986** | **0.9916** |
| model's own call (circular) | 1.0000 | 0.9998 |

**Relabelling to the model's own prediction always improves the score** — the target has been
moved to where the model already points. That arm is in there as the control that shows what a
circular improvement looks like, not as a result. The honest arm moves the border using the
*ribs*, which are not among the features, and it recovers about a third of the circular arm's
gain. So: partly yes, the poorly-performing cases are mislabelled relative to rib anatomy, and
most of the remaining disagreement is not explained that way.

What none of this settles: a rib on L1 could be a thirteenth thoracic vertebra above five
lumbar ones, or a rudimentary rib on a true L1. Those are different columns with the same rib
and only a count from C2 separates them. If your corpus is whole-spine and *does* contain C2,
you can settle it — that is the single biggest thing this corpus can do that CTSpinoPelvic1K
could not.

## Where to start on the census

1. Run `selftest`. Then check the identifier map on three volumes by eye (trap 1).
2. `measure` a few hundred cases first, not the whole corpus; confirm the measures look
   sane at the levels you care about before spending the compute.
3. Run `border` at T12/L1 first, because that is the one with a published answer to compare
   against. A wildly different number means the pipeline, not the anatomy.
4. Only then move to borders with no published answer (C7/T1, L5/S1).
5. Because the corpus has C2, add the true count as a column and ask the question
   CTSpinoPelvic1K could not: of the cases where shape and name disagree, how many are
   *counted* anomalies? That is `disagree`, which also runs the rib arm and the circular arm
   beside it. SchwingNet's `grid/bordercall.sbatch` runs steps 1 to 5 over the census's
   existing SPINEPS masks, counted from C2 by `tools/bordercall_corpus.py` there, a pilot of a
   few hundred countable cases first.

## Files

| File | What it is |
|---|---|
| `run.py` | CLI: `scheme`, `selftest`, `measure`, `phenotype`, `border`, `breakout`, `sweep`, `plot`, `disagree`, `panjabi`, `panjabi-corpus`, `panjabi-figures`, `synth-corpus`, `all` |
| `disagree.py` | step 5 below as a command: the count, the ribs and the circular arm, with denominators |
| `panjabi.py`, `junction.py` | the junction named from Panjabi's tables with no CT; the owner's junction predictor for the CNS slides, robust to lumbosacral anomalies by construction; at a TLTV the count and the ribs name the junction one level apart and the shape cannot choose (README, `panjabi`) |
| `junction_figures.py`, `records/`, `slides/make_junction_slides.py` | the five figures from a recorded `panjabi` run (textbook line figures, each with its CSV, caption and `FIGURES.md`), the recorded runs, and the six CNS slides built from them on the deck's own template |
| `synth_corpus.py` | a made-up corpus in SchwingNet's grid layout, so the commands run anywhere; nothing from it is a finding |
| `border.py` | corpus loading, shape features, grouped-CV logistic regression, border evaluation. No corpus-specific knowledge |
| `measure_levels.py` | label volumes -> wide per-level table. CTSpinoPelvic1K's `extract_level_gradients.py` with `LEVELS` widened to the full spine; everything else unchanged |
| `_separability_reference.py` | the original thoracolumbar experiment, kept verbatim as the thing `selftest` is checking against |

Dependencies: numpy, scipy, nibabel. No sklearn — the model is a logistic regression written
out, because the question is whether the shape carries the border at all, and a black box would
answer it less usefully.
