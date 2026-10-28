# What the 42 papers assume, and the data beyond them

Source: the thread "Get full texts through Elsevier key", 2026-10-28, answering the owner's question of 17:00 UTC ("can you tell me about what assumptions im making by limiting to these papers? surely there is more data on the internet particularly given the introduction of ct based morphometrics"). The same answer is the Claude Doc https://claude.ai/artifact/XREXDs6498pSUMn5o4dE1b. Confidential, this repository only.

Every dataset and study below was read on its own page on 2026-10-28, and each claim was checked a second time against that page; the corrections of that check are in the text.

## The short answer

The naming rule (bordercall's SchwingCheck) does not rest on 42 papers. It rests on one source, Panjabi's twelve cadaveric spines, measured in 1991 to 1993. The other 39 papers of spine-program's synthetic_spine collection were gathered for one figure of the CTSpinoPelvic1K article and feed nothing the rule computes. So the assumptions are Panjabi's, plus every constant a table of means cannot supply, which were set by hand.

Much more data exists, most of it new since CT segmentation became routine. But nobody has published what the rule needs most, the within-person correlations across the whole column. Those have to be measured from people, one whole spine at a time, and the best source is one the lab already holds: the SPINEPS masks of full CTs counted from C2, the owner's plan of 2,000 patients (bordercall TODO.md, item P step e, the owner's words of 2026-10-27 16:43 UTC).

## What the rule takes from the papers

- Three papers in the 42: Panjabi's cervical (1991), thoracic (1991) and lumbar (1992). They give the seven measures of the archive's rule.
- One paper outside the 42: the facets paper (Spine 1993;18(10):1298-1310). With the other three it brings the build-up study's pool to 32 measures.
- All four measured the same twelve spines: 8 men and 4 women, aged 19 to 59 (mean 46), half dead of cancer, ancestry and screening for spine disease not stated, boiled and bleached, measured with an electromechanical morphometer.
- A level's spread is its printed SEM times the square root of 12.

The other 39 were collected on 2026-09-10 for Figure 6 of the CTSpinoPelvic1K article, which was later cut back to Panjabi alone. The level table covers T11 to L5, and synthetic_spine's README says "There is no record of a systematic search."

## The assumptions

| Assumed | What the record shows | What would settle it |
|---|---|---|
| Twelve spines give every level's mean and spread | The error of a level's mean is about 0.29 of a spread (1 over the root of 12), about what neighbouring levels differ by; the same twelve people stand behind every level | Hundreds of whole columns measured the same way |
| Dry, boiled bone measures like CT or fluoroscopy | CT body heights ran about 6 mm above Panjabi on CTSpinoPelvic1K with every artefact excluded (spine-program 03 STATUS.md, F.35); the mapping from masks is checked only in the lumbar spine and refuses the pedicle | The table measured in the modality it is used on |
| Levels move together at rho 0.5 (0.25 between levels given size), equal at every distance | Set by hand (exact.py); no decay with distance is modelled | Within-person correlations from whole columns |
| The measures are independent given size | Set by hand; the one external pair the record holds (body AP against lateral diameter) correlates 0.8 | The same |
| One size factor with a 7% spread, on top of spreads that already include size | Heights rise about 6.5% per level from T9 to L1 (Palm 2025), so the size factor can pass for a one-level shift, and size is counted twice | Height or another size measure with each column |
| Measurement error of 1 mm, Gaussian, at every level | A round figure; the only measured chord error is a phantom's, 3.12 mm with 5 mm slices and a 4 degree tilt (bordercall scanimport/README.md) | Repeat measures, or masks against a reader |
| Every spine has 7, 12 and 5 bodies | Yoon 2024: 30 of 450 young adults (6.7%) without 24 presacral bodies; the rule abstains on anomalies by design but does not name them | Reader-counted anomalous columns |
| Every place from C3 to L5 equally likely | Real fields cluster where surgery is done | A surgical series |
| Healthy middle-aged spines stand for everyone | Weight, age and sex are hooks at zero; sex gaps vary by level (Palm 2025), canal size by ancestry (Shin 2024) | Covariates with each column |
| The 42 papers are the published evidence | No search; the series disagree by 17 to 71%; Tan 2004 and Busscher 2010 cover C3 to L5 but only their T12 to L5 rows were copied | A designed search, and those two tables read whole |

## What they cost, by bordercall's own checks

At three bodies, for answers given at 0.99:

- A table re-estimated from twelve people: right 95.5%, not the promised 99.78% (archive record exact-2026-10-26); in the build-up study (bordercall PR 18) 95.75% with the seven measures and 98.05% with all 32.
- The same from 50 people or more: 99.36% or more (PR 18, the data axis). This is the curve the owner's 2,000 CTs would sit on.
- 3 mm of measurement error: between 82.6% and 96.85% across the rules (archive/docs/SCHWINGCHECK_LEVELCHECK.md, Limitations 3).
- Measures correlated 0.4, a twelve-spine table and 1.5 mm of error together: 92.9% (the same, Limitations 5).
- Six lumbar bodies or a T13, all 32 measures, three to nine bodies: 5.1% to 7.2% of the answers wrong, nearly all at the extra body (TODO.md, rung 0).

Every test draws its spines from the generator the rule assumes, so the 0.99 describes that generator, not patients. No real spine has been scored.

## Person-level data that could be measured

| Source | People | Coverage | Access | Held here |
|---|---|---|---|---|
| VerSe 2019 and 2020 | 355 people, 374 CTs | C1 to L5, L6 and T13 labelled; mostly partial | Open, CC BY-SA 4.0 | Yes; 17 whole columns, provisional |
| TotalSegmentator v3 (Zenodo 22688904, Sept 2026) | 1,939 CTs, 291 children | C1 to sacrum; v3 fixed its vertebra label mix-ups | Open, CC BY 4.0 | Yes; 142 whole columns |
| CTSpine1K | 1,005 CTs | C1 to L6, thin in the neck | Open, CC BY-NC-SA 4.0 | Yes; 782 of its people are CTSpinoPelvic1K's |
| VertebralBodiesCT-Labels | 1,460 CTs | Bodies T1 to L5 and sacrum; no neck, canal or pedicle | Open, CC BY-SA 4.0 | 70 |
| CADS | 22,022 CTs from 40 collections | C1 to sacrum, machine labels | Gated, each source's licence | Access granted 2026-10-21, not fetched |
| NLST masks (Imaging Data Commons) | 26,194 smokers (the source also says 24,194) | Mostly thoracic, machine masks; C7, L3 and L4 often in pieces | Open | No |
| New Mexico Decedent Image Database | Over 15,000 decedents | Whole-body post-mortem CT, with height and weight in life; no labels | Free, approved request and agreement | No |
| NAKO MRI | About 30,000 imaged; 10,215 segmented C2 to L5 (Streckenbach 2022) | Whole spine; VERIDAH counted 6,291, anomalies 5.8% thoracic and 9.7% lumbar, labels not released | Application | No |
| UK Biobank lateral DXA | Tens of thousands | T4 to L4, projected heights only | Application, GBP 6,000 to 9,000 | No |
| NHANES 2013-14 DXA (DXXL4_H and its sibling files) | 3,330 adults 40 and over | T4 to L4, three heights and a 95-point outline per body, linked by SEQN to age, sex, height, weight | Public | No record mentions it |
| NHANES II films | About 17,000 people | Lateral lumbar and cervical films | Public | 543 films of 364 people |
| Framingham MDCT | 4,427 | About T7 to T11 and L2 to L5 | dbGaP | No |
| MrOS and SOF | 5,994 men and 9,704 women, 65 and over | T4 to L4 films, six-point heights | NIA biobank; release of heights not stated | No |

## Published summaries

| Study | People | What it gives |
|---|---|---|
| Shin 2024 | 1,000 CTs | Lumbar canal by sex and race |
| Palm 2025 | 262, TotalSegmentator on CT | T1 to L5 heights by sex, ratios between levels |
| Masharawi 2008 | 240 skeletons | T1 to L5 body shape in every person, by a protocol unlike Panjabi's |
| Pavlova 2017 | 1,511 DXA | A T10 to L5 shape model |
| Meng 2020 | 80 VerSe CTs | A whole-spine shape model, non-commercial |
| Hipp 2022 | About 17,000 films (7,364 lumbar, 9,662 cervical) | Per-level ratios, correlations between six measures, adjacent-level differences |
| Yukawa 2012 | 1,230 Japanese adults | Cervical canal, body and disc height by sex and decade |
| Nell 2019 (SHIP) | 2,453 | Cervical canal and body depth |
| Yoon 2024, Doo 2020, Tins 2016, Zhou 2023 | 450, 1,340, 418, 6,097 | How often the count is not 7, 12 and 5 |

Griffith 2016 (1,080 people) is the one large series already among the 42.

Searched for and not found: a covariance of Panjabi-type measures across the whole column from 200 or more people (a 2026 review of 85 lumbar shape models names no whole-spine one); a C2 to L5 table of Panjabi's measures from hundreds of people; per-level CT morphometry at TotalSegmentator scale beyond Palm's 262.

