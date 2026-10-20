# Many cloud sessions on one project at once

Several Claude Code cloud sessions work one repository at the same time, each on its own issue, on one account or on several. Nothing coordinates them but GitHub: each session claims its issue by pushing the branch `claude/<issue>`, GitHub refuses the second push of the same branch, and the board shows every session the claims, the pull requests and the queue. Every session claims under the GitHub login of the person who started it, unless its environment sets SYMPHONY_WORKER to another name, so one person's sessions are one worker on the board, each holding its own issue ([docs/agents/WORKERS.md](../agents/WORKERS.md)). ORG/NAME is the repository; [README.md](README.md) says how to read the blocks.

## Before you start

- [solo.md](solo.md), steps 1 to 4: the repository, its GitHub side and the Claude GitHub App, which every cloud session pushes through.
- Several issues labelled todo, one per session, each a piece of work whose files no other open issue touches: write them in the Task form's "Files likely touched", for the session to copy into its claim file's "Files to touch", which the board's Claims section shows, while its Overlaps section lists each file that two pieces of open work change, with the order they should land in (the Queue shows only each issue's number, title and labels), so a collision shows before the work meets. [prompts.md](prompts.md) has a prompt that splits a piece of work into such issues.
- Every account that runs sessions: its own Claude Pro, Max or Team plan, or an Enterprise seat with Claude Code, signed in at https://claude.ai/code with Sign in with GitHub, and Write on the repository (https://github.com/ORG/NAME/settings/access). Before someone else's account gets Write, take the secrets out of the repository ([team.md](team.md), step 1).
- On an organization's repository, the Claude GitHub App is installed once, by an organization owner, from https://github.com/apps/claude/installations/new, choosing the organization and Only select repositories; https://github.com/organizations/ORG/settings/installations (Configure) changes that list later. Every member's sessions then use that one installation.

What a session needs, and what it does not: it runs on the claude.ai sign-in of the account that started it, and reaches GitHub through the session's proxy, which holds the credentials outside the VM. No token goes into the cloud environment for this, and no account lends its sign-in to another.

## Steps

1. **One cloud environment per account.** At https://claude.ai/code, select the cloud icon with the current environment's name, in the row above the message box (there is no settings page or direct link for it), then Cloud, Add cloud environment. Fill it in, then press "Create environment":

   | Field | Value | Why |
   | --- | --- | --- |
   | Name | `NAME-work` | the links in step 2 choose it by name |
   | Network access | Trusted | package registries and GitHub; GitHub, connectors and the Anthropic API are reached at every level |
   | Environment variables | none | the session runs on your own sign-in; no token belongs here |
   | Setup script | empty, or what your project's own checks need | it runs as root before Claude Code starts and must exit 0; the template's checks need only bash and python3, which the image has |

   You should see its name on the cloud icon. On Pro and Max the environment named Default already does the same, so make your own only for a setup script, another network level, or to keep the benchmark's token out of everyday sessions ([benchmark.md](benchmark.md)). On Team and Enterprise an Owner first turns on the GitHub connector at https://claude.ai/admin-settings/connectors; keep your environment personal, since every member's sessions read a shared one's variables. Never put CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY in it: the first is withheld from the session, and the second does not replace the session's own sign-in.

