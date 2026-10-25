# SPINEPS to FleXray: finding anomalous spines, testing the finding, and fine-tuning for it

Source: the thread "Plan the FleXray audit for #391", 2026-10-25, from the owner's message of 21:00 UTC. Confidential with the rest of SchwingNet's method: it names the record's anomaly counts and the counting line's use of them. The public half of #391 is symphony-template's docs/research/flexray-audit-plan-2026-10-25.md, and this note changes none of its items. It counts their jobs once, in section 6.

## 1. What was asked, and how it is read

The owner, verbatim: "use spineps to segment a set of CTs strategically chosen initially the ones with paired XRs and then use the textbook to choose the rest of the CTs for segmentation from the enormous collection of segmentations already done in the osc drive, convert them to DRRs per the flexray approach and see if it finds anomalous spines, so hold out a few known from versefusion to test this approach for sensitivity and specificity and then finetune the flexray for anomalies".

The reading taken here:

- SPINEPS, with its labeller VERIDAH, is the anomaly finder on CT. VERIDAH names T13 (id 28) and L6 (id 25), which TotalSegmentator cannot.
- The CTs come in two tranches:
  - first the CTs that have a paired X-ray;
  - then the rest, chosen by the textbook's rules from the CTs already segmented on the grid.
- The finder's calls are tested for sensitivity and specificity against a few VerSeFusion spines whose variants the readers know. VerSeFusion is the VerSe'19 and '20 union, 374 series of 355 patients, not a set of fused vertebrae; data/reproduce/sources.json lines 2669 and 2721.
- The spines it finds become DRRs rendered the way FleXray renders: fxr-render on packed ct-seg data.
- FleXray is fine-tuned on those DRRs with an L6 and a T13 channel.

An alternative reading is that "it" means FleXray finding anomalous spines on the DRRs. Section 4 runs that test too, at no extra count, because the same job can do it.

## 2. What already exists, so most of the segmentation is done

The grid already holds SPINEPS and VERIDAH runs over most of what the owner names. That changes "segment" into "inventory, select, and segment only the gap". Each source below is from the records.

