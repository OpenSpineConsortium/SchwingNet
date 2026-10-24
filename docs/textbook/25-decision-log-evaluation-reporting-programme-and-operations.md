# 25 Decision log: evaluation, reporting, programme and operations

Label: schwingnet-internal. This chapter is for the project's members and stays in this private repository; it records decisions and their reasons, names each method only by what it is for, and leaves how any stage works to Part III.

This chapter logs every decision outside data and method: how a number is reported, what happens to the papers, the order of the programme's work, the rules of the grid, the governance the project has settled, and how a new person or Claude Project starts. Each decision carries its date, its owner by role, its status, the reason the record gives and what would reverse it, so a planner can tell a rule that answers a measured incident from a habit nobody has examined. The families are R (reporting), V (papers and venues), P (programme), O (operations), G (governance) and N (onboarding). Method decisions M1 to M23 live only in [chapter 16](16-method-decisions-and-what-would-reverse-them.md); data, licence and split decisions are in [chapter 24](24-decision-log-data-licences-and-splits.md). A pull request that changes a decision here should name its number.

## How the log was built

Three sources carry most of the log. The [Handoff: SchwingNet, CTSpinoPelvic1K and the imaging programme](../../artifacts/handoff-schwingnet-ctspinopelvic1k-and-the-imaging-programme-rbcdmf/) of 8 October 2026, canonical for the programme cluster, lists the ten rules that bound all work then. [Research directions from the data holding](../../artifacts/research-directions-from-the-data-holding-kcyckb/), of the same day, sets the order of work. [The Lab Recipe](../../artifacts/the-lab-recipe-1t2gvp/) of 27 September is the runbook where most operating rules first appear, each beside the incident that paid for it. The [spine-program student onboarding](../../artifacts/spine-program-student-onboarding/) of 13 October and the [SchwingNet grid pipeline](../../artifacts/schwingnet-grid-pipeline/) of 21 October carry the later state. The handoff and the research directions restate one results ledger, so they count as one source ([the level-naming contradictions](../../artifacts/_synthesis/contradictions/level-naming-and-counting.md), row 61).

Owners are given by role: the owner, the project's principal investigator; a session, a Claude session working for the owner, whose choice stands until the owner overrules it; the study team of a protocol draft; and the figure inspector. Where an artifact names no owner the log says so. Undated decisions take the date of the artifact that records them ("by 8 Oct"). Status is in effect, done, narrowed (held for less than it first claimed), replaced, or open. Every decision was checked against two later records whose words win where they differ: the owner's words of 20 October in [docs/research/retraining-plan.md](../../docs/research/retraining-plan.md), which make the first model this workflow trains to work version 1 and the reported stack context rather than a baseline, and the shared memory, [docs/memory/MEMORY.md](../../docs/memory/MEMORY.md).

## The log in one table

Each row gives the decision, its date and owner by role, and its status; what would reverse it is in the decision's own section below.

| No. | Decision | Date, owner | Status |
| --- | --- | --- | --- |
| R1 | Accuracy with coverage, never one accuracy | 16 Sep, a session | in effect |
| R2 | Intervals clustered at the case | 22 Sep, a session | in effect, moving to the person |
| R3 | Per source, never pooled | by 8 Oct; 20 Oct, the owner | in effect |
| R4 | Within-one-level as primary | 13 Sep, unowned | narrowed |
| R5 | Nothing from eight transitional spines | 18 Sep, a session | in effect |
| R6 | The catalog wins | by 8 Oct, a session | in effect for the old programme |
| R7 | Manifest keys, never typed; pre-register, then score | 27 Sep, the owner | in effect, gaps open |
| R8 | The failure reported with the result | 22 and 23 Sep | in effect |
| R9 | Random verification samples | undated | in effect |
| R10 | Leaked families as records only | by 8 Oct; 23 Oct, the owner | in effect as revised |
| V1 | Paper 1 held for technology transfer | by 8 Oct, the owner | in effect |
| V2 | Paper 2's blinded gate cancelled | 27 Sep, the owner | done |
| V3 | No JEEHP submission | by 8 Oct, the owner | in effect |
| V4 | Six method figures, results to a supplement | 22 Sep, the owner | in effect |
| V5 | No pooled wrong-level frequency | 16 Sep, a session | in effect |
| V6 | Results on slides only before the provisional | 20 and 21 Oct, the owner | until the filing |
| P1 | The standing determination | 23 Sep, no owner recorded | in effect |
| P2 | Measurement, then human reads, then models | 8 Oct, the owner | narrowed 20 Oct |
| P3 | One miss of 43 for the 85 % bound | 8 Oct, the owner | in effect |
| P4 | No job without the owner's word and number | 20 Oct, the owner | in effect |
| P5 | Version 1 first; what drops first | 20 and 21 Oct, the owner | to the talk |
| O1 | Nothing on the login node | 21 Sep onward, the owner | in effect |
| O2 | afterany, never afterok | 9 Sep incident | departed from in the gate |
| O3 | The requeue partition, now hpcworker's classes | 27 Sep; 21 Oct, the owner | replaced in form |
| O4 | Record every job before cancelling | 27 Sep, the owner | in effect |
| O5 | No polling loop beyond ten minutes | 24 Sep incident | in effect |
| O6 | Status computed, never hand-written | 27 Sep | in effect |
| O7 | Nextflow only for CPU pipelines of three stages | 27 Sep | in effect |
| O8 | No PowerShell, no heredoc for shipping | 13 Oct, the owner | may lapse |
| O9 | A second grid worker waits for the owner | 21 Oct, the owner | in effect |
| O10 | A 5 TB free-space margin | 21 Oct | replaced 23 Oct |
| O11 | Credentials from files of mode 600 | 27 Sep, the owner | in effect |
| G1 | IRB correspondence purged | by 8 Oct | done, one step left |
| G2 | Expedited review, Category 5 | draft, the study team | in effect |
| G3 | No prospective study before detector performance is known | draft, the study team | in effect |
| G4 | coordbench out of the grant | 15 Oct, the owner | in effect |
| G5 | Aggregates only; no public release of the corpus | Oct | in effect |
| N1 | Blank Project fields | 13 Oct, the owner | in effect |
| N2 | Results in the grid archive | 13 Oct, the owner | archive not confirmed |
| N3 | Issue 19 first | 13 Oct, the owner | open |
| N4 | What a fresh Claude project loads | by 8 Oct, a session | in effect for that repository |

