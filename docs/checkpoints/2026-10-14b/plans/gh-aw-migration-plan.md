# Compiling Symphony's workflows: the plan

A plan, not a change: no pull request is opened by it and no workflow is edited. Written 2026-10-14 for the owner's three messages of 03:23Z, 04:06Z and 04:14Z, the last of which is the constraint this version is built from, word for word: "dont regress any features, just migrate as much handrolled workflow to compiled workflow as possible without losing the absolutely solo usage of a claude substription token". The first version of this plan recommended Copilot inference for Claude in Actions; the owner refused it, and nothing here moves any Claude run off the subscription token.

Measured at symphony-template cb83274 (main, after #70 and #74 merged on 2026-10-14), symphony-protocol 3e98b88 (0.4.1) with its drafts #21, #23 and #24, github/gh-aw d06e087 (docs under docs/src/content/docs/, runtime under actions/setup/js/, compiler under pkg/), and github/docs main. Four sample workflows were compiled with gh-aw built from that commit, the last of them twice; their sources and locks are quoted where they matter. The two notes beside this file, /mnt/project-files/notes/gh-aw-vs-symphony.md and symphony-vs-gh-aw.md, hold the per-capability table and the scale scoring and are not repeated.

## Status (2026-10-14, 10:15 UTC)

Both decisions were approved by the owner on 2026-10-14, first on the coordinator's two decision cards in the project chat (10:03 and 10:04 UTC) and then in this thread ("yes, yes", 10:05 UTC). Both are queued, as the cards said:

- Candidate A, Symphony's own compiler for all eleven workflows, starts once 0.5.0's fixes have landed, as its own thread within the owner's cap of three threads at once. The coordinator will say when. The order from PR 1a to PR 7 in section 6 stands.
- The gh-aw pilot of section 7 runs on symphony-protocol-canary after the owner releases 0.5.0.

PR 1a was prepared before the timing was known and then parked: nothing was pushed and no pull request exists. Its commit is saved as /mnt/project-files/plans/candidate-a-pr-1a-pins.patch, made against main at cb83274, and it passed `bash scripts/check.sh` (564 tests); its adversarial review was stopped before it reported. Whoever picks it up re-resolves the six pins with `git ls-remote` first, since the tags will have moved, and then runs the review. What it holds: the 30 `uses:` lines pinned to commits with a `# vX.Y.Z` comment (checkout v7.0.1, upload-artifact v7.0.2, cache v6.1.0, create-github-app-token v1.12.0, claude-code-action v1.0.249, the last the peeled commit of an annotated tag); .github/dependabot.yml grouping every action into one weekly pull request, since commit pins take every patch release and claude-code-action ships several a week; .claude/rules/writing.md:6 and docs/setup/github.md:42 reworded to "pinned to a commit"; tests/test_usage.py reading the pinned form; and tests/test_pinned_actions.py, which fails on a tag, a pin without its version comment, or one action pinned to two commits. zizmor's unpinned-uses findings went from 30 to 0 with it; the 13 artipacked and 1 github-app findings are PR 1b's.

Two facts read for PR 1b, at claude-code-action's commit 34968b5 (v1.0.249): agent mode, which workers.yml and coordinator.yml run, calls configureGitAuth (src/modes/agent/index.ts:47, 61), which unsets the checkout's persisted extraheader and sets the action's own token (src/github/operations/git-config.ts:51-93); tag mode, which claude.yml runs, calls setupBranch first (src/modes/tag/index.ts:67) and configureGitAuth after it (:84, :97), so claude.yml's checkout keeps its credential. The checkouts and the git network commands of every job are listed in section 3, Credentials in checkouts.

## The answer

Yes, with one word made exact: the hand-written workflows can be replaced by generated ones, the Symphony protocol unchanged and the subscription token the only Claude credential anywhere, when the generator is this repository's own. gh-aw, the compiler the owner named, can compile three of the eleven and only through a route it declares unsupported; it cannot take the eight deterministic workflows at all, and its own Claude engine ignores the subscription token. The two routes that keep the token:

- Candidate A, a compiler of Symphony's own: a Python module in tools/ (standard library only) that generates all eleven workflows from a checked source, with the anthropics/claude-code-action steps exactly as they are today, on CLAUDE_CODE_OAUTH_TOKEN. It compiles all eleven, loses nothing by construction, since its first output for each workflow is the committed file byte for byte, and `bash scripts/check.sh` fails when a generated file drifts from its source, as it already fails when the vendored protocol drifts from tools/VENDORED. This is the recommendation.
- Candidate B, gh-aw with a self-defined engine: gh-aw lets a repository define its own engine in `.github/workflows/shared/<name>.md`, and a definition that installs Claude Code and runs `claude -p` with CLAUDE_CODE_OAUTH_TOKEN compiled today in strict mode, twice. The first definition passed the token but no MCP configuration, tools list or turn cap to the CLI, so its agent could have called no safe output; the second (Appendix A) wires them through gh-aw's own Claude converter, turns gh-aw's threat detection off, since detection runs only on gh-aw's built-in engines and those bill Copilot or an API key, and gives each worker its own concurrency group. It can compile only the three workflows that run Claude (workers' Claude leg, the coordinator's four jobs, the mention), never the eight deterministic ones, and it changes how those three do several things the table in section 5 lists. Its run time is unmeasured and gh-aw declares subscription OAuth unsupported. It is a pilot for the canary after 0.5.0, if the owner wants gh-aw's sandbox and safe outputs at all; it is not the migration.
- Candidate C, gh-aw as a shell around claude-code-action: rejected. A gh-aw workflow always runs its engine step, so the Claude work would still be the hand-written step and the compiled part would compile nothing that matters.

Recommendation: Candidate A for all eleven, starting now and in parallel with the 0.5.0 fixes, since it changes no behaviour and the protocol library is untouched. Candidate B only as a measured pilot, after 0.5.0, if the owner says yes to gh-aw as a dependency.

The first pull requests: pin every action to a commit, settle the checkout credentials and give the eleven files one YAML style (three small ones, now); then the compiler with the two smallest workflows generated; then the board, the check and the metrics workflows. No setting changes, no secret moves, nothing for the owner to click.

## 1. The constraint, read against every route

| Route | Claude credential | Bills | Compiles | Verdict |
| --- | --- | --- | --- | --- |
| A: Symphony compiler, claude-code-action unchanged | CLAUDE_CODE_OAUTH_TOKEN, the repository secret, as today | the account's plan | all eleven | keeps the token solo; recommended |
| B: gh-aw, self-defined engine `claude-subscription` | CLAUDE_CODE_OAUTH_TOKEN, passed to `claude -p` by the engine definition | the account's plan, with gh-aw's threat detection turned off, since it runs only on gh-aw's built-in engines | the three agentic workflows | keeps the token solo; compiles with the MCP wiring; run time unmeasured; declared unsupported by gh-aw |
| C: gh-aw with claude-code-action in `steps:` and an engine that does nothing | the token for the step, plus whatever the engine step needs | the account's plan plus the engine's | nothing useful | rejected |
| gh-aw's built-in `claude` engine on Copilot inference or ANTHROPIC_API_KEY | none, or an API key | an organization Copilot plan or Anthropic's API | the three | refused by the constraint |

The facts behind the gh-aw rows. gh-aw's authentication page says, in full: "CLAUDE_CODE_OAUTH_TOKEN is not supported by GitHub Agentic Workflows. Provider-based OAuth authentication (such as billing through a Claude Teams or Claude Max subscription) is not supported. If you have set CLAUDE_CODE_OAUTH_TOKEN as a repository secret, it will be ignored" (docs reference/auth.mdx:217-219). The compiler enforces that for its built-in Claude engine alone: `gh aw secrets set` refuses to store the Claude engine's secret while the operator's shell exports CLAUDE_CODE_OAUTH_TOKEN (pkg/cli/engine_secrets.go:27, 342, 714), and nothing reads the secret's name in an engine definition. A self-defined engine is a documented route (third-party-agent.md; the vendored samples opencode, kiro, cursor, aider, crush and goose under .github/workflows/shared/, each called an unsupported sample at its lines 8 and 121): an `engine:` block with `auth: [{role, secret}]`, `installation` (npm package, version, binary), `execution` (command, args, the flags for the MCP configuration and the model) and an `mcp.config-adapter` that writes the gateway's server list in the CLI's own shape. The definition in Appendix A names CLAUDE_CODE_OAUTH_TOKEN as its secret; `gh aw compile --strict` asked for `--approve` once, for a secret new to the repository, and compiled a 1,689-line lock with four jobs (activation, agent, safe_outputs, conclusion) whose agent job validates the secret, installs `@anthropic-ai/claude-code@2.1.296`, writes Claude's MCP configuration with gh-aw's own convert_gateway_config_claude.cjs (lock lines 796-800) and runs `claude -p --no-chrome --strict-mcp-config --permission-mode dontAsk --allowed-tools '<the template's list>,mcp__safeoutputs,mcp__github' --output-format stream-json --verbose --mcp-config "<runner temp>/gh-aw/mcp-config/mcp-servers.json" "$(cat prompt)"` (lock line 1014) with `CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}` in its environment. So gh-aw can carry a subscription-token Claude step through its compiler, with the MCP servers the safe outputs need wired in. What that proves and what it does not is section 4.

## 2. What is there today, measured

| What | Count |
| --- | --- |
| Workflows under .github/workflows/ | 11 files, 1,769 lines, of which 472 are comment lines (board.yml gained `queue: max` and its prose in #70) |
| `uses:` lines, all by major tag | 30 (actions/checkout 15, anthropics/claude-code-action 6, actions/upload-artifact 6, actions/cache 2, actions/create-github-app-token 1) |
| anthropics/claude-code-action steps | 6: workers.yml 1, coordinator.yml 4, claude.yml 1; each with `claude_code_oauth_token`, `claude_args`, five with `allowed_bots: "github-actions,claude"`, five with a `prompt` |
| Copies of the same text | the usage recorder's three steps 6 times; "Point at the setup when the token is not there" 6; the CLAUDE_CROWD guard 12; the is_template guard 5; `gh workflow run` 5 |
| zizmor 1.30.1 findings | 31 high (30 unpinned-uses; 1 github-app at template-init.yml:58), 13 low (artipacked: a checkout that keeps its credential) |
| actionlint findings | 1 (protocol.yml:172, shellcheck SC2016, info) |
| The Claude credential | one repository secret, CLAUDE_CODE_OAUTH_TOKEN, read by three workflows; every Claude step is skipped with a pointer when it is empty (HAVE_TOKEN) |
| Who pushes for Claude | claude-code-action with `id-token: write`: it exchanges the job's OIDC token for the Claude GitHub App's installation token, whose pushes and pull requests start workflows, which a GITHUB_TOKEN push never does (github/docs, actions-do-not-trigger-workflows) |

The eleven, by what they are:

| Workflow | Lines | Runs Claude | Pushes | Trigger |
| --- | ---: | --- | --- | --- |
| board.yml | 188 | no | yes, the branch `board` | push, create, delete, pull_request, issues, every 6 hours, dispatch |
| ci.yml | 133 | no | no | pull_request, push (not claude/**), dispatch; the ruleset requires its job `check` |
| metrics.yml | 206 | no | yes, the branch `metrics` | push of the switch, daily, dispatch |
| protocol.yml | 229 | no | yes, `symphony-protocol/sync` | weekly, dispatch |
| tidy.yml | 54 | no | deletes branches | issues closed |
| queue.yml | 50 | no | no | issues opened, labeled, edited |
| add-worker.yml | 134 | no | yes, a pull request | issues opened, edited |
| template-init.yml | 99 | no | yes, with the App's token | the first push |
| workers.yml | 180 | one step per worker | Claude pushes, through the App's token | every 6 hours, an issue labelled, dispatch |
| coordinator.yml | 408 | four jobs | Claude pushes, through the App's token | epic labeled or closed, weekly, dispatch |
| claude.yml | 88 | one step | Claude pushes, through the App's token | @claude in a comment, review or issue |

## 3. Candidate A: a compiler of Symphony's own

What it is. A Python package `tools/workflows/` with no dependency beyond the standard library (the rule in .claude/rules/writing.md; the standard library has no YAML module, so the package emits YAML itself, in one style, which the eleven files do not yet share: 39 `|` block scalars beside 14 `>-`, one `>` and one `if: |`, cron strings double-quoted in three files and single-quoted in two, strings quoted with no YAML need beside plain ones for the same key; so PR 1c rewrites the eleven into the emitter's style first, a YAML-only diff with no behaviour change, after which byte-identity is by construction). One module per workflow holds that workflow as data: triggers, permissions, concurrency, jobs, steps, and the prose comments, each a Python string beside the step it explains, since the comments are a third of the files and the writing rule wants them. One module of fragments holds what is repeated today: the checkout, the token pointer, the crowd guard, the template guard, the claude-code-action step with its usage recorder and artifact, the round dispatch. `python3 -m tools.workflows write` writes the eleven files under .github/workflows/, each with a header saying it is generated from which module and not edited by hand; `python3 -m tools.workflows check` regenerates in memory and fails naming the file when a committed workflow differs from its source, and scripts/check.sh runs it beside `vendoring.py verify`. tests/test_workflows.py holds the emitter's own tests and one that checks every generated file is the one committed, so a copy made from the template runs it too (tests/test_filled_copy.py runs the copy's check).

The pins. PR 1a pins every `uses:` to a commit with the version as a trailing comment, by hand, before the compiler exists; Dependabot, already configured for github-actions weekly (.github/dependabot.yml), moves such pins and their comments. The compiler keeps no lock file of its own: before it writes, it reads the pins from the committed workflows, refuses to write when two files pin one action to two commits, and writes every occurrence with the one pin. A Dependabot pull request therefore passes `check` as long as it moves every occurrence of an action together, which is how Dependabot's github-actions updates behave for one directory; when it does not, `check` says which action disagrees and `write` settles it. `check` also requires every `uses:` to be a 40-character commit with a `# vX.Y.Z` comment, so a hand edit back to a tag fails; an action with one occurrence, or a workflow not yet generated, takes its pin from a `--pin name@sha` argument to `write`, recorded in the pull request, and a hand edit of such a pin from one commit to another is review's and Dependabot's to catch, not `check`'s. This avoids a second source of truth for the pins and lets GitHub's own tool keep them current, which is what gh-aw's committed actions-lock.json does with a tool of its own.

Credentials in checkouts. Only three jobs push with the checkout's own credential, in add-worker.yml:117, board.yml:155 and metrics.yml:194; template-init.yml:42 and protocol.yml:72 already set `persist-credentials: false` and push with an explicit header; claude-code-action in agent mode (workers.yml, coordinator.yml) swaps the checkout's credential for its own token before Claude runs (src/github/operations/git-config.ts:78-133), while in tag mode (claude.yml) it fetches the pull request's branch before it configures its own auth (src/entrypoints/tag/branch.ts:213-221), so that checkout keeps its credential in a private copy. The compiler's checkout fragment writes `persist-credentials: false` unless the job declares it pushes or fetches with the checkout's credential, and then writes `true` explicitly, which zizmor 1.30.1 does not flag (artipacked.rs:132-137); PR 1b does the same by hand, and the generated files then match it.

What it compiles: all eleven, including the Claude steps unchanged. What it cannot do: it is a compiler, not a runtime. It does not put the agent in a container behind a network allowlist, does not make the agent read-only with writes through audited safe outputs, does not run threat detection over the agent's output, does not cap AI credits. Those are gh-aw's run-time features for its agent job; Symphony's rails for the same risks are the protocol's (the push guard in the session, the claim lock on GitHub, the required check that runs from the default branch, the Phase 3 caps in code), and this plan leaves them where they are. If the owner wants gh-aw's sandbox for the three agentic workflows, that is Candidate B's pilot, on top of A, not instead of it.

The proof that nothing regresses. The first generated output of each workflow is the committed file byte for byte after PR 1a to 1c, with the header the only difference, shown by `diff` in the pull request and in its check. Behaviour is the YAML, so identical YAML is identical behaviour; the feature table in section 5 therefore reads "same" in every row for A, and it is listed anyway so that a later change to the source can be held to it. After the first compile the source is the truth and a change to a workflow is a change to its module, reviewed as the diff of the generated file.

What A pays off:

| Debt today | Where it goes |
| --- | --- |
| 30 actions pinned to a moving major tag | a commit pin each, moved by Dependabot (PR 1a) |
| 13 checkouts that keep a credential they never use | `persist-credentials: false`, or `true` written out where the job uses it (PR 1b) |
| 6 copies of the usage recorder, 6 of the token pointer, 12 of the crowd guard, 5 of the template guard, 5 of the round dispatch | one fragment each; a fix lands in six workflows from one edit |
| 472 lines of comments, many repeated across copies | one prose string per fragment, emitted beside each use |
| no check that a workflow matches what the documents say about it | the source module is the document; `check` holds the files to it |
| a copy's workflows diverge from the template's silently | a copy's `check` fails when its generated files differ from its source; the update route for copies, when it is built, moves source modules, not YAML |

What A does not pay off: gh-aw's scanners and the firewall; and the "no new dependencies" rule means actionlint and zizmor stay out of CI until an issue proposes them (section 10). Until then they run in the adversarial review before each pull request, as they did for this plan, and the compiler enforces by construction the two things they found: the pins and the credentials.

## 4. Candidate B: gh-aw with a self-defined engine

What it compiles. Three sources, `.github/workflows/symphony-worker.md`, `symphony-coordinator.md` and `symphony-claude.md`, with `.github/workflows/shared/claude-subscription.md` as the engine they import, to three locks of about 2,000 lines each. The deterministic parts of workers.yml (the registry, the dealer `tools/team.py next`, the matrix, the round loop) and of coordinator.yml (the route job, the clerk) stay plain, as does every one of the eight; gh-aw requires an engine and has no engine-less form (docs reference/engines.md:213), so under B those are Candidate A's or hand-written.

How the token gets in, and what the compile proves. The engine definition names the secret, and the compiled lock validates it, exports it to the agent step and runs `claude -p` (section 1). The first compile proved less than it seemed: its command line was `claude -p --output-format stream-json --verbose "$(cat prompt)"` and nothing else, the MCP gateway's configuration and the turn cap reached the step only as environment variables Claude Code never reads, and the safe outputs are MCP tools, so that agent could have pushed, commented or dispatched nothing. The second definition (Appendix A) adds `execution.mcp-config-flag: --mcp-config`, an `mcp.config-adapter` that calls gh-aw's own convert_gateway_config_claude.cjs, the one the built-in Claude engine uses, to write the gateway's servers in Claude's `mcpServers` shape, and the flags the built-in engine passes (pkg/workflow/claude_engine.go:247-275): `--no-chrome --strict-mcp-config --permission-mode dontAsk --allowed-tools <the template's list>,mcp__safeoutputs,mcp__github`. It compiled in strict mode, and the lock's agent step now runs that command with `--mcp-config` pointing at the written file (lock line 1014) and lists the `github` and `safeoutputs` servers in its manifest (line 2). gh-aw's firewall wraps the run (the sandbox launcher at line 1014, its configuration at line 995 with `isolation: true` and an api-proxy with `enableTokenSteering: true` and `maxAiCredits` from the frontmatter). Whether Claude Code's OAuth call to api.anthropic.com passes that proxy untouched, whether the proxy counts its tokens as AI credits and stops the run at the cap, whether the MCP servers answer the CLI through the gateway and the prompt reaches it as intended, and what the usage artifact then holds, none of that was run here; the cloud session cannot run Actions. Those are the first measurements of the pilot (section 7). Three compile-time facts beside: the `tools:` section is ignored for an engine that "doesn't support MCP tool allow-listing" (`GH_AW_INFO_SUPPORTS_TOOLS_ALLOWLIST: "false"`), so the tools list lives in the engine's `execution.args`, static for every workflow that imports it; the turn cap is enforced for a self-defined engine by the api-proxy's request cap, not by Claude Code's `--max-turns`, so a literal `max-turns: 60` in the frontmatter became `maxRuns: 60` in the first lock's proxy configuration, while `max-turns: ${{ inputs.max_turns }}` in the second landed only in GH_AW_MAX_TURNS, which the CLI does not read, and the proxy's cap fell to its default of 500; and `model:` is written by the compiler into the agent step's environment as ANTHROPIC_MODEL (behavior_defined_engine.go:643-654), a plain string in the schema (main_workflow_schema.json:15174), so whether a dispatch input may stand there, and so a worker's model still come from its file, is unmeasured.

What gh-aw says about it. gh-aw states that subscription OAuth authentication "is not supported by GitHub Agentic Workflows" (auth.mdx:217-219), for the product and not for one engine, and enforces it only where its code meets the built-in Claude engine; every vendored engine definition is called an unsupported sample (third-party-agent.md:8, 121), and the definition here is this repository's, with this repository as its only owner and support. Nothing in the compiler refuses it today. A later gh-aw release may: a compiler that refuses the secret's name in an engine definition would end the route at the next upgrade, which is the pilot's first risk and the reason the plain claude-code-action leg stays in git history. Anthropic's side: the CLI and the token are the same ones claude-code-action runs in Actions today, started by gh-aw's agent job instead of the action; the owner may want to confirm that this is within the subscription's terms before the pilot, which this plan cannot do.

Threat detection. gh-aw's detection job, which reads the agent's output for prompt injection and leaked secrets before the safe outputs are applied, "only runs on the built-in engines" (third-party-agent.md:151): with a self-defined engine it runs on Copilot by default, or on `claude` or `codex` if the definition says so, and the first sample lock installed the Copilot CLI in its detection job and listed COPILOT_GITHUB_TOKEN among its secrets (that lock's lines 1682-1684 and 2); in strict mode detection does not continue on error, so no safe output would have been applied without a Copilot credential. Each of those engines bills an organization Copilot plan or an API key, which the constraint forbids, so under B detection is turned off: the second sample sets `safe-outputs.threat-detection: false` (threat-detection.md:64), which strict mode accepted, and its lock has no detection job and `"threat_detection":{"mode":"disabled"}` in its manifest; `threat-detection: {engine: false}` (threat-detection.md:104) keeps the job without a model, and what it still checks is for the pilot to read. That removes one of the three things gh-aw's sandbox adds (the network allowlist and the read-only agent with safe outputs stay), which weighs on the second decision in section 10.

The protocol under B. Five rules shape the compiled worker, each the protocol's or gh-aw's.

1. The agent never pushes. gh-aw's agent job has read permissions and strict mode refuses more; every write is a safe output applied by a later job. So the parts of the worker routine that push or label (claim, announce, draft, finish) move into code that runs before and after the agent, in workers.yml.
2. The claim is code. After `tools/team.py next` deals the issue, a claim command pushes `claude/N` from the default branch with the claim file as its only commit, puts on the labels, posts the plan and opens the draft with "Closes #N", all with the job's GITHUB_TOKEN, as the claim skill's steps say. Where it lives: tools/team.py and tools/check_protocol.py are shims that hand their arguments to the vendored library (`python -m sdlc_protocol team`), which this repository never edits (docs/memory/protocol-changes-come-from-symphony-protocol.md), so the command is a new template tool, tools/claim.py, importing the vendored adapters and claims module, in PR B1's file list, until a library command `team claim` comes in a symphony-protocol release through the gate and the sync, which section 9's queue places after 0.5.0. This pays off on its own: an Actions worker can no longer claim wrongly or not at all, and a Claude run that dies leaves a well-formed claim that release handles.
3. The lock stays GitHub's. A second push of `claude/N` is refused because the ref exists; the loser's claim fails and the worker asks the dealer again next round. gh-aw's native work queue (`tools.work-queue`) stays off: the protocol has one claim authority, the branch (spec lines 883 and 1110-1111 in the comparison note), and gh-aw is the compiled run layer only. gh-aw's `create-pull-request` is not used anywhere under B: its handler salts the branch name (`claude/N-<hex>`) before any collision check, throws on an existing remote branch when `preserve-branch-name` is set, and force-deletes the ref under `recreate-ref` (actions/setup/js/create_pull_request.cjs:1548-1552, 693-700, 713-717), so it can neither claim nor land on a claim; every pull request under B is opened by the claim command and written to by `push-to-pull-request-branch`.
4. The work lands on the existing draft, and its push must start the required check. The lock is dispatched by workers.yml with inputs `worker`, `issue`, `branch`, `pull` and `max_turns`; `checkout: {ref: ${{ inputs.branch }}, fetch: ["main"], fetch-depth: 0}` compiled (the literal `main` names the default branch, which the template's workflows never do; whether `fetch` takes the default-branch expression or an input is unmeasured); the agent works, commits, and `push-to-pull-request-branch: {target: ${{ inputs.pull }}, signed-commits: false, fallback-as-pull-request: false}` pushes to the draft's head. "main moved" is answered by merging the default branch in, never by a lease, since the push is append-only and the unsigned path keeps the merge commit. Then the fact the first review of this plan established: a push or a pull request made with github.token starts no workflow run (github/docs, actions-do-not-trigger-workflows; gh-aw's own triggering-ci.mdx:10-12 says it of both safe outputs), and ci.yml runs `check` on a claim branch only through pull_request events (ci.yml:71-74), so a safe-output push on github.token leaves a head with no check run, which can never go green. Today's worker has no such problem because the Claude GitHub App's token pushes. Under B there are three ways to get the check: `safe-outputs.github-app` with SymphonyBoard's SDLC_APP_ID and SDLC_APP_PRIVATE_KEY (auth.mdx:521-532), which holds only where the key is, the owner's organization; gh-aw's `github-token-for-extra-empty-commit` with a personal access token, which is a stored credential and pushes its empty commit only when exactly one new commit was pushed (actions/setup/js/extra_empty_commit.cjs:84-85), so it fails a worker that commits in steps or merges main in, and is not used; or the route protocol.yml already takes for its own GITHUB_TOKEN-made pull request (protocol.yml:213): the finish job runs `gh workflow run ci.yml --ref claude/N`, a workflow_dispatch the default token may make, whose check run lands on the branch's head where the required check looks (ci.yml:28-32). The third is the default, since it needs no credential and holds in every copy. It needs one template change: the library's protocol check reads only the pull request in the event file and passes any other run (tools/sdlc_protocol/cli.py:149-170; ci.yml:113-114 runs it on pull_request only), so on a dispatched run ci.yml writes a synthetic event file from `gh pr view --json` for the branch's open pull request and gives the crowd guard its pull request inputs (ci.yml:103-105) the same way, a change to ci.yml and tools/check_protocol.py in PR B2, until a library `check --pull <number>` reading the API comes by release. The App route is a measured option where the key is.
5. The finish is code, by the protocol's own words for a worker that cannot mark ready. The agent keeps the claim file, since the protocol check fails a draft without it (tools/sdlc_protocol/protocol_check.py:70-75), pushes the finished work with `bash scripts/check.sh` passing, and posts "finished; ready to mark" through `add-comment`, whose `target` is the `pull` input, since a dispatched run has no triggering item and the handler refuses the default (actions/setup/js/add_comment.cjs:509, 710); that comment counts only from the pull request's author and only as the author's latest comment (claims.py:292-301), and both the draft, opened by rule 2 with github.token, and the comment, applied by the safe_outputs job with github.token, are github-actions[bot], one identity. That identity has a cost today's worker does not pay: the board's own comments on the pull request, "main moved", the idle notice after a day and the overlap notices, are github-actions[bot] too (adapters/github.py:443-449, 530-535, 684; board.py:513), so any of them after the finished comment reads as the author's latest and unmakes the signal, and the coordinator releases the draft after 24 hours without a commit. So the finish never waits: the agent asks for it in the same run, through `dispatch-workflow` into workers.yml's `finish` job (the target must exist and is named without its extension), which commits the claim file's deletion and pushes it, marks the pull request ready at once (the ready_for_review event starts no run on github.token, so the order is push, mark ready, then dispatch ci.yml on the branch and read the check), labels the issue in-review, dispatches board.yml once so the board sees the work, and runs the next round; a refusal goes on the issue, never on the pull request, and leaves no draft behind. Where the App's key is, the App's identity for the draft and the comment avoids the collision; a library rule that reads the author's latest comment starting with the signal would end it everywhere, and is a symphony-protocol release for the owner's queue.

The rest of B's shape, each item compiled in the second sample unless it says otherwise: a top-level `concurrency: {group: gh-aw-${{ github.workflow }}-${{ inputs.worker }}, queue: max}` beside the engine-level group, since without it the compiler emits one top-level group for the whole workflow and two workers' runs queue one behind the other before any job starts (the first lock's lines 90-92; pkg/workflow/concurrency.go:15-57), and `engine.concurrency` reaches the agent job alone; `job-discriminator: ${{ inputs.worker }}`, not yet set, since the conclusion job's group is shared by every dispatch and strict mode warns of it; `max-ai-credits` raised from the default 1,000 per run, since the api-proxy stops the run there whatever the token (frontmatter.md:489-504), and `max-daily-ai-credits` is bypassed by a workflow_dispatch run (rate-limiting-controls.md:144), which every dealt worker run is, so the dealer's runs-a-day rail in code stays the real cap; `noop: {report-as-issue: false}`, since a bare `noop:` generates a maintenance workflow; `protected-files: {policy: request-review, exclude: [CLAUDE.md, .claude/]}`, since gh-aw protects CLAUDE.md, README.md, CODEOWNERS and the top-level dot folders by default and its default policy asks for review on the draft rather than refusing the push, while Symphony's workers edit CLAUDE.md's checkpoint block and .claude/ by design; the usage reader in tools/usage.py for gh-aw's artifact `usage`, since the Symphony-Usage trailer survives only the unsigned push path; one board.yml dispatch from the claim command and one from the finish job, since no write a B run makes on github.token starts the board, not only the push (board.yml takes workflow_dispatch); for the coordinator, one source with an `event` input, the plan written as a fenced JSON block in a comment that the clerk validates in place of `--json-schema`, which gh-aw has no equivalent of; for the mention, gh-aw's `slash_command: claude`, which fires on `/claude` as the first word (command-triggers.md:55), or the raw `issue_comment` trigger with an `if:` on the body, which the schema accepts and the pilot measures.

## 5. Feature by feature, nothing lost

The subscription-token worker is the first row. "same" under A means the generated YAML is the committed YAML. Under B, "changed" is a different mechanism with the same outcome, "lost" a regression, "unmeasured" a thing the compile cannot show.

| Feature today | Where | A | B |
| --- | --- | --- | --- |
| A worker in Actions runs Claude on CLAUDE_CODE_OAUTH_TOKEN and no other Claude credential | workers.yml:134 | same | kept, through the self-defined engine; compiles with the MCP wiring the safe outputs need; run time unmeasured |
| No Copilot plan and no API key is billed by any run | every workflow | same | kept only with gh-aw's threat detection off or without a model, since detection runs on the built-in engines alone |
| No run and a pointer when the secret is empty | HAVE_TOKEN, 6 steps | same | changed: the dispatcher keeps the check; gh-aw's own validate step would fail the run |
| Crowd mode never runs Claude; the template itself never runs workers | CLAUDE_CROWD, is_template | same | changed: the dispatcher's conditions, before any dispatch |
| Claude's push and pull request start the required check and the board | id-token: write, the Claude GitHub App's token | same | lost on github.token; the check recovered by the finish job dispatching ci.yml on the branch (secret-free), or by the App key where it is; the board by one board.yml dispatch from the claim and one from the finish, since no B write starts it |
| The claim is the first push of `claude/N`, refused for the second worker | the routine, step 2 | same | changed: `team.py claim` pushes before the run; the same lock |
| The claim file stays while the draft is a draft and is gone when it is ready | protocol_check.py:70-75 | same | changed: the agent keeps it; the finish job deletes it and marks ready |
| "main moved" answered by rebase and `--force-with-lease` on the own branch | the routine | same | changed: merge the default branch in, append-only push, no lease |
| The worker marks ready and labels in-review | the routine, with gh | same | changed: the finish job, after "finished; ready to mark" |
| One more round while the worker has work | `gh workflow run workers.yml` | same | changed: the finish job dispatches |
| Model, max_turns and rounds from the worker's file | workers.yml:121 | same | rounds kept in the dispatcher; max-turns kept only as a literal per source, enforced by gh-aw's api-proxy as its request cap (the first lock: maxRuns 60), not as a dispatch input (the second: the input lands in a variable the CLI does not read and the cap falls to 500); model unmeasured as an input; if either is refused, one source file per worker setting, or one setting for all workers in Actions |
| `--allowedTools` from the repository variable CLAUDE_ALLOWED_TOOLS, with the default list | 6 steps | same | changed: static in the engine definition's args (compiled); the variable's override lost |
| Runs started by the bots github-actions and claude are accepted | allowed_bots | same | changed: `bots:` in the frontmatter |
| What the run spent, as an artifact metrics.yml reads, and the Symphony-Usage trailer on commits | usage.py, 6 copies | same | changed: gh-aw's artifact `usage` and a reader for it; the trailer kept on the unsigned push path |
| One worker runs one issue at a time; workers run in parallel | concurrency worker-<name> | same | changed: engine concurrency group per worker with queue: max, written explicitly |
| A worker run is one job, 90 minutes | workers.yml | same | changed: four jobs in a chain with detection off (activation, agent, safe_outputs, conclusion), the agent's timeout from the frontmatter |
| The coordinator's plan is structured output under a JSON schema | coordinator.yml:148 | same | changed: a fenced block in a comment, validated by the clerk |
| Four duties behind one route job | coordinator.yml | same | changed: one source with an event input, dispatched by the route job |
| Integrate opens a fix pull request | the Claude App's token | same | changed: lands as the worker lands, a claim by code, the agent's push to that draft, the finish job marking ready and arming auto-merge with `gh pr merge --auto --merge` as coordinator.yml:331 does today; never gh-aw's create-pull-request, which salts or refuses an existing branch |
| @claude anywhere in a comment, review or issue | claude.yml | same | changed: `/claude` as the first word, or the raw trigger with an `if:` (unmeasured) |
| Claude's writes appear as the Claude GitHub App | id-token: write | same | changed: github-actions[bot] for every write; the draft and the finished comment share that identity, as the release rule needs, and so do the board's own comments on the pull request, which is why the finish never waits (rule 5) |
| Claude reads CLAUDE.md, the rules and the memory, and may edit them | the checkout | same | kept (`manifest: {files: [CLAUDE.md], path-prefixes: [.claude/]}`), with CLAUDE.md and .claude/ taken out of gh-aw's protected files (compiled) |
| Claude can `git fetch` from a private copy | the action's own token, set after the checkout (agent mode), or the checkout's credential (claude.yml's tag mode) | same | lost in the agent job (persist-credentials false); `checkout.fetch` prefetches the default branch |
| Pushes by the eight deterministic workflows | GITHUB_TOKEN, or the App in template-init | same | not compiled: unchanged |
| The protocol's rules, the library, the release gate | tools/sdlc_protocol | same | same: no rule changes; what the Actions worker does differently is a sentence in WORKERS.md about who pushes |

A: every row same. B: one row kept only with a gh-aw feature turned off (detection), two rows lost outright (the check on the pushed head, recovered by code; the fetch in a private copy), fourteen changed, the turn cap kept only as a literal, and three unmeasured beyond the engine's run time (the model as an input, the tools override, the raw mention trigger). The constraint is "dont regress any features": A meets it by identity; B meets it only with the recoveries written and measured, and may lose the per-worker model and turn cap unless one source file is kept per worker.

## 6. Candidate A's pull requests, in order

Every pull request: one change, from the thread's own branch, `bash scripts/check.sh` first, an adversarial review before it, merged once green on the owner's standing permission. Each migrated workflow keeps its path and its name; GitHub reads the generated file exactly as it reads the hand-written one.

### PR 1a, now: pin the actions

- Changes: every `uses:` in the eleven to a commit with the version as a trailing comment; .github/dependabot.yml's own comment, .claude/rules/writing.md:6 and docs/setup/github.md:42 reworded from "pinned to a major tag" to "pinned to a commit, the version beside it, which Dependabot moves".
- Deletes: nothing.
- Proof: zizmor's 30 unpinned-uses findings to 0, actionlint 0, `bash scripts/check.sh`, tests/test_filled_copy.py.
- Goes before F4's template change (#23's workers.yml part): a pin on a `uses:` line is a trivial rebase for the later one.

### PR 1b, now: credentials in checkouts, the App token's permissions

- Changes: `persist-credentials: false` on every checkout whose job neither pushes nor fetches with it (ci, tidy, queue, workers, coordinator, and the checkouts in add-worker, board and metrics that do not push); `persist-credentials: true` written out on the three that push with it (add-worker.yml:117, board.yml:155, metrics.yml:194) and on claude.yml's, whose tag mode fetches the pull request's branch before the action sets its own token; template-init.yml and protocol.yml already false. On template-init.yml's create-github-app-token step, `permission-contents: write` and `permission-issues: write`, the two template_init.py uses (its push, and its labels and setup issue), which is what zizmor's github-app finding asks for; not `repositories:`, since v1 of the action already scopes the token to the current repository and passes a `repositories` value raw as a repository name, so `OWNER/NAME` would fail the request and the step's `continue-on-error` would fall back to GITHUB_TOKEN silently, losing the push that starts the first Board and Checks (template-init.yml:58-63, 76-83).
- Proof: zizmor's 13 artipacked and 1 github-app findings to 0 (an explicit `true` is not flagged); one run of a copy made from the template on the test repository, whose init step logs "creating token for the current repository" and whose first push lands with the App; the filled-copy tests.
- Reviewed for one thing: a job that pushes or fetches with a credential it no longer has.

### PR 1c, now: one YAML style

- Changes: the eleven files rewritten into the emitter's style (block scalars, quoting, flow sequences, cron quotes), nothing else; reviewed as a YAML-only diff, with a script in the review that confirms each file parses to the same structure as before (the review's own tooling, not a dependency of the repository).
- Proof: check.sh and the filled-copy tests; the board's and metrics' next runs push as before.
- Why its own pull request: PR 2's proof is "header only", which holds only once the committed files are in the style the emitter writes.

### PR 2, now: the compiler, with tidy.yml and queue.yml generated

- Adds: tools/workflows/__init__.py and __main__.py (the emitter, `write` and `check`), tools/workflows/fragments.py, tools/workflows/tidy.py and queue.py; tests/test_workflows.py; one line in scripts/check.sh after `vendoring.py verify`; a header on the two generated files; docs/memory/workflows-are-generated.md with its index line (the remember skill: one file, one line, the same pull request); a sentence in .claude/rules/writing.md: a workflow is changed in its module under tools/workflows/, never in .github/workflows/.
- Changes: tidy.yml and queue.yml are regenerated byte for byte but for the header.
- Deletes: nothing.
- Proof: `diff` of each generated file against main is the header only; `python3 -m tools.workflows check` passes and, with one byte changed in a generated file, fails naming it (a test); check.sh; the filled-copy tests.
- Why these two: 104 lines between them, no Claude step, no push, so the emitter is proved on the smallest shapes first.

### PR 3: board.yml, ci.yml and metrics.yml

- The three the protocol runs on and the board workflow that rewrites STATE.md. ci.yml's job `check` keeps its name and its own file, since the ruleset requires the context `check` (docs/setup/ruleset-main.json:31). Proof as PR 2, generated from main as it is after #70 (board.yml's `queue: max` and prose, tools/board.py). Lands when no open pull request touches them; none does today.

### PR 4: protocol.yml, add-worker.yml and template-init.yml

- The three that open pull requests or run at init. template_init.py:15-17 says the workflows carry no placeholder and GITHUB_TOKEN may not write them, which stays true: the compile happens in a session or a pull request, never in Actions, and CI only checks. Proof as PR 2.

### PR 5: claude.yml

- The first Claude step through the fragment: `claude_step(token_input, args, prompt)` emitting the pointer, the recorder copy, the action step with `claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}`, `allowed_bots`, `claude_args`, the two usage steps. Proof as PR 2, and the generated action step compared field by field with the hand-written one in the review.

### PR 6, after F4's template change lands: workers.yml

- The matrix, the dealer and the round loop as data; the Claude leg through the fragment. Waits for #23's workers.yml change so that it generates what F4 made, not what F4 replaces. Proof as PR 2; canary C1 unaffected, since the YAML is the same.

### PR 7: coordinator.yml

- Four Claude jobs through the fragment with the plan job's `--json-schema` argument kept. The last hand-written workflow goes with it. Proof as PR 2. After it, `python3 -m tools.workflows check` covers all eleven and no file under .github/workflows/ is edited by hand again.

### Afterwards

- symphony-start's adopt.py copies the generated files as it copies the hand-written ones today, since they are the same paths. A protocol-only adoption copies three of them (board, tidy, metrics) and no tools/workflows/ or check.sh, so the header names the template, not a local path: "Generated in OpenSpineConsortium/symphony-template by tools/workflows; a copy without that folder edits this file directly". Whether a copy later gets the compiler is the runtime design's call.
- The runtime design (docs/checkpoints/2026-10-14/handoff-page/DESIGN-runtime.md) and this plan do not compete: a thin caller file is a generated file like any other, and the compiler is what writes the thin callers when the runtime exists.
- An update route for copies, when one is built, moves tools/workflows/ and regenerates, so a copy's local change to a module shows as a merge conflict in prose rather than in YAML.

## 7. Candidate B's pilot, if the owner wants it

After 0.5.0 is released and synced, on symphony-protocol-canary, with gh-aw installed at a pinned version (`gh extension install github/gh-aw@<version>`), and only on the owner's yes to section 10's second decision. No pull request to this repository before step 0's findings are written.

Step 0, measure before writing. Compile the three sources with the engine definition of Appendix A; run the worker once end to end on a dealt issue: the claim by code, the dispatch with inputs, the checkout of the claim branch, Claude's OAuth call through gh-aw's api-proxy (the first thing that can fail), the MCP servers answering the CLI through the gateway (a safe-output tool call recorded in the agent's log), the turn cap as the proxy's request cap, the tools list from the engine's args, a push onto `claude/N` through the safe output, a merge of the default branch pushed unsigned, the finished comment on the draft as github-actions[bot], the finish job's dispatch of ci.yml and the check run appearing on the pushed head, the finish job marking ready in the same run, a board.yml dispatch and the board showing the work. Record per run: whether the api-proxy counted AI credits against the subscription run and at what cap it stopped; Actions minutes across the four jobs; the GITHUB_TOKEN requests the activation, agent and safe_outputs jobs made (the rate-limit header before and after), with the two dispatches; wall time; what the `usage` artifact holds. Then let a board run post "main moved" or its idle notice on a finished draft left on purpose, and read that the release rule takes it, to fix the collision's cost in numbers. Try the App for safe outputs once and read whether its push starts a board run. Try `gh aw compile` in a plain CI job against a committed lock for the lock-drift check. Try the raw `issue_comment` trigger with an `if:` for @claude, `model:` and `checkout.fetch` with an input, and `job-discriminator` on the worker.

Go or no go. The pilot goes on only if Claude ran to completion on the token through the proxy, the check run appeared on the pushed head without a stored credential, and the per-run request count leaves the repository under GITHUB_TOKEN's 1,000 an hour at the planned number of workers. Otherwise the findings go into a dated checkpoint page and Candidate A stands alone.

If it goes: PR B1, claim by code in workers.yml, as tools/claim.py importing the vendored adapters (worth doing under A too, since it fixes the Actions worker's claim whatever runs Claude), with its scripted policy in the harness; PR B2, the worker source, its lock, the engine definition, the `locks` job in ci.yml installing gh-aw at a pinned version (setup-cli's `version:`; aw.json has no version field) and failing when a lock differs from its source or names another version, .github/aw/actions-lock.json committed, the finish job, ci.yml's dispatched-run event file and tools/check_protocol.py reading it, the usage reader, the variable SYMPHONY_AGENTIC read by the dealer as the kill switch; PR B3, the coordinator source and the clerk's plan reader; PR B4, the mention. Each proved by the harness (a scripted actions_worker policy whose claim is the code's verbs; the two-worker search with the gh-aw run shape: claim by code at one hour, the agent's push as a separate verb later, a run that dies between them, no lease; every mutant still caught) and on the canary (one gh-aw worker end to end, then a backdated commit and the release). Under B workers.yml, coordinator.yml and claude.yml are still generated by A's compiler; what B adds is three sources, three locks and the engine definition beside them.

## 8. What breaks first at scale, and how each step moves it

The comparison thread's scoring (symphony-vs-gh-aw.md, section 12): Symphony's first wall is GITHUB_TOKEN's 1,000 requests an hour per repository, shared by the board, tidy, metrics and the clerk, with the board running on nearly every event and keeping no budget; then the board group's 100 queued runs; then one subscription token's five-hour window shared by every Actions worker. gh-aw's first wall is its own churn.

| Break point | Today | After A (PR 1a to 7) | After B's pilot | Hedge |
| --- | --- | --- | --- | --- |
| GITHUB_TOKEN, 1,000 requests an hour per repository | the first wall; the board has no budget | unchanged: the same YAML makes the same calls | nearer: each worker run adds gh-aw's activation and safe-output calls and the agent's reads through the GitHub MCP server, all on github.token (step 0 counts them), plus the finish job's ci.yml dispatch and the two board.yml dispatches | a request budget in the library's board.py, the first 0.6.0 item; the protocol is per repository, so scale is horizontal |
| The board's group, 100 queued runs | `queue: max` since #70 | unchanged | unchanged in kind: a github.token write fires no board run, and B adds two dispatched board runs per worker run | unchanged |
| One subscription token, one five-hour window for every worker in Actions | the third wall | unchanged, by the constraint | unchanged: the same token; gh-aw adds its own per-run credit cap and the api-proxy's `maxRuns: 60` on top | the dealer's runs-a-day rail (Phase 3), in code, before any dispatch; one worker account whose window nobody else spends |
| Concurrent jobs: 20 Free, 40 Pro, 60 Team, 500 Enterprise | one job per worker run | unchanged | four jobs per worker run in a chain, one at a time | Team or Enterprise for a large test |
| Actions minutes: unlimited on a public repository | about a minute of overhead per run | unchanged | three more job starts and six container pulls per run | the scale test runs on a public repository |
| Compiler churn | none: the YAML is hand-written | none: the compiler is this repository's, changed by its pull requests, with no upstream to move it | gh-aw's weekly releases (five in the week of 2026-10-12), every upgrade regenerating every lock, and .github/aw/compat.json able to refuse a compiled version remotely (releases.md:78-83) | pin the CLI version in the locks job's install step and assert the lock's header matches it (aw.json has no version field); commit actions-lock.json; upgrades as pull requests through the check; SYMPHONY_AGENTIC=off; the plain leg stays in git history |
| Secondary limits on content creation, 80 a minute and 500 an hour per account | the board's comments | unchanged | gh-aw's safe outputs add theirs, paced (rate-limiting-controls.md:85-95) | one bot account as today |

In one sentence: A moves no wall and adds none, since it changes the representation and not the behaviour; B leaves the token wall where it is, brings the request wall nearer and adds gh-aw's churn as a wall of its own, with a pin, a drift check and a switch as hedges; the request wall is the library's to move, and that fix is independent of both.

## 9. Ordering against the 0.5.0 queue

The queue (docs/checkpoints/2026-10-14/HANDOFF.md:17): land the open pull requests (template #70; protocol #21, #23, #24), then F4, F14, F9, F13, F2, F8, the stuck claim, the last raising the version to 0.5.0, which the owner approves.

Candidate A runs beside it, not after it: PR 1a to 1c and PR 2 to 5 touch files the fixes do not (#70 and #74 are merged and no template pull request is open; the protocol fixes touch the library, which the compiler never reads), and the harness proves nothing about A because A changes no behaviour for it to prove. PR 6 waits for F4's template change to workers.yml; PR 7 goes when no open pull request touches coordinator.yml. Candidate B's step 0 waits for 0.5.0 released and synced, for the three reasons the first version gave: the harness and the canary it is proved with are what the fixes change, F4 reshapes the dealing B's claim-by-code hangs on, and the release is the owner's click, which the plan should not queue behind itself.

## 10. The owner's decisions

Nothing to click for Candidate A: it needs no setting, no secret and no permission; CLAUDE_CODE_OAUTH_TOKEN stays where it is and keeps being read by the same six steps.

1. Candidate A as the route for all eleven: yes or no, in the thread. On yes, PR 1a to 1c and PR 2 are the next work.
2. gh-aw as a dependency for the three agentic workflows, through the pilot of section 7: yes, no, or later. Yes means a weekly-moving compiler, a 2,000-line lock per workflow in the repository, a vendor that can refuse a compiled version remotely, an experimental route for the token, gh-aw's threat detection off, and the changes in section 5's B column; no means Candidate A alone, which this plan recommends as sufficient. Nothing to click either way until step 0, which runs on the canary with the token already there.
3. actionlint and zizmor in CI: the writing rule says a new dependency is an issue first. Recommended for now: no issue; they run in the adversarial review before each pull request, and the compiler enforces what they found. If the owner wants them in CI, a session opens the issue on the owner's word.
4. Two editorial changes ride in PR 1a and 1c and are named here so that nothing is decided by default: the writing rule's and docs/setup/github.md's words move from "pinned to a major tag" to "pinned to a commit", and the eleven files take one YAML style. Say no to either and the plan keeps tags, or proves PR 2 by a structural comparison in review instead of by `diff`.

Marked as the owner's and untouched by this plan: the release gate and its approval, the secret CLAUDE_CODE_OAUTH_TOKEN, every repository and organization setting.

## 11. What the coordinator asked to be explicit about

- One claim authority per issue: the branch `claude/N`, refused by GitHub for the second pusher. Under A nothing changes. Under B gh-aw is the compiled run layer only; a compiled worker still claims by that push, made by code before the run, and `tools.work-queue` stays off.
- Where the dispatch credential lives: today workers.yml's own GITHUB_TOKEN, with `actions: write`, dispatches the next round (workers.yml:162-179). Under A, the same. Under B, the same token dispatches the lock with its inputs, and the lock's safe_outputs job dispatches the finish job back with its own github.token (`dispatch-workflow`, actions write granted to that job); the claim command and the finish job dispatch board.yml and ci.yml with the same job token. No credential is stored for dispatching and no job holds more than it has today.
- gh-aw's task graph (issue and pull request gate nodes, cycle checks) is read as input to F13 and the open U3 and U4 questions on the protocol's dependencies between tasks, not adopted: Symphony's issues, labels and refs are the state.

## 12. What this plan does not do

- It does not move any Claude run off CLAUDE_CODE_OAUTH_TOKEN, and it adds no Claude credential, API key or Copilot billing anywhere.
- It does not adopt gh-aw's native work queue, nor Copilot dynamic workflows.
- It does not change the protocol library's rules, the release gate or its approval.
- It does not change how a person's sessions or routines work.
- It does not put the eight deterministic workflows under gh-aw, which cannot take them.

## Appendix A: the self-defined engine and the worker, as compiled

Compiled on 2026-10-14 with gh-aw d06e087, `gh aw compile --validate --strict --approve` (the `--approve` for the secret new to the repository): 1 succeeded, 2 warnings (the experimental engine; no `concurrency.job-discriminator`). This is the second definition; the first, which lacked the `mcp-config-flag`, the `mcp.config-adapter` and the tools and permission flags, compiled too but gave the CLI no way to reach the safe outputs (section 4).

`.github/workflows/shared/claude-subscription.md`:

```yaml
engine:
  id: claude-subscription
  display-name: Claude Code on a subscription token
  description: Claude Code CLI authenticated by CLAUDE_CODE_OAUTH_TOKEN from claude setup-token, as anthropics/claude-code-action does
  detection-engine: copilot
  experimental: true
  version: "2.1.296"
  provider: {name: anthropic}
  auth:
    - role: oauth-token
      secret: CLAUDE_CODE_OAUTH_TOKEN
  behaviors:
    supported-env-var-keys: [CLAUDE_CODE_OAUTH_TOKEN]
    capabilities: {max-turns: true, bash-command-allowlist: true}
    manifest: {files: [CLAUDE.md], path-prefixes: [.claude/]}
    network:
      defaults: [host.docker.internal, github.com, api.github.com, raw.githubusercontent.com]
      provider-domains: {anthropic: api.anthropic.com}
    installation:
      package-manager: npm
      package-name: "@anthropic-ai/claude-code"
      version: "2.1.296"
      step-name: Install Claude Code
      binary-name: claude
      include-node-setup: true
      verify-command: claude --version
      verify-step-name: Verify Claude Code
      docs-url: https://code.claude.com/docs
    execution:
      command-name: claude
      args:
        - -p
        - --no-chrome
        - --strict-mcp-config
        - --permission-mode
        - dontAsk
        - --allowed-tools
        - "Read,Write,Edit,MultiEdit,Glob,Grep,Bash(git:*),Bash(gh:*),Bash(bash scripts/check.sh),Bash(python3:*),mcp__safeoutputs,mcp__github"
        - --output-format
        - stream-json
        - --verbose
      step-name: Run Claude Code on the subscription token
      mcp-config-flag: --mcp-config
      model-env-var: ANTHROPIC_MODEL
      mcp-config-env-var: GH_AW_MCP_CONFIG
      write-timestamp: true
    mcp:
      config-adapter: |
        require("./convert_gateway_config_claude.cjs").main();
    log-parser: |
      function parseLog(logContent) {
        return require("./parse_claude_log.cjs").parseClaudeLog(logContent);
      }
```

Notes. `detection-engine: copilot` is required by the schema and names a built-in engine, since detection runs only on those (third-party-agent.md:151); the worker turns detection off, so the line has no effect there, and a workflow that left detection on would bill Copilot. The config adapter is gh-aw's own converter for its built-in Claude engine, so the file it writes is the one that engine reads; the lock runs it as a step named "Write Claude Code on a subscription token MCP config adapter script" and passes the file with `--mcp-config` (lock lines 796-800, 1014). The tools list is static here; a per-repository override would need a second definition.

`.github/workflows/symphony-worker.md`, the frontmatter:

```yaml
on:
  workflow_dispatch:
    inputs:
      worker: {description: "The worker's name", required: true, type: string}
      issue: {description: "The issue", required: true, type: string}
      branch: {description: "The claim branch", required: true, type: string}
      pull: {description: "The draft's number", required: true, type: string}
      max_turns: {description: "The worker's turn cap", required: false, type: string, default: "60"}
  roles: [admin, maintainer, write]
permissions:
  contents: read
  issues: read
  pull-requests: read
engine:
  id: claude-subscription
  concurrency:
    group: "gh-aw-claude-${{ github.workflow }}-${{ inputs.worker }}"
    queue: max
imports:
  - shared/claude-subscription.md
concurrency:
  group: "gh-aw-${{ github.workflow }}-${{ inputs.worker }}"
  queue: max
network:
  allowed: [defaults, python, api.anthropic.com]
checkout:
  ref: ${{ inputs.branch }}
  fetch: ["main"]
  fetch-depth: 0
timeout-minutes: 90
max-turns: ${{ inputs.max_turns }}
max-ai-credits: 2000
safe-outputs:
  threat-detection: false
  push-to-pull-request-branch:
    target: ${{ inputs.pull }}
    max: 3
    signed-commits: false
    fallback-as-pull-request: false
    protected-files:
      policy: request-review
      exclude: [CLAUDE.md, .claude/]
  add-comment:
    target: ${{ inputs.pull }}
    max: 2
  noop:
    report-as-issue: false
```

What the lock shows: 1,689 lines; four jobs, activation, agent, safe_outputs and conclusion, with no pre_activation and no detection job; `"threat_detection":{"mode":"disabled"}` and the MCP servers `github` and `safeoutputs` in the manifest (line 2); the top-level concurrency group per worker with `queue: max` (lines 95-97); `GH_AW_INPUT_PULL: ${{ inputs.pull }}` as the comment's and the push's target (lines 625-626, 1656); `GH_AW_MAX_TURNS: ${{ inputs.max_turns }}` as an environment variable only, with the api-proxy's `maxRuns` at its default 500 (lines 995, 1019), where the first lock's literal `max-turns: 60` had become `maxRuns: 60`. COPILOT_GITHUB_TOKEN still appears in the manifest and in the activation job's "Check for OAuth tokens" step (lines 2, 250), a check that passes with the secret absent; no job uses it.

Still to add for the pilot: `concurrency.job-discriminator: ${{ inputs.worker }}` for the conclusion job's group; `dispatch-workflow: {workflows: [workers]}` once workers.yml has its finish job; `bots: ["github-actions[bot]"]` on any label trigger; a literal `max-turns` per source, or the measurement that the proxy takes the input; `checkout.fetch` with the default branch by input or expression, if the schema takes it.

## Appendix B: what the first review found and how this version answers it

The first version was reviewed from four lenses by eighteen agents; three lenses finished with 29 findings and two verifier verdicts before a session limit stopped the rest. What survived and shaped the second version: the required check never runs on a head pushed with github.token (confirmed; section 4 rule 4 and section 5); the claim file must stay while the pull request is a draft and the finish must push the deletion and mark ready at once (confirmed in part; rule 5); the draft and the finished comment must be one identity (rule 5); the push guard sees no push a workflow step makes, so B's claim by code is held by GitHub's refusal and the protocol check, not the hook; `job-discriminator` has no effect beside an explicit engine concurrency group, and `queue: max` must be written; the daily credit cap never applies to a dispatched run, the per-run cap does; the usage artifact is named `usage`; a lock's model cost table is an estimate, not a bill; the App's installation token has its own per-installation bucket; a GITHUB_TOKEN label fires no worker trigger. Everything the first version said about Copilot billing is withdrawn.

The second version was reviewed from three lenses by twelve agents, 23 findings, of which seven were verified against the sources and shaped this version: the first compiled engine gave the CLI no MCP configuration, tools list or turn cap, so its agent could have called no safe output (confirmed; the engine was rewritten and recompiled, section 4 and Appendix A); gh-aw's top-level concurrency group would have serialized every worker (confirmed; a per-worker group, compiled); the board's own github-actions[bot] comments on a pull request unmake the finished signal (confirmed; rule 5 and the step 0 measurement); integrate cannot use gh-aw's create-pull-request on a claim branch (confirmed in part; it lands as the worker does); PR 1's `repositories:` on the App token step would have broken template-init's first push, and the right change is the permission inputs (confirmed; PR 1b); the eleven files do not share one YAML style, so byte-identity needs a normalising step first (confirmed; PR 1c); only three jobs push with the checkout's credential, and claude-code-action's two modes differ (confirmed in part; PR 1b and section 3). Also taken: add-comment needs the `pull` input as its target on a dispatched run (compiled), detection runs only on built-in engines (compiled off), the claim command and the dispatched check are template tools until a library release carries them, aw.json pins no version, .claude/ is a protected file too, the dispatched worker lock had five jobs and now has four, #70 changed board.yml and not workers.yml and is merged, a protocol-only adoption copies three workflows, and the one-line answer now says what "compiled" means.

## Appendix C: sources read

- symphony-template cb83274: .github/workflows/*.yml, .github/dependabot.yml, scripts/check.sh, tools/ (template_init.py, usage.py, team.py, check_protocol.py, workers.py, sdlc_protocol/{vendoring,protocol_check,team,claims,cli,board}.py, sdlc_protocol/adapters/github.py), tests/test_filled_copy.py, docs/agents/{PROTOCOL,WORKERS}.md, docs/agents/routines/worker.md, docs/setup/{claude-action,github}.md, docs/setup/ruleset-main.json, docs/memory/protocol-changes-come-from-symphony-protocol.md, docs/checkpoints/2026-10-14/{HANDOFF,protocol-fixes}.md and handoff-page/DESIGN-runtime.md.
- symphony-protocol 3e98b88 and its branches for #21, #23, #24: validation/{DESIGN,GUARANTEES,README}.md, validation/known.json, scripts/canary.py.
- github/gh-aw d06e087: docs reference/{auth.mdx,engines,third-party-agent,threat-detection,concurrency,rate-limiting-controls,cost-management,safe-outputs,safe-outputs-pull-requests,steps-jobs,command-triggers,releases,frontmatter,frontmatter-full,triggering-ci.mdx,checkout,billing}.md; .github/workflows/shared/kiro.md; pkg/workflow/{engine_definition,behavior_defined_engine,claude_engine,engine_helpers,concurrency}.go; pkg/cli/engine_secrets.go; pkg/parser/schemas/main_workflow_schema.json; actions/setup/js/{create_pull_request,check_permissions,extra_empty_commit,add_comment,convert_gateway_config_claude,start_mcp_gateway}.cjs; actions/setup/sh/check_oauth_tokens.sh; the four compiled samples' locks.
- anthropics/claude-code-action v1: src/github/operations/git-config.ts, src/entrypoints/tag/branch.ts; actions/create-github-app-token v1: lib/main.js; zizmor 1.30.1: crates/zizmor/src/audit/{artipacked,github_app}.rs.
- github/docs main: content/actions/reference/limits.md, data/reusables/actions/actions-do-not-trigger-workflows.md, content/rest/using-the-rest-api/rate-limits-for-the-rest-api.md.
- Scanners: zizmor 1.30.1, actionlint, shellcheck 0.10.0, over the eleven workflows.
