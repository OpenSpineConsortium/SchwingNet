# Reading the prior's measure check

Source: the thread "Train on randomized spine phantoms" of the project symphony_3, 2026-10-31. The
design workflow asked whether the fitted R_measure understates how one vertebra's own measures move
together. Three critiques followed, by the lenses statistics, measurement and scope; README.md in
this folder says what each found. This guide was written before the first send of the job that
prints the check, against the prior published in bordercall records/prior-2026-10-31/report.md.

This guide is frozen. READING.md.sha256 beside it holds its sha256, and the gate word
`morphometry prior` (grid/gate.sh) refuses to send from a commit where the two disagree. It governs
the reading of every report whose job was sent from a commit that holds it. A change is a new guide
with a new sha256, and it governs only the jobs sent after it. No report is read under a guide
written after its numbers were seen.

What it is for. After the fit, the same CPU job prints descriptive lines, each starting
"<population> C3..L5 check: " (grid/prior/prior_check.py). The sections keep the design's numbers,
S0 to S15; S3, S7 and S10 were cut. The lines decide nothing. A session reads them jointly as this
guide says and writes what they show for greg. greg makes every choice that follows: whether the
measure part of the prior stays held, and whether the measures, the neck, the protocol mix or the
generator's size factor are taken up, and how.

Contents: 1 what is known before the job; 2 first, S0, S12 and the lines that are missing; 3 the
primary contrasts and the reading rule; 4 the signatures of the matched truths; 5 the hypotheses,
read jointly; 6 what a reading leads to; 7 what the check cannot settle; 8 where the numbers come
from.


## 1. What is known before the job

R_measure is not the same-level correlation. The prior is a matrix normal kron(R_level, R_measure),
fitted by Dutilleul's flip-flop on whole spines standardised per cell and then shrunk 0.05 toward
the identity (grid/prior/gold3_prior.py, grid/prior/schwingcheck/correlation.py). The flip-flop's
measure step weights each pair of levels' block of the data by the inverse of R_level, so R_measure
is a level-whitened, separable quantity. Its low entries do not by themselves say that the plates
of one vertebra are weakly coupled: endplate with endplate_lower is 0.301 over C3..L5 in
enhance_pet and 0.164 over T1..L5, and endplate_depth with endplate_lower_depth is 0.463 and 0.446
(bordercall records/prior-2026-10-31/report.md). The measure part waits on this check (bordercall
README.md, the limit "Independent measures").

The separable form explains only part of the gap. The statistics critique built truths whose
flip-flop limit reproduces the published enhance_pet fits exactly, and read their raw same-level
pairs.
- Some reproduce both the C3..L5 and the T1..L5 fit: a measure part that differs in the neck, plus a
  whole-spine shared factor of share 0.20 to 0.40. Their raw pairs over T2..L4 are 0.31 to 0.46 for
  the widths and 0.56 to 0.66 for the depths (truths/regional_size_bound.json). Factors on the
  widths alone, or on the widths and the depths separately, give widths of 0.27 to 0.32
  (truths/width_factor_bound.txt).
- Truths matched to the C3..L5 fit alone reach 0.57 for the widths and 0.71 for the depths
  (truths/mixed_bound.json, truths/regional_size_bound.json). But they give a T1..L5 width pair of
  0.28 to 0.32, against the published 0.173 (unshrunk).

The published couplings of one vertebra's upper and lower plates are far higher.
- On dry bone they are 0.76 (cervical) and 0.83 (lumbar) to 0.92 to 0.94 (thoracic) (Gibbs 2022, an
  MSc thesis of the University of Pretoria, 30 men). They are probably pooled over the levels of a
  region, which inflates them.
- On the NHANES II lateral films, the upper over lower end-plate depth ratio has a CV of 0.017 to
  0.019 at L1-L4 and 0.030 to 0.036 at C3-C7 (Hipp 2022, JBMR Plus, PMC9549721, Appendix S1). At a
  depth CV of 0.08 that means a coupling of about 0.97, by r = 1 - s^2 / (2 cv^2) for equal CVs cv
  and a ratio SD s.

By the critique's arithmetic, the separable reading explains at most about 0.29 of a 0.59 to 0.77
gap in the thoracolumbar width pair. In the depth pair it explains about 0.19 of a 0.48 to 0.52 gap.
That is a third to a half, and only at the largest shared factor the fits allow. The measures (their
definitions, their noise, the neck cut, the thick-slice slabs) are joint leading suspects with a
whole-spine shared factor. No reading under this guide says the separable form explains most of the
gap.

The neck is already known to matter in enhance_pet. Its width pair falls from 0.317 over C3..L5 to
0.173 over T1..L5 (unshrunk, each fit on its own spines), a change of -0.144. TotalSegmentator's does
not move (0.321 to 0.323). No single kind of structure matched to the C3..L5 fit reproduces the
fall. The regional truths, whose cervical widths couple at 0.81 to 0.85, do
(truths/regional_size_bound.json). So P3 below is known to sit near -0.14 in enhance_pet. The check
adds its unit bootstrap on the same spines, and the lines that say what in the neck does it.

