# TotalSegmentator on the gold tier 4 CTs

Source: the thread "Train on randomized spine phantoms" of the project symphony_3, 2026-10-31, on the owner's word of 00:55 UTC, "you can start the totalsegmentator segmentation of those scans currently on the grid". Label: confidential-method.

Where it stands on 2026-10-31: built and frozen, not yet sent. The design is PREREG.md beside this file (frozen, its sha256 in PREREG.md.sha256); every departure after the freeze goes into DEVIATIONS.md here.

## What runs

The census (gate word `census gold3`, job 40870542) read every SPINEPS mask on the grid through rule 3's field test and found the gold tier 4: CTs whose image shows C2's foot and the sacrum's top and which no release draws. The census admitted them by SPINEPS's reading of their bones alone. TotalSegmentator 2.18.0 has drawn most of them before, in the ruleclass census's arm A of September 2026 (all but 852 of the tier lists' 17,311 CTs by 2026-09-29, spine-program 06_transitional_ct_census/STATUS.md G.1), whose code lives on the grid and in no repository; this run reads none of arm A's maps and makes its own, so that each is reproduced by a command from a record here (PREREG.md, opening), and arm A's stay for a later check of TotalSegmentator's repeatability. This arm runs TotalSegmentator 2.18.0 on each of them as it lies, its total task with every vertebra, S1 and the sacrum, and writes its map in VerSe's ids on the CT's own grid, the sacrum one mask (26). Each map is set beside the SPINEPS mask: each level's centre, the kind (the two machines naming every bone alike, a name shift, an unmatched level, a variant SPINEPS draws and TotalSegmentator cannot name, or C2 or the sacrum not drawn), and each level's Dice where the two maps share a lattice. A machine arm of its own, never pooled with the releases' masks or the SPINEPS masks.

- The code: tools/gold4_totalseg_grid.py (run and merge, tested by tests/test_gold4_totalseg_grid.py), the launched flow gold4_totalseg (flows/gold4_totalseg.py, in flows/registry.txt with this PREREG), the job script grid/totalseg-gold4.sbatch and the gate word `totalseg gold4` (grid/gate.sh).
- A send is one chain: an array of 16 GPU tasks that share the CTs by claiming each, then one CPU merge afterany the array. A send again carries on where the last stopped; the gate queues one only while the sends make headway (PREREG.md, part 6). A CT that fails in two chains at one code, tools/run_code.py's digest of the files the run executes, is given up; a merge to main that changes none of them keeps it given up.
- Held out: C-ArmLSpine's CT and every CT whose person the tier lists mark test only (real_frames 1, real fluoroscopy kept for validation and test) are segmented and marked held_out, so that nothing trains on them.
- Both tier lists are read, or nothing runs; SPINEPS's end plates (200 + X) are read as their vertebra and its discs (100 + X) as no bone.
- On the grid: the lab volume's gold4-totalseg/ holds labels/ (one map per CT, named by the sha256 of its CT's path), units/ (each CT's run.json), records.jsonl and chains/<array job>/ (jobs.json, each task's lines, the merge's REPORT.md). The report the gate prints, logs/TOTALSEG-gold4.md, carries counts alone.

## The population

At most 1,328 CTs, 1,319 admitted and 9 for a look, in 16 collections (PREREG.md, part 2, from data/gold3-ct/members.json, census.gold4). The census's own sum of 1,388 new studies and 24 border cases counted TotalSegmentator's own subjects (its collection ts, 69 admitted and 14 look) as new, since the census's member rule reads the prefixes totalseg and ts_ alone, and FDG-PET-CT-Lesions' one border case, which is ENHANCE.PET's autoPET; both are left out here. A reply in the thread on 2026-10-31 at 00:57 UTC gave 1,412 (1,388 and 24); 1,328 is the number.

What to expect, from what is already measured: of the census's 1,388, 968 have both C2 and the sacrum drawn by their SPINEPS mask, and 374 have only C2's foot in view (members.json, census.gold4, ends_and_flags). The gold tier 3 completion found TotalSegmentator drew C2 in 4 of 19 fields that show no more than C2's foot (docs/research/gold3-ct/README.md, section 2c), so many of those CTs may end with no C2 from either machine. That is why the first bar is read on the CTs whose SPINEPS mask draws both ends, and the rest are reported beside it with no bar.

## The bars (PREREG.md, part 4)

- H1: TotalSegmentator draws C2 and the sacrum, the sacrum below, in at least 90 percent of the CTs whose SPINEPS mask draws both.
- H2: of the CTs compared, at least 80 percent are concordant, every bone named alike.
- H3: over the concordant CTs on a shared lattice, the median Dice of each region at least 0.80 (cervical, C2 to C7) and 0.85 (thoracic, lumbar); C1's and the sacrum's are reported with no bar.

The merge reads the three from the records and writes met or not met into the report.

## Results

None yet. The counts and the bars' verdicts come here by pull request once a merge ends 0.