## Reporting: how a number may be said

### R1, accuracy with coverage

On 16 September [Overnight: The Honest 99%](../../artifacts/overnight-the-honest-99-kantj8/) changed how the project reports a level model. No published system reaches 99 % on plain radiographs, so a single accuracy at that target would be untrue; the system instead reports a pair, how often it is right on the cases it answers and how many it answers, with the whole risk-coverage curve rather than one flattering operating point. The decision was a session's.

The rule outlived the number that prompted it. The page's headline, 99 % among answered at 35.7 % coverage on held-out renders, came from the allspine v2 family, which the handoff marks leaked; it is a record, not a final value, from [the overnight report](../../artifacts/overnight-the-honest-99-kantj8/). A planner keeps the form and discards the figure. How a coverage pair is computed and bounded is [chapter 18](18-metrics-intervals-and-witness-frames.md)'s; what makes the system decline a frame is method, in [chapter 14](14-transitional-anatomy-two-anchors-disagreement-and-abstention.md). R1 would be reversed by a system that answers every held-out real frame at the stated accuracy, when the pair collapses to one number.

### R2, intervals clustered at the case

[Counting From The Sacrum](../../artifacts/counting-from-the-sacrum/) of 22 September clustered every confidence interval at the case, because frames within a case are not independent; it reports that a naive interval covered the truth 70.8 % of the time, a figure this chapter did not check against its simulation. The owner's plan of 20 October keeps the rule and moves its unit: every naming number carries a Wilson interval on person-keyed n ([docs/research/retraining-plan.md](../../docs/research/retraining-plan.md), section 4). The move matters because a case is not always a person: C-ArmLSpine's records give 149 sessions and 120 distinct subjects without settling which counts ([the programme contradictions](../../artifacts/_synthesis/contradictions/programme-direction-handoffs-and-onboarding.md), row 22). A person table for each source would settle the unit; nothing would reverse the clustering.

### R3, per source and never pooled

The [Vertebra Detector Field Report](../../artifacts/vertebra-detector-field-report-1jljc6/) reports per source and per acquisition, never pooled, because a pooled number hides the generalisation worth measuring. The research directions add that a pooled device number is never quoted without the device-held-out arm beside it, and that the published 0.990 for one thoracolumbar shape test is a ceiling, never the three-dimensional side of parity, since each C-arm is its own domain and the 0.990 is a within-patient number. The owner's plan of 20 October keeps the transitional stratum in its own rows at every version. [Chapter 19](19-what-a-valid-comparison-needs.md) turns R3 into the conditions for comparing two numbers. Nothing argues for reversing it; a pooled figure may only sit beside the per-source ones.

### R4, within-one-level, narrowed

The [Level Context Ladder](../../artifacts/level-context-ladder-xd7eltc/) of 13 September called within-one-level "the honest primary metric for a level-confirmation tool", because at wide context most remaining errors were whole-case shifts of every vertebra by one level. No owner is recorded. Every later record makes the exact level the headline: the handoff's results, the OR ledger and the retraining plan's per-level accuracy. The log records R4 as narrowed: within-one is the right secondary figure wherever whole-case shifts dominate, but the programme's claims are about the exact level. No artifact withdrew R4; the reading is Inferred.

### R5, nothing from eight transitional spines

[Naming Vertebrae Without CT](../../artifacts/naming-vertebrae-without-ct-hjy4vc/) of 18 September quotes no figure from its eight held-out transitional spines, because eight cannot tell 60 % from 95 %. Its superseded twin of the same day, [Vertebral Levels Without CT](../../artifacts/vertebral-levels-without-ct-a4rydj/), alone adds that no rate from the reader study is quoted either, its misnamed frames being a census, not a sample. The research directions turn the rule into counts: 22 carriers for an 85 % sensitivity bound, 35 error-free at-risk persons for 90 %, and below 22 carriers with an exported frame no fluoroscopy transitional sensitivity is claimed and the render number stands alone. On 8 October the verified real-frame transitional test count was zero. Only reaching those counts reverses R5.

### R6 and R7, the catalog, the manifest and the freeze

The handoff's author, a session, decided that where any file differs from the results catalog of 8 October the catalog wins, because it was one record of every result on disk that day, each row with its file, model, split, truth, job and status. That binds the old programme. SchwingNet's own numbers come from run records that stamp the version, the shard list's hash, the commit and the clean-tree flag, and a dirty tree is refused ([docs/research/retraining-plan.md](../../docs/research/retraining-plan.md), section 4). The log's reading, with no conflicting case yet on record, is that for one claim the newer run record wins over the catalog's snapshot.

The owner's rule, in the handoff's ten and in the Lab Recipe, is that every printed number enters through a manifest key and never by typing, and that a study is pre-registered, frozen by its hash and only then scored, with departures in a dated deviations file. Pre-stated rules make a negative result reportable: when one corpus went against the render-ablation rule, that cell went into the manuscript. The recipe also records how far the rule had reached on 27 September: 167 bare numerals in the tables, because the check scanned only the prose, and none of 79 manifest keys beginning with a job id. Whether those gaps closed is not in this chapter's sources. Nothing would reverse R7; only its gaps close.

