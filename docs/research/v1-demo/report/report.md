# Evidence report: https://github.com/OpenSpineConsortium/schwingnet

Made 2026-10-21T02:56:09+00:00 by beethoven-qa 6.0.0 (`python -m beethoven_qa report`). **Every lane passed.**

Beethoven runs Claude Code and is not an Anthropic product; "Claude" and "Claude Code" are Anthropic's marks, used here to say what it runs; "Open OnDemand" is the mark of its publisher.

## The repository

- HEAD `3a0407904f9ccf17cdc5e040b04644ad38e57027` on `claude/11`
- the tree was clean when the report began
- origin: https://github.com/OpenSpineConsortium/schwingnet

## The lanes

Each command of each task of `pixi.toml` ran as its own process, in the environment the report was started in; the output file holds everything it printed.

| task | command | exit | seconds | output |
| - | - | - | - | - |
| lint | ruff check src tests/schwingnet | 0 | 0.0 | lanes/lint-1.txt |
| lint | ruff format --check src tests/schwingnet | 0 | 0.0 | lanes/lint-2.txt |
| typecheck | mypy src | 0 | 0.4 | lanes/typecheck-1.txt |
| test | pytest -q | 0 | 3.8 | lanes/test-1.txt |
| boundary | python -m beethoven_qa boundary | 0 | 4.2 | lanes/boundary-1.txt |
| symbolic | python -m beethoven_qa gate | 0 | 366.7 | lanes/symbolic-1.txt |
| standards | python -m beethoven_qa standards all --sarif /home/user/schwingnet-11/docs/research/v1-demo/report/sarif | 0 | 22.3 | lanes/standards-1.txt |
| vendor-check | python -m beethoven_qa vendor-check | 0 | 0.5 | lanes/vendor-check-1.txt |

## The environment

What `pixi.lock` pins, and what each tool answers to `--version`. `pixi.lock` read: 87 of its 280 records are the environment `default` for linux-64, this machine's platform.

| package | pinned in pixi.lock | reports itself as |
| - | - | - |
| python | 3.11.17 | Python 3.11.17 |
| ruff | 0.17.1 | ruff 0.17.1 |
| mypy | 2.4.0 | mypy 2.4.0 (compiled: yes) |
| pytest | 9.1.1 | pytest 9.1.1 |
| typeguard | 4.6.0 | says nothing of itself |
| beartype | 0.23.1 | says nothing of itself |
| icontract | 2.7.3 | says nothing of itself |
| pydantic | 2.14.1 | says nothing of itself |
| crosshair-tool | 0.0.111 | says nothing of itself |
| z3-solver | 5.3.1.0 | says nothing of itself |
| complexipy | 8.1.0 | complexipy 8.1.0 |
| radon | 6.0.1 | 6.0.1 |
| bandit | 1.9.4 | bandit 1.9.4 |
| coverage | 7.16.2 | Coverage.py, version 7.16.2 with C extension |
| lizard | 1.24.1 | 1.24.1 |
| jscpd | 5.4.2 | jscpd 5.4.2 |
| zizmor | 1.31.1 | zizmor 1.31.1 |

## The gate

Of 42 conditions, **4 were confirmed over all paths** (a proof), 38 were not confirmed within 20 s each (a bounded search that found no counterexample, not a proof), and 0 could be given no input that meets the precondition (a vacuous contract, or one stated over values CrossHair cannot build; either fails the gate).

