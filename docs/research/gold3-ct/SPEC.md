Source: thread "Finish scan import and tier counts", 2026-10-27 to 28, the thread's own spec for the gold tier 3 CT dataset, written in its cloud container and kept here so a session on the grid can build from it (docs/checkpoints/2026-10-28-gold3-ct-grid/HANDOFF.md). The README beside it says where the programme stands; where they differ, the README is the later word.

Paths under /tmp/claude-0/ and /mnt/project-files/ name the thread's cloud container and the Claude project's files, which a grid session cannot read; the handoff of 2026-10-28 (docs/checkpoints/2026-10-28-gold3-ct-grid/HANDOFF.md) says where each lives on the grid. Section 0's "nothing goes to the grid" was the container's rule: the owner moved the mask reading to the grid on 2026-10-28 00:04 UTC, and the handoff's count, once the owner says yes to it, is the one exception.

# Gold tier 3 CT dataset: build spec (thread "Finish scan import and tier counts", 2026-10-27)

The owner's ask, 22:49 UTC, verbatim: "well whenvever this finishes i want all the gold tier 3 CT data as
its own dataset, with a indexable database, an artefact, and anything i need to use it in the workflow,
including anomaly statistics, and quality assurance they are true anomalies".

Read first: the design brief BRIEF.md beside this file
(what exists, file:line references, the schema idea, the open questions). This spec settles the open
questions with the recommended option; each decision is listed in section 9 so the owner can overrule it.

## 0. Hard rules (from the owner and the repositories; break none)

- Nothing goes to the grid, no fetch, no training, no workflow dispatch. Reading files already in this
  container is allowed. Do not download anything from the internet.
- Never push, never commit to a default branch, never open or merge a pull request (the coordinator does).
  Commit only if your task says so, on branch claude/project-thread-cne00q.