### R8 and R9, report the failure, sample at random

Counting From The Sacrum decided on 22 September that the naming result and the unsolved detection problem are reported together, because reporting both makes the first credible; the standing determination of the next day says "not at parity" is stated plainly if that is the result (P1); and the recipe's submission checklist reports failed bars as failures. A negative result is a deliverable.

The [Level Verification Bench](../../artifacts/level-verification-bench-mkjxsy/) draws a human check as a random sample within each route with a fixed seed, never a set the model's uncertainty picked, so the accuracy is unbiased; can't-tell marks leave the denominator, and the sample is a measurement, never training data. [Chapter 17](17-benches-and-human-reads.md) holds the benches.

### R10, leaked families as records

The handoff records the owner's decision that numbers from the allspine v2, v6 and v7 families, the anchor_drr split and vindrps are not quoted, since each family leaked; the catalog names a clean replacement beside each. On 23 October the owner revised this for the book: such a number may appear as a record with a direct link to its source and the words that it is not final. Allspine v2's 99.02 % plain-film figure, the owner's example, is a record, not a final value, from [the handoff](../../artifacts/handoff-schwingnet-ctspinopelvic1k-and-the-imaging-programme-rbcdmf/). The held-out rule and the split that fixed the leaks are data decisions, in chapter 24. The [OR Readiness Ledger](../../artifacts/or-readiness-ledger/) of 22 September made three smaller decisions of the same kind: a 100 % sacrum figure on one cadaver set ruled not the method's and sent to a clean retrain, phantom results declared "a sheet to look at, not a number to quote" until projected truth exists, and a held-out detection cell re-scored under one truth convention before any comparison.

## Papers and venues

### V1 and V2, paper 1 held, paper 2's gate cancelled

The handoff records paper 1, for Radiology: Artificial Intelligence, as complete and held from submission pending the technology-transfer office, because of the invention disclosure submitted on 25 September and the provisional to follow. The provisional's filing was not recorded on 8 October, and the grid pipeline of 21 October still lists it as a future date; the goal page gives the owner's date, by 30 October ([docs/project.md](../../docs/project.md)). Paper 1 still needed a determination number in one placeholder and a supplement cut from 13 pages to the 12-page cap. The determination that placeholder awaited is recorded as HPR 2026-330 of 29 September ([docs/memory/vindr-is-covered-by-hpr-2026-330.md](../../docs/memory/vindr-is-covered-by-hpr-2026-330.md)). The filing and the office's answer reverse V1.

On 27 September the owner cancelled the blinded gate of paper 2, SchwingNet against registration-assisted surgeons, with no recorded reason. The comparator, 97.6 % assisted naming, is frozen; the open gate had scored names only because of a path bug; and the comparator cannot be exceeded at any reachable n, which the literature page backs with no power below 152 persons and 708 needed at a true 99 % ([the programme contradictions](../../artifacts/_synthesis/contradictions/programme-direction-handoffs-and-onboarding.md), row 72). The research directions say what reopens it: 19 or more verified at-risk persons with an exported frame, after which power is recomputed and the gate unblinded under its frozen protocol; with fewer, paper 2 waits on verified cases. Its venue is not chosen.

### V3 to V5, a duplicate, the figures, a pooled frequency

The owner decided not to submit the medical-education study to JEEHP, because it would duplicate the Cureus paper of 14 July 2026.

The [SchwingNet Figures](../../artifacts/schwingnet-figures-xyz6kr/) build of 22:50 on 22 September is the canonical figure record. The owner kept Figures 1 and 5 unchanged; the inspector re-laid Figure 4, whose panels printed under 5 pt, and redrew Figure 6; and the integration pass swapped the six method figures in and moved the result plots to a supplement, because the journal allows six figures. The superseded 20:12 build, [SchwingNet Figures](../../artifacts/schwingnet-figures-jshksq/), alone holds the captions of rows a to j, the decision that no millimetre value of the overlap row is quotable while one bank's spacing was suspected about 15 % short, and the rule that for submission the one-page figure splits into figures of at most four components. A venue with a larger figure limit would reverse V4.

The overnight review of 16 September declined to pool the reported frequency of wrong-level surgery, because registries and small series measure two quantities under one name: R3 applied to the literature.

### V6, results on slides, and the talk

On 20 October the owner answered the demo plan: the talk is on 2 November, it shows what SchwingNet does and not how, the demo is a recorded sweep made in private and shown only after the filing, and nothing of the method goes on a slide ([docs/research/demo-plan.md](../../docs/research/demo-plan.md), section 8). On 21 October the [Any-View Spine Plan](../../artifacts/any-view-spine-plan/) recorded that results go on slides as results only and nothing appears in an external text before the provisional. The handoff's earlier form allowed only the public v12 deck for the CNS talk, after a disclosure audit. The talk is the CNS mini-oral 66629 ([docs/project.md](../../docs/project.md)). The other venue states in the handoff, the NeurIPS dataset paper accepted as a poster on 24 September and the dataset article's third packet built on 25 September with its upload not recorded, are context; they could not be checked against spine-program's status file. V6 lapses at the filing; the book's site goes public only then, from an allowlist the owner approves ([docs/memory/the-textbook-website.md](../../docs/memory/the-textbook-website.md)).

## The programme's order

### P1, the standing determination

