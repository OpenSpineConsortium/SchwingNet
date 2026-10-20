# Several people, each on their own account

Each person brings their own Claude plan and their own GitHub login, and the repository coordinates them as it does every worker ([docs/agents/WORKERS.md](../agents/WORKERS.md)): each person's sessions claim under the person's GitHub login, with the label `worker:<login>` on the board, each session on its own issue; a routine of theirs claims under a name of its own; and the coordinator, a step of the board's own run, releases idle claims and tells open work that changes the same files, with no Claude usage. Nobody's credential reaches anyone else, as long as the repository holds none: a repository's Actions secrets reach every workflow a writer runs there, so step 1 takes the repository's Claude token out before anyone else gets Write. The last section is for a repository you alone write: workers in GitHub Actions, and the epics the coordinator plans for them, which run on that token. ORG/NAME is the repository; [README.md](README.md) says how to read the blocks.

## Steps

1. **Take the secrets out first.** A writer can push a workflow of their own on a branch of their own, and it runs with every Actions secret of the repository, so it can print one; and every writer's @claude comment, every worker in Actions and every run of the coordinator workflow runs on the token's account. Left in place, CLAUDE_CODE_OAUTH_TOKEN would lend that account's subscription to everyone with Write, which Anthropic's Consumer Terms forbid, and a coordinator routine's trigger token would let them fire the routine on its account's usage. So before anyone else gets Write, on your own computer:

   ```bash
   gh secret delete CLAUDE_CODE_OAUTH_TOKEN --repo ORG/NAME
   gh secret delete ANTHROPIC_API_KEY --repo ORG/NAME
   gh secret delete COORDINATOR_TRIGGER_URL --repo ORG/NAME
   gh secret delete COORDINATOR_TRIGGER_TOKEN --repo ORG/NAME
   gh secret delete SDLC_APP_PRIVATE_KEY --repo ORG/NAME
   ```

   The same lines run in PowerShell, and a name you never set only answers that it was not found. SDLC_APP_PRIVATE_KEY is the GitHub App's key, which only the first push's "Template init" run reads; ANTHROPIC_API_KEY is there only if `/install-github-app` stored an API key instead of the token, and bills the API. A secret that comes from the organization is not deleted by these lines: at https://github.com/organizations/ORG/settings/secrets/actions open each of these names and look at its Repository access. "Selected repositories" has a list to take this repository off; "All repositories" and "Private repositories" have none, so change the policy to "Selected repositories" with every repository but this one, or delete the secret at the organization (`gh secret delete NAME --org ORG`). You should see none of the five at https://github.com/ORG/NAME/settings/secrets/actions. From then on @claude, the workers in Actions and the coordinator workflow do nothing, and the board wakes no coordinator routine; each person's own sessions and routines do the work, on their own plans, and the board's own run still releases idle claims and tells overlapping work. For volunteers in an organization, crowd mode ([crowd.md](crowd.md)) does the same and holds the repository to it, since its required check fails while any of these reaches it.

2. **Give each person Write.** A claim is a branch pushed to this repository, not to a fork: the protocol check refuses a claim whose branch lives elsewhere. At https://github.com/ORG/NAME/settings/access (Collaborators & teams), or:

   ```bash
   gh api --method PUT repos/ORG/NAME/collaborators/LOGIN -f permission=push
   ```

   You should see LOGIN listed with Write once they accept the invitation.

3. **A name per person, with nothing to register.** Each person's sessions claim under their GitHub login: the label `worker:LOGIN` on the issues they claim and the line `- Worker: LOGIN` in their claim files, so the board and the issues say whose claim is whose. The claim skill makes the label the first time it is needed; to see it at https://github.com/ORG/NAME/labels from the start, make it now:

   ```bash
   gh label create worker:LOGIN --repo ORG/NAME --color c5def5 --description "Held by or given to LOGIN"
   ```

   A session whose environment sets SYMPHONY_WORKER claims under that name instead. A routine takes a name of its own, after its job and never a person's login (step 5), so it never takes that person's claims for its own.

4. **An area per person, optional, by pull request.** Open a Task issue at https://github.com/ORG/NAME/issues/new?template=task.yml asking for it, and in a session in your clone (`claude`) paste the prompt below; from a cloud session, add the line under "Add this line in a cloud session" in [prompts.md](prompts.md) after it, since gh issue and gh pr are refused there:

   ```
   Claim issue N with the claim skill: add a row to docs/agents/OWNERSHIP.md for the worker LOGIN, label worker:LOGIN, owning the paths I name next; register LOGIN with the file .github/symphony/workers/LOGIN.json, "runs": "session" and those paths as its area, as .github/symphony/workers/README.md says; say so in docs/project.md under Owners; and add a line per path at the end of .github/CODEOWNERS naming @LOGIN beside the login already there, since GitHub uses only the last line that matches a file. Do not merge.
   ```

   You should see the row and the file on main once you merge it. A pull request touching those paths then asks LOGIN for a look through CODEOWNERS, once they have accepted step 2's invitation, since GitHub asks only a user with Write; and LOGIN's sessions, told to take the next issue ([prompts.md](prompts.md)), take an unclaimed blocker or queued work in their area, or work that names no files, the lowest-numbered first. The file alone also comes from the "Add a worker" form, https://github.com/ORG/NAME/issues/new?template=worker.yml, with "session" under Where it runs.