## What the lab already holds

- The census: 21,622 CTs of 21,603 people with SPINEPS masks (tier 1 5,094, tier 2 12,217); both junctions are in the field in 2,951 tier-1 and 8,050 tier-2 CTs. How many count from C2 is the first table of the bordercall pilot (bordercall-corpus.md), approved for two CPU jobs and unsent. The pilot pins bordercall 6938a2e's measure code, so its numbers are checked against the seven measures before they feed a table.
- ENHANCE.PET: 1,557 whole columns of 865 to 1,478 people, per-level facts in data/gold3-ct/ (gold3-ct/README.md); MOOSE masks, oncology patients.
- TotalSegmentator v3: 142 whole columns. VerSe: 17, provisional.
- CTSpinoPelvic1K: 802 measured in Panjabi's terms, but excluded as truth and without C2.
- C-ArmLSpine (149) and COBRA (692): CT paired with projections, both test sets.

## What more data fixes, and what it does not

More people remove sampling error, not bias. 2,000 whole columns would fix the error of every level's mean and spread, every constant now set by hand (rho, the correlation between measures, the size spread, the slopes of age, sex and height), the anomaly rates of the population, and the modality of the table. They would not fix a segmenter's bias (CT already runs about 6 mm above Panjabi), who is scanned (hospital and cancer patients, not surgical candidates), where operations happen (the prior over places), how the same bodies look under a C-arm, how often a machine count is wrong (that needs a reader-counted sample), or columns whose count breaks (fused blocks, hemivertebrae, metal).

## What waits for the owner

1. The bordercall pilot, approved and unsent under the rule that nothing goes to the grid for now; the status word first.
2. Whether ENHANCE.PET's MOOSE masks and TotalSegmentator's 142 may feed the table; recommended only as a second arm, never pooled with SPINEPS.
3. The NHANES 2013-14 DXA files, 13 public files, size read first; a fetch needs the owner's word and count.
4. Reading Tan 2004's and Busscher 2010's whole tables and the thoracic rows of Lien 2007 and Kunkel 2011.
5. A designed search, screened against the 42.
6. Which C-ArmLSpine and COBRA people may be spent fitting how CT measures differ from fluoroscopy.
7. Later, applications that need the owner's signature: NMDID first (free, whole columns with height and weight), then NAKO and UK Biobank.

## Sources

- NHANES DXXL4_H: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2013/DataFiles/DXXL4_H.htm
- VerSe: https://arxiv.org/pdf/2103.06360 (Sci Data doi 10.1038/s41597-021-01060-0)
- TotalSegmentator v3: https://zenodo.org/records/22688904
- CTSpine1K: https://www.melba-journal.org/papers/2025:037.html
- CADS: https://huggingface.co/datasets/mrmrx/CADS-dataset
- VertebralBodiesCT-Labels: https://huggingface.co/datasets/fhofmann/VertebralBodiesCT-Labels
- NLST masks: https://portal.imaging.datacommons.cancer.gov/analysis_results/TotalSegmentator-CT-Segmentations
- NMDID: https://nmdid.unm.edu/
- NAKO: https://transfer.nako.de/transfer/index; Streckenbach 2022 https://www.mdpi.com/2227-9032/10/11/2132; VERIDAH https://arxiv.org/abs/2601.14066
- UK Biobank: https://biobank.ctsu.ox.ac.uk/ukb/ukb/docs/DXA_explan_doc.pdf
- Framingham MDCT: https://ega-archive.org/studies/phs003593
- Hipp 2022: https://www.medrxiv.org/content/10.1101/2022.05.05.22274448v1 (doi 10.1002/jbm4.10677)
- Palm 2025: https://www.nature.com/articles/s41598-025-05091-0
- Shin 2024: https://scholars.duke.edu/publication/1643335
- Masharawi 2008: https://cris.haifa.ac.il/en/publications/vertebral-body-shape-variation-in-the-thoracic-and-lumbar-spine-c/
- Pavlova 2017: https://aura.abdn.ac.uk/items/2610af3c-7ade-4f30-ab90-12e9d6ff8285/full
- Meng 2020: https://link.springer.com/doi/10.1007/978-3-030-61056-2_10
- Yukawa 2012: https://www.doi.org/10.1007/S00586-012-2176-4
- Nell 2019: https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0222682
- Yoon 2024: https://www.ajnr.org/content/45/1/119
- Doo 2020: https://www.anesth-pain-med.org/journal/view.php?id=10.17085%2Fapm.2020.15.1.103
- Tins 2016: https://link.springer.com/10.1007/s13244-016-0468-7