The research directions quote the standing determination of 23 September: name the level correctly on a transitional spine (L6, T13, sacralised L5, four lumbar) from C-arm exposures at parity with an ordinary spine, and report "not at parity" plainly if that is the result. No owner is recorded. It is narrower than "anomaly-aware" because one Castellvi type cannot be seen on a lateral, so the target is the count-changing types. The owner's goal of 20 October is broader, low-latency, high-accuracy vertebral classification on fluoroscopic video or images ([docs/research/retraining-plan.md](../../docs/research/retraining-plan.md), section 1), and carries P1 as the transitional stratum in its own rows. Only the owner's restatement would end it.

### P2, measurement first, human reads second, models third

The research directions of 8 October, the owner's page, set one order: measurement first, human reads second, models third. The two-dimensional system was at ceiling on ordinary spines while no number existed on a real transitional frame with a human read, so the first projects define the three-dimensional target and measure what survives projection, the reader work that creates power starts the same week, and models wait for a frozen truth file and a clean encoder; week one had no model. The page took proposal B as the programme, because its three asks were the structure and its feature specification was what a student could act on, and grafted proposal A's rule of the smallest experiment that changes a decision and proposal C's venue and power discipline. Three rules ran through it: a moved re-read changes the split and re-runs the leak audit before the clean encoder scores anyone; no weight trained with one licensed film set leaves before the owner reads its licence; nothing trains on the flagship recipe before the first gates close. Chapter 28 ([The ranked experiment backlog](28-the-ranked-experiment-backlog.md)) holds the ranked list; M21 to M23 in chapter 16 are the method side.

The owner's words of 20 October changed the order in practice: the data workflow first, the first model trained to work is version 1, evaluation on real frames visible from the first checkpoint; the grid pipeline schedules version 1 for 28 October. Whether the 8 October order still binds is open in the record ([the programme contradictions](../../artifacts/_synthesis/contradictions/programme-direction-handoffs-and-onboarding.md), rows 0 and 1, cannot-tell). The log's reading, Inferred, is that the two orders govern different claims and both hold: the October 20 order governs what is built and shown before the talk, version 1 with its transitional rows reported as they come out; the October 8 order governs any transitional claim, which needs the human reads and the counts of R5 first. Version 1's existence is not permission to claim transitional parity. Verified real-frame transitional persons, or the owner's restatement, would re-order P2.

### P3 to P5, one miss of 43, the owner's word, what drops first

The research directions record the owner's choice that the 85 % bound on the 43 test L6 persons allows one miss, not two, since 42 of 43 gives 87.9 % and 41 of 43 gives 84.5 %; proposals A and C had allowed two. The page's arithmetic is Reported here.

The goal page holds that no training job, grid job or Claude run is submitted without the owner's word and the number of jobs, and usage credits are never used ([docs/project.md](../../docs/project.md)); the research directions add that each later model variant waits for the owner's decision. The textbook's synthesis reads are the one standing exception, granted on 23 October with a daily cap. For a planner, P4 means a plan that needs a job ends at the job's description and waits.

The grid pipeline of 21 October records that version 1 no longer waits on the multi-day X-ray fetch and starts from the first catalog, which holds C-ArmLSpine, since the X-ray sets join the next catalog as they arrive. The retraining plan's section 9 sets what drops first if time runs short, some film rows of the evaluation set, the CPU latency and the export, and what never drops: the registry, version 1 and the evaluation page. The owner turned the full CT-RATE fetch, 21.3 TB, off the same day. All of P5 is tied to the talk and expected to be revisited after it.

## Operations: the grid's rules and the incidents behind them

Every rule here exists because something went wrong, and the Lab Recipe prints each beside its incident; they bind every job, a ten-record test included. How a run starts and finishes is [chapter 21](21-the-grid-how-a-run-starts-waits-and-finishes.md); quotas are [chapter 22](22-quotas-cost-and-the-budget-of-a-run.md); Claude workers on the grid are [chapter 31](31-claude-workers-on-the-grid-and-the-labs-machines.md).

### O1 and O2, the login node and afterany

The recipe allows the login node only submission, queue reads, cancellation, listing, tailing and git, after dozens of smoke tests ran on a node shared by about 95 users on 21 September; downloads are jobs too. The onboarding gives the owner's stricter form: nothing runs there, even a one-minute job. A general playbook's small allowance does not apply on this grid ([the programme contradictions](../../artifacts/_synthesis/contradictions/programme-direction-handoffs-and-onboarding.md), row 41).

The recipe's chains use afterany, never afterok, the child reading a file to decide whether its parent succeeded, because on 9 September an eight-hour limit left a whole chain unsatisfiable. The SchwingNet gate of 21 October departs from it: its graph links setup, the first catalog and the version 1 run with afterok, and uses afterany only for the X-ray chain and the leak checks ([SchwingNet grid pipeline](../../artifacts/schwingnet-grid-pipeline/)). No record says this was decided. The log's reading, Inferred, is that afterok in the version 1 path trades the recipe's protection for a simpler failure, a job that never starts, and that whoever extends the gate should keep those edges short or check the parent's output as the recipe does. A recorded decision, or a repeat of the September incident, would settle O2.

### O3 to O6, the partition, the resume record, polling, status

The student templates were fixed on 27 September to the requeue partition and QoS for CPU work, node-local scratch in shared memory removed by a trap, explicit checks and afterany. On 21 October the owner ordered SchwingNet's jobs onto the lab's tested Slurm knowledge: every job is queued through hpcworker's job submit with a class, the CPU class meaning the same requeue partition, and no header of ours names a partition ([docs/memory/grid-jobs-go-through-hpcworker-job-submit.md](../../docs/memory/grid-jobs-go-through-hpcworker-job-submit.md), issue 77). O3 is replaced in form and kept in substance.

