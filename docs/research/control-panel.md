# The Symphony control panel and what Symphony costs

The research notes of the thread "Symphony control website", item 7 of the owner's handoff of
2026-10-15 (docs/checkpoints/2026-10-15b/handoff.md). Written 2026-10-16 and kept current as the
work goes on; every figure names its source and the day it was read. The owner asked on
2026-10-16 that research notes accumulate in this repository rather than in replies, so this file
is the record and the thread's replies only point at it.

## The ask

Item 7, in the owner's words: "Interactive UI website with native claude browser to drive the
symphony environment (add repos, monitor CI, tasks, board, add workers, also with the option of
interacting through prompts) and direct comparison of money spent on this site versus
competitors (particularly notsorry)".

"notsorry" is unsorry, agenticsnz/unsorry, the swarm that proves theorems in Lean with
volunteers' own agents and coordinates them in GitHub Actions: it is the one system in the
taxonomy of 2026-10-15 that shares Symphony's shape (coordination as Actions jobs, no server, a
first-push-wins claim), and the taxonomy's manual walks it through as its worked example
(docs/checkpoints/2026-10-15b/taxonomy/spec.md, section 5.1; manual.md, section 5). No project
named "notsorry" was found on GitHub; the spelling is taken as a slip for unsorry.

## The answer in short

- Built in four pull requests merged on 2026-10-16 (the table under Where it lives): the control
  panel at /symphony/control/ and the cost page at /symphony/cost.html on the site, one script
  behind both; the stateless sign-in service in symphony-app; version 8 of the Apps' privacy
  statement in symphony-start; this note and a memory fact in the template. The same day the
  owner asked for "Sign in with GitHub" as the first way in, and three more pull requests made it
  so, with a fourth for what the fifth review of the sign-in found (Design decisions, 2).
- The way in: both pages open on one "Sign in with GitHub" button. Until the sign-in service
  runs, the button is shown but cannot be pressed, one line says why, and the token box beneath
  it stands open, so the pages work today with a fine-grained GitHub token pasted in; once the
  service runs, one press signs in, and the token stays folded under "Use a fine-grained token
  instead" as the fallback. Either way the person drives any repository of theirs that carries
  the topic symphony from the browser, as themselves. A Claude driving a browser reads the same
  page: every state is a sentence under the summary line and every action is a named button.
- Switched on 2026-10-17: the owner deployed the sign-in service at
  https://symphony-signin.openspineconsortium.workers.dev and sent SymphonyBoard's Client ID,
  and site pull request #24 set the two constants, so the button can be pressed. What is left is
  the owner's first real sign-in (What waits on the owner, below).
- The money: a Symphony repository pays one flat Claude plan for its workers in Actions ($20,
  $100 or $200 a month) and, on a public repository, nothing for the compute, since standard
  runners are free there and the coordination makes no model call. The other ways of running
  coding agents on GitHub meter every token: an API key (gh-aw's Claude engine, claude-code-action
  with a key) at Anthropic's list prices, GitHub Copilot's coding agent at the same list prices in
  AI credits past a plan's included ones, unsorry at whatever each volunteer pays for their own
  runs, and OpenAI's Codex at OpenAI's rates. The worked example below prices 300 runs a month:
  $210 of Sonnet 5.5 tokens at the list, which Symphony covers with a $100 plan while the runs fit
  its windows.

## Where it lives

| Repository | Files | Pull request |
| --- | --- | --- |
| OpenSpineConsortium/openspineconsortium.github.io | tools/pages/symphony/control/index/body.html, tools/pages/symphony/cost/body.html, assets/js/symphony-panel.js, assets/css/control.css, tools/build_site.py (two nodes), README.md; the built pages symphony/control/index.html and symphony/cost.html | #20, merged 2026-10-16 |
| OpenSpineConsortium/symphony-app | signin/worker.js, signin/test_worker.mjs, signin/README.md, scripts/check.sh | #14, merged 2026-10-16 |
| OpenSpineConsortium/symphony-start | PRIVACY.md, version 8 (rendered by the site at /symphony/apps-privacy.html) | #44, merged 2026-10-16 |
| OpenSpineConsortium/symphony-template | docs/research/control-panel.md (this file), docs/memory/the-control-panel.md and its index line | #95, merged last |
| OpenSpineConsortium/symphony-template | tools/economics.py, Sonnet 5.5's cache-read price | #102, merged 2026-10-16 |
| OpenSpineConsortium/openspineconsortium.github.io | Sign in with GitHub first: the gate in both body files, assets/js/symphony-panel.js, assets/css/control.css, README.md; every built page, with the site's master merged in | #22, merged 2026-10-16 |
| OpenSpineConsortium/symphony-app | signin/README.md: the deployment steps as Cloudflare's and GitHub's pages read on 2026-10-16 | #15, merged 2026-10-16 |
| OpenSpineConsortium/symphony-start | PRIVACY.md, version 9: a sign-in for one tab keeps its refresh token in the page's memory alone, a reopened tab brings its token back, a pasted token is asked about at GitHub first, and a replaced sign-in token is revoked | #45, merged 2026-10-16 |
| OpenSpineConsortium/symphony-template | this file and the memory fact, for Sign in with GitHub first | #109, merged last |
| OpenSpineConsortium/openspineconsortium.github.io | assets/js/symphony-panel.js: the fifth review's fixes | #23, merged 2026-10-16 |
| OpenSpineConsortium/symphony-template | this file and the memory fact, for the fifth review | the pull request after #109, merged last |
| OpenSpineConsortium/openspineconsortium.github.io | assets/js/symphony-panel.js: SIGNIN_SERVICE and CLIENT_ID set; every built page restamped ?v=202610171418 | #24, merged 2026-10-17 |
| OpenSpineConsortium/symphony-app | signin/panel-checks/: the checks set the two constants themselves, empty or mocked, whatever the shipped script holds, and SITE names the site's checkout | #17, merged 2026-10-17 |
| OpenSpineConsortium/symphony-template | this file and the memory fact, for the switch-on | the pull request after #17, merged last |

