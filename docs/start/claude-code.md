# A new project from Claude Code

You stay in Claude Code on your own computer: it makes the repository, the two Symphony Apps fill it with the whole template by pull request, and it opens a cloud session on the repository. The browser opens twice, because GitHub lets no API install an App: once for the two Symphony Apps and the form's Create, once for the Claude GitHub App. ORG/NAME is the new repository; [README.md](README.md) says how to read the blocks.

The whole page is one skill of the symphony plugin, `/symphony:new ORG/NAME`, which does the steps and hands you the two links. Install the plugin once in Claude Code, `/plugin marketplace add OpenSpineConsortium/symphony-marketplace` then `/plugin install symphony@symphony-marketplace`, or do the steps by hand below.

## Before you start

Claude Code signed in to your own claude.ai account (Pro, Max or Team, or an Enterprise seat with Claude Code, with cloud sessions allowed by your Owner at https://claude.ai/admin-settings/claude-code on Team and Enterprise), gh signed in to your GitHub login (`gh auth login`), git and Python 3.12 or later, as [solo.md](solo.md)'s "Once per machine" says. A cloud session cannot run steps 1 and 2: its GitHub proxy refuses them.

## Steps

1. **Make the repository, with a first commit.** The adoption needs one, and the README it makes is replaced by the template's:

   ```bash
   gh repo create ORG/NAME --private --add-readme --description "A Symphony project"
   OWNER_ID=$(gh api users/ORG --jq .id)
   REPO_ID=$(gh api repos/ORG/NAME --jq .id)
   echo "$OWNER_ID $REPO_ID"
   ```

   `--public` where the plan enforces branch rules only on a public repository ([tiers.md](../setup/tiers.md)); an organization answers `gh api users/ORG` as a user does. You should see the two numbers.

2. **See whether SymphonyBoard already reaches it.** An installation on ORG with `all` reaches every repository ORG makes; with `selected`, the second line says whether NAME is on its list:

   ```bash
   gh api user/installations --jq '.installations[] | select(.app_slug == "symphonyboard") | [.id, .account.login, .repository_selection] | @tsv'
   gh api user/installations/ID/repositories --jq '.repositories[].full_name'
   ```

3. **Open one link, in the browser.** It carries the repository, so every page comes with it already chosen, and `state` carries its name to the form.

   - SymphonyBoard does not reach it yet: `https://github.com/apps/symphonyboard/installations/new/permissions?target_id=OWNER_ID&suggested_target_id=OWNER_ID&repository_ids[]=REPO_ID&state=ORG/NAME`. GitHub installs SymphonyBoard on that one repository and sends you on to Symphony Setup's install page (the Symphony browser extension carries the selection to it; without the extension, pick the repository there), and that install sends you to the form with the repository filled in. Press Create, with Kind on Auto and Merge on "Merge the pull request for me".
   - SymphonyBoard reaches it already: `https://github.com/apps/symphony-setup/installations/new/permissions?suggested_target_id=OWNER_ID&repository_ids[]=REPO_ID&state=ORG/NAME`, which lands on the form the same way. Never open the SymphonyBoard link for an account that has it on all repositories: an installation has one repository list, and the link would narrow it to this one repository. On an organization whose installation is "Only select repositories", add the repository under Configure at `https://github.com/organizations/ORG/settings/installations` first, then open the Symphony Setup link.

   You should see the form's issue on https://github.com/OpenSpineConsortium/symphony-start/issues answered within about two minutes.

4. **Wait for the pull request and its merge.** The run opens it from the branch symphony/adopt and merges it, as you asked on the form:

   ```bash
   gh pr list --repo ORG/NAME --head symphony/adopt --state all --json number,state,mergedAt
   ```

   You should see `"state": "MERGED"` within about two minutes. Open, because you chose to review it first: merge it at its page, or `gh pr merge N --repo ORG/NAME --merge --delete-branch`. Nothing after five minutes: the run refused the request and said why on it, at https://github.com/OpenSpineConsortium/symphony-start/issues?q=is%3Aissue+author%3A%40me; do what it says. The sweep is the fallback: an account with SymphonyBoard on all its repositories gets the pull request within about an hour without the form, with no settings applied and the pull request left open; then merge it, clone, and run `bash scripts/setup-repo.sh` from the clone for the settings and the topic ([solo.md](solo.md), step 3).

5. **Install the Claude GitHub App.** It lets the cloud clone the repository itself and pushes every cloud session's work. Clone and run `/install-github-app` in Claude Code, pick the repository, and choose "Skip for now" when it offers the Actions setup, since the token for @claude is a later choice ([claude-action.md](../setup/claude-action.md)):

   ```bash
   gh repo clone ORG/NAME
   cd NAME
   claude
   ```

   Or open `https://github.com/apps/claude/installations/new/permissions?target_id=OWNER_ID&repository_ids[]=REPO_ID`. You should see Claude at https://github.com/ORG/NAME/settings/installations. Without the App, `claude --cloud` still works by bundling the clone and uploading it, and `/web-setup` lends the session your gh token instead; the App is the cleaner way. The merge also opened the issue "Set up this project" in the repository, whose checklist is the rest of the setup; the first cloud session can take it.

6. **Open the cloud session**, from the clone with nothing unpushed, since the cloud clones the remote's branch and not your checkout. Pick the environment once with `/remote-env` inside `claude`, then:

   ```bash
   claude --cloud "Read the board, take the next issue as docs/agents/routines/worker.md's steps 2 to 5 say, claim it with the claim skill and carry it to a ready pull request; work on the branch claude/<issue>, not this session's own branch. gh issue and gh pr are refused in a cloud session, so add the labels, post the plan and open the draft pull request with your GitHub tools or gh api. Mark the pull request ready with your GitHub tool update_pull_request (draft false), not gh api. Do not merge."
   ```

   It creates the session on claude.ai and returns; open it at https://claude.ai/code or in the Claude app. Each further `claude --cloud` is another session on the same repository, and the board keeps them apart ([parallel.md](parallel.md)). The link that fills the box at claude.ai/code instead, where nothing starts until you send, is in parallel.md, step 2.

7. **A Project, for many threads on one repository.** At https://claude.ai/code (Pro and Max; the beta reaches accounts gradually), make a Project and link ORG/NAME as its only resource, leaving its instructions, description and memory blank ([claude-project.md](../setup/claude-project.md)): every thread of it is a cloud session that starts from a fresh clone and reads the repository's CLAUDE.md, memory and board, so nothing is copied into the Project. A message in the Project's conversation starts a thread per task, threads run in parallel, and the board keeps them apart, each on its own issue; a session started in step 6 moves into the Project from its menu ("Move to project"); the worker routine is made inside the Project ([worker.md](../agents/routines/worker.md)). A Project belongs to one account and cannot be shared, and no command or API makes one: claude.ai alone does. What is shared is the repository: another person works it from a Project of their own, on their own account and plan, once they have Write on it (`gh api -X PUT repos/ORG/NAME/collaborators/LOGIN -f permission=push`) and the Claude GitHub App's installation reaches it; take the secrets out of the repository first ([team.md](team.md), step 1).
