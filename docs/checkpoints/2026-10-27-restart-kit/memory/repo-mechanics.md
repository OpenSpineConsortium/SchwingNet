---
name: repo-mechanics
description: The three repositories, how to check, push, mark ready and merge in each, and the cloud session's limits (no hooks in a multi-repo project, no PR wakes, Workflow concurrency 2, proxy refusals)
metadata:
  type: reference
---

- OpenSpineConsortium/bordercall (private, under SchwingNet's confidentiality until the filing): top level is README.md (the exact Bayes rule) and TODO.md; everything older under archive/ since bb86584. See [[bordercall-state]].
- OpenSpineConsortium/SchwingNet (private, confidential): docs/research/, docs/memory/, docs/checkpoints/ (every handoff), grid/gate.sh (the job words), the board: `git fetch origin +refs/heads/board:refs/remotes/origin/board && git show origin/board:STATE.md`.
- OpenSpineConsortium/symphony-template (internal, not public): the restart pages under docs/research/, grid-accounts.yml (every grid word goes through it), the branch grid (every send's record). It has NO board branch.
- A project with several repositories runs none of their hooks: no push guard, no board at session start. Read the board by hand and keep .claude/rules/board.md's push rules yourself; never push to a default branch.
- Checks: symphony-template `bash scripts/check.sh` in the clone. SchwingNet's check.sh only in a throwaway copy (it once left the owner's clone dirty), with beartype, icontract and pydantic in a venv; CI's check and gate jobs are the verdict for the pixi steps. SchwingNet's required checks: check, gate, standards, owner-ok. bordercall has no CI; run `cd archive && python3 -m unittest discover -s tests` (222 tests).
- SchwingNet's pre-push hook runs the whole beethoven-qa gate and refuses a push while anything is untracked (a stray .githooks/commit-msg counts: set it aside). beethoven-qa 10.0.0 (SchwingNet #413) proves only the modules a change reaches and reads pyproject.toml by key, so an unproven entry reaches nothing; pixi.toml, pixi.lock, vendor/ or another pyproject key re-proves every module (30 to 45 min). Batch fixes into one push; export PATH="$HOME/.pixi/bin:$PATH" first.
- A SchwingNet PR marked ready needs "## Adversarial review" in its body; mark it ready in a call of its own after the body edit (`gh api -X POST repos/OpenSpineConsortium/SchwingNet/pulls/N/ccr/ready_for_review`; GraphQL is refused in sessions). Its symphonyboard auto-merge then merges once green. Merge others with the head sha copied from git, then read main.
- beethoven-qa's org ruleset "Require owner approval to merge" is passed with `gh api -X PUT .../pulls/N/merge -f sha=<head>` on the standing permission.
- subscribe_pr_activity answered "Could not subscribe" in this project (2026-10-26): poll a PR's checks yourself before marking ready or merging.
- Workflow fan-outs run 2 agents at a time on the 4-CPU container; a session limit (2026-10-26 01:00 UTC) killed 15 of 47 agents mid-run, and missing votes can read as "refuted": size fan-outs and read the failures list.
- The proxy refuses arxiv.org, docs.github.com, huggingface.co and most publishers, GitHub's HTML pages, GraphQL and branch deletion; an Actions job that failed unstarted with "recent account payments have failed or your spending limit needs to be increased" is billing (2026-10-26 21:00 to 2026-10-27 03:10 UTC), not code: the owner raises it at https://github.com/organizations/OpenSpineConsortium/settings/billing.
- A page that declares a connector (the textbook door) cannot be published from a cloud thread; the owner publishes it from the owner's computer.
- docs.yml in SchwingNet and symphony-template runs only when the owner starts it.

**Why:** each line cost a thread time once.
**How to apply:** read before the first push or merge in a new session.
