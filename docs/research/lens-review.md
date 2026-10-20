# Several lenses on one Word document

Source: the thread "Organize a whole OneDrive" in the project symphony, 2026-10-18, answering
the owner's message that day: "provide the ability to multiple claude sessions editing the same
onedrive word file or other office document in real time and be able to see it yourself, even
agents that have different purposes/expertises/lenses". The tool is tools/docx_review.py's
panel command; the procedure is .claude/skills/lens-review.

## What can and cannot be live

Word co-authors live only among people in Word, Word for the web or the Office apps, which
merge each other's edits through OneDrive's own protocol. A program outside them can only
replace the whole file: Microsoft Graph and the Microsoft 365 connector (sharepoint_update_file)
write a new version, and Word, holding the document open, offers to reload it. No public
interface lets a program type into an open document, and the connector reads a document as
text (it converts Word and PowerPoint through PDF), so it never hands a session the .docx
itself. So "in real time" is lens by lens, not keystroke by keystroke: each lens's whole review
lands as one new version of a copy, and the owner sees it arrive and steps through the versions
in OneDrive's Version history.

## How it works

- A lens is a reviewer with one expertise or point of view: an editor, a methods reviewer, a
  domain expert, a plain-language reader, or any Claude Code agent file under .claude/agents/.
  Each runs as its own subagent on the same review sheet (docx_review.py sheet), so no lens
  sees another's output and each stays its own view.
- `docx_review.py panel FILE --lens "Name=revisions.json" ...` applies the lenses in order, each
  as tracked changes and comments under its own author name, so Word's Show Markup, Specific
  People shows one lens at a time and the owner accepts or rejects each change.
- A lens that revises a paragraph an earlier lens has already changed, or one that no longer
  reads as the sheet said, or one holding a field or a picture, becomes that lens's comment on
  the paragraph, "Suggests: <its text> Why: <its reason>". apply refuses to rewrite a paragraph
  that already holds a tracked change, since it could lose it, so the clash is kept and nobody's
  view overwrites another's. A bad entry is skipped and said in the report; the rest go on.
- The copy is written back after each lens, never over the owner's file: uploaded beside it as
  "<name> (review).docx" the first time, replaced after each later lens. The connector takes a
  file of at most 1 MB in one base64 string, which the session writes out whole, so a large
  document goes back through the drive sync instead (docs/research/drive-sync.md), committed
  after each lens.

## Not yet known

- Nothing has run on a real document of the owner's; the tests use the sample paper.
- What a 1 MB upload costs a session in output: the base64 is about 1.37 bytes a byte, all of
  it written by the model. A typical paper of 50 to 200 KB is affordable; a document with
  pictures may not be.
- Excel and PowerPoint have no tracked changes Word's way. A lens on a workbook would write
  its findings beside it, as the organizer's tasks do; that is not built.