The owner's rule of 27 September is that every job is recorded with its script header, as the resume instruction, before anything is cancelled; the gate records every job it submits and its stop word cancels only its own. The handoff adds that resume is not reproduce, since chains write to fixed folders. The recipe limits an agent's polling to about ten minutes in all, submit, estimate, checkpoint and stop, because on 24 September polling agents burned a session limit four times in a day; a playbook's limit on how often to poll is a different rule, and both hold (row 42). Status is computed from disk and queue by a tool, never hand-written, because a hand-written table listed a job as pending three hours after the scheduler showed it cancelled; the gate's status word reads the scheduler's accounting.

### O7 to O9, Nextflow, the shipping commands, a second worker

The recipe uses Nextflow only for pipelines of three or more stages over many cases, mostly CPU and mostly other people's tools; the GPU census stays as the scheduler's arrays, and no imaging repository runs Nextflow (row 43 finds no conflict with the later checklist).

The onboarding forbids PowerShell for the commands that ship code to the grid, because it breaks the stream, and forbids saving a job script with a heredoc. Both serve the laptop step, which lasts only until issue 19 settles whether the grid can reach GitHub (N3). A page of 14 October found the network reaches GitHub but the private repository has no login there (row 40), and the SchwingNet gate already keeps its own checkout through Beethoven, so O8 may lapse for SchwingNet.

On 21 October the owner decided that no second grid worker starts without the owner's word and a number, because it spends allocation ([Grid and cloud Claude workers: review](https://claude.ai/artifact/L7nL3xkYzoitmWf4ab8ARN), files at https://github.com/OpenSpineConsortium/symphony-template/tree/main/artifacts/grid-and-cloud-claude-workers-review). It is P4 applied to workers.

### O10 and O11, the free-space margin and credentials

The grid pipeline of 21 October has each fetch chain refuse to submit beyond the volume's free space less 5 TB. Two days later the owner replaced the margin: every fetch reads its exact size before a byte lands and is refused whole when it would pass the lab volume's quota after what running fetches still owe, with no floor ([docs/memory/the-size-rule.md](../../docs/memory/the-size-rule.md)). O10 is the clearest case here of an operations decision reversed by a better one within days; chapter 22 holds the rule.

The recipe and the onboarding agree that credentials are read from files of mode 600, never echoed, never on a command line, in a job's export, a log or a repository, and that each student uses a token of their own, because a token on a command line lands in the history and the job log.

## Governance

Governance here records what was decided. The owner has settled what data the project may use and on what terms ([docs/memory/vindr-is-covered-by-hpr-2026-330.md](../../docs/memory/vindr-is-covered-by-hpr-2026-330.md)); no entry below is open on that account or a reason to drop a result.

G1: the [OpenSpine Board](../../artifacts/openspine-board-t3gfds/) of 11 September listed the IRB correspondence as still public and awaiting a go; [Spine Program Decisions](../../artifacts/spine-program-decisions-qqhkqz/), which supersedes the board and carries its items in their later state, records it purged from public history and both remotes force-pushed, because the files named eight staff with work addresses. One step is left to the owner: asking GitHub support to purge cached views of two old commits. The board alone dates these items to 11 September and holds its grid job list, including the cancellation of a download chain that resubmitted itself every five minutes after 17,073 of 17,075 files were down.

G2 and G3: the [Retrospective Fluoroscopy Protocol](../../artifacts/retrospective-fluoroscopy-protocol/), a draft dated January 2027, requests Expedited review under Category 5 rather than Exempt Category 4, because research that may support an FDA pre-submission cannot be exempt, a coded master list is kept during abstraction and the images carry burned-in text. The [AIDaS Seed Grant Proposal](../../artifacts/aidas-seed-grant-proposal/) had left either open; the protocol settles it ([the OR-study contradictions](../../artifacts/_synthesis/contradictions/the-case-for-the-or-study-proposal-seed-grant-and-irb-protoc.md)). The protocol also starts no prospective study until detector performance on the institution's own machines and patients is known, since the deployment risk is the detector and synthetic fluoroscopy does not close the domain gap; the shadow-mode study is a separate protocol, sent only if this one meets its endpoints. These are the study team's draft decisions; what was submitted is not in the sources. [Chapter 20](20-readiness-for-the-operating-room.md) holds the study.

