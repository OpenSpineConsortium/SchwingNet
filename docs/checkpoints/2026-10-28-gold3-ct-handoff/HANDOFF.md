# Handoff: the gold tier 3 CT dataset, to the next account (2026-10-28)

Thread "Finish scan import and tier counts" of the claude.ai project symphony, written at 17:10 UTC on 2026-10-28 on the owner's ask of 17:08 UTC, verbatim: "im on usage credits so id like to transition to another account please push what you have, uodate the handoff, checkpoint everything, push everything only this thread can see, INCLUDING THE WORK ON THE GOLD TIER 3 DATA BECAUSE I DISAGREE THAT ONLY 17 VERSE SHOULS BE INCLUDED AND NO TOTALSEGMENTATOTR BUT ILL HANDLE THAT ON THE NEXT ACCOUTN MAKE SURE I CAN CONTINUE WORKING EXCATLY HOW THIS ACCOUNT WOULD!"

This page is the thread's whole state. A thread on the next account reads it, then docs/research/gold3-ct/README.md (the programme), and can carry on with nothing else from this account. Confidential like the rest of SchwingNet and bordercall: nothing here goes to a public place, and no path under the data root, no DICOM UID and no PatientID leaves the grid.

## 1. What is done

The owner's ask of 2026-10-27 22:49 UTC, verbatim: "well whenvever this finishes i want all the gold tier 3 CT data as its own dataset, with a indexable database, an artefact, and anything i need to use it in the workflow, including anomaly statistics, and quality assurance they are true anomalies". It is built and merged:

- SchwingNet #437, merged 2026-10-28 06:20 UTC as 5f2165c: the records under data/gold3-ct/, tools/gold3_ct.py (build a read-only versioned SQLite store, query, stats, qa, export, page, check; standard library only), docs/research/gold3-ct/ (README, SPEC, BRIEF, STATS, QA, page-data.json), the grid handoff docs/checkpoints/2026-10-28-gold3-ct-grid/, and the page's source under artifacts/gold-tier-3-ct-xdgjjg/.
- bordercall #17, merged 2026-10-28 06:20 UTC as 0ecb844: the mask readers holdings/enhance_facts.py (first reading), enhance_facts_check.py (second, written blind from SPEC.md, with `compare`), enhance_facts_cross.py (the first reading against the count and touch.json) and enhance_views.py (the bench's pictures), with 113 tests under holdings/tests/.
- ENHANCE.PET's masks were read twice in full in the thread's container, 1,597 studies each. `compare` holds on all 1,597, the cross-check holds against the count and against touch.json's 143 distances, and the one fault the full run found (slice centres rounded twice, 11 Careggi rows) is fixed at bordercall 0be8f0c with mutation tests. The facts are committed (data/gold3-ct/enhance-pet/facts.jsonl, facts-b.jsonl, FACTS.json), so the grid handoff is now its case B: a grid run, if the owner ever sends it, only checks that the grid's masks give the same facts.
- The private page Gold Tier 3 CT, https://claude.ai/artifact/XDGjjGKVcdi2xDht7a689w, published from this account (gschwing) on 2026-10-28: overview, members, anomaly statistics with Wilson intervals, the studies, the sixteen quality checks, a reader bench over 191 studies (and the three repaired masks), and a SQL tab over a redacted copy of the store. Twenty-seven reviewers read it; the 21 findings that held are fixed and replayed in Chromium.
- Nothing went to the grid. No fetch, job or training ran.

The members as merged: ENHANCE.PET 1,557 gold 3 of 1,597 (autoPET 979, Leipzig 379, Careggi 199; 37 with no C2 are silver 3; 1134, 1283 and 1347 repaired, gold 4, rows 1134r, 1283r, 1347r), VerSe 17 (provisional until each sacrum is seen), TotalSegmentator 142 declared with no rows. STATS.md has every class and interval.

## 2. Open: the owner disagrees with 17 VerSe and no TotalSegmentator rows

The owner, 2026-10-28 17:08 UTC: "I DISAGREE THAT ONLY 17 VERSE SHOULS BE INCLUDED AND NO TOTALSEGMENTATOTR BUT ILL HANDLE THAT ON THE NEXT ACCOUTN". The dataset's decisions 3 and 4 (docs/research/gold3-ct/README.md, section 8) were taken on the owner's behalf and are now overruled in principle; the owner settles what replaces them. Nothing below has been changed in the data; this section is the full record of what limited the two members and of every candidate, so the next account starts from it.

