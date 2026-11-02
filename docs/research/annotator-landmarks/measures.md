# The annotators' landmarks: the measures they make, beside Panjabi, through an X-ray, and for the Bayes rule

Source: the local session of 1 November 2026 (night), on the owner's asks that evening: "the bare minimum my landmark net should also be able to place landmarks annotators have found useful such as the ones deepfluoro placed, the corners a ton of xray groups have placed, etc; it should somehow find where those points correspond to the 3d ct scans and propagate them through and use them if possible for bayesian measurements, and even better if they correlate with known anatomical papers like panjabi". Confidential with the rest of this repository. Every number below comes from grid job 40940528 (2 November, 04:11 to 04:17 UTC; tools/annotator_measures.py at sha256 d06b0947..., as committed here; tools/qaloop_samples.py 001b57dc..., tools/qaloop_gates.py addec0c1...), which read the real pairs under the data root's realx/deepfluoro and realx/cobra (tools/realx_pairs.py, 1 November) with their exports' metadata, ENHANCE.PET's morphometry rows of job 40900765 (rows.csv sha256 98fc3411..., code stamp 1cee7ea83e4c28db, bordercall 9c85de1 as vendored under grid/bordercall/) with the covariates' choice of one study a person (job 40902924, persons.csv sha256 8c2d91d2...), and ranked them with bordercall's census (schwingcheck/census.py) from a clone of bordercall's main at 5529bbd, read as a library and not changed. Aggregates only: the rows, the frames and the persons stay on the grid.

## In short

- The oracle's eighteen points (tools/qaloop_gates.py LANDMARKS) make Panjabi's chords exactly, the lateral reader's corner heights and their ratios, the anteroposterior reader's widths, the segmental angles between levels, and a dozen scale-free ratios. They cannot make Genant's wedge or biconcavity as Genant meant them, the wedge angle, the plates' inclinations, the concavity, the discs or the pelvis: the oracle sets all four points of a plate at the slab's median height, so the plate's four points share one height in the vertebra's frame to 6e-14 mm and the two depth chords are parallel to 6e-14 degrees over 315 vertebrae (section 2). Those measures are read from the engine's own rows (h_ant, h_mid, h_post_inset, body_index_ant_post, body_index_mid_post, wedge, the inclinations, the concavities, the discs, pelvic_incidence, intercristal_level).
- Projection, tested on 69 real persons (3 DeepFluoro specimens, 66 COBRA cases) through every registered frame: within 15 degrees of the vertebra's own anteroposterior or lateral view every chord read in its view keeps its length to a median 0.3 to 0.6 per cent once divided by the magnification, the ratios keep their values to a median 0.001 to 0.009 (0.019 for the height over the width, whose lateral heights have a depth part, and 0.044 for the transverse span over the width, the one ratio that fails its bar), and the segmental angles to 0.3 and 0.4 degrees. Past 15 degrees the lengths that lie across the turn fall away (the end-plate depth reads 11 per cent short at 25 to 35 degrees and 20 at 35 to 60), while the posterior height, the corner heights and the ratios of two chords that lie the same way hold (ha/hp 0.016, EPDl/EPDu 0.002, the width taper 0.008 at 25 to 35 degrees).
- None of DeepFluoro's pair readings, and 3 of the 446 from its other frames, lies within 15 degrees of its vertebra's own view: its pairs' frames are within 15 degrees of anteroposterior by the export's angle in the patient's axes, but a median 43 degrees off the vertebrae's own nearer view, whose frames lie a median 32 degrees tilted against the scanner's long axis. The projection numbers within 15 degrees are COBRA's.
- For the Bayes rule, over the six lumbar names (T12 to L5, at most 1.79 nats), the census ranks the transverse span first on Panjabi's table (0.56 nats) and on the gold tier's 1,440 persons (0.53), most of it at T12 (1.54 nats, 93 per cent of T12's bodies named alone, its span 51.5 mm against L1's 74.6). The engine's posterior height comes next on the gold tier, adding 0.15 after the span; alone it tells 0.47 nats at L5 (23.8 mm against L4's 28.2) and at most 0.11 at any other level; then L5's own shape: its lower plate's inclination (15.2 degrees against 7.3 at L4), its wedge ratio (body_index_ant_post 1.15 against 1.05 at L4) and its wedge angle (8.6 degrees). Panjabi's own posterior height carries 0.014 nats over these levels: his means run 22.7 to 24.3 mm from T12 to L5 with L5 at 22.9 (panjabi_long.csv), where the gold tier's L5 stands 4.4 mm below its L4.
- Read as an X-ray reads them within 15 degrees of the view, no measure loses more than 0.003 nats: the projection's error (at most 0.7 mm on a length, the transverse span's, and 0.015 on a ratio) is small beside the census's own reading error (1 mm, 0.04, 3 degrees) and the persons' spread. Off the view the cost is the lengths': the transverse span falls from 0.54 to 0.40 nats at 25 to 35 degrees and to 0.26 at 35 to 60, while the scale-free ratios of chords that lie the same way keep theirs (body_index_ant_post 0.186 on the CT, 0.172 at 35 to 60 degrees; canal_w_over_width 0.140 and 0.139).
- The iliac crests' line (Tuffier's line), a counting landmark of its own, crosses L4 in 886 of the 1,348 persons whose line crosses a lumbar body (65.7 per cent) and L5 in 451: it tells 1.11 of 1.79 nats about the body it crosses, as read on the supine CT along the scanner's long axis. That is a question of its own, about the one body the line marks, but no chord tells a lone body as much on average over the six levels (the transverse span 0.53 to 0.56).

