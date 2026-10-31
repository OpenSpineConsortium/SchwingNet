#!/bin/bash
# The one entry point the Beethoven grid gate calls (issue #53), as the gate word
# `schwingnet <word> [<id>]`, so the owner never types a grid command again (his rule of
# 2026-10-21 19:37 UTC). The gate's side brings the checkout to main first (a clone at ~/SchwingNet
# when there is none, else a fast-forward) and then runs `bash ~/SchwingNet/grid/gate.sh <word> [<id>]`.
# On the login node this script runs only bash, git (with gh as its sign-in for a carried folder),
# hpcworker, squeue, sacct, scancel, flock, awk, sed and coreutils (warrior kills python by name);
# every byte of work is a Slurm job, queued through hpcworker's `job submit` with a class and no
# partition or QoS of ours (grid/hpcw.sh, issue #77), and every Python step of those jobs runs inside
# the container (grid/box.sh, grid/bin/). The one exception is a carried folder's copy, which git
# makes here as the gate's side fetches main, since it is a copy and no computation (word_fetch_carried).
#
#   start           the whole graph, with Slurm dependencies, once:
#                     setup        the container and the pixi environments, only when pixi.lock
#                                  changed since the environments were last made
#                     weights      the ImageNet ResNet-18 file, only when it is not there yet
#                     carmlspine   C-ArmLSpine's bank as a train and a test shard (afterok setup)
#                     catalog      the first catalog version, with C-ArmLSpine and the shards
#                                  already there (afterok setup, afterany carmlspine)
#                     xr_*         the X-ray chain: fetch (afterok setup), bank and ingest,
#                                  catalog (afterany bank and the first catalog)
#                     dp_*         the CT platform fetch, after the X-ray fetch (X-ray before CT)
#                     probe        what the raw case134 and case39 sweeps are on disk
#                     v1_driver    the version 1 run (afterok the first catalog, carmlspine,
#                                  setup and weights)
#   status          the gate's jobs and their states; the end of the log of each newest job that
#                   failed, masked (grid/redact.sed), and for a job that reads DICOM headers,
#                   person keys or a sign-in only its tracebacks and status lines (grid/log-shapes.awk);
#                   the stage reports with their paths cut and a quoting reason withheld
#                   (grid/report-shapes.awk), masked; the newest run; one page of 400 lines and
#                   64 KiB, handed out in the order a reader needs it (grid/status-page.awk)
#   leaks           the leak checks over every shard on the volume, once no ingest is queued
#   v1              the version 1 run alone (again, after a failure), while start's other jobs are
#                   still live: each input is there, made by a live job of the gate's, or submitted
#                   now (the weights, the C-ArmLSpine ingest, a catalog build afterok on it), and
#                   the run waits afterok on each, so an input that fails again cancels it; the
#                   catalog version is the one grid/v1-version.sh chooses
#   latency         the latency jobs for the newest run that has a checkpoint, with the case134 sweep
#   fetch <id>      one set of grid/fetch-xray.json, a credentialed one with ~/.netrc, banked and catalogued;
#                   or one source of grid/run-platform-fetch.sh's --gated-ids (CADS, RSNA RATIC, RSPECT,
#                   ReXGradient once its token or link file is in place; the full NLST on the owner's yes),
#                   after any live X-ray fetch; or one carried folder of grid/carry/, a commit a cloud
#                   session pushed to a private branch, fetched with git on this node and checked file by
#                   file against its SHA256SUMS before it lands, with no job (the owner's word of
#                   2026-10-28 17:24 UTC for the Claude project's shared folder)
#   explore <id>    one look inside a fetched set (tools/explore.py, grid/explore.sbatch): the first send
#                   queues one job for the listing of its raw folder and zips and, for a set the gate
#                   names one for (explore_against), the comparison with it by name and content; the
#                   next send prints the report, logs/EXPLORE-<id>.md, and queues nothing; a new fetch
#                   of the set or a change to tools/explore.py makes the next send look again
#   dropzip <id>    the deletion of a fetched set's download zips (tools/dropzip.py, grid/dropzip.sbatch,
#                   the owner's word of 2026-10-23): the first send queues one job, which deletes a zip
#                   only when every file in it sits unpacked beside it at the same size; the next send
#                   prints its report, logs/DROPZIP-<id>.md, and clears it, so a later send looks again
#   unpack <id>     the unpacking of a fetched set's download zips beside themselves (tools/unpack.py,
#                   grid/unpack.sbatch, the owner's word of 2026-10-23 for RSPECT): the first send
#                   queues one job, which starts writing only when the size rule admits what the
#                   unpacked files take; the next send prints its report, logs/UNPACK-<id>.md, and
#                   clears it, so a later send goes on where a job cut short stopped
#   nodequota       the volume's readout as a compute node reads it (grid/nodequota.sbatch, the owner's yes
#                   of 2026-10-24): the first send queues one job, the next prints logs/NODEQUOTA.md and
#                   clears it, so the send after that looks again
#   folders         what each unmapped folder of the data root holds (tools/folder_report.py,
#                   grid/folders.sbatch, #296, the owner's yes of 2026-10-25): the first send queues one
#                   job over the newest whole sample index, the next sends print its pages,
#                   logs/FOLDERS-<n>.md, one a send, clearing each, so the send after the last looks again
#   samples         the sample index (grid/run-samples.sh): plan, scan and merge, refused while one
#                   of them is live; status shows its MANIFEST.md, aggregates only
#   sweep <plan>    one plan of grid/sweeps/ (issue #252): the block smoke test on one GPU through
#                   the Metaflow flow (grid/sweep-driver.sbatch), after the setup and the weights
#                   where the plan needs them, on the catalog version that qualifies now (the v1
#                   plan's of C-ArmLSpine alone, grid/v1-version.sh --alone) or after a live build
#                   that can make one, and afterany every live run that holds the checkout; status
#                   shows each plan's PROGRESS.txt under SMOKE
#   bank <id>       one recipe of grid/banks/ banked and ingested (grid/02-bank-ingest.sbatch with
#                   ONLY=<id>) and a catalog build afterok on it: two CPU jobs, once its held raw
#                   copy is there, no job still lands the folder under the data root that holds it,
#                   and the room under the quota takes what they may write by the recipe's format,
#                   which the bank holds as the size rule's admission while it is live and checks
#                   again when it starts, then for the larger of that and its frames' pixel bound
#   experiment <n>  one requested combination of data and blocks, issue #<n> labelled experiment: the
#                   request the experiment workflow recorded as <n>.request on the branch experiments,
#                   fetched now and checked line by line, run as one GPU job (experiment-driver.sbatch)
#                   once the version 1 inputs are there (the environments, the weights, C-ArmLSpine's
#                   shards and a qualifying catalog version, which 'v1' makes), refused while a run for
#                   the same issue is live and afterany every other live run that holds the checkout;
#                   the job checks the values against the blocks module before anything trains
#   bench <name>    one public model's benchmark as its authors published it (#287, the owner's word and
#                   count of 2026-10-25): flexray_carmlspine, flexray_deepfluoro or xvr_deepfluoro, each one
#                   GPU job (grid/bench.sbatch, tools/bench_public.py) once its fetch has landed; the next
#                   send prints logs/BENCH-<name>.md, and every later one prints it again and queues nothing,
#                   but for a report that ended in failure on older code (#312) or whose job BENCH_RERUNS
#                   lists, the owner's count for one more run, each kept under its job's number and queued once more;
#                   and flexray_drr_gap, the DRR domain-gap study (tools/domain_gap.py), sharded (the
#                   owner's words of 2026-10-27 17:51 UTC and 2026-10-28 00:23 UTC): three GPU jobs on
#                   any card of the gpu class (grid/drr-gap.sbatch), prepare, an array of DRR_GAP_TASKS
#                   (16) shard tasks afterany it and
#                   the merge afterany the array, all queued or none, each step run from prepare's copy of
#                   the code and none holding the checkout, once FleXray's weights, a whole sample index,
#                   the TotalSegmentator CTs and the ImageNet file are there; FluXray, the SPINEPS masks
#                   (spineps) and the MOOSE masks (moose, which flexray_drr_seg makes) are each read where
#                   they are there and the groups that need one skipped with its reason otherwise, since
#                   a DRR is a projection of the CT alone and the groups that read no label render
#                   without masks (the owner's word of 2026-10-27), and the send says which are read; a
#                   send while any of the three is live prints the study's PROGRESS.txt, which status
#                   shows too, and refuses; only its summary leaves the grid, through grid/redact.sed; and
#                   flexray_drr_seg, one GPU job before it (the owner's word of 2026-10-26: MOOSE labels
#                   for the FleXray replication, SPINEPS for production): the study's choice of CTs
#                   (tools/domain_gap.py plan) and MOOSE on exactly those (tools/flexray_render.py segment),
#                   once the TotalSegmentator CTs, the SPINEPS masks and the five model zips of
#                   `fetch moose_weights` are there; it writes the masks under the data root's moose.
#                   Both run on launched flows (the owner's rule of 2026-10-29): each of the study's
#                   jobs, and each task of its array, starts flows/launch.py drr_gap from prepare's copy
#                   of the code, and flexray_drr_seg's job (grid/drr-seg.sbatch) flows/launch.py drr_seg
#   anomaly <stage> one stage of the SPINEPS to FleXray anomaly route (#398, the owner's word and count of
#                   2026-10-25 21:22 UTC: seven jobs, two CPU and five GPU, docs/research/spineps-anomaly-route.md),
#                   queued once as one job (grid/anomaly.sbatch, tools/anomaly_route.py) once the stage's code has
#                   merged; the next send prints logs/ANOMALY-<stage>.md, and every later one prints it again and
#                   queues nothing. Built so far: select, the inventory, the two-labeller call, the holdout's
#                   score and the selection, one CPU job over masks that already exist; timing, one GPU job that
#                   lists the paired CTs without a named SPINEPS mask and times SPINEPS on ten of them
#                   (tools/anomaly_timing.py), sent once select's report ended well, and queued again at the
#                   same commit when its GPU self-test left a node the spineps environment cannot use (exit 4);
#                   pack, one CPU job of three days at most that rewrites the existing masks to the canonical
#                   ids and packs FleXray's two whole-volume packages under the landing flexray_pack
#                   (tools/anomaly_pack.py), sent once timing's report ended well, admitted under the size
#                   rule before a byte lands and queued again at the same commit when the rule refused it (exit 5)
#   bordercall <stage>  the bordercall corpus and its answer, which junction the shape of the bone names most
#                   robustly in normal and anomalous spines, over every full-spine SPINEPS mask the grid holds
#                   (the owner's prompt of 2026-10-25 23:48 UTC and count of 23:56 UTC: two CPU jobs; grid/bordercall.sbatch,
#                   tools/bordercall_corpus.py, the copy under grid/bordercall/): pilot, the first few hundred countable
#                   cases, then full, every countable mask, which the gate takes only once the pilot's report ended
#                   well; each queued once as one batch job, the next send printing logs/BORDERCALL-<stage>.md, and
#                   every later one printing it again and queueing nothing; and complete, the gold tier 3
#                   completion (the owner's count of 2026-10-29 15:22 UTC, one CPU job; grid/bordercall-complete.sbatch,
#                   tools/gold3_complete_grid.py, the matcher under grid/bordercall/holdings/): bordercall's matcher
#                   over the census's existing SPINEPS masks, nothing segmented, queued once with no pilot before
#                   it, the next send printing logs/BORDERCALL-complete.md and every later one printing it again;
#                   a job that left no report is not queued again without the owner's word
#   census gold3    the gold tier census, one CPU job that reads only and segments nothing (the owner's tap of
#                   2026-10-29 12:26 UTC, "Send the 1 CPU job now"; grid/gold3-census.sbatch, tools/gold3_census.py):
#                   the older TotalSegmentator list, the autoPET match, gold 4 over the census's SPINEPS masks,
#                   TotalSegmentator's own image extents and the held files; queued once as one batch job, requeueable
#                   (a preemption starts the same job again where it stopped), from git's copy of its code at the
#                   gate's commit, so it holds no checkout; refused while a root it reads is not on the volume;
#                   the next send printing logs/CENSUS-gold3.md, or the unfinished .part a job killed outright
#                   left, and every later one printing it again and queueing nothing; a second job only where
#                   CENSUS_RERUNS, committed by pull request, carries the owner's word for it
#   totalseg complete  the gold tier 3 completion's TotalSegmentator arm (the owner's word of 2026-10-30 08:54 UTC,
#                   "Add sacrum and c2 w total seg", and his count; grid/totalseg-complete.sbatch, tools/gold3_totalseg_grid.py,
#                   the launched flow totalseg under docs/research/gold3-ct/completion/PREREG.md): TotalSegmentator 2.18.0's
#                   total task with roi_subset vertebrae_C2 sacrum on each admitted study's own CT whose release lacks C2
#                   or the sacrum (MOOSE's vertebrae model for ENHANCE.PET's, whose masks MOOSE made, the owner's word of
#                   09:33 UTC), each drawn level checked against the release's own levels and kept as a machine arm
#                   file in the release's own label id, named by its sha256; one GPU job, queued once after `fetch
#                   totalseg_weights` has landed its two zips whole beside moose_weights' five, the next send printing logs/TOTALSEG-complete.md and every later one printing it again;
#                   a job that left no report is not queued again without the owner's word, and a second job, the
#                   report kept as logs/TOTALSEG-complete-<job>.md, only where TOTALSEG_RERUNS, committed by pull
#                   request, carries his word for it
#   morphometry <set>  bordercall's morphometry engine (the packages morphometry, scanimport and screening,
#                   and morphoview's lines, pinned under grid/bordercall/ beside the archived package,
#                   bordercall 9c85de1 since 2026-10-30) over one gold tier 3 set (the thread "Extract morphometrics from gold tier 3
#                   CT"; the owner's count of 2026-10-29 15:19 UTC: two CPU jobs, and of 2026-10-30 14:33 UTC:
#                   one more a set and the join once more; grid/morphometry.sbatch): enhance, every ENHANCE.PET
#                   vertebra label map, or verse, VerSe's 374 int16 copies and then TotalSegmentator's 159
#                   admitted subjects stacked into int16 volumes in VerSe's ids, the facts and the whole-spine
#                   verdicts beside the rows; each set queued once as one batch job once its inputs have
#                   landed, with no setup job, the next send printing logs/MORPHOMETRY-<set>.md, aggregates
#                   alone, and every later one printing it again and queueing nothing, a set that failed
#                   among them; a second job only where MORPHOMETRY_RERUNS, committed by pull request,
#                   carries the owner's word for it, one word for each job, a lost answer's among them (its
#                   job waited for while Slurm holds it by name or by the part it writes), the report it
#                   replaces kept as logs/MORPHOMETRY-<set>-<job>.md, ending with where the files it names
#                   are now, and a whole run's rows and step logs under the set's kept/<job>/; or
#                   covariates, the join of both sets' rows with each person's sex and age
#                   (grid/morphometry-covariates.sbatch, tools/gold3_covariates.py), one CPU job on the
#                   owner's count, refused while any morphometry job is live, while either set's report is
#                   missing, ended in failure, is one MORPHOMETRY_RERUNS names or names no code stamp, while
#                   the two reports name different code stamps, while an earlier join whose report printed
#                   cells has kept no joined table, or while the gate cannot read its commit, queued once
#                   from git's copy of its code at the gate's commit, so it holds no checkout (its interpreter the
#                   checkout's train-cpu only where no SPINEPS environment's or the system's imports numpy and
#                   sqlite3), the per-person tables staying on the grid; the next send printing
#                   logs/MORPHOMETRY-covariates.md, aggregates alone, a page a send (COVARIATES_PAGE_LINES),
#                   and every later one the next page and queueing nothing; a second job only where
#                   COVARIATES_RERUNS, committed by pull request, carries the owner's word for it, one word
#                   for each job, a lost answer's among them, and each such join checked against every
#                   earlier one whose report printed cells (COVARIATES_PREVIOUS, the check across reports); or prior, the gold tier 3
#                   correlation prior (grid/prior/gold3_prior.py, grid/morphometry-prior.sbatch; greg, 2026-10-30), one CPU job
#                   from git's copy of grid/prior at the gate's commit that fits per population how the body
#                   and end-plate measures move together across levels and measures, the next send printing
#                   logs/MORPHOMETRY-prior.md, aggregates alone, and a report from older code fitted again
#   realism <stage> one stage of the FluXray reproduction (docs/research/flux-realism/PREREG.md; the owner's
#                   count of 2026-10-29 02:35 UTC, two GPU jobs): edit, then stats, each one GPU job that runs
#                   the Metaflow flow flows/realism.py through flows/launch.py (grid/realism.sbatch) once its
#                   inputs have landed and the stage before it has finished; the next send prints
#                   logs/REALISM-<stage>.md, or the .part a job ended before its exit left, and every later
#                   one prints it again and queues nothing, a failed or unfinished one queued once more only
#                   once a fix has moved the checkout; lora and eval are refused until they have a count and
#                   a PREREG of their own
#   autoanatomist <plan>  one plan of the auto-anatomist screen under grid/screens/ (the thread "Restart the
#                   auto-anatomist probe"; the owner's words of 2026-10-30, docs/research/autoanatomist-screen/PREREG.md):
#                   every arm of the plan trained at every seed on gold tier 3 CTs, a trial a card, each read on the
#                   plan's validation CTs every few epochs, then the join, which decides each arm against the null;
#                   every part runs the Metaflow flow flows/autoanatomist.py through flows/launch.py from git's copy of
#                   the code at the gate's commit (grid/autoanatomist.sbatch), so none holds the checkout; a plan of
#                   the second screen (AUTOANATOMIST2_PLANS) runs the same flow as the kind autoanatomist2 under its own
#                   PREREG, docs/research/autoanatomist-screen2/PREREG.md (grid/autoanatomist2.sbatch). A plan laid
#                   out as a series is one GPU job, its trials one after another and then the join; one laid out as an
#                   array is a GPU array of a task a trial and a CPU join afterany it, both queued or neither. A plan is
#                   queued only where AUTOANATOMIST_COUNTED names it, the owner's word and count committed by pull
#                   request, only while the frozen PREREG covers its bytes (exit 90), and only once the plans
#                   AUTOANATOMIST_AFTER puts before it have reports ending in exit 0 (the screen after the
#                   smoke); the next send prints
#                   logs/AUTOANATOMIST-<plan>.md, or its unfinished .part, and every later one prints it again and
#                   queues nothing, a failed or unfinished one queued once more only once a fix has moved the
#                   checkout, and any other only where AUTOANATOMIST_RERUNS carries the owner's word; a send while its
#                   jobs last prints where each trial stands
#   literature <list>  one reading list's papers fetched onto the grid (the owner's word of 2026-10-27
#                   23:00 UTC; grid/literature.sbatch, grid/literature_fetch.py, the list grid/literature/<list>.csv):
#                   PMC's open-access copies, Elsevier's through its API with the key and institutional token
#                   the key route wrote, and the open copies Semantic Scholar names, under the size rule, into
#                   the landing literature_<list>, 0700; queued as one batch job, the next send prints
#                   logs/LITERATURE-<list>.md, which names every paper it could not get, keeps it under its job's
#                   number and queues nothing, and the send after that fetches again what is still missing
#   stop            cancel the gate's own jobs that are still queued or running, and nothing else
#   cancel <job>    cancel one of the gate's own live jobs and every other live job its word queued
#                   with it (a fetch's bank and catalog, the DRR domain-gap study's three jobs), and nothing else
#
# While a version 1 run, a sweep, an experiment run, a benchmark, an anomaly stage, a bordercall stage, a
# realism stage or a morphometry set lasts, grid/logs/HOLD names its job and commit (grid/v1-driver.sbatch, grid/sweep-driver.sbatch,
# grid/experiment-driver.sbatch, grid/bench.sbatch, grid/drr-seg.sbatch, grid/anomaly.sbatch, grid/bordercall.sbatch, grid/realism.sbatch,
# grid/morphometry.sbatch;
# not the DRR domain-gap study's steps, grid/drr-gap.sbatch, which run from a copy of their code); the
# gate's side skips its fast-forward while the file is there, and every word but a refused one
# clears a hold whose job Slurm no longer holds, so the run's later steps run the code it
# recorded. One file holds one job, so each run that takes it waits afterany on every other one
# still live (checkout_holders) rather than run beside it.
# Every submission is one line of grid/logs/GATE_JOBS.txt (<job id> <word> <what> <when>) as well
# as of hpcworker's ledger for the project; status and stop read the gate's file, which knows the
# word each job came from, and touch no job it does not name. Which of them are live is read from
# squeue, as before: hpcworker's `job status` reads every job as ended when neither squeue nor sacct
# answers, and a gate that took that for "nothing live" would queue a second graph beside the first.
# HPCWORKER names the hpcworker (the gate's clone hands it here), SQUEUE, SACCT, SCANCEL and
# GETFATTR fakes for the tests, GETFATTR read by the size rule only where SIZE_RULE_STAND_INS=yes
# says so (grid/size-rule.sh); DATA_ROOT, RUNS, SMOKE and MODELS other folders. Exit codes: 0 done,
# 64 a word refused, 75 busy (a word still running, or jobs still live), 2 the checkout or a file
# missing, 1 a submission failed.
set -uo pipefail
# One stream, in order: what the jobs were and why a word was refused reach the gate together.
exec 2>&1
REPO=${SCHWINGNET:-$HOME/SchwingNet}
SQUEUE=${SQUEUE:-squeue}
SACCT=${SACCT:-sacct}
SCANCEL=${SCANCEL:-scancel}
GETFATTR=${GETFATTR:-getfattr}
VOLUME=${VOLUME:-/rs/rs_grp_oschome}
SHARED_DATA=${SHARED_DATA:-/rs/rs_grp_oschome/shared/datasets}
# DATA_ROOT reaches the jobs only when the caller set it (a test's folder): on the grid each stage
# keeps its own default, since stage 2 reads a set DATA_ROOT as its off-grid layout
# (<root>/<id>/raw in place of each recipe's raw folder), where LUMOS and VinDr-SpineXR are not.
GRID_DATA=/rs/rs_grp_oschome/go2432/data
DATA_ROOT_GIVEN=""
[ -z "${DATA_ROOT:-}" ] || [ "$DATA_ROOT" = "$GRID_DATA" ] || DATA_ROOT_GIVEN=yes
export -n DATA_ROOT 2>/dev/null
DATA_ROOT=${DATA_ROOT:-$GRID_DATA}
STORE=$DATA_ROOT/_catalog
RUNS=${RUNS:-/rs/rs_grp_oschome/go2432/runs}
# The block smoke test's results (issue #252): <plan>/<code 8>-<catalog sha256 first 8>/ per sweep, the
# code part naming the code its rows run and the plan's bytes, as `tools/block_sweep.py state` prints it.
SMOKE=${SMOKE:-/rs/rs_grp_oschome/go2432/smoke}
MODELS=${MODELS:-/rs/rs_grp_oschome/go2432/models}
# Each benchmark's results, <name>/ (grid/bench.sbatch, grid/drr-gap.sbatch), where status reads a PROGRESS.txt.
BENCH_ROOT=${BENCH_ROOT:-/rs/rs_grp_oschome/go2432/bench}
# The Metaflow datastore flows/launch.py starts every flow in, the one the launcher defaults to, where
# each run keeps its progress page under progress/<Flow>/<run>/ (flows/stage_progress.py).
FLOW_ROOT=${SCHWINGNET_METAFLOW:-/rs/rs_grp_oschome/go2432/metaflow}
WEIGHTS=$MODELS/resnet18-f37072fd.pth
SWEEP_BANK=${SWEEP_BANK:-$DATA_ROOT/realxray/carmlspine_sweep}
# The anomaly route's stages write under ANOMALY_ROOT (grid/anomaly.sbatch reads the same default from
# the lab volume), and its pack stage reads G3's person split from the home, as the clone's tools do.
ANOMALY_ROOT=${ANOMALY_ROOT:-$VOLUME/go2432/anomaly}
G3_SPLIT=${G3_SPLIT:-$HOME/split_final.json}
NETRC=${NETRC:-$HOME/.netrc}
# The DRR domain-gap study's array (bench flexray_drr_gap, grid/drr-gap.sbatch): how many shard tasks
# share its units, a committed default changed by pull request, since a gate word carries no option
# and the owner's count of jobs decides it. Its three jobs ask no partition, so the gpu class puts
# each on whichever of its partitions frees first (the owner's words of 2026-10-28 00:23 UTC, "shard
# it to more gpus like 16" and "drop the requirement for h200 unless its a memory problem").
DRR_GAP_TASKS=16
# The study's folder under BENCH_ROOT, where its three steps write everything they compute and keep
# (grid/drr-gap.sbatch, DRR_GAP_OUT): a committed name changed by pull request, as DRR_GAP_TASKS is.
# The study keeps whatever an earlier run left in its folder under the same stamps (its plan, the
# images, features and heads keyed by it, and every unit done), so a run in a folder of its own
# computes every render, plan, image, feature, head and unit again from the same inputs, and the
# folder of the run before it is left as it was. Run 3 (docs/research/drr-domain-gap/DEVIATIONS.md,
# item 12) is such a run, the owner's count of 2026-10-29 12:51 UTC; runs 1 and 2 used flexray_drr_gap.
DRR_GAP_FOLDER=flexray_drr_gap_run3
# The benchmarks the owner's word and count let run once more although a report of theirs stands,
# each as <id>:<the job that report's first line names>: a committed list changed by pull request,
# as DRR_GAP_TASKS is, since a gate word carries no option. A send of bench <id> whose standing
# report names a job listed beside the id, from a commit other than the checkout's, keeps that report
# under its job's number, as a failure on older code is kept (#312), and queues the benchmark again;
# the new report names its own job, which no entry lists, so an entry queues its benchmark once and
# every later send prints the new report and queues nothing. A run that writes no report (its merge
# cut short, or its prepare never started) leaves none standing, and the next send queues the
# benchmark again, as it does wherever no report stands, so that send waits for the owner's word.
# flexray_drr_gap:40859208 is the owner's word of 2026-10-29 12:45 UTC, "rerun on grid when u can",
# and his count tapped at 12:51 UTC, one more run of the DRR domain-gap study's 18 jobs (prepare, 16
# shards, the merge), each on its launched flow (the owner's rule of 02:39 UTC that day), and one
# bench flexray_drr_seg only where MOOSE's masks are missing (DEVIATIONS.md, item 12). The entry
# before it, flexray_drr_gap:40828920, was his tap of 2026-10-28 16:28 UTC and his go of 22:58 UTC,
# spent by the second run, prepare 40859208.
BENCH_RERUNS="flexray_drr_gap:40859208"
# The owner's word for one more census job, <id>:<job of the report or the record it replaces>, or
# <id>:lost for a submission whose answer was lost; one word, one more job (word_census).
CENSUS_RERUNS=""
# The auto-anatomist screen's chains, <plan>/<chain>/ (grid/autoanatomist.sbatch reads the same default
# from the lab volume), where a send while its jobs last reads each trial's PROGRESS.txt.
AUTOANATOMIST_ROOT=${AUTOANATOMIST_ROOT:-$VOLUME/go2432/autoanatomist}
# The plans of grid/screens/ the owner's word and count let the screen queue, each once
# (word_autoanatomist): a committed list changed by pull request, as BENCH_RERUNS is, since a gate word
# carries no option. gold3_latent_smoke is the one short GPU smoke of the owner's count of 2026-10-30
# 03:20 UTC ("2 CPU 2 GPU 2 Full run plus 1 short GPU smoke is fine"): one GPU job, its two trials in
# series and the join. gold3_latent_screen, a GPU array of eight trials and a CPU join afterany it, is
# the two jobs of his word of 2026-10-30 08:56 UTC ("Yes to both", to the ask that named those two jobs
# and said they were outside the 03:20 count). The second screen's plans, gold3_latent_smoke2 (one GPU
# job, five trials in series and the join) and gold3_latent_screen2 (a GPU array of twelve trials and a
# CPU join afterany it), are counted since the owner lifted his hold on grid jobs at 2026-10-30 23:03 UTC
# ("please remove all instructions to avoid grid use"), each still sent only after the plan before it
# ends in exit 0 (AUTOANATOMIST_AFTER).
AUTOANATOMIST_COUNTED="gold3_latent_smoke gold3_latent_screen gold3_latent_smoke2 gold3_latent_screen2"
# The plans sent only once another plan's report ends in exit 0, <plan>:<the plan before it>
# (word_autoanatomist): the PREREG (section 5) sends the screen only after the smoke's two trials and
# its join end in exit 0, so the screen's eight cards wait for the smoke to show the code runs. The
# second screen's PREREG (section 5) sends its smoke only once the first screen's report ends in exit
# 0, so the first verdict stands before any trial of the second runs, and its screen after its smoke.
AUTOANATOMIST_AFTER="gold3_latent_screen:gold3_latent_smoke gold3_latent_smoke2:gold3_latent_screen gold3_latent_screen2:gold3_latent_smoke2"
# The plans of the second screen, which run as the kind autoanatomist2 (flows/registry.txt) under its
# own frozen PREREG, queued with its job script grid/autoanatomist2.sbatch; every other plan runs as
# the kind autoanatomist with grid/autoanatomist.sbatch (autoanatomist_kind).
AUTOANATOMIST2_PLANS="gold3_latent_smoke2 gold3_latent_screen2"
# The owner's word for one more send of a plan whose record stands, <plan>:<job that record's first line
# names>, or <plan>:lost for a submission whose answer was lost; one word, one more send.
AUTOANATOMIST_RERUNS=""
# The partition every GPU part of the screen is sent to (word_autoanatomist): galhp, whose cards are
# L40S, and not the gpu class's three. The smoke's first send (job 40884715, 2026-10-30 18:26 UTC)
# landed on a V100 of gvohp, and both its trials stopped at their first compile, JAX 0.10.2's GPU
# compiler finding no configuration for 46 of 218 instructions on that card; each trial still names
# its card (the report's GPU line, environment.json). DEVIATIONS.md beside the PREREG, item 1.
AUTOANATOMIST_PARTITION=galhp
# The owner's word for one more join of the morphometry rows with sex and age, covariates:<job of the
# report or the record it replaces>, or covariates:lost for a submission whose answer was lost, then
# covariates:lost2 for the next such and on, each spent once (logs/MORPHOMETRY-covariates.lost records
# them); one word, one more job (word_morphometry_covariates). A rerun over rows that changed by a few
# persons would print means that difference against an earlier report's into fewer than five, so the
# job is handed every earlier join whose report printed cells (covariates_previous) and withholds each
# block that would (tools/gold3_covariates.py --previous), and the gate refuses while one of those
# joins has no joined table left to check against. covariates:40878978 is the third job of the owner's
# count of 2026-10-30 14:33 UTC (MORPHOMETRY_RERUNS, below): the join once more over both sets' rows
# measured on the merged engine, refused while either set's report standing is still one
# MORPHOMETRY_RERUNS names or the two name different code stamps (covariates_inputs_missing). Its
# report supersedes job 40878978's pedicle, interpedicular, disc and foramen lines, which the merged
# engine reads anew (docs/research/gold3-ct/README.md, section 7a).
# The owner held this count until a resynthesis (2026-10-30), then at 23:56 UTC asked for it to be
# written and the count sent (docs/research/morphometry-resynthesis.md), so the word is back.
COVARIATES_RERUNS="covariates:40878978"
# The owner's word for one more measuring of a morphometry set, <set>:<job of the report or the record
# it replaces>, or <set>:lost for a submission whose answer was lost, then <set>:lost2 and on, each spent
# once (logs/MORPHOMETRY-<set>.lost records them); one word, one more job (word_morphometry). The report
# it replaces is kept as logs/MORPHOMETRY-<set>-<job>.md, its last line saying where the files it names
# are now (morphometry_aside_note), and, where it ended 0, its rows and step logs under
# <morphometry root>/<set>/kept/<job>/ (morphometry_keep). A report that failed needs a word as one that
# ended 0 does, since any merge moves the checkout. enhance:40872077 and verse:40877151 are
# the owner's choice of 2026-10-30 14:33 UTC on the decision card "How many grid jobs for the morphometry
# rerun on the new engine?", "Three: enhance, verse, covariates": each set measured once more on the
# merged engine, now bordercall 9c85de1 with morphoview's lines (code stamp 1cee7ea83e4c28db with
# --lines; ee495d5's was a56adf14a9e98b15, where both reports name the 81e732f142d3aa16 of bordercall
# 16f7b40), then the join once more (COVARIATES_RERUNS).
# Held with the join's word above until the resynthesis, written on the owner's word of 2026-10-30
# 23:56 UTC (docs/research/morphometry-resynthesis.md).
MORPHOMETRY_RERUNS="enhance:40872077 verse:40877151"
# The owner's word for one more totalseg complete job, complete:<job of the report or the record it
# replaces>, or complete:lost for a submission whose answer was lost; one word, one more job (word_totalseg). complete:40882547 is his tap of 2026-10-30 16:49 UTC
# on "Fix and rerun (one GPU job)": the first job failed on every study it ran, before any segmenter
# drew, since tools/profile.py shadowed the standard library's profile (fixed in tools/gold3_totalseg_grid.py).
TOTALSEG_RERUNS="complete:40882547"
# A page of the join's report: the relay keeps the last 400 lines of a send's answer (grid_accounts.py's
# log_in) and status holds itself to 400 lines and 64 KiB, so a page is 300 of the report's lines with its
# first and last, each cut to LINE_CHARS by the masks, about 61,000 bytes at most, and the gate's own few
# lines around it. The report holds at most 822 lines of cells (each of the three members' 26 vertebra
# keys at 8 levels and the column, 234, and 5 disc keys at 7 disc levels and the column, 40;
# tools/gold3_covariates.py's MAX_CELL_LINES) and about 25 more, so it takes three sends.
COVARIATES_PAGE_LINES=300
LOGS=$REPO/grid/logs
STATE=$LOGS/GATE_JOBS.txt
WORDS="start status leaks v1 latency fetch explore dropzip unpack nodequota folders samples sweep bank experiment bench anomaly bordercall census totalseg realism autoanatomist morphometry literature stop cancel"
ENVS="default train-cpu train-gpu telemetry"

