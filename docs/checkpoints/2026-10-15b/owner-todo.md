# The owner's to-do list, 2026-10-15b

Nothing here is done by Claude: each item is the owner's own, with its link and what to click. It replaces docs/checkpoints/2026-10-14e/owner-todo.md for every item it lists; the items of that file it does not list (item 7 below) stand there unchanged. Times are UTC unless they say ET.

The one urgent item is the grant, due Friday 2026-10-16 at 11:59 p.m. ET (Saturday 03:59 UTC).

## Do now, most urgent first

### 1. The AIDaS grant (spine-program)

1. If the next session is on another account or in a new Project: before you switch, save a copy of AIDaS_SEED_2027_overleaf.zip and AIDaS_SEED_2027_submission_draft.pdf from this Project's files (the grant folder). In the new grant thread, attach the two biosketch PDFs again and paste the cover's two contact lines (Dr. Han's and Loren Schwiebert's office, phone and e-mail): the new account cannot read this Project's files, and those three are never committed.
2. Answer the two calls the grant thread put to you, in that thread:
   - The Claude seats: budget line C1 buys Team seats, while Beethoven's decision D1 asks for a plan in each trainee's own name. Say "amend D1" or "switch C1 to Pro plans".
   - CLAIM: the packet says Aim 1 "plans" the CLAIM checklist, since beethoven-research only names it as coming. Point the thread to the checklist if it exists and the packet will say "holds".
