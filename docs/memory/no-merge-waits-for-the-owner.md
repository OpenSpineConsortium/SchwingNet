No merge waits for the owner since 2026-10-31 03:45 UTC: a pull request merges once its checks are green; owner-ok holds only a non-admin person's.

The owner's words, 2026-10-31 03:45 UTC: "PLEASE FROM NOW REMOVE ALL OWNER REQUIRED PERMISSION FOR MERGING PRS!" They widen the word of 2026-10-30 22:55 UTC that the tap was meant only to keep a collaborator's code out of main.

- A session merges its own pull request once its tests and required checks are green, never asking.
- .github/workflows/owner-ok.yml passes at once for an admin's pull request and for a bot's (the synthesis workflow, the research loop, the SymphonyBoard App), so they land through automerge.yml; it still asks the owner's tap of a person who may write without administering the repository, or whose role GitHub does not give, until the owner says otherwise.
- The research loop's brief (.github/symphony/research.md) lets its pull requests merge on green.
- The organization ruleset "Require owner approval to merge" is the owner's to disable at github.com/organizations/OpenSpineConsortium/settings/rules (docs/setup/github.md, section 10); a session cannot change organization rulesets.