word=${1:-}
id=${2:-}
# Matched whole, so one argument holding two words ("v1 latency") is refused and never runs nothing.
case "$word" in
  start|status|leaks|v1|latency|fetch|explore|dropzip|unpack|nodequota|folders|samples|sweep|bank|experiment|bench|anomaly|bordercall|census|totalseg|realism|autoanatomist|morphometry|literature|stop|cancel) ;;
  "") echo "refusing: no word; one of: $WORDS"; exit 64 ;;
  *) echo "refusing: '$word' is not one of: $WORDS"; exit 64 ;;
esac
if [ "$word" = fetch ] || [ "$word" = explore ] || [ "$word" = dropzip ] || [ "$word" = unpack ] || [ "$word" = sweep ] || [ "$word" = bank ] || [ "$word" = bench ] || [ "$word" = anomaly ] || [ "$word" = bordercall ] || [ "$word" = census ] || [ "$word" = totalseg ] || [ "$word" = realism ] || [ "$word" = autoanatomist ] || [ "$word" = morphometry ] || [ "$word" = literature ]; then
  [ $# -eq 2 ] || { echo "refusing: $word takes exactly one id"; exit 64; }
  case "$id" in ""|*[!a-z0-9_]*) echo "refusing: an id is lower-case letters, digits and _"; exit 64 ;; esac
  [ ${#id} -le 40 ] || { echo "refusing: an id is at most 40 characters"; exit 64; }
elif [ "$word" = experiment ]; then
  [ $# -eq 2 ] || { echo "refusing: experiment takes exactly one issue number"; exit 64; }
  case "$id" in ""|*[!0-9]*|0*) echo "refusing: an issue is digits alone, with no leading zero"; exit 64 ;; esac
  [ ${#id} -le 9 ] || { echo "refusing: an issue is at most 9 digits"; exit 64; }
elif [ "$word" = cancel ]; then
  [ $# -eq 2 ] || { echo "refusing: cancel takes exactly one job"; exit 64; }
  case "$id" in ""|*[!0-9]*) echo "refusing: a job is digits alone"; exit 64 ;; esac
  [ ${#id} -le 12 ] || { echo "refusing: a job is at most 12 digits"; exit 64; }
else
  [ $# -eq 1 ] || { echo "refusing: $word takes no argument"; exit 64; }
fi
[ -d "$REPO/grid" ] || { echo "no $REPO/grid: the gate clones the repository there first"; exit 2; }
mkdir -p "$LOGS"
cd "$REPO/grid" || exit 2
# One word at a time: two starts sent together would each see no job of the other's yet.
exec 9> "$LOGS/gate.lock"
flock -w 60 9 || { echo "refusing: another gate word is still running"; exit 75; }
# The jobs and the scripts they start find pixi and the train-cpu python through the shims, which
# run them inside the container; the stages read PYDRV, the X-ray chain, the leaks and the ingest.
export PATH="$REPO/grid/bin:$PATH" SCHWINGNET="$REPO"
[ -z "$DATA_ROOT_GIVEN" ] || export DATA_ROOT
export PYDRV=$REPO/grid/bin/train-cpu-python
WHO=${USER:-$(id -un)}

# shellcheck source=grid/hpcw.sh
. "$REPO/grid/hpcw.sh"
# shellcheck source=grid/size-rule.sh
. "$REPO/grid/size-rule.sh"
# status still reads what it can without one (the logs of jobs queued before issue #77 among it)
[ "$word" = status ] || hpcw_bin > /dev/null || { echo "schwingnet $word: exit 2"; exit 2; }

commit=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)
echo "schwingnet $word${id:+ $id} at commit $commit on $(hostname) $(date -u '+%F %T') UTC"

record() {  # record ID WHAT: one line of the gate's own job list, the word with its id (fetch:<id>)
  echo "$1 $word${id:+:$id} $2 $(date -u '+%FT%TZ')" >> "$STATE"
  echo "  $2: job $1"
}
# Every deep learning job on the grid starts through flows/launch.py (the owner's rule of 2026-10-29):
# a GPU job's script must be one flows/registry.txt names in its fourth column, the job script that
# starts the launcher, so a word not yet moved onto a flow is refused here before anything is queued.
launched_script() {  # launched_script SCRIPT: status 0 where flows/registry.txt names SCRIPT as a flow's job script
  awk -v script="$1" '$1 !~ /^#/ && NF == 5 && $4 == script { found = 1 } END { exit !found }' "$REPO/flows/registry.txt" 2>/dev/null
}
script_of() {  # script_of ARGS...: the word after --, the job script a submit names
  while [ $# -gt 1 ] && [ "$1" != "--" ]; do shift; done
  [ "${1:-}" = "--" ] && echo "${2:-}"
}
submit() {  # submit WHAT CLASS [K=V...] [job submit options...] -- SCRIPT: the job id on stdout, the record on stderr
  local what=$1 out script
  script=$(script_of "$@")
  if [ "$2" = gpu ] && ! launched_script "$script"; then
    echo "  refusing: $what is a GPU job whose script ${script:-(none)} flows/registry.txt does not name, and every GPU job starts through flows/launch.py; it waits for its flow (flows/README.md); nothing was queued" >&2
    return 90
  fi
  out=$(hpcw_submit "$@" 2>&1) || { echo "  $out" >&2; return 1; }
  record "$out" "$what" >&2
  echo "$out"
}
gate_ids() {  # every job id the gate's list names, oldest first
  [ -f "$STATE" ] && awk '{ print $1 }' "$STATE"
}
QUEUED="" SQUEUE_ANSWERED="" NAMED=""
snapshot() {  # what Slurm holds for WHO, read once per word; a failed squeue refuses the word
  local out
  # Each line is a job's id and its name: the name finds a job whose submission's answer was lost,
  # which the gate's list never named (named_live).
  if ! out=$("$SQUEUE" -h -u "$WHO" -o '%i %j' 2>/dev/null); then
    echo "refusing: squeue failed, so the gate cannot tell which of its jobs are queued or running; send the word again"
    return 75
  fi
  QUEUED=" $(echo "$out" | awk '{ print $1 }' | sed 's/_.*//' | sort -u | tr '\n' ' ') " SQUEUE_ANSWERED=yes NAMED=$out
}
named_live() {  # named_live WHAT: the base ids of the live jobs Slurm holds under hpcworker's name for WHAT, schwingnet-WHAT, whatever the gate's list names
  printf '%s\n' "$NAMED" | awk -v what="$1" '$2 == "schwingnet-" what || $2 == what { sub(/_.*/, "", $1); print $1 }' | sort -u
}
live_ids() {  # the gate's jobs Slurm still holds, queued or running (an array as its base id)
  gate_ids | sort -u | while read -r job; do
    case "$QUEUED" in *" $job "*) echo "$job" ;; esac
  done
}
live_of() {  # live_of WHAT [FROM]: the newest live job the gate submitted for WHAT (from the word FROM)
  local job from what
  [ -f "$STATE" ] || return 0
  tac "$STATE" | while read -r job from what _; do
    if [ "$what" = "$1" ] && { [ -z "${2:-}" ] || [ "$from" = "$2" ]; }; then
      case "$QUEUED" in *" $job "*) echo "$job"; break ;; esac
    fi
  done
}
envs_ready() {  # the four environments exist and were made from this pixi.lock
  local env stamp
  for env in $ENVS; do [ -x "$REPO/.pixi/envs/$env/bin/python" ] || return 1; done
  stamp=$(cat "$REPO/.pixi/SETUP.sha256" 2>/dev/null)
  [ -n "$stamp" ] && [ "$stamp" = "$(sha256sum < "$REPO/pixi.lock" | cut -d' ' -f1)" ]
}
weights_ready() {  # the file is there and its job wrote the digest torchvision's name promises
  [ -s "$WEIGHTS" ] && grep -q '^f37072fd' "$WEIGHTS.sha256" 2>/dev/null
}
carmlspine_ready() {  # a train and a test shard of C-ArmLSpine are on the data root, as 00-carmlspine.sbatch reads it
  local kind
  for kind in train test; do
    grep -lqs "\"kind\": *\"$kind\"" "$DATA_ROOT"/carmlspine/shards/*/MANIFEST.json || return 1
  done
}
v1_version() {  # the catalog version the version 1 run would read now, as v1-driver.sbatch chooses it
  bash "$REPO/grid/v1-version.sh" "$STORE" "$DATA_ROOT" "$REPO" 2>/dev/null
}
ingest_failed_here() {  # the newest C-ArmLSpine ingest was refused at the commit the gate is at now
  local report=$LOGS/00-carmlspine-STAGE-REPORT.md
  [ "$commit" != unknown ] && [ -f "$report" ] || return 1
  head -n 1 "$report" | grep -q "commit $commit\$" && grep -qE 'refused|FAILED' "$report"
}
setup_dependency() {  # prints afterok:<setup job> unless the environments are ready
  local job
  envs_ready && return 0
  job=$(live_of setup)
  [ -n "$job" ] || job=$(submit setup batch -- 00-setup.sbatch) || return 1
  echo "afterok:$job"
}
joined() {  # joined DEP...: the non-empty dependencies, comma-separated
  local out="" one
  for one in "$@"; do [ -n "$one" ] && out=${out:+$out,}$one; done
  echo "$out"
}
depend_on() {  # depend_on DEPS: job submit's --after options for DEPS (sbatch's text) into opts, none when DEPS is empty
  # job submit adds --kill-on-invalid-dep=yes itself, so a dependency that can never be met ends the job
  hpcw_after "$1" || return 1
  opts=(${HPCW_AFTER[@]+"${HPCW_AFTER[@]}"})
}
last_line() {  # last_line PATTERN: the newest line of LAST_RUN.txt that holds PATTERN
  grep -- "$1" "$REPO/grid/LAST_RUN.txt" 2>/dev/null | tail -n 1
}
value_of() {  # value_of KEY LINE: the value of KEY=value in LINE
  echo "$2" | tr ' ' '\n' | sed -n "s/^$1=//p" | head -n 1
}
chain() {  # chain DEPEND [run-xray-chain.sh arguments...]: the X-ray chain after DEPEND, ids recorded
  local depend=$1 before after
  shift
  before=$(last_line ' fetch=')
  DEPEND=$depend CATALOG_DEPEND=${CATALOG_DEPEND:-} bash "$REPO/grid/run-xray-chain.sh" "$@" 2>&1 | sed 's/^/  /'
  [ "${PIPESTATUS[0]}" = 0 ] || return 1
  after=$(last_line ' fetch=')
  [ -n "$after" ] && [ "$after" != "$before" ] || { echo "  the X-ray chain wrote no new line to grid/LAST_RUN.txt"; return 1; }
  XR_FETCH=$(value_of fetch "$after"); XR_CATALOG=$(value_of catalog "$after")
  record "$XR_FETCH" xr_fetch; record "$(value_of bank "$after")" xr_bank; record "$XR_CATALOG" xr_catalog
}
checkout_holders() {  # afterany:<job> for every live job of the gate's that holds the checkout while it runs, comma-joined
  # A version 1 run, a sweep, an experiment run, a benchmark, an anomaly, bordercall, totalseg or realism stage and a morphometry set each write grid/logs/HOLD, one file
  # naming one job, and the first of two side by side to end would clear it while the other still
  # runs, whose end check then finds the checkout moved and throws the run away; so each waits for
  # the others, a sweep sent while a benchmark lasts up to its 12 hours among them. The DRR domain-gap
  # study's three jobs (bench_flexray_drr_gap, _shard, _merge) match too, though they run from a copy
  # of their code and hold no HOLD, so a run sent while the study lasts waits for it as it waited for
  # the study's one job before: bench flexray_drr_seg among them, which writes the masks it reads.
  # The morphometry join, morphometry_covariates, runs from git's copy of its code and holds none; its
  # interpreter is the checkout's train-cpu environment only where no other imports numpy and sqlite3.
  # A morphometry set whose submission's answer was lost holds it all the same, though the gate's list
  # never named its job, so that job is found as morphometry_lost_live finds it and waited for too.
  local job waits=""
  for job in $( { [ ! -f "$STATE" ] || awk '$3 == "v1_driver" || $3 == "sweep" || $3 ~ /^experiment_[0-9]+$/ || $3 ~ /^bench_[a-z_]+$/ || $3 ~ /^anomaly_[a-z_]+$/ || $3 ~ /^bordercall_[a-z]+$/ || $3 ~ /^totalseg_[a-z]+$/ || $3 ~ /^realism_[a-z]+$/ || ($3 ~ /^morphometry_[a-z]+$/ && $3 != "morphometry_covariates") { print $1 }' "$STATE"
                  morphometry_lost_live enhance; morphometry_lost_live verse; } | sort -u); do
    case "$QUEUED" in *" $job "*) waits=$(joined "$waits" "afterany:$job") ;; esac
  done
  echo "$waits"
}
v1_driver() {  # v1_driver DEPS: the version 1 run after DEPS and after every live run that holds the checkout
  local opts
  depend_on "$(joined "$1" "$(checkout_holders)")" || return 1
  # ${a[@]+"${a[@]}"}: the grid's bash 4.2 calls an empty array unbound under set -u
  submit v1_driver gpu RUNS="$RUNS" WEIGHTS="$WEIGHTS" ${opts[@]+"${opts[@]}"} --no-requeue -- v1-driver.sbatch >/dev/null
}

word_start() {
  local live setup weights_dep="" ingest first opts platform job name
  live=$(live_ids | wc -l)
  if [ "$live" -gt 0 ]; then
    echo "refusing: $live of the gate's jobs are still queued or running; 'status' lists them, 'stop' cancels them"
    return 75
  fi
  setup=$(setup_dependency) || return 1
  [ -n "$setup" ] || echo "  setup: the environments match pixi.lock; no job"
  if weights_ready; then
    echo "  weights: $WEIGHTS is there; no job"
  else
    job=$(submit weights batch MODELS="$MODELS" -- 00-weights.sbatch) || return 1
    weights_dep="afterok:$job"
  fi
  depend_on "$setup" || return 1
  ingest=$(submit carmlspine batch ${opts[@]+"${opts[@]}"} -- 00-carmlspine.sbatch) || return 1
  # The first catalog version: C-ArmLSpine and every shard already on the data root, built once the
  # ingest ends, so the version 1 run starts hours after it and not days after the X-ray fetch. The
  # X-ray chain's own catalog job builds the next version after it, once its banks are in.
  depend_on "$(joined "$setup" "afterany:$ingest")" || return 1
  first=$(submit catalog batch ${opts[@]+"${opts[@]}"} -- 03-catalog.sbatch) || return 1
  # X-ray before CT (the owner's order of 2026-10-21). The fetch waits on setup alone, since without
  # the environments every stage would fail; the chain's catalog waits on the first catalog too.
  XR_FETCH="" XR_CATALOG=""
  if CATALOG_DEPEND="afterany:$first" chain "$setup"; then
    # The CT platform chain after the X-ray fetch, so the X-ray sets take the network first. Each
    # job it printed is recorded, a refusal part-way or not, so 'stop' reaches every one.
    platform=$(DEPEND="afterany:$XR_FETCH" bash "$REPO/grid/run-platform-fetch.sh" 2>&1)
    [ $? = 0 ] || echo "  the platform fetch refused; the X-ray jobs stand"
    echo "$platform" | sed -n '/^Not submitted/q; p' | sed 's/^/  /'
    echo "$platform" | sed -n 's/^\([a-z0-9_]*\): job \([0-9][0-9]*\).*/\2 \1/p' | while read -r job name; do
      record "$job" "dp_$name"
    done
  else
    echo "  the X-ray chain was not submitted (above), so the CT platform chain is not either (X-ray before CT); 'stop', then 'start' again"
  fi
  # The probe reads what the sweeps are on disk with the node's own python3; it needs nothing above.
  # Its job id is read from what this call printed, never from LAST_LATENCY.txt, which an earlier
  # call may have left; a probe that was not submitted is said and start goes on without it.
  probed=$(bash "$REPO/grid/run-latency-sweep.sh" --probe 2>&1)
  probe_rc=$?
  echo "$probed" | sed 's/^/  /'
  if [ "$probe_rc" = 0 ]; then
    echo "$probed" | awk '$1 == "probe" && $2 ~ /^[0-9]+$/ { print $2 }' | while read -r job; do record "$job" probe; done
  else
    echo "  the probe was not submitted (exit $probe_rc, above); the rest of start goes on"
  fi
  # Version 1 needs C-ArmLSpine (its test part is the frozen persons), the first catalog with its
  # split check passed, the environments and the weights: afterok on each, so a failure cancels it.
  v1_driver "$(joined "afterok:$first" "afterok:$ingest" "$setup" "$weights_dep")" || {
    echo "  the version 1 run was not submitted (above); the jobs above stand, and 'v1' submits it alone after them"
    return 1
  }
  echo "submitted. 'status' follows them; 'leaks' once the catalog job has ended; 'latency' once the version 1 run has its checkpoint."
}

# status shows the end of the log of each of the gate's newest jobs that ended in one of these
# states (sacct's first word: "CANCELLED by <uid>" is CANCELLED), at most SHOWN_JOBS of them, two
# tasks of an array, TAIL_LINES lines each and LINE_CHARS characters a line.
FAILED_STATES=" FAILED TIMEOUT OUT_OF_MEMORY NODE_FAIL CANCELLED "
SHOWN_JOBS=6 ARRAY_TASKS=2 TAIL_LINES=15 SHAPE_LINES=400 LINE_CHARS=200
# The jobs whose logs hold nothing read from a patient's file, a person key or a sign-in, shown
# whole (masked): the container and the environments, and the public weights file. Every other
# job's log, any name not here among them, is shown only as shapes: the C-ArmLSpine ingest and the
# X-ray stages read DICOM headers and print person keys, the fetches run wget and curl with a
# sign-in, the probe prints the sweeps' file names, which carry case numbers, and the catalog, the
# leak checks, the latency jobs and the run print persons.
# Matched against what the gate recorded the job as (GATE_JOBS.txt), never the name Slurm shows.
OPEN_LOGS=" setup weights "
newest_jobs() {  # " <id> <id> ... ": the newest job the gate submitted for each thing it makes
  # Keyed by what was made, so a v1 that ran the ingest again hides start's failed one; an X-ray
  # job's key carries its word, so each fetch's chain is its own, and so does a sweep's, each plan's.
  echo " $(tac "$STATE" 2>/dev/null | awk '{ key = $3; if (key ~ /^xr_/ || key == "sweep") key = $2 " " key; if (!(key in seen)) { seen[key] = 1; print $1 } }' | tr '\n' ' ') "
}
what_of() {  # what_of ID: what the gate recorded job ID as
  awk -v j="$1" '$1 == j { what = $3 } END { print what }' "$STATE" 2>/dev/null
}
# sacct says a queued job is PENDING and no more, so a job that waits hours reads the same whether
# Slurm is waiting for a node to come free or will never start it under its partition's or QoS's
# limits; squeue's reason tells the two apart, and its expected start says how long the first is.
# The reason is the one field of the job list Slurm may write in words of its own, so it passes the
# same redaction as a log's lines; a row the redaction cuts short is dropped, never shown in part.
pending_reasons() {  # one squeue read of WHO's pending jobs: id|base id|reason|expected start per row, nothing where squeue does not answer
  "$SQUEUE" -h -u "$WHO" -t PENDING -o '%i|%r|%S' 2>/dev/null | LC_ALL=C tr -cd '\12\40-\176' | sed -r -f "$REPO/grid/redact.sed" \
    | awk -F'|' 'NF == 3 && $1 ~ /^[0-9]/ { base = $1; sub(/_.*/, "", base); print $1 "|" base "|" substr($2, 1, 80) "|" substr($3, 1, 19) }'
}
waiting_for() {  # waiting_for ID STATE PENDING: what a PENDING job waits for, as a tail for its sacct line, else nothing
  # An array split by Slurm, one task held or requeued apart from the rest, has a row for each part,
  # so the row of the same id comes first and its array's first row only where none has that id.
  [ "$2" = PENDING ] || return 0
  awk -F'|' -v job="$1" 'function tail(reason, start) {
      return ", waiting: " reason (start ~ /^[0-9][0-9][0-9][0-9]-/ ? ", start expected " start " grid time" : "") }
    $3 == "" { next }
    $1 == job { exact = tail($3, $4); exit }
    { base = job; sub(/_.*/, "", base) }
    $2 == base && first == "" { first = tail($3, $4) }
    END { print (exact != "" ? exact : first) }' <<< "$3"
}
masked() {  # every line status shows of a log or a stage report: masked, then cut
  sed -r -f "$REPO/grid/redact.sed" | cut -c "1-$LINE_CHARS"
}
report_shapes() {  # a stage report's lines with their paths cut and a quoting reason withheld
  awk -v data="$DATA_ROOT" -v runs="$RUNS" -v models="$MODELS" -v repo="$REPO" \
    -f "$REPO/grid/shape-words.awk" -f "$REPO/grid/report-shapes.awk"
}
printable() {  # the last 64 KiB of stdin as lines of printable ASCII
  tail -c 65536 | tr '\r' '\n' | LC_ALL=C tr -cd '\11\12\40-\176'
}
log_text() {  # log_text ID TASK NAME: the end of a job's output, or nothing when there is none
  local id=$1 task=$2 name=$3 out old
  # hpcworker's log of the job, which job submit wrote (issue #77)
  if out=$(hpcw log --project "$HPCW_PROJECT" "$id" ${task:+--task "$task"} --lines "$SHAPE_LINES" 2>/dev/null) \
    && [ -n "$out" ] && [[ $out != "HPCW-JOB no output yet"* ]]; then
    printf '%s\n' "$out" | printable
    return 0
  fi
  # a job sbatch queued before then wrote logs/<Slurm's name>_<id>.out (_<task> for an array task;
  # _4294967294, Slurm's NO_VAL, for a job that is no array but whose script named its log %x_%A_%a)
  [[ $name =~ ^[A-Za-z0-9_.-]+$ ]] || return 0
  for old in "$LOGS/${name}_$id${task:+_$task}.out" "$LOGS/${name}_${id}_4294967294.out"; do
    [ -f "$old" ] && { printable < "$old"; return 0; }
  done
}
log_tail() {  # log_tail WHAT: a failed job's log on stdin, its end whole for an open job, as shapes otherwise
  local kept withheld
  case "$OPEN_LOGS" in
    *" $1 "*) tail -n "$TAIL_LINES" | masked | sed 's/^/    /'; return ;;
  esac
  kept=$(tail -n "$SHAPE_LINES" | awk -f "$REPO/grid/shape-words.awk" -f "$REPO/grid/log-shapes.awk")
  withheld=$(echo "$kept" | sed -n 's/^#withheld \([0-9][0-9]*\)$/\1/p' | tail -n 1)
  echo "$kept" | grep -v '^#withheld ' | tail -n "$TAIL_LINES" | masked | sed 's/^/    /'
  echo "    (${withheld:-0} of its last $SHAPE_LINES lines withheld: this job can print DICOM header values, person keys or a sign-in, so only its tracebacks and status lines are shown; the whole log stays on the grid)"
}
failed_tails() {  # failed_tails SACCT: the end of the log of each newest job that failed
  local newest shown=0 more=0 tasks="" job name state elapsed code node base task end what text
  newest=$(newest_jobs)
  while IFS='|' read -r job name state elapsed code node; do
    base=${job%%_*} end=${state%% *}
    case "$newest" in *" $base "*) ;; *) continue ;; esac
    case "$FAILED_STATES" in *" $end "*) ;; *) continue ;; esac
    if [ "$base" != "$job" ]; then
      [ "$(echo "$tasks" | tr ' ' '\n' | grep -cx "$base")" -lt "$ARRAY_TASKS" ] || continue
      tasks="$tasks $base"
    fi
    [ "$shown" -lt "$SHOWN_JOBS" ] || { more=$((more + 1)); continue; }
    shown=$((shown + 1))
    if ! [[ $job =~ ^[0-9]+(_[0-9]+)?$ ]]; then
      echo "## $base ended $end; no log can be named from what sacct gave"; continue
    fi
    task=""; [ "$base" = "$job" ] || task=${job#*_}
    what=$(what_of "$base")
    echo "## $job (${what:-unrecorded}) ended $end after $elapsed, exit $code"
    text=$(log_text "$base" "$task" "$name")
    if [ -n "$text" ]; then
      printf '%s\n' "$text" | log_tail "$what"
    elif [ "$end" = CANCELLED ]; then
      echo "    cancelled before it started (a job it waited on failed, or 'stop'); no log"
    else
      echo "    no log of it yet"
    fi
  done <<< "$1"
  [ "$more" = 0 ] || echo "## $more more failed jobs not shown; their logs stay on the grid"
}

