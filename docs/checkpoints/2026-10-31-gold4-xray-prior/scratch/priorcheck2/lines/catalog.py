"""The check's line catalogue for SPEC.md: per section, each line's readable example (enhance_pet's head,
illustrative values only) with its length, and the longest the same format prints (totalsegmentator's
head, the widest values), both with the '- ' the sbatch adds. Also passes every worst-case line through
the gate's own filters (grid/shape-words.awk, grid/report-shapes.awk, grid/redact.sed)."""
import json, re, subprocess, sys

E, T = "enhance_pet C3..L5 check: ", "totalsegmentator C3..L5 check: "
STAMP = "1cee7ea83e4c28db"
JW = "-0.150 null -0.012 sd 0.005 z -999.9"
JBW = JW + ", boot se 0.015 z -999.9"
P10W = " ".join(["-0.32"] * 10)
P6W = " ".join(["-0.030"] * 6)
L22W = " ".join(["0.12"] * 22)
R5W = " ".join(["-0.12"] * 5)
CLS = "at most 1.5 mm %s; 2.5 mm %s; 3 mm %s; 5 mm %s"
CLS5 = "at most 1.5 mm %s; 2.5 mm %s; 2.8 mm %s; 3 mm %s; 5 mm %s"

# (section, key, readable, worst)
L = []
def add(s, k, r, w=None):
    L.append((s, k, r, w if w is not None else r))

add("S0", "stamp", "rows at one code stamp %s; whole fit spines 693 of 809 kept, whole held 158 of 190; refit against the fitted prior, largest difference 0e+00" % STAMP,
    "rows at one code stamp %s; whole fit spines 1693 of 1809 kept, whole held 1158 of 1190; refit against the fitted prior, largest difference 2e-16" % STAMP)
add("S0", "stamps", "rows at 2 code stamps, the commonest %s on 801 of 809 kept fit studies; whole fit spines 693, whole held 158; refit against the prior 0e+00" % STAMP,
    "rows at 12 code stamps, the commonest %s on 1801 of 1809 kept fit studies; whole fit spines 1693, whole held 1158; refit against the prior 2e-16" % STAMP)
add("S0", "legend", "legend: e endplate, d endplate_depth, l endplate_lower, ld endplate_lower_depth, h h_post; pairs ed el eld eh dl dld dh lld lh ldh; plate pairs leave out h")
add("S0", "missing", "missing cells of the kept fit studies: e 1.2%, d 0.8%, l 1.1%, ld 0.9%, h 2.0%; most in C3-C7, 4.1%; z is per cell over the whole fit spines",
    "missing cells of the kept fit studies: e 12.2%, d 10.8%, l 11.1%, ld 10.9%, h 12.0%; most in T2-T12, 14.1%; z is per cell over the whole fit spines")
add("S11", "class", "class 2.5 mm, 365 spines: autoPET 364, Leipzig 1; models 2, top Biograph128 300; kernels 2, top I31f-2 200",
    "class at most 1.5 mm, 1110 spines: autoPET 1092, Leipzig 1018, Careggi 1001; models 12, top " + "Q" * 21 + " 1160; kernels 12, top " + "Q" * 21 + " 1155")
add("S11", "same-by-class", "same level, class 5 mm, over C3-C7 T1-T4 T5-T12 L1-L4: el 0.60 0.40 0.30 0.35, dld 0.50 0.45 0.47 0.49; h with e d l ld 0.05 0.10 0.04 0.09",
    "same level, class at most 1.5 mm, over C3-C7 T1-T4 T5-T12 L1-L4: el -0.60 -0.40 -0.30 -0.35, dld -0.50 -0.45 -0.47 -0.49; h with e d l ld -0.05 -0.10 -0.04 -0.09")
