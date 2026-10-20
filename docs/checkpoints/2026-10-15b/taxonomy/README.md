# Taxonomy spec and manual: checkpoint 2026-10-15b

The taxonomy thread of the Symphony project on claude.ai, started by the owner's ask of 2026-10-15 18:04 UTC:
"can you give me a SPEC and MANUAL for placing symphony/beethoven into a taxonomy of software to see where it fits, how it could work with other softwares or improve and close a real need, what is unique about it sct. i want o do deep research on it and use it to explain the power of this approach, particularly the github actions nativeness and the free unlimieted minutes for public repos,"
Follow-up of 21:58 UTC: "I need pdfs with references". At 22:29 UTC the owner asked to render the PDFs as they stood and checkpoint at once.

## Done

- The spec and the manual, written, adversarially reviewed and corrected. They are Claude Docs owned by the owner's current account:
  - Spec: https://claude.ai/code/artifact/9ed6238d-6b5e-4a7e-acb5-df360435c19c (rev 59)
  - Manual: https://claude.ai/code/artifact/c42e4d26-b238-4834-bb7b-318ae086152c (rev 30)
- PDFs of both as they stand, rendered 2026-10-15 22:30 UTC: spec.pdf (36 pages), manual.pdf (23 pages). They carry the inline links and the spec's section 12 "Sources" list, but NOT yet the numbered reference list the owner asked for.
- Markdown exports of both docs: spec.md, manual.md.
- The research behind them: research/notes/01-13 (one note per topic, every fact with its source and grade) and research/verify/01-03 (the adversarial checks). They are Markdown kept as .txt here, because the template's tests hold every .md page under docs/ to its push rules and these notes quote other projects' git commands.
- Two Symphony protocol findings from verify/02 went to the protocol-fixes thread on 2026-10-15 21:25 UTC: the push guard reads claim files from the hook's working directory, not the clone a `git -C <dir>` push names; and a reopened issue keeps the claimed and in-review labels, so no worker is dealt it.

## Open: the numbered references (the owner's 21:58 ask)

Citation proposals exist as JSON in refs-work/out/: each is a list of find-and-replace edits that add [[sN]] markers to one group of sections, plus the source records (authors, title, venue, date, commit, URL, how it was read).

| Group | Sections | State |
| --- | --- | --- |
| spec-A | spec 1-2 | drafted |
| spec-B | spec 3 | drafted |
| spec-C | spec 4 | drafted |
| spec-D | spec 5.1 | drafted |
| spec-E | spec 5.2-5.3 | drafted |
| spec-F | spec 6 | drafted and checked by a second reviewer (spec-F-check.json) |
| spec-G | spec 7 | drafted |
| spec-H | spec 8 | drafted |
| spec-I | spec 9 | drafted |
| spec-J | spec 10-11 | not started |
| man-A | manual 1-3 | drafted |
| man-B | manual 4-5 | drafted |
| man-C | manual 6 | drafted |
| man-D | manual 7 | drafted |
| man-E | manual 8-9 | not started |

"Drafted" means the file passes refs-work/check_edits.py with 0 problems (every find exists once, every marker names a defined source), but no second reviewer has yet checked that each source supports its claim.

## The exact next step

1. Run the citing workflow refs-work/cite-workflow.js for spec-J and man-E, and its check step for every group but spec-F. First change the constant R in it to where refs-work now lives. It reads refs-work/packets/<group>.txt and .json and writes refs-work/out/<group>-cite.json and -check.json.
2. Run `python3 refs-work/apply.py spec` and `python3 refs-work/apply.py manual`. Each merges the groups, numbers the sources in order of first citation, and writes <doc>_apply.json (one find-and-replace op per edited paragraph, nth set where a find repeats) and <doc>_refs.md (the numbered list).
3. Apply the ops to each doc with the Claude Docs update tool (engine prose, op replace, target kind find, as text). Send them in reverse document order. A find-and-replace as text keeps links and bold; a marker inserted right after a link lands outside it, tested on rev 58. Then replace the spec's section 12 "Sources" with "12. References" (a short lead and the numbered list), and append "10. References" to the manual.
4. Export both docs as PDFs (Claude Docs export, letter), render a few pages to check the drawings, the markers and the reference list, and deliver them.

If the next session runs on another account, it cannot edit these Claude Docs. Then rebuild both documents from spec.md and manual.md, apply the same edits to the markdown (the finds are plain text, and they match except where a link's markup sits inside a find), and render the PDFs from the markdown.

## Notes for whoever continues

- The copies under docs/checkpoints/ in symphony-template are folded to ASCII, because scripts/check.sh requires ASCII under docs/; JSON keeps its exact text through \u escapes. The unfolded originals are in this project's files under research/taxonomy/.
- These files describe Beethoven's private, proprietary repositories (research/notes/04, 05 and parts of 11 and 12). symphony-template is internal today; remove this folder before it is ever made public.
- Source records graded "search" were seen only in a search summary; a reference list must say so (apply.py prints "Not opened by the research session").
- The research session could not reach docs.github.com, github.blog or arxiv.org; GitHub's documentation was read in the github/docs repository at commit 12691d2.
