# Crowdsourcing a project on contributors' own Claude accounts

This page sets a project up the way Cursor's "Scaling long-running autonomous coding" describes, planners and many workers on one codebase, with one difference: the workers are volunteers, and each contributor runs Claude Code under their own Claude Pro or Max account, on their own machine, in their own cloud sessions or through their own routines. The repository coordinates them through GitHub alone. An issue is a task, the first push of a branch `claude/<issue>` is the claim, the board (STATE.md on the branch `board`) is the shared state, and a pull request is the handoff. The repository never holds, sees or runs on a contributor's Claude credential, and it holds none of the owner's either.

The owner's part is two commands, `python3 scripts/crowd.py setup` and `python3 scripts/crowd.py finish`, plus the few steps GitHub and claude.ai offer no API for, which the commands print as links; a contributor's part is one command, `python3 scripts/crowd.py doctor`, run until it says ready. Once they have run, GitHub itself holds the repository to crowd mode's rules (the Safety checklist below says which, and which remain conventions). The evidence and the reasoning behind every step are in [the research record](../history/crowdsourcing/research.md). The commands are tested against a stand-in for GitHub; nothing here was run end to end on a live organization.

Names: in your copy, template-init has already written your repository, your organization and your default branch into the commands below; in the template they show as placeholders in double braces. ORG and NAME are the organization and the repository before the copy exists, TEMPLATE_OWNER/TEMPLATE_NAME the public copy of the template it is made from, OWNER_LOGIN is your GitHub login, LOGIN a contributor's, AREA one slice of the project (lowercase letters, digits and hyphens, such as `parser`, with folders src/AREA/ and tests/test_AREA/ of the project's own), and N an issue's number.

## What is allowed with contributors' accounts