add("S11", "class-nofacts", "class at most 1.5 mm, 67 whole fit spines: sites, models and kernels are read for enhance_pet alone")
add("S11", "one-class", "one protocol class, so the by-class lines and the within-class reruns are the pooled ones and are not printed")
add("S11", "meanz-a", "class 2.5 mm mean z by C3-C7 T1 T2-T12 L1-L4 L5: e +0.04 +0.10 -0.02 -0.05 +0.01, d -0.06 -0.03 +0.02 +0.04 +0.00, l +0.03 +0.08 -0.01 -0.04 +0.02",
    "class at most 1.5 mm mean z by C3-C7 T1 T2-T12 L1-L4 L5: e %s, d %s, l %s" % (R5W, R5W, R5W))
add("S11", "meanz-b", "class 2.5 mm mean z by C3-C7 T1 T2-T12 L1-L4 L5: ld -0.05 -0.02 +0.03 +0.04 +0.01, h -0.10 -0.08 -0.06 -0.07 -0.09",
    "class at most 1.5 mm mean z by C3-C7 T1 T2-T12 L1-L4 L5: ld %s, h %s" % (R5W, R5W))
add("S11", "hpost", "h_post SD in mm by class, C3-C7 then T2-L4: at most 1.5 mm 1.6 1.7; 2.5 mm 1.9 2.0; 3 mm 2.0 2.1; 5 mm 2.6 2.7",
    "h_post SD in mm by class, C3-C7 then T2-L4: " + CLS5 % ("99.9 99.9", "99.9 99.9", "99.9 99.9", "99.9 99.9", "99.9 99.9"))
add("S11", "too-few", "classes under 30 whole fit spines, left out of every by-class line: 2.8 mm 8",
    "classes under 30 whole fit spines, left out of every by-class line: at most 1.5 mm 29; 2.5 mm 29; 2.8 mm 29; 3 mm 29; 5 mm 29; no spacing row 1029")
add("S12", "anchors-1", "anchors e, mean then SD in mm, C3 to T6: 16.1 1.2, 16.5 1.3, 17.2 1.4, 18.6 1.6, 25.1 5.5, 40.2 9.1, 31.2 3.1, 29.0 2.8, 28.1 2.6, 28.5 2.7, 29.6 2.9",
    "anchors ld, mean then SD in mm, C3 to T6: " + ", ".join(["62.2 13.0"] * 11))
add("S12", "anchors-2", "anchors e, mean then SD in mm, T7 to L5: 30.8 3.0, 32.0 3.1, 33.4 3.3, 35.1 3.4, 36.9 3.6, 38.6 3.8, 41.0 4.1, 44.2 4.6, 47.9 5.1, 53.6 6.2, 62.2 13.0",
    "anchors ld, mean then SD in mm, T7 to L5: " + ", ".join(["62.2 13.0"] * 11))
add("S1", "pair", "same level el: C3-C7 0.21 T1 0.15 T2-T12 0.33 L1-L4 0.35 L5 0.30 all 0.30 ranks 0.31; drawn 0.29; misfit +0.004 null +0.001 sd 0.004 z +0.8",
    "same level ldh: C3-C7 -0.21 T1 -0.15 T2-T12 -0.33 L1-L4 -0.35 L5 -0.30 all -0.30 ranks -0.31; drawn -0.30; misfit " + JW)
add("S1", "six", "same level, the six plate pairs: raw 0.25 drawn 0.21 misfit +0.040 null +0.010 sd 0.004 z +7.5, boot se 0.012 z +2.5",
    "same level, the six plate pairs: raw -0.25 drawn -0.10 misfit " + JBW)
add("S1", "by-level-el", "same level el by level C3 to L5, in hundredths: 22 20 19 21 30 15 33 32 31 33 34 33 32 33 34 35 36 35 36 35 34 28",
    "same level dld by level C3 to L5, in hundredths: " + " ".join(["-22"] * 22))
add("S1", "by-level-se", "same level by level, unit bootstrap SE: median el 0.040 dld 0.035; largest el 0.080 at T1, dld 0.070 at L5",
    "same level by level, unit bootstrap SE: median el 0.040 dld 0.035; largest el 0.080 at T12, dld 0.070 at T12")
add("S1", "within-ten", "within class, 718 spines in 4 classes, same level ten pairs: 0.17 0.28 0.10 -0.02 0.06 0.44 0.03 0.12 0.08 0.05",
    "within class, 1718 spines in 5 classes, same level ten pairs: " + P10W)