probe_text() {  # a heading line, then the newest latency probe's output; nothing when there is none
  # Since issue #77 the probe (latency_probe) logs to hpcworker's folder, read by its recorded id; a
  # probe sbatch queued before then left grid/logs/sn_probe_<id>_4294967294.out, read when no
  # recorded probe has output.
  local id out probe
  id=$(awk '$3 == "probe" { job = $1 } END { print job }' "$STATE" 2>/dev/null)
  if [ -n "$id" ] && out=$(log_text "$id" "" sn_probe) && [ -n "$out" ]; then
    echo "## the latency probe: job $id"
    printf '%s\n' "$out"
    return 0
  fi
  probe=$(ls -1t "$LOGS"/sn_probe_*.out 2>/dev/null | head -n 1)
  [ -n "$probe" ] || return 0
  echo "## the latency probe: $(basename "$probe") ($(date -r "$probe" '+%F %T'))"
  cat "$probe"
}
latency_lines() {  # the newest run's parity, latency and sweep numbers, one line a file (#99)
  local run file files=()
  run=$(ls -1dt "$RUNS"/*/ 2>/dev/null | head -n 1)
  [ -n "$run" ] || return 0
  for file in "$run"onnx/parity-*.json "$run"latency/*.json "$run"evaluate/latency.json "$run"sweep/*/summary.json; do
    [ -f "$file" ] && files+=("$file")
  done
  [ ${#files[@]} -gt 0 ] || return 0
  # Handed the page's room before the stage reports (grid/status-page.awk), so they never cut it off.
  echo "## latency of the newest run, $(basename "$run")"
  awk -f "$REPO/grid/latency-lines.awk" "${files[@]}" | masked | sed 's/^/  /'
}

# The owner's tally of the lab volume (2026-10-22: "keep a tally of how much space ive used on ceph
# oschome"), so he chooses which sets stay on it at once and cycles the rest in and out. CephFS keeps
# each folder's recursive size as the attribute ceph.dir.rbytes, read at once whatever the tree
# holds, so no du walks millions of files; where the attribute is not there the size reads unknown.
rbytes_of() {  # the size rule's own reading (grid/size-rule.sh), read whole, so a value with a NUL or that is no count reads unknown
  xattr_whole ceph.dir.rbytes "$1"
}
gb_of() {  # whole GB, rounded up, of a byte count
  awk -v b="$1" 'BEGIN { printf "%d", (b + 999999999) / 1000000000 }'
}
space_lines() {  # one folder's sets, largest first: GB and the set's folder name
  local root=$1 one bytes
  for one in "$root"/*/; do
    [ -d "$one" ] || continue
    bytes=$(rbytes_of "${one%/}")
    if [ -n "$bytes" ]; then echo "$(gb_of "$bytes") $(basename "$one")"; else echo "? $(basename "$one")"; fi
  done | sort -k1,1nr
}
word_space() {
  local root label bytes
  # Labels, never paths: status leaves the grid, and its answer names no folder of the volume.
  echo "## space on the lab volume (CephFS ceph.dir.rbytes; GB rounded up)"
  # The room under the quota as the size rule reads it (grid/size-rule.sh, #160), never df, which on
  # CephFS reports the whole Ceph pool: 5,881,937 GB free on 2026-10-23 under a quota of 21,991 GB.
  DATA=$DATA_ROOT quota_readout "$VOLUME" "Lab Volume Disk Usage (CephFS quota; 1 gb = 10^9 bytes)" | sed 's/^/  /'
  for label in "data" "shared datasets"; do
    if [ "$label" = data ]; then root=$DATA_ROOT; else root=$SHARED_DATA; fi
    [ -d "$root" ] || { echo "  $label: not there"; continue; }
    bytes=$(rbytes_of "$root")
    if [ -n "$bytes" ]; then echo "  $label: $(gb_of "$bytes") GB in all"; else echo "  $label: ? GB in all"; fi
    space_lines "$root" | head -n 80 | sed 's/^/    /'
  done
}

samples_report() {  # the sample index's manifest, whole: counts per source and nothing else
  # (tools/sample_index.py), read up to the 180 lines run-samples.sh's report gives. Status's 400
  # lines once cut it off, after the jobs, and masked's 200 characters cut its widest rows, the
  # bank root that a dozen X-ray sources share, so the rows are folded, not cut, after the masks.
  # A root the manifest and the registry leave unmapped is named by its folder under the data
  # root, which the report's own path cuts show too; written "unmapped <folder>" here, since
  # redact.sed withholds "<word>:<value>" as a person key.
  local report=$LOGS/SAMPLES-STAGE-REPORT.md
  [ -f "$report" ] || return 0
  echo "## SAMPLES-STAGE-REPORT.md ($(date -r "$report" '+%F %T'))"
  head -n 180 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | sed 's/unmapped:/unmapped /g' \
    | report_shapes | sed -r -f "$REPO/grid/redact.sed" | fold -w $((LINE_CHARS - 10)) | sed 's/^/  /'
}

attr_digits() {  # attr_digits NAME FOLDER: one CephFS attribute's leading digits up to its first NUL, or nothing
  # Leading digits, since ceph.dir.rctime is seconds and nanoseconds; as a count only, as the size
  # rule takes one (is_count), since an age is worked out from them in bash's arithmetic.
  local digits
  digits=$(xattr_value "$1" "$2" | sed -n 's/^\([0-9][0-9]*\).*/\1/p')
  if is_count "$digits"; then echo "$digits"; fi
}
fetch_progress() {  # one line per live fetch of one set: what its raw folder holds, read with no walk
  # A fetch runs for hours and status shows a job's log only once it has ended, so until this nobody
  # could tell a slow fetch from a stalled one without a grid shell (#125). CephFS keeps each
  # folder's recursive file count, size and newest change as attributes, three reads on the login
  # node in place of a find over thousands of files, and no file name leaves the grid.
  local job from what id raw files bytes written now age seen=" "
  [ -f "$STATE" ] || return 0
  now=$(date -u +%s)
  tac "$STATE" | while read -r job from what _; do
    [ "$what" = xr_fetch ] || continue
    case "$from" in fetch:*) id=${from#fetch:} ;; *) continue ;; esac
    case "$QUEUED" in *" $job "*) ;; *) continue ;; esac
    case "$seen" in *" $id "*) continue ;; esac
    seen="$seen$id "
    raw=$DATA_ROOT/$id/raw
    [ -d "$raw" ] || { echo "  fetch of $id (job $job): nothing landed yet"; continue; }
    files=$(attr_digits ceph.dir.rfiles "$raw"); bytes=$(attr_digits ceph.dir.rbytes "$raw"); written=$(attr_digits ceph.dir.rctime "$raw")
    if [ -z "$files" ] || [ -z "$bytes" ] || [ -z "$written" ]; then
      echo "  fetch of $id (job $job): the raw folder is there; its size is not readable here (no CephFS attributes)"
      continue
    fi
    age=$((now - written))
    if [ "$age" -lt 120 ]; then age="${age}s ago"
    elif [ "$age" -lt 7200 ]; then age="$((age / 60)) min ago"
    else age="$((age / 3600)) h ago"; fi
    echo "  fetch of $id (job $job): $files files, $(( (bytes + 999999) / 1000000 )) MB, last write $age"
  done
}

# What reaches the gate of status is one page of 400 lines and 64 KiB at most, and its sections
# together can hold twice that on the grid. Each is made whole (status_sections) and then handed
# the page's room in the order a reader needs it (grid/status-page.awk): the space, the sweeps'
# progress, the newest jobs and the failed jobs' logs come first, the stage reports and the sample
# manifest after them, newest first, so the manifest, which changes only when a census runs, never
# pushes the newest jobs, a failed job's log or the newest stage report off the page; a section
# cut short says so, and one left out is named on the page's last line.
STATUS_LINES=400 STATUS_BYTES=65536
word_status() {
  local newer
  # The manifest is handed its room among the stage reports by its date, after those newer than it.
  newer=$(ls -1t "$LOGS"/*STAGE-REPORT.md 2>/dev/null | awk '/\/SAMPLES-STAGE-REPORT\.md$/ { print NR - 1; exit }')
  status_sections | LC_ALL=C awk -v lines="$STATUS_LINES" -v bytes="$STATUS_BYTES" -v samples_after="${newer:-0}" \
    -f "$REPO/grid/status-page.awk"
}
status_sections() {  # every section of status whole, in the order the page shows them
  local ids run lines job name state elapsed code node probe pending
  # The space first and the sweeps' progress, the one live view of a sweep, after it, then each
  # benchmark's, the DRR domain-gap study's while its shards run, and each launched flow's page in
  # short lines; then the sample manifest, which
  # once came after the jobs, where the page's end cut it.
  word_space
  sweep_progress | head -n "$SWEEP_LINES_SHOWN"
  bench_progress
  flow_progress
  samples_report
  ids=$(gate_ids | tail -n 60 | tr '\n' ',' | sed 's/,$//')
  if [ -z "$ids" ]; then
    echo "no job submitted by the gate yet; 'start' submits the graph"
  else
    echo "## the gate's newest jobs (sacct): id, what, state, elapsed, exit code, node, and what a pending job waits for (squeue)"
    lines=$("$SACCT" -X -n -P -j "$ids" --format=JobID,JobName,State,Elapsed,ExitCode,NodeList 2>/dev/null)
    # squeue is asked for reasons only where the word's own read of it answered and a job waits,
    # so a slow scheduler costs status no second timeout and a quiet list no extra call.
    pending=""
    if [ -n "$SQUEUE_ANSWERED" ] && [[ "$lines" == *"|PENDING|"* ]]; then pending=$(pending_reasons); fi
    while IFS='|' read -r job name state elapsed code node; do
      [ -n "$job" ] || continue
      echo "  $job $(what_of "${job%%_*}") $state $elapsed $code $node$(waiting_for "$job" "$state" "$pending")"
    done <<< "$lines"
    fetch_progress
    failed_tails "$lines"
  fi
  # The latency probe's answer (#87): counts, sizes, PNG dimensions and the export's meta keys only,
  # never a DICOM header; only its own lines' shapes, with no folder or file name
  # (grid/probe-shapes.awk), then masked (#80).
  probe=$(probe_text)
  if [ -n "$probe" ]; then
    printf '%s\n' "$probe" | head -n 1
    printf '%s\n' "$probe" | tail -n +2 | head -n 40 | LC_ALL=C tr -cd '\11\12\40-\176' \
      | awk -f "$REPO/grid/probe-shapes.awk" | masked | sed 's/^/  /'
  fi
  latency_lines
  # Newest first, the order they are handed the page's room in, so a sweep's or a run's report from
  # today comes before a stage's from last week.
  ls -1t "$LOGS"/*STAGE-REPORT.md 2>/dev/null | while read -r report; do
    [ -f "$report" ] || continue
    [ "$(basename "$report")" != SAMPLES-STAGE-REPORT.md ] || continue
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    tail -n 12 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | report_shapes | masked | sed 's/^/  /'
  done
  run=$(ls -1dt "$RUNS"/*/ 2>/dev/null | head -n 1)
  if [ -n "$run" ]; then
    echo "## newest run: $run"
    if [ -f "$run/train/checkpoint.json" ]; then echo "  checkpoint: training finished (train/checkpoint.json)"
    elif [ -f "$run/train/best.pt" ]; then echo "  checkpoint: not yet; training has kept a best epoch but has not finished"
    else echo "  checkpoint: not yet"; fi
    [ -f "$run/wandb-sync.json" ] && grep -o 'https://wandb\.ai/[^" ]*' "$run/wandb-sync.json" | sort -u | sed 's/^/  W\&B /' | head -n 4
    [ -f "$run/evaluate/results.md" ] && head -n 30 "$run/evaluate/results.md" | sed 's/^/  /'
  fi
}

# A plan's section is its heading, its headline, up to SWEEP_ROWS_SHOWN rows, the line counting the
# rest and up to SWEEP_WANDB_SHOWN links, 27 lines; the four plans of grid/sweeps/ take 108 of the
# section's 120, and the space tally before it at most about 180, so both fit inside status's 400
# with room left for the job list, which is handed lines right after them (grid/status-page.awk).
SWEEP_ROWS_SHOWN=20 SWEEP_WANDB_SHOWN=4 SWEEP_LINES_SHOWN=120
smoke_paths() {  # every line with the smoke folder's path cut to <smoke>, matched as text and not as a pattern
  awk -v smoke="$SMOKE" '{
    while (smoke != "" && (at = index($0, smoke)) > 0) $0 = substr($0, 1, at - 1) "<smoke>" substr($0, at + length(smoke))
    print }'
}
progress_lines() {  # progress_lines FILE: a sweep's PROGRESS.txt as status shows it
  # Its headline, the rows that have not matched their prediction yet (failed, mismatched or still
  # to come; the rows that matched are counted on the headline) and its W&B links. tools/block_sweep.py
  # writes the file whole and renames it into place, so it never reads half written.
  # A refused or failed row ends with its code and, after "why:", the last words the tools wrote of
  # it, which can quote a run's folder, a frame's file name or a run's id: each row shown is judged
  # as a stage report's line is (report_shapes), its paths cut and that reason withheld unless it
  # holds no value, while the code before it stays. The headline and the W&B links are the sweep's
  # own words and are left whole, the links so that they still open.
  local unmatched count
  head -n 1 "$1"
  unmatched=$(tail -n +2 "$1" | awk '$1 == "row" && ($3 == "failed" || $3 == "to-come" || $3 == "to_come" ||
                                                    $4 == "no" || $4 == "false" || $4 == "mismatched")')
  count=$(printf '%s' "$unmatched" | grep -c '^row ')
  [ -z "$unmatched" ] \
    || printf '%s\n' "$unmatched" | head -n "$SWEEP_ROWS_SHOWN" | LC_ALL=C tr -cd '\11\12\40-\176' | report_shapes
  [ "$count" -le "$SWEEP_ROWS_SHOWN" ] \
    || echo "($((count - SWEEP_ROWS_SHOWN)) more rows not yet matched; the state folder's PROGRESS.txt holds them)"
  tail -n +2 "$1" | awk '$1 == "wandb"' | head -n "$SWEEP_WANDB_SHOWN"
}
sweep_progress() {  # for each plan under SMOKE, its newest sweep's PROGRESS.txt (issue #252)
  local plan progress
  for plan in "$SMOKE"/*/; do
    [ -d "$plan" ] || continue
    # A state folder is one that holds PROGRESS.txt, so the synthetic plan's catalog beside them is passed over.
    progress=$(ls -1t "$plan"*/PROGRESS.txt 2>/dev/null | head -n 1)
    [ -n "$progress" ] || continue
    echo "## sweep $(basename "$plan"), $(basename "$(dirname "$progress")") ($(date -r "$progress" '+%F %T'))" \
      | LC_ALL=C tr -cd '\11\12\40-\176' | masked
    progress_lines "$progress" | LC_ALL=C tr -cd '\11\12\40-\176' | smoke_paths | masked | sed 's/^/  /'
  done
}

# A benchmark whose tool keeps <name>/PROGRESS.txt under BENCH_ROOT, the DRR domain-gap study's
# (grid/drr-gap.sbatch), shows it here while it runs: the study's one live view from outside the
# grid, as a sweep's is, at most BENCH_PROGRESS_LINES short lines of counts and group ids, each masked.
BENCH_PROGRESS_LINES=60
bench_progress_of() {  # bench_progress_of NAME: one benchmark's PROGRESS.txt as status shows it, its heading and its first lines, masked
  local progress=$BENCH_ROOT/$1/PROGRESS.txt
  [ -f "$progress" ] || return 0
  echo "## bench $1, progress ($(date -r "$progress" '+%F %T'))" | LC_ALL=C tr -cd '\11\12\40-\176' | masked
  head -n "$BENCH_PROGRESS_LINES" "$progress" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | sed 's/^/  /'
}
bench_progress() {  # every benchmark under BENCH_ROOT that keeps a PROGRESS.txt, by its folder's name
  local folder name
  for folder in "$BENCH_ROOT"/*/; do
    name=$(basename "$folder")
    # A benchmark's folder is named by its id; any other name is no benchmark's and is passed over.
    case "$name" in ""|*[!a-z0-9_]*) continue ;; esac
    # The DRR study's folder is DRR_GAP_FOLDER; an earlier run's folder keeps its last PROGRESS.txt,
    # which is no live view, and is passed over.
    case "$name" in flexray_drr_gap|flexray_drr_gap_run*) [ "$name" = "$DRR_GAP_FOLDER" ] || continue ;; esac
    bench_progress_of "$name"
  done
}

# Every run flows/launch.py starts keeps its progress page, and the page in short lines, PROGRESS.txt,
# under FLOW_ROOT/progress/<Flow>/<run>/ (flows/stage_progress.py, the owner's rule of 2026-10-29).
# Status shows FLOW_RUNS_SHOWN runs' lines (flow_runs_chosen says which), each under a heading naming the run's kind
# and id, which tools/progress_page.py reads back into the same page off the grid. The page's own
# lines are the flow's words; a task's last line and a report's can quote a path or a value, so those
# are judged as a stage report's lines are (report_shapes), and every line is masked. The writer puts
# how the run ended, its verdict and its reports, right after the two head lines and shows a few tasks
# of each step, so a whole smoke plan's run fits in FLOW_PROGRESS_LINES; the cut is only a bound.
# The file's own word is written while the run still moves, and nothing draws a dead job's page
# again, so status judges silence as it prints: a run the file calls running that has not moved for
# FLOW_SILENT_SECONDS (stage_progress.SILENT_SECONDS) is shown silent, with a line saying so.
FLOW_RUNS_SHOWN=4 FLOW_PROGRESS_LINES=40 FLOW_SILENT_SECONDS=600
flow_shapes() {  # a flow's progress lines, its tasks' and its reports' judged as a stage report's
  local line
  while IFS= read -r line; do
    case "$line" in
      "task "*|"report: "*) printf '%s\n' "$line" | report_shapes ;;
      *) printf '%s\n' "$line" ;;
    esac
  done
}
flow_lines() {  # flow_lines FILE: its first FLOW_PROGRESS_LINES lines, a running run judged silent by the file's age
  local progress=$1 moved now first=""
  moved=$(date -u -r "$progress" +%s 2>/dev/null) now=$(date -u +%s)
  # The head is read without a pipe: grep -q ending early would fail head under pipefail.
  IFS= read -r first < "$progress" || true
  case "$first" in
    "flow "*": running, started "*)
      if [ -n "$moved" ] && [ $((now - moved)) -gt "$FLOW_SILENT_SECONDS" ]; then
        printf '%s\n' "${first/: running, started /: silent, started }"
        echo "silent: no file of this run has moved for $(( (now - moved) / 60 )) minutes by this status; a job Slurm ended writes nothing more, and a resume is a new run"
        sed -n "2,$((FLOW_PROGRESS_LINES - 1))p" "$progress"
        return
      fi ;;
  esac
  head -n "$FLOW_PROGRESS_LINES" "$progress"
}
flow_progress() {  # the newest runs of every launched flow, each its PROGRESS.txt as status shows it
  local progress run kind
  flow_runs_chosen
  printf '%s\n' ${FLOW_SHOWN[@]+"${FLOW_SHOWN[@]}"} | while read -r progress; do
    [ -f "$progress" ] || continue
    run=$(basename "$(dirname "$progress")")
    kind=$(head -n 1 "$progress" | awk '$1 == "flow" { sub(/:$/, "", $3); print $3 }')
    case "$run" in ""|*[!A-Za-z0-9_.-]*) continue ;; esac
    case "$kind" in ""|*[!a-z0-9_]*) kind=unknown ;; esac
    echo "## flow $kind $run, progress ($(date -u -r "$progress" '+%F %H:%M') UTC)"
    flow_lines "$progress" | LC_ALL=C tr -cd '\11\12\40-\176' | flow_shapes | masked | sed 's/^/  /'
  done
  flow_kinds_left
}

# Which runs status shows: the newest run of each kind, the kinds whose newest run moved last first,
# then the newest of the rest, FLOW_RUNS_SHOWN in all and shown newest first, so that the DRR
# domain-gap study's 18 runs a chain (prepare, 16 shard tasks, the merge), whose own PROGRESS.txt
# the bench progress shows, never push another kind's newest run out. A kind whose newest run has
# no room among them is named on one line of its own under "## flow kinds not shown", which the page
# hands room after the job list and the failed jobs' logs (grid/status-page.awk), so the flows'
# sections stay FLOW_RUNS_SHOWN however many kinds have run. The files are read by the shell alone,
# with no process for each run, since the progress folder keeps every run there has been.
FLOW_HEAD='^flow [^ ]+ ([^ ]+): ([a-z]+)'
FLOW_KIND="" FLOW_STATE="" FLOW_SHOWN=() FLOW_LEFT=()
flow_kind_of() {  # flow_kind_of PROGRESS: the kind and the state its first line names, into FLOW_KIND and FLOW_STATE, each unknown where it names none
  local first=""
  FLOW_KIND=unknown FLOW_STATE=unknown
  read -r first 2>/dev/null < "$1"
  [[ "$first" =~ $FLOW_HEAD ]] || return 0
  case "${BASH_REMATCH[1]}" in *[!a-z0-9_]*) ;; *) FLOW_KIND=${BASH_REMATCH[1]} ;; esac
  FLOW_STATE=${BASH_REMATCH[2]}
}
flow_runs_chosen() {  # the PROGRESS.txt files status shows into FLOW_SHOWN, newest first, and a line for each kind left out into FLOW_LEFT
  local files=() kinds=() chosen=() seen=" " count=0 i run
  FLOW_SHOWN=() FLOW_LEFT=()
  mapfile -t files < <(ls -1t "$FLOW_ROOT"/progress/*/*/PROGRESS.txt 2>/dev/null)
  for i in ${files[@]+"${!files[@]}"}; do
    run=${files[$i]%/PROGRESS.txt}; run=${run##*/}
    [ -f "${files[$i]}" ] || continue
    case "$run" in ""|*[!A-Za-z0-9_.-]*) continue ;; esac
    flow_kind_of "${files[$i]}"
    kinds[$i]=$FLOW_KIND
    case "$seen" in *" $FLOW_KIND "*) continue ;; esac
    seen="$seen$FLOW_KIND "
    if [ "$count" -lt "$FLOW_RUNS_SHOWN" ]; then
      chosen[$i]=1
      count=$((count + 1))
    else
      FLOW_LEFT+=("$FLOW_KIND $run: $FLOW_STATE ($(date -u -r "${files[$i]}" '+%F %H:%M') UTC)")
    fi
  done
  for i in ${kinds[@]+"${!kinds[@]}"}; do
    [ "$count" -lt "$FLOW_RUNS_SHOWN" ] || break
    [ -z "${chosen[$i]:-}" ] || continue
    chosen[$i]=1
    count=$((count + 1))
  done
  for i in ${chosen[@]+"${!chosen[@]}"}; do FLOW_SHOWN+=("${files[$i]}"); done
}
flow_kinds_left() {  # one line for each kind whose newest run flow_runs_chosen had no room for, its run, its state and when its file last moved
  [ "${#FLOW_LEFT[@]}" -gt 0 ] || return 0
  echo "## flow kinds not shown, for want of room among the newest $FLOW_RUNS_SHOWN: each kind's newest run, its state and when it last moved"
  printf '%s\n' "${FLOW_LEFT[@]}" | masked | sed 's/^/  /'
}