They merged in the order symphony-start (the site renders its privacy statement), the site,
symphony-app, then the template, each with a merge commit once its check was green, on the
owner's standing permission; the site has no check of its own beyond its build. The change to
Sign in with GitHub first merged the same way: the privacy statement's version 9, the site,
symphony-app, then the template.

## What the panel does

The parentheses in the ask, one by one, and how each is done through GitHub's REST API as the
signed-in person, with nothing of ours in between.

- Add repos: "Find my Symphony repositories" lists the person's repositories (up to 300) and
  keeps those whose About carries the topic symphony, which an adoption sets; a repository named
  by hand that lacks the topic gets the two presses that set Symphony up on it, the App's install
  link preselected for that one repository and the front door's form. `?repo=OWNER/NAME` in the
  address lands on one repository.
- Board: STATE.md on the branch board, read as raw text and rendered by a small Markdown renderer
  of the page's own, which escapes every character first and allows only headings, paragraphs,
  lists, tables, code, bold and http links; the branch's commit date says when it was written.
- Tasks: the open issues sorted by the protocol's labels into the Queue, Given to workers,
  Claimed, In review, Blocked, Blockers and Epics; "Queue a task" opens an issue labelled todo in
  the shape the Task form writes (Goal, Acceptance, Files likely touched); a select on each queued
  issue gives it to a registered worker by adding its worker:<name> label, making the label when
  it is missing.
- Prompts: "Ask Claude" opens an issue, or comments on one, mentioning @claude, which the
  repository's claude.yml answers on its own Claude token.
- Add workers: the registry under .github/symphony/workers/ is listed, and "Add the worker"
  opens an "Add a worker" issue in the form's shape, which add-worker.yml turns into the pull
  request that registers it; the page never takes a credential for a worker.
- Monitor CI: the latest Actions runs with their outcomes, the open pull requests with the state
  of every check on each head, and four buttons that start the workers, the board, the checks and
  the metrics by workflow_dispatch; a Merge button becomes pressable on a ready pull request whose
  checks have all passed, asks once more, and merges with a merge commit.
- Cost: the cost page reads METRICS.json on the branch metrics (the economics and coordination
  blocks the metrics workflow writes) and sets what the last 30 days cost at API list prices
  beside the flat plan, beside the same tokens under each competitor, and feeds a calculator
  whose inputs the person can change.

## Design decisions

1. A static page that calls GitHub's API as the person, plus a small stateless sign-in service
   through the App's user token. The owner decided this shape on 2026-10-13 (CLAUDE.md, Durable
   decisions: "the control panel is a site page with a small stateless sign-in service acting
   through the App's user token"). Nothing of ours sees the repository's data; the site has no
   server, and the service holds one secret and keeps nothing.
2. Sign in with GitHub first, the token second. The owner, 2026-10-16 09:09 UTC: "OK I
   ABSOLUTELY NEED ONE-CLICK OAUTH GITHUB SIGN AS THE PRIMARY OPTION AS OPPOSED TO FINEGRAINED
   TOKEN". "Sign in with GitHub" is the first and largest control on both pages; it gives a
   user-to-server token of SymphonyBoard, scoped to the App's permissions intersected with the
   person's own access, on the repositories the App is installed on. It needs the sign-in service
   running and the script's SIGNIN_SERVICE and CLIENT_ID set; until then the button is shown but
   cannot be pressed, one line says why, and the token box beneath it stands open. A
   fine-grained personal access token stays as the fallback, folded under "Use a fine-grained
   token instead": it needs nothing deployed and nothing from the App, and it reaches what the
   App's permissions leave out (listing Actions runs and starting a workflow).
3. No Claude token, until 2026-10-18. The page asked for none, held none and sent none; the
   workers run on the token the repository holds as its secret. The owner dropped the rule on
   2026-10-18, saying it was set arbitrarily, for the Tokens page's Add a slot box, which saves
   a pasted token as an organization secret through the App, which then needs organization
   secrets write, granted by the owner. The box is built by the thread that owns the Claude
   tokens, not from the pages described here, and the Apps' privacy statement, which says the
   pages never take a Claude token, is versioned before the box goes live.