add("S1", "within-six", "within class, same level, the six plate pairs: raw 0.22 drawn 0.19 misfit +0.030 null +0.010 sd 0.005 z +4.0, boot se 0.011 z +1.8",
    "within class, same level, the six plate pairs: raw -0.25 drawn -0.10 misfit " + JBW)
add("S1", "ap-ten", "autoPET 2.5 mm alone, 364 spines, same level ten pairs: 0.18 0.30 0.11 -0.01 0.07 0.46 0.04 0.13 0.09 0.06",
    "autoPET 2.5 mm alone, 1364 spines, same level ten pairs: " + P10W)
add("S1", "ap-six", "autoPET 2.5 mm alone, same level, the six plate pairs: raw 0.24 drawn 0.20 misfit +0.035 null +0.010 sd 0.007 z +3.6, boot se 0.016 z +1.6",
    "autoPET 2.5 mm alone, same level, the six plate pairs: raw -0.25 drawn -0.10 misfit " + JBW)
add("S1", "reruns-within-off", "reruns within class, of the same-level and far-apart lines: not run, under two classes of 30")
add("S1", "reruns-ap-off", "reruns in autoPET 2.5 mm alone, of the same-level and far-apart lines: not run, under 60 spines")
add("S2", "lag-m", "one level apart, same measure, e: C3-C7 0.62 C7-T2 0.31 T2-T12 0.71 T12-L4 0.69 L4-L5 0.40",
    "one level apart, same measure, ld: C3-C7 -0.62 C7-T2 -0.31 T2-T12 -0.71 T12-L4 -0.69 L4-L5 -0.40")
add("S2", "lag-core", "one level apart in T2 to L4, same measure: e 0.52 d 0.55 l 0.50 ld 0.56 h 0.31; range of the five, misfit +0.250 null +0.032 sd 0.010 z +21.8",
    "one level apart in T2 to L4, same measure: e -0.52 d -0.55 l -0.50 ld -0.56 h -0.31; range of the five, misfit " + JW)
add("S2", "disc", "across a disc in T2 to L4, widths: facing 0.24 far 0.12, facing minus far +0.120 null +0.000 sd 0.006 z +20.0, boot se 0.012 z +10.0",
    "across a disc in T2 to L4, depths: facing -0.24 far -0.12, facing minus far " + JBW)
add("S2", "disc-groups", "facing minus far by disc group, the lower vertebra T3-T9 T10-T12 L1-L4: widths +0.100 +0.120 +0.150; depths +0.080 +0.090 +0.200",
    "facing minus far by disc group, the lower vertebra T3-T9 T10-T12 L1-L4: widths -0.100 -0.120 -0.150; depths -0.080 -0.090 -0.200")
add("S2", "disc-class", "facing minus far by class, widths over T2-L4 then L1-L4: at most 1.5 mm +0.05 +0.07; 2.5 mm +0.12 +0.15; 3 mm +0.08 +0.10; 5 mm +0.20 +0.22",
    "facing minus far by class, depths over T2-L4 then L1-L4: " + CLS5 % ("-0.05 -0.07", "-0.12 -0.15", "-0.12 -0.15", "-0.08 -0.10", "-0.20 -0.22"))
add("S4", "far-pairs", "far apart, C3-C7 with L1-L4, misfit by plate pair ed el eld dl dld lld: +0.020 +0.030 +0.010 +0.020 +0.030 +0.020; one sign",
    "far apart, C3-C7 with L1-L4, misfit by plate pair ed el eld dl dld lld: " + P6W + "; signs differ")
add("S4", "far-mean", "far apart, C3-C7 with L1-L4, mean of the six plate pairs: raw 0.05 drawn 0.03 misfit +0.022 null +0.000 sd 0.004 z +5.5, boot se 0.009 z +2.4",
    "far apart, C3-C7 with L1-L4, mean of the six plate pairs: raw -0.05 drawn -0.02 misfit " + JBW)
