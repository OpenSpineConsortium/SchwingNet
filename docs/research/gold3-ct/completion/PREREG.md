# Pre-registration: the C2 and the sacrum TotalSegmentator draws for the gold tier 3 completion

Source: the thread "Complete gold tier 3 census", 2026-10-30, on the owner's word of 08:54 UTC, "Add sacrum and c2 w total seg", which follows his rule of 2026-10-29 23:46 UTC that a CT whose image shows C2 and the sacrum is in and that a segmentation completes what its masks lack, and on his rule of 2026-10-29 that every deep learning job on the grid runs on a launched flow under a frozen pre-registration; the protocol is the Lab Recipe (artifacts/the-lab-recipe-1t2gvp/index.md, "Pre-register and freeze"). Label: confidential-method, as the programme's README.

This file is frozen. It is the design the completion's TotalSegmentator arm runs under, written in the Lab Recipe's seven parts before the segmenter was run on any of these CTs and before any of its masks was read: on 2026-10-30 no job of this arm had been sent and no fetch of its weights had. The job is sent only on the owner's count, which is not this file's to give. Where docs/research/gold3-ct/README.md, section 2c, differs from it, this file governs. Every departure from it after the freeze goes into DEVIATIONS.md beside it, dated, with its reason.

## 1. The question

For each gold tier 3 study whose admission (data/gold3-ct/admission.json) lists C2 or the sacrum among the levels its release does not draw, does TotalSegmentator, run on the study's own CT, draw that level where the release's own levels say it should lie, so that it can be kept as a machine arm beside the release?

## 2. Population and inputs

- The studies: every row of admission.json with verdict admitted or look whose complete list names C2 or sacrum, as tools/gold3_totalseg_grid.py studies_asked reads it at the commit the job runs from. At the freeze that is 38: VerSe 27 (every admitted or held series, since VerSe draws no sacrum, 13 of them C2 too), TotalSegmentator 10 (s0102, s0437, s0621, s0931, s1329, s1344, s1593, s1606, s1762, s1778) and ENHANCE.PET 1 (1379, C2). A study whose CT or release masks are not on the data root is listed with its reason and not run.
- The CTs: each study's own CT on the data root (a VerSe series by the CT path its census row names under versefusion, a TotalSegmentator subject's ct.nii.gz under totalsegmentator_v300 wherever the release nests it, ENHANCE.PET's by its id under aws_enhance_pet_ct); never resampled before the segmenter, so its masks come out on the CT's own grid.
- The release masks, the reference each drawn level is checked against: VerSe's int16 copies (verse_masks_2026_10_29), the subject's segmentations/ folder, ENHANCE.PET's Vertebrae file. They are read; none is changed.
- The segmenter: TotalSegmentator 2.18.0 from PyPI (Apache 2.0), task total with roi_subset vertebrae_C2 and sacrum and fast false, which crops with its 6 mm model (Dataset298) and runs the vertebrae part (Dataset292) at 1.5 mm; the two weight zips from the project's v2.0.0-weights release, fetched once by the gate word `fetch totalseg_weights` under the size rule and unpacked once into the folder TOTALSEG_WEIGHTS_PATH names; the job never downloads, and usage statistics are off.
- Files and hashes: each kept mask's sha256 is in its file name and in records.jsonl; the segmenter's version is in every record; no CT or mask leaves the grid.

## 3. The measurements

For each study and each asked target (C2 or sacrum), on the CT's grid, which is the release's:

- voxels: the number of voxels TotalSegmentator drew of the target.
- overlap share: the share of those voxels lying on any of the release's own drawn levels.
- side: the target's centre along the world's vertical (the affine's third row) against the centre of the release's topmost level for C2 and its lowest for the sacrum.
- gap_mm: from the target's lowest point to the top of the release's topmost level (C2), or from the bottom of its lowest level to the target's highest point (sacrum), signed, in mm.
- undrawn_between: the levels the admission still lists as undrawn on the target's side of the release.

## 4. The hypotheses and their bars

- H1: TotalSegmentator draws the sacrum in at least 24 of VerSe's 27 series (each has at least 200 voxels of it, clear of the release's levels and below them).
- H2: it draws C2 in at least 10 of the 19 studies that ask for it.
- A bar not met is reported as such; nothing is tuned and the job is not sent again on this arm without the owner's count.

## 5. What counts as failure

- A target is refused, and no arm file written, where TotalSegmentator wrote no file, drew fewer than 200 voxels (MIN_VOXELS), where more than 5 percent of its voxels lie on the release's own levels (OVERLAP_SHARE), where its centre lies on the wrong side of the release's nearest level, or where its mask is not on the release's grid, so that no check can be made.
- A study is in error where the segmenter failed on its CT or its release masks could not be read; the reason is recorded whole and cut to 160 characters in the report.
- A kept target never raises a tier and is never pooled with the release's masks or with the SPINEPS arm: it is a third machine arm, recorded by segmenter, version and sha256, read only where a method says it reads a machine arm.

## 6. The analysis plan

- tools/gold3_totalseg_grid.py prepare, run, check, report, in that order, in one GPU job (grid/totalseg-complete.sbatch) as the launched flow totalseg (flows/totalseg.py), with its progress page; run skips a study whose masks are already there, so a job cut short carries on.
- The report, logs/TOTALSEG-complete.md: the counts, a line per study and every refusal's reason; store and file names only, no path under the data root, no DICOM header, no person key.
- The counts, the kept targets by study and each gap go into data/gold3-ct/members.json (completion) and README section 2c by pull request; a VerSe series whose sacrum is kept stays provisional, since a machine arm is no reader's read.

## 7. Freeze

Frozen on 2026-10-30 by `sha256sum PREREG.md > PREREG.md.sha256` in this folder; flows/registry.txt names this file for the kind totalseg, and the flow's start and end hold every run to it.
