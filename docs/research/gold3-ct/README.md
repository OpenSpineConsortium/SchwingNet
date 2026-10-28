# The gold tier 3 CT dataset

Source: the thread "Finish scan import and tier counts" of the symphony project, 27 October 2026, the owner's ask of 22:49 UTC, in his words: "well whenvever this finishes i want all the gold tier 3 CT data as its own dataset, with a indexable database, an artefact, and anything i need to use it in the workflow, including anomaly statistics, and quality assurance they are true anomalies". The thread's design brief and build spec are kept beside this README as BRIEF.md and SPEC.md, as the thread wrote them in its container; where they and this README differ, this README is the later word. ENHANCE.PET's own finding, which most of the counts here rest on, is [ENHANCE.PET 1.6k in the evidence tiers](../enhance-pet-gold-tier-3.md). Confidential: this programme describes unpublished data work and never leaves this private repository.

Where it stands: the records under `data/gold3-ct/` and the tool `tools/gold3_ct.py` are written and tested, and the dataset builds from what is committed here with no grid job. ENHANCE.PET's rows, one for each of its 1,597 studies and one for each repaired mask, come from its facts file (section 3), read from the published masks in the thread's container or, as the owner asked on 2026-10-28 at 00:04 UTC, on the grid by docs/checkpoints/2026-10-28-gold3-ct-grid/HANDOFF.md; until that file is committed the dataset carries ENHANCE.PET's counts by the records, and STATS.md says which holds. VerSe's 17 have rows from the records; TotalSegmentator's 142 are declared with their count and no rows. Whether the grid has fetched and read the masks is said by members.json (ENHANCE.PET's grid.held) and FACTS.json (read_on), not by this paragraph. No reader verdict is recorded, so no anomaly is yet confirmed by a reader. What waits is section 7; the choices made on the owner's behalf are section 8, for him to overrule.

## 1. What the dataset is, and why

It is every CT the project counts as gold tier 3, kept as one dataset of its own: one row per study, with its person key, member and site, tier, the facts read from its masks, two column calls kept apart, an anomaly class with its status, and the result of every quality check. It is held as a read-only, versioned SQLite store, as the frame catalog is, and it gives the workflow one manifest to read.

The tiers are the owner's of 27 October 2026. Gold is a field from C2 to the sacrum in one study, silver a partial one. Tier 1 is a real CT and X-ray pair with a person's annotation, 2 the pair without one, 3 one modality with a person's annotation and 4 one modality without. A machine mask or a synthetic image never raises a tier. Truth comes only from whole spines countable from C2 to the pelvis, and a spine is never dropped for a missing or an extra lumbar label (the owner, 17:10 UTC).

Why one dataset: no held person is gold 1 or gold 2, so these CTs are the project's only spines counted from C2 under a person's annotation, and the anomaly route, the DRR renders and the tiers sort draw on them. Until now they sat in three sources with three label schemes, two person-id spellings and four versions of the whole-spine rule. Kept together they get one person key, one whole rule, one set of anomaly classes with intervals, and one place where each anomaly's evidence is checked.

## 2. Members and counts

| Member | Source record | Studies with rows | Gold 3 | Persons | What the count rests on |
| --- | --- | --- | --- | --- | --- |
| ENHANCE.PET 1.6k: autoPET, Leipzig, Careggi | scidb_enhance_pet_1_6k | 1,597, with 3 repaired masks beside them | 1,557 studies | 865 to 1,478 | the published vertebra and rib masks, read where FACTS.json's read_on says |
| VerSe 19 and 20 | verse | 17 | 17, provisional | 17 | the committed records; provisional until the sacrum is seen on the grid |
| TotalSegmentator v3 | totalsegmentator | none yet | 142, perhaps 156 | 142 to 156 | the count in the records; the subject list is on the grid only |

Before any check across members, the three give at most 1,637 gold 3 persons, or 1,651 if TotalSegmentator's count is 156.

ENHANCE.PET by site:

