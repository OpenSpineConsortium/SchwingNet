# The annotators' landmarks: the measures they make, beside Panjabi, through an X-ray, and for the Bayes rule

Source: the local session of 1 November 2026 (night), on the owner's asks that evening: "the bare minimum my landmark net should also be able to place landmarks annotators have found useful such as the ones deepfluoro placed, the corners a ton of xray groups have placed, etc; it should somehow find where those points correspond to the 3d ct scans and propagate them through and use them if possible for bayesian measurements, and even better if they correlate with known anatomical papers like panjabi"; corrected the same night after two adversarial reviews of pull request #555 (the review's findings and what was done are in that pull request's body). Confidential with the rest of this repository. Every number below comes from grid job 40940875 (2 November, 05:16 to 05:26 UTC; tools/annotator_measures.py at sha256 b9ce2847..., as committed here, whose outputs were byte for byte those of job 40940775, the same code with CRLF line endings; tools/qaloop_samples.py 001b57dc..., tools/qaloop_gates.py addec0c1...), which read the real pairs under the data root's realx/deepfluoro and realx/cobra (tools/realx_pairs.py, 1 November) with their exports' metadata, ENHANCE.PET's morphometry rows of job 40900765 (rows.csv sha256 98fc3411..., code stamp 1cee7ea83e4c28db, bordercall 9c85de1 as vendored under grid/bordercall/) with the covariates' choice of one study a person (job 40902924, persons.csv sha256 8c2d91d2...) cut to the persons whose column bordercall's count calls T12L5 (verdicts.csv sha256 bd5bc908...), and ranked them with bordercall's census (schwingcheck/census.py) from a clone of bordercall at 5529bbd, read as a library and not changed; the census also read the clinical reread's series (research_notes/paper-tables/data/series.csv at that commit). The run's outputs: census.json sha256 1ce33d2d..., projection.json dedefe47..., gold/table.csv 9ad2ea7f.... Aggregates only: the rows, the frames and the persons stay on the grid.

## In short

- The oracle's eighteen points (tools/qaloop_gates.py LANDMARKS) make chords under Panjabi's names, the lateral reader's corner heights and their ratios, the segmental angles between levels, and a dozen scale-free ratios, but several of those chords are not Panjabi's. The plate widths and the canal width are the CT label's slab extents (scanimport's, as the engine read them at 9c85de1), which take in what the label fuses to the plate's edge and read the canal from the label's hole: they read 5.0 to 9.3 mm over Panjabi's EPWu (9.3 at L5) and 4.5 and 6.1 mm under his SCW at L4 and L5, and bordercall #78 (69cae89, after 9c85de1) has since replaced both with plate_w and canal_w_ct, which these rows do not hold. The spinous length is another chord (33 to 41 mm against Panjabi's 47 to 72). The posterior wall reads 4.2 to 5.3 mm over Panjabi's VBHp at T12 to L4 and 0.7 at L5, though within the range of the reread's other series at every level but L4, where it is 0.3 mm over their most. And the points cannot make a wedge: the oracle sets all four points of a plate at the slab's median height, so they share one height to 6e-14 mm and the two depth chords are parallel to 6e-14 degrees over 315 vertebrae (section 2). The six-point heights and their wedge, biconcavity and crush ratios (Eastell 1991), the wedge angle, the inclinations, the concavity, the discs and the pelvis are read from the engine's own rows.
- Projection, tested on 66 COBRA cases through every registered frame, as fixed 3-D points carried through each frame's P. Within 15 degrees of the vertebra's own view, every chord read in its view keeps its length to a median 0.3 to 0.6 per cent once divided by the frame's magnification. The ratios keep their values to 0.001 to 0.009 (0.019 for the height over the width, whose lateral heights have a depth part) and the segmental angles to 0.3 and 0.4 degrees. Two measures fail their bars there: the lateral heights read on an AP view (hl, 4.2 per cent) and the transverse span over the width (TPW/EPWu, 0.044). Past 25 degrees, the lengths that lie across the turn lose 8.6 to 11.3 per cent at 25 to 35 degrees and 16.6 to 20.8 at 35 to 60. The heights and the ratios of two chords that lie the same way hold. These are what the view does to fixed points. A reader marks an outline's extreme instead, and off the view that reads differently: modelled as an elliptic plate of Panjabi's L3 size, at 30 degrees the outline's width reads 4.6 per cent short where the fixed points read 13.4, and its depth 6.9 per cent long (section 2).
- DeepFluoro's three specimens are tabled apart. None of their pair readings lies within 15 degrees of the vertebra's own view (a median 43 degrees off), and their read vertebrae lie a median 32 degrees tilted in the scanner, which the test cannot tell from a tilted oracle frame. Pooling them would dilute the off-view figures: EPWu at 35 to 60 degrees would read 13.4 per cent where COBRA alone reads 16.6. The magnification a frame does not state has a log SD of 0.022 on COBRA's fixed gantry and 0.065 on DeepFluoro's C-arm (5th over 95th percentile 0.93 and 0.83), once each frame is taken on its own canvas; pooling the pairs' 512-pixel canvases with the export's 384 gave 0.133.
- For the Bayes rule, over the six lumbar names (T12 to L5, at most 1.79 nats), on the 1,343 ENHANCE.PET persons whose column has twelve thoracic and five lumbar vertebrae, the census ranks the transverse span first, 0.54 nats. Most of that is at T12: 1.57 nats there, 93 per cent of T12's bodies named by it alone, its span 51.4 mm against L1's 75.1. Panjabi's table ranks it first too (0.56), and his step from T12 to L1 is 24.3 mm against the gold tier's 23.7. The posterior wall comes next, adding 0.16 nats; alone it tells 0.51 nats at L5 (23.7 mm against L4's 28.3) and at most 0.11 at any other level. Then come L5's lower plate inclination (15.6 degrees against 7.2 at L4; 0.70 nats at L5) and its wedge ratio (1.15 against 1.04; 0.52 nats).
- That L5 stands shorter at its back than L4 is anatomy, not only the engine's: every one of the six human series in the reread that prints both levels steps down from L4 to L5 (by 1.4 to 3.1 mm), as Panjabi's does (1.2). The gold tier's step, 4.7 mm, is larger than any of them, so its size is partly the engine's or this population's: the information the census credits to it holds for bodies read as this engine reads them, and a reader whose heights step as the other series' do would get less.
- Read on an X-ray within 15 degrees of the view, with the frame's magnification known, no measure that passes its bar and has a stand-in loses more than 0.003 nats. On a frame whose magnification is unknown by the C-arm's spread, the lengths lose up to 0.055 nats (the transverse span 0.541 to 0.488; body_w_mid, spinous_length and h_post 0.026 to 0.030), while the ratios and angles lose at most 0.003. Three things stand outside that: tp_span_over_width, which fails its bar and loses 0.016 and 0.028 nats at 5 to 10 and 10 to 15 degrees; the discs and the concavities, which have no stand-in and were not run; and the wedge, the inclinations and the six-point ratios, whose errors come from stand-ins that show no wedge.
- The iliac crests' line (Tuffier's) crosses L4 in 881 of the 1,295 persons whose line crosses a lumbar body (68.0 per cent), and L5 in 403. Of the body it crosses it tells 1.13 of 1.79 nats. Of a lone body, on the census's terms, it tells 0.232 nats: 0.64 at L4 and 0.06 to 0.18 elsewhere. That is less than the transverse span (0.54), about as much as L5's lower plate inclination (0.22), and more than the posterior wall alone (0.14).

## 1. The measures the annotators' schemes make