word_leaks() {
  local busy line
  busy=$( { live_of carmlspine; live_of catalog; live_of xr_bank; live_of xr_catalog; } | tr '\n' ' ')
  if [ -n "${busy// /}" ]; then
    echo "refusing: an ingest or the catalog is still queued or running (jobs $busy); the leak checks read every shard once they end"
    return 75
  fi
  busy=$( { live_of leaks_fingerprint; live_of leaks_join; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: the leak checks are still queued or running (jobs $busy)"; return 75; }
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  CONCURRENCY=${CONCURRENCY:-32} bash "$REPO/grid/run-leaks.sh" 2>&1 | sed 's/^/  /'
  [ "${PIPESTATUS[0]}" = 0 ] || return 1
  line=$(last_line ' leaks fingerprint=')
  record "$(value_of fingerprint "$line")" leaks_fingerprint
  record "$(value_of join "$line")" leaks_join
}

word_v1() {
  local running setup opts ingest catalog ingest_dep="" catalog_dep="" weights_dep="" job version
  running=$(live_of v1_driver)
  [ -z "$running" ] || { echo "refusing: the version 1 run is already queued or running (job $running)"; return 75; }
  # Each input of the run is there, made by a live job of the gate's (start's or an earlier v1's),
  # or submitted now, so v1 runs again what failed while start's X-ray and CT jobs are still live,
  # which start refuses to while any of them is (issue #80). The run waits afterok on each input
  # still to come, so one that fails again cancels it rather than leaving it to fail on the GPU.
  setup=$(setup_dependency) || return 1
  job=$(live_of weights)
  if [ -n "$job" ]; then
    weights_dep="afterok:$job"
  elif weights_ready; then
    echo "  weights: $WEIGHTS is there; no job"
  else
    job=$(submit weights batch MODELS="$MODELS" -- 00-weights.sbatch) || return 1
    weights_dep="afterok:$job"
  fi
  # C-ArmLSpine's train and test shards: its test part is the frozen persons the run is measured on.
  ingest=$(live_of carmlspine)
  if [ -n "$ingest" ]; then
    ingest_dep="afterok:$ingest"
  elif carmlspine_ready; then
    echo "  carmlspine: a train and a test shard are under $DATA_ROOT/carmlspine/shards; no job"
  else
    if ingest_failed_here; then
      echo "  carmlspine: the last ingest was refused at this same commit $commit (logs/00-carmlspine-STAGE-REPORT.md);"
      echo "    it is submitted again and will fail the same way unless its bank changed; 'status' shows why it failed"
    fi
    depend_on "$setup" || return 1
    ingest=$(submit carmlspine batch ${opts[@]+"${opts[@]}"} -- 00-carmlspine.sbatch) || return 1
    ingest_dep="afterok:$ingest"
  fi
  # A catalog version the run may read (grid/v1-version.sh): one there already, the gate's live catalog job
  # when it was submitted after a live ingest (start's and v1's always are), or a new build. The
  # build waits afterok on an ingest still to come, unlike start's, so a failed ingest cancels it
  # and no version without C-ArmLSpine is made for this run. The X-ray chain's xr_catalog jobs
  # are never waited on: they wait on fetches that take days.
  catalog=$(live_of catalog)
  if [ -n "$ingest_dep" ] && [ -n "$catalog" ] && [ "$catalog" -gt "$ingest" ]; then
    catalog_dep="afterok:$catalog"
  elif [ -z "$ingest_dep" ] && version=$(v1_version); then
    echo "  catalog: $version qualifies for the run (grid/v1-version.sh); no job"
  elif [ -z "$ingest_dep" ] && [ -n "$catalog" ]; then
    catalog_dep="afterok:$catalog"
  else
    depend_on "$(joined "$setup" "$ingest_dep")" || return 1
    catalog=$(submit catalog batch ${opts[@]+"${opts[@]}"} -- 03-catalog.sbatch) || return 1
    catalog_dep="afterok:$catalog"
  fi
  v1_driver "$(joined "$catalog_dep" "$ingest_dep" "$weights_dep" "$setup")"
}

word_latency() {
  local run version catalog busy rc said
  busy=$( { live_of latency_gpu; live_of latency_cpu; live_of latency_sweep; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: latency jobs are still queued or running (jobs $busy)"; return 75; }
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  run=$(for one in $(ls -1dt "$RUNS"/*/ 2>/dev/null); do
          # train.py keeps best.pt from the first epoch on and writes checkpoint.json only when it
          # has finished, which the latency tools need, so a run still training is passed over
          [ -f "$one/RUN.json" ] && [ -f "$one/train/checkpoint.json" ] && [ -f "$one/train/best.pt" ] && { echo "${one%/}"; break; }
        done)
  [ -n "$run" ] || { echo "refusing: no run under $RUNS has finished training yet (RUN.json, train/checkpoint.json and train/best.pt)"; return 2; }
  version=$(sed -n 's/.*"catalog_version": *\([0-9][0-9]*\).*/\1/p' "$run/RUN.json" | head -n 1)
  [ -n "$version" ] || { echo "refusing: $run/RUN.json names no catalog_version"; return 2; }
  catalog=$(ls -1 "$STORE/versions/catalog-$(printf '%06d' "$version")-"*.sqlite 2>/dev/null | head -n 1)
  [ -n "$catalog" ] || { echo "refusing: catalog version $version is not under $STORE/versions"; return 2; }
  echo "  run: $run; catalog: $catalog"
  said=$(bash "$REPO/grid/run-latency-sweep.sh" --catalog "$catalog" "$run" --sweep "case134:bank=$SWEEP_BANK" 2>&1)
  rc=$?
  echo "$said" | sed 's/^/  /'
  # Every job this call submitted is recorded, a refusal part-way or not, so 'stop' reaches it; the
  # ids come from what this call printed, never from LAST_LATENCY.txt, which an earlier call may have left.
  echo "$said" | awk '($1 == "gpu" || $1 == "cpu" || $1 == "sweep") && $NF ~ /^[0-9]+$/ { print $NF, "latency_" $1 }' \
    | while read -r job what; do record "$job" "$what"; done
  [ "$rc" = 0 ] || return 1
}

fetch_section() {  # fetch_section ID: open or credentialed, the section of grid/fetch-xray.json that names ID, or nothing
  awk -v id="$1" '
    /"credentialed": \[/ { cred = 1 }
    index($0, "\"id\": \"" id "\"") { print (cred ? "credentialed" : "open"); exit }' "$REPO/grid/fetch-xray.json"
}
word_fetch() {
  local section setup busy waits="" one args=(--only "$id")
  # A folder a cloud session carried to GitHub comes by git on this node, with no job (word_fetch_carried).
  if [ -f "$REPO/grid/carry/$id.txt" ]; then word_fetch_carried; return; fi
  # A look at the set taken before this fetch no longer says what it holds (word_explore).
  rm -f "$LOGS/EXPLORE-$id.md" "$LOGS/EXPLORE-$id.md.key"
  section=$(fetch_section "$id")
  if [ -z "$section" ]; then
    gated_platform_id || { echo "refusing: $id is not an id of grid/fetch-xray.json nor a gated source of grid/run-platform-fetch.sh"; return 64; }
    word_fetch_gated
    return
  fi
  if [ "$section" = credentialed ]; then
    # The owner's PhysioNet sign-in, read by the fetch job alone; never printed here.
    [ -f "$NETRC" ] || { echo "refusing: $id is credentialed and there is no ~/.netrc"; return 2; }
    [ "$(stat -c '%a' "$NETRC")" = 600 ] || { echo "refusing: ~/.netrc is not mode 600"; return 2; }
    grep -q 'physionet\.org' "$NETRC" || { echo "refusing: ~/.netrc has no physionet.org line"; return 2; }
    args+=(--credentialed)
  fi
  # One fetch of a set at a time: two would resume the same .part files at once. start's chain
  # fetches every open set, so an open id waits for it too.
  busy=$(live_of xr_fetch "fetch:$id")
  [ "$section" = credentialed ] || busy=$busy$(live_of xr_fetch start)
  [ -z "$busy" ] || { echo "refusing: a fetch that holds $id is still queued or running (job $busy)"; return 75; }
  # Nor beside the bank word's job of the set (word_bank refuses the other way round): this chain's
  # bank half would write the same bank folder, and the fetch's admission would take the place of
  # the bank's in the set's meta/SIZE.
  busy=$(live_of bank "bank:$id")
  [ -z "$busy" ] || { echo "refusing: a bank of $id is still queued or running (job $busy), and this fetch's chain banks the same folder"; return 75; }
  # Nor beside an unpacking of the set, a look at it or a deletion of its zips, each of which
  # holds its room through the same admission file and reads the raw folder this fetch writes.
  busy=$( { live_of unpack "unpack:$id"; live_of explore "explore:$id"; live_of dropzip "dropzip:$id"; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: an unpacking, a look or a deletion of zips in $id is still queued or running (job $busy)"; return 75; }
  # One catalog build at a time: this chain's catalog job waits for every one still live.
  for one in $(awk '$3 == "catalog" || $3 == "xr_catalog" { print $1 }' "$STATE" 2>/dev/null | sort -u); do
    case "$QUEUED" in *" $one "*) waits=$(joined "$waits" "afterany:$one") ;; esac
  done
  setup=$(setup_dependency) || return 1
  CATALOG_DEPEND=$waits chain "$setup" "${args[@]}"
}

gated_platform_id() {  # whether $id is one of the granted gated CT sources the platform script fetches alone
  bash "$REPO/grid/run-platform-fetch.sh" --gated-ids 2>/dev/null | grep -qxF -- "$id"
}
word_fetch_gated() {  # one gated CT source through the platform script, recorded as dp_<id> under fetch:<id>
  local busy xray="" one out rc
  # One fetch of a source at a time: two would write the same landing at once.
  busy=$(live_of "dp_$id")
  [ -z "$busy" ] || { echo "refusing: a fetch of $id is still queued or running (job $busy)"; return 75; }
  # X-ray before CT (the owner's order of 2026-10-21): the CT fetch waits on every X-ray fetch still live.
  for one in $(awk '$3 == "xr_fetch" { print $1 }' "$STATE" 2>/dev/null | sort -u); do
    case "$QUEUED" in *" $one "*) xray=$(joined "$xray" "afterany:$one") ;; esac
  done
  out=$(DEPEND="$xray" bash "$REPO/grid/run-platform-fetch.sh" --only "$id" 2>&1)
  rc=$?
  # The platform script's list of the owner's own lines (CT-RATE, NLST) is not this word's business.
  echo "$out" | sed -n '/^Not submitted/q; p' | sed 's/^/  /'
  echo "$out" | sed -n 's/^\([a-z0-9_]*\): job \([0-9][0-9]*\).*/\2 \1/p' | while read -r one name; do
    record "$one" "dp_$name"
  done
  return $rc
}

# A carried folder (grid/carry/<id>.txt): files a cloud session can hand on only through GitHub, as a
# Claude project's shared folder, which does not follow the owner to another project (the owner's
# word of 2026-10-28 17:24 UTC, "push these to the grid to the new project to fine there"). They ride
# as one commit on a branch of a private repository, and the fetch word brings that commit's tree
# onto the data root as the landing <id> with git on this node, as the gate's side fetches main: a
# copy and no computation, so no job is queued. The record pins the repository, the branch, the
# commit, the files and bytes its tree holds and the sha256 of its SHA256SUMS, which lists every other
# file; each is checked before the folder is put in place, so what lands is exactly what the session
# sent, or nothing. The size rule's lock is held from the room's reading until the folder is in
# place, so nothing is admitted beside bytes the rule has not counted, and the git copy counts
# against the room with the files while it lasts. A later send checks the landing against
# SHA256SUMS again and fetches nothing.
CARRY_BASE=${CARRY_BASE:-https://github.com}
CARRY_TIMEOUT=${CARRY_TIMEOUT:-480}
carry_field() {  # carry_field KEY: the one value the record gives KEY on a line "KEY VALUE"; status 1 where it gives none, several or more than one word
  awk -v k="$1" '$1 == k { n++; v = $2; if (NF != 2) n++ } END { if (n != 1) exit 1; print v }' "$REPO/grid/carry/$id.txt"
}
carry_gh() {  # where gh is, on PATH or where a login shell finds it, as the grid gate's own gh_on_path looks; status 1 where it is not
  local d
  command -v gh 2>/dev/null && return 0
  for d in "$HOME/bin" "$HOME/.local/bin" "$HOME/opt/gh/bin"; do [ -x "$d/gh" ] && { echo "$d/gh"; return 0; }; done
  return 1
}
carry_fetch() {  # carry_fetch GIT_DIR URL BRANCH: the branch's tip fetched as refs/carry, through gh's own sign-in where gh is found
  # A ~/.gitconfig helper may hold another account's sign-in, as the grid gate's artifacts word found,
  # so gh's comes first, as that word fetches.
  local gh helper=()
  gh=$(carry_gh) && helper=(-c credential.helper= -c "credential.helper=!env -u GITHUB_TOKEN -u GH_TOKEN $gh auth git-credential")
  GIT_TERMINAL_PROMPT=0 timeout "$CARRY_TIMEOUT" git ${helper[@]+"${helper[@]}"} --git-dir="$1" fetch -q --no-tags --depth 1 "$2" "+refs/heads/$3:refs/carry" < /dev/null
}
carry_tree() {  # carry_tree GIT_DIR COMMIT: "<files> <bytes> <others>", the tree's plain files, their bytes, and its entries that are none (links, submodules)
  git --git-dir="$1" ls-tree -r -l --full-tree "$2" | awk -F '\t' '
    { split($1, f, " "); if (f[1] == "100644" || f[1] == "100755") { n++; b += f[4] } else o++ }
    END { printf "%d %.0f %d\n", n, b, o }'
}
carry_check() {  # carry_check FOLDER MANIFEST FILES: 0 where SHA256SUMS hashes to MANIFEST, lists every other file once and each matches; the reason otherwise
  local f=$1 listed found count out
  [ "$(sha256sum < "$f/SHA256SUMS" 2>/dev/null | cut -c1-64)" = "$2" ] || { echo "its SHA256SUMS is not the one the record names"; return 1; }
  listed=$(sed 's/^[0-9a-f]\{64\}  //' "$f/SHA256SUMS" | LC_ALL=C sort)
  found=$(cd "$f" && find . -path ./meta/CARRIED -prune -o -type f ! -path ./SHA256SUMS -print | sed 's|^\./||' | LC_ALL=C sort)
  [ "$listed" = "$found" ] || { echo "SHA256SUMS does not list exactly the files there"; return 1; }
  count=$(printf '%s\n' "$listed" | grep -c .)
  [ "$count" = $(( $3 - 1 )) ] || { echo "SHA256SUMS lists $count files where the record counts $(( $3 - 1 )) beside it"; return 1; }
  out=$(cd "$f" && sha256sum -c --quiet --strict SHA256SUMS 2>&1) && return 0
  echo "$(printf '%s\n' "$out" | grep -c 'FAILED') of its files do not match SHA256SUMS"
  return 1
}
carry_land() {  # carry_land REPO BRANCH COMMIT FILES BYTES MANIFEST: the commit fetched to $stage, checked, checked out, checked again and put in place as $dest
  local n b o why
  if [ -e "$stage" ] || [ -L "$stage" ]; then
    [ -d "$stage" ] && [ ! -L "$stage" ] || { echo "refusing: .carry_$id on the data root is no folder of this word's; nothing was fetched"; return 2; }
    rm -rf "$stage" || { echo "fetch $id failed: an earlier send's .carry_$id could not be cleared"; return 1; }
  fi
  ( umask 077; mkdir "$stage" "$stage/tree" && git init -q --bare "$stage/git" ) > /dev/null 2>&1 \
    || { echo "fetch $id failed: its git copy could not be made on the data root"; return 1; }
  if ! carry_fetch "$stage/git" "$CARRY_BASE/$1.git" "$2" > "$stage/fetch.log" 2>&1; then
    echo "fetch $id failed: git could not fetch the branch $2 of $1 within $CARRY_TIMEOUT seconds; what it said last:"
    # with the data root cut, since no path under it leaves the grid (a full volume names the git copy's)
    tail -n 3 "$stage/fetch.log" | printable | while IFS= read -r line; do echo "  ${line//"$DATA"/<data root>}"; done
    return 1
  fi
  [ "$(git --git-dir="$stage/git" rev-parse -q --verify refs/carry 2>/dev/null)" = "$3" ] \
    || { echo "refusing: the branch $2 of $1 is not at the record's commit ${3:0:12}; nothing was put in place"; return 2; }
  read -r n b o <<< "$(carry_tree "$stage/git" "$3")"
  [ "$n" = "$4" ] && [ "$b" = "$5" ] && [ "$o" = 0 ] \
    || { echo "refusing: the commit holds $n files of $b bytes and $o other entries, where the record says $4 files of $5 bytes and none other; nothing was put in place"; return 2; }
  ( umask 077; GIT_TERMINAL_PROMPT=0 timeout "$CARRY_TIMEOUT" git --git-dir="$stage/git" --work-tree="$stage/tree" checkout -q -f "$3" -- . < /dev/null ) > /dev/null 2>&1 \
    || { echo "fetch $id failed: git could not check the commit out within $CARRY_TIMEOUT seconds"; return 1; }
  [ ! -e "$stage/tree/meta" ] || { echo "refusing: the commit has a meta at its top, where the landing keeps its record; nothing was put in place"; return 2; }
  why=$(carry_check "$stage/tree" "$6" "$4") || { echo "refusing: $why; nothing was put in place"; return 1; }
  ( umask 077; mkdir "$stage/tree/meta" && echo "carried $3 $4 $5 $(date -u '+%FT%TZ') $1 $2" > "$stage/tree/meta/CARRIED" ) \
    || { echo "fetch $id failed: meta/CARRIED could not be written"; return 1; }
  chmod 700 "$stage/tree" && mv -T "$stage/tree" "$dest" || { echo "fetch $id failed: the checked folder could not be put in place"; return 1; }
  echo "  $id: carried at ${3:0:12} from the branch $2 of $1: $4 files, $5 bytes, each matching SHA256SUMS; the landing $id on the data root, 0700, with meta/CARRIED"
}
word_fetch_carried() {  # one carried folder brought onto the data root, or its landing checked again where it stands
  local DATA=$DATA_ROOT repo branch commit files bytes manifest dest stage need rc why
  repo=$(carry_field repo) && branch=$(carry_field branch) && commit=$(carry_field commit) && files=$(carry_field files) \
    && bytes=$(carry_field bytes) && manifest=$(carry_field manifest) \
    || { echo "refusing: grid/carry/$id.txt does not give each of repo, branch, commit, files, bytes and manifest once"; return 2; }
  [[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] && [[ "$branch" =~ ^[A-Za-z0-9_./-]+$ ]] && [[ "$branch" != *..* ]] \
    && [[ "$commit" =~ ^[0-9a-f]{40}$ ]] && [[ "$manifest" =~ ^[0-9a-f]{64}$ ]] \
    && [[ "$files" =~ ^[1-9][0-9]{0,8}$ ]] && [[ "$bytes" =~ ^[1-9][0-9]{0,14}$ ]] \
    || { echo "refusing: a value of grid/carry/$id.txt is not of its shape"; return 2; }
  [ -d "$DATA" ] || { echo "refusing: there is no data root to land $id in"; return 2; }
  dest=$DATA/$id stage=$DATA/.carry_$id
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    [ -d "$dest" ] && [ ! -L "$dest" ] && [ "$(awk '{ print $2; exit }' "$dest/meta/CARRIED" 2>/dev/null)" = "$commit" ] \
      || { echo "refusing: $id is on the data root already and holds no carry of ${commit:0:12}; nothing was changed (move it aside to fetch it again)"; return 2; }
    why=$(carry_check "$dest" "$manifest" "$files") || { echo "fetch $id: carried earlier, but $why"; return 1; }
    echo "  $id: carried at ${commit:0:12} on $(awk '{ print $5; exit }' "$dest/meta/CARRIED"); its $files files match SHA256SUMS again; nothing was fetched"
    return 0
  fi
  # The pack git fetches holds the files' bytes again until the folder is in place, and a little more.
  need=$(( 2 * bytes + bytes / 50 ))
  exec 8> "$DATA/.size-rule.lock" || { echo "refusing: the size rule's lock on the data root could not be opened; nothing was fetched"; return 2; }
  if ! flock -w "${SIZE_RULE_WAIT:-900}" 8; then
    exec 8>&-
    echo "refusing: another decision held the size check for ${SIZE_RULE_WAIT:-900} seconds; nothing was fetched"
    return 75
  fi
  room_for "$need" "the folder and its git copy need" "nothing was fetched" \
    && carry_land "$repo" "$branch" "$commit" "$files" "$bytes" "$manifest"
  rc=$?
  exec 8>&-
  rm -rf "$stage"
  return $rc
}

explore_against() {  # the sets $id is compared with, label=folder joined by |; nothing for most sets
  # The Kaggle scoliosis export (spine-datasets #23) may be AASCE's films re-exported by Roboflow:
  # both AASCE copies on the volume, as grid/fetch-xray.json's confirm list for it names them.
  case "$id" in
    kaggle_scoliosis_yolov5)
      echo "AASCE-ke30-mirror=$DATA_ROOT/thoracic_xr/mirror_zlinzju_ke30_u7_AASCE2019|AASCE-BoostNet=$DATA_ROOT/aasce2019_boostnet/raw/aasce" ;;
  esac
}
explore_tool_key() {  # what a report must have been written by to be printed: the tool's own hash
  sha256sum < "$REPO/tools/explore.py" | cut -c1-12
}
word_explore() {
  local raw report busy against
  raw=$DATA_ROOT/$id/raw report=$LOGS/EXPLORE-$id.md
  grep -q "\"id\": \"$id\"" "$REPO/grid/fetch-xray.json" || gated_platform_id \
    || { echo "refusing: $id is not an id of grid/fetch-xray.json nor a gated source of grid/run-platform-fetch.sh"; return 64; }
  busy=$(live_of explore "explore:$id")
  [ -z "$busy" ] || { echo "refusing: the look at $id is still queued or running (job $busy); send explore $id again once it ends"; return 75; }
  if [ -f "$report" ] && [ "$(cat "$report.key" 2>/dev/null)" = "$(explore_tool_key)" ]; then
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 300 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 60000
    return 0
  fi
  busy=$( { live_of xr_fetch "fetch:$id"; live_of "dp_$id"; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: a fetch of $id is still queued or running (job $busy)"; return 75; }
  [ -d "$raw" ] || { echo "refusing: $id has no raw folder on the data root yet; fetch it first"; return 2; }
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  against=$(explore_against)
  rm -f "$report" "$report.key"
  explore_tool_key > "$report.key"
  submit explore batch EXPLORE_ID="$id" EXPLORE_RAW="$raw" EXPLORE_AGAINST="$against" -- explore.sbatch > /dev/null || return 1
  echo "submitted one job. Send explore $id again once it ends to read the report."
}

word_dropzip() {
  local raw report busy
  raw=$DATA_ROOT/$id/raw report=$LOGS/DROPZIP-$id.md
  grep -q "\"id\": \"$id\"" "$REPO/grid/fetch-xray.json" || gated_platform_id \
    || { echo "refusing: $id is not an id of grid/fetch-xray.json nor a gated source of grid/run-platform-fetch.sh"; return 64; }
  busy=$(live_of dropzip "dropzip:$id")
  [ -z "$busy" ] || { echo "refusing: the deletion for $id is still queued or running (job $busy); send dropzip $id again once it ends"; return 75; }
  if [ -f "$report" ]; then
    # Printed once: the next send looks again, so a zip a later fetch leaves is settled too.
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 100 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 20000
    rm -f "$report"
    return 0
  fi
  # Never while the set is still landing or being read: a zip half unpacked has members not yet beside it.
  busy=$( { live_of xr_fetch "fetch:$id"; live_of "dp_$id"; live_of explore "explore:$id"; live_of unpack "unpack:$id"; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: a fetch, an unpacking or a look at $id is still queued or running (job $busy)"; return 75; }
  [ -d "$raw" ] || { echo "refusing: $id has no raw folder on the data root yet; fetch it first"; return 2; }
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  submit dropzip batch DROPZIP_ID="$id" DROPZIP_RAW="$raw" -- dropzip.sbatch > /dev/null || return 1
  echo "submitted one job. Send dropzip $id again once it ends to read what it deleted."
}

word_unpack() {
  local raw report busy
  raw=$DATA_ROOT/$id/raw report=$LOGS/UNPACK-$id.md
  grep -q "\"id\": \"$id\"" "$REPO/grid/fetch-xray.json" || gated_platform_id \
    || { echo "refusing: $id is not an id of grid/fetch-xray.json nor a gated source of grid/run-platform-fetch.sh"; return 64; }
  busy=$(live_of unpack "unpack:$id")
  [ -z "$busy" ] || { echo "refusing: the unpacking of $id is still queued or running (job $busy); send unpack $id again once it ends"; return 75; }
  if [ -f "$report" ]; then
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 100 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 20000
    rm -f "$report"
    return 0
  fi
  # Never beside a fetch of the set, a look at it, a deletion of its zips or a bank of it, which
  # would read half a raw folder and holds its room through the same admission file.
  busy=$( { live_of xr_fetch "fetch:$id"; live_of "dp_$id"; live_of explore "explore:$id"; live_of dropzip "dropzip:$id"; live_of bank "bank:$id"; live_of xr_bank; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: a fetch, a deletion, a bank or a look at $id is still queued or running (job $busy)"; return 75; }
  [ -d "$raw" ] || { echo "refusing: $id has no raw folder on the data root yet; fetch it first"; return 2; }
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  submit unpack batch UNPACK_ID="$id" UNPACK_RAW="$raw" DATA_ROOT="$DATA_ROOT" VOLUME="$VOLUME" -- unpack.sbatch > /dev/null || return 1
  echo "submitted one job. It starts writing only once the size rule admits it; send unpack $id again once it ends to read what it wrote."
}

experiment_request() {  # experiment_request N: the lines the workflow recorded for issue N, on stdout
  # From the branch experiments on origin, fetched now, since the gate's side brings main alone; a test
  # sets EXPERIMENTS_DIR to a folder of such files instead, where no origin answers.
  if [ -n "${EXPERIMENTS_DIR:-}" ]; then cat "$EXPERIMENTS_DIR/$1.request" 2>/dev/null; return; fi
  git -C "$REPO" fetch -q --no-tags origin "+refs/heads/experiments:refs/remotes/origin/experiments" 2>/dev/null || return 1
  git -C "$REPO" show "refs/remotes/origin/experiments:$1.request" 2>/dev/null
}
experiment_lines_ok() {  # experiment_lines_ok FILE: every line has the shape the workflow writes, the four settings once each
  # The shapes alone, on the login node, where no python runs; the driver checks the values against the
  # blocks module inside the container before anything trains.
  local n=0 line key
  while IFS= read -r line || [ -n "$line" ]; do
    n=$((n + 1))
    [ $n -le 40 ] || { echo "refusing: the request has more than 40 lines"; return 1; }
    [ ${#line} -le 120 ] || { echo "refusing: line $n of the request is over 120 characters"; return 1; }
    case "$line" in *[!A-Za-z0-9._,=:\ -]*) echo "refusing: line $n of the request holds a character outside letters, digits and . _ , = : -"; return 1 ;; esac
    case "$line" in
      "recipe: "[a-z]*|"epochs: "[1-9]*|"seed: "[0-9]*|"hours: "[0-9]*|"block: "[a-z]*=?*) ;;
      *) echo "refusing: line $n of the request is not one the gate takes: $(printf '%s' "$line" | cut -c1-60)"; return 1 ;;
    esac
  done < "$1"
  for key in recipe epochs seed hours; do
    [ "$(grep -c "^$key: " "$1")" = 1 ] || { echo "refusing: the request names $key once, not $(grep -c "^$key: " "$1") times"; return 1; }
  done
}
experiment_wall() {  # experiment_wall HOURS: the job's wall time as Slurm takes it, H:MM:00
  # The request's hours are the training's (the panel's "the training job's wall time"); in this one job the
  # evaluation follows the training, given a quarter of its hours as flow.py's slurm mode gives it, and an
  # hour more holds the checks and the container's start. Never less than the driver's own 24 hours, which
  # the version 1 run proved, so a short request runs as v1 did and a long one gets the time it asked for.
  awk -v h="$1" 'BEGIN { m = int((h * 1.25 + 1) * 60 + 0.999); if (m < 1440) m = 1440; printf "%d:%02d:00\n", int(m / 60), m % 60 }'
}
word_experiment() {
  local req=$LOGS/experiment-$id.request busy version hours wall holds opts
  busy=$(live_of "experiment_$id")
  [ -z "$busy" ] || { echo "refusing: the run for #$id is already queued or running (job $busy)"; return 75; }
  if ! experiment_request "$id" > "$req.new" || [ ! -s "$req.new" ]; then
    rm -f "$req.new"
    echo "refusing: no $id.request on the branch experiments; the experiment workflow writes it when issue #$id's combination holds (grid/README.md)"
    return 75
  fi
  mv "$req.new" "$req"
  experiment_lines_ok "$req" || { rm -f "$req"; return 64; }
  hours=$(sed -n 's/^hours: //p' "$req")
  case "$hours" in ''|*[!0-9.]*|*.*.*|.*|*.) rm -f "$req"; echo "refusing: hours is a number such as 4 or 2.5, not ${hours:-nothing}"; return 64 ;; esac
  wall=$(experiment_wall "$hours")
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  weights_ready || { echo "refusing: no ImageNet weights at $WEIGHTS; 'v1' makes them first"; return 75; }
  carmlspine_ready || { echo "refusing: C-ArmLSpine's train and test shards are not on the data root; 'v1' makes them first"; return 75; }
  version=$(v1_version) || { echo "refusing: no catalog version qualifies (grid/v1-version.sh); 'v1' builds one first"; return 75; }
  echo "  catalog: $version qualifies for the run (grid/v1-version.sh); no job"
  echo "  request: $(tr '\n' ' ' < "$req")"
  echo "  wall time: $wall for $hours hours of training"
  # Queued after every run that holds the checkout, as a sweep is, rather than refused.
  holds=$(checkout_holders)
  [ -z "$holds" ] || echo "  the checkout: after the live runs that hold it ($holds)"
  depend_on "$holds" || return 1
  submit "experiment_$id" gpu REQUEST="$req" ISSUE="$id" RUNS="$RUNS" WEIGHTS="$WEIGHTS" ${opts[@]+"${opts[@]}"} \
    --no-requeue --time "$wall" -- experiment-driver.sbatch > /dev/null || return 1
  echo "submitted one job. 'status' shows it; its report is logs/experiment-$id-STAGE-REPORT.md"
}
word_nodequota() {
  local report=$LOGS/NODEQUOTA.md busy
  busy=$(live_of nodequota)
  [ -z "$busy" ] || { echo "refusing: the node's readout is still queued or running (job $busy); send nodequota again once it ends"; return 75; }
  if [ -f "$report" ]; then
    # Printed once, so the send after it reads a node again.
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 100 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 20000
    rm -f "$report"
    return 0
  fi
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  submit nodequota batch -- nodequota.sbatch > /dev/null || return 1
  echo "submitted one job. Send nodequota again once it ends to read what the node read."
}

word_folders() {
  local busy page left index
  busy=$(live_of folders)
  [ -z "$busy" ] || { echo "refusing: the folder report is still queued or running (job $busy); send folders again once it ends"; return 75; }
  page=$(find "$LOGS" -maxdepth 1 -name 'FOLDERS-*.md' 2>/dev/null | sort -V | head -n 1)
  if [ -n "$page" ]; then
    left=$(( $(find "$LOGS" -maxdepth 1 -name 'FOLDERS-*.md' | wc -l) - 1 ))
    echo "## $(basename "$page") ($(date -r "$page" '+%F %T')), $left more to print"
    head -c 60000 "$page" | LC_ALL=C tr -cd '\11\12\40-\176' | masked
    rm -f "$page"
    return 0
  fi
  index=$(samples_index) || { echo "refusing: no whole sample index yet; 'samples' makes it"; return 2; }
  # The report needs only the standard library, so an environment a newer pixi.lock left behind
  # still runs it: only a train-cpu python that is not there at all waits for 'start'.
  [ -x "$REPO/.pixi/envs/train-cpu/bin/python" ] || { echo "refusing: no train-cpu environment yet; 'start' makes it first"; return 75; }
  submit folders batch FOLDERS_DB="$index" -- folders.sbatch > /dev/null || return 1
  echo "submitted one job. Send folders again once it ends to print its report, one page a send."
}

samples_index() {  # the newest whole run's samples.sqlite, as grid/run-samples.sh names it in CURRENT
  local out=${SAMPLES_OUT:-$DATA_ROOT/_samples} current
  current=$(cat "$out/CURRENT" 2>/dev/null)
  [ -n "$current" ] && [ -f "$out/$current/samples.sqlite" ] || return 1
  echo "$out/$current/samples.sqlite"
}

bench_inputs_missing() {  # what bench $id still lacks on the data root, one line, or nothing
  local zip busy
  case "$id" in
    flexray_carmlspine|flexray_deepfluoro)
      find "$DATA_ROOT/hf_flexray_weights/raw" -maxdepth 3 -name ensemble.json -print -quit 2>/dev/null | grep -q . \
        || { echo "FleXray's weights (fetch hf_flexray_weights first)"; return; }
      if [ "$id" = flexray_carmlspine ]; then
        [ -d "$DATA_ROOT/realxray/carmlspine/meta" ] || echo "C-ArmLSpine's bank at $DATA_ROOT/realxray/carmlspine"
      else
        find "$DATA_ROOT/deepfluoro_h5/raw" -name '*.h5' -size +1M -print -quit 2>/dev/null | grep -q . \
          || echo "DeepFluoro's .h5 under $DATA_ROOT/deepfluoro_h5/raw"
      fi ;;
    xvr_deepfluoro)
      find "$DATA_ROOT/hf_xvr_models/raw" -path '*/deepfluoro/finetuned/subject01.pth' -print -quit 2>/dev/null | grep -q . \
        || { echo "xvr's DeepFluoro models (fetch hf_xvr_models first)"; return; }
      [ -f "$DATA_ROOT/hf_xvr_data/raw/deepfluoro/subject01/volume.nii.gz" ] || echo "xvr's DeepFluoro data (fetch hf_xvr_data first)" ;;
    flexray_drr_gap)
      # The study's inputs in the order its prepare step reads them (grid/drr-gap.sbatch). FluXray and the two
      # segmenters' masks are optional and never refused for, so word_bench only says which are
      # there: a DRR is a projection of the CT alone, so the render groups that read no label
      # (segmenter=none) render without any mask, and a group whose segmenter's masks are not there,
      # or too few CTs have, is skipped by the study with that reason (the owner's word of 2026-10-27).
      find "$DATA_ROOT/hf_flexray_weights/raw" -maxdepth 3 -name ensemble.json -print -quit 2>/dev/null | grep -q . \
        || { echo "FleXray's weights (fetch hf_flexray_weights first)"; return; }
      samples_index > /dev/null || { echo "a whole sample index (the gate word samples makes it)"; return; }
      [ -d "$DATA_ROOT/totalsegmentator_v201" ] || { echo "the TotalSegmentator CTs at $DATA_ROOT/totalsegmentator_v201, which its render groups draw"; return; }
      weights_ready || echo "the ImageNet ResNet-18 file at $WEIGHTS (the gate word start fetches it)" ;;
    flexray_drr_seg)
      # The segment job's inputs in the order it reads them: the CTs and the SPINEPS masks the plan
      # chooses among, then MOOSE's weights, which the job never downloads: no fetch of them still
      # live, as the fetch, explore and unpack words refuse beside one, and every zip there and
      # whole, since the url route lands each under its final name while curl resumes it and leaves
      # a part there when a download is cut short (grid/platform-fetch.sbatch, fetch_url), which
      # [ -s ] passes and the job's unpack would die on.
      [ -d "$DATA_ROOT/totalsegmentator_v201" ] || { echo "the TotalSegmentator CTs at $DATA_ROOT/totalsegmentator_v201, which the study's render groups draw"; return; }
      [ -d "$DATA_ROOT/spineps" ] || { echo "the SPINEPS masks at $DATA_ROOT/spineps, which the choice of CTs is made among"; return; }
      busy=$(live_of dp_moose_weights)
      [ -z "$busy" ] || { echo "the fetch of moose_weights to end: it is still queued or running (job $busy)"; return; }
      zip=$(moose_weights_missing)
      case "$zip" in
        "") ;;
        row) echo "MOOSE's model zips named: the row moose_weights of grid/run-platform-fetch.sh was not read" ;;
        *" part") echo "MOOSE's model zip ${zip% part} under $DATA_ROOT/moose_weights/raw whole: what is there is a part, still landing or cut short, which a resend of fetch moose_weights resumes" ;;
        *) echo "MOOSE's model zip ${zip% missing} under $DATA_ROOT/moose_weights/raw (fetch moose_weights first)" ;;
      esac ;;
  esac
}
moose_weights_missing() {  # the first of MOOSE's model zips not whole under the data root's moose_weights/raw, by the fetch row's URLs: "<name> missing", "<name> part", or "row" where the row was not read
  weights_zip_missing moose_weights
}
weights_zip_missing() {  # weights_zip_missing ROW: the first zip of a url fetch row (moose_weights, totalseg_weights) not whole under the data root's <row>/raw, by the row's URLs: "<name> missing", "<name> part", or "row" where the row was not read
  local urls url file
  urls=$(bash "$REPO/grid/run-platform-fetch.sh" --args "$1" 2>/dev/null)
  [ -n "$urls" ] || { echo row; return; }
  for url in $urls; do
    file=$DATA_ROOT/$1/raw/${url##*/}
    [ -s "$file" ] || { echo "${url##*/} missing"; return; }
    zip_whole "$file" || { echo "${url##*/} part"; return; }
  done
}
zip_whole() {  # zip_whole FILE: the file ends in a whole end-of-central-directory record, read as Python's zipfile.is_zipfile reads it
  # The record's signature PK\5\6 within the last 65557 bytes, 18 bytes after it and then a comment
  # of the length the record states, up to the file's end: a zip cut short anywhere, in its last
  # bytes included, fails this, a whole one passes. awk and coreutils alone, since the login node
  # runs no python; grid/drr-seg.sbatch's copy adds unzip's test of every member where the node has it.
  local size from
  size=$(stat -c %s "$1" 2>/dev/null) && [ "$size" -ge 22 ] || return 1
  from=$(( size > 65558 ? size - 65558 : 0 ))
  tail -c +"$((from + 1))" "$1" | od -An -v -tx1 -w1 | awk '
    function hex(s,  i, v) { v = 0; for (i = 1; i <= length(s); i++) v = v * 16 + index("0123456789abcdef", substr(s, i, 1)) - 1; return v }
    { bytes[NR] = $1 }
    END { for (i = NR - 21; i >= 1; i--) if (bytes[i] bytes[i + 1] bytes[i + 2] bytes[i + 3] == "504b0506" && i + 21 + hex(bytes[i + 21] bytes[i + 20]) == NR) exit 0; exit 1 }'
}
bench_job_of() {  # the job number a benchmark report's first line names
  sed -n '1s/.*: job \([0-9][0-9]*\) .*/\1/p' "$1"
}
bench_failed_on_older_code() {  # a report whose last line is a nonzero exit, from a commit not the checkout's
  local last
  last=$(tail -n 1 "$1")
  [[ "$last" =~ ^-\ exit\ [1-9][0-9]*\  ]] || return 1
  began_on_older_code "$1"
}
began_on_older_code() {  # a report whose first line names its job and a commit not the checkout's
  local began
  began=$(sed -n '1s/.*, commit \([0-9a-f]*\|unknown\),.*/\1/p' "$1")
  [ -n "$began" ] && [ -n "$(bench_job_of "$1")" ] && [ "$began" != "${commit:0:7}" ]
}
bench_rerun_allowed() {  # a report whose job BENCH_RERUNS lists beside the benchmark's id, from a commit not the checkout's
  local job began
  job=$(bench_job_of "$1")
  began=$(sed -n '1s/.*, commit \([0-9a-f]*\|unknown\),.*/\1/p' "$1")
  [ -n "$job" ] && [ -n "$began" ] && [ "$began" != "${commit:0:7}" ] || return 1
  case " $BENCH_RERUNS " in *" $id:$job "*) return 0 ;; esac
  return 1
}
drr_gap_masks() {  # one line on each segmenter's masks bench flexray_drr_gap will read
  # The study waits afterany on a live bench flexray_drr_seg, as on every run that holds the
  # checkout, so it reads the MOOSE masks that job wrote once it has ended, however it ended; a
  # folder that holds fewer CTs' masks than a group needs to be tested is read as no masks, which
  # the study's summary says, so this line says only where each folder is. While that job holds
  # the checkout this word is read by the gate at the commit the job started from, so it is sent
  # once the job has ended.
  local name label maker
  for name in spineps moose; do
    label="the ${name^^} masks" maker=""
    [ "$name" != moose ] || maker=" (bench flexray_drr_seg makes them)"
    if [ -d "$DATA_ROOT/$name" ]; then
      echo "  $label: in $DATA_ROOT/$name, read where enough CTs have them (the study's summary says how many)"
    else
      echo "  $label: not at $DATA_ROOT/$name$maker; the render groups that name segmenter=$name are skipped with that reason"
    fi
  done
}
drr_gap_live() {  # the study's live jobs, its prepare, its shard array and its merge, space-separated
  { live_of bench_flexray_drr_gap; live_of bench_flexray_drr_gap_shard; live_of bench_flexray_drr_gap_merge; } | tr '\n' ' ' | sed 's/ $//'
}
drr_gap_jobs() {  # drr_gap_jobs [WAIT...]: the study's three jobs (grid/drr-gap.sbatch), prepare after WAIT, the shard array afterany it, the merge afterany the array; all of them or none
  # The owner's word of 2026-10-27 17:51 UTC: sharded by the Lab Recipe (rules 3, 8, 9 and 10,
  # grid/drr-gap.sbatch), on any card since the owner's word of 2026-10-28 00:23 UTC. Each step reads a file to tell whether the one before it did
  # its part, so each waits afterany; the shards and the merge are handed prepare's job, so neither
  # reads a step file an earlier chain left, and the merge the array's count, so it names each task.
  local waits=("$@") study prepare shards merge opts
  study=(BENCH="$id" DATA_ROOT="$DATA_ROOT" INDEX="$(samples_index)" MODELS="$MODELS" BENCH_ROOT="$BENCH_ROOT"
         DRR_GAP_OUT="$BENCH_ROOT/$DRR_GAP_FOLDER")
  prepare=$(submit bench_flexray_drr_gap gpu "${study[@]}" STEP=prepare ${waits[@]+"${waits[@]}"} \
    --cpus 16 --mem 64G --time 12:00:00 --no-requeue -- drr-gap.sbatch) || return 1
  # Both or neither, as grid/run-leaks.sh queues its array and join: a prepare whose shards were
  # refused would cut units nobody claims, and shards whose merge was refused would leave no report.
  if ! depend_on "afterany:$prepare" || ! shards=$(submit bench_flexray_drr_gap_shard gpu "${study[@]}" STEP=shard PREPARE_JOB="$prepare" \
    ${opts[@]+"${opts[@]}"} --array "0-$((DRR_GAP_TASKS - 1))" --cpus 16 --mem 64G --time 12:00:00 --no-requeue -- drr-gap.sbatch); then
    "$SCANCEL" "$prepare" && echo "  cancelled prepare $prepare, since its shard array was refused"
    return 1
  fi
  if ! depend_on "afterany:$shards" || ! merge=$(submit bench_flexray_drr_gap_merge gpu "${study[@]}" STEP=merge PREPARE_JOB="$prepare" \
    SHARD_TASKS="$DRR_GAP_TASKS" ${opts[@]+"${opts[@]}"} --cpus 4 --mem 64G --time 04:00:00 --no-requeue -- drr-gap.sbatch); then
    "$SCANCEL" "$prepare" "$shards" && echo "  cancelled prepare $prepare and the shard array $shards, since the merge was refused"
    return 1
  fi
  echo "  the study: prepare $prepare, then the shard array $shards ($DRR_GAP_TASKS tasks, afterany $prepare), then the merge $merge (afterany $shards), each on the first card of the gpu class that frees"
}
drr_gap_progress() {  # the study's PROGRESS.txt, masked, as a send while it lasts prints it, or that it has none yet
  [ -f "$BENCH_ROOT/$DRR_GAP_FOLDER/PROGRESS.txt" ] || { echo "  the study has written no PROGRESS.txt yet in $DRR_GAP_FOLDER: prepare starts it once it runs"; return 0; }
  bench_progress_of "$DRR_GAP_FOLDER"
}
word_bench() {  # one public model's benchmark (#287): queued once, its report printed on every later send
  local report=$LOGS/BENCH-$id.md busy missing holds opts setup again="" script
  case "$id" in
    flexray_carmlspine|flexray_deepfluoro|xvr_deepfluoro|flexray_drr_gap|flexray_drr_seg) ;;
    *) echo "refusing: bench takes flexray_carmlspine, flexray_deepfluoro, xvr_deepfluoro, flexray_drr_gap or flexray_drr_seg"; return 64 ;;
  esac
  if [ "$id" = flexray_drr_gap ]; then
    # Any of the study's three jobs still live is the study still running: what it has done so far
    # first, from its PROGRESS.txt, then the refusal.
    busy=$(drr_gap_live)
    if [ -n "$busy" ]; then
      drr_gap_progress
      echo "refusing: the benchmark $id is still queued or running (jobs $busy); send bench $id again once its merge ends"
      return 75
    fi
  fi
  busy=$(live_of "bench_$id")
  [ -z "$busy" ] || { echo "refusing: the benchmark $id is still queued or running (job $busy); send bench $id again once it ends"; return 75; }
  if [ -f "$report" ]; then
    # Kept, so the owner's count of one job each holds: a report that stands queues nothing. The
    # study's report carries each step's lines, one for each of its 16 shard tasks, beside a summary
    # of up to 85 and a run log of up to 50, so 220 lines are printed, its exit line last among them.
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 220 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 45000
    if bench_failed_on_older_code "$report"; then
      # A benchmark that failed scored nothing, so once a fix has moved the checkout it is queued
      # once more, its report kept under its job's number (#312); the same commit queues nothing.
      again="ended in failure on older code"
    elif bench_rerun_allowed "$report"; then
      # The owner's count for one more run, listed in BENCH_RERUNS by the job of the report it replaces.
      again="is job $(bench_job_of "$report")'s, which BENCH_RERUNS lets the owner's count run once more"
    else
      return 0
    fi
  fi
  missing=$(bench_inputs_missing)
  [ -z "$missing" ] || { echo "refusing: bench $id needs $missing"; return 2; }
  # Kept only once the inputs are there, so a refused send leaves the report standing as it was.
  if [ -n "$again" ]; then
    mv "$report" "$LOGS/BENCH-$id-$(bench_job_of "$report").md" || return 1
    echo "  the report above $again: queueing the benchmark again at $commit"
  fi
  if [ "$id" = flexray_drr_gap ]; then
    # The study reads the index this word checked and the ImageNet file beside the models; FluXray
    # and each segmenter's masks join it only where they are there, and prepare says so in the
    # report rather than wait for them.
    drr_gap_masks
    [ -d "$DATA_ROOT/hf_flexray_data/raw" ] || echo "  FluXray: not on the data root (fetch hf_flexray_data); the study skips its group with that reason"
  fi
  # Stale environments are rebuilt by the one setup job, which every bench sent while it runs waits
  # on, rather than by 'start', which would queue the whole pipeline (the owner's choice, 2026-10-25).
  setup=$(setup_dependency) || return 1
  [ -z "$setup" ] || echo "  the environments: after the setup job that rebuilds them (${setup#afterok:})"
  # The job holds the checkout while it runs (grid/bench.sbatch, grid/drr-seg.sbatch), so it is queued after every other
  # run that holds it, as a sweep is, rather than refused; the study's prepare waits for them too,
  # bench flexray_drr_seg among them, whose MOOSE masks it reads.
  holds=$(checkout_holders)
  [ -z "$holds" ] || echo "  the checkout: after the live runs that hold it ($holds)"
  depend_on "$(joined "$setup" "$holds")" || return 1
  if [ "$id" = flexray_drr_gap ]; then
    drr_gap_jobs ${opts[@]+"${opts[@]}"} || return 1
    echo "submitted the study. 'status' shows its progress while it runs; send bench $id again once its merge ends to read its report, logs/BENCH-$id.md."
    return 0
  fi
  # MOOSE's masks for the study run on a launched flow (grid/drr-seg.sbatch, flows/drr_seg.py), under the
  # same job name, so the holders and the report's name are as they were; the public benchmarks stay here.
  script=bench.sbatch
  [ "$id" != flexray_drr_seg ] || script=drr-seg.sbatch
  submit "bench_$id" gpu BENCH="$id" DATA_ROOT="$DATA_ROOT" ${opts[@]+"${opts[@]}"} --no-requeue -- "$script" > /dev/null || return 1
  echo "submitted the benchmark. Send bench $id again once it ends to read its report, logs/BENCH-$id.md."
}

anomaly_class() {  # the job class a built stage of the anomaly route runs as, else nothing
  case "$1" in
    select|pack) echo batch ;;
    timing) echo gpu ;;
  esac
}
anomaly_options() {  # the job options a stage asks beyond its class: timing as spinesurg-ct-nnunet's slurm/spineps_cases.sh asked them, pack three days of one node for the guard, the rewrite and two packs over about a thousand CTs
  case "$1" in
    timing) echo "--cpus 8 --mem 64G --time 04:00:00" ;;
    pack) echo "--cpus 4 --mem 64G --time 3-00:00:00" ;;
  esac
}
anomaly_ended_well() {  # a stage report whose last line is exit 0
  [[ "$(tail -n 1 "$1" 2>/dev/null)" =~ ^-\ exit\ 0\  ]]
}
anomaly_left_its_node() {  # a stage report whose last line is exit 4: step 0 left a node the environment cannot use (grid/anomaly.sbatch)
  [[ "$(tail -n 1 "$1" 2>/dev/null)" =~ ^-\ exit\ 4\  ]] && [ -n "$(bench_job_of "$1")" ]
}
anomaly_refused_room() {  # a stage report whose last line is exit 5: the size rule refused the pack before a byte landed (grid/anomaly.sbatch)
  [[ "$(tail -n 1 "$1" 2>/dev/null)" =~ ^-\ exit\ 5\  ]] && [ -n "$(bench_job_of "$1")" ]
}
anomaly_inputs_missing() {  # what anomaly $id still lacks, one line, or nothing
  local conda_sh=${CONDA_SH:-$HOME/mambaforge/etc/profile.d/conda.sh} ssn=${SSN:-$HOME/spinesurg-ct-nnunet}
  case "$id" in
    select)
      [ -f "$REPO/data/splits/anomaly-holdout.json" ] || echo "the frozen holdout, data/splits/anomaly-holdout.json" ;;
    timing)
      # Each stage goes once the one before looks sane (docs/research/spineps-anomaly-route.md, section 5).
      anomaly_ended_well "$LOGS/ANOMALY-select.md" || { echo "a select report that ended in exit 0 (logs/ANOMALY-select.md: send anomaly select first and read it)"; return; }
      [ -f "$conda_sh" ] || { echo "conda at $conda_sh, which holds the spineps environment"; return; }
      [ -f "$ssn/benchmark/run_spineps_cases.py" ] || echo "the SPINEPS runner, $ssn/benchmark/run_spineps_cases.py (the spinesurg-ct-nnunet clone at its branch L6_Class)" ;;
    pack)
      # Pack needs nothing of timing's, but the route's rule is one stage at a time, each after the last looked sane.
      anomaly_ended_well "$LOGS/ANOMALY-select.md" || { echo "a select report that ended in exit 0 (logs/ANOMALY-select.md: send anomaly select first and read it)"; return; }
      anomaly_ended_well "$LOGS/ANOMALY-timing.md" || { echo "a timing report that ended in exit 0 (logs/ANOMALY-timing.md: send anomaly timing first and read it)"; return; }
      [ -f "$REPO/data/splits/anomaly-validation.json" ] || { echo "the frozen validation rule, data/splits/anomaly-validation.json"; return; }
      [ -f "$conda_sh" ] || { echo "conda at $conda_sh, which holds the spineps environment"; return; }
      [ -f "$ssn/tools/spineps_ids.py" ] || { echo "the SPINEPS guard, $ssn/tools/spineps_ids.py (the spinesurg-ct-nnunet clone at its branch L6_Class)"; return; }
      [ -f "$G3_SPLIT" ] || { echo "G3's person split, $G3_SPLIT (spine-program 02_transitional_naming_truth's split_final.json)"; return; }
      [ -f "$ANOMALY_ROOT/select/selection.csv" ] || echo "the selection select wrote, $ANOMALY_ROOT/select/selection.csv" ;;
  esac
}
word_anomaly() {  # one stage of the SPINEPS to FleXray anomaly route (#398): queued once, its report printed on every later send
  local report=$LOGS/ANOMALY-$id.md class busy missing holds opts setup stage_opts
  class=$(anomaly_class "$id")
  [ -n "$class" ] || { echo "refusing: anomaly takes select, timing or pack; the stages render, figure, tune and eval are not built yet, and each comes by pull request first"; return 64; }
  busy=$(live_of "anomaly_$id")
  [ -z "$busy" ] || { echo "refusing: the anomaly stage $id is still queued or running (job $busy); send anomaly $id again once it ends"; return 75; }
  if [ -f "$report" ]; then
    # Kept, so the owner's count of one job a stage holds: a report that stands queues nothing.
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 200 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 30000
    if anomaly_left_its_node "$report"; then
      # Step 0 left a node the environment cannot use before a CT was staged, so the stage spent
      # nothing of the count: it is queued again at the same commit, its report kept under its
      # job's number, to land where the class's partitions next have room.
      mv "$report" "$LOGS/ANOMALY-$id-$(bench_job_of "$report").md" || return 1
      echo "  the report above says the stage left its node unused: queueing the stage again at $commit"
    elif anomaly_refused_room "$report"; then
      # The size rule refused the pack before a byte landed, so the stage spent nothing of the count:
      # queued again at the same commit, to decide once more when it starts; status shows the room.
      mv "$report" "$LOGS/ANOMALY-$id-$(bench_job_of "$report").md" || return 1
      echo "  the report above says the size rule refused the pack: queueing the stage again at $commit (status shows the room)"
    else
      bench_failed_on_older_code "$report" || return 0
      # A stage that failed decided nothing, so once a fix has moved the checkout it is queued once
      # more, its report kept under its job's number, as a benchmark's is; the same commit queues nothing.
      mv "$report" "$LOGS/ANOMALY-$id-$(bench_job_of "$report").md" || return 1
      echo "  the report above ended in failure on older code: queueing the stage again at $commit"
    fi
  fi
  missing=$(anomaly_inputs_missing)
  [ -z "$missing" ] || { echo "refusing: anomaly $id needs $missing"; return 2; }
  setup=$(setup_dependency) || return 1
  [ -z "$setup" ] || echo "  the environments: after the setup job that rebuilds them (${setup#afterok:})"
  holds=$(checkout_holders)
  [ -z "$holds" ] || echo "  the checkout: after the live runs that hold it ($holds)"
  depend_on "$(joined "$setup" "$holds")" || return 1
  # depend_on filled opts with the --after options; the stage's own job options follow them
  read -ra stage_opts <<< "$(anomaly_options "$id")"
  opts+=(${stage_opts[@]+"${stage_opts[@]}"})
  submit "anomaly_$id" "$class" STAGE="$id" DATA_ROOT="$DATA_ROOT" ${opts[@]+"${opts[@]}"} --no-requeue -- anomaly.sbatch > /dev/null || return 1
  echo "submitted the anomaly stage $id. Send anomaly $id again once it ends to read its report, logs/ANOMALY-$id.md."
}