add("S4", "far-nomean", "far apart, C3-C7 with L1-L4: the six plate pairs differ in sign, so no mean is taken")
add("S4", "far-core", "far apart in T2 to L4, six or more levels, misfit by plate pair: +0.020 +0.030 +0.010 +0.020 +0.030 +0.020; mean +0.022 null +0.000 sd 0.004 z +5.5",
    "far apart in T2 to L4, six or more levels, misfit by plate pair: " + P6W + "; mean " + JW)
add("S4", "within-pairs", "within class, far apart, C3-C7 with L1-L4, misfit by plate pair: +0.002 -0.004 +0.001 +0.003 -0.002 +0.001; signs differ",
    "within class, far apart, C3-C7 with L1-L4, misfit by plate pair: " + P6W + "; signs differ")
add("S4", "within-mean", "within class, far apart, C3-C7 with L1-L4, mean of the six plate pairs: misfit +0.004 null +0.000 sd 0.004 z +1.0, boot se 0.008 z +0.5",
    "within class, far apart, C3-C7 with L1-L4, mean of the six plate pairs: misfit " + JBW)
add("S4", "ap-pairs", "autoPET 2.5 mm alone, far apart, C3-C7 with L1-L4, misfit by plate pair: +0.010 +0.012 +0.008 +0.011 +0.015 +0.009; one sign",
    "autoPET 2.5 mm alone, far apart, C3-C7 with L1-L4, misfit by plate pair: " + P6W + "; signs differ")
add("S4", "ap-mean", "autoPET 2.5 mm alone, far apart, C3-C7 with L1-L4, mean of the six plate pairs: misfit +0.011 null +0.000 sd 0.006 z +1.8, boot se 0.012 z +0.9",
    "autoPET 2.5 mm alone, far apart, C3-C7 with L1-L4, mean of the six plate pairs: misfit " + JBW)
add("S5", "base", "refit C3..L5 unshrunk, ten pairs: 0.18 0.32 0.11 -0.02 0.07 0.49 0.04 0.13 0.09 0.05",
    "refit C3..L5 unshrunk, ten pairs: " + P10W)
add("S5", "sub", "refit T1..L5 on the same spines: 0.26 0.17 0.16 -0.07 0.12 0.47 0.05 0.17 0.08 0.07; width pair change -0.150 null +0.001 sd 0.005 z -30.2",
    "refit T2..L4 on the same spines: " + P10W + "; width pair change " + JW)
add("S5", "change", "width pair change from C3..L5 to T1..L5: -0.150 null +0.001 sd 0.005 z -30.2, boot se 0.020 z -7.6",
    "width pair change from C3..L5 to T1..L5: " + JBW)
add("S5", "change-class", "width pair change from C3..L5 to T1..L5 by class: at most 1.5 mm -0.100; 2.5 mm -0.120; 3 mm -0.200; 5 mm -0.250",
    "width pair change from C3..L5 to T1..L5 by class: " + CLS5 % ("-0.100", "-0.120", "-0.120", "-0.200", "-0.250"))
add("S6", "tails", "beyond 4 SD on robust z, median and MAD: e 0.30% d 0.25% l 0.28% ld 0.22% h 0.40%; most in C3-C7, 1.10%; a Gaussian gives 0.006%",
    "beyond 4 SD on robust z, median and MAD: e 10.30% d 10.25% l 10.28% ld 10.22% h 10.40%; most in T2-T12, 11.10%; a Gaussian gives 0.006%")
add("S6", "paired", "paired tails beyond 3 robust SD, widths depths, by class: at most 1.5 mm 0.10% 0.05%; 2.5 mm 0.20% 0.10%; 3 mm 0.15% 0.12%; 5 mm 0.60% 0.40%",
    "paired tails beyond 3 robust SD, widths depths, by class: " + CLS5 % ("9.99% 9.99%", "9.99% 9.99%", "9.99% 9.99%", "9.99% 9.99%", "9.99% 9.99%"))
add("S6", "winsor", "winsorised at 4 robust SD, refit C3..L5 unshrunk: width pair 0.330 depth pair 0.495, change +0.013 +0.008",
    "winsorised at 4 robust SD, refit C3..L5 unshrunk: width pair -0.330 depth pair -0.495, change -0.013 -0.008")
