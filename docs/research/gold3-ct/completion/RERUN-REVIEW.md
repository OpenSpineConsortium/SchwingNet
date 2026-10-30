# What must change before the totalseg complete rerun is sent

Source: the project thread "Continue Bayesian synthetic validation", 2026-10-30. A read-only review
of the rerun path at SchwingNet 756f4a8 (PR #499, merged as b49583b): five reviewers (TotalSegmentator,
MOOSE, the gate and job, the check and report, a dry run), each finding of medium or worse put to two
more who tried to refute it. TotalSegmentator 2.18.0, nnunetv2 2.8.1 and moosez 3.2.2 were read from
their wheels as data. Verification of the last three lenses stopped when the account's weekly limit
ran out, so the findings marked unverified are one reviewer's reading. Nothing ran on the grid.

The rerun was not sent, since items 1 and 2 would fail it again. Line numbers are those of
tools/gold3_totalseg_grid.py at b49583b.

## Fix before the word is sent

1. TotalSegmentator 2.18.0 looks for all five parts of the total task (Dataset291 to 295) before it
   applies roi_subset, and downloads any it lacks. The job fetched only 292 (vertebrae) and 298 (the
   6 mm crop). On a node with no internet every study fails; with internet it pulls four parts of
   unknown size, outside the size rule. Fix in run_totalseg (:258): replace
   totalsegmentator.python_api.download_pretrained_weights (bound at python_api.py:16, called at its
   lines 319, 321 and 386) with a guard that returns for 291, 293, 294 and 295, which this roi_subset
   never computes (nnunet.py:582-592), and refuses any other missing part. The other way is empty
   placeholder folders for the four parts under $WEIGHTS before `tool run` (libs.py:225 checks only
   that the folder exists). Verified by two of two in two lenses.
2. MOOSE is given TotalSegmentator's device word "gpu" (moose_one, :324). torch.device refuses it, so
   ENHANCE.PET 1379 fails and the job ends 1. Fix: map gpu to cuda, and gpu:N to cuda:N, in moose_one
   before moose(), and default moose-one's own --device to cuda (:643), with a test whose stub moose
   receives cuda. Verified by two of two in two lenses.

## For greg: the sacrum target

3. TotalSegmentator's sacrum leaves out S1, which is its own class (vertebrae_S1). VerSe's id 26 and
   the gold tier 3 release mean the whole sacrum. As frozen in PREREG line 16, the arm would write a
   sacrum without S1 at the whole-sacrum id. The reviewers agree on the fix: add vertebrae_S1 to
   TASK["roi_subset"] (the same part 292, so no new weights) and take the sacrum target as the union
   of sacrum and vertebrae_S1 in check_target and write_arm. MOOSE's id 28 already includes S1. It
   changes the frozen roi_subset, so it needs greg's word and an item in DEVIATIONS.md. Verified by
   two of two (high).

## Worth fixing in the same pull request

4. A MOOSE study whose earlier attempt wrote the multilabel file fails on every rerun, since the
   before/after file diff at :323 never sees moosez rewrite the same name. Use what moose() returns,
   or remove the earlier outputs first. Verified by two of two (medium).
5. Refusal and error reasons name TotalSegmentator for the MOOSE study (:443). Pass the segmenter
   into check_target. Verified (medium).
6. word_totalseg drops its .sent mark without checking that the gate's list names the queued job
   (grid/gate.sh:1901). Do what morphometry covariates does. Unverified (medium).
7. undrawn_between (:426) ignores the release's drawn levels and can list levels on the release's
   far side, and release_levels (:402) counts strays under MIN_VOXELS as levels. Unverified (medium).
8. The report's asked column reads "-" for a study in error and errored targets drop out of the
   counts (:589); run.json cuts a failure's reason to 160 characters and loses the exception (:289).
   Unverified (medium).

Low, for later: a CPU fallback is silent and run.json records no device; C2 is drawn only inside the
6 mm crop; ENHANCE.PET's hip labels are read as release levels; arm/ is never cleared; a grid/logs/HOLD
keeps the gate on an older commit; DEVIATIONS.md still says the arm takes two jobs; PREREG and the
README say 13 VerSe C2 studies where the tool asks 10.

## What held

The profile fix holds on both paths (tools/ is stripped at :73, and again by flexray_render before
moosez is imported). Every keyword run_totalseg passes exists in 2.18.0, and "gpu" is valid there.
The fetched zips hold the 292 and 298 folders TotalSegmentator reads from TOTALSEG_WEIGHTS_PATH.
Usage statistics stay off, and no licence check runs for task total. The outputs are
vertebrae_C2.nii.gz and sacrum.nii.gz on the CT's own grid. The 37 failed run.json records are run
again, and check_target's geometry follows PREREG section 3.