4. The GitHub token lives in the browser only: sessionStorage by default (gone when the tab
   closes), localStorage when "Keep me signed in" is ticked, and the tick is off by default so
   that a shared computer forgets. A sign-in for one tab keeps its refresh token in the open
   page's memory alone, never in storage, since a browser brings sessionStorage back with a
   reopened or restored tab and copies it into a duplicated one; that sign-in ends with its
   eight-hour token once its page is gone, closed, reloaded or left for another page such as the
   cost page, and a tab the browser reopens or restores brings the token back for what is left
   of its eight hours (the privacy statement's version 9). A tab reads its sign-in from one
   storage, its own when that holds one, and writes a renewal back to it, so a tab-only sign-in
   never moves into the kept storage, and a new tab-only sign-in or paste leaves the kept one to
   the other tabs. A pasted token is asked about at GitHub before it takes the place of
   anything, and one with a character no token has (a zero-width space a copy brought along) is
   refused unsent. GitHub's refresh tokens are single use, so a browser's tabs renew in turn
   through the browser's lock (navigator.locks): a tab that finds another's renewal stored takes
   it, and where there is no lock a tab refused looks in storage for 22 seconds, past the
   service's 20-second limit, before it signs out, though a tab-only sign-in, whose refresh
   token no other tab holds, signs out at once. Only GitHub's own word for a dead refresh token
   (bad_refresh_token) ends a sign-in; any other failure, of the service or of GitHub, is of the
   moment and leaves it, and Refresh tries again. A token GitHub refuses brings the sign-in box
   back with the reason, unless another tab has stored a newer one, with which the call is made
   once more; a dead sign-in leaves only its own storage, and a tab whose own sign-in ended
   takes up no other until the person signs in, pastes or reloads; any other failure at load
   opens the panel with its message. "Forget the token" drops this tab's sign-in and the one
   kept on the browser, signs out at once every other tab that used the kept one, ends a renewal
   a tab was waiting its turn for unsent, and, for each token of "Sign in with GitHub" among
   them, asks GitHub through the service to revoke it; a sign-in's token that a new sign-in or
   an accepted paste replaces is revoked the same way, and a pasted token is the person's own,
   which only GitHub's settings revoke. A tab that sees another tab keep a different token in
   place of its own asks GitHub whose it is, names that account and says so when it changed.
   One rule holds every call: a call goes out with a token GitHub has named for the page, and
   GitHub is asked whose a token is first where it has not; only while GitHub has named nobody
   for the page, as when its first question failed, do the tab's own tokens (the one it opened
   with, the one the person gave it, and its renewals) go out unnamed, and a token another tab
   kept is named first even then. A write goes out only for the account the page named when the
   write was asked for, or, asked for while the page named nobody, only with the tab's own token,
   so a write meant for one account is never made as another; when the account changed meanwhile
   the page does nothing and says so. The question whose a token is gives up after 20 seconds and
   says so, a sign-in or paste of the tab asks afresh, and a paste kept while the panel stands
   closes it until GitHub names the token. A call refused while a renewal is under way is judged
   once the renewal has ended, since GitHub stops taking the old token once its refresh token is
   spent, and is made again with the renewed token.
5. The sign-in service exchanges the code with PKCE: the page makes a secret for each sign-in,
   sends GitHub its hash, and sends the secret with the code, so a code stolen from an address
   bar is worth nothing to anyone else; the Origin check on top keeps other sites' scripts out.
   The service bounds every request body in bytes, answers only the site's origin, returns only
   the five token fields, and takes an optional rate-limit binding.
6. The issue bodies the page writes are in the exact shape GitHub gives the two issue forms, so
   the existing workflows (add-worker.yml, the board, the workers) read them as if the forms had
   been used, and no workflow changes.
