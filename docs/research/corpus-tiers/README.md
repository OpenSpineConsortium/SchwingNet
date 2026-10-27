# The corpus in the owner's gold and silver tiers

Source: the thread "Sort the corpus into gold and silver tiers" of the symphony project, 2026-10-27, on the owner's message of 03:06 UTC that day (the tiers, the newly approved Radiopaedia licence, the correspondence with Michelle Marks of Setting Scoliosis Straight and with Fiona Mellor of Exeter for Alan and Alex Breen). Confidential: this page and data/corpus-tiers/ never leave SchwingNet. The public method is symphony-template's docs/research/corpus-evidence-tiers-2026-10-27.md.

## 1. Where it stands

The sort is in progress, stopped at the owner's checkpoint of 04:47 UTC. Every one of the 303 sources the records know has a row, each written by one reader and checked by a skeptic, 122 corrections in all; the completeness lens added 7 sources no batch covered, each classified and checked the same way, so the table holds 310. Four of five cross-checking lenses (overlaps, gold and pairs, the census map, missing sources) have run, each with an adjudicator, and 234 of their corrections are applied. The consistency lens's verdicts came after the build and are kept apart, not applied, since two of them conflict with the other lenses. docs/checkpoints/2026-10-27-corpus-tiers/HANDOFF.md says what is left and how to finish.

The answer as it stands, persons counted once across sources:

- No held person is gold 1 or gold 2. The project holds no whole-spine CT paired with a real radiograph of the same person.
- Gold 3, 159 persons, counted from the release masks: TotalSegmentator 142 and VerSe 17. These are the only held whole spines a person annotated.
- Gold 4, about 1,929 persons, mostly estimated from whole-body PET/CT fields until the census reads the masks. FDG-PET-CT-Lesions is about 720, the IDC collections about 320, CADS about 390, VSD full-body about 90, deep-PSMA about 70, Quadra about 48, the TMTV benchmark about 48. The IEEE DataPort set gives 236 standing lateral films described as head to mid-thigh. They are the only held real full-spine radiographs, and no film has been read yet.
- Silver 1, one person (the Ljubljana 2D/3D gold standard). Silver 2, 848 persons: COBRA 692, C-ArmLSpine 149, DeepFluoro 6 and the Killeen cadaver 1, every pair partial.
- Silver 3, about 13,840, and silver 4, about 210,600. These are most of the corpus: partial CTs and films.

