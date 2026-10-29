# The pipeline's Metaflow flows

Issue #252. The owner's rule of 2026-10-24 is that where the workflow software has a native
behaviour, it is used and enforced. Metaflow (2.19.39, in the pixi feature train, so in the
train-cpu and train-gpu environments and not in the default one) is the engine; this folder is
where the grid's pipeline stages run under it, so that a job the grid cuts short is continued by
Metaflow's own resume rather than by anything written around it.

## The flows

- `bank.py`, BankFlow: stage 2 of the X-ray chain, each recipe's raw copy into a bank and each
  bank into a shard. start lists the recipes as grid/02-bank-ingest.sbatch does (BANKS, ONLY,
  DATA_ROOT; a raw folder not fetched is a skipped line), one branch of a foreach per recipe to
  bank, a `bank` step and an `ingest` step in each, each running the stage script for that one
  recipe and that half of its loop body (PART=bank, PART=ingest), a join, and end, which writes
  logs/02-bank-ingest-STAGE-REPORT.md under the launcher's working folder in the stage's words
  and prints it with `XR_BANK_RC=<0|1>`. Until then the report says the run is not finished:
  start writes its head, the skipped lines and a "Not finished as of <time>: <n> of <m> recipes
  with a raw copy done" line, and each recipe's ingest step rewrites it once the recipe is done,
  so the gate's status shows a run in progress, or one cut short, as the stage's report did by
  stopping short. A refusal of the bank or the ingest tool is the stage's own report line,
  recorded, not raised, as before. A kill mid-ingest resumes at that recipe's ingest with its
  bank cloned.
