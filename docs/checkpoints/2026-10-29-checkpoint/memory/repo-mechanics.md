---
name: repo-mechanics
description: The four repositories, how to check, push, mark ready and merge in each, and the cloud session's limits (no hooks in a multi-repo project, no PR wakes, proxy refusals, billing failures)
metadata:
  type: reference
---

- OpenSpineConsortium/bordercall (private, confidential): README.md and TODO.md on top, schwingcheck/, scanimport/, combinations/, coarse/, holdings/, research_notes/, everything older under archive/. See [[bordercall-state]].
- OpenSpineConsortium/SchwingNet (private, confidential): docs/research/, docs/memory/, docs/checkpoints/ (every handoff), grid/gate.sh (the job words), the board: `git fetch origin +refs/heads/board:refs/remotes/origin/board && git show origin/board:STATE.md`.
- OpenSpineConsortium/symphony-template (internal, not public): the restart pages under docs/research/, grid-accounts.yml (every grid word goes through it), the branch grid (every send's record). It has no board branch.
- OpenSpineConsortium/spine-program (private): synthetic_spine/ and #239; its own CLAUDE.md rules (claim branches claude/<issue>, greg merges).
- A project with several repositories runs none of their hooks: no push guard, no board at session start. Read the board by hand and keep the push rules yourself; never push to a default branch; push by name (`git push -u origin <branch>`).
- Checks: bordercall has no CI; run every suite before a merge (schwingcheck `python3 -m unittest discover -s tests`, 146 tests, about 10 to 25 minutes; `cd archive && python3 -m unittest discover -s tests`; holdings, scanimport, combinations, coarse). SchwingNet's scripts/check.sh only in a throwaway copy (it once left the owner's clone dirty); CI's check and gate jobs are the verdict. symphony-template's check.sh in the clone.
- SchwingNet's pre-push hook runs the beethoven-qa gate and refuses a push while anything is untracked (a stray .githooks/commit-msg counts: work in a git worktree or set it aside); export PATH="$HOME/.pixi/bin:$PATH" first. A docs-only push proves little.
- A SchwingNet PR marked ready needs "## Adversarial review" in its body; mark ready with mcp__github__update_pull_request draft=false in a call of its own after the body edit. Merge with mcp__github__merge_pull_request and expectedHeadSha copied from git, then read main. bordercall's org ruleset wants one approval (mergeable_state "blocked"), yet that merge call merges as greg.
- `gh api -X PATCH repos/O/R/pulls/N -F body=@file` sets a long PR body. GraphQL is refused.
- PR subscriptions did not deliver events in this project: poll a PR's checks yourself before marking ready or merging.
- The proxy of the built-in environment refuses arxiv.org, huggingface.co and most publishers; see [[cloud-environment]]. An Actions job that fails unstarted with "recent account payments have failed or your spending limit needs to be increased" is billing, not code: greg raises it at https://github.com/organizations/OpenSpineConsortium/settings/billing.
- A page that declares a connector (the textbook door) cannot be published from a cloud thread; greg publishes it from his own computer. docs.yml in SchwingNet and symphony-template runs only when greg starts it.
- Workflow fan-outs run few agents at a time on the 4-CPU container, and a usage limit can stop them mid-run; missing votes can read as "refuted", so read the failures list.
- SchwingNet's Dependabot action bumps fail the gate when they touch beethoven-qa's kit files (automerge.yml, rulesets.yml, standards.yml) and standards when they rewrite `@v7`: land only non-kit hash pins in a PR of your own, close the bump with the reason (#425, #426, #449). Editing gate.yml makes the gate prove every module (about 46 min). Branch deletion is refused by the proxy (403); give greg the branches page link.

**Why:** each line cost a thread time once.
**How to apply:** read before the first push or merge in a new session.
