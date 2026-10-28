# Gold tier 3 CT dataset: statistics

Written by `python3 tools/gold3_ct.py stats` from the committed files under data/gold3-ct/ (their sha256 are listed at the end); do not edit it by hand, since `python3 tools/gold3_ct.py check` fails on a page that is not what the files give. Every share carries its 95 percent Wilson interval. A class rests on two masks the same readers checked; it is not a reader's read of the CT (QA.md says what the checks can and cannot show).

## Members

| Member | Rows | Gold 3 | Gold 4 | Silver 3 | Gold 3 by the records | Persons | Persons basis |
| --- | --- | --- | --- | --- | --- | --- | --- |
| enhance_pet | 1,597 | 1,557 | 3 | 37 | 1,557 | 865 to 1,478 | autoPET's range, and at most one person a whole study at the sites with no person id |
| verse | 17 | 17 | 0 | 0 | 17 | 17 | one person a key |
| totalsegmentator | 0 | 0 | 0 | 0 | 142 | 142 to 156 | by the records; no rows yet |

## ENHANCE.PET by site

| Site | Studies | Whole, gold 3 | Repaired, gold 4 | Not whole, silver 3 | Persons |
| --- | --- | --- | --- | --- | --- |
| Careggi | 199 | 199 | 0 | 0 | at most 199 |
| Leipzig | 384 | 379 | 3 | 2 | at most 379 |
| autoPET | 1,014 | 979 | 0 | 35 | 865 to 900 |
| all | 1,597 | 1,557 | 3 | 37 | 865 to 1,478 |

## ENHANCE.PET classes

One class per study. The share is of the whole studies (gold 3) of the column; a repaired or not-whole study is counted, with no share, since it is not among them.

| Class | All | Careggi | Leipzig | autoPET |
| --- | --- | --- | --- | --- |
| l6_twelve_ribs | 50 (3.2 %, 2.4 to 4.2) | 5 (2.5 %, 1.1 to 5.7) | 14 (3.7 %, 2.2 to 6.1) | 31 (3.2 %, 2.2 to 4.5) |
| l6_thirteen_ribs | 14 (0.9 %, 0.5 to 1.5) | 1 (0.5 %, 0.1 to 2.8) | 1 (0.3 %, 0.0 to 1.5) | 12 (1.2 %, 0.7 to 2.1) |
| four_lumbar_twelve_ribs | 28 (1.8 %, 1.2 to 2.6) | 2 (1.0 %, 0.3 to 3.6) | 6 (1.6 %, 0.7 to 3.4) | 20 (2.0 %, 1.3 to 3.1) |
| eleven_ribs | 33 (2.1 %, 1.5 to 3.0) | 5 (2.5 %, 1.1 to 5.7) | 12 (3.2 %, 1.8 to 5.5) | 16 (1.6 %, 1.0 to 2.6) |
| thirteen_ribs | 2 (0.1 %, 0.0 to 0.5) | 0 (0.0 %, 0.0 to 1.9) | 0 (0.0 %, 0.0 to 1.0) | 2 (0.2 %, 0.1 to 0.7) |
| asymmetric_ribs | 4 (0.3 %, 0.1 to 0.7) | 1 (0.5 %, 0.1 to 2.8) | 2 (0.5 %, 0.1 to 1.9) | 1 (0.1 %, 0.0 to 0.6) |
| labelling_error | 3 (0.2 %, 0.1 to 0.6) | 0 (0.0 %, 0.0 to 1.9) | 0 (0.0 %, 0.0 to 1.0) | 3 (0.3 %, 0.1 to 0.9) |
| open | 2 (0.1 %, 0.0 to 0.5) | 0 (0.0 %, 0.0 to 1.9) | 1 (0.3 %, 0.0 to 1.5) | 1 (0.1 %, 0.0 to 0.6) |
| look | 15 (1.0 %, 0.6 to 1.6) | 1 (0.5 %, 0.1 to 2.8) | 7 (1.8 %, 0.9 to 3.8) | 7 (0.7 %, 0.3 to 1.5) |
| not_whole | 37 | 0 | 2 | 35 |
| repaired | 3 | 0 | 3 | 0 |
| normal | 1406 (90.3 %, 88.7 to 91.7) | 184 (92.5 %, 87.9 to 95.4) | 336 (88.7 %, 85.1 to 91.5) | 886 (90.5 %, 88.5 to 92.2) |

## ENHANCE.PET statuses

| Class | Status | Studies |
| --- | --- | --- |
| asymmetric_ribs | candidate | 4 |
| eleven_ribs | candidate | 9 |
| eleven_ribs | confirmed_by_masks | 24 |
| four_lumbar_twelve_ribs | candidate | 14 |
| four_lumbar_twelve_ribs | confirmed_by_masks | 14 |
| l6_thirteen_ribs | candidate | 4 |
| l6_thirteen_ribs | confirmed_by_masks | 10 |
| l6_twelve_ribs | candidate | 10 |
| l6_twelve_ribs | confirmed_by_masks | 40 |
| labelling_error | labelling_error | 3 |
| look | candidate | 15 |
| normal | candidate | 251 |
| normal | confirmed_by_masks | 1,155 |
| not_whole | not_assessed | 37 |
| open | open | 2 |
| repaired | candidate | 3 |
| thirteen_ribs | confirmed_by_masks | 2 |

