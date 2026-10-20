# The pool of Claude tokens: usage, assignment and auto mode

Notes of the thread "Symphony beyond cooperation" (the token wizard's
thread), written 2026-10-17 from the owner's ask that day: the control
panel should list the Claude tokens, assign them to jobs, show each one's
use of its five-hour and seven-day windows with their resets and the
Fable weekly limit, as claude-swap (cswap) does, and keep a pool in an
auto mode that moves to another token before one runs out. The sources
are this thread's own reading of Claude Code 2.1.302's binary (strings),
of claude-swap 0.27.2 from PyPI, and of coordbench's bench.yml; no Claude
Doc, artifact or upload lies behind it.

## What can read a token's usage

GitHub never gives a secret back, and the control panel runs in the
browser as the signed-in person, so neither can read a slot's token.
What a token's account has used is known in three places.

- Claude's answers. Every response to a subscription token carries the
  anthropic-ratelimit-unified-* headers (5h-utilization, 5h-reset,
  7d-utilization, 7d-reset, status and others), and Claude Code turns
  them into a stream-json message, rate_limit_event, whose
  rate_limit_info.unifiedWindows has five_hour and seven_day, each with
  utilization (a fraction) and resetsAt (unix seconds), and
  seven_day_overage_included for accounts that have it. Its schema in
  the binary says it is absent for API keys, Bedrock and Vertex, and
  present once the first response with the headers is seen. So every
  Claude run in Actions already holds a reading of its token, and a
  probe of one word gives a fresh one.
- The usage page, https://api.anthropic.com/api/oauth/usage, which
  cswap reads with each account's full login. Its newer limits array has
  weekly_scoped entries named by model, such as Fable, which is where
  cswap's per-model weekly limits come from. A token from claude
  setup-token is minted inference-only (its scope is user:inference; the
  binary's sign-in builds it with inferenceOnly), and Claude Code itself
  says a sign-in missing user:profile cannot read the account's
  profile, so the usage page is out of a runner's reach: inferred, not
  tried, since no session holds a token.
- cswap on the owner's machine, which has the full logins.
  `cswap list --json` gives, per account, usage.fiveHour, usage.sevenDay
  and usage.scoped (each pct in percent and resetsAt), or lastGoodUsage
  when the newest fetch failed, with usageFetchedAt.

So the five-hour and seven-day windows come from any of the three, and
the Fable limit only from cswap: the event's rateLimitType names two
per-model weekly windows, seven_day_opus and seven_day_sonnet, and only
when one of them is the limiting window, and names no Fable window in
this version. pool.py keeps an Opus or Sonnet window the event names as a
per-model limit, and a refused request's window as full until its reset.

## The design

One file per slot and kind of reading on the branch pool, kept as the
branches board and metrics are, one commit with no history: slot-N.run,
slot-N.probe and slot-N.cswap, each with the slot, when, the windows and
the per-model limits, and no token, e-mail or text (tools/pool.py).

- run: the Claude workflows read the last rate_limit_event of their
  execution file after claude-code-action, at no cost. Whether the
  action's execution file keeps those events is not yet seen: the first
  run with the step says so.
- probe: .github/workflows/pool.yml asks each slot one word with
  claude-code-action on Haiku and keeps the reading; it runs when a
  person presses Run workflow or the panel's Refresh, and never on a
  schedule, since each probe spends a little of the window it reads (the
  owner chose "On Refresh" on the thread's card, 2026-10-17).
- cswap: `python3 scripts/tokens.py usage` on the owner's machine maps
  cswap's accounts to slots by the numbers the wizard remembered in
  tokens.json and writes the readings through GitHub's git API.

The auto mode is tools/pool.py's pick: among the slots of the pool, the
one with the least used five-hour window, then seven-day window, then
the list's order, a slot with no reading yet after every slot with one
(its secret may be unset or revoked), passing over any slot a window or a model limit holds
at or past 90 percent until its reset; when every slot is held, the one
free first, which the caller is told. A window past its reset counts as
empty. A run takes its slot when it starts, so a run already going
finishes on its token; the next run moves on.

The picker sits in the template's tools/, not in the protocol library:
the decision of 2026-10-13 put the pool's picker in the library, and the
library takes new features only after 0.5.1 is cut, so it moves there
then, as its own pull request in symphony-protocol.

## The steps

1. tools/pool.py, the branch pool, pool.yml's probe and tokens.py's
   usage (this note's pull request).
2. A worker in Actions takes a slot, named or auto, from
   .github/symphony/accounts.json, a file of the template's own, since
   the workers' registry is the protocol library's and takes no new key
   before 0.5.1; workers.yml records each run's reading on the branch
   pool. @claude and the coordinator stay on the main token.
3. coordbench's bench.yml takes auto in its accounts box
   (coordbench#29): coordbench's GITHUB_TOKEN cannot read this
   repository's branch, so coordbench keeps a pool of its own, from its
   real jobs' streams through a workflow Pool of its own, Bench itself
   staying read-only, and from `tokens.py usage --also coordbench`.
4. The control panel's Tokens page (openspineconsortium.github.io#25):
   the slots' windows, resets and model limits, which slot auto takes,
   the assignment as a pull request, and Refresh.

## Open items

- Whether claude-code-action's execution file carries rate_limit_event.
- Whether the panel's sign-in token may dispatch pool.yml and write the
  assignment file (the App's user token's permissions).
