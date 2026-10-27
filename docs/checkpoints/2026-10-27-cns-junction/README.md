# The CNS junction checkpoint of 2026-10-27: the SchwingCheck white paper and textbook chapter 36

Source: the thread "Finish CNS slides with junction predictor" in the claude.ai project symphony (chan_014WUU19NHgHPhf7QetT9cbS), written at about 04:55 UTC on 2026-10-27 on the owner's words of 04:47 UTC ("PLEASE CHECKPOINT ALL SESSIONS AND PUSH ALL FILES AND WRITE A HANDOFF SO A NEW ACCOUNT CAN PICK UP WHERE THESE LEFT OFF"). The thread's previous checkpoint is docs/checkpoints/2026-10-26-cns-junction/; bordercall's HANDOFF.md steps 7 to 11 carry the studies in between.

## 1. Where everything is

- The white paper is the Claude Doc "SchwingCheck and LevelCheck", https://claude.ai/artifact/4VwMe9CKMX87s4jiEJBpRE, at revision 189. The owner rewrote it from about 00:50 UTC on 27 October into three pathways (LevelCheck as prior art, SchwingCheck3D with a preoperative CT, SchwingCheck2D without one, the recommended default). The session folded the checked corrections that still applied into revision 138 as 49 narrow edits and 14 references (revision 188), and at 04:25 UTC, on the owner's word that their preliminary data show 100 percent accuracy when making panoramas with SchwingNet, rewrote the paragraph on stitching to give that result with its sets (revision 189). The owner's text wins: fold only verified corrections, as narrow edits, never over their text.
- OpenSpineConsortium/bordercall (private), main at df976d7: docs/SCHWINGCHECK_LEVELCHECK.md is the ASCII copy of revision 189, identical to the Doc's export after the conversion in HANDOFF.md step 11; records/exact-2026-10-26/ (the exact rule, 00f969f) and records/whitepaper-2026-10-26/ (second opinion, latency, anomalous columns counted from C2, power of the two-arm and three-arm reader studies, 9e041ef and 6821f53) hold every SchwingCheck number; slides/exact/ holds the five-slide decks on the exact rule (exact_slides_neurips.pptx with the method, exact_slides_cns.pptx results only, HANDOFF.md step 10); slides/junction_slides.pptx the six junction slides of the earlier checkpoint.
- Here, pull request #416 (draft, branch claude/project-thread-7qoboa): textbook chapter 36 (docs/textbook/36-schwingcheck-an-explainable-bayesian-check-on-vertebral-labels.md), carrying revision 189 verbatim behind a framing and the book's four closing sections; five figures under docs/textbook/figures/36/ drawn by tools/schwingcheck_figures.py from tools/schwingcheck_records.json; the chapter's entry in artifacts/_synthesis/work/out/toc-hand.json (Part III, after 34); two questions in docs/textbook/rag/questions.json; docs/research/schwingcheck.md and docs/memory/schwingcheck.md with their index lines. scripts/check.sh passed in a throwaway copy on 6f75616 and CI's check, gate and standards were green there; b4c966e (revision 189 in the chapter) and this folder are not yet through CI.

## 2. Pull request #416: what is left

An adversarial review by four lenses (numbers, faithfulness to the paper, figures and code, repository rules), each finding verified by a skeptic, ran on 6f75616 and was stopped at the checkpoint with one verification left. It confirmed about twenty distinct defects in the session's own text and figures, none in the owner's paper; review-findings.md in this folder lists them with their fixes. To finish, in order:

1. Fix every item of review-findings.md in the chapter's framing (lines 1 to 58), its closing sections, the five figures and tools/schwingcheck_records.json; redraw with `python3 tools/schwingcheck_figures.py docs/textbook/figures/36`; never edit the paper's section, which must stay identical to bordercall's copy with headings demoted (the check is in this folder's review-findings.md, item 0).
2. Review the revision 189 paragraph and b4c966e's framing lines the same way, since the review predates them.
3. Run `python3 tools/check_docs.py`, `python3 tools/rag.py check` and `python3 -m unittest tests.test_textbook_site tests.test_figure_run tests.test_rag_tool`, and scripts/check.sh in a throwaway copy with icontract, beartype and pydantic in a venv.
4. Write the pull request's "## Adversarial review" section from what the review found and what was fixed, mark it ready in a call of its own, and merge once check, gate, standards and owner-ok are green, on the owner's standing permission.

## 3. The grid pilot, approved and unsent

Unchanged since the previous checkpoint: the owner's count of two CPU jobs (2026-10-25 23:56 UTC), bordercall's pilot over existing SPINEPS masks counted from C2, then the full corpus only if the pilot ends well, waiting on the pass-through (hpcworker #50) and the send; docs/checkpoints/2026-10-26-cns-junction/README.md section 2 gives the order. The pilot runs the junction predictor vendored at grid/bordercall/ (bordercall 6938a2e), not the exact rule: scoring SchwingCheck itself on real masks needs exact.py brought into the vendored copy and a job the owner has not counted.

## 4. The owner's rules from this thread

- The paper hinges on the owner's sentence of 26 October 21:28 UTC: no function of the same anatomist's measurements, formula or network, names fields correctly more often than the Bayes rule for these fields and this prior; its error is the floor for any network.
- The owner's text wins in the Doc; corrections go in as narrow edits only after they are checked.
- Panoramas made with SchwingNet are 100 percent accurate in the owner's preliminary data (27 October 04:25 UTC); quote it with chapter 34's sets and as a record, not a final value.
- The owner's uploads (Manbachi 2018, De Silva 2016 and its supplement) are read, never committed or copied; Doc text is never sent to a web service.
- Results may be shown, mechanism may not, until the provisional is filed and the TTO has read the decks; both exact-rule decks carry the confidential footer.

## 5. Not known

No SchwingCheck number comes from a patient: every one is from synthetic columns drawn from Panjabi's tables, and the record says the rule worsens off its generator (a table from twelve spines, 3 mm of measurement error, transitional columns). The segmentation-free device of figure 36.5 is a design; no head finds the pedicles' medial borders or the spinolaminar point. The reader study's effect sizes are the paper's assumptions.
