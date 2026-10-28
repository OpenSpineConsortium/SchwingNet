Source: thread "Finish scan import and tier counts", 2026-10-27 to 28, the thread's own brief for the gold tier 3 CT dataset, written in its cloud container and kept here so a session on the grid can build from it (docs/checkpoints/2026-10-28-gold3-ct-grid/HANDOFF.md). The README beside it says where the programme stands; where they differ, the README is the later word.

Paths under /tmp/claude-0/ and /mnt/project-files/ name the thread's cloud container and the Claude project's files, which a grid session cannot read; the handoff of 2026-10-28 (docs/checkpoints/2026-10-28-gold3-ct-grid/HANDOFF.md) says where each lives on the grid. The owner moved the mask reading to the grid on 2026-10-28 00:04 UTC.

# Gold tier 3 CT dataset: design brief

This brief draws on five reader reports and my own read-only checks on 27 October 2026. I changed nothing, fetched nothing and started nothing. Unless a path says otherwise, it is in /home/claude/SchwingNet, branch claude/project-thread-cne00q at d7eede4, "Merge main into the ENHANCE.PET count branch". That branch has unstaged edits that are not mine: docs/research/README.md, docs/research/enhance-pet-gold-tier-3.md and docs/textbook/04-the-registry-and-the-holding.md. PR #420 was read at 828fb90 and not changed.

## 0. What I found myself, beyond the five reports

- **The ENHANCE.PET masks are in this container now, but they will not last.** bordercall holdings/gold-tier-3.md:18 says "the container does not keep them". Today they are here:
  - /tmp/claude-0/enh/masks: 1,597 vertebra masks, 367 MB.
  - /tmp/claude-0/enh/ribs: 1,597 rib masks, 302 MB.
  - /tmp/claude-0/s/enh/CT-details.xlsx, plus ct_details_rows.json and labels.json beside it.
  - The bucket listings with exact bytes: /tmp/claude-0/enh/ct_keys.json, keys.json and rib_keys.json.
- **The per-study outputs of holdings/count_enhance_pet.py are in the scratchpad**, at /tmp/claude-0/-home-claude/d63b09b0-2bbd-5a24-9c75-f56391308481/scratchpad/run/:
  - extents.json: 1,597 studies, extents in mm and voxels per label.
  - sites.json: site per study.
  - count.json: class per study, plus 23 lists including gold_3 with 1,557 ids, l6, no_l5, out_of_order and c2_in_top_slice.
  - ribs_pairs.json: rib pairs and voxels for all 1,597.
  - ribs_contacts.json: lowest-rib contact tally for 214 studies.

  These files are the seed of the ENHANCE.PET member. Turning them into committed facts needs no fetch. They should be taken before the container is lost.
- **The repair folder can be reached from here.** /mnt/project-files/enhance-pet-repair (a link to /mnt/attach/project-files, 237 MB) holds the README, SHA256SUMS, the ct/, published/, repaired/ and moose/ folders, and the scripts with their JSON outputs (oo, step, touch, compare, final). The anomaly reader thought it was out of reach.
- **The ENHANCE.PET CT bytes are exact now**, summed from ct_keys.json by site in sites.json:

  | CTs | Studies | Bytes |
  |---|---|---|
  | All in the bucket | 1,597 | 197,321,490,975 (grid/run-platform-fetch.sh:105 states 177 GB) |
  | autoPET | 1,014 | 151,989,888,830 |
  | Leipzig | 384 | 35,669,987,160 |
  | Careggi | 199 | 9,661,614,985 |
  | Whole Leipzig and Careggi | 379 + 199 | 44,963,586,694 |
  | The same plus the 3 repaired | 382 + 199 | 45,207,300,328 (holdings/gold-tier-3.md:98) |

- **CT-details.xlsx carries no autoPET or TCIA subject id.** Its columns are Patient, Data-Source, Manufacturer, Model, kVp, Filter, Convolutional Kernel, Pixel Spacing, Slice Thickness and Focal Spots. So each autoPET mask can be matched to its held FDG-PET-CT-Lesions CT only by the NIfTI's shape and affine, with the scanner columns to break ties.
- **docs/memory/MEMORY.md is already 33,599 bytes in 70 lines**, over the 25 KB its own rule sets (.claude/rules/memory.md). tools/check_docs.py does not enforce the size, so a new index line has to be short.

