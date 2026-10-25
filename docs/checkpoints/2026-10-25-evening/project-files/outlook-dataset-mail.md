# Handoff: Record dataset-access replies from Outlook (checkpoint 2026-10-25 22:40 UTC)

Thread: "Record dataset-access replies from Outlook" (item 4 of the owner's message of 2026-10-25). Safe to copy into symphony-template's combined handoff as written: it names no dataset detail, only where the SchwingNet record is.

## State

- Done and merged. SchwingNet PR #396 merged into main (merge commit ecb9640, checked on main). Nothing of this thread is unpushed, and no draft pull request is open. The branch claude/project-thread-dmpfo3 on SchwingNet holds only merged work and may be deleted by the owner.
- The 15:35 UTC read in symphony-template's docs/research/handoff-2026-10-25.md is out of date. The second full read on 2026-10-25, Junk Email included, found a bounce the first one missed. That handoff's line saying no reply is owed by a session should now point to SchwingNet #396.
- What the mail says now is recorded only in SchwingNet: docs/research/data-access-requirements.md, section "Where each request stands (2026-10-25)", and the records under data/sources/. Those notes are confidential and stay in SchwingNet.
- A new SchwingNet memory, docs/memory/dataset-mail-is-read-with-junk-email.md, says every future read of the tagged mail also searches Junk Email for returns.
- Two reply drafts wait unsent in the owner's Outlook Drafts folder, one per conversation. The session sent nothing.

## Open: the owner's steps

The thread's last reply lists these with links. In short:

1. Open the unread return in Outlook's Junk Email of 2026-10-24, read why the letter was refused, confirm the address and resend the letter from Sent Items.
2. Read the two drafts in Outlook Drafts and send any you approve.
3. Ask Wayne State's research office for the data use agreement the thread's reply names.
4. Submit the image requests at the NIA Aging Research Biobank, https://agingresearchbiobank.nia.nih.gov.

## How to restart

1. Open a new thread in this project.
2. Ask it to "read every conversation tagged [XR/CT Imaging Research] newer than SchwingNet's data-access-requirements.md, Junk Email included, and record the answers by pull request".
3. The thread reads SchwingNet's docs/research/data-access-requirements.md first; its opening paragraph says when the mail was last read.
4. It reads only mail newer than that. It searches Junk Email by date for returns, and it uses the Microsoft 365 connector, which must be connected.
5. It edits records with exact replacements and leaves licence fields alone. Then it runs, in SchwingNet, `tools/sources.py render`, `tools/reproduce_table.py render` and `tools/choose_data.py write` (the last refreshes data/choice/CHOICE.json's hash of the records). It runs `bash scripts/check.sh` in a throwaway copy and opens one pull request.
6. It drafts any reply and never sends one.
