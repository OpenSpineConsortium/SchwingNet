# Handoff: the 42 papers, what they assume, and the owner's seven decisions (2026-10-28)

Thread "Get full texts through Elsevier key", 2026-10-27 23:00 UTC to 2026-10-28 evening. The owner asked at 20:40 UTC to wrap up every thread for now and to put his decisions into the final handoff; at 20:41 UTC: "no please continue checking but after finishing that stop". This page is that handoff. The research it points to is docs/research/morphometry-beyond-the-42-papers.md and docs/research/literature-on-the-grid.md; this page carries none of it. Confidential like the rest of SchwingNet: nothing here goes to a public place.

## 1. The owner's seven decisions, verbatim

The owner, 2026-10-28 20:40:26 UTC, in this thread: "ok fyi i agree to all these directions but i want to wrap up all threads for now so simple put it in the final handoff my decisions". The seven directions he agreed to are the list "What needs your word" at the end of the Claude Doc "What the 42 papers assume, and the data beyond them" (https://claude.ai/artifact/XREXDs6498pSUMn5o4dE1b), which he pasted back with that message:

1. "Send the bordercall pilot. It is approved for two CPU jobs but unsent, under your rule that nothing goes to the grid for now. It answers the first question on this page: how many census CTs count from C2. The status word would go first."
2. "Decide whether non-SPINEPS masks may feed the table. ENHANCE.PET's 1,557 columns are MOOSE masks, and TotalSegmentator's 142 are its own. I would use them only as a second arm, never pooled with the SPINEPS one."
3. "Fetch the NHANES 2013-14 DXA files. These are 13 small public files, one per body from T4 to L4. They are the only public, population-weighted, per-person heights found, and the fetch needs your word and count. The size is read before any byte lands."
4. "Read the whole tables already in hand. Tan 2004 and Busscher 2010 both cover C3 to L5, and Lien 2007 and Kunkel 2011 (uploaded today) have thoracic rows. Only their lower rows were ever copied."
5. "Decide on a systematic search. The 42 were never searched for. A designed PubMed and Scopus search, screened against them, would turn the list into a review."
6. "Decide which C-ArmLSpine and COBRA people may be spent to fit how CT measures differ from fluoroscopy, since both are test sets now."
7. "Later: applications. The New Mexico decedent CTs, NAKO and UK Biobank each need an agreement you would sign. NMDID is free and has whole columns with height and weight, so it is the one I would apply to first."

Nothing of the seven was started in this thread: he asked for them to wait. Decision: the owner agreed on 2026-10-28 at 20:40 UTC to all seven directions, to be carried out from the next session on.

Hold, beside item 1 and any use of the grid or of WSU data for the Bayesian work (added at the coordinator's request of 20:58 UTC): "hold until greg's own patent attorney has advised on ownership (see greg's private doc)".

## 2. What the source check found that bears on each

The seven were written before the check of the evening of 2026-10-28 (eight readers, one verifier per finding; the corrections are in the note and the doc). Where the check changes what a direction means, the next session reads this before acting.

1. The pilot. Held as section 1 says until the owner's own patent attorney has advised. The approval of 2026-10-25 23:56 UTC is two CPU jobs: the pilot, then the full corpus only if the pilot finds countable columns and its report ends well (bordercall-corpus.md). The order is: send `update` once, then the status word once, then the pilot; its report is read from the next status word (docs/memory/bordercall-on-the-grid.md). Two limits: the pilot reads at most 4,000 rows, tier 1 first, and stops at 300 countable columns, so its share counting from C2 is tier 1's, not the census's; and it runs bordercall at 6938a2e, which predates the exact rule and spineps_map.py, so it cannot score the rule and its measures must be checked against the seven before they count. Whether the owner's "i agree" is his word to send now or after the wrap-up is not settled: ask once before the first send.
2. Non-SPINEPS masks. ENHANCE.PET's masks are MOOSE's corrected by readers (Ferrara 2026), not raw machine output; they are not on the grid, and fetching them is its own word. The committed facts (data/gold3-ct/enhance-pet/facts.jsonl) are mask geometry, not Panjabi's measures. bordercall's rules use the existing SPINEPS masks and never TotalSegmentator (bordercall TODO.md, Rules that hold for every item), so using either as a second arm changes a rule of bordercall's, which the owner's agreement now covers.
3. The NHANES 2013-14 DXA files. The count stated is 13 public files; the fetch reads each size first and is refused whole if it would pass the quota. No record in SchwingNet, bordercall or spine-program names DXXL4_H before this note.
4. The whole tables. Busscher 2010 is open in PMC (PMC2900026); its Table 3 prints anterior, central and posterior body height and disc height from C3 to L5, and only T12 to L5 was copied, without the central height. Tan 2004 was read only as an abstract; none of its 60 copied values has been checked against its page. Both PDFs, with Lien 2007 and Kunkel 2011, are in the Claude project files under literature/synthetic_spine/ (MANIFEST.md there gives each sha256).
5. The search. No query, date or inclusion rule was ever written down (spine-program synthetic_spine README.md and HANDOFF.md).
6. C-ArmLSpine and COBRA. Their CTs are test only in the census lists and the anomaly route, but their frames are not all test: only five C-ArmLSpine people are frozen test persons (data/splits/test-persons.json), and COBRA's 118 Elekta cases trained the reported sacrum detector. Which people to spend is still to be picked; the agreement is to the direction, not to a list.
7. Applications. NMDID's agreement bars derivative works beyond its permitted uses, and the lab's data platform ruled it out because it reads derived labels as one (data/reproduce/sources.json, excluded_nmdid); it has no masks, so a table from it needs a segmenter run, which bordercall's rules forbid; and its CT data is over 50 TB, more than the lab volume's quota. So NMDID first needs the owner to decide those three points. UK Biobank publishes every approved project's lay summary, and nothing may be public before the provisional is filed. Every application's text falls under the rule for dataset letters.

The check added an eighth item the owner has not seen: the rule's age range. TotalSegmentator v3 has 291 paediatric CTs and the census marks 556 CTs as children's; until he sets the range, children's CTs stay out of any table or form an arm of their own.

## 3. Where things are

| what | where |
| --- | --- |
| The research note | SchwingNet docs/research/morphometry-beyond-the-42-papers.md, pull request #446 from claude/project-thread-bh3ojq |
| The same as a Claude Doc | https://claude.ai/artifact/XREXDs6498pSUMn5o4dE1b |
| The literature route and its report | SchwingNet docs/research/literature-on-the-grid.md (merged in #438 and #440) |
| The 42 papers | Claude project files, literature/synthetic_spine/, with MANIFEST.md (sha256 and origin of each); 22 the grid fetch did not get came from the owner's uploads and a thread on the open network, the other 20 from the grid fetch of 2026-10-28 (17 got, 3 held already); Eisenstein 1977 arrived last, at 18:54 UTC, so all 42 are held |
| The verifier's findings | this thread's container only; their result is the text of the note |

Whether the grid copy of the project files (/rs/rs_grp_oschome/go2432/data/project_files_2026_10_28/, made by the other account) includes the uploads of 17:00 and 18:54 UTC was not checked.

## 4. What still waits on the owner from this thread

1. Elsevier answered 403 to the key and institutional token for both its papers (literature-on-the-grid.md). The question for Elsevier (case 260924-003406) is which API key the institutional token is bound to, and whether that key is enabled for ScienceDirect full text under the text-mining amendment; the owner was to ask James and Mike.
2. spine-program pull request #239 (the closed-papers check of synthetic_spine) is ready with its check green; it merges only on the owner's word, with its five decisions his.
3. The seven directions above, and the age range.