add("S6", "ns-refit", "normal-scores refit C3..L5 unshrunk, ten pairs: 0.19 0.33 0.12 -0.01 0.08 0.48 0.04 0.14 0.09 0.05",
    "normal-scores refit C3..L5 unshrunk, ten pairs: " + P10W)
add("S6", "ns-gap", "normal scores minus Pearson, same level, six plate pairs: +0.010 +0.030 +0.005 +0.012 -0.004 +0.008; largest absolute 0.030 at el",
    "normal scores minus Pearson, same level, six plate pairs: " + P6W + "; largest absolute 0.050 at lld")
add("S13", "canal", "canal test, r over spines of the plates mean z with canal_ap mean z: all -0.10 of 690; at most 1.5 mm -0.05; 2.5 mm -0.12; 3 mm -0.15; 5 mm -0.30",
    "canal test, r over spines of the plates mean z with canal_ap mean z: all -0.10 of 1690; " + CLS5 % ("-0.05", "-0.12", "-0.12", "-0.15", "-0.30"))
add("S13", "canal-one", "canal test, r over spines of the plates mean z: with canal_ap -0.10, with canal_w -0.05, of 67 spines",
    "canal test, r over spines of the plates mean z: with canal_ap -0.10, with canal_w -0.05, of 1067 spines")
add("S9", "legend", "neck: foramina is the body cut at the foramina, fallback the cut at the canal side walls; e and l pooled mean z; r within a branch; agree, widths within 1 mm")
add("S9", "level", "neck C5, 2.5 mm: pooled r 0.27; foramina 210 e -0.05 l +0.02 r 0.25 agree 4%; fallback 155 e +0.10 l -0.03 r 0.40 agree 18%",
    "neck C5, at most 1.5 mm: pooled r -0.25; foramina 1210 e -0.05 l -0.02 r -0.25 agree 14%; fallback 1155 e -0.10 l -0.03 r -0.40 agree 18%")
add("S9", "cov", "neck widths covariance in z, within then between, C3 to C7, 2.5 mm: +0.20 +0.05, +0.18 +0.02, +0.22 +0.01, +0.25 -0.02, +0.30 +0.10",
    "neck widths covariance in z, within then between, C3 to C7, at most 1.5 mm: " + ", ".join(["-0.20 -0.05"] * 5))
add("S9", "diff", "neck, 2.5 mm: fallback minus foramina width-pair r over C3-C7, levels weighted by the smaller count: +0.12, unit bootstrap 0.05 to 0.19",
    "neck, at most 1.5 mm: fallback minus foramina width-pair r over C3-C7, levels weighted by the smaller count: -0.12, unit bootstrap -0.05 to -0.19")
add("S9", "centred", "neck widths centred within level and branch, refit width pair: 0.317 before, 0.262 after",
    "neck widths centred within level and branch, refit width pair: -0.301 before, -0.250 after")
add("S9", "centred-class", "neck widths centred within level and branch, refit width pair change by class: at most 1.5 mm -0.040; 2.5 mm -0.060; 3 mm -0.040; 5 mm -0.050",
    "neck widths centred within level and branch, refit width pair change by class: " + CLS % ("-0.040", "-0.060", "-0.040", "-0.050"))
add("S14", "ratio-w", "SD of log of e over l by level C3 to L5: 0.12 0.11 0.10 0.10 0.13 0.20 0.07 0.07 0.06 0.06 0.06 0.06 0.06 0.06 0.06 0.06 0.06 0.07 0.07 0.07 0.07 0.14",
    "SD of log of d over ld by level C3 to L5: " + L22W)
add("S14", "ratio-d", "SD of log of d over ld by level C3 to L5: 0.09 0.08 0.08 0.08 0.09 0.11 0.07 0.07 0.06 0.06 0.06 0.06 0.06 0.06 0.06 0.06 0.06 0.06 0.06 0.06 0.06 0.09",
    "SD of log of d over ld by level C3 to L5: " + L22W)
