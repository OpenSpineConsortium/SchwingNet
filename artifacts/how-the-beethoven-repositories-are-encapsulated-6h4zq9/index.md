# How the Beethoven repositories are encapsulated

Oct 7, 2026 · @greg

All seven code repositories this work could change are now sealed. Each declares what it offers and what it takes in `interface/INTERFACE.json`. It takes another repository's work only as a pinned copy checked against an `ORIGIN` record, and its own tests fail if a file reaches into another checkout. hpcworker, beethoven-sites, beethoven-desktop, beethoven-qa and beethoven-extension are merged. beethoven-agents and beethoven-research have open pull requests, and the standard itself is merged in the hub as `INTERFACES.md`.

**What greg does next:** two decisions, in "What lands next" below: whether the VS Code edition gives up its own grid scripts for hpcworker's, and whether qa's vendor command should fetch through gh. Everything else has landed. beethoven-qa `v2.0.0` is tagged, beethoven-agents and beethoven-research are re-pinned to it and merged, and beethoven-desktop pins agents' registry schemas (#8, merged).

## The standard

Every repository is a sealed unit. Another repository reaches it only through what it publishes, at a version, through a copy pinned to a merged commit, and never through its source tree. The full text is `INTERFACES.md` in the hub repository. Five rules say what that means, and each repository checks them on itself in its own test run, with no secret and no network.

1. **Own tree.** A repository builds, tests and runs from its own tree. No tracked file reads, runs or copies another checkout. That rules out `../<repository>`, a path built from the checkout's parent, a variable that names another checkout (`HPCWORKER_DIR`), a submodule, a dependency by path or git URL, and a clone of another repository in CI. Prose may still name another repository.
2. **One declaration.** `interface/INTERFACE.json` lists every export (id, kind, integer version, paths, consumers) and every import. Everything not listed is private and may change in any pull request.
3. **Pinned, checked copies.** An import is one folder with an `ORIGIN` record. Only that folder's `pull.sh` fills it, through the person's own `gh` sign-in, from a commit the provider's `main` contains, taking only the paths the provider's manifest lists. Nobody edits it by hand. The consumer's tests fail when one byte differs, and a pull never deletes.
4. **Published surface only.** A parser is tested against the provider's schemas and the vectors its real code wrote. A constant typed by hand (a failure code, a variable to strip) is tested equal to the pinned export. Python imports go only through a `python` export's modules.
5. **Direction.** beethoven-qa, then beethoven-agents, then beethoven-research, never back. The launcher and the engine share data only, never code.

An export has one of eight kinds: `contract` (schemas, a line grammar, the allowed commands, rules and vectors), `schema`, `data`, `python`, `cli`, `files`, `program` (run as a black box in a test, never imported) and `text`. Its version goes up only when a consumer must change its code. A new optional field keeps the version.

A pinned copy's record looks like this:

```
repository OpenSpineConsortium/hpcworker
commit 818f4a2c746b7a81325cfe5e5b02e8bca36c0276
export profiles 1
sha256 cd718ac8…85098 wayne.json
```

When a provider changes an export, the code and the export change in one pull request. A contract's vectors are rewritten by the provider's own tool (`python3 framework/tests/vectors.py --write` in hpcworker), and its tests fail until they are, so an output never moves silently. After the merge, each consumer takes the new copy with its `pull.sh` in a pull request of its own.

## Who takes what from whom

&#91;embedded content: who takes what from whom · 7 repositories\]

Arrows point from the repository that offers to the one that takes. Each solid arrow is one folder in the taker with an `ORIGIN` record. The dashed one is a file beethoven-desktop reads on the student's computer at run time: agents now publishes its schema, and desktop pins it once agents' pull request merges.

