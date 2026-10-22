# Handoff: SchwingNet, CTSpinoPelvic1K and the imaging programme

Oct 8, 2026 · @greg

This is the shareable summary of the handoff being written into `spinesurg-ct-nnunet/HANDOFF/`, for a new student and for a fresh Claude project: what the work is, where every result lives, how to regenerate it, what each manuscript still needs, how leakage is checked, and the context exported from this session.

## The programme in plain words

One question runs through everything: can a vertebral level be named from what a surgeon already has in the room, an operating-room C-arm exposure or a plain film, without counting down from C2 and without a registered preoperative scan. Three projects answer it from different sides, and a fourth makes the grid usable by students.

| Project | What it is | Where | Public |
| --- | --- | --- | --- |
| CTSpinoPelvic1K | 802 abdominopelvic CTs with per-level vertebrae, ribs, sacrum, hips and femora, released on Zenodo and Hugging Face, with a dataset article and its spinopelvic and morphometric measurements | `CTSpinoPelvic1K-1` (paper/mpda, CAMERA\_READY\_NEURIPS, scripts), Zenodo 10.5281/zenodo.22139642 | yes |
| SchwingNet | The level-identification network and the C-arm programme: render banks from CT, plain-film crop banks, the real C-arm sets with 3-D truth, device calibration, the RSNA AI manuscript, the anomaly harvest for transitional spines | `spinesurg-ct-nnunet` (private; SchwingNet/, docs/, tools/, slurm/) | no; the level-identification code is never pushed public |
| OpenSpineToolkit | The measurement library the morphometrics use (label-scheme detection, spinopelvic estimators, the PACS demo) | `OpenSpineToolkit` | yes |
| Beethoven | The browser extension and cluster tool through which students reach the grid, start a Claude Code worker there and read the data | `ashley-bridge` (OpenSpineConsortium/beethoven) | private repository, store listing in progress |
| The data platform | The manifest of 212 sources, the re-acquisition driver, the Ceph layout, the migration and the index database | `spinesurg-ct-nnunet/data_platform` | part of the private repository |

The grid is go2432@grid.wayne.edu: home under `/wsu/home/go/go24/go2432`, data on the Ceph volume under `/rs/rs_grp_oschome/go2432/data`, training logs under `model_night/`. The handoff folder `spinesurg-ct-nnunet/HANDOFF/` holds the full versions of every section below: README (start here), RESULTS\_CATALOG, RECIPES, DATASET\_USAGE, LEAKAGE, MANUSCRIPTS, INFRASTRUCTURE, CONTEXT\_EXPORT with the exported notes, GLOSSARY and OPEN\_QUESTIONS.

## What the SchwingNet model uses today, and what it does not

"The SchwingNet model" is five pieces: a film-trained keypoint body detector (detector\_v5z\_final), a real-frame vertebra and sacrum detector (rx\_lodo\_carmlspine\_1024), the allspine\_v9 level encoder, its recurrent head, and, for the fine-tuned numbers only, five C-ArmLSpine fold models re-initialised from v9. The full answer, dataset by dataset with its file, is HANDOFF/DATASET\_USAGE.md.

| Piece | Trained on | Used for |
| --- | --- | --- |
| Body detector (YOLO11m-pose) | zoomed film windows from CSXA, BUU AP and lateral, and the 543 annotated NHANES films: 12,709 films, with no written reason for the other 26,996 held films | the naming boxes |
| Vertebra and sacrum detector (YOLO11m) | 3,094 real frames: COBRA Elekta train and validation (118 cases) and DeepFluoro (5 specimens), initialised from a TotalSegmentator-render detector | the sacrum anchor for counting; held-out detection on C-ArmLSpine |
| Level encoder (ResNet-18, 27 classes) | the allspine\_v9 bank: CSXA 4,963 films, BUU-LSPINE laterals 3,603, the 543 NHANES films, and renders of CTSpinoPelvic1K, VerSe 19 and 20 and TotalSegmentator v2 | zero-shot naming |
| Recurrent head (BiGRU) | the same v9 bank, mixed runs of 2 to 9 bodies | sequence naming |
| C-ArmLSpine fold models | the shipped fold banks, fine-tuned from the v9 encoder | the case-grouped and day-grouped cross-validation |
| Count and coupling | no learned parameters | the ordinal from the detected sacrum; the stop signal |