| Set | SPINEPS on the grid | Where |
| --- | --- | --- |
| C-ArmLSpine, 149 CBCT, paired with 299 spot frames | done, with TotalSegmentator beside it | carmlspine/spineps/ and carmlspine/ts/; symphony-template docs/research/paired-ct-xray-annotation-plan.md section 8 |
| COBRA2026 planning CTs, paired with kV projections | done, TotalSegmentator against SPINEPS into seg/levels.json | cobra2026/seg; the same section |
| CTSpinoPelvic1K, 800 of 800 | done | ~/bench/spineps |
| TotalSegmentator v2 (1,228) and VerSe (374) | done; SPINEPS failed on 72 spines | ~/bench_ts; sources.json 2899 and 3852 |
| The anomaly harvest | done for 12,630 gate-passed acquisition CTs, with TotalSegmentator on all | anomaly_harvest/<collection>/{seg,spineps} |
| SPINEPS masks and body masks | 14,527 NIfTI, 8.2 GB | /rs/rs_grp_oschome/go2432/data/spineps; docs/research/data-manifest/MANIFEST.md line 82 |
| LUMOS, 280 CTs with films | not segmented, and the pairing of CT n with film n is still a hypothesis (spine-datasets #207) | zenodo_lumos |
| DeepFluoro, 6 H5 CTs and 19 vendor CTs | not recorded either way | deepfluoro_h5, deepfluoro_vendor |

SPINEPS is installed on the grid as spineps 2.1.1 (~/mambaforge/envs/spineps) and in /rs/rs_grp_oschome/go2432/envs/spineps212. Its weights are already there. The Blackwell nodes ymh3 and ymh4 cannot run it, and no gate word runs it yet.

Three traps from the record bear on every count below:

- Masks harvested before spinesurg-ct-nnunet's commit 147428d carry raw ids 1 to N, not level names.
- VERIDAH alone matched reader truth on CTSpinoPelvic1K for 10 of its 24 L6 calls and 0 of its 52 T13 calls (chapter 7). As a single labeller it over-calls.
- On TotalSegmentator's 70 outside-read CTs, the screen found only 12 to 17 of 28 L6.

So the finder that section 4 tests is two labellers agreeing, TotalSegmentator's count against SPINEPS's, as the textbook ranks truth (chapter 7: a read above two labellers, two above one, one above morphology). VERIDAH alone is reported beside it for the record.

## 3. The holdout, frozen before anything runs

Chapter 9 defines held out: no checkpoint in the lineage saw the person, and derived images inherit their source's person. Chapter 9 also says the frozen test list grows only by pull request, before shards are cut. So the first change is a pull request that writes the holdout list, data/splits/anomaly-holdout.json, with its hash, before any job reads it.

From VerSeFusion, where readers recorded the variants (Loeffler 2021):

- **T13:** all six recorded, verse547, 582, 588, 601, 602 and 631. VerSe's has_T13 field says 18 and is wrong (chapter 7). verse707 is a recorded conflict and stays out until it is re-read.
- **L6:** the spines whose raw mask carries id 25 and that the Loeffler table reads as L6. The record holds four counts, 85, 47, 50 or 87, and 39 of the 85 lack id 25, so the CPU job of section 6 counts the raw masks first and the list takes the intersection. Ten are taken, by the lowest subject number. A few, as asked, keeps most L6 spines for training.
- **Normals:** twenty spines read as having neither variant and Castellvi grade 0 to I, matched to the positives by VerSe release and field of view. Castellvi I shares its cell with grade 0 in the table, which makes these normals for count, not for every transitional grade.

What a few known spines can show, as Wilson intervals at 95 percent:

| Holdout result | Sensitivity interval |
| --- | --- |
| 6 of 6 T13 | 61 to 100 percent |
| 10 of 10 L6 | 72 to 100 percent |
| 20 of 20 normals called normal | specificity 84 to 100 percent |

Chapter 14 sets 22 carriers with no miss for an 85 percent sensitivity claim, and only 7 T13 persons exist in all sources. These numbers therefore describe the method on these spines and are not a claim of the method's sensitivity.

A second truth set guards against VerSe being in VERIDAH's own training. VERIDAH comes from the group that made VerSe, and its paper's abstract names no training set (arXiv 2601.14066, read through its index pages, since arXiv is refused here). CTSpinoPelvic1K's reader-confirmed L6 spines serve, without the seven disputed records chapter 7 keeps out of truth, with matched normals. It is scored the same way, so a VerSe result much better than this one points to leakage rather than skill.

The holdout persons never enter the fine-tune, the selection's training list or any render shard. The COBRA and C-ArmLSpine transitional persons stay test-only, as the harvest directive requires.

## 4. The stages

1. **Inventory and select (one CPU job).** This job reads the existing masks and levels.json files, maps raw ids to level names where a mask predates 147428d, and counts thoracic and lumbar bodies under each labeller. It writes three things.
   - The two-labeller anomaly call for every CT: T13, L6, four lumbar, eleven thoracic, or normal. A CT whose two labellers disagree is no_count.
   - The holdout's sensitivity and specificity, two-labeller and VERIDAH alone, on both truth sets of section 3.
   - The selection.
   
   The selection follows the textbook's rules:
   - Variants are 25 to 35 percent of the rendered CTs by the choice of CTs, never by duplication (chapters 9 and 14).
   - Collections are ranked by n times P(junction countable) times prevalence.
   - Truth order is a read, then two labellers, then one.
   - The disputed records, every one-labeller call and the holdout are left out.
   
   The paired CTs come first, C-ArmLSpine and COBRA, both already segmented. Only aggregates leave the grid.
2. **SPINEPS on the paired CTs that lack it.** This is LUMOS's 280 once spine-datasets #207 proves the pairing, and DeepFluoro's CTs if stage 1 finds them unsegmented. The rule is a timing run before a production array (chapter 21), so the count asked now is one GPU job on ten CTs. The array is asked later with its number. Neither is on the anomaly test's path, which runs on masks that already exist.
3. **Pack and render (one CPU job, one GPU job).** The pack is fxr-dataset pack of the selected CTs with their SPINEPS masks in the ct-seg preprocessing FleXray released: a 512 by 512 by 256 crop, HU clipped to -1000 to 2000, float16. The pack is item 7's pack of the #391 plan, shared, not a second one. The render is fxr-render with FleXray's MOOSE profile, the holdout's CTs rendered into a test package of their own. A dataset spec maps SPINEPS's ids into a protocol that carries vertebra_l6 and vertebra_t13. This job is item 8's render.
4. **FleXray as released on the holdout's renders, and the counting figure (one GPU job).** Two readings of "see if it finds anomalous spines" are scored in one run.
   - Does FleXray's output reveal the variant? It has no L6 or T13 channel and was trained with L6 as background, so the record predicts a missed body.
   - Does the count from the anchor still name every body right when every body is boxed? The same job draws the figure of section 5.
5. **Fine-tune (one GPU job).** FleXray from its released bundle, the 61 output rows copied row by row into a head with two more rows for L6 and T13. This is item 14's row-wise copy, which the fork lacks and SchwingNet brings by pull request, with the extended protocol and model label list under protocol.config_root. The fine-tune trains on the selection's renders and never on the holdout.
6. **Evaluate (one GPU job).** The fine-tuned model is scored on four things:
   - the holdout's renders: per-body naming, and per-spine sensitivity and specificity for the variant;
   - C-ArmLSpine's transitional cases case42, case121 and case136 on real frames;
   - the 1,627 truth boxes FleXray was first scored on, so the fine-tune's cost on ordinary spines is seen;
   - the counting line with the fine-tuned names in place of the released ones.

## 5. The counting figure on a real anomalous spine

The owner asked on 2026-10-25 at 21:11 UTC: "no i want the stitched fields figure to be a visualization based on a real example for demonstrating how the counting algorithm can score 100% even on anomalous spines by error correction as long as it detects all the vertebra".

The real anomalous spines are only on the grid. This container is refused by VerSe's hosts (s3.bonescreen.de and osf.io, both 403 at the proxy), so the figure is drawn in stage 4's job. It runs on four holdout spines: one T13, one L6, one four-lumbar from CTSpinoPelvic1K's reader-confirmed set, and one normal.

For each spine the figure shows three panels, in the layout of the stitched fluoroscopy figures:

- **The round fields,** a to f. Each is a lateral render cut at 140 mm and stepped up from the sacrum with two bodies of overlap (chapter 34's optimum). Every body's box is drawn from the CT mask's projection, which is what "detects all the vertebrae" means here. FleXray's own name for each body is written beside it, in red where it is wrong.
- **The stitched panorama,** numbered from the anchor by the chain.
- **The render with the readers' names,** the variant marked.

Under each spine, two scores: FleXray's per-frame names against truth, and the count from the anchor against truth.

Error correction is shown in two ways:

- The count consumes box positions and never reads a class (chapter 10), so a wrong name in a frame does not move the count.
- src/schwingnet/chain.py's decoder takes FleXray's per-body names as its posteriors. It decodes them over the column hypotheses of 11 to 13 thoracic and 4 to 6 lumbar bodies and writes the names it settles on. Where the boxes are complete, the decoder's names are expected to match the readers' on all four spines. That expectation is the claim the figure tests, not one it assumes, and the figure prints what it finds.

The figure goes to the project's Weights and Biases run, the way the v1 flow already returns its witness frames from the grid. The PNG stays on the lab volume beside it. A grid job prints only text to the gate's log, and the runner chain that returns files has no lab volume (grid.yml), so W&B is the one existing route back.

## 6. The counts

New jobs beyond the #391 plan, and the plan's own jobs this route uses:

| Stage | Fetches | CPU jobs | GPU jobs | Against the #391 plan |
| --- | --- | --- | --- | --- |
| 1 Inventory, select, holdout test | 0 | 1 | 0 | new |
| 2 SPINEPS timing on ten paired CTs | 0 | 0 | 1 | new; the array is asked later with its number |
| 3 Pack and render | 0 | 1 | 1 | item 7's pack and item 8's render, not new |
| 4 FleXray as released, and the counting figure | 0 | 0 | 1 | new |
| 5 Fine-tune | 0 | 0 | 1 | item 14's fine-tune, counted now |
| 6 Evaluate | 0 | 0 | 1 | new |
| **Total** | **0** | **2** | **5** | 3 GPU and 1 CPU new, plus item 14's GPU counted now; item 7's pack and item 8's render shared |

No fetch is needed. SPINEPS and its weights are on the grid, and FleXray's released bundle is there from the public benchmark (bench flexray_carmlspine). The renders' sizes are read before the job writes, and each stage's output is admitted against the oschome quota as the bank word admits a bank's.

Two counts another thread handed to this plan, with the owner's word to do what is recommended:

- **The six 20-epoch trials** (grid/sweeps/trials.json, word schwingnet-sweep-trials). Not sent, since the route does not need SchwingNet's own trained baseline.
- **The scaling study, SchwingNet #385.** Kept as its own item, with fxr-render as one arm, after stage 3 shows the render path works.

## 7. Before any job: the code, by pull request

Every stage above waits on code that is written first and sent nowhere:

- the holdout list and its hash;
- tools/anomaly_route.py, which does the inventory, the id mapping, the two-labeller call, the selection and the scoring with Wilson intervals;
- the protocol and dataset spec with L6 and T13;
- the row-wise head copy;
- the figure tool;
- the gate words schwingnet-anomaly-select, -render, -figure, -tune and -eval, each one job through hpcworker's job submit with its class.

The fine-tuned weights inherit FleXray's CC BY-NC 4.0, and VerSe is CC BY-SA 4.0 in the registry. So the fine-tune is research use until item 15, the owner's licence decision, which is laid out as options and never blocks.
