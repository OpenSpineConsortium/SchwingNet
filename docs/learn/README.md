# Learn by doing

Four short lessons that teach Symphony by running it. Each one takes about ten minutes, needs no Claude account and no key, and works on your own machine with no sign-in at all, or in a Codespace or Google Colab with the GitHub access to this repository that each of those asks for. They are written for students and new users who have never used git's branches or GitHub's pull requests in a team: every step says what to type, what you should see, and why it matters.

Every command on these pages is run by the repository's required check on every pull request (`python3 tools/living_docs.py test`), and its output is compared with the output printed under it. A lesson that no longer matches the code fails the check, so what you read here is what the current release does.

| Lesson | You learn | Features it uses |
| --- | --- | --- |
| [1. Claim your first task](01-first-claim.md) | how two people can never take the same task | claim branches, claim files |
| [2. When Symphony says no](02-push-guard.md) | which pushes are refused, and what to do instead | the push guard |
| [3. Read the board](03-read-the-board.md) | where to find your next task, and what comes first | the board: Queue, Given to workers, Blockers |
| [4. Two students, one file](04-overlaps.md) | how work that touches the same file lands in order | Overlaps |

## How to run a lesson

- **On your machine.** You need git and Python 3.12. From the top of a clone of this repository, copy each grey block into one terminal, in order. Step 0 of every lesson makes a practice folder, `$LAB`, and points Python at the library in tools/; every later block starts with `cd "$LAB"`, so nothing touches your real projects.
- **In Colab.** Each lesson is also a notebook in [notebooks/](notebooks/), generated from the lesson itself so the two never differ. Open one in Colab and choose Runtime, then Run all. Its first cell makes the practice folder and fetches the newest release of the public library, so it needs nothing from this repository. While this repository is internal, Colab opens it only through File, Open notebook, the GitHub tab with "Include private repos" ticked and the organization granted.
- **In a Codespace.** The demo Codespace ([capabilities.md](../start/capabilities.md), Try it in a minute) has everything installed; open a terminal and follow the lesson there.

## The rules of the practice folder

Every block starts with `cd "$LAB"`, so a block never depends on where the one before it left you; that is also how the notebooks' cells run, each in a shell of its own. A local "bare" repository in that folder stands in for GitHub: it refuses the same pushes GitHub refuses, for the same reason, so what you see is the real mechanism, not a simulation.

## Living documents

These pages are living documents in three ways, all enforced by the required check, `bash scripts/check.sh`, so a pull request that breaks one cannot merge:

- **The lessons run.** `python3 tools/living_docs.py test` runs every block marked `bash run` in a fresh practice folder and fails when an output block is no longer printed. A lesson is written with the rule in mind: quote the lines that matter, never a hash or a date.
- **The notebooks follow the lessons.** [notebooks/](notebooks/) is generated from the lessons by `python3 tools/living_docs.py notebooks`; `check` fails when one is out of date, so the Colab version is always the page's own commands.
- **The reference follows the code.** The site's Reference page is made from each module's docstring and each script's opening comment, as Javadoc is made from comments, and `check` fails a module or script that has none.

The tests behind all of it accumulate in [tests/](../../tests/): every test any pull request has added stays there and runs on every pull request and push ([ci.yml](../../.github/workflows/ci.yml)). Run them again at any time with `python3 -m unittest discover -s tests`, or from the CI workflow's Run workflow button on GitHub. The site's Tests page lists each test file and its results from the run that built it.

## Publishing the site

[docs.yml](../../.github/workflows/docs.yml) builds the site on every push to the default branch with `python3 tools/living_docs.py site`, and publishes it with GitHub Pages once two settings are made, which the workflow's own token cannot make:

1. The repository's Settings, Pages, Build and deployment, Source: GitHub Actions.
2. The repository's Settings, Secrets and variables, Actions, Variables tab, New repository variable: name `SYMPHONY_DOCS`, value `pages`.

Then run the Docs workflow once from the Actions tab (Run workflow). On an internal or private repository, Pages is visible only to people who can read the repository (inferred from GitHub's rules for Pages on such repositories). To preview the site locally: `python3 tools/living_docs.py site _site`, then open `_site/index.html`.
