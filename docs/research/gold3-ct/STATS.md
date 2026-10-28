# Gold tier 3 CT dataset: statistics

Written by `python3 tools/gold3_ct.py stats` from the committed files under data/gold3-ct/ (their sha256 are listed at the end); do not edit it by hand, since `python3 tools/gold3_ct.py check` fails on a page that is not what the files give. Every share carries its 95 percent Wilson interval. A class rests on two masks the same readers checked; it is not a reader's read of the CT (QA.md says what the checks can and cannot show).

## Members

| Member | Rows | Gold 3 | Gold 4 | Silver 3 | Gold 3 by the records | Persons | Persons basis |
| --- | --- | --- | --- | --- | --- | --- | --- |
| enhance_pet | 0 | 0 | 0 | 0 | 1,557 | 865 to 1,478 | by the records; no rows yet |
| verse | 17 | 17 | 0 | 0 | 17 | 17 | one person a key |
| totalsegmentator | 0 | 0 | 0 | 0 | 142 | 142 to 156 | by the records; no rows yet |

## ENHANCE.PET

The ENHANCE.PET rows are not yet committed (data/gold3-ct/enhance-pet/facts.jsonl, made by bordercall's holdings/enhance_facts.py from the published masks), so this page carries their counts by the records alone. Once they are, `python3 tools/gold3_ct.py stats` writes the sites, the classes with their intervals, the note's table made again and the distributions here.

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
| verse | fold3 | 2 |
| verse | holdout | 5 |
| verse | none | 10 |

## Inputs

- data/gold3-ct/enhance-pet/FACTS.json: not committed
- data/gold3-ct/enhance-pet/bucket.json: 42678637bf4c9243310339b93d0a854ef85916f76953577c35a4656388f5799a
- data/gold3-ct/enhance-pet/facts-b.jsonl: not committed
- data/gold3-ct/enhance-pet/facts.jsonl: not committed
- data/gold3-ct/enhance-pet/record.json: 143d447a7dc5c1aab4c33abb0e68999b08e268acf1fa7067539f097545c946d3
- data/gold3-ct/members.json: 74200e3657906158a25b28a6c295141a148a89572db2f8ba0f7bab84082ec5f5
- data/gold3-ct/totalsegmentator.json: 99d8594b5aef8532d9da8488a7bd4f90d820fb7c970ce12f6fb2af6c237e6a0d
- data/gold3-ct/verse.json: f398383d474889fefcb360b7792f1f6fd95808ef3ffb6232f2c49728faa8fcd0
