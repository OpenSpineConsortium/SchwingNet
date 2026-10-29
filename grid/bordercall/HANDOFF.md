# bordercall — handoff

Naming a vertebral border from the shape of the bone, with no count from C2. Ported out of
the CTSpinoPelvic1K thoracolumbar experiment (`03_ctspinopelvic1k_dataset/mdpa/`) with the
corpus and the border taken out as parameters, so it can be pointed at the full-spine
segmented census this folder owns.

## Where this stands at the checkpoint of 2026-10-26, 03:10 UTC

> **Later the same day**, a literature survey of optimisation software turned into six commits
> that changed how every synthetic number here is reported, and added `run.py enumerate`.
> `CHECKPOINT_2026-10-26.md` records what changed and what is still open;
> `research/solver-survey-2026-10-26/INDEX.md` is the survey. **If you are a new account picking
> this up to run on the grid, go to "FOR THE NEXT ACCOUNT" below** — it is a numbered plan with
> the Slurm scripts in it, and it needs no CT, no labels and no data access.

Written on the owner's word to push everything and hand off, so that a new account's project
continues from git alone. Nothing needed is held only in a thread, a scratch folder or OneDrive.
The commands further down that name `06_transitional_ct_census` and `03_ctspinopelvic1k_dataset`
are from the spine-program origin; in this repository it is `cd bordercall && python run.py ...`,
and `selftest` takes no argument.

### In this repository

| What | Where | Rebuilt by |
|---|---|---|
| The method and its tests | `bordercall/` (`run.py`, `panjabi.py`, `junction.py`, `junction_figures.py`, `disagree.py`, `synth_corpus.py`, `reference/panjabi_full_spine.csv`) and `tests/` | `cd bordercall && python run.py selftest`; `python -m unittest discover -s tests` from the repository root (37 tests; 36 pass, and `test_junction_figures.JunctionFigures` errors in `setUpClass` on a matplotlib colour fault that is present on `origin/main` independently of any of this work) |
| The recorded runs every figure and slide number is read from | `records/panjabi-2026-10-26/three-measures/panjabi_junction.json` and `four-measures/panjabi_junction.json` | the commands in `records/README.md`; a re-run is a new record beside these, never a replacement |
| The five figures: PDF, PNG, the CSV of the numbers drawn and the caption of each, with `FIGURES.md` naming the record and the code by sha256 | `records/panjabi-2026-10-26/figures/` | `cd bordercall && python run.py panjabi-figures --json ../records/panjabi-2026-10-26/three-measures/panjabi_junction.json --outdir ../figures/junction` (the root `figures/` is ignored by git; the copy under `records/` is the committed one) |
| The six CNS slides, as PowerPoint and as PDF | `slides/junction_slides.pptx`, `slides/junction_slides.pdf` | `python slides/make_junction_slides.py --template <deck> --out out/junction_slides.pptx --figures records/panjabi-2026-10-26/figures`, where `<deck>` is the owner's CNS deck, which spine-program holds at `provisional_patent/wsu_tto/TTO_package_2026-09-25/followup/CNS2026_spine_talk_v10_2026-09-26_CNS_template_ACCME.pptx` (sha256 59497c01f0cadee96a9a6a96489015bfc72be3d366051308c6345426ed72a3f5) and this repository does not |

Pull request #1 (merged as aa31c7a) brought the code, the tests and the records; the pull
request after it brings the figures and the slides, which until then were attached to a thread
and in a `figures/` that git ignored.

### What the slides say, and what they do not

Everything on them is fitted to Panjabi's published tables and scored on synthetic columns drawn
from those tables: no CT, no patient and no SPINEPS mask has been measured yet. The numbers are in
the CSV beside each figure; the headline ones, three measures (end-plate width, posterior height,
canal width):

- A window of eight bodies names the cervicothoracic junction exactly in 85.6% of 250 windows
  and within one level in 98.4% (`junction_width.csv`, row `ct,8`); the thoracolumbar junction is
  the hard one, exact in the sixties and within one in the nineties (row `tl,8`).
- By class, 500 windows each (`junction_twins.csv`, `phenotype` rows): C7/T1 exact in 85.2% of
  every class; T12/L1 exact in 59.4% (six lumbar) to 65.2% (four lumbar).
- A lumbosacral twin, the same column with the lumbosacral levels added or taken away, changes
  the call in 0.4% (four lumbar) and 0.8% (six lumbar) of 500 at either junction (`twin` rows):
  the anomaly at L5/S1 leaves the two junctions where they were, which is what the owner asked
  the predictor to be robust to.
- At a thirteenth thoracic body the count and the ribs name the junction one level apart and the
  shape cannot choose; `junction_blend.csv` scores both truths side by side. That is the TLTV
  case the owner named as the hard one, and it is not solved here.

### Not done, in the order to take it

