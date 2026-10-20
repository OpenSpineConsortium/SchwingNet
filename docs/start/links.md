# Every settings page, as a link

Put your repository for ORG/NAME (ORG is the user or the organization that owns it) and your organization for ORG. The GitHub links are the paths this project's scripts and setup pages already use; GitHub's own documentation names the pages only by their menus, given in the second column, so the menu still finds a page if a path ever moves.

## GitHub repository

| Link | In the menus | What you do there |
| --- | --- | --- |
| https://github.com/ORG/NAME/settings | Settings | under Pull Requests, "Allow auto-merge" and "Automatically delete head branches"; "Template repository" for the template itself |
| https://github.com/ORG/NAME/settings/rules | Settings, Rules, Rulesets | New ruleset, Import a ruleset: docs/setup/ruleset-main.json |
| https://github.com/ORG/NAME/settings/security_analysis | Settings, Advanced Security | secret scanning, then push protection |
| https://github.com/ORG/NAME/settings/secrets/actions | Settings, Secrets and variables, Actions | the secrets: CLAUDE_CODE_OAUTH_TOKEN, COORDINATOR_TRIGGER_URL, COORDINATOR_TRIGGER_TOKEN, SDLC_APP_PRIVATE_KEY |
| https://github.com/ORG/NAME/settings/secrets/actions/new | the same, New repository secret | one new secret |
| https://github.com/ORG/NAME/settings/variables/actions | the same, Variables tab | CLAUDE_ALLOWED_TOOLS, CLAUDE_CROWD, SDLC_APP_ID, SDLC_METRICS; workers are files, not variables (the registry, below) |
| https://github.com/ORG/NAME/settings/variables/actions/new | the same, New repository variable | one new variable |
| https://github.com/ORG/NAME/settings/actions | Settings, Actions, General | whether Actions run, the default token's rights, and under Workflow permissions "Allow GitHub Actions to create and approve pull requests", which setup-repo.sh turns on |
| https://github.com/ORG/NAME/settings/access | Settings, Collaborators & teams | Write for each person who claims issues, once the secrets above are out of the repository ([team.md](team.md), step 1) |
| https://github.com/ORG/NAME/settings/installations | Settings, GitHub Apps | see that the Claude GitHub App reaches this repository |
| https://github.com/ORG/NAME/labels | Issues, Labels | the six labels, and `worker:<name>` per worker |
| https://github.com/ORG/NAME/issues/new?template=task.yml | Issues, New issue, Task | a piece of work for the queue, labelled todo |
| https://github.com/ORG/NAME/issues/new?template=blocker.yml | Issues, New issue, Blocker | something that stops everyone |
| https://github.com/ORG/NAME/issues/new?template=worker.yml | Issues, New issue, Add a worker | a routine or a worker in Actions for the registry; its workflow opens the pull request that adds the file and answers with what to do next |
| https://github.com/ORG/NAME/tree/main/.github/symphony/workers | Code, .github, symphony, workers | the registry: one file per routine or worker in Actions ([WORKERS.md](../agents/WORKERS.md)) |
| https://github.com/ORG/NAME/blob/board/STATE.md | the branch board, STATE.md | the board |
| https://github.com/ORG/NAME/branches | Code tab, branches | the claim branches |
| https://github.com/ORG/NAME/blob/main/.github/CODEOWNERS | Code, .github, CODEOWNERS | GitHub marks a line it cannot resolve |
| https://github.com/ORG/NAME/actions/workflows/board.yml | Actions, Board | the board's runs, with the coordinator's releases and overlap comments in their log; Run workflow |
| https://github.com/ORG/NAME/actions/workflows/claude.yml | Actions, Claude | @claude's runs |
| https://github.com/ORG/NAME/actions/workflows/workers.yml | Actions, Workers | the workers in Actions, a leg per worker; Run workflow |
| https://github.com/ORG/NAME/actions/workflows/coordinator.yml | Actions, Coordinator | the coordinator's planning of epics, settling of blocked tasks, integrating and weekly tidying; Run workflow |
| https://github.com/ORG/NAME/actions/workflows/add-worker.yml | Actions, Add a worker | the runs that turn the form's answers into a pull request |
| https://github.com/ORG/NAME/actions/workflows/template-init.yml | Actions, Template init | the first push's run |
| https://github.com/ORG/NAME/actions/workflows/metrics.yml | Actions, Metrics | the daily field-metrics runs, and one by hand after setting SDLC_METRICS ([metrics.md](../setup/metrics.md)); Run workflow |
| https://github.com/ORG/NAME/blob/metrics/METRICS.json | the branch metrics, METRICS.json | the aggregates the repository shares, or that sharing is off |

Making a repository:

