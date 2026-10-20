---
name: setup-app-org-settings
description: What Symphony Setup does at adoption since 2026-10-19 (stays installed, check pin, settings.json list, org token lending); read before touching symphony-start setup.py or the Setup App's permissions.
metadata:
  type: project
  modified: 2026-10-19T11:56:05.430Z
---

As of 2026-10-19 (symphony-start #69, #72; privacy statement 32):
- Symphony Setup stays installed after an adoption. This was greg's card choice "Keep installed". It acts only during an adoption run.
- In mode new, the run waits up to 10 minutes for GitHub Actions to report "check" on symphony/adopt. It reads that with a SymphonyBoard checks:read token, then pins the ruleset's "check" to integration 15368.
- settings.json in symphony-start is the one list of every adoption setting. tests/test_settings_list.py fails when setup.py disagrees with it. This answers greg's 01:51 ask that every settings change be tracked and reproduced.
- Organization token lending: Setup has organization Secrets and Variables write, which greg approved at 09:32 UTC. It adds the new repository to the requester's own pool secrets.
  - A slot is the requester's only when its login matches (case ignored) AND its uid equals issue.user.id.
  - It never lends a slot with no uid, nor one with keeping=organization (symphony-template#253).
  - It lends SYMPHONY_CLAUDE_ACCOUNTS and SYMPHONY_CLAUDE_SETTINGS only when a requester token is usable there.
  - The public log has one line: "token lending: tokens lent" or "token lending: no tokens lent".
- Privacy statement wording for symphony-start is owned by the Control panel sign-in thread. Any behaviour change needs the next version to go live before the merge.
- Mismatches still open between the template's scripts/setup-repo.sh and setup.py:
  - The Actions pull-request box: setup-repo.sh ticks it in every repository, setup.py only in mode new.
  - The required "check" in mode existing: setup-repo.sh always requires it, setup.py drops it.
  - Where the pin reads the check: setup-repo.sh reads the default branch, setup.py reads the adoption head.
  - Only setup-repo.sh has --var/--token and the crowd guard.
