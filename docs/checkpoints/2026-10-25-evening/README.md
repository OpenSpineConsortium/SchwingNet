# The evening checkpoint of 2026-10-25: what only the old project held, for a new one

Source: the thread "Plan the FleXray audit for #391" in the claude.ai project symphony_3 (chan_017oGDcW5qgxYtogE2Rbh26i), written at 23:00 UTC on 2026-10-25 after the owner's words of 22:57 UTC: "no i need it to be able to continue from a new project". The project-wide restart page is symphony-template's docs/research/handoff-2026-10-25-checkpoint-2.md; this folder is its confidential companion and stays in SchwingNet.

A claude.ai project's shared files, its memory and its threads belong to that project, and a new project sees none of them. Everything below was only there, so it is copied here, as it stood at the checkpoint.

## 1. The owner's request of 22:57 UTC, for the next session

The owner wrote, with a paste from another session (a Claude Code session on the owner's own Windows computer, in a folder named CTSpinoPelvic1K-1): "i want it to do this but just put it in the handoff dont bother even looking at it now, just trust the next session will figure it out". This thread did not read or open anything the paste names. The paste follows, word for word except that a multiplication sign is written x, a dash -- and an HTML-escaped quote as the quote itself, since files under docs/ are ASCII:

~~~
 10 Its spinopelvic measures match published CT
 11 The segmenter fails by phenotype, one level at a time
 12 The released model: spine and pelvis in one pass
 13 What the merge repairs: the junction and the sacrum
 14 What it does not repair
 15 Shape alone names the border, without a count
 16 Limitations and next steps
 17 Conclusions
 18 Acknowledgments and data availability
Shell cwd was reset to C:\Users\grego\OneDrive\Desktop\CTSpinoPelvic1K-1

6:40 PM
Done. Here's where everything landed.
1. Standalone repo: https://github.com/OpenSpineConsortium/bordercall -- private, because it's level-ID code. 18 files, 364 KB. A fresh clone runs `python run.py selftest` with no arguments and passes, since the 802-record fixture ships with it. The prompt for your other project is in my previous message.
2. The deck: `Desktop/CNS2026_Schwing_NotAllSpines_public_v13.pptx` -- new slide 15, "Shape alone names the border, without a count", sitting between "What it does not repair" and "Limitations". That's where it belongs: slide 14 ends with "telling four lumbar bodies from five needs a component that sees the whole column", and this is the answer -- shape names the border without counting at all.
The figure is the four phenotypes as 2x2 3D renders from the released labels, each captioned with its result: typical 97%, rib on a lumbar body 36%, no rib on the last thoracic 50%, six lumbar 89%. I built it at the slot's exact 5.14 x 3.65 aspect rather than squashing the 4.8:1 gallery, and used renders rather than a sideways bar chart per your style rule.
~~~

What the next session needs to know before it starts on this, from the paste alone:

- "This" is the work the paste describes: the private repository OpenSpineConsortium/bordercall, made that evening on the owner's computer, and the CNS 2026 deck's new slide 15. The local session wrote a prompt "for your other project" in the message before this one, which the owner did not paste. So the next session attaches bordercall (add_repo), reads it whole, and works out the task from it, the deck's outline above and #391; if the task still cannot be told, it asks the owner once for that earlier message, saying exactly that.
- The deck lives only on the owner's computer (Desktop/CNS2026_Schwing_NotAllSpines_public_v13.pptx). No session can open it unless the owner uploads it.
- The numbers in the paste are the local session's, not checked by any session of this project.
- bordercall is private because it is level-identification code, and SchwingNet's rule holds for it as for this repository: nothing of it goes to a public place before the filing.

## 2. The project's shared files at the checkpoint

- project-files/drr-domain-gap.md: the DRR comparison thread's fuller handoff. It adds to the branch copy (docs/checkpoints/2026-10-25-drr-domain-gap/HANDOFF.md on claude/project-thread-7ltron) the first commit on restart: #401's red check and the gate's one unmet precondition.
- project-files/issue-163-exact-sizes.md: the #163 thread's handoff with its step 0, merge main in first, which the branch copy on claude/163 lacks.
- project-files/outlook-dataset-mail.md: the mail thread's handoff, done, with how to read the mail again.
- project-files/section-10-owner-steps.md: the section 10 thread's handoff, done; the same page is symphony-template #492.
- figures/owner-reference-2026-10-25-2055.png: the picture the owner uploaded at 20:55 UTC with "also make a picture like this", the layout of the stitched fluoroscopy figures of the scoliosis literature.
- figures/stitched-fields-aasce-v1.png, with figures/stitched_fields_figure.py and its check figures/check_stitched_fields_figure.py: this thread's first answer to it, at 21:05 UTC, fields cut from four AASCE films. The owner then asked at 21:11 UTC for a real anomalous example showing the count reach 100 percent by error correction when every vertebra is detected; that figure is the anomaly route's figure stage (docs/research/spineps-anomaly-route.md, section 6). The script was written for tools/ and never committed there; it is kept here as it stood, to move into tools/ by pull request if the figure stage builds on it.
- Not copied: textbook/, the staged book for the textbook reader (86 MB, built from main 8d8ca23). A new project stages its own with `python3 tools/textbook_reader.py stage --clone <a clone>` and changes the reader's project id by pull request, as SchwingNet #399 did for this project; the owner then republishes from the owner's computer (symphony-template handoff-2026-10-25.md, section 3).

## 3. The project's memory at the checkpoint

project-memory/ is every file of the project's own memory as it stood at 23:00 UTC, its index MEMORY.md among them, with its few non-ASCII characters written in ASCII. A new project's first thread reads it and writes into its own memory what still holds; the files say when each fact was read. They hold no secret, and they carry SchwingNet's details, which is why they are here and not in symphony-template.

## 4. The corpus search the owner asked for at 22:31 UTC

corpus-search-workflow.js is the Workflow script of the search for more full-spine corpora with ground-truth anomalies, stopped at the checkpoint before any agent returned. A new session may run it again with the Workflow tool (scriptPath) or write its own; it answered nothing yet.
