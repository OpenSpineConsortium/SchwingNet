# The textbook as a claude.ai artifact: why the book goes to claude.ai, and from where

Source: the textbook thread of 2026-10-24 (issues #233 and #236), the owner's decision card of 18:15 UTC and the change of plan of 18:42 UTC; the measurements were taken from the cloud session's container on 2026-10-24 and are quoted here, with no transcript.

## The question

The owner asked on 2026-10-24 for the artifacts themselves in the book, interactive, not screenshots (#233), and then for the book itself to live on claude.ai with Claude inside its pages (#236). Two ways were open: bring the live claude.ai artifacts into the members-only Pages site, or take the book to claude.ai as one artifact. Which of the two is possible decided the design.

## The finding: a live artifact cannot be framed from anywhere else

On 2026-10-24 the cloud session fetched the headers of a live artifact page from this container with curl. The page answers `content-security-policy: frame-ancestors 'self' chrome-extension://fcoeoabgfenejglbffodgkkbkcdhcgfn chrome-extension://dngcpimnedloihjnnfngkgjoidhnaolf`, and the artifact's own content is served from a per-artifact frame origin, `<uuid>.frame.claudeusercontent.com`, which the claude.ai page frames. A browser obeys frame-ancestors before it renders, so a page on any other origin, the Pages site included, gets a blank frame; the two extension ids name Anthropic's own browser extensions, which a web page cannot borrow. Nothing a repository holds, no token, no header and no proxy of ours, changes that, and the project keeps no server. Grade: Measured, by the header read on that day; it holds until claude.ai changes its policy.

So #233 embeds the exported copies under artifacts/ in the Pages site, in sandboxed iframes, and #236 goes the other way round: the whole site, with the exported pages inside it, is published as one multi-page artifact, where the exported pages are pages of the same artifact and open as themselves.

## Where the publish may run

Three places were tried or weighed.

- A cloud session, publishing with its Artifact tool. On 2026-10-24 the session's safety guard refused the publish of the built edition as data exfiltration, even with the owner's decision card in the conversation: the edition is the whole confidential book, and a guard that reads a hundred megabytes of patent material leaving a repository for a hosted page refuses it whatever the person says. A retry from the cloud on the owner's own words was not tried.
- The owner's machine, by a slash command a session runs there, the first plan of #236. It works, and it puts the republish after each merge in a person's hands or a routine's.
- A GitHub Action, the owner's choice at 18:42 UTC: on every push to main that changes the book, from a session anthropics/claude-code-action runs on the repository's Claude token, the subscription token already kept for the synthesis reads (the one exception to the rule that no Claude credential is kept anywhere, the owner's choice of 2026-10-23). Nobody is present, nothing of the book is read by a person, and the artifact lands in that account's gallery, private until shared.

What the Action cannot prove before it runs: that claude-code-action's headless session carries the Artifact tool at all. The tool is part of Claude Code's cloud and desktop surfaces; whether a `claude -p` run in Actions under a subscription token has it is answered by the first run. The prompt tells the session to print ARTIFACT_TOOL_MISSING if it does not, the helper fails the run on that line, and nothing is recorded, so a missing tool costs one failed run and the design falls back to the owner's machine.

## Why an Action, and why a schedule beside it

The repository is the source of the book, and the artifact is a copy that must not fall behind it, so the copy is republished by the thing that knows when the source moved. A push to main that changes the book starts the run; a merge GitHub's auto-merge makes starts no workflow, because automerge.yml arms it with the workflow token, and most of this repository's pull requests merge that way, so a schedule every half hour is the fallback that catches them, as synthesis.yml and docs.yml run daily for the same reason. The schedule is kept cheap by a fingerprint: the sha256 of git's listing of the book's inputs at the commit (the chapters and figures, artifacts/ with the synthesis's records, the site's and the edition's code, the stylesheet, CODEOWNERS), kept in the record, so a scheduled run that finds the fingerprint already published stops before building. The day is capped (TEXTBOOK_PUBLISHES_PER_DAY, 12, at most 50) and the switch TEXTBOOK_ARTIFACT set to off stops it.

The record is the metrics branch's pattern (a commit built from the files alone, never replacing a branch that holds other files) with one change: each commit is a fast-forward on the branch's head, so the branch's history is the publish log and the day's publishes are counted from it, which needs no run list and no marker artifact. The session itself holds a read-only token and the Artifact and Read tools alone; the job that writes the record runs no session.

## What the artifact is, measured

Built from the site of main at adb3afe on 2026-10-24: 442 files, 103.6 MB, two publish batches under the Artifact tool's limits of 255 files and 64 MB a publish and 511 files and 256 MB a version; 41 of the files are exported artifact pages (index.html under artifacts/), the rest the book's 70 pages, the figures and the exported pages' own trees. The figure records (JSON beside an image or a page) are not among the files; "The record" links the file on GitHub at the built commit. The first publish's prompt is 26 KB of paths. The front page is the tool's page proper, which the tool wraps in its own skeleton; every other page keeps its whole document, since supporting files are served as they are, and links between pages stay relative.

The Ask Claude box on every page asks the artifact runtime's sample capability (`claude.use("sample")`, declared on the first publish beside the GitHub connector's two tools behind Run as me, tools/textbook_publish.py CAPABILITIES, which a later publish passes again only when the record's list differs, since passing none keeps what the artifact has; docs/research/experiments-panel.md, section 4): the page's main text, at most 180,000 characters of the runtime's 256 KiB, the book's grading rules and the question, streamed back, on the viewer's own Claude account and with their consent on the first call. Where the runtime is absent the box says so and offers the front page's box, which reads any chapter named in its link, or hands the question to Claude in the repository as a prefilled issue beginning @claude, as #220's research loop does.

## What is not settled

- Whether the Artifact tool is in the Action's session (above); the first run answers it.
- Whether the frame origin resolves the supporting pages' relative links and fetches exactly as the tool's contract says; the first edition shows it.
- A run cancelled during a first publish, before the session has answered, can leave an artifact the record never learns of; the owner deletes it from the gallery, and the next run makes the one the record keeps.
- The tool's read of the existing artifact, required before a publish to it, returns the front page's HTML into the session; that is the one text of the book a run's session sees, and it is the book's own front page on the owner's own account.
- Sharing is the owner's: the artifact is private to the account that publishes it until that account shares it from the artifact's Share menu, and nothing of the book is public before the provisional is filed (#196's allowlist governs a public edition).