The generator adds its own size. bordercall's draw_columns (schwingcheck/columns.py at 8ae5db9,
vendored here for the check) multiplies each column by its own size factor, exp(N(0, 0.07^2)), on
top of the prior's field, and adds 1 mm of noise. The prior was fitted on spines that already carry
whatever whole-spine factor they have. With the card's margins, the results are
(truths/results-phantom.json):
- the drawn same-level width pair is 0.509, against the prior's 0.301;
- the drawn lags one to five levels apart are 0.582 to 0.507, against 0.487 to 0.354;
- the size factor carries about 32 per cent of a cell's variance.

The check holds nothing. Nothing in production draws from the prior. The naming run (#56) gives the
same primary answer under the fitted prior and under widths and depths coupled at 0.8: no k up to 6
reaches 0.90, and the two worlds differ by about one point (scope critique, from a reduced copy of
the run). TotalSegmentator's measure part stays held whatever its lines say. At 67 fit spines the
check cannot tell its hypotheses apart (statistics critique; section 4).


## 2. First: S0, S12 and the lines that are missing

Read these before any primary, for each population.

S0, the inputs. These are the expected lines:
- rows at one code stamp, 1cee7ea83e4c28db (every set's rows were at it on 2026-10-31);
- whole fit spines 693 of 809 kept and whole held 158 of 190 for enhance_pet, and 67 of 85 and 13 of
  18 for totalsegmentator;
- the refit's largest difference from the fitted prior, 0e+00 or a round-off under 1e-6.

The fit's own lines above the check give enhance_pet's C3..L5 width pair as 0.301 and its depth
pair as 0.463, and totalsegmentator's as 0.305 and 0.298. Any difference is a finding: name it, and
read nothing more of that population. The refit only shows that the check read the spines the fit
read. A reading error the two share passes it (statistics critique); S12 is there for that.

Another stamp. The truths of section 4 were matched to fits of the rows at 1cee7ea83e4c28db. Rows at
another stamp may differ where it matters: the two re-read records of 2026-10-29 disagree on the
same three studies (measurement critique). Report the lines as a description and ask greg whether
the truths should be matched again to the new fits. Read no band until he answers. A note that is
not a stamp in the engine's 16-hex form prints as "not 16 hex" and is read as another stamp.

The counts line. gold3_prior.py's counts line, above the check, now splits the anomaly removals by
reason: L6, T13, no L5. A transitional spine whose masks name no extra level stays in, with its
levels shifted by one. That reads as a small whole-spine offset, and the rows hold no count from C2
to find it (section 7).

S12, the anchors. Two lines per measure give each level's mean and SD in mm. They are the only lines
that meet values from outside the computation. Check, before any primary:
- every measure grows from C3 to L4 overall. Endplate steps up from C7 to T1 and back down at T2: on
  the thin-slice studies of bordercall records/morphometry-2026-10-29/compare-229.csv, 25.1, 40.2
  and 31.2 mm. T1's body keeps what stands beside it in front of the canal (measurement critique);
- in L1-L4 each depth lies well below each width. At L4 on those studies: endplate 53.6 mm, SD 6.2;
  endplate_lower 56.6, SD 5.6; endplate_depth 36.3, SD 4.5; endplate_lower_depth 35.2, SD 4.6;
  h_post 27.7, SD 2.1;
- at each level compare-229.csv holds, each mean lies within two of its SDs there. The job pools
  every protocol class, so a few millimetres apart is expected;
- the other population, level by level, lies within two SDs as well. That is the same code on other
  scans: an outside view of the scans, though not of the code.

A failure ends the population's reading at "the rows or their reading are in doubt", with the line
named, for greg. These checks find a swap of measures whose means differ, and a shift of levels.
They cannot find a swap of the upper and lower plate of one measure, whose means are close. That
swap reverses P2's sign (section 3).

Missing lines. Each of these is not read, and the reading says so:
- a section that failed prints "fault at S<n>, an error of the kind <Kind>". A fault at S0 ends the
  population's check;
- a line "S<n> and every section after it not run, the check ran past 90 minutes" covers every
  section from S<n>;
- verse prints "not run" (3 fit spines);
- the reruns of S1 and S4 print "not run", with the reason, when a stratum is under its floor;
- the gate prints the report through its shape and redaction filters and cuts it at 400 lines and
  64,000 bytes. A line withheld or cut there is missing too.

A primary whose line is missing is not read. It is never filled from another line, another
population or another run. The done line names the draws. A reading of z_boot needs at least 200
(the default); with fewer, the reading says so and reads sizes only.


## 3. The primary contrasts and the reading rule

Five contrasts, eight statistics, carry every reading. They were chosen before the job runs, to
bound how many lines can raise an alarm. Every other line is secondary. A secondary may qualify a
primary's reading, name a mechanism inside it or show where it does not hold, but it never makes a
reading alone. A striking secondary with no primary behind it goes to greg as a question, not as a
finding.

P1, a factor shared along the whole spine (three statistics).
- The lines: "far apart, C3-C7 with L1-L4, mean of the six plate pairs" (S4), and its two reruns.
  "within class, far apart, C3-C7 with L1-L4, mean of the six plate pairs" standardises every cell
  within its protocol class. "autoPET 2.5 mm alone, far apart, ..." takes one site and one protocol.
- The statistic: the misfit (data minus what the Kronecker draws) of the correlations between a
  neck level and a lumbar level. Each plate pair's two orders are averaged, and then the six plate
  pairs ed el eld dl dld lld are averaged.
- Why it works: a whole-spine factor raises every far pair. Noise, a disc term and a structure
  confined to the neck barely reach pairs 13 or more levels apart.
- The mean is printed only when the six pairs share a sign. Otherwise the line says no mean is
  taken, P1 is not read, and the far-pairs line is a description.

P2, a coupling across the disc (two statistics).
- The lines: "across a disc in T2 to L4, widths: ..." and the same for depths (S2).
- The statistic: facing minus far, over the 14 discs inside T2..L4. Facing pairs the lower plate of
  the upper body with the upper plate of the body below. Far pairs the upper plate of the upper body
  with the lower plate of the body below.
- The Kronecker draws facing and far equal, so every truth without a disc term gives 0.

P3, the neck's share of the width pair (one statistic).
- The line: "width pair change from C3..L5 to T1..L5" (S5).
- The statistic: the width pair of a refit without C3-C7, on the same whole spines, minus the
  C3..L5 refit's. Both are unshrunk.

P4, the plates as measured against films (one statistic).
- The line: the L1-L4 depth value of "plate ratios, median SD of log ratio" (S14). Its boot se is
  the second of the three on the line. The line prints NHANES II's figures beside it.
- The statistic: the median over L1 to L4 of each level's SD of log(endplate_depth /
  endplate_lower_depth).
- It needs no model, and a scale shared by the vertebra cancels in the ratio.

P5, the generator as it draws (one statistic).
- The line: "generator check, one to five levels apart, same measure, drawn ..., data ..." (S15).
- The drawn side: 5000 typical columns drawn as run_naming draws them (the fitted prior, the size
  factor at SD 0.07, 1 mm noise), here with the data's own cell means and SDs, set beside the data.
- The statistic: the smallest of the five differences, drawn minus data.

The rule.
1. Size first. Read each primary's value against its bands below. They come from the truths of
   section 4, in the population limit, and for P4 from the films.
2. Then evidence.
   - P1, P2 and P3: z_boot = (misfit - null mean) / boot se, both taken from the same line. It must
     reach 3 in size for a band to count. Where the line says "boot se none", the size is read
     alone and the reading says the bootstrap failed.
   - The parametric z on the line is printed but not read. Its null treats the spines as
     independent Gaussian draws, which the repeat scans and the mix of sites are not, so it
     overstates (statistics critique). At n 693 its SDs of 0.004 to 0.010 let almost any misfit
     pass.
   - P4: (P4 - 0.019) / boot se must reach 3, measured from the films' highest L1-L4 figure.
   - P5 is read on its size alone: both sides describe the same data, and the drawn side holds 5000
     columns.
3. Eight statistics, each at |z| 3, give a family-wise chance of a false alarm under about 2.2 per
   cent (8 x 0.0027). Requiring the size as well makes it smaller.
4. Order:
   1. S0 and S12;
   2. P2's sign;
   3. P1 and its reruns;
   4. P3;
   5. P2;
   6. P4;
   7. P5;
   8. the secondaries that qualify each;
   9. totalsegmentator beside enhance_pet.

The bands. A value in the gap between two bands is undecided between them.

P1, pooled:
- -0.04 or below: a vertebra-specific term (the matched truth: -0.076);
- above -0.04 and under 0.06: no shared factor beyond what noise, a disc term or a neck structure
  leave. Their matched values are 0.033 to 0.039; the separable form alone gives 0.004;
- 0.06 to under 0.12: undecided between those two, a smaller shared factor or a mixture;
- 0.12 or more: a shared factor carrying about 0.15 or more of each cell's variance (matched values
  0.140 to 0.317).