add("S14", "ratio-primary", "plate ratios, median SD of log ratio: depths C3-C7 0.080 L1-L4 0.060, NHANES II 0.030 to 0.036 and 0.017 to 0.019; widths T2-L4 0.060; boot se 0.003 0.003 0.002",
    "plate ratios, median SD of log ratio: depths C3-C7 1.080 L1-L4 1.060, NHANES II 0.030 to 0.036 and 0.017 to 0.019; widths T2-L4 1.060; boot se 0.003 0.003 0.002")
add("S14", "mismatch", "spines holding a vertebra over 20% off its level ratio of means, C3..L5: widths 45.1% depths 30.2% either 55.3%; T2..L4: 30.1% 20.4% 38.2%",
    "spines holding a vertebra over 20% off its level ratio of means, C3..L5: widths 100.0% depths 100.0% either 100.0%; T2..L4: 100.0% 100.0% 100.0%")
add("S14", "mismatch-v", "vertebrae over 20% off their level ratio of means, C3..L5: widths 15.0% depths 8.0%; T2..L4: widths 10.0% depths 6.0%",
    "vertebrae over 20% off their level ratio of means, C3..L5: widths 100.0% depths 100.0%; T2..L4: widths 100.0% depths 100.0%")
add("S15", "legend", "generator check: 5000 typical columns from draw_columns with the fitted prior, size SD 0.07 and noise 1.0 mm as run_naming, and the data cell means and SDs")
add("S15", "same", "generator check, same level el, drawn then data: C3-C7 0.48 0.21, T2-T12 0.52 0.33, L1-L4 0.53 0.35, all 0.51 0.30, data boot se 0.015",
    "generator check, same level dld, drawn then data: C3-C7 -0.51 -0.21, T2-T12 -0.52 -0.33, L1-L4 -0.53 -0.35, all -0.51 -0.30, data boot se 0.015")
add("S15", "lags", "generator check, one to five levels apart, same measure, drawn 0.58 0.55 0.53 0.51 0.51, data 0.49 0.43 0.39 0.37 0.35",
    "generator check, one to five levels apart, same measure, drawn -0.58 -0.55 -0.53 -0.51 -0.51, data -0.49 -0.43 -0.39 -0.37 -0.35")
add("S15", "mismatch", "generator check, spines with a vertebra over 20% off, drawn then data: widths 60.2% 45.1%, depths 40.3% 30.2%, either 70.4% 55.3%",
    "generator check, spines with a vertebra over 20% off, drawn then data: widths 100.0% 100.0%, depths 100.0% 100.0%, either 100.0% 100.0%")
add("S15", "variance", "generator check, a cell variance: size factor share median 0.31, range 0.10 to 0.45; noise share median 0.05; drawn SD over data SD median 1.21",
    "generator check, a cell variance: size factor share median 0.31, range 0.10 to 0.45; noise share median 0.05; drawn SD over data SD median 99.99")
add("S8", "units", "repeat units in the fit part: 47 holding 113 spines (34 of 2, 9 of 3, 2 of 4, 2 of 5); 37 all autoPET 2.5 mm, 8 of mixed classes, 2 other",
    "repeat units in the fit part: 147 holding 1113 spines (134 of 2, 19 of 3, 12 of 4, 12 of 5, 11 of more); 137 all autoPET 2.5 mm, 18 of mixed classes, 12 other")
add("S8", "caveat", "repeat units were found by matching volumes, spacings and ribs, so each ICC below is an upper bound on repeatability within one protocol")
add("S8", "icc", "ICC1 e by C3-C7 T1 T2-T12 L1-L4 L5: 0.85 0.80 0.90 0.92 0.88; T2-L4 0.91, unit bootstrap 0.86 to 0.94",
    "ICC1 ld by C3-C7 T1 T2-T12 L1-L4 L5: -0.85 -0.80 -0.90 -0.92 -0.88; T2-L4 -0.91, unit bootstrap -0.86 to -0.94")
add("S8", "within-sd", "within-unit SD in mm, C3-C7 then T2-L4: e 1.5 1.2, d 0.9 0.8, l 1.4 1.1, ld 0.9 0.8, h 1.3 1.0",
    "within-unit SD in mm, C3-C7 then T2-L4: e 11.5 11.2, d 10.9 10.8, l 11.4 11.1, ld 10.9 10.8, h 11.3 11.0")