The schemes: the six points of a lateral reader (each plate's anterior, middle and posterior points), which the quantitative morphometry of Eastell 1991 (the wedge, biconcavity and crush ratios against a normal range), Black 1991 (the normal dimensions by level) and McCloskey 1993 (the posterior height against what the neighbours predict) reads, where Genant 1993 grades the same deformities by eye and places no points; the four corners a lateral or anteroposterior reader marks; Panjabi's chords (1991 to 1993); the S1 plate and the hip centres of the pelvic parameters (Legaye and Duval-Beaupere 1998); the iliac crests' line; and DeepFluoro's fourteen pelvic points a person placed in each specimen's CT. The Panjabi mnemonics are bordercall schwingcheck/mnemonics.py's and data/panjabi_long.csv's; the literature keys are the clinical reread's research_notes/paper-tables/tools/vocabulary.csv's; the engine rows are grid/bordercall/morphometry's, at 9c85de1; the eighteen points' construction is grid/autoanatomist/autoanatomist/oracle.py's.

| Measure | Landmarks that make it | Panjabi or literature key | Engine row | The eighteen points make it | View |
|---|---|---|---|---|---|
| Upper plate width | the plate's right and left ends | EPWu (endplate) | endplate: the label slab's lateral extent at 9c85de1, which takes in what the label fuses to the plate's edge (at L5 the transverse processes' roots); plate_w on the plate's own layer since bordercall #78, not in these rows | the same slab extent, not the corner an AP reader marks: 5.0 to 9.3 mm over Panjabi's EPWu, 9.3 at L5 (section 3) | AP |
| Lower plate width | the lower plate's right and left ends | EPWl (endplate_lower) | endplate_lower, the slab's extent as above | the same slab extent: 5.7 to 8.2 mm over Panjabi's EPWl | AP |
| Upper plate depth | the upper plate's posterior and anterior ends at the midline | EPDu (endplate_depth) | endplate_depth | yes: within 0.9 mm of Panjabi's at every level | lateral |
| Lower plate depth | the lower plate's posterior and anterior ends | EPDl (endplate_lower_depth) | endplate_lower_depth | yes: within 2.4 mm of Panjabi's | lateral |
| Posterior height, Panjabi's | the posterior wall's superior and inferior ends | VBHp (h_post) | h_post | the chord of that name: 4.2 to 5.3 mm over Panjabi's at T12 to L4 and 0.7 at L5, within the reread's other series' range at every level but L4, 0.3 mm over their most there (section 3) | lateral |
| Anterior height ha (six-point morphometry) | the two plates' anterior corners | h_ant (no Panjabi table) | h_ant, 2.5 mm inside the corner, between the plates' surfaces (body.heights) | in part: endplate_depth.anterior to endplate_lower_depth.anterior, between the slabs' median heights, not the surfaces | lateral |
| Posterior height hp (six-point) | the two plates' posterior corners | h_post | h_post_inset, read as h_ant is | in part, as ha | lateral |
| Middle height hm | the plates' middle points | h_mid | h_mid | in part: the depth chords' middles, which lie on the slabs' median heights, so no concavity shows | lateral |
| Wedge ratio ha/hp (Eastell) | the four lateral corners | body_index (named, no table in the reread) | body_index_ant_post | no: the anterior and posterior corner heights are equal by construction, but for the anterior ends' offset | lateral |
| Biconcavity ratio hm/hp (Eastell) | the six points | body_index | body_index_mid_post | no, for the same reason | lateral |
| Crush ratio, hp against the neighbours' (Eastell, McCloskey) | the posterior corners of three levels | none | none; computed here from h_post_inset over its neighbours' mean (crush_index) | an analogue: the same form on the posterior wall (VBHp) of three levels, a different chord from h_post_inset | lateral |
| Wedge angle, between the plates | the four lateral corners | wedge; Panjabi's EPIt printed without a spread | wedge (body.inclinations) | no: both depth chords run along the frame's y | lateral |
| Plate inclinations | each plate's corners against the posterior wall | EPItu, EPItl (endplate_incl, endplate_lower_incl) | endplate_incl, endplate_lower_incl | no | lateral |
| Plate concavity | the plate's middle against its rim | endplate_concavity (printed without a spread) | endplate_concavity, endplate_lower_concavity | no | lateral |
| Disc heights | the facing plates' corners and middles | disc_h_ant, disc_h_mid, disc_h_post | disc_h_ant, disc_h_mid, disc_h_post | no: the plates' points lie inside the bone, at the slabs' median heights | lateral |
| Segmental angle, sagittal and coronal | a level's upper plate and the next level's | alignment | segment_sagittal, segment_coronal | yes, between the levels' plate chords (seg_sag, seg_cor) | lateral, AP |
| Canal depth | the canal's posterior and anterior walls at the midline | SCD (canal_ap) | canal_ap, canal_ap_lateral_film | yes, the label's canal: 1.4 to 4.0 mm under Panjabi's, within the other series' range at L1 to L5 | lateral |
| Canal over body (Torg and Pavlov) | the canal's walls and the body's front and back | canal_index | canal_index_torg (canal_ap over body_d_mid) | an analogue, SCD over EPDu | lateral |
| Canal width; the interpedicular distance of the AP film (Hinck 1966) | the canal's side walls; the pedicles' medial walls | SCW (canal_w); interpedicular | canal_w, read from the label's hole at 9c85de1, which closes in some planes at L5 (canal_w_ct on the CT since bordercall #78, not in these rows); interpedicular, interpedicular_max | the same chord as the engine's: 4.5 and 6.1 mm under Panjabi's SCW at L4 and L5, where every other series widens from L4 to L5 and this one does not; the interpedicular distance as an analogue | AP |
| Transverse span | the transverse processes' tips | TPW (transverse_width) | tp_span (specs.py keeps it record-only) | yes: 2.5 to 10.4 mm over Panjabi's TPW, with his T12 to L1 step (23.7 against 24.3 mm) | AP |
| Spinous length | the canal's posterior wall to the spinous tip | SPL (spinous_length) | spinous_length | no: a chord of that name, 33 to 41 mm against Panjabi's 47 to 72 and the reread's other series' medians of 48.5 to 61.6 | lateral |
| Lateral heights, right and left | each plate's right ends, each plate's left ends | h_lat (named, no table) | none | yes, but each is a chord in three dimensions with a depth part, which an AP view drops (section 2) | AP |
| Coronal wedge, right over left height | the four coronal corners | none | none | yes | AP |
| Waist width and depth (Eisenstein) | the body's mid-height outline | body_w_mid, body_d_mid | body_w_mid, body_d_mid | analogues, EPWu and EPDu | AP, lateral |
| Ratios of the chords: depth over height, depth taper, width taper, canal width over plate width, transverse span over plate width, spinous length over depth, a chord over the next level's | the chords' ends | none | none; computed here from the engine's rows (depth_over_h_post, depth_taper, width_taper, canal_w_over_width, tp_span_over_width, spinous_over_depth, h_post_over_below, depth_over_below, width_over_below, tp_span_over_below) | yes, of the chords as the engine reads them, so a ratio over the plate width carries the slab's extent | as the chords |
| Pelvic incidence, sacral slope, pelvic tilt (Legaye and Duval-Beaupere 1998) | the S1 plate's centre and normal, the two hip centres | sacrum, alignment (other) | pelvic_incidence, sacral_slope_supine, pelvic_tilt_supine (pelvis.incidence; supine, against the scanner's long axis) | no; qaloop_samples.sacral_points gives the promontory, the top of S1 and the alae, not the plate, and the pairs carry no hips | lateral |
| Femoral head centres (DeepFluoro FH-l, FH-r) | a person's points in the CT | none | the acetabulum's centre (pelvis.socket_centre) and hip_axis_width; ENHANCE.PET labels no femur | no | AP |
| The iliac crests' line (Tuffier) | each crest's highest point | none | intercristal_level, intercristal_above_l4l5 (pelvis.crests) | no | AP |
| DeepFluoro's sciatic notches, obturator foramina, pubic symphysis, anterior superior iliac spines (GSN, IOF, MOF, SPS, IPS, ASIS) | a person's points in the CT | none; the spines and the symphysis make Lewinnek's anterior pelvic plane | none | no | AP |

