---
name: lens-review
description: Use when the owner wants several reviewers with different expertise or lenses to revise one Word document, each as its own author in Word's tracked changes and comments, and to watch their changes arrive.
---

# Several lenses on one Word document

Word lets no outside program type into an open document, so the reviewers do not co-edit live. Each lens is a reviewer with one expertise or point of view, and writes its revisions as tracked changes and comments under its own author name (tools/docx_review.py panel), so the owner sees in Word whose every change is and accepts or rejects each. The lenses are applied one at a time and the file is written back after each, so the owner watches them arrive lens by lens. docs/research/lens-review.md says why it is shaped this way.

Every lens is a Claude run and spends the owner's usage: start only on their word, with the lenses and the document they named.

1. Get the .docx itself. A file the drive sync keeps in the repository (docs/research/drive-sync.md) is already here; a file the owner attaches is too. The Microsoft 365 connector reads a document as text, never as the file, so a document only on OneDrive comes in through the sync or an attachment.
2. Pick the lenses: the ones the owner named, else four, an editor (clarity and flow), a methods reviewer (is every claim supported), a domain expert of the document's field, and plain language (a reader outside the field). A Claude Code agent file under .claude/agents/ is a lens too, named by its name; the control panel's Agents tab imports more (docs/agents/AGENTS.md). An author name is one line of up to 60 plain characters, such as "Methods reviewer (Claude)".
3. Write the review sheet: `python3 tools/docx_review.py sheet FILE.docx`. Every lens reads the same sheet, FILE.review.md, never another lens's output, so each lens is its own view.
4. Run one subagent per lens, in parallel (the Agent tool, with the agent file as its type where there is one), each given the sheet and its lens, and asked for a JSON list of revisions in docx_review's shape (`{"paragraph": N, "old": "...", "text": "...", "why": "..."}`), at most one entry a paragraph, written to `$S/<lens>.json` in the session's scratchpad. A subagent changes no file but its own JSON.
5. Apply them one lens at a time, in the order the owner gave, each on the output of the last:
   `python3 tools/docx_review.py panel FILE.docx --lens "Editor (Claude)=$S/editor.json" --out $S/review.docx`
   and then again with the next lens on `$S/review.docx`. A revision on a paragraph an earlier lens has changed becomes that lens's comment, "Suggests: ...", so no lens's view is lost and none overwrites another's. The report says per lens how many it revised, suggested and skipped.
6. Write it back after each lens, so the owner sees it come in. Never over the owner's own file: the first time, upload the copy beside it as `<name> (review).docx` with the connector's sharepoint_upload_file (conflictBehavior fail; the file at most 1 MB, sent as one base64 string), and after each later lens replace that copy with sharepoint_update_file. OneDrive keeps every version, so the owner can step through the lenses in Version history. A document in the repository is instead committed after each lens on the thread's branch, where the drive sync takes it back to the drive.
7. Tell the owner where the copy is and how many changes and comments each lens made, by author. In Word they choose Review, Track Changes, Show Markup, Specific People, to see one lens at a time.