1. The grid pilot. The owner approved two CPU jobs on 2026-10-25 at 23:56 UTC ("Two CPU jobs:
   pilot, then full"); none has been sent. The route is in place: SchwingNet #404 (merged) gives
   `grid/gate.sh` the word `bordercall <pilot|full>`, `grid/bordercall.sbatch`,
   `tools/bordercall_corpus.py` (the count from C2 over the census's existing SPINEPS masks, the
   ribs from the census's rib table) and `grid/bordercall/`, this repository vendored at 6938a2e;
   symphony-template #495 (merged 03:08 UTC) gives grid-accounts.yml the dispatch word
   `schwingnet-bordercall-<stage>`; hpcworker #50 (the gate's pass-through) had its review
   section added at 03:04 UTC and its check re-run, and is merged next. Then, each on a dispatch
   of symphony-template's grid-accounts.yml, action `job`: `update`; `schwingnet-status` once
   (last sent 2026-10-25 23:41 UTC; never twice for one read); `schwingnet-bordercall-pilot`;
   read its report; `schwingnet-bordercall-full` only if the report says countable > 0 and the
   pilot ended well. A third job needs the owner's word and count again.
2. What the pilot answers that nothing here does: the published T12/L1 answer against a count
   from C2 on real masks; the per-class tables with denominators; the rib arm beside the circular
   arm (`disagree`); the `sweep` winner with its typical-versus-worst gap.
3. The owner's rules from this thread, which stand: only full-spine C2-to-pelvis CTs are truth
   (00:16 UTC), nothing from the 802 CTSpinoPelvic1K columns; existing SPINEPS masks, never
   re-run and never TotalSegmentator (00:17 UTC); figures in Benzel's style with the code that
   makes them committed and runnable from recorded inputs (01:17 UTC); the OneDrive upload is
   stopped (02:48 UTC; `junction_twins.pdf` is the one verified copy in Documents/bordercall_figures
   and stays); the public deck: count-free naming from morphometry sat near Part A of the
   provisional and was left out of v12_public, so check with the TTO before showing these slides.
4. Not known: traps 1 and 2 below (the identifier map is assumed; only the lumbar measurements
   are validated); every number above is synthetic until the pilot reports.
5. SchwingNet's vendored copy takes `bordercall/` only, so this commit (records, figures, slides)
   leaves its VENDORED record true; after any change under `bordercall/` run
   `python3 tools/bordercall_vendor.py copy` there and commit the copy with the change.

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

## The five traps, in the order they will bite

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

**5. Every synthetic accuracy is an upper bound, and the default hides it.** The generator
draws each measure's departure from its published mean independently. Real vertebrae do not
work that way — a wide body tends to come with a deep one — so independence hands the
classifier more information than it would have. No published source gives the within-patient
correlation; `run.py covariance` shows why, including the one paper that looks like the
answer and is not (Kunkel 2010 regresses parameter on parameter, which is the right shape,
but over sixteen *level means* rather than over individuals — reading a within-patient
correlation from it is the ecological fallacy). So pass `--r-between` and sweep it rather
than quoting the default. On the measure-set question the sweep settles it: the verdict is
unchanged across r = 0.0 to 0.9, moving by at most 1.6 Monte Carlo standard errors. **Do
that sweep for any new synthetic claim before quoting it.** `r_between=0` reproduces the
recorded runs exactly, which is what the tests check.

## FOR THE NEXT ACCOUNT: run the measure-set study on the Wayne State grid

Everything in this section is **pure synthetic** — columns drawn from Panjabi's published means
and spreads. **No CT, no labels, no corpus, no data access of any kind.** That is the whole
reason it is the right first thing to run on a new account: it needs nothing but the repository
and a Python with numpy and scipy, so nothing is blocked on an access list.

The literature survey behind all of this is committed at
`research/solver-survey-2026-10-26/` — start at its `INDEX.md`, and read
`adversarial-verification.txt` beside any notes file, because all seven of the survey's
decision-changing claims needed correction.

### What to pull, and what it needs

```bash
git clone git@github.com:OpenSpineConsortium/bordercall.git   # private
cd bordercall && git log --oneline -8                          # expect 400e73a or later on main
```

`numpy`, `scipy`. (`nibabel` is needed only for the label-reading commands, which this study
does not use.) On the grid: `~/mambaforge/envs/spineps/bin/python` has all three.

### Step 0 — prove the copy works before trusting a number from it

Not optional, and the reason is in the traps above: a corpus numbered differently, or a drifted
model, produces finite, plausible, wrong numbers and raises nothing.

```bash
cd ~/bordercall/bordercall && python run.py selftest
cd ~/bordercall && python -m unittest discover -s tests
```

Expect 70 tests, 69 passing. The single error is `test_junction_figures.JunctionFigures` in
`setUpClass`, a matplotlib colour fault present on `origin/main` independently of this work. **If
anything else fails, stop** — do not run the study on a copy whose tests do not pass.

### Step 1 — re-measure the per-evaluation cost on a compute node

The 7.24 s in the next section is a Windows workstation. A grid core will differ, and every wall
time below scales off it, so measure it rather than inherit it.

```python
import time, panjabi as P, junction as J, covariance as CV
ref = P.load_reference(measures=CV.SPINEPS_7)
t = time.perf_counter()
m = J.train(ref, "tl", measures=CV.SPINEPS_7, n_columns=600, seed=11,
            rho=0.5, noise_mm=1.0, scale_sd=0.07, r_between=0.0)
for ph in P.PHENOTYPES:
    J.evaluate(m, ref, ph, seed=97, n=400, rho=0.5, noise_mm=1.0, scale_sd=0.07, r_between=0.0)
print("%.2f s per evaluation" % (time.perf_counter() - t))
```

### Step 2 — the study itself: enumerate every subset

This is the science, and at this size exhaustive enumeration is the **right** method, not a
fallback: exact by construction, no relaxation or optimality gap, and it returns the whole ranked
distribution instead of an argmax. 127 subsets of the 7 measures, 6 values of `r`, both
junctions — about 3.1 hours of single-core work, so 16 shards is roughly 12 minutes each.

Save as `~/bordercall/jobs/enumerate.sbatch`:

```bash
#!/bin/bash
#SBATCH --job-name=bc-enum
#SBATCH --partition=reqp
#SBATCH --qos=requeue
#SBATCH --array=0-15
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=2:00:00
#SBATCH --output=logs/enum_%A_%a.out
set -euo pipefail
OUT=/rs/rs_grp_oschome/go2432/bordercall/enum-${SLURM_ARRAY_JOB_ID}
mkdir -p "$OUT"
SHARD_OUT="$OUT/shard_${SLURM_ARRAY_TASK_ID}.json"
# reqp is requeueable, so a preempted task restarts: finished shards are not redone
if [ -s "$SHARD_OUT" ]; then echo "shard already complete, nothing to do"; exit 0; fi
cd ~/bordercall/bordercall
exec ~/mambaforge/envs/spineps/bin/python run.py enumerate \
     --shard "$SLURM_ARRAY_TASK_ID" --of 16 --out "$SHARD_OUT"
```

```bash
mkdir -p ~/bordercall/logs
sbatch -D ~/bordercall ~/bordercall/jobs/enumerate.sbatch
```

`sbatch -D` is load-bearing: `#SBATCH --output` resolves against the **submit** directory, and
without it the logs land wherever you happened to be standing.

### Step 3 — gather, and read off two answers

```bash
OUT=/rs/rs_grp_oschome/go2432/bordercall/enum-<jobid>
cd ~/bordercall/bordercall
python run.py enumerate --gather $OUT/shard_*.json --out $OUT/gathered.json
```

The gather prints, per junction, the top five subsets **by worst case over `r`** — the maximin
criterion, which is the right one when `r` cannot be measured — and it refuses to call a winner
whose lead is inside the noise. It also answers a structural question that decides which methods
are even admissible: **is `A` monotone in `S`?** A small pilot already says no at T12/L1, with 7
of 18 supersets scoring lower by more than 2 standard errors and a worst drop of −0.1028. If
that holds at full `n`, then **adding a measure can hurt**, a cardinality constraint is not
needed to make the problem non-trivial, and every submodular-greedy guarantee is ruled out on
its own terms, independently of the Krause-Guestrin argument. Only drops clearing 2 s.e. count;
the command says "neither established nor refuted" when none do, rather than reporting scatter.

### Step 4 — close the Lipschitz question with a fine grid

`A(S, ·)` was measured **not** monotone in `r`, so the grid's `L*h/2` term is not disposable, and
refining the grid is not a check on itself (a 0.02 dip hidden between points takes the interval's
coverage from 0.95 to 0.42 — `covariance.coverage_check()` measures exactly that). A 19-point
grid cuts `h` by an order of magnitude. Cost scales linearly: ~10 hours single core, so widen the
array.

```bash
python run.py covariance --sweep --r-grid 0,0.05,0.1,0.15,0.2,0.25,0.3,0.35,0.4,0.45,0.5,0.55,0.6,0.65,0.7,0.75,0.8,0.85,0.9 \
       --out $OUT/sweep-fine.json
python run.py covariance --from-json $OUT/sweep-fine.json     # re-report, costs nothing
```

Compare the reported `L` and `gap` against the coarse run's. **If the fine grid's worst case drops
materially, the coarse grid was hiding a dip and every interval quoted from it was optimistic.**

### Step 5 — test OCBA against ground truth, which is the thing you now have

This is why step 2 comes first. `sim-tools` 1.3.0 (MIT, PyPI 2026-06-24) ships OCBA, OCBA-m, KN
and KN++, and is the one package the survey says to adopt. Its `ovs` module is **2021 code under a
2026 version string with no tests of its own**, so pin the commit and validate it yourself — and
the enumeration gives you the only validation that means anything: *did it find the subset that is
actually best?*

```bash
~/mambaforge/envs/spineps/bin/python -m pip install --user 'sim-tools==1.3.0'
```

Compute nodes have internet, so run the install inside a job. Then feed the enumeration's
per-subset means and variances to `sim_tools.ovs.fixed_budget` and report **attained probability
of correct selection against the known best**, and the budget it used against the 127 × 6 × 2
evaluations enumeration spent. Do not quote a figure for OCBA's saving over equal allocation from
the literature — the survey could not source one.

### Step 6 — where this stops being free, and OCBA starts earning its keep

| measures `m` | subsets | single-core |
|---|---|---|
| 7 | 127 | 0.5 h |
| 9 | 511 | 2.1 h |
| 12 | 4,095 | 16.5 h |
| 17 | 131,071 | **22 days** |

So grow the ground set — the transcribed Panjabi table carries more than seven measures, and
`SPINEPS_MAPPING.md` says which are honestly measurable from a segmentation — and at `m` around 12
switch from `--shard/--of` enumeration to OCBA, now that step 5 has shown whether you can trust
it. **The pedicle measures stay excluded**: SPINEPS labels the whole arch 41 and never isolates
the pedicle, so PDW and PDH cannot be read off one. The table does carry six pedicle rows,
which is why the ground set looks larger than seven at first glance: 13 measures over 23
levels, C2-L5, and six of the 13 are refused rather than approximated.

### Step 7 — the neighbour-identity and dimensionality study

**Done on 2026-10-26**: the results, the four verdicts and the figures are
`docs/NEIGHBOUR_IDENTITY_RESULTS.md`, drawn from `records/neighbour-2026-10-26/` by the five
`neighbour` commands of `run.py`. The owner's word of 06:31 UTC removed the one constraint the
brief had put on the problem: the target body is measurable too, so the main arm is the field
of view with the target in it, named as a whole (`neighbour-more`), and the neighbour-only arms
are the obscured case. A review by four independent readers told to refute the verdicts
found one thing of substance, that a fit on typical columns never learns the last name a longer
column carries, so every anomalous rate is given with that body excluded (its section 12 lists
every correction). Specified in full at **`docs/NEIGHBOUR_IDENTITY_STUDY.md`**;
that file is the brief, this is the one-paragraph version. Can vertebra `i` be named from the vertebrae **adjacent** to it, with its
own measurements withheld — and does the discriminating information fit in one radiographic
plane, or does it need a volume?

The second question is the one that decides the clinical plan, and it is decided by a clean
partition of the seven measures by anatomical axis: `h_post` is craniocaudal and visible in both
planes, `endplate_depth`/`endplate_lower_depth`/`canal_ap` are antero-posterior and **lateral
only**, `endplate`/`endplate_lower`/`canal_w` are transverse and **AP only**. So run three
regimes — `lateral` (4 measures), `ap` (4 measures), `both` (7) — and if a single plane reaches
`both` within the margin, one fluoroscopic shot is enough. If not, the information is genuinely
3-D and the recovery route is fluoroscopy-to-CT registration used **as a measurement device for
the missing axis, not as a level localiser**. Keep those two uses separate; conflating them is
how this becomes the registration-based approach, whose published naming accuracy is a number
this repository does not record with its source.

Everything is run across all six phenotypes, because a neighbour-based rule is *more* exposed to
transitional anatomy than a target-based one — the neighbour relation is exactly what a
transitional vertebra breaks. Report the **signed** offset per phenotype: a systematic one-level
shift in `six_lumbar` is the dangerous outcome, and it is the first thing to look for.

Three traps are written out in the brief and each would yield a plausible wrong answer: absolute
position must not reach the model, the per-case median normalisation leaks position when it is
estimated from two or three visible bodies, and chance is not 1/23.

### Latency, measured

Measured on a Windows workstation, 2026-10-26, single core. Re-measure on a compute node (step 1).

| operation | time | rate |
|---|---|---|
| **place one window (inference only)** | **0.40 ms** | **2,500 /s** |
| synthesize one column | 1.15 ms | 868 /s |
| `load_reference`, 7 measures | 3.9 ms | — |
| train, 120 columns | 0.35 s | — |
| train, 600 columns | 2.35 s | — |
| train, 2000 columns | 7.69 s | — |
| evaluate one phenotype, 400 windows | 0.71 s | 561 /s |
| **one full `A(S, r)` evaluation** | **7.24 s** | — |

Two things follow. **Inference is 0.40 ms, so naming is not the latency problem** — the budget is
spent on segmentation and, if step 7 says 3-D, on registration. A 3-D answer is therefore a
pipeline cost rather than a real-time one, and that is where latency work belongs. And training
scales linearly in `n_columns` (0.35 / 2.35 / 7.69 s at 120 / 600 / 2000), so a wall-time estimate
for any new sweep is arithmetic, not a guess.

### Grid etiquette that will bite otherwise

- **Nothing on the login node.** Everything through `sbatch`, including the gather.
- **`sbatch -D <dir>`**, because `--output` resolves against the submit directory.
- **Chain with `afterany`, not `afterok`**, and check the output yourself — `afterok` strands a
  dependent job permanently when the parent exits non-zero for a trivial reason.
- **`/tmp` is node-local and swept.** A cleaner once deleted the multiprocessing listener sockets
  of two 18-hour runs at the same minute. Put IPC under `/dev/shm`.
- **Large outputs go on CephFS**, `/rs/rs_grp_oschome/go2432/`, not the home directory, which is a
  Panasas soft quota and has been 93 % full. `df-ceph oschome` for usage.
- **Nothing container-related on `warrior`**, and nothing of ours under its `/tmp`. Container
  builds and execs run only inside Slurm jobs.
- **The grid's bash is 4.2.** `${var/pat/"$new"}` keeps the quotes there; a suite written against
  WSL's 5.2 will not catch it.
- `reqp` with `--qos=requeue` is preemptible, which is why each shard writes its own file and the
  script skips a shard that is already complete.

### Step 8 — which vertebrae of a normal spine can be named best, and by what

**Done on 2026-10-26**: the results, the five verdicts and the nine figures are
`docs/LEVEL_IDENTIFIABILITY_RESULTS.md`, drawn from `records/identify-2026-10-26/` by the two
`identify` commands of `run.py` (`identify`, 308 s; `identify-figures`). The owner's ask of
08:21 UTC, with Kunkel et al. 2010 attached: T12 looks like the most isolated point along the
x axis of Kunkel's Fig 2A; evaluate, as thoroughly as the neighbour study, which vertebrae of
the synthetic normal spine can be identified best, formulated on the prior research. The
formulation is section 0 of the results: Kunkel's Table 1 and Fig 2A fits are reproduced from
Panjabi's table first (the external check), then a level's identifiability is measured four
ways, loosest to most honest: the gap to the nearest level along one measure in units of one
body's spread, the nearest-rival Mahalanobis distance in the seven-measure space (size unknown,
known and removed; by plane; by measure subset; with the field around the body named as a
whole), the classifier of the neighbour study refitted on typical columns and scored per level
by width and plane with abstention, and the exact likelihood of the generator at one body as
the ceiling no rule can pass; the table's own sampling error is propagated by 400 redraws.
What it found: the premise does not hold (over Kunkel's sixteen levels T1 is the most isolated
along the body height, over all twenty-two T12's rival is L5 at 0.2 mm, and the spreads are
wider than the gap at every one of Kunkel's sixteen levels); the cervicothoracic junction is
what a field names with near certainty (C7 and T1 at 99% and 96% from nine bodies, 100% and 97%
of them kept by a detector held to 95% precision), the thoracolumbar junction is not (T12 16%
from one body, 77% from nine, its commonest error T11; the Bayes rule's own one-body recall
37%); the width of the field is the largest lever, then both planes, then the
patient's size, and the pedicle rows, which no SPINEPS label gives, would move the lumbar
levels most. Three skeptics refuted the design before the run, four the text after it and three the
corrected text again (one stopped at the usage limit; its sections were checked by script);
section 12 lists what changed. Typical columns only; the anomalous phenotypes are the
neighbour study's.

### Step 9 — is there a function that names a vertebra exactly, and what can be said for certain

**Done on 2026-10-26**: the results, the verdicts and the eight figures are
`docs/EXACT_IDENTIFICATION_RESULTS.md`, drawn from `records/exact-2026-10-26/` by the three
`exact` commands of `run.py` (`exact`, 4,652 s; `exact-supplement`, 879 s; `exact-figures`).
The owner's asks: at 10:43 UTC, whether any formula, function or network takes 1 to n
consecutive bodies' measurements and names a vertebra unambiguously, using the solver survey's
"exactness by construction ... plus the entire ranked score distribution"; at 11:26 UTC, which
weaker statements (such as "below L1" or "below T4") can be said nearly certainly from as local
a morphology as possible, in measures downstream of SPINEPS. The answer is the generator's own
Bayes rule, which enumerates every place a field can take and integrates the patient's size by
quadrature (no fitting), with its whole posterior. No function names every field (the Bayes
error is positive), but the rule names 47%, 73%, 86% and 96% of fields exactly from one, three,
five and nine bodies (the identifiability study's classifier, on the same columns, 36.5% to
83.3%), and its names at posterior 0.99 are right 99.78% of the time from three bodies and
99.93% from nine; one body says its region nearly certainly away from the thoracolumbar
junction, and the side of C7/T1. On a table estimated from twelve spines, as Panjabi's is, its
names at 0.99 fall to 95 to 96 per cent; a rule with widened spreads and 2 mm of error brings
them back to 98.9 to 99.3 per cent pooled, but its lumbar names stay at 96.75 to 97.65 per
cent, and near T12/L1 one body's region claim is right only 94 to 97 per cent. Four skeptics
read the code during the first run, five more read the finished text, each finding re-checked by
another (99 readers; 82 problems fixed, their own checks recorded as `supplement.json`), and
six more read the passages that changed and two more read those corrections, each finding
re-checked (42 readers, 33 more fixes); section 12 lists what changed. Typical columns and a uniform prior over places
only; the anomalous phenotypes and a real series' prior are section 10's open questions.

### Step 10 — five slides on the exact rule, for the CNS or a NeurIPS oral

**Built on 2026-10-26** (the owner's ask of 20:45 UTC: figures and five PowerPoint slides with
the figures, the text and the LaTeX as separate elements, styled like Benzel with inspiration
from Murphy's chapter on Bayes' rule, ready for the CNS or a NeurIPS main-conference oral), and
corrected the same evening from a review of 47 findings.
`python run.py exact-slide-figures --json ../records/exact-2026-10-26/exact.json --outdir
../records/exact-2026-10-26/slide-figures` draws two figure sets from the record, each panel at
the exact inches its deck gives it, so no deck scales a picture: the NeurIPS set into
`slide-figures/` (seven panels: the field of view, the seven measures, the prior and posteriors,
the ceiling, the calibration, the border claims, the robustness) and the CNS set into
`slide-figures/cns/` (six panels, no calibration, a step larger type, no method word in a label or
a caption); `--venue neurips` or `--venue cns` draws one. `python slides/make_exact_slides.py`
builds `slides/exact/exact_slides_neurips.pptx` on a plain 16:9 deck, with the method, and
`exact_slides_cns.pptx` on the CNS template the junction deck carries, results only, with speaker
notes written for each venue. The NeurIPS equations are native Office Math set by pandoc, kept as
`slides/exact/equations/*.omml.xml` so a build needs no pandoc, and every constant in them is read
from the record; a build into another folder writes any new equation there and never into the
committed cache. Each deck is the same bytes from build to build (one fixed date on every zip
entry, the equation pictures drawn from matplotlib's defaults), and `--pdf` adds the LibreOffice
previews committed beside them. Murphy's pyprobml repository was outside this session's GitHub
access, so its conventions (prior, likelihood and posterior as stacked panels, the posterior in
one colour, the notation p(k | x_{1:n})) were followed from the book.

Both decks carry "Confidential: pre-filing draft, not for distribution" in every footer until they
are built with `--public`, which is for use only after the provisional is filed and the TTO has
read the deck. The build checks the saved file, every XML part of it (slides, notes, alternative
text, properties): neither deck may hold a word of the confidential work or a template's author,
and the CNS deck may hold no method word (`CNS_REFUSED` in the builder: Bayes, likelihood,
posterior, prior, Gauss, Hermite, quadrature, rank-one, Sherman, covariance, enumeration,
generator, 13/12, 1/12, LaTeX, equation; "posterior body height" is a measure and allowed). A deck
that fails is deleted and the build stops. The file's properties name the speaker.

What the results-only CNS talk cuts, against the NeurIPS deck: every equation (the problem, Bayes'
rule, the likelihood, the covariance and the size prior, the selective guarantee with its k-hat and
p-hat, the border claim and the middle body, the widened spreads); slide 1's place k (now "Seven
measures per body. Which levels are in view?"); slide 2's rule and method text (now the share of
T12 fields named exactly from one, three and nine bodies); slide 3's calibration panel and
guarantee (now a result sentence, "at 99% confidence"); slide 4's claim as a sum (now the claim as
a result with its condition); slide 5's spread inflation and 2 mm (now "a corrected rule") and the
next steps (now "test the rule on real full-spine CT"); and every method sentence of the notes,
each number in which says synthetic.

For the TTO to read before either deck is shown, and to confirm that the provisional as filed
covers each element:

- the seven-measure schematic (`exact_slide_measures`, on slide 1 of both decks), which names the
  feature set;
- the CNS slide 2 statement that no formula or network on these measures names more fields
  correctly on average;
- the NeurIPS method elements: consecutive bodies reduced to one place k over C3 to L5; the
  size-scaled Gaussian likelihood with its diagonal-plus-rank-one covariance; the Gauss-Hermite
  quadrature over log size; the selective guarantee, answering only at posterior at least
  1 - epsilon; region and border claims made by summing the posterior; the widened-spread
  correction for a table from a small sample (spreads times the root of 1 + 1/n, and an assumed
  error); and anomalous phenotypes as places of their own, which neither deck now says.

### Step 11 — the white paper: the exact rule beside LevelCheck, and a randomized study

**Written on 2026-10-26** (the owner's ask of 21:18 UTC: a succinct white paper on how the
method would fare against LevelCheck, based in provable mathematical statistics, with the spec
for a demo of an IRB study randomizing surgeon-assisted level identification in a simulated
browser environment to either aid). The owner supplied two LevelCheck papers as full text (De
Silva et al. 2016, Spine; Manbachi et al. 2018, Ann Biomed Eng) with De Silva's supplement
tables, and set the sentence the paper hinges on (21:28 UTC): no function of the same
measurements, formula or neural network, names fields correctly more often than this rule,
because it is the Bayes rule for these fields and this prior over places, up to the 0.5 mm floor
and the quadrature, so its error is the floor for any network. The paper is a Claude Doc
(https://claude.ai/artifact/4VwMe9CKMX87s4jiEJBpRE), to be copied here as
`docs/SCHWINGCHECK_LEVELCHECK.md`; the PDFs are the publishers' and are not committed. A review
by several skeptics found 72 problems, and two further checks of the fixes and of the reframed
paper found more. On 2026-10-27 from about 00:50 UTC the owner rewrote the Doc live, first with three
configurations (LevelCheck alone, SchwingCheck with LevelCheck, SchwingCheck alone) and then as
three pathways: LevelCheck as prior art, SchwingCheck3D where a preoperative CT exists (segment
the CT, check its labels, carry them by a pose fitted to matched centroids) and SchwingCheck2D
with no CT, the recommended default. The rewrite stood still at Doc revision 138 from about 03:31
UTC, and at about 04:00 UTC the checked fixes that still applied were folded into it as 49 narrow
find-and-replace edits, with 14 references the text cited and the list lacked (revision 188). At
04:25 UTC the owner said their preliminary data show 100% accuracy when making panoramas with
SchwingNet, so the paragraph on stitching in SchwingCheck2D now gives that result with the sets it
holds on, as SchwingNet's textbook chapter 34 records them (revision 189); the copy here is
revision 189, the owner's text with those edits and nothing else.

Checkpoint, 2026-10-27 about 04:55 UTC, on the owner's word of 04:47 UTC. The paper is also
textbook chapter 36 in OpenSpineConsortium/SchwingNet, pull request #416 (draft, branch
claude/project-thread-7qoboa), with five figures drawn for it. That pull request's adversarial review
confirmed about twenty defects in the chapter's own framing, figures and records, none in the paper;
they and the steps to finish are in SchwingNet's docs/checkpoints/2026-10-27-cns-junction/ (README.md
and review-findings.md). The grid pilot is still unsent.

What it concludes. On the owner's comments in the Doc (2026-10-26 23:38 and 2026-10-27 00:11
UTC) the paper is framed against the upstream labeller, not the registration: LevelCheck has no
classifier of its own, it carries the CT's labels to the radiograph, and those labels come from a
clinician's click in the published workflow, a neuroradiologist's review as the published truth,
or, in proposals only, an automatic labeller. No LevelCheck study measures that labeller against an
independent count, and its authors write that a wrong CT label is faithfully reproduced, so its
error is about the labeller's plus the registration's, and the published counts bound only the
second. Statement 1 bounds every rule on the seven measures, not a reader who counts a full CT from
C2. Against the registration itself the rule does not compete: on typical spines with a correctly
labelled CT and four or more levels in view, zero failures in De Silva's 178 patients would have
had probability 0.0009 if LevelCheck erred as often as the exact rule's forced choice from nine
bodies. What the rule adds is a calibrated probability from the bodies' own shape, fused with each
overlaid label by Bayes' rule (one multiplication per level, about 14 ms for a three-body field),
flagging 84% of off-by-one labels from nine bodies at posterior 0.01 while questioning 1 correct
answer in 1,000, though only 71% to 78% for fields centred T6 to T10. It also runs with no CT, on
C-arm views alone: from nine bodies it names 96% of fields with an AP and a lateral view, 89% with
the AP view alone and 84% with the lateral alone (`exact.json`, the three regimes); oblique views
are not modelled and nothing yet reads the measures off radiographs. The two fail together on a
transitional spine: scored by the count from C2, the rule's names at 0.99 from nine bodies are
right 90.6% on thirteen-rib columns and 92.9% on six-lumbar columns (`checks.json`). Every number
for the rule is synthetic.

The study. 30 readers by 60 cases, every reader the same cases, each randomized within reader
and stratum to a registration aid or the exact rule: 20 standard and 20 narrow-field cases make
the primary comparison, where the registration has a correctly labelled CT of a typical spine,
and 10 transitional and 10 no-CT cases are compared on their own, never pooled into the test.
Readers and cases are both random, by the law of total variance, with critical values
calibrated by simulation (2.33 for noninferiority within 5 points, 2.03 for superiority), since
a t interval over readers treats the shared cases as fixed and lets up to 9% of null studies
through when the aid's effect varies by case. Power at moderate variation is 89% and 81%. Aid B
takes its measures by hand from the same radiographs the readers see; Aid A's settings are
frozen and reviewed outside the team before any of the rule's outputs on the cases exist. The
owner's rewrite of 2026-10-27 randomizes each case to one of three configurations instead,
registration alone (A), the rule alone (B) and the two together (C), 40 readers by 48 cases in
four strata of 12, with C minus A over the whole case mix as the primary and a t interval over
readers. `study_power_three_arms.json` simulates that design with the same model: under the
rewrite's own assumptions (no variation in the aids' difference, the t interval at its nominal
value) it reproduces the rewrite's powers, 0.98 for noninferiority and 0.91 for superiority at 90%
against 95%; but that t interval lets 4.2% of null studies through at a nominal 2.5% with no
variation and 7.2% when the difference varies widely, and up to 12.1% at a nominal 5% inside a
12-case stratum. With the calibrated critical values (2.31 and 2.05 at 40 by 48) and moderate or
wide variation, power is 0.92 and 0.85 for noninferiority and 0.85 and 0.75 for superiority.

