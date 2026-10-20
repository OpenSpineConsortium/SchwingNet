# The coordinator prompt

The coordinator keeps the queue, the claims and the memory tidy, and most of it is code. The board's own run, on the repository's own token, releases idle claims and tells open work that overlaps (docs/agents/WORKERS.md); .github/workflows/coordinator.yml plans epics, settles blocked tasks and integrates finished epics with Claude, on the repository's Claude token. This page is the rest, the part that needs judgement and no event: splitting requests into issues and tidying the shared memory. The coordinator workflow runs it every week where the secret CLAUDE_CODE_OAUTH_TOKEN is set (docs/setup/claude-action.md), so a repository that holds the token needs no routine for it. The coordinator comments, labels, opens issues and opens pull requests; people merge. It never force-pushes and never touches a branch a worker claimed.

## As a routine

A repository that holds no Claude token, as one in crowd mode never does (docs/setup/crowdsourcing.md), runs this prompt as a routine on one account instead. A routine is a saved prompt on one claude.ai account that runs on a schedule, on a repository's pull request events, or when something POSTs to its API trigger with its bearer token. Make it inside that account's Project (docs/setup/claude-project.md), not on the routines page: open the Project's own conversation, paste the short prompt below and ask for the schedule ("run this every day"). It then runs as threads of that Project, each from a fresh clone of the Project's repository, and shows on the Project's Routines tab, where a stopped routine shows too (docs/setup/github.md). A routine made at claude.ai/code/routines, outside the Project, runs on its own and not as a thread of it. Every thread of the routine clones {{DEFAULT_BRANCH}}, where docs/agents/STATE.md only describes the board, which is why the full prompt's first step fetches the branch `board` and shows the file.

A schedule is all it needs: the releases and the overlaps no longer wait for it. An API trigger is there for a repository that wants the routine woken the moment the board moves, and only while every writer of the repository is you: its address and its bearer token have to be repository secrets, which any writer's workflow can read, and each fire runs the routine on that account's usage. docs/start/team.md, step 1, takes those secrets out before anyone else gets Write.

- The API trigger, only where every writer is you: copy its address and its bearer token into the repository secrets COORDINATOR_TRIGGER_URL and COORDINATOR_TRIGGER_TOKEN (docs/setup/github.md). .github/workflows/board.yml fires it only when a run changed the board, never when the board came out unchanged, so the routine's own labels and comments, each of which starts a board run, do not call it back in a chain. An API trigger takes at most 30 fires an hour per routine and 100 an hour per account; a busy hour loses the rest, and the next scheduled run catches up.
- A schedule, daily or hourly: the floor that splits requests and tidies memory even when nothing happens on GitHub.

## The prompt

The short prompt below is what the weekly run of the coordinator workflow passes, and what a routine's own prompt is, pasted once, as it stands; {{REPO}} is already this repository's name. Every run reads the full prompt, the last block on this page, from {{DEFAULT_BRANCH}}, so a change to it reaches the next run once its pull request merges, and nobody pastes it again.

```
You coordinate the repository {{REPO}}. Run `git fetch origin {{DEFAULT_BRANCH}} && git show origin/{{DEFAULT_BRANCH}}:docs/agents/routines/coordinator.md` and do what the last fenced block of that page says, exactly and nothing else. Read it again on every run, since it changes by pull request.
```

The full prompt, which every run reads from here:

```
You coordinate the repository {{REPO}}, which is a Claude project kept as files. First read the board: run `git fetch origin +refs/heads/board:refs/remotes/origin/board && git show origin/board:STATE.md`. The board is the file STATE.md on the branch board; docs/agents/STATE.md on {{DEFAULT_BRANCH}} only describes it, and before the first board run the branch does not exist yet, in which case there is no board and you read the open issues and pull requests directly. Then read CLAUDE.md, docs/agents/PROTOCOL.md (how work is claimed), docs/agents/WORKERS.md (who works here) and the open issues and pull requests. The board's own run releases idle claims and tells open work that overlaps, so leave both to it. Then do only the following, and nothing else.

1. Split new requests into issues. An issue or a comment that asks for more than one piece of work becomes one issue per piece, each with a goal, an acceptance line and the files likely touched, labelled todo; link each to where the request came from. A request whose pieces meet at interfaces, so that they need a plan before anyone starts, gets the label epic instead, and the coordinator workflow plans it into tasks for the workers; where the repository holds no Claude token, no workflow plans it, so split it into issues as above, writing each interface where two pieces meet into both, and leave the label epic off. Leave alone an issue labelled epic, claimed, in-review, proposed or drive, or one that a worker's label names: proposed and drive are the drive organizer's, whose work waits for a person to accept it (docs/research/drive-organizer.md).

2. Tidy the shared memory. When docs/memory/MEMORY.md nears 200 lines or 25 KB (this project's own limit: the file loads whole into every session's context, as .claude/rules/memory.md says), or a fact there is contradicted by a merged change, open one pull request that corrects or removes the facts and their index lines, with one sentence per fact saying why. Never commit to the default branch directly.

Rules: never force-push; never push to a branch a worker claimed; never close an issue that is not done; never merge; never hold a credential or a token, and never write one anywhere. Write plain prose that says why, with no emoji. When nothing needs doing, do nothing and say so in one line.
```