### Why the dataset has what it has

- The rule applied: gold is a field from C2 to the sacrum in one study, tier 3 is one modality with a person's annotation, and truth comes only from whole spines countable from C2 to the pelvis (the owner's tiers of 2026-10-27 and his science rules). A machine mask never raises a tier.
- VerSe labels no sacrum. The 17 are the series whose release masks run from C1 or C2 to L4-L6 with the lumbosacral junction in the field, by spinesurg-ct-nnunet's transitional_registry/verse/screened.csv (columns mask and junction_ls_in_fov; junction_ls_in_fov is the labeller's geometry, a machine call), carried by pull request #420's corpus-tiers draft and bordercall holdings/gold-tier-3.md. Every other VerSe person was counted silver 3.
- TotalSegmentator's 142 are a count from the records (v3 subjects whose release masks hold C2 to L5 and the sacrum, each at least 200 voxels, and no metal). The subject list exists only on the grid, `${HOME}/model_night/ts_clean_subjects.txt`, sha256 2f96f917292b85416d1b803230732624a3dde0bae7c2c29f54abc4f2a30dc1b7, so no repository names a subject and the member has its count and no rows (data/gold3-ct/totalsegmentator.json). Making rows needs a grid read, which waits for the owner's word and count.

### VerSe: every candidate

VerSe'19 and '20 together are 374 series of 355 persons (VerSe'19 160 series of 141 subjects, VerSe'20 319 of 300), expert vertebra masks and centroids from C1 to L6 with T13 as id 28, no sacrum label. On the grid: the versefusion folder, 383.7 GB, 4,325 images, 1,652 annotated (docs/research/data-manifest/MANIFEST.md).

| Pool | Series or persons | Ids | Where the list is |
| --- | --- | --- | --- |
| In the dataset now | 17 series, 17 persons | verse108, 236, 547, 549, 563, 573, 581, 585, 602, 631, 644, 649, 758, 759, 766, 809, 823 | data/gold3-ct/verse.json |
| Hold C2 but stop above the lumbar spine | 59 series (76 hold C2 in all) | not committed | screened.csv in spinesurg-ct-nnunet |
| Neuroradiologist variant reads (Loeffler 2021 Supplementary Table 1) and a Castellvi table | 325 TUM subjects | not committed | the grid home's lstv_flag/sources/verse_suppl_table1.csv, sha256 recorded in data/splits/anomaly-holdout.json inputs |
| Counted silver 3 | 338 persons | not committed | pull request #420's sources.json, rows verse, verse19_20, versefusion |
| Never downloaded | 10 VerSe'20 series | not committed | grid/README.md |
| Out of every truth pool | 6 disputed persons | not committed | the anomaly route's records |

Known faults to carry whatever the choice: the release's has_T13 flag is wrong (18 against 6 by the masks); 39 of 85 L6 masks lack id 25, so the L6 count is unsettled; verse581 has no T12 because its readers' structure is 7/11/6/5 (eleven thoracic, six lumbar, Castellvi IIIb), a variant, not a gap; vf_813 drops C1 to T9 and is never used for whole-spine work; 18 subjects own 37 series; the licence records disagree (CC BY-SA 4.0 in the registry, CC BY 4.0 in the VerSeFusion readme). Five of the 17 are in the frozen anomaly holdout (verse547, 549, 573, 759, 809) and two in fold 3 (verse581, 585); they stay flagged with training_allowed false.