**Not in the level bank at all:** VinDr-SpineXR (0 of 10,466), the 16,531 unannotated NHANES films, the 3,600 BUU AP films, AASCE, Mendeley, the IEEE lateral set, Spinal-AI2024, FluoroCap, the TotalSegmentator v3 renders, the RSNA 2022 cervical CT archive (203 GB, never unpacked), RibFrac, CTSpine1K, and every real C-arm frame.

**The defect to decide on.** The C-ArmLSpine fold models behind the fine-tuned naming numbers still train on 2,632 VinDr crops and 2,100 FluoroCap crops per fold bank, plus both NHANES copies, because the v9-initialised fold models reuse fold banks built from allspine\_v7. That contradicts the directive that FluoroCap is out of every training set, and it leaves VinDr, a PhysioNet data-use agreement, outside the IRB determination. Fold models without VinDr or FluoroCap already exist: the 250 Figure 5b name\_fill cells were fine-tuned from the v9 encoder on the v9 base sample.

**Real C-arm data is barely used.** Of COBRA2026's 692 fetched cases only 145 Elekta cases are in any frame bank and 0 of 225 Varian; 2,293 DeepFluoro vendor frames, the second C-ArmLSpine sweep, the Ljubljana frames and all SpineSAC frames train or score nothing. Nothing after 2026-09-27 changed the banks or models as far as any file shows.

## Results and where they live

HANDOFF/RESULTS\_CATALOG.md holds every result found on disk on 2026-10-08, one row each: the claim with its number, the file that holds it, the model, bank, split and truth, the tool and grid job, a status word and the figure or table it feeds. Where any other file or memory note differs, the catalog wins. Its status words are CURRENT, CURRENT-SEL (measured on the split that chose the checkpoint), HELD-OUT NOT QUOTED, SUPERSEDED, DISPUTED, REFUTED, RECORD ONLY, NOT RECORDED and OPEN, and each row carries the rigor marks of the 2026-09-22 audit (threshold-dependent, selective reporting, wrong bank, leaked, selection split, one seed, automatic truth, derived, wording).

| Part | What it catalogs | The numbers a newcomer meets first |
| --- | --- | --- |
| A. SchwingNet, paper 1 | what the encoder learned; zero-shot and fine-tuned naming on C-ArmLSpine; counting from the sacrum; the coupling and stop signal; held-out detection; the detection learning curve and its plateau; naming against training persons by view; the film N-curve and render ablation; angle and coverage; device cards; the corpus manifold; transitional persons and the sample-size argument; study population; data-integrity numbers | 97.4 % of bodies named on a whole lateral frame and 74.8 % with one body in view; the count alone names 97.0 % of anchored bodies and the coupling adds 1.2 points; held-out-device detection recall 80.5 %; same-device plateau about 84 %; renders raise film naming 6 to 22 points at 5 to 25 persons; 0 verified real-frame transitional test persons against 35 needed |
| B. Paper 2 | SchwingNet against registration-assisted surgeons (LevelCheck): the frozen comparator, the open gate, the cancelled blinded gate | the comparator 97.6 % cannot be exceeded at any reachable n; the open gate scored names only because of a path bug |
| C. The programme before SchwingNet | plain-film level models; the 2026-09-17 fraction sweep; the sweep, chain and confirmation line; DeepFluoro and devices; CT segmentation ablations | the 99.02 % and 99 % selective-accuracy numbers come from the leaked allspine\_v2 bank and are record only |
| D. The anomaly scan | the transitional harvest, the two labellers, the registry, the ruleclass super-detector run over 21,622 CTs | registry L6 146 and T13 14; the one-labeller COBRA screen is not trusted (precision 10 of 24 on L6, 0 of 52 on T13) |
| E. Power | every power and sample-size calculation on disk | 35 error-free at-risk persons for the 90 % bound; 22 carriers for 85 % sensitivity; 19 for paper 2's H1; every planning value assumed 95 to 99 % that no measurement supports |
| F. CTSpinoPelvic1K | building the dataset; the spinopelvic and per-level measurements; NeurIPS paper 3474 | 802 records; T12 against L1 AUC 0.990; the two per-level defects caught by spread, not medians; the v11 sacral slope 36.6 against Veilleux 36.5 |
| G. OpenSpineToolkit | the measurement library and related tools | the canal-closing regression at ostk 1b7005c inflates two measures by 10 to 17 mm on about 1 in 7 vertebrae |

