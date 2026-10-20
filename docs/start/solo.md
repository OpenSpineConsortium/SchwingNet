# One person, one account, a new project

You make a repository from the template, set its GitHub side in one command, claim the first issue and turn on @claude, all on your own Claude account. About fifteen minutes. ORG/NAME is your new repository; [README.md](README.md) says how to read the blocks.

## Once per machine

Claude Code, signed in to your own claude.ai account; the GitHub CLI, signed in to your own GitHub login; git; and Python 3.12 or later, since setup-repo.sh, crowd.py, scripts/check.sh and the hooks run `python3`. On Windows, do all of it inside WSL (`wsl --install`, then everything below in its terminal): the scripts and the hooks need bash and python3, and what you install and sign in to from PowerShell is not what WSL runs. First the tools, with the line for your system. macOS, with Homebrew (https://brew.sh):

```bash
brew install gh git python
```

Debian or Ubuntu, WSL included. Add GitHub's own apt repository first, the "Recommended (Official)" lines of https://github.com/cli/cli/blob/trunk/docs/install_linux.md, because the distribution's gh (2.45 on Ubuntu 24.04) is older than the 2.65 that setup-repo.sh's secret-scanning flags need; then:

```bash
sudo apt update && sudo apt install gh git python3
```

The python3 of Debian 13, and of Ubuntu 24.04 and later, is 3.12 or newer. Debian 12's is 3.11 and Ubuntu 22.04's 3.10: there, install 3.12 or later yourself (https://www.python.org/downloads/) and see that `python3` runs the one you installed, since the scripts and the hooks call it by that name.

Then Claude Code. Bash (macOS, Linux, WSL):

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

PowerShell, only for the route without WSL in step 3, which needs git and gh in Windows as well:

```powershell
irm https://claude.ai/install.ps1 | iex
winget install --id Git.Git
winget install --id GitHub.cli
```

Open a new terminal, so the installs are on its path, and sign in to both, the same two lines in bash and in PowerShell; `claude` opens a browser:

```bash
claude
gh auth login
```

You should see your account under "Login method" when you type `/status` in Claude Code, "Logged in to github.com" from `gh auth status`, 2.65 or higher from `gh --version`, and 3.12 or higher from `python3 --version`.

## Steps

1. **Make the repository.** Open the link, name the repository and create it.

   - A member of the template's enterprise: private, in an organization of the enterprise, whose plan (GitHub Enterprise Cloud) already enforces branch rules and offers auto-merge on a private repository: https://github.com/new?template_owner=OpenSpineConsortium&template_name=symphony-template&owner=OpenSpineConsortium&visibility=private, with another organization of the enterprise in place of `owner=OpenSpineConsortium` if that is where you make repositories. A public repository made from the internal template publishes its files and history, which needs the template's owner's agreement first ([crowdsourcing.md](../setup/crowdsourcing.md), Part 1, step 2), and a managed user cannot make one at all.
   - Anyone else, from the public copy: https://github.com/new?template_owner=TEMPLATE_OWNER&template_name=TEMPLATE_NAME&owner=@me&visibility=public. Public, because on GitHub Free only a public repository gets enforced branch rules and unlimited Actions minutes ([tiers.md](../setup/tiers.md)); put an organization's name in place of `@me` to make it there.

   You should see the new repository with the template's files.

2. **Wait for "Set up this project".** The first push runs the workflow "Template init", which fills your names into the files, makes the six labels and opens that issue; its checklist is the rest of this page. Open https://github.com/ORG/NAME/issues: you should see it within a few minutes, and a green "Template init" run at https://github.com/ORG/NAME/actions. If it never comes, do it by hand:

   ```bash
   gh repo clone ORG/NAME
   cd NAME
   GITHUB_TOKEN=$(gh auth token) python3 tools/template_init.py --repo ORG/NAME --default-branch main --create-labels --open-issue
   ```

   Run from a clone, the script has no push event to say who made an organization's copy, so in an organization's copy it writes `* @ORG` into .github/CODEOWNERS, which asks nobody for review: change that line to `* @LOGIN`, your own GitHub login (`gh api user --jq .login`), before you commit. Then:

   ```bash
   git add -A
   git commit -m "Initialise from the template"
   git push origin main
   ```

3. **The GitHub side, in one command, on your own computer.** A cloud session cannot run it: its GitHub proxy refuses gh's GraphQL commands, and the session has no admin rights. Leave out the first two lines if step 2 already made the clone. In a second terminal run `claude setup-token`, approve it in the browser, and paste the token it prints at the hidden prompt of the first; nothing you paste is shown or saved.

   `--token` stores that token as the repository's secret CLAUDE_CODE_OAUTH_TOKEN, which stays yours only while you are the repository's one writer: anyone with Write can push a workflow that reads it, and every writer's @claude comment spends your plan ([README.md](README.md), Accounts and tokens). A repository in an organization has writers you did not add: the organization's owners are admins of every repository in it, and its base permission can give every member Write. So in an organization, first open https://github.com/ORG/NAME/settings/access, the owners at https://github.com/orgs/ORG/people?query=role%3Aowner and the base permission at https://github.com/organizations/ORG/settings/member_privileges; if anyone besides you can write, leave `--token` out and skip step 6 and step 7's worker in Actions, which run on it ([team.md](team.md), step 1).

   ```bash
   gh repo clone ORG/NAME
   cd NAME
   bash scripts/setup-repo.sh --token
   ```

   It touches [Rules](https://github.com/ORG/NAME/settings/rules), [General](https://github.com/ORG/NAME/settings), [Advanced Security](https://github.com/ORG/NAME/settings/security_analysis), [Actions](https://github.com/ORG/NAME/settings/actions), [Labels](https://github.com/ORG/NAME/labels) and [Actions secrets](https://github.com/ORG/NAME/settings/secrets/actions). You should see one line per step, among them `ruleset "Protect the default branch": created from docs/setup/ruleset-main.json`, `general: delete head branches on merge, allow auto-merge: on`, `workflow permissions: allow GitHub Actions to create and approve pull requests: on`, `secret CLAUDE_CODE_OAUTH_TOKEN: set` (`skipped` without `--token`) and `code owners: GitHub resolves every owner in .github/CODEOWNERS`. Where the organization or its enterprise holds that setting off, its line says so instead, with the page where an owner allows it; until then the weekly protocol update and the "Add a worker" form offer an issue or a link in place of their pull requests, and once it is allowed, run the script again. On a private repository it also prints a note that GitHub Free does not enforce its ruleset, which does not hold in an organization of the enterprise. Run it again at any time; nothing is done twice.

   On Windows without WSL, store the token from PowerShell, under the same condition, and do the rest of this step by hand from the first box of "Set up this project"; gh asks for the value at a hidden prompt. That route also serves steps 4, 6, 7 and 8, but step 5's local session needs bash and python3, which WSL provides: without it, do step 5 from a cloud session, with the prompt in [README.md](README.md), step 5. Step 7's `gh workflow run` line runs in PowerShell.

   ```powershell
   claude setup-token
   gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo ORG/NAME
   ```

4. **Install the Claude GitHub App.** Cloud sessions push through it, and Projects and routines need it. Follow "install the app" in the second box of "Set up this project", which usually has your repository already chosen (if not, pick it); or run `/install-github-app` in Claude Code in your clone, pick the repository, and choose "Skip for now" when it offers the GitHub Actions setup, since step 3 stored the token, or left it out on purpose, and .github/workflows/claude.yml is already here. You should see Claude at https://github.com/ORG/NAME/settings/installations. On an organization, an organization owner may need to approve the installation.

5. **Open the first task and claim it.** Open https://github.com/ORG/NAME/issues/new?template=task.yml with the title "Task: write the goal", the goal "docs/project.md's Goal, Scope and Model and effort are written" and the acceptance "bash scripts/check.sh passes and the owner agrees". You should see it labelled todo, and a minute later in the Queue of the board at https://github.com/ORG/NAME/blob/board/STATE.md. Then, in your clone:

   ```bash
   git pull
   claude
   ```

   and paste, with the issue's number for N:

   ```
   Claim issue N with the claim skill and carry it to a ready pull request, as docs/agents/PROTOCOL.md says; ask me for the goal, the scope and the model and effort, and write them into docs/project.md. Do not merge.
   ```

   You should see the branch `claude/N` on GitHub, the issue labelled claimed and `worker:LOGIN` (your GitHub login, the name your sessions claim under) with the plan as a comment, a draft pull request saying "Closes #N", and at the end the pull request ready with the label in-review. Merge it yourself at https://github.com/ORG/NAME/pulls; the merge closes the issue. To do the same from a cloud session instead, use the prompt in [README.md](README.md), step 5.

6. **@claude in Actions, on your own token.** Write on any issue:

   ```
   @claude summarise what this repository is for, in three sentences.
   ```

   You should see a run of "Claude" at https://github.com/ORG/NAME/actions/workflows/claude.yml and its answer on the issue. Each run spends your own plan's usage (the five-hour window and the weekly limit), which is why the workflow caps its turns. Only someone with write access starts it, and each of them spends your plan: that is why step 3 stores the token only while you are the one writer. Keep usage credits off unless you want overage billed at API rates.

7. **Keep it going, optional: a worker that runs on its own.** Either a worker in Actions, which runs on step 3's token and every six hours, and whenever an issue is queued, starts Claude only when there is work for it; or a routine on claude.ai, which runs on your plan on its own schedule. Add either with the "Add a worker" form at https://github.com/ORG/NAME/issues/new?template=worker.yml: a name after its job (`nightly`, say), never your login, so it never takes your own sessions' claims for its own, and "actions" or "routine" under Where it runs. You should see the form's answer on the issue, with the pull request that adds `.github/symphony/workers/<name>.json`; merge it. A worker in Actions needs nothing more; to see it run at once:

   ```bash
   gh workflow run workers.yml --repo ORG/NAME
   ```

   (you should see a "Workers" run at https://github.com/ORG/NAME/actions/workflows/workers.yml, with a leg for your worker). For a routine, the form's answer is the prompt to paste: make the routine with it as [docs/agents/routines/worker.md](../agents/routines/worker.md) says, in the Project of step 8, so on Pro and Max do that step first; on Team and Enterprise, which have no Projects yet, make it at https://claude.ai/code/routines with New routine, the same prompt, the repository and a Schedule trigger, as [parallel.md](parallel.md), step 6, says. Add the line under "Add this line in a cloud session" in [prompts.md](prompts.md) at the end of a routine's prompt, since every run is a cloud session. One worker is enough, and two under names of their own never hold the same issue, since the branch `claude/<issue>` is the lock.

8. **A thin Project, optional (Pro and Max).** At https://claude.ai/code/projects/browse make a Project that links ORG/NAME and nothing else, with its instructions, description and memory left blank, since every thread reads them from the repository ([claude-project.md](../setup/claude-project.md)). Then close "Set up this project" when every box is ticked.

Next: [parallel.md](parallel.md) runs several sessions at once on this repository; [prompts.md](prompts.md) has the everyday sentences.