Ways the owner might widen it, none taken: (a) count every series whose experts labelled C2 and the lowest lumbar body with the junction in the field, confirming the sacrum on the grid, which is the 17 by today's screen and may be more by a read of the masks themselves rather than screened.csv; (b) take the 325 subjects with a neuroradiologist's read of the lumbosacral junction as person-annotated anomaly truth whatever the field, as their own tier or a flag; (c) take all 355 persons into the store as rows, each with its tier, so the store holds VerSe whole and the gold filter is a query. Each needs the masks read on the grid (a CPU job and the owner's count); the rows of (c) could also be written from the committed records with each tier as the records say, with no grid job, at the cost of reading nothing new.

### TotalSegmentator: every candidate

TotalSegmentator v3.0.0 is 1,939 subject folders, 1,935 distinct scans and persons by release id; v2.0.1's 1,228 are a complete subset of v3. Masks: 117 structures, model output refined by hand by the release's authors, every vertebra named by level, no L6, T13 or lumbar-rib class, and a sacrum label that excludes S1. On the grid: totalsegmentator_v300 48.8 GB, totalsegmentator_v201 39.6 GB (MANIFEST.md).

| Pool | Subjects | Where the list is |
| --- | --- | --- |
| C2 to L5 and the sacrum, at least 200 voxels each, no metal | 142 | the grid home's model_night/ts_clean_subjects.txt (sha256 above) |
| C2 and the sacrum present, dropped by the level or metal rule | 14 more (156 in all) | spinesurg-ct-nnunet's DATA_COMPLETENESS_AUDIT.md lines 113, 500 and 509 |
| Partial fields, counted silver 3 | 1,583 | pull request #420's sources.json, row totalsegmentator |
| SPINEPS failed, untiered | 210 | the same row |
| Hofmann's external VertebralBodiesCT labels with L6 and T13 flags | 70 v2 CTs linked (of his 1,460, with 69 L6 and 14 T13 flags) | the grid's data root, validation_ts (70 links) |
| Under 18, whose unfused S1 reads as a free body | 286 | the release's meta |
| Byte-identical duplicates across versions | v2 s1406 to s1429 against other v3 ids, up to 24 people merged or split | the same row's caveats |

Caveats: the project's full-spine note calls these masks tool labels, while the owner's rule counts automatic masks refined by hand as a person's annotation, which is why they are gold 3 and flagged; the scheme cannot express an L6 or T13, so a count from it is typical as far as the scheme can say, and an anomaly call would have to come from SPINEPS and VERIDAH or from Hofmann's 70 reads; TotalSegmentator is never run as a segmenter here (the owner's rule), which is no bar to its release masks as data.

What including it takes: one CPU job on the grid that reads the subject list and checks its sha256, reads the 142 (or 156) subjects' release masks with a TotalSegmentator scheme beside enhance_facts.py's ENHANCE.PET one (bordercall's scanimport/schemes.py already maps the release files, TOTALSEG_FILES and TOTALSEG_RIB_FILES), and writes their facts and rows, then `tools/gold3_ct.py stats`, `qa`, `page` and a new store version. It is the grid index job of docs/research/gold3-ct/README.md section 7, which also covers the autoPET mask-to-CT match and VerSe's sacrum. The owner's word and count come first, offered once as a decision card.

## 3. Where everything is

| What | Where |
| --- | --- |
| The programme, its decisions and what waits | SchwingNet docs/research/gold3-ct/README.md (sections 7 and 8), SPEC.md, BRIEF.md |
| Records, facts and statistics | SchwingNet data/gold3-ct/, docs/research/gold3-ct/STATS.md and QA.md |
| The dataset tool and its tests | SchwingNet tools/gold3_ct.py, tests/test_gold3_ct.py |
| The mask readers and their tests | bordercall holdings/enhance_facts*.py, enhance_views.py, holdings/tests/ |
| The grid run, if ever sent | SchwingNet docs/checkpoints/2026-10-28-gold3-ct-grid/HANDOFF.md and gold3-facts.sbatch |
| The page's source and how to publish it again | SchwingNet artifacts/gold-tier-3-ct-xdgjjg/ (README.md, template.html, build_page.py, index.html, views/) |
| The published page and its reader verdicts | https://claude.ai/artifact/XDGjjGKVcdi2xDht7a689w, collection verdicts; empty at 17:15 UTC on 2026-10-28 |
| The masks the thread read, the repair record, the count's outputs | the Claude project's files: gold3-ct/enhance-pet-source/ (678 MB), enhance-pet-repair/ (the SchwingCheck test set of the three repaired masks) |
| What was only in this thread's container | the Claude project's files: gold3-ct/thread-handoff-2026-10-28/ (below) |

The folder gold3-ct/thread-handoff-2026-10-28/ in the project's files holds: page/ (the Playwright test test2.js with sql.js's sql-asm.js 1.10.3, the published store carrier gold3-000001-f04a0bd020c0-page-copy.zip.json, the patch sources the page review's fixes were made from, and files.json, the publish's file map); store/ (the full store, version gold3-000001-f04a0bd020c0, sha256 f04a0bd020c0f7db32c44c21f605619e5b5e6dc94a27261b9d5ec3ee8c1bfcc2, the same that `build` makes from main's files); readings/ (agreement.json and agreement2.json from `compare`, cross.json from the cross-check, the bench and repaired id lists, the repaired rows, and the second reading's run folder); review/ (the page review's findings, the earlier reads of what the records say of VerSe and TotalSegmentator, gold3_reads.md, and #437's body as drafted); dicom-references/ (the DICOM standard's attribute tables and dcm2niix's sources, gathered for the mask-free import research, which is committed in bordercall under reports/ and research_notes/).

The project's files belong to the claude.ai project, not to an account's container. If the next account works in a new project that cannot see them, the masks can be read again from the public bucket (s3://enhance-pet-1-6k, data/gold3-ct/enhance-pet/bucket.json has every key with its bytes, SHA256SUMS every mask's hash), and everything else above is in git or rebuilt from it.

## 4. How to continue exactly as this account would

- The rules: the owner's standing rules and science rules are the restart kit's memory (docs/checkpoints/2026-10-27-restart-kit/memory/), with this thread's own fact as gold3-ct-dataset.md there. No fetch, grid job or training without the owner's word and the count, one decision card per count; "idk" means the recommended option.
- SchwingNet: standard library only. `python3 tools/gold3_ct.py check` is part of `bash scripts/check.sh`; after any change to the records run `stats`, `qa` and `page`, then `check`. A store is built only outside the repository: `python3 tools/gold3_ct.py build --root <folder>` or GOLD3_ROOT. Pushing needs `export PATH="$HOME/.pixi/bin:$PATH"` for the pre-push gate. In this container the gate's 7 test_bank_depth errors were a missing beartype, environmental; CI ran green.
- bordercall: the readers need numpy, scipy, nibabel and Pillow (`python3 -m venv ~/venv-bc && ~/venv-bc/bin/pip install numpy scipy nibabel pillow`), then `python -m unittest discover -s holdings/tests -t .` (113 tests). Read the stored integers of a mask, never nibabel's float64 scaled array: two scaled reads at once ran a container out of memory. Never touch schwingcheck/, the root tests/, tests/test_schwingcheck_*.py or requirements-schwingcheck.txt, which are another account's.
- The page: to change it, edit artifacts/gold-tier-3-ct-xdgjjg/template.html and rebuild with build_page.py as its README says, from a store built from main and the views drawn by enhance_views.py from the masks in the project's files. To test it, serve the build folder (`python3 -m http.server 8766`) and run `node test2.js <out> <shots> <sql-asm.js> 8766` from the project files' page/ folder; Playwright and Chromium are preinstalled in a cloud container. The page is this account's artifact: a publish from another account makes a new page with a new, empty verdicts collection, so the owner decides which page is the bench of record and the other is retired. Its capabilities are db (rules: root read view, write owner; verdicts read view, write owner; verdicts/{self} write interact), user (scope profile) and downloads.
- Pull requests: one branch per thread, a draft with "## Adversarial review" in its body, marked ready in a call of its own, merged with the head sha copied from git once the check is green; SchwingNet's body ends with the line that it is no claim branch. bordercall has no CI; run its tests before merging.

## 5. What this account would do next, in order

1. Put the owner's disagreement (section 2) to him as two decision cards, VerSe and TotalSegmentator, each with its pools, the recommended option and the grid count it needs. Recommended, for him to overrule: for both, take every person into the store as a row with its tier as the records give it (no grid job), so the store holds each member whole and gold is a query; then one CPU index job, on his count, to read the TotalSegmentator masks (142 and the 14) and VerSe's 76 C2 series, which moves persons between tiers by what the masks show.
2. Build the import of the bench's verdicts into the store's qa_review table (`tools/gold3_ct.py import-verdicts <export.json>`, from the page's download or the Artifact database tool's list of verdicts), so a reader's verdict makes an anomaly reader_confirmed; until then reader_confirmed stays empty.
3. The grid, only on the owner's word and count, each its own card: the grid handoff of 2026-10-28 (case B, reproduction only), the index job above, the Leipzig and Careggi CTs (45,207,300,328 bytes, a new url-route line first).
4. The lumbosacral questions the masks cannot settle (sacralisation, lumbarisation, Castellvi type) stay needs_ct until a reader reads the CT; two readers counting from C2 with the rib pairs, on the bench.
