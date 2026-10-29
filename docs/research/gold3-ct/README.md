# The gold tier 3 CT dataset

Source: the thread "Finish scan import and tier counts" of the symphony project, 27 October 2026, the owner's ask of 22:49 UTC, in his words: "well whenvever this finishes i want all the gold tier 3 CT data as its own dataset, with a indexable database, an artefact, and anything i need to use it in the workflow, including anomaly statistics, and quality assurance they are true anomalies". The thread's design brief and build spec are kept beside this README as BRIEF.md and SPEC.md, as the thread wrote them in its container; where they and this README differ, this README is the later word. ENHANCE.PET's own finding, which most of the counts here rest on, is [ENHANCE.PET 1.6k in the evidence tiers](../enhance-pet-gold-tier-3.md). Confidential: this programme describes unpublished data work and never leaves this private repository.

Where it stands on 2026-10-29: the owner's answer of 2026-10-28 22:58 UTC to #443 widens the dataset to every CT whose volume shows the whole spine (section 2a). The rule is written and tested (tools/gold3_field.py), held has one definition (section 2b), and every VerSe series (374) and TotalSegmentator subject (1,939) is read into rows from its public release, so section 2's counts are the field test's (ADMISSION.md): 1,726 gold 3 studies, 1,557 of ENHANCE.PET, 18 of VerSe and 151 of TotalSegmentator, with 11 border cases waiting for a person's look. An adversarial review of the first counts (1,731 and 21) found that a sliver of C2 or of the sacrum at the field's edge, a tilted or padded grid and a name the column skips each moved studies; the rule now reads them as section 2a says. The levels a segmenter must add (section 2c) wait for one CPU grid job and the owner's word; nothing went to the grid. No reader verdict is recorded, so no anomaly is yet confirmed by a reader. The choices made on the owner's behalf are section 8, for him to overrule; the account handoff is docs/checkpoints/2026-10-29-gold3-full-spine/HANDOFF.md.

## 1. What the dataset is, and why

It is every CT the project counts as gold tier 3, kept as one dataset of its own: one row per study, with its person key, member and site, tier, the facts read from its masks, two column calls kept apart, an anomaly class with its status, and the result of every quality check. It is held as a read-only, versioned SQLite store, as the frame catalog is, and it gives the workflow one manifest to read.

The tiers are the owner's of 27 October 2026. Gold is a field from C2 to the sacrum in one study, silver a partial one. Tier 1 is a real CT and X-ray pair with a person's annotation, 2 the pair without one, 3 one modality with a person's annotation and 4 one modality without. A machine mask or a synthetic image never raises a tier. Truth comes only from whole spines countable from C2 to the pelvis, and a spine is never dropped for a missing or an extra lumbar label (the owner, 17:10 UTC).

Why one dataset: no held person is gold 1 or gold 2, so these CTs are the project's only spines counted from C2 under a person's annotation, and the anomaly route, the DRR renders and the tiers sort draw on them. Until now they sat in three sources with three label schemes, two person-id spellings and four versions of the whole-spine rule. Kept together they get one person key, one whole rule, one set of anomaly classes with intervals, and one place where each anomaly's evidence is checked.

## 2. Members and counts

| Member | Source record | Studies with rows | Gold 3 | Persons | What the count rests on |
| --- | --- | --- | --- | --- | --- |
| ENHANCE.PET 1.6k: autoPET, Leipzig, Careggi | scidb_enhance_pet_1_6k | 1,597, with 3 repaired masks beside them | 1,557 studies | 865 to 1,478 | the published vertebra and rib masks, read where FACTS.json's read_on says |
| VerSe 19 and 20 | verse | 374 series | 18 series, provisional while a segmenter adds the sacrum | 18 | the release's expert masks, by the field test (rule 2) |
| TotalSegmentator v3 | totalsegmentator | 1,777 subjects, of 1,939 | 151 subjects, 5 of them to complete | 151 | the release's masks, by the field test (rule 2) |

