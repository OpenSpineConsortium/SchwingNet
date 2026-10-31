"""Example check lines with their lengths, for SPEC.md (illustrative values only)."""
import re, sys

HEADS = {"enhance_pet": "enhance_pet C3..L5 check: ", "totalsegmentator": "totalsegmentator C3..L5 check: "}
J = "+0.150 null +0.002 sd 0.005 z +29.6"            # judged, worst width about 36
JB = J + ", boot se 0.015 z +9.9"                     # judged with the unit bootstrap
PAIRS10 = "0.18 0.32 0.11 -0.02 0.07 0.49 0.04 0.13 0.09 0.05"
PAIRS10W = "-0.18 -0.32 -0.11 -0.02 -0.07 -0.49 -0.04 -0.13 -0.09 -0.05"   # worst width
L22 = " ".join(["0.12"] * 22)

lines = [
 # S0
 ("S0", "rows at one code stamp 1cee7ea83e4c28db; whole fit spines 693 of 809 kept, whole held 158 of 190; refit against the fitted prior, largest difference 2e-16"),
 ("S0", "rows at 2 code stamps, the commonest 1cee7ea83e4c28db on 801 of 809 kept fit studies; whole fit spines 693, whole held 158; refit against the prior 2e-16"),
 ("S0", "legend: e endplate, d endplate_depth, l endplate_lower, ld endplate_lower_depth, h h_post; ten pairs ed el eld eh dl dld dh lld lh ldh, the six plate pairs without h"),
 ("S0", "missing cells of the kept fit studies: e 1.2%, d 0.8%, l 1.1%, ld 0.9%, h 2.0%; most in C3-C7, 4.1%; z is per cell over the whole fit spines"),
 # S11 classes
 ("S11", "class 2.5 mm, 365 whole fit spines: autoPET 364, Leipzig 1; models Biograph128 300, Biograph 16 64; kernels I31f 200, B31f 164"),
 ("S11", "class at most 1.5 mm, 110 whole fit spines: autoPET 92, Leipzig 18; models SOMATOM Definition AS 60, Biograph128 50; kernels B31f 55, B10f 18"),
 ("S11", "class at most 1.5 mm, 67 whole fit spines: sites, models and kernels are read for enhance_pet alone"),
 ("S11", "one protocol class, so the by-class lines and the within-class reruns are the pooled ones and are not printed"),
 ("S11", "class 2.5 mm mean z by C3-C7 T1 T2-T12 L1-L4 L5: e +0.12 +0.10 -0.05 -0.08 -0.02, d -0.12 -0.10 -0.05 -0.08 -0.02, l +0.12 +0.10 -0.05 -0.08 -0.02"),
 ("S11", "class at most 1.5 mm mean z by C3-C7 T1 T2-T12 L1-L4 L5: ld -0.12 -0.10 -0.05 -0.08 -0.02, h -0.12 -0.10 -0.05 -0.08 -0.02"),
 ("S11", "h_post SD in mm over C3-C7 T2-T12 L1-L4 by class: at most 1.5 mm 1.6 1.5 1.9; 2.5 mm 1.9 1.8 2.2; 2.8 mm 2.1 2.0 2.4; 3 mm 2.0 1.9 2.3; 5 mm 2.6 2.5 2.9"),
 ("S11", "classes under 30 whole fit spines, left out of every by-class line: 2.8 mm 8"),
 # S12 anchors
 ("S12", "anchors e, mean then SD in mm, C3 to T6: 16.1 1.2, 16.5 1.3, 17.2 1.4, 18.6 1.6, 25.1 5.5, 40.2 9.1, 31.2 3.1, 29.0 2.8, 28.1 2.6, 28.5 2.7, 29.6 2.9"),
 ("S12", "anchors ld, mean then SD in mm, T7 to L5: 31.5 2.9, 32.0 3.0, 33.1 3.1, 34.0 3.2, 35.2 3.3, 36.6 3.4, 38.0 3.6, 39.2 3.8, 40.1 3.9, 62.2 13.0, 62.4 9.6"),
 # S1 same level
 ("S1", "same level el: C3-C7 0.21 T1 0.15 T2-T12 0.33 L1-L4 0.35 L5 0.30 all 0.30 ranks 0.31; drawn 0.30; misfit +0.004 null +0.001 sd 0.004 z +0.8"),
 ("S1", "same level ldh: C3-C7 -0.21 T1 -0.15 T2-T12 -0.33 L1-L4 -0.35 L5 -0.30 all -0.30 ranks -0.31; drawn -0.30; misfit -0.104 null +0.001 sd 0.004 z -26.3"),
 ("S1", "same level, the six plate pairs: raw 0.25 drawn 0.10 misfit " + JB),
 ("S1", "within class, 718 spines in 4 classes, same level ten pairs: " + PAIRS10W),
 ("S1", "within class, same level, the six plate pairs: raw 0.25 drawn 0.10 misfit " + J),
 ("S1", "autoPET 2.5 mm alone, 364 spines, same level ten pairs: " + PAIRS10W),
 ("S1", "autoPET 2.5 mm alone, same level, the six plate pairs: raw 0.25 drawn 0.10 misfit " + J),
 ("S1", "within-class and autoPET 2.5 mm reruns: not run, one protocol class"),
 # S2 adjacent, disc
 ("S2", "one level apart, same measure, ld: C3-C7 0.62 C7-T2 0.31 T2-T12 0.71 T12-L4 0.69 L4-L5 0.40"),
 ("S2", "one level apart in T2 to L4, same measure: e 0.52 d 0.55 l 0.50 ld 0.56 h 0.31; range of the five, misfit +0.250 null +0.012 sd 0.010 z +23.8"),
 ("S2", "across a disc in T2 to L4, widths: facing 0.24 far 0.12, facing minus far " + JB),
 ("S2", "facing minus far by disc group T2-T9 T9-T12 T12-L4: widths +0.100 +0.120 +0.150; depths +0.080 +0.090 +0.200"),
 ("S2", "facing minus far by class, widths over T2-L4 then T12-L4: at most 1.5 mm +0.05 +0.07; 2.5 mm +0.12 +0.15; 3 mm +0.08 +0.10; 5 mm +0.20 +0.22"),
 # S4 far apart
 ("S4", "far apart, C3-C7 with L1-L4, misfit by plate pair ed el eld dl dld lld: +0.020 +0.030 +0.010 +0.020 +0.030 +0.020; one sign"),
 ("S4", "far apart, C3-C7 with L1-L4, mean of the six plate pairs: raw 0.05 drawn 0.02 misfit " + JB),
 ("S4", "far apart, C3-C7 with L1-L4: the six plate pairs differ in sign, so no mean is taken"),
 ("S4", "far apart in T2 to L4, six or more levels, misfit by plate pair: -0.020 -0.030 -0.010 -0.020 -0.030 -0.020; mean " + J),
 ("S4", "within class, far apart, C3-C7 with L1-L4, misfit by plate pair: -0.020 -0.030 -0.010 -0.020 -0.030 -0.020; mean " + J),
 ("S4", "autoPET 2.5 mm alone, far apart, C3-C7 with L1-L4, by plate pair: -0.020 -0.030 -0.010 -0.020 -0.030 -0.020; mean " + J),
 # S5 refits
 ("S5", "refit C3..L5 unshrunk, ten pairs: " + PAIRS10W),
 ("S5", "refit T1..L5 on the same spines: " + PAIRS10W + "; width pair change -0.150 null +0.001 sd 0.005 z -30.2"),
 ("S5", "width pair change from C3..L5 to T1..L5: " + "-0.150 null +0.001 sd 0.005 z -30.2, boot se 0.020 z -7.6"),
 ("S5", "width pair change from C3..L5 to T1..L5 by class: at most 1.5 mm -0.100; 2.5 mm -0.120; 3 mm -0.200; 5 mm -0.250"),
 # S6 tails, ranks
 ("S6", "beyond 4 SD on robust z, median and MAD: e 0.30% d 0.25% l 0.28% ld 0.22% h 0.40%; most in C3-C7, 1.10%; a Gaussian gives 0.006%"),
 ("S6", "normal-scores refit C3..L5 unshrunk, ten pairs: " + PAIRS10W),
 ("S6", "normal scores minus Pearson, same level, six plate pairs: +0.030 -0.010 +0.020 +0.010 -0.020 +0.050; largest absolute 0.050 at lld"),
 # S13 canal
 ("S13", "canal test, r over spines of the plates' mean z with canal_ap's: all -0.10 of 690; at most 1.5 mm -0.05; 2.5 mm -0.12; 3 mm -0.15; 5 mm -0.30"),
 ("S13", "canal test, r over spines of the plates' mean z: with canal_ap's -0.10, with canal_w's -0.05, of 67 spines"),
 # S9 neck
 ("S9", "neck: foramina is the body cut at the foramina, fallback the cut at the canal's side walls; e and l pooled mean z; r within the branch; agree, widths within 1 mm"),
 ("S9", "neck C5, 2.5 mm: foramina 210 e -0.05 l +0.02 r 0.25 agree 4%; fallback 155 e +0.10 l -0.03 r 0.40 agree 18%"),
 ("S9", "neck C5, at most 1.5 mm: foramina 210 e -0.05 l +0.02 r -0.25 agree 4.5%; fallback 155 e -0.10 l -0.03 r -0.40 agree 18.5%"),
 ("S9", "neck widths covariance, within then between, C3 to C7, 2.5 mm: 0.20 +0.05, 0.18 +0.02, 0.22 +0.01, 0.25 -0.02, 0.30 +0.10; pooled r 0.25 0.20 0.23 0.23 0.40"),
 ("S9", "neck widths covariance, within then between, C3 to C7, at most 1.5 mm: -0.20 -0.05, -0.18 -0.02, -0.22 -0.01, -0.25 -0.02, -0.30 -0.10; pooled r -0.25 -0.20 -0.23 -0.23 -0.40"),
 ("S9", "neck widths centred within level and branch, refit width pair: all 0.301 to 0.250; at most 1.5 mm 0.310 to 0.270; 2.5 mm 0.300 to 0.240; 3 mm 0.29 to 0.25"),
 # S14 plate ratios
 ("S14", "SD of log of e over l by level C3 to L5: " + L22),
 ("S14", "plate ratios, median SD of the log ratio: depths C3-C7 0.060 and L1-L4 0.055, NHANES II 0.030 to 0.036 and 0.017 to 0.019; widths T2-L4 0.070; boot se 0.003 0.003 0.004"),
 ("S14", "spines holding a vertebra over 20% off its level's median ratio, over C3..L5: widths 45.1% depths 30.2% either 55.3%; over T2..L4: 30.1% 20.4% 38.2%"),
 # S15 generator
 ("S15", "generator check: 5000 typical columns from draw_columns with the fitted prior, the data's cell means and SDs, size SD 0.07 and noise 1.0 mm, as run_naming draws"),
 ("S15", "generator check, same level el, drawn then data: C3-C7 0.51 0.21, T2-T12 0.52 0.33, L1-L4 0.53 0.35, all 0.51 0.30, data boot se 0.015"),
 ("S15", "generator check, one to five levels apart, same measure, drawn 0.58 0.55 0.53 0.51 0.51, data 0.49 0.43 0.39 0.37 0.35"),
 ("S15", "generator check, spines with a vertebra over 20% off, drawn then data: widths 60.2% 45.1%, depths 40.3% 30.2%, either 70.4% 55.3%"),
 ("S15", "generator check, share of a cell's variance from the size factor: median 0.31, range 0.10 to 0.45; from the 1.0 mm noise: median 0.05"),
 ("S15", "generator check: not run, schwingcheck columns is not in this copy of the code"),
 # S8 repeat units
 ("S8", "repeat units in the fit part: 47 of 113 studies (34 of 2, 9 of 3, 2 of 4, 2 of 5); 37 all autoPET 2.5 mm, 8 of mixed classes, 2 other"),
 ("S8", "repeat units were matched on vertebral volume, so every ICC below is an upper bound on reliability within one protocol, not of the whole population"),
 ("S8", "ICC1 ld by C3-C7 T1 T2-T12 L1-L4 L5: 0.85 0.80 0.90 0.92 0.88; T2-L4 0.91, unit bootstrap 0.86 to 0.94"),
 ("S8", "within-unit SD in mm, C3-C7 then T2-L4: e 1.5 1.2, d 0.9 0.8, l 1.4 1.1, ld 0.9 0.8, h 1.3 1.0"),
 ("S8", "ICC1 of size-free log ratios over T2-L4: e over l 0.40 (0.25 to 0.55), d over ld 0.35 (0.20 to 0.50), h over d 0.30 (0.15 to 0.45)"),
 ("S8", "within-unit error correlation, ten pairs over every level: " + PAIRS10W + "; boot se el 0.05 dld 0.06"),
 ("S8", "autoPET 2.5 mm alone, 37 units, same level over T2-L4, raw then corrected for within-unit error: el 0.31 0.45, dld 0.47 0.60, ed 0.17 0.22, lld 0.13 0.16"),
 ("S8", "repeat units: not run, no repeat unit of this population is in the fit part"),
 # end
 ("end", "done in 412 s, 200 draws for each null and each unit bootstrap"),
 ("fault", "fault at S9, an error of the kind ZeroDivisionError"),
 ("notrun", "not run, the C3..L5 fit took fewer than 30 whole spines"),
]

BAD = re.compile(r"/|[0-9]{5}|(?i:patient|institution|operators|physician|accession)|:[^ ]")
for sec, body in lines:
    for pop, head in HEADS.items():
        line = head + body
        n = len(line) + 2
        bad = BAD.search(line)
        hexrun = [m.group(0) for m in re.finditer(r"[0-9a-fA-F]{8,}", line) if m.group(0) != "1cee7ea83e4c28db"]
        flag = ("  TOO LONG" if n > 196 else "") + ("  SHAPE %r" % bad.group(0) if bad else "") + ("  HEX %r" % hexrun if hexrun else "")
        if pop == "enhance_pet":
            print("%-6s %3d %3d%s | %s" % (sec, len(HEADS['enhance_pet'] + body) + 2, len(HEADS['totalsegmentator'] + body) + 2, flag, body[:90]))
        elif flag:
            print("       totalsegmentator%s" % flag)
