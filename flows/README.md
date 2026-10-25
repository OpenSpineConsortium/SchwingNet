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
  manifests to the marker (issue #80); a kill reruns it whole, which costs under a minute. Its
  verdict is the stage's XR_CATALOG_RC.
- `sweep.py`, SweepFlow: one plan of the block smoke test (grid/sweeps/<plan>.json). start runs
  `tools/block_sweep.py prepare`, a foreach over the rows with no parent runs `block_sweep.py row`
  for each, a second foreach the warm starts, which read a parent's train/best.pt, and end runs
  `block_sweep.py results`, writes METAFLOW.json into the plan's state folder, exports the rows'
  cards there (cards/<step>-<slug>.html) and makes a card of the results table. A row whose `row`
  could not run or record it (any exit but 0; block_sweep says 2) raises, is retried once at once
  (`@retry(times=1)`), and is then caught (`@catch(var="fault")`), so the other rows still run
  and the verdict is 1. The verdict is 0 only when every row was recorded and did what the
  compatibility check predicted. A kill mid-row resumes with every finished row cloned and the
  cut row run again, which tools/flow.py carries on from its last epoch (tools/train.py --resume).

Every flow's end step sets an int artifact `verdict`, 0 when all went well and 1 otherwise.

Where a list a foreach would take is empty (no recipe with a raw copy, no warm start in a plan),
a switch, Metaflow 2.19's conditional next (`self.next({...}, condition=...)`), steps past the
foreach, since Metaflow refuses a foreach over nothing. A switch's path may not lead straight to
a join step, so a switch lands on a plain step: BankFlow's end, SweepFlow's middle and end.

## Starting and resuming: always the launcher

    python flows/launch.py {bank|catalog|sweep} [--max-workers N] [--root DIR] -- <flow parameters>

The launcher names a launch by a key, the first 16 hex of the sha256 of the flow, the commit,
the flow's parameters as given and, for bank, a line per recipe start would list with the
recipe's bytes and its raw folder's state, every file by path, size and modification time as
tools/bank.py's BANK.json stamp lists it (flows/bank.py's key_reads; schwingnet.pipeline.run_key),
since a resume clones start's listing of what has a raw copy and every bank step that finished:
a raw copy fetched, grown or changed since the cut, or a recipe edited, names another key and so
a new run, while raw copies as they were resume. Every run it starts or resumes carries the
tags `key:<key>` and `commit:<7>`. It lists the runs of the flow carrying the key, newest first,
and the newest decides (schwingnet.pipeline.decide): a newest run that did not succeed, killed
or failed, is resumed (`resume --origin-run-id`, with the same --max-workers and no parameters,
which resume clones); else a new run starts. A job queued again with the same words therefore
continues where the killed one stopped; a change of code, of words or of a raw copy starts
afresh, and so does a launch after a success, where the tools' own
content addressing finds the finished work (an ingest's "already there", a run folder tools/flow.py
reuses). Bank's ingest date is the caller's `--date`, in the key like any word, so a job asking
for another date runs anew under it; where the words name none, the launcher chooses today for a
new run, after the key is taken, and resume keeps it, so a resumed ingest writes the shard its
first half meant, on whatever day the job is queued again.

A run still running is never resumed, since a resume clones what it has done so far, a catalog
built before the shards that landed since among them. While its flow lasts the launcher keeps a
heartbeat, <root>/launches/<Flow>/<key>/<host>-<pid>.json, written before the flow starts,
naming the run within a second of Metaflow's writing its id, rewritten every minute with the
host, the process and SLURM_JOB_ID, and taken away when the flow ends. The launcher lists the
runs before it reads the beats, so a live run it lists always has a beat it reads; a newest run
that a fresh beat names, or any newest run while a fresh beat names none yet, is live
(schwingnet.pipeline.marked_live), and the launch starts a run of its own beside it, as two jobs
of a stage ran before Metaflow, the stage's own locks ordering what may not overlap: a second
catalog job waits on BUILD.lock and builds with the shards that landed since. A beat left by a
launcher killed with its job stops counting once it is 300 s old (LIVE_SECONDS), at once where
it names this very Slurm job, which Slurm queued again, and at once where it names a process on
this host that is gone.

Its first line on stdout is the decision, `{"decision", "flow", "key", "live", "origin", "root"}`,
with `live` the id of a newest run passed over as live, else null, and its last `{"flow", "run":
"Class/ID", "successful", "verdict"}`; the flow's own output passes
through between them. It exits with the flow's own code where that is not 0 (128 plus the
signal where the flow was killed), else with the verdict, so a job's afterok means what it meant
before Metaflow. It refuses, exit 69, where Metaflow cannot be imported or the datastore's parent
folder is missing, and, exit 64, a flow it does not know or a --commit among the words, which it
passes itself.

The stage scripts call it: grid/02-bank-ingest.sbatch and grid/03-catalog.sbatch exec it whenever
Slurm runs them (SLURM_JOB_ID set and SCHWINGNET_FLOW_STEP not), passing only what the caller
gave, and the flows' steps run the same scripts again with SCHWINGNET_FLOW_STEP=1, which runs
their bodies; a direct bash call, as the tests make, runs the body as before. grid/sweep-driver.sbatch
runs `launch.py sweep` and never block_sweep itself. PYDRV on the grid is grid/bin/train-cpu-python,
which carries Metaflow.

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
