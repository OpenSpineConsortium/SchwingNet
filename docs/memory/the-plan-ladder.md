What each GitHub and Claude plan unlocks for this template; verified 2026-10-13, the per-plan table in docs/setup/free-or-paid.md and the spending profiles in docs/setup/tiers.md.

A public repository makes GitHub free outright: unlimited Actions on
standard runners, and rulesets, branch protection, required checks and
reviews, code owners, auto-merge and environments on every plan, with
secret scanning, push protection, CodeQL and dependency review free too.
A private repository on GitHub Free, personal or organization, gets
Dependabot, the dependency graph and 2,000 minutes a month, but nothing
that enforces the gate: a ruleset there is saved and not enforced (as
GitHub's settings page shows; the docs say only "not available"). Pro
(personal) and Team (organization) bring the gate back, rulesets with
the required check pinned to GitHub Actions, reviews, code owners,
auto-merge and environments, and 3,000 minutes; Enterprise Cloud 50,000.
In a private repository deployment reviewers, artifact attestations and
merge queue need Enterprise Cloud, and code scanning, SARIF upload,
dependency review, secret scanning and push protection need the paid
add-ons GitHub Code Security and GitHub Secret Protection, which only
Team and Enterprise can buy. Classic protection's push restrictions and
bypass lists belong to organizations, a Free one's only on its public
repositories; push rulesets start at Team,
private repositories. With no payment method stored, the minute quota
is a hard stop, never a bill. GitHub's docs give plan prices only from
2020 (Pro $4, Team $4 a user), not confirmed current.

Claude Code comes with every paid Claude plan on the one usage pool
(five-hour window plus weekly limit): Pro $17 annually or $20 monthly,
Max $100 (5x) or $200 (20x) monthly (more usage, higher output limits
and early access, nothing this template needs), Team
$20 a seat annually or $25 monthly, premium seats $100/$125.
`claude setup-token` works from Pro up, so the @claude and worker
workflows need only the cheapest paid plan. The API credits bundled with
Max and Team are spendable on the API side only and never extend Claude
Code. Keep CI on ubuntu runners: Windows bills at about 1.7x, macOS at
about 10x.