- Allowed: Claude Code's legal page says its rules do not "prevent an end user from signing in to the unmodified Claude Code binary with their own Claude subscription" ([legal and compliance](https://code.claude.com/docs/en/legal-and-compliance)). Each contributor works under their own account, and the usage counts against their own limits.
- The same page says advertised Pro and Max limits "assume ordinary, individual usage of Claude Code and the Agent SDK", and that Anthropic may enforce its authentication rules "without prior notice". A worker on your own account is your own use, but how much you run is yours to weigh ([unattended use](../history/crowdsourcing/research.md#what-the-documents-do-not-settle)).
- Forbidden to contributors: "You may not share your Account login information, Anthropic API key, or Account credentials with anyone else. You also may not make your Account available to anyone else." ([Consumer Terms](https://www.anthropic.com/legal/consumer-terms)).
- Forbidden to the project whenever it builds or runs a service that touches Claude: the legal page says third-party developers may not "route requests through Free, Pro, or Max plan credentials on behalf of their users", and "may not collect, store, or intermediate Claude.ai credentials or session tokens".
- So there is no token pool, no dispatcher, no "sign in with Claude", and no contributor's `claude setup-token` output anywhere in the project. A routine's trigger token stays out too, by this page's cautious choice: no source says whether handing one over makes an account available.
- The owner's subscription token stays out as well: "Any user with write access to your repository has read access to all secrets configured in your repository." ([secure use](https://docs.github.com/en/actions/reference/security/secure-use)).
- An owner who wants to pay for the agents uses Claude Team seats, Console API keys or a cloud provider, and, by this page's cautious choice, never contributors' personal plans. Team seats and the Console fall under Anthropic's Commercial Terms, which the research behind this page did not review: read them before seating people who are not your staff ([paying centrally](../history/crowdsourcing/research.md#paying-for-the-agents-centrally)).
- Where the documents are silent, this page takes the cautious side ([what they do not settle](../history/crowdsourcing/research.md#what-the-documents-do-not-settle)).

## Cursor's roles, and where each lives here

| Cursor's role | Here | Runs on |
| --- | --- | --- |
| Root planner | The owner: the goal and scope in docs/project.md, one epic per area | The owner's account |
| Sub-planners, one per slice | Area maintainers (docs/agents/OWNERSHIP.md, .github/CODEOWNERS), who split their epic into sub-issues | Each maintainer's account |
| Workers, one task each | Contributors under the claim protocol (docs/agents/PROTOCOL.md) | Each contributor's account |
| The handoff | A pull request saying "Closes #N" | GitHub |
| Judge | The required check "check", accepted only from GitHub Actions, and code-owner review | GitHub and the reviewers |
| Fresh starts | Every routine run clones fresh; idle claims are released after 24 hours, by the board's own run | Each account, and GitHub for the releases |
| Integrator (Cursor removed it) | Maintainers merging by hand | The maintainers |

Sources and confidence for each row: [the full mapping](../history/crowdsourcing/research.md#cursors-roles-mapped-in-full).

## Part 1: the owner

Before you start, have git, the GitHub CLI (`gh`), Python 3.12 or later and Claude Code signed in to your own account, and run every command on your own computer: a cloud session's GitHub proxy refuses gh's GraphQL commands, `gh issue`, `gh pr` and the merge `finish` makes among them, and the setup needs the organization scope on your own login ([why](../history/crowdsourcing/research.md#own-computer-and-gh-scopes)). Turn on two-factor authentication for your own GitHub account first, since GitHub requires that before you can require it of others. Then sign gh in and give it the organization scope; setup stops with the second line when the scope is missing, and `publish-template` asks for `workflow` the same way:
```
gh auth login
gh auth refresh -h github.com -s admin:org
```

1. **Make the organization.** Create ORG on the Free plan at https://github.com/account/organizations/new?plan=free; no API makes one, and a public repository there has every feature this page uses ([why](../history/crowdsourcing/research.md#a-free-organization)). Setup sets its member defaults (members read, and cannot make repositories). Requiring two-factor authentication has no API either: setup lists https://github.com/organizations/ORG/settings/security among what it leaves to you, and the audit fails until it is on.

2. **Get a public copy of the template.** OpenSpineConsortium/symphony-template is internal to its enterprise, so a new organization cannot see it or use "Use this template". Every route below publishes the template's files and history, so get its owner's agreement first, and ask whether its enterprise uses Enterprise Managed Users (a managed user's login ends in an underscore and the enterprise's short code). If it does, routes A and B cannot work, because a managed user cannot push outside the enterprise or publish a public repository; the one way left is for the template's owner to send the files as a bundle (in their clone, `git fetch origin && git switch main && git merge --ff-only origin/main`, so the bundle is not behind, then `git bundle create symphony-template.bundle main`) to a non-managed account, which runs route B with `git clone --branch main symphony-template.bundle NAME` in place of HELPER's first line ([why](../history/crowdsourcing/research.md#the-internal-template-and-managed-users)). Template-init must not fill a copy before its files have all landed, which is why every route keeps it from running until then ([why](../history/crowdsourcing/research.md#actions-off-for-the-first-push)).

   **Route A: the template's owner publishes a template.** Either they make OpenSpineConsortium/symphony-template public, or, from their own clone of it, they publish a public copy, TEMPLATE_OWNER/TEMPLATE_NAME. The first run only reads, and prints everything publishing would make public: the visibility it has now, the branch and its head, the number of commits, the name and email of every author and committer in that history, every file at the head, and every path that only earlier commits hold, which the history publishes too; with `--yes` it makes TEMPLATE_OWNER/TEMPLATE_NAME public and a template from its creation, so template-init and the board skip it with Actions on ([why](../history/crowdsourcing/research.md#a-template-from-its-creation)), and pushes the default branch with its history. If a run stops after making TEMPLATE_OWNER/TEMPLATE_NAME and before its push, run it again: it pushes into the empty template it made, and refuses any other repository of that name. Managed users are refused with the bundle route.
   ```
   python3 scripts/crowd.py publish-template OpenSpineConsortium/symphony-template TEMPLATE_OWNER/TEMPLATE_NAME
   python3 scripts/crowd.py publish-template OpenSpineConsortium/symphony-template TEMPLATE_OWNER/TEMPLATE_NAME --yes
   ```
   Then clone it, which gives you scripts/crowd.py, and go on with step 3 with `--template TEMPLATE_OWNER/TEMPLATE_NAME`, which makes your repository from it:
   ```
   gh repo clone TEMPLATE_OWNER/TEMPLATE_NAME
   cd TEMPLATE_NAME
   ```

   **Route B: a member of the template's enterprise, HELPER, pushes it for you.** You make the repository with Actions off and give HELPER Write on it:
   ```
   gh repo create ORG/NAME --public
   gh api --method PUT repos/ORG/NAME/actions/permissions -F enabled=false
   gh api --method PUT repos/ORG/NAME/collaborators/HELPER -f permission=push
   ```
   HELPER turns on two-factor authentication (ORG requires it, and an outside collaborator without it loses access), accepts the invitation, and runs:
   ```
   gh repo clone OpenSpineConsortium/symphony-template NAME -- --branch main --single-branch
   cd NAME
   git remote set-url origin https://github.com/ORG/NAME.git
   git push origin main
   GITHUB_TOKEN=$(gh auth token) python3 tools/template_init.py --repo ORG/NAME --default-branch main --create-labels --open-issue
   git add -A
   git commit -m "Initialise from the template"
   git push origin main
   ```
   If a push is refused for lack of the workflow scope, HELPER runs `gh auth refresh -s workflow` and pushes again. Then you turn Actions on, take HELPER's access back (the audit warns while it remains) and make your own clone, from which step 3 runs without `--template`:
   ```
   gh api --method PUT repos/ORG/NAME/actions/permissions -F enabled=true
   gh api --method DELETE repos/ORG/NAME/collaborators/HELPER
   gh repo clone ORG/NAME
   cd NAME
   ```
   If you are HELPER yourself, leave out the collaborator lines and the last clone, and in HELPER's clone run `git config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'`: a single-branch clone otherwise never fetches other accounts' claim branches or a fresh board ([why](../history/crowdsourcing/research.md#a-single-branch-clone)).

3. **Run setup.** In the clone from step 2, name your repository and its areas; `--dry-run` first prints every write instead of making it (on a repository that does not exist yet it stops at the first, since everything after reads the copy). Leave out `--template` when the repository already exists, as after route B:
   ```
   python3 scripts/crowd.py setup ORG/NAME --template TEMPLATE_OWNER/TEMPLATE_NAME --area AREA --dry-run
   python3 scripts/crowd.py setup ORG/NAME --template TEMPLATE_OWNER/TEMPLATE_NAME --area AREA
   ```
   It prints one line per step. Before any write it checks that gh has the organization scope, that you own ORG, and that the repository is not a template itself and is public (a Free organization's private repository gets its ruleset written but not enforced), then that it has a commit, has finished template-init and carries the crowd files; with `--template` and no repository yet, it first makes ORG/NAME from the template, public, waits for GitHub to fill the copy, which it does a while after it answers, and then for template-init (`--wait`, 300 seconds in all by default) ([why](../history/crowdsourcing/research.md#a-copy-fills-later)). Then, in order:
   - ORG's member defaults ([why](../history/crowdsourcing/research.md#a-free-organization)).
   - Head branches deleted on merge, auto-merge off ([why](../history/crowdsourcing/research.md#no-token-no-variables-no-auto-merge)), pull requests only from collaborators, so no stranger's title reaches every session through the board ([why](../history/crowdsourcing/research.md#pull-requests-from-collaborators)), and secret scanning and push protection on. `--open-pull-requests` leaves pull requests open to anyone.
   - Actions: a read-only default token that approves no pull request, and approval before any outside contributor's workflows run; where GitHub refuses the second, it names the settings page ([why](../history/crowdsourcing/research.md#actions-settings-secrets-and-variables)).
   - It deletes any Claude secret (CLAUDE_CODE_OAUTH_TOKEN, ANTHROPIC_API_KEY, COORDINATOR_TRIGGER_URL, COORDINATOR_TRIGGER_TOKEN, SDLC_APP_PRIVATE_KEY) and the variables CLAUDE_WORKER and CLAUDE_TEAM, which switched on the Actions worker and team mode in older copies, from the repository, reports any other secret without deleting it, and leaves one that comes from the organization to you, since it may serve other repositories ([why](../history/crowdsourcing/research.md#no-secret-is-a-convention)).
   - The repository variable CLAUDE_CROWD, true, before anything else lands: while it is true, claude.yml, coordinator.yml and workers.yml never start, so @claude, the coordinator's planning and the workers in Actions stay off, and the "Add a worker" form refuses a worker in Actions ([why](../history/crowdsourcing/research.md#the-owners-claude-workflows)).
   - The board's six labels, your own `worker:OWNER_LOGIN`, so your claims name your login as everyone else's do, and `area:AREA` for each area; an area is at most 45 characters, so its label fits GitHub's 50 ([why](../history/crowdsourcing/research.md#labels-the-board-and-tidy), [names](../history/crowdsourcing/research.md#names-github-refuses)).
   - The teams, closed so code owners can name them: contributors with Write, which the claim protocol needs; maintainers with Maintain, which queues work; and AREA-maintainers with Write for each area ([why](../history/crowdsourcing/research.md#teams)).
   - The ruleset "Protect the default branch" from docs/setup/ruleset-crowd.json: one approval, a code owner's review, approval of the latest push, resolved threads, stale approvals kept, the up-to-date rule off, and a bypass for organization owners on pull requests only, so your own pull requests to the paths only you own can merge ([why](../history/crowdsourcing/research.md#bypass-review-rules-and-the-strict-policy), [the bypass actor](../history/crowdsourcing/research.md#the-bypass-actor-and-the-pin)).
   - With `--members-only`, issues and comments limited to collaborators for six months, which running setup again renews; when ORG has a limit of its own, that one applies here, GitHub refuses one for the repository, and setup says so and goes on ([why](../history/crowdsourcing/research.md#interaction-limits), [the organization's limit](../history/crowdsourcing/research.md#an-organizations-interaction-limit)).
   - One pull request from the branch crowd/setup with the crowd files from docs/setup/crowd/: .github/CODEOWNERS giving .github/, .claude/, tools/, scripts/, tests/, CLAUDE.md, docs/project.md, docs/agents/, docs/memory/ and docs/setup/ to you alone (`--owner LOGIN` names another login), each area's folders to its team and the rest to maintainers, and then, last so that they win inside an area too, CLAUDE.md, CLAUDE.local.md, AGENTS.md and .claude/ in any folder and the root's .mcp.json to you alone, since Claude Code loads those as instructions or MCP servers once a session works in that folder ([why](../history/crowdsourcing/research.md#code-owners), [nested files](../history/crowdsourcing/research.md#instructions-in-any-folder)); the Task and Blocker forms without labels, so a new issue is not queued by itself ([why](../history/crowdsourcing/research.md#who-queues-work)); .claude/rules/crowd.md, and a checkpoint skill that posts a pull request comment instead of committing ([why](../history/crowdsourcing/research.md#crowd-rules-and-checkpoints)); the crowd coordinator and worker pages; docs/project.md's crowd mode line, with its decisions, and its owners; docs/agents/OWNERSHIP.md; and tests/test_AREA/__init__.py for each area, so test discovery finds the area's tests and the area's team owns them (a folder named tests/AREA/ would be imported as a package named AREA and stand in for src/AREA in every test).
   - A Task issue for the goal, and the setup issue's checklist rewritten for crowd mode, with what setup verified ticked ([why](../history/crowdsourcing/research.md#the-goal-and-the-setup-issue)).

   Run it again at any time: it writes only what differs and says "already" for the rest. Once crowd mode is on, it never undoes an edit of yours: a crowd file whose latest commit on the default branch is not one of setup's (.claude/rules/crowd.md, the checkpoint skill, the coordinator and worker pages, .github/CODEOWNERS, docs/agents/OWNERSHIP.md) is kept as it is, setup prints so and the pull request lists it, and it leaves the one-time edits to docs/project.md, CLAUDE.md and README.md alone; to take a newer crowd file from docs/setup/crowd/ into one you edited, merge the two by hand ([why](../history/crowdsourcing/research.md#a-later-setup-keeps-your-edits)). To add an area later, run it with the new `--area`; it keeps every area whose label exists, puts the new area's rows into CODEOWNERS and OWNERSHIP.md in place, and opens a new crowd/setup pull request, which `finish` merges as before; with no new area and no other change it opens none, so `--members-only` alone only renews the limit. Do not run scripts/setup-repo.sh here: it would turn auto-merge on and can store a token, so it refuses while CLAUDE_CROWD is true or the clone's docs/project.md says crowd mode is on, and whenever it cannot read the variable.

4. **Do what setup leaves to you.** Its last lines list only what is still open; besides reading its pull request (step 5), that is:
   - Require two-factor authentication for ORG, at the link it prints.
   - Install the Claude GitHub App on this repository only, from the link it prints with ORG and the repository already chosen ("Only select repositories"), or, when it is already installed on every repository of ORG, limit it to this one at the page it prints. Cloud sessions connected through the app push through it, and routines' GitHub triggers need it. If you use `/install-github-app` instead, choose "Skip for now" when it offers GitHub Actions setup, or it stores a token or an API key in the repository ([why](../history/crowdsourcing/research.md#the-claude-github-app)).
   - Take this repository off the list of any Claude secret or variable of the organization it named, or delete it, at https://github.com/organizations/ORG/settings/secrets/actions and .../variables/actions; the pull request's check fails until you do.
   - Any edit to your copy's text it could not match, with the text to write.

5. **Read the pull request, then finish.** Read every file of the crowd/setup pull request: nobody else can approve yet, so your reading is the only review the shared paths get. Then:
   ```
   python3 scripts/crowd.py finish ORG/NAME
   ```
   While the check still runs, or GitHub's record of the branch does not show its last push yet, it says to wait and run it again. It refuses, writing nothing, when:
   - GitHub's record of crowd/setup, the branch's activity view, which names the account behind each push where a commit's author is only what the pusher typed into git, shows anyone but you pushing it, for its head or since the pull request opened;
   - the branch is not, blob for blob, what setup would write from the default branch now (run setup again), for the owner login, which never comes from the pull request: you, or `--owner LOGIN` if you gave setup one (give `finish`, `invite` and `audit` the same), and once crowd mode is on the one owner the default branch's CODEOWNERS names;
   - CODEOWNERS does not resolve, or "check" came from anything but GitHub Actions ([why](../history/crowdsourcing/research.md#who-pushed-and-what-it-holds)).

   Otherwise it takes "check" only from GitHub Actions (app id 15368; GitHub pins a check only to an app that has already reported it, which is why this waits for the pull request's run), merges with `gh pr merge --admin --match-head-commit`, so nothing pushed after the check gets in, rewrites the setup issue's checklist and runs the audit ([why](../history/crowdsourcing/research.md#bypass-review-rules-and-the-strict-policy), [the pin](../history/crowdsourcing/research.md#the-bypass-actor-and-the-pin)). Write still lets any contributor merge someone else's approved pull request ([who may merge](../history/crowdsourcing/research.md#who-may-merge)). Add a merge queue later, when merges start waiting on each other; it needs `merge_group` in .github/workflows/ci.yml first ([the merge queue](../history/crowdsourcing/research.md#the-merge-queue)).

6. **Write the goal**, under the Task issue setup opened, "Task: write the goal, the scope and the areas"; "Set up this project" carries no todo, and "Closes #N" would close its checklist early. The crowd mode section, the owners and docs/agents/OWNERSHIP.md are already written ([why](../history/crowdsourcing/research.md#the-goal-and-the-setup-issue)). In a clone of your repository:
   ```
   gh repo clone ORG/NAME
   cd NAME
   claude
   ```
   Tell Claude Code: "Claim issue N with the claim skill; my worker label is worker:OWNER_LOGIN and the claim file's Worker line is OWNER_LOGIN." Setup made that label, and the audit reads your claim branches as yours by the Worker line. In that pull request, write docs/project.md's Goal (one paragraph: what comes first and how done is measured), Scope (each out-of-scope item with its reason), and Model and effort, and correct the areas in docs/agents/OWNERSHIP.md if they are wrong. Run `bash scripts/check.sh`, finish as Part 2, step 8 says, and once the check is green merge it with `gh pr merge N --merge --admin`: those paths are yours alone, and an author cannot approve their own pull request.

7. **Seed the queue: one epic per area, tasks as its sub-issues.** An issue labelled epic stays out of the board's Queue, and so does one labelled worker:LOGIN, which the board lists under "Given to workers" for that contributor alone; in crowd mode no coordinator workflow plans an epic, so its area's maintainer writes the plan and opens the tasks. Write the bodies outside the clone, where no session's `git add -A` can commit them: /tmp/epic.md says who owns which files, the interface between tasks that meet and the order they land in; /tmp/task.md starts with `Epic: #EPIC_NUMBER`, then the Task form's headings `### Goal`, `### Acceptance` and `### Files likely touched`. Write each task as one session's work, owning files no other open task owns, with any interface written into both sides, split by failure class or hotspot, and with a measurable acceptance such as a test in tests/test_AREA/ ([why](../history/crowdsourcing/research.md#planning-tasks)). Give a task to one contributor with `--label worker:LOGIN`, and let each area maintainer open their own area's tasks.
   ```
   gh issue create --repo ORG/NAME --title "Epic: AREA" --label epic --label area:AREA --body-file /tmp/epic.md
   gh issue create --repo ORG/NAME --title "Task: one piece" --label todo --label area:AREA --body-file /tmp/task.md
   child=$(gh api repos/ORG/NAME/issues/TASK_NUMBER --jq .id)
   gh api --method POST repos/ORG/NAME/issues/EPIC_NUMBER/sub_issues -F sub_issue_id="$child"
   ```
   Only someone with Maintain or Admin queues work. .github/workflows/queue.yml takes todo or blocker off again, and says so on the issue, when anyone else adds one, opens an issue with one or edits the title or body of an issue labelled todo or blocker; it does not see an epic, a comment, or an edit to either, so maintainers and sessions re-read those (Safety checklist). The workers and the coordinator still check who queued an issue before they take it ([why](../history/crowdsourcing/research.md#who-queues-work)). To see the board at any time, run `gh workflow run board.yml --repo ORG/NAME` and, a minute later, `git fetch origin +refs/heads/board:refs/remotes/origin/board && git show origin/board:STATE.md`.

8. **The coordinator, on your own account, outside any Project.** It splits queued requests into issues for a maintainer to queue and tidies the shared memory; the board's own run, on the repository's own token, releases idle claims and tells open work that overlaps. Setup's pull request made docs/agents/routines/coordinator.md the crowd page: make the routine at https://claude.ai/code/routines as it says, with its short prompt as it stands, which reads the full prompt from that page on every run, the Default environment, an hourly schedule, no other trigger and no connector, then Run now once and read the transcript. claude.ai has no API for routines. Not in a Project: a Project's thread watches the pull requests it opens and wakes on anyone's review comment, on your usage ([why](../history/crowdsourcing/research.md#the-coordinator-outside-a-project)).

9. **Invite contributors.** `invite` refuses until `finish` has merged the crowd files and pinned the check, and while CODEOWNERS gives any shared path to anyone but you (`--owner LOGIN` names another): before that, anyone with Write could merge an unreviewed change to the hooks and the instructions every session loads. It makes each person's label `worker:LOGIN`, invites them into contributors (with `--maintainer`, into maintainers and, with `--area`, their AREA-maintainers team too) and prints the message to send them, which points at Part 2. Put every area maintainer on maintainers, since only Maintain and Admin queue work here. An author cannot approve their own pull request, so each area team needs two members besides you; you are on every team you made, so stay on an area team until it has two others, as `invite --maintainer --area` reminds you. Invitees must turn on two-factor authentication before they can accept, the invitation expires after 7 days, and a new organization can send 50 a day; `invite` says when that limit stops it ([why](../history/crowdsourcing/research.md#invitations), [teams](../history/crowdsourcing/research.md#teams)). `remove` takes someone out of the organization and the repository, cancels an invitation still pending, and lists their open pull requests and claims for a maintainer to release.
   ```
   python3 scripts/crowd.py invite ORG/NAME LOGIN [LOGIN ...]
   python3 scripts/crowd.py invite ORG/NAME LOGIN --area AREA --maintainer
   python3 scripts/crowd.py remove ORG/NAME LOGIN
   ```

10. **Every week, the audit.** It reads only, prints one line per check (`ok`, `warn` or `FAIL`, with the command or page that fixes it) and exits 1 on any failure, so your own cron can mail it; the repository holds no token to run it from Actions. It covers two-factor authentication and the organization's defaults and owners; every secret and variable that reaches the repository, from it, the organization, an environment, Dependabot or Codespaces; the repository and Actions settings; the ruleset against docs/setup/ruleset-crowd.json; CODEOWNERS, whose every shared path, the instruction files inside each area included, must ask you alone (`--owner LOGIN` names another login); the mode line; the teams and outside collaborators; that ci.yml, board.yml, queue.yml and tidy.yml are active; the interaction limit, with how to renew it where it was set; who pushed `board` and each claim branch this week; who queued each queued issue; the default branch's check; and the Claude app ([why](../history/crowdsourcing/research.md#no-secret-is-a-convention)).
    ```
    python3 scripts/crowd.py audit ORG/NAME
    ```

## Part 2: a contributor

1. **Your own plan and tools.** You need Claude Pro or Max on your own account; the free plan has no Claude Code. Keep usage credits off unless you want overage billed, and check the training setting at https://claude.ai/settings/data-privacy-controls. You also need git, bash, Python 3.12 or later and the GitHub CLI: `bash scripts/check.sh` and the hooks run `bash` and `python3`. On Windows, work inside WSL; on native Windows the hooks need bash and python3 on PATH, which was not tested ([why](../history/crowdsourcing/research.md#tools-and-windows)). Never give anyone your login, a token from `claude setup-token` or a routine's trigger token; nobody from the project will ask, and if someone does, tell the owner.

2. **Install Claude Code, sign in as yourself, sign gh in.** Before the first `claude`, take away what would outrank your own claude.ai login, since with one of them set Claude Code may skip the sign-in and run the session on it ([why](../history/crowdsourcing/research.md#signing-in)): unset ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, CLAUDE_CODE_OAUTH_TOKEN, the cloud provider switches CLAUDE_CODE_USE_BEDROCK, CLAUDE_CODE_USE_VERTEX and CLAUDE_CODE_USE_FOUNDRY, and ANTHROPIC_PROFILE, ANTHROPIC_FEDERATION_RULE_ID and ANTHROPIC_ORGANIZATION_ID; remove any `apiKeyHelper`, and those names under `env`, from ~/.claude/settings.json; end an active Anthropic profile set up for federation, or a Claude apps gateway sign-in, as [the authentication page](https://code.claude.com/docs/en/authentication#authentication-precedence) says; and if Claude Code still asks whether to use an API key, decline. The first line below prints the names of any that are set in this shell, never their values. Then `claude` opens a browser: sign in to your own claude.ai account (`/login` does it later). Step 4's `doctor` checks the shell and every settings file again, and `/status` in Claude Code names the credential in use.
   ```
   env | cut -d= -f1 | grep -E '^(ANTHROPIC_(API_KEY|AUTH_TOKEN|PROFILE|FEDERATION_RULE_ID|ORGANIZATION_ID)|CLAUDE_CODE_(OAUTH_TOKEN|USE_BEDROCK|USE_VERTEX|USE_FOUNDRY))$'
   curl -fsSL https://claude.ai/install.sh | bash
   claude
   gh auth login
   ```

3. **Accept the invitation.** Turn on two-factor authentication for your GitHub account first, at https://github.com/settings/security, then accept at https://github.com/orgs/{{OWNER}}/invitation within 7 days ([why](../history/crowdsourcing/research.md#invitations)). Ask the owner which area is yours, the AREA in the rest of this part (docs/agents/OWNERSHIP.md lists them), or leave it out to take any issue.

4. **Clone, read what doctor runs, and run doctor**, then do what its last line, "Next:", says and run it again, until it says "ready". Doctor is scripts/crowd.py, and it imports tools/crowd_check.py, tools/marked_section.py and tools/template_init.py: they run on your machine, so read them first. The owner alone reviews scripts/ and tools/ (.github/CODEOWNERS) on a protected default branch, which is why running them is reasonable, but the reading is yours to do. Leave out `--area AREA` to take any issue.
   ```
   gh repo clone {{REPO}} && cd "$(basename {{REPO}})"
   less scripts/crowd.py tools/crowd_check.py tools/marked_section.py tools/template_init.py
   python3 scripts/crowd.py doctor --area AREA
   ```
   It checks, in order: Python, git and bash (and says to work in WSL on native Windows); that gh is signed in; that no other Claude credential is set in your shell or your settings files; that Claude Code is installed; that the clone is of this repository, fetches every branch and says crowd mode is on; that you are a member of {{OWNER}}, with Write here; and that your label `worker:LOGIN` and your area's label exist. The "Next:" line names the first item unmet: the command to run, or what to ask the owner for. At ready it prints the files the hooks in .claude/settings.json run, with what they import: read them before you trust the folder, since they run as commands on your machine. The file also names OpenSpineConsortium/symphony-marketplace, so Claude Code may offer to add that marketplace; you can decline, since this repository wires the same hooks itself. Each session then loads CLAUDE.md with the goal, the protocol and the shared memory, the rules in .claude/rules/ (crowd.md among them), a session hook that prints your branch's distance from origin and the top of the board, the push guard, and the claim, remember and checkpoint skills ([what loads](../history/crowdsourcing/research.md#what-loads-in-a-session)).

5. **For cloud sessions and routines, connect GitHub** at https://claude.ai/code by authorizing the Claude GitHub App. In a cloud session, `gh issue` and `gh pr` are refused; the worker prompt's last line gives the `gh api` calls to use there ([why](../history/crowdsourcing/research.md#cloud-sessions)).

6. **Claim one issue.** Run `claude` in the clone, check that `/status` names your own claude.ai account, and say the sentence doctor printed: it claims the lowest-numbered queued issue in your area that a maintainer queued. For a task given to you, which the board lists under "Given to workers" and not in the Queue, and which a maintainer queued with todo too, since anyone with Write can add a worker's label (.claude/rules/crowd.md): "Claim issue N with the claim skill; it is given to me with worker:LOGIN, so it is not in the Queue." The skill pushes `claude/N` with the claim file alone, labels the issue, posts the plan and opens a draft pull request. If the push is refused, someone claimed it first; pick another. Hold one open claim at a time (.claude/rules/crowd.md).

7. **Work in the open.** Small commits; `bash scripts/check.sh` before every push; push at least once a day while the pull request is a draft, since a draft idle for 24 hours is released. While it is a draft, rebase on `origin/{{DEFAULT_BRANCH}}` whenever the session hook says you are behind, and push with `git push --force-with-lease=claude/N:<the tip you last pushed> origin claude/N`, only ever on your own claim branch: named, since one that names no branch under git's push.default matching forces every branch with a namesake on origin, and with the tip you pushed before the rebase, so that it never forces over a push made since (the claim skill's step 7). Once it is ready, rebase only when GitHub reports a conflict: each rebase needs a new approval ([why](../history/crowdsourcing/research.md#rebasing-and-approvals)). Your checkpoint is a comment on your pull request, which the checkpoint skill posts; the required check fails a pull request that commits .claude/session.md or changes the checkpoint block of CLAUDE.md. A fact for everyone goes to docs/memory/ in the same pull request, with the remember skill. If you run out of usage, push and say on the issue where it stands.

8. **Finish.** Mark the pull request ready right after the push: the check run for the push sees a draft without its claim file and fails, and the run for marking ready is the one that should pass ([why](../history/crowdsourcing/research.md#finishing)).
   ```
   git rm docs/agents/claims/N.md
   git commit -m "Finish #N"
   bash scripts/check.sh
   git push origin claude/N
   gh pr ready claude/N
   gh issue edit N --add-label in-review
   ```
   In a cloud session, push your work and stop there; finish on your machine (`git fetch origin`, `git switch claude/N`, then the lines above), or on GitHub: delete docs/agents/claims/N.md on the branch (the file's menu, Delete file), press "Ready for review" straight after, and add the label with `gh api repos/{{REPO}}/issues/N/labels -f "labels[]=in-review"`. Do not merge your own pull request, even when GitHub would let you. Use `/autofix-pr` only while you watch: on a public repository anyone's review comment steers it, spends your usage and gets a reply under your name ([why](../history/crowdsourcing/research.md#auto-fix)).

   When a review asks for changes, push the fixes to the same branch, answer each thread and request review again. Every push after an approval needs a new approval from someone other than you, so gather the fixes into one push.

9. **If you want, run the worker unattended, on your own account.** Advertised Pro and Max limits assume ordinary, individual use, so how much you run is yours to weigh ([unattended use](../history/crowdsourcing/research.md#what-the-documents-do-not-settle)). In crowd mode docs/agents/routines/worker.md is the crowd page, its prompt carrying the lines a contributor's worker needs ([each line's reason](../history/crowdsourcing/research.md#the-worker-addendum)); this prints its short prompt with your login and your area filled in, or with the line that takes any issue when you leave `--area` out; every run reads the full prompt from that page on {{DEFAULT_BRANCH}}, so a later change to it reaches your worker with nothing pasted again:
   ```
   python3 scripts/crowd.py doctor --worker --area AREA
   ```
   A cloud worker leaves its finished claim as a draft for you to finish as in step 8. Run it one of three ways, one worker per contributor, under your GitHub login, the name your own sessions work under too ([details](../history/crowdsourcing/research.md#three-ways-to-run-a-worker)):
   - **A routine**, which runs with your computer off: at https://claude.ai/code/routines, New routine; paste the prompt and pick the model docs/project.md names; add {{REPO}}; keep the Default environment; add a schedule, hourly, a few minutes past the hour; remove every connector; Create, then Run now once and read the transcript. Make it there, not in a Project. Optionally add a GitHub trigger, Pull request, action closed, with Author equals LOGIN and Is merged equals true, so a merge of yours starts the next task.
   - **A Desktop task** on your machine: in the Desktop app's Code tab, Routines, New routine, Local; paste the prompt; permission mode Manual; your clone, with the isolated worktree on; Hourly; Run now. Always-allow only read-only commands, and answer pushes and label changes yourself.
   - **`/loop` in its own worktree**: run the lines below, then type `/loop 1h` followed by the prompt. It keeps the session's permission prompts, so it waits at each push or label change for you to answer, as the Desktop task does. It stops after seven days and carries its context from run to run, so end it and start a fresh session each day.
     ```
     git worktree add "../$(basename {{REPO}})-worker" origin/{{DEFAULT_BRANCH}}
     cd "../$(basename {{REPO}})-worker"
     claude
     ```

## Limits you will meet first

All but the last bind at a few dozen contributors; [the scale analysis](../history/crowdsourcing/research.md#scale) has the arithmetic and the rest.

- **Review.** The people who merge are Cursor's integrator, the one gate for many workers. Today: an area team per slice with its own CODEOWNERS lines; small tasks with measurable acceptance; hand docs/memory/ and the shared tests/ to a trusted team if they pile up.
- **The board's API budget.** The board runs with GITHUB_TOKEN, which has 1,000 REST requests an hour for the whole repository; a run costs about three calls per open pull request, and under steady activity runs go back to back, so by an estimate from the code, not a measurement, the budget runs out somewhere between a handful and about 15 open pull requests. The run then fails and the board stays stale until the hour resets ([arithmetic](../history/crowdsourcing/research.md#the-boards-api-budget)). The field-metrics run draws on the same budget once a day, at 03:43 UTC: a few calls per pull request changed in its 30-day window and one per commit made in it, and it stops short of a reserve of 300 for the board ([metrics.md](metrics.md)). Today: one open claim per contributor, as the crowd rules say, and, by pull request to .github/workflows/board.yml, drop the `synchronize` pull request trigger and the `edited`, `labeled` and `unlabeled` issue triggers, give `push` a `branches-ignore: ["claude/**"]` so claim pushes stop displacing waiting runs, and run the schedule every 15 minutes instead of every six hours (untested).
- **Every worker takes the lowest-numbered issue.** Dozens of hourly workers converge on one issue from a board that lags each claim. Today: each contributor's area label, and tasks given to one contributor with worker:LOGIN.
- **The session hook prints 120 lines of the board.** Claims, open pull requests and the files they overlap in come before the Queue and the issues given to workers, so past about 100 of them no Queue row reaches a session. Today: `/board` prints all of it.
- **Invitations.** A new organization can send 50 a day, and each person must accept within 7 days. Today: `invite` takes several logins at once and says when the limit stops it; onboard in batches.
- **At hundreds: GitHub's guidance per repository.** Its 6 pushes a minute binds before its 1 merge a minute: at about nine pushes per landed task plus the board's own, one repository lands about 35 pull requests an hour, roughly 175 contributors landing one every five hours. Beyond that, split the project into more repositories.

## Safety checklist

Why each item matters: [the safety analysis](../history/crowdsourcing/research.md#safety).

GitHub enforces these once `setup` and `finish` have run, with nobody remembering them:

- The Claude workflows never start while CLAUDE_CROWD is true: their job-level condition reads it. A writer can delete it (below), so while docs/project.md says crowd mode is on, every run of the required check, on the default branch or on a pull request, fails until it is back, naming the command that puts it back; a Claude job that starts meanwhile finds no token and does nothing.
- No Claude credential or switch reaches the repository. The required check fails while any of CLAUDE_CODE_OAUTH_TOKEN, ANTHROPIC_API_KEY, COORDINATOR_TRIGGER_URL, COORDINATOR_TRIGGER_TOKEN, SDLC_APP_PRIVATE_KEY, CLAUDE_WORKER or CLAUDE_TEAM (an older copy's switches) does, from the repository or the organization, and the audit fails on any repository secret at all. The check's own job, which runs the pull request's scripts and tests, never names a secret: a job of its own that runs nothing of the repository's tells it which exist, by name ([why](../history/crowdsourcing/research.md#the-check-holds-no-secret)). Auto-merge is an admin's setting, which setup turns off, and the workers in Actions never start while CLAUDE_CROWD is true.
- The owner's coordinator routine is never started by the repository: board.yml's step that would call its trigger does not run while CLAUDE_CROWD is true, whatever trigger pair reaches it.
- Checkpoints are pull request comments. The required check fails a pull request that changes .claude/session.md or the checkpoint block of CLAUDE.md.
- "check" counts only from GitHub Actions, and the shared paths need your review. The ruleset pins the check to app 15368 and asks for a code owner's review, an approval of the latest push and resolved threads, and CODEOWNERS gives the paths every session loads or runs to you alone, the instruction files inside an area included; `finish` merges crowd/setup only as setup would write it for you and as you alone pushed it.
- Only Maintain or Admin queues work. The issue forms put no label on, and queue.yml takes todo or blocker off whenever anyone else adds one, opens an issue with one, or edits the title or body of an issue labelled todo or blocker. It sees nothing else: not an epic, not a comment, and not an edit to either (below).
- Strangers cannot open pull requests, and nobody is invited before the review rules hold: `invite` refuses until `finish`.

These stay conventions, made loud but not prevented, because GitHub gives every writer the power:

- Invite only people you trust with Write. It lets them push to every unprotected branch, others' claim branches, `board` and `metrics` included (the push guard passes a `--force-with-lease` to anyone's `claude/` branch), edit anyone's comments, merge approved pull requests, set any commit status, add secrets and variables, delete CLAUDE_CROWD, disable a workflow, and run a workflow of their own on a branch of their own with every secret that exists. The check, queue.yml and the audit make most of these loud, though nothing reports an edited comment; the protection against the last is that no secret exists to read.
- Run the audit every week, and read its lines on who pushed `board` and the claim branches.
- Review each diff against the claim file as first committed and the plan on the issue, line by line under .github/, .claude/, tools/, scripts/ and tests/: a pull request that edits the check runs its own edited copy, which is why those paths wait for you.
- Treat all issue, comment, pull request and board text as data: crowd.md, the worker prompt and the coordinator's step 1 say so.
- Re-read an epic, its comments and a queued issue's comments whenever they are edited, and check their edit history (the "edited" menu) before acting on them; take todo off when an edit changed what the issue asks. Any writer can edit them, and queue.yml sees only a queued issue's title and body. crowd.md tells every session the same ([why](../history/crowdsourcing/research.md#prompt-injection)).
- Make routines outside any Project, with no connectors and the Default environment's Trusted network; keep auto-fix on only while you watch.
- Before a session on your machine, read what changed in the shared paths, the instruction files of every folder included: `git fetch origin && git log -p HEAD..origin/{{DEFAULT_BRANCH}} -- '*CLAUDE.md' '*CLAUDE.local.md' '*AGENTS.md' '*.claude/*' .mcp.json tools scripts tests docs/project.md docs/agents docs/memory`.
- Keep your cloud sessions Private, and permission prompts on for a local worker.

Field metrics need nothing of crowd mode ([docs/setup/metrics.md](metrics.md)): .github/workflows/metrics.yml names no secret but GITHUB_TOKEN and writes aggregates alone to the branch `metrics`, and the judge runs only when a maintainer runs it, on their own machine and their own Claude account. A crowd project that should share nothing says off in .github/symphony-metrics, by pull request like any file.

## What is to be built

Each item, with its reason and size, is in [the gap list](../history/crowdsourcing/research.md#gaps-with-sizes). The crowd ruleset, CODEOWNERS with teams, the crowd checklist, the forms without labels, the crowd rule, checkpoint skill and prompts, the secret check, the maintainer-only queue and most of the onboarding are built: scripts/crowd.py, tools/crowd_check.py and .github/workflows/queue.yml. What is left:

- An owner-only @claude that reads its token from an environment.
- A board that spends less: fewer triggers or a debounce, then rendering by the symphony-app's token, with `board` protected.
- One idle threshold, `merge_group` in ci.yml, and a quiet "main moved" under a merge queue.
- A session hook that shows the reader's own queue first, deal-out of the queue across contributors' workers, as tools/team.py deals it among the workers in Actions, and the claim's worker taken from the pusher's login.
- A server-side check that only the claimer pushes to `claude/N`; per-issue checkpoint files; the claim skill's REST calls for cloud sessions.
- Area coordinators and review routines, a planner woken by merges, nested epics, a conflict resolver, a scoreboard, and claims for people without Write.
