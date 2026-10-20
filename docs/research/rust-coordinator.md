# A Rust coordinator in place of GitHub Actions

Source: the owner's question in the thread of 2026-10-19, 02:58 UTC: "can you do deep research into building a low latency memory safe rust coordinator which would replace how I'm using GitHub actions but nearly instant to coordinate GitHub instead of slow ass actions? Further the compiler is much more powerful for syntactic guarantees than yaml". Research only: no code was written, no service started, nothing spent. Measured at symphony-template cd0889e from the repository's own Actions runs and events through the REST API; compared with the plan the owner approved on 2026-10-14 (docs/checkpoints/2026-10-14b/plans/gh-aw-migration-plan.md) and its summary, docs/research/workflow-languages.md.

## The answer

Not as a replacement, and not yet as anything hosted. The measurement says GitHub's own overhead is seconds, not minutes: an event becomes a run in about 1 second (median of 18, at most 5), a job waits 2 to 3 seconds for a runner (40 jobs), and setup and checkout take about 2 seconds more. The minutes the owner feels are the work itself: the required check spends 160 to 230 seconds inside scripts/check.sh, and a Claude session takes minutes on any host. A Rust server would turn each hop's 5 to 10 seconds into well under a second, and it would remove the one real queue, the board's single concurrency group, but it cannot make the check or Claude faster, and Claude cannot run on it at all without breaking the credential rule (section 4).

Where Rust does buy something real is correctness, though not the way the question puts it. Python is memory safe already, so memory safety gains nothing over today. What Rust adds is static types over every event and claim state, and, with the stateright crate, model checking of the same actor code that would run. The protocol's bugs so far (F1 to F18) were races against GitHub's state and Actions' concurrency semantics, not typos in YAML, and a single writer per repository removes a class of them outright (F12, the board's waiting run cancelled by a newer one).

Recommendation, in three steps, each on the owner's word:

1. Free now: measure a copy's board runs under a burst (a merge fires four events) to learn how long the board queue really holds work. The template skips its own board, so this needs a copy such as symphony-protocol-canary.
2. A Rust core with no server: the board's state machine (claim, release, overlap, deal) as a Rust crate checked by stateright against the oracle of symphony-protocol's validation harness, run in CI only. This gives the compiler's and the model checker's guarantees with nothing hosted, and it can cross-check the Python library on every interleaving. It is a second implementation of the protocol, which is the owner's call.
3. Only if step 1 shows the queue matters: a webhook edge in Rust on Cloudflare (a Worker and one Durable Object per repository), as a hosted part of the paid SymphonyBoard App, with Actions kept as the fallback sweep and as the only place Claude runs. This reverses the standing decision "no server of ours", so it is the owner's decision alone.