7. Words and named buttons. Every state is a sentence (the summary line, "No open pull
   request.", "Written 3 minutes ago"), every action is a button with a name, and errors say
   what GitHub answered and what to do, so a Claude driving a browser needs no screenshot
   reading.
8. The merge needs two presses and a token with Contents: Read and write; a draft, a failed
   check or a check still running keeps the button off. A wrong merge is the one action on the
   page that cannot be undone.
9. The cost page's price table is kept in the script beside the template's own
   (tools/economics.py) with the date it was read, and every price names its source at the foot
   of the page; where the two tables differ the page says which date each is of.

## The cost comparison

### How each system charges

Read at each source on 2026-10-15 (the Sources section); every row is what the system itself
says.

| System | Where the agents run | Compute | Inference | Who pays |
| --- | --- | --- | --- | --- |
| Symphony | GitHub Actions on the repository's subscription token; people's own sessions | Standard runners, free and unlimited on a public repository; 2,000 minutes a month on Free and 3,000 on Pro and Team for a private one, then $0.006 a minute | One Claude plan for the Actions workers (Pro $20, Max 5x $100, Max 20x $200 a month); past the plan's five-hour and weekly windows, usage credits at API list prices | The repository's owner, one plan |
| An API key in Actions (gh-aw's Claude engine; claude-code-action with a key) | GitHub Actions | The same minutes | Every token at Anthropic's list prices; gh-aw says the subscription token "is not supported" | The key's owner, per token |
| GitHub Copilot coding agent (the Claude and Codex agents on GitHub) | Actions runners under GitHub's service | Actions minutes | AI credits at $0.01 each; a plan includes some (Pro $10 with 1,500, Pro+ $39 with 7,000, Max $100 with 20,000), then metered; Claude at Anthropic's list prices | The Copilot subscriber, per token |
| unsorry | The board, the dispatcher and the reaper in Actions; the agents on volunteers' machines | Free in a public repository's Actions | Each volunteer's own claude -p, Codex or Gemini runs, on their plan or their key | The volunteers |
| OpenAI (openai/codex-action, openai/symphony) | Actions, or a daemon of the user's | Actions minutes, or the host | An OpenAI API key is required; OpenAI's rates | The key's owner |

### The prices

- Claude plans (claude.com/pricing, read 2026-10-15, monthly billing): Pro $20, Max 5x $100,
  Max 20x $200. The allowance is published as a multiple of Free per five-hour window, with
  weekly limits on top, not as a token count; past the limits, usage credits bill at the API
  prices (support.claude.com, "Manage usage credits for paid Claude plans").
- Anthropic's API list prices per million tokens, read from platform.claude.com/docs/en/about-claude/pricing
  on 2026-10-15: input, cache write kept five minutes, cache write kept an hour, cache read,
  output. Sonnet 5.5: 2, 2.5, 4, 0.10, 10. Opus 5.5: 4, 5, 8, 0.20, 20. Fable 5.1: 10, 12.5, 20,
  0.25, 50. Haiku 5.5: 0.10, 0.125, 0.20, 0.01, 0.50.
- Claude Code in Actions on a subscription: "If you authenticate with an OAuth token, runs use
  your Claude subscription instead of API billing" (code.claude.com/docs/en/github-actions).
- GitHub Actions (github/docs, content/billing/concepts/product-billing/github-actions.md at
  commit 12691d2, read 2026-10-15): free and unlimited standard runners on public repositories;
  2,000 minutes a month on Free and 3,000 on Pro and Team for private ones; a Linux 2-core
  runner $0.006 a minute from 2026-01-01.
- GitHub Copilot (github/docs, content/copilot/concepts/billing-and-usage/individuals/billing.md
  and data/variables/copilot.yml at 12691d2; content/copilot/reference/copilot-billing/models-and-pricing.md):
  usage-based since 2026-06-01, AI credits at $0.01, the plans' included credits as above, and
  Claude priced at Anthropic's list prices; third-party coding agents consume Actions minutes and
  AI credits (about-third-party-coding-agents.md).
- gh-aw's Claude engine (github/gh-aw, docs/src/content/docs/engines/claude.md at dc91dbe, read
  2026-10-15): "Claude subscription OAuth tokens such as CLAUDE_CODE_OAUTH_TOKEN are not
  supported".
- OpenAI: openai/codex-action's README requires an API key as a secret.
- unsorry (agenticsnz/unsorry at 029d328b, read 2026-10-15): ADR-004 for the claims on one shared
  branch, reaper.yml and queue-dispatcher.yml for the coordination in Actions, swarm/agent.sh for
  each volunteer's own runs.

### A worked example

The calculator's defaults: 10 runs a day for 30 days, 10 runner minutes a run, and a run of
1,745,000 tokens (20,000 input, 100,000 cache writes at the five-minute rate, 1,600,000 cache
reads, 25,000 output), the shape of a Claude Code run that re-reads a cached context. Cache
writes are priced at the five-minute rate, which an API key gets by default; on a subscription
the cache lives an hour.

| Model | Tokens a run | Tokens a month, 300 runs | Copilot Pro ($10 + 1,500 credits) | Copilot Pro+ ($39 + 7,000) | Copilot Max ($100 + 20,000) |
| --- | --- | --- | --- | --- | --- |
| Sonnet 5.5 | $0.70 | $210 | $205 | $179 | $110 |
| Opus 5.5 | $1.40 | $420 | $415 | $389 | $320 |
| Fable 5.1 | $3.10 | $930 | $925 | $899 | $830 |
| Haiku 5.5 | $0.04 | $13 | $10 | $39 | $100 |

Against those, Symphony's bill for the same 300 runs is the plan alone, $100 a month on Max 5x,
while the runs fit the plan's windows, and $0 of compute on a public repository; on a private
repository on GitHub Free the 3,000 runner minutes exceed the 2,000 included by 1,000, which is
$6 (none on Pro or Team, whose 3,000 cover them), and every row above pays the same minutes. An
API key pays the Tokens a month column; Copilot pays its plan plus the tokens past its credits;
unsorry's volunteers pay the Tokens a month column between them; OpenAI's figure depends on
OpenAI's price list, outside the table. Whether 300 such runs fit a plan's windows is not
published as a token count, so the page says so and gives the tokens' list price as the most the
usage credits could add.

### What the measured figures are

A Symphony repository records what its work cost beside the work: each session's commits carry a
Symphony-Usage line and each Claude run in Actions leaves a usage artifact, and metrics.yml sums
them into METRICS.json on the branch metrics (docs/memory/field-metrics.md). Signed in, the cost
page reads that file as the person and shows the economics block (the pull requests ended and
merged, the tokens by kind, the time at work, the estimate at list prices, the coordinator's
share, the dollars per merged pull request) and the coordination ratios (alone against parallel:
tokens and dollars per merge, latency, throughput, first check passed, commits per merge,
failures per pull request, over 1 where parallel did better), prices the measured tokens under
each competitor, and can hand the measured window to the calculator. The page states the date
the template's table priced the record by (economics.prices_as_of) beside its own.

One difference found while comparing the tables: tools/economics.py prices Sonnet 5.5's cache
reads at 0.20 per million (PRICES_AS_OF 2026-10-06), and Anthropic's page of 2026-10-15 says 0.10;
the page's table has 0.10. The fix to the template is a follow-up pull request of its own (under
Follow-ups).

## Checks and reviews

- The service: `node --test signin/test_worker.mjs`, 15 tests that drive the handler with a fake
  GitHub (the description, the preflight, the exchange with and without a verifier, the refresh,
  the revoke, foreign and malformed origins, bad bodies, the byte bounds, a missing setting, a
  rate-limit binding, GitHub refusing or unreachable); symphony-app's scripts/check.sh runs them
  where node is on the path, as on GitHub's runners (`PYTHON=python3.12 bash scripts/check.sh`
  passed).
