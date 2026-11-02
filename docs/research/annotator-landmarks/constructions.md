# The annotators' landmarks as the CT engine's constructions, checked against the points a person placed

Source: the owner's local Claude Code session of the night of 1 November 2026, on his words that night: "the bare minimum my landmark net should also be able to place landmarks annotators have found useful such as the ones deepfluoro placed, the corners a ton of xray groups have placed, etc; it should somehow find where those points correspond to the 3d ct scans and propagate them through and use them if possible for bayesian measurements, and even better if they correlate with known anatomical papers like panjabi". Confidential with the rest of this repository.

## What was built

tools/annotator_landmarks.py places, on a labelled CT, the points readers mark on films, each as a named 3-D point in world millimetres in LPS (x to the patient's left, y posterior, z superior, the frame of DeepFluoro's vol-landmarks and of the QA loop's pairs), each from one construction of bordercall's morphometry engine (the pinned copy under grid/bordercall/, 9c85de1), by the owner's rule of 29 October that corners and landmarks come from the CT engine's constructions, projected, and never from a 2-D fit. The tool's CONSTRUCTIONS table says each in words; in short, as the tool stands after the check (the four points read on a shape were first read otherwise, as the section after the run says):

| construction | what it is | QA loop landmark it stands for |
|---|---|---|
| anterior_superior, anterior_inferior | each end plate's front end on the midline: column.wall_corner's construction mirrored to the front, in the plate's own frame | endplate_depth.anterior, endplate_lower_depth.anterior |
| posterior_superior, posterior_inferior | each end plate's back end on the midline, where the posterior wall meets it (column.wall_corner, the corners the slip is read between) | endplate_depth.posterior, endplate_lower_depth.posterior (and near h_post's two ends) |
| centre_superior, centre_inferior | each end plate's centre on its plane (column.plate_centre): the middle points of the six-point morphometry of Genant (1993) and of Black and McCloskey | none |
| superior_right, superior_left, inferior_right, inferior_left | each end plate's lateral ends, the corners an anteroposterior reader marks: the ends of the widest row of the plate's own layer across its front half, as bordercall's plates.py reads the plate's width (commit 69cae89, repeated in the tool since the pinned copy predates it) | endplate.right/left, endplate_lower.right/left |
| hip_centre | the acetabulum's centre (pelvis.socket_centre: a vote of the hip bone's surface normals over radii of 18 to 32 mm, refined by a sphere) | none |
| femoral_head | the femoral head's centre, read again on the femur: the same vote with the normals turned inward over the femur's proximal 100 mm, refined by a sphere through the head | none |
| crest_top | the iliac crest's highest point along the scanner's long axis (pelvis.crest_top) | none |
| s1_centre, s1_anterior, s1_posterior | the S1 end plate under the lowest lumbar body (pelvis.s1_plate), its front end on the midline, the sacral promontory, and its back end at the sacral canal: the plate's layer walked from its centre forward and backward until a gap of more than 2 mm; flagged where the plate lies more than 20 mm below the lowest lumbar plate or 10 mm beside the midline (s1_against) | none (the QA loop's sacral anchor is tools/qaloop_samples.py's, which this does not change) |
| asis | the anterior superior iliac spine: where the anterior pelvic plane (the plane resting on both ilia above the hip axis and on the pubis in front, turned until every point lies behind it) touches each ilium | none |
| symphysis_superior, symphysis_inferior | each pubis's face at the symphysis (its bone within 6 mm of the other pubis beyond their narrowest gap); its upper end along the joint's own long axis, its lowest point along the scanner's long axis (DIRECTIONS) | none |
| obturator_inferior, obturator_medial | the obturator foramen as the largest hole in the silhouette of the hip bone below the acetabulum, over views within 40 degrees of the anterior pelvic plane's normal; its outline in 3-D, the middle of the bone round the hole's edge in the view that shows it largest; the outline's extreme toward the ischium (back and down with the plane upright, the direction DeepFluoro's annotators' points lie in) and toward the midline (DIRECTIONS) | none |
| sciatic_notch | the greater sciatic notch's deepest point: the hip bone seen along the hip axis, the point of its posterior concavity furthest inside its convex hull, and the bone there | none |