| Repository | Offers (each at version 1) | Takes, and into which folder |
| --- | --- | --- |
| hpcworker | `contract`, `contract-text`, `profiles`, `module-schema`, `testbed`, `framework` | beethoven-sites' `modules` into `framework/sites/` |
| beethoven-sites | `modules` | hpcworker's `module-schema` into `schema/` |
| beethoven-extension | `agreement-texts`, `version` | hpcworker's `profiles`, `contract`, `contract-text`, `testbed` and `framework`, each into its own folder under `framework/` (the framework as `framework/shared-copy/`) |
| beethoven-desktop | nothing | hpcworker's `profiles`, `contract` and `contract-text` into folders of the same names; `testbed` and `framework` into `test/hpcworker-testbed/` and `test/hpcworker-framework/` |
| beethoven-qa | `python`, `cli`, `kit`, `plugin`, `docs` | nothing |
| beethoven-agents | `registry` (the schemas of bee's `accounts.json` and usage files) | qa's `python`, `cli`, `kit` and `plugin` into `vendor/beethoven-qa/`; hpcworker's `profiles` and `contract` into `profiles/` and `contract/` |
| beethoven-research | nothing | qa's `python`, `cli`, `kit` and `plugin` into `vendor/beethoven-qa/` |

The launcher (hpcworker, sites, extension, desktop) and the engine (qa, agents, research) meet only in data: agents pins hpcworker's profiles and contract, and desktop pins agents' registry schemas. No code crosses between them.

## How each repository does it

Every repository has the same three pieces. `interface/INTERFACE.json` says what it offers and what it takes. `interface/README.md` says the same in words, with what a taker may rely on. A boundary test in its own suite fails on a reach into another checkout, on a copy that differs from its `ORIGIN`, and on a manifest out of form. What differs is what each one offers and how it proves that the export is the truth about its code.

### hpcworker

- It offers the seam the clients read. `interface/contract/` holds `cli.json` (every command a client may type), `lines.json` (the grammar of the `HPCW-STEP`, `HPCW-KEY`, `HPCW-LOGIN` and gate lines), the JSON Schemas of `status.json`, `connection.json` and the worker's status line, `rules.json` (the credential variables to strip, the agent markers, the sign-in verdicts) and `vectors/`, which the real code wrote. `interface/testbed/` is the fake grid a client's tests run against, and `framework` is the framework itself, offered as a program to run, never to import.
- `framework/tests/test_interface.py` holds the export to the code. The vectors must be what `framework/tests/vectors.py` writes today; the strip list, the markers and the sign-in verdicts must be the code's own; every failure code `connect` prints must be listed with its exit status; the published module schema must be what `profile.py` prints. A change to an output fails here until its vectors are rewritten in the same pull request.
- `framework/tests/test_boundary.py` checks that nothing reaches a sibling checkout, that CI checks out no other repository, and that `framework/sites/` equals its `ORIGIN`. It takes beethoven-sites' modules only through `framework/sites/pull.sh`.

### beethoven-sites

- Data only: one module per university's cluster and one per lab. It offers them as `modules` and takes hpcworker's `module-schema` into `schema/` with `tools/pull_schema.sh`.
- `tools/check_modules.py` checks every module against the pinned schema. `tests/test_boundary.py` holds the manifest, the path rule, the copy and the pull script.

### beethoven-extension

- It takes five hpcworker exports into folders under `framework/` with `interface/pull.sh`. The contract text replaced its own copy of the V11 and V12 documents.
- `extension/test/conformance.test.ts` (55 tests) reads every vector through the code the extension really runs. The line patterns in `contract.ts` must equal `lines.json` character for character, the commands it types must be in `cli.json`, the sign-in verdict must be `rules.json`'s, every file and status line must pass the schemas, and every vector is read or named with the reason it is not. Writing it found seven readers that disagreed with the framework, all fixed in the same pull request.
- `extension/test/boundary.test.ts` covers rules 1 to 3. It offers `agreement-texts` and `version`, so the website can pin them instead of reading this checkout.

### beethoven-desktop

- The same five imports, at the root and under `test/`, taken with `interface/pull.sh`. `--pinned` re-fetches the two program exports, which git ignores, at the commit their `ORIGIN` names.
- `test/contract.test.ts` (24 tests) checks what it types against `cli.json`, the lines it reads against `lines.json`, every vector through its own readers, the schema fields, the strip list against `rules.json`, and `test/gate-standin.sh` against what the contract says the gate prints. It found seven differences, all fixed.
- The real-gate lab now runs hpcworker's pinned `framework` and `testbed` instead of a sibling checkout named by `HPCWORKER_DIR`.

### beethoven-qa

- It offers its Python surface (`interface/python.json`: `beethoven_qa.contracts` and `__version__`, nothing else), its five commands (`interface/cli.json`), the kit, the plugin and the docs.
- The new `python -m beethoven_qa boundary` (`src/beethoven_qa/boundary.py`) checks the five rules over what git tracks. Every repository that pins qa gets the same check by pinning it, and it is a lane of qa's own gate. `tests/test_interface.py` holds the manifest to the code: every published name imports, the commands are the ones the command line accepts, and one version is everywhere.
- Its copy is the one import not taken by `pull.sh`: a consumer takes it with qa's own `vendor` command from a release tag, and `vendor-check` keeps it byte for byte.

### beethoven-agents

- It offers `registry`: the JSON Schemas of bee's `accounts.json` and `usage/<label>.json` in `interface/bee/`, tested against bee's own model and what its status line writes. Desktop and VS Code read those files today.
- It takes qa's copy and hpcworker's `profiles` and `contract`. The credential variables bee, the guard and the image strip, the agent markers they refuse under, and the sign-in cases bee's verdict runs against are now tested against the pinned `contract/rules.json`, not a hand copy.
- `tests/test_boundary.py` also tests `profiles/pull.sh` itself: it takes only the export at a merged commit, refuses what `main` does not hold, and takes only what the manifest declares.

### beethoven-research

- The last link, so it offers nothing. It takes qa's four exports into the pinned copy.
- `tests/test_interface.py` allows `beethoven_qa` imports only through the `python` export's names, no `beethoven_agents` import until one is declared, and no tracked line that reaches another checkout. Its held copy of qa's `python` export must equal qa's own once the copy carries it.

## What still crosses a boundary, and why

Three entries in two repositories still reach another checkout once beethoven-extension's pull request merges. Each one is on a known list in that repository's boundary test, with its reason. A new reach fails the test, and so does an entry whose line has gone, so the list can only shrink. None runs in CI or anywhere a student goes: two are maintainer's tools switched on only by a variable or a flag the maintainer sets, and the third is a comment.

| Repository | File | What reaches out | Why it stays | Removed by |
| --- | --- | --- | --- | --- |
| beethoven-extension | `extension/test/killlist.live.test.ts` | the maintainer's check of a signed kill-list reads it from the website's checkout (`BEETHOVEN_SITE_DIR`) before it is published | the website offers nothing yet | greg, with the website |
| beethoven-extension | `extension/store-assets/src/build_assets.mjs` | `--sync-site` copies the home page's diagram from the website's checkout | the website offers nothing yet | greg, with the website |
| beethoven-desktop | `.github/workflows/ci.yml` | a comment naming `HPCWORKER_DIR`, whose reason is now out of date | nothing: a session could push this workflow file after all | reworded and removed in [beethoven-desktop #7](https://github.com/OpenSpineConsortium/beethoven-desktop/pull/7), merged |

hpcworker, beethoven-sites, beethoven-qa, beethoven-agents and beethoven-research have empty lists. hpcworker's three entries went with [hpcworker #7](https://github.com/OpenSpineConsortium/hpcworker/pull/7) and [hpcworker #8](https://github.com/OpenSpineConsortium/hpcworker/pull/8), both merged, from the access approvals work. That seam is now two plain-text lists: the roster, one AccessID per line, and the readers, an AccessID and a folder per line. VS Code's `admin.mjs` prints them ([beethoven-vscode #13](https://github.com/OpenSpineConsortium/beethoven-vscode/pull/13)), and hpcworker reads them only from a file or a command the person names. The format is written in beethoven-vscode's `ACCESS_CHECK.md` ("Lab storage, read only") and in the header of hpcworker's `grid_access.sh`. Desktop's lab and the extension's end-to-end lane, which used to copy hpcworker's framework from a sibling checkout, now run its pinned `framework` and `testbed` exports, checked against their `ORIGIN` before they start.

## The read-only neighbours

Beethoven for VS Code, the website and the two studies were audited but not changed, because nothing here edits them. The VS Code edition and the website still reach other repositories through sibling checkouts and hand copies. The studies reach no Beethoven code. Each row below is a change that repository's own owner would make.

| Repository | What crosses today | Weight | What it needs |
| --- | --- | --- | --- |
| Beethoven for VS Code | It writes `state.json` and consent markers into the shared sign-in folder `~/.beethoven/claude`, which hpcworker and beethoven-agents also use | high | A written `~/.beethoven` layout (who may write which file), and its own files moved to `~/.beethoven/vscode/` |
| Beethoven for VS Code | Its access commands set the volume's ACL and modes, recursively, over the folder hpcworker's `grid_access.sh` also keeps | high | One owner for the volume ACL (hpcworker), with VS Code's commands calling it or retired |
| Beethoven for VS Code | It mirrors beethoven-agents' `accounts.json` by hand (keys, label pattern, coercions) | high | agents publishes the registry as a schema with vectors; VS Code pins it |
| Beethoven for VS Code | It copies hpcworker's credential strip list and sign-in rule in five places; identical to hpcworker today, but nothing checks it | medium | Pin hpcworker's `contract` export (`rules.json`) and test the five lists against it |
| Beethoven for VS Code | Its tests read hpcworker's tree when `HPCWORKER_DIR` is set | low | The pinned `contract` vectors replace it |
| Beethoven for VS Code | It types Wayne State's host, partitions, QoS and paths by hand | medium | Pin hpcworker's `profiles` export and read them from there |
| Website | `build_site.py` reads both editions' agreement texts and versions from sibling working trees; none of its candidate folders is beethoven-extension, and it renders version 5 of the VS Code terms while VS Code's main has version 7 | high | Pin beethoven-extension's new `agreement-texts` and `version` exports (published in its PR) and the VS Code texts of a released tag, each with `ORIGIN` |
| Website | VS Code's `deploy.sh` writes the website's `services.json` in a sibling checkout | medium | `deploy.sh` prints the routes; the website takes them in a reviewed commit |
| Website | Its PACS demo puts a sibling or pull-request checkout of OpenSpineToolkit on `sys.path` | low | Install OpenSpineToolkit pinned by commit |
| The two studies | Both type Wayne State's scheduler facts by hand and share one unpinned conda environment and container cache in `$HOME` | low | Nothing while no engine job runs them; the engine's job template supplies these when one does |
| spinesurg-ct-nnunet | The worker's container binds the owner's whole lab folder, beside the study's data | high | beethoven-sites and hpcworker decide what a worker binds, so no bind includes a folder that holds patient data |

Every VS Code fix in that table can start now: hpcworker's `contract` and `profiles` are on its `main`, and agents' `registry` is published in agents' open pull request. The audit also found that `grid_access.sh` defaulted its roster to a sibling checkout and called a roster command that did not exist; [hpcworker #7](https://github.com/OpenSpineConsortium/hpcworker/pull/7) and [beethoven-vscode #13](https://github.com/OpenSpineConsortium/beethoven-vscode/pull/13) fixed both.

### Who owns the access service and the grid install

greg asked whether beethoven-vscode installing things on the grid fits this work. It does not, and it is the largest piece left. The VS Code edition's setup copies its own `grid/` folder into the student's `~/.beethoven/bin` and runs `beethoven install` (beethoven-vscode `extension/src/core/wizard.ts`, lines 689 and 738). That writes a `.bashrc` block, submits a bootstrap job and runs the edition's own workers. It is a second cluster side next to hpcworker, from before the split. No boundary test fails on it, because it reads no hpcworker file; the problem is two owners of one cluster side, both writing under `~/.beethoven`. The lines this report draws:

- **Everything that runs on the grid is hpcworker's.** The VS Code edition should become a client of the lab's shared hpcworker, as the browser and desktop editions are: it types only what `cli.json` publishes, reads only what the contract describes, and retires its `grid/` folder. What hpcworker lacks (the request queue behind send, wait and ask, the daemon, the phone and sign-in relays) moves into hpcworker as published commands or is dropped. That is greg's call and a large change.
- **The access service is its own repository.** It runs on Cloudflare, not on the grid, and serves both editions, the website's request pages and `grid_access.sh`. greg chose on 2026-10-07 to move it into a private repository, beethoven-access, and the access approvals thread is doing the move. Its only seam is its HTTP contract (the routes in `ACCESS_CHECK.md`). `grid_access.sh` will fetch the two lists from its admin routes instead of running `admin.mjs` from a VS Code checkout.
- **The grid install lane fits.** The one the access approvals thread is adding lives in hpcworker and installs only hpcworker's shared copy, from hpcworker's own `main`.
- The VS Code licence-key tools stay in beethoven-vscode. Where the signer of the withdrawn-versions list goes is not settled, since it serves both editions; beethoven-access is the likely home.

## What lands next, in order

1. Merge [beethoven #3](https://github.com/OpenSpineConsortium/beethoven/pull/3), which puts the standard, `INTERFACES.md`, in the hub.
2. Merge [beethoven-extension #4](https://github.com/OpenSpineConsortium/beethoven-extension/pull/4). Done: merged on 2026-10-07.
3. Done: [beethoven-qa #4](https://github.com/OpenSpineConsortium/beethoven-qa/pull/4) merged, and greg tagged `v2.0.0` at its merge commit (53d5ae5) on 2026-10-07. A session may not create tags.
4. Done: beethoven-agents and beethoven-research re-pinned to qa 2.0.0 with qa's `vendor --kit`, with the `boundary` lane in their gates and CI; the kit's `standards.yml` reported the required check, and [beethoven-agents #4](https://github.com/OpenSpineConsortium/beethoven-agents/pull/4) and [beethoven-research #6](https://github.com/OpenSpineConsortium/beethoven-research/pull/6) merged on 2026-10-07 with every check green.
5. The two workflow edits are settled. beethoven-desktop's `.github/workflows/ci.yml` comment now gives the true reason, and its boundary test's exception list is empty ([beethoven-desktop #7](https://github.com/OpenSpineConsortium/beethoven-desktop/pull/7)); a session could push that workflow file after all. beethoven-qa's `ci.yml` needs no boundary step, because its test suite runs the boundary check on its own tree (`tests/test_boundary.py`, line 395) and the tests are a CI step.
6. Decide whether qa's `vendor` command should fetch through `gh` like every other pull. Today it copies from a local qa checkout at a release tag, the one exception to rule 3.
7. Done: beethoven-desktop declares and pins agents' `registry` (bee's two account files as JSON Schema) in `registry/`, and `test/registry.test.ts` holds `src/accounts.ts` to them ([beethoven-desktop #8](https://github.com/OpenSpineConsortium/beethoven-desktop/pull/8)). The VS Code edition reads the same `accounts.json` and is greg's to pin.

### Found while building, not fixed here

- **hpcworker.** `framework/lib/adapters/common.sh` line 251 counts a sign-in as a subscription when `apiProvider` is an empty string, but `rules.json` says any provider other than `firstParty` is not, and no published case covers it. Claude Code has not been seen to print that, but it is a gap in the one fundamental rule. It should be closed in hpcworker first, with a case added to `rules.json`.
- **hpcworker.** `lines.json` has no stop line (`worker NAME: stopped (`), which desktop reads. `cli.json` does not publish the gate's invocation, `probe`, `discover`, `claude login --plain` or the browser key's add line, which clients type. hpcworker's `CLAUDE.md` still says the extension refreshes profiles with `framework/profiles/pull.sh`; it is `interface/pull.sh` now.
- **beethoven-agents.** Five modules import `icontract` directly instead of through `beethoven_qa.contracts`, and only `guard.py` has a stated reason. `site.py` reads a `containers_dir` field hpcworker's schema does not define. bee accepts the account labels `apikey` and `default`, which are folders the VS Code edition writes under `~/.beethoven/accounts/`.
- **beethoven-desktop.** `src/accounts.ts` reads agents' account files without declaring the import yet (step 7).
- **beethoven-qa.** `vendor-check --source` refuses a 1.0.0 copy (`vendor.py` line 345). `standards.yml` line 34 lists the groups a second time.
- **beethoven-extension.** The mock portal refuses under 5 of the 9 agent markers (`mock-ood/lib/tool.mjs` line 681). `install.ts` line 109 reads a line hpcworker does not publish. The direct-way lane against the pinned framework is not yet measured, and its grid set-up script is in no repository.

## Pull requests and what was checked

| Repository | Pull request | State | What its run showed |
| --- | --- | --- | --- |
| hub | [beethoven #3](https://github.com/OpenSpineConsortium/beethoven/pull/3) | merged | the standard; the hub has no CI |
| hpcworker | [#6](https://github.com/OpenSpineConsortium/hpcworker/pull/6) | merged | the exports and their tests, green in CI on ubuntu and in the CentOS 7 container |
| beethoven-sites | [#3](https://github.com/OpenSpineConsortium/beethoven-sites/pull/3) | merged | takes hpcworker's merged module schema |
| beethoven-desktop | [#6](https://github.com/OpenSpineConsortium/beethoven-desktop/pull/6) | merged | 24 contract tests; seven differences from the contract found and fixed |
| beethoven-desktop | [#7](https://github.com/OpenSpineConsortium/beethoven-desktop/pull/7) | merged | the reworded comment and the empty exception list; the full gate green locally (106 tests, the packed bundle) |
| beethoven-extension | [#4](https://github.com/OpenSpineConsortium/beethoven-extension/pull/4) | merged | locally 788 tests passed and 38 skipped, the mock's selftest 138 passed, the Rust bridge 17 of 17; seven reader fixes |
| beethoven-qa | [#4](https://github.com/OpenSpineConsortium/beethoven-qa/pull/4) | merged | the full gate on that commit passed locally: 184 tests, the boundary rules, and no counterexample from the symbolic check (11 minutes 39 seconds on 4 cores) |
| beethoven-agents | [#4](https://github.com/OpenSpineConsortium/beethoven-agents/pull/4) | merged | re-pinned to qa 2.0.0 with the boundary lane; gate, image and all six standards groups green |
| beethoven-research | [#6](https://github.com/OpenSpineConsortium/beethoven-research/pull/6) | merged | re-pinned to qa 2.0.0 with the boundary lane; gate and all six standards groups green, 15 tests |
| beethoven-desktop | [#8](https://github.com/OpenSpineConsortium/beethoven-desktop/pull/8) | merged | agents' registry schemas pinned, and accounts.ts held to them; the full gate green locally, 113 tests, 7 of them new |

Every push went through that repository's own gate first. Two things the checks caught:

- **Fourteen readers disagreed with what the cluster side really writes**, seven in the extension and seven in desktop: a status word one did not know, line patterns that matched too little, a stop treated as done before it exited, credential variables missing from a strip list, and more. Each was found by running hpcworker's own vectors through the client's real reader, and each is fixed in that client's pull request.
- **qa's CI found two faults in CrossHair 0.0.111** that the local run had missed. It compiles each literal of a case-insensitive pattern without escaping it, so a `+` raised an error and a `.` matched any character. And a string holding a NUL character trips its own string comparison. The patterns now spell both cases by hand and escape every literal, and the function states its real domain (no path holds a NUL). No contract was loosened, and the record of both faults is in the commit.