Three numbers in circulation must not be quoted: anything from allspine\_v2, v6 or v7 (NHANES pooled twice across the split), the anchor\_drr split (301 of 801 persons on both sides) and vindrps (a 77.8 % validation leak). The catalog names the clean replacement beside each.

## Recipes: regenerating the named deliverables

HANDOFF/RECIPES.md gives every command, copied from its script header or result document, for the scaling plots, the film N-curve, the anomaly scan, the power calculations, the DRR banks, the device calibration, the C-ArmLSpine experiment, the benchmark suite, the CTSpinoPelvic1K measurements and figures, and the leakage checks. Read its section 0 first: nothing computes on the login node, code ships by commit through `git archive | ssh tar` because the grid can no longer fetch the private repository, and resume is not reproduce (the chains write to fixed output folders and come back unchanged unless the folder is moved aside).

| Deliverable | How it is regenerated | Checks that prove it worked |
| --- | --- | --- |
| The scaling plots (Figure 5) | from result files already on disk, in minutes: the figure script, then the manifest check that fails on a pending key or a bare numeral, then the limits check (words, abstract, captions at or under 60 words, references, the banned word); TeX compiles only on the grid | the figure record lists every drawn number with its file and key; the inputs are hashed into power.json |
| Panel b, C-arm naming against training persons | the name\_fill chain, fine-tuned from the v9 encoder on the v9 base sample without VinDr or FluoroCap, 250 cells | every cell passes the evaluation gate with held out true |
| Panel c, same-device detection against real frames | the det\_fill chain and the plateau diagnosis | the plateau about 84 % is the truth denominator: 95.6 % on repaired boxes |
| Accuracy against the number of samples (the film N-curve) | a render-only encoder (the v9 bank minus every film row), scored on the v9 validation persons of each corpus; cells at N of 0, 5, 10, 25, 50, 100, 200 and all per corpus, seeds 0 to 2 at N of 25 or fewer; a four-job chain (prep, encoder, 48-cell array, collect) with afterany dependencies, about 18 GPU-minutes a cell | every cell reads HELD OUT; NHANES all 92.7 %, BUU all 96.9 %, CSXA all 99.8 %; the render ablation found renders help in six cells and hurt in one |
| The anomaly scan | in dependency order: the anomaly manifest (pass the v9 bank, the default bank was deleted), the inventory job, the subtypes script, the frozen G3 person split (never rerun in place), the harvest streams per source, the registry, the rare-class renders, the acquisition screens, the census table (its counts are one high per collection), the ruleclass arms on the grid, and the rules, review tree and report only after the pre-registration freeze | the truth tiers: read above two-labeller above single-labeller above morphology-only; a segmenter call is never promoted without a read; a CT that cannot count is no\_count, never ordinary |
| The power calculations | the figure script writes the Wilson bounds and the n needed at 0, 1, 2 and 5 errors; an independent pure-arithmetic check reproduces 35 and 22, 53 and 34, 69 and 45, 113 and 74 and matched every printed value on 2026-10-08; the two statistical recomputation scripts; the frozen exact-binomial code of the LevelCheck model; the two-proportion planner (its top-level help crashes, the subcommands work) | the method to copy for any new analysis: write the rule and its success criterion, hash the document, stamp every output row with the hash, and treat any number produced before the freeze as calibration |
| The DRR banks and crop banks | the render scripts and the bank builder; the allspine\_v9 builder deletes the folder that holds the encoder, so it is a record of how the bank was built, never to rerun in place | per-source counts; the person keys file |
| The C-ArmLSpine level experiment | data preparation scripts in order, then the case-grouped and day-grouped cross-validation arrays | the series UID and pixel-spacing traps are listed |
| CTSpinoPelvic1K measurements and figures | the extraction scripts and figure builders; the level atlas script rewrites its CSV, so copy it aside first | the dataset article's reprint build is the only page count that matters |
| The leakage checks | the gate, the leak checker and the patient-key tests | see the leakage section |

