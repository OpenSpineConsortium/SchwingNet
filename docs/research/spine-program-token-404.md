# Why Add Token and Add people failed on spine-program

Source: the thread "Tokens and adopted repositories" in the symphony_2 Project, 2026-10-20, from the owner's report of the Tokens page and the Share tab on OpenSpineConsortium/spine-program; checked against the Sync run https://github.com/OpenSpineConsortium/symphony-template/actions/runs/39288858429 and spine-program's tree at its default branch.

## What the owner saw

Add Token, from an invited collaborator's sign-in, stopped with a 404 for .github/workflows/token.yml and said SymphonyBoard is not installed on spine-program. Add people stopped with "you must administer OpenSpineConsortium/spine-program, and SymphonyBoard needs its Administration permission accepted".

## What is true

- spine-program has no workflow Token: its workflows are board.yml, metrics.yml, protocol.yml and tidy.yml. It was adopted for the protocol alone, before adoptions brought the Token (symphony-start #76).
- The handoff of 2026-10-19 expected a symphony/sync pull request there, but none was ever opened. The sync's first run counted 2 repositories as "whole template", and spine-program is one: tools/sync_adopted.py took .github/workflows/protocol.yml as the mark of a whole template's copy, and spine-program carries that workflow (it merged symphony-protocol/sync #210) while it has no scripts/check.sh and none of the template's tests. A whole template's copy is left to its own update route, so spine-program was never offered the Token.
- SymphonyBoard is installed on the organization with "All repositories", so it does reach spine-program; the page's own check, which reads the repository before choosing its hint, found it reached and went on to the adoption hint. The 404 was the missing file, and the words "SymphonyBoard is not installed there" came from the generic 404 text placed in front of the hint.
- Inviting a collaborator is GitHub's to allow only to an administrator of the repository, so a collaborator with Write is refused whatever the App holds; the sign-in also needs SymphonyBoard's Administration permission accepted on the organization's installation.

## What changed

- tools/sync_adopted.py now takes a repository as a whole template's copy only where it holds both protocol.yml and scripts/check.sh. Run against spine-program's tree, the plan offers 12 files: the board's, metrics and Token workflows with their scripts (tokens.py, pool.py, sealbox.py, token_run.py, usage.py, profile.py, economics.py), and holds nothing back; the library is already current.
- The control panel's text (a patch handed to the control panel's thread): the Token's 404, once the repository is reached, says only that the file is missing and points at an open symphony/sync pull request when there is one; the invitation's refusal says that only an administrator may invite.

## Where it stands

The sync ran on the merge of symphony-template #262 and opened spine-program #213, which merged on 2026-10-20 with the 12 files above; spine-program's default branch now holds .github/workflows/token.yml. Add Token there still waits on the organization's SDLC_APP_ID and SDLC_APP_PRIVATE_KEY reaching the repository, and the environment token-store, which the first lend makes unless the owner makes it first and limits it to main. Add people waits on an administrator and on SymphonyBoard's Administration permission accepted on the organization's installation. The real test is the owner's.

## The environment by setup, not by hand

The owner asked on 2026-10-20 that token-store be made by the setup, not by a step per repository. Symphony Setup's adoption run (symphony-start's scripts/setup.py, step 8) and scripts/setup-repo.sh from a clone now make it, limited to the default branch, unless the repository has an environment of that name, which is left as it is. The Setup App tells whether the environment is there from its custom deployment rule integrations (GET .../deployment_protection_rules/apps), which Administration reads, since GitHub's permission table gives the environment's own read to Actions: read, which the App does not hold; that a missing environment answers 404 there is read from the REST description and not yet seen on a live run. Where the branch rule is refused after the environment is made, the environment stands with no branch allowed, so nothing runs there until the rule is added. A repository adopted before this gets it by a run of scripts/setup-repo.sh, or by hand; the Setup App acts only during an adoption run. As token-add-faults.md says, the environment fences the Token workflow's script, not the App's key, which stays an organization secret other workflows read.

## The second 404: the pool's settings variable (2026-10-20)

Run #4 of Add Token on spine-program (https://github.com/OpenSpineConsortium/spine-program/actions/runs/39435492291) signed in, held the token and stopped with "GitHub answered 404 when the run tried to mark slot 1 as yours in SYMPHONY_CLAUDE_SETTINGS". The calls before it, reading the organization's secrets list and slot 1's secret, were answered, so the installation token holds organization Secrets; the first call on an organization variable, the read and then the write, were the ones refused. GitHub answers 404 there when the installation lacks the organization permission Variables (inferred: the session cannot read the installation's permissions or the organization's variables). The App asks for Variables (read and write), so the likely cause is that its newer permissions are still waiting for an owner's acceptance on the organization's installation, the same request that holds Administration for the Share tab. The fix is that acceptance, which only an owner can give, at https://github.com/organizations/OpenSpineConsortium/settings/installations. tools/token_run.py now reads GitHub's X-Accepted-GitHub-Permissions header on such a refusal and says which permission is missing and where to accept it, so the next refusal names its own cause.