P1's reruns, read when the pooled P1 is 0.06 or more:
- both under 0.06: the factor lies between the protocol classes. It is an offset of a protocol
  (site, scanner, kernel, spacing) or a difference between the sites' people, not a factor of
  persons within one protocol. Standardising within class removes both (measurement critique).
  The autoPET rerun, one site and one protocol, is the cleaner of the two;
- both 0.06 or more, each with |z_boot| at least 3: a factor remains within one protocol and one
  site. It is a factor of the person or a per-scan shift of the bone boundary. Its size reads on
  the pooled bands, and S13 tells the two causes apart (section 5);
- otherwise: the factor lies partly between classes. The class lines' mean z (S11) show which
  classes carry the offset.

P2, widths and depths:
- either at -0.05 or below: no truth tried gives a negative value. A swap of the upper and lower
  plates, in the rows or in their reading, would turn a real disc term negative. P2 is not read, and
  the swap goes to greg as a question;
- both under 0.02: no disc term. Every truth without one gives 0, and the null SD at n 693 is 0.006
  to 0.007;
- both 0.05 or more: a coupling across the disc. The matched values are 0.163 at the largest share
  the fit allows, and 0.080 mixed with noise;
- otherwise: undecided.

P3:
- -0.10 or below: a regional structure, the neck's widths coupled apart from the rest (the regional
  truths: -0.144);
- -0.06 to above -0.10: a neck term at a smaller share, or a mixture of one with noise or a disc term
  (the cervical widths alone at 0.20: -0.084). S9 says which;
- from -0.01 down to -0.05: noise or a disc term (-0.026 and -0.041; both mixed, -0.030). P2 tells
  which;
- above -0.01 and under +0.01: none of these, so the separable form or a shared factor (-0.003 to
  0.000);
- +0.02 or more: a vertebra-specific term (+0.032).
In enhance_pet, P3 is already known to sit near -0.14, and in totalsegmentator near 0 (section 1).

