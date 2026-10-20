---
name: checkpoint
description: Use at the end of a session, or before handing work to another account or session, to record where things stand in .claude/session.md and in the marker section of CLAUDE.md.
---

# Write a checkpoint

A checkpoint is what the next session reads first. It is two things: `.claude/session.md`, the whole state of the work, and the block between `<!-- cswap:checkpoint:begin -->` and `<!-- cswap:checkpoint:end -->` at the end of CLAUDE.md, the durable part. The markers are cswap's, so `cswap checkpoint write` and this skill update the same block.

1. Collect from the conversation: what was completed, where things stand now (the branch, the pull request, what is pushed and what is not), what remains, and every line tagged `Decision:` or `Constraint:`, word for word.
2. Write `.claude/session.md` with these sections, in this order: `# Session checkpoint`, `## Completed work`, `## Current state`, `## Remaining tasks`, `## Decisions`, `## Constraints`. Plain prose and short lists; under 16 KB; ASCII and LF; no secrets, no tokens, no tool output, no logs. Say plainly what is not known rather than guessing.
3. Write the marker section to a scratch file outside the repository, `section.md`: the whole block, from the begin marker to the end marker, shaped as CLAUDE.md has it now: the heading `## Session checkpoint (kept by cswap)`, a blank line, the intro sentence unchanged, a blank line, then `### Durable decisions` and `### Constraints`, each followed by one `- ` line per item, or `- (none recorded)`. Decisions and constraints from earlier checkpoints stay unless a later one reverses them.
4. Refresh CLAUDE.md in place: `python3 tools/marked_section.py CLAUDE.md < section.md`. The helper replaces what is between the markers and touches nothing else. It refuses a file with one marker and not the other, which means someone edited the block by hand: fix the markers first rather than forcing anything.
5. Run `bash scripts/check.sh`; it fails when the marker pair is missing or doubled.
6. Commit both files on the issue's branch, in the pull request of the work, and push it by name, as the claim skill pushes: `git add .claude/session.md CLAUDE.md`, `git commit -m "Checkpoint"`, `git push origin claude/N`, N being the issue's number. A push that names no branch goes where git's `push.default` sends it: under `matching` it also sends a local main that has moved ahead of origin's, and under `nothing` it sends nothing at all. A checkpoint reaches the default branch by pull request like everything else.

What belongs here and not in docs/memory/: the state of one piece of work. A fact that holds for the project as a whole is a memory (.claude/skills/remember). What a piece of work found out is research, under docs/research/ (.claude/rules/research.md), committed before the checkpoint, which names the file and does not repeat it.
