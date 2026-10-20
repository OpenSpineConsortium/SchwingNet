# What each dollar buys: the three profiles of this template

The template's files are the same at every price. What changes with money
is which switches GitHub will enforce and how much Claude usage the
accounts have, so an adopter picks a profile, flips the named settings,
and spends nothing that does not buy a named feature. Every number below
was verified against GitHub's and Anthropic's own pages on 2026-10-09,
and again on 2026-10-13, when docs/setup/free-or-paid.md tabled every
GitHub feature the template leans on, per plan, from GitHub's docs;
what could not be verified is marked so. Prices move: when a decision
hangs on one, read the linked page, not this file.

## The facts the ladder stands on

- GitHub Actions on standard runners is free without limit in public
  repositories and on self-hosted runners, on every plan. Private
  repositories draw on included minutes: 2,000 a month on Free (personal
  and organization), 3,000 on Pro and Team alike, 50,000 on Enterprise
  Cloud, the one large jump in the ladder
  (https://docs.github.com/en/billing/reference/product-usage-included).
- With no payment method on file, private-repository Actions stop at the
  quota: a hard cap, never a surprise bill. Larger runners are blocked
  outright. A repository that never names a larger runner and an account
  that never stores a card cannot spend a dollar on Actions
  (https://docs.github.com/en/billing/concepts/product-billing/github-actions).
- Overage, where a card exists, is per-SKU: Linux 2-core $0.006 a
  minute, Windows $0.010, macOS $0.062. The template pins ubuntu runners
  everywhere; keep it that way.
- Branch protection and rulesets are free on public repositories and
  need Pro (personal repositories only), Team or Enterprise on private
  ones; GitHub's docs give Pro's and Team's price, $4 a month and $4 a
  user, only from 2020, so every $4 below is that price, unconfirmed
  since. On a Free private repository a ruleset can be written but is
  not enforced, as GitHub's settings page shows rather than its docs
  say, and the UI does not make that obvious (https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets).
- Classic branch protection's push restrictions and bypass lists belong
  to organizations only: a Free organization's public repositories, or
  every repository on Team and Enterprise Cloud. A personal account
  never gets them at any price; its rulesets, from Pro on a private
  repository, still restrict updates, creations and deletions. Push
  rulesets (blocking by path, size, extension across a fork network)
  start at Team, private repositories; organization-wide
  rulesets reached the Team plan in June 2025
  (https://github.blog/changelog/2025-06-16-organization-rulesets-now-available-for-github-team-plans/).
- Claude Code is in every paid Claude plan, from Pro up, on the same
  usage pool as the apps: a rolling five-hour window plus a weekly
  limit. Pro is $17 a month billed annually or $20 monthly; Max is $100
  (5x) or $200 (20x) monthly only and buys usage, higher output limits
and early access, never a feature this template needs; Team
  is 2 to 150 seats at $20 a seat annually ($25 monthly), premium seats
  $100/$125 with 5x usage, plus SSO and central billing
  (https://claude.com/pricing).
- `claude setup-token` works from Pro upward: a one-year OAuth token for
  CI, so the @claude and worker workflows (docs/setup/claude-action.md)
  run on the cheapest paid Claude plan with no API billing
  (https://code.claude.com/docs/en/authentication).
- The monthly API credits bundled with Max and Team are spendable only
  on the API and Console side. They never extend Claude Code or app
  limits, so they do not change this ladder; value them as an API-side
  bonus or not at all.

## Profile 1: economy, one person, about $17 a month all in

GitHub Free with the repository public, Claude Pro. The GitHub bill is
zero by construction: public means unlimited standard-runner Actions and
enforced branch protection and rulesets for free, and storing no payment
method makes the ceiling hard. Everything in this template runs whole:
the board, the checks, the protocol gate, tidy, the hooks, @claude and
the worker on the Pro account's setup-token. Set the branch rules of
docs/setup/github.md, skip nothing.

A private repository on Free costs nothing either but loses enforcement:
protection rules sit unenforced and the hooks and the protocol check in
CI become the only fences. That is the one place the $4 Pro plan earns
its keep: enforced protection on a personal private repository, plus
3,000 included minutes, the same allotment Team gets. The board's cron
fallback costs about 120 of them a month (four runs a day, one billed
minute each); the event triggers carry the real updates.

What this profile cannot have at any price on a personal account:
classic protection's push restrictions and bypass lists. The push-guard
hook and the protocol check stand in for them, honestly but client-side.

## Profile 2: team, two to five people, from about $48 a month for two

GitHub Team ($4 a person a month) on an organization, Claude Team
standard seats ($20 a seat a month annually), or Claude Max for a solo
power user who only needs more usage, not seats. For two people that is
$8 GitHub and $40 Claude a month; each further person adds $24. What the
money genuinely buys, none of it replicable below this rung:

- Enforced protection on the organization's private repositories, and
  push restrictions with bypass lists: the server, not a hook, refuses
  the push to main and the push to another account's claim branch.
- Push rulesets on private repositories, and one organization-wide
  ruleset protecting main and the board branch across every repository
  the project ever adds.
- Claude Code on every Team seat under one bill and SSO, each account
  with its own worker routine and its own label on the board; premium
  seats (5x) only where a seat actually hits the weekly limit.

The multi-account machinery of this template, OWNERSHIP.md, per-account
labels, the coordinator routine, is built for exactly this rung.

## Profile 3: scale, when an enterprise is already the answer

GitHub Enterprise Cloud adds the capacity jump (50,000 included minutes,
16.7x Team), enterprise-level rulesets above organizations, and internal
repositories with push rulesets. Claude Enterprise adds the shared,
administered workspace, priced on 2026-10-13 at $20 a seat a month
billed annually plus usage at API rates, so its Claude Code is billed
by use where every other rung runs on a plan's limits; this profile is
a direction, not a quote. Two
things stay true at this rung: the repository remains the only shared
plane that is versioned, reviewed and machine-checked, so the template
loses none of its point; and what native sharing buys over it is the
removal of one cost this template accepts everywhere, the latency of a
git fetch between a change and every session seeing it.

## Not verified, decide with the page open

Since 2026-10-13 docs/setup/free-or-paid.md settles merge queue (an
organization's public repositories, or private ones on Enterprise
Cloud), code owners (public, or private from Pro), and secret scanning
and push protection (free on public repositories, the paid add-on
GitHub Secret Protection on private ones, Team and up). Still open:
the current price of GitHub Pro and Team, Enterprise Cloud's price, and
Claude Enterprise's shared-Project feature set. The board, the claim
protocol and the required check already give this template a working
merge discipline without the merge queue.
