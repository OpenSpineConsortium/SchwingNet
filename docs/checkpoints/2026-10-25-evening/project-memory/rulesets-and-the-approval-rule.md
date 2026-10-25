---
name: rulesets-and-the-approval-rule
description: What holds a merge in symphony-template and SchwingNet as of 2026-10-25 evening: the organization ruleset "Owner OK" (check owner-ok), each repo's "Protect the default branch" ruleset and its bypass list
metadata:
  type: project
  modified: 2026-10-25T19:48:24.263Z
---

Read from the rulesets API on 2026-10-25 ~19:45 UTC (gh api repos/OpenSpineConsortium/<repo>/rulesets works; org-level paths are refused).

- Organization ruleset "Owner OK" (id 25710532, on both repos, no bypass actors) requires the check run `owner-ok` on the default branch. The check comes from .github/workflows/owner-ok.yml in each repo: a pull request whose author administers the repo (the owner and every session, since sessions open PRs under the owner's login) deploys to environment owner-self and passes at once; another author's waits in environment owner-ok for the owner's Approve tap (GitHub Mobile). Drafts start no run.
- SchwingNet "Protect the default branch" (id 25494231): required checks check, gate, standards (every group green), owner-ok; required approving reviews 0; bypass actors OrganizationAdmin and EnterpriseOwner in pull_request mode (the owner's change of 18:36 UTC, so a merge made with the owner's sign-in can go in before checks finish; use only on the owner's words).
- symphony-template "Protect the default branch" (id 24827932): required checks check and owner-ok; approving reviews 0; no bypass actors.

**Why:** the owner's standing rule is "merge once green; if the org approval rule blocks, tell me to tick the bypass box". Knowing which ruleset holds a PR tells a thread whether to wait for a check or ask the owner.

**How to apply:** before reporting a held merge, read the head's check-runs (repos/.../commits/<sha>/check-runs); a PR blocked only by a running `gate` or `check` is not held by the approval rule. Related: [[symphony-standing-merge-permission]].
