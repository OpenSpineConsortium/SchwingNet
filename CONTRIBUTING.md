# Contributing

Every contributor here works to the same rules, a person or a Claude session alike, and whoever owns the project is held to them too. Most of them GitHub enforces, so a change that breaks one cannot merge; the rest are expected of everyone and checked by review. symphony-template's docs/research/same-ci-for-every-contributor.md says which is which in each of OpenSpineConsortium's repositories, and why.

## What GitHub enforces

- Every change reaches the default branch by pull request: the ruleset "Protect the default branch" refuses a direct push, a forced push and deleting the branch.
- The required checks "check", "gate" and "standards (every group green)" pass, "check" taken only from GitHub Actions; gate and standards are beethoven-qa's definition of done for the package under src/schwingnet. "check" is `bash scripts/check.sh` (the documents, the memory index, the vendored protocol held to its record, the workers, the agents, the lessons of docs/learn/ and the tests), the claim protocol for a `claude/<issue>` pull request (docs/agents/PROTOCOL.md) and the review record below. Run `bash scripts/check.sh` before you push, as CI runs the same script.
- A pull request marked ready carries a section headed `## Adversarial review` in its body: what a reviewer who wanted the change to fail checked, by reading it or by running it, what they found and what was fixed. It is at least a sentence; "LGTM" does not count. The pull request template has the heading. A draft, a bot's pull request (Dependabot, a GitHub App, a workflow's own token), one from a branch a workflow or a script writes (crowd/setup, symphony-protocol/, symphony/, drive/sync) and one opened before 2026-10-22 05:00 UTC are not asked for one. Editing the body re-runs the check; "Re-run" on the old run reads the body as it was, so edit the body instead, or push.
- Where the organization adds rulesets of its own, they apply on top: in OpenSpineConsortium, "Require owner approval to merge" asks one approval, given after the last push, of a pull request from anyone but an organization owner.

## What everyone is expected to do

- One change, one pull request, from the branch of its own issue (`claude/<issue>`, claimed as docs/agents/PROTOCOL.md says).
- The review above is adversarial: someone, or a second session, other than the author's first pass, tries to make the change fail before it is marked ready.
- What you find out is committed under docs/research/ with its line in docs/research/README.md, in the pull request of the work it came from (.claude/rules/research.md).
- A fact every later session should know becomes one file under docs/memory/ with its index line (.claude/rules/memory.md).
- Nothing of this project is copied to a public place before the provisional is filed (docs/project.md).
- Plain prose, ASCII and LF, no new dependencies, no secret, token or credential anywhere (.claude/rules/writing.md).