P4, the L1-L4 depths:
- 0.038 or more, with its z from 0.019 at 3 or more, points at the measures. 0.038 is twice the
  films' highest L1-L4 figure, so the depths of one vertebra disagree at least twice as much as on
  films. The factor of two leaves room for what separates the two methods. Films are projections
  read at the plate's edge, and the CT depth is read from a slab. NHANES II also left out every
  vertebra beyond 2 SD on any metric, which narrows the SD it reports.
- For scale: at the CVs of the thin-slice studies at L4 (0.123 and 0.129, compare-229.csv),
  SD^2 = cv_u^2 + cv_l^2 - 2 r cv_u cv_l puts 0.038 at a raw depth coupling of about 0.96. It puts
  the matched truths' 0.56 to 0.66 at a ratio SD of 0.10 to 0.12.
- under 0.038: first S0 and S12 again, since a depth column read twice, or one depth derived from
  the other, gives a ratio SD near 0. Then the depths of one vertebra agree within twice the films'
  scatter. The low fitted depth entry then comes from the fit's form and the shared factors (P1),
  not from a disagreement of the depths.

P5:
- +0.05 or more at every lag (the smallest difference at least +0.05): the generator counts size
  twice along the spine. That points at the generator's size factor;
- otherwise: no double count that moves the phantoms' level structure by 0.05. The variance line
  still says how large the size factor's share is.
For orientation, without the size factor the drawn lags would sit about 0.02 to 0.03 under the
data's, since the prior is shrunk by 0.05 and the noise takes a share. With the card's margins they
sit 0.09 to 0.15 above the prior's own lags (truths/results-phantom.json). The data's margins give
the size factor a smaller share where a cell's CV is larger, so only the job's lines are read.
S15's other lines are secondaries to P5 and to 6.5. The drawn far-apart value carries the size
factor on top of the prior's own far value, and is read beside the data's raw value as the lags
are. The size factor cancels in a ratio, so the drawn ratio SDs and mismatch shares show what the
prior's same-level coupling and the noise give a phantom's plates. Drawn above the data's, the
phantoms' plates disagree more than the measured ones. That points at the prior's level-whitened
same-level coupling (section 1) and the noise, not at the size factor.

What each section is for:

| Section | Its lines | Role |
|---|---|---|
| S0 | stamp, legend, missing cells | first (section 2) |
| S12 | anchors | first (section 2) |
| S11 | classes, mean z by region, same level by class, h_post SD by class | secondary: 5.2, 5.4, 5.7 |
| S1 | same level by pair and by level, the six plate pairs, reruns | secondary: 5.1, 5.4, 5.6, 5.7 |
| S2 | lags, their range, across a disc, disc groups, by class | P2; secondary: 5.1, 5.4, 5.5 |
| S4 | far pairs, far mean, far in T2 to L4, reruns | P1; secondary: 5.1, 5.6 |
| S5 | refits over level subsets, the change, by class | P3; secondary: 5.7 |
| S6 | tails, paired tails, winsorised refit, normal scores | secondary: 5.6, 5.8 |
| S13 | canal test | secondary: 5.3 |
| S9 | neck by level, branch and class; canal width beside the neck's widths | secondary: 5.7 |
| S14 | plate ratios, mismatch shares | P4; secondary: 5.4 |
| S15 | generator check: same level, lags, far apart, plate ratios, mismatch, variance | P5; secondary: 6.5 |
| S8 | repeat units | secondary: 5.4, 5.6 |


## 4. The signatures of the matched truths

Every band in section 3 comes from truths the statistics critique built. Each one's flip-flop limit
reproduces the published enhance_pet C3..L5 prior exactly. It is a Kronecker part plus one kind of
structure a Kronecker cannot hold, at a share theta (kron_sim.match_core). Two of them also
reproduce the T1..L5 fit: regional measure blocks plus a shared factor (match_regional_mixed). For
each truth, truths/limit_check.jsonl gives the check's own statistics, with its own definitions, in
the population limit, with no sampling.

The kinds:
- separable: the Kronecker alone;
- noise: independent error in every cell;
- disc: the facing plates across each disc move together, widths and depths;
- size: one factor shared by every cell of the spine;
- size_wd: one factor shared by the four plate measures, not by h_post;
- vertebra_wd: one factor per vertebra, shared by its four plate measures;
- cervical_widths: the two widths of each cervical vertebra move together;
- regional: the measure part in C3-C7 differs from T1-L5, with the cervical widths coupled at 0.81
  to 0.85.

In the population limit:

| Truth (share) | P1 | P2 widths | P2 depths | P3 | lag range | six pairs | far T2-L4 | C3..C7 change |
|---|---|---|---|---|---|---|---|---|
| separable | +0.004 | 0 | 0 | 0.000 | 0 | +0.011 | +0.009 | 0.000 |
| noise 0.20 | +0.039 | 0 | 0 | -0.026 | 0 | +0.088 | +0.085 | +0.086 |
| disc 0.163 | +0.038 | +0.163 | +0.163 | -0.041 | 0 | +0.100 | +0.082 | +0.113 |
| noise 0.10 + disc 0.08 | +0.038 | +0.080 | +0.080 | -0.030 | 0 | +0.093 | +0.082 | +0.097 |
| cervical_widths 0.20 | +0.033 | 0 | 0 | -0.084 | 0 | +0.080 | +0.075 | +0.252 |
| size 0.20 | +0.172 | 0 | 0 | -0.002 | 0 | +0.144 | +0.167 | +0.053 |
| size 0.365 | +0.317 | 0 | 0 | -0.003 | 0 | +0.260 | +0.304 | +0.131 |
| size_wd 0.20 | +0.176 | 0 | 0 | -0.002 | +0.200 | +0.143 | +0.172 | +0.053 |
| size_wd 0.15 + noise 0.10 | +0.140 | 0 | 0 | -0.010 | +0.150 | +0.131 | +0.151 | +0.066 |
| vertebra_wd 0.20 | -0.076 | 0 | 0 | +0.032 | 0 | -0.177 | -0.166 | -0.122 |
| regional + size_wd 0.35 | +0.309 | 0 | 0 | -0.144 | +0.350 | +0.246 | +0.299 | +0.488 |
| regional + size 0.30 | +0.258 | 0 | 0 | -0.144 | 0 | +0.213 | +0.251 | +0.501 |

How to read the columns:
- P1, P2 and P3 are as in section 3.
- "lag range" is the range of the five measures' lag-one correlations inside T2..L4 ("one level
  apart in T2 to L4", S2). The Kronecker's own range is 0.
- "six pairs" is the same-level misfit over the six plate pairs (S1).
- "far T2-L4" is the far misfit at six or more levels inside T2..L4 (S4).
- "C3..C7 change" is the width pair of the neck's own refit minus the C3..L5 refit's (S5).

The raw same-level width pair over all levels is 0.317 under the separable truth. It is 0.43 to
0.53 under noise, disc and the shared factors, and 0.152 under vertebra_wd. By region, it is 0.84
at C3-C7 against 0.39 to 0.42 elsewhere in the regional truths, and 0.54 against 0.34 under
cervical_widths. The depth pair runs from 0.364 (vertebra_wd) to 0.710 (disc).

The null spread at the fit's n: 120 draws from the separable truth fitted to the published prior,
each statistic computed as the job computes it (truths/null_sd.jsonl):

| Statistic | n 693 mean | n 693 SD | n 67 mean | n 67 SD |
|---|---|---|---|---|
| P1 | +0.003 | 0.009 | +0.004 | 0.030 |
| P2 widths | +0.000 | 0.007 | +0.002 | 0.025 |
| P2 depths | +0.001 | 0.006 | +0.001 | 0.023 |
| P3 | 0.000 | 0.004 | -0.001 | 0.013 |
| lag range | +0.027 | 0.010 | +0.100 | 0.036 |
| six pairs | +0.010 | 0.007 | +0.014 | 0.025 |
| far T2-L4 | +0.008 | 0.010 | +0.014 | 0.038 |
| one far pair (el) | +0.004 | 0.016 | +0.001 | 0.050 |

The job prints its own null beside each statistic, from each stratum's own refit. These figures say
what to expect before it runs.
- The lag range has a positive null mean, since a range of noisy values is never negative. It is
  read as its misfit minus its null mean.
- At n 67 every spread is three to four times wider. In totalsegmentator, P1 reads only beyond
  about 0.09 and P2 beyond about 0.075, so most of its bands cannot be told apart.

The sizes survive sampling at enhance_pet's n. truths/rule_on_matched.jsonl holds one draw at
n 693 per truth, with the critic's own definitions, which average the far pairs differently from
the check:
- disc 0.163 gave facing minus far of 0.164 and 0.166, and a T2..L4 change of -0.068;
- noise 0.20 gave a six-pair misfit of 0.084 and a T1..L5 change of -0.029;
- size 0.365 gave a T1..L5 change of -0.002;
- vertebra_wd 0.20 gave a six-pair misfit of -0.176 and a T1..L5 change of +0.028.


## 5. The hypotheses, read jointly

Each hypothesis below is a joint pattern over the primaries, with the secondary lines that qualify
it. Several can hold at once, and they can pull a primary opposite ways. A vertebra-specific term
lowers P1 while a shared factor raises it, so a P1 near 0 does not rule out both. A reading names:
- every hypothesis whose pattern the primaries match;
- the secondaries that tell those hypotheses apart;
- plainly, when the primaries match none of the truths tried.

