---
name: remember
description: Use when a session learns a fact every account should know, or finds a recorded fact wrong, to add or correct it in docs/memory/ in the same pull request as the change.
---

# Add or correct a memory fact

The shared memory is docs/memory/: one fact per file, one index line per fact in docs/memory/MEMORY.md, which CLAUDE.md imports into every session. The rules are in .claude/rules/memory.md; this is the procedure.

1. Decide whether it is a fact or a checkpoint. A fact holds for the project as a whole and would still be true next month: where something lives, why a choice was made, what a system refuses. Where today's work stands is a checkpoint (.claude/skills/checkpoint), not a memory.
2. Look for it first: `grep -ril` with a word from the fact over docs/memory/. A fact that exists is corrected in its own file, never duplicated in a new one.
3. For a new fact, pick a kebab-case file name that says what the fact is about (`how-this-repository-works.md`, `why-the-board-is-a-file.md`) and write the file: the first line is a one-line description, the rest is the fact in plain prose that says why, with the issue or pull request it came from named at the end. ASCII and LF; no secret, no token, no key.
4. Add its index line to MEMORY.md, in the form `- [title](file-name.md): one line`, in alphabetical order of file name. For a corrected fact, fix the index line when the one line changed. MEMORY.md stays under 200 lines and 25 KB, this project's own limit (.claude/rules/memory.md says why); when it nears the limit, facts that no longer hold go, with their files, by pull request.
5. Run `bash scripts/check.sh`: it fails when a file under docs/memory/ is missing from the index, when the index names a file that is not there, or when something looks like a secret.
6. Commit it in the same pull request as the change the fact came from, with one sentence in the pull request saying what was learned. Memory never travels alone.