Where a definition was ambiguous, the reading chosen and why:

- Grupp et al. (2020, IJCARS 15:759-769, "Automatic annotation of hip anatomy in fluoroscopy for robust and efficient 2D/3D registration", arXiv 1911.07042) name the fourteen points and say they were "manually digitized" in the CT; the paper gives no definition of any of them and no spread between annotators (read on PMC7263976, 1 November 2026: its heatmaps' spread was "subjectively chosen to approximate the variance found in manual landmark annotation", with no number). So each construction above takes the textbook reading of the name: the ASIS as the iliac spine the anterior pelvic plane rests on (the plane of Lewinnek, which a navigation system registers by palpating the same spines); the notch's apex as its deepest point; the foramen's inferior and medial points as its rim's extremes downward and toward the midline; the symphysis's points as each pubis's own end of the joint, since the release gives a left and a right point for each. For the foramen and the symphysis these readings were changed after the run, as the section after it says.
- Before the run, the foramen's extremes were taken in one view, the one along the foramen, because the rim is a band of bone 10 to 20 mm thick along that view and its 3-D lowest voxel is wherever the band's edge happens to dip; the point was the band's mean at the extreme, the middle of the bone a person clicks on. The run showed that the oblique view's "down" is not the annotators' (below); the band's mean is kept, now as the foramen's outline in 3-D.
- The femoral head's centre is read twice: once as the acetabulum's centre, which the engine already reads and which a congruent hip makes the head's centre too, the joint space lying between two spheres about one centre, and once on the femur's own ball where a femur mask exists; the check shows how far the two lie apart on these specimens.

## The check, and its bars, written before the run

DeepFluoro's release holds, for each of its six cadaveric specimens, fourteen points a person placed in the CT (vol-landmarks: the femoral head centres FH, the greater sciatic notches GSN, the obturator foramen's inferior and medial points IOF and MOF, the pubic symphysis's superior and inferior points SPS and IPS, and the anterior superior iliac spines ASIS, each left and right), in the volume's world frame, which is ct.nii.gz's world in LPS. `tools/annotator_landmarks.py persons` reads them, and nothing else of the file, for the five specimens 17-1882, 17-1905, 18-0725, 18-2799 and 18-2800; 18-1109, the QA loop's held-out test specimen, is never read. `check` builds every construction twice per specimen, on TotalSegmentator's masks (ts/ and ts_femur/) and on the dataset authors' own 3-D labels (vol_seg.nii.gz: hemipelves, the lumbar vertebrae as one class split into its connected pieces and each named by the TotalSegmentator level that holds 70 per cent of it, the sacrum, the femurs), and reports per landmark the 3-D distance between each construction and the person's point (median, maximum and n), the distance between the two sources' constructions, and how far each person's point lies from the authors' bone labels, which shows whether the two frames are one.

The bars, stated before the run:

- A construction agrees with the person where its median distance over the specimens is at most 5 mm. Grupp et al. give no spread between annotators to set this against (above), so the bar is the one set for this check, about the size of the error their own network made on the detector plane over these specimens (5.0 mm mean over all fourteen landmarks, their Table 1); every landmark is reported whatever it shows.
- The frame is one where every person's point other than the femoral head centres lies within 5 mm of the authors' bone labels (the head centres lie inside the femur, at no distance); if not, no distance below means anything.
- The femoral head centre agrees on both readings, the acetabulum's and the ball's, or the difference between the two is reported as what it is.
- Nothing here is checked against a person for the vertebral and sacral points: DeepFluoro's person placed none. Those are reported as the agreement between the two sources (TotalSegmentator against the authors' labels) and, for the promontory, as its place against L5's lower plate, the check the QA loop's sacral anchor failed (docs/research/qa-loop-external/README.md): the promontory should stand in front of L5's lower plate centre by about half the plate's depth, not 4 mm.

## What the check found