## Manuscripts, abstracts, decks and disclosures

HANDOFF/MANUSCRIPTS.md is for Greg and the Claude project only, because it carries the disclosure and technology-transfer record. It lists every written work found on 2026-10-08 with its venue, paths, state, what is finished, what must be redone, the claims map, the binding style rules, twenty contradictions between documents, and one order of work. The state was frozen at the last manuscript commits of 2026-09-27; no commit touched a manuscript between 2026-09-28 and 2026-10-07.

| Work | Venue | State as recorded |
| --- | --- | --- |
| SchwingNet, paper 1 | Radiology: Artificial Intelligence | complete in review and camera-ready copies; one placeholder (the VinDr determination number); supplement 13 pages against a 12-page cap; Word packets stale; held from submission pending the technology-transfer office |
| Paper 2, SchwingNet against registration-assisted surgeons (LevelCheck) | not chosen | comparator frozen; blinded gate cancelled 2026-09-27; the open gate scored names only because of a path bug; needs human reads of transitional test persons |
| Older C-arm drafts | Radiology: AI, each in turn | superseded; sources to lift from; two disclose the undisclosed sweep |
| The QI paper, "The Universal Protocol with a level in it" | The Joint Commission Journal on Quality and Patient Safety | 9-page draft, builds, not submitted; discloses invention aspects, stays private |
| CTSpinoPelvic1K dataset article | Medical Physics, Dataset and Software Article | submitted and returned twice for format; the third packet built 2026-09-25; upload not recorded; arXiv public |
| "Not All Spines Are Created Equal" (NeurIPS 2026, submission 3474) | Evaluations and Datasets Track | accepted as a poster on 24 Sep 2026; the committed camera-ready is 21 pages; the uncommitted working copy is 31 pages with 134 pending slots whose jobs were cancelled |
| CTSpinoPelvic1K benchmark paper | MLHC 2026 | rejected |
| CT one-shot and numbered-rib paper; NeurIPS revision draft; BIBM wrap-up and XRSpinoPelvic1K | Radiology: AI; NeurIPS; IEEE BIBM | drafts with open items; submission not recorded |
| The iliac crest clinical paper | Spine Surgery and Related Research | complete draft with numbers; first author unassigned; computed before v11 |
| Medical-education study | Cureus | published 14 Jul 2026; a JEEHP submission would duplicate it |
| CNS 2026 (12 abstracts, the mini-oral and its deck) | CNS Annual Meeting, Washington DC, 31 Oct to 4 Nov 2026 | accepted; only the public v12 deck is disclosure-safe |
| AACA Tech Fair | 43rd AACA meeting, 13 Jun 2026 | presented |
| Invention disclosure and provisional package | WSU technology commercialization | disclosure submitted 2026-09-25; provisional filing not recorded |
| Fluoroscopy and C-arm data requests | 14 cine sources, SX-Stitch, Balgrist | drafted; none sent |
| NIH F30 year-4 progress report | NIH | sent July 2026 |

The binding rules for anything that leaves: never the banned word; no fractional versions; captions at or under 60 words; matrix tables in black; the Medical Physics figure rules and no abstract in a Dataset and Software article; the Radiology: AI limits (3,000 words, 250-word abstract, 6 figures, 4 tables, 35 references, a 12-page supplement); never state the commercial goal or name the product; never re-add level-identification text to a public repository; the affiliation is General Surgery; every printed number enters through a manifest key, never typed.

The flags a successor must act on first: the supplement page count; the atlas model cards and two markdown tables still carry superseded numbers; the recurrent-head result is attributed to the wrong bank in two scripts; the supplement says FluoroCap is refused by the guard while the fold banks still hold FluoroCap and VinDr crops; the older draft gives the affiliation as Neurosurgery; paper 2's reference-standard scoring must be fixed before it scores anything; and the pending VinDr determination number.

## How data leakage is checked

