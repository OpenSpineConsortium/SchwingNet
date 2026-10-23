# Artifact Textbook: where to resume

Written 2026-10-22 23:45 UTC by the thread "Artifact Textbook" when the owner's account reached its usage limit, so another account's session carries the work on. Issue #136, branch claude/136, draft pull request #137. Phase 1 (inventory, clusters, contradictions found, proposed table of contents) is merged by #121; its 9 questions for the owner are on #121 and still unanswered.

## What this folder holds

- tools/: the scripts that made artifacts/_synthesis/. extract.py writes the plain text of every artifact; verify_quotes.py checks a quote against that text and the page's own files; merge_contradictions.py joins the sweeps; render_contradictions2.py writes contradictions.md with one page per cluster under contradictions/; merge_skeptics.py keeps a workflow's skeptic verdicts from its journal and merges them into the record, and check_verdict_quotes.py checks that each verdict quotes its own candidate's artifacts; render_inventory.py, render_clusters.py, render_toc.py and textbook_toc.py made the other files.
- out/clustering.json: the 14 clusters. out/toc-hand.json: the proposed table of contents.
- out/sweep-A-raw.json and out/sweep-B-raw.json: the finders' candidates for clusters 2 to 13 (372 and 269 candidates, Outreach included), with whatever verdicts came back.
- out/contradictions-all.json: the merge of every sweep so far; out/clusters-verify-0-1-6.json and out/numbers-partial.json: clusters 0, 1 and 6 and the 247 number collisions, 15 of them with a verdict; out/numbers-verify-batches.json: the 87 number candidates in 17 batches still to be read.
- out/journal-results.json: every agent result the last three runs returned before they were stopped, and the list of those that did not finish. out/journal-results-2.json and out/journal-results-3.json: the skeptic verdicts of 2026-10-23, nine groups and then the tenth.

## Where it stands on 2026-10-23

Another account's session merged the Outreach sweep and the two verifier results the journal held (tools/merge_resume.py, into out/contradictions-merged.json), re-extracted the texts with extract.py and rendered contradictions.md and contradictions/ with render_contradictions2.py. All 14 clusters are swept: 858 candidates. On the owner's word of 2026-10-23 the same thread ran the skeptic reads of the other 12 clusters (761 candidates) and of the 87 number candidates in out/numbers-verify-batches.json, one skeptic per group of clusters: out/journal-results-2.json keeps the nine groups that came back before the container restarted and out/journal-results-3.json the one relaunched after it (Datasets, holdings and licences), each extracted from its workflow's journal by tools/merge_skeptics.py extract. tools/merge_skeptics.py merge put every verdict at its candidate's index in out/contradictions-merged.json, asserting that none was filled twice, and the number verdicts into its numbers_extra. Every one of the 858 cluster candidates now has a verdict, and so do 102 of the 247 number collisions: the 91 a reader classed as a contradiction or a later revision, and 11 more the first run took. tools/check_verdict_quotes.py checks that each verdict quotes its own candidate's artifacts, which a verdict merged at the wrong index would not. render_contradictions2.py keys a number verdict by its two artifacts and its whole quantity, since the first 30 characters gave two pairs of candidates one key. The paths the scripts read are set by SYNTH_TEXT, SYNTH_SCHWINGNET and SYNTH_SYMPHONY.

## What is left

1. Nothing of #136's verification. The 145 number collisions that readers classed as another scope or another quantity have no skeptic's verdict by design; a planner reads their quotes, which the script found in the sources.
2. To render again: `SYNTH_TEXT=<text dir> SYNTH_SCHWINGNET=<clone> SYNTH_SYMPHONY=<clone> python3 -I tools/render_contradictions2.py out/contradictions-merged.json out/numbers-partial.json out/clustering.json ../inventory.json ../contradictions.md <date>`, after `python3 -I tools/extract.py <clone> SchwingNet <text dir>` and the same for symphony-template, then update the counts in artifacts/_synthesis/README.md and docs/research/artifact-textbook/README.md.

## After #136

Phases 2 to 4 (sourced research per cluster with every claim graded, the chapters under docs/textbook/, the experiment stubs) start only on the owner's go and his answers to the 9 questions on #121, each under an issue of its own. No grid job, training run or paid usage is part of this work.