Grid jobs of 2 November 2026 (UTC), one CPU job each, run from a throwaway copy under qadiag/annotator-constructions: the run the bars were set for is job 40940269, on the tool of commit 18110ff4 (its sha256 on the grid, d4d3c476..., was the commit's); the later readings are jobs 40940314, 40940356 and 40940426, the last on the tool as this pull request leaves it. The person's points were read from the release file (2,541,608,861 bytes) for the five specimens alone; 18-1109 was never opened. Every number below is in those jobs' check.json and table.md.

The frame is one. Of the 60 person's points other than the femoral head centres, the median lies 0.69 mm from the authors' bone labels and 59 lie within 3.4 mm; one, 18-0725's right superior symphysis point, lies 5.85 mm away, past the 5 mm stated, so the bar as written fails on one point in sixty and every distance below stands with that said. The femoral head centres lie within 0.69 mm of the femur labels' voxels.

### The run the bars were set for (job 40940269)

Median / maximum / n, mm, both sides pooled (five specimens, two sides):

| landmark | construction | TotalSegmentator | authors' labels | between the two labelings | at most 5 mm? |
|---|---|---|---|---|---|
| FH | hip_centre (the acetabulum) | 2.1 / 6.3 / 10 | 3.7 / 8.3 / 10 | 4.0 / 5.6 / 10 | yes |
| FH | femoral_head (the femur's ball) | 2.9 / 5.4 / 10 | 2.6 / 5.8 / 10 | 0.5 / 0.7 / 10 | yes |
| ASIS | asis | 4.8 / 9.0 / 10 | 4.6 / 8.7 / 10 | 1.3 / 3.0 / 10 | yes |
| GSN | sciatic_notch | 4.3 / 10.2 / 10 | 4.1 / 8.8 / 10 | 1.6 / 3.0 / 10 | yes |
| MOF | obturator_medial | 3.2 / 10.4 / 10 | 4.4 / 9.2 / 10 | 1.7 / 8.6 / 10 | yes |
| SPS | symphysis_superior | 4.1 / 10.5 / 10 | 4.8 / 8.5 / 10 | 1.9 / 3.6 / 10 | yes |
| IPS | symphysis_inferior | 14.0 / 24.6 / 10 | 13.9 / 24.1 / 10 | 1.0 / 3.3 / 10 | no |
| IOF | obturator_inferior | 26.2 / 35.0 / 10 | 20.5 / 34.6 / 10 | 1.2 / 12.5 / 10 | no |

So five of the seven kinds agreed with the person on both labelings as first defined, the femoral head on both its readings, and the obturator foramen's inferior point and the symphysis's inferior point did not. Side by side, beyond the two kinds that failed, two single-side medians passed 5 mm where the pooled one did not: the left ASIS (6.0 on both labelings) and the right SPS on the authors' labels (6.1). The femoral head's two readings lie a median 1.3 mm apart on TotalSegmentator (at most 2.2) and 5.5 mm on the authors' labels (at most 6.9), where the socket's reading is the one further from the person; the ball's reading is the stabler, 0.5 mm between the two labelings.

### After the run: the four points read on a shape (exploratory, in sample)

What follows was done after the run above was seen, on the same five specimens, so it is exploratory. The foramen's two points and the symphysis's two are each one shape's extreme along one direction; the direction is what the release's names leave open, and four readings were measured (medians, TotalSegmentator / authors' labels, mm, ten points each):

| point | the first reading (job 40940269) | the scanner's long axis (job 40940314) | the name's words with the anterior pelvic plane upright (job 40940356) | learned from the other four specimens, each left out in turn (jobs 40940356, 40940426) |
|---|---|---|---|---|
| IOF | 26.2 / 20.5 (down in the oblique view) | 24.6 / 24.4 | 11.1 / 9.5 | 2.0 / 2.7 |
| MOF | 3.2 / 4.4 (medial in the oblique view) | 4.6 / 4.0 | 4.6 / 4.0 | 5.6 / 4.8 |
| SPS | 4.1 / 4.8 (up the joint's own axis) | 14.3 / 16.1 | 12.1 / 11.6 | 4.5 / 3.7 (in the joint's frame) |
| IPS | 14.0 / 13.9 (down the joint's own axis) | 3.2 / 4.8 | 8.4 / 9.3 | 11.4 / 11.8 (in the scanner's frame) |

What they show, in anatomical words:

- The annotators' "inferior obturator foramen" is not the foramen's lowest point in any frame tried: it is its back lower end, toward the ischium. From the foramen's centre, with the anterior pelvic plane upright, the person's points lie along (0.23 lateral, 0.83 posterior, 0.51 inferior) on both labelings, each within a median 8.5 (TotalSegmentator) and 9.3 degrees (authors') of that line, and the outline's extreme along it, learned from four specimens and placed on the fifth, lies a median 2.0 and 2.7 mm from the person's point (at most 5.5 and 6.2). The learning works because the foramen is a closed ring whose centre does not move with how much of it a label holds.
- The annotators' "inferior pubic symphysis" is the joint's lowest point along the scanner's long axis, the slice where a person scrolling down sees the joint end; along the joint's own axis the faces run on 7 to 17 mm further back (debug job 40940285, two specimens). The learned direction fails here (11.4 mm) because the face's centre moves with how far back the faces run.
- The "superior pubic symphysis" is the joint's upper end along its own axis, the first reading; the faces' highest point in either frame lies a median 12 to 16 mm from the person's.

The tool now takes, in its table DIRECTIONS: the learned direction for IOF, whose fair error is the leave-one-out figure; the name's words for MOF; the joint's axis for SPS; the scanner's axis for IPS. The SPS and IPS readings were chosen among readings measured on the same ten points, so their figures below are optimistic; only the first run's figures and IOF's leave-one-out figure are fair.

### What the tool places now (job 40940426)

| landmark | construction | TotalSegmentator | authors' labels | between the two labelings |
|---|---|---|---|---|
| FH-l | hip_centre | 1.7 / 6.3 / 5 | 3.4 / 4.5 / 5 | 3.9 / 5.6 / 5 |
| FH-r | hip_centre | 2.3 / 5.1 / 5 | 4.6 / 8.3 / 5 | 4.7 / 5.5 / 5 |
| FH-l | femoral_head | 2.7 / 5.4 / 5 | 2.5 / 5.8 / 5 | 0.5 / 0.6 / 5 |
| FH-r | femoral_head | 3.1 / 4.5 / 5 | 3.1 / 5.0 / 5 | 0.6 / 0.7 / 5 |
| ASIS-l | asis | 6.0 / 9.0 / 5 | 6.0 / 8.7 / 5 | 0.6 / 3.0 / 5 |
| ASIS-r | asis | 4.5 / 8.6 / 5 | 3.9 / 6.4 / 5 | 1.4 / 2.3 / 5 |
| GSN-l | sciatic_notch | 4.3 / 10.2 / 5 | 4.4 / 8.8 / 5 | 1.3 / 1.8 / 5 |
| GSN-r | sciatic_notch | 4.4 / 8.1 / 5 | 3.5 / 8.3 / 5 | 1.6 / 3.0 / 5 |
| IOF-l | obturator_inferior | 4.6 / 5.5 / 5 | 4.1 / 6.2 / 5 | 1.0 / 2.2 / 5 |
| IOF-r | obturator_inferior | 2.0 / 5.5 / 5 | 1.9 / 5.9 / 5 | 0.8 / 1.8 / 5 |
| MOF-l | obturator_medial | 5.1 / 9.2 / 5 | 5.0 / 8.0 / 5 | 1.4 / 2.9 / 5 |
| MOF-r | obturator_medial | 4.2 / 5.4 / 5 | 3.2 / 5.4 / 5 | 0.9 / 1.4 / 5 |
| SPS-l | symphysis_superior | 4.1 / 6.5 / 5 | 4.6 / 5.9 / 5 | 1.8 / 1.9 / 5 |
| SPS-r | symphysis_superior | 4.2 / 10.5 / 5 | 6.3 / 8.6 / 5 | 2.1 / 3.6 / 5 |
| IPS-l | symphysis_inferior | 2.6 / 7.2 / 5 | 4.3 / 9.8 / 5 | 2.8 / 4.2 / 5 |
| IPS-r | symphysis_inferior | 3.4 / 13.7 / 5 | 5.4 / 8.9 / 5 | 2.4 / 5.6 / 5 |
| all fourteen, both sides pooled by kind | | FH 2.1 (socket), 2.9 (ball); ASIS 4.8; GSN 4.3; IOF 2.0; MOF 4.6; SPS 4.1; IPS 3.2 | FH 3.7, 2.6; ASIS 4.6; GSN 4.1; IOF 2.3; MOF 4.0; SPS 4.7; IPS 4.8 | |

Every kind's pooled median is at or under 5 mm on both labelings; five single-side medians are over it (the left ASIS on both, the left MOF on TotalSegmentator by 0.1 mm, the right SPS and IPS on the authors' labels), and the single-side maxima run from 4.5 to 13.7 mm on TotalSegmentator, so one specimen in five can still miss by a centimetre. The two labelings place the same construction a median 0.5 to 2.8 mm apart for every construction but the socket's (3.9 and 4.7 mm), mostly less than either lies from the person, so what is left is mostly the definitions' and the person's, not the masks'.

The picture, constructions.png beside this note: 17-1882 and 17-1905, the CT's mean along its anterior-posterior axis (bone's attenuation only), the patient's right on the left as on an anteroposterior film, the person's points as green rings, the constructions on TotalSegmentator's masks as red crosses and on the authors' labels as blue ones, and the vertebrae's corners and plate centres on TotalSegmentator as orange dots.

### The vertebrae and the S1 plate

- TotalSegmentator's labels gave the engine L4 and L5 (17-1882), L5 (17-1905), L4 (18-0725) and L2 to L5 (18-2799, 18-2800), 112 vertebral points; the levels above were cut by the field or closed no canal ring. The authors' lumbar class is one joined piece in three specimens, so no vertebra was read on it there; on 17-1905 its piece named L5 put the midline points 0.5 to 2.4 mm from TotalSegmentator's and the plates' lateral ends 1.1 to 7.1 mm away; on 18-0725 the piece the 70 per cent rule named L4 is not TotalSegmentator's L4 (its points lie 17 to 47 mm away), a failure of that naming rule. DeepFluoro's person placed no vertebral point, so the vertebral constructions are checked here only on the synthetic box of tests/test_annotator_landmarks.py (every corner within 0.8 mm) and by the two labelings against each other.
- The S1 plate could not be checked. On every specimen where the engine read one, its centre lies 26 to 33 mm below the lowest lumbar body's lower plate or 17 to 40 mm beside the midline, where no lumbosacral disc puts it, and the tool flags it (s1_against) and leaves it off the picture. The debug job 40940285 traced it to the labels: on 17-1882 TotalSegmentator's sacrum reaches up to L5's lower plate at the midline with no disc between them, and the engine, which reads the sacrum only below L5's lowest point, found its plate 32 mm lower; on 18-2799 the label holds no sacrum within 3 mm of the midline under L5's body until about 100 mm below its lower plate, and the plate was read on the ala. DeepFluoro's two level labellers disagree at the sacrum too (tools/realx_pairs.py). So the promontory's place against L5, the check the QA loop's sacral anchor failed, waits for CTs whose sacrum label is sound, such as the gold tier's ENHANCE.PET masks the engine's pelvis was built on.

## What follows

- The pelvic points carry DeepFluoro's own names, so a landmark network trained on their projections can be scored against the release's shipped 2-D landmarks on every frame, and the vertebral corners carry the QA loop's names (the table above), so the two sets join one target list.
- The fair errors to quote are the first run's and IOF's leave-one-out; the SPS and IPS readings the table takes should be checked on a set they were not chosen on, such as a second annotator's points or another release with the same names, before they are called settled.
- No change was made to the pinned engine; the readings of the plates' lateral ends repeat bordercall's plates.py (69cae89), and the pin should move to it when the vendored copy is next brought up.