**Headline counts**

| Member | Gold 3 | Persons | Condition |
|---|---|---|---|
| TotalSegmentator | 142, perhaps up to 156 | 142 to 156 | Only if the owner counts its hand-refined masks as a person's |
| VerSe | 17 | 17 | Only once the sacrum is confirmed on the grid |
| ENHANCE.PET | 1,557 studies | 865 to 1,478 | autoPET 979 studies = 865 to 900 persons; Leipzig 379 and Careggi 199 carry no person id, so at most 578 persons |
| Upper bound | | about 1,637 | Before deduplicating across sources |

## 1. What already exists and must be reused

**Label ids and mask reading**
- tools/anomaly_pack.py:64-80: the 28 canonical ids (`CANONICAL`, with `T13, L6, SACRUM = 20, 26, 27`), plus `VERSE_TO_CANONICAL`, `DROPPED`, `PRESACRAL` and `TOP_IDS`.
- tools/nifti_label.py: a NIfTI-1 reader and rewriter in the standard library alone. Its refusal reasons are at :40-43; `check_against_ct` is at :242-252.
- src/schwingnet/segmenters.py:62-78, the one home for alphabets, which today has only spineps, moose and none.
- bordercall scanimport/schemes.py:41-84: `ENHANCE` (L1-L6 = 20-25, sacrum 28, hips 26 and 27, no T13), `TOTALSEG_FILES`, `TOTALSEG_RIB_FILES` and `EXPRESSES`. These maps should be ported into segmenters.py.
- **Do not feed ENHANCE.PET masks through `VERSE_TO_CANONICAL`.** It would turn the right hip (26) into the sacrum, drop the left hip (27) as coccyx, and turn the real sacrum (28) into T13. A separate map is needed: 1-25 as VerSe, 28 to 27, and 26 and 27 to background.

**Counting and classing**
- bordercall holdings/count_enhance_pet.py: steps `extents`, `sites`, `count`, `ribs` and `report`; classes at :581; `variants_of` at :510-523; rib contact at :125-137; `REPAIR_RECORD` at :168; tests under holdings/tests.
- tools/bordercall_corpus.py: the count from C2 and its gap rule (:18-28, :84-86), the phenotypes (:279-322) and `ROW_FIELDS` (:90-94).
- tools/anomaly_route.py: `truth_of` (:81-97), `call_of`, `two_labeller_call` (:128-134), the disputed rule (:141-146), and `check --holdout --list`.
- tools/anomaly_pack.py `countable_of` (:439-465).
- src/schwingnet/chain.py:34-57: the column call `T{11..13}L{4..6}`.

**The store pattern**
- tools/catalog.py:1-30: `versions/`, mode 0444, `VERSIONS.jsonl`, `CURRENT` and `LOCK`.
- Its schema (:103-187), the `build` table with the split hashes (:104-111, :251-264), and `split_check` (:896-925).
- tools/licences.py `derive`, `drop_sources`, `provenance` and `counts_by_source` (:236-383) work unchanged on any SQLite that has the catalog's table and column names.

**Splits**
- data/splits/rule.json, anomaly-holdout.json and anomaly-validation.json are used as they stand.
- No new file goes under data/splits or data/registry: both are in tools/run_code.py:50 `SPLIT_RULES`, so a new file there changes the bank and catalog keys.

**Inventory and licences**
- data/sources/{totalsegmentator,verse,scidb_enhance_pet_1_6k}.json; none has `grid_path`.
- data/licences.json:727, 791 and 831.
- data/reproduce/sources.json cards: verse19_20 at :2493 and :2591-2595; TotalSegmentator v3 at :3943 and :4062; tcia_fdg_pet_ct_lesions at :13183; devcorpus with ts_clean_subjects.txt at :27734-27815.

**The page pattern**
- tools/storage_panel.py: `record_of` at :1395-1450 and `check` at :1456-1490.
- tools/experiments_panel.py, and scripts/check.sh:109-124 for their check lines.
- Data is put inline in the page (docs/research/experiments-panel.md:17).