New code: `second_opinion.py`, `whitepaper_checks.py` and `study_power.py`, with their records
in `records/whitepaper-2026-10-26/` and `tests/test_whitepaper.py`.

For the TTO to read before the paper leaves the lab, and before any reader sees the study:

- the paper states the method in full (the seven measures, the size-scaled Gaussian likelihood,
  the quadrature, the selective guarantee and the reject rule, region and border claims, the
  widened-spread correction, and Bayes' rule combining the exact rule with a registration's
  answer), so it is as sensitive as the NeurIPS deck;
- the combination with a registration and the study's Aid A touch LevelCheck's patents (US
  11,284,846 of Siemens and Johns Hopkins, listed active until 2034, and US 9,165,362, US
  10,368,956, US 10,262,424 and US 11,657,518 of Johns Hopkins); a product that combined the
  two, an open registration built for the study, or a study that used LevelCheck itself, needs
  the TTO's review first, and Hopkins' licence or a freedom-to-operate opinion where it would
  practise them;
- the inventors' interest in one arm is disclosed to the IRB and the conflict of interest office;
- the study, its pilot and demo, and its OSF registration wait until the provisional is filed
  and the TTO has reviewed it, because readers see the rule's output.

## What one evaluation costs, and where enumeration stops being free

Measured on a Windows workstation, 2026-10-26. One evaluation of `A(S, r)` -- train the junction
model on 600 synthetic columns, then score six phenotypes at 400 windows each -- is **7.24 s**
(2.40 s train, 4.84 s evaluate, `n = 2400`, 7 measures). Reproduce with `J.train` followed by
`J.evaluate` over `P.PHENOTYPES`, which is exactly what `covariance._score()` calls.