- `catalog.py`, CatalogFlow: stage 3, the catalog's build and its split check, in one step that
  runs grid/03-catalog.sbatch whole, since the build lock is held from the listing of the
  manifests to the marker (issue #80); a kill in it reruns it whole, which costs under a minute,
  and a kill in end, once the build is done, clones the build, but only while the manifests are
  as the key names them (below). Its verdict is the stage's XR_CATALOG_RC.
- `sweep.py`, SweepFlow: one plan of the block smoke test (grid/sweeps/<plan>.json). start runs
  `tools/block_sweep.py prepare`, a foreach over the rows with no parent runs `block_sweep.py row`
  for each, a second foreach the warm starts, which read a parent's train/best.pt, and end runs
  `block_sweep.py results`, writes METAFLOW.json into the plan's state folder, exports the rows'
  cards there (cards/<step>-<slug>.html) and makes a card of the results table. A row whose `row`
  could not run or record it (any exit but 0; block_sweep says 2) raises, is retried once at once
  (`@retry(times=1)`), and is then caught (`@catch(var="fault")`), so the other rows still run
  and the verdict is 1. The verdict is 0 only when every row was recorded and did what the
  compatibility check predicted, and every row that ran has its CLAIM 2024 and REFORMS report
  current (below). A kill mid-row resumes with every finished row cloned and the cut row run
  again, which tools/flow.py carries on from its last epoch (tools/train.py --resume). Its runs
  are held to docs/research/block-smoke/PREREG.md, which covers the plans synthetic, real and
  two_source by their bytes; `sweep trials` is refused until the six trials have a PREREG of their
  own, and so is a plan made again with other rows. grid/gate.sh's word `sweep <plan>` reads the
  same Covers line in bash and refuses such a plan with 90 before it queues anything, since the
  launcher's own refusal comes only once the job holds a GPU and its catalog is built.
- `v1.py`, V1Flow: the version 1 run on real frames (issue #53), which grid/v1-driver.sbatch
  starts through the launcher once it has chosen the catalog version and checked its split again.
  start holds the run to docs/research/v1-demo/PREREG.md, a step `train_evaluate` runs
  `tools/flow.py run` whole in local mode, its card and its line on the page moving with the
  trainer's train/metrics.jsonl, and end writes and checks the run's CLAIM 2024 and REFORMS report
  in its folder and writes METAFLOW.json there. A step that fails is retried once at once
  (`@retry(times=1)`); a kill mid-training resumes the step, which tools/flow.py carries on from
  its last epoch. The key reads the catalog's and the ImageNet file's bytes, as tools/flow.py
  names the run. The verdict is 0 only where tools/flow.py finished the run (FINISHED.json) and
  its report is current.
- `realism.py`, RealismFlow: the FluXray reproduction (docs/research/flux-realism/PREREG.md), one
  run per stage on the owner's count of 2026-10-29 (two GPU jobs, edit and then stats; grid word
  `realism <stage>`, grid/realism.sbatch). start holds the run to the PREREG and to its frozen block,
  which must equal schwingnet.realism.frozen_lines(), and checks every input (`tools/realism.py
  inputs`) before a GPU second is spent. For edit, prepare draws the subjects by the frozen seed into
  shards, a foreach runs `render`, `edit` and `score` per shard (`@retry(times=1)`; a shard that
  still fails fails the run, and a later launch of the same key resumes it from that shard, every
  sample already whole skipped and a half-written one redone), and join_shards runs `keep`,
  `fluxray-export` and `measure` over all of them;
  for stats, a foreach runs `stats` on the kept edits and on the raw renders, and join_comparisons
  reads the replication's word and the geometry's; the stats start records its own environment and
  the weights' sha256 (`tools/realism.py environment`). Each run works in
  <out>/<stage>-<run key>-<run id>, a resume in the folder its first run made and a new run of the
  same key in an empty one; end writes RECORD.json (with where, the run that made the folder, and
  ended_in, the run that ended it, each with the commit and whether the tree was clean) and
  SUMMARY.md, checks the run's CLAIM 2024 and REFORMS report (`tools/report.py --study
  flux-realism`, tools/realism_report.py), and, for an edit with verdict 0, writes <out>/edit.json,
  the one way the stats stage finds its edit. The verdict is 1 where the report is not current or an
  edit made fewer renders, edits or FluXray images than its own draw holds, so the stats, which
  refuse an edit whose verdict was not 0 or whose PREREG differs, never read a sample short of the
  PREREG's. lora and eval are refused until they have a count and a PREREG of their own.

Every flow's end step sets an int artifact `verdict`, 0 when all went well and 1 otherwise.

Where a list a foreach would take is empty (no recipe with a raw copy, no warm start in a plan),
a switch, Metaflow 2.19's conditional next (`self.next({...}, condition=...)`), steps past the
foreach, since Metaflow refuses a foreach over nothing. A switch's path may not lead straight to
a join step, so a switch lands on a plain step: BankFlow's end, SweepFlow's middle and end.

## Every deep learning job: a launched flow, a frozen PREREG, its report and its page

The owner's rule of 2026-10-29, 02:39 UTC: every deep learning job on the grid runs on this
block-based pipeline, under a PREREG frozen before the run, with the CLAIM 2024 and REFORMS report
enforced and a page that shows its progress in the browser; a plain Slurm job is not enough.

As of this pull request only the sweep keeps it. These words of grid/gate.sh still submit a plain
job that trains or runs a network, each to be moved onto a flow listed in registry.txt, one pull
request each, under a PREREG of its own:

- `start` and `v1`, version 1's training and evaluation (grid/v1-driver.sbatch);
- `experiment <issue>`, one combination of blocks from the experiments panel
  (grid/experiment-driver.sbatch);
- `bench <id>`, a public model's benchmark (grid/bench.sbatch), and among its ids
  `flexray_drr_seg`, the step that makes MOOSE's masks;
- `bench flexray_drr_gap`, the DRR domain-gap study (grid/drr-gap.sbatch);
- `anomaly timing`, SPINEPS over the anomaly route's CTs (grid/anomaly.sbatch);
- `latency`, the latency arms and the recorded sweep (grid/run-latency-sweep.sh);
- `realism <edit|stats|lora|eval>`, the Flux realism stages (grid/realism.sbatch).

The rule holds already, so until a word is moved it is not sent. Once they all are, the gate
refuses any GPU job that does not start through flows/launch.py; that refusal is a later pull
request.

- `registry.txt` is the one list of the flows: per kind its class in flows/<kind>.py, the word the
  launcher's last line ends with, the job script under grid/ that starts the launcher when Slurm
  runs it, and its PREREG.md, a relative path under docs/research/, where git holds its freeze
  (below), or `-`, which only the stages that train and run no network may name (bank, catalog;
  NO_NETWORK in flows/stage_registry.py).
  `python3 flows/stage_registry.py check`, which scripts/check.sh runs, fails on a line whose class
  or script does not hold, whose PREREG is not the one frozen or leads out of the checkout, or
  whose PREREG has a Covers line for a flow that names no part (no `prereg_part`).
- A PREREG is frozen as the Lab Recipe says, `sha256sum PREREG.md > PREREG.md.sha256` in its
  folder, both committed, and never edited again: a departure goes in DEVIATIONS.md beside it, and
  a correction of a departure is a new dated entry below the last, never an edit of an earlier
  one. Git holds the freeze too, since an edit with its .sha256 written again passes every check
  of the bytes: `python3 flows/stage_registry.py frozen`, in scripts/check.sh, fails where a
  PREREG.md or PREREG.md.sha256 under docs/research/ or docs/history/ that the base holds differs
  at HEAD, or a DEVIATIONS.md beside a frozen PREREG no longer begins with its text there. A frozen
  folder moved whole to docs/history/, as .claude/rules/research.md lets a settled note move, is
  held at its new place, and moved and edited is gone. The base: in CI, whose checkout of a pull
  request is GitHub's merge commit one commit deep, the commit it was merged onto, its first
  parent, fetched one commit deep, so a run queued behind a merge to main, or run again, is never
  held to a newer main; elsewhere where HEAD left origin/main, and a clone that has no origin/main,
  or too shallow for git to tell where HEAD left it, skips the check with a line. scripts/check.sh
  runs the default branch's own copy of the check from a scratch folder against the checkout
  (`frozen --repo`), so a change that loosens flows/stage_registry.py is still held by the copy it
  loosened. What is still open: a change that edits scripts/check.sh's frozen_check, or
  .github/workflows/ci.yml, which runs it, can skip the check; its diff shows that, and the owner's
  review of such a change is what holds it. The
  launcher refuses a kind whose PREREG is missing or moved before it imports Metaflow, with the
  recipe's exit 90 and the line `LaunchError: ... STOP: <PREREG> changed since the freeze`, so the
  job does nothing. A PREREG's line `Covers: <part>, ...` names the parts of its kind it covers,
  each by its name alone or as `<part>=<sha256>`, by its bytes too, and a flow whose runs differ
  in design names the part a run is and the sha256 of its bytes (the sweep's `prereg_part`, its
  plan's name and the plan file's sha256), so a run of a part no frozen PREREG covers, or of one
  whose bytes are not those its entry names, a plan edited or made again since the freeze, is
  refused with exit 90 too: after Metaflow is imported, since the part is read from the flow's own
  file, which imports it, but before the datastore is touched or anything is written. The PREREG's
  path and sha256 are in the key and on the run's tags (prereg:<12>), and start keeps them as the
  run's artifacts prereg_path and prereg_sha256, with the part and its sha256
  (`stage.hold_to_prereg`). A resume clones start, and `python flows/sweep.py resume` started by
  hand skips the launcher's refusal too, so end holds the run to them again (`stage.still_held`)
  and fails where the PREREG frozen now is another or no longer covers the part as start read it.
  A refusal by start or end is the flow's own (`StageFault`), so it fails the run and the launcher
  exits with the flow's 1, not 90; only the launcher's own refusal exits 90.
- `stage.py` is what every flow's steps run for the rule: `Beat` around a step's work, its line on
  the page, `run_watched` for a command whose line moves while it runs, `Beat(self).passed()` in a
  step that only routes the flow, `claim_report` in end, and `finish`, the verdict and the
  report's lines on the page. `claim_report` checks a run folder's report with tools/report.py
  before it writes anything, since the tool's check compares the report's files with what a write
  would render now and so always passes right after one: a current report is well; a folder with
  none has it written then and checked, and the line says it was written at the end; a report not
  what the folder's files give is written anew, so the folder and the page hold the current one.
  That stale report makes the verdict 1 where the folder's work was done in this Metaflow run, its
  FINISHED.json (or, with none, its newest file but the report's) written after Metaflow
  registered the run (`run_began`, `done_since`); a folder done before, a row a resume cloned or
  one tools/flow.py found finished, is only stale because tools/report.py, the study's answers or
  the checklists changed since, which no run's key names, so it is written anew under the tool as
  it is now and is well, and its line says so. A report that cannot be written makes the verdict 1
  either way. An item a report counts
  as missing is shown, never inferred; `tools/report.py check --complete` stays the gate for a
  number that is to be published.
- `stage_progress.py` draws the page. Each run keeps <datastore root>/progress/<Flow>/<run>/:
  run.json, the head the launcher writes once Metaflow has named the run (its kind, key, commit,
  code, PREREG and, for a resume, its origin, whose finished steps the page shows as cloned and
  whose tasks still running when it was cut as cut, to be run again, never as running);
  graph.json; one file a task under tasks/, which only that task writes; result.json from end; and
  launch.json, how the launcher saw the flow end. Every write draws index.html, the page, which
  reloads itself every 30 s while the run lasts; PROGRESS.txt, the same in short lines, how the
  run ended (its verdict, the launcher's last word, the reports counted and the first six of their
  lines, those not current first) right after its two head lines, and then each step with its
  first eight tasks, a failed one first, so the 40 lines the gate's status keeps of a run always
  hold its end; and
  <datastore root>/progress/index.html, the newest runs of every flow. A run still running whose
  files have not moved for ten minutes is silent: a job Slurm ended writes nothing more, so its own
  page keeps the word running it last wrote, and silence is judged where the page is read instead,
  by the page's script in the browser when it is opened, by the list of runs whenever any run
  draws it, by the gate's status from PROGRESS.txt's time (the head then says silent, with a line
  saying how long), and by tools/progress_page.py from the status answer's time. Nothing here
  fails a step: a page that cannot be written is said once in the step's log.

To open a page in the browser on the grid: Open OnDemand (https://ondemand.grid.wayne.edu, on the
university's VPN), Files, then /rs/rs_grp_oschome/go2432/metaflow/progress/, the flow's folder,
the run's folder and index.html, opened with View; not yet tried on the grid, so where the Files
app shows the page as text, Download it and open the file in the browser. Off the grid, the gate's status word prints the
newest four runs' PROGRESS.txt under `## flow <kind> <run>, progress (<time> UTC)`, their task and
report lines judged as a stage report's are (a path cut, a quoting reason withheld) and every line
masked, and `python3 tools/progress_page.py <status answer> --out page.html` draws the same page
from that answer.

## Starting and resuming: always the launcher

    python flows/launch.py <kind> [--max-workers N] [--root DIR] -- <flow parameters>

The launcher names a launch by a key, the first 16 hex of the sha256 of the flow, the code it
runs, the flow's parameters as given and what the flow reads that they do not name
(schwingnet.pipeline.run_key). The code is tools/run_code.py's digest of the tracked files the
flow's kind executes (`python3 tools/run_code.py files sweep` lists them), not the commit: main
merges many times a day, most merges change nothing a flow runs, and a key with the commit in it
started a cut run over after any of them (issue #252, finding 27). What the flow reads is listed
by its own key_reads: for bank a line per recipe start would list with the recipe's bytes and its
raw folder's state, every file by path, size and modification time as tools/bank.py's BANK.json
stamp lists it, since a resume clones start's listing of what has a raw copy and every bank step
that finished: a raw copy fetched, grown or changed since the cut, or a recipe edited, names
another key and so a new run, while raw copies as they were resume; for catalog a line per
manifest the stage would build from, each `<source>/shards/<shard>/MANIFEST.json` under the data
root as its find lists them, by its path, size and sha256, since a resume of a run cut in end
clones its build: a shard landed, gone or rewritten since names another key and so a new run
that builds from what is there, while manifests as they were carry the cut run on (the second
review of #252, finding 2; resuming from the catalog step, Metaflow's `resume catalog`, would
rebuild on every resume, with nothing new as well). The step lists the manifests again under the
build lock, so a shard that lands between the launch and that listing is in the build and not in
the key, and the next launch, whose key names it, runs anew. For sweep it is the plan file's
sha256, since start makes the state folder and its lists of rows from the plan. Every run it
starts or resumes carries the tags `key:<key>`, `commit:<7>`, the checkout that launched it, and
`code:<12>`; a new run is given the checkout's `--commit`, which resume clones with the other
parameters, so a resumed run names the commit it was first started on, which holds the same
code. It lists the runs of the flow carrying the key, newest first,
and the newest decides (schwingnet.pipeline.decide): a newest run that did not succeed, killed
or failed, is resumed (`resume --origin-run-id`, with the same --max-workers and no parameters,
which resume clones), unless Metaflow never saved its parameters; else a new run starts.
Metaflow registers a run, with its tags, before it saves the parameters, and refuses to resume a
run that has none, after registering the resume as one more such run of the key, so a run killed
between the two holds no work, and resuming it made every later launch of the key fail in turn
(the second review of #252, finding 1). Each run's end task is read once for whether it finished
and whether it succeeded, a success counting as finished, since Metaflow writes the two flags one
after the other, and the newest is read again, after the beats, before it is resumed, so a run
that ended well in the meantime is not resumed as one that had not (finding 3). A job queued
again with the same words therefore continues where the killed one stopped; a change of the code
it runs, of words, of a plan, of a raw copy or of a shard starts afresh, and so does a launch
after a success, where the tools' own content addressing finds the finished work (an ingest's
"already there", a run folder tools/flow.py reuses). Bank's ingest date is the caller's
`--date`, in the key like any word, so a job asking for another date runs anew under it; where
the words name none, the launcher chooses today for a new run, after the key is taken, and
resume keeps it, so a resumed ingest writes the shard its first half meant, on whatever day the
job is queued again.

A run still running is never resumed, since a resume clones what it has done so far, a catalog
built before the shards that landed since among them. While its flow lasts the launcher keeps a
heartbeat, <root>/launches/<Flow>/<key>/<host>-<pid>.json, written before the flow starts,
naming the run within a second of Metaflow's writing its id, rewritten every minute with the
host, the process and SLURM_JOB_ID, and taken away when the flow ends. The launcher lists the
runs before it reads the beats, so a live run it lists always has a beat it reads; a newest run
that a fresh beat names is live, and so is any newest run while a fresh beat names none yet, or
one the listing lacks, made after it by a launch that may be resuming the newest
(schwingnet.pipeline.marked_live), and the launch starts a run of its own beside it, as two jobs
of a stage ran before Metaflow, the stage's own locks ordering what may not overlap: a second
catalog job waits on BUILD.lock and builds with the shards that landed since. A beat left by a
launcher killed with its job stops counting once it is 300 s old (LIVE_SECONDS), at once where
it names this very Slurm job, which Slurm queued again, and at once where it names a process on
this host that is gone.

The flow runs in a process group of its own, and a SIGTERM or SIGINT the launcher is sent while
it runs is passed on to every process of the flow: Slurm's TERM at a time limit or a preemption,
which reaches every process of the job, and the one job submit sends the batch shell two minutes
before the limit (`--signal=B:TERM@120`), which reaches the launcher where the stage's script
execs it, as bank and catalog do. Without that the TERM killed the launcher and left the flow's
runtime and tasks running, its beat stale and its page open. What has not ended 60 s later
(STOP_GRACE_SECONDS) is killed; the beat is taken away as at any end, so the job Slurm queues
again resumes the run at once; launch.json says which signal ended it; and the launcher exits
128 plus the signal, 143 for SIGTERM. The signal is passed on before the launcher says a word of
it, and a line it cannot write, its reader gone as a pipe's tee goes with its job, is dropped and
its stream pointed at /dev/null, so no message ever cuts a stop short; a launcher that breaks for
any other reason while its flow runs kills the flow before its beat goes. grid/sweep-driver.sbatch
runs the launcher in the background and waits on it, since a shell holds a trapped signal while a
command runs in its foreground: its trap passes job submit's early TERM, or a person's INT, on to
the launcher as TERM, tee ignores both, and the driver waits again, so the launcher stops its flow
and closes the page inside the two minutes and the driver's report still says it exited 143.

Its first line on stdout is the decision, `{"code", "decision", "flow", "key", "live", "origin",
"root"}`, with `code` the code's digest and `live` the id of a newest run passed over as live,
else null, and the flow's own output passes through after it, followed by `{"flow", "run":
"Class/ID", "successful", "verdict"}`. It exits with the flow's own code where that is not 0 (128
plus the signal where the flow was killed, or where the launcher was stopped, above), else with the verdict, so a job's afterok means what
it meant before Metaflow. A refusal comes before any flow starts, as the line `LaunchError:
<words>` on stderr: exit 90 where the kind's PREREG is missing or moved or does not cover the
run's part (above); exit 69 where Metaflow cannot be imported, the datastore's parent folder is
missing or the commit or the code cannot be named; exit 64 for a flow it does not know,
a --max-workers that is no whole number from 1 to 9999 or a --commit among the words, which it
passes itself; and exit 70 where the runs Metaflow lists break a rule of schwingnet.pipeline.
Anything else that stops it prints its traceback and exits 1. Whatever the end, its last line on
stdout is the flow's
`XR_BANK_RC=<code> <date> <time>`, `XR_CATALOG_RC=` or `SWEEP_RC=` (`LAUNCH_RC=` for a flow it
does not know), since the gate's status keeps such a line and withholds the words of every other:
a job's log shows how it ended, a refusal's included (the second review of #252, finding 6). A
bank or catalog job whose flow ran so logs two such lines, the stage's own, behind Metaflow's
prefix, and the launcher's, last, with the job's exit code; a sweep job's driver prints its
SN_SWEEP_RC after the launcher's SWEEP_RC.

The stage scripts call it: grid/02-bank-ingest.sbatch and grid/03-catalog.sbatch exec it whenever
Slurm runs them (SLURM_JOB_ID set and SCHWINGNET_FLOW_STEP not), passing only what the caller
gave, and the flows' steps run the same scripts again with SCHWINGNET_FLOW_STEP=1, which runs
their bodies; a direct bash call, as the tests make, runs the body as before. grid/sweep-driver.sbatch
runs every row through `launch.py sweep`, and calls block_sweep itself only for what runs no row:
`synthetic`, the synthetic catalog, and `state`, the state folder's path for its report. PYDRV on
the grid is grid/bin/train-cpu-python, which carries Metaflow and execs grid/box.sh; every tool
of a bank or catalog step runs through the two, so both are in those kinds' code digests.

## The datastore

Local, on the lab volume: --root, else $SCHWINGNET_METAFLOW, else
/rs/rs_grp_oschome/go2432/metaflow, whose parent must exist. The launcher sets
METAFLOW_DATASTORE_SYSROOT_LOCAL to it, METAFLOW_DEFAULT_DATASTORE and METAFLOW_DEFAULT_METADATA
to local, and METAFLOW_USER to $USER, or schwingnet where neither is set, since Metaflow refuses
to run with no user. The flow runs with the datastore root as its working directory, because
Metaflow 2.19.39 writes a task's card under the .metaflow folder it finds by walking up from the
working directory, while its card reader looks under the datastore root named in the task's
metadata (measured 2026-10-25: a flow run from another folder wrote its cards there, where
get_cards found none; METAFLOW_CARD_LOCALROOT set put them under the datastore without
mf.cards/, where get_cards found none either). The launcher's own folder reaches the flow as
SCHWINGNET_WORKDIR: the stage reports are written under it, as before, and a relative path
among the parameters is read from it. BankFlow's per-recipe halves each run in a folder of their
own, <root>/work/BankFlow/<run>/<recipe>/<half>/, so no half reads another's report, and each
recipe done leaves its report lines in <root>/work/BankFlow/<run>/progress/, start's run, which a
resumed run keeps with start, so the report in progress counts what was done before the cut.

## Looking at a run

From the datastore root, with the train-cpu python on a compute node (the login node runs no
python), so that the card commands find the datastore by the same walk:

    cd /rs/rs_grp_oschome/go2432/metaflow
    python ~/SchwingNet/flows/sweep.py card server            # every card, refreshed live
    python ~/SchwingNet/flows/sweep.py card view <run>/first/<task> --id row
    python ~/SchwingNet/flows/bank.py logs <run>/ingest/<task>

A row's card refreshes every 15 s while it trains with the last line of its train/metrics.jsonl.
`card view` follows a cloned task to the run it was cloned from (its --follow-resumed); SweepFlow's
own export does the same through the task's origin, best-effort, one line for a card not found.
The sweep's state folder holds METAFLOW.json, which names the run and the datastore root.

## What was measured

With Metaflow 2.19.39 in this repository's train-cpu environment (2026-10-24 and 2026-10-25):
a run killed with SIGKILL mid-step, as a Slurm time limit or a preemption kills it, is continued
by `resume --origin-run-id ID`, which clones every finished step and every finished branch of a
foreach, inside the step that failed too, and reruns only the rest, through a switch as well;
resume clones the parameters and never changes them, and continues only a run that did not
finish. `@retry(times=1)` with `@catch(var=...)` lets a branch that keeps failing be recorded
with the artifacts it set before it raised, and the run goes on. `Flow(name).runs("key:<k>")`
under `namespace(None)` lists the runs carrying a tag, newest first, each with `.finished` and
`.successful`; a flow that never ran raises MetaflowNotFound. `metaflow.cards.get_cards(task,
id=...)` raises for a task that made no card, a caught one or a cloned one, whose
`origin_pathspec` names the task it was cloned from. A task killed alone is retried by @retry
within the run, so tests/test_flows.py kills the flow's runtime with the task, as the end of a
Slurm job does. The tests run every flow through the launcher (tests/test_flows.py, with the
train-cpu environment).

## What Metaflow does not cover here

- Reuse across separate runs: a new run after a success does the work again as far as the tools
  let it, and the tools' content addressing is what makes that cheap (an ingest's shard already
  there; tools/flow.py's configuration-addressed run folders; issue #260's ingest reuse notes,
  kept in <grid root>/.reuse/ beside shards/, a dot folder no listing here takes for a shard).
- The fetch, stage 1, which resumes its own downloads by their .part files.
- grid/00-carmlspine.sbatch, the C-ArmLSpine ingest, which ran once.
- A stage's own refusals, which stay its report lines and its verdict, never a fault.
