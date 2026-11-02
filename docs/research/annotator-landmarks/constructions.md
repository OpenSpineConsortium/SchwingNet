# The annotators' landmarks as the CT engine's constructions, checked against the points a person placed

Source: the owner's local Claude Code session of the night of 1 November 2026, on his words that night: "the bare minimum my landmark net should also be able to place landmarks annotators have found useful such as the ones deepfluoro placed, the corners a ton of xray groups have placed, etc; it should somehow find where those points correspond to the 3d ct scans and propagate them through and use them if possible for bayesian measurements, and even better if they correlate with known anatomical papers like panjabi". Confidential with the rest of this repository.

## What was built

tools/annotator_landmarks.py places, on a labelled CT, the points readers mark on films, each as a named 3-D point in world millimetres in LPS (x to the patient's left, y posterior, z superior, the frame of DeepFluoro's vol-landmarks and of the QA loop's pairs), each from one construction of bordercall's morphometry engine (the pinned copy under grid/bordercall/, 9c85de1), by the owner's rule of 29 October that corners and landmarks come from the CT engine's constructions, projected, and never from a 2-D fit. The tool's CONSTRUCTIONS table says each in words; in short:

| construction | what it is | QA loop landmark it stands for |
|---|---|---|
| anterior_superior, anterior_inferior | each end plate's front end on the midline: column.wall_corner's construction mirrored to the front, in the plate's own frame | endplate_depth.anterior, endplate_lower_depth.anterior |
| posterior_superior, posterior_inferior | each end plate's back end on the midline, where the posterior wall meets it (column.wall_corner, the corners the slip is read between) | endplate_depth.posterior, endplate_lower_depth.posterior (and near h_post's two ends) |
| centre_superior, centre_inferior | each end plate's centre on its plane (column.plate_centre): the middle points of the six-point morphometry of Genant (1993) and of Black and McCloskey | none |
| superior_right, superior_left, inferior_right, inferior_left | each end plate's lateral ends, the corners an anteroposterior reader marks: the ends of the widest row of the plate's own layer across its front half, as bordercall's plates.py reads the plate's width (commit 69cae89, repeated in the tool since the pinned copy predates it) | endplate.right/left, endplate_lower.right/left |
| hip_centre | the acetabulum's centre (pelvis.socket_centre: a vote of the hip bone's surface normals over radii of 18 to 32 mm, refined by a sphere) | none |
| femoral_head | the femoral head's centre, read again on the femur: the same vote with the normals turned inward over the femur's proximal 100 mm, refined by a sphere through the head | none |
| crest_top | the iliac crest's highest point along the scanner's long axis (pelvis.crest_top) | none |
| s1_centre, s1_anterior, s1_posterior | the S1 end plate under the lowest lumbar body (pelvis.s1_plate), its front end on the midline, the sacral promontory, and its back end at the sacral canal: the plate's layer walked from its centre forward and backward until a gap of more than 2 mm | none (the QA loop's sacral anchor is tools/qaloop_samples.py's, which this does not change) |
| asis | the anterior superior iliac spine: where the anterior pelvic plane (the plane resting on both ilia above the hip axis and on the pubis in front, turned until every point lies behind it) touches each ilium | none |
| symphysis_superior, symphysis_inferior | each pubis's face at the symphysis (its bone within 6 mm of the other pubis beyond their narrowest gap), its two ends along the joint's long axis | none |
| obturator_inferior, obturator_medial | the obturator foramen as the largest hole in the silhouette of the hip bone below the acetabulum, over views within 40 degrees of the anterior pelvic plane's normal; its lowest point and its point nearest the midline in the view that shows it largest, and the bone there | none |
| sciatic_notch | the greater sciatic notch's deepest point: the hip bone seen along the hip axis, the point of its posterior concavity furthest inside its convex hull, and the bone there | none |

Where a definition was ambiguous, the reading chosen and why:

- Grupp et al. (2020, IJCARS 15:759-769, "Automatic annotation of hip anatomy in fluoroscopy for robust and efficient 2D/3D registration", arXiv 1911.07042) name the fourteen points and say they were "manually digitized" in the CT; the paper gives no definition of any of them and no spread between annotators (read on PMC7263976, 1 November 2026: its heatmaps' spread was "subjectively chosen to approximate the variance found in manual landmark annotation", with no number). So each construction above takes the textbook reading of the name: the ASIS as the iliac spine the anterior pelvic plane rests on (the plane of Lewinnek, which a navigation system registers by palpating the same spines); the notch's apex as its deepest point; the foramen's inferior and medial points as its rim's extremes downward and toward the midline; the symphysis's points as each pubis's own end of the joint, since the release gives a left and a right point for each.
- The foramen's extremes are taken in one view, the one along the foramen, and not over the rim in 3-D, because the rim is a band of bone 10 to 20 mm thick along that view and its 3-D lowest voxel is wherever the band's edge happens to dip; the point is the band's mean at the extreme, the middle of the bone a person clicks on.
- The femoral head's centre is read twice: once as the acetabulum's centre, which the engine already reads and which a congruent hip makes the head's centre too, the joint space lying between two spheres about one centre, and once on the femur's own ball where a femur mask exists; the check shows how far the two lie apart on these specimens.

## The check, and its bars, written before the run

DeepFluoro's release holds, for each of its six cadaveric specimens, fourteen points a person placed in the CT (vol-landmarks: the femoral head centres FH, the greater sciatic notches GSN, the obturator foramen's inferior and medial points IOF and MOF, the pubic symphysis's superior and inferior points SPS and IPS, and the anterior superior iliac spines ASIS, each left and right), in the volume's world frame, which is ct.nii.gz's world in LPS. `tools/annotator_landmarks.py persons` reads them, and nothing else of the file, for the five specimens 17-1882, 17-1905, 18-0725, 18-2799 and 18-2800; 18-1109, the QA loop's held-out test specimen, is never read. `check` builds every construction twice per specimen, on TotalSegmentator's masks (ts/ and ts_femur/) and on the dataset authors' own 3-D labels (vol_seg.nii.gz: hemipelves, the lumbar vertebrae as one class split into its connected pieces and each named by the TotalSegmentator level that holds 70 per cent of it, the sacrum, the femurs), and reports per landmark the 3-D distance between each construction and the person's point (median, maximum and n), the distance between the two sources' constructions, and how far each person's point lies from the authors' bone labels, which shows whether the two frames are one.

The bars, stated before the run:

- A construction agrees with the person where its median distance over the specimens is at most 5 mm. Grupp et al. give no spread between annotators to set this against (above), so the bar is the one set for this check, about the size of the error their own network made on the detector plane over these specimens (5.0 mm mean over all fourteen landmarks, their Table 1); every landmark is reported whatever it shows.
- The frame is one where every person's point other than the femoral head centres lies within 5 mm of the authors' bone labels (the head centres lie inside the femur, at no distance); if not, no distance below means anything.
- The femoral head centre agrees on both readings, the acetabulum's and the ball's, or the difference between the two is reported as what it is.
- Nothing here is checked against a person for the vertebral and sacral points: DeepFluoro's person placed none. Those are reported as the agreement between the two sources (TotalSegmentator against the authors' labels) and, for the promontory, as its place against L5's lower plate, the check the QA loop's sacral anchor failed (docs/research/qa-loop-external/README.md): the promontory should stand in front of L5's lower plate centre by about half the plate's depth, not 4 mm.

## What the check found

To follow from the grid job.
