A session with several repositories runs none of this repository's hooks: GitHub's ruleset, the claim lock, the required check, /board and the claim skill still hold there; the push guard, the board at session start and the Symphony-Usage trailer do not.

Claude Code runs a repository's hooks, permission rules and environment
(.claude/settings.json) only in a session with that one repository. A
claude.ai Project's thread made with several repositories, or one that
adds a repository to itself mid-session, runs none of them, by
Anthropic's rule (code.claude.com/docs/en/claude-projects, read
2026-10-13).

What stands on GitHub holds whatever the session runs: the default
branch's ruleset, the claim lock (GitHub refuses the second push of a
branch's name) and the required check. /board and the claim skill load in
every repository and read the board by forms that work in a clone made
for one branch, as a cloud session's is, where `git fetch origin board`
alone updates no remote-tracking branch: /board fetches
`+refs/heads/board:refs/remotes/origin/board`, the form CLAUDE.md,
docs/agents/PROTOCOL.md and .claude/rules/board.md give too, and the
claim skill first adds the fetch refspec `+refs/heads/*:refs/remotes/origin/*`.

What does not hold: the push guard, the board printed at session start,
and the commit-msg hook's Symphony-Usage trailer, so the cost metrics
count such a session's pull requests as unmeasured. Keep this repository
the Project's only resource; docs/setup/claude-project.md says the same
for the people making a Project.
