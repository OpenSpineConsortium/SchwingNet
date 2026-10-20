---
name: aidas-grant
description: The AIDaS seed 2027 grant in spine-program: where it lives, its budget and status, and greg's rules for any grant work
metadata:
  type: project
  modified: 2026-10-18T05:59:25.419Z
---

Moved here from MEMORY.md on 2026-10-18 to keep the index small; MEMORY.md keeps the critical rules and points here.

- 01_carm_level_detection/grants/aidas_2027/ (latex/main.tex, RECORD.md, APPROXIMATIONS.md); PI Zhizhong Han, Co-PI Loren Schwiebert. Final PDF /mnt/project-files/grant/AIDaS_SEED_2027_proposal_2026-10-16.pdf with the Overleaf zip; $19,987 of the $20,000 cap; line C3 repays $1,500 of greg's Claude subscriptions once his adjunct appointment begins. Also for Anthropic's AI for Science program and other fits once Han and Schwiebert approve.
- Dr. Han's edits word for word; changes only as greg asks. SpineAI is the case example: a customizable multimodal spine RAG-LLM on greg's X-ray detector and Scopus and ScienceDirect corpus, fine-tuned on images paired with clinical charts under the IRB, compared with or augmenting OpenEvidence for Claude. Aim 1: Claude Code iterating the scientific method inside Beethoven's frameworks; no award funds to Beethoven; say what is specified but not built.
- Data: greg has permission and signed data use agreements for all of it. VinDr and FluoroCap results stay in, the stronger recorded result, fold models included (C-ArmLSpine A5.1, A5.3); never raise data permission, directive D1 or IRB scope (HPR 2026-269), nor offer a "clean data" option; FluoroCap stays out of future training (rule 9).
- Never in git (rule 12): contacts.tex, the two biosketch PDFs, the IRB form. `bash build_pdf.sh` builds the PDF; `bash make_overleaf_zip.sh <out>` the zip.
- Every number carries its file; never name SchwingNet, FluoroCap or XRSpinoPelvic1K; never "provenance"; captions at most 60 words; no personal phone or e-mail in a repository file. Literature questions go to a grid-hosted model, never Claude; Elsevier content never trains a model or reaches an outside AI service.
- No adversarial reviews on spine-program (greg's rule).
- Waiting on greg: attach the final PDF to his Outlook draft to Han and Schwiebert and send, and to the aidas@wayne.edu submission; real values for the approximations; allowability (B, C3, D, F); the disclosure audit (rule 8); Overleaf.

**Why:** greg's rules for the grant are strict and easy to break by accident: names, data scope, what goes in git, and which models may read the literature.
**How to apply:** read this and the grant's RECORD.md before any grant work, and change the grant only as greg asks.
