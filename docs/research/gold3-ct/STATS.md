# Gold tier 3 CT dataset: statistics

Written by `python3 tools/gold3_ct.py stats` from the committed files under data/gold3-ct/ (their sha256 are listed at the end); do not edit it by hand, since `python3 tools/gold3_ct.py check` fails on a page that is not what the files give. Every share carries its 95 percent Wilson interval. A class rests on two masks the same readers checked; it is not a reader's read of the CT (QA.md says what the checks can and cannot show).

## Members

| Member | Rows | Gold 3 | Gold 4 | Silver 3 | Gold 3 by the records | Persons | Persons basis |
| --- | --- | --- | --- | --- | --- | --- | --- |
| enhance_pet | 1,597 | 1,558 | 3 | 36 | 1,558 | 865 to 1,479 | autoPET's range, and at most one person a whole study at the sites with no person id |
| verse | 374 | 21 | 0 | 353 | 21 | 21 | one person a key |
| totalsegmentator | 1,777 | 154 | 0 | 1,623 | 154 | 154 | one person a key |

## ENHANCE.PET by site

| Site | Studies | Gold 3 | Repaired, gold 4 | Silver 3 | Persons |
| --- | --- | --- | --- | --- | --- |
| Careggi | 199 | 199 | 0 | 0 | at most 199 |
| Leipzig | 384 | 380 | 3 | 1 | at most 380 |
| autoPET | 1,014 | 979 | 0 | 35 | 865 to 900 |
| all | 1,597 | 1,558 | 3 | 36 | 865 to 1,479 |

## ENHANCE.PET classes

One class per study. The share is of the whole studies of the column, gold 3 with C2 to the sacrum drawn by their masks; a repaired or not-whole study is counted, with no share, since it is not among them, as is 1379, gold 3 by the field test while a segmenter adds its C2.

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

## VerSe and TotalSegmentator by the field test

Rule version 3: a CT is admitted when its field holds the foot of C2 and the top of the sacrum, whatever its masks hold; docs/research/gold3-ct/ADMISSION.md gives every verdict's numbers and README.md the rule. A study that draws no vertebra above the sacrum is no spine study and has no row.

| Member | Tier | Studies | Persons |
| --- | --- | --- | --- |
| totalsegmentator | gold 3, whole by the release's masks | 147 | 147 |
| totalsegmentator | gold 3, a segmenter adds levels | 7 | 7 |
| totalsegmentator | silver 3, part of the column | 1,623 | 1,621 |
| verse | gold 3, a segmenter adds levels | 21 | 21 |
| verse | silver 3, part of the column | 347 | 329 |
| verse | silver 3 until a person's look (a border case) | 6 | 6 |

## VerSe's classes

The 17 series the committed records read keep the readers' reads, and a series whose person data/splits/anomaly-holdout.json reads, in its holdout or its folds, takes that read; every other series is named by its release's masks, a candidate where they draw a T13 or an L6. Shares are of the gold 3 series: t13 4 (19.0 %, 7.7 to 40.0); l6 3 (14.3 %, 5.0 to 34.6); four_lumbar 1 (4.8 %, 0.8 to 22.7); normal 3 (14.3 %, 5.0 to 34.6); unread 10 (47.6 %, 28.3 to 67.6). The series with a class or an anomaly route role:

| Series | Tier | Class | Status | Anomaly route role | Castellvi |
| --- | --- | --- | --- | --- | --- |
| gl279 | silver3 | l6 | candidate | none |  |
| verse010 | silver3 | normal | candidate | holdout |  |
| verse023 | silver3 | l6 | candidate | fold1 |  |
| verse024 | silver3 | l6 | candidate | fold4 |  |
| verse034 | silver3 | l6 | candidate | fold3 |  |
| verse083 | silver3 | l6 | candidate | fold3 |  |
| verse085 | silver3 | l6 | candidate | fold1 |  |
| verse088 | silver3 | l6 | candidate | fold4 |  |
| verse113 | silver3 | l6 | candidate | fold2 |  |
| verse131 | silver3 | l6 | candidate | fold2 |  |
| verse153 | silver3 | normal | candidate | holdout |  |
| verse208 | silver3 | l6 | candidate | fold1 |  |
| verse214 | silver3 | l6 | candidate | holdout |  |
| verse255 | silver3 | l6 | candidate | fold1 |  |
| verse261 | silver3 | l6 | candidate | holdout |  |
| verse502 | silver3 | l6 | candidate | fold2 |  |
| verse505 | silver3 | l6 | candidate | fold1 |  |
| verse506 | silver3 | l6 | candidate | fold3 |  |
| verse509 | silver3 | l6 | candidate | holdout |  |
| verse510 | silver3 | l6 | candidate | fold4 |  |
| verse512 | silver3 | l6 | candidate | fold2 |  |
| verse513 | silver3 | l6 | candidate | holdout |  |
| verse514 | silver3 | l6 | candidate | holdout |  |
| verse517 | silver3 | l6 | candidate | fold1 |  |
| verse518 | silver3 | l6 | candidate | holdout |  |
| verse519 | silver3 | l6 | candidate | fold1 |  |
| verse522 | silver3 | l6 | candidate | fold3 |  |
| verse524 | silver3 | normal | candidate | holdout |  |
| verse525 | silver3 | l6 | candidate | fold2 |  |
| verse526 | silver3 | l6 | candidate | fold1 |  |
| verse527 | silver3 | l6 | candidate | fold3 |  |
| verse529 | silver3 | l6 | candidate | fold3 |  |
| verse530 | silver3 | l6 | candidate | fold4 |  |
| verse532 | silver3 | l6 | candidate | fold4 |  |
| verse533 | silver3 | normal | candidate | holdout |  |
| verse534 | silver3 | l6 | candidate | fold4 |  |
| verse535 | silver3 | l6 | candidate | fold4 |  |
| verse536 | silver3 | l6 | candidate | fold4 |  |
| verse539 | silver3 | l6 | candidate | fold2 |  |
| verse540 | silver3 | l6 | candidate | fold1 |  |
| verse542 | silver3 | l6 | candidate | fold4 |  |
| verse544 | silver3 | l6 | candidate | holdout |  |
| verse545 | silver3 | l6 | candidate | fold4 |  |
| verse547 | gold3 | t13 | candidate | holdout |  |
| verse549 | gold3 | four_lumbar | candidate | holdout |  |
| verse550 | silver3 | normal | candidate | holdout |  |
| verse551 | silver3 | l6 | candidate | holdout |  |
| verse553 | silver3 | l6 | candidate | fold1 |  |
| verse554 | silver3 | l6 | candidate | fold2 |  |
| verse555 | silver3 | l6 | candidate | fold1 |  |
| verse556 | silver3 | l6 | candidate | fold3 |  |
| verse557 | silver3 | l6 | candidate | fold2 |  |
| verse560 | silver3 | l6 | candidate | fold2 |  |
| verse565 | silver3 | l6 | candidate | fold4 |  |
| verse569 | silver3 | l6 | candidate | fold3 |  |
| verse570 | silver3 | l6 | candidate | fold2 |  |
| verse571 | silver3 | l6 | candidate | fold1 |  |
| verse572 | silver3 | l6 | candidate | fold4 |  |
| verse573 | gold3 | normal | candidate | holdout |  |
| verse576 | silver3 | l6 | candidate | fold3 |  |
| verse577 | silver3 | l6 | candidate | fold1 |  |
| verse578 | silver3 | l6 | candidate | fold3 |  |
| verse580 | silver3 | l6 | candidate | fold3 |  |
| verse581 | gold3 | l6 | candidate | fold3 | IIIb |
| verse582 | silver3 | t13 | candidate | none |  |
| verse585 | gold3 | l6 | candidate | fold3 |  |
| verse586 | silver3 | l6 | candidate | fold1 |  |
| verse587 | silver3 | l6 | candidate | fold1 |  |
| verse588 | gold3 | t13 | candidate | none |  |
| verse590 | silver3 | l6 | candidate | fold2 |  |
| verse592 | silver3 | l6 | candidate | fold2 |  |
| verse593 | silver3 | l6 | candidate | fold1 |  |
| verse597 | silver3 | l6 | candidate | holdout |  |
| verse598 | silver3 | l6 | candidate | fold4 |  |
| verse599 | silver3 | l6 | candidate | fold4 |  |
| verse601 | silver3 | t13 | candidate | holdout |  |
| verse602 | gold3 | t13 | candidate | none |  |
| verse604 | silver3 | l6 | candidate | fold4 |  |
| verse605 | silver3 | l6 | candidate | fold1 |  |
| verse606 | silver3 | l6 | candidate | fold2 |  |
| verse607 | gold3 | l6 | candidate | fold4 |  |
| verse609 | silver3 | l6 | candidate | fold3 |  |
| verse612 | silver3 | l6 | candidate | fold3 |  |
| verse613 | silver3 | l6 | candidate | fold1 |  |
| verse614 | silver3 | l6 | candidate | fold4 |  |
| verse615 | silver3 | normal | candidate | holdout |  |
| verse616 | silver3 | l6 | candidate | fold2 |  |
| verse618 | silver3 | l6 | candidate | fold3 |  |
| verse619 | silver3 | l6 | candidate | holdout |  |
| verse620 | silver3 | l6 | candidate | fold4 |  |
| verse623 | silver3 | l6 | candidate | fold2 |  |
| verse626 | silver3 | l6 | candidate | fold3 |  |
| verse631 | gold3 | t13 | candidate | none |  |
| verse636 | silver3 | l6 | candidate | fold1 |  |
| verse642 | silver3 | l6 | candidate | holdout |  |
| verse646 | silver3 | normal | candidate | holdout |  |
| verse705 | silver3 | normal | candidate | holdout |  |
| verse707 | silver3 | l6 | candidate | none |  |
| verse751 | silver3 | l6 | candidate | fold3 |  |
| verse755 | silver3 | normal | candidate | holdout |  |
| verse756 | silver3 | normal | candidate | holdout |  |
| verse759 | gold3 | normal | candidate | holdout |  |
| verse761 | silver3 | normal | candidate | holdout |  |
| verse768 | silver3 | l6 | candidate | fold2 |  |
| verse804 | silver3 | normal | candidate | holdout |  |
| verse809 | gold3 | normal | candidate | holdout |  |
| verse810 | silver3 | l6 | candidate | fold2 |  |
| verse814 | silver3 | l6 | candidate | fold2 |  |
| verse816 | silver3 | l6 | candidate | fold1 |  |
| verse817 | silver3 | normal | candidate | holdout |  |
| verse820 | silver3 | normal | candidate | holdout |  |
| verse821 | silver3 | normal | candidate | holdout |  |
| verse825 | silver3 | normal | candidate | holdout |  |
| verse835 | silver3 | normal | candidate | holdout |  |