5.1 A factor of the person shared along the whole spine: sex, size, stature (the design's H1).
- The primaries: P1 at 0.12 or more, surviving both reruns; P3 within 0.01 of 0; P2 under 0.02.
- The six-pair same-level misfit and the far misfit inside T2..L4 sit near P1 (0.13 to 0.30 in the
  matched truths). The C3..C7 refit's width pair rises (+0.05 to +0.13).
- The lag range says where the factor sits. It stays at its null mean if the factor is on all five
  measures. It rises about the factor's share above that if the factor is on the four plate
  measures and not on h_post (0.15 to 0.20 in the matched truths).
- The canal test (S13) stays near 0, or is no more negative in the thick classes than in the at most
  1.5 mm class.
- Sex alone, at autoPET's mix and effect sizes, would give pooled same-level correlations of about
  0.34 for the widths and 0.36 for the depths at T10 (truths/regional_size_bound.json,
  sex_floor_T10). The check cannot tell sex from stature or from other factors of the person
  (section 7).

5.2 An offset of the protocol: site, scanner, kernel, slice spacing (H6).
- The primaries: P1 at 0.06 or more pooled, falling under 0.06 in both reruns.
- The class lines (S11) show a class whose mean z sit apart from the others.
- Offsets of opposite sign between measures point at how the protocol is read, rather than at the
  sites' people. Resampling the same thin masks to 5 mm moved h_post by a median +0.84 mm and
  endplate_depth by -0.37 mm (bordercall records/morphometry-2026-10-29/thicken.csv; +0.38 and
  -0.05 in the -axis record). One sign across every measure can be either.
- The by-class lines of the other primaries say whether each holds within one protocol: same level
  by class, facing minus far by class, the width pair change by class, the ratios by class.

5.3 A per-scan shift of the bone boundary: kernel, dose, the segmenter, the readers who corrected
the masks (measurement critique).
- The primaries look like 5.1, since such a shift varies within one protocol.
- The canal test turns negative: dilating the bone moves every body measure one way and the canal
  the other.
- The canal test is a correlation over spines between the plates' mean z and canal_ap's or canal_w's
  mean z. Where it is more negative in a class than in the at most 1.5 mm class, it points at
  boundaries in that class. Near 0, it leaves 5.1.

5.4 Noise in the measures (H3, H6).
- The primaries:
  - P1 under 0.06;
  - P2 under 0.02, unless a disc term joins the noise;
  - P3 from -0.01 down to -0.05 (-0.026 at the largest share the fit allows);
  - P4 at 0.038 or more.
- Noise raises the six-pair same-level misfit up to 0.09 while P1 stays low. That is why that line
  is no primary (statistics critique).
- Noise on every measure leaves the lag range at its null. Noise on one measure widens it, with that
  measure's lag lowest.
- Within the protocol:
  - the plate pairs are higher in the thin class than in the thick ones (same level by class);
  - the ratio SDs are larger on thick slices (ratios by class);
  - h_post's SD grows with spacing. The measurement critique infers h_post's error SD at about 1.3
    to 1.5 mm at 2.5 mm and 1.9 to 2.3 mm at 5 mm from thicken.csv, against a population SD of 1.4
    to 2.5 mm on thin slices. So h_post's near-zero couplings are read as anatomy only in the at
    most 1.5 mm class.
- The repeat units (S8) give the within-unit SD in mm, beside the anchors' SDs. They also give the
  ICC of the size-free ratios, which the volume matching that found the units does not select on.
  Low values there put the ratios' scatter in the scans, not in the persons.
- totalsegmentator, on a 1.5 mm grid, gives its own P4. If it lies near the films while
  enhance_pet's lies far above them, that points at enhance_pet's protocols.

5.5 A coupling across the disc (H5).
- The primaries: P2 at 0.05 or more in both; P1 under 0.06 (0.038); P3 from -0.03 to -0.05 (-0.041).
- It reads as anatomy only where it holds over L1-L4 within the at most 1.5 mm and 2.5 mm classes
  (facing minus far by class). The measurement critique names other routes:
  - on thick slices a thin disc spans one or two voxel layers, and one segmentation's assignment of
    them sets both facing plates;
  - osteophytes bridge the rims;
  - at T3 to T9 rib heads may enter both masks.
- The disc-group line says where along the spine it sits.

5.6 A vertebra-specific term (H7).
- The primaries: P1 at -0.04 or below; P3 at +0.02 or more; P2 under 0.02.
- The six-pair same-level misfit and the far misfit inside T2..L4 are negative (-0.18 and -0.17 in
  the matched truth). The C3..C7 refit's width pair falls (-0.12).
- Its causes are either a vertebra's own size moving its plates, or an error the engine shares
  between two measures of one vertebra (measurement critique):
  - a tilt the slices cannot resolve moves both widths, or both depths, one way;
  - both depths subtract one canal-wall intercept;
  - in the neck, both widths are cut at one pair of lines.
- It reads as anatomy only where it holds in the at most 1.5 mm class, and where the within-unit
  error correlation of the pair (S8) is near 0. A positive error correlation, or paired tails (S6),
  point at the engine, that is, at the measures.

5.7 A structure confined to the neck (H2).
- The primaries: P3 at -0.10 or below (-0.06 to -0.10 at a smaller share); P2 under 0.02. P1 reads
  whatever the shared factor gives: the two regional truths computed carry one, at 0.258 and 0.309.
- The width pair by level (S1) runs high at C3-C7 against the rest: 0.84 against 0.39 to 0.42 in the
  regional truths, and 0.54 against 0.34 with the cervical widths alone.
- The C3..C7 refit's width pair rises far: +0.49 to +0.50 in the regional truths, and +0.25 with the
  cervical widths alone.
- The T1..L4 and T2..L5 refits sit beside T1..L5, so that T1 and L5 are not taken for the neck. Their
  widths are wide and scattered by definition (measurement critique).
- Which mechanism, from S9, per class and level:
  - a large between-branch part of the width covariance, and a centred refit that lowers the width
    pair, point at the mix of the two cuts;
  - a high share of vertebrae whose two widths agree within 1 mm points at both widths reaching the
    cut;
  - the difference of the within-branch couplings, with its interval, says whether the two cuts
    couple the widths differently;
  - the canal line gives canal_w beside the two widths in mm at each cervical level. The fallback
    keeps about the canal's width plus 2 mm, so a plate whose mean width comes near that meets
    the cut, and one well under it does not. canal_w is the rows' own canal width, close to but
    not the reading the cut uses, so the line places the cut and does not measure it.
- Both branches cut the whole body at one pair of lines. So a neck pattern points at how the neck is
  measured, the cut in both branches and the slabs, not at the fallback cut alone (measurement
  critique).
- On 5 mm slices the two plates of a cervical body are read from slabs that share a voxel layer, and
  down to about T4 from slabs that abut. A pattern confined to the thick classes at C3-C7 and T1-T4
  (same level by class, width pair change by class) points at the slabs. One that holds in the at
  most 1.5 mm class points at the cut or at anatomy.
- totalsegmentator's P3 near 0, on a 1.5 mm grid, is a second view but not a test. Its scans and its
  people differ in more than their spacing.
- If P3 is at -0.10 or below while P1 is under 0.06, the primaries match none of the truths tried:
  every regional truth tried carries a shared factor. The reading says so.

5.8 Gross values (H4). Only secondaries speak to it.
- The share of cells beyond 4 robust SD (S6) is a description only. A t distribution with 3 to 4
  degrees of freedom reaches 0.5 per cent, and heavy tails do not bias the fit (scope critique).
- What matters is whether they move the coupling, read on the winsorised refit and on the
  normal-scores gap, both ways.
- On the separable truth, 3 per cent of cells moved by 3.5 to 4.5 SD lowered the Pearson width pair
  from 0.31 to between 0.19 and 0.22, while normal scores gave 0.24 to 0.25
  (truths/masking_max.jsonl).
- Independent gross values put normal scores above Pearson. Errors shared by two plates put Pearson
  above normal scores (measurement critique).
- A move of 0.05 or more in the width or depth pair qualifies every primary that rests on Pearson,
  and the reading gives the size of the move.

5.9 An error in the reading (H9). It would show in S0 and S12 (section 2), in a negative P2 and in a
P4 near 0.

5.10 Low coupling as anatomy (H8). The check reaches it only by elimination. It needs:
- P1, P2 and P3 accounted for;
- P4 at 0.038 or more in the at most 1.5 mm class too;
- the ratios' ICC high, so that their scatter repeats between scans of one person.
Even then, it would say that the plates as the engine defines them differ per person more than
films show. It would not say that the bone's plates do (section 7).


## 6. What a reading leads to

Each outcome is a proposal that a session writes for greg, with the lines it rests on.
- None is acted on without his word.
- None changes by itself the prior, its hold, the generator, the engine or #56.
- More than one can follow from one reading.

6.1 Keep the measure part held. This is the default after every reading.
- The hold waits on whether the low R_measure comes from error in the rows or from the fit's
  separable form (bordercall README.md, "Independent measures"). The check shows which the lines
  favour.
- Lifting the hold, or replacing the measure part, is greg's choice. A replacement would be a design
  of its own: the person-effect model, the blend, EM and the choice among models were cut from this
  check (scope critique), and they come back only if he asks.
- totalsegmentator's measure part stays held whatever its lines say.

6.2 Point at the measures.
- When: P4 is 0.038 or more with its z; or 5.4's or 5.6's pattern holds with the engine behind it.
  The engine shows in a coupling that falls with spacing, h_post's SD growing with spacing, a
  positive within-unit error correlation, or paired tails.
- The proposal names the measure and the mechanism the lines point at:
  - the depths' one canal-wall intercept and its slope, which is set to 0 when too few rings are
    found;
  - the rim-to-rim widths;
  - h_post's whole-layer heights on thick slices;
  - the two-layer slabs;
  - a tilt the slices cannot resolve.
- It asks greg one of three things: whether bordercall's engine should change; whether a measure
  part corrected for noise should be designed (the repeat units give only an upper bound on
  repeatability within autoPET 2.5 mm); or whether the hold stays, with the finding recorded.
- One engine measures both populations. A finding about the engine's definitions, read in
  enhance_pet, applies to totalsegmentator's rows as well, though its own lines are too few to
  show it (statistics critique). Its measure part stays held either way (6.1).

6.3 Point at the neck.
- When: P3 is -0.06 or below, and S9 names a mechanism.
- The proposal says which mechanism: the mix of the two cuts, both widths at the cut, or the slabs.
- Its consequences, for greg, are one of two:
  - a change of the engine, for the cut or the slabs;
  - a prior without the neck. That is no drop-in replacement (scope critique). run_naming's columns
    start at C3 with C2 in view. The phantom refuses a prior that does not name every level of its
    column, and a T1..L5 prior needs a cervical source. The change also alters #56's estimand, so
    it needs his word and a new or declared PREREG.
- Until he decides, the C3..L5 prior stays as it is.

6.4 Point at the protocol.
- When: P1's factor falls in both reruns.
- The proposal: the pooled fit's whole-spine factor is in good part a difference between protocol
  classes, or between the sites' people. Three options for greg: a fit within one protocol, a fit
  per class, or standardising within class before the fit.
- The classes also become a route of their own to each measure's noise, through how each pair
  changes across them.

6.5 Point at the generator's size factor.
- When: P5 is +0.05 or more. The phantoms drawn with the fitted prior and the size factor are then
  more coupled along the spine than the data.
- Three options for greg:
  - scale_sd 0 whenever a fitted prior is given;
  - a level part refitted net of size;
  - the factor kept, with the reason recorded.
- For #56, any of them goes in a DEVIATIONS.md beside bordercall's records/run-naming/PREREG.md, with
  its reason, before the run, as that PREREG requires. The check does not hold #56.
- correlation.py's docstring says a draw keeps every cell's mean and SD; the size factor breaks
  that. It is corrected in bordercall, not here.

6.6 Add the covariates.
- When: P1's factor survives both reruns, and the canal test does not point at boundaries. The next
  step is then to size sex and stature, which this check deferred.
- It needs the covariates join's per-person table on the grid, and the covariates word's guard
  against differencing within-sex aggregates across reports.
- autoPET has sex for 861 of its 867 persons, TotalSegmentator for its subjects (85 men, 73
  women), and Leipzig and Careggi for none.
- It is added when greg asks.

Writing a reading. The steps:
1. The job, the commit it was sent from, the stamp, and S0 and S12: read or stopped, and why.
2. Each primary, with enhance_pet's and totalsegmentator's side by side:
   - its value;
   - its z_boot (for P4, its z from the films);
   - its band, or "not read" and why.
3. The hypotheses whose patterns the primaries match, with the secondary lines that qualify each,
   and those the lines rule out. Or a plain statement that they match none of the truths tried.
4. The proposals of section 6, each with the lines it rests on.
5. What stays unsettled (section 7).
It goes to greg in plain words. The lines it quotes are kept under a dated name in this folder
(README.md).


## 7. What the check cannot settle

- Whom the factor belongs to. The check can say that a whole-spine factor survives within one
  protocol and one site. It cannot tell sex from stature, or from any other factor of the person:
  the covariates are deferred (README.md).
- The bone's coupling. No line measures the true coupling of one vertebra's plates. The repeat
  units were found by matching volumes, spacings and ribs, so their ICC is an upper bound on
  repeatability within autoPET at 2.5 mm. Every corrected coupling is printed only inside that
  class, and nothing says how other protocols repeat.
- Whether the literature applies. Gibbs's correlations may pool levels. NHANES II reads films, by
  another definition, with outliers left out, in another population. The factor of two in P4's
  band is a judgment, not a measurement.
- Structures the bands were not calibrated on. The bands come from single kinds of structure and a
  few mixtures, matched to enhance_pet's published fits. Not all of these were computed:
  - noise on one measure alone;
  - a factor on the widths alone, or one whose loadings differ in sign between classes;
  - a vertebra term on the widths alone;
  - mixtures that cancel in a primary.
  A reading against the bands is a reading against those families, not a proof.
- Clustering above the unit. The bootstrap resamples repeat units, and every other spine is a unit
  of its own; it does not resample sites. A factor shared by one site's scans shows in the reruns,
  not in boot se.
- totalsegmentator. It has 67 fit spines, one protocol class and no repeat units, and its truths
  were matched to enhance_pet's fit, not its own. Most of its bands cannot be told apart (section
  4), and it has no reruns.