## 1. The measures the annotators' schemes make

The schemes: the six points of a lateral reader (each plate's anterior, middle and posterior points; Genant 1993, McCloskey 1993, Black 1991), the four corners a lateral or anteroposterior reader marks, Panjabi's chords (1991 to 1993), the S1 plate and the hip centres of the pelvic parameters (Legaye and Duval-Beaupere 1998), the iliac crests' line, and DeepFluoro's fourteen pelvic points a person placed in each specimen's CT. The Panjabi mnemonics are bordercall schwingcheck/mnemonics.py's and data/panjabi_long.csv's; the literature keys are the clinical reread's research_notes/paper-tables/tools/vocabulary.csv's; the engine rows are grid/bordercall/morphometry's, at 9c85de1; the eighteen points' construction is grid/autoanatomist/autoanatomist/oracle.py's.

| Measure | Landmarks that make it | Panjabi or literature key | Engine row | The eighteen points make it | View |
|---|---|---|---|---|---|
| Upper plate width | the upper plate's right and left ends | EPWu (endplate) | endplate | yes, endplate.right to .left | AP |
| Lower plate width | the lower plate's right and left ends | EPWl (endplate_lower) | endplate_lower | yes | AP |
| Upper plate depth | the upper plate's posterior and anterior ends at the midline | EPDu (endplate_depth) | endplate_depth | yes | lateral |
| Lower plate depth | the lower plate's posterior and anterior ends | EPDl (endplate_lower_depth) | endplate_lower_depth | yes | lateral |
| Posterior height, Panjabi's | the posterior wall's superior and inferior ends | VBHp (h_post) | h_post | yes, h_post.superior to .inferior | lateral |
| Anterior height ha (Genant, McCloskey, Black) | the two plates' anterior corners | h_ant (no Panjabi table) | h_ant, 2.5 mm inside the corner, between the plates' surfaces (body.heights) | in part: endplate_depth.anterior to endplate_lower_depth.anterior, between the slabs' median heights, not the surfaces | lateral |
| Posterior height hp (the six points') | the two plates' posterior corners | h_post | h_post_inset, read as h_ant is | in part, as ha | lateral |
| Middle height hm | the plates' middle points | h_mid | h_mid | in part: the depth chords' middles, which lie on the slabs' median heights, so no concavity shows | lateral |
| Wedge ratio ha/hp (Genant) | the four lateral corners | body_index (named, no table in the reread) | body_index_ant_post | no: the anterior and posterior corner heights are equal by construction, but for the anterior ends' offset | lateral |
| Biconcavity ratio hm/hp (Genant) | the six points | body_index | body_index_mid_post | no, for the same reason | lateral |
| Crush ratio, hp over the neighbours' hp (Genant) | the posterior corners of three levels | none | none; computed here from h_post_inset (crush_index) | yes, from VBHp of three levels | lateral |
| Wedge angle, between the plates | the four lateral corners | wedge; Panjabi's EPIt printed without a spread | wedge (body.inclinations) | no: both depth chords run along the frame's y | lateral |
| Plate inclinations | each plate's corners against the posterior wall | EPItu, EPItl (endplate_incl, endplate_lower_incl) | endplate_incl, endplate_lower_incl | no | lateral |
| Plate concavity | the plate's middle against its rim | endplate_concavity (printed without a spread) | endplate_concavity, endplate_lower_concavity | no | lateral |
| Disc heights | the facing plates' corners and middles | disc_h_ant, disc_h_mid, disc_h_post | disc_h_ant, disc_h_mid, disc_h_post | no: the plates' points lie inside the bone, at the slabs' median heights | lateral |
| Segmental angle, sagittal and coronal | a level's upper plate and the next level's | alignment | segment_sagittal, segment_coronal | yes, between the levels' plate chords (seg_sag, seg_cor) | lateral, AP |
| Canal depth | the canal's posterior and anterior walls at the midline | SCD (canal_ap) | canal_ap, canal_ap_lateral_film | yes | lateral |
| Canal over body (Torg and Pavlov) | the canal's walls and the body's front and back | canal_index | canal_index_torg (canal_ap over body_d_mid) | an analogue, SCD over EPDu | lateral |
| Canal width; the interpedicular distance of the AP film (Hinck 1966) | the canal's side walls; the pedicles' medial walls | SCW (canal_w); interpedicular | canal_w; interpedicular, interpedicular_max | yes, SCW; the interpedicular distance as an analogue | AP |
| Transverse span | the transverse processes' tips | TPW (transverse_width) | tp_span (specs.py keeps it record-only) | yes | AP |
| Spinous length | the canal's posterior wall to the spinous tip | SPL (spinous_length) | spinous_length | yes; Panjabi's L3 SPL is 71.7 mm in panjabi_long.csv and the engine's L3 mean 41.4, so the two are not one chord | lateral |
| Lateral heights, right and left | each plate's right ends, each plate's left ends | h_lat (named, no table) | none | yes, but each is a chord in three dimensions with a depth part, which an AP view drops (section 2) | AP |
| Coronal wedge, right over left height | the four coronal corners | none | none | yes | AP |
| Waist width and depth (Eisenstein) | the body's mid-height outline | body_w_mid, body_d_mid | body_w_mid, body_d_mid | analogues, EPWu and EPDu | AP, lateral |
| Ratios of the chords: depth over height, depth taper, width taper, canal width over plate width, transverse span over plate width, spinous length over depth, a chord over the next level's | the chords' ends | none | none; computed here from the engine's rows (depth_over_h_post, depth_taper, width_taper, canal_w_over_width, tp_span_over_width, spinous_over_depth, h_post_over_below, depth_over_below, width_over_below, tp_span_over_below) | yes | as the chords |
| Pelvic incidence, sacral slope, pelvic tilt (Legaye and Duval-Beaupere 1998) | the S1 plate's centre and normal, the two hip centres | sacrum, alignment (other) | pelvic_incidence, sacral_slope_supine, pelvic_tilt_supine (pelvis.incidence; supine, against the scanner's long axis) | no; qaloop_samples.sacral_points gives the promontory, the top of S1 and the alae, not the plate, and the pairs carry no hips | lateral |
| Femoral head centres (DeepFluoro FH-l, FH-r) | a person's points in the CT | none | the acetabulum's centre (pelvis.socket_centre) and hip_axis_width; ENHANCE.PET labels no femur | no | AP |
| The iliac crests' line (Tuffier) | each crest's highest point | none | intercristal_level, intercristal_above_l4l5 (pelvis.crests) | no | AP |
| DeepFluoro's sciatic notches, obturator foramina, pubic symphysis, anterior superior iliac spines (GSN, IOF, MOF, SPS, IPS, ASIS) | a person's points in the CT | none; the spines and the symphysis make Lewinnek's anterior pelvic plane | none | no | AP |

## 2. What projection does to each

The test, by the code in tools/annotator_measures.py (`project`). Each real pair's 3-D landmarks (levels, 18, 3, in the CT's LPS millimetres) were read with qaloop_samples.load_pair and projected through each of its frames' P; then each person's other frames were read from the export's own metadata (its K and extrinsic, the same registration), since the pairs keep only frames within 15 degrees of either view by the export's angle and the test needs the oblique ones; the persons each set holds out (27 COBRA cases, DeepFluoro's 18-1109) are in no pair and were never read. A pair's frame read through its own P and through the export's P gave the same ratios to 8e-12 (COBRA) and 2e-13 (DeepFluoro), as two readings of one frame should. Each measure was read on the 2-D points in pixels beside its 3-D value: a ratio or an angle against its 3-D value, a length against its 3-D length times the frame's magnification at the length's middle (the focal length over the depth along the principal axis), so that 0 per cent is a length the view shows whole. The angle is the ray's from the source to the vertebra's centre, against the vertebra's own axes from its own points (z up the posterior wall, y from the canal along the upper depth chord, x their cross product): degrees off its true anteroposterior view (the ray along y) or its true lateral view (the ray along x), whichever is nearer. Only readings with every point of the measure inside the frame count: 46,084 of 226,580. The bars were written in the code before the test ran: within 15 degrees of the view a measure is read in, a ratio within 0.04 of its 3-D value at the median and 0.08 at the 90th percentile (the census's ratio error), an angle within 3 and 6 degrees, a length within 5 and 10 per cent.

Median absolute agreement by degrees off the vertebra's own view, in the view the measure is read in (the count of readings in brackets), the median and 90th percentile within 15 degrees, the correlation across persons of the 2-D reading (a length divided by its magnification) with the 3-D value within each level, and the verdict:

| Measure | Kind | View | Persons | 0-5 | 5-10 | 10-15 | 15-25 | 25-35 | 35+ | Within 15: median, p90 | r within level | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EPWu | length | ap | 24 | 0.1% (10) | 0.4% (33) | 1.4% (50) | 3.1% (149) | 7.8% (221) | 13.4% (353) | 0.6%, 2.0% | 1.00 | survives |
| EPWl | length | ap | 39 | 0.1% (19) | 0.4% (58) | 1.3% (87) | 3.5% (269) | 9.1% (343) | 14.9% (551) | 0.6%, 2.0% | 1.00 | survives |
| EPDu | length | lat | 42 | 0.0% (38) | 0.2% (109) | 1.5% (108) | 4.3% (179) | 11.1% (184) | 20.2% (203) | 0.4%, 2.2% | 1.00 | survives |
| EPDl | length | lat | 57 | 0.0% (51) | 0.2% (174) | 1.4% (199) | 4.4% (296) | 10.8% (296) | 20.3% (335) | 0.4%, 2.2% | 1.00 | survives |
| VBHp | length | lat | 43 | 0.2% (38) | 0.2% (114) | 0.4% (113) | 0.6% (183) | 1.0% (188) | 2.3% (208) | 0.3%, 1.1% | 1.00 | survives |
| SCW | length | ap | 31 | 0.1% (14) | 0.4% (46) | 1.3% (71) | 3.3% (220) | 8.9% (280) | 16.1% (409) | 0.6%, 2.1% | 1.00 | survives |
| SCD | length | lat | 44 | 0.1% (44) | 0.2% (137) | 1.4% (140) | 4.5% (226) | 11.3% (229) | 20.8% (253) | 0.5%, 2.2% | 1.00 | survives |
| TPW | length | ap | 27 | 0.1% (10) | 0.3% (32) | 1.2% (52) | 3.1% (173) | 8.2% (213) | 16.6% (296) | 0.5%, 2.1% | 1.00 | survives |
| SPL | length | lat | 43 | 0.7% (34) | 0.3% (122) | 1.5% (118) | 3.7% (183) | 9.2% (195) | 19.4% (241) | 0.6%, 4.0% | 1.00 | survives |
| ha | length | lat | 48 | 0.2% (40) | 0.3% (122) | 0.5% (127) | 0.5% (204) | 0.9% (209) | 1.6% (236) | 0.4%, 2.2% | 0.96 | survives |
| hp | length | lat | 43 | 0.3% (39) | 0.3% (117) | 0.4% (118) | 0.5% (189) | 0.9% (194) | 2.0% (210) | 0.3%, 2.4% | 0.95 | survives |
| hm | length | lat | 42 | 0.3% (38) | 0.3% (109) | 0.4% (108) | 0.5% (179) | 0.8% (184) | 1.6% (197) | 0.3%, 2.5% | 0.95 | survives |
| hl | length | ap | 24 | 2.8% (10) | 3.6% (33) | 4.5% (49) | 4.7% (149) | 6.1% (220) | 10.0% (353) | 4.2%, 11.2% | 0.92 | does not survive |
| ha/hp | ratio | lat | 42 | 0.001 (38) | 0.002 (109) | 0.005 (108) | 0.009 (179) | 0.016 (184) | 0.022 (197) | 0.002, 0.007 | 0.99 | survives |
| hm/hp | ratio | lat | 42 | 0.001 (38) | 0.001 (109) | 0.002 (108) | 0.005 (179) | 0.008 (184) | 0.011 (197) | 0.001, 0.004 | 0.95 | survives |
| crush | ratio | lat | 7 | 0.001 (6) | 0.002 (15) | 0.002 (13) | 0.004 (20) | 0.008 (21) | 0.018 (18) | 0.002, 0.008 | 1.00 | survives |
| EPDu/VBHp | ratio | lat | 42 | 0.004 (38) | 0.005 (108) | 0.018 (105) | 0.045 (175) | 0.120 (181) | 0.221 (197) | 0.007, 0.027 | 1.00 | survives |
| EPDl/EPDu | ratio | lat | 42 | 0.001 (38) | 0.001 (109) | 0.002 (108) | 0.002 (179) | 0.002 (184) | 0.002 (197) | 0.001, 0.006 | 1.00 | survives |
| SCD/EPDu | ratio | lat | 42 | 0.001 (38) | 0.002 (107) | 0.004 (106) | 0.007 (179) | 0.011 (183) | 0.014 (199) | 0.002, 0.006 | 1.00 | survives |
| SPL/EPDu | ratio | lat | 41 | 0.009 (29) | 0.005 (91) | 0.015 (88) | 0.030 (141) | 0.063 (154) | 0.094 (184) | 0.009, 0.052 | 1.00 | survives |
| VBHp/below | ratio | lat | 16 | 0.007 (16) | 0.004 (39) | 0.007 (47) | 0.009 (60) | 0.017 (69) | 0.025 (63) | 0.006, 0.016 | 1.00 | survives |
| EPDu/below | ratio | lat | 20 | 0.003 (17) | 0.003 (43) | 0.009 (52) | 0.017 (73) | 0.029 (76) | 0.044 (74) | 0.005, 0.027 | 0.96 | survives |
| EPWl/EPWu | ratio | ap | 24 | 0.006 (10) | 0.008 (33) | 0.008 (49) | 0.008 (149) | 0.008 (220) | 0.008 (353) | 0.008, 0.012 | 1.00 | survives |
| SCW/EPWu | ratio | ap | 24 | 0.008 (10) | 0.009 (33) | 0.008 (50) | 0.007 (149) | 0.007 (220) | 0.005 (330) | 0.008, 0.010 | 0.99 | survives |
| TPW/EPWu | ratio | ap | 23 | 0.040 (8) | 0.045 (25) | 0.044 (39) | 0.043 (128) | 0.039 (182) | 0.029 (263) | 0.044, 0.058 | 0.99 | does not survive |
| hl/EPWu | ratio | ap | 24 | 0.014 (10) | 0.019 (33) | 0.022 (49) | 0.018 (149) | 0.049 (220) | 0.102 (353) | 0.019, 0.052 | 0.96 | survives |
| hlR/hlL | ratio | ap | 24 | 0.002 (10) | 0.004 (33) | 0.008 (49) | 0.014 (149) | 0.024 (220) | 0.036 (353) | 0.005, 0.019 | 1.00 | survives |
| EPWu/below | ratio | ap | 18 | 0.008 (6) | 0.012 (28) | 0.007 (36) | 0.011 (79) | 0.020 (79) | 0.032 (75) | 0.009, 0.025 | 1.00 | survives |
| TPW/below | ratio | ap | 23 | 0.007 (6) | 0.005 (26) | 0.007 (38) | 0.013 (105) | 0.021 (92) | 0.035 (92) | 0.006, 0.017 | 0.99 | survives |
| seg_sag | angle | lat | 18 | 0.1 deg (17) | 0.3 deg (42) | 0.6 deg (49) | 1.2 deg (69) | 2.2 deg (73) | 4.8 deg (68) | 0.4 deg, 1.2 deg | 1.00 | survives |
| seg_cor | angle | ap | 17 | 0.1 deg (6) | 0.3 deg (26) | 0.4 deg (31) | 0.7 deg (74) | 1.2 deg (76) | 1.9 deg (73) | 0.3 deg, 1.0 deg | 1.00 | survives |

What the numbers say:

- A length that lies across the turn is read short by about what the turn takes out of the image plane, and the angle is what matters: within 5 degrees every length is read whole to 0.1 to 0.7 per cent, by 25 to 35 degrees the widths and depths lose 8 to 11 per cent, and by 35 to 60 degrees 13 to 21. The heights, which stand along the column, lose 1 to 2 per cent at 35 to 60 degrees, since a turn about the long axis leaves a vertical chord in the image plane. The signed medians run the same way (a reading is short, never long), so this is foreshortening and not noise.
- In the other view a chord across the ray is all but gone: within 15 degrees of the lateral, the widths read 83 to 84 per cent short, and within 15 degrees of the anteroposterior, the depths 82 to 83 (the second table of the job's report). The heights read whole in either view (VBHp 0.4 per cent in an anteroposterior frame), though only the lateral view shows the posterior wall as an edge.
- A ratio of two chords that lie the same way keeps its value at any angle, since both foreshorten alike: the depth taper EPDl/EPDu by 0.002 from 0 to 60 degrees, the width taper by 0.008, the canal over the body SCD/EPDu by 0.014 at worst. A ratio of chords that lie different ways (depth over height, EPDu/VBHp) holds within 15 degrees (0.007) and falls apart past 25 (0.120, then 0.221).
- Two measures fail their bars, and why can be read off the geometry. The lateral heights an anteroposterior reader takes from the eighteen points (hl) read 4.2 per cent short within 15 degrees, signed, because the upper and the lower plate's lateral ends lie at different depths (each at its own slab's median depth), so the 3-D chord has a part along the ray; it is a property of the construction, not of the view, and a reader's lateral height, an edge on the image, would not have it. The transverse span over the plate's width (TPW/EPWu) varies by 0.044 within 15 degrees with a signed median of 0.004, about 2.5 per cent of a ratio whose gold tier means run 1.62 to 1.87 from L1 to L5: the transverse processes lie behind the plate's points along an anteroposterior ray, so the two chords' magnifications differ, the sign set by which side the source is on, and that spread is past the census's 0.04.
- DeepFluoro: none of its 1,703 in-frame pair readings and 3 of its 446 export readings lie within 15 degrees of the vertebra's own view (5th, 50th and 95th percentiles 27, 43 and 59 degrees for the pair frames). Its six read vertebrae have their long axes 13, 32 and 44 degrees (the same percentiles) off the scanner's and their left-right axes 8, 18 and 39 degrees off the scanner's, where COBRA's 309 have 2, 12 and 35 and 1, 5 and 18. Its widths still read within 0.5 to 1.4 per cent at 25 to 60 degrees off the vertebra's anteroposterior view (12 to 118 readings, 1 to 3 persons), where COBRA's lose 8.6 to 18.1 per cent, which fits a tilt about the vertebra's own left-right axis, which leaves a left-right chord in the image plane, where COBRA's oblique frames are the gantry's turn about the long axis, which does not. Whether the specimens' lumbar columns lie that bent in the scanner or the oracle's frame (the column's line through the neighbours' centroids, here on a CT that cuts the lumbar spine) is tilted, the test cannot say; the realx pairs' first check, the landmarks inside the export's boxes, says nothing of a frame's tilt.
- The magnification a frame does not state: across in-frame readings the logarithm of the magnification has an SD of 0.022 on COBRA (a fixed gantry, the 5th percentile 0.93 of the 95th) and 0.133 on DeepFluoro (a C-arm, 0.65). A length read in pixels on an uncalibrated C-arm frame carries a scale unknown to about 13 per cent; a ratio carries none.

## 3. How much each tells the Bayes rule

The census (bordercall schwingcheck/census.py, the owner's ask of 29 October): the information a measure gives a lone body about its level is the mean log posterior at the truth plus log K, the bodies drawn from the table's mean and spread at each level, the person's size log-normal (SD 0.07) and integrated out, each measure read with its error (1 mm, 0.04 for a ratio, 3 degrees). Run here over the six lumbar names a lumbar frame shows, T12 to L5, at most log 6 = 1.79 nats, with 2,000 bodies a level. Three sources, each its own population, never pooled: Panjabi's table cut to those levels; the gold tier's ENHANCE.PET persons (one study a person as the covariates' join chose it: 1,445 chosen, 867 autoPET and 578 of the members the join names enhance_pet, 1,440 of them with rows), their per-level means, SDs and counts computed from the engine's rows (cells of 5 or more; a sixth lumbar's rows and its disc's left out, so L5's neighbour below is the sacrum and the ratios against the level below run T12 to L4, ranked as a group of their own); and the same gold table as read on an X-ray, each measure's error widened by what section 2 measured for its stand-in within 15 degrees of its view (the bias and the robust SD, in quadrature with the census's error; a length's relative error times its mean). The census assumes the measures independent given the level and the size, so what a ratio adds after its parts is an upper bound; the correlation table (Pearson within each level, 30 persons or more) names the pairs that share.

Panjabi, T12 to L5 (the measures the eighteen points or a lateral reader's corners make; "named alone" is the share of bodies the measure alone names right, a sixth by chance):

| # | Measure | Alone, mean nats | Named alone | Adds, nats |
|---|---|---|---|---|
| 1 | transverse_width (TPW) | 0.561 | 0.47 | 0.561 |
| 2 | spinous_length (SPL) | 0.386 | 0.36 | 0.094 |
| 3 | endplate (EPWu) | 0.179 | 0.29 | 0.081 |
| 4 | endplate_lower_depth (EPDl) | 0.036 | 0.22 | 0.068 |
| 5 | canal_w (SCW) | 0.113 | 0.29 | 0.058 |
| 6 | canal_ap (SCD) | 0.042 | 0.23 | 0.048 |
| 7 | endplate_incl (EPItu) | 0.056 | 0.23 | 0.040 |
| 8 | endplate_lower (EPWl) | 0.141 | 0.28 | 0.038 |
| 9 | endplate_lower_incl (EPItl) | 0.044 | 0.22 | 0.025 |
| 10 | endplate_depth (EPDu) | 0.020 | 0.21 | 0.016 |
| 11 | h_post (VBHp) | 0.014 | 0.20 | 0.015 |

The gold tier on the CT, T12 to L5, the greedy order (what each adds after those above it; a measure whose gain is under a tenth of its own is listed as repeating the one it shares most with):

| # | Measure | Alone, mean nats | Named alone | Adds, nats | Repeats |
|---|---|---|---|---|---|
| 1 | tp_span | 0.528 | 0.43 | 0.528 | |
| 2 | h_post | 0.128 | 0.27 | 0.152 | |
| 3 | tp_span_over_width | 0.432 | 0.41 | 0.127 | |
| 4 | endplate_lower_incl | 0.215 | 0.31 | 0.095 | |
| 5 | body_w_mid | 0.188 | 0.30 | 0.065 | |
| 6 | canal_w_over_width | 0.127 | 0.27 | 0.049 | |
| 7 | body_index_ant_post | 0.187 | 0.30 | 0.041 | |
| 8 | spinous_length | 0.163 | 0.29 | 0.037 | |
| 9 | canal_ap | 0.063 | 0.24 | 0.037 | |
| 10 | canal_w | 0.076 | 0.24 | 0.025 | |
| 11 | canal_index_torg | 0.076 | 0.24 | 0.023 | |
| 12 | endplate | 0.121 | 0.26 | 0.022 | |
| 13 | wedge | 0.148 | 0.28 | 0.018 | |
| 14 | endplate_lower_concavity | 0.126 | 0.27 | 0.017 | |
| 15 | spinous_over_depth | 0.100 | 0.26 | 0.015 | |
| 16 | canal_ap_over_depth | 0.078 | 0.25 | 0.014 | |
| 17 | body_index_mid_post | 0.130 | 0.27 | 0.012 | endplate_lower_incl |
| 18 | width_taper | 0.094 | 0.26 | 0.011 | |
| 19 | interpedicular | 0.081 | 0.25 | 0.009 | |
| 20 | endplate_lower | 0.099 | 0.26 | 0.009 | tp_span |
| 21 | h_post_inset | 0.059 | 0.24 | 0.009 | |
| 22 | depth_over_h_post | 0.098 | 0.26 | 0.007 | endplate_lower_incl |
| 23 | h_ant | 0.091 | 0.26 | 0.005 | tp_span |
| 24 | depth_taper | 0.053 | 0.22 | 0.005 | endplate_lower_incl |
| 25 | h_mid | 0.045 | 0.23 | 0.002 | tp_span |
| 26 | endplate_incl | 0.023 | 0.21 | 0.002 | endplate_lower_incl |
| 27 | endplate_lower_depth | 0.030 | 0.21 | 0.002 | tp_span |
| 28 | body_d_mid | 0.025 | 0.21 | 0.001 | tp_span |
| 29 | endplate_depth | 0.024 | 0.20 | 0.001 | spinous_length |
| 30 | endplate_concavity | 0.041 | 0.22 | 0.000 | endplate_lower_incl |

Shared by correlation (median |r| of 0.7 or more over the six levels): body_index_ant_post and wedge (0.90), body_d_mid and endplate_depth (0.82), depth_over_h_post and endplate_depth (0.81), canal_ap_over_depth and endplate_depth (0.80), body_w_mid and endplate_lower (0.79), canal_w and interpedicular (0.77), body_d_mid and endplate_lower_depth (0.76), endplate_depth and endplate_lower_depth (0.74), endplate and endplate_lower (0.71).

The gold tier on the CT, the measures against the level below (and Genant's crush, which needs both neighbours), T12 to L4, at most 1.61 nats:

| # | Measure | Alone, mean nats | Named alone | Adds, nats |
|---|---|---|---|---|
| 1 | tp_span_over_below | 0.459 | 0.48 | 0.459 |
| 2 | h_post_over_below | 0.240 | 0.37 | 0.192 |
| 3 | depth_over_below | 0.127 | 0.32 | 0.062 |
| 4 | width_over_below | 0.097 | 0.30 | 0.050 |
| 5 | disc_h_ant | 0.078 | 0.29 | 0.027 |
| 6 | segment_sagittal | 0.057 | 0.28 | 0.016 |
| 7 | disc_h_post | 0.054 | 0.27 | 0.015 |
| 8 | crush_index | 0.021 | 0.24 | 0.007 |
| 9 | segment_coronal | 0.012 | 0.23 | 0.004 |

Why the leaders lead, from the same tables (the gold tier's means and SDs, and the census's nats at each level): the transverse span at T12 is 51.5 mm (SD 5.7) against 74.6 (9.0) at L1, so it tells 1.54 nats at T12 and names 93 per cent of T12's bodies alone, against 0.21 to 0.48 nats at L1 to L5; Panjabi's TPW and SPL do the same at T12 (1.55 and 1.48 nats). L5 is told by its shape: its posterior height (h_post) is 23.8 mm (2.9) against 28.2 (2.7) at L4, 0.47 nats at L5; its lower plate's inclination 15.2 degrees (7.4) against 7.3 (6.4), 0.66 nats; its wedge ratio 1.15 (0.13) against 1.05 (0.11), 0.50 nats; its wedge angle 8.6 degrees (8.5) against 2.2 (7.2), 0.42 nats. The posterior height over the next level's is 1.21 (0.18) at L4 against 0.95 to 1.04 above it (0.62 nats at L4), which is L5's short back seen from L4. The middle levels are told least: at L2 to L4 the transverse span tells 0.21 to 0.31 nats alone and the posterior height 0.03 to 0.11, which is where a count needs its anchor.

As read on an X-ray within 15 degrees of the view: each measure alone, on the CT and on the X-ray from the same draws, so that the difference is the projection's alone (SE of the mean 0.002 to 0.006): no measure loses more than 0.003 nats, the transverse span 0.530 against 0.529, the plate width 0.126 against 0.125, the wedge ratio 0.187 against 0.187. The greedy order on the X-ray keeps the CT's leaders (tp_span 0.530, h_post 0.154 added, endplate_lower_incl 0.103, body_w_mid 0.063); tp_span_over_width is left out of it for failing its bar, and the discs and the concavities for having no stand-in among the eighteen points.

Each measure alone as read at each angle off its view (500 bodies a level; mean nats, the CT's first; a bin with under 20 readings left out), the leaders and the ratios:

| Measure | Stand-in | View | CT | 5-10 | 10-15 | 15-25 | 25-35 | 35-60 |
|---|---|---|---|---|---|---|---|---|
| tp_span | TPW | ap | 0.539 | 0.539 | 0.536 | 0.512 | 0.404 | 0.256 |
| tp_span_over_below | TPW/below | ap | 0.455 | 0.453 | 0.451 | 0.441 | 0.423 | 0.372 |
| h_post_over_below | VBHp/below | lat | 0.239 | 0.239 | 0.238 | 0.236 | 0.232 | 0.220 |
| endplate_lower_incl | seg_sag (analogue) | lat | 0.216 | 0.215 | 0.213 | 0.206 | 0.192 | 0.127 |
| body_index_ant_post | ha/hp (analogue) | lat | 0.186 | 0.185 | 0.185 | 0.183 | 0.179 | 0.172 |
| body_w_mid | EPWu (analogue) | ap | 0.174 | 0.174 | 0.172 | 0.164 | 0.128 | 0.080 |
| spinous_length | SPL | lat | 0.164 | 0.164 | 0.159 | 0.142 | 0.098 | 0.048 |
| wedge | seg_sag (analogue) | lat | 0.148 | 0.148 | 0.146 | 0.141 | 0.129 | 0.079 |
| body_index_mid_post | hm/hp (analogue) | lat | 0.141 | 0.141 | 0.141 | 0.140 | 0.139 | 0.137 |
| canal_w_over_width | SCW/EPWu | ap | 0.140 | 0.139 | 0.138 | 0.139 | 0.139 | 0.139 |
| h_post | VBHp | lat | 0.129 | 0.129 | 0.129 | 0.128 | 0.126 | 0.117 |
| depth_over_h_post | EPDu/VBHp | lat | 0.100 | 0.100 | 0.098 | 0.094 | 0.076 | 0.049 |
| endplate | EPWu | ap | 0.098 | 0.098 | 0.097 | 0.090 | 0.067 | 0.040 |
| width_taper | EPWl/EPWu | ap | 0.093 | 0.092 | 0.091 | 0.091 | 0.091 | 0.091 |
| canal_ap_over_depth | SCD/EPDu | lat | 0.079 | 0.079 | 0.079 | 0.079 | 0.077 | 0.076 |
| canal_w | SCW | ap | 0.058 | 0.058 | 0.057 | 0.050 | 0.028 | 0.010 |
| depth_taper | EPDl/EPDu | lat | 0.057 | 0.057 | 0.057 | 0.057 | 0.057 | 0.057 |

So the measures a landmark net should place first, for naming, are the ones that tell most and survive the view: the transverse processes' tips (T12 against L1), the posterior wall's two ends and the four lateral corners (L5's short back and its wedge, as ratios that hold at any angle), and the lower plate's line (its inclination); and for an oblique frame the ratios of chords that lie the same way, which lose almost nothing to the angle where the lengths lose half or more.

The crests' line and the pelvis (the gold tier's pelvis rows, one value a person): the line crosses L4 in 886 persons, L5 in 451, L3 in 11, the L4-L5 disc in 8 and a sixth lumbar in 5 (cells under 5 withheld, 3 of them); over the six lumbar names it tells 1.11 of 1.79 nats about the body it crosses, the commonest body (L4) 65.7 per cent of the time; its height above the middle of the L4-L5 disc is 1.3 mm on average (SD 23.3, 1,366 persons). Pelvic incidence 47.7 degrees (SD 14.5), the supine sacral slope 34.5 (13.4) and the supine pelvic tilt 13.1 (7.3), 1,370 persons, the hip axis 177.6 mm wide (10.7): one value a person, so they tell nothing about which body is which; they are the pelvis's own measures and the lordosis's context, and the S1 plate under them is the count's anchor.

## 4. What this does not do, and what would be needed

- No measure of the pelvis was tested through projection: the pairs carry no hip centre or S1 plate, and all of DeepFluoro's frames are anteroposterior, where pelvic incidence is not read. Testing it needs the engine's S1 plate and socket centres on the pairs' CTs (pelvis.s1_plate and socket_centre, which the realx builder does not call) and a lateral real frame; DeepFluoro's person-placed femoral head centres (FH-l, FH-r) are the check on the socket centres the engine would give there.
- Genant's heights, the wedge angle, the inclinations, the concavity and the discs were tested through stand-ins (the slab-centre heights, the segmental angle), not as the engine draws them: the engine's points for them (body.heights' band surfaces, rim_plane) are computed and not returned. Placing them as landmarks means returning those points from the engine, a change to make in bordercall and vendor here, never in the copy.
- The census reads every measure as independent given the level and the size; with the gold tier's correlations (above) the joint information of the leaders is less than the sum of their gains. bordercall's correlation prior (docs/memory/the-correlation-prior.md) is the way to take that in.
- The ratios that need a table the papers do not print: Genant's wedge and biconcavity ratios, his crush ratio, the coronal wedge, the depth over the height, the canal over the body, the spinous over the depth and every chord over the next level's have no table in Panjabi or the reread's series (vocabulary.csv names body_index, canal_index and h_lat with no series). The gold tier's per-level means and SDs here are one such table, for one population; a second, of a different population measured another way (a lateral-film series of the six-point heights by level, such as the morphometric fracture studies keep for their normal ranges), is what would tell whether these ratios name levels outside ENHANCE.PET's persons.
- The 18 points' lateral heights in an anteroposterior view and the transverse span over the width fail their bars for the reasons in section 2; the first is a property of the construction and would go if the heights were read at the body's side walls.
- No Radiopaedia image was read: the agreement covers saving cases by hand (docs/memory/radiopaedia-by-hand.md), and nothing of this test needs a frame without a registered CT.

To run it again: copy tools/annotator_measures.py, tools/qaloop_samples.py and tools/qaloop_gates.py to a throwaway folder on the grid with a clone of bordercall at main, and run `project`, `gold` and `census` as the module's docstring says, one CPU job (about eight minutes); `report` prints the tables above from the two JSON files.