| Site | Studies | Whole, C2 to the sacrum | Persons |
| --- | --- | --- | --- |
| autoPET | 1,014 | 979 | 865 to 900 |
| Leipzig | 384 | 379 | at most 379, no person id |
| Careggi | 199 | 199 | at most 199, no person id |
| All | 1,597 | 1,557 | at most 1,478, at least 865 of them autoPET's |

What each count rests on:

- ENHANCE.PET. MOOSE drew the masks; a medical student verified and corrected each scan, a second student reviewed the first, and a radiology resident and a nuclear medicine resident reviewed both, by the paper's Methods (Ferrara D et al., Scientific Data 2026). Checked and refined by people, they are a person's annotation, so a whole study is gold 3. The whole rule: C2 and the sacrum each with at least 200 voxels and every level between them, an absent L5 excepted, as the owner asked at 17:10 UTC. The 1,014 autoPET studies are 900 persons (Gatidis S et al., Scientific Data 2022;9:601), so its 979 whole studies are 865 to 900 persons. CT-details.xlsx gives no person id for Leipzig or Careggi, so their 578 whole studies are at most 578 persons, and the 1,478 is an upper bound. Of the other 40 studies, 37 have no C2 and are silver 3, and 3 (1134, 1283 and 1347) were left out for a skipped or scrambled label and repaired, two by renaming the readers' labels as the ribs direct and one with MOOSE's rerun; their names come from a rule or a machine, so they stay gold 4, with the repaired masks kept beside the published ones as the rows 1134r, 1283r and 1347r.
- VerSe. 17 series run from C1 or C2 into the lower lumbar spine with the lumbosacral junction in the field, by the records. VerSe labels no sacrum, so each stays provisional until the sacrum is seen on the grid. The records hold a read for nine of the 17 and none for the other eight. Persons in the anomaly route's holdout or its folds (`data/splits/anomaly-holdout.json`) are carried, flagged, and refused for training.
- TotalSegmentator. 142 v3 subjects whose release masks hold C2 to L5 and the sacrum, each with at least 200 voxels, and no metal; 14 more that the level or metal rule dropped may make 156 once read. The masks are model output refined by hand, counted as a person's annotation and flagged. The release scheme cannot express an L6 or a T13, so a count from it is typical as far as the scheme can say. The subject list sits on the grid alone (model_night/ts_clean_subjects.txt in the grid home, sha256 2f96f917292b85416d1b803230732624a3dde0bae7c2c29f54abc4f2a30dc1b7), so the member has its count and no rows until the grid index job reads it.

Licences, as `data/licences.json` classes them: ENHANCE.PET CC BY 4.0 for Leipzig and Careggi and CC BY-NC 4.0 for autoPET, non-commercial as one set; VerSe CC BY-SA 4.0, share-alike; TotalSegmentator CC BY 4.0, open.

## 3. Where the records are

- `data/gold3-ct/members.json`: the three members, with each one's source record, label scheme, mask author, licence by site, grid roots (which copy is canonical is not settled), person-key rule, whole rule, counts, tier and caveats.
- `data/gold3-ct/enhance-pet/facts.jsonl`: one line per ENHANCE.PET study, and per repaired mask, with what its masks hold: the file's bytes and sha256, the grid and orientation, the scanner columns of CT-details.xlsx, each label's voxels, head-foot extent, centroid and pieces, each rib's voxels and the vertebra labels it touches within 3 mm, and the shortest 3-D distance between neighbouring labels and from each lumbar label to the sacrum. They are made by bordercall's holdings/enhance_facts.py, which needs numpy and scipy and so lives there; `FACTS.json` beside them records the tool, bordercall's commit, the input hashes, the date and the row count.
- `data/gold3-ct/enhance-pet/facts-b.jsonl`: the second reading of the same masks, by bordercall's holdings/enhance_facts_check.py, written blind from SPEC.md; check Q14 sets it beside facts.jsonl study by study. Until the facts are taken, `facts-repaired.jsonl` holds the three repaired rows read in the thread's container, and `tools/gold3_ct.py take-facts` joins them to a reading of the published masks and removes it.
- `data/gold3-ct/enhance-pet/touch.json`: the repair record's shortest 3-D distances between L4, L5 and the sacrum for 143 studies, measured by its own touch.py, which the grid job's cross-check sets beside the facts' distances.
- `data/gold3-ct/verse.json`: the 17 ids with what the records say of each, its read and its holdout or fold role; no paths.
- `data/gold3-ct/totalsegmentator.json`: the count, the subject list's grid path and sha256, no rows, and why.
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