**The QA bench pattern**
- artifacts/lstv-verification-bench-6m2qhr/ (a `verdicts` collection in the page's db, data in bench_data.js) and artifacts/level-verification-bench-mkjxsy/.

**The grid**
- grid/gate.sh: the word list at :192; `submit`; `checkout_holders` at :334; `settle_banks` at :1734-1743.
- grid/size-rule.sh: `size_and_admit` at :1083; the admission pattern of grid/anomaly.sbatch at :94-96 and :302-326.
- grid/run-platform-fetch.sh:105-106 and the s3 sizer in grid/fetch_size.py:349-395.

**Per-subject records already on the grid** (not readable from here)
- `${HOME}/model_night/ts_clean_subjects.txt`, sha256 2f96f917292b85416d1b803230732624a3dde0bae7c2c29f54abc4f2a30dc1b7.
- spinesurg-ct-nnunet's `transitional_registry/verse/screened.csv`.
- `anomaly_harvest/{totalsegmentator,verse,validation_ts,tcia_fdg_pet_ct_lesions}/{cases,rows}.csv`.
- `/rs/rs_grp_oschome/go2432/anomaly/select/selection.csv` (Slurm 40785048).
- The Moller rib table at `$RS/ruleclass/arms/moller_fast/`.

**Notes to read, never to change**
- docs/research/enhance-pet-gold-tier-3.md (another thread's edits are open on it) and bordercall holdings/gold-tier-3.md.
- PR #420: docs/research/corpus-tiers/README.md:12, :34 and :37, and data/corpus-tiers/sources.json (TotalSegmentator caveats at :12930, VerSe at :13450).

## 2. Recommended layout (placeholder id `gold3_ct`)

**Committed in the repository**
- data/sources/gold3_ct.json: group `ct`, the licence line per member, counts per member, `measured` left empty.
  - `reach` takes one value. I suggest `get` until the ENHANCE.PET labels sit on the grid.
  - Add per-site records (enhance_pet_autopet, enhance_pet_leipzig, enhance_pet_careggi) only if the owner wants the CC BY open subset, because data/licences.json keys must match a record (`entry_problems`, tools/licences.py:160-177).
- data/gold3-ct/:
  - members.json: per member, the source id, the CT and mask roots on HOME or Ceph, the scheme, the person-key rule and its crosswalk, the licence per site, and the whole-spine rule.
  - enhance-pet.json: per-study facts made from the scratchpad outputs: public study id, site, class, levels present with voxels and z extents, variant tags, rib pairs, lowest-rib contact, and scanner columns. No paths, UIDs or PatientIDs.
  - Later, totalsegmentator.json and verse.json from grid reports.
  - Add `data/gold3-ct` to `PLAIN_TEXT_FOLDERS` (tools/check_docs.py:31).
- src/schwingnet/gold3.py: pure code under the gate. Pydantic shapes for member, manifest, study row and version, and the rules (whole by extents, the column call from count and ribs).
  - New alphabets in segmenters.py: enhance, totalseg_release and verse_release.
  - Tests in tests/schwingnet/test_gold3.py. Functions that take a pydantic model are listed in pyproject.toml `[tool.beethoven-qa.unproven]`.
- tools/gold3_ct.py: standard library, with a module docstring. Subcommands:
  - `ingest-enhance`, which reads the count_enhance_pet outputs;
  - `build [--local|--grid]`;
  - `query`, `summary` and `qa`;
  - `split-check`, which runs anomaly_route's holdout check;
  - `page`, and `check` for the committed files.
  - Tests in tests/test_gold3_ct.py. Place it in tools/run_code.py `KINDS` or `LEFT_OUT`, held by tests/test_run_code.py.
- **The database in two places.**
  - `build --local` makes a SQLite from the committed JSON, so the dataset can be queried in any clone or container.
  - The grid version adds the location columns and stays on the grid. This follows docs/research/data-manifest/README.md:97-98 and :120-125: rows with paths below a root, UIDs or PatientIDs never leave the grid.
- Page: docs/textbook/figures/07/gold3-ct.json as input, with gold3-ct.html (data inline), gold3-ct.svg and the figure record in the `record_of` schema. Chapter 07 places it. Add a `python3 tools/gold3_ct.py check` line to scripts/check.sh.
- Optional claude.ai artifact:
  - Publish the built page privately with no connector, then copy it to artifacts/gold-tier-3-ct-<6 id chars>/ with a row appended to artifacts/README.md.
  - The row is required: artifacts/_synthesis/work/tools/synth_reads.py:53 parses it and :125 refuses a folder without one.
  - A merge touching artifacts/** or data/sources/** starts the synthesis reads (.github/workflows/synthesis.yml:96-106), within their standing 10 a day.
  - A QA bench (section 5) would be a second artifact with a `verdicts` collection in the page's db, exported to records/ by the export skill.
- docs/research/gold3-ct/README.md as a programme folder, with its line in docs/research/README.md. docs/memory/gold3-ct.md with one short line in MEMORY.md.
- Files to regenerate: data/licences.json and data/LICENCES.md (`propose --write`, then `render`); data/reproduce/map.json (`platform`: totalsegmentator_v300, verse19_20, tcia_fdg_pet_ct_lesions, scidb_enhance_pet_1_6k); docs/research/datasets-inventory.md (`tools/sources.py render`); docs/research/datasets-reproduce.md; data/choice/CHOICE.json (`tools/choose_data.py write`); the line in docs/textbook/figures/35/corpora-overlay.json, then `tools/data_figures.py write`.

**On the grid**
- `$DATA_ROOT/_gold3_ct/`:
  - `members/<member>/MANIFEST.json`, content-hashed and never rewritten;
  - `versions/gold3-NNNNNN-<12hex>.sqlite` at 0444;
  - `VERSIONS.jsonl`, `CURRENT` and `LOCK`.
- No voxels are copied. Rows point at the raw copies where they sit, HOME copies included.
- ENHANCE.PET labels land at `$DATA_ROOT/aws_enhance_pet_labels/raw` through the existing fetch.
- `grid/gold3.sbatch` (header only `--time`, `--cpus-per-task`, `--mem`) and a gate word such as `gold3 <index|qa>`.

**Into training, later**
- data/registry/gold3_ct_drr.json: render, synthetic, regions C/T/L/S, with `level_map` projector `render`, the same person keys, then the existing bank, catalog and flow path.

## 3. The index database

Table names follow the catalog so that tools/licences.py `derive` and `provenance` work unchanged. `derive` needs source, item(source, part, sha256, person), person, shard, label(shard) and embedding(item).

| Table | Columns |
|---|---|
| build | version, made_utc, code_digest (run_code style), commit, members_sha256, rule_sha256, holdout_sha256, validation_sha256, whole_rule_version, inputs_json |
| source | source PK (record id or per-site id), record_id, name, site, licence, licence_class, scheme, expresses_l6, expresses_t13, expresses_ribs, mask_author (readers, model refined by hand, machine), reach, grid_root, url, doi |
| shard | shard PK (member manifest id), source, manifest_sha256, made_utc, made_by, run_id |
| person | person PK `<source>:<native id>` (one spelling), source, native_id, persons_low, persons_high (for site-only ids), part (train, val, test, holdout, fold_k), part_reason, anomaly_role (holdout, fold3, validation_drawn, none), training_allowed, child_flag where a record states it (no ages) |
| person_alias | alias, person, kind. Covers ts: and totalsegmentator_v201/_v300; v2 ids s1406-s1429 identical to v3 ids; verse, verse19_20 and versefusion; nnunet_dataset815; ENHANCE autoPET study to FDG-PET-CT-Lesions subject |
| item (one row per CT study) | item PK, source, person, study_native_id, site, part, sha256 (CT), ct_location (grid), ct_url, ct_bytes, shape, spacing_mm, affine_sha256, slice_mm, manufacturer, model, kvp, kernel, tier (gold3, gold4, none), tier_reason, has_c2, c2_in_top_slice, has_sacrum, sacrum_basis (mask, record, look), n_presacral, duplicate_of, shard |
| mask | mask PK, item, kind (vertebrae, ribs), scheme, author, location, url, sha256, bytes, dtype, reasons_refused, matched_by (shape+affine), match_ok |
| label (one row per level) | item, shard, canonical_id, level, source_label, voxels, z_top_mm, z_bottom_mm, gap_to_next_mm, out_of_order, fragment_share |
| rib | item, side, rib_k, voxels, meets_label, meets_level, contacts, tie |
| anomaly (one row per CT) | item, column_call (`T{t}L{l}`, chain.py), presacral_count (23, 24, 25), rib_pairs_left, rib_pairs_right, lowest_rib_meets, label_pattern (L6 named, no L5 with L4 at the sacrum, L5 fragment, ...), route_truth (anomaly_route vocabulary), phenotype (bordercall vocabulary), evidence (read, two labellers, release names plus ribs, single, machine), reader_source (for example the Loeffler table's sha256), status (confirmed, candidate, labelling_error, open, normal), castellvi (empty: no code exists), note |
| qa_check | item, check_id, check_version, verdict (pass, fail, look, not_run), value, threshold, ran_where (container, grid), run_id, ran_utc |
| qa_review | item, reviewer_role, reader_n, verdict, column_call_read, utc, source (the bench db export) |
| embedding | item; empty, kept for `derive` |

Provenance is carried by build, shard and qa_check (input sha256, tool, commit, run).

## 4. Anomaly classes and statistics per source

**One primary call per CT, with the evidence kept beside it.**
- The primary call is chain.py's `T{t}L{l}` and the presacral count.
- The rib reading and the release's label pattern are separate columns, never merged into the call.
- Each vocabulary gets a mapping table into it: anomaly_route.py's L6, T13, four_lumbar, eleven and normal; bordercall's six_lumbar, four_lumbar, lumbar_rib, no_rib_T12 and typical; and count_enhance_pet's variant tags.
- Three conventions name a thirteenth rib-bearing body: T13 in VerSe, L1 plus lumbar_rib in bordercall, and L1 plus an L6 in ENHANCE.PET.

**Classes**
- normal T12L5
- L6, split into twelve rib pairs (S1 freed from the sacrum, or a long column) and thirteen pairs with the thirteenth on "L1" (25 bodies)
- T13
- four_lumbar, L4 at the sacrum (23 bodies or a sacralised L5)
- eleven, a ribless T12
- asymmetric ribs
- labelling_error
- open, where the CT is needed

**Statistics per source, and per site for ENHANCE.PET**
- Studies, persons (as a range) and whole studies.
- Every class with a 95 percent Wilson interval, the convention of docs/memory/the-v1-flow.md:4.
- The evidence tier of each class.
- The distributions of rib pairs (11, 12, 13), lowest-rib-meets, presacral count, and L4-to-sacrum distance in 3-D.
- Sacrum height, descriptive only: holdings/gold-tier-3.md:74 says it is "not a test".
- C2 in the top slice, out-of-order labels and exclusion reasons.
- Overlap with the holdout and the folds.
- What the scheme can express: for TotalSegmentator, "typical as far as the scheme says" (scanimport/column.py:125-126).
- Prevalence priors beside the counts: Tins 2016 at 7.7 percent; Sun 2025, Hanhivaara 2020 and Nardo 2012 (docs/textbook/07-...md:161).

**What is known now**

| Member | Known |
|---|---|
| ENHANCE.PET (holdings/gold-tier-3.md:42-92) | 1,557 whole. 68 name an L6: 67 below an L5, plus 0529. 40 have no L5, 39 of them with L4 touching the sacrum at 0.7 to 1.2 mm. |
| ENHANCE.PET, lowest rib | Of the 67 L6 spines: 51 twelve pairs, 14 thirteen pairs on L1, 2 one level off. Of the 39 with L4 at the sacrum: 24 twelve, 8 eleven, 1 asymmetric (1186), 2 off, 4 with no contact. Controls: 96, 3, 0, 1. |
| ENHANCE.PET, mislabels | Labelling errors 0529, 0245 and 0603. Open: 0005 and 1336. Out of order: 0816 and 1273 clearly, 0040 and 1463 weakly. None repaired. 1134, 1283 and 1347 repaired and kept at gold 4. |
| ENHANCE.PET, coverage | Rib pairs are read for all 1,597; the contact tally for only 214. |
| VerSe 17 | T13: 547, 602, 631. L6: 581, 585 (581 also eleven thoracic, Castellvi IIIb). four_lumbar: 549. Sacralised: 573. No read recorded for 108, 236, 563, 644, 649, 758, 766, 823. |
| TotalSegmentator 142 | Never counted. The release scheme cannot express L6 or T13. Only its 24 rib files can check the count. |

## 5. QA checks

**Can run now in this container, on ENHANCE.PET**

This works only while /tmp/claude-0/enh lasts.

| Check | Status |
|---|---|
| Integrity: nifti_label's refusal reasons, plus each mask's bytes against keys.json and rib_keys.json | To run |
| Alphabet: ids 0-28 only; schemes.problems | To run |
| The whole rule: C2 and the sacrum at 200 voxels or more, every level between, an absent L5 excepted | Done; per study in count.json |
| Order and gaps: head-foot order, `UNLABELLED_GAP_MM`, `LOOK_GAP_MM` | Done |
| C2 in the top slice | Done: 17 studies |
| L5 fragment under a quarter of L4's voxels | Done: 0179, 0213, 0270, 1240 |
| L4 to sacrum in 3-D (enhance-pet-repair/touch.py) | Done for the 39 no-L5 studies; extend to all whole studies |
| Lowest-rib contact, rib k on Tk | Done for 214; extend to all 1,557 (the masks are here) |
| Voxel-ratio check for split pieces and shifts (C1:C2:C3, neighbours; the 0603 and 1336 reasoning) | To write as a rule |
| Two independent implementations agree, as on the 420 sides | To repeat for every new check |
| Slice spacing in the xlsx against the NIfTI | Known exception: 1213 |
| Mask-only thumbnails (coronal and sagittal projections of label and rib masks) for a person's bench | Can be drawn now; no CT needed |

**Need the grid, or CTs this container does not hold** (only the 3 repair CTs are here, and the disk is about 30 GB)
- **CT intensity for every member:** HU inside each vertebra label, the metal rule (fewer than 20 voxels above 2,500 HU), and the mask-to-CT grid match by `check_against_ct`.
- **ENHANCE.PET autoPET:** match masks to the FDG-PET-CT-Lesions CTs by shape and affine; what the 900 NIfTI in that folder are is unknown; map the 1,014 studies to 900 persons.
- **ENHANCE.PET Leipzig and Careggi:** CT checks only after a fetch.
- **TotalSegmentator:**
  - read ts_clean_subjects.txt and check its sha256;
  - settle v2 against v3, and the duplicate ids s1406-s1429;
  - apply the rule again to the release masks and read the 14 the rule dropped (156 against 142);
  - rib contact from `rib_left_k` and `rib_right_k`, and a count from C2;
  - compare with the SPINEPS/VERIDAH census masks and the harvest's two-labeller calls;
  - overlap with Hofmann's validation_ts;
  - count children (286 of all v3 subjects are under 18).
- **VerSe:**
  - confirm the sacrum in all 17, using SPINEPS's sacrum in ~/bench_ts or a look at the CT, since VerSe labels none;
  - read the Loeffler table rows for the 8 unread;
  - check the disputed list.
- **Second labeller:** bordercall pilot and full (approved, unsent) give SPINEPS counts plus Moller ribs for TotalSegmentator and VerSe.

**What a person must still confirm**
- Every anomaly candidate on CT, not by the release's names:
  - ENHANCE.PET: 68 L6, 40 no L5, about 10 eleven-rib, 14 thirteen-rib, the 9 mislabelled or likely, the 3 repaired (gold 4 until checked), and 0005 and 1336.
  - VerSe: the 8 unread and every sacrum.
  - TotalSegmentator: every anomaly.
- The read should be a count from C2 with rib pairs, by two readers.
- Nothing in either repository types Castellvi, counts sacral segments or finds the iliolumbar origin, so lumbosacral typing is a person's alone.
- The tier policy (section 7).

## 6. What needs the owner's word and count

The queue order of 27 October 05:48 UTC holds every grid send until the owner names item 5, "gold 1/2/3 data". No file records that the 22:49 UTC ask is that word.

| Item | What it is | Size or count | Notes |
|---|---|---|---|
| `fetch aws_enhance_pet_labels` | Existing gate word, 1 batch job | Line states 2.5 GB. Measured: Vertebrae 381,439,888 B + Ribs 312,882,241 B = 694 MB. The whole 7-folder prefix is unmeasured; fetch_size.py sizes and s5cmd lands the whole prefix. | Its NOTE says "not yet the owner's yes". The 2026-10-26 01:58 UTC approval was for realism. |
| `fetch aws_enhance_pet_ct` | Existing gate word, 1 batch job, whole prefix | 197,321,490,975 B (not 177) | autoPET's 152 GB duplicates the held DICOM |
| Leipzig and Careggi only | New `url`-route line plus a list | 44,963,586,694 B, or 45,207,300,328 with the 3 repaired | Needs a pull request first |
| Grid index build and QA | New `gold3` word: grid/gate.sh, tests/test_gate.py, symphony-template scripts/grid-accounts.sh:31 and tests/test_grid_accounts.py, hpcworker's JOBS_RE pull request, then `update` | I suggest 2 CPU jobs, index then QA | The QA job reads CTs: about 367 GB of FDG DICOM on the lab volume, plus TotalSegmentator and VerSe on HOME |
| bordercall pilot and full | Already approved | 2 CPU | Unsent; hpcworker #50 pass-through unverified |
| `census tiers` | PR #420 | 1 CPU | Not approved; another thread's |
| Room under the quota | | 4,393.36 GB at 2026-10-27 04:08 UTC | Only the fetches write data; the index is small |
| Container re-read of the masks | If the container is lost | 694 MB from the public bucket | The first read was on the owner's word at 16:05 and 17:41 UTC. Preserving derived facts from the files already here needs no fetch. |
| Publishing the artifact | | | Confidential until the filing: private, no connector, never shared by link. The ask reads as consent, but the owner may want to confirm. |
| Loosening a licence class | | | The owner's alone |

## 7. Open questions

1. **Tier policy.** Are TotalSegmentator's hand-refined masks a person's? The tiers sort says yes. docs/research/full-spine-corpora-with-reader-counted-variants.md:34 files them as "tool labels only". The owner's rule of 2026-10-26 is never TotalSegmentator as a segmenter (docs/memory/bordercall-on-the-grid.md:3). Are the MOOSE masks checked by four readers a person's? The note says yes.
2. **142 or 156**, and which TotalSegmentator release the list names.
3. **Canonical copies.** For TotalSegmentator and VerSe, is it the data-root folders (totalsegmentator_v201 and _v300, versefusion, all "unmapped") or the HOME copies?
4. **The VerSe sacrum** in all 17. And the mask-scheme question for the dataset: VerSe has no sacrum id.
5. **Holdout use.** verse547, 549, 573, 759 and 809 are holdout; verse581 and 585 are fold 3. Does the dataset carry them, flagged and refused for training, or leave them out?
6. **Person keys.** One spelling, `<source>:<id>` or `ts:` and `verse:`? rule.json hashes the literal string, so the two spellings split differently.
7. **Licence.** autoPET masks are CC BY-NC but the TCIA CTs are recorded CC BY 4.0. FDG-PET-CT-Lesions has no data/licences.json entry. VerSe is CC BY in one record and BY-SA in another. Should the CC BY Leipzig and Careggi open subset be its own source?
8. **The autoPET match.** It has not been tried, and the 900 NIfTI in tcia_fdg_pet_ct_lesions are unexplained.
9. **Leipzig and Careggi have no person id**, so are persons counted as an upper bound only? And how is repeat-person leakage handled in splits?
10. **One whole-spine rule** to replace four: anomaly_pack `countable_of`, count_enhance_pet, bordercall_corpus and scanimport/tiers.py. It should name C2 explicitly and state its L5 exception.
11. **The two rib rules:** above 38 mm (Moller) and 50 voxels or more (ENHANCE.PET). Which one does the dataset report?
12. **Per-study public ids on the page.** Precedent allows them (data/splits), but no rule says so.
13. **Whose dataset.** Does it fold into PR #420's tiers or stand alone? #420 also mis-tiers ENHANCE.PET as machine output and guesses 720 for FDG-PET-CT-Lesions, against 865 to 900.
14. **Which claim and issue** carries this work, and the overlaps with data/sources, data/licences.json and the open edits to docs/research/enhance-pet-gold-tier-3.md.

**Not found:** the 142 TotalSegmentator ids in any repository; tools/ts_clean_subjects.py; screened.csv; the Loeffler table; spineps_ids.py; spinesurg-ct-nnunet's holding.sqlite schema and LAYOUT.md; the grid status branch; hpcworker's JOBS_RE; and the byte size of the whole ENHANCE.PET ground-truth prefix.