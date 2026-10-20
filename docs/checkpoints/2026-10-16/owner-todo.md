# The owner's to-do list, 2026-10-16

Nothing here is done by Claude: each item is the owner's own, with its link and what to click. It replaces docs/checkpoints/2026-10-15b/owner-todo.md for every item it lists; the items of that file and of docs/checkpoints/2026-10-14e/owner-todo.md it does not list (item 11 below) stand there unchanged. Times are UTC unless they say ET.

The one urgent item is the grant, due tonight, Friday 2026-10-16 at 11:59 p.m. ET (Saturday 03:59 UTC).

## Do now, most urgent first

### 1. The AIDaS grant (spine-program): submit tonight, by 11:59 p.m. ET

Dr. Han and Dr. Schwiebert both approved (11:19 and 11:54 a.m. ET), so only your submission is left; at 19:10 UTC your mail showed nothing sent to aidas@wayne.edu yet. The grant's own handoff, with the same steps, is https://github.com/OpenSpineConsortium/spine-program/blob/main/01_carm_level_detection/grants/aidas_2027/HANDOFF_2026-10-16.md .

1. Build the PDF in Overleaf: open your Overleaf project from the link in your e-mail of 7:51 a.m. ET ("AIDaS seed grant: final PDF for your approval"), or find it at https://www.overleaf.com/project ; click "Recompile", check that the PDF is 10 pages, and click "Download PDF" (the download button beside "Recompile"). Use this copy, not the PDF in the Project's files: Dr. Schwiebert updated both investigators' addresses after that one was built, most likely in Overleaf.
2. Run the disclosure audit (spine-program's CLAUDE.md rule 8): run spinesurg-ct-nnunet's tools/disclosure_audit.py over that PDF. It quotes the level model's held-out results (Figure 1f), so what reviewers may see is your call.
3. Submit: open https://outlook.office.com/mail/deeplink/compose?to=aidas@wayne.edu , click "Attach", pick the PDF, then click "Send", before 11:59 p.m. ET (03:59 UTC on Saturday). No connector can attach a file for you.

Later, at your pace:

4. Ask aidas@wayne.edu, with the submission or after it, whether lines B (the cadaver set), C3 (the $1,500 reimbursement), D (the FDA regulatory consultant) and F (the poster) are allowable, and how line A may be hired; the totals without them are in RECORD.md section 4.
5. Replace the 17 approximations as values come in: https://github.com/OpenSpineConsortium/spine-program/blob/main/01_carm_level_detection/grants/aidas_2027/APPROXIMATIONS.md lists each with its basis and who can confirm it. Send the values to a grant thread for a rebuild, with contacts.tex and the two biosketches from Overleaf (Menu, then "Source" under Download), or edit them in Overleaf.
6. The other submissions you plan, to Anthropic's AI for Science program and other fits, are yours; nothing about them is recorded.

### 2. Before you switch accounts (optional)

A new account cannot read this Project's shared folder, and nothing in it is needed to carry on: the work is in git and the grant's current copy is your Overleaf project. If you want the bench's logs and the agents' transcripts kept (about 45 MB; transcripts stay out of git), open the Project at https://claude.ai/code/project/chan_01JV1B5DpVW16Xd9rDo7wKF5 , open its files, and download coordbench/curse-1-logs-2026-10-16.tar.gz.

### 3. Approve the symphony-protocol 0.5.0 release

Open https://github.com/OpenSpineConsortium/symphony-protocol/actions/runs/38889703117 , press "Review deployments", tick "release", then press "Approve and deploy". Approve before any other change under .github/workflows/ merges in symphony-protocol, or the approved run fails and the release has to be made by hand; a run nobody reviews fails by itself after 30 days. Once it is published, the weekly sync brings 0.5.0 to symphony-template, and item 8 no longer comes up.

### 4. Switch on Sign in with GitHub for the control panel (six steps; you were at step 1)

1. Open https://github.com/organizations/OpenSpineConsortium/settings/apps/symphonyboard . Under "Client secrets" press "Generate a new client secret" and copy it at once, since GitHub shows it only once; it goes only into Cloudflare in step 4. Copy the "Client ID" at the top of the page. Under "Callback URL" put https://openspineconsortium.com/symphony/control/ , press "Add Callback URL" and put https://openspineconsortium.com/symphony/cost.html . Leave every other box as it is: keep "Request user authorization (OAuth) during installation" unticked, the "Setup URL" unchanged, and do not change the webhook secret. Press "Save changes".
2. Open https://dash.cloudflare.com/ (a free account is enough), open "Workers & Pages", press "Create application", then "Start with Hello World!", name it symphony-signin and press "Deploy".
3. Open https://github.com/OpenSpineConsortium/symphony-app/blob/main/signin/worker.js and press "Copy raw file"; on the Worker press "Edit code", replace everything with it and press "Deploy".
4. On the Worker open "Settings", then "Variables and Secrets", press "Add": type Text, name GITHUB_CLIENT_ID, value the Client ID; press "Add" again: type Secret, name GITHUB_CLIENT_SECRET, value the client secret; press "Deploy".
5. In the same "Settings", under "Observability", turn "Workers Logs" off.
6. Send the Worker's address (https://symphony-signin.<yours>.workers.dev) and the Client ID to the thread that picks this up (handoff.md, part 2.6), never the secret. One small site pull request then switches the button on.

Optional: for the panel's four "Run now" buttons to work through the sign-in too, on the same App page open "Permissions & events", set "Actions" to "Read and write" and press "Save changes"; each installation accepts it once.

### 5. Send Beethoven 21.0.0 for review

The store holds 21.0.0.108 as Beethoven's draft, uploaded at 18:49 UTC but not submitted.

1. Open https://chrome.google.com/webstore/devconsole , click Beethoven, then "Submit for review" at the top right. Or open https://github.com/OpenSpineConsortium/beethoven-extension/actions/workflows/release.yml , click "Run workflow", keep "main", tick "upload" and "publish", and click "Run workflow".
2. For every merge to go to the store on its own, open https://github.com/OpenSpineConsortium/beethoven-extension/settings/variables/actions and check that CWS_ON_PUSH is there with the value publish; if it is not, click "New repository variable" and add it. "Cancel review" in the store's dashboard withdraws a submission before Google approves it.

### 6. Symphony on the WSU grid (three steps)

The full page is https://github.com/OpenSpineConsortium/symphony-template/blob/main/docs/setup/grid.md .

1. Add the runner's tests to hpcworker's CI: open https://github.com/OpenSpineConsortium/hpcworker/edit/main/.github/workflows/ci.yml , find the step that runs `bash tools/tests/test_grid_ci.sh`, and paste these two lines right after it, indented like it:

   ```yaml
         - name: the grid's Actions runner (tools/grid_runner.sh; Slurm, gh, Apptainer and the runner stood in for)
           run: bash tools/tests/test_grid_runner.sh
   ```

   Press "Commit changes...", keep "Commit directly to the main branch" and press "Commit changes".
2. Start the runner: on the VPN open https://ondemand.grid.wayne.edu , then the "Clusters" menu, then the shell entry, and run `gh repo clone OpenSpineConsortium/hpcworker` (or `git -C hpcworker pull` if you have it), then `cd hpcworker && bash tools/grid_runner.sh --install --site wayne`. When `bash tools/grid_runner.sh --status --site wayne` shows "runner image:" with a version, run `bash tools/grid_runner.sh --start --repo OpenSpineConsortium/symphony-template --site wayne`. The runner shows as Idle at https://github.com/OpenSpineConsortium/symphony-template/settings/actions/runners ; to try it, open https://github.com/OpenSpineConsortium/symphony-template/actions/workflows/grid.yml , press "Run workflow", then the green "Run workflow".
3. Test whether a key alone gets in from off the VPN: in WSL run `ssh-keygen -t ed25519 -f ~/.ssh/grid_gate_test -N '' -C grid-gate-test`, then `cat ~/.ssh/grid_gate_test.pub`. In the grid's shell run `printf '%s\n' 'restrict,command="echo key-only sign-in works" PASTE' >> ~/.ssh/authorized_keys` with the printed line in place of PASTE. Turn the VPN off and run `ssh -i ~/.ssh/grid_gate_test -o IdentitiesOnly=yes -o PreferredAuthentications=publickey <your AccessID>@grid.wayne.edu`, and send what it prints to the grid thread. Then take the test key out in the grid's shell: `sed -i '/grid-gate-test/d' ~/.ssh/authorized_keys`. The ssh gate's pull request follows your result.

### 7. The Claude tokens, by the token wizard

In WSL, from your clone of symphony-template:

1. `git pull`
2. `gh auth refresh -h github.com -s admin:org`: it prints a code and opens https://github.com/login/device ; paste the code, press "Continue", then "Authorize github".
3. `python3 scripts/tokens.py --org OpenSpineConsortium --repos coordbench`: for each account you lend it asks for a slot and a word to tell the account by, tells you to sign in to claude.ai as that account, and runs claude setup-token for you; press "Authorize" on the page that opens. The token never appears on your screen.
4. For the workflows' own token: `python3 scripts/tokens.py main --org OpenSpineConsortium --repos symphony-template`.
5. If you made coordbench's own SYMPHONY_CLAUDE_ACCOUNTS variable by an earlier wording, delete it: open https://github.com/OpenSpineConsortium/coordbench/settings/variables/actions and press the delete icon beside SYMPHONY_CLAUDE_ACCOUNTS.

The page is https://github.com/OpenSpineConsortium/symphony-template/blob/main/docs/setup/claude-tokens.md . Before a real CooperBench run in Actions, also make the environment bench: open https://github.com/OpenSpineConsortium/coordbench/settings/environments , press "New environment", name it bench, tick "Required reviewers" and add yourself, leave "Prevent self-review" unticked, and limit "Deployment branches and tags" to main.

## Later, when it comes up

### 8. Close the weekly sync's downgrade (Monday 2026-10-19, after 06:17 UTC), unless 0.5.0 is published by then

The sync opens a symphony-template pull request titled "Vendor symphony-protocol 0.4.1"; it would undo every fix since 0.4.1. Open https://github.com/OpenSpineConsortium/symphony-template/pulls , open that pull request, press "Close pull request" at the bottom. No session fixes its check.

### 9. The flowbench pilot, when you want it

Write "run the pilot" in the thread "Agentic workflow benchmarks" (or in a new thread for flowbench on the new account): 8 SWE-bench Verified issues under solo, script and symphony, 24 runs, Sonnet 5.5 at medium effort unless you name others, about one to two five-hour windows of one account.

### 10. Approvals only you can give

- Each real CooperBench dispatch in Actions: on its run's page under https://github.com/OpenSpineConsortium/coordbench/actions press "Review deployments", tick bench, then "Approve and deploy".
- Once a real run works on the new secrets: remove COORDBENCH_CLAUDE_TOKEN from the old account's claude.ai cloud environment (the Project's settings, "Cloud environment", the gear beside the environment, "Environment variables"). Do not add it to a new account.
- If Symphony Setup is still installed on the organization from the canary's adoption: open https://github.com/organizations/OpenSpineConsortium/settings/installations , find "Symphony Setup", press "Configure", then the red "Uninstall" button.

## Unchanged in the earlier lists

### 11. Still open there, not rechecked on 2026-10-16

- https://github.com/OpenSpineConsortium/symphony-template/blob/main/docs/checkpoints/2026-10-14e/owner-todo.md : item 4 (spine-program's Actions setting, the archive run, the student route on issue #72, the onboarding document's comment), item 5 (housekeeping: the organization secrets' repositories, the old test repositories, "Automatically delete head branches", the leftover merged branches, Symphony Setup's description), item 6 (Beethoven 20.0.0's hand test; the store credentials are now set) and item 10 (the optional canary check C7, and the compiler plan's decisions 3 and 4).
- https://github.com/OpenSpineConsortium/symphony-template/blob/main/docs/checkpoints/2026-10-15b/owner-todo.md : item 8 (optional deep research for the taxonomy) and item 9 (before symphony-template is ever made public, publish a copy made without its history, since docs/checkpoints/ describes private repositories and this list's memory.md describes the private grant).