Candidate A (Symphony's own Python compiler to YAML) stays first either way: it fixes the YAML's lack of checks with no server and no new language, and the Rust core of step 2 would sit beside it, not in place of it.

## 1. Where the time goes today, measured

Measured on 2026-10-19 between 00:25 and 02:58 UTC in OpenSpineConsortium/symphony-template, from /repos/.../events (the time GitHub recorded each push) and /actions/runs and /actions/runs/{id}/jobs.

| Hop | Measured | n |
| --- | --- | ---: |
| Push recorded to run created (Board, Checks) | median 1 s, range 1 to 5 s | 18 |
| Job created to job started (runner assigned) | 2 to 3 s | 40 |
| Set up job and actions/checkout | 1 to 2 s | 20 |
| The "values" job of ci.yml, whole | 2 to 4 s | 20 |
| The "check" job, whole | 166 to 233 s, almost all in "Run the checks" | 20 |

One outlier, 409 s from push to a pull_request run, was a later event on the same commit, not a wait. One evening's numbers on GitHub-hosted runners: at peak hours or during an incident the runner wait grows, which this sample cannot show.

What a chain costs. The slow paths are chains of hops and the work between them: a claim's push starts a board run, which waits in the group `board` behind every earlier run (queue: max); a label starts workers.yml, which deals and then starts a Claude session; a finished leg dispatches itself again. Each hop costs the 5 to 10 seconds above plus its own work. The board's own run length was not measured, since the template skips its board job.

What a server cannot shorten: the check (scripts/check.sh, three to four minutes), Claude's sessions (minutes), and the 24-hour idle rule for releasing a claim, which is a rule and not a delay.

Cheaper speed-ups that need no server, inferred and not measured: run the check's independent parts in parallel jobs; fold the deal into the board's run where a label event already started it, saving one hop; keep schedules as fallbacks only, as they already are.

## 2. What a Rust coordinator would be

A design sketch for comparison, not a plan to build.

- Events in: SymphonyBoard's webhook turned on, pointed at a Cloudflare Worker written in Rust (workers-rs, compiled to WebAssembly). It checks the X-Hub-Signature-256 HMAC, answers inside GitHub's 10-second limit, and hands the event to one Durable Object per repository.
- One writer per repository: a Durable Object runs one request at a time, so the board's concurrency group becomes an in-memory queue of milliseconds, with no runner per event and no waiting run for a newer one to cancel (F12 by construction).
- Level-triggered, never edge-triggered: each event only says "look again"; the object reads issues, branches and pull requests and computes the board, the releases, the overlaps and the deal from that state, as board.yml already does ("no comment depends on the event that started the run"). This is what keeps no missed work when deliveries are lost.
- Missed deliveries: GitHub does not redeliver a failed delivery by itself; its deliveries API lists the last three days and redelivers on request. So the edge needs a sweep: a Cron Trigger that reconciles every repository and redelivers failures, with Actions' six-hourly board run kept as the last fallback.
- GitHub App auth: the App's private key as a Worker secret; a JWT signed RS256 for at most ten minutes, exchanged for a one-hour installation token per installation, cached in the object. octocrab (0.54) supports App JWTs and installation tokens on a native target; whether it builds for WebAssembly was not checked, and a Worker may need plain fetch calls and a JWT crate that does.
- Claude work out: the edge never runs Claude. It starts workers.yml or claude.yml by workflow_dispatch, which since February 2026 returns the run's id, so the object can follow the run. Claude keeps running in Actions on each repository's own CLAUDE_CODE_OAUTH_TOKEN secret, exactly as today.
- Writes back: labels, comments, branch renames and the board branch through the installation token, inside GitHub's rate limits (5,000 requests an hour per installation and secondary limits on content-creating calls, from GitHub's documentation as recalled, not re-read this session). Faster reaction does not raise those limits; a burst still has to be paced.

## 3. Hosting and what it costs

| Host | Price | Fit |
| --- | --- | --- |
| Cloudflare Workers Free with Durable Objects | free: 100,000 requests a day, 10 ms of CPU per invocation (waiting on GitHub is not CPU), Durable Objects 100,000 requests and 13,000 GB-s a day, SQLite storage only | likely enough for a handful of repositories; the 10 ms CPU cap is the risk for rendering a large board |
| Cloudflare Workers Paid | $5 a month minimum: 10 million requests and 30 million CPU ms included, up to 5 minutes of CPU per request, 15 for a Cron Trigger | comfortable; the account already runs the control panel's sign-in Worker |
| Fly.io, an always-on machine | $2.19 a month for shared-cpu-1x with 256 MB, $3.69 with 512 MB; no free allowance for new organizations | a plain Rust binary (tokio, axum, octocrab) with no WebAssembly limits, but a server to patch and keep up |
| GitHub Actions, today | free on public repositories; private ones spend the plan's minutes | no server; seconds of overhead per hop |

Prices read on 2026-10-19 from Cloudflare's Workers pricing page, its Durable Objects free-tier changelog of 2025-04-07 and Fly.io's pricing page.

## 4. Claude workers and the credential rule

Claude Code's legal and compliance page (code.claude.com/docs/en/legal-and-compliance, read 2026-10-19) says OAuth sign-in is "designed to support ordinary use of Claude Code", that developers "may not collect, store, or intermediate Claude.ai credentials or session tokens", and that a product running Claude Code for others needs each end user to "authenticate with their own" credentials. So:

- The coordinator must never hold a Claude token. A hosted edge that stored subscription tokens and ran `claude -p` for each repository would be intermediating them, and it would break the project's own rules (no Claude credential anywhere; a paid product runs on each customer's own subscription, never on pooled accounts).
- A Worker cannot start a process anyway, so `claude -p` cannot run there; a container host could, but that is the case above.
- The route that keeps the rule is the one in section 2: the edge dispatches, Actions runs Claude on the repository's own secret. The Claude leg keeps Actions' start-up cost of a few seconds, which is small beside a session of minutes.

## 5. What the compiler guarantees, and what it does not

What Rust's compiler gives over YAML:

- Every event and every claim state as a type: an exhaustive match over the events a handler takes, a claim lifecycle whose states (claimed, finished, released, renamed) can only move along legal edges (typestate), no expression that names a field the event does not carry, no string where a number belongs. YAML expressions are checked only at run time, and only partly by actionlint.
- No garbage collector and no interpreter start-up, so a handler runs in milliseconds.

What it does not give:

- Memory safety over today: the protocol is Python, which is memory safe; nothing changes there.
- The protocol's properties: no deadlock, no missed work and no orphaned worker are properties of interleavings of several workers against GitHub's eventually consistent state, lost and reordered webhooks included. A type checker proves none of them. The findings that the validation harness made (F1 to F18) were of that kind.
- The rest of the YAML: the workflows that remain (the check, the Claude legs, the fallback sweep) stay YAML, so Candidate A is still needed for them.

What would give the protocol's properties: model checking. stateright is a Rust actor library with an embedded model checker that explores every ordering of messages, with linearizability and sequential consistency testers, and the same actors run on a real network. Written that way, the board's state machine would be checked for no deadlock and no missed work over every interleaving of a few workers, lost deliveries included, the same oracle symphony-protocol's validation harness (validation/DESIGN.md) already runs against the Python library. That, not syntax, is the real gain, and it needs no server (step 2 above).

## 6. Against the other routes

| | Actions today | Candidate A: Python compiler to YAML | gh-aw pilot | Rust edge (step 3) |
| --- | --- | --- | --- | --- |
| Reaction per hop | 5 to 10 s, plus the board queue | the same | the same | well under 1 s for the deterministic work; Claude legs unchanged |
| Server of ours | none | none | none | one Worker and Durable Objects, or a machine |
| Claude credential | the repository's secret | the same | the same, through a self-defined engine gh-aw calls unsupported | the same, dispatched; the edge holds none |
| Checks on the logic | actionlint, the protocol tests | a generator that fails the check on drift, plus the above | gh-aw's compiler on three workflows | Rust types; stateright if the core is written for it |
| New code | none | a stdlib-only Python module | gh-aw as a dependency | a second implementation of the protocol in Rust, a toolchain, a deploy |
| Standing decisions | fits | fits; approved 2026-10-14 | approved as a pilot only | breaks "no server of ours" and the planned deletion of the webhook server; fits open core only as a paid hosted part |

## 7. The owner's decisions

1. Whether to measure a copy's board queue under a burst (step 1): free, a few pushes to symphony-protocol-canary.
2. Whether a second implementation of the protocol, in Rust and model checked, is wanted beside the Python library (step 2).
3. Whether to lift "no server of ours" for a hosted, paid SymphonyBoard edge (step 3), and on which host.

Nothing above is built; outside code bases wait for the owner's choice (docs/research/outside-code-bases.md).

## 8. Candidate A's goal without writing a compiler

The owner's follow-up of 2026-10-19, 03:13 UTC: "I'm leaning toward A but I'd rather [not] build my own compiler." Three ways to get the checks Candidate A was for without writing one, best first:

1. A checker in place of a compiler. actionlint already type-checks every `${{ }}` expression against the contexts an event carries, the `needs` and `matrix` objects, the inputs and outputs of well-known actions, and runs shellcheck over every `run:` block; zizmor adds the security checks (unpinned actions, credentials left in checkouts, injection from event text). The plan of 2026-10-14 already ran both by hand (one actionlint finding, 44 zizmor findings). Making them part of `bash scripts/check.sh` and CI gives most of the "compiler" guarantee for the YAML as written, with nothing generated. They are single binaries, a dependency the writing rule makes an issue first.
2. Less YAML to check. The one public runtime the owner chose on 2026-10-13 moves Symphony's logic into tested Python behind a dispatcher workflow and a composite action, leaving each repository a few thin caller files (about 38 for a whole-template copy, 8 for a protocol-only one). Logic in Python is covered by the protocol's tests and its validation harness, which no YAML compiler reaches. The less logic left in YAML, the less a typed generator can add.
3. An existing typed generator, if the owner still wants to write workflows in a typed language:
   - github-workflows-kt (typesafegithub, Kotlin scripts, Apache-2.0, release 4.0.0 of 2026-07-03, about 650 stars): typed bindings for actions' inputs, generated from the actions' own metadata. It is the mature choice; it adds a JVM and Kotlin to the toolchain. From memory and not re-read this session: its generated files carry a job that fails when the committed YAML differs from the script, the drift check Candidate A planned.
   - gh-workflow (tailcallhq, Rust, 0.9.0 of 2026-07-22, about 176 stars): workflows built in Rust and written out by `cargo test`. Rust's types, but young: half its items are documented, and no drift check or typed action inputs are shown.
   - gaji (TypeScript compiled to YAML by a Rust binary, typed action wrappers from action.yml): early, several 0.x releases in weeks.
   - gh-aw stays a pilot for the Claude workflows only, for the reasons in docs/research/workflow-languages.md.

Recommendation: 1 and 2 together. They need no compiler of anyone's, keep Python as the one language of Symphony's logic, and leave only thin YAML that actionlint and zizmor check on every pull request. github-workflows-kt is the fallback if typed authoring is still wanted after that; a Rust core for the board's state machine (step 2 above) remains a separate choice about correctness, not about YAML.

### Typed generators against linted YAML

The owner asked next (03:22 UTC) whether gh-workflow or github-workflows-kt offers anything over YAML checked by actionlint and zizmor, for technical debt, the complexity of coordination and future proofing. Inferred from the sources above and the plan's counts, nothing measured:

- Technical debt: a generator's one real gain is removing repeated text (the plan counted the usage recorder's three steps six times and the crowd guard twelve times) with ordinary functions. GitHub's own composite actions and reusable workflows remove the same repetition in YAML, and the public runtime is built from exactly those. Against that, a generator adds a second source of truth, a toolchain (Kotlin and a JVM, or Rust and cargo) for anyone who edits a workflow, and a drift check. Net debt is higher.
- Coordination: neither helps. Symphony's coordination is in the Python protocol and in Actions' run-time behaviour (concurrency groups, event order, the lost-run case F12); a generator types the plumbing around it and checks none of that. The protocol's validation harness is what covers coordination.
- Future proofing: plain YAML is GitHub's own format, so new syntax works the day it ships (board.yml uses `queue: max`, new this year); a generator must add it first or be bypassed by hand. The linters track GitHub closely and drop out without a trace. gh-workflow is one maintainer's young crate; github-workflows-kt is healthier but still a third party. Leaving either is cheap, since the generated YAML is committed, but it is churn.

So for Symphony, linted YAML with the logic in Python is the better position on all three counts; a typed generator pays off for a repository with many large, hand-written workflows and no runtime to move their logic into, which is not Symphony's case.

## Sources read

- GitHub REST API on OpenSpineConsortium/symphony-template: /events, /actions/runs, /actions/workflows/ci.yml/runs, /actions/runs/{id}/jobs (2026-10-19).
- .github/workflows/board.yml, workers.yml, coordinator.yml and ci.yml at cd0889e.
- docs/checkpoints/2026-10-14b/plans/gh-aw-migration-plan.md and docs/research/workflow-languages.md.
- GitHub Docs: handling failed webhook deliveries (no automatic redelivery; 10-second limit) and redelivering webhooks (the past three days; REST API for an App).
- GitHub changelog 2026-02-19: the workflow dispatch API returns run ids.
- Cloudflare: Workers pricing page; changelog 2025-04-07, Durable Objects on the free plan.
- Fly.io: resource pricing page.
- Claude Code docs: legal and compliance, authentication and credential use.
- docs.rs: gh-workflow 0.9.0, gaji 0.2.2; dev.co's page on github-workflows-kt.
- docs.rs: stateright 0.31 (model checker, linearizability tester); octocrab 0.54 (App JWT and installation tokens).