| Link | What it does |
| --- | --- |
| https://github.com/new?template_owner=OpenSpineConsortium&template_name=symphony-template&owner=OpenSpineConsortium&visibility=private | "Use this template", for a member of the template's enterprise: a private repository in an organization of the enterprise (put another one of its organizations for `owner` if you make repositories there); a public one publishes the internal template's files and history and needs the template's owner's agreement first |
| https://github.com/new?template_owner=TEMPLATE_OWNER&template_name=TEMPLATE_NAME&owner=@me&visibility=public | the same from the public copy, for anyone else; an organization's name in place of `@me` makes it there |
| https://github.com/apps/symphonyboard/installations/new | the front door, for anyone outside the enterprise: install the Symphony App on a repository of your own, press Create on the form GitHub sends you to (https://github.com/OpenSpineConsortium/symphony-start/issues/new?template=adopt.yml, where you name the repository instead when you come on your own), and a pull request with the whole template, or the protocol alone, is open there within about two minutes ( with the Setup App installed too, https://github.com/apps/symphony-setup/installations/new, the run also applies the repository's settings, the ones scripts/setup-repo.sh applies, and you uninstall it afterwards); it answers once the front door's owner has set it up |
| https://github.com/account/organizations/new?plan=free | a new organization on the Free plan |

## GitHub organization, and your own account

| Link | In the menus | What you do there |
| --- | --- | --- |
| https://github.com/organizations/ORG/settings/installations | organization Settings, Third-party Access, GitHub Apps | Configure an app's Repository access: All repositories, or Only select repositories |
| https://github.com/organizations/ORG/settings/member_privileges | organization Settings, Member privileges | what members may do by default |
| https://github.com/organizations/ORG/settings/security | organization Settings, Authentication security | require two-factor authentication for everyone |
| https://github.com/organizations/ORG/settings/rules | organization Settings, Rules | organization rulesets (GitHub Team and up): docs/setup/ruleset-org.json |
| https://github.com/organizations/ORG/settings/actions | organization Settings, Actions, General | under Workflow permissions, "Allow GitHub Actions to create and approve pull requests", which a new repository inherits and which, held off here, can keep a repository from turning it on |
| https://github.com/organizations/ORG/settings/secrets/actions | organization Settings, Secrets and variables, Actions | organization secrets, with which repositories see them |
| https://github.com/organizations/ORG/settings/variables/actions | the same, Variables tab | organization variables |
| https://github.com/orgs/ORG/teams | the organization's Teams tab | the teams crowd mode makes |
| https://github.com/orgs/ORG/invitation | the invitation | accept an invitation to ORG |
| https://github.com/settings/security | your Settings, Password and authentication | your own two-factor authentication |
| https://github.com/settings/installations | your Settings, Applications, Installed GitHub Apps | the apps on your personal repositories |
| https://github.com/settings/applications | your Settings, Applications, Authorized OAuth Apps | revoke the gh token that /web-setup sent (entry GitHub CLI) |
| https://github.com/apps/claude | the Claude GitHub App | what it is and what it may do |
| https://github.com/apps/claude/installations/new | the same, Install | install it on an account or organization, for chosen repositories |

## Claude

| Link | What you do there |
| --- | --- |
| https://claude.ai/code | cloud sessions: start, list and review them; Sign in with GitHub on the first visit |
| https://claude.ai/code?prompt=PROMPT&repositories=ORG/NAME&environment=ENVIRONMENT | a new session with its box filled in; URL-encode each value ([parallel.md](parallel.md), step 2, prints them) |
| https://claude.ai/code/new | a new session, from a phone |
| https://claude.ai/code/routines | routines: New routine, Run now, Edit |
| https://claude.ai/code/projects/browse | Projects (Pro and Max, in beta): New project |
| https://claude.ai/customize/connectors | your connectors; disconnect GitHub here |
| https://claude.ai/settings/usage | your plan's usage |
| https://claude.ai/mobile | the Claude app, for the Code tab on a phone |
| https://claude.ai/admin-settings/connectors | Team and Enterprise Owners: turn on the GitHub connector |
| https://claude.ai/admin-settings/claude-code | Team and Enterprise Owners: Quick setup, and routines on or off |
| https://claude.ai/admin-settings | Team and Enterprise Owners: Cloud environments shared with the organization |
| https://claude.com/pricing | the plans |

Cloud environments have no page and no link of their own: at https://claude.ai/code select the cloud icon with the current environment's name, in the row above the message box, then Cloud, Add cloud environment, or the gear beside an environment to edit it. In the Desktop app it is the environment menu in the prompt box, Cloud; in a routine, Edit, then the cloud icon below Instructions.

Claude Code's own documentation, for the details behind these pages: [cloud sessions](https://code.claude.com/docs/en/claude-code-on-the-web), [the web quickstart](https://code.claude.com/docs/en/web-quickstart), [cloud environments](https://code.claude.com/docs/en/cloud-environments), [routines](https://code.claude.com/docs/en/routines), [Projects](https://code.claude.com/docs/en/claude-projects), [GitHub Actions](https://code.claude.com/docs/en/github-actions), [authentication](https://code.claude.com/docs/en/authentication), [installing](https://code.claude.com/docs/en/setup) and [legal and compliance](https://code.claude.com/docs/en/legal-and-compliance).