add("S8", "ratios", "ICC1 of size-free log ratios over T2-L4: e over l 0.40 (0.25 to 0.55), d over ld 0.35 (0.20 to 0.50), h over d 0.30 (0.15 to 0.45)",
    "ICC1 of size-free log ratios over T2-L4: e over l -0.40 (-0.25 to -0.55), d over ld -0.35 (-0.20 to -0.50), h over d -0.30 (-0.15 to -0.45)")
add("S8", "errcorr", "within-unit error correlation, ten pairs over every level: 0.10 0.35 0.05 0.02 0.08 0.40 0.03 0.06 0.04 0.02; boot se el 0.05 dld 0.06",
    "within-unit error correlation, ten pairs over every level: " + P10W + "; boot se el 0.05 dld 0.06")
add("S8", "corrected", "corrected r, autoPET 2.5 mm alone, 37 units, same level over T2-L4, raw then corrected: el 0.31 0.45, dld 0.47 0.60, ed 0.17 0.22, lld 0.13 0.16",
    "corrected r, autoPET 2.5 mm alone, 137 units, same level over T2-L4, raw then corrected: el -0.31 over 1, dld -0.47 over 1, ed -0.17 over 1, lld -0.13 over 1")
add("S8", "off", "repeat units: not run, 7 in the fit part hold two whole spines or more, under 10",
    "repeat units: not run, 9999 in the fit part hold two whole spines or more, under 10")
add("end", "done", "done in 412 s, 200 draws for each null and each unit bootstrap", "done in 7199 s, 2000 draws for each null and each unit bootstrap")
add("any", "fault", "fault at S9, an error of the kind ZeroDivisionError", "fault at S15, an error of the kind " + "Q" * 40)
add("any", "notrun", "not run, the C3..L5 fit took fewer than 30 whole spines")
add("any", "late", "S9 and every section after it not run, the check ran past 90 minutes",
    "S15 and every section after it not run, the check ran past 90 minutes")
add("S14", "ratio-class", "plate ratios by class, median SD of log ratio, depths L1-L4 then widths T2-L4: " + CLS % ("0.050 0.060", "0.045 0.055", "0.060 0.070", "0.080 0.090"),
    "plate ratios by class, median SD of log ratio, depths L1-L4 then widths T2-L4: " + CLS % ("9.999 9.999", "9.999 9.999", "9.999 9.999", "9.999 9.999"))
add("S1", "pair-h", "same level dh: C3-C7 0.05 T1 0.02 T2-T12 0.04 L1-L4 0.06 L5 0.03 all 0.04 ranks 0.05; drawn 0.03; misfit +0.010 null +0.001 sd 0.004 z +2.2",
    "same level ldh: C3-C7 -0.99 T1 -0.99 T2-T12 -0.99 L1-L4 -0.99 L5 -0.99 all -0.99 ranks -0.99; drawn -0.99; misfit -0.999 null -0.999 sd 0.999 z -999.9")
add("S15", "same-d", "generator check, same level dld, drawn then data: C3-C7 0.55 0.45, T2-T12 0.60 0.47, L1-L4 0.62 0.49, all 0.59 0.46, data boot se 0.014",
    "generator check, same level dld, drawn then data: C3-C7 -0.99 -0.99, T2-T12 -0.99 -0.99, L1-L4 -0.99 -0.99, all -0.99 -0.99, data boot se 0.999")


add("S0", "stamp-other", "rows at one code stamp not 16 hex; whole fit spines 693 of 809 kept, whole held 158 of 190; refit against the fitted prior, largest difference 0e+00",
    "rows at one code stamp not 16 hex; whole fit spines 1693 of 1809 kept, whole held 1158 of 1190; refit against the fitted prior, largest difference 2e-16")
add("S0", "stamps-other", "rows at 2 code stamps, the commonest not 16 hex on 801 of 809 kept fit studies; whole fit spines 693, whole held 158; refit against the prior 0e+00",
    "rows at 12 code stamps, the commonest not 16 hex on 1801 of 1809 kept fit studies; whole fit spines 1693, whole held 1158; refit against the prior 2e-16")
