# Handoff: the textbook on claude.ai, read through the project's files (2026-10-25)

Written 2026-10-25 about 09:55 UTC from the project thread that built and staged the reader (#294, #295), at the owner's checkpoint of 09:46 UTC, with the weekly limit at 92 percent: "push any outstanding prs (either draft or done), and update a handoff which will permit a different account to continue this work (including instructions, goal, first prompt)". The research is docs/research/textbook-as-an-artifact.md and the standing fact docs/memory/the-textbook-artifact.md; this page only points to them.

## Goal

The Artifact Textbook readable on claude.ai, privately, with the book's own files kept out of the artifact. On 2026-10-25 at 04:28 UTC the owner chose the reader over this project's files (#294). It is one small page, tools/textbook_reader.html, which Claude reads whole and the owner publishes. It declares the files capability for the Claude project chan_0173jSoVxEEsU7awM7a8mhVW and the sample capability. When it is opened, it reads the built book from textbook/ in that project's files.

The work is finished when the owner has opened the link and the book shows, with its search and Ask boxes answering, and each later change to the book reaches the link by a stage.

## Done

- #295 merged at 05:59 UTC as 2774384. It brought the reader page, the stage (`tools/textbook_reader.py stage`), the publish command (`tools/textbook_publish.py local`), their tests, the research note and the memory.
- The book was staged at 05:59 UTC from main 2774384: 455 files, packed into 86.0 MB, in the project's files at textbook/ (CURRENT.json, book-2774384ca060.json, book-2774384ca060.bin and README.txt). Every file was read back against its sha256. The book's inputs are unchanged at main dac6206, so a stage now does nothing.
- The owner published the page at about 09:30 UTC at https://claude.ai/artifact/Roz1iKJfgPVSTsSNd2iw9m and set it to "anyone with the link can view".
  - A viewer outside the project still reads nothing, since the book comes through the project's files.
  - The first try, at 09:25, was refused with deploy 422 on capabilities.files. The owner's Claude Code was signed in to an account that is not a member of the project; `/status` shows the account and `/login` switches it.
- The record is state.json on the branch textbook-artifact, commit 8441abe, schema textbook-reader-page/1. This thread wrote it at 09:33 UTC, since the owner's command had not recorded it yet.
- The pull request that carries this page also records the publish in the research note (its section "The reader published, 2026-10-25") and in the memory.

## Open, in order

1. **The owner's first opening.** The reader was tested only in Chromium against tests/reader_stand_in.py, a stand-in written from the runtime contract's type definitions (0.2.90), never on claude.ai. Ask the owner what the link shows.
   - If the book does not show, or search or Ask fails, fix the reader in a pull request of its own (one issue, branch claude/<N>).
   - Then the owner runs `python -X utf8 tools/textbook_publish.py local` again in the owner's clone, signed in to this project's account. With the record in place, it republishes the changed page to the same link. With the page and capabilities unchanged, it says so and publishes nothing; `--anyway` forces a publish.
2. **Stage after every merge that changes the book.** Run `python3 tools/textbook_reader.py stage --clone <a clone of main>` from a thread of this project, since only such a thread can write this project's files. No workflow stages the book.
   - The stage builds main's edition with main's own builders, keeps the previous edition for a reader still open on it, and writes CURRENT.json last.
   - The page itself is published again only when tools/textbook_reader.html or its capabilities change.
3. **The first scheduled synthesis run since #275.**
   - #275 merged 2026-10-25 02:26 UTC and put allowed_bots: "github-actions" on the sessions in .github/workflows/synthesis.yml.
   - The schedule is cron 41 6, which GitHub has been starting about five hours late. The last scheduled run was 2026-10-24 11:32 UTC, and none had run today at 09:50 UTC.
   - When today's run comes, check two things where it plans reads: that its claude-code-action steps start and finish, and that it is not refused for a run no person started. Read the logs with the GitHub tools' get_job_logs and return_content, since the proxy refuses gh's log download.
4. **#271, noticed and not claimed.** The memory index is 29,044 bytes, over its 25 KB limit, and nothing checks it. The issue is open and labelled todo. Read the board's Overlaps before claiming it.

## Moving the reader to another account's project

The reader is tied to this Claude project. Its capabilities name chan_0173jSoVxEEsU7awM7a8mhVW (PROJECT in tools/textbook_publish.py, the only place the id is set). Only a member of that project can publish the page, and only a thread of that project can stage into its files. If the next account is a member of this project, nothing changes.

If the work moves to a project of another account:

1. A pull request sets PROJECT to the new project's id.
2. A thread of the new project stages the book there.
3. The record is cleared, so the next publish makes a new artifact. The command's record() refuses to record a link other than the recorded one, and a record of another schema reads as empty. This thread wrote the current record with write_record from that module, and the same call clears it.
4. The owner publishes from Claude Code signed in to the new account, and the command records the new link.

## Rules that hold

- No grid job, fetch or training without the owner's word and the count; the research loop's standing exception (.github/symphony/research.md) is the only one.
- The book, its figures and the research stay in this private repository and this project. Nothing of them is quoted, posted or published elsewhere, and the docs site's link is never posted outside the project.
- A cloud session or a GitHub Action never publishes the book or the reader as an artifact; the owner publishes from the owner's computer. A refused publish is never retried from a session or routed through another one.
- Never publish a file Claude has not read whole, and never suggest a way around that rule.
- The reader stays at files and sample. Declaring the GitHub connector (mcp) in its capabilities was refused as a remote-code surface; do not retry it or work around it. A figure's prefilled issue still works.
- Process for each change:
  - one issue, one branch claude/<N>, one pull request;
  - `bash scripts/check.sh` in a scratch copy first (docs/memory/run-the-checks-in-a-throwaway-copy.md);
  - an "## Adversarial review" section in the body;
  - mark it ready in a call of its own;
  - merge once green on the owner's standing permission.
- Never push to or force-push main.
- Every manual step for the owner is numbered, with the exact link and what to click.

## First prompt for the next account

"Continue the textbook reader handoff in SchwingNet docs/checkpoints/2026-10-25-textbook-reader/HANDOFF.md: ask me whether the book opened at the reader's link and fix the reader by pull request if it did not, stage the book again after any merge that changed it, and check the first scheduled synthesis run since #275. No grid job, fetch or training without my word and the count."