- Transitional spines whose masks name no extra level. The gold tier 3 completion's count from C2
  is not in the rows.
- What the check does not touch:
  - C2 and the sacrum;
  - the held part, which is counted only and stays the fit's untouched score;
  - VerSe, which is not run;
  - the prior's held-out gain;
  - #56's answer, which does not depend on R_measure (section 1).
- Whether the drawn phantoms are plausible as bones. S15 compares the generator with the data as
  measured. A phantom as mismatched as the data is still as mismatched as the measures.


## 8. Where the numbers come from

In this folder (truths/README.md says how each was made):
- truths/limit_check.jsonl (this thread): the check's statistics, with its own definitions, in the
  population limit for each matched truth. It is the source of every band and of section 4's first
  table.
- truths/null_sd.jsonl (this thread): 120 draws each at n 693 and n 67 from the separable truth
  fitted to the published enhance_pet C3..L5 prior. The statistics are computed as the job computes
  them. It is the source of section 4's second table.
- truths/limit_stats.jsonl and truths/rule_on_matched.jsonl (the statistics critique): the same
  truths with the critic's definitions, and one draw at n 693 of each.
- truths/regional_size_bound.json, truths/mixed_bound.json and truths/width_factor_bound.txt (the
  statistics critique): the bounds on the raw same-level pairs, and the sex floor at T10.