That number decides how this problem should be attacked, so it is recorded rather than guessed
at. Enumerating every subset, scored at both junctions:

| measures `m` | subsets | cost |
|---|---|---|
| 7 | 127 | **0.5 h** -- free |
| 9 | 511 | 2.1 h -- free overnight |
| 12 | 4,095 | 16.5 h -- one night |
| 17 | 131,071 | **22 days** -- not enumerable |

So **at the 7 measures in use there is no optimization problem**: enumerate, which is exact by
construction and returns the whole ranked distribution instead of an argmax. Above roughly
`m = 12` the binding constraint becomes simulator throughput, and the thing to reach for is a
replication-budget rule -- `sim-tools` 1.3.0 (MIT, PyPI 2026-06-24) ships OCBA, OCBA-m, KN and
KN++, with the caveat that every commit touching its `ovs` module since 2021-07-05 is
formatting and the module has no tests, so pin the commit and write your own.

The closed-form separability of the published Gaussians runs about 290,000 times faster than
this, and it is **a different function, not a cheap version of this one**. Use it to rank and
screen; report the final accuracy from the simulator on held-out draws. Never quote the two
interchangeably.

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
| `run.py` | CLI: `scheme`, `selftest`, `measure`, `phenotype`, `border`, `breakout`, `sweep`, `plot`, `disagree`, `panjabi`, `panjabi-corpus`, `panjabi-figures`, `synth-corpus`, `covariance`, `all` |
| `covariance.py` | the between-measure correlation: what the literature does and does not supply, the exchangeable draw that puts it into the generator, and the sweep showing the measure-set conclusion survives the whole range of it |
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