- Confidential: SchwingNet and bordercall are private; nothing goes to a public place.
- bordercall: never touch schwingcheck/, the root tests/, tests/test_schwingcheck_*.py or
  requirements-schwingcheck.txt (another account's). holdings/ is ours.
- SchwingNet: tools/ and scripts are Python 3.12 standard library only (no numpy, no scipy, no new
  dependency); ASCII and LF in everything under docs/, tools/, .github/, data/; plain prose that says why;
  short functions; names that read as English; no emoji. bash scripts/check.sh is the gate (run it in a
  scratch copy of the repository: it leaves stray files in the tree it runs in).
- Do not change paused threads' files or PRs (#416, #418, #420); docs/research/enhance-pet-gold-tier-3.md
  is read-only for this work except where the task says so.
- /mnt/project-files is a network mount: trailing slash on directory paths, never search the whole folder.
- Science: truth only from whole spines countable from C2 to the pelvis; a machine mask or a synthetic image
  never raises a tier; never drop a spine for a missing or extra lumbar label (the owner, 17:10 UTC).

## 1. Members and tiers

Tiers (the owner's, 2026-10-27): gold = C2 to the sacrum in one study; silver = partial. 1 = real CT and
X-ray pair with a person's annotation, 2 = the pair without, 3 = one modality with a person's annotation,
4 = one modality without. Machine masks never raise a tier.

| member | studies listed | gold 3 | where the rows come from |
| --- | --- | --- | --- |
| enhance_pet (ENHANCE.PET 1.6k, sites autoPET, Leipzig, Careggi) | 1,597 | 1,557 | facts from the published masks (section 2), read in this container |
| verse (VerSe 19/20) | 17 | 17, provisional until the sacrum is confirmed on the grid | ids and reads from committed records (brief, data/splits/anomaly-holdout.json, docs/research/spineps-anomaly-route.md) |
| totalsegmentator (v3) | 0 rows yet | 142 (perhaps 156), by records | the subject list is only on the grid (${HOME}/model_night/ts_clean_subjects.txt, sha256 2f96f917...); the member is declared with its count and no rows until the grid index job reads it |

ENHANCE.PET per-study tier: gold 3 for the 1,557 whole; gold 4 for the 3 repaired (1134, 1283, 1347: names
moved by rule or MOOSE); silver 3 for the 37 with no C2 (partial, a person's annotation).

## 2. ENHANCE.PET facts (made in bordercall, numpy/scipy/nibabel allowed there)

Inputs (all local, read-only):
- vertebra masks: /tmp/claude-0/enh/masks/<id>.nii.gz (1,597); persistent copy /mnt/project-files/gold3-ct/enhance-pet-source/masks/
- rib masks: /tmp/claude-0/enh/ribs/<id>.nii.gz (1,597); copy in .../enhance-pet-source/ribs/
- CT-details.xlsx: /tmp/claude-0/s/enh/CT-details.xlsx (copy in .../enhance-pet-source/meta/)
- bucket listings with exact bytes: /tmp/claude-0/enh/keys.json (vertebrae), rib_keys.json, ct_keys.json
  (lists of [key, bytes]); copies in .../enhance-pet-source/meta/
- the repair record: /mnt/project-files/enhance-pet-repair/ (repaired/<id>.nii.gz for 1134, 1283, 1347;
  SHA256SUMS; README)
- the count's outputs: /mnt/project-files/gold3-ct/enhance-pet-source/seed/ (extents.json, sites.json,
  count.json with per-study class and lists, ribs_pairs.json, ribs_contacts.json)

Label schemes. Vertebra mask: C1-C7 = 1-7, T1-T12 = 8-19, L1-L6 = 20-25, hips 26 and 27, sacrum 28; no T13.
Rib mask: left rib k = k (1-13), right rib k = 13 + k (14-26), sternum 27. Rib k's own vertebra is label
k + 7 (rib 13's own body is the one this scheme names L1, label 20).

One JSON object per study, one line each, sorted by id, keys sorted, ASCII, ints where counts, floats rounded
to 0.1 mm (distances, extents, centroids) or 6 decimals (affine, zooms) or 4 decimals (shares):

```
{"id": "0001", "site": "autoPET",
 "mask": {"bytes": int, "sha256": hex, "shape": [i,j,k], "zooms": [a,b,c], "affine": [[4 floats] x 4],
          "axcodes": "LPS" or similar from nibabel, "head_foot_axis": 0|1|2, "dtype": "uint8"},
 "ribs_mask": {"bytes": int, "sha256": hex, "same_grid": true},
 "scanner": {"manufacturer", "model", "kvp", "kernel", "pixel_spacing", "slice_thickness"}  (xlsx row, strings as given),
 "labels": {"<label>": {"voxels": int, "top_mm": f, "bottom_mm": f, "centroid_mm": [x,y,z],
            "components": int, "largest_share": f}}   (every vertebra label 1..28 present with >= 1 voxel;
            top/bottom = head-most and foot-most world head-foot coordinate of the label's voxels, the same
            head-foot convention as count_enhance_pet's extents step),
 "ribs": {"<rib label>": {"voxels": int, "components": int,
          "contacts": {"<vertebra label>": int}, "lead": int|null, "lead_n": int, "tie": bool}}
          (every rib label 1..26 present with >= 1 voxel; contacts = the contact tally below),
 "sternum_voxels": int,
 "distances_mm": {"<a>-<b>": f}   (shortest 3-D distance between the voxels of two vertebra labels, for the
          pairs below where both labels are present),
 "outside_scheme_voxels": {"vertebrae": int, "ribs": int}}
```

Contact tally (must equal bordercall holdings/count_enhance_pet.py contact_tally and rib_contacts):
every voxel of the rib within CONTACT_MM = 3.0 mm (Euclidean distance transform in millimetres, sampling =
the voxel sizes) of any vertebra label in CONTACT_LABELS = 1..25 and 28 (never a hip) is tallied by the label
of the nearest such spine voxel; the box is MARGIN_MM = 30 mm around the rib. lead = the label with most
contacts, a tie going to the head-most (lowest) label and marked tie = true; null when no contact.

Distance pairs: each neighbouring pair in the column C1-C2 ... T12-L1, L1-L2 ... L5-L6, and each lumbar label
L1..L6 to the sacrum (28). Keys are label numbers "<a>-<b>" with a < b, never level names: "23-28" is L4 to
the sacrum, "24-28" L5 to the sacrum, "23-24" L4 to L5, "19-20" T12 to L1. Shortest distance = min over
voxels of a of the EDT (mm) to label b, over a box 60 mm around both labels (as enhance-pet-repair/touch.py).

Coverage: all 1,597 studies with their published masks, and the 3 repaired masks as extra rows keyed
"1134r", "1283r", "1347r" (published ribs, repaired vertebrae), with "repaired_from": "1134".

Expected cross-checks (must hold; a failure is a bug to find before anything else):
- voxels per label equal seed/extents.json's counts;
- the lowest rib's lead and tie on each side equal seed/ribs_contacts.json for its 214 studies;
- rib voxels equal seed/ribs_pairs.json for all 1,597;
- the 23-28 distance equals /mnt/project-files/enhance-pet-repair/touch.json for its 143 studies;
- mask bytes equal the bucket listings.

## 3. Calls and statuses per study (SchwingNet, pure code over the facts)

Two column calls, never merged:
- call_by_names: from the release's labels: T{n thoracic labels present}L{n lumbar labels present}, plus
  the presacral count = labels C1..L6 present (C1 counted when present; a missing C1 at the field's top is
  counted as 1 when C2 is present). E.g. normal T12L5 (24 presacral), L6 spine T12L6 (25), no-L5 T12L4 (23).
- call_by_ribs: rib-bearing bodies = the distinct leads of the ribs on each side with contacts, read as the
  body count down to the lowest rib-bearing body; thoracic count = the highest rib number whose lead is
  consistent, lumbar = presacral bodies below the lowest rib-bearing body down to the sacrum. Where the rib
  ladder is shifted (rib k leads on T(k-1) or T(k+1) for most ribs) the study is a labelling suspect.
  Keep the side-by-side reading: rib_pairs_left, rib_pairs_right, lowest_rib_meets_left/right.

Classes (one primary class per study; the brief section 4):
normal (T12L5 by names, ribs agree); l6_twelve_ribs; l6_thirteen_ribs (13th rib on the label L1: 25 bodies);
four_lumbar_twelve_ribs (L4 meets the sacrum, twelve rib pairs: 23 bodies or a sacralised L5); eleven_ribs
(lowest rib on T11 both sides: a ribless T12); asymmetric_ribs; labelling_error (0529 skipped L5, 0245
one high, 0603 split T6: the record's three); open (0005, 1336: CT needed); look (L5 fragment 0179, 0213,
0270, 1240; out of order 0816, 1273 clearly, 0040, 1463 weakly); not_whole (no C2); repaired (gold 4).
These must reproduce the note's numbers (docs/research/enhance-pet-gold-tier-3.md "What the ribs say"
table) on the 107 unusual + 100 controls exactly, and then extend to all whole studies.

Status of each anomaly (the owner's "quality assurance they are true anomalies"):
- confirmed_by_masks: the release names and the rib ladder agree and every structural check passes. This
  is internal consistency of two masks the same readers checked; it is not a reader's read of the CT.
- candidate: the class rests on names alone or one check says look.
- labelling_error / open: as above.
- reader_confirmed: only from a recorded reader verdict (the bench, section 6); none yet.
- needs_ct: always true for lumbosacral questions (sacralisation, lumbarisation, Castellvi), which no mask
  check can settle; say so in the row.

## 4. QA checks (each: id, version, verdict pass|fail|look|not_run, value, threshold, why)

Q01 header (mask readable, uint8, shape/affine sane, same grid as the rib mask); Q02 alphabet (ids 0-28
vertebrae, 0-27 ribs; outside-scheme voxels 0); Q03 whole rule (C2 and sacrum >= 200 voxels, every level
between, absent L5 excepted); Q04 head-foot order of neighbours; Q05 gaps (> 20 mm fail, > 10 mm look);
Q06 C2 in the field's top slice (look); Q07 L5 fragment (< 0.25 of L4, look); Q08 lowest lumbar label
touches the sacrum in 3-D (<= 1.5 mm: pass; controls never nearer than 2.3 mm across a labelled L5); Q09
rib ladder: every rib k with contacts leads on its own label k+7 (count of ribs off by one; > half off one
way = shift, fail); Q10 lowest rib meets its own vertebra; Q11 split piece: a column label under 0.4 of
both neighbours' voxels (look); Q12 fragments: largest connected component share < 0.9 of a label (look);
Q13 C7/T1 voxel ratio outside the controls' 1st to 99th percentile (look); Q14 two independent
implementations agree on Q08 to Q10 inputs (facts A against facts B); Q15 slice spacing in the xlsx
against the NIfTI (look; 1213 is the known exception); Q16 the bucket's bytes equal the mask's bytes.
Thresholds as named constants with the reason, taken from count_enhance_pet.py where they exist.

## 5. SchwingNet layout (stdlib only)

- data/gold3-ct/members.json: the three members (source record ids data/sources/totalsegmentator,
  verse, scidb_enhance_pet_1_6k; scheme; mask author: readers / model refined by hand / experts; licence per
  site as data/licences.json says; grid roots from the brief section 3 with a note which copy is canonical
  is unsettled; person-key rule; whole rule; counts; tier; caveats).
- data/gold3-ct/enhance-pet/facts.jsonl: section 2, committed (a few MB is fine), made by bordercall
  holdings/enhance_facts.py; a FACTS.json beside it records the tool, bordercall commit, input hashes (each
  mask's sha256 is in the rows; the xlsx sha256), the date and the row count.
- data/gold3-ct/verse.json: the 17 ids with what the records say (reads, holdout/fold role); no paths.
- data/gold3-ct/totalsegmentator.json: the count, the list's grid path and sha256, rows empty, why.
- Add data/gold3-ct to tools/check_docs.py PLAIN_TEXT_FOLDERS if that is how data folders are held to ASCII/LF.
- tools/gold3_ct.py (module docstring for the Reference page; tests in tests/test_gold3_ct.py), subcommands:
  - build [--root DIR]: a versioned SQLite store like tools/catalog.py (versions/gold3-NNNNNN-<12hex>.sqlite
    mode 0444, VERSIONS.jsonl, CURRENT, LOCK; unchanged bytes make no new version), built deterministically
    from the committed files. Default root: a folder outside the repository given by GOLD3_ROOT or --root;
    on the grid it would be $DATA_ROOT/_gold3_ct. Tables follow the brief section 3 (build, source, person,
    person_alias, item, mask, label, rib, anomaly, qa_check, qa_review, shard, embedding), keeping the
    catalog's table and column names where tools/licences.py derive/provenance read them. Views for the
    common questions (gold3 persons per member, anomalies by class and status, QA failures).
  - query SQL [--root]: run a read-only query on CURRENT and print rows (tab-separated or JSON).
  - stats: per member and per ENHANCE.PET site, studies, persons as a range, whole, every class with a 95%
    Wilson interval (the project's convention), distributions (rib pairs, lowest rib meets, presacral
    count, L4-to-sacrum distance), exclusion reasons; writes docs/research/gold3-ct/STATS.md.
  - qa: runs section 4 over the facts (and facts B where present) and writes the qa_check rows and
    docs/research/gold3-ct/QA.md (summary counts, every fail and look with its study id).
  - export [--format json|csv] [--tier gold3] [--training-only]: the manifest the workflow reads: one row
    per study with person, member, site, tier, part (data/splits/rule.json's rule applied to the person key,
    by the same function tools/catalog.py uses; holdout persons of data/splits/anomaly-holdout.json flagged
    and training_allowed false), the anomaly class and status, and where the CT and masks are (public URL
    for ENHANCE.PET objects, s3://enhance-pet-1-6k/imaging-data/...; the grid path pattern for the others).
  - page: writes the artifact's data file (JSON) from the store, for the private page.
  - check: fails when a committed generated file (STATS.md, QA.md, the page data) is stale or the facts
    break their schema; add `python3 tools/gold3_ct.py check` to scripts/check.sh beside the other checks.
- Place tools/gold3_ct.py in tools/run_code.py KINDS or LEFT_OUT as tests/test_run_code.py requires.
- docs/research/gold3-ct/README.md: a programme folder: what the dataset is, its members and counts, how to
  build and query it, what the QA can and cannot show, what waits for the grid and the owner, the
  decisions of section 9. Its line in docs/research/README.md. docs/memory/gold3-ct.md and one SHORT line in
  docs/memory/MEMORY.md (the index is over its size budget already).

## 6. The artifact (made by the coordinator, not by agents)

Private claude.ai page: overview, members, anomaly statistics with intervals, a searchable study table, QA
results, a reader bench (mask projections per candidate, verdicts stored in the page's database), and a SQL
tab over the same schema in the browser. Copied into artifacts/<name>-<id>/ with its README row.

## 7. Grid (written, never sent)

The card to the owner offers: copying ENHANCE.PET's labels to the grid (the existing word `fetch
aws_enhance_pet_labels` lands the whole ground-truth prefix: 11,256,936,591 bytes, measured from the public
listing on 2026-10-27, of which Vertebrae 381,439,888 and Ribs 312,882,241), the Leipzig and Careggi CTs
(45,207,300,328 bytes, a new url-route line), and one CPU job for the grid index (autoPET mask-to-CT match by
shape and affine against the held FDG-PET-CT-Lesions NIfTI, TotalSegmentator's 142 rows, VerSe's sacrum).

## 8. Tests and gates

Every new function has a unit test on small synthetic inputs. bordercall: python -m unittest discover -s
holdings/tests -t . ; SchwingNet: python3 -m unittest tests.test_gold3_ct and bash scripts/check.sh in a
scratch copy (7 beartype errors in test_bank_depth are the container's environment, known).

## 9. Decisions taken on the owner's behalf (each listed in the README and the PR for the owner to overrule)

1. Home: the dataset lives in SchwingNet; the mask-reading code lives in bordercall (it needs numpy/scipy).
2. ENHANCE.PET's four-reader masks are a person's annotation (gold 3), as the note says.
3. TotalSegmentator's 142 stay gold 3 by the records (hand-refined masks), flagged; no rows until the grid.
4. VerSe's 17 are gold 3, provisional until the sacrum is confirmed.
5. Person key: "<member>:<native id>" (enhance_pet:0001, verse:<the spelling data/splits uses>,
   totalsegmentator:<sid>); ENHANCE.PET autoPET persons are unknown, so a study is a person for splits and
   the persons are reported as a range; leakage risk recorded.
6. Holdout and fold persons are carried, flagged, training_allowed false.
7. The rib rule reported is the release's (50 voxels, contact within 3 mm); the Moller 38 mm rule is
   named as the other.
8. Per-study public ids appear in the committed files and the private page (precedent: data/splits).
9. The dataset stands alone and feeds the tiers sort later; it does not edit PR #420.
