# SchwingNet v1: the demo run and what it measured

Source: the thread "SchwingNet video demo plan", 2026-10-21, the owner's ask of 02:16 UTC ("by tomorrow have some demo numbers about a v1 of the schwingnet paper but created using this high quality approach and make sure there are figures and ledgers about what ran and how the quality of the workflow is using my beethoven-qa"); task #11 of docs/research/retraining-plan.md. Confidential, this repository only: nothing here is public until the provisional is filed, and the talk shows results, not methods.

## What this folder holds

- `runs/<run id>/`: one folder per run, copied from the run directory by `tools/flow.py record`: `RUN.json` (the record every number cites), `split-check.json`, `train/metrics.jsonl` (one line per epoch), `train/checkpoint.json` and `train/MODEL.md` (the card, with the checkpoint's sha256; the checkpoint itself stays in the run directory), `train/accuracy.png`, the witness strips of the first and last epoch, and `evaluate/results.md`, `results.json`, `confusion.png`, `per-level.png`.
- Since #12, also in each run's folder: `witness.json` (the witness frames the run drew: frozen in data/witness/witness.json once the first real run is recorded with `--freeze`, else chosen from the run's catalog by schwingnet.witness), `train/witness/frames/` and `evaluate/witness/frames/` (each frame's strip over the epochs and its animation, and a sheet of all frames at the first and last epoch; the full-size picture of every epoch stays in the run directory and in W&B), `evaluate/witness-test.jsonl` (the test, transitional and sweep frames' scores at every epoch, read only at the version boundary), `wandb-sync.json` (whether the run reached W&B, and its links), and `evaluate/latency.json` where the latency step (#13) wrote one. The page that reads them all is docs/research/evaluation/README.md.
- `LEDGER.md`: one row per run: date, run id, mode, what ran, the commit, the catalog version and sha256, what it cost in wall and GPU hours as the runner measured it, the number of jobs, and how it was verified. Appended by `record`, never by hand.
- `report/`: beethoven-qa's evidence report over this repository's package (`pixi run --locked report`): every lane the gate runs, each tool's version, the gate's counts, each standards group's findings, and who decides each verdict. That is "how good the workflow is": the code that produced the numbers, held to the definition of done.

## The workflow, in the order a run takes it

1. Ingest: a bank of frames becomes a content-hashed shard with a manifest (tools/ingest.py, task #33), under the registry's layout; a frame's bytes are its name, duplicates are counted, frozen test persons are refused from a train shard.
2. Build: the manifests become one read-only SQLite catalog, named by its sha256, with the person-keyed split written in (tools/catalog.py; the versioned store is #33).
3. Split check: no person and no frame sits in two parts (SQL over the catalog; `split-check.json`). A run on a split that is not disjoint is refused by the record itself (schwingnet.flow.RunRecord), so no number can be written against a leaky split.
4. Record: tools/flow.py refuses a dirty tree, hashes the catalog, and writes `RUN.json` before any step starts; the run id is the hash of the commit, the catalog's sha256 and the start, so two runs never share one and the same facts give the same id.
5. Train: tools/train.py reads labelled crops from the train and validation parts only, trains the level stage (resnet18, 27-way head) under one seed, and at every epoch writes the metrics line and a witness strip of the same validation crops with truth over prediction, so a reader sees the model learn rather than trusting a curve.
6. Evaluate: tools/evaluate.py reads the test part once, after training, and writes every number as correct/n with its 95 percent Wilson interval and the persons behind it, stamped with the run id, the commit, the clean-tree flag and the catalog's sha256 from `RUN.json`; per level, per source and the transitional stratum apart.
7. Cost: each step is one job, timed by the runner (local) or read from sacct (Slurm): seconds, GPUs, preemptions, exit code; the ledger row sums them.

Every step is a process in the locked pixi environment (`train-cpu` for a laptop or the dry run, `train-gpu` for the grid's H200s, the same `pixi.lock`), so a run is reproduced by the same command on the same commit and catalog.

## The dry run of 2026-10-21 (synthetic bank; the workflow, not the model, is what it measures)

No real frame was read in this run and no grid job was submitted: the grid gate and the Beethoven worker's sign-in are the owner's steps (below), and no training spends without the owner's word. The run used tools/synthetic_bank.py, a bank in the real builders' shape whose frames hold nothing of any person: a vertebra is a bright rectangle with as many dark bars as its level's index, so a trainer that reads the crops learns the level and a trainer that reads nothing scores chance (1/27). An accuracy near 1 here says the workflow works end to end; it says nothing about SchwingNet on fluoroscopy.

| what | value |
|---|---|
| run | a767a466f5c1 (commit 11546b7e534e, catalog 1, sha256 9051dd4f7b35) |
| bank | 1,500 frames from 60 synthetic persons (15 duplicates dropped at ingest), plus 150 test frames of the five frozen test persons (2 duplicates dropped) |
| catalog | 1,633 frames; train 4,840 crops from 54 persons, validation 546 from 6, test 556 from 5 |
| split check | disjoint: no person and no frame in two parts |
| training | 4 epochs, seed 1, batch 64, crops 64x64, from scratch (no ImageNet file on this machine), CPU, 4 cores, 134 s |
| validation | epoch 1: 0.665 (0.624 to 0.703, n=546); epochs 2 to 4: 0.993 (0.981 to 0.997) |
| test, all levels | 556/556, 1.000 (0.993 to 1.000), 5 persons |
| test, per level | T11 24/24, T12 44/44, L1 73/73, L2 82/82, L3 101/101, L4 105/105, L5 79/79, sacrum 48/48 |
| transitional (T13, L6) | none in the synthetic bank; the row is absent, never pooled |
| cost | 0.04 h wall, 0.00 GPU h, 3 jobs |

The full table with every interval is `runs/a767a466f5c1/evaluate/results.md`; the figures are `train/accuracy.png` (validation accuracy with its interval, epoch by epoch), `train/witness/epoch-01.png` and `epoch-04.png` (the same twelve validation crops; four wrong at epoch 1, marked x, none at epoch 4), `evaluate/confusion.png` and `evaluate/per-level.png`.

What the dry run found and fixed: `tools/profile.py` shadows the standard library's `profile` module when a script under tools/ runs, which torch imports, so the trainer and the evaluator take tools/ off their path (commit 11546b7); the gate found `run_id`'s preconditions did not state its domain (a non-ASCII commit raised inside the hash), so they now say hex, and the two functions that take a pydantic model are listed under `[tool.beethoven-qa.unproven]` with that reason, their contracts checked by the tests. On the push of the finished branch the gate reported `hash_part(0, 1.5e-323)` as a counterexample to its own postcondition, which holds concretely (the product of a subnormal share and the hash space is a normal float above zero); CrossHair's float model is the fault, so the share's real domain is stated as a precondition instead, at least one in a thousand (`SplitRule` holds the same bound), and nothing is loosened.

What the dry run did not do: the manifests came from a scratch stand-in that writes the same shape as tools/ingest.py, since #33 (the ingest and the versioned store) was in review when the run was made; the real bank goes through tools/ingest.py and the store, and the record cites the store's version number. The detector stage is not in v1: crops come from the truth boxes, as the plan's stage order allows, and every result row says "over truth boxes".

## The grid run (waits on the owner)

The plan, for one word: the level stage on C-ArmLSpine as ingested, 20 epochs, seed 1, one H200 on `gmsap`, 4 hours of wall time requested (`python tools/flow.py plan --mode slurm --epochs 20 --hours 4` prints the two jobs), at most 6 GPU-hours in all with the evaluation job; the CPU ingest and build on `reqp --qos=requeue`. Nothing is submitted until the owner says go and the number.

Before it can run, three things only the owner can do:

1. The grid gate: `grid-gate.yml` needs the environment `grid` with `GRID_GATE_KEY`, `GRID_ACCESS_ID` and `GRID_HOST_KEY` on this repository (docs/setup/grid.md), or the Beethoven worker signed in with the account the owner keeps (`hpcworker claude login`); the chain was stopped on 2026-10-21 01:25 UTC.
2. The bank on the grid: the real builders' output under the registry's grid root (`/rs/rs_grp_oschome/go2432/data/carmlspine`), ingested by tools/ingest.py from a grid job; `tools/ingest.py plan` reports the frozen persons the bank never showed, which is the check that the case spelling matches `data/splits/test-persons.json`.
3. ImageNet weights as a file: compute nodes have no internet, so `--weights <resnet18 state_dict>` is a file on the lab volume, named in the record by its sha256, or the run starts from scratch and says so.

## Weights and Biases

The owner's words of 2026-10-21: the grid holds a W&B key and the runs are to be pushed there, visible as soon as training starts. tools/wandb_log.py looks for the key by name only, in this order: the environment's WANDB_API_KEY, the file ~/.wandb/token.env (one line WANDB_API_KEY=..., mode 600, as the grid's other token files are), and ~/.netrc's api.wandb.ai entry, which `wandb login` writes. Where one is found the trainer and the evaluator log online, live, epoch by epoch, to the project SchwingNet (WANDB_PROJECT and WANDB_ENTITY override it), one W&B run per step grouped by the run id. Where the node has no route out, W&B's start gives up within a minute and the step logs offline under the run's wandb/ folder; tools/flow.py, on the login node, pushes each step's offline run as soon as the step ends. The flow's last line, the ledger row and `wandb-sync.json` say whether the run reached W&B, and why not where it did not; nothing about the key is written anywhere but the key's own file.

## Reproduce

```
pixi run --locked python tools/flow.py run --catalog <catalog.sqlite> --out <runs> --mode local --epochs 4 --seed 1
pixi run --locked python tools/flow.py record --run <runs>/<run id> --into docs/research/v1-demo/runs --activity "..." --verified "..."
```

The same commit, catalog and seed give the same run id and, on the same CPU build of torch, the same numbers; a different machine may differ in the last digits of the loss, never in which crops are right, and the witness strips show which.