The private page, the artifact the owner asked for, is made by the coordinator from `page`'s data: an overview, the members, the anomaly statistics with their intervals, a searchable table of the studies, the QA results, the reader bench and a SQL tab over the same schema in the browser. It is published privately, with no connector and never shared by link, and copied under artifacts/ with its row there.

## 7. What waits for the grid and the owner's word

On 2026-10-28 at 00:04 UTC the owner asked for the mask reading itself to run on the grid; docs/checkpoints/2026-10-28-gold3-ct-grid/HANDOFF.md is that plan, with its own count of one fetch and one CPU job, and is the later word where it and this list differ. Whether that fetch and job have run is said by members.json (ENHANCE.PET's grid.held) and FACTS.json (read_on and reproduced_on), not by this list. Each item waits for the owner's word and the number of jobs, offered once as a card:

- Copying ENHANCE.PET's labels to the grid with the existing word `fetch aws_enhance_pet_labels`, which lands the whole ground-truth prefix: 11,256,936,591 bytes, measured from the public listing on 2026-10-27, of which the vertebra masks are 381,439,888 bytes and the rib masks 312,882,241. The word's line still says 2.5 GB and that it is not yet the owner's yes.
- The Leipzig and Careggi CTs, 45,207,300,328 bytes for the 581 whole studies with the three repaired, through a new url-route line that needs a pull request first.
- One CPU job for the grid index: each autoPET mask matched to its held FDG-PET-CT-Lesions CT by the shape and affine of its NIfTI, which has not been tried; TotalSegmentator's 142 rows from the subject list; and VerSe's sacrum. It needs a gate word that does not exist yet, and the owner's count.

Beyond the grid: a reader's verdict on every candidate, by two readers counting from C2 with the rib pairs, recorded on the bench; the tier policy for TotalSegmentator's hand-refined masks, 142 or 156, and which copy of TotalSegmentator and VerSe on the grid is canonical; and any loosening of a licence class, which is the owner's alone.

## 8. Decisions taken on the owner's behalf

Each is the recommended option of the thread's open questions, recorded here for the owner to overrule:

1. The dataset lives in SchwingNet; the code that reads the masks lives in bordercall, since it needs numpy and scipy.
2. ENHANCE.PET's masks, checked by four readers, are a person's annotation, gold 3, as the note says.
3. TotalSegmentator's 142 stay gold 3 by the records (hand-refined masks), flagged, with no rows until the grid.
4. VerSe's 17 are gold 3, provisional until the sacrum is confirmed.
5. The person key is `<member>:<native id>`; an ENHANCE.PET study is a person for splits, its persons reported as a range, the leakage risk recorded.
6. Holdout and fold persons are carried, flagged, with training_allowed false.
7. The rib rule reported is the release's (a rib of 50 voxels or more, meeting the spine within 3 mm); Moller's 38 mm rule is named as the other.
8. Per-study public ids appear in the committed files and on the private page, as data/splits already does.
9. The dataset stands alone and feeds the tiers sort later; it does not change pull request #420.

## 9. Related

- [ENHANCE.PET 1.6k in the evidence tiers](../enhance-pet-gold-tier-3.md): the count, the ribs and the repaired three; bordercall's holdings/gold-tier-3.md holds the same finding.
- [SPINEPS to FleXray: finding anomalous spines](../spineps-anomaly-route.md): the route whose holdout and folds the export flags.
- [The frame catalog](../data-catalog.md): the store's pattern, which this dataset follows.
- [Chapter 04 of the textbook](../../textbook/04-the-registry-and-the-holding.md): the holding by evidence tier.
