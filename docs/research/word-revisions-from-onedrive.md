# Word revisions from OneDrive through Symphony's tasks

Source: the thread "Word revisions from OneDrive" in the project symphony2,
2026-10-18, answering the owner's ask that Symphony generalize to a folder of
Word documents: read the papers' comments, revise through the task workflow
and Claude-powered Actions, and, if a OneDrive account can be reached, bring
the files onto the repository and sync the edits back.

## What was built and shown

tools/docx_review.py (standard library only) reads a .docx file's paragraphs
and comments, with the words each comment marks, whether Word marks it done
and which comment it replies to; writes a review sheet beside the document;
makes one task per document in the Task form's shape, or opens it with gh;
and writes a worker's revisions back as tracked changes, word level, joined
across spaces so a rewritten phrase reads as one deletion and one insertion,
each run keeping its formatting, with a comment of Claude's for each "why".
docs/setup/word-revisions.md is the procedure; tests/test_docx_review.py
holds it.

Shown on a sample paper with three comments (the tool's `sample`): the
accepted text is the revised text, the rejected text is the original, bold
survives, and Claude's three answers are comments. LibreOffice 7 opened the
result (seven changed regions, six annotations in its own conversion) and
the same loop ran on a .docx that LibreOffice itself wrote, with its full set
of namespaces. An adversarial review then found five faults on shapes real Word files
have, each fixed with a test: a picture's prefixes left undeclared after a
rewrite (a corrupt file), tab stops read as tab characters, an empty
comments part rewritten as broken XML, a "why" dropped silently where no
comments part exists, and a line break written raw; and three that only
misread the sheet: a comment range begun outside a paragraph, moved text
shown twice, a text box listed twice. Every rewritten part is now parsed
again before the file is written. Not yet shown: a file written by Microsoft Word itself, and
the result opened in Word; a real paper's citation fields will be refused by
paragraph, by design, until a field-safe rewrite is worth building.

## How the files reach the repository from OneDrive, and back

Three routes, judged on 2026-10-18:

- The owner's computer, recommended. OneDrive's own client keeps the folder
  on the owner's disk; a thread whose folder tools reach that folder (the
  Claude desktop app's folder access) copies the .docx files into the
  repository by pull request, and once the revisions merge copies the revised
  files back, where OneDrive uploads them. No credential is made or held, and
  the copy back is refused when the file changed since it came in (the folder
  tools' modification-time guard), so an edit the author made meanwhile is
  never overwritten: the revised copy is then saved beside it under a name of
  its own. It needs the computer on and connected while a thread copies.
- The Microsoft 365 connector. It is not connected in this project
  (2026-10-18); its listed tools are search and read, so by its tool list,
  inferred and not tried, it can bring a file's content in but not write a
  file back. It suits a one-way read.
- Microsoft Graph from GitHub Actions. A workflow could pull and push the
  folder on a schedule with an app registered in Microsoft Entra and a
  refresh token or client secret held as an Actions secret. That is a stored
  credential with access to the owner's OneDrive, which the project's rule
  against stored credentials covers in spirit, and a university tenant
  usually needs its administrator's consent for such an app. Not built; the
  owner's decision.

## Open

- The owner names the OneDrive folder; until then no file of the owner's is
  touched.
- A real revision by a worker in Actions spends the Claude token's usage and
  waits for the owner's word.
- Whether the papers live in this repository or in one of their own: a
  paper's repository made from the template carries the tool and the
  procedure, and keeps the papers out of the template's history.