| target | confirmed over all paths | not confirmed | precondition unmet |
| - | - | - | - |
| schwingnet.catalog.band | 0 | 2 | 0 |
| schwingnet.catalog.best | 0 | 2 | 0 |
| schwingnet.catalog.content_digest | 0 | 2 | 0 |
| schwingnet.catalog.cosine | 0 | 1 | 0 |
| schwingnet.catalog.hash_part | 0 | 2 | 0 |
| schwingnet.catalog.is_transitional | 1 | 0 | 0 |
| schwingnet.catalog.part_of | 0 | 1 | 0 |
| schwingnet.catalog.region_of | 2 | 0 | 0 |
| schwingnet.catalog.shard_name | 0 | 3 | 0 |
| schwingnet.catalog.view_band | 0 | 2 | 0 |
| schwingnet.catalog.where_clause | 0 | 3 | 0 |
| schwingnet.flow.gpu_hours | 0 | 1 | 0 |
| schwingnet.flow.ledger_row | 0 | 3 | 0 |
| schwingnet.flow.run_id | 0 | 2 | 0 |
| schwingnet.flow.wall_hours | 0 | 1 | 0 |
| schwingnet.flow.wilson | 0 | 2 | 0 |
| schwingnet.measure.better | 1 | 0 | 0 |
| schwingnet.measure.fraction | 0 | 1 | 0 |
| schwingnet.slurm.elapsed_seconds | 0 | 1 | 0 |
| schwingnet.slurm.is_finished | 0 | 1 | 0 |
| schwingnet.slurm.job_id_of | 0 | 1 | 0 |
| schwingnet.slurm.wall_time | 0 | 1 | 0 |
| schwingnet.sources.bar | 0 | 1 | 0 |
| schwingnet.sources.counts_cell | 0 | 1 | 0 |
| schwingnet.sources.escape_cell | 0 | 1 | 0 |
| schwingnet.sources.format_number | 0 | 1 | 0 |
| schwingnet.sources.table_row | 0 | 1 | 0 |
| schwingnet.sources.tally | 0 | 1 | 0 |

Functions set aside under `[tool.beethoven-qa.unproven]`, never targets; their contracts are checked by the tests alone:

| function | reason |
| - | - |
| schwingnet.flow.result_line | takes a ResultRow, a pydantic model CrossHair cannot construct; its contracts are checked by the tests |
| schwingnet.slurm.sbatch_script | takes a JobSpec, a pydantic model CrossHair cannot construct; its contracts are checked by the tests |

## The code standards

Each group's verdict as printed, the tools its SARIF log names, and its results by level and by `baselineState` against the base commit (`new` and `updated` errors block).

- **coverage**: passed; coverage.py 7.16.2; results by level: no results; by state: none
- **design**: passed; beethoven-qa 6.0.0; results by level: no results; by state: none
- **duplication**: passed; jscpd 5.4.2; results by level: no results; by state: none
- **readability**: passed; complexipy 8.1.0, ruff 0.17.1, lizard 1.24.1; results by level: no results; by state: none
- **security**: passed; bandit 1.9.4; results by level: no results; by state: none
- **supply-chain**: passed; beethoven-qa 6.0.0, zizmor 1.31.1; results by level: 160 error, 23 note; by state: 183 unchanged

## Enforcement

- `git config core.hooksPath`: `.githooks`
- `.githooks/pre-push`: present, executable; hands over to `pixi run --locked gate`
- required checks of `.github/rulesets/main.json`: none (strict: unknown)
- who the rule lets past its checks: no one it names
- workflows and their jobs:
  - `add-worker.yml`: add
  - `agents.yml`: import, plan, run
  - `automerge.yml`: arm
  - `board.yml`: board
  - `ci.yml`: check, values
  - `claude.yml`: claude
  - `coordinator.yml`: route, plan, unblock, integrate, tidy
  - `docs.yml`: build, deploy
  - `drive-organize.yml`: catalog, organize, open, accept
  - `drive-sync.yml`: sync
  - `gate.yml`: gate
  - `grid-gate.yml`: gate
  - `grid.yml`: start, grid
  - `metrics.yml`: metrics
  - `papers.yml`: queue
  - `pool.yml`: plan, probe, publish
  - `protocol.yml`: update
  - `queue.yml`: gate
  - `rulesets.yml`: apply
  - `settings.yml`: apply
  - `standards.yml`: standards / ${{ matrix.group }}, standards (every group green), scorecard (report)
  - `sync.yml`: offer
  - `template-init.yml`: init
  - `tidy.yml`: tidy
  - `token.yml`: mint, store, manage, no-app, crowd
  - `workers.yml`: registry, work, pool-publish

