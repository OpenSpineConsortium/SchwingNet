# Shared memory

The shared memory is docs/memory/, imported into every session through the line `@docs/memory/MEMORY.md` in CLAUDE.md. A claude.ai Project's own memory is private to the account that made it, so anything every account should know goes here instead.

- One fact per file under docs/memory/, named in kebab-case (`how-this-repository-works.md`), with a one-line description as the file's first line.
- One index line per fact in docs/memory/MEMORY.md, in the form `- [title](file.md): one line`. MEMORY.md stays under 200 lines and 25 KB; the limit is this project's own, because an imported file loads whole into every session's context, and Claude Code's guidance for an instruction file is under 200 lines. `scripts/check.sh` fails when a fact is missing from the index or the index names a file that is not there.
- A thread that learns a fact, or finds one wrong, adds or corrects it in the same pull request as the change it learned from. Memory never travels alone and never waits for a later pull request.
- Never a secret, never a token, never a cookie or a key. The checks look for the shapes of common secrets and refuse them.
- What holds only for one piece of work (what was done today, what is left) is a checkpoint (.claude/skills/checkpoint), not a memory.
