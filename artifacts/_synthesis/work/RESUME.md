# Artifact Textbook: where to resume

Written 2026-10-22 23:45 UTC by the thread "Artifact Textbook" when the owner's account reached its usage limit, so another account's session carries the work on. Issue #136, branch claude/136, draft pull request #137. Phase 1 (inventory, clusters, contradictions found, proposed table of contents) is merged by #121; its 9 questions for the owner are on #121 and still unanswered.

## What this folder holds

- tools/: the scripts that made artifacts/_synthesis/. extract.py writes the plain text of every artifact; verify_quotes.py checks a quote against that text and the page's own files; merge_contradictions.py joins the sweeps; render_contradictions2.py writes contradictions.md with one page per cluster under contradictions/; render_inventory.py, render_clusters.py, render_toc.py and textbook_toc.py made the other files.
- out/clustering.json: the 14 clusters. out/toc-hand.json: the proposed table of contents.
- out/sweep-A-raw.json and out/sweep-B-raw.json: the finders' candidates for clusters 2 to 13 (372 and 269 candidates, Outreach included), with whatever verdicts came back.
- out/contradictions-all.json: the merge of every sweep so far; out/clusters-verify-0-1-6.json and out/numbers-partial.json: clusters 0, 1 and 6 and the 247 number collisions, 15 of them with a verdict; out/numbers-verify-batches.json: the 87 number candidates in 17 batches still to be read.
- out/journal-results.json: every agent result the last three runs returned before they were stopped, and the list of those that did not finish.

## What is left of issue #136

1. Verify the candidates no skeptic has read. Not finished: the verifiers of Datasets, Detectors, Verification benches, the OR study, Programme direction, Symphony, Symphony's origins, Grid operations, Beethoven, Level naming and Renders, and the 17 number batches. Only FluoroCap's and Transitional vertebrae's came back. A skeptic reads both source texts of a candidate and says confirmed, superseded, refuted or cannot tell.
2. Merge: `python3 -I tools/merge_contradictions.py out/clustering.json out/contradictions-all.json <new results> extra=<number verdicts>`, then render with render_contradictions2.py into artifacts/_synthesis/contradictions.md and contradictions/.
3. Update the counts in artifacts/_synthesis/README.md and docs/research/artifact-textbook/README.md, delete this work folder or keep it as the record, delete the claim file, run bash scripts/check.sh in a throwaway clone, push, write the adversarial review into #137's body, mark it ready and merge once green.

Run the scripts with python3 -I from a scratch directory; REPOS in verify_quotes.py names the two checkouts' artifacts/ folders and may need the new paths.

## After #136

Phases 2 to 4 (sourced research per cluster with every claim graded, the chapters under docs/textbook/, the experiment stubs) start only on the owner's go and his answers to the 9 questions on #121, each under an issue of its own. No grid job, training run or paid usage is part of this work.