add("S9", "canal-mm", "neck mean widths in mm, canal_w then e then l, C3 to C7: 24.1 25.2 19.3; 24.5 26.0 19.6; 25.0 27.1 21.0; 25.3 28.0 23.9; 24.9 29.0 23.8",
    "neck mean widths in mm, canal_w then e then l, C3 to C7: " + "; ".join(["999.9 999.9 999.9"] * 5))
add("S8", "corrected-boot", "corrected r, unit bootstrap 2.5 and 97.5 percentiles: el 0.38 to 0.55, dld 0.52 to 0.71; draws past 1 in size, el 0 dld 2",
    "corrected r, unit bootstrap 2.5 and 97.5 percentiles: el -1.00 to -1.00, dld -1.00 to -1.00; draws past 1 in size, el 2000 dld 2000")
add("S8", "corrected-boot-none", "corrected r, unit bootstrap 2.5 and 97.5 percentiles: boot none")
add("S8", "corrected-off", "corrected r: not run, fewer than 10 repeat units wholly inside autoPET 2.5 mm")
add("S15", "far", "generator check, far apart, C3-C7 with L1-L4, raw mean of the six plate pairs, drawn then data: 0.21 0.05",
    "generator check, far apart, C3-C7 with L1-L4, raw mean of the six plate pairs, drawn then data: -0.21 -0.05")
add("S15", "ratios", "generator check, plate ratios, median SD of log ratio, drawn then data: depths C3-C7 0.070 0.080, L1-L4 0.055 0.060; widths T2-L4 0.050 0.060",
    "generator check, plate ratios, median SD of log ratio, drawn then data: depths C3-C7 9.999 9.999, L1-L4 9.999 9.999; widths T2-L4 9.999 9.999")


BAD = re.compile(r"/|[0-9]{5}|(?i:patient|institution|operators|physician|accession|stationname|deviceserial|instanceuid|studydate|seriesdate|acquisitiondate|contentdate|studytime|studyid|invalid value for vr|bearer|basic|token|secret|credential|password|passwd|pwd|apikey|api_key|api-key|authorization|cookie)|:[^ ]|['\"`]|\(first |FAILED|refused:|why:|=|\([0-9A-Fa-f]{4}, ?[0-9A-Fa-f]{4}\)|[0-9]+(\.[0-9]+){4,}")
grid = "/home/claude/SchwingNet/grid"
problems, worst_lines = [], []
cat = {}
for s, k, r, w in L:
    le, lw = len("- " + E + r), len("- " + T + w)
    for line in ("- " + E + r, "- " + T + w):
        if len(line) > 196: problems.append("long %s %s %d" % (s, k, len(line)))
        m = BAD.search(line[2:])
        if m: problems.append("shape %s %s %r" % (s, k, m.group(0)))
        if [h for h in re.findall(r"[0-9a-fA-F]{8,}", line) if h != STAMP]: problems.append("hex %s %s" % (s, k))
        if re.search(r"(19|20)[0-9]{2}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])", line): problems.append("date %s %s" % (s, k))
        if any(ord(c) < 32 or ord(c) > 126 for c in line): problems.append("ascii %s %s" % (s, k))
    worst_lines.append("- " + T + w); worst_lines.append("- " + E + r)
    cat.setdefault(s, []).append((k, "- " + E + r, le, lw))
text = "\n".join(worst_lines) + "\n"
p = subprocess.run("awk -v data=/rs/x -v runs=/rs/r -v models=/rs/m -v repo=/home/x -f %s/shape-words.awk -f %s/report-shapes.awk | sed -r -f %s/redact.sed" % (grid, grid, grid),
                   shell=True, input=text, capture_output=True, text=True)
filters_same = p.stdout == text
json.dump(dict(problems=problems, filters_same=filters_same, catalog=cat), open(sys.argv[1], "w"), indent=0)
print("lines", len(L), "problems", problems, "filters leave them as they are:", filters_same)
