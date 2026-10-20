# Prompts to paste

Each block is one message for a Claude Code session on the repository: `claude` in your clone, a cloud session at https://claude.ai/code, or a thread of the account's Project, itself a cloud session. Every session already reads CLAUDE.md, the protocol, the memory index and the board, so the prompts stay short. Put the issue's number for N, the repository for ORG/NAME and a worker's name for `<name>`. No prompt needs to say whose claim a session makes: it claims under your GitHub login, or under the name SYMPHONY_WORKER gives where its environment sets it ([docs/agents/WORKERS.md](../agents/WORKERS.md)).

## Work

**Claim the next issue,** when one session works at a time; it takes what the board's Given to workers section gives you first, then an unclaimed blocker, then the lowest-numbered unclaimed issue in the Queue; of the blockers and the Queue only one that fits your area when you registered one, and never an epic, which the coordinator plans, or an issue labelled blocked:

```
Read the board, take the next issue as docs/agents/routines/worker.md's steps 2 to 5 say, claim it with the claim skill and carry it to a ready pull request; work on the branch claude/<issue>, not this session's own branch. If the push of claude/<issue> is refused, another session holds it: take the next one. Do not merge.
```

**Claim issue N,** when several sessions run at once, so none waits on a refused push:

```
Claim issue N with the claim skill and carry it to a ready pull request, as docs/agents/PROTOCOL.md says; work on the branch claude/N, not this session's own branch. If the push of claude/N is refused, another session holds the issue: say so in one line and stop. Do not merge.
```

**Add this line in a cloud session,** a Project's thread or a routine's run included, since each is one and its GitHub proxy refuses gh's GraphQL commands:

```
gh issue and gh pr are refused here, so add the labels, post the plan and open the draft pull request with your GitHub tools or gh api (repos/ORG/NAME/issues/N/labels, repos/ORG/NAME/issues/N/comments, repos/ORG/NAME/pulls). Mark the pull request ready with your GitHub tool update_pull_request (draft false), not gh api, which cannot change a draft; if you have no such tool, comment "finished; ready to mark" on the pull request and stop before you delete the claim file.
```

**Run a worker once,** to see what a routine will do before you schedule it:

```
Do what the full prompt in docs/agents/routines/worker.md, its last block, says, once, as it stands, as the worker <name>.
```

**Make a routine,** in the account's Project conversation, so it runs as the Project's threads. Register it first with the "Add a worker" form at https://github.com/ORG/NAME/issues/new?template=worker.yml, "routine" under Where it runs and a name after its job, never your login; the form's answer on the issue is the short prompt from docs/agents/routines/worker.md with that name filled in, which reads the full prompt from that page on every run. Paste it, add the cloud line above at its end with your repository for ORG/NAME, N then standing for whichever issue the run takes (every run is a cloud session, and the prompt's claim step uses gh issue and gh pr), then:

```
Run this every hour, a few minutes past the hour.
```

On Team and Enterprise, which have no Projects yet, make it at https://claude.ai/code/routines with New routine instead: the same prompt, the repository, your environment and a Schedule trigger hourly a few minutes past the hour ([parallel.md](parallel.md), step 6).

**Split a piece of work into issues,** so parallel sessions each get files no other session touches; where the repository holds a Claude token, the label epic on the request has the coordinator do the same and give the pieces to registered workers ([team.md](team.md), last section):

```
Split the work below into one Task issue per piece, each with a Goal, an Acceptance line and the Files likely touched, labelled todo, with no two issues touching the same file; where two pieces meet, write the interface between them into both. Show me the list before you open them. The work:
```

**Rebase after "main moved",** the one forced push the protocol allows:

```
The board says main moved on my pull request: push what claude/N holds and note its tip (git rev-parse claude/N), git fetch origin, rebase claude/N on origin/main, run bash scripts/check.sh, and push with git push --force-with-lease=claude/N:<that tip> origin claude/N.
```

## Keep what you learned

**Checkpoint,** so the next session or account starts where this one stopped; the skill commits it on the pull request's branch, or in a crowd repository ([crowd.md](crowd.md)) posts it as a comment on the pull request, since there the required check fails a committed one:

```
Write a checkpoint for this pull request with the checkpoint skill, as the skill says.
```

**Remember a fact for every account,** since a Project's own memory is private to its account:

```
Remember this with the remember skill, in this pull request: <the fact, in one sentence>
```

**Show the whole board,** since the session hook prints only its first 120 lines (`/symphony:board` where the plugin brings it):

```
/board
```

## Review

**Review a pull request,** a second reading before the owner merges:

```
Review pull request #N: read the issue it closes and the plan posted on it as a comment (a ready pull request has deleted its claim file; the branch's first commit still holds it), check that the diff does what the issue asks and nothing else, that bash scripts/check.sh passes on its branch and that it finishes as docs/agents/PROTOCOL.md says. Leave your findings as one review comment. Do not push and do not merge.
```

**Or ask @claude on the pull request itself,** which runs in Actions on the repository's Claude token, so only on a repository where you are the one writer and stored CLAUDE_CODE_OAUTH_TOKEN ([solo.md](solo.md), steps 3 and 6); once anyone else has Write ([team.md](team.md), step 1), or in crowd mode, the comment does nothing, so use the review prompt above:

```
@claude review this pull request against the issue it closes and docs/agents/PROTOCOL.md; comment, and do not push.
```

## Benchmark

**The smoke test,** in a cloud session on OpenSpineConsortium/coordbench with the environment from [benchmark.md](benchmark.md); one agent session, the cheapest proof the whole chain works:

```
Run coordbench's smoke test: bash bench/cooperbench/setup.sh, then bash bench/cooperbench/prepare_task.sh pallets_click_task 2068, then env -u ANTHROPIC_API_KEY python3 coordbench/run.py run --arm solo --repo pallets_click_task --task 2068 --features 1,6 --driver claude-cli --name smoke-solo, then python3 bench/cooperbench/report.py --run solo=smoke-solo. Show me the timings line and the report, and stop. Do not run judge.py's model sections.
```

**The pilot,** six arms on one task, about 66 agent sessions:

```
Run bash bench/cooperbench/pilot.sh pallets_click_task 2068 pilot in the background with a two-hour timeout (7200000 ms), the most a background command gets. If it stops before the report, first remove the agent containers the stopped run left behind, which would otherwise run on for up to two more hours on my usage: docker ps -aq --filter label=coordbench.run | xargs -r docker rm -f (Redis and the git server carry no such label and stay); then run it again the same way, since finished pairs are kept. When it ends, show me ~/cooperbench/logs/pilot-report.md and remove the task's image with docker rmi akhatua/cooperbench-pallets-click:task2068.
```
