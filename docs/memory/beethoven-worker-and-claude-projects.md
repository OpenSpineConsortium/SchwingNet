A Claude project cannot take the session Beethoven's worker starts by itself; it reaches the worker only through its own Work locally, so Beethoven 21.0.0 opens the project's page and says the three steps.

A Claude project (claude.ai/code/project/...) runs a thread on a machine only when the student
asks for the task inside the project with Work locally from the + menu and presses Allow once on
the card, with `claude remote-control` (2.1.280 or later) running in the folder; the worker's own
link is a plain session the project cannot adopt (code.claude.com/docs/en/claude-projects, read
2026-10-16). Beethoven 21.0.0 (beethoven-extension#17) therefore takes the project's address in
Settings and opens that page in place of the worker's link, which stays on New session, Copy
link and Phone. The worker's Claude Code 2.1.283 meets the minimum; it does not pass `--spawn
worktree`, and 2.1.283 refuses that together with the successor job's `--continue`, a choice left
to hpcworker. Whether the successor's resume brings a project's thread back after the job ends is
not yet measured. The research is docs/research/beethoven-worker-opening.md, and the two
adversarial reviews of 21.0.0 are docs/research/beethoven-21-reviews.md.

A merge to beethoven-extension's main is a release: its release.yml builds and keeps every push to
main as a GitHub release, and with the five CWS_ secrets set (2026-10-16) the repository variable
`CWS_ON_PUSH` decides the rest, upload sending each merge to the Chrome Web Store as a draft and
publish submitting it for review. A cloud session cannot read that variable, so it takes any merge
there as one that may reach students.
