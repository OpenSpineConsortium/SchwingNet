# gh-aw against Symphony: the facts a migration plan needs

Handoff for the thread planning symphony-template's hand-written workflows onto compiled gh-aw YAML. Everything here was read on 2026-10-14 from github/gh-aw at d06e087 (docs under docs/src/content/docs/), githubnext/gh-aw-workshop at d8c57ab, github/docs main, OpenSpineConsortium/symphony-protocol at 3e98b88 and symphony-template main at 1dda21d. The full comparison, with the owner's four questions answered and the recommendation, is symphony-vs-gh-aw.md beside this file; this file holds what a plan must not get wrong.

## 1. Engines and credentials

Storing a Claude credential in GitHub is not enough for gh-aw. The owner has said GitHub may store their Claude credentials; the deciding fact is billing, not storage.

- The subscription token is refused by design: "CLAUDE_CODE_OAUTH_TOKEN is not supported by GitHub Agentic Workflows. Provider-based OAuth authentication (such as billing through a Claude Teams or Claude Max subscription) is not supported. If you have set CLAUDE_CODE_OAUTH_TOKEN as a repository secret, it will be ignored" (reference/auth.mdx:219; engines/claude.md:22). Activation also fails early on any `gho_` OAuth token in COPILOT_GITHUB_TOKEN or GH_AW_GITHUB_TOKEN (auth.mdx:159).
- The Claude engine's three routes (engines/claude.md:18-35):
  1. ANTHROPIC_API_KEY as a repository secret: Anthropic API billing, per token.
  2. Anthropic workload identity federation: no stored secret, short-lived OIDC exchange, still Anthropic API billing (auth.mdx:225-267).
  3. Copilot inference: `engine: claude`, `model: copilot/<claude model>`, `permissions: copilot-requests: write`; "no PAT, COPILOT_GITHUB_TOKEN secret, or ANTHROPIC_API_KEY is required"; billed to the organization's Copilot plan; the default sandbox is required and holds the GitHub credential; Claude receives a placeholder key. Needs an organization Copilot subscription with centralized billing, else COPILOT_GITHUB_TOKEN, a fine-grained PAT (auth.mdx:108-138).
- The Copilot engine: `copilot-requests: write`, else COPILOT_GITHUB_TOKEN as a fine-grained PAT with Copilot Requests access (engines/copilot.md:17-18).
- Symphony today: the workers in Actions and @claude run anthropics/claude-code-action with `claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}` (symphony-template .github/workflows/workers.yml:134, claude.yml:65; docs/project.md:41), on one account's subscription plan, and the durable decision reads "no API billing: Claude in CI runs on a subscription OAuth token" (CLAUDE.md:38). Moving the Actions workers onto gh-aw moves their cost from that plan to Anthropic API billing or to Copilot billing. A person's sessions and routines are unaffected: they never ran in Actions (docs/agents/WORKERS.md:7-10).

## 2. Per-capability map

"as-is": gh-aw ships the same thing for the same purpose. "weaker": something in the same place that does not give what Symphony's spec or F-fixes require. "no": nothing there.

