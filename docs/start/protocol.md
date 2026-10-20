# Change the protocol once, everywhere

The claim protocol's rules (the labels, the claim, the board, the coordinator's releases and overlaps, the registry of workers, the protocol check, the clerk, the push guard, the merge gate) live in one place, [OpenSpineConsortium/symphony-protocol](https://github.com/OpenSpineConsortium/symphony-protocol), and four repositories run a copy of it: this template under tools/sdlc_protocol, coordbench, the plugin marketplace and the GitHub App. A change is made there and nowhere else; one merge to its main carries it to every copy as a pull request that each repository's own check decides. A hand edit of a copy fails that repository's check, since the copy is held to the sha256 of every file in its VENDORED record and, on CI, to the library's own files. [ECOSYSTEM.md](https://github.com/OpenSpineConsortium/symphony-protocol/blob/main/ECOSYSTEM.md) says which repository takes which modules.

## Steps

1. **Branch in a fork of symphony-protocol.** Write on symphony-protocol stays its owner's alone, because its Actions hold the App's key (the one-time setup below, step 2) and a writer's pull request runs the workflow that reads it. Everyone else works from a fork: `gh repo fork --clone` makes it, clones it and sets symphony-protocol as `upstream`, the repository the pull request of step 3 opens in. The owner clones symphony-protocol itself with `gh repo clone OpenSpineConsortium/symphony-protocol`. Every branch on this page is made with `--no-track` so that it never takes a default branch as its upstream: wherever git's push.default is upstream, a push of a branch with that upstream writes that default branch.

   ```bash
   gh repo fork OpenSpineConsortium/symphony-protocol --clone
   cd symphony-protocol
   git switch -c my-change --no-track
   ```

2. **Change the module and its tests, and run the checks.** One test module per module, `tests/test_<module>.py`. A rendered string (the board, the guard's refusals, the gate's answers, the VENDORED record) is part of the interface: change one only on purpose, and say so in the pull request. When a module's imports or ecosystem.json change, rewrite the map. A new release raises `__version__` in sdlc_protocol/__init__.py and `version` in pyproject.toml together, which the tests hold equal. Then run the module's own tests (here the board's), the map and the whole check:

   ```bash
   python3.12 -m unittest tests.test_board -v
   python3 scripts/architecture.py
   bash scripts/check.sh
   ```

   You should see the suite pass and check.sh end without a problem; it holds every file to ASCII with LF endings and ECOSYSTEM.md to what architecture.py writes.

3. **Open the pull request.**

   ```bash
   git push -u origin my-change
   gh pr create --fill
   ```

   You should see the check `check` and one job per consumer, `downstream (symphony-template)`, `downstream (coordbench)`, `downstream (symphony-marketplace)` and `downstream (symphony-app)`: each vendors your change into that repository's main and runs its own check there, so a change that would break a consumer is red before it merges. A fork's pull request gets no secrets, so on it `downstream (symphony-template)` and `downstream (symphony-app)`, whose repositories are not public and are read only with the App's key, say they skipped and pass; the owner's own branch runs all four.

4. **When a downstream job is red on purpose,** because a consumer pins the old output in a test or calls a function that changed, that consumer goes first: in a clone of it, vendor your branch and answer the change in a pull request of its own, merge that, then re-run this pull request's downstream jobs. From the consumer's clone, with your branch checked out in ../symphony-protocol:

   ```bash
   git switch -c answer-my-change --no-track
   python3 ../symphony-protocol/scripts/vendor.py . --consumer OpenSpineConsortium/CONSUMER
   ```

   CONSUMER is that repository's name, as the job names it. Then change the test or the code that pinned the old behaviour, run that repository's own `bash scripts/check.sh`, and open its pull request.

   The sync cannot carry such a change for you: it rebuilds its branch from the consumer's main on every run. symphony-protocol's README, "A change a consumer must answer", has the order.

5. **Merge with a merge commit, not a squash,** so the commit each consumer's record names stays the last one that changed the package, and the sync finds the consumer you answered in step 4 already up to date.

6. **Watch the sync.** Nothing reaches the consumers until the owner has approved the release that carries the change (step 7); the Release run that publishes it then starts the workflow Sync at https://github.com/OpenSpineConsortium/symphony-protocol/actions/workflows/sync.yml (also weekly, and by hand with Run workflow, or `gh workflow run sync.yml --repo OpenSpineConsortium/symphony-protocol`), which carries the newest published release, never main's head. You should see one row per consumer in the run's summary: up to date, or the pull request `symphony-protocol/sync` it opened or updated there, as the App Symphony, and whether auto-merge is armed. On every consumer it lands by itself once that repository's required check is green (the one-time setup below, steps 3 and 4), and on the marketplace the same commit raises the plugin's version, so the merge is also the plugin's release. symphony-app is private, and GitHub offers auto-merge on a private repository only on a paid plan, which the organization has. Where a consumer's settings do not allow auto-merge, or its main requires no check, the run's summary and its log give GitHub's reason, and that pull request waits for its owner.

7. **The release, which waits for the owner, and the repositories made from the template.** A merge that raises the version starts the workflow Release at https://github.com/OpenSpineConsortium/symphony-protocol/actions/workflows/release.yml, whose job waits in the environment release for the owner's approval: on the run's page the owner presses Review deployments, ticks release and presses Approve and deploy, which no session can do. Only then does it tag the commit that raised main to the version from step 2 and publish the release; a release a failed run missed is made by the next, and a merge that raises no version waits for the next release. A repository made from the template is not on the sync's list, so its own .github/workflows/protocol.yml brings the release in. Weekly, or at once with Run workflow on its page, it vendors the newest release tag on the branch `symphony-protocol/sync` and opens the pull request; the repository's check decides, and auto-merge lands it where the repository allows it. Where the repository does not let GitHub Actions open pull requests, the run opens an issue instead, whose link opens the pull request in one press; scripts/setup-repo.sh and the front door's Setup App turn that setting on where the organization allows it ([github.md](../setup/github.md), section 8). A repository made before protocol.yml existed lacks it: copy .github/workflows/protocol.yml and tools/protocol_update.py from the template into it once, by pull request. Or bring a release in by hand, from its own clone with symphony-protocol beside it (the first line clones it there if it is not), and land it by pull request:

   ```bash
   [ -d ../symphony-protocol ] || gh repo clone OpenSpineConsortium/symphony-protocol ../symphony-protocol
   git switch main && git pull
   git switch -c symphony-protocol-vX.Y.Z --no-track
   git -C ../symphony-protocol fetch --tags && git -C ../symphony-protocol checkout vX.Y.Z
   python3 ../symphony-protocol/scripts/vendor.py . --consumer OpenSpineConsortium/symphony-template
   bash scripts/check.sh
   git add tools
   git commit -m "Vendor symphony-protocol vX.Y.Z"
   git push -u origin HEAD
   gh pr create --fill
   ```

   You should see a line beginning `vendor: replaced the copy and its record`, `checks ok` after the check, and the new pull request's address at the end; merge it once its check is green.

   When the check fails on the new copy instead, the release changed something the template's tests pin, and the template answered it in a pull request of its own (step 4): in a clone of the template you made the repository from, `git log --stat --full-diff -- tools/VENDORED` lists the commits that moved the record past your version and every file each one changed (without `--full-diff`, only the record), and the files outside tools/ (tests, fixtures, scripts) are that answer; copy them into this branch and commit them with the copy. A repository not made from the template ([existing-repo.md](existing-repo.md)) has no scripts/check.sh: it runs `python3 tools/sdlc_protocol/vendoring.py verify tools` and its own checks in that line's place, and should see the verify line end with `files match VENDORED`.

## The sync's one-time setup, by the owner

Until the variable SDLC_APP_ID is set on symphony-protocol, the sync skips itself, stays green and says in its summary what is missing. Once, in this order:

1. Install the App Symphony on all five repositories, at https://github.com/organizations/OpenSpineConsortium/settings/installations (Configure, then All repositories or the five chosen).
2. Give symphony-protocol the App's id and key, from a clone of OpenSpineConsortium/symphony-app, whose .sdlc-app.env scripts/register.py wrote, so the key goes through a pipe and never onto the screen:

   ```bash
   gh variable set SDLC_APP_ID --repo OpenSpineConsortium/symphony-protocol --body 5258276
   python3 scripts/register.py --print-key | gh secret set SDLC_APP_PRIVATE_KEY --repo OpenSpineConsortium/symphony-protocol
   ```

   The key stays on symphony-protocol only while you are its one writer: the downstream jobs read it on every pull request from a branch of the repository itself, any writer could read it the same way with a workflow of their own, and its tokens push branches and open pull requests on all five repositories, the private symphony-app and the internal template among them. So everyone else works from a fork (the steps above, step 1), whose pull request gets no secrets.

3. Allow auto-merge on the consumers the sync arms it for:

   ```bash
   gh api -X PATCH repos/OpenSpineConsortium/symphony-template -F allow_auto_merge=true
   gh api -X PATCH repos/OpenSpineConsortium/coordbench -F allow_auto_merge=true
   gh api -X PATCH repos/OpenSpineConsortium/symphony-marketplace -F allow_auto_merge=true
   ```

4. Require the check `check` on each consumer's main with a ruleset (Settings, Rules, Rulesets, New ruleset, Import a ruleset, docs/setup/ruleset-main.json), so auto-merge has something to wait for; on symphony-protocol require `check` and, if you like, the downstream jobs.
