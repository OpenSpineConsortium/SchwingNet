# The bordercall corpus: which junction the shape of the bone names most robustly

The thread "Finish CNS slides with junction predictor", 2026-10-26, from the owner's prompt of
2026-10-25 23:48 UTC ("find which vertebral junction the shape of the bone names most robustly,
in normal AND anomalous spines") and the owner's rules of 00:16 and 00:17 UTC: only full-spine
columns from C2 to the pelvis are truth, and the vertebrae come from the existing SPINEPS
masks, never TotalSegmentator and never a re-run. No link: the prompt was written into the
project chat. Confidential, as the whole repository is until the filing.

## Where it stands

Nothing has run. The job is written (grid/bordercall.sbatch, the word `bordercall <stage>` of
grid/gate.sh, the corpus builder tools/bordercall_corpus.py, the copy of bordercall under
grid/bordercall/), the owner's count of 23:56 UTC is two CPU jobs, a pilot over a few hundred
countable cases and then the full corpus, and both wait for the pass-through of the word
(symphony-template's grid-accounts.yml and hpcworker's gate) to merge and for `update`. The
first real numbers are the pilot's report, grid/logs/BORDERCALL-pilot.md, printed by the next
status word.

## What the job does, and why each rule

1. The corpus is every row of the census's tier lists ($RS/ruleclass/tiers/tier1.tsv and
   tier2.tsv, 5,094 and 12,217 CTs) that names a SPINEPS vertebra mask, in a fixed order. A
   mask whose ids are raw is relabelled in memory through its centroid file with
   spinesurg-ct-nnunet's guard (tools/spineps_ids.py); one with no guard reachable is set
   aside, since raw ids read as wrong names and raise nothing (the census's DATA.md trap).
2. The column is counted from C2: every instance below C2 is named by its ordinal, C3 to C7,
   T1 to T12, then L1 onward. A column with no C2, or with a gap between bodies wider than
   1.8 times the local body spacing, or with more than one instance above C2, is set aside;
   VERIDAH's own names are recorded beside the count (whether they agree, the offset at L1)
   and are never the truth below C2. A thirteenth rib-bearing body is L1 with a rib and the
   lumbar count is six; a column of four lumbar bodies ends at L4. The label volume written
   for bordercall carries the count's names in bordercall's scheme.
3. The ribs come from the census's existing Moller rib table
   ($RS/ruleclass/arms/moller_fast/<collection>/<case>_rib_measurements.csv, the upstream
   variant, the longest rib per vertebra, rib-bearing at 38 mm or more, the census's rule 1),
   since SPINEPS makes no rib mask and nothing is re-run. The rib reading gives the phenotype
   (lumbar_rib, no_rib_T12, six_lumbar, four_lumbar, typical) and is the independent naming
   disagree.py scores against; a case with no rib table is countable with its phenotype
   unknown, and reports in its own row.
4. bordercall runs its own commands over the label tree: selftest first (the published
   CTSpinoPelvic1K numbers from the bundled fixture, so a drifted copy scores nothing), scheme,
   measure, phenotype, then border and breakout at T12/L1 and at C7/T1, disagree at both
   (the count's accuracy with the disagreements by class and how many fall in a counted
   anomaly; the rib arm; the circular arm for scale), the two figures the owner asked for at
   each junction (endplate, canal_w, into figures/thoracolumbar/ and
   figures/cervicothoracic/), sweep over every candidate border with min-class 10, and
   panjabi-corpus, the Panjabi models fitted on no CT scored on the corpus by phenotype with
   bordercall's own fit beside them as the ceiling.
5. The pilot reads at most 4,000 rows and stops at 300 countable cases; the job stops with
   exit 4 and measures nothing when no case is countable, as the owner's step 2 asks. `full`
   is refused until the pilot's report ends well. Every step's full output is under
   $RS/bordercall/<stage>/<step>.txt; the report holds the first lines of each table, under
   the gate's 200-line print.

## What is validated and what is not

Only the lumbar measurements of bordercall are validated against published norms (end-plate
width, canal width, transverse-process span, at lumbar levels); the thoracic and cervical
figures are a pipeline test until each measure is checked against a published series at those
levels, which the Panjabi tables in bordercall/reference/ are there for. The count from C2 is
truth for the names; the rib reading is truth for nothing, it is the independent arm. The
synthetic corpus (bordercall's synth-corpus) proves the commands run and agree with each
other and nothing about a spine. The 802 CTSpinoPelvic1K columns are not used for any number
here, on the owner's word of 00:16 UTC.

## What is not known

How many of the census's masks count from C2 (the pilot's first table); whether the rib table
covers the countable cases (its coverage is reported per class); whether the local
measurements transfer to thoracic and cervical levels; and every number about the real
corpus, until the pilot runs.

## The owner's steps

1. Merge the three pull requests (SchwingNet, symphony-template, hpcworker).
2. Send `update` through grid-accounts.yml, then `schwingnet-status` once, then
   `schwingnet-bordercall-pilot`; read its report from the next status word.
3. `schwingnet-bordercall-full` only if the pilot found countable cases and ended well.