bordercall_pilot_ended_well() {  # the pilot's report stands and ended in exit 0, so the full corpus may be sent
  local report=$LOGS/BORDERCALL-pilot.md
  [ -f "$report" ] && [ "$(tail -n 1 "$report" | awk '{ print $3 }')" = 0 ]
}
word_bordercall() {  # the bordercall corpus, pilot then full (the owner's count of 2026-10-25 23:56 UTC): each queued once, its report printed on every later send
  local report=$LOGS/BORDERCALL-$id.md busy holds opts setup wall
  case "$id" in
    pilot) wall=12:00:00 ;;
    full) wall=36:00:00 ;;
    complete) word_bordercall_complete; return ;;
    *) echo "refusing: bordercall takes pilot, full or complete"; return 64 ;;
  esac
  busy=$( { live_of bordercall_pilot; live_of bordercall_full; live_of bordercall_complete; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: a bordercall stage is still queued or running (job $busy); send bordercall $id again once it ends"; return 75; }
  if [ -f "$report" ]; then
    # Kept, so the owner's count of one job a stage holds: a report that stands queues nothing.
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 200 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 30000
    bench_failed_on_older_code "$report" || return 0
    # A stage that failed decided nothing, so once a fix has moved the checkout it is queued once
    # more, its report kept under its job's number, as a benchmark's is; the same commit queues nothing.
    mv "$report" "$LOGS/BORDERCALL-$id-$(bench_job_of "$report").md" || return 1
    echo "  the report above ended in failure on older code: queueing the stage again at $commit"
  fi
  if [ "$id" = full ] && ! bordercall_pilot_ended_well; then
    echo "refusing: bordercall full waits for a pilot report that ended well (send bordercall pilot first, then read it)"
    return 2
  fi
  [ -f "$REPO/grid/bordercall/bordercall/run.py" ] || { echo "refusing: no vendored bordercall under grid/bordercall/ at this commit"; return 2; }
  setup=$(setup_dependency) || return 1
  [ -z "$setup" ] || echo "  the environments: after the setup job that rebuilds them (${setup#afterok:})"
  holds=$(checkout_holders)
  [ -z "$holds" ] || echo "  the checkout: after the live runs that hold it ($holds)"
  depend_on "$(joined "$setup" "$holds")" || return 1
  submit "bordercall_$id" batch STAGE="$id" ${opts[@]+"${opts[@]}"} --no-requeue --time "$wall" -- bordercall.sbatch > /dev/null || return 1
  echo "submitted the bordercall stage $id. Send bordercall $id again once it ends to read its report, logs/BORDERCALL-$id.md."
}
word_bordercall_complete() {  # the gold tier 3 completion (the owner's count of 2026-10-29 15:22 UTC, one CPU job): queued once, its report printed on every later send
  local report=$LOGS/BORDERCALL-complete.md busy holds job opts=()
  busy=$( { live_of bordercall_pilot; live_of bordercall_full; live_of bordercall_complete; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: a bordercall stage is still queued or running (job $busy); send bordercall complete again once it ends"; return 75; }
  if [ -f "$report" ]; then
    # Kept, so the owner's count of one job holds: a report that stands queues nothing, failed or not,
    # since a second job is a second count and waits for his word.
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 200 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 30000
    return 0
  fi
  job=$(awk '$3 == "bordercall_complete" { job = $1 } END { print job }' "$STATE" 2>/dev/null)
  if [ -n "$job" ]; then
    [ ! -f "$report.part" ] || { echo "## $(basename "$report").part, unfinished: what job $job wrote before it ended"; head -n 200 "$report.part" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 30000; }
    echo "refusing: a bordercall complete job was queued before (job $job) and left no report; the owner's count was one job, so another waits for his word"
    return 64
  fi
  [ -f "$REPO/grid/bordercall/holdings/fullspine_complete.py" ] || { echo "refusing: no vendored matcher under grid/bordercall/holdings/ at this commit (tools/bordercall_vendor.py copy)"; return 2; }
  [ -f "$REPO/grid/bordercall-complete.sbatch" ] && [ -f "$REPO/tools/gold3_complete_grid.py" ] || { echo "refusing: no completion job script or tool at this commit"; return 2; }
  # The job runs in the SPINEPS environment's python, not the pixi environments, so no setup job goes
  # with it; it holds the checkout as a benchmark does, so it waits for the live runs that hold it.
  holds=$(checkout_holders)
  [ -z "$holds" ] || echo "  the checkout: after the live runs that hold it ($holds)"
  depend_on "$holds" || return 1
  submit bordercall_complete batch ${opts[@]+"${opts[@]}"} --no-requeue --time 08:00:00 -- bordercall-complete.sbatch > /dev/null || return 1
  echo "submitted the bordercall complete job: one CPU job that reads the census's SPINEPS masks and segments nothing. Send bordercall complete again once it ends to read its report, logs/BORDERCALL-complete.md."
}

word_totalseg() {  # the gold tier 3 completion's TotalSegmentator arm (the owner's word of 2026-10-30 08:54 UTC, "Add sacrum and c2 w total seg", and his count: one GPU job): queued once, its report printed on every later send
  local report=$LOGS/TOTALSEG-complete.md sent=$LOGS/TOTALSEG-complete.sent busy job holds zip row opts=() again=""
  case "$id" in
    complete) ;;
    *) echo "refusing: totalseg takes complete"; return 64 ;;
  esac
  busy=$(live_of totalseg_complete)
  [ -z "$busy" ] || { echo "refusing: the totalseg complete job is still queued or running (job $busy); send totalseg complete again once it ends"; return 75; }
  if [ -f "$report" ]; then
    # Kept, so the owner's count of one job holds: a report that stands queues nothing, failed or not,
    # since a second job is a second count and waits for his word, which names the report's job in
    # TOTALSEG_RERUNS (committed by pull request).
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 200 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 30000
    job=$(totalseg_job_of "$report")
    totalseg_rerun_allowed "$job" || return 0
    mv "$report" "$LOGS/TOTALSEG-complete-$job.md" || return 1
    again="is job $job's, which TOTALSEG_RERUNS lets the owner's count run once more"
  elif [ -f "$sent" ]; then
    # A submission whose answer was lost (the controller timed out after it queued the job) leaves no
    # record and no live job the gate knows, and the record it does find is the job before, which a
    # word for that job would let run again; so the mark is read first, and the owner's word for
    # another is complete:lost.
    totalseg_rerun_allowed lost || {
      echo "refusing: a totalseg complete job was submitted at $(cat "$sent") and no job id came back, so it may be queued or ended under Slurm's name schwingnet-totalseg_complete; another waits for the owner's word, committed as TOTALSEG_RERUNS=complete:lost in grid/gate.sh"
      return 64
    }
    rm -f "$sent"
    again="follows a submission whose answer was lost, which TOTALSEG_RERUNS lets the owner's count run once more"
  else
    job=$(awk '$3 == "totalseg_complete" { job = $1 } END { print job }' "$STATE" 2>/dev/null)
    if [ -n "$job" ]; then
      [ ! -f "$report.part" ] || { echo "## $(basename "$report").part, unfinished: what job $job wrote before it ended"; head -n 200 "$report.part" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 30000; }
      totalseg_rerun_allowed "$job" || {
        echo "refusing: a totalseg complete job was queued before (job $job) and left no report; the owner's count was one job, so another waits for his word, committed as TOTALSEG_RERUNS=complete:$job in grid/gate.sh"
        return 64
      }
      [ ! -f "$report.part" ] || mv "$report.part" "$LOGS/TOTALSEG-complete-$job.part" || return 1
      again="is job $job's, which TOTALSEG_RERUNS lets the owner's count run once more"
    fi
  fi
  [ -f "$REPO/grid/totalseg-complete.sbatch" ] && [ -f "$REPO/tools/gold3_totalseg_grid.py" ] && [ -f "$REPO/flows/totalseg.py" ] \
    || { echo "refusing: no totalseg job script, tool or flow at this commit"; return 2; }
  # The weights first: the job reads the two zips fetch totalseg_weights lands and never downloads, so
  # it is not queued while the fetch is live or a zip is not whole.
  busy=$(live_of dp_totalseg_weights)
  [ -z "$busy" ] || { echo "refusing: the fetch of totalseg_weights is still queued or running (job $busy); send totalseg complete again once it ends"; return 75; }
  # MOOSE's vertebrae model draws ENHANCE.PET's (the owner's word of 2026-10-30 09:33 UTC), so its
  # zips, fetch moose_weights, must be whole too.
  for row in totalseg_weights moose_weights; do
    zip=$(weights_zip_missing "$row")
    case "$zip" in
      "") ;;
      row) echo "refusing: the row $row of grid/run-platform-fetch.sh was not read, so no weight zip can be named"; return 2 ;;
      *" part") echo "refusing: the weight zip ${zip% part} under $DATA_ROOT/$row/raw is a part, still landing or cut short, which a resend of fetch $row resumes"; return 2 ;;
      *) echo "refusing: no ${zip% missing} under $DATA_ROOT/$row/raw (fetch $row first)"; return 2 ;;
    esac
  done
  # The job makes its own environment over train-gpu (grid/venv.sh), so no setup job goes with it; it
  # holds the checkout as a benchmark does, so it waits for the live runs that hold it.
  holds=$(checkout_holders)
  [ -z "$holds" ] || echo "  the checkout: after the live runs that hold it ($holds)"
  depend_on "$holds" || return 1
  # The job's script and shape are asked before the submission is marked, so a refusal marks nothing,
  # and the mark stands from before the submission until its answer names the job.
  launched_script totalseg-complete.sbatch || { echo "refusing: flows/registry.txt names no flow for totalseg-complete.sbatch, and every GPU job starts through flows/launch.py; nothing was queued"; return 90; }
  hpcw_check totalseg_complete gpu ${opts[@]+"${opts[@]}"} --no-requeue --time 06:00:00 -- totalseg-complete.sbatch || return 1
  [ -z "$again" ] || echo "  the totalseg complete job $again"
  echo "$(date -u '+%F %T') UTC at commit $commit" > "$sent" || { echo "refusing: the mark $(basename "$sent") could not be written, so a lost answer could not be told from none; nothing was queued"; return 1; }
  local queued
  queued=$(submit totalseg_complete gpu ${opts[@]+"${opts[@]}"} --no-requeue --time 06:00:00 -- totalseg-complete.sbatch) || return 1
  # The mark goes only once the gate's list names the job it queued, as morphometry covariates does:
  # a list the gate could not write would otherwise leave no mark and no record, and the next send
  # would read the job before as the last and let the word queue a second.
  awk -v job="$queued" '$1 == job && $3 == "totalseg_complete" { found = 1 } END { exit !found }' "$STATE" 2>/dev/null || {
    echo "  the gate's list (logs/GATE_JOBS.txt) does not name the job it queued (${queued:-no id}), so the marker logs/$(basename "$sent") stays and no second job follows without the owner's word"
    return 1
  }
  rm -f "$sent"
  echo "submitted the totalseg complete job: one GPU job that runs TotalSegmentator (VerSe, TotalSegmentator) or MOOSE (ENHANCE.PET) on each admitted study's own CT for the C2 or sacrum its release lacks. Send totalseg complete again once it ends to read its report, logs/TOTALSEG-complete.md."
}
totalseg_job_of() {  # the job number a totalseg complete report's first line names
  head -n 1 "$1" | sed -n 's/^# totalseg complete: job \([0-9][0-9]*\) .*/\1/p'
}
totalseg_rerun_allowed() {  # totalseg_rerun_allowed JOB: TOTALSEG_RERUNS names JOB (or lost) beside complete
  [ -n "$1" ] || return 1
  case " $TOTALSEG_RERUNS " in *" complete:$1 "*) return 0 ;; esac
  return 1
}