- truths/masking_max.jsonl (the statistics critique): the draws with gross values.
- truths/results-phantom.json (the design): draws of the generator with the card's margins.
The truths were built by kron_sim.match_core and match_regional_mixed, in the critic's scratch
scripts. Those scripts are not in this repository (README.md).

In bordercall at origin/main 1ef008f:
- records/prior-2026-10-31/report.md: the published fits (job 40902475, commit 59ef820).
- records/morphometry-2026-10-29/compare-229.csv: the thin-slice studies' means and SDs, beside the
  CT papers.
- records/morphometry-2026-10-29/thicken.csv and records/morphometry-2026-10-29-axis/thicken.csv:
  three thin masks resampled to 2.5 and 5 mm.
- README.md, the limit "Independent measures": the hold.
- schwingcheck/columns.py at 8ae5db9: the generator, vendored here as
  grid/prior/schwingcheck/columns.py.

Papers:
- Hipp 2022, JBMR Plus, PMC9549721, Appendix S1: NHANES II lateral films, 35,275 lumbar and 44,938
  cervical vertebrae.
- Gibbs 2022, MSc thesis in anatomy, University of Pretoria, repository handle 2263/86351: 30 men,
  dry bone.

The critiques are named in words throughout (statistics, measurement, scope). README.md in this
folder gives their source.
