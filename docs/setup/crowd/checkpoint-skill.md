---
name: checkpoint
description: Use at the end of a session, or before handing work to another account or session, to post where things stand as a checkpoint comment on the session's pull request; in crowd mode a checkpoint is never committed.
---

# Write a checkpoint

In crowd mode a checkpoint is a comment on the session's pull request, never a commit: many people work here at once, and a checkpoint kept in the tree would collide between their pull requests and reach every session. The next session on the same pull request reads the latest comment whose first line is `# Checkpoint`.

1. Collect from the conversation: what was completed, where things stand now (the branch, the pull request, what is pushed and what is not), what remains, and every line tagged `Decision:` or `Constraint:`, word for word.
2. Write the checkpoint to a scratch file outside the repository, such as `/tmp/checkpoint-<pr>.md`, where no commit can pick it up: the first line `# Checkpoint`, then the sections `## Completed work`, `## Current state`, `## Remaining tasks`, `## Decisions` and `## Constraints`, in that order. Plain prose and short lists; under 16 KB; ASCII; no secrets, no tokens, no tool output, no logs. Say plainly what is not known rather than guessing.
3. Post it on the pull request. Locally: `gh pr comment <pr> --body-file /tmp/checkpoint-<pr>.md`. In a cloud session, whose GitHub proxy refuses gh's pull request commands: `gh api repos/{{REPO}}/issues/<pr>/comments -F body=@/tmp/checkpoint-<pr>.md`.
4. Leave .claude/session.md and the block between the cswap markers in CLAUDE.md as they are: the required check fails a pull request that changes either while crowd mode is on.

A fact that holds for the project as a whole, beyond this piece of work, is a memory: add it with the remember skill (.claude/skills/remember), in the pull request of the work.