Every claim that checks a name on a real radiograph against a count from C2 therefore has no held gold person to stand on. Such claims wait for a new source (Setting Scoliosis Straight's films, a reader-counted cohort) or for the Flux conversion to pass its test. Claims on CT alone have 159 annotated and about 1,900 unannotated whole spines.

## 2. The tiers and how a case is placed

The owner's words of 2026-10-27 03:06 UTC set two spans and four tiers within each.

- Gold: one study of the person shows the whole spine, so a level named in it can be checked by counting from C2. Silver: it shows less.
- 1: a CT and a real X-ray (AP, lateral or both) of the same person, with a person's annotation of the vertebrae on at least one.
- 2: the same pair, with no person's annotation on either.
- 3: a CT or an X-ray alone, with a person's annotation.
- 4: a CT or an X-ray alone, with none.

The owner wrote tiers 3 and 4 as "full spine CT paired or full spine XRay". This page reads that as one modality alone, since it is the only reading that keeps the four tiers distinct.

The rules the sort applies to every case:

- The unit is the person. A person with several studies counts once, at the best tier any study reaches, gold 1 to 4 and then silver 1 to 4.
- Whole spine means the count from C2 holds on the mask itself. C2 is in the centroid file, at most one body lies above it, no gap hides a missed body (tools/bordercall_corpus.py's gap rule), and the sacrum is in the mask.
- A pair is gold only when both images are whole. Real C-arm frames show part of the spine, so a whole CT with real frames is gold 3 or 4 alone and silver 1 or 2 as a pair. Both are reported.
- An X-ray is a real radiograph or real fluoroscopy. A DRR, edited by Flux or not, is not an X-ray for these tiers.
- A person's annotation is a mask, point, corner or level name a person drew, checked or refined. Machine labels from SPINEPS, VERIDAH, TotalSegmentator or MOOSE never raise a tier. A report that only mentions a level is report-only and does not raise one either.
- CTSpinoPelvic1K is held with human-refined masks, but the owner does not trust it as ground truth (2026-10-26 00:16 UTC). Its CTs are lumbopelvic, so the count from C2 cannot be checked on them, and they sit at silver 3 by the rules anyway.
- A source not yet held gets the tier it would bring and holds no one until it is on the grid.

## 3. The table

`python3 tools/corpus_tiers.py table` prints every source with its tiers, and `python3 tools/corpus_tiers.py power` prints the held persons per tier. The table is data/corpus-tiers/sources.json. A source with counted_in is a copy, version or subset of another row, and its persons are left out of the totals. A count with the basis needs_grid_read is an estimate that the census replaces.

## 4. The sources the owner named

- **Radiopaedia, approved.** Approval ID 202610-9517 was countersigned by Andrew Murphy on 2026-10-23 for personal use, with access for the owner alone. Every publication carries the line "Permission was sought and obtained from Radiopaedia.org (ID:202610-9517) prior to research being undertaken." Cases are collected by hand and never by script, and nothing is held yet. A case whose image carries its author's drawn level label is silver 3, or gold 3 for a whole-spine film or CT. A case naming its level only in the text is report-only, silver 4 or gold 4.
- **Setting Scoliosis Straight, the Harms Study Group registry, pending.** The group's own account says deidentified standing PA and lateral radiographs from every site are held centrally, digital since 2001, and measured by trained central staff. No public account says it keeps any CT. Expected tiers are gold 3 for films showing C2 to the sacrum with the readers' level names tied to them, silver 3 for shorter films, and gold 4 or silver 4 if only the images come. The owner wrote on 2026-10-23, and Michelle Marks answered asking for the study's details. A short follow-up is in the owner's Outlook Drafts. It asks for DICOM films with pixel spacing, any CT of the same patients, the readers' level names with the data dictionary, and counts. data/corpus-tiers/work/hsg-research.json holds the research with its sources.
- **Exeter and Bournemouth, pending.** On 2026-10-26 Fiona Mellor wrote that she will answer with Alan and Alex Breen as one. Every event is partial, on real fluoroscopy, with corner templates a person placed, so the cine is silver 3 when it comes. The 63 cervical people's tracks are held but carry no pixels, so they place no one in a tier yet.

## 5. The conversions, and what each must show first

The owner named three ways to move people up the tiers. None of them has moved anyone yet. Each is counted in a column of its own and never pooled with the tier it aims at.

- **SPINEPS masks, tier 4 towards tier 3.** SPINEPS gives every vertebra of a held CT a provisional name, and the census reads the count from C2 off those masks. The masks are a machine's, so by the owner's definition the person stays at tier 4. The person moves to tier 3 only once a person has checked the masks. The census counts how many tier 4 CTs already carry masks, so the size of the review is known before anyone starts it.
- **A Flux-edited DRR, tier 3 towards tier 1.** An edited DRR rendered from a whole-spine annotated CT would stand in for the missing radiograph of the same person. It can do so only once the domain-gap study (docs/research/drr-domain-gap/README.md) shows, by its pre-registered two-sample tests, that the edited DRRs cannot be told from real radiographs at the resolution a claim is read at. Until then such a pair is synthetic and reported apart. Its labels are the CT's own, so it can test the transfer from CT to image but never naming on a real radiograph.
- **A person's review, or SchwingCheck with a person confirming, tier 3 towards tier 1 and tier 4 towards tier 3.** Each reviewed case moves one step, and the record names the reviewer. The tool's own answer is a machine's until a person confirms it. For a pair, the reviewer also links the CT and the radiograph case by case.

The owner's aside is recorded and not built. SchwingCheck recomputes its names as each new acquisition arrives, which places it naturally in the operating room. Its Bayesian generator could also run in reverse: from one C-arm seed it would give a morphologically consistent outline that a realism model such as Flux could fill to make radiographs. This is a direction for later work. Nothing here builds it, and no image it made would count as an X-ray for these tiers.


## 6. The power of each planned experiment

Each claim is a proportion over persons. Its precision is the Wilson interval at the expected rate over the gold persons it can use. A claim that no error occurs is bounded by the exact binomial bound, about three over n. The expected rates are the synthetic results in bordercall (docs/EXACT_IDENTIFICATION_RESULTS.md and the white paper's records, all synthetic), and the persons below are the gold persons each claim can use today.

| claim | expected | tier it needs | gold persons held | 95% half-width | persons for 2 points |
|---|---|---|---|---|---|
| the exact rule names the vertebra from nine bodies, real CT | 96% | gold 3 or 4 CT, count from C2 | 159 annotated; about 2,088 with gold 4 | 3.1 points; about 0.8 | 381 |
| from five bodies | 86% | the same | the same | 5.4 points; about 1.5 | 1,157 |
| from three bodies | 73% | the same | the same | 6.8 points; about 1.9 | 1,890 |
| names at 0.99 are right at least 99% (from three bodies) | 99.78% | the same | the same | the lower bound passes 99% at 577 persons and 98% at 190 | 577 |
| transitional spines: names at 0.99 right on 13-rib and 6-lumbar columns | 90.6% and 92.9% | gold CT with the variant, read by a person | VerSe's whole-spine T13 and L6, a handful; 13 persons give plus or minus 16 points | 8.5 points at 50 | 821 |
| the junction predictor, C7/T1 and T12/L1 exact | 86% and 65% | gold, both junctions in view | 159; about 2,088 | 5.4 and 7.3 points; 1.5 and 2.0 | 1,157 and 2,181 |
| the second opinion flags an off-by-one label | 84% at posterior 0.01 | gold CT with a registration's labels | none paired | 7.2 points at 100 fields | 1,290 |
| the second opinion questions 1 correct label in 1,000 | 0.1% | the same | none paired | the upper bound falls below 0.5% at 1,200 fields | 1,200 |
| the reader study, 40 readers by 48 cases in four strata of 12 | power 0.92 and 0.85 (bordercall's calibrated simulation) | gold 1: a CT and a real radiograph, count from C2 | 0 | not applicable | 48 cases |
| edited DRRs cannot be told from real radiographs | the domain-gap study's own endpoints | real radiographs of any tier, person-grouped | silver 2 and 3 suffice | its own design | its own design |

What follows from the table:

- The CT claims can be run now on gold 3 and gold 4, once the census has replaced the gold 4 estimates. Gold 4's truth is the count from C2 on the machine's masks, so a person's check of the masks, the SPINEPS conversion, is what turns that truth into gold 3.
- No claim about a real radiograph checked from C2 can be powered from held data. The reader study needs 48 gold 1 cases. The second opinion needs a CT and a radiograph of the same person with a registration's labels. Both wait for Setting Scoliosis Straight's films with a CT, a reader-counted cohort with films (Tatara 2021 and Sabri 2025 in docs/research/full-spine-corpora-with-reader-counted-variants.md), or the Flux conversion passing.
- The transitional claims are the weakest. Held gold transitional spines number in the tens, so their intervals stay wide until a reader-counted cohort arrives (Lodz 2026, Jeonbuk 2020, Yoon 2024 in the same note).

## 7. The census job

One CPU job, the grid word `census tiers`, which grid-accounts.yml sends as `schwingnet-census-tiers`. grid/census.sbatch reads every existing vertebra mask the transitional census lists (tools/corpus_tiers.py census). It writes only its per-case file and a report of counts. It segments, trains and fetches nothing. It waits for the owner's word and count. A collection the census map marks with a person's annotation only in part (CTSpinoPelvic1K, 784 of 802) is read as unannotated per case, so the census undercounts silver 3 there; this does not touch gold. An untrusted collection is never read as whole.