## 2. What projection does to each

The test, by the code in tools/annotator_measures.py (`project`). Each real pair's 3-D landmarks (levels, 18, 3, in the CT's LPS millimetres) were read with qaloop_samples.load_pair and projected through each of its frames' P. Then each person's other frames were read from the export's own metadata (its K and extrinsic, the same registration), since the pairs keep only frames within 15 degrees of either view by the export's angle and the test needs the oblique ones; the persons each set holds out (27 COBRA cases, DeepFluoro's 18-1109) are in no pair and were never read. A pair's frame read through its own P and through the export's P gave the same ratios to 8e-12 (COBRA) and 2e-13 (DeepFluoro), as two readings of one frame should. Each measure was read on the 2-D points in pixels beside its 3-D value: a ratio or an angle against its 3-D value, a length against its 3-D length times the frame's magnification at the length's middle (the focal length over the depth along the principal axis), so that 0 per cent is a length the view shows whole. The angle is the ray's from the source to the vertebra's centre, against the vertebra's own axes from its own points (z up the posterior wall, y from the canal along the upper depth chord, x their cross product): degrees off its true anteroposterior view (the ray along y) or its true lateral view (the ray along x), whichever is nearer. Only readings with every point of the measure inside the frame count: 46,084 of 226,580. The bars were written in the code before the test ran: within 15 degrees of the view a measure is read in, a ratio within 0.04 of its 3-D value at the median and 0.08 at the 90th percentile (the census's ratio error), an angle within 3 and 6 degrees, a length within 5 and 10 per cent.

What is projected is fixed points: the oracle's eighteen, each a 3-D position, carried through P. No image is read. A reader marks the extreme of an outline on the image instead, the plate's lateral edge or its front, and as the view turns that extreme moves round the rim. So the off-view figures below describe the fixed points, not a reader's marks. Modelled as an ellipse of Panjabi's L3 width and depth (44.1 and 35.2 mm), a plate turned off the view reads as follows. At 15, 30 and 45 degrees, the fixed points' width reads 3.4, 13.4 and 29.3 per cent short. The outline's width, in an AP view, reads 1.2, 4.6 and 9.5 per cent short. The outline's depth, in a lateral view, reads 1.9, 6.9 and 13.3 per cent long, since the turned plate shows some of its greater width. That is a model, not a measurement. It says that within 15 degrees the two readings differ by about 2 per cent and past 25 degrees they differ in sign for a depth. The tips (the transverse and spinous processes) and the posterior wall's ends are nearer to fixed points than a plate's rim is.

The sources are tabled apart. DeepFluoro's three specimens lie a median 32 degrees tilted against the scanner by their vertebrae's own frames, which the test cannot tell from a frame the oracle tilted, so their angles off the view are in doubt (ANGLES_IN_DOUBT in the code). Their readings are left out of the binned agreement, the verdicts and the census's errors, and shown on their own below. Every figure in the table is COBRA's: 66 cases, 309 read vertebrae.

Median absolute agreement by degrees off the vertebra's own view, in the view the measure is read in (the count of readings in brackets), the median and 90th percentile within 15 degrees, the correlation across persons of the 2-D reading (a length divided by its magnification) with the 3-D value within each level, and the verdict:

| Measure | Kind | View | Persons | 0-5 | 5-10 | 10-15 | 15-25 | 25-35 | 35+ | Within 15: median, p90 | r within level | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EPWu | length | ap | 24 | 0.1% (10) | 0.4% (33) | 1.4% (50) | 3.1% (149) | 8.6% (207) | 16.6% (278) | 0.6%, 2.0% | 1.00 | survives |
| EPWl | length | ap | 39 | 0.1% (19) | 0.4% (58) | 1.3% (87) | 3.5% (269) | 9.3% (327) | 18.0% (433) | 0.6%, 2.0% | 1.00 | survives |
| EPDu | length | lat | 42 | 0.0% (38) | 0.2% (109) | 1.5% (108) | 4.3% (179) | 11.1% (184) | 20.2% (203) | 0.4%, 2.2% | 1.00 | survives |
| EPDl | length | lat | 57 | 0.0% (51) | 0.2% (174) | 1.4% (199) | 4.4% (296) | 10.8% (296) | 20.3% (334) | 0.4%, 2.2% | 1.00 | survives |
| VBHp | length | lat | 43 | 0.2% (38) | 0.2% (114) | 0.4% (113) | 0.6% (183) | 1.0% (188) | 2.3% (208) | 0.3%, 1.1% | 1.00 | survives |
| SCW | length | ap | 31 | 0.1% (14) | 0.4% (46) | 1.3% (71) | 3.3% (220) | 9.2% (264) | 18.1% (327) | 0.6%, 2.1% | 1.00 | survives |
| SCD | length | lat | 44 | 0.1% (44) | 0.2% (137) | 1.4% (140) | 4.5% (226) | 11.3% (229) | 20.8% (252) | 0.5%, 2.2% | 1.00 | survives |
| TPW | length | ap | 27 | 0.1% (10) | 0.3% (32) | 1.2% (52) | 3.0% (172) | 8.6% (201) | 17.6% (261) | 0.5%, 2.1% | 1.00 | survives |
| SPL | length | lat | 43 | 0.7% (34) | 0.3% (122) | 1.5% (118) | 3.7% (183) | 9.2% (195) | 19.4% (240) | 0.6%, 4.0% | 1.00 | survives |
| ha | length | lat | 48 | 0.2% (40) | 0.3% (122) | 0.5% (127) | 0.5% (204) | 0.9% (209) | 1.6% (236) | 0.4%, 2.2% | 0.96 | survives |
| hp | length | lat | 43 | 0.3% (39) | 0.3% (117) | 0.4% (118) | 0.5% (189) | 0.9% (194) | 2.0% (210) | 0.3%, 2.4% | 0.95 | survives |
| hm | length | lat | 42 | 0.3% (38) | 0.3% (109) | 0.4% (108) | 0.5% (179) | 0.8% (184) | 1.6% (197) | 0.3%, 2.5% | 0.95 | survives |
| hl | length | ap | 24 | 2.8% (10) | 3.6% (33) | 4.5% (49) | 4.7% (149) | 7.0% (206) | 9.3% (278) | 4.2%, 11.2% | 0.92 | does not survive |
| ha/hp | ratio | lat | 42 | 0.001 (38) | 0.002 (109) | 0.005 (108) | 0.009 (179) | 0.016 (184) | 0.022 (197) | 0.002, 0.007 | 0.99 | survives |
| hm/hp | ratio | lat | 42 | 0.001 (38) | 0.001 (109) | 0.002 (108) | 0.005 (179) | 0.008 (184) | 0.011 (197) | 0.001, 0.004 | 0.95 | survives |
| crush | ratio | lat | 7 | 0.001 (6) | 0.002 (15) | 0.002 (13) | 0.004 (20) | 0.008 (21) | 0.018 (18) | 0.002, 0.008 | 1.00 | survives |
| EPDu/VBHp | ratio | lat | 42 | 0.004 (38) | 0.005 (108) | 0.018 (105) | 0.045 (175) | 0.120 (181) | 0.221 (197) | 0.007, 0.027 | 1.00 | survives |
| EPDl/EPDu | ratio | lat | 42 | 0.001 (38) | 0.001 (109) | 0.002 (108) | 0.002 (179) | 0.002 (184) | 0.002 (197) | 0.001, 0.006 | 1.00 | survives |
| SCD/EPDu | ratio | lat | 42 | 0.001 (38) | 0.002 (107) | 0.004 (106) | 0.007 (179) | 0.011 (183) | 0.014 (199) | 0.002, 0.006 | 1.00 | survives |
| SPL/EPDu | ratio | lat | 41 | 0.009 (29) | 0.005 (91) | 0.015 (88) | 0.030 (141) | 0.063 (154) | 0.094 (184) | 0.009, 0.052 | 1.00 | survives |
| VBHp/below | ratio | lat | 16 | 0.007 (16) | 0.004 (39) | 0.007 (47) | 0.009 (60) | 0.017 (69) | 0.025 (63) | 0.006, 0.016 | 1.00 | survives |
| EPDu/below | ratio | lat | 20 | 0.003 (17) | 0.003 (43) | 0.009 (52) | 0.017 (73) | 0.029 (76) | 0.044 (74) | 0.005, 0.027 | 0.96 | survives |
| EPWl/EPWu | ratio | ap | 24 | 0.006 (10) | 0.008 (33) | 0.008 (49) | 0.008 (149) | 0.008 (206) | 0.006 (278) | 0.008, 0.012 | 1.00 | survives |
| SCW/EPWu | ratio | ap | 24 | 0.008 (10) | 0.009 (33) | 0.008 (50) | 0.007 (149) | 0.006 (206) | 0.004 (261) | 0.008, 0.010 | 0.99 | survives |
| TPW/EPWu | ratio | ap | 23 | 0.040 (8) | 0.045 (25) | 0.044 (39) | 0.043 (128) | 0.039 (171) | 0.026 (232) | 0.044, 0.058 | 0.99 | does not survive |
| hl/EPWu | ratio | ap | 24 | 0.014 (10) | 0.019 (33) | 0.022 (49) | 0.018 (149) | 0.050 (206) | 0.101 (278) | 0.019, 0.052 | 0.96 | survives |
| hlR/hlL | ratio | ap | 24 | 0.002 (10) | 0.004 (33) | 0.008 (49) | 0.014 (149) | 0.025 (206) | 0.044 (278) | 0.005, 0.019 | 1.00 | survives |
| EPWu/below | ratio | ap | 18 | 0.008 (6) | 0.012 (28) | 0.007 (36) | 0.011 (79) | 0.019 (78) | 0.032 (75) | 0.009, 0.025 | 1.00 | survives |
| TPW/below | ratio | ap | 23 | 0.007 (6) | 0.005 (26) | 0.007 (38) | 0.013 (104) | 0.021 (90) | 0.034 (88) | 0.006, 0.017 | 0.99 | survives |
| seg_sag | angle | lat | 18 | 0.1 deg (17) | 0.3 deg (42) | 0.6 deg (49) | 1.2 deg (69) | 2.2 deg (73) | 4.8 deg (68) | 0.4 deg, 1.2 deg | 1.00 | survives |
| seg_cor | angle | ap | 17 | 0.1 deg (6) | 0.3 deg (26) | 0.4 deg (31) | 0.7 deg (74) | 1.2 deg (75) | 1.9 deg (73) | 0.3 deg, 1.0 deg | 1.00 | survives |

What the numbers say:

- A length that lies across the turn is read short by about what the turn takes out of the image plane, and the angle is what matters. Within 5 degrees every length is read whole to 0.1 to 0.7 per cent; by 25 to 35 degrees the widths and depths lose 8.6 to 11.3 per cent, and by 35 to 60 degrees 16.6 to 20.8. The heights, which stand along the column, lose 1 to 2 per cent at 35 to 60 degrees, since a turn about the long axis leaves a vertical chord in the image plane. The signed medians run the same way (a reading is short, never long), so this is foreshortening and not noise.
- In the other view a chord across the ray is all but gone: within 15 degrees of the lateral, the widths read 83 to 84 per cent short, and within 15 degrees of the anteroposterior, the depths 82 to 83 (the second table of the job's report). The heights read whole in either view (VBHp 0.4 per cent in an anteroposterior frame), though only the lateral view shows the posterior wall as an edge.
- A ratio of two chords that lie the same way keeps its value at any angle, since both foreshorten alike: the depth taper EPDl/EPDu by 0.002 from 0 to 60 degrees, the width taper by 0.008, the canal over the body SCD/EPDu by 0.014 at worst. A ratio of chords that lie different ways (depth over height, EPDu/VBHp) holds within 15 degrees (0.007) and falls apart past 25 (0.120, then 0.221).
- Two measures fail their bars, and the geometry says why. The lateral heights an anteroposterior reader takes from the eighteen points (hl) read 4.2 per cent short within 15 degrees, signed, because the upper and the lower plate's lateral ends lie at different depths (each at its own slab's median depth), so the 3-D chord has a part along the ray; it is a property of the construction, not of the view, and a reader's lateral height, an edge on the image, would not have it. The transverse span over the plate's width (TPW/EPWu) varies by 0.044 within 15 degrees with a signed median of 0.004, about 2.5 per cent of a ratio whose gold tier means run 1.63 to 1.87 from L1 to L5: the transverse processes lie behind the plate's points along an anteroposterior ray, so the two chords' magnifications differ, the sign set by which side the source is on, and that spread is past the census's 0.04.
- DeepFluoro, on its own: none of its 1,703 in-frame pair readings and 3 of its 446 export readings lie within 15 degrees of the vertebra's own view (5th, 50th and 95th percentiles 27, 43 and 59 degrees for the pair frames). Its six read vertebrae have their long axes 13, 32 and 44 degrees (the same percentiles) off the scanner's and their left-right axes 8, 18 and 39 degrees off the scanner's, where COBRA's 309 have 2, 12 and 35 and 1, 5 and 18. Its widths read within 0.5 to 1.4 per cent at 25 to 60 degrees off the vertebra's anteroposterior view (12 to 118 readings), where COBRA's lose 8.6 to 18.1 per cent. That fits a tilt about the vertebra's own left-right axis, which leaves a left-right chord in the image plane, where COBRA's oblique frames are the gantry's turn about the long axis, which does not. Pooled, its readings would dilute the off-view figures: EPWu at 35 to 60 degrees reads 16.6 per cent short on COBRA, 13.4 pooled and 1.2 on DeepFluoro alone; EPWl 18.0, 14.9 and 1.3; TPW 17.6, 16.6 and 1.4 (the job's pooling table). Whether the specimens' lumbar columns lie that bent in the scanner or the oracle's frame (the column's line through the neighbours' centroids, here on a CT that cuts the lumbar spine) is tilted, the test cannot say; the realx pairs' first check, the landmarks inside the export's boxes, says nothing of a frame's tilt.
- The magnification a frame does not state. A pair's frame is its export frame brought to 512 pixels, and an export frame keeps its own side (DeepFluoro's 384, COBRA's 517), so each magnification is taken per pixel of its own canvas's side. Across in-frame readings its logarithm then has an SD of 0.022 on COBRA (a fixed gantry; the 5th percentile 0.93 of the 95th) and 0.065 on DeepFluoro (a C-arm; 0.83), the pair frames 0.061 and the export's 0.081 apart. Pooled in each canvas's raw pixels, as the first version of this note did, DeepFluoro's reads 0.133, which is the two canvases' 512 over 384 and not geometry. A length read in pixels on an uncalibrated C-arm frame therefore carries a scale unknown to about 6.5 per cent (its log SD), and a ratio carries none; section 3 puts that into the census.

## 3. How much each tells the Bayes rule

The census (bordercall schwingcheck/census.py, the owner's ask of 29 October): the information a measure gives a lone body about its level is the mean log posterior at the truth plus log K. The bodies are drawn from the table's mean and spread at each level, with the person's size log-normal (SD 0.07) and integrated out, and each measure is read with its error (1 mm, 0.04 for a ratio, 3 degrees). It is run here over the six lumbar names a lumbar frame shows, T12 to L5, at most log 6 = 1.79 nats, with 2,000 bodies a level.

Three populations, never pooled:

- Panjabi's table cut to those levels.
- The gold tier's ENHANCE.PET persons. One study a person, as the covariates' join chose it: 1,445 chosen, 867 autoPET and 578 of the members the join names enhance_pet. Of those, bordercall's count calls 1,348 T12L5, 62 T12L6 and 35 T12L4, and only the 1,348 are kept, 1,343 of them with rows. In a column of twelve thoracic and five lumbar vertebrae the six names are the bodies they mean, and L5's neighbour below is the sacrum; a person with six lumbar vertebrae would put a non-terminal L5 in the L5 cells, and one with four would put the sacrum's neighbour in the L4 cells. The per-level means, SDs and counts are computed from the engine's rows (cells of 5 or more). The ratios against the level below run T12 to L4 and are ranked as a group of their own.
- The same gold table as read on an X-ray, within 15 degrees of each measure's view. Each measure's error is widened by what section 2 measured for its stand-in there (the bias and the robust SD, in quadrature with the census's error; for a length, the relative error times its mean). This credits the X-ray with each frame's magnification, as the projection test divides by it. So the same table is also read on a frame whose magnification is unknown: every length of a body is then read times one unknown factor, as an unknown size is, so the census's size spread is widened in quadrature by the source's measured spread (0.022 for COBRA, 0.065 for DeepFluoro's C-arm). A ratio or an angle, of power 0 in the size, is untouched. One shared factor is exact for a measure alone and slightly optimistic for an anteroposterior and a lateral length together, whose two frames would each have their own.

The census assumes the measures independent given the level and the size, so what a ratio adds after its parts is an upper bound; the correlation table (Pearson within each level, 30 persons or more) names the pairs that share. The plate widths and the canal width are the slab's extents at 9c85de1 (section 1), so every measure built on them (endplate, endplate_lower, canal_w, width_taper, canal_w_over_width, tp_span_over_width, width_over_below) carries what the label fused to the plate's edge, most of it at L5.

Panjabi, T12 to L5 (the measures the eighteen points or a lateral reader's corners make, under his names; "named alone" is the share of bodies the measure alone names right, a sixth by chance). His SPL is not the eighteen points' spinous chord (section 1):

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

The gold tier on the CT, T12 to L5, the greedy order (what each adds after those above it; a measure whose gain is under a tenth of its own is listed as repeating the one it shares most with, with the pair's redundancy in nats):

| # | Measure | Alone, mean nats | Named alone | Adds, nats | Repeats |
|---|---|---|---|---|---|
| 1 | tp_span | 0.542 | 0.43 | 0.542 |  |
| 2 | h_post | 0.137 | 0.28 | 0.162 |  |
| 3 | tp_span_over_width | 0.447 | 0.41 | 0.124 |  |
| 4 | endplate_lower_incl | 0.224 | 0.31 | 0.096 |  |
| 5 | body_w_mid | 0.193 | 0.31 | 0.064 |  |
| 6 | canal_w_over_width | 0.132 | 0.27 | 0.051 |  |
| 7 | canal_ap | 0.065 | 0.24 | 0.041 |  |
| 8 | spinous_length | 0.169 | 0.29 | 0.041 |  |
| 9 | body_index_ant_post | 0.189 | 0.30 | 0.031 |  |
| 10 | canal_w | 0.079 | 0.25 | 0.026 |  |
| 11 | canal_index_torg | 0.078 | 0.24 | 0.023 |  |
| 12 | endplate | 0.122 | 0.26 | 0.021 |  |
| 13 | wedge | 0.152 | 0.29 | 0.018 |  |
| 14 | endplate_lower_concavity | 0.132 | 0.27 | 0.016 |  |
| 15 | canal_ap_over_depth | 0.082 | 0.25 | 0.014 |  |
| 16 | spinous_over_depth | 0.102 | 0.26 | 0.013 |  |
| 17 | width_taper | 0.099 | 0.26 | 0.011 |  |
| 18 | body_index_mid_post | 0.134 | 0.27 | 0.010 | endplate_lower_incl (0.053) |
| 19 | interpedicular | 0.083 | 0.25 | 0.009 |  |
| 20 | endplate_lower | 0.101 | 0.26 | 0.009 | tp_span (0.073) |
| 21 | h_post_inset | 0.061 | 0.24 | 0.009 |  |
| 22 | depth_over_h_post | 0.100 | 0.26 | 0.006 | endplate_lower_incl (0.037) |
| 23 | h_ant | 0.090 | 0.26 | 0.005 | tp_span (0.084) |
| 24 | depth_taper | 0.055 | 0.22 | 0.004 | endplate_lower_incl (0.019) |
| 25 | h_mid | 0.045 | 0.23 | 0.002 | tp_span (0.035) |
| 26 | endplate_incl | 0.025 | 0.22 | 0.002 | endplate_lower_incl (0.009) |
| 27 | endplate_lower_depth | 0.030 | 0.21 | 0.002 | tp_span (0.019) |
| 28 | endplate_depth | 0.025 | 0.21 | 0.001 | spinous_length (0.011) |
| 29 | body_d_mid | 0.025 | 0.21 | 0.001 | tp_span (0.016) |
| 30 | endplate_concavity | 0.044 | 0.22 | 0.000 | endplate_lower_incl (0.021) |

Shared by correlation (median |r| of 0.7 or more over the six levels): body_index_ant_post and wedge (0.89), body_d_mid and endplate_depth (0.82), depth_over_h_post and endplate_depth (0.82), canal_ap_over_depth and endplate_depth (0.79), body_w_mid and endplate_lower (0.79), canal_w and interpedicular (0.77), body_d_mid and endplate_lower_depth (0.76), endplate_depth and endplate_lower_depth (0.74), endplate and endplate_lower (0.71).

The gold tier on the CT, the measures against the level below (and the crush index, which needs both neighbours), T12 to L4, at most 1.61 nats:

| # | Measure | Alone, mean nats | Named alone | Adds, nats | Repeats |
|---|---|---|---|---|---|
| 1 | tp_span_over_below | 0.508 | 0.50 | 0.508 |  |
| 2 | h_post_over_below | 0.249 | 0.38 | 0.199 |  |
| 3 | depth_over_below | 0.135 | 0.32 | 0.064 |  |
| 4 | width_over_below | 0.102 | 0.31 | 0.051 |  |
| 5 | disc_h_ant | 0.079 | 0.30 | 0.025 |  |
| 6 | segment_sagittal | 0.059 | 0.28 | 0.016 |  |
| 7 | disc_h_post | 0.055 | 0.28 | 0.014 |  |
| 8 | crush_index | 0.021 | 0.24 | 0.007 |  |
| 9 | segment_coronal | 0.012 | 0.24 | 0.004 |  |

Why the leaders lead, from the same tables (the gold tier's means and SDs, and the census's nats at each level, with the share it names alone):

- T12 by the transverse span: 51.4 mm (SD 5.5) against 75.1 (8.4) at L1, so it tells 1.57 nats at T12 and names 93 per cent of T12's bodies alone, against 0.21 to 0.51 nats at L1 to L5. Panjabi's TPW and SPL do the same at T12 (1.55 and 1.48 nats).
- L5 by its shape: its posterior height is 23.7 mm (2.9) against 28.3 (2.7) at L4, 0.51 nats at L5. Its lower plate's inclination is 15.6 degrees (7.3) against 7.2 (6.3), 0.70 nats. Its wedge ratio is 1.15 (0.13) against 1.04 (0.11), 0.52 nats, and its wedge angle 8.7 degrees (8.5) against 2.1 (6.8), 0.44 nats.
- The posterior height over the next level's is 1.22 (0.18) at L4 against 0.95 to 1.03 above it (0.66 nats at L4), which is L5's short back seen from L4.
- The middle levels are told least: at L2 to L4 the transverse span tells 0.21 to 0.32 nats alone and the posterior height 0.03 to 0.11, which is where a count needs its anchor.

The chords against Panjabi and the other papers. The census read the clinical reread's series of the same keys at T12 to L5: the values each paper measured itself, no quoted value, figure's example or pig cohort, a series being one paper's cohort, technique and sex. In the table, "others" is their median, least and most, with the count of series:

| Chord | Gold less Panjabi, T12 to L4 | At L5 | Gold, Panjabi and others at L5 | Reading |
|---|---|---|---|---|
| endplate (EPWu) | +5.0 to +7.4 | +9.3 | 56.6; 47.3; 48.8 (41.6 to 54.0, 7) | the slab's extent: over Panjabi and over every other series' median at every level, most at L5 |
| endplate_lower (EPWl) | +5.7 to +6.3 | +8.2 | 57.6; 49.4; 47.4 (43.7 to 52.4, 6) | the same |
| endplate_depth (EPDu) | -0.6 to +0.5 | -0.9 | 33.8; 34.7; 34.1 (27.5 to 36.7, 7) | Panjabi's chord |
| h_post (VBHp) | +4.2 to +5.3 | +0.7 | 23.6; 22.9; 24.4 (20.0 to 25.7, 6) | over Panjabi above L5; inside the others' range at every level but L4 (28.3 against their 21.6 to 28.0) |
| canal_w (SCW) | -0.4 to -4.5 | -6.1 | 21.0; 27.1; 27.1 (23.4 to 34.9, 12) | the label's hole: does not widen from L4 to L5, where all 12 other series widen by 2.0 to 6.2 mm |
| canal_ap (SCD) | -1.4 to -3.0 | -4.0 | 15.7; 19.7; 16.3 (11.4 to 18.9, 15) | under Panjabi, inside the others' range at L1 to L5 |
| spinous_length (SPL) | -13.8 to -31.5 | -34.9 | 33.4; 68.3; 55.0 (50.6 to 59.5, 2) | another chord |
| tp_span (TPW) | +3.9 to +10.4 | +2.5 | 95.0; 92.5; 78.6 (71.3 to 85.9, 2) | over Panjabi, but with his T12 to L1 step: +23.7 against +24.3 mm |

The steps the ranking leans on, series by series (mm, the later level less the earlier). L5 less L4 of the posterior height: the gold tier -4.7, Panjabi -1.2, and the reread's six human series that print both all negative: bonczar2024 (a pooled meta-analysis) -1.7, busscher2010 (male cadavers, CT) -3.1, frontphys2026 (100 CTs, Zhengzhou) -1.7, gilad1985 (lateral films, men) -1.4, moncadahabib2025 (37 CTs, Mexico) -2.5, tan2004 (10 cadavers, a contact digitiser) -1.6. L1 less T12 of the transverse span: the gold tier +23.7, Panjabi +24.3, Tan 2004 +12.6, the one other series that prints both.

Each measure alone, on the CT and as read on an X-ray within 15 degrees of its view, from the same draws so that the difference is the X-ray's alone (mean nats over its levels with the standard error of the mean). "Known" means the frame's magnification is known. The last four columns read the frame with its magnification unknown by COBRA's and by DeepFluoro's spread:

| Measure | Kind | Levels | Error, CT | Error, X-ray | Alone, CT | Known | Cost | Unknown, cobra | Cost | Unknown, deepfluoro | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tp_span | length | T12 to L5 | 1 | 1.22 | 0.543 +- 0.005 | 0.541 +- 0.005 | 0.001 | 0.535 | 0.008 | 0.488 | 0.055 |
| tp_span_over_below | ratio | T12 to L4 | 0.04 | 0.0409 | 0.526 +- 0.006 | 0.523 +- 0.006 | 0.003 | 0.523 | 0.003 | 0.523 | 0.003 |
| h_post_over_below | ratio | T12 to L4 | 0.04 | 0.0405 | 0.242 +- 0.006 | 0.242 +- 0.006 | 0.001 | 0.242 | 0.001 | 0.242 | 0.001 |
| endplate_lower_incl | angle | T12 to L5 | 3 | 3.05 | 0.225 +- 0.005 | 0.224 +- 0.005 | 0.001 | 0.224 | 0.001 | 0.224 | 0.001 |
| body_index_ant_post | ratio | T12 to L5 | 0.04 | 0.0401 | 0.189 +- 0.005 | 0.189 +- 0.005 | 0.000 | 0.189 | 0.000 | 0.189 | 0.000 |
| body_w_mid | length | T12 to L5 | 1 | 1.08 | 0.186 +- 0.005 | 0.185 +- 0.005 | 0.001 | 0.182 | 0.005 | 0.156 | 0.030 |
| spinous_length | length | T12 to L5 | 1 | 1.08 | 0.170 +- 0.005 | 0.169 +- 0.005 | 0.001 | 0.165 | 0.005 | 0.140 | 0.030 |
| wedge | angle | T12 to L5 | 3 | 3.05 | 0.156 +- 0.004 | 0.156 +- 0.004 | 0.001 | 0.156 | 0.001 | 0.156 | 0.001 |
| depth_over_below | ratio | T12 to L4 | 0.04 | 0.0408 | 0.143 +- 0.005 | 0.142 +- 0.005 | 0.000 | 0.142 | 0.000 | 0.142 | 0.000 |
| h_post | length | T12 to L5 | 1 | 1.01 | 0.139 +- 0.004 | 0.139 +- 0.004 | 0.000 | 0.136 | 0.004 | 0.113 | 0.026 |
| body_index_mid_post | ratio | T12 to L5 | 0.04 | 0.04 | 0.132 +- 0.004 | 0.132 +- 0.004 | 0.000 | 0.132 | 0.000 | 0.132 | 0.000 |
| endplate | length | T12 to L5 | 1 | 1.12 | 0.127 +- 0.004 | 0.127 +- 0.004 | 0.001 | 0.124 | 0.003 | 0.106 | 0.021 |
| canal_w_over_width | ratio | T12 to L5 | 0.04 | 0.0409 | 0.126 +- 0.004 | 0.125 +- 0.004 | 0.001 | 0.125 | 0.001 | 0.125 | 0.001 |
| width_over_below | ratio | T12 to L4 | 0.04 | 0.0423 | 0.106 +- 0.004 | 0.103 +- 0.004 | 0.003 | 0.103 | 0.003 | 0.103 | 0.003 |
| endplate_lower | length | T12 to L5 | 1 | 1.12 | 0.104 +- 0.004 | 0.104 +- 0.004 | 0.000 | 0.101 | 0.003 | 0.084 | 0.020 |
| spinous_over_depth | ratio | T12 to L5 | 0.04 | 0.0427 | 0.102 +- 0.004 | 0.101 +- 0.004 | 0.001 | 0.101 | 0.001 | 0.101 | 0.001 |
| depth_over_h_post | ratio | T12 to L5 | 0.04 | 0.0417 | 0.101 +- 0.004 | 0.101 +- 0.004 | 0.000 | 0.101 | 0.000 | 0.101 | 0.000 |
| width_taper | ratio | T12 to L5 | 0.04 | 0.0415 | 0.100 +- 0.004 | 0.099 +- 0.004 | 0.002 | 0.099 | 0.002 | 0.099 | 0.002 |
| h_ant | length | T12 to L5 | 1 | 1.02 | 0.090 +- 0.003 | 0.090 +- 0.003 | 0.000 | 0.088 | 0.003 | 0.073 | 0.018 |
| canal_ap_over_depth | ratio | T12 to L5 | 0.04 | 0.0402 | 0.087 +- 0.003 | 0.087 +- 0.003 | 0.000 | 0.087 | 0.000 | 0.087 | 0.000 |
| canal_index_torg | ratio | T12 to L5 | 0.04 | 0.0402 | 0.082 +- 0.003 | 0.082 +- 0.003 | 0.000 | 0.082 | 0.000 | 0.082 | 0.000 |
| interpedicular | length | T12 to L5 | 1 | 1.02 | 0.081 +- 0.003 | 0.081 +- 0.003 | 0.000 | 0.079 | 0.002 | 0.068 | 0.013 |
| canal_w | length | T12 to L5 | 1 | 1.02 | 0.077 +- 0.003 | 0.077 +- 0.003 | 0.000 | 0.075 | 0.002 | 0.064 | 0.013 |
| h_post_inset | length | T12 to L5 | 1 | 1.02 | 0.071 +- 0.003 | 0.071 +- 0.003 | 0.000 | 0.069 | 0.002 | 0.056 | 0.015 |
| canal_ap | length | T12 to L5 | 1 | 1.01 | 0.062 +- 0.003 | 0.062 +- 0.003 | 0.000 | 0.061 | 0.002 | 0.052 | 0.010 |
| segment_sagittal | angle | T12 to L4 | 3 | 3.05 | 0.056 +- 0.003 | 0.055 +- 0.003 | 0.000 | 0.055 | 0.000 | 0.055 | 0.000 |
| depth_taper | ratio | T12 to L5 | 0.04 | 0.04 | 0.047 +- 0.003 | 0.047 +- 0.003 | 0.000 | 0.047 | 0.000 | 0.047 | 0.000 |
| h_mid | length | T12 to L5 | 1 | 1.01 | 0.043 +- 0.002 | 0.043 +- 0.002 | 0.000 | 0.042 | 0.001 | 0.034 | 0.009 |
| endplate_incl | angle | T12 to L5 | 3 | 3.05 | 0.028 +- 0.002 | 0.028 +- 0.002 | 0.000 | 0.028 | 0.000 | 0.028 | 0.000 |
| endplate_lower_depth | length | T12 to L5 | 1 | 1.04 | 0.026 +- 0.002 | 0.026 +- 0.002 | 0.000 | 0.026 | 0.001 | 0.021 | 0.005 |
| body_d_mid | length | T12 to L5 | 1 | 1.03 | 0.026 +- 0.002 | 0.026 +- 0.002 | 0.000 | 0.025 | 0.001 | 0.022 | 0.004 |
| endplate_depth | length | T12 to L5 | 1 | 1.03 | 0.023 +- 0.002 | 0.023 +- 0.002 | 0.000 | 0.022 | 0.000 | 0.019 | 0.004 |
| crush_index | ratio | T12 to L4 | 0.04 | 0.0401 | 0.022 +- 0.002 | 0.022 +- 0.002 | 0.000 | 0.022 | 0.000 | 0.022 | 0.000 |
| segment_coronal | angle | T12 to L4 | 3 | 3.04 | 0.013 +- 0.002 | 0.013 +- 0.002 | 0.000 | 0.013 | 0.000 | 0.013 | 0.000 |

Read with the magnification known, no measure that passes its bar and has a stand-in loses more than 0.003 nats. Read with the C-arm's unknown magnification, the lengths lose 0.004 to 0.055 nats and the ratios and angles at most 0.003; on COBRA's fixed gantry the lengths lose at most 0.008. The greedy order on an X-ray of known magnification keeps the CT's leaders: tp_span 0.544, h_post 0.163 added, endplate_lower_incl 0.104, body_w_mid 0.062. On a frame of the C-arm's unknown magnification it is tp_span 0.489, h_post 0.191 added, endplate_lower_incl 0.105, canal_ap 0.067 and body_w_mid 0.061. Left out of these X-ray runs are tp_span_over_width, for failing its bar, and the discs and the concavities, for having no stand-in among the eighteen points. In them on borrowed errors are the wedge, the inclinations and the six-point ratios read their X-ray errors from stand-ins (the segmental angle; the slab-centre heights) that cannot show a wedge, so their X-ray figures say what the view does to a line of that direction, not to the wedge itself.

Each measure alone as read at each angle off its view, the frame's magnification known (500 bodies a level, so the CT's figure here differs a little from the tables above; mean nats, the CT's first; a bin with under 20 COBRA readings left out). Every gold measure with a stand-in is listed, tp_span_over_width among them, which fails its bar within 15 degrees and loses 0.016 and 0.028 nats there:

| Measure | Stand-in | View | CT | 0-5 | 5-10 | 10-15 | 15-25 | 25-35 | 35-60 |
|---|---|---|---|---|---|---|---|---|---|
| tp_span | TPW (same) | ap | 0.553 | - | 0.552 | 0.549 | 0.525 | 0.411 | 0.251 |
| tp_span_over_below | TPW/below (same) | ap | 0.500 | - | 0.497 | 0.496 | 0.486 | 0.466 | 0.407 |
| tp_span_over_width | TPW/EPWu (same) | ap | 0.448 | - | 0.432 | 0.420 | 0.433 | 0.423 | 0.437 |
| h_post_over_below | VBHp/below (same) | lat | 0.248 | - | 0.248 | 0.247 | 0.245 | 0.241 | 0.229 |
| endplate_lower_incl | seg_sag (analogue) | lat | 0.225 | - | 0.225 | 0.223 | 0.215 | 0.200 | 0.132 |
| body_index_ant_post | ha/hp (analogue) | lat | 0.188 | 0.187 | 0.187 | 0.187 | 0.185 | 0.181 | 0.174 |
| body_w_mid | EPWu (analogue) | ap | 0.179 | - | 0.179 | 0.178 | 0.169 | 0.130 | 0.083 |
| spinous_length | SPL (same) | lat | 0.170 | 0.169 | 0.170 | 0.165 | 0.148 | 0.102 | 0.050 |
| wedge | seg_sag (analogue) | lat | 0.153 | - | 0.152 | 0.151 | 0.145 | 0.133 | 0.081 |
| canal_w_over_width | SCW/EPWu (same) | ap | 0.146 | - | 0.144 | 0.144 | 0.144 | 0.144 | 0.145 |
| body_index_mid_post | hm/hp (analogue) | lat | 0.145 | 0.145 | 0.145 | 0.145 | 0.145 | 0.143 | 0.142 |
| h_post | VBHp (same) | lat | 0.138 | 0.138 | 0.138 | 0.137 | 0.137 | 0.134 | 0.124 |
| depth_over_below | EPDu/below (same) | lat | 0.119 | - | 0.119 | 0.118 | 0.116 | 0.109 | 0.090 |
| spinous_over_depth | SPL/EPDu (same) | lat | 0.116 | 0.115 | 0.116 | 0.114 | 0.109 | 0.087 | 0.068 |
| width_over_below | EPWu/below (same) | ap | 0.110 | - | 0.107 | 0.109 | 0.107 | 0.101 | 0.089 |
| depth_over_h_post | EPDu/VBHp (same) | lat | 0.101 | 0.101 | 0.101 | 0.100 | 0.096 | 0.077 | 0.050 |
| endplate_lower | EPWl (same) | ap | 0.100 | - | 0.100 | 0.098 | 0.088 | 0.056 | 0.029 |
| endplate | EPWu (same) | ap | 0.099 | - | 0.099 | 0.098 | 0.092 | 0.067 | 0.040 |
| width_taper | EPWl/EPWu (same) | ap | 0.097 | - | 0.096 | 0.096 | 0.095 | 0.095 | 0.096 |
| h_ant | ha (analogue) | lat | 0.097 | 0.097 | 0.097 | 0.096 | 0.096 | 0.094 | 0.091 |
| canal_ap_over_depth | SCD/EPDu (same) | lat | 0.083 | 0.083 | 0.083 | 0.083 | 0.082 | 0.081 | 0.079 |
| interpedicular | SCW (analogue) | ap | 0.082 | - | 0.082 | 0.081 | 0.074 | 0.049 | 0.024 |
| canal_index_torg | SCD/EPDu (analogue) | lat | 0.079 | 0.079 | 0.079 | 0.078 | 0.078 | 0.077 | 0.075 |
| h_post_inset | hp (analogue) | lat | 0.061 | 0.061 | 0.061 | 0.061 | 0.061 | 0.060 | 0.057 |
| canal_w | SCW (same) | ap | 0.060 | - | 0.060 | 0.059 | 0.052 | 0.029 | 0.010 |
| segment_sagittal | seg_sag (same) | lat | 0.060 | - | 0.060 | 0.059 | 0.055 | 0.049 | 0.026 |
| depth_taper | EPDl/EPDu (same) | lat | 0.059 | 0.059 | 0.059 | 0.059 | 0.059 | 0.059 | 0.059 |
| canal_ap | SCD (same) | lat | 0.056 | 0.056 | 0.056 | 0.055 | 0.050 | 0.033 | 0.016 |
| h_mid | hm (analogue) | lat | 0.044 | 0.044 | 0.044 | 0.044 | 0.044 | 0.043 | 0.042 |
| endplate_lower_depth | EPDl (same) | lat | 0.037 | 0.037 | 0.037 | 0.037 | 0.033 | 0.022 | 0.010 |
| body_d_mid | EPDu (analogue) | lat | 0.033 | 0.033 | 0.033 | 0.032 | 0.028 | 0.017 | 0.007 |
| endplate_incl | seg_sag (analogue) | lat | 0.027 | - | 0.027 | 0.027 | 0.025 | 0.023 | 0.013 |
| crush_index | crush (analogue) | lat | 0.023 | - | - | - | 0.023 | 0.022 | - |
| endplate_depth | EPDu (same) | lat | 0.021 | 0.021 | 0.021 | 0.021 | 0.019 | 0.013 | 0.007 |
| segment_coronal | seg_cor (same) | ap | 0.004 | - | 0.004 | 0.004 | 0.004 | 0.003 | 0.002 |

So the measures a landmark net should place first, for naming, are the ones that tell most and survive the view:

- the transverse processes' tips, for T12 against L1;
- the posterior wall's two ends and the four lateral corners, for L5's short back and its wedge, read as ratios that hold at any angle and need no magnification;
- the lower plate's line, for its inclination.

On an oblique or uncalibrated frame, the ratios of chords that lie the same way lose almost nothing, where the lengths across the turn lose half or more of their information past 35 degrees and every length a tenth to a fifth of it to the C-arm's unknown magnification.

The crests' line and the pelvis (the gold tier's pelvis rows, one value a person, the typical columns). The line crosses L4 in 881 persons, L5 in 403, L3 in 11 and the L4-L5 disc in 8; three cells under 5 are withheld; 1,308 persons have a crest level read. About the body it crosses, it tells 1.13 of 1.79 nats, the commonest body (L4) being 68.0 per cent of the bodies it crosses. That figure answers a question of its own: it weights the levels by how often the line crosses them, and T12 to L2 never. On the census's terms, a body drawn at each level alike and the observation whether the line crosses it, the line tells a lone body 0.232 nats: 0.641 at L4, 0.062 at L5, 0.145 at L3, and 0.180 at each of T12 to L2, where never being crossed is what it tells. That is the figure that sits beside the chords'. Its height above the middle of the L4-L5 disc is 2.1 mm on average (SD 23.4, 1,308 persons). Pelvic incidence is 47.5 degrees (SD 14.3), the supine sacral slope 34.5 (13.3) and the supine pelvic tilt 13.0 (7.2), over 1,312 persons, and the hip axis is 177.6 mm wide (10.8). These are one value a person, so they tell nothing about which body is which; they are the pelvis's own measures and the lordosis's context, and the S1 plate under them is the count's anchor.

## 4. What this does not do, and what would be needed

- The plate widths and the canal width are the slab's extents of the engine at 9c85de1, which bordercall #78 replaced with plate_w, plate_d and canal_w_ct (69cae89, merged at 5529bbd). The gold tier's rows predate it and the vendored engine under grid/bordercall/ is pinned at 9c85de1. Reading these measures as Panjabi's means a morphometry run of ENHANCE.PET with the newer engine (vendored here by a pull request of its own, never edited in the copy). The oracle's endplate.right and .left would then need to follow plate_w.
- The projection test projects fixed points and reads no image. What a reader marks on an outline differs off the view (section 2's model), and testing that needs the vertebra's outline projected, from the label's surface, not its eighteen points.
- No measure of the pelvis was tested through projection: the pairs carry no hip centre or S1 plate, and all of DeepFluoro's frames are anteroposterior, where pelvic incidence is not read. Testing it needs the engine's S1 plate and socket centres on the pairs' CTs (pelvis.s1_plate and socket_centre, which the realx builder does not call) and a lateral real frame. DeepFluoro's person-placed femoral head centres (FH-l, FH-r) are the check on the socket centres the engine would give there.
- The six-point heights, the wedge angle, the inclinations, the concavity and the discs were tested through stand-ins (the slab-centre heights, the segmental angle), not as the engine draws them: the engine computes its points for them (body.heights' band surfaces, rim_plane) and does not return them. Placing them as landmarks means returning those points from the engine, a change to make in bordercall and vendor here, never in the copy.
- DeepFluoro's angles are in doubt and no projection figure rests on them. Settling them needs the oracle's frame checked on a CT that holds the whole lumbar column, or DeepFluoro's specimens' column read from vol_seg's lumbar class.
- The census reads every measure as independent given the level and the size; with the gold tier's correlations (above) the joint information of the leaders is less than the sum of their gains. bordercall's correlation prior (docs/memory/the-correlation-prior.md) is the way to take that in. The uncalibrated run's one shared factor for every length is slightly optimistic for an anteroposterior and a lateral length read on two frames.
- The ratios that need a table the papers do not print: the six-point wedge and biconcavity ratios, the crush ratio, the coronal wedge, the depth over the height, the canal over the body, the spinous over the depth and every chord over the next level's have no table in Panjabi or the reread's series (vocabulary.csv names body_index, canal_index and h_lat with no series). The gold tier's per-level means and SDs here are one such table, for one population. A second, of a different population measured another way, is what would tell whether these ratios name levels outside ENHANCE.PET's persons: a lateral-film series of the six-point heights by level, such as the morphometric fracture studies keep for their normal ranges (Black 1991).
- The 18 points' lateral heights in an anteroposterior view and the transverse span over the width fail their bars for the reasons in section 2; the first is a property of the construction and would go if the heights were read at the body's side walls.
- No Radiopaedia image was read: the agreement covers saving cases by hand (docs/memory/radiopaedia-by-hand.md), and nothing of this test needs a frame without a registered CT.

To run it again, in one CPU job of about twelve minutes:

1. Copy tools/annotator_measures.py, tools/qaloop_samples.py and tools/qaloop_gates.py to a throwaway folder on the grid, with a clone of bordercall checked out at 5529bbd.
2. Run `project --pairs <data>/realx/deepfluoro <data>/realx/cobra`.
3. Run `gold` with `--rows` the enhance rows.csv, `--persons` the covariates' persons.csv of job 40902924 and `--verdicts` the enhance verdicts.csv.
4. Run `census` at its default of 2,000 bodies a level; the record names the clone's commit.
5. `report` prints the tables above from the two JSON files.