word_census() {  # the gold tier census (the owner's tap of 2026-10-29 12:26 UTC, one CPU job): queued once, its report printed on every later send
  local report=$LOGS/CENSUS-$id.md sent=$LOGS/CENSUS-$id.sent busy job missing again=""
  case "$id" in
    gold3) ;;
    *) echo "refusing: census takes gold3"; return 64 ;;
  esac
  busy=$(live_of "census_$id")
  [ -z "$busy" ] || { echo "refusing: the census $id job is still queued or running (job $busy); send census $id again once it ends"; return 75; }
  if [ -f "$report" ]; then
    # Kept, so the owner's count of one job holds: a report that stands queues nothing, unless the
    # owner's word for one more job names the report's job in CENSUS_RERUNS (committed by pull request).
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 400 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | report_shapes | masked | head -c 40000
    job=$(census_job_of "$report")
    census_detail "$job"
    census_rerun_allowed "$job" || return 0
    mv "$report" "$LOGS/CENSUS-$id-$job.md" || return 1
    again="is job $job's, which CENSUS_RERUNS lets the owner's count run once more"
  elif [ -f "$report.part" ]; then
    # A job that ended past its trap (killed outright, a node lost) leaves the parts it finished here.
    echo "## $(basename "$report").part, unfinished ($(date -r "$report.part" '+%F %T')): what the job wrote before it ended"
    head -n 400 "$report.part" | LC_ALL=C tr -cd '\11\12\40-\176' | report_shapes | masked | head -c 40000
  fi
  if [ -z "$again" ]; then
    job=$(awk -v what="census_$id" '$3 == what { job = $1 } END { print job }' "$STATE" 2>/dev/null)
    if [ -n "$job" ]; then
      census_rerun_allowed "$job" || {
        echo "refusing: a census $id job was queued before (job $job) and left no report; the owner's count was one job, so another waits for his word, committed as CENSUS_RERUNS=$id:$job in grid/gate.sh"
        return 64
      }
      [ ! -f "$report.part" ] || mv "$report.part" "$LOGS/CENSUS-$id-$job.part" || return 1
      again="is job $job's, which CENSUS_RERUNS lets the owner's count run once more"
    elif [ -f "$sent" ]; then
      # A submission whose answer was lost (the controller timed out after it queued the job) leaves no
      # record and no live job the gate knows; the owner's word, as above, is what queues another.
      census_rerun_allowed lost || {
        echo "refusing: a census $id job was submitted at $(cat "$sent") and no job id came back, so it may be queued or ended under Slurm's name schwingnet-census_$id; another waits for the owner's word, committed as CENSUS_RERUNS=$id:lost in grid/gate.sh"
        return 64
      }
      rm -f "$sent"
      again="follows a submission whose answer was lost, which CENSUS_RERUNS lets the owner's count run once more"
    fi
  fi
  [ -f "$REPO/tools/gold3_census.py" ] && [ -f "$REPO/grid/gold3-census.sbatch" ] || { echo "refusing: no census tool or job script at this commit"; return 2; }
  missing=$(census_inputs_missing)
  [ -z "$missing" ] || { echo "refusing: the census would read nothing from $missing; the one job is not spent on an empty root"; return 2; }
  # The job's shape is asked before the submission is marked, so a refused shape marks nothing.
  hpcw_check "census_$id" batch -- gold3-census.sbatch || return 1
  [ -z "$again" ] || echo "  the census $again"
  echo "$(date -u '+%F %T') UTC at commit $commit" > "$sent"
  submit "census_$id" batch CENSUS_COMMIT="$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo "")" -- gold3-census.sbatch > /dev/null || return 1
  rm -f "$sent"
  echo "submitted the census $id job: one CPU job that reads only and segments nothing. Send census $id again once it ends to read its report, logs/CENSUS-$id.md."
}
census_detail() {  # census_detail JOB: the two readings the report counts and the owner's rule needs by name (the owner, 2026-10-29 23:46 UTC)
  # The report carries counts alone. Two of them name what a pull request then records: the planes of
  # each TotalSegmentator CT the extent part found padded (constant slices at an end), which the CT's
  # own extent rule reads in place of the cord's guess (tools/gold3_field.py, data/gold3-ct/totalsegmentator/planes.json),
  # and VerSe's recorded mask names the held part found missing under the data root's VerSeFusion copy,
  # which the repair fetches. The copy holds many of its masks as symbolic links to files, which the
  # census's os.walk lists as files, so a link counts as found here too (the read of 2026-10-30 00:08
  # UTC named 89 with -type f alone, against the report's 17). Both are public ids and heights in millimetres, no path; the detail file
  # stays where the job left it, and the names are read here on the login node, as status reads a quota.
  local detail="${CENSUS_ROOT:-$VOLUME/go2432/gold3_census}/$1/extent.json" verse=$DATA_ROOT/versefusion/raw/VerSeFusion_data/raw
  echo "## census gold3 detail: the padded TotalSegmentator CTs' own planes (id, top mm, foot mm; none where the CT ends at its grid), job $1"
  if [ -f "$detail" ]; then
    # extent.json is json.dumps(indent=1, sort_keys=True): under "judged" each subject's planes are two
    # lines after its "planes": [ line, null where the CT gives no plane at that end.
    awk '
      /^ "judged": \{$/ { judged = 1; next }
      judged && /^ "/ { judged = 0 }
      !judged { next }
      /^  "[A-Za-z0-9_-]+": \{$/ { id = $1; gsub(/[":]/, "", id); next }
      /^   "planes": \[$/ { want = 2; top = ""; next }
      want == 2 { top = $1; sub(/,$/, "", top); want = 1; next }
      want == 1 { foot = $1; sub(/,$/, "", foot); want = 0
        if (top != "null" || foot != "null") { gsub(/null/, "none", top); gsub(/null/, "none", foot); print "  planes " id " " top " " foot; listed++ }
        next }
      END { print "  planes listed " (listed + 0) "; every other subject the report says it judged again has no padded end and keeps its field" }
    ' "$detail" | LC_ALL=C tr -cd '\11\12\40-\176' | masked
  else
    echo "  no extent detail for job $1 where the census keeps it; the planes are not read"
  fi
  echo "## census gold3 detail: VerSe's recorded mask names not found under the data root's VerSeFusion copy"
  if [ -d "$verse" ] && [ -f "$REPO/data/gold3-ct/verse/facts.jsonl" ]; then
    LC_ALL=C comm -23 <(grep -o '"[A-Za-z0-9_-]*_seg\.nii\.gz"' "$REPO/data/gold3-ct/verse/facts.jsonl" | tr -d '"' | sort -u) \
                      <(find "$verse" \( -type f -o -type l \) -name '*_seg.nii.gz' -printf '%f\n' 2>/dev/null | sort -u) \
      | sed 's/^/  not found /' | masked
    echo "  (the names are the facts' $(grep -o '"[A-Za-z0-9_-]*_seg\.nii\.gz"' "$REPO/data/gold3-ct/verse/facts.jsonl" | sort -u | wc -l) recorded, matched by name alone; the report's count matched the bytes too)"
  else
    echo "  no VerSeFusion copy under the data root, or no facts at this commit; the names are not read"
  fi
}
census_job_of() {  # the job number a census report's first line names
  head -n 1 "$1" | sed -n 's/^# census [a-z0-9]*: job \([0-9][0-9]*\) .*/\1/p'
}
census_rerun_allowed() {  # census_rerun_allowed JOB: CENSUS_RERUNS names JOB beside the census's id
  case " $CENSUS_RERUNS " in *" $id:$1 "*) return 0 ;; esac
  return 1
}
census_inputs_missing() {  # what the census would find no file of, one line, or nothing
  # Each root the parts read, tested on the login node as the data root holds them, so the one job is
  # never spent on a root that moved: every part counts a missing root as zero and ends 0.
  local what="" root
  lacks() { what="${what:+$what; }$1"; }
  [ -f "$VOLUME/go2432/ruleclass/tiers/tier1.tsv" ] && [ -f "$VOLUME/go2432/ruleclass/tiers/tier2.tsv" ] \
    || lacks "the census tier lists under the lab volume's go2432/ruleclass/tiers"
  for root in totalsegmentator_v300 aws_enhance_pet_labels/raw aws_enhance_pet_ct/raw tcia_fdg_pet_ct_lesions versefusion/raw/VerSeFusion_data/raw; do
    [ -d "$DATA_ROOT/$root" ] || lacks "$DATA_ROOT/$root"
  done
  echo "$what"
}
morphometry_inputs_missing() {  # what morphometry $id still lacks on the data root, one line, or nothing
  case "$id" in
    enhance)
      find "$DATA_ROOT/aws_enhance_pet_labels/raw" -path '*Vertebrae*' -name '*.nii.gz' -print -quit 2>/dev/null | grep -q . \
        || echo "ENHANCE.PET's truth (fetch aws_enhance_pet_labels first)" ;;
    verse)
      find "$DATA_ROOT/verse_masks_2026_10_29" -name '*.nii.gz' -print -quit 2>/dev/null | grep -q . \
        || { echo "VerSe's int16 masks (fetch verse_masks_2026_10_29 first)"; return; }
      find "$DATA_ROOT/totalsegmentator_v300" -mindepth 1 -print -quit 2>/dev/null | grep -q . \
        || echo "TotalSegmentator v3's release (fetch totalsegmentator_v300 first)" ;;
  esac
}
word_morphometry() {  # bordercall's morphometry engine over one gold tier 3 set (the owner's counts: 2026-10-29 15:19 UTC, one CPU job a set; 2026-10-30 14:33 UTC, one more a set, MORPHOMETRY_RERUNS): queued once a word, its report printed on every later send
  local report=$LOGS/MORPHOMETRY-$id.md sent=$LOGS/MORPHOMETRY-$id.sent busy job="" missing holds opts=() again="" lost="" keep="" before="" part_job queued
  case "$id" in
    enhance|verse) ;;
    covariates) word_morphometry_covariates; return ;;
    prior) word_morphometry_prior; return ;;
    *) echo "refusing: morphometry takes enhance or verse, covariates once both have run, or prior"; return 64 ;;
  esac
  # One at a time: both sets hold the checkout and write under one root, and the count is one job a set;
  # the join reads both sets' rows, so neither set is measured again while it runs. A job a lost answer
  # may have queued counts as one of them (morphometry_busy).
  busy=$(morphometry_busy)
  [ -z "${busy// /}" ] || { echo "refusing: a morphometry job is still queued or running (job $busy); send morphometry $id again once it ends"; return 75; }
  if [ -f "$report" ]; then
    # Kept, so the owner's count holds: a report that stands queues nothing, whether it ended 0 or in
    # failure, unless the owner's word for one more job names its job in MORPHOMETRY_RERUNS. A failure
    # waits for the word too, since any merge moves the checkout and nothing here tells a fix from
    # another change, and each job is up to a day of 32 CPUs.
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 200 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 30000
    job=$(bench_job_of "$report")
    morphometry_rerun_allowed "$id" "$job" || return 0
    again="the report above is job $job's, which MORPHOMETRY_RERUNS lets the owner's count measure once more"
    # A whole run's rows may have been joined, so they are kept beside its report under its job, where
    # no later job writes, and the next job measures every study again; a failed run's rows stay for the
    # next job, which keeps each study's rows its own code stamp wrote without an error and measures the rest.
    ! morphometry_ended_0 "$report" || keep=$job
  elif [ -f "$report.part" ]; then
    # A job that ended past its trap (cancelled, its time limit, a node lost) leaves what it wrote here.
    echo "## $(basename "$report").part, unfinished ($(date -r "$report.part" '+%F %T')): what the job wrote before it ended"
    head -n 200 "$report.part" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 30000
  fi
  if [ -z "$again" ]; then
    job=$(awk -v what="morphometry_$id" '$3 == what { job = $1 } END { print job }' "$STATE" 2>/dev/null)
    if [ -f "$sent" ]; then
      # A submission whose answer was lost leaves no record, and the job it may have queued is no longer
      # held by Slurm (morphometry_busy waited for it above); the word that named it was spent on it, so
      # another waits for the owner's word for the lost one (lost, then lost2, lost3 and on), as the join's does.
      lost=$(morphometry_lost_word "$id")
      morphometry_rerun_allowed "$id" "$lost" || {
        echo "refusing: a morphometry $id job was submitted at $(cat "$sent") and no job id came back, so it may be queued or ended under Slurm's name schwingnet-morphometry_$id; another waits for the owner's word, committed as MORPHOMETRY_RERUNS=$id:$lost in grid/gate.sh"
        return 64
      }
      again="the set follows a submission whose answer was lost, which MORPHOMETRY_RERUNS lets the owner's count run once more"
    elif [ -n "$job" ]; then
      # A job killed past its trap writes no report, only the part above, and was one of the count's jobs.
      morphometry_rerun_allowed "$id" "$job" || {
        echo "refusing: a morphometry $id job was queued before (job $job) and left no report; the owner's count was one job a set, so another waits for his word, committed as MORPHOMETRY_RERUNS=$id:$job in grid/gate.sh"
        return 64
      }
      again="the set's job $job left no report, which MORPHOMETRY_RERUNS lets the owner's count measure once more"
    fi
  fi
  [ -f "$REPO/grid/bordercall/morphometry/__main__.py" ] || { echo "refusing: no vendored morphometry under grid/bordercall/ at this commit"; return 2; }
  # The job draws the lines beside the rows (morphometry run --lines), which import morphoview.lines.
  [ -f "$REPO/grid/bordercall/morphoview/lines.py" ] || { echo "refusing: no vendored morphoview/lines.py under grid/bordercall/ at this commit, which the job's lines need"; return 2; }
  missing=$(morphometry_inputs_missing)
  [ -z "$missing" ] || { echo "refusing: morphometry $id needs $missing"; return 2; }
  [ -z "$keep" ] || morphometry_keep "$keep" check || return
  # No setup job: the set runs on the SPINEPS environment's interpreter, and its screening venv is its own.
  holds=$(checkout_holders)
  [ -z "$holds" ] || echo "  the checkout: after the live runs that hold it ($holds)"
  depend_on "$holds" || return 1
  # The job's shape is asked before anything is spent, so a refused shape moves and marks nothing.
  hpcw_check "morphometry_$id" batch SET="$id" DATA_ROOT="$DATA_ROOT" MORPHOMETRY_ROOT="$(morphometry_root)" ${opts[@]+"${opts[@]}"} --no-requeue --time 24:00:00 -- morphometry.sbatch || return 1
  # The marker comes before anything moves, so a gate that cannot write it refuses with nothing moved,
  # and it stands from here until the gate's list names the job it queued: an answer lost in between,
  # or a list the gate could not write, leaves a marker and never a second job.
  [ ! -f "$sent" ] || before=$(cat "$sent")
  echo "$(date -u '+%F %T') UTC at commit $commit" > "$sent" 2>/dev/null || {
    echo "refusing: the gate cannot write logs/$(basename "$sent"), the marker that keeps a lost answer from queueing a second job; nothing was moved or queued"
    return 1
  }
  # Only now, with nothing left to refuse it, is the word spent: a whole run's rows set aside under its
  # job, the report or the part it replaces under its job, each ending with where the files it names
  # went, and a lost answer's word recorded last. A move that fails queued nothing, so the marker goes
  # back as it stood before this send, and the next send moves what is left.
  if [ -n "$keep" ]; then
    morphometry_keep "$keep" || { marker_back "$sent" "$before"; return 1; }
  fi
  if [ -f "$report" ]; then
    mv "$report" "$LOGS/MORPHOMETRY-$id-$job.md" || { marker_back "$sent" "$before"; return 1; }
    morphometry_aside_note "$LOGS/MORPHOMETRY-$id-$job.md" "$keep"
  fi
  if [ -f "$report.part" ]; then
    part_job=$(bench_job_of "$report.part")
    mv "$report.part" "$LOGS/MORPHOMETRY-$id-${part_job:-${job:-unknown}}.part" || { marker_back "$sent" "$before"; return 1; }
    morphometry_aside_note "$LOGS/MORPHOMETRY-$id-${part_job:-${job:-unknown}}.part" ""
  fi
  if [ -n "$lost" ]; then
    echo "$id:$lost spent at $(date -u '+%F %T') UTC on the submission of $before" >> "$LOGS/MORPHOMETRY-$id.lost" \
      || { marker_back "$sent" "$before"; return 1; }
  fi
  [ -z "$again" ] || echo "  $again: queueing the set again at $commit"
  # The shape was asked above, before the mark, so job submit does not ask it again (HPCW_CHECKED): a
  # refusal there would queue nothing and still read as a lost answer, spending the word on no job.
  queued=$(HPCW_CHECKED=1 submit "morphometry_$id" batch SET="$id" DATA_ROOT="$DATA_ROOT" MORPHOMETRY_ROOT="$(morphometry_root)" ${opts[@]+"${opts[@]}"} --no-requeue --time 24:00:00 -- morphometry.sbatch) || return 1
  awk -v job="$queued" -v what="morphometry_$id" '$1 == job && $3 == what { found = 1 } END { exit !found }' "$STATE" 2>/dev/null || {
    echo "  the gate's list (logs/GATE_JOBS.txt) does not name the job it queued (${queued:-no id}), so the marker logs/$(basename "$sent") stays and no second job follows without the owner's word"
    return 1
  }
  rm -f "$sent"
  echo "submitted the morphometry job for $id. Send morphometry $id again once it ends to read its report, logs/MORPHOMETRY-$id.md."
}
morphometry_rerun_allowed() {  # morphometry_rerun_allowed SET WORD: MORPHOMETRY_RERUNS names WORD (a job, or a lost word) beside SET
  [ -n "$2" ] || return 1
  case " $MORPHOMETRY_RERUNS " in *" $1:$2 "*) return 0 ;; esac
  return 1
}
morphometry_lost_word() {  # morphometry_lost_word SET: the word that lets one more job follow the lost answer now standing: lost, then lost2, lost3 and on
  local spent=0
  [ ! -f "$LOGS/MORPHOMETRY-$1.lost" ] || spent=$(wc -l < "$LOGS/MORPHOMETRY-$1.lost")
  if [ "$spent" -eq 0 ]; then echo lost; else echo "lost$(( spent + 1 ))"; fi
}
morphometry_ended_0() {  # morphometry_ended_0 REPORT: its last line is a zero exit, a run that measured what it chose
  tail -n 1 "$1" 2>/dev/null | grep -q '^- exit 0 at '
}
morphometry_rerun_pending() {  # morphometry_rerun_pending SET: the set's standing report is one MORPHOMETRY_RERUNS names, so it is measured once more before any join
  [ -f "$LOGS/MORPHOMETRY-$1.md" ] && morphometry_rerun_allowed "$1" "$(bench_job_of "$LOGS/MORPHOMETRY-$1.md")"
}
morphometry_stamp() {  # morphometry_stamp REPORT: the code stamp a set's report names for the engine that measured it, or status 1 where it names none of the plain form
  local stamp
  stamp=$(sed -n 's/^- code stamp: \([0-9a-f]\{16\}\)$/\1/p' "$1" 2>/dev/null | head -n 1)
  [ -n "$stamp" ] || return 1
  echo "$stamp"
}
morphometry_keep() {  # morphometry_keep JOB [check]: a whole run's rows and step logs moved under the set's kept/JOB; with check, only whether they can be
  # Moved, never copied: kept/ is the set's own folder on one volume, so each move is a rename, and what
  # the next job reuses (the masks' links, the venv, TotalSegmentator's stacks) stays where it reads it.
  # A file already under kept/JOB is never written over: a person looks at both first.
  local out from to name sub
  out=$(morphometry_root)/$id
  for sub in "" totalseg; do
    [ -z "$sub" ] || [ "$id" = verse ] || continue
    for name in rows rows.csv run.log steps.log facts.log whole.log facts.jsonl facts.jsonl.part verdicts.csv inputs.txt ids.txt; do
      from=$out${sub:+/$sub}/$name to=$out/kept/$1${sub:+/$sub}/$name
      [ -e "$from" ] || [ -L "$from" ] || continue
      if [ -e "$to" ] || [ -L "$to" ]; then
        echo "refusing: $to is there already, so job $1's $name would land on it; a person looks at both first; nothing was queued"
        return 2
      fi
      [ "${2:-}" != check ] || continue
      mkdir -p "${to%/*}" && mv -T -- "$from" "$to" || { echo "refusing: $from could not be moved under kept/$1; nothing was queued, and the next send moves what is left"; return 1; }
    done
  done
}
morphometry_aside_note() {  # morphometry_aside_note FILE KEEP: the line a report or part the gate set aside ends with, where the files it names are now, added to FILE and printed
  # The set's folder is the next job's, so the paths and digests a kept report prints would name that
  # job's files; the line goes last, since only bench_job_of reads a kept report, and it reads line 1.
  local root note reused="the masks' links and the screening venv"
  root=$(morphometry_root)/$id
  [ "$id" != verse ] || reused="the masks' links, the screening venv and TotalSegmentator's stacks"
  if [ -n "$2" ]; then
    note="the rows, step logs, facts and verdicts it names under $root/ are under $root/kept/$2/ now, and $reused stay where they were, for the next job"
  else
    note="the files it names under $root/ stay there for the next job to resume from and write over, so the paths it names hold that job's files from now on"
  fi
  note="set aside by the gate at $(date -u '+%F %T') UTC for one more job: $note"
  echo "- $note" >> "$1" || echo "  the gate could not add its last line to logs/$(basename "$1"), which follows"
  echo "  logs/$(basename "$1") is $note"
}
morphometry_lost_live() {  # morphometry_lost_live SET: the live job a submission of SET whose answer was lost may have queued, while its marker stands, or nothing
  # The gate's list never named that job, so live_of cannot find it: once it runs, the part it writes
  # names it on its first line, and before that Slurm holds it under hpcworker's name for it (named_live).
  local job=""
  [ -f "$LOGS/MORPHOMETRY-$1.sent" ] || return 0
  [ ! -f "$LOGS/MORPHOMETRY-$1.md.part" ] || job=$(bench_job_of "$LOGS/MORPHOMETRY-$1.md.part")
  case "$QUEUED" in *" ${job:-none} "*) echo "$job"; return 0 ;; esac
  named_live "morphometry_$1" | head -n 1
}
morphometry_busy() {  # the live jobs of both sets and the join, those the gate's list names and those a lost answer may have queued, space-separated
  { live_of morphometry_enhance; live_of morphometry_verse; live_of morphometry_covariates; live_of morphometry_prior
    morphometry_lost_live enhance; morphometry_lost_live verse; morphometry_lost_live covariates; } | tr '\n' ' '
}
marker_back() {  # marker_back MARKER BEFORE: a send that queued nothing puts its marker back as it stood, BEFORE's text, or none where BEFORE is empty
  if [ -n "$2" ]; then echo "$2" > "$1"; else rm -f "$1"; fi
}

