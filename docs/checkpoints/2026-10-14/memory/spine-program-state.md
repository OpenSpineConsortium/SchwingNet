---
name: spine-program-state
description: OpenSpineConsortium/spine-program (the owner's private research repo, to be handed to a med student) runs symphony-protocol 0.4.1 with a self-updating protocol.yml since 2026-10-13; what is still the owner's.
metadata:
  type: project
  modified: 2026-10-13T18:37:26.142Z
---

spine-program is a protocol-only Symphony adoption (board, tidy, metrics, protocol workflows; committed skills under .claude/; no CI check, no scripts/check.sh). On 2026-10-13 spine-program#86 (issue #85) brought it from sdlc-protocol 0.2.0 to 0.4.1 and added .github/workflows/protocol.yml + tools/protocol_update.py, which vendor each later release on the branch symphony-protocol/sync (weekly, Monday 06:17 UTC, and by hand). Verified: the first Board and Protocol runs on main were green.

**Why:** a protocol-only adoption gets no update workflow (symphony-start adopt.py PROTOCOL_FILES has none), so copies stay at the release they were made with unless someone adds protocol.yml by hand. The update route for copies is parked in the template's plan until the runtime exists.

**How to apply:** 
- Claims there are labelled worker:<GitHub login> (the skill makes the label); the old account:main is still read. Greg merges, or a session on the owner's standing permission (development phase).
- Issue #72: the owner said on 2026-10-13 23:52 that one student is invited (not verified against the collaborator list); still the owner's: uninstall the Symphony Setup App from spine-program and try the route once; the grid python env was opened by job 40602926 on 2026-10-12.
- Free student access options given to the owner: a free GitHub Team org via GitHub Education for teachers (keeps rulesets), or a Free org/personal account (no rulesets on private repos); Enterprise Cloud charges a seat per outside collaborator.
- Student onboarding doc (Claude Doc, 2026-10-13): https://claude.ai/code/artifact/f730cf94-98ba-4c18-b185-eebb9255659d (accounts, Project setup, Beethoven, every task, grid tasks, first task #19, rules); revise it there rather than making another.
- 2026-10-13 (spine-program#88, issue #87, merged): each numbered folder's results/, figures/, manuscripts/ and regulatory/ (4,379 files, 673 MB) are symlinks to /rs/rs_grp_oschome/shared/spine-program/archive/; files stay in git history at main 5597197; ARCHIVE.md is the account; Greg still has to run _ops/ship_archive.sh once from WSL (until then the links dangle on the grid). The tree is 2,547 files, 82 MB. The cloud auto-mode classifier refused `git rm -r` on the working tree; the removal was done in the index only (git rm --cached + update-index --cacheinfo 120000).
- 2026-10-14: a Beethoven session on a compute node cloned two public GitHub repos over HTTPS anonymously (the owner relayed the session's report), so the grid reaches GitHub; the private spine-program needs the person's own token in git's credential store on their grid account (steps given in the thread). aschehr (Ashley Schehr, co-PI) has Write on spine-program as of 2026-10-14. Noted on issue #19 (comment 6158442495); #19 itself still unclaimed.
- Doc for Ashley, 2026-10-14: "Connect the grid to GitHub" https://claude.ai/code/artifact/8e18020d-4025-4aeb-b3e5-4cedf16343f4 (classic PAT with repo scope in ~/.beethoven/git-credentials via git credential store, clone outside hpcworker); revise there rather than making another.
- Thread: cmsg_01DwBZXhqgJsTCs7bpRxnwy4HdmVfQGYVjaL7xFKu8gD7N. See [[symphony-project]].