2. **Start N sessions from the browser.** The block prints one link per issue, with the prompt, the repository and the environment filled in; open each, check the repository below the box and the environment above it, leave the mode on Auto (or Accept edits where Auto is not offered), and send. A link only fills the box; nothing starts until you send. If you kept the environment Default rather than making `NAME-work`, set ENVIRONMENT=Default (in PowerShell, `$environment = "Default"`). Bash:

   ```bash
   REPO=ORG/NAME
   ENVIRONMENT=NAME-work
   for N in 2 3 4; do
     PROMPT="Claim issue $N with the claim skill and carry it to a ready pull request, as docs/agents/PROTOCOL.md says; work on the branch claude/$N, not this session's own branch, and run bash scripts/check.sh before every push. If the push of claude/$N is refused, another session holds the issue: say so in one line and stop. gh issue and gh pr are refused in a cloud session, so add the labels, post the plan and open the draft pull request with your GitHub tools or gh api (repos/$REPO/issues/$N/labels, repos/$REPO/issues/$N/comments, repos/$REPO/pulls). Mark the pull request ready with your GitHub tool update_pull_request (draft false), not gh api, which cannot change a draft; if you have no such tool, comment 'finished; ready to mark' on the pull request and stop before you delete the claim file. Do not merge."
     python3 -c 'import sys, urllib.parse as p; print("https://claude.ai/code?" + p.urlencode({"prompt": sys.argv[1], "repositories": sys.argv[2], "environment": sys.argv[3]}, safe="/", quote_via=p.quote))' "$PROMPT" "$REPO" "$ENVIRONMENT"
   done
   ```

   PowerShell:

   ```powershell
   $repo = "ORG/NAME"
   $environment = "NAME-work"
   foreach ($n in 2, 3, 4) {
     $prompt = "Claim issue $n with the claim skill and carry it to a ready pull request, as docs/agents/PROTOCOL.md says; work on the branch claude/$n, not this session's own branch, and run bash scripts/check.sh before every push. If the push of claude/$n is refused, another session holds the issue: say so in one line and stop. gh issue and gh pr are refused in a cloud session, so add the labels, post the plan and open the draft pull request with your GitHub tools or gh api (repos/$repo/issues/$n/labels, repos/$repo/issues/$n/comments, repos/$repo/pulls). Mark the pull request ready with your GitHub tool update_pull_request (draft false), not gh api, which cannot change a draft; if you have no such tool, comment 'finished; ready to mark' on the pull request and stop before you delete the claim file. Do not merge."
     "https://claude.ai/code?prompt=$([uri]::EscapeDataString($prompt))&repositories=$repo&environment=$([uri]::EscapeDataString($environment))"
   }
   ```

   You should see each session in the list at https://claude.ai/code, and within minutes a branch `claude/<issue>` and a draft pull request for each.

3. **Or start them from the terminal.** In a clone, with nothing unpushed, since the cloud clones the remote's branch and not your checkout. Pick the environment `--cloud` uses once, with `/remote-env` inside `claude`; then each command starts a session and returns, so the loop starts all of them. Bash:

   ```bash
   cd NAME
   git switch main && git pull
   for N in 2 3 4; do
     claude --cloud "Claim issue $N with the claim skill and carry it to a ready pull request, as docs/agents/PROTOCOL.md says; work on the branch claude/$N, not this session's own branch. If the push of claude/$N is refused, another session holds the issue: say so and stop. gh issue and gh pr are refused in a cloud session, so use your GitHub tools or gh api for the labels, the plan and the draft pull request. Mark the pull request ready with your GitHub tool update_pull_request (draft false), not gh api, which cannot change a draft; if you have no such tool, comment 'finished; ready to mark' on the pull request and stop before you delete the claim file. Do not merge."
   done
   ```

   PowerShell:

   ```powershell
   cd NAME
   git switch main; git pull
   foreach ($n in 2, 3, 4) {
     claude --cloud "Claim issue $n with the claim skill and carry it to a ready pull request, as docs/agents/PROTOCOL.md says; work on the branch claude/$n, not this session's own branch. If the push of claude/$n is refused, another session holds the issue: say so and stop. gh issue and gh pr are refused in a cloud session, so use your GitHub tools or gh api for the labels, the plan and the draft pull request. Mark the pull request ready with your GitHub tool update_pull_request (draft false), not gh api, which cannot change a draft; if you have no such tool, comment 'finished; ready to mark' on the pull request and stop before you delete the claim file. Do not merge."
   }
   ```

   You should see them with `/tasks` in Claude Code and at https://claude.ai/code. `--cloud` needs a claude.ai sign-in, not an API key. To add a message to a running session: `claude -p "your message" --cloud <session id or its claude.ai/code link>`. To take one over in your terminal: `claude --teleport`, which lists them.

4. **On several accounts.** When the accounts belong to different people, take the secrets out of the repository before the others get Write ([team.md](team.md), step 1): a writer can run a workflow of their own that reads CLAUDE_CODE_OAUTH_TOKEN or a coordinator routine's trigger token, and every writer's @claude comment spends the token's account. Each person starts their own sessions the same way, signed in as themselves, with nothing added to the prompt: every session claims under its person's GitHub login, label `worker:<login>`, so the board says whose claim is whose ([team.md](team.md), step 3).

   Name a different issue in every prompt, across all the accounts: sessions told only "the next issue" all reach for the same lowest-numbered one, and all but one are refused and try again. One person with two accounts of their own (a work seat and a personal plan, say) keeps them apart on one machine with one config folder each: `alias claude-work='CLAUDE_CONFIG_DIR=~/.claude-work claude'`. Both accounts' sessions then claim under that person's one GitHub login, each its own issue.

