# SPINEPS to FleXray: finding anomalous spines, testing the finding, and fine-tuning for it

Source: the thread "Plan the FleXray audit for #391", 2026-10-25, from the owner's message of 21:00 UTC, the owner's Go of 21:22 UTC for seven jobs, two CPU and five GPU, sent stage by stage, and the owner's yes of 22:30 UTC to eight more GPU jobs for a four-fold cross-validation of the fine-tune (section 5). Confidential with the rest of SchwingNet's method: it names the record's anomaly counts and the counting line's use of them. The public half of #391 is symphony-template's docs/research/flexray-audit-plan-2026-10-25.md. This note changes two of its items: items 7 and 8 share this route's pack and render (section 5), so both now wait on stage 1's selection and on the frozen holdout. It also brings item 14's fine-tune forward on the owner's Go, as research use only (section 7).

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

An alternative reading is that "it" means FleXray finding anomalous spines on the DRRs. Stage 5 runs that test too, in the same job as the figure.

## 2. What already exists, so most of the segmentation is done

The grid already holds SPINEPS and VERIDAH runs over most of what the owner names. That changes "segment" into "inventory, select, and segment only the gap". Each source below is from the records.

| Set | SPINEPS on the grid | Where |
| --- | --- | --- |
| C-ArmLSpine, 149 CBCT, paired with 299 spot frames | done, with TotalSegmentator beside it | carmlspine/spineps/ and carmlspine/ts/; symphony-template docs/research/paired-ct-xray-annotation-plan.md section 8 |
| COBRA2026 planning CTs, paired with kV projections | masks recorded for 146 of 692 CTs, all with raw ids; anomaly_harvest/cobra may hold more | cobra2026/seg/spineps; the same section |
| CTSpinoPelvic1K, 800 of 802 | done, every mask with raw ids (from before 147428d) | ~/bench/spineps/native |
| TotalSegmentator v2 (1,228) and VerSe (374) | done; SPINEPS failed on 72 spines; the VerSe store is mostly raw ids | ~/bench_ts; sources.json 2899 and 3852 |
| The anomaly harvest | done for 12,630 gate-passed acquisition CTs, with TotalSegmentator on all | anomaly_harvest/<collection>/{seg,spineps} |
| SPINEPS masks and body masks | 14,527 NIfTI among 41,571 files (15,507 JSON, 11,412 symlinks), 8.2 GB in all | /rs/rs_grp_oschome/go2432/data/spineps; docs/research/data-manifest/MANIFEST.md line 82 |
| LUMOS, 280 CTs with films | not segmented, and the pairing of CT n with film n is still a hypothesis (spine-datasets #207) | zenodo_lumos |
| DeepFluoro, 6 H5 CTs and 19 vendor CTs | not recorded either way | deepfluoro_h5, deepfluoro_vendor |

SPINEPS is installed on the grid as spineps 2.1.1 (~/mambaforge/envs/spineps) and in /rs/rs_grp_oschome/go2432/envs/spineps212. Its weights are already there. The timing stage (section 5, item 2) is the first gate word that runs it, through spinesurg-ct-nnunet's benchmark/run_spineps_cases.py as its slurm/spineps_cases.sh ran it. The counts in the table are what the records said when this note was written; the timing stage's inventory reads the folders themselves (tools/anomaly_timing.py), since COBRA's LSTV screen (cobra2026/lstv/seg) and the harvest collections may hold VERIDAH-named masks the table does not count, and its report carries the counts as they stand.

Three traps from the record bear on every count below:

- Masks harvested before spinesurg-ct-nnunet's commit 147428d carry raw instance ids 1 to N, not level names. On such a mask "id 25 present" means only "at least 25 instances", and no level is ever named by a SPINEPS id: it is named from the centroid file, and a mask passes spinesurg-ct-nnunet's tools/spineps_ids.py guard before anything trains on it.
- VERIDAH alone matched reader truth on CTSpinoPelvic1K for 10 of its 24 L6 calls and 0 of its 52 T13 calls (chapter 7's one-labeller screen; the attribution to VERIDAH is the topic memory spineps-ids-can-be-scrambled). As a single labeller it over-calls.
- On TotalSegmentator's 70 outside-read CTs, the screen found only 12 to 17 of 28 L6.

So the finder is two labellers agreeing, TotalSegmentator's count against SPINEPS's, as the textbook ranks truth (chapter 7: a read above two labellers, two above one, one above morphology). VERIDAH alone is reported beside it for the record.

## 3. What the records already say: the finder against the readers

"See if it finds anomalous spines" needs no grid job for the CT finder: spinesurg-ct-nnunet's VerSe screen (SchwingNet/results/transitional_registry/verse/screened.csv, sha256 a0cb756c2ef7) carries both labellers' counts for every VerSe scan beside the readers' structure (Loeffler 2021, Supplementary Table 1). `python3 tools/anomaly_route.py score` reads it. Each person is scored once, by its first scan; 325 read persons, 6 disputed and left out, 319 scored. A no_count, a single labeller or a discordant pair on a variant is a miss, and on a normal count it is no normal call. Wilson intervals at 95 percent.

A scan is disputed only where something other than the labellers under test contradicts the read: the release mask's own count, an L6 in the mask of a normal read (verse707), or mask ids out of order. The first draft also left out every read that labeller A alone contradicted, ten persons with the mask supporting the read, verse588 and verse601 among them; that dropped exactly the finder's own errors from its score, so they are scored now (the review of #398).

| | Two labellers agreeing | VERIDAH alone |
| --- | --- | --- |
| L6 found (sensitivity) | 22 of 83, 26.5 % (18.2 to 36.9) | 36 of 83, 43.4 % (33.2 to 54.1) |
| T13 found | 2 of 6 (9.7 to 70.0) | 4 of 6 (30.0 to 90.3) |
| four lumbar found | 2 of 2 (34.2 to 100) | 2 of 2 (34.2 to 100) |
| No L6 or T13 on a normal count (specificity) | 228 of 228 (98.3 to 100) | 225 of 228 (96.2 to 99.6) |
| Normal counts called normal (coverage) | 120 of 228 (46.2 to 59.0) | 135 of 228 (52.7 to 65.4) |
| L6 calls right (precision) | 22 of 22 (85.1 to 100) | 36 of 38 (82.7 to 98.5) |
| T13 calls right | 2 of 2 (34.2 to 100) | 4 of 16 (10.2 to 49.5); 11 of the wrong ones are L6 spines |
| four-lumbar calls right | 2 of 14 (4.0 to 39.9) | 2 of 20 (2.8 to 30.1) |

CTSpinoPelvic1K tells the same story on a second set of readers (spinesurg-ct-nnunet SchwingNet/results/transitional_registry/cobra/labeller_validation_ctsp.md): the two-labeller L6 calls are 7 of 7 right (64.6 to 100), and they find 7 of the 29 registry L6 (12.2 to 42.1).

What this means for the route:

- The CT finder is precise and insensitive. When both labellers call an L6 or a T13 it is right in every case on record, and it never calls either on a normal count; it finds about a quarter of the L6 spines. Most L6 misses are the two labellers disagreeing (34 of 61), not a wrong agreed call.
- Its calls are therefore good training labels with a low yield, and a poor screen. The selection takes reads first and two-labeller calls second, and never a one-labeller call.
- Its four-lumbar calls are wrong 12 times in 14, so four-lumbar enters the selection from reads only.
- VERIDAH alone finds more L6 but calls T13 on eleven L6 spines: the textbook's warning, measured.

## 4. The holdout, frozen before anything runs

Chapter 9 defines held out: no checkpoint in the lineage saw the person, and derived images inherit their source's person. The list is data/splits/anomaly-holdout.json, written by `python3 tools/anomaly_route.py freeze` from the committed VerSe screen and the Loeffler table, whose sha256 it records. Nothing about it is chosen by hand.

- **The rank.** Each person's place is the first 8 bytes of sha256 over "schwingnet-anomaly-holdout|2026-10-25|" and the person, lowest first, so the list is the same on any machine and nobody picked the easy cases. Each variant is split over the VerSe releases in proportion to its candidates, and a release short of candidates is topped up from the others.
- **Disputed persons are out of everything,** neither scored, held nor trained: the 6 VerSe persons of section 3's rule (verse026, 417, 559, 707, 753 and 765) and the seven CTSpinoPelvic1K records chapter 7 keeps out of truth (0008, 0021, 0033, 0049, 0176, 0179, 0196).
- **T13: 2 held, 4 left to train.** The rank holds verse547 and verse601 of the six read T13 persons and leaves verse582, 588, 602 and 631 to train, with 3 two-labeller T13 from TotalSegmentator: 7 T13 to train on in the local trial. Holding all six, as the first draft did, would have left the T13 channel nothing verified to learn from.
- **L6: 10 held,** 9 from VerSe'20 and 1 from VerSe'19. Spines with and without id 25 in the release mask are reported as separate strata (6 with, 4 without), since the ones the release masked as their own vertebra are the easier cases.
- **Four lumbar: 1 held,** verse549, so the figure's four-lumbar spine is a held one.
- **Normals: 20 held,** count-normal spines of any Castellvi grade, lumbar ribs and sacralised L5 included and reported as their own strata (12 plain, 5 unassigned subtype, 2 sacralised L5, 1 Castellvi I to II), with both junctions in the field of every scan. Leaving out the hard negatives would flatter the specificity.
- **CTSpinoPelvic1K: 5 of its 16 reader-confirmed L6 held** (0376, 0366, 0005, 0302, 0234) **and 5 read normal counts** (0875, 0151, 0156, 0170, 0760: four sacralised L5 and one Castellvi I to II), by the same rank, frozen now so the select stage can never list them for training; the registry holds only CTSpinoPelvic1K persons with something transitional, so its normals are all hard negatives. VERIDAH comes from the group that made VerSe and its paper names no training set (arXiv 2601.14066, read through its index pages), so a VerSe result much better than this one points to leakage, not skill.
- **Four folds for the cross-validation.** The 73 clean read VerSe L6 persons the holdout leaves are dealt into four folds of 19, 18, 18 and 18, in rank order within each release, and written into the same file. Each fold's fine-tune trains on everything the main one does except its own fold, and is scored on that fold; with the 10 held, which the main fine-tune is scored on, every one of the 83 is tested once by a model that never saw it.

What these few can show, as Wilson intervals at 95 percent if every one is found: 2 of 2 T13, 34 to 100 percent; 10 of 10 L6, 72 to 100; 5 of 5 CTSpinoPelvic1K L6, 57 to 100; 20 of 20 normals, specificity 84 to 100. Chapter 14 sets 22 carriers with no miss for an 85 percent claim, and only 7 T13 persons exist in all sources, so these describe the method on these spines and are no claim of its sensitivity. The finder itself on the holdout alone finds 1 of 10 L6, 1 of 2 T13 and the four-lumbar spine, with no L6 or T13 called on the 20 normals (two of them called four-lumbar).

The cross-validation is what gives L6 a usable number: pooled over the four folds and the holdout, 83 spines. Found in 75 of them (90 percent), the interval would be about 82 to 95. The pooled figure describes the recipe, not one model, since five fine-tunes make it. T13 stays a case series, since 7 T13 persons are all the sources hold.

How the list is held:

- `select` refuses a held or disputed person and fails if one reaches its list; `check` reads any list with a patient_key or person column and fails on one. A harvest collection that screens a registry stream again under another key (validation_ts writes totalsegmentator_v2:sNNNN for the registry's ts:sNNNN) is read in the registry's spelling, so one CT is never two persons. The pack and the fine-tune words run `check` on their lists before they write (section 5), since fxr-train runs outside the catalog and data/splits/test-persons.json, which the catalog reads, accepts only registered sources and VerSe and CTSpinoPelvic1K are not registered.
- The holdout is packed and rendered apart, as a test package, never into a training shard.
- **Lineage is unresolved for FleXray as released.** FleXray's configs do not list MOOSE 3.0's sites, and the MOOSE spec carries vertebra_l6. Until item 6's census by file finds none of these persons in MOOSE 3.0 or FluXray, stages 5 to 7 report "lineage unresolved" beside every holdout number, as chapter 9 says unknown is not clean.

## 5. The stages: seven words, one job each, and the folds

Every stage is a gate word `schwingnet-anomaly-<stage>`, one job through hpcworker's job submit with its class, sent once its code has merged and the stage before looks sane. Only `select` is built; the others are refused by the gate until their pull requests land.

1. **select (batch, built).** Scores the finder again on the grid's copy of the VerSe screen, noting it if that copy differs from the frozen one, and writes the selection to the lab volume, counts and digests only in the report.
   - Truth order: a read, then two labellers; never one. four_lumbar from reads only.
   - Normal counts are the subtypes none, ordinary, castellvi_I_II, sacralised_L5_fused and lumbar_rib with both junctions in the field.
   - Paired real-frame sources (cobra2026, carmlspine, deepfluoro, geneva, spinesac, ljubljana) are test-only.
   - Normals are drawn by the holdout's rank until variants are 30 percent of the training CTs, by the choice of CTs and never by duplication (chapter 14), split over the collections in proportion to their eligible normal counts. Which collections were harvested at all was the anomaly-harvest directive's ranking by n times P(junction countable) times prevalence (2026-09-23, symphony-template topic memory).
   - Each training row carries its cross-validation fold, where it has one.
   - The local trial on the committed registry, with no harvest rows: 400 training CTs at 30.0 percent variants (112 L6, 7 T13, 1 four-lumbar), 114 test-only paired CTs, a pack bound of 96 GiB at 192 MiB a crop. The grid adds the harvest collections' rows.
2. **timing (gpu, built).** SPINEPS on ten paired CTs that lack it, as chapter 21 asks a timing run before a production array (rule 14), one GPU job with the resources slurm/spineps_cases.sh asked (8 CPUs, 64 GB, four hours), sent once select's report ended in exit 0.
   - The inventory first (tools/anomaly_timing.py inventory): for each test-only set, where the records say its CTs and masks lie. COBRA2026 under cobra2026/cases with NIfTIs where the LSTV screen or the Varian export left them and named masks under cobra2026/lstv/seg, data/spineps/cobra_varian and the harvest collections; C-ArmLSpine by carmlspine/cases.csv with masks under carmlspine/spineps; DeepFluoro by the realxray export's cases.csv where its ct stage ran, else its H5 and vendor DICOM, which need an export; LUMOS by what the fetch left. A mask counts only where VERIDAH named it: the old Elekta harvest under cobra2026/seg/spineps carries raw instance ids and is reported as lacking. The report tables the counts per set and per store; no case id or path leaves the grid.
   - The ten are drawn by rank (a salted sha256 of set and case, as the holdout ranks a person) among the CTs that lack a named mask and already have a NIfTI, shared over the sets by largest remainder of how many each lacks; what lacks a NIfTI is counted for the production array's request, and LUMOS is never timed until #207 proves its pairing.
   - Step 0 is chapter 21's rule 8, the GPU self-test: nvidia-smi's name and compute capability, and a card of capability 10 or above (Blackwell: ymh3 and ymh4 at sm_120) is left with exit 4 before a CT is staged, since the spineps environment's torch 2.6 cu124 build has no kernels for it. The gate reads exit 4 as a stage that spent nothing and queues it again at the same commit on the next send, its report kept under the job's number; a failure at any other step is queued again only once a fix has moved the checkout, as a benchmark is.
   - SPINEPS runs as it always has on the grid: the spineps conda environment, the CT models under ~/spineps_models, each CT staged alone under /dev/shm, the masks harvested to the lab volume under anomaly/timing/spineps/<set>/, the runner's log, which names cases, beside them and never in the report.
   - The estimate closes the report: seconds per CT (median, least, most), the CTs still lacking a named mask per set, the hours one GPU would take at the median and the array that keeps each task under eight hours. The production array is not approved and is asked once, as a decision card, with that number.
3. **pack (batch).** fxr-dataset pack in FleXray's ct-seg preprocessing (a 512 by 512 by 256 crop, HU clipped to -1000 to 2000, float16), shared with items 7 and 8 so no second pack runs.
   - VerSe and CTSpinoPelvic1K are packed with their release masks. A CT with SPINEPS masks only has its bodies renamed from the agreed column, counted from the sacrum, and passes the spineps_ids.py guard; raw ids are never mapped by a spec.
   - Each mask is rewritten into contiguous ids with canonical names (0 background, vertebra_c1 to vertebra_t13, vertebra_l1 to vertebra_l6, sacrum) before packing, since fxr-render reads the pack's stored_labels and a label missing from the model's list renders as background with no warning. The protocol and model label list naming vertebra_l6 and vertebra_t13 sit under protocol.config_root.
   - The list runs `check`, and G3's validation and test transitional persons (spine-program 02_transitional_naming_truth) are left out of the training list.
   - A person-disjoint validation split drawn from the selection is frozen in this stage's pull request; it picks the fine-tune's checkpoint, and the holdout never picks an epoch.
   - The pull request states the pack's size and admits it against the oschome quota under the size-rule lock, recorded in meta/SIZE, as gate.sh's bank word does.
4. **render (gpu).** fxr-render with FleXray's MOOSE profile for the training renders. The holdout's test package is rendered with attenuation_cfg.prob=0 and fixed frontal and lateral presets whose field holds both junctions, since the random profile's orbit and centre need not show the junction that decides the call. Sizes are stated and admitted as for the pack.
5. **figure (gpu).** FleXray as released on the holdout's test package, and the counting figure of section 6. Does FleXray's output reveal the variant? It has no L6 or T13 channel and was trained with L6 as background, so the record predicts a missed body. Item 9's panorama job scores FleXray on whole rendered spines of its own sets; this job scores the holdout package and draws the figure, and reads item 9's output where it has already run on the same renders.
6. **tune (gpu).** FleXray from its released bundle with its 61 output rows copied row by row into a head of 63, the two new rows L6 and T13.
   - The row-wise copy is item 12's, a pull request in OpenSpineConsortium/FleXray installed on the grid at its commit in place of the flexray==1.0.2 pin; or a SchwingNet tool that writes a local 63-channel bundle (weights, model config and label_schema.json in the extended order), loaded with --init-from and no --replace-head. fxr-train itself offers only a strict copy or --replace-head, which discards the whole head.
   - The config: dataloader.proportions holds the new pack and real frames with a few level masks (paired sets, non-test persons), both on the partial_labeled_seg route, since a pack with vertebra labels only, routed as standard_seg, trains every other channel as background, and chapters 14 and 16 found renders alone lost 25.6 anomalous points against renders and films mixed in every batch. base.yml's eleven absent sets are dropped, since DatasetRoutedLoss refuses a configured set with no route.
   - The pull request states epochs times iterations, --time and an estimate, and runs --no-requeue or resumes with fxr-train --resume.
   - **The cross-validation, four more fine-tunes** (words tune_f1 to tune_f4), the same recipe less the fold's persons, each sent only once the main fine-tune and its eval look sane.
7. **eval (gpu).** The fine-tuned model is scored on:
   - the holdout's test package: per-body naming, and per-spine sensitivity and specificity for the variant, each with "lineage unresolved" until item 6;
   - C-ArmLSpine's transitional cases case42, case121 and case136 on real frames, reported as agreement with one labeller's read, never as correctness;
   - the 1,627 truth boxes FleXray was first scored on, so the fine-tune's cost on ordinary spines is seen;
   - the counting line with the fine-tuned names in place of the released ones, a research measurement reported apart from SchwingNet's numbers.
   
   **The folds' evals** (words eval_f1 to eval_f4) score each fold's fine-tune on its own fold's L6 spines, and the L6 sensitivity is reported pooled over the four folds and the holdout, 83 spines, and per fold.

   It needs item 12's checkpoint-to-bundle exporter, or a loader of last.pt's EMA state into fxr.models.UNet with the extended label list, and T13 between T12 and L1 in tools/bench_public.py's LEVEL_ORDER, which raises ValueError on vertebra_t13 today.

## 6. The counting figure on a real anomalous spine

The owner asked on 2026-10-25 at 21:11 UTC: "no i want the stitched fields figure to be a visualization based on a real example for demonstrating how the counting algorithm can score 100% even on anomalous spines by error correction as long as it detects all the vertebra".

The real anomalous spines are only on the grid. This container is refused by VerSe's hosts (s3.bonescreen.de and osf.io, both 403 at the proxy), so the figure is drawn in stage 5's job, on four held spines: one T13, one L6, the four-lumbar verse549 and one normal, each chosen among the held spines of its kind whose CT covers C2 to the sacrum. Counted from the sacrum alone, every body above an L6 is one level off from the readers' names and T13 needs the whole thoracic column, so the fixed-end rule needs both ends in view. Where no held spine of a kind covers C2, the panel uses the lowest rib as the second anchor and says so.

Each figure spine gets one whole-column lateral render from its uncropped CT, made as spinesurg-ct-nnunet's tools/sweep_map.py makes it, and the fields are cut from it as sweep_map.py does. fxr-render on the 512 by 512 by 256 crops cannot show a whole column. For each spine, three panels, in the layout of the stitched fluoroscopy figures:

- **The round fields,** a to f, 140 mm each, stepped from the sacrum to C2 with two bodies of overlap (chapter 34's optimum). Every body's box is drawn from the CT mask's projection, which is what "detects all the vertebrae" means here. FleXray's own name for each body is written beside it, in red where it is wrong.
- **The stitched panorama,** numbered from the anchor by the chain.
- **The render with the readers' names,** the variant marked.

Under each spine, two scores: FleXray's per-frame names against truth, and the count against truth. The count states its convention (sacrum 0) and is scored by the fixed-end rule, with "ordinal reported, name withheld" on a mismatched column counted apart from a correct name.

Error correction is shown first by the count itself: it consumes box positions and never reads a class (chapter 10), so a wrong name in a frame does not move it. That is the claim the figure tests, and it prints what it finds.

src/schwingnet/chain.py's decoder is a second panel only where its prior exists without the holdout. decode takes bodies with a position, a height and a posterior over level names, a ChainPrior, a weight and a margin, and returns labels, the chosen column, a score, a margin and an abstain flag. Each body's posterior would be FleXray's per-channel coverage of its box (bench_public.py's shares), normalised over the level names, never one-hot names, which cost about 13.8 nats a change. The prior is tools/chain_stats.py's fit, built and never run, which reads the T13 and L6 spacing from the very CTs that show them and has no option to leave the holdout out; the weight and margin are chosen on validation frames only. None of that is among the seven jobs, so unless it has run without the holdout by stage 5, the figure leaves the decoder out and says so.

The PNG stays on the lab volume, and only the job's text summary comes back through the gate. No grid job has reached Weights and Biases yet: the grid has no W&B key until the owner adds WANDB_API_KEY with grid-accounts.yml's key action, and a compute node has not been shown to reach api.wandb.ai. Stage 5's pull request settles how the image comes back.

## 7. The counts

| Stage | Word | Fetches | CPU jobs | GPU jobs | Against the #391 plan |
| --- | --- | --- | --- | --- | --- |
| 1 Select and score | select | 0 | 1 | 0 | new |
| 2 SPINEPS timing on ten paired CTs | timing | 0 | 0 | 1 | new; the array is asked later with its number |
| 3 Pack | pack | 0 | 1 | 0 | item 7's pack, shared with item 8 |
| 4 Render | render | 0 | 0 | 1 | item 8's render |
| 5 FleXray as released, and the figure | figure | 0 | 0 | 1 | new; reads item 9's output where it has run |
| 6 Fine-tune | tune | 0 | 0 | 1 | item 14's, brought forward on the owner's Go |
| 7 Evaluate | eval | 0 | 0 | 1 | new |
| 6b Cross-validation fine-tunes | tune_f1 to tune_f4 | 0 | 0 | 4 | new, the owner's yes of 22:30 UTC |
| 7b Their evals | eval_f1 to eval_f4 | 0 | 0 | 4 | new, the owner's yes of 22:30 UTC |
| **Total** | | **0** | **2** | **13** | the owner's Go of 21:22 UTC and yes of 22:30 UTC |

No fetch is needed for these fifteen. SPINEPS and its weights are on the grid, and FleXray's released bundle is there from the public benchmark (bench flexray_carmlspine). Item 6's fetch and census, which resolves the lineage, is the #391 plan's own and is not counted here.

The fine-tune's weights inherit FleXray's CC BY-NC 4.0, and VerSe is CC BY-SA 4.0 in the registry. The #391 plan made item 14 wait on item 15; the owner's Go counts it now as research use. Item 15, the owner's licence decision, still decides whether those weights or their names reach any SchwingNet network, the demo or a reported number, and it never blocks the audit.

Two counts another thread handed to this plan, with the owner's word to do what is recommended:

- **The six 20-epoch trials** (grid/sweeps/trials.json, word schwingnet-sweep-trials). Not sent, since the route does not need SchwingNet's own trained baseline.
- **The scaling study, SchwingNet #385.** Kept as its own item, with fxr-render as one arm, after stage 4 shows the render path works.

## 8. What each stage's pull request brings

- **select (this pull request):** the holdout, the CTSpinoPelvic1K normals and the four folds, with the hashes of the three records they were drawn from, tools/anomaly_route.py (freeze, score, select, check), grid/anomaly.sbatch, the gate word, and the pass-through in hpcworker's grid gate (hpcworker #49) and in symphony-template's grid-accounts (symphony-template #491).
- **timing:** tools/anomaly_timing.py (the GPU verdict, the inventory, the pick and the estimate), the timing branch of grid/anomaly.sbatch, the gate's class, job options and exit-4 rule for the stage, and its tests.
- **pack:** the relabel to contiguous canonical ids, the protocol and model label list with L6 and T13, the validation split, the G3 exclusion, the size admission.
- **render:** the training and test presets, the size admission.
- **figure:** the whole-column renderer from sweep_map.py, the figure tool, and the image's way back.
- **tune:** the row-wise head copy (item 12, a FleXray fork pull request, or the local bundle writer), the config, the length, and the fold words, which drop a fold's persons from the training list.
- **eval:** the exporter or loader, LEVEL_ORDER with T13, the scoring, and the pooled cross-validation.