**The rule** (Greg, 2026-09-23). An evaluation item is held out for a checkpoint only if its patient key is in neither the training set nor the validation set of that checkpoint or of any ancestor it was initialised from. A derived image (a render, a styled frame, a crop) inherits the person of its source CT. Only public ImageNet and COCO weights are exempt as ancestors, and only when declared. Unknown is not clean: an unkeyed item, an unresolved lineage link or a check that did not run counts as a failure. An item is one acquisition, not a file; splits are enforced on the patient key and duplicates on the item key; validation is seen; identity comes from metadata first and the file name last.

| Check | Tests | Run in the G3 split? |
| --- | --- | --- |
| CHK-1 | item disjointness: no acquisition on two sides | yes |
| CHK-2 | alias closure: one item under two names counted once (the NHANES failure) | yes |
| CHK-3 | patient closure, including derived items: a person and all their renders on one side | yes |
| CHK-4 | derivation closure: parent and child on one side; 8,082 training renders sit under the poses of validation, test or held real subjects, 2,720 of them under test poses | yes, as a warning |
| CHK-5 | a held-out device or corpus is held out whole | yes |
| CHK-6 | near-duplicates across splits by perceptual hash and correlation | not run |
| CHK-7 | undeclared aliases by store or pixel key | not run |
| CHK-8 | orphans and coverage (17 unkeyed AASCE coronal films) | yes, as a warning |
| CHK-9 | evaluation against selection and lineage for every quoted number, 563 rows | yes |

**The two historical leaks.** NHANES II entered the banks twice under two names (films\_drr and nhanes\_drr split independently), so 48 of 54 validation persons of the older banks were also in training; found 2026-09-22. CTSpinoPelvic1K entered under two names (its renders and the anchor\_drr bank), putting 301 of 801 persons on both sides. The consequences: allspine v2, v6 and v7, anchor\_drr and vindrps are leaked families, and every number from them is record only, including the 99.02 % shortcut-free film number and the 99 % selective-accuracy claim. The fix was the G3 person-disjoint split applied 2026-09-23 with a leak audit pass, and the patient-key module that refuses names it cannot key.

**How to run the checks.** The patient-key tests, the leak-check fixtures, the evaluation-gate tests and CHK-9 through its Slurm wrapper; the commands are in RECIPES.md section 10 and LEAKAGE.md section 6. On 2026-10-08 the evaluation-gate tests passed 58, the patient-key and statistics tests passed, and the leak-check suite fails on one stale Geneva fixture.

**What remains open.** The full content-hash chain (CHK-6 and CHK-7) has never been run on the real corpus. The C-ArmLSpine fold banks behind the fine-tuned table still hold VinDr, FluoroCap and both NHANES copies. 92 of 97 transitional validation and test persons sit in the current encoder's training lineage, so any transitional number on the current encoder is not held out. The person counts behind AASCE's index groups, CSXA's one-image-one-patient assumption and VinDr studies per patient are unverified, and every leak check is only as good as these keys.

## Operating the work

HANDOFF/INFRASTRUCTURE.md covers the repositories, the grid, how a job is written and submitted, the data platform, the model registry, environments, the toolkit, the tools a student touches first, the standing preferences, the lab recipe and board, and the laptop traps. Credential names and locations sit in GREG\_ONLY, never contents. The ten rules that bind all work, from README section 5:

1. Words and style: never the banned word for where data came from; no fractional versions; captions at or under 60 words; matrix tables in black; the affiliation is General Surgery; Ashley Schehr is a person.
2. Every number carries its file; what no file records is written "not recorded".
3. Check outside the computation: published values, an independent implementation, the distribution's spread, a rendered mask. An identity check cannot catch a shared bad landmark.
4. Labels and orientation: two label schemes exist and mixing them does not raise; call `labels_for`, never a fixed map; identifier 29 is retired in v11; zero-pad case ids; canonicalise to analyse, never reorient when writing.
5. Held out means the person was never seen, by the checkpoint or any ancestor; every quoted score goes through the evaluation gate; never quote from the leaked banks.
6. Pre-register, then score; manuscript numbers enter through manifest keys, never typed.
7. The grid's login node runs nothing: every computation is an sbatch job; use the submit-directory flag, afterany not afterok, /dev/shm for IPC, Ceph for large outputs; write grid bash for bash 4.2.
8. What stays private: SchwingNet and all level-identification code, text, figures and weights, FluoroCap, the spinesurg-ct-nnunet and XRSpinoPelvic1K repositories; run the disclosure audit before any talk or submission; only the public v12 deck for the CNS talk.
9. Data directives: use all of a public dataset; every truncation fixed or justified in writing; a leaked initialisation is fixed by retraining, never disclosed as a caveat; FluoroCap is out of training; the IRB umbrella covers only public de-identified data downloadable without an agreement.
10. Git, network and credentials: CTSpinoPelvic1K commits directly to master and pushes to both remotes; network goes through WSL; tokens are read from files, never echoed; scripts are written as files and run by path.

