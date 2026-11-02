# COBRA2026's Varian arm: centres F and G exported and paired

Source: the local session of the night of 1 November 2026, on the owner's ask to wake to many more paired CT and X-ray sets of the spine, after that night's survey of paired sets, which named COBRA2026's Varian part (Zenodo 21322350, CC BY-NC 4.0; data/sources/cobra_varian.json) as held and never used. Grid jobs 40940320 and 40940458 (diagnostics), 40940399 (smoke), 40940472 to 40940479 and 40940494 to 40940501 (the export, sixteen CPU jobs), 40940627 (summary, pairs and check). Confidential with the rest of this repository. Every number below was read from the export's summary, the arm's manifest and check, or the case records on the grid; no frame, mask or image left the grid.

## What was done, and why

The QA loop's external arm reads COBRA2026's Elekta cases (realx/cobra, 66 persons) through an export spinesurg-ct-nnunet's tools/realxray_cobra_export.py made, which refuses every Varian case on a manufacturer check and on the 0.28 by 1.12 mm pixels of one Varian imager. The Varian part is 225 living pelvic radiotherapy patients with real kV cone-beam projections (407 to 895 a case), the RTK geometry of every projection and the planning CT deformably registered to the scan. tools/cobra_varian_export.py writes that exporter's method again for Varian, read from it and from its geometry solver (tools/cobra_varian_geometry.py there) and never run from them, and tools/realx_pairs.py cobra_varian builds the arm from the export by the Elekta arm's rules. The arm is data: it joins no loop until a new PREREG names it, and qa-loop-external/PREREG.md is untouched.

## The geometry, checked before any image

Each projection's matrix is made from its parameters by RTK's own composition (rtkThreeDCircularProjectionGeometry.cxx: the ZXY Euler rotation of the negated gantry, out-of-plane and in-plane angles, the source offset, the magnification by the source-to-detector and source-to-isocentre distances, the detector offset). Over all 225 cases the made matrices put a 600 mm cube about the isocentre within 1.5e-11 mm of where the matrices the files ship put it, so the reading of the convention holds on every projection. The tests check the composition against a ray drawn through the detector plane by hand with a rotation scipy builds, and against the first matrix of case F003's file.