## Holdout and folds

Persons the SPINEPS to FleXray route holds out or deals into folds (data/splits/anomaly-holdout.json) are carried, flagged, and never trained on (training_allowed 0).

| Member | Role | Persons |
| --- | --- | --- |
| enhance_pet | none | 1,597 |
| totalsegmentator | none | 1,775 |
| verse | fold1 | 19 |
| verse | fold2 | 18 |
| verse | fold3 | 18 |
| verse | fold4 | 18 |
| verse | holdout | 33 |
| verse | none | 249 |

## Inputs

- data/gold3-ct/admission.json: 7ce2b7fdf6fc885a6eed4ecb03b7867ca1c7ecffb0b70299177a893c26323daf
- data/gold3-ct/enhance-pet/FACTS.json: 43ef43abe1dbaecdfa6c778815446668a7cc6f9da5ffcdcacb30e0fc90798ae5
- data/gold3-ct/enhance-pet/bucket.json: 42678637bf4c9243310339b93d0a854ef85916f76953577c35a4656388f5799a
- data/gold3-ct/enhance-pet/facts-b.jsonl: 12eb15d27f64b58cc2aee20cfe415fc6c88eebaad6936e4fb01d5760a976f7b4
- data/gold3-ct/enhance-pet/facts.jsonl: 95cc36bf5e4c710bb0000e8a1eb9290dae7ca730c88a347ca9792110f96cd847
- data/gold3-ct/enhance-pet/record.json: 143d447a7dc5c1aab4c33abb0e68999b08e268acf1fa7067539f097545c946d3
- data/gold3-ct/members.json: 2a7a2fd9ad4e0fae8adc3f409f43300782cf63bde2d6f5ca5107efe5f5e41fba
- data/gold3-ct/totalsegmentator.json: cc2bb3e7404e04ee73862f1d9e03a92b5dd9b2f685a343d499ef934be6799b7b
- data/gold3-ct/totalsegmentator/facts.jsonl: a0cb5b927c7b50845912198a003572315b8cccf085eeb6a1121a2eb7c8803356
- data/gold3-ct/verse.json: 88b4d0f268697532d1cdc53ccf677f012f8e737e4b02a9652f66606a29a7fdea
- data/gold3-ct/verse/facts.jsonl: 7278e12b820bab9b7458a631564ec7ca67fd792734aaf6de1203b3f549d94437
- data/gold3-ct/verse/series.json: 9ce47932389eee6f51b5c8359c3091575c403a0e20375878169bd9d29e81ce08
