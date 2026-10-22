# data/reproduce: the manifest and the fetch code, copied

What is here, where each file comes from, what was checked and when, and how to use it. Every number about a source
is in the manifest; this file says only what the copies are.

| File | What it is | From |
| --- | --- | --- |
| `sources.json` | the manifest: 211 imaging sources, each with its origin links, acquisition date and method, counts, licence and access, grid layout, defects, and the commands and checks that fetch and verify it again | Gregory-Schwing-MD-PhD/spinesurg-ct-nnunet (private), branch L6_Class, `data_platform/sources.json` at commit bf1432f (2026-10-20) |
| `reacquire/reacquire.py` | re-acquires any source by id: a dry run prints the exact commands with the variables resolved and the checks; `--run` executes inside a Slurm job and writes a state folder; `--verify` runs only the checks; it refuses to run work on the login node | the same commit, `data_platform/reacquire/reacquire.py` |
| `reacquire/reacquire.sbatch` | the Slurm wrapper that runs it on a compute node | the same commit, `data_platform/reacquire/reacquire.sbatch` |
| `map.json` | for every registry record of `data/sources/`, the manifest records that hold it, with the basis of each mapping | written here |
| `SHA256SUMS` | the SHA-256 of the three copies; `python3 tools/reproduce_table.py check` recomputes and compares them, so a changed copy fails `scripts/check.sh` | written here |

The page made from these is `docs/research/datasets-reproduce.md`.

## What was checked on 2026-10-20, in the source repository on the owner's laptop, with no network

- `python3 reacquire.py --list`: 211 sources, each with its route and mode.
- `python3 reacquire.py --grid --all`: the dry run of every source, 2,171 lines, exit code 0, no error in the output.
- `python3 test_reacquire.py`: 28 tests, OK, in 29 seconds. The suite covers the planning side: the manifest's two
  forms agree, every source has a usable re-acquisition entry, every command parses, every repository tool a command
  names exists, the dry run prints every command, the login-node refusal, `--run` writing its state folder, and the
  helpers verifying what they fetch, against local stand-ins.
- The three copies here are byte-identical to the source files at bf1432f (`cmp`), and SHA256SUMS records them.

The test suite is not copied: it expects the source repository's layout, where it checks that the tools the rebuild
commands name exist. It runs there.

## How to use it

- Dry run on any machine, standard library only:
  `python3 data/reproduce/reacquire/reacquire.py --grid <id> [<id> ...]` prints, per source, the commands with the
  variables resolved to the grid's roots, the checks that prove a copy, and the manual steps a gated source needs.
  `--list` prints every id; `--all --modes run submit` covers everything that runs unattended.
- On the grid, run the same bytes from the source repository, because the rebuild routes call that repository's
  tools under `${REPO}` (`~/spinesurg-ct-nnunet`):
  `cd ~/spinesurg-ct-nnunet/data_platform/reacquire && mkdir -p logs && sbatch -D "$PWD" --export=ALL,IDS="<id>",MODE=--run reacquire.sbatch`;
  `MODE=--verify` runs only the checks. Compute nodes have internet; the login node never fetches.
- Secrets for gated routes (`HF_TOKEN`, `KAGGLE_API_TOKEN`) come from the submitter's environment. Nothing here
  holds a token, and the checks refuse one.

## Keeping it current

When the source data platform changes, copy the three files again from the new commit, rewrite SHA256SUMS, name the
commit here, run `python3 tools/reproduce_table.py render`, and say so in the pull request. A partial update cannot
land silently: the check fails when a copy and SHA256SUMS disagree, or when the page and its inputs differ.