The proof renders of 2026-09-23 (cobra2026/varian/proof: 25 pictures with SPINEPS body boxes, 20 bone contours and overlay_summary.json, the last box run's 20 frames) were tested by their numbers, since their pictures cannot leave the grid: the summary's boxes drawn again through the made matrices and the solved map, sampling the mask voxels as that run did, agree to 0.049 px, the summary's own rounding (0.42 px from every voxel). Only two of its cases carry boxes, A002 (Elekta, 8) and F003 (Varian, 8); its F010, F020 and G000 frames hold none, so the renders confirm the Varian map numerically on one case. Nobody has yet looked at the pictures themselves.

The survey's count of the old solver was wrong both ways. VARIAN_GEOMETRY.json (written 05:03 on 2026-09-23) lists seven unsolved cases, but four of them (F010, F011, F017, F020) are its confirm files read as records, and the other three (G042, G051, G089) were solved again between 05:04 and 05:27 that morning: the solver confirmed the map [[1, 0, 0], [0, 0, -1], [0, -1, 0]] on all 99 Varian cases it tried, and never tried the other 126.

## The patient map, tested on every case

As the Elekta export did, the CT is rendered through each of the 16 signed maps that put the patient's long axis on the rotation axis, on four frames spread over the sweep, at blocks of about 4 mm, and scored by the normalised cross-correlation (NCC) of the body edges with the real frames inside the exposed band; a case is exported only when the solved map ranks first and leads the next by 0.10. All 225 cases were tested, the 126 the old solver never tried among them, since this test is itself a solve.

- On every case the solved map ranked first on the real frames. Four fell short of the 0.10 lead and were refused: F028 (0.091), F130 (0.024), F167 (0.077), G194 (0.094); the old solver had passed F028 on the authors' simulated projections.
- Over the 220 exported, the solved map's edge NCC has a median of 0.757 (5th percentile 0.611, smallest 0.293), its lead a median of 0.308 (smallest 0.105). The authors' own simulated projections, which they made from the same CT through the same geometry, match this tool's render through the solved map at a median edge NCC of 0.965 (smallest 0.894), and lead the next map there by a median of 0.418 (smallest 0.082). That target is the authors' own: nothing this tool computes went into it.
- Per frame, over 5,280 exported frames, the edge NCC has a median of 0.794 (25th percentile 0.692, 5th 0.494); 278 frames are below 0.5. The log-intensity NCC has a median of 0.970. A low frame is kept and its score written into its meta, as the Elekta export did: the pose is the case's machine geometry, which the map test confirmed on the case; what can lower a frame's edges with a right pose is what the CT does not hold (the treatment couch, gas that moved, the arms), and no frame was looked at to say which.

## From stored signal to attenuation

The stored projections are the detector's raw signal with the bowtie in the beam: on F003 the air level divided by the case's own bowtie air scan is flat across the field (about 3.3 on both sides) while the signal itself follows the bowtie. The air scan is read from Calibrations/AIR-*/Current/FilterBowtie.xim (the tool reads Varian's XIM format; the property list after the pixels reads whole, which a wrong pixel count would break), chosen where its folder names the sweep's kV and its own header names the sweep's bowtie and kV and has the stack's size. Then a = -log(I / (s F)), s the median of I / F over the pixels whose rays cross no tissue of the CT on that frame (2,808 of 5,280 frames have enough of them; the rest take the case's median, or, on the 19 cases where no frame shows enough air, the 99.9th percentile of I / F, to which the percentile window is blind). The scan's orientation is tested on every case: the spread of log(I / F) over the air has a median of 0.027 as stored against 0.089 mirrored over the 201 cases with air. G008 was refused here, its air fitting the scan neither way (0.77 as stored, 0.36 mirrored). The gantry-matched air scans each folder also holds (FilterBowtie_000 to _011, and _CC_ and _CW_ on the half fan) were tried on F003 and G000 and change the spread by about one per cent, so the one scan is used.

## What the frames show

Each frame is cropped to a square of the exposed band's height about the projected lumbosacral junction (the mean of the L4, L5 and sacrum centroids), resampled to 512 pixels and windowed by the Elekta export's display ladder. The fields are pelvic and centred on the treatment target, below the spine. The Bowtie V3 sweeps are collimated craniocaudally (F003: 186 mm at the isocentre), the 1024 by 768 imagers' uncollimated field is about 199 mm (F010), and on the half-fan imagers the detector's edge runs about 26 mm past the central ray at the isocentre (G000), so a spine near the isocentre is cut in most views. Boxes kept, where half a structure's projected voxels fall in the frame (TotalSegmentator's name, then where both labellers agree): sacrum 3,128 (3,088), L5 1,759 (1,512), L4 506 (441), L3 174 (142), L2 38 (38), L1 38 (38), T12 24 (24). So the Varian frames show the sacrum on 3,128 of 5,280 frames, L5 on a third, and the column above L4 almost never: an anchor for the count, not a lumbar column.

Imaging chains among the 220: Bowtie V3 on 3072 by 384 pixels (74 cases, frame edge NCC median 0.764), Half Fan V1 on 1024 by 768 (89, 0.861), Full Fan V1 on 1024 by 768 (31, 0.765), Full Fan V1 on 1536 by 384 (20, 0.746), Half Fan V1 on 1536 by 384 (6, 0.755). By the held-out rule (md5 of the case mod 10: 8 and 9 test), 150 cases are training, 18 validation and 52 test.

## The levels

TotalSegmentator's labels are the anomaly harvest's (2.18.0, run on this ct_def), which label S1 apart from the rest of the sacrum on all 220 cases; S1 is counted in the sacrum, as SPINEPS's sacrum and the Elekta seg tree count it. A level is named only where TotalSegmentator and SPINEPS with VERIDAH name the same bone alike (Dice 0.5 or more), SPINEPS's mask taken from the transitional screen's own record and only where the screen checked its ids against the centroid file: SPINEPS was used on 218 cases, and the median case has three levels named alike.

## The arm (realx/cobra_varian)

tools/realx_pairs.py cobra_varian, by the Elekta arm's rules: the export's test cases held out, a case the transitional screen (cobra2026/lstv) does not call ordinary left out, the longest stretch of levels both labellers name alike, frames within 15 degrees of the anteroposterior or lateral view. One rule is the Varian arm's own: a frame with no kept box of the sacrum or of the person's levels is left out and counted, since the Varian fields leave many frames with nothing of the column in view.

- Built: 38 persons and 275 frames (151 anteroposterior, 124 lateral), 5 to 9 frames a person but one with 1; 20 persons on L1 to L5 and 18 on T12 to L5; 3,112 of 3,744 landmarks read. 15 of the 38 come from the cases the old solver confirmed and 23 from those it never tried.
- Held out: 52 persons (1,248 frames), never read.
- Left out: 135 persons, 126 by the transitional screen (unreadable 107, the planning CT not reaching L1 so the count cannot be made; L6 13; T13 3; four lumbar 2; no call 1), 5 refused by the export, 3 with no frame left, 1 with no stretch the labellers agree on. Frames left out: 662 oblique, 47 with no structure in view.
- The check (`realx_pairs.py check`): the arm's projected landmarks fall inside the export's own box for their level on 84.0 per cent of in-frame points (4,001 of 4,761; persons 0.78 to 0.91), the sacral points inside the sacrum's box on 64.0 per cent (624 of 975). The Elekta arm's same check reads 86.2 and 68.7 per cent. Ten of the 38 persons have no in-frame lumbar landmark with a kept box. The contact sheet (check_sheet.png beside the arm) is on the grid and has not been looked at by eye.

## What is left

- A look at the proof renders and the arm's contact sheet, on the grid, by someone who may see the frames.
- Any use in a loop: a new PREREG that names this arm, its bars and its held-out part; the running loop's PREREG stays as it is.
- The screen's unreadable calls (107 of the 135 left out): the planning CT stops below L1, so the count from T12 cannot be made there; an arm that anchors on the sacrum alone could take them, which is a design question for that PREREG, not a change here.
- The four cases refused by a lead under 0.10 could be tested again at another block size (the old solver's confirm runs found the edge score rises with the block on the fine-pitch imager), never taken in by lowering the bar.

## Reproducing it

On the grid, from a clone of this repository with the box's Python (numpy, scipy, nibabel, Pillow):

    python tools/cobra_varian_export.py proof --data <data root> --out <folder>
    python tools/cobra_varian_export.py export --data <data root> --out <data root>/realxray/cobra_varian --list <cases> --shard i --n-shards 8
    python tools/cobra_varian_export.py summary --out <data root>/realxray/cobra_varian --solved-list <the old solver's cases>
    python tools/realx_pairs.py cobra_varian --data <data root> --out <data root>/realx/cobra_varian
    python tools/realx_pairs.py check --out <data root>/realx/cobra_varian --data <data root>

A case took a median of 53 seconds on two CPUs, four hours of job time in all.