5. **Each person, once, on their own account.** Claude Pro or Max, or a Team or Enterprise seat with Claude Code; `claude` signed in as themselves; Sign in with GitHub at https://claude.ai/code; a cloud environment of their own ([parallel.md](parallel.md), step 1); and a thin Project of their own on ORG/NAME, Pro and Max only ([claude-project.md](../setup/claude-project.md)). Their sessions need no sentence to say whose claim they make, since each claims under their login (step 3). If they want work taken without starting sessions by hand, a routine of their own does it, under a name after its job, never their login, so it never takes their sessions' claims for its own: registered with the "Add a worker" form, its prompt the one the form's answer gives with the line under "Add this line in a cloud session" in [prompts.md](prompts.md) added at its end, and made as [parallel.md](parallel.md), step 6, says, in their Project or, on Team and Enterprise, which have no Projects yet, at https://claude.ai/code/routines with their own environment and an hourly Schedule trigger.

6. **The coordinator, with the token gone.** Its everyday half needs nothing: the board's own run, on the repository's own token and with no Claude usage, releases a claim idle for 24 hours, with a comment that says whose it was, what the branch holds and what its plan was, and tells open work that changes the same files which should land first ([docs/agents/WORKERS.md](../agents/WORKERS.md)). Its other half needs Claude, and with step 1's token gone the coordinator workflow does nothing, so one person, usually the owner, runs the coordinator prompt as a routine on their own account: it splits requests that ask for more than one piece of work into issues and tidies the shared memory; it comments and opens pull requests, and never merges. In that person's Project, paste the short prompt from [docs/agents/routines/coordinator.md](../agents/routines/coordinator.md), which reads the full prompt from that page on every run, and add "run this every day". You should see the routine on the Project's Routines tab, and a run each day. Without Projects (Team and Enterprise plans do not have them yet), make it at https://claude.ai/code/routines with New routine, the same prompt, the repository and a daily Schedule trigger. Leave out its API trigger while anyone else has Write: the trigger's token would have to be a repository secret, which step 1 takes out, and the schedule catches up with what it would have woken early. The coordinator workflow is also what plans an issue labelled epic, so here split such a request into issues instead, with the prompt in [prompts.md](prompts.md).

## Workers in Actions, and the epics the coordinator plans for them

Workers in GitHub Actions run on the repository's Claude token, and so does the coordinator workflow, which plans an issue labelled epic into tasks given to registered workers, settles a task labelled blocked and integrates the finished epic, the way CooperBench's best-scoring configuration does ([docs/agents/WORKERS.md](../agents/WORKERS.md)). Both need CLAUDE_CODE_OAUTH_TOKEN among the repository's secrets, so they run only on a repository where you are the one writer; once anyone else has Write, step 1 above has taken the token out, and they do nothing. A worker in Actions is a name, not a person: every one of them runs on the token's account, so three workers spend that account's usage window about three times as fast as one session, and Max suits it better than Pro; a worker with nothing to do starts no Claude session, so it spends none.

1. **Register the workers.** They need the token from [solo.md](solo.md), step 3, and, for a worker whose pull requests land by auto-merge, "Allow auto-merge", which setup-repo.sh turns on. For each, open the "Add a worker" form at https://github.com/ORG/NAME/issues/new?template=worker.yml with a name after its job (`w1`, `docs-fixer`), "actions" under Where it runs, the area it prefers and how its pull requests land; or add the files by hand in one pull request, as .github/symphony/workers/README.md says. You should see the form's answer on the issue, with the pull request that adds `.github/symphony/workers/<name>.json`, or the link that opens it in one press where the repository does not let GitHub Actions open pull requests ([solo.md](solo.md), step 3); merge it. From then on the workflow "Workers" (https://github.com/ORG/NAME/actions/workflows/workers.yml) runs a leg per worker every six hours and whenever an issue is queued or given to one, deals the open work among them by area, and goes another round while a worker has work, up to its rounds; `gh workflow run workers.yml --repo ORG/NAME` starts one now.

2. **Label an issue epic.** Write what the work is and what done looks like into epic.md, then:

   ```bash
   gh issue create --repo ORG/NAME --title "Epic: what it delivers" --label epic --body-file epic.md
   ```

   You should see a "Coordinator" run at https://github.com/ORG/NAME/actions/workflows/coordinator.yml, the plan written into the epic, and its tasks opened as sub-issues, each labelled todo and `worker:<name>` for the registered worker whose area fits it, which the board lists under Given to workers (or todo alone, for the Queue, when no worker is registered); then a "Workers" run with a leg per worker in Actions, and their pull requests landing as each worker's file says. A worker that is stuck labels its task `blocked`, which calls the coordinator. When the last task closes, the coordinator checks the integrated default branch and closes the epic.

3. **Tune it, optional.** A worker's model, its turns per run (`max_turns`) and its rounds in a row (`rounds`, 6 by default) are in its file, changed by pull request; `CLAUDE_ALLOWED_TOOLS` replaces the tools the sessions may use when your checks need more than git, gh, python3 and scripts/check.sh ([claude-action.md](../setup/claude-action.md)). To stop a worker, remove its file by pull request; to stop them all, @claude and the coordinator workflow with them, delete the secret CLAUDE_CODE_OAUTH_TOKEN.