Before any check across members, the three give 1,726 gold 3 studies (1,557, 18 and 151) and at most 1,647 gold 3 persons (1,478, 18 and 151), at least 1,034 (autoPET's 865 with VerSe's 18 and TotalSegmentator's 151). Border cases, silver 3 until a person's look: 11, which are 1 of ENHANCE.PET (1379, at the head), 9 of VerSe (all at the head) and 1 of TotalSegmentator (s1597, whose field holds 17.2 mm of the sacrum).

ENHANCE.PET by site:

| Site | Studies | Whole, C2 to the sacrum | Persons |
| --- | --- | --- | --- |
| autoPET | 1,014 | 979 | 865 to 900 |
| Leipzig | 384 | 379 | at most 379, no person id |
| Careggi | 199 | 199 | at most 199, no person id |
| All | 1,597 | 1,557 | at most 1,478, at least 865 of them autoPET's |

What each count rests on:

- ENHANCE.PET. MOOSE drew the masks; a medical student verified and corrected each scan, a second student reviewed the first, and a radiology resident and a nuclear medicine resident reviewed both, by the paper's Methods (Ferrara D et al., Scientific Data 2026). Checked and refined by people, they are a person's annotation, so a whole study is gold 3. The whole rule: C2 and the sacrum each with at least 200 voxels and every level between them, an absent L5 excepted, as the owner asked at 17:10 UTC. The 1,014 autoPET studies are 900 persons (Gatidis S et al., Scientific Data 2022;9:601), so its 979 whole studies are 865 to 900 persons. CT-details.xlsx gives no person id for Leipzig or Careggi, so their 578 whole studies are at most 578 persons, and the 1,478 is an upper bound. Of the other 40 studies, 37 have no C2 and are silver 3, and 3 (1134, 1283 and 1347) were left out for a skipped or scrambled label and repaired, two by renaming the readers' labels as the ribs direct and one with MOOSE's rerun; their names come from a rule or a machine, so they stay gold 4, with the repaired masks kept beside the published ones as the rows 1134r, 1283r and 1347r.
- VerSe. Of the 374 series of 355 patients, 18 are admitted by the field test: 76 series draw C2, none draws the sacrum (the release draws no label 26), and the sacrum's top is placed in view in 293 from the last lumbar level, so most series show the neck or the lumbar spine and few both. The 18 are the 17 the older records read, every one, and verse607, whose field reaches 39.1 mm above C3 where C2's top lies within 37.5 mm in 95 of 100 spines, so its C2 is to complete beside the sacrum. Every admitted series is gold 3 provisional until a segmenter's sacrum confirms the placement. The 9 border cases are all at the head end; verse623, a tenth before the review, is out, since over its column the field reaches only 2.5 mm above C5, below where C2's foot lies in 95 of 100 spines. The records hold a read for nine of the 17 and none for the other eight, and the other series are named by their masks. Persons in the anomaly route's holdout or its folds (`data/splits/anomaly-holdout.json`) are carried, flagged, and refused for training.
- TotalSegmentator. Of the 1,939 v3 subjects, 162 draw no vertebra above the sacrum and have no row: 131 draw nothing of the spine (a head, a limb or an abdomen) and 31 a sacrum alone. Of the 1,777 others, 151 are admitted, 146 whole by the release's masks and 5 with levels to complete (s1411, s1532, s1593, s1606 and s2065), and 1 is a border case. The review moved five of the first 156: s0462 and s1310 hold a sliver of C2 (the field's top cuts C2 and C3 alike), s1018 and s1171 hold under 20 mm of the sacrum with the last lumbar cut too, and s1597 holds 17.2 mm of the sacrum with its L5 whole, a border case; the first count's ten border cases are all out. 22 of the admitted are under 18 at the scan (flagged child; 286 of the 1,924 subjects with an age are), and none is left out for it. The masks are model output refined by hand, counted as a person's annotation and flagged. v3 ships an L6 file and no T13, so an L6 it draws is a candidate and a thirteenth thoracic body cannot be named. The older count of 142 (model_night/ts_clean_subjects.txt in the grid home, sha256 2f96f917292b85416d1b803230732624a3dde0bae7c2c29f54abc4f2a30dc1b7) is set beside the 151 only once a grid job reads that list.

Licences, as `data/licences.json` classes them: ENHANCE.PET CC BY 4.0 for Leipzig and Careggi and CC BY-NC 4.0 for autoPET, non-commercial as one set; VerSe CC BY-SA 4.0, share-alike; TotalSegmentator CC BY 4.0, open.

## 2a. The admission rule, version 2

Source: the thread "Complete every full-spine CT for gold tier 3" of the project symphony_4, 28 and 29 October 2026, on the owner's answer of 2026-10-28 22:58 UTC to #443's question, in his words: "my understanding is both totalsegmentator and VerSe were nearly all full spine, also i do have a VerseFusion github dataset which i think is more complete, but if these lack only the sacrum or c2, i dont mind segmenting those to complete the full spine, essentially if the full spune is in view in the volume, and just missing a mask or two, that should just be completed using a segmentation software of choice, even gold tier 4, which may lack masks can be segmented and used for studies, i dont think i should leave out any spines that have ct volumes with the full spine in view, i should do whatever is necessary to get them ready for usage".

The rule: a CT is admitted when its field holds C2 and the top of the sacrum, whatever its masks hold. Version 1 asked the masks to draw C2, every level to T12 and the sacrum, so a field that held the whole spine but whose release drew no sacrum (every VerSe series) or missed one level stayed out. Version 2 asks the volume, and lists what a segmenter must add. tools/gold3_field.py is the rule; ADMISSION.md beside this README is every count it gives, with its tables and checks, written by `python3 tools/gold3_field.py write` and held current by `check` in scripts/check.sh.