## The note's table, made again

Where the lowest rib meets, for the record's 100 controls and the rules' two groups (docs/research/enhance-pet-gold-tier-3.md, What the ribs say about the unusual lumbar counts). The rows give the note's numbers exactly.

| Lowest rib meets | controls | L4 above the sacrum | L6 below L5 |
| --- | --- | --- | --- |
| rib 12 on T12 | 96 | 24 | 51 |
| rib 11 on T11 | 3 | 8 | 0 |
| rib 11 on T11 on one side, rib 12 on T12 on the other | 0 | 1 | 0 |
| rib 13 on L1 | 0 | 0 | 14 |
| a label one level off | 0 | 2 | 2 |
| no spine label within 3.0 mm | 1 | 4 | 0 |
| Studies | 100 | 39 | 67 |

## ENHANCE.PET distributions, whole studies

Rib pairs: 12 1,495; 11 46; 13 16.

Lowest rib meets: rib 12 on T12 1,466; rib 11 on T11 33; no spine label within 3.0 mm 27; rib 13 on L1 16; a label one level off 11; rib 11 on T11 on one side, rib 12 on T12 on the other 4.

Bodies above the sacrum, by the names: 24 1,451; 25 67; 23 39.

Call by the names: T12L5 1,451; T12L6 67; T12L4 39.

Call by the ribs: T12L5 1,398; T12L6 53; none 29; T12L4 26; T11L6 25; T13L5 14; T11L5 9; T13L4 2; T8L9 1.

Rib ladder: own 1,549; one_high 4; one_low 4.

Lumbar names: C2 to L5 named 1,446; L6 named below an L5 67; no L5, L4 meeting the sacrum 39; L5 label a fragment, L4 meeting the sacrum 4; no L5, an L6 in its place 1.

L4 to the sacrum, shortest 3-D distance, over the 1,557 whole studies that carry it (median 15.0 mm): touching, 1.5 mm or less 41; 1.5 to 2.3 mm 1; 2.3 to 5 mm 9; 5 to 10 mm 93; 10 to 20 mm 1,327; over 20 mm 86.

## Why a study is not whole

| Reason | Studies |
| --- | --- |
| no C2 | 37 |

## VerSe

17 series of 17 persons, gold 3 provisional until each sacrum is confirmed on the grid; the classes are the readers' reads as the committed records carry them. t13 3 (17.6 %, 6.2 to 41.0); l6 2 (11.8 %, 3.3 to 34.3); four_lumbar 1 (5.9 %, 1.0 to 27.0); normal 3 (17.6 %, 6.2 to 41.0); unread 8 (47.1 %, 26.2 to 69.0).

| Series | Class | Status | Anomaly route role | Castellvi |
| --- | --- | --- | --- | --- |
| verse108 | unread | not_assessed | none |  |
| verse236 | unread | not_assessed | none |  |
| verse547 | t13 | candidate | holdout |  |
| verse549 | four_lumbar | candidate | holdout |  |
| verse563 | unread | not_assessed | none |  |
| verse573 | normal | candidate | holdout |  |
| verse581 | l6 | candidate | fold3 | IIIb |
| verse585 | l6 | candidate | fold3 |  |
| verse602 | t13 | candidate | none |  |
| verse631 | t13 | candidate | none |  |
| verse644 | unread | not_assessed | none |  |
| verse649 | unread | not_assessed | none |  |
| verse758 | unread | not_assessed | none |  |
| verse759 | normal | candidate | holdout |  |
| verse766 | unread | not_assessed | none |  |
| verse809 | normal | candidate | holdout |  |
| verse823 | unread | not_assessed | none |  |

## Holdout and folds

Persons the SPINEPS to FleXray route holds out or deals into folds (data/splits/anomaly-holdout.json) are carried, flagged, and never trained on (training_allowed 0).

| Member | Role | Persons |
| --- | --- | --- |
| enhance_pet | none | 1,597 |
| verse | fold3 | 2 |
| verse | holdout | 5 |
| verse | none | 10 |

## Inputs

- data/gold3-ct/enhance-pet/FACTS.json: 43ef43abe1dbaecdfa6c778815446668a7cc6f9da5ffcdcacb30e0fc90798ae5
- data/gold3-ct/enhance-pet/bucket.json: 42678637bf4c9243310339b93d0a854ef85916f76953577c35a4656388f5799a
- data/gold3-ct/enhance-pet/facts-b.jsonl: 12eb15d27f64b58cc2aee20cfe415fc6c88eebaad6936e4fb01d5760a976f7b4
- data/gold3-ct/enhance-pet/facts.jsonl: 95cc36bf5e4c710bb0000e8a1eb9290dae7ca730c88a347ca9792110f96cd847
- data/gold3-ct/enhance-pet/record.json: 143d447a7dc5c1aab4c33abb0e68999b08e268acf1fa7067539f097545c946d3
- data/gold3-ct/members.json: c0b755877541fcc4f7ac43e61ad04d68e03087d8982a36fa3b73fbe031e8eaf6
- data/gold3-ct/totalsegmentator.json: 99d8594b5aef8532d9da8488a7bd4f90d820fb7c970ce12f6fb2af6c237e6a0d
- data/gold3-ct/verse.json: f398383d474889fefcb360b7792f1f6fd95808ef3ffb6232f2c49728faa8fcd0