G4: on 15 October the owner kept coordbench, the coordination experiment, out of the grant text until the owner says otherwise, because it is a pilot whose token and dollar figures are inflated ([Symphony and Beethoven Taxonomy Spec](../../artifacts/symphony-and-beethoven-taxonomy-spec-lcbqro/)); a comparison of the next day adds that a harness audit found 11 of 40 runs spoiled ([Symphony versus competitors](https://claude.ai/artifact/LynwZkPadyo2SQ7G4mJfHc)).

G5: the seed grant makes public release of the corpus no deliverable, and the protocol shares only aggregates, any release of de-identified images going to the IRB as an amendment first. The proposal requests $20,000 for 2027 and delivers a validated prototype, in-domain data and an FDA pre-submission rather than clearance; whether it was submitted by its 16 October deadline is not recorded (row 66). The recipe's two-track rule, that the research track never moves to a commercial one, is [chapter 23](23-who-may-do-what.md)'s.

## Onboarding

N1 and N4: the onboarding of 13 October leaves a claude.ai Project's instructions, description and memory blank, because everything Claude needs is in the repository and nothing typed in a Project can then drift from what the owner's threads read; SchwingNet's Project works the same way. The handoff's earlier instruction, that a fresh Claude project loads the handoff's README, infrastructure page and note index and never the archived memory, whose summaries carry leaked numbers, applies to the older repository (row 50).

N2: since 13 October each folder's results, figures, manuscripts and regulatory files live in the grid archive with a link in the folder, by the owner's decision; a page of the next day says the owner had still to fill the archive by script (row 47), so whether it holds them is unsettled.

N3: issue 19 is a student's first task, because it needs no data, exercises the whole setup and decides whether the laptop step is needed; its outcome is not in the sources. The onboarding's other rules stand: an owner-first issue is a student's only once handed over, no research without an issue, no student's name or personal address in a file, the house words and whole-integer versions. The recipe's ICMJE authorship rule, with the middle of the byline ordered by recorded volume, waits on the owner's confirmation.

## What we know

The reporting rules are decisions with reasons: accuracy with coverage (R1), intervals clustered at the case and now keyed to the person (R2), per source with the device-held-out arm beside any pooled figure (R3), no figure from eight transitional spines and no transitional claim below the stated counts (R5), numbers only through manifest keys or run records (R6, R7), the failure reported with the result (R8), random verification samples (R9) and leaked families as records only (R10). Paper 1 is held for technology transfer, paper 2's blinded gate is cancelled and waits on verified persons, and nothing of the method appears outside before the provisional. The owner set the order of work on 8 October and changed what is built first on 20 October; no job runs without the owner's word and number. Each grid rule answers a dated incident, and the free-space margin was already replaced by a better rule. The governance decisions are settled.

## What we do not know

The record does not settle whether the 8 October order binds work before the talk, or whether a held-out transitional person may be scored before the hypothesis is recorded as seen. It does not say whether the provisional was filed, whether paper 1, the dataset article or the seed grant went in, whether the manifest gaps of 27 September closed, whether the grid archive holds what N2 moved, or what issue 19 found. No record decides the gate's afterok edges. C-ArmLSpine's persons per case are unsettled, so R2's unit is too. Paper states were not checked against spine-program's status file.

## What would change our mind

Verified real-frame transitional persons in the numbers R5 and P3 name would reopen paper 2's gate and allow a transitional claim. A filed provisional ends V1's hold and V6's slide rule. A recorded decision on the gate's afterok edges, or a chain lost to one, would settle O2. A person table for C-ArmLSpine would fix R2's unit. The owner's restatement of which order binds would settle P2. A run record that disagrees with the old catalog on one claim would test R6.

## Provenance

| Statement | Source | Grade |
| --- | --- | --- |
| Report accuracy among answered with coverage and the whole risk-coverage curve, because no published system reaches 99 % on plain radiographs (16 Sep) | [Overnight: The Honest 99%](../../artifacts/overnight-the-honest-99-kantj8/) ([claude.ai](https://claude.ai/artifact/KanTj8B4omwWtpbz9wABZD)) | Reported |
| 99 % accuracy among answered at 35.7 % coverage on held-out renders, a record and not a final value | [Overnight: The Honest 99%](../../artifacts/overnight-the-honest-99-kantj8/) ([claude.ai](https://claude.ai/artifact/KanTj8B4omwWtpbz9wABZD)) | Unverified |
| The 99 % selective-accuracy claim and allspine v2's 99.02 % come from leaked families and are record only | [Handoff](../../artifacts/handoff-schwingnet-ctspinopelvic1k-and-the-imaging-programme-rbcdmf/) ([claude.ai](https://claude.ai/artifact/RBCDMF1YwL93MmeJTkv3oa)) | Reported |
| Every confidence interval clustered at the case; a naive interval covered 70.8 % of the time (22 Sep) | [Counting From The Sacrum](../../artifacts/counting-from-the-sacrum/) ([claude.ai](https://claude.ai/artifact/WSW2UJAR4ar2PjmbymLVRf)) | Reported |
| Naming numbers carry Wilson intervals on person-keyed n; the transitional stratum is its own rows; every row stamps version, shard hash, commit and clean-tree flag | [docs/research/retraining-plan.md](../../docs/research/retraining-plan.md) | Reported |
| C-ArmLSpine's sessions and subjects (149 against 120) are not settled | [the programme contradictions](../../artifacts/_synthesis/contradictions/programme-direction-handoffs-and-onboarding.md), row 22 | Unverified |
| Results per source and acquisition, never pooled | [Vertebra Detector Field Report](../../artifacts/vertebra-detector-field-report-1jljc6/) ([claude.ai](https://claude.ai/artifact/1jLJC6zVJpcSw1VCCFbJPR)) | Reported |
| Pooled device numbers never quoted without the device-held-out arm; the published 0.990 is a ceiling, not the 3-D side of parity | [Research directions from the data holding](../../artifacts/research-directions-from-the-data-holding-kcyckb/) ([claude.ai](https://claude.ai/artifact/KCyCkBtrHXGYQVM6LtpnK8)) | Reported |
| Within-one-level called the honest primary metric for a level-confirmation tool (13 Sep) | [Level Context Ladder](../../artifacts/level-context-ladder-xd7eltc/) ([claude.ai](https://claude.ai/artifact/Xd7ELTcKW1yXaC7KtKma9z)) | Reported |
| Later records make the exact level the headline, so R4 is narrowed | [docs/research/retraining-plan.md](../../docs/research/retraining-plan.md), against [Level Context Ladder](../../artifacts/level-context-ladder-xd7eltc/) ([claude.ai](https://claude.ai/artifact/Xd7ELTcKW1yXaC7KtKma9z)) | Inferred |
| No figure quoted from the eight held-out transitional spines (18 Sep) | [Naming Vertebrae Without CT](../../artifacts/naming-vertebrae-without-ct-hjy4vc/) ([claude.ai](https://claude.ai/artifact/HJY4VC3VUVh7oNH4C7YEpR)) | Reported |
| No rate from the reader study quoted; the misnamed frames were a census | [Vertebral Levels Without CT](../../artifacts/vertebral-levels-without-ct-a4rydj/) ([claude.ai](https://claude.ai/artifact/A4rydJAxQurBkPKrvfAUQs)) | Reported |
| 22 carriers for 85 %, 35 at-risk persons for 90 %; below 22 no fluoroscopy transitional sensitivity is claimed; verified real-frame count zero on 8 Oct | [Research directions from the data holding](../../artifacts/research-directions-from-the-data-holding-kcyckb/) ([claude.ai](https://claude.ai/artifact/KCyCkBtrHXGYQVM6LtpnK8)) | Reported |
| Where any file differs from the results catalog, the catalog wins | [Handoff](../../artifacts/handoff-schwingnet-ctspinopelvic1k-and-the-imaging-programme-rbcdmf/) ([claude.ai](https://claude.ai/artifact/RBCDMF1YwL93MmeJTkv3oa)) | Reported |
| Numbers through manifest keys, never typed; pre-register, freeze, departures in a deviations file | [The Lab Recipe](../../artifacts/the-lab-recipe-1t2gvp/) ([claude.ai](https://claude.ai/artifact/1T2gVPMkKhzU2J4TryUDRG)) | Reported |
| On 27 Sep the tables carried 167 bare numerals and none of 79 manifest keys began with a job id | [The Lab Recipe](../../artifacts/the-lab-recipe-1t2gvp/) ([claude.ai](https://claude.ai/artifact/1T2gVPMkKhzU2J4TryUDRG)) | Reported |
| Both the naming result and the unsolved detection problem are reported | [Counting From The Sacrum](../../artifacts/counting-from-the-sacrum/) ([claude.ai](https://claude.ai/artifact/WSW2UJAR4ar2PjmbymLVRf)) | Reported |
| Verification samples are random within route with a fixed seed; can't-tell leaves the denominator; the sample never trains | [Level Verification Bench](../../artifacts/level-verification-bench-mkjxsy/) ([claude.ai](https://claude.ai/artifact/MKJXSYgzFBa5ndLK8TVsKo)) | Reported |
| The owner allowed leaked-family numbers in the book as records with a link and a disclaimer (23 Oct) | the preface's owner answers, [artifacts/_synthesis/table-of-contents.md](../../artifacts/_synthesis/table-of-contents.md) | Reported |
| A 100 % sacrum figure ruled not the method's; phantom results a sheet, not a number; a held-out cell re-scored under one convention | [OR Readiness Ledger](../../artifacts/or-readiness-ledger/) ([claude.ai](https://claude.ai/artifact/TUNtAawdAQh2vvRT9kWNf2)) | Reported |
| Paper 1 held pending technology transfer; disclosure submitted 25 Sep; provisional not recorded; supplement 13 pages against 12 | [Handoff](../../artifacts/handoff-schwingnet-ctspinopelvic1k-and-the-imaging-programme-rbcdmf/) ([claude.ai](https://claude.ai/artifact/RBCDMF1YwL93MmeJTkv3oa)) | Reported |
| The provisional is to be filed by 30 Oct; the talk is the CNS mini-oral 66629 on 2 Nov | [docs/project.md](../../docs/project.md) | Reported |
| The determination the paper's placeholder awaited is HPR 2026-330 of 29 Sep | [docs/memory/vindr-is-covered-by-hpr-2026-330.md](../../docs/memory/vindr-is-covered-by-hpr-2026-330.md) | Reported |
| Paper 2's blinded gate cancelled 27 Sep; comparator 97.6 % frozen; open gate scored names only because of a path bug | [Handoff](../../artifacts/handoff-schwingnet-ctspinopelvic1k-and-the-imaging-programme-rbcdmf/) ([claude.ai](https://claude.ai/artifact/RBCDMF1YwL93MmeJTkv3oa)) | Reported |
| The comparator cannot be exceeded at a reachable n: no power below 152 persons, 708 needed at a true 99 % | [the programme contradictions](../../artifacts/_synthesis/contradictions/programme-direction-handoffs-and-onboarding.md), row 72 | Reported |
| With 19 or more verified at-risk persons paper 2's gate is unblinded under its frozen protocol | [Research directions from the data holding](../../artifacts/research-directions-from-the-data-holding-kcyckb/) ([claude.ai](https://claude.ai/artifact/KCyCkBtrHXGYQVM6LtpnK8)) | Reported |
| No JEEHP submission, since the Cureus paper of 14 Jul 2026 would be duplicated | [Handoff](../../artifacts/handoff-schwingnet-ctspinopelvic1k-and-the-imaging-programme-rbcdmf/) ([claude.ai](https://claude.ai/artifact/RBCDMF1YwL93MmeJTkv3oa)) | Reported |
| Six method figures swapped in, result plots to a supplement; Figures 1 and 5 kept by the owner | [SchwingNet Figures, 22:50](../../artifacts/schwingnet-figures-xyz6kr/) ([claude.ai](https://claude.ai/artifact/XyZ6krXFYezkdkpj2kAKPw)) | Reported |
| Millimetre values of the overlap row not quotable; one-page figure to split into at most four components | [SchwingNet Figures, 20:12](../../artifacts/schwingnet-figures-jshksq/) ([claude.ai](https://claude.ai/artifact/JSHksQ6Tgad2w8cwJmaDZT)) | Reported |
| The review declines to pool reported wrong-level frequency | [Overnight: The Honest 99%](../../artifacts/overnight-the-honest-99-kantj8/) ([claude.ai](https://claude.ai/artifact/KanTj8B4omwWtpbz9wABZD)) | Reported |
| The talk shows what SchwingNet does, not how; recorded sweep; nothing of the method on a slide | [docs/research/demo-plan.md](../../docs/research/demo-plan.md) | Reported |
| Results go on slides as results only before the provisional (21 Oct) | [Any-View Spine Plan](../../artifacts/any-view-spine-plan/) ([claude.ai](https://claude.ai/artifact/XofcEieMWzL443pSG8qrLh)) | Reported |
| The standing determination of 23 Sep: parity on transitional spines, "not at parity" reported plainly | [Research directions from the data holding](../../artifacts/research-directions-from-the-data-holding-kcyckb/) ([claude.ai](https://claude.ai/artifact/KCyCkBtrHXGYQVM6LtpnK8)) | Reported |
| Measurement first, human reads second, models third; proposal B taken with A's and C's grafts; one miss of 43 | [Research directions from the data holding](../../artifacts/research-directions-from-the-data-holding-kcyckb/) ([claude.ai](https://claude.ai/artifact/KCyCkBtrHXGYQVM6LtpnK8)) | Reported |
| The owner's words of 20 Oct put the data workflow first and make the first model trained to work version 1 | [docs/research/retraining-plan.md](../../docs/research/retraining-plan.md) | Reported |
| Whether the 8 Oct order binds before the talk is cannot-tell | [the programme contradictions](../../artifacts/_synthesis/contradictions/programme-direction-handoffs-and-onboarding.md), rows 0 and 1 | Unverified |
| The two orders govern different claims and both hold | [docs/research/retraining-plan.md](../../docs/research/retraining-plan.md), against [Research directions from the data holding](../../artifacts/research-directions-from-the-data-holding-kcyckb/) ([claude.ai](https://claude.ai/artifact/KCyCkBtrHXGYQVM6LtpnK8)) | Inferred |
| Version 1 no longer waits on the X-ray fetch; full CT-RATE off; registry, version 1 and the evaluation page never drop | [SchwingNet grid pipeline](../../artifacts/schwingnet-grid-pipeline/) ([claude.ai](https://claude.ai/artifact/UMnwCkV9SQm2kokkCXWUKA)) | Reported |
| Grid rules with their incidents: login node, afterany, scratch, resume record, no polling, computed status, Nextflow scope | [The Lab Recipe](../../artifacts/the-lab-recipe-1t2gvp/) ([claude.ai](https://claude.ai/artifact/1T2gVPMkKhzU2J4TryUDRG)) | Reported |
| Nothing on the login node, even a one-minute job; no PowerShell, no heredoc; issue 19 first; blank Project fields; grid archive | [spine-program student onboarding](../../artifacts/spine-program-student-onboarding/) ([claude.ai](https://claude.ai/artifact/XXQGQczdaQ7rj83znFbiQL)) | Reported |
| The gate uses afterok in the version 1 path, departing from the recipe | [SchwingNet grid pipeline](../../artifacts/schwingnet-grid-pipeline/) ([claude.ai](https://claude.ai/artifact/UMnwCkV9SQm2kokkCXWUKA)) | Inferred |
| Every SchwingNet job goes through hpcworker's job submit with a class (21 Oct, issue 77) | [docs/memory/grid-jobs-go-through-hpcworker-job-submit.md](../../docs/memory/grid-jobs-go-through-hpcworker-job-submit.md) | Reported |
| The 5 TB margin was replaced on 23 Oct by an exact-size, all-or-nothing rule with no floor | [docs/memory/the-size-rule.md](../../docs/memory/the-size-rule.md) | Reported |
| No second grid worker without the owner's word and a number | [Grid and cloud Claude workers: review](https://claude.ai/artifact/L7nL3xkYzoitmWf4ab8ARN) | Reported |
| IRB correspondence purged from public history; asking GitHub support to purge cached views remains | [Spine Program Decisions](../../artifacts/spine-program-decisions-qqhkqz/) ([claude.ai](https://claude.ai/artifact/QQhkqZ5rJsPidb7xjBRKyp)) | Reported |
| The board of 11 Sep listed the IRB files as awaiting a go and cancelled a self-resubmitting download chain | [OpenSpine Board](../../artifacts/openspine-board-t3gfds/) ([claude.ai](https://claude.ai/artifact/T3GfDSZpBYiLRC2166iu8o)) | Reported |
| Expedited Category 5; no prospective study before detector performance is known; aggregates only | [Retrospective Fluoroscopy Protocol](../../artifacts/retrospective-fluoroscopy-protocol/) ([claude.ai](https://claude.ai/artifact/8sz8XUJsAdDDWZdKBCt5sc)) | Reported |
| $20,000 for 2027; no FDA clearance within the year; public release not a deliverable; submission by 16 Oct not recorded | [AIDaS Seed Grant Proposal](../../artifacts/aidas-seed-grant-proposal/) ([claude.ai](https://claude.ai/artifact/UwoqsEAjFPcUJVDutVpFHx)) | Reported |
| coordbench stays out of the grant until the owner says so (15 Oct) | [Symphony and Beethoven Taxonomy Spec](../../artifacts/symphony-and-beethoven-taxonomy-spec-lcbqro/) ([claude.ai](https://claude.ai/artifact/Lcbqrojz4uLvqPfvv1DZym)) | Reported |
| A harness audit found 11 of 40 coordbench runs spoiled | [Symphony versus competitors](https://claude.ai/artifact/LynwZkPadyo2SQ7G4mJfHc) | Reported |
| A fresh Claude project loads the handoff's README, infrastructure page and index, not the archived memory | [Handoff](../../artifacts/handoff-schwingnet-ctspinopelvic1k-and-the-imaging-programme-rbcdmf/) ([claude.ai](https://claude.ai/artifact/RBCDMF1YwL93MmeJTkv3oa)) | Reported |
| Whether the grid archive was filled is disputed between pages of 13 and 14 Oct | [the programme contradictions](../../artifacts/_synthesis/contradictions/programme-direction-handoffs-and-onboarding.md), row 47 | Unverified |
