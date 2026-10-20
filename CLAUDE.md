# SchwingNet

This repository is a Claude project kept as files: its instructions, its goal, its shared memory and its board live here, and Claude Code reads them in every session, local or cloud. The repository is the source of truth for every Claude session and every account; a claude.ai Project only links it, its own fields stay blank, and Claude Code loads this file and what it imports at the start of every session, a Project's thread and a cloud session opened on the repository alike.

## Read first

- The goal, the scope and who owns what, loaded into every session by this line: @docs/project.md
- How work is claimed, done in the open and finished, loaded the same way: @docs/agents/PROTOCOL.md
- Who works here: every session, routine and worker in GitHub Actions is a worker under a name of its own, labelled worker:<name> (docs/agents/WORKERS.md). A session's name is the GitHub login of the person it works for, unless its environment sets SYMPHONY_WORKER; a routine's or a worker in Actions' is the one its prompt gives.
- The board: the file STATE.md on the branch `board`, rewritten by the board workflow from the open issues, the claim branches and the pull requests. It lives on another branch, which no import reaches: read it with `git fetch origin +refs/heads/board:refs/remotes/origin/board && git show origin/board:STATE.md`, the form /board uses, since `git fetch origin board` updates no remote-tracking branch in a clone made for one branch, as a cloud session's is; the session hook prints it at the start of every session, and docs/agents/STATE.md on main only describes it.

Before any work: fetch, read the board, check the claim on the issue you mean to take. One issue, one branch `claude/<issue>`, one pull request.

## Shared memory

@docs/memory/MEMORY.md

A fact worth keeping is one file under docs/memory/ with one index line in MEMORY.md, added in the same pull request as the change it came from.

## Conventions

- The board first (.claude/rules/board.md): fetch, read the board (STATE.md on the branch `board`) and PROTOCOL.md, check the claim; never push to another worker's branch; never force-push the default branch or any branch that is not your own claim. A hook refuses the pushes this rule forbids, and /board (.claude/commands/board.md) reprints the whole board mid-session.
- Memory (.claude/rules/memory.md): one fact per file, a kebab-case name, a one-line description first, one index line; never a secret.
- Writing (.claude/rules/writing.md): plain prose that says why, short functions, names that read as English, no emoji, ASCII and LF, no new dependencies; tag a durable fact in conversation as Decision: or Constraint: so a checkpoint keeps it.
- Research (.claude/rules/research.md): what a session finds out goes under docs/research/, one file or folder per topic that opens by naming its source, with a line in docs/research/README.md, in the same pull request as the work and before its checkpoint; a handoff under docs/checkpoints/ points to it and never carries it.
- Skills: .claude/skills/claim, .claude/skills/remember and .claude/skills/checkpoint are the three procedures, in the order a piece of work meets them; .claude/skills/drive-organize (a OneDrive sorted into projects, read through Microsoft Graph under the owner's own Microsoft sign-in), .claude/skills/lens-review (several reviewers on one Word document) and .claude/skills/notebook (drive files held together as a notebook in a repository of its own, never moved) are run when the owner asks.
- The block at the end of this file, between the cswap markers, is rewritten by the checkpoint skill and by `cswap checkpoint write`; do not edit it by hand.

## Checks

Run `bash scripts/check.sh` before opening or updating a pull request. CI runs the same script as the check named "check", and the default branch takes only pull requests that pass it.

<!-- cswap:checkpoint:begin -->
## Session checkpoint (kept by cswap)

Read `.claude/session.md` at the start of a session: it holds the completed work, the current state and the remaining tasks. Tag durable facts in conversation as `Decision:` or `Constraint:` so the next `cswap checkpoint write` keeps them.

### Durable decisions
- (none recorded)
### Constraints
- (none recorded)
<!-- cswap:checkpoint:end -->