3. Paste Dr. Han's and Loren Schwiebert's answers into the grant thread as they reach your inbox. The e-mails asking for them went out from your Gmail on 2026-10-15 at 19:35; do not resend. Dr. Han's edits of 21:42 are already in (spine-program#103).
4. Fill the red [DATA NEEDED] marks that remain (16 at the build after #103; RECORD.md section 3 lists each): https://github.com/OpenSpineConsortium/spine-program/blob/main/01_carm_level_detection/grants/aidas_2027/RECORD.md . Give the values in the grant thread, or type them into Overleaf after step 8.
5. E-mail the AIDaS office at aidas@wayne.edu to ask whether the cadaver lines (B1 to B5), the FDA Pre-Submission line (D) and lines A and F are allowable, and whether DMC can be paid as a fee-for-service scan. The text is in the grant's resume file: https://github.com/OpenSpineConsortium/spine-program/blob/main/01_carm_level_detection/grants/aidas_2027/HANDOFF_2026-10-14e.md . An office that has not answered by 3 p.m. ET on Friday gets "estimate, quote requested" in the budget.
6. Your own checks before sending: the disclosure audit (spine-program's CLAUDE.md rule 8; the narrative quotes private SchwingNet results); what the award releases under the MIT License, and WSU's conflict-of-interest rules; that Elsevier has turned on the Scopus APIs, and the library's ScienceDirect text-and-data-mining amendment; the 2027 trainee cohort; references 4, 8 and 9. If you submit IRB protocol IRB-26-03-8648 first, tell the grant thread so "pending" changes.
7. The next session's grant thread finishes draft #107, the spine aim widened to the whole corpus, the C-arm work, the data mining and the hospital use case (https://github.com/OpenSpineConsortium/spine-program/pull/107), and rebuilds the zip and the PDF; submit after that. Keep the coordination experiment's numbers out of the grant unless you lift your hold of 18:01.
8. Submit: open https://www.overleaf.com , press New Project, then Upload Project, and pick the zip; press Recompile and check that the PDF is 10 pages and has no red [DATA NEEDED] mark left; download the PDF (the download icon beside Recompile) and e-mail it to aidas@wayne.edu by Friday 2026-10-16 at 11:59 p.m. ET.

### 2. Close the weekly sync's downgrade (Monday 2026-10-19, after 06:17 UTC)

The sync opens a symphony-template pull request titled "Vendor symphony-protocol 0.4.1"; it would undo every fix since 0.4.1. Open https://github.com/OpenSpineConsortium/symphony-template/pulls , open that pull request, press "Close pull request" at the bottom. No session fixes its check.

### 3. CooperBench in Actions: settings before a real run (steps 2 and 3 changed on 2026-10-16 for the token wizard)

1. Environment: open https://github.com/OpenSpineConsortium/coordbench/settings/environments , press "New environment" and name it bench; on its page tick "Required reviewers" and add yourself, leave "Prevent self-review" unticked (you both dispatch and approve), and limit "Deployment branches and tags" to main. If bench is listed already, open it and add only the reviewer.
2. Secrets, by the token wizard (symphony-template#100): in WSL, from your clone of symphony-template, run `git pull`, then `gh auth refresh -h github.com -s admin:org` (it prints a code and opens https://github.com/login/device: paste the code, press Continue, then Authorize github), then `python3 scripts/tokens.py --org OpenSpineConsortium --repos coordbench`. For each account you lend it asks for a slot and a word to tell the account by, tells you to sign in to claude.ai as that account, and runs `claude setup-token` for you: press Authorize on the page that opens. It stores SYMPHONY_CLAUDE_1, SYMPHONY_CLAUDE_2 and so on, seen by coordbench, and the token never appears on your screen. The page is docs/setup/claude-tokens.md.
3. Variable: the wizard keeps SYMPHONY_CLAUDE_ACCOUNTS as the organization's variable, seen by coordbench. If you made coordbench's own variable of that name by this step's earlier wording, delete it, since it would hide the organization's list from bench.yml: open https://github.com/OpenSpineConsortium/coordbench/settings/variables/actions and press the delete icon beside SYMPHONY_CLAUDE_ACCOUNTS. `python3 scripts/tokens.py status --org OpenSpineConsortium --repos coordbench` names it while it is there.

Your decision: which accounts, and how many. Use accounts nobody uses by hand, since a run draws on that account's five-hour window. Nothing runs until you approve a real dispatch (item 6).

### 4. The coordination experiment: each step up is yours

The experiment thread runs no bench work beyond what you chose. Your choice of 18:36 on 2026-10-15 was the full run: the remaining pairs under the five arms, batch by batch, xblossom left out (your 19:36 choice). Before it, the 12 runs the harness spoiled run again, since the step of 8 pairs' figures count 11 of them. The next thread names each batch's pair count and the usage windows it takes before it starts; answer it in that thread.

### 5. The canary repository

Adopted, and check C5 passed 3 of 3 when you ran it at 16:18 on 2026-10-15. If Symphony Setup is still installed on the organization: open https://github.com/organizations/OpenSpineConsortium/settings/installations , find "Symphony Setup", press Configure, then the red Uninstall button.

## Later, when a thread tells you

### 6. Approvals only you can give

- Release 0.5.0, when the protocol thread says it is ready: GitHub e-mails you; on the run's page under https://github.com/OpenSpineConsortium/symphony-protocol/actions press "Review deployments", tick release, then "Approve and deploy". Approve before any other change under .github/workflows/ merges, or the approved run fails and the release has to be made by hand. A run nobody reviews fails by itself after 30 days.
- Each real CooperBench dispatch: on its run's page under https://github.com/OpenSpineConsortium/coordbench/actions press "Review deployments", tick bench, then "Approve and deploy". One approval covers the whole dispatch.
- Once a real run works on the new secrets: remove COORDBENCH_CLAUDE_TOKEN from the old account's claude.ai cloud environment (the Project's settings, Cloud environment, the gear beside the environment, Environment variables). Do not add it to a new account.

## Unchanged, in the 2026-10-14e list

### 7. Still open there, not rechecked on 2026-10-15

https://github.com/OpenSpineConsortium/symphony-template/blob/main/docs/checkpoints/2026-10-14e/owner-todo.md holds each with its links and clicks:

- Item 4, spine-program: "Allow GitHub Actions to create and approve pull requests", the archive run from WSL, the student route on issue #72, the onboarding document's open comment.
- Item 5, housekeeping: limit the organization secrets to their repositories; delete the five old test repositories; "Automatically delete head branches" in six repositories; the leftover merged branches (sessions cannot delete branches); Symphony Setup's description.
- Item 6, Beethoven 20.0.0: the hand test, the Chrome Web Store upload, the store API credentials and the five CWS_ secrets.
- Item 10, the optional canary check C7, and "Decisions you can make any time" (the compiler plan's decisions 3 and 4).

## Optional

### 8. Deep research for the taxonomy

Open the manual (https://claude.ai/code/artifact/c42e4d26-b238-4834-bb7b-318ae086152c, a Claude Doc of this account; from another account, its copy https://github.com/OpenSpineConsortium/symphony-template/blob/main/docs/checkpoints/2026-10-15b/taxonomy/manual.md), copy the prompt in its section 3, paste it into a new chat at https://claude.ai with Research turned on, and bring the report back to the taxonomy thread.

### 9. Before symphony-template is ever made public

docs/checkpoints/2026-10-15b/taxonomy/ describes Beethoven's private repositories. The repository is internal today. Removing the folder by pull request still leaves it in the repository's history, so before you ever make the repository public, publish a copy made without that history rather than switching this one's visibility.