word_morphometry_prior() {  # the gold tier 3 correlation prior fitted from both sets' rows (greg, 2026-10-30): one CPU job, its report printed on the next send
  # greg's word of 2026-10-30 23:03 UTC lifted the counts for grid work, so a report from older code is
  # fitted again at this commit, whatever its exit; a report from this commit is printed and queues nothing.
  local report=$LOGS/MORPHOMETRY-prior.md sent=$LOGS/MORPHOMETRY-prior.sent busy head path
  busy=$( { live_of morphometry_enhance; live_of morphometry_verse; live_of morphometry_prior; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: a morphometry job is still queued or running (job $busy); send morphometry prior again once it ends"; return 75; }
  if [ -f "$report" ]; then
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 400 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | report_shapes | masked | head -c 64000
    began_on_older_code "$report" || return 0
    mv "$report" "$LOGS/MORPHOMETRY-prior-$(bench_job_of "$report").md" || return 1
    echo "  the report above is from older code: fitting again at $commit"
  fi
  # A marker older than the job's wall time names a submission whose answer was lost and whose job has
  # ended, so it no longer stands in the way; a younger one may be a job still queued.
  if [ -f "$sent" ]; then
    if [ -n "$(find "$sent" -mmin -180 2>/dev/null)" ]; then
      echo "refusing: a morphometry prior job was submitted at $(cat "$sent") and no job id came back; it may still be queued under Slurm's name schwingnet-morphometry_prior. Send morphometry prior again in three hours, or once squeue shows it ended"
      return 75
    fi
    rm -f "$sent"
  fi
  [ -f "$REPO/grid/prior/gold3_prior.py" ] && [ -f "$REPO/grid/morphometry-prior.sbatch" ] || { echo "refusing: no prior tool or job script at this commit"; return 2; }
  [ -f "$(morphometry_root)/enhance/rows.csv" ] || { echo "refusing: morphometry prior needs the enhance set's rows (send morphometry enhance first)"; return 2; }
  head=$(covariates_commit) || { echo "refusing: the gate cannot read the checkout's commit, which the job copies its code from; nothing was queued"; return 2; }
  for path in grid/prior/gold3_prior.py grid/prior/schwingcheck/correlation.py grid/prior/schwingcheck/__init__.py \
      data/gold3-ct/admission.json data/gold3-ct/verse/series.json data/splits/latent-prior-test-reserve.json \
      data/splits/latent-prior-repeat-groups.json; do
    git -C "$REPO" cat-file -e "$head:$path" 2>/dev/null || { echo "refusing: commit ${head:0:7} holds no $path, which the job copies; nothing was queued"; return 2; }
  done
  hpcw_check morphometry_prior batch -- morphometry-prior.sbatch || return 1
  echo "$(date -u '+%F %T') UTC at commit $commit" > "$sent" 2>/dev/null || {
    echo "refusing: the gate cannot write logs/$(basename "$sent"), the marker that keeps a lost answer from queueing a second job; nothing was queued"
    return 1
  }
  submit morphometry_prior batch PRIOR_COMMIT="$head" MORPHOMETRY_ROOT="$(morphometry_root)" -- morphometry-prior.sbatch > /dev/null || return 1
  rm -f "$sent"
  echo "submitted the morphometry prior job: one CPU job that reads the rows and writes the priors under the morphometry root. Send morphometry prior again once it ends to read its report, logs/MORPHOMETRY-prior.md."
}
word_morphometry_covariates() {  # the morphometry rows joined with each person's sex and age (one CPU job on the owner's count): queued once, its report printed a page a send
  local report=$LOGS/MORPHOMETRY-covariates.md sent=$LOGS/MORPHOMETRY-covariates.sent busy job missing again="" lost="" before="" head part_job path queued previous
  busy=$(morphometry_busy)
  [ -z "${busy// /}" ] || { echo "refusing: a morphometry job is still queued or running (job $busy); send morphometry covariates again once it ends"; return 75; }
  if [ -f "$report" ]; then
    # Kept, so the owner's count of one job holds: a report that stands queues nothing, unless the
    # owner's word for one more job names the report's job in COVARIATES_RERUNS (committed by pull request).
    covariates_page "$report"
    job=$(bench_job_of "$report")
    covariates_rerun_allowed "$job" || return 0
    again="is job $job's, which COVARIATES_RERUNS lets the owner's count run once more"
  elif [ -f "$report.part" ]; then
    # A job that ended past its trap (killed outright, a node lost) leaves what it wrote here.
    echo "## $(basename "$report").part, unfinished ($(date -r "$report.part" '+%F %T')): what the job wrote before it ended"
    head -n 200 "$report.part" | LC_ALL=C tr -cd '\11\12\40-\176' | report_shapes | masked | head -c 30000
  fi
  if [ -z "$again" ]; then
    job=$(awk '$3 == "morphometry_covariates" { job = $1 } END { print job }' "$STATE" 2>/dev/null)
    if [ -f "$sent" ]; then
      # A submission whose answer was lost (the controller timed out after it queued the job) leaves no
      # record, whether or not a job before it is recorded, and the job it may have queued is no longer
      # held by Slurm (morphometry_busy waited for it above): the lost one came after that job, so the
      # word that named it was spent on the lost one. The owner's word for the lost one queues another,
      # each lost answer its own word (lost, then lost2, lost3 and on), so a word whose job is lost too
      # queues nothing more.
      lost=$(covariates_lost_word)
      covariates_rerun_allowed "$lost" || {
        echo "refusing: a morphometry covariates job was submitted at $(cat "$sent") and no job id came back, so it may be queued or ended under Slurm's name schwingnet-morphometry_covariates; another waits for the owner's word, committed as COVARIATES_RERUNS=covariates:$lost in grid/gate.sh"
        return 64
      }
      again="follows a submission whose answer was lost, which COVARIATES_RERUNS lets the owner's count run once more"
    elif [ -n "$job" ]; then
      covariates_rerun_allowed "$job" || {
        echo "refusing: a morphometry covariates job was queued before (job $job) and left no report; the owner's count was one job, so another waits for his word, committed as COVARIATES_RERUNS=covariates:$job in grid/gate.sh"
        return 64
      }
      again="is job $job's, which COVARIATES_RERUNS lets the owner's count run once more"
    fi
  fi
  [ -f "$REPO/tools/gold3_covariates.py" ] && [ -f "$REPO/grid/morphometry-covariates.sbatch" ] || { echo "refusing: no join tool or job script at this commit"; return 2; }
  missing=$(covariates_inputs_missing)
  [ -z "$missing" ] || { echo "refusing: morphometry covariates needs $missing"; return 2; }
  # Read before the standing report is set aside, though covariates_previous finds it under its kept
  # name too; covariates_inputs_missing has already refused where it names no job.
  previous=$(covariates_previous) || { echo "refusing: an earlier join's report names no job, so the check across reports cannot find its joined table; nothing was queued"; return 2; }
  # The job copies its code from git at this commit, so a commit the gate cannot read, or one that does
  # not hold what the job copies, would spend the one job on a failure: refused here, spending nothing.
  head=$(covariates_commit) || { echo "refusing: the gate cannot read the checkout's commit, which the job copies its code from; nothing was queued"; return 2; }
  for path in tools/gold3_covariates.py tools/gold3_census.py tools/gold3_field.py data/gold3-ct \
      data/gold3-ct/admission.json data/gold3-ct/enhance-pet/facts.jsonl data/gold3-ct/verse/series.json \
      data/gold3-ct/totalsegmentator/subjects.json; do
    git -C "$REPO" cat-file -e "$head:$path" 2>/dev/null || { echo "refusing: commit ${head:0:7} holds no $path, which the job copies or reads; nothing was queued"; return 2; }
  done
  # The job's shape is asked before the submission is marked, so a refused shape marks nothing.
  hpcw_check morphometry_covariates batch -- morphometry-covariates.sbatch || return 1
  # The marker comes before anything moves, so a gate that cannot write it refuses with nothing moved,
  # and it stands from here until the gate's list names the job it queued: an answer lost in between,
  # or a list the gate could not write, leaves a marker and never a second job.
  [ ! -f "$sent" ] || before=$(cat "$sent")
  echo "$(date -u '+%F %T') UTC at commit $commit" > "$sent" 2>/dev/null || {
    echo "refusing: the gate cannot write logs/$(basename "$sent"), the marker that keeps a lost answer from queueing a second job; nothing was moved or queued"
    return 1
  }
  # Only now, with nothing left to refuse it, is the word spent: the report or the part it replaces set
  # aside under its job, and a lost answer's word recorded last, so it lets no later job follow. A move
  # that fails queued nothing, so the marker goes back as it stood before this send.
  if [ -f "$report" ]; then
    mv "$report" "$LOGS/MORPHOMETRY-covariates-$job.md" || { marker_back "$sent" "$before"; return 1; }
    rm -f "$LOGS/MORPHOMETRY-covariates.page"
  fi
  if [ -f "$report.part" ]; then
    part_job=$(bench_job_of "$report.part")
    mv "$report.part" "$LOGS/MORPHOMETRY-covariates-${part_job:-${job:-unknown}}.part" || { marker_back "$sent" "$before"; return 1; }
  fi
  if [ -n "$lost" ]; then
    echo "covariates:$lost spent at $(date -u '+%F %T') UTC on the submission of $before" >> "$LOGS/MORPHOMETRY-covariates.lost" \
      || { marker_back "$sent" "$before"; return 1; }
  fi
  [ -z "$again" ] || echo "  the join $again"
  [ -z "$previous" ] || echo "  the check across reports: each block checked against the earlier joins of jobs $previous"
  # The shape was asked above, before the mark, so job submit does not ask it again (HPCW_CHECKED): a
  # refusal there would queue nothing and still read as a lost answer, spending the word on no job.
  queued=$(HPCW_CHECKED=1 submit morphometry_covariates batch COVARIATES_COMMIT="$head" COVARIATES_PREVIOUS="$previous" \
    MORPHOMETRY_ROOT="$(morphometry_root)" AUTOPET="$(covariates_autopet)" INDEX="$(samples_index)" \
    VERSE_DEMOGRAPHICS="$(covariates_verse_table)" DATA_ROOT="$DATA_ROOT" -- morphometry-covariates.sbatch) || return 1
  awk -v job="$queued" '$1 == job && $3 == "morphometry_covariates" { found = 1 } END { exit !found }' "$STATE" 2>/dev/null || {
    echo "  the gate's list (logs/GATE_JOBS.txt) does not name the job it queued (${queued:-no id}), so the marker logs/$(basename "$sent") stays and no second job follows without the owner's word"
    return 1
  }
  rm -f "$sent"
  echo "submitted the morphometry covariates job: one CPU job that reads only, its per-person tables kept on the grid. Send morphometry covariates again once it ends to read its report, logs/MORPHOMETRY-covariates.md, a page a send."
}
covariates_commit() {  # the checkout's whole commit, which the job copies its code from, or status 1 where git gives none
  local head
  head=$(git -C "$REPO" rev-parse --verify -q 'HEAD^{commit}' 2>/dev/null) || return 1
  [[ $head =~ ^[0-9a-f]{40}([0-9a-f]{24})?$ ]] || return 1
  echo "$head"
}
covariates_lost_word() {  # the word that lets one more job follow the lost answer now standing: lost, then lost2, lost3 and on
  local spent=0
  [ ! -f "$LOGS/MORPHOMETRY-covariates.lost" ] || spent=$(wc -l < "$LOGS/MORPHOMETRY-covariates.lost")
  if [ "$spent" -eq 0 ]; then echo lost; else echo "lost$(( spent + 1 ))"; fi
}
covariates_rerun_allowed() {  # covariates_rerun_allowed JOB: COVARIATES_RERUNS names JOB beside covariates
  case " $COVARIATES_RERUNS " in *" covariates:$1 "*) return 0 ;; esac
  return 1
}
covariates_previous() {  # the jobs of every earlier join whose report printed cells, the standing one and those kept, once each; status 1 where one names no job
  # A report holding a member's line printed that member's cells, and they left the grid a page a
  # send, so the next join is checked against each such report's joined table; an unfinished part
  # counts too, since the gate prints a part, while a report that failed before the join printed
  # no cell and is no earlier join. A job beyond twelve digits is no Slurm job and the job refuses it.
  local file job jobs=""
  for file in "$LOGS/MORPHOMETRY-covariates.md" "$LOGS/MORPHOMETRY-covariates.md.part" \
      "$LOGS"/MORPHOMETRY-covariates-*.md "$LOGS"/MORPHOMETRY-covariates-*.part; do
    [ -f "$file" ] || continue
    grep -Eq '^- member [a-z]+: persons [0-9]+' "$file" || continue
    job=$(bench_job_of "$file")
    [[ $job =~ ^[0-9]{1,12}$ ]] || return 1
    case " $jobs " in *" $job "*) ;; *) jobs="${jobs:+$jobs }$job" ;; esac
  done
  echo "$jobs"
}
morphometry_root() {  # where grid/morphometry.sbatch writes both sets' rows, handed to each set's job so its folder and kept/ are the gate's
  echo "${MORPHOMETRY_ROOT:-$VOLUME/go2432/morphometry}"
}
covariates_verse_table() {  # VerSeFusion's demographics table, whose sha256 data/gold3-ct/verse/series.json records
  echo "${VERSE_DEMOGRAPHICS:-$HOME/VerSeFusion/configs/verse_demographics.csv}"
}
covariates_autopet() {  # the census job's map of autoPET's studies to PETCT keys, by the job its report names
  local job
  job=$(census_job_of "$LOGS/CENSUS-gold3.md" 2>/dev/null)
  [ -n "$job" ] || return 1
  echo "${CENSUS_ROOT:-$VOLUME/go2432/gold3_census}/$job/autopet.json"
}
covariates_inputs_missing() {  # what the join would find no file of, one line, or nothing
  # Each set's report must stand and have ended 0, since the rows of a set that failed or never ran are
  # no rows to join, and both must name one code stamp, since rows two engines measured would blend
  # in every table; then each earlier join's table the check across reports reads, and each input the
  # job reads, tested on the login node so the one job is never spent on a root that moved.
  local what="" set root autopet stamp enhance_stamp="" verse_stamp="" previous job
  lacks() { what="${what:+$what; }$1"; }
  for set in enhance verse; do
    if [ ! -f "$LOGS/MORPHOMETRY-$set.md" ]; then
      lacks "the morphometry $set report (send morphometry $set first)"
    elif ! morphometry_ended_0 "$LOGS/MORPHOMETRY-$set.md"; then
      lacks "a morphometry $set report that ended 0 (the one standing ended in failure)"
    elif morphometry_rerun_pending "$set"; then
      lacks "the morphometry $set rerun the owner counted (the report standing is job $(bench_job_of "$LOGS/MORPHOMETRY-$set.md")'s, which MORPHOMETRY_RERUNS names; send morphometry $set first)"
    elif stamp=$(morphometry_stamp "$LOGS/MORPHOMETRY-$set.md"); then
      case "$set" in enhance) enhance_stamp=$stamp ;; *) verse_stamp=$stamp ;; esac
    else
      lacks "a code stamp line in the morphometry $set report, which ties its rows to the engine that measured them"
    fi
  done
  if [ -n "$enhance_stamp" ] && [ -n "$verse_stamp" ] && [ "$enhance_stamp" != "$verse_stamp" ]; then
    lacks "both sets measured by one engine (the enhance report names code stamp $enhance_stamp and the verse report $verse_stamp; the set on the older engine is measured once more on the owner's word, MORPHOMETRY_RERUNS)"
  fi
  root=$(morphometry_root)
  if previous=$(covariates_previous); then
    for job in $previous; do
      [ -f "$root/covariates/$job/joined.csv" ] && [ -r "$root/covariates/$job/joined.csv" ] \
        || lacks "the joined table of the earlier join job $job (covariates/$job/joined.csv under the morphometry root), which the check across reports reads, since its report printed cells"
    done
  else
    lacks "a job named on the first line of every earlier join report that printed cells, whose joined table the check across reports reads"
  fi
  for set in enhance/rows.csv verse/rows.csv verse/totalseg/rows.csv; do
    [ -f "$root/$set" ] || lacks "the morphometry rows $set under the morphometry root"
  done
  if autopet=$(covariates_autopet); then
    [ -f "$autopet" ] || lacks "the census job's autopet map (autopet.json under the census root)"
  else
    lacks "the census report logs/CENSUS-gold3.md naming its job (send census gold3 first)"
  fi
  samples_index > /dev/null || lacks "a whole sample index (send samples first)"
  [ -f "$(covariates_verse_table)" ] || lacks "VerSeFusion's demographics table (configs/verse_demographics.csv in the VerSeFusion clone)"
  for root in totalsegmentator_v300 aws_enhance_pet_ct/raw; do
    [ -d "$DATA_ROOT/$root" ] || lacks "$DATA_ROOT/$root"
  done
  echo "$what"
}
covariates_page() {  # covariates_page REPORT: one page of the join's report, the next page on the next send, cycling
  # The report's first line (job, host, commit) and last (the exit) go with every page, so each page
  # says whose it is and how the job ended; the page number is kept beside the report by its job, so a
  # new report starts at page 1. Every line goes through report_shapes and the masks, as a census's does.
  local report=$1 mark=$LOGS/MORPHOMETRY-covariates.page job page=1 kept_job kept_page total body pages first last
  job=$(bench_job_of "$report")
  if [ -f "$mark" ] && read -r kept_job kept_page < "$mark" && [ "$kept_job" = "$job" ] && [[ $kept_page =~ ^[1-9][0-9]{0,5}$ ]]; then
    page=$kept_page
  fi
  total=$(wc -l < "$report")
  body=$(( total > 2 ? total - 2 : 0 ))
  pages=$(( body > 0 ? (body + COVARIATES_PAGE_LINES - 1) / COVARIATES_PAGE_LINES : 1 ))
  [ "$page" -le "$pages" ] || page=1
  first=$(( 2 + (page - 1) * COVARIATES_PAGE_LINES ))
  last=$(( first + COVARIATES_PAGE_LINES - 1 ))
  [ "$last" -le $(( total - 1 )) ] || last=$(( total - 1 ))
  echo "## $(basename "$report") ($(date -r "$report" '+%F %T')), page $page of $pages: its first line, lines $first to $last of $total, its last line; the next send prints page $(( page < pages ? page + 1 : 1 ))"
  {
    head -n 1 "$report"
    [ "$last" -lt "$first" ] || sed -n "${first},${last}p" "$report"
    [ "$total" -lt 2 ] || tail -n 1 "$report"
  } | LC_ALL=C tr -cd '\11\12\40-\176' | report_shapes | masked | head -c 64000
  echo "$job $(( page < pages ? page + 1 : 1 ))" > "$mark"
}

word_literature() {  # one reading list fetched onto the grid: queued once, its report printed and kept on the next send
  local report=$LOGS/LITERATURE-$id.md busy
  [ -f "$REPO/grid/literature/$id.csv" ] || { echo "refusing: no reading list grid/literature/$id.csv"; return 64; }
  busy=$(live_of literature "literature:$id")
  [ -z "$busy" ] || { echo "refusing: the fetch of the list $id is still queued or running (job $busy); send literature $id again once it ends"; return 75; }
  if [ -f "$report" ]; then
    # Printed once and kept under its job's number, so the send after this one fetches again what
    # is still missing (an Elsevier paper once its access opens) while the landing keeps what came.
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 200 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 30000
    mv "$report" "$LOGS/LITERATURE-$id-$(bench_job_of "$report").md" || return 1
    return 0
  fi
  if [ -f "$report.part" ]; then
    # A job killed past its own trap, by memory or a node's failure, leaves its report unfinished:
    # printed and kept the same way, so a failed run is never followed by a silent new one.
    echo "## $(basename "$report") unfinished: the job ended before it wrote its exit ($(date -r "$report.part" '+%F %T'))"
    head -n 200 "$report.part" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 30000
    mv "$report.part" "$LOGS/LITERATURE-$id-$(bench_job_of "$report.part")-unfinished.md" || return 1
    return 0
  fi
  submit literature batch LIST_ID="$id" DATA_ROOT="$DATA_ROOT" VOLUME="$VOLUME" -- literature.sbatch > /dev/null || return 1
  echo "submitted one job. It lands a byte only once the size rule admits it; send literature $id again once it ends to read its report, logs/LITERATURE-$id.md."
}

realism_class() {  # the job class a stage of the reproduction runs as, else nothing
  case "$1" in
    edit|stats) echo gpu ;;
  esac
}
realism_report_ok() {  # a stage's report that ends in exit 0, so the stage after it may run
  [ -f "$LOGS/REALISM-$1.md" ] && tail -n 1 "$LOGS/REALISM-$1.md" | grep -q '^- exit 0 '
}
klein_landed() {  # klein_landed <4b|9b|base-4b|base-9b>: that FLUX.2 klein's diffusers folder is on the data root
  local root=$DATA_ROOT/hf_flux2_klein_${1//-/_}/raw
  [ -d "$root" ] && find "$root" -maxdepth 3 -name model_index.json -print -quit 2>/dev/null | grep -q .
}
realism_inputs_missing() {  # what realism $id still lacks on the data root or in the reports, one line, or nothing
  case "$id" in
    edit)
      # The recipe's klein-9B and no other (PREREG.md, section 2): a klein-4B on the data root stands in for nothing.
      klein_landed 9b || { echo "FLUX.2 klein-9B's weights (fetch hf_flux2_klein_9b first)"; return; }
      weights_ready || { echo "ResNet-18's ImageNet weights at $WEIGHTS, which the imagenet space reads (the weights job makes them)"; return; }
      find "$DATA_ROOT/hf_flexray_weights/raw" -maxdepth 3 -name ensemble.json -print -quit 2>/dev/null | grep -q . \
        || { echo "FleXray's weights (fetch hf_flexray_weights first)"; return; }
      find "$DATA_ROOT/hf_flexray_data/raw" -path '*FluXray*' -name samples.csv -print -quit 2>/dev/null | grep -q . \
        || { echo "FluXray's samples.csv (fetch hf_flexray_data first)"; return; }
      find "$DATA_ROOT/aws_enhance_pet_ct/raw" -name '*.nii.gz' -print -quit 2>/dev/null | grep -q . \
        || { echo "ENHANCE.PET's CTs (fetch aws_enhance_pet_ct first)"; return; }
      find "$DATA_ROOT/aws_enhance_pet_labels/raw" -path '*Vertebrae*' -name '*.nii.gz' -print -quit 2>/dev/null | grep -q . \
        || echo "ENHANCE.PET's truth (fetch aws_enhance_pet_labels first)" ;;
    stats)
      realism_report_ok edit || echo "the edit stage's report ending in exit 0 (send realism edit first)" ;;
  esac
}
word_realism() {  # one stage of the Flux realism programme: queued once, its report printed on every later send
  local report=$LOGS/REALISM-$id.md class busy missing holds opts setup
  class=$(realism_class "$id")
  case "$id" in
    lora|eval) echo "refusing: realism $id waits for a count and a PREREG of its own; the count of 2026-10-29 is edit, then stats"; return 64 ;;
  esac
  [ -n "$class" ] || { echo "refusing: realism takes edit or stats, one stage at a time, in that order"; return 64; }
  busy=$(live_of "realism_$id")
  [ -z "$busy" ] || { echo "refusing: the realism stage $id is still queued or running (job $busy); send realism $id again once it ends"; return 75; }
  if [ -f "$report" ]; then
    # Kept, so each stage runs once on the owner's word: a report that stands queues nothing.
    echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    head -n 200 "$report" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 30000
    bench_failed_on_older_code "$report" || return 0
    # A stage that failed decided nothing, so once a fix has moved the checkout it is queued once
    # more, its report kept under its job's number, as a benchmark's is; the same commit queues nothing.
    mv "$report" "$LOGS/REALISM-$id-$(bench_job_of "$report").md" || return 1
    echo "  the report above ended in failure on older code: queueing the stage again at $commit"
  fi
  if [ -f "$report.part" ]; then
    # A job ended past its own trap (its time, a cancel, memory or a node's failure) leaves its
    # report unfinished and decided nothing, so it stands as a failed report does: printed on every
    # send, and queued again only once a fix has moved the checkout, its record kept under its job's
    # number, since a new job at the same commit would be one the count never gave and would write
    # over that record.
    echo "## $(basename "$report") unfinished: the job ended before it wrote its exit ($(date -r "$report.part" '+%F %T'))"
    head -n 200 "$report.part" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 30000
    began_on_older_code "$report.part" || return 0
    mv "$report.part" "$LOGS/REALISM-$id-$(bench_job_of "$report.part")-unfinished.md" || return 1
    echo "  the unfinished report above began on older code: queueing the stage again at $commit"
  fi
  missing=$(realism_inputs_missing)
  [ -z "$missing" ] || { echo "refusing: realism $id needs $missing"; return 2; }
  setup=$(setup_dependency) || return 1
  [ -z "$setup" ] || echo "  the environments: after the setup job that rebuilds them (${setup#afterok:})"
  holds=$(checkout_holders)
  [ -z "$holds" ] || echo "  the checkout: after the live runs that hold it ($holds)"
  depend_on "$(joined "$setup" "$holds")" || return 1
  submit "realism_$id" "$class" STAGE="$id" DATA_ROOT="$DATA_ROOT" ${opts[@]+"${opts[@]}"} --no-requeue -- realism.sbatch > /dev/null || return 1
  echo "submitted the realism stage $id. Send realism $id again once it ends to read its report, logs/REALISM-$id.md."
}