| Symphony capability | gh-aw has it? | Reinventing? | What differs |
| --- | --- | --- | --- |
| The queue as issues labelled todo, Given to workers, blocker, epic | no | no | The native queue is JSONL on a branch; issues are a mirror at most (`tools.work-queue.issues`, reference/frontmatter-full.md:4443 onward) |
| The claim lock by first push of claude/N | no | no | gh-aw's Claim is granted by a dispatcher to an Actions worker (patterns/workqueue-ops.md:27); nothing locks a branch name |
| Claim file and announce (labels, comment) | weaker | partly | `safe-outputs.add-labels`, `add-comment` write labels and comments, but carry no claim semantics |
| The board STATE.md on a branch, rewritten on every event | weaker | partly | `repo-memory` is Git-backed state on a branch (reference/repo-memory.md); no rendered view of claims |
| "main moved" by state, rebase-or-merge policy | no | no | Workers deliver effects through safe-outputs; `push-to-pull-request-branch` exists, `update-pull-request`'s `update-branch` merges the base in and pull request creation leaves a rebase to the author (reference/safe-outputs-pull-requests.md:150, 194-196), as delivery steps; nothing tells a worker its branch is behind main (no non-test file in pkg/workqueue mentions behind, rebase or mergeable) |
| Idle release after 24 hours, rename to released/ | no | no | "locks never expire or get stolen" (reference/work-queue.md:310); crash recovery that clears them "is not implemented" (:321); retries only after a terminal run attempt (:422) |
| Overlaps by file, landing order, told once | no | no | Nothing reads which open work touches the same files |
| Planning epics into tasks, the clerk, dealing | weaker | partly | ResearchPlanAssignOps and orchestrator-ops plan and assign; the native queue has dependency graphs; no dealing to a matrix of workers |
| Workers registry (.github/symphony/workers/*.json), Add a worker form | weaker | partly | Each gh-aw worker is a .md workflow with its own frontmatter; `roles` (frontmatter-full.md:1070) says who may trigger; no registry of areas |
| Workers in Actions and @claude mentions on the subscription token | no | no | See section 1; `slash_command` and `command` triggers (frontmatter-full.md:181, 239) are the nearest named form, but gh-aw also takes plain triggers with a top-level `if:`, so claude.yml's @claude conditions carry over unchanged |
| A person's sessions and routines as workers; session hook; skills | no | no | gh-aw has no notion of a session outside Actions |
| The push guard hook, the lease fence | no | no | gh-aw's agent never has push rights; writes go through safe-outputs, so the problem does not arise there and is not solved for a session |
| The protocol check in CI | no | no | Nothing checks a pull request against a claim protocol |
| Required check, rulesets, the planned QA gate | as-is in part | partly | `threat-detection`, `staged` mode and `max-patch-size` under safe-outputs do the run side of a QA gate; the required check and rulesets are GitHub's, used by both |
| Rails: 10 runs a day, none while main is red, write access to queue | as-is in part | yes, partly | `max-daily-ai-credits` (frontmatter-full.md:3581, default 5000 AIC per workflow per 24 hours), `user-rate-limit` (:23540, 1 to 10 runs per window of up to 180 minutes), `stop-after` (:905), `skip-if-match` (:918), `roles` (:1070), `timeout-minutes` (:1868, agent default 20 minutes), `max-turns` (:3521); "none while main is red" is `skip-if-check-failing` (frontmatter-full.md:984-989: skip the run while CI checks on the target branch fail); in Symphony that cap is a Phase 3 decision not yet built |
| Field metrics, Symphony-Usage trailers, economics | weaker | partly | Per-run spend reporting and reference/cost-management.md; no 30-day aggregates by work setting |
| Shared memory and the checkpoint | weaker | partly | `cache-memory` and `repo-memory` are an agent's memory, not a project's instructions |
| Tidy, protocol.yml sync, template-init, crowd mode | no | no | `aw.json` auto-upgrade of the compiler is the sync's cousin; crowd mode has no counterpart |
| The gate (policy and world) and the harness | no | no | gh-aw keeps "executable contracts, models, fixtures" for its own queue (specs/work-queue-specification.md:11); nothing checks a claim protocol |
| Sandbox, network allowlist, action pinning, lock files | Symphony has none | not building it | gh-aw ships them (`sandbox`, `network`, the compiler); Symphony relies on anthropics/claude-code-action |

Tally: as-is in part 2, weaker 7, no 11.

## 3. What a gh-aw repository looks like

- Source and output: a `.md` file with YAML frontmatter compiles to a `.lock.yml`. In the workshop, q.md is 304 lines and q.lock.yml 2,065; 22 workflows and one shared guidelines file they import, 22 lock files, about 50,000 lines under .github/workflows/.
- The compile step: schema validation, allow-listed expressions, import resolution, job construction, action pinning to SHAs, YAML generation (reference/compilation-process.md:12-58). Optional actionlint, zizmor, poutine, yamllint; `gh aw validate` runs them all without emitting; `--strict` refuses write permissions, unpinned actions and wildcard network domains (setup/cli.md:340-404). The markdown body is loaded at runtime and needs no recompile (compilation-process.md:14); the compiler "does not constrain runtime behavior" (introduction/architecture.mdx:429).
- Per run: seven pinned container images in the workshop's locks (gh-aw-firewall agent, api-proxy and squid, gh-aw-mcpg, github-mcp-server, gh-aw-node, alpine; q.lock.yml:2), the safe-outputs job separate from the agent job, and the agent with read-only permissions.
- Secrets each lock lists: GH_AW_GITHUB_TOKEN, GH_AW_GITHUB_MCP_SERVER_TOKEN, GH_AW_CI_TRIGGER_TOKEN, GH_AW_DEFAULT_OTLP_HEADERS, GITHUB_TOKEN (q.lock.yml:2).
- Upkeep: `aw.json` with a weekly `auto_upgrade` cron and `--pre-releases` in the workshop; the compiler generates agentics-maintenance.yml and agentic-auto-upgrade.yml; five releases shipped in the week of 2026-10-12 (v0.91.4 to v0.91.8, blog/2026-10-12-weekly-update.md:11). Every upgrade regenerates every lock file.
- Concurrency defaults the compiler writes: per-workflow groups keyed on workflow name plus issue, PR, branch or label, `queue: max` where cancel-in-progress is off (on those per-issue, per-PR or per-ref groups, never one group for a whole repository as Symphony's board is), and a per-engine group `gh-aw-{engine-id}` that "ensures only one agent job runs per engine across all workflows" (reference/concurrency.md:9-30). Parallel workers need that per-engine group overridden.
- Rate limiting defaults: agent timeout 20 minutes; `max-daily-ai-credits` 5000 AIC (about 50 USD) per workflow per rolling day; safe-output maxima such as one dispatched agent per run (reference/rate-limiting-controls.md:40, 67-81, 130-140).
- The owner's steps: `gh extension install github/gh-aw`, `gh aw init`, `gh aw compile` after each frontmatter change, the secrets above (workshop .github/agents/agentic-workflows.md:194-209).
- The native work queue, if ever used: `tools.work-queue` with `require-assignment: true` and `worker: true` on workers (patterns/workqueue-ops.md:38); Git storage only; shipped in v0.91.6; its spec calls itself "the intended experience of the proposed design, not a feature already implemented" (specs/work-queue-specification.md:23) and "cannot promise indefinite growth" (section 10, item 10).

## 4. Scale limits that bite first

GitHub's, which both sides share (github/docs content/actions/reference/limits.md; content/rest/using-the-rest-api/rate-limits-for-the-rest-api.md; the numbers also in symphony-template's handoff page RESEARCH-scale.md:195, 239, 356, 515):
- GITHUB_TOKEN: 1,000 requests an hour per repository (15,000 on GHEC). Symphony's board, tidy, metrics and clerk share it; the board runs on nearly every event, reads per claim and per pull request, and has no budget of its own (RESEARCH-scale.md:239). This is Symphony's first wall. An App installation token gets 5,000 an hour, scaling with the organization.
- Secondary limits on content creation (comments, issues) apply per account whatever the primary limit.
- Workflow queuing: 500 runs per 10 seconds per repository; with `queue: max` at most 100 runs wait per concurrency group and "runs beyond this limit will be rejected" (limits.md:36, 38). Symphony's board is one group with queue: max since #70 merged on 2026-10-14 (cb83274), so a burst of more than 100 events loses runs; once the library half of F12's fix is in the template a lost run costs only a delay, and today it is not: the library's state-keyed main moved is past 0.4.1 and unreleased (symphony-protocol sdlc_protocol/__init__.py:19; the template's tools/VENDORED:1 and tools/sdlc_protocol/board.py:507 still key it on the push event).
- Concurrent jobs per plan: 20 Free, 40 Pro, 60 Team, 500 Enterprise; a matrix at most 256 jobs; a job at most 6 hours (RESEARCH-scale.md:356, 515).
- Schedules are best effort and were measured hours late or absent (RESEARCH-scale.md:227), so every fallback cron on either side is a fallback, never the trigger to count on.

Symphony's own:
- One subscription token for every worker in Actions, so they share one account's five-hour window (CLAUDE.md, the token decision), and the Phase 3 cap of 10 Claude runs a day per repository.
- The protocol is per repository, so scale is horizontal: each repository gets its own token budget, board group and claim namespace.

gh-aw's own:
- The per-engine concurrency default of one agent job per engine across all workflows (reference/concurrency.md:30).
- Version churn and lock regeneration on every upgrade; `aw.json` auto-upgrade weekly in the workshop.
- The native queue: hooks batch 25 targets, "Writes are paced and exhausted rate limits stop subsequent live requests" (reference/work-queue.md:323-326); reservations of a dead worker hold until an operator's `cancel-claim` (:310, :321, :481).
- Default 5000 AIC a day per workflow and a 20-minute agent timeout, both overridable.

Copilot dynamic workflows (github/docs content/copilot/concepts/agents/dynamic-workflows.md): public preview behind `--experimental`; runs where the Copilot CLI runs, one host; limits on concurrent subagents, total subagents, active time and approximate AI credits; no coordination between hosts or sessions.

## 5. Where the rest is

symphony-vs-gh-aw.md beside this file: the four answers (sections 1 to 4), the concurrency page (5), the compile step (6), the workshop (8), dynamic workflows (9), the two choices and what survives of 0.5.0 (10), the Copilot-as-coordinator addendum (11) and the scale comparison of the four candidates (12).

## 6. Two rules for the migration, from the verification pass

- One lock. A gh-aw worker is one Actions run, "(run_id, run_attempt=1)" (specs/work-queue-specification.md:1110-1111), and only `dispatch_next` creates Claims (spec:883). Do not put the Actions workers on `tools.work-queue` while sessions and routines claim by branch: two claim authorities on one issue break guarantee G1 (spec/PROTOCOL.md:3). gh-aw is the compiled run layer; the branch push stays the lock for every worker, so a compiled worker still runs the claim skill's steps.
- The dispatch credential. gh-aw's dispatch "requires contents: write alongside actions: write on the trusted dispatch credential" (reference/work-queue.md:138-143). Symphony's workers.yml already grants its job those two scopes on GITHUB_TOKEN, contents: write and actions: write (.github/workflows/workers.yml:94-100), beside the Claude secret; the plan has to say whether gh-aw's trusted dispatcher runs on GITHUB_TOKEN or an App token, since its agent "receives neither credential" (reference/work-queue.md:140-142).

## 7. Verification pass

Checked on 2026-10-14 by a second pass over both source trees: 12 comparison claims and 24 of the 28 capability mappings re-verified. No verdict in the table changed. Four sentences were corrected above: the "main moved" row (gh-aw has the landing mechanics as delivery steps, not the notice), the concurrency default (per-context groups, not a repository-wide one), F12's standing (#70 has since merged; the library half is unreleased, so the template's main does not have it yet) and the dispatcher's scopes (workers.yml already grants them). The main note's last section lists the same with its sources.

## 8. The last verification round

On 2026-10-14 a second round re-checked the mappings the usage limit had skipped. Five finished, each keeping its verdict; the table above is corrected for the first two points:

- The rails row was wrong on one point: "none while main is red" has a counterpart, `skip-if-check-failing` (reference/frontmatter-full.md:984-989), and in Symphony that cap is a Phase 3 decision not yet built in workers.yml.
- @claude carries over as is: gh-aw takes plain triggers with a top-level `if:`, so the mention need not become a /command.
- The dependency rule (.claude/rules/writing.md:6) allows GitHub's own actions, and github/gh-aw-actions is published by GitHub, so whether gh-aw breaks the rule is a ruling for the owner, not a given. What the rule clearly does not cover is the `gh aw` CLI, the sandbox's container images and gh-aw's exact SHA pins in place of major tags.
- Adding a worker costs more on gh-aw: a worker is a file under .github/workflows/, so the pull request that adds one needs the workflows permission, which GITHUB_TOKEN cannot hold, plus its compiled lock file. Symphony's worker JSON sits outside that folder. gh-aw's per-Work `worker_profile` is where area dealing would go.
- A 90-minute worker needs two limits raised on gh-aw: `timeout-minutes` and the agent job's own 60-minute default.
- The required check needs a token decision: a pull request a gh-aw agent opens or pushes with the default GITHUB_TOKEN starts no CI run, so Symphony's required check would not report on it unless another token (GH_AW_CI_TRIGGER_TOKEN, a PAT or an App) pushes.
- Cost accounting is a wheel gh-aw has: per-run usage artifacts, cross-run reports inside Actions through the `agentic-workflows` tool, episodes that total an orchestrated run's cost (reference/cost-management.md:66-76, 444), and a daily-cap ledger on a repo-memory branch. Symphony's usage artifact, list-price estimate and run cap are partly reinvented; its 30-day aggregates by work setting, its alone-versus-parallel ratios and its name-free record are not in gh-aw.
- Precision only: several line numbers in the capability map were off by a few lines; no verdict rested on them.

Not verified: the shared memory and checkpoint row, and two claims in the main note (the state of both proofs; that no Symphony document had considered an outside queue). Section 14 of symphony-vs-gh-aw.md lists them. Pull request #70 has merged since this file was written (cb83274).