- The privacy statement: symphony-start's `bash scripts/check.sh`, 300 tests, passed.
- The site: `python3 -X utf8 tools/build_site.py` builds and `--check-only` reports 0 problems
  (49 pages; the one note is older and about the Beethoven pages' link depth).
- The pages: a Playwright test outside the repositories (the site has no test runner) drives
  both pages against a mocked api.github.com: sign-in with the tick and without, the summary
  line, the board's rendering with a hostile script tag escaped, queueing a task in the form's
  shape with the label todo, giving an issue to a worker, adding a worker in the form's shape,
  starting the workers, the two-press merge with Cancel, a repository without the topic and its
  preselected install link, the cost page's measured rows and calculator, Forget the token, and a
  refused token. It passes against the built pages of 2026-10-16.
- The sign-in as the first way in: a second Playwright file of 112 checks, against a mocked
  api.github.com, a mocked authorize page of GitHub's and a mocked service, with the script's
  two constants patched in. It covers the gate unconfigured on both pages (the button first and
  unpressable, the line saying why, the token box open) and configured (pressable, the token
  folded, nothing sent before the press); one press signing in with PKCE (the verifier hashes to
  the challenge), the state, ?repo= brought back, the tab-only and the kept storage, and the
  cost page as its own callback; GitHub refusing, a wrong state and the service refusing; a
  renewal before the first call; two tabs of a kept sign-in renewing in turn (one renewal), and,
  in a browser with no lock, the refused tab taking the other's renewal; a tab-only renewal
  leaving the kept sign-in alone; a revoked sign-in and a refused pasted token bringing the box
  back; a crafted ?error= link; GitHub's words cut to a line; the 404 on Add with and without
  the sign-in; Forget the token during a renewal; and, from the second review, Forget the token
  reaching another tab at once and at its next call while leaving another tab's own sign-in, a
  tab-only sign-in renewing from the page's memory and asking anew after a reload past its eight
  hours, three failures of the service (502, 500, no answer) keeping the sign-in until Refresh
  renews it, a failure at load other than a 401 opening the panel, a tab-only and a kept paste
  beside a kept sign-in, a copy of a tab never spending its refresh token, Forget's words for a
  pasted token, Back to a sign-in's return address, a 401 on the cost page, a six-second renewal
  with no lock, and a call made again with a token renewed meanwhile; and, from the third
  review, Forget the token while a tab waits its turn to renew (the other tab's renewal made,
  failing before GitHub, and with no lock), a paste with a zero-width space, a kept paste GitHub
  refuses or cannot answer about beside a working sign-in, a Forget in another tab while this
  tab's first answer is on its way on both pages, another account's token kept in another tab, a
  kept sign-in GitHub refused in another tab, Forget with a pasted token kept behind a tab's own
  sign-in, a tab-only sign-in running out mid-load beside a kept one, and, with no lock, a
  tab-only sign-in GitHub will not renew; and, from the fourth review, a write refused because
  another tab kept another account's token (with Sign in with GitHub and with pasted tokens),
  another tab's keep during a load, a call refused during this tab's own renewal (renewed and
  refused), a follow GitHub cannot answer about and a token a call took up before it was named,
  a paste during the first question about a kept sign-in, a paste during its renewal, a paste
  GitHub never answers about, a refused paste beside another tab's keep, a token no request can
  carry on both pages, Forget's words for a tab signed in for itself and for a classic token, a
  page brought back from the back-forward cache, a call refused during another tab's renewal
  with and without the lock, Give's two writes, and a Forget while a renewal is on its way, from
  another tab and from this one; and, from the fifth review, a paste while the page still asks
  about a kept sign-in, a question about a token that GitHub never answers (after a renewal,
  before a second paste of the same token, on the cost page, and about a token another tab kept),
  a refusal far from the token's end with no lock, a kept token no request can carry, Forget
  while a write is on its way and while a write waits for a name, a page that opened naming
  nobody brought back from the back-forward cache, Forget with storage refused, an answer about
  another tab's token after this tab's own paste, a browser with no AbortSignal.timeout, Forget
  with a classic and a fine-grained token pasted, a slow answer and a slow failure on the cost
  page, the late answer of Forget's revoke after a paste, both ways, a token another tab kept
  while the page names nobody, and the page's own renewal while it names nobody; and, from the
  rerun of the earlier rounds' mutants, a tab-only sign-in running out mid-load beside a kept one
  in its last minute. Seventy-nine mutants, one per fix, each fail the check meant for it against
  the fifth round's script, and the panel's earlier checks and the 13 checks of hostile input
  pass with the change.
- Where the checks are kept: OpenSpineConsortium/symphony-app, folder signin/panel-checks/
  (symphony-app#16, merged 2026-10-16), beside the sign-in service. It holds the 112 checks, the
  panel's walkthrough, the 13 hostile-input checks, the 79 mutants and the five reviews' scripts
  and reports, and its README says how to run them again. CI does not run them, since they need
  Playwright with Chromium and a checkout of the site.
- Adversarial reviews, as the handoff requires before a substantive pull request: one of the
  pages, one of the service and the privacy statement, and five of the sign-in as the first way
  in; what each found and what was done:
  - The pages: a loader of one repository could write into the next after a switch (every loader
    now checks the state it started for); the summary stayed at "Reading..." when a read failed
    (it now says what is known and names each failed read); the merge confirmed with a browser
    dialog (now a second press with Cancel); the cost table's wording implied the template and
    the page share one table (each names its own date); the cost page called minutes free on a
    private repository (it reads the repository's visibility and says which); "Keep me signed
    in" was on by default (off); giving an issue to a worker could label the wrong one (scoped);
    an escaped pipe broke a board cell (unescaped in the cell); the issue list's cut at five
    pages, the pull requests' at two and the discovery's at 300 were silent (each says "at
    least"); a board over 1 MB was unreadable through the JSON contents API (read raw); the
    queued task's label was assumed (the answer's labels are checked, and the page says when
    GitHub dropped todo); an archived repository was not said (it is); the Copilot pricing link
    was the wrong page (models-and-pricing.md); a label was made with no colour (one colour for
    worker labels); dead code; a 429 was explained as a 403 (its own words).
  - The service and the statement: the "keep" tick was lost across the OAuth redirect (kept in
    the sign-in state); the cost page could start a sign-in from an unregistered callback (both
    pages are callbacks, and the README says so); the refresh token was kept but unsaid (said);
    two reads were unlisted in the statement (listed); Cloudflare keeps Workers Logs on by
    default (the README's step 2 turns them off, and the statement says the host's logs are off);
    no PKCE (added, required); a failed refresh left the page signed in with a dead token (it
    signs out and says why); the body reader had no byte bound (4,096 bytes, counted as read);
    no rate limit (an optional binding, 429 past it); the statement contradicted itself on what
    the service sees (rewritten); ALLOWED_ORIGIN with a path or a slash broke the check silently
    (normalized, 503 until it is a bare origin); a null body, a code in the URL with no state, a
    non-JSON answer from GitHub and two refreshes in flight each had a wrong answer (each has its
    own); no way to revoke (POST /revoke, pressed by Forget the token); index.html in the
    callback (stripped); GitHub unreachable answered 500 (502 with words).
  - The sign-in as the first way in, 2026-10-16: two tabs renewing one refresh token signed
    each other out (renewals take turns through the browser's lock, look in storage first, and
    look again after a refusal); a renewal could move a tab-only sign-in into the kept storage
    (it is written back where it came from); a 401 on the sign-in's token left the panel up
    with nothing working (the box comes back, and only that tab's sign-in is dropped); a crafted
    link could put GitHub-looking words on the page (said only for a sign-in the tab started,
    and cut to a line); a repository without SymphonyBoard read as missing through the sign-in
    (Add offers the App's install page for it); and smaller ones, the token box not opened after
    a sign-in that came back wrong, a disabled button that changed colour under the pointer, the
    lead's wording. With the fixes, Forget the token revokes every sign-in token it forgets, no
    call goes out with no token, and a call to the service gives up after 20 seconds.
  - The fixes, reviewed again, 2026-10-16, ten findings: Forget the token in one tab left the
    other tabs signed in with the forgotten token (each call reads storage first, and a storage
    event signs out at once a tab whose kept token was forgotten); a tab-only sign-in kept its
    refresh token in sessionStorage, which a browser restores and copies into a duplicated tab,
    so the sign-in outlived its tab and two copies could spend one refresh token (it is held in
    the page's memory alone); a brief outage of the service signed people out (only
    bad_refresh_token does); any failure at load showed the sign-in box (only a 401 or no token
    does; anything else opens the panel with its message); a tab-only sign-in or paste wiped the
    sign-in kept for the other tabs (each touches only its own storage, and a sign-in token it
    replaces is revoked); Forget's words implied a pasted token was revoked (they say it stays
    valid at GitHub and where to delete it); Back after a sign-in warned that its state differed
    (only a sign-in the tab started is warned about); the cost page gave no reason on a 401 (the
    reason is said where the box comes back); with no lock, a renewal slower than 2.5 seconds
    signed both tabs out (the refused tab looks for 22 seconds); and a duplicated tab's renewal
    was the second finding's consequence. Also changed: a call refused because another tab
    renewed the token meanwhile is made again with the new one.
  - The second round of fixes, reviewed a third time, 2026-10-16, eight findings and four
    theories, each finding reproduced in a browser: Forget the token did not stop a renewal
    another tab was waiting its turn for, so the forgotten refresh token could be renewed after
    it (a renewal that finds nothing stored any more ends signed out, and a look for another
    tab's renewal stops there too); a pasted token replaced and revoked the kept sign-in before
    GitHub had seen it, and one carrying a character no token has opened the panel with every
    request failing unsent (the paste is refused with the reason, and GitHub is asked about a
    token before it replaces anything); a Forget in another tab while this tab's first answer
    from GitHub was on its way opened the panel signed in (it stays on the box); a token another
    tab kept in place of this tab's carried it to another account under the old name (the tab
    asks GitHub whose the new token is, names that account and says it changed); the other tabs
    were told the token was forgotten when GitHub had refused it (the words name both); Forget's
    words left out a pasted token kept behind the tab's own sign-in (they name it); a tab whose
    own sign-in ended went on with the sign-in the browser kept for its other tabs (it takes up
    nothing until the person signs in, pastes or reloads); with no lock, a tab-only sign-in
    GitHub would not renew waited 22 seconds for a tab that cannot exist (it signs out at once);
    and the texts said a tab-only sign-in's refresh token went when the tab closed or reloaded,
    where leaving the page for another does it too, and left out that a reopened tab brings its
    token back (both are said now, on the page and in the privacy statement's version 9). Of the
    theories, a sign-in that could open the panel twice went with the third fix; the other
    three, a retried call refused again after two token changes inside one round trip, the
    service's permanent refusals worded as of the moment, and a cost-page answer for a forgotten
    token landing on the hidden panel, were judged not worth their code. The reviewer's
    reproductions pass on the fixed page but two: one asserts the other tabs' words never say
    "forgotten in another tab", which they now say beside GitHub's refusal, and one asks a
    tab-only sign-in to renew after the panel's link to the cost page, which by design it does
    not.
  - The third round of fixes, reviewed a fourth time, 2026-10-16, ten findings and six
    theories, each finding reproduced in a browser, and one rule for the fixes: a call goes out
    only with a token the page has named. A write GitHub refused because another tab kept
    another account's token meanwhile was made again as that account, under the old name (a
    write goes out only for the account the page named when it was asked for, and when the
    sign-in changed meanwhile the page does nothing and says so); a token another tab kept while
    this tab was loading, or one a call took up before the page could name it, was used under the
    old name (GitHub is asked whose a token is before a call carries it, and the look at the
    other tabs' storage names a token a call took up); a call waiting on this tab's own renewal
    went out, after the sign-in ended, with the sign-in kept for the other tabs (it is stopped);
    a follow whose question to GitHub failed kept the old name (it names nobody, says GitHub
    could not be asked, and asks again before the next call); the page named whichever answer
    about a token came last (an answer about a token the page no longer holds names nobody, and
    only the latest opening of the panel counts); a token pasted for this tab while the page
    renewed the sign-in kept for the other tabs revoked that renewal (the renewal is checked and
    written back only in the storage it came from); a paste GitHub never answered about held the
    button until a reload (it waits 20 seconds); a tab whose pasted token GitHub refused said it
    was signed in when another tab kept another token (it stops using the refused token, which
    stays for the person to replace); a stored token no request can carry opened the panel with
    the browser's raw error (the box stays, with the reason and the token box open); and Forget's
    words left out a tab signed in for itself, which keeps its sign-in (they say so, and send a
    classic token to github.com/settings/tokens). Of the theories, two were fixed: a page the
    browser brings back from its back-forward cache missed every storage event meanwhile (it
    looks at storage at once), and a call refused while a renewal was under way ended the
    sign-in, where GitHub stops taking the old token once its refresh token is spent, as its
    documentation of refresh tokens says (such a refusal is judged once the renewal has ended,
    and the call is made again with the renewed token). The window between another tab's write
    and this tab's look closes with the rule; the sign-in box standing while a stored sign-in is
    checked is kept, since a paste in it now wins cleanly; a storage too full to take a new
    sign-in after the old one was removed needs another page of the site to fill it, and was
    judged not worth its code; and a renewal cut off after the service spent the refresh token
    comes with single-use refresh tokens and is out of the page's reach (the next renewal is
    refused, and the tab says so). The reviewer's reproductions pass on the fixed page but one,
    by design: the first variant of its R1 expects a tab whose call GitHub refused during its
    own renewal to be signed out, where it now goes on with the renewed token.
  - The fourth round of fixes, reviewed a fifth time, 2026-10-16, seven findings and seven
    theories, each finding reproduced in a browser, fixed in openspineconsortium.github.io#23: a
    token pasted while the page still asked GitHub about the kept sign-in left the panel open
    under the kept account's name while its calls carried the pasted token (the paste closes the
    panel, and drops what the kept sign-in was still reading, until GitHub names it); one
    question to GitHub about a token that never came back held every later call of the tab, and a
    second paste of the same token with it (it gives up after 20 seconds with the reason, and a
    sign-in or paste of the tab asks afresh); in a browser with no lock, a sign-in GitHub refused
    far from its end waited 22 seconds for a renewal no other tab makes (another tab renews only
    in the token's last minute, so a refusal further than two minutes from the end signs out at
    once); a kept token no request can carry stayed kept for every new tab (it is forgotten once
    the box says so); Forget's words were replaced by the failure of an action on its way (a call
    begun before a sign-out says nothing when it fails); a page that opened naming nobody spoke
    of another tab when brought back from the back-forward cache with nothing changed (it says
    nothing); and, with storage refused, Forget's words left out the pasted token and claimed the
    listed repositories stay (they name the token, and the repositories only where some are
    listed). Of the theories, four were fixed and one went with a finding's fix: a page that
    opened naming nobody sent any token unnamed, one another tab kept included (only the tab's
    own go out unnamed, and a write asked for while the page named nobody goes out only with one
    of them); a browser without AbortSignal.timeout put no time limit on the service or the
    paste's check, so a hung service held the renewal lock for good (a timer of the page's own
    ends such a request); the words of another tab could follow this tab's own Forget and paste
    (they are said only of a token this tab did not choose since the question was asked, and the
    late answer of Forget's revoke likewise says nothing over a sign-in or paste made since);
    Forget named one of GitHub's two token pages for a classic and a fine-grained token pasted
    together (it names both); and the words of another tab after a re-paste of the very token the
    page holds went with the back-forward cache's fix. Two were left: "The sign-in changed" said
    when the change came just before the press, true from the page's view, and a token no request
    can carry taken up mid-session from a tab of an older version, which happens only during a
    deploy. Of three older points it raised, the revoke-failure words now say the listed
    repositories stay and the cost page shows only the latest choice of repository's answer;
    Merge staying armed after "The sign-in changed" is by design. The reviewer's reproductions
    pass on the fixed page, configured and unconfigured, 28 of 28. Running every earlier round's
    mutant again against the fixed page found one that the fourth round's fix had left uncaught:
    with the page's first look at whether this tab's sign-in ended taken out, a tab whose
    sign-in ended still sent nothing to GitHub, since a second look, added in the fourth round,
    stops the call, but it renewed the sign-in its other tabs keep when that one was in its last
    minute; a new check of that catches it, and the page needed no change.
  - The reviewer's own probe script, 13 checks written against the pages before the rewrite
    (repository switching mid-load, a failed read said in words, the 300-issue cut, the merge
    button on a draft and on a failed check, a hostile board, an escaped pipe, the fallback
    without Actions: read, a private repository's minutes, sharing off and a missing record,
    the tab-only token, a dropped todo label, a hostile ?repo=, an archived repository), was
    rerun after the rewrite with its fixtures served as raw text, as the page now reads files,
    and its failed-read check pointed at the summary line, where the failure is now said: all
    13 pass.

## What waits on the owner

The setup is done (2026-10-17, thread "Finish control panel sign-in"): the Worker answers
`{"service":"symphony-signin","routes":["/exchange","/refresh","/revoke"],"keeps":"nothing"}` at
https://symphony-signin.openspineconsortium.workers.dev, the owner sent the Client ID
Iv23liTkIRov2FYN83wD (public, as every GitHub App's is; the client secret was never sent and is
only in the Worker's GITHUB_CLIENT_SECRET), and site #24 set SIGNIN_SERVICE and CLIENT_ID. The
earlier steps, each with its link and what to click, stay in symphony-app's signin/README.md for
a new deployment. A cloud session cannot reach workers.dev or openspineconsortium.com through its
proxy (403); the Worker was read through the web-fetch tool, and no session can sign in as the
owner, so two steps are the owner's:

1. The first sign-in: open https://openspineconsortium.com/symphony/control/ , press "Sign in
   with GitHub", then "Authorize" on GitHub's page; the panel comes back signed in and lists the
   repositories with the topic symphony. A failure says what GitHub or the service answered: a
   redirect_uri error means a callback URL is missing on the App's page, and an
   incorrect_client_credentials error means the Worker's GITHUB_CLIENT_ID or GITHUB_CLIENT_SECRET
   is wrong.
2. Optional: add "Actions: Read and write" to the App's permissions, so that a signed-in token
   lists runs and starts workflows; without it the panel falls back to the default branch's
   check runs and says so, and a fine-grained token needs nothing from the App.

The fine-grained token stays the fallback, under "Use a fine-grained token instead":
https://github.com/settings/personal-access-tokens/new,
the repositories Symphony runs in, and under Repository permissions Actions Read and write,
Checks Read-only, Contents Read and write, Issues Read and write, Pull requests Read and write.

## Follow-ups

- tools/economics.py: Sonnet 5.5's cache-read price 0.20 to 0.10 and PRICES_AS_OF to 2026-10-16,
  the day the page was read again (its footnote: cache hits on Opus 5.5 and Sonnet 5.5 are 0.05
  times the input price, Sonnet 5's 0.1 times), in the pull request after #95; done.
- The fifth adversarial review, of the fourth review's fixes (site commit 75da0b4), ran before
  the constants pull request, and what it found is fixed in openspineconsortium.github.io#23;
  done.
- The constants pull request on the site, once the owner gives the Worker's address and the
  Client ID.
- The Playwright tests live outside the repositories; the site has no test runner, and adding
  one is a proposal, not a change (the writing rule on dependencies).
- The panel's Assistant section (design A of docs/research/control-board-graph.md, the owner's
  choice of 2026-10-17): built on 2026-10-18 as openspineconsortium.github.io#28, its twenty browser
  checks as symphony-app#18 and the Apps' privacy statement version 11 as symphony-start#47, merged
  first; done.
- Not built, by the owner's choice of shape: a hosted server and an account pool. The Tokens
  page's Add a slot box, which takes a pasted Claude token, is built elsewhere since the owner
  dropped the no-token rule on 2026-10-18 (decision 3 above).

## Sources

- The owner's handoff: docs/checkpoints/2026-10-15b/handoff.md, item 7; the shape of the panel:
  CLAUDE.md, Durable decisions (2026-10-13).
- The taxonomy: docs/checkpoints/2026-10-15b/taxonomy/spec.md (section 5.1) and manual.md
  (section 5), for unsorry as the nearest system.
- Prices and terms: claude.com/pricing (2026-10-15); support.claude.com, "Manage usage credits
  for paid Claude plans"; platform.claude.com/docs/en/about-claude/pricing (2026-10-15);
  code.claude.com/docs/en/github-actions; github/docs at commit 12691d2 (2026-10-15):
  content/billing/concepts/product-billing/github-actions.md,
  content/copilot/concepts/billing-and-usage/individuals/billing.md, data/variables/copilot.yml,
  content/copilot/reference/copilot-billing/models-and-pricing.md,
  content/copilot/concepts/agent-capabilities/about-agents/about-third-party-coding-agents.md;
  github/gh-aw at dc91dbe, docs/src/content/docs/engines/claude.md; openai/codex-action's
  README; agenticsnz/unsorry at 029d328b.
- GitHub's refresh tokens: github/docs, content/apps/creating-github-apps/
  authenticating-with-a-github-app/refreshing-user-access-tokens.md, read 2026-10-16: "Once
  you use a refresh token, that refresh token and the old user access token will no longer
  work."
- Platforms: Cloudflare's Workers Logs page (on by default for new Workers, seven days of
  invocation logs) and the rate-limiting binding's page
  (developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/), read 2026-10-16;
  GitHub's App docs on callback URLs (exact match, up to ten, the Setup URL apart) and on
  user-to-server tokens (eight hours, a six-month single-use refresh token), read from
  github/docs on 2026-10-16.