autoanatomist_kind() {  # autoanatomist_kind PLAN: the kind the plan runs as, autoanatomist2 for a plan AUTOANATOMIST2_PLANS names, else autoanatomist
  case " $AUTOANATOMIST2_PLANS " in *" $1 "*) echo autoanatomist2 ;; *) echo autoanatomist ;; esac
}
autoanatomist_counted() {  # autoanatomist_counted PLAN: status 0 where AUTOANATOMIST_COUNTED names the plan
  case " $AUTOANATOMIST_COUNTED " in *" $1 "*) return 0 ;; esac
  return 1
}
autoanatomist_rerun_allowed() {  # autoanatomist_rerun_allowed WHAT: AUTOANATOMIST_RERUNS names WHAT, a job or lost, beside the plan
  [ -n "$1" ] || return 1
  case " $AUTOANATOMIST_RERUNS " in *" $id:$1 "*) return 0 ;; esac
  return 1
}
autoanatomist_waits() {  # autoanatomist_waits PLAN: the plans AUTOANATOMIST_AFTER puts before PLAN whose reports do not end in exit 0, space-separated
  local pair before waits=""
  for pair in $AUTOANATOMIST_AFTER; do
    [ "${pair%%:*}" = "$1" ] || continue
    before=${pair#*:}
    [ -f "$LOGS/AUTOANATOMIST-$before.md" ] && tail -n 1 "$LOGS/AUTOANATOMIST-$before.md" | grep -q '^- exit 0 ' \
      || waits=${waits:+$waits }$before
  done
  echo "$waits"
}
autoanatomist_note() {  # autoanatomist_note LINE: one more line on the send's record, where the record stands
  [ ! -f "$LOGS/AUTOANATOMIST-$id.md.part" ] || echo "- $1" >> "$LOGS/AUTOANATOMIST-$id.md.part"
}
flow_prereg() {  # flow_prereg KIND: the PREREG flows/registry.txt names for a launched flow's kind, else nothing
  awk -v kind="$1" '$1 == kind && NF == 5 { print $5; exit }' "$REPO/flows/registry.txt" 2>/dev/null
}
screen_covered() {  # screen_covered PLAN NAME: status 0 where the screen's frozen PREREG covers the plan, by its name and bytes; the refusal otherwise
  # The launcher holds every part to the same PREREG and part (flows/stage.py); a plan it would stop
  # is refused here, before a card is spent, as sweep_covered refuses a sweep's.
  local prereg entry frozen bytes want
  prereg=$(flow_prereg "$(autoanatomist_kind "$2")")
  case "$prereg" in
    ""|/*|../*|*/../*) echo "refusing: flows/registry.txt names no PREREG inside the checkout for the screen, so no plan is covered; nothing was queued"; return 90 ;;
  esac
  frozen=$(awk 'NR == 1 && NF == 2 && ($2 == "PREREG.md" || $2 == "*PREREG.md") { print $1 }' "$REPO/$prereg.sha256" 2>/dev/null)
  bytes=$(sha256sum < "$REPO/$prereg" 2>/dev/null | cut -c1-64)
  if [ -z "$frozen" ] || [ "$frozen" != "$bytes" ]; then
    echo "refusing: STOP: $prereg is not frozen as its PREREG.md.sha256 says (the Lab Recipe's freeze), so no screen runs under it; nothing was queued"
    return 90
  fi
  entry=$(covers_entry "$REPO/$prereg" "$2")
  if [ -z "$entry" ]; then
    echo "refusing: $prereg does not cover the plan $2, which waits for a PREREG of its own, frozen before it runs; nothing was queued"
    return 90
  fi
  case "$entry" in
    *=*)
      want=${entry#*=}
      bytes=$(sha256sum < "$1" | cut -c1-64)
      if [ "$want" != "$bytes" ]; then
        echo "refusing: $prereg covers $2 as the bytes of sha256 ${want:0:16}, and grid/screens/$2.json's are ${bytes:0:16}: a plan changed since the freeze is another design, which waits for a PREREG of its own; nothing was queued"
        return 90
      fi ;;
  esac
}
# A plan is read from the text tools/autoanatomist_plan.py writes, json.dumps with indent 2, which the
# PREREG covers by its bytes, so the login node reads it with sed and awk and runs no python.
screen_field() {  # screen_field PLAN KEY: a top-level word of the plan, else nothing
  sed -n "s/^  \"$2\": \"\([a-z0-9_]*\)\",\{0,1\}\$/\1/p" "$1" | head -n 1
}
screen_trials() {  # screen_trials PLAN: the plan's trials, every arm at every seed, as schwingnet.autoanatomist_screen.trials counts them
  # The arms are the keys one level inside "arms", the seeds the numbers one level inside "seeds";
  # the flow refuses a task count other than the plan's (--tasks), so a miscount stops there.
  awk '
    /^  "arms": \{$/ { block = "arms"; next }
    /^  "seeds": \[$/ { block = "seeds"; next }
    /^  []}]/ { block = ""; next }
    block == "arms" && /^    "[a-z0-9_]+": \[/ { arms++ }
    block == "seeds" && /^    [0-9]+,?$/ { seeds++ }
    END { print arms * seeds }
  ' "$1"
}
screen_sources() {  # screen_sources PLAN: the sources the plan's data block names, one a line
  awk '/^  "data": \{$/ { on = 1; next } on && /^  []}]/ { exit } on && /^    "[a-z0-9_]+": \{$/ { name = $1; gsub(/[":]/, "", name); print name }' "$1"
}
screen_data() {  # screen_data PLAN SOURCE KEY: one word of a source's entry in the plan's data block, else nothing
  awk -v source="$2" -v key="$3" '
    /^  "data": \{$/ { on = 1; next }
    on && /^  []}]/ { exit }
    on && /^    "[a-z0-9_]+": \{$/ { name = $1; gsub(/[":]/, "", name); next }
    on && name == source && index($0, "      \"" key "\": \"") == 1 { value = substr($0, length(key) + 12); sub(/",?$/, "", value); print value; exit }
  ' "$1"
}
autoanatomist_inputs_missing() {  # autoanatomist_inputs_missing PLAN: what the plan's sources still lack on the data root, one line, or nothing
  # Each source's CT folder and label maps, as the plan names them and the trials read them (a label
  # map is the file of a row's id under a folder of labels_folder's name), so no card waits on a fetch.
  local source sources ct labels folder value
  sources=$(screen_sources "$1")
  [ -n "$sources" ] || { echo "a source in the plan's data block, which names none"; return; }
  for source in $sources; do
    ct=$(screen_data "$1" "$source" ct) labels=$(screen_data "$1" "$source" labels) folder=$(screen_data "$1" "$source" labels_folder)
    for value in "$ct" "$labels" "$folder"; do
      case "$value" in ""|/*|*..*|*[!A-Za-z0-9_./-]*) echo "a plain folder under the data root for the source $source's ct, labels and labels_folder"; return ;; esac
    done
    find "$DATA_ROOT/$ct" -name '*.nii.gz' -print -quit 2>/dev/null | grep -q . \
      || { echo "the source $source's CTs under $ct (fetch ${ct%%/*} first)"; return; }
    find "$DATA_ROOT/$labels" -path "*/$folder/*" -name '*.nii.gz' -print -quit 2>/dev/null | grep -q . \
      || { echo "the source $source's label maps under $labels, in folders named $folder (fetch ${labels%%/*} first)"; return; }
  done
}
autoanatomist_live() {  # the plan's live jobs, its series or trials' array and its join, space-separated
  { live_of "autoanatomist_$id"; live_of "autoanatomist_${id}_join"; } | tr '\n' ' ' | sed 's/ $//'
}
autoanatomist_chain() {  # the newest chain the gate queued for the plan, its series job or trials' array, else nothing
  awk -v what="autoanatomist_$id" '$3 == what { job = $1 } END { print job }' "$STATE" 2>/dev/null
}
autoanatomist_progress() {  # autoanatomist_progress CHAIN: where each trial of the chain stands, its PROGRESS.txt's last line, masked
  local folder=$AUTOANATOMIST_ROOT/$id/$1 file
  if ! compgen -G "$folder/trials/*/PROGRESS.txt" > /dev/null; then
    echo "  no trial of chain $1 has written its PROGRESS.txt yet: each starts it once its card is ready"
    return 0
  fi
  echo "  where each trial of chain $1 stands, the last line of its PROGRESS.txt:"
  for file in "$folder"/trials/*/PROGRESS.txt; do
    echo "    $(basename "$(dirname "$file")"): $(tail -n 1 "$file")"
  done | LC_ALL=C tr -cd '\11\12\40-\176' | masked
}
autoanatomist_unstarted() {  # autoanatomist_unstarted PART: the record is the gate's own, of a send no part of which made its folder
  # Every part makes its chain's folder before anything else (grid/autoanatomist.sbatch), so a send
  # Slurm ended before it started (a cancel, or a job it waited on failed) spent nothing.
  local job
  head -n 1 "$1" | grep -q '; no part of it has started yet$' || return 1
  job=$(bench_job_of "$1")
  [ -n "$job" ] && [ ! -e "$AUTOANATOMIST_ROOT/$id/$job" ]
}
autoanatomist_queued() {  # autoanatomist_queued CHAIN WHAT: the send's record where its report goes, until a part of it writes its own
  # Each part that writes the report starts it again under this name, so a send whose join never ran
  # still leaves a record a later send reads; set -C makes the file only where no part has yet.
  ( set -C
    { echo "# autoanatomist $id: job $1 queued, commit ${commit:0:7}, $(date -u '+%F %T') UTC; no part of it has started yet"
      echo "- queued: $2"
      echo "- folder: $AUTOANATOMIST_ROOT/$id/$1, where every part works"; } > "$LOGS/AUTOANATOMIST-$id.md.part" ) 2>/dev/null
  return 0
}
word_autoanatomist() {  # one plan of the auto-anatomist screen, on the owner's count: queued once, its report printed on every later send
  local plan=$REPO/grid/screens/$id.json report=$LOGS/AUTOANATOMIST-$id.md sent=$LOGS/AUTOANATOMIST-$id.sent
  local layout class trials busy record job kept again="" aside="" waits missing full setup opts screen chain join
  local script
  script=$(autoanatomist_kind "$id").sbatch
  [ -f "$plan" ] || { echo "refusing: no plan grid/screens/$id.json at commit $commit"; return 64; }
  autoanatomist_counted "$id" || {
    echo "refusing: the plan $id waits for the owner's word and count of its jobs, committed in AUTOANATOMIST_COUNTED in grid/gate.sh by pull request; nothing was queued"
    return 64
  }
  screen_covered "$plan" "$id" || return
  layout=$(screen_field "$plan" layout) class=$(screen_field "$plan" class) trials=$(screen_trials "$plan")
  case "$layout:$class" in
    series:gpu|array:gpu) ;;
    *) echo "refusing: the plan $id is laid out as '${layout:-none}' on '${class:-none}', and the screen runs a series or an array on gpu; nothing was queued"; return 64 ;;
  esac
  [[ $trials =~ ^[1-9][0-9]?$ ]] || { echo "refusing: the plan $id holds ${trials:-no} trials as the gate counts them, and a send takes 1 to 99; nothing was queued"; return 64; }
  busy=$(autoanatomist_live)
  if [ -n "$busy" ]; then
    echo "refusing: the plan $id is still queued or running (job ${busy// /, job }); send autoanatomist $id again once it ends"
    autoanatomist_progress "$(autoanatomist_chain)"
    return 75
  fi
  if [ -f "$report" ] || [ -f "$report.part" ]; then
    # Kept, so the owner's count holds: a record that stands queues nothing, but for a send that
    # failed or never finished, queued once more once a fix has moved the checkout, as a realism
    # stage is, a send that never started, and one AUTOANATOMIST_RERUNS names by its job.
    record=$report kept=""
    [ -f "$record" ] || record=$report.part kept=-unfinished
    if [ -z "$kept" ]; then
      echo "## $(basename "$report") ($(date -r "$report" '+%F %T'))"
    else
      echo "## $(basename "$report") unfinished: the send ended before it wrote its exit ($(date -r "$record" '+%F %T'))"
    fi
    head -n 200 "$record" | LC_ALL=C tr -cd '\11\12\40-\176' | masked | head -c 30000
    job=$(bench_job_of "$record")
    if autoanatomist_rerun_allowed "$job"; then
      again="the record above is job $job's, which AUTOANATOMIST_RERUNS lets the owner's word run once more"
    elif [ -z "$kept" ] && bench_failed_on_older_code "$report"; then
      again="the report above ended in failure on older code"
    elif [ -n "$kept" ] && autoanatomist_unstarted "$record"; then
      again="Slurm ended the send above before any part of it started" kept=-unstarted
    elif [ -n "$kept" ] && began_on_older_code "$record"; then
      again="the unfinished report above began on older code"
    else
      return 0
    fi
    aside=$LOGS/AUTOANATOMIST-$id-$job$kept.md
  elif [ -f "$sent" ]; then
    # A submission whose answer was lost leaves no record and no live job the gate knows; the mark
    # stays until the new send's own mark takes its place.
    autoanatomist_rerun_allowed lost || {
      echo "refusing: a send of the plan $id was submitted at $(cat "$sent") and no job id came back, so it may be queued or ended under Slurm's name schwingnet-autoanatomist_$id; another waits for the owner's word, committed as AUTOANATOMIST_RERUNS=$id:lost in grid/gate.sh"
      return 64
    }
    again="a submission whose answer was lost came before, and AUTOANATOMIST_RERUNS lets the owner's word run once more"
  fi
  waits=$(autoanatomist_waits "$id")
  if [ -n "$waits" ]; then
    echo "refusing: the plan $id is sent only once the report of ${waits// / and } (logs/AUTOANATOMIST-${waits%% *}.md) ends in exit 0, as its PREREG says; send autoanatomist ${waits%% *} first; nothing was queued"
    return 2
  fi
  missing=$(autoanatomist_inputs_missing "$plan")
  [ -z "$missing" ] || { echo "refusing: the plan $id needs $missing"; return 2; }
  full=$(git -C "$REPO" rev-parse HEAD 2>/dev/null)
  [[ $full =~ ^[0-9a-f]{40}$ ]] || { echo "refusing: the checkout's commit cannot be read, and every part of the screen copies the code at it"; return 2; }
  setup=$(setup_dependency) || return 1
  [ -z "$setup" ] || echo "  the environments: after the setup job that rebuilds them (${setup#afterok:})"
  screen=(PLAN="$id" TRIAL_TASKS="$trials" AUTOANATOMIST_COMMIT="$full" AUTOANATOMIST_ROOT="$AUTOANATOMIST_ROOT" DATA_ROOT="$DATA_ROOT")
  # What can refuse a send without queueing anything is asked before the send is marked, so the
  # submission after the mark can fail only where its answer may have been lost, which the mark is
  # for: the job script, which submit refuses for a GPU job no flow names, and each shape, an array
  # asked as one of its tasks, since job submit asks no array first (grid/hpcw.sh). The series is
  # then submitted with HPCW_CHECKED, so job submit does not ask its shape a second time after the mark.
  launched_script "$script" || {
    echo "refusing: flows/registry.txt names grid/$script as no flow's job script, and every GPU job starts through flows/launch.py; nothing was queued"
    return 90
  }
  hpcw_check "autoanatomist_$id" gpu "${screen[@]}" PART="$([ "$layout" = series ] && echo series || echo trial)" \
    --partition "$AUTOANATOMIST_PARTITION" --cpus 8 --mem 64G --time 12:00:00 --no-requeue -- "$script" || return 1
  if [ "$layout" = array ]; then
    hpcw_check "autoanatomist_${id}_join" batch "${screen[@]}" PART=join TRIALS_JOB=1 --cpus 4 --mem 16G --time 02:00:00 --no-requeue -- "$script" || return 1
  fi
  [ -z "$again" ] || echo "  $again: queueing the plan again at $commit"
  depend_on "$setup" || return 1
  # The record a send again replaces moves aside only here, past every refusal, so a send refused
  # leaves it where the next send reads it, and the new send's record never meets the old one.
  [ -z "$aside" ] || mv "$record" "$aside" || return 1
  echo "$(date -u '+%F %T') UTC at commit $commit" > "$sent"
  if [ "$layout" = series ]; then
    chain=$(HPCW_CHECKED=1 submit "autoanatomist_$id" gpu "${screen[@]}" PART=series ${opts[@]+"${opts[@]}"} \
      --partition "$AUTOANATOMIST_PARTITION" --cpus 8 --mem 64G --time 12:00:00 --no-requeue -- "$script") || return 1
    # The mark goes once the send's record stands, so a record that could not be written leaves the
    # send read as one whose answer was lost, never as no send at all.
    autoanatomist_queued "$chain" "one GPU job on $AUTOANATOMIST_PARTITION, the plan's $trials trials one after another on one card, then the join on the same node"
    [ ! -f "$report.part" ] || rm -f "$sent"
    echo "submitted the plan $id: one GPU job ($chain) that trains its $trials trials one after another on one card and then joins them, in $AUTOANATOMIST_ROOT/$id/$chain. Send autoanatomist $id again once it ends to read its report, logs/AUTOANATOMIST-$id.md."
    return 0
  fi
  chain=$(submit "autoanatomist_$id" gpu "${screen[@]}" PART=trial ${opts[@]+"${opts[@]}"} --array "0-$((trials - 1))" \
    --partition "$AUTOANATOMIST_PARTITION" --cpus 8 --mem 64G --time 12:00:00 --no-requeue -- "$script") || return 1
  # The record names the array as soon as it is queued, before its join is asked for, so trials whose
  # join is refused and whose cancel then fails leave a record a later send reads, and are never
  # queued again on the same count; a send Slurm ended before any trial started reads as unstarted.
  autoanatomist_queued "$chain" "the trials' array $chain, $trials tasks of a card of $AUTOANATOMIST_PARTITION each, and its join on a CPU node afterany it"
  [ ! -f "$report.part" ] || rm -f "$sent"
  # Both or neither, as the DRR domain-gap study queues its steps: trials whose join was refused would
  # leave no decision and no report. The join waits for the setup as the trials do, so a setup that
  # fails ends both before either starts, the send then reading as one that never started.
  if ! depend_on "$(joined "$setup" "afterany:$chain")" || ! join=$(submit "autoanatomist_${id}_join" batch "${screen[@]}" PART=join TRIALS_JOB="$chain" \
    ${opts[@]+"${opts[@]}"} --cpus 4 --mem 16G --time 02:00:00 --no-requeue -- "$script"); then
    if "$SCANCEL" "$chain"; then
      autoanatomist_note "join: refused, so the gate cancelled the trials' array $chain"
      echo "  cancelled the trials' array $chain, since its join was refused"
    else
      autoanatomist_note "join: refused, and the gate's cancel of the trials' array $chain failed"
      echo "  the join was refused and the cancel of the trials' array $chain failed: it may still run, and its record stands, so the plan is not queued again on this count"
    fi
    return 1
  fi
  autoanatomist_note "join: job $join on a CPU node, afterany the trials' array"
  echo "submitted the plan $id: the trials' array $chain ($trials tasks, each on the first card of $AUTOANATOMIST_PARTITION that frees) and the join $join afterany it on a CPU node, in $AUTOANATOMIST_ROOT/$id/$chain. Send autoanatomist $id again once they end to read its report, logs/AUTOANATOMIST-$id.md."
}

word_samples() {
  local busy said rc
  busy=$( { live_of samples_plan; live_of samples_scan; live_of samples_merge; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: the sample index is still queued or running (jobs $busy)"; return 75; }
  envs_ready || { echo "refusing: the environments are not ready; 'start' makes them first"; return 75; }
  said=$(bash "$REPO/grid/run-samples.sh" 2>&1)
  rc=$?
  echo "$said" | sed 's/^/  /'
  # Every job this call printed is recorded, a refusal part-way or not, so 'stop' reaches it.
  echo "$said" | sed -n 's/^\(samples_[a-z]*\): job \([0-9][0-9]*\)$/\2 \1/p' | while read -r job what; do
    record "$job" "$what" > /dev/null
  done
  [ "$rc" = 0 ] || return 1
  echo "submitted. 'status' shows the index's MANIFEST.md (counts per source) once the merge ends."
}

# The block smoke test (issue #252). A plan is a file tools/block_sweep.py wrote with indent 1 and
# sorted keys, so its own keys are the lines one space in and a row's sit deeper; the login node
# runs no python, so sed and grep read it.
sweep_plans() {  # the plans under grid/sweeps/, by name
  local one names=""
  for one in "$REPO"/grid/sweeps/*.json; do [ -f "$one" ] && names="$names $(basename "$one" .json)"; done
  echo "${names# }"
}
plan_catalog() {  # plan_catalog FILE: the plan's catalog: synthetic, v1 or with:<source>
  sed -n 's/^ "catalog": "\([^"]*\)",\{0,1\}$/\1/p' "$1" | head -n 1
}
plan_names_weights() {  # plan_names_weights FILE: whether a row of the plan starts from an ImageNet file
  grep -q '^  *"weights": "[^"]' "$1"
}
# A sweep's runs are held to the frozen PREREG flows/registry.txt names for the kind sweep, which
# covers a plan by its name and, where its Covers entry is <plan>=<sha256>, by its bytes too
# (flows/stage_registry.py). The launcher refuses any other plan with the Lab Recipe's exit 90, but
# only once the job holds a GPU and its catalog is built, so the word reads the same lines first and
# refuses with 90 before anything is queued. A plan's name is its file's, as the launcher takes it.
sweep_prereg() {  # the PREREG flows/registry.txt names for the sweep, a path under the checkout, else nothing
  awk '$1 == "sweep" && NF == 5 { print $5; exit }' "$REPO/flows/registry.txt" 2>/dev/null
}
covers_entry() {  # covers_entry PREREG NAME: the entry of the PREREG's first Covers line that names the plan, else nothing
  sed -n 's/^Covers: //p' "$1" | head -n 1 | tr ', \t' '\n\n\n' | awk -v name="$2" '$0 == name || index($0, name "=") == 1 { print; exit }'
}
sweep_covered() {  # sweep_covered PLAN NAME: status 0 where the sweep's frozen PREREG covers the plan, by its name and bytes; the refusal otherwise
  local prereg entry frozen bytes want
  prereg=$(sweep_prereg)
  case "$prereg" in
    ""|/*|../*|*/../*) echo "refusing: flows/registry.txt names no PREREG inside the checkout for the sweep, so no plan is covered; nothing was queued"; return 90 ;;
  esac
  frozen=$(awk 'NR == 1 && NF == 2 && ($2 == "PREREG.md" || $2 == "*PREREG.md") { print $1 }' "$REPO/$prereg.sha256" 2>/dev/null)
  bytes=$(sha256sum < "$REPO/$prereg" 2>/dev/null | cut -c1-64)
  if [ -z "$frozen" ] || [ "$frozen" != "$bytes" ]; then
    echo "refusing: STOP: $prereg is not frozen as its PREREG.md.sha256 says (the Lab Recipe's freeze), so no sweep runs under it; nothing was queued"
    return 90
  fi
  entry=$(covers_entry "$REPO/$prereg" "$2")
  if [ -z "$entry" ]; then
    echo "refusing: $prereg does not cover the plan $2, which waits for a PREREG of its own, frozen before it runs; nothing was queued"
    return 90
  fi
  case "$entry" in
    *=*)
      want=${entry#*=}
      bytes=$(sha256sum < "$1" | cut -c1-64)
      if [ "$want" != "$bytes" ]; then
        echo "refusing: $prereg covers $2 as the bytes of sha256 ${want:0:16}, and grid/sweeps/$2.json's are ${bytes:0:16}: a plan changed since the freeze is another design, which waits for a PREREG of its own; nothing was queued"
        return 90
      fi ;;
  esac
}
CATALOG_DEP=""
shard_folders() {  # the folders of the data root that hold a shard, one a line, where grid/03-catalog.sbatch lists them
  # <data root>/<folder>/shards/<shard>/MANIFEST.json, never a dot folder, which holds a shard still
  # being staged or ingest's notes; the folder is the source's own, its registry entry's grid root.
  local manifest folder
  for manifest in "$DATA_ROOT"/[!.]*/shards/[!.]*/MANIFEST.json; do
    [ -f "$manifest" ] || continue
    folder=${manifest%/shards/*}
    echo "${folder##*/}"
  done | sort -u
}
newest_build_of() {  # newest_build_of FROM...: the newest live catalog build the gate submitted from one of the words FROM
  local job from what want
  [ -f "$STATE" ] || return 0
  tac "$STATE" | while read -r job from what _; do
    [ "$what" = catalog ] || continue
    for want in "$@"; do
      if [ "$from" = "$want" ]; then
        case "$QUEUED" in *" $job "*) echo "$job"; break 2 ;; esac
      fi
    done
  done
}
plan_build() {  # plan_build CATALOG: the live catalog build of the gate's that can make a version CATALOG qualifies by, else nothing
  # Every build takes in every shard on the data root (grid/03-catalog.sbatch), so a bank's build
  # always holds the source it banked. The v1 plan's version holds C-ArmLSpine alone, so only
  # start's or v1's build can make one, and only while no other source's shard is there; a
  # with:<source> plan's holds that source, so the build of a bank of it can, and so can any build
  # once a shard of it is on the data root. The X-ray chain's builds wait on fetches of days and
  # are never waited on.
  local source
  # grep reads the whole list, never -q, so no early exit ends shard_folders with SIGPIPE under pipefail.
  case "$1" in
    v1) shard_folders | grep -vx carmlspine > /dev/null || newest_build_of start v1 ;;
    with:*)
      source=${1#with:}
      if shard_folders | grep -xF -- "$source" > /dev/null; then live_of catalog; else live_of catalog "bank:$source"; fi ;;
  esac
}
sweep_catalog() {  # sweep_catalog CATALOG: the wait a plan's real catalog needs, in CATALOG_DEP; 75 with the reason where none can come
  # A version that qualifies now first, which the run reads once it starts (grid/v1-version.sh), so
  # a build of another kind that lands before then is never the reason it waits or is cancelled;
  # else a live build of the gate's that can make one.
  local source="" choice job version why
  CATALOG_DEP=""
  case "$1" in with:*) source=${1#with:} choice=$source ;; *) choice=--alone ;; esac
  why=$(mktemp "${TMPDIR:-/tmp}/sweep-catalog.XXXXXX") || { echo "refusing: no temporary file could be made; nothing was queued"; return 2; }
  if version=$(bash "$REPO/grid/v1-version.sh" "$STORE" "$DATA_ROOT" "$REPO" "$choice" 2> "$why"); then
    rm -f "$why"
    echo "  catalog: $version qualifies (grid/v1-version.sh $choice); no job"
    return 0
  fi
  version=$(head -n 1 "$why" | cut -c1-200)
  rm -f "$why"
  job=$(plan_build "$1")
  if [ -n "$job" ]; then
    CATALOG_DEP="afterok:$job"
    echo "  catalog: none qualifies yet ($version); after the live catalog build, job $job"
    return 0
  fi
  if [ -z "$source" ]; then
    echo "refusing: no catalog version holds C-ArmLSpine alone for the v1 plan ($version), and no live catalog build of the gate's can make one;"
    echo "  the v1 word or start makes the catalog first, and makes one of C-ArmLSpine alone only while C-ArmLSpine's are the only shards on the data root"
  else
    echo "refusing: no catalog version holds $source's train part beside C-ArmLSpine's ($version), and no live catalog build of the gate's can hold it; bank $source first"
  fi
  return 75
}
word_sweep() {
  local plan=$REPO/grid/sweeps/$id.json catalog source running setup job weights_dep="" holds opts
  [ -f "$plan" ] || { echo "refusing: $id is not a plan under grid/sweeps/ (the plans: $(sweep_plans))"; return 64; }
  sweep_covered "$plan" "$id" || return
  running=$(live_of sweep "sweep:$id")
  [ -z "$running" ] || { echo "refusing: a sweep of $id is already queued or running (job $running); 'status' follows it"; return 75; }
  # Every refusal before any job is queued, so a refused word leaves nothing behind.
  catalog=$(plan_catalog "$plan")
  case "$catalog" in
    synthetic) CATALOG_DEP=""; echo "  catalog: the synthetic one, which the run finds under the smoke folder or builds afresh there when its arguments or the code that makes it changed" ;;
    v1) sweep_catalog v1 || return ;;
    with:*)
      source=${catalog#with:}
      case "$source" in ""|*[!a-z0-9_]*) echo "refusing: grid/sweeps/$id.json names the catalog '$catalog', whose source is no id"; return 2 ;; esac
      sweep_catalog "$catalog" || return ;;
    *) echo "refusing: grid/sweeps/$id.json names no catalog the sweep knows ('$catalog'; synthetic, v1 or with:<source>)"; return 2 ;;
  esac
  setup=$(setup_dependency) || return 1
  [ -n "$setup" ] || echo "  setup: the environments match pixi.lock; no job"
  if plan_names_weights "$plan" && ! weights_ready; then
    job=$(live_of weights)
    [ -n "$job" ] || job=$(submit weights batch MODELS="$MODELS" -- 00-weights.sbatch) || return 1
    weights_dep="afterok:$job"
  fi
  # Queued after every run that holds the checkout rather than refused, so the sweeps the owner
  # sends together run one after another, each on the code it records.
  holds=$(checkout_holders)
  [ -z "$holds" ] || echo "  the checkout: after the live runs that hold it ($holds)"
  depend_on "$(joined "$setup" "$weights_dep" "$CATALOG_DEP" "$holds")" || return 1
  # Not requeued: the word sent again resumes the cut sweep through the launcher (flows/launch.py),
  # and a requeue racing that word would start a second launcher on the same flow run.
  submit sweep gpu PLAN="$id" SMOKE="$SMOKE" DATA_ROOT="$DATA_ROOT" WEIGHTS="$WEIGHTS" MODELS="$MODELS" \
    ${opts[@]+"${opts[@]}"} --no-requeue -- sweep-driver.sbatch > /dev/null || return 1
  echo "submitted. 'status' shows the plan's PROGRESS.txt once the sweep writes it; the same word again after a cut sweep ends resumes it."
}

recipe_raw() {  # recipe_raw FILE: the raw folder a recipe of grid/banks/ names, as stage 2 reads it
  # Off the grid stage 2 reads <data root>/<id>/raw in place of the recipe's path (issue #40), and
  # the gate hands the stage a data root only where its caller gave one.
  if [ -n "$DATA_ROOT_GIVEN" ]; then echo "$DATA_ROOT/$id/raw"; return 0; fi
  sed -n 's/^ *"raw": *"\([^"]*\)".*/\1/p' "$1" | head -n 1
}
landing_of() {  # landing_of RAW: the folder under the data root that holds RAW, the first on its path; status 1 where RAW is not under the data root
  # The folder a fetch lands and whose meta/SIZE holds the fetch's admission: a recipe's own id for
  # most recipes, zenodo_lumos for lumos, which start's platform chain lands as dp_zenodo_lumos.
  local rest=${1#"$DATA_ROOT"/} landing
  [ "$rest" != "$1" ] || return 1
  landing=${rest%%/*}
  case "$landing" in ""|*[!a-z0-9_]*) return 1 ;; esac
  echo "$landing"
}
bank_room() {  # bank_room NEED: 0 where the room under the quota takes NEED bytes after what the running fetches owe, saying both
  # The room the bank word decides against before it queues its job (grid/size-rule.sh): what the
  # running fetches owe first, then the room twice a minute apart, the smaller kept. The fetch
  # word's chain decides nothing at submit since #163; its job decides each set in turn.
  room_for "$1" "the bank and its shard need" "nothing was queued"
}
room_for() {  # room_for NEED WHAT NOTHING: as bank_room, WHAT naming what needs NEED in a refusal and NOTHING what was left undone
  local owed owed_bytes owed_n unsized free free_from room
  owed=$(owed_by_running "") || { echo "refusing: squeue did not answer, so what the running fetches owe is not known; $3"; return 75; }
  read -r owed_bytes owed_n unsized <<< "$owed"
  [ -z "$unsized" ] || { echo "refusing: the running fetch of $unsized states no size, so the room after it is not known; $3"; return 75; }
  read -r free free_from <<< "$(settled_room "$VOLUME")"
  if [ -z "$free" ]; then
    echo "refusing: the room on the lab volume could not be read: $(room_unread_words "$VOLUME"); $3"
    return 2
  fi
  room=$(( free > owed_bytes ? free - owed_bytes : 0 ))
  echo "  room: $(gb_down "$room") GB $(free_space_words "$free_from") after $(gb_up "$owed_bytes") GB owed to $(running_fetches "$owed_n")"
  [ "$1" -le "$room" ] || { echo "refusing: $2 $(gb_up "$1") GB and the room is $(gb_down "$room") GB; $3"; return 75; }
}
admission_holder() {  # admission_holder [SET]: the live job whose admission $DATA/<SET>/meta/SIZE still holds (SET $id by default), else nothing
  local set=${1:-$id} state job
  [ -f "$DATA/$set/meta/SIZE" ] || return 0
  read -r state job _ < "$DATA/$set/meta/SIZE"
  [ "$state" = admitted ] || return 0
  case "$QUEUED" in *" $job "*) echo "$job" ;; esac
}
bank_jobs() {  # bank_jobs NEED: the bank and its catalog build queued, and the bank's admission recorded, under the size lock
  # What the bank and its shard write is held from the moment the job is queued: its admission, the
  # line a fetch's job writes when it starts (grid/size-rule.sh, admit_fetch), counts against every
  # later decision while Slurm holds the job, at what it may write less what the set's folder on
  # the data root, which holds the bank and the shard, has grown by since. The job decides again
  # when it starts, its own admission aside (grid/02-bank-ingest.sbatch, BANK_NEED).
  local need=$1 base setup bank catalog opts
  bank_room "$need" || return
  base=$(landing_bytes "$id")
  [ -n "$base" ] || { echo "refusing: what $id's folder on the data root holds could not be read, which the bank's admission is measured from; nothing was queued"; return 2; }
  setup=$(setup_dependency) || return 1
  [ -n "$setup" ] || echo "  setup: the environments match pixi.lock; no job"
  depend_on "$setup" || return 1
  bank=$(submit bank batch ONLY="$id" BANK_NEED="$need" VOLUME="$VOLUME" ${opts[@]+"${opts[@]}"} -- 02-bank-ingest.sbatch) || return 1
  # Recorded as catalog, so a sweep of a plan with:<id> waits on it as on any build of the gate's.
  if ! depend_on "afterok:$bank" || ! catalog=$(submit catalog batch ${opts[@]+"${opts[@]}"} -- 03-catalog.sbatch); then
    "$SCANCEL" "$bank" && echo "  cancelled the bank job $bank, so no bank runs that no catalog build follows"
    return 1
  fi
  if ! { mkdir -p "$DATA/$id/meta" && echo "admitted $bank $need $base $(date -u '+%FT%TZ') $need" > "$DATA/$id/meta/SIZE"; }; then
    "$SCANCEL" "$bank" "$catalog" && echo "  cancelled the bank job $bank and its catalog build $catalog"
    echo "refusing: the bank's admission could not be written to its folder's meta/SIZE, so no later decision would count it"
    return 2
  fi
}
word_bank() {
  local recipe=$REPO/grid/banks/$id.json busy raw landing bytes need format factor why rc DATA=$DATA_ROOT
  [ -f "$recipe" ] || { echo "refusing: $id is not a recipe under grid/banks/"; return 64; }
  # One bank and one build at a time: two banks of one set write the same bank folder, and the X-ray
  # chain's stage 2 banks every recipe its fetch names, start's every one there is.
  busy=$( { live_of bank; live_of catalog; live_of xr_bank; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: a bank or a catalog build of the gate's is still queued or running (jobs $busy)"; return 75; }
  # Never beside an unpacking of the set, which would hand the bank half a raw folder and holds its
  # room through the same admission file, nor over an admission a live job still holds.
  busy=$(live_of unpack "unpack:$id")
  [ -z "$busy" ] || { echo "refusing: an unpacking of $id is still queued or running (job $busy)"; return 75; }
  busy=$(admission_holder)
  [ -z "$busy" ] || { echo "refusing: the size rule's admission for $id is still held by job $busy, which is queued or running"; return 75; }
  [ "$(unconfirmed_fields "$recipe")" = 0 ] \
    || { echo "refusing: grid/banks/$id.json still has a field spelled \"to confirm\"; stage 2 refuses it until the page is read and the field filled in"; return 2; }
  format=$(recipe_format "$recipe")
  read -r factor why <<< "$(bank_factor "$format")"
  [ -n "$factor" ] || { echo "refusing: grid/banks/$id.json names the format '$format', which the bank word has no budget for"; return 2; }
  raw=$(recipe_raw "$recipe")
  # Never while the landing that holds the raw copy is still being fetched, unpacked or admitted by
  # any word's job: the bank would read part of the set and the budget below would be read from
  # part of it, while the job banks whatever has landed by the time it starts.
  landing=$(landing_of "$raw") \
    || { echo "refusing: $id's raw folder is not under the data root, so nothing can say whether it is still landing; nothing was queued"; return 2; }
  busy=$( { live_of xr_fetch "fetch:$landing"; [ "$(fetch_section "$landing")" != open ] || live_of xr_fetch start
            live_of "dp_$landing"; live_of unpack "unpack:$landing"; admission_holder "$landing"; } | tr '\n' ' ')
  [ -z "${busy// /}" ] || { echo "refusing: $landing, which holds $id's raw copy, is still being landed (job ${busy% }): a fetch, an unpacking or an admission of it is queued or running"; return 75; }
  [ -n "$raw" ] && [ -d "$raw" ] && [ -n "$(ls -A "$raw" 2>/dev/null | head -n 1)" ] \
    || { echo "refusing: $id's raw copy is not on the volume (its recipe's raw folder is missing or empty); fetch it first"; return 2; }
  # What the raw copy holds, read with no walk as the size rule reads a folder, whole, times what
  # the bank and its shard may write of each byte of it (bank_factor).
  bytes=$(xattr_whole ceph.dir.rbytes "$raw")
  [ -n "$bytes" ] || { echo "refusing: what $id's raw copy holds could not be read (ceph.dir.rbytes); nothing was queued"; return 2; }
  [ "$bytes" -le $(( 999999999999999999 / factor )) ] \
    || { echo "refusing: $factor times what $id's raw copy holds is more than the size rule counts; nothing was queued"; return 2; }
  need=$(( factor * bytes ))
  echo "  raw copy: $(gb_up "$bytes") GB of $format, $why; the bank and its shard: $(gb_up "$need") GB held, and the job asks for more before it writes where their frames' pixels need it"
  # One decision at a time with the fetch and unpack jobs' own and the fetch word's chain, from the
  # room's reading to the record of this bank's admission (grid/size-rule.sh, admit_fetch).
  exec 8> "$DATA/.size-rule.lock" || { echo "refusing: the size rule's lock on the data root could not be opened; nothing was queued"; return 2; }
  if ! flock -w "${SIZE_RULE_WAIT:-900}" 8; then
    exec 8>&-
    echo "refusing: another decision held the size check for ${SIZE_RULE_WAIT:-900} seconds; nothing was queued"
    return 75
  fi
  bank_jobs "$need"
  rc=$?
  exec 8>&-
  [ "$rc" = 0 ] || return "$rc"
  echo "submitted. 'status' shows the stage reports and counts the bank's room as owed while it lasts; a sweep of a plan with:$id sent while the build is live waits on it."
}

word_stop() {
  local live
  live=$(live_ids | tr '\n' ' ')
  [ -n "${live// /}" ] || { echo "nothing of the gate's is queued or running"; return 0; }
  # shellcheck disable=SC2086
  "$SCANCEL" $live && echo "cancelled: $live"
}

word_cancel() {  # the job named, if the gate's and live, with every live job of the same word
  local from cancel
  from=$(awk -v job="$id" '$1 == job { print $2; exit }' "$STATE" 2>/dev/null)
  [ -n "$from" ] || { echo "refusing: job $id is not one of the gate's"; return 64; }
  case "$QUEUED" in *" $id "*) ;; *) echo "job $id is no longer queued or running; nothing cancelled"; return 0 ;; esac
  cancel=$(awk -v from="$from" '$2 == from { print $1 }' "$STATE" | sort -u | while read -r job; do
    case "$QUEUED" in *" $job "*) echo "$job" ;; esac
  done | tr '\n' ' ')
  # shellcheck disable=SC2086
  "$SCANCEL" $cancel && echo "cancelled ($from): $cancel"
}

release_hold() {  # a run's hold (grid/v1-driver.sbatch, grid/sweep-driver.sbatch, grid/experiment-driver.sbatch, grid/bench.sbatch, grid/drr-seg.sbatch, grid/anomaly.sbatch, grid/bordercall.sbatch, grid/realism.sbatch, grid/morphometry.sbatch) is cleared once Slurm no longer holds its job
  local job
  [ -f "$LOGS/HOLD" ] || return 0
  job=$(awk '{ print $1; exit }' "$LOGS/HOLD")
  case "$QUEUED" in
    *" $job "*) echo "  the checkout holds still at $(awk '{ print substr($2, 1, 7); exit }' "$LOGS/HOLD") while the run that took it (job $job) lasts" ;;
    *) rm -f "$LOGS/HOLD" ;;
  esac
}
settle_banks() {  # every bank's admission whose job Slurm no longer holds is settled (grid/size-rule.sh, settle_admission)
  # The job hands itself to the launcher with exec and so cannot settle its own once it ends; the
  # size rule counts only a live job's admission, and a settled one counts for nothing even where
  # Slurm hands the job's id out again.
  local DATA=$DATA_ROOT job from what one
  [ -f "$STATE" ] || return 0
  # The anomaly route's pack holds its admission under the landing flexray_pack, whatever its word says.
  awk '$3 == "bank" || $3 == "anomaly_pack" { print $1, $2, $3 }' "$STATE" | sort -u | while read -r job from what; do
    case "$QUEUED" in *" $job "*) continue ;; esac
    if [ "$what" = anomaly_pack ]; then one=flexray_pack; else one=${from#bank:}; fi
    case "$one" in ""|*[!a-z0-9_]*) continue ;; esac
    settle_admission "$one" "$job"
  done
}
if [ "$word" = status ]; then
  # status reads even when squeue does not answer; only a hold or an admission it can see is over is cleared
  snapshot > /dev/null && { release_hold; settle_banks; }
else
  snapshot || { echo "schwingnet $word: exit 75"; exit 75; }
  release_hold
  settle_banks
fi
case "$word" in
  start) word_start ;;
  # Bounded whatever the logs hold: 400 lines and 64 KiB reach the gate at most. word_status fits
  # its page into them; the cut here is a second net.
  status) out=$(word_status); printf '%s\n' "$(head -n "$STATUS_LINES" <<< "$out" | head -c "$STATUS_BYTES")" ;;
  leaks) word_leaks ;;
  v1) word_v1 ;;
  latency) word_latency ;;
  fetch) word_fetch ;;
  explore) word_explore ;;
  dropzip) word_dropzip ;;
  unpack) word_unpack ;;
  nodequota) word_nodequota ;;
  folders) word_folders ;;
  experiment) word_experiment ;;
  bench) word_bench ;;
  anomaly) word_anomaly ;;
  bordercall) word_bordercall ;;
  census) word_census ;;
  totalseg) word_totalseg ;;
  realism) word_realism ;;
  autoanatomist) word_autoanatomist ;;
  morphometry) word_morphometry ;;
  literature) word_literature ;;
  samples) word_samples ;;
  sweep) word_sweep ;;
  bank) word_bank ;;
  stop) word_stop ;;
  cancel) word_cancel ;;
esac
rc=$?
echo "schwingnet $word: exit $rc"
exit $rc