- A level is drawn when its mask holds 200 voxels or more, version 1's floor.
- A drawn C2 is in view: a person drew what the CT shows. A C2 the field's top cuts is flagged c2_at_field_top for a look, as version 1's Q06 did; but where the field's top cuts the level below C2 too, the field holds a sliver of C2 and the end is out. A drawn sacrum is in view when the field holds 20 mm of it below its top. A sacrum the field's foot cuts short of that, drawn or a label under the floor, makes the foot end out when the foot-most level above it is cut too, and a border case otherwise; every sacrum the foot cuts is flagged sacrum_at_field_foot.
- The field over a level is read along the world's vertical line through the level's centre, since on a tilted grid the faces are tilted planes and the corners overstate the field. TotalSegmentator's grids are sometimes padded with slices that hold no image; there the spinal cord, which runs on past the cervical and lumbar levels, stops with the column at one plane, and that plane is the field's edge, a level within a slice and the tilt's reach of it counting as cut.
- An undrawn C2 is placed from the head-most drawn level. The head table measures, on every spine of the three members that draws both whole, how far C2's top lies above each level's top. The head end is in view when the field reaches the 95th percentile of that above the level; out when the level itself is cut by the field's top, or when the field ends below the 5th percentile of where C2's foot lies; a border case between.
- An undrawn sacrum is placed from the foot-most drawn level by the foot table, the same measure from each level's foot to the sacrum's top, with every last lumbar (L4, L5 or L6, whichever a spine draws last) pooled as one row. The foot end is in view when the field reaches 20 mm below the highest place the sacrum's top lies in 95 of 100 spines, so the L5-S1 disc and the top of S1 are in the field; out when the foot-most level is cut by the field's foot, or when the field ends above the lowest place the sacrum's top lies in 95 of 100; a border case between. The 20 mm is a choice no published number fixes; ADMISSION.md gives the counts at 10 and 30 mm beside it.
- Admitted: both ends drawn or in view. Look: a border case at either end, silver 3 until a person's look admits it. Not admitted: either end out, or no vertebra drawn above the sacrum (a head, a limb, an abdomen or a sacrum alone in TotalSegmentator), which is no spine study and has no row.
- The completion list of an admitted study: every level from C2 to L4 the release leaves undrawn between two drawn ones that leave room for a body, C2 and every level above the head-most drawn one when C2 is placed, the sacrum when it is placed, and the lumbar levels, L5 among them, below a foot-most level above L4. Drawn neighbours overlap by their facets, so where the upper one's foot lies at or below the lower one's top the names skip a level the column does not have, a count variant (eleven thoracic and then L1) or a skipped label: flagged name_skipped and never a level to add. A missing L5 between a drawn L4 and the sacrum is a flag (no_l5), never a level to add, since VerSe's labellers leave a vertebra fused to the sacrum undrawn and a spine is never dropped for a missing lumbar label (the owner, 2026-10-27 17:10 UTC).
- Flags, never exclusions: c2_at_field_top, sacrum_at_field_foot, name_skipped, cut_in_plane (a level reaches a side face), no_l5, stray_labels (a label under the floor), child (under 18 at the scan, where an unfused S1 can read as a free body), small_column (C2's top to L1's foot under 300 mm) and label_spans_levels (a label over four times the study's median level height, one label drawn over several bodies); ADMISSION.md says what each means and counts them.

How the rule was tested before it was used: run on ENHANCE.PET, whose masks draw C2 and the sacrum, each study judged once, on its repaired mask where it has one, every study it admits is one version 1 counts gold 3 or gold 4 and every one it leaves out is one version 1 counts silver 3, study for study (check holds them equal); with C1 and C2 hidden on every spine that draws them, it finds C2 in view or a border case and never out; with the sacrum hidden, the same, but for one TotalSegmentator subject, s1127, whose L5 label runs 225 mm over the sacrum to the field's foot, so that with the sacrum hidden its L5 reads as cut (it is flagged label_spans_levels, and its head end is out, so it is not admitted either way); and on every spine whose head-most level is cut by the field's top it calls C2 out (ADMISSION.md, Checks). Its unit tests are tests/test_gold3_field.py.

Which masks were read: VerSe's expert masks from the release (OSF, the MICCAI nodes 923ap and b2wxj), all 374 series, verse20's mask where a series is in both releases with verse19's set beside it; TotalSegmentator v3's released masks (Zenodo record 22688904), all 1,939 subjects, read by byte ranges from the release zip; in the cloud containers of the project's threads by bordercall's holdings/fullspine_facts.py (TotalSegmentator at 5bd759a, VerSe at 4a6cd72). Every VerSe mask (473 files: 160 of VerSe 19 and 313 of VerSe 20, where series.json's 319 VerSe 20 series include six whose node publishes no mask, read from VerSe 19) and every TotalSegmentator subject's masks (1,939) were checked against their CT's header, shape and affine, and all lie on their CT's grid, so the mask's field is the CT's (FACTS.json beside each member's rows). VerSeFusion, the owner's repository, holds the same 374 series of 355 patients (its configs/verse_demographics.csv, kept as data/gold3-ct/verse/series.json with each series' patient and age); it adds no series, and it is the copy on the grid.

## 2b. Held: one definition

A study is held when its CT and its masks are on the grid, under the member's canonical root on the data root (members.json, grid.root), and every one of those files hashes to the sha256 this repository records for it: the facts' sums for the masks, and the CT's once a grid check has recorded it. A copy anywhere else, a grid home, the Claude project's files, a public bucket or a thread's container, is a copy, readable but not held, and a file whose bytes differ from the record is not held, whatever its name. A member's grid.held in members.json says checked (with the date and the job), unchecked or not_held, and is never true until a grid check has compared the sums.

Why: the rows name files by sha256, so a study used for truth or training must be the file its facts were read from, and a copy outside the data root may move or be cleaned away. data/sources/<source>.json's reach held (HAVE, on the grid now) says the same of a whole source; this is it for a study.

Where each member stands: ENHANCE.PET is not held (its masks were read from the public bucket; `fetch aws_enhance_pet_labels` has not run; autoPET's CTs are on the grid as FDG-PET-CT-Lesions but unmatched to its masks; Leipzig's and Careggi's CTs are not on the grid). VerSe is unchecked: the data root's VerSeFusion copy is its canonical root and the grid home's is another copy; 364 of its 374 series are on the grid by the source records, and the 10 VerSe'20 series never downloaded (grid/README.md) are not held. TotalSegmentator is unchecked: the data root's totalsegmentator_v300 is canonical and the grid home's v3 is another copy.

## 2c. Completing the masks, and gold 4

The completion list of every admitted study is in admission.json. The segmenter is SPINEPS, by the owner's science rule: SPINEPS for production segmentations, reusing the masks already on the grid, never re-run and never TotalSegmentator. The census (spine-program 06_transitional_ct_census, docs/ruleclass/TIERS.md) already holds a SPINEPS mask for all 374 VerSe series and for 1,660 of TotalSegmentator's 1,935 scans (SPINEPS failed on 210 and 65 more have none), so completing them needs no new segmentation, only a read. A completed level is a machine mask: it is kept as an arm of its own beside the release's masks, recorded by segmenter, version and sha256, never pooled with the release's masks or with another segmenter's, and it never raises a tier. A study admitted with levels to add is gold 3, provisional, because gold is the field's (C2 to the sacrum in one study) and 3 is the person's annotation of the levels the release draws; a use that needs a person's drawing of the added level reads the flag.

Gold 4, the owner's "even gold tier 4, which may lack masks can be segmented and used for studies": every other CT whose volume shows C2 to the sacrum, with no person's annotation. The same field test admits them from the census's SPINEPS masks (tiers 1 and 2 of TIERS.md, 5,094 and 12,217 CTs, less 113 with no SPINEPS mask: 17,198, VerSe's and TotalSegmentator's among them), so gold 4 is read, not segmented; 13 of VerSe's and 517 of TotalSegmentator's SPINEPS masks carry SPINEPS's raw ids and are relabelled first (TIERS.md section 5). Their lists stay on the grid, since most are not public sets; only counts by collection leave it.

Both are one CPU job on the grid that reads masks already there and segments nothing: it waits for the owner's word and count (section 7).

## 2d. The auto-anatomist's spines and their licence

The owner, 2026-10-28 23:03 UTC: the 2,000 labelled spines are "verse+totalsegmentator+PET". Their label is a mask per vertebral level, named by level: VerSe's expert masks from C1 to L6 with T13, TotalSegmentator's hand-refined files from C1 to L6 with the sacrum, ENHANCE.PET's reader-checked masks from C1 to L6 with the sacrum and the ribs. None carries a measurement, so the auto-anatomist makes its measurements on these masks.

Licence: data/licences.json classes TotalSegmentator open (CC BY 4.0), VerSe share-alike (CC BY-SA 4.0) and ENHANCE.PET non-commercial as one set (autoPET CC BY-NC 4.0, Leipzig and Careggi CC BY 4.0). Recommended on the owner's behalf, for him to overrule, and recorded in members.json (auto_anatomist): train it under the recipe non-commercial (data/recipes/non-commercial.json), which allows open, share-alike and non-commercial data with no owner review and so takes all three members whole; its network may be published and shared for non-commercial use. A commercial auto-anatomist would take TotalSegmentator alone under the recipe commercial, ENHANCE.PET's Leipzig and Careggi only after a per-site split, every class first confirmed by the owner (that recipe takes reviewed classes only), and VerSe only under commercial-share-alike after counsel. Whether a network's weights are an adaptation of its data is unsettled; if they were, VerSe's share-alike and autoPET's non-commercial terms could not both be met by one licence, which is counsel's question before any release. Loosening a class is the owner's alone.

## 3. Where the records are

- `data/gold3-ct/members.json`: the three members, with each one's source record, label scheme, mask author, licence by site, grid roots (the canonical one and the other copies), whether it is held, person-key rule, counts, tier and caveats; and, for the dataset as a whole, the whole rule (version 2, with version 1 kept under previous), the definition of held, the completion rule and the auto-anatomist's licence.
- `data/gold3-ct/admission.json` and `ADMISSION.md` in this folder: the field test's verdict on every study of the three members, its two ends, its flags and the levels a segmenter must add, with the tables, the checks and the sensitivity counts, written by `python3 tools/gold3_field.py write` from the facts and held to them by `check` (section 2a).
- `data/gold3-ct/verse/facts.jsonl` and `data/gold3-ct/totalsegmentator/facts.jsonl`: one line per VerSe series and per TotalSegmentator subject, what its masks hold (each level's voxels, head-foot extent, faces it touches and pieces; the field's edges; the ribs' contacts for TotalSegmentator; the masks' sums as one digest), made by bordercall's holdings/fullspine_facts.py, with `FACTS.json` beside each recording where they were read, bordercall's commit, the source and the check of every mask against its CT's header. `verse/series.json` maps each VerSe series to its patient and age (VerSeFusion's configs/verse_demographics.csv), and `totalsegmentator/subjects.json` carries the release's meta.csv columns the dataset uses (age, institute, split).
- `data/gold3-ct/enhance-pet/facts.jsonl`: one line per ENHANCE.PET study, and per repaired mask, with what its masks hold: the file's bytes and sha256, the grid and orientation, the scanner columns of CT-details.xlsx, each label's voxels, head-foot extent, centroid and pieces, each rib's voxels and the vertebra labels it touches within 3 mm, and the shortest 3-D distance between neighbouring labels and from each lumbar label to the sacrum. They are made by bordercall's holdings/enhance_facts.py, which needs numpy and scipy and so lives there; `FACTS.json` beside them records the tool, bordercall's commit, the input hashes, the date and the row count.
- `data/gold3-ct/enhance-pet/facts-b.jsonl`: the second reading of the same masks, by bordercall's holdings/enhance_facts_check.py, written blind from SPEC.md; check Q14 sets it beside facts.jsonl study by study. Until the facts are taken, `facts-repaired.jsonl` holds the three repaired rows read in the thread's container, and `tools/gold3_ct.py take-facts` joins them to a reading of the published masks and removes it.
- `data/gold3-ct/enhance-pet/touch.json`: the repair record's shortest 3-D distances between L4, L5 and the sacrum for 143 studies, measured by its own touch.py, which the grid job's cross-check sets beside the facts' distances.
- `data/gold3-ct/verse.json`: the 17 series the older records read, with what they say of each, its read and its holdout or fold role; no paths. Their anomaly rows keep these reads.
- `data/gold3-ct/totalsegmentator.json`: the older count of 142, the subject list's grid path and sha256, kept to set beside the field test's admitted subjects once a grid job reads the list.
- Generated and checked: STATS.md and QA.md in this folder, written by `stats` and `qa`, and the private page's data, written by `page`.

No voxel is copied into the repository or into the store. A row points at its CT and masks where they sit: the public bucket's address for ENHANCE.PET (s3://enhance-pet-1-6k/imaging-data/...), and the grid's path pattern for the others. The masks the thread read are kept in the Claude project's files, in the folder gold3-ct/enhance-pet-source, with the repair record in enhance-pet-repair, and on the grid under members.json's grid root once its held says so; the bucket is public, so they can be read again.

## 4. Anomaly classes and their status

Two column calls are made for every study and never merged. The call by names reads the release's labels: T and L as the thoracic and lumbar labels present, with the presacral count, so a typical spine is T12L5 with 24 bodies above the sacrum, an L6 spine T12L6 with 25 and a spine with no L5 T12L4 with 23. The call by ribs reads the ribs: which body each rib meets, on each side, and so how many rib-bearing bodies there are and how many bodies lie below the lowest of them down to the sacrum. Where most ribs meet the body one level off their own, the release's names are suspect.

Each study has one primary class:

- normal: T12L5 by its names, and the ribs agree.
- l6_twelve_ribs: an L6 below an L5 with twelve rib pairs (an S1 freed from the sacrum, or a column one body long).
- l6_thirteen_ribs: an L6 with a thirteenth rib on the body named L1, 25 bodies; the scheme has no T13.
- four_lumbar_twelve_ribs: L4 meets the sacrum with twelve rib pairs (23 bodies, or an L5 counted into the sacrum).
- eleven_ribs: the lowest rib on T11 on both sides, a T12 that bears no rib.
- asymmetric_ribs: eleven ribs on one side and twelve on the other.
- labelling_error: the record's three, 0529 (L5 skipped), 0245 (labels one level high) and 0603 (T6 split).
- open: 0005 and 1336, which need the CT.
- look: an L5 fragment (0179, 0213, 0270, 1240) or labels out of order (0816 and 1273 clearly, 0040 and 1463 weakly).
- not_whole: no C2 in the field.
- repaired: the three repaired studies, gold 4.

Before the classes extend to every whole study they must give exactly the numbers of the note's table "What the ribs say about the unusual lumbar counts" on its 107 unusual studies and 100 controls: of the 67 L6 spines below an L5, 51 with twelve rib pairs and 14 with thirteen; of the 39 with L4 at the sacrum, 24 with twelve and 8 with eleven, and 1186 asymmetric; the 3 labelling errors and the 2 open. A build that does not reproduce them is a bug, found before anything else.

Each anomaly carries a status, which answers the owner's "quality assurance they are true anomalies" as far as masks can:

- confirmed_by_masks: the release's names and the ribs agree and every structural check passes. That is the internal agreement of two masks the same readers checked; it is not a reader's read of the CT.
- candidate: the class rests on the names alone, or a check says look.
- labelling_error and open, as above.
- reader_confirmed: given only by a recorded reader verdict; there are none yet.
- needs_ct: set on every lumbosacral question, sacralisation, lumbarisation or a Castellvi type, which no check of a mask can settle; the row says so.

## 5. Quality assurance: what it can show and what it cannot

Each check gives an id, a version, a verdict (pass, fail, look or not_run), the value, the threshold and why, and lands in the store's qa_check table and in QA.md, with every fail and look by study id. The thresholds are named constants, taken from bordercall's holdings/count_enhance_pet.py where it has them.

| Check | What it looks at |
| --- | --- |
| Q01 header | the mask is readable, of an integer type (most are unsigned 8-bit, 17 are 16-bit), with a sane shape and affine, on the same grid as the rib mask |
| Q02 alphabet | only the scheme's ids, 0 to 28 for vertebrae and 0 to 27 for ribs; no voxel outside the scheme |
| Q03 whole rule | C2 and the sacrum with at least 200 voxels and every level between, an absent L5 excepted |
| Q04 order | neighbouring labels in head-foot order |
| Q05 gaps | a gap over 20 mm fails, over 10 mm is a look |
| Q06 top slice | C2 in the field's top slice, so its top may be cut off (look) |
| Q07 L5 fragment | an L5 under a quarter of L4's voxels (look) |
| Q08 junction | the lowest lumbar label touches the sacrum in 3-D, so no body without a label lies between |
| Q09 rib ladder | each rib meets its own vertebra; most ribs one level off the same way is a shift (fail) |
| Q10 lowest rib | the lowest rib on each side meets its own vertebra |
| Q11 split piece | a column label under 0.4 of both neighbours' voxels (look) |
| Q12 fragments | a label whose largest piece holds under 0.9 of it (look) |
| Q13 C7 and T1 | their voxel ratio outside the controls' 1st to 99th percentile (look) |
| Q14 two readings | two separate implementations agree on what Q08 to Q10 read |
| Q15 slice spacing | CT-details.xlsx against the NIfTI (look; Leipzig study 1213 is the known exception) |
| Q16 bytes | the mask's bytes equal the bucket's listing |

What it can show: that each mask is the file the bucket lists and reads cleanly in its scheme; that a study is whole by the rule; that its labels are in order, without gaps, split pieces or fragments; and that the release's names and the ribs, two masks drawn and checked by the same readers, tell the same story, read twice by separate code.

What it cannot show:

- Agreement between two masks the same readers checked is not a reader's read of the CT. confirmed_by_masks says the masks hold together, not that the anomaly is in the patient.
- A lumbosacral question always needs the CT. The ribs cannot tell an L5 counted into the sacrum from a column one body short, nor say whether a thirteenth rib-bearing body arose at the thoracolumbar or the lumbosacral junction, and nothing in this repository or in bordercall types Castellvi, counts sacral segments or finds the iliolumbar origin.
- No check reads CT intensity, the metal rule or the match of a mask to its CT; those need the CTs, which are on the grid or not held (section 7).
- A rib with no spine label within 3 mm says nothing, so a study read on one side only, or on none, is thinner than its count looks.

The reader bench is the step past this: a private page that shows each candidate's mask projections to a reader and records the verdict in the page's database. Only such a recorded verdict makes an anomaly reader_confirmed.

## 6. Building, querying and exporting

```
python3 tools/gold3_ct.py build [--root DIR]
python3 tools/gold3_ct.py query "SELECT source, tier, count(*) FROM item GROUP BY source, tier" [--root DIR]
python3 tools/gold3_ct.py stats
python3 tools/gold3_ct.py qa
python3 tools/gold3_ct.py export --format json --tier gold3 --training-only
python3 tools/gold3_ct.py page
python3 tools/gold3_ct.py check
```

- `build` makes the store from the committed files alone, deterministically, in a folder outside the repository named by `--root` or the variable GOLD3_ROOT; on the grid it would be the data root's _gold3_ct. The layout is the catalog's: versions/gold3-NNNNNN-<12 hex>.sqlite at mode 0444, VERSIONS.jsonl, CURRENT and LOCK, and unchanged bytes make no new version. Its tables keep the catalog's table and column names where tools/licences.py reads them (build, source, person, person_alias, item, mask, label, rib, anomaly, qa_check, qa_review, shard and embedding), and views answer the common questions: gold 3 persons by member, anomalies by class and status, the QA failures and the workflow's manifest. A cut by tools/licences.py derive takes every row of a source its recipe refuses.
- `query` runs one read-only query on the current version and prints the rows, tab-separated or as JSON.
- `stats` counts, by member and by ENHANCE.PET site, the studies, the persons as a range, the whole studies and every class with its 95 percent Wilson interval, the project's convention, with the distributions of rib pairs, of the body the lowest rib meets, of the presacral count and of the L4 to sacrum distance, and the reasons for each exclusion; it writes STATS.md here.
- `qa` runs the checks of section 5, writes QA.md here and prints each check's verdict counts; `build` writes the same results into the store's qa_check table.
- `export` writes the manifest the workflow reads, as JSON or CSV: one row per study with its person, member, site, tier, part, anomaly class and status, and where its CT and masks are. The part comes from `data/splits/rule.json`'s rule applied to the person key, by the same function tools/catalog.py uses; holdout and fold persons of `data/splits/anomaly-holdout.json` are flagged with training_allowed false, and `--training-only` leaves them out.
- `page` writes the private page's data file, page-data.json here, from the committed files, or from a store's current version with `--root`.
- `check` fails when STATS.md, QA.md or the page's data is stale, when the facts break their schema, when the ENHANCE.PET classes no longer give the note's table, or when the rows' tiers differ from members.json's counts; scripts/check.sh runs it.

The person key is `<member>:<native id>`, such as enhance_pet:0001. ENHANCE.PET's autoPET persons are not known yet and Leipzig and Careggi carry no person id, so for splits each ENHANCE.PET study is its own person, and a person with two studies could fall in two parts. That leakage risk is recorded in the store, and the grid match of section 7 closes it for autoPET.

The private page, the artifact the owner asked for, is made by the coordinator from `page`'s data: an overview, the members, the anomaly statistics with their intervals, a searchable table of the studies, the QA results, the reader bench and a SQL tab over the same schema in the browser. It is published privately, with no connector and never shared by link, and copied under artifacts/ with its row there: Gold Tier 3 CT, https://claude.ai/artifact/XDGjjGKVcdi2xDht7a689w, published on 2026-10-28 and kept in artifacts/gold-tier-3-ct-xdgjjg/, whose README says how to publish it again. Its store is a copy with the grid locations and the anomaly route's notes taken out, and its numbers are worked out in the page from the counts. The bench's verdicts are kept in the page, one document per reader in its collection verdicts, and are read with the Artifact database tool or the page's download; nothing moves them into qa_review yet, so reader_confirmed stays empty until that import is built.

## 7. What waits for the grid and the owner's word

Nothing has gone to the grid, and nothing goes while the owner's hold stands (2026-10-28 21:17 UTC: grid and WSU data use for the Bayesian work waits for his own attorney's advice). Each item below waits for his word and the number of jobs, offered once as a card. On 2026-10-28 at 00:04 UTC he asked for the mask reading to run on the grid; docs/checkpoints/2026-10-28-gold3-ct-grid/HANDOFF.md is that plan, and members.json (grid.held) and FACTS.json (read_on) say whether any of it has run.

- One CPU job that reads only what is already on the grid and segments nothing, for which a gate word and its script come by pull request first: (a) completion, every admitted VerSe and TotalSegmentator study's missing levels taken from the census's SPINEPS mask of the same CT (section 2c), checked to lie on the CT's grid, relabelled where SPINEPS wrote its raw ids, and written as the machine arm with its sha256; (b) gold 4, the field test run over the census's 17,198 SPINEPS masks, with its counts by collection the only thing that leaves the grid; (c) held, every file of the three members under its canonical root hashed and set beside the sums recorded here (section 2b); (d) the autoPET mask-to-CT match by shape and affine, and the 142 of the older TotalSegmentator list set beside the field test's admitted subjects; and (e) each admitted TotalSegmentator CT's own image extent, where its grid is padded, set beside the plane the field test reads from the cord and the column.
- Copying ENHANCE.PET's labels to the grid with the existing word `fetch aws_enhance_pet_labels`, which lands the whole ground-truth prefix: 11,256,936,591 bytes, measured from the public listing on 2026-10-27, of which the vertebra masks are 381,439,888 bytes and the rib masks 312,882,241. The word's line still says 2.5 GB and that it is not yet the owner's yes.
- The Leipzig and Careggi CTs, 45,207,300,328 bytes for the 581 whole studies with the three repaired, through a new url-route line that needs a pull request first.

Beyond the grid: a person's look at every border case (look), which admits it or leaves it silver; a reader's verdict on every candidate anomaly, by two readers counting from C2 with the rib pairs, recorded on the bench; and any loosening of a licence class, which is the owner's alone.

## 8. Decisions taken on the owner's behalf

Each is the recommended option of the thread's open questions, recorded here for the owner to overrule. On 2026-10-28 at 17:08 UTC the owner overruled 3 and 4 ("I DISAGREE THAT ONLY 17 VERSE SHOULS BE INCLUDED AND NO TOTALSEGMENTATOTR BUT ILL HANDLE THAT ON THE NEXT ACCOUTN"), and at 22:58 UTC he said what replaces them (section 2a): admit every CT whose volume shows the full spine and complete what its masks lack. 3 and 4 are kept below as the record of what changed; 10 to 18 were taken by the thread that carried his answer out, on 28 and 29 October.

1. The dataset lives in SchwingNet; the code that reads the masks lives in bordercall, since it needs numpy and scipy.
2. ENHANCE.PET's masks, checked by four readers, are a person's annotation, gold 3, as the note says.
3. Superseded on 2026-10-28 at 22:58 UTC: TotalSegmentator's 142 stayed gold 3 by the records, with no rows until the grid. Every subject now has a row and the field test decides.
4. Superseded on 2026-10-28 at 22:58 UTC: VerSe's 17 were gold 3, provisional until the sacrum was confirmed. Every series now has a row and the field test decides; the 17 keep their reads.
5. The person key is `<member>:<native id>`; an ENHANCE.PET study is a person for splits, its persons reported as a range, the leakage risk recorded.
6. Holdout and fold persons are carried, flagged, with training_allowed false.
7. The rib rule reported is the release's (a rib of 50 voxels or more, meeting the spine within 3 mm); Moller's 38 mm rule is named as the other.
8. Per-study public ids appear in the committed files and on the private page, as data/splits already does.
9. The dataset stands alone and feeds the tiers sort later; it does not change pull request #420.
10. A C2 a person drew is in view unless the field's top cuts the level below it too, which leaves a sliver of C2 in the field; one not drawn is placed by tables measured on the members' own whole spines, between their 5th and 95th percentiles (section 2a).
11. The sacrum is in view only with 20 mm of S1 below its top, so the L5-S1 disc and the top of S1 are in the field, whether a person drew it or the table places it; a sacrum the field's foot cuts short of that is out when the last level above it is cut too and a border case otherwise. ADMISSION.md gives the counts at 10 and 30 mm beside it.
12. A border case at either end is silver 3 until a person's look admits it, never gold by default.
13. Children (under 18 at the scan) and the other flags are carried and flagged, never left out.
14. TotalSegmentator's hand-refined masks stay a person's annotation, so its admitted subjects are gold 3, flagged; a subject whose masks are byte for byte another's shares the first's person.
15. A member's canonical grid root is its copy on the data root; a copy in the grid home is another copy (section 2b).
16. The auto-anatomist is trained under the recipe non-commercial, which takes all three members whole (section 2d).
17. The field over a level is read along the world's vertical line through it, and a padded TotalSegmentator grid's field ends where the spinal cord and the column stop together; the CT's own extent, read on the grid, would settle a padded grid for good (section 7).
18. A name the column's order skips where its drawn neighbours leave no room for a body is a count variant or a skipped label, flagged name_skipped and never a level to add; each ENHANCE.PET study is judged once, on its repaired mask where it has one.

## 9. Related

- [ENHANCE.PET 1.6k in the evidence tiers](../enhance-pet-gold-tier-3.md): the count, the ribs and the repaired three; bordercall's holdings/gold-tier-3.md holds the same finding.
- [SPINEPS to FleXray: finding anomalous spines](../spineps-anomaly-route.md): the route whose holdout and folds the export flags.
- [The frame catalog](../data-catalog.md): the store's pattern, which this dataset follows.
- [Chapter 04 of the textbook](../../textbook/04-the-registry-and-the-holding.md): the holding by evidence tier.