**Where things stand on 2026-10-08.** Paper 1 is complete and held; paper 2 needs human reads; the dataset article's third packet was built and its upload is not recorded; the NeurIPS paper is accepted with its camera-ready split between a 21-page committed copy and a 31-page working copy; the anomaly scan's pre-registration is an unsigned draft and the ruleclass outcome after 2026-09-27 is not recorded; the data migration to Ceph is in progress with batches B00 to B03, B06, B08 and B14 cut over; the person-level gate is in place and the content-hash chain has never run.

**A student's first week.** Day 1: read the README, both CLAUDE.md files and the lab recipe; request a grid account; install Beethoven. Day 2: the data platform README and manifest, then DATASET\_USAGE and LEAKAGE, until you can say which bank trained the encoder and why VinDr is a problem. Day 3: run the laptop self-tests and re-derive the power numbers with the pure-arithmetic check. Day 4: read the evaluation-gate leak report and the catalog's parts A and D; rebuild one figure from committed files without touching the committed copies. Day 5: with Greg, pick one item from OPEN\_QUESTIONS or the board and write its pre-registration before running anything. Questions only Greg can answer in week one: was SchwingNet uploaded; was the Medical Physics packet uploaded and under what number; the VinDr determination number; whether the NeurIPS deadline is past; whether he wants the ratio sweep, the per-level supplement table and seeds above N of 25; and whether the reader split of this folder is confirmed.

## Context exported from this session

HANDOFF/context/ holds 141 of the session's memory notes copied with their original bytes, refreshed on 2026-10-08 at 16:39 by the builder script that also applies the redactions: five notes and the index moved to GREG\_ONLY/context/ (the commercial stance, the disclosure-scrub state, the credential-location notes), three notes redacted of personal or contact data, the six Beethoven notes copied to GREG\_ONLY/context\_beethoven/, and the U251 and history-only notes left out. context/INDEX.md lists every copied note with a one-line digest, its project, and a status that carries the day's verification: LEAKED or SUPERSEDED where a note's numbers were measured on a leaked bank or replaced, naming the file and number that replace them. HANDOFF/CONTEXT\_EXPORT.md digests all 165 notes, says what was copied where, and lists the context that lives only in the session or outside the repositories.

**What a fresh Claude project should load.** README.md, INFRASTRUCTURE.md and context/INDEX.md as standing context, not the archived MEMORY.md (its one-line summaries carry leaked numbers and point at notes that were not copied), plus GREG\_ONLY/PRIVATE\_STATE.md for Greg's own project. The two repository CLAUDE.md files remain the working context of their repositories. Open RESULTS\_CATALOG.md for any number, RECIPES.md to regenerate anything, and RESEARCH\_DIRECTIONS.md for what to do next. Before any handover, re-run the two builder scripts (refresh the copies, then rebuild the index), and never re-run the superseded copy scripts, which would undo the moves and the redactions.

**Memory hygiene a successor inherits.** The notes are the orchestrator's own record of decisions, traps and standing preferences, written when they were true; a note that names a file, function or flag is verified before it is relied on. Two notes are already known to be outdated: the film N-curve result note (it says seven of nine cells all help, while the record is six help and one hurt) and the memory index's summaries of the leaked-bank numbers.

**What is on the grid only and was not re-verified.** The interior-window result files, the alphabet-loss failure renders, the decoder rare-penalty sweep, the LSTV flag learning curve, the ruleclass corpus file and the state of the arms after 2026-09-27, the registered status of the v9 encoder, and whether the 2026-09-17 scaling outputs still exist.
