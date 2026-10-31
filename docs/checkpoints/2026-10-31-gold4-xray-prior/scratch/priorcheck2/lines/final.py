"""The check's line formats filled with worst-width placeholder values, measured against the rules."""
import re, subprocess, sys

E, T = "enhance_pet C3..L5 check: ", "totalsegmentator C3..L5 check: "
J = "+0.150 null +0.012 sd 0.005 z +27.6"
JB = J + ", boot se 0.015 z +9.2"
P10 = " ".join(["-0.32"] * 10)
P6 = " ".join(["-0.030"] * 6)
L22 = " ".join(["0.12"] * 22)
R5 = " ".join(["-0.12"] * 5)
CLS4 = "at most 1.5 mm %s; 2.5 mm %s; 3 mm %s; 5 mm %s"
rows = [
 ("S0", "rows at one code stamp 1cee7ea83e4c28db; whole fit spines 693 of 809 kept, whole held 158 of 190; refit against the fitted prior, largest difference 2e-16"),
 ("S0", "rows at 2 code stamps, the commonest 1cee7ea83e4c28db on 801 of 809 kept fit studies; whole fit spines 693, whole held 158; refit against the prior 2e-16"),
 ("S0", "legend: e endplate, d endplate_depth, l endplate_lower, ld endplate_lower_depth, h h_post; pairs ed el eld eh dl dld dh lld lh ldh; plate pairs leave out h"),
 ("S0", "missing cells of the kept fit studies: e 12.2%, d 10.8%, l 11.1%, ld 10.9%, h 12.0%; most in C3-C7, 14.1%; z is per cell over the whole fit spines"),
 ("S11", "class at most 1.5 mm, 110 whole fit spines: autoPET 92, Leipzig 18, Careggi 1; models SOMATOM Definition AS 60, GEMINI TF TOF 16 50; kernels B31f 55, B10f 18"),
 ("S11", "class at most 1.5 mm, 67 whole fit spines: sites, models and kernels are read for enhance_pet alone"),
 ("S11", "one protocol class, so the by-class lines and the within-class reruns are the pooled ones and are not printed"),
 ("S11", "class at most 1.5 mm mean z by C3-C7 T1 T2-T12 L1-L4 L5: e %s, d %s, l %s" % (R5, R5, R5)),
 ("S11", "class at most 1.5 mm mean z by C3-C7 T1 T2-T12 L1-L4 L5: ld %s, h %s" % (R5, R5)),
 ("S11", "h_post SD in mm over C3-C7 T2-T12 L1-L4 by class: " + "at most 1.5 mm 1.6 1.5 1.9; 2.5 mm 1.9 1.8 2.2; 2.8 mm 2.1 2.0 2.4; 3 mm 2.0 1.9 2.3; 5 mm 2.6 2.5 2.9"),
 ("S11", "classes under 30 whole fit spines, left out of every by-class line: 2.8 mm 8; no spacing row 3"),
 ("S12", "anchors e, mean then SD in mm, C3 to T6: " + ", ".join(["62.2 13.0"] * 11)),
 ("S12", "anchors ld, mean then SD in mm, T7 to L5: " + ", ".join(["62.2 13.0"] * 11)),
 ("S1", "same level ldh: C3-C7 -0.21 T1 -0.15 T2-T12 -0.33 L1-L4 -0.35 L5 -0.30 all -0.30 ranks -0.31; drawn -0.30; misfit " + J),
 ("S1", "same level, the six plate pairs: raw -0.25 drawn -0.10 misfit " + JB),
 ("S1", "within class, 718 spines in 4 classes, same level ten pairs: " + P10),
 ("S1", "within class, same level, the six plate pairs: raw -0.25 drawn -0.10 misfit " + JB),
 ("S1", "autoPET 2.5 mm alone, 364 spines, same level ten pairs: " + P10),
 ("S1", "autoPET 2.5 mm alone, same level, the six plate pairs: raw -0.25 drawn -0.10 misfit " + JB),
 ("S1", "reruns within class and in autoPET 2.5 mm alone, of the same-level and far-apart lines: not run, one protocol class"),
 ("S2", "one level apart, same measure, ld: C3-C7 -0.62 C7-T2 -0.31 T2-T12 -0.71 T12-L4 -0.69 L4-L5 -0.40"),
 ("S2", "one level apart in T2 to L4, same measure: e 0.52 d 0.55 l 0.50 ld 0.56 h 0.31; range of the five, misfit " + J),
 ("S2", "across a disc in T2 to L4, depths: facing -0.24 far -0.12, facing minus far " + JB),
 ("S2", "facing minus far by disc group T2-T9 T9-T12 T12-L4: widths -0.100 -0.120 -0.150; depths -0.080 -0.090 -0.200"),
 ("S2", "facing minus far by class, depths over T2-L4 then T12-L4: " + CLS4 % ("-0.05 -0.07", "-0.12 -0.15", "-0.08 -0.10", "-0.20 -0.22")),
 ("S4", "far apart, C3-C7 with L1-L4, misfit by plate pair ed el eld dl dld lld: " + P6 + "; signs differ"),
 ("S4", "far apart, C3-C7 with L1-L4, mean of the six plate pairs: raw -0.05 drawn -0.02 misfit " + JB),
 ("S4", "far apart, C3-C7 with L1-L4: the six plate pairs differ in sign, so no mean is taken"),
 ("S4", "far apart in T2 to L4, six or more levels, misfit by plate pair: " + P6 + "; mean " + J),
 ("S4", "within class, far apart, C3-C7 with L1-L4, misfit by plate pair: " + P6 + "; one sign"),
 ("S4", "within class, far apart, C3-C7 with L1-L4, mean of the six plate pairs: misfit " + JB),
 ("S4", "autoPET 2.5 mm alone, far apart, C3-C7 with L1-L4, misfit by plate pair: " + P6 + "; signs differ"),
 ("S4", "autoPET 2.5 mm alone, far apart, C3-C7 with L1-L4, mean of the six plate pairs: misfit " + JB),
 ("S5", "refit C3..L5 unshrunk, ten pairs: " + P10),
 ("S5", "refit T1..L5 on the same spines: " + P10 + "; width pair change " + J),
 ("S5", "width pair change from C3..L5 to T1..L5: " + JB),
 ("S5", "width pair change from C3..L5 to T1..L5 by class: " + CLS4 % ("-0.100", "-0.120", "-0.200", "-0.250")),
 ("S6", "beyond 4 SD on robust z, median and MAD: e 10.30% d 10.25% l 10.28% ld 10.22% h 10.40%; most in C3-C7, 11.10%; a Gaussian gives 0.006%"),
 ("S6", "normal-scores refit C3..L5 unshrunk, ten pairs: " + P10),
 ("S6", "normal scores minus Pearson, same level, six plate pairs: " + P6 + "; largest absolute 0.050 at lld"),
 ("S13", "canal test, r over spines of the plates mean z with canal_ap mean z: all -0.10 of 690; " + CLS4 % ("-0.05", "-0.12", "-0.15", "-0.30")),
 ("S13", "canal test, r over spines of the plates mean z: with canal_ap -0.10, with canal_w -0.05, of 67 spines"),
 ("S9", "neck: foramina is the body cut at the foramina, fallback the cut at the canal side walls; e and l pooled mean z; r within a branch; agree, widths within 1 mm"),
 ("S9", "neck C5, at most 1.5 mm: pooled r -0.25; foramina 210 e -0.05 l -0.02 r -0.25 agree 14%; fallback 155 e -0.10 l -0.03 r -0.40 agree 18%"),
 ("S9", "neck widths covariance in z, within then between, C3 to C7, at most 1.5 mm: " + ", ".join(["-0.20 -0.05"] * 5)),
 ("S9", "neck widths centred within level and branch, refit width pair: all 0.301 to 0.250; " + CLS4 % ("0.310 to 0.270", "0.300 to 0.240", "0.290 to 0.250", "0.280 to 0.230")),
 ("S14", "SD of log of d over ld by level C3 to L5: " + L22),
 ("S14", "plate ratios, median SD of log ratio: depths C3-C7 0.060 L1-L4 0.055, NHANES II 0.030 to 0.036 and 0.017 to 0.019; widths T2-L4 0.070; boot se 0.003 0.003 0.004"),
 ("S14", "spines holding a vertebra over 20% off its level median ratio, C3..L5: widths 45.1% depths 30.2% either 55.3%; T2..L4: 30.1% 20.4% 38.2%"),
 ("S15", "generator check: 5000 typical columns from draw_columns with the fitted prior, the data cell means and SDs, size SD 0.07 and noise 1.0 mm, as run_naming draws"),
 ("S15", "generator check, same level dld, drawn then data: C3-C7 -0.51 -0.21, T2-T12 -0.52 -0.33, L1-L4 -0.53 -0.35, all -0.51 -0.30, data boot se 0.015"),
 ("S15", "generator check, one to five levels apart, same measure, drawn 0.58 0.55 0.53 0.51 0.51, data 0.49 0.43 0.39 0.37 0.35"),
 ("S15", "generator check, spines with a vertebra over 20% off, drawn then data: widths 60.2% 45.1%, depths 40.3% 30.2%, either 70.4% 55.3%"),
 ("S15", "generator check, a cell variance: size factor share median 0.31, range 0.10 to 0.45; noise share median 0.05; drawn SD over data SD median 1.21"),
 ("S8", "repeat units in the fit part: 47 of 113 studies (34 of 2, 9 of 3, 2 of 4, 2 of 5); 37 all autoPET 2.5 mm, 8 of mixed classes, 2 other"),
 ("S8", "repeat units were matched on vertebral volume, so every ICC below is an upper bound on reliability within one protocol, not of the whole population"),
 ("S8", "ICC1 ld by C3-C7 T1 T2-T12 L1-L4 L5: -0.85 -0.80 -0.90 -0.92 -0.88; T2-L4 -0.91, unit bootstrap -0.86 to -0.94"),
 ("S8", "within-unit SD in mm, C3-C7 then T2-L4: e 11.5 11.2, d 10.9 10.8, l 11.4 11.1, ld 10.9 10.8, h 11.3 11.0"),
 ("S8", "ICC1 of size-free log ratios over T2-L4: e over l -0.40 (-0.25 to -0.55), d over ld -0.35 (-0.20 to -0.50), h over d -0.30 (-0.15 to -0.45)"),
 ("S8", "within-unit error correlation, ten pairs over every level: " + P10 + "; boot se el 0.05 dld 0.06"),
 ("S8", "autoPET 2.5 mm alone, 37 units, same level over T2-L4, raw then corrected for within-unit error: el 0.31 0.45, dld 0.47 over 1, ed 0.17 0.22, lld 0.13 0.16"),
 ("S8", "repeat units: not run, no repeat unit of this population is in the fit part"),
 ("end", "done in 1412 s, 200 draws for each null and each unit bootstrap"),
 ("fault", "fault at S15, an error of the kind ModuleNotFoundError"),
 ("notrun", "not run, the C3..L5 fit took fewer than 30 whole spines"),
]
BAD = re.compile(r"/|[0-9]{5}|(?i:patient|institution|operators|physician|accession|basic |token)|:[^ ]|'")
grid = "/home/claude/SchwingNet/grid"
allok = True
out = []
for sec, body in rows:
    le, lt = len(E + body) + 2, len(T + body) + 2
    flags = []
    if lt > 196: flags.append("LONG")
    m = BAD.search(T + body)
    if m: flags.append("SHAPE %r" % m.group(0))
    hexr = [h for h in re.findall(r"[0-9a-fA-F]{8,}", body) if h != "1cee7ea83e4c28db"]
    if hexr: flags.append("HEX %r" % hexr)
    out.append(("- " + T + body))
    allok &= not flags
    print("%-6s %3d %3d %s| %s" % (sec, le, lt, " ".join(flags), body))
# through the gate's own filters
text = "\n".join(out) + "\n"
p = subprocess.run("awk -v data=/rs/x -v runs=/rs/r -v models=/rs/m -v repo=/home/x -f %s/shape-words.awk -f %s/report-shapes.awk | sed -r -f %s/redact.sed" % (grid, grid, grid),
                   shell=True, input=text, capture_output=True, text=True)
same = p.stdout == text
print("filters leave every line as it is:", same, p.stderr[:200])
if not same:
    for a, b in zip(text.splitlines(), p.stdout.splitlines()):
        if a != b: print("CHANGED:", b)
print("all within the rules:", allok)