## Who decides each verdict

| check | decided by |
| - | - |
| lint | a tool, ruff 0.17.1 |
| typecheck | a tool, mypy 2.4.0 |
| test | a tool, pytest 9.1.1; what each test asserts is a person's judgement |
| boundary | home-made code, `beethoven_qa.boundary`, contracted and under the gate, whose table says how far each contract was confirmed |
| symbolic, check 1: every public function carries contracts | home-made code, `beethoven_qa.gate`, contracted and under the gate, whose table says how far each contract was confirmed; what reads the files is private code the tests hold |
| symbolic, check 2: no counterexample within the bound | a tool, crosshair-tool 0.0.111 with z3-solver 5.3.1.0 |
| standards: coverage | the findings: a tool, coverage.py 7.16.2; the verdict over them: home-made code, beethoven-qa 6.0.0 (the limit, the base matching), contracted and under the gate, whose table says how far each contract was confirmed |
| standards: design | the findings: home-made code, beethoven-qa 6.0.0; the verdict over them: home-made code, beethoven-qa 6.0.0 (the limit, the base matching), contracted and under the gate, whose table says how far each contract was confirmed |
| standards: duplication | the findings: a tool, jscpd 5.4.2; the verdict over them: home-made code, beethoven-qa 6.0.0 (the limit, the base matching), contracted and under the gate, whose table says how far each contract was confirmed |
| standards: readability | the findings: a tool, complexipy 8.1.0; a tool, ruff 0.17.1; a tool, lizard 1.24.1; the verdict over them: home-made code, beethoven-qa 6.0.0 (the limit, the base matching), contracted and under the gate, whose table says how far each contract was confirmed |
| standards: security | the findings: a tool, bandit 1.9.4; the verdict over them: home-made code, beethoven-qa 6.0.0 (the limit, the base matching), contracted and under the gate, whose table says how far each contract was confirmed |
| standards: supply-chain | the findings: home-made code, beethoven-qa 6.0.0; a tool, zizmor 1.31.1; the verdict over them: home-made code, beethoven-qa 6.0.0 (the limit, the base matching), contracted and under the gate, whose table says how far each contract was confirmed |
| vendor-check | home-made code, `beethoven_qa.vendor`, contracted and under the gate, whose table says how far each contract was confirmed |
| whether a change merges | GitHub's required checks, the rule as code in `.github/rulesets/main.json`; no person |
| every limit, and what a contract or a test means | a person, in a reviewed release of beethoven-qa |

## Where a language model is involved

- The plugin's workflows (gate-until-green, verify-module, improve-module), its skills and its stream agent have a language model write code and contracts; the gate then proves the contracts, and a person reviews what they mean.
- The plugin's coaching hook has a language model read a verdict: after an edit it is shown what the code standards would block in that file, and the edit stays as it is.
- No verdict in this report comes from a model. Each is a tool's, the gate's contracted code's, or GitHub's rule's, as the table above says.

## What this report does not show

- A condition "not confirmed" is a bounded search that found no counterexample within its seconds; it is not a proof. Only a condition confirmed over all paths is one.
- The code standards block only code new or worse since the base commit; the findings of older code are recorded as unchanged and pass.
- A green test lane says every test passed; what each test means, and whether it is the right test, is a person's judgement, and so is what each contract promises.
- The pre-push hook runs every lane on the machine that pushes; GitHub's runner runs the jobs the Enforcement section lists, and a lane no job runs is checked by the hook alone. This report is as true as the machine that made it, and no truer: its lanes ran in that machine's environment.