5. **Watch the board.** It is the shared state: `/board` in any session, https://github.com/ORG/NAME/blob/board/STATE.md in the browser, or in a shell:

   ```bash
   git fetch origin +refs/heads/board:refs/remotes/origin/board && git show origin/board:STATE.md
   ```

   You should see a row per session under Claims, each pull request under Open pull requests with its state (clean, behind, conflicting, blocked or unknown), under Overlaps any file that two of them change, with the order to land them in, and the Queue shrinking. When a merge moves main past an open pull request, the board comments "main moved" on it: send that pull request's session the rebase prompt from [prompts.md](prompts.md), or, once that session has ended, a new session of yours with the same prompt, and it rebases and pushes with `--force-with-lease`, the one forced push the protocol allows. Merge the ready pull requests at https://github.com/ORG/NAME/pulls; each merge closes its issue.

6. **Keep them going.** A routine takes the next issue on its schedule, each run a cloud session of its own, so nobody starts sessions by hand. Register it first with the "Add a worker" form at https://github.com/ORG/NAME/issues/new?template=worker.yml: a name after its job, never your login, "routine" under Where it runs, and the area it prefers; merge the pull request the form's workflow opens. The form's answer on the issue is the routine's prompt: the short one in [docs/agents/routines/worker.md](../agents/routines/worker.md) with the routine's name filled in, which reads the full prompt from that page on every run. Add the line under "Add this line in a cloud session" in [prompts.md](prompts.md) at its end, since every run is a cloud session, where the prompt's gh issue and gh pr are refused, and put your repository for ORG/NAME in the added line (N there stands for whichever issue the run takes). Make it in the account's Project ("run this every hour"), or at https://claude.ai/code/routines with New routine, that prompt, the repository, your environment, a Schedule trigger hourly a few minutes past the hour, and the connectors it does not need removed; Create, then Run now. You should see the run's session open and its claim on the board under the routine's name. Give every routine a name of its own: a routine carries on every open claim made under its name, so two under one name would carry on each other's branches and push over them, while a routine under its own name leaves the claims of your sessions, made under your login, alone. For workers that run on the repository's Claude token instead of an account's routine, with the open work dealt out among them by area, see workers in Actions ([team.md](team.md), last section).

## What each way draws on

| Way | Usage it spends |
| --- | --- |
| A cloud session from claude.ai/code, the Claude app, the Desktop app or `claude --cloud` | the plan of the account that started it, with the rest of that account's Claude use; the VM costs nothing extra, and N sessions at once spend N times as fast |
| A thread of a Project | the Project's account; at most 200 new threads a day across your Projects |
| A routine's run | the routine's account; scheduled runs at most hourly |
| @claude, the workers in Actions, the coordinator workflow | the account whose token is the repository secret CLAUDE_CODE_OAUTH_TOKEN, kept only while you are the repository's one writer; a worker in Actions with nothing to do spends none |
| The board with the coordinator's releases and overlaps, the checks, tidy | GitHub Actions minutes: free on a public repository, the plan's included minutes on a private one |

See an account's usage at https://claude.ai/settings/usage. A Project's thread that reaches the plan's limit waits for the reset and goes on, and a routine's run does not; keep usage credits off unless you want overage billed at API rates.

## When two sessions pick the same issue

The second `git push -u origin claude/N` is refused, because the branch exists and the push is not a fast-forward of it: git prints `! [rejected]` and the branch's name. The claim skill then deletes the local branch and picks another issue (.claude/skills/claim, step 5), or, told one issue, says so and stops. Nobody forces it: the push guard refuses a plain `--force` and a `+` before a refspec, which forces as `--force` does, and `--force-with-lease` is only for your own claim after a rebase. The guard also refuses the refspec `:` and patterns with `*`, which push many branches at once, and a push to a name such as `claude/03`, which reads as a claim and claims nothing, since GitHub's lock holds per name and the claim branch of #3 is `claude/3`. A claim with no commit for 24 hours is released by the coordinator in the board's own run, with a comment that says whose it was, what the branch holds and what its plan was, for whoever picks the issue up next ([team.md](team.md), step 6); the same run renames the branch to `released/N-<sha>`, which keeps the work and frees the name, and lists the issue in its Queue again.

A session with several repositories loads no repository's hooks, so the push guard and the board at session start hold only in a session with this one repository; keep one repository per session.
