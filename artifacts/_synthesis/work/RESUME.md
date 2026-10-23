# Artifact Textbook: where to resume

Written 2026-10-22 23:45 UTC by the thread "Artifact Textbook" when the owner's account reached its usage limit, so another account's session could carry the work on; rewritten on 2026-10-23 by the thread "SchwingNet textbook and Flepp critiques", which finished it. Issue #136, branch claude/136, pull request #137. Phase 1 (inventory, clusters, contradictions found, proposed table of contents) is merged by #121; its 9 questions for the owner are on #121, where the owner's answers of 2026-10-23 are recorded too (#151).

## What this folder holds

- tools/: the scripts that made artifacts/_synthesis/.
  - extract.py writes the plain text of every artifact, with e-mail addresses and phone numbers replaced before any reader sees it.
  - verify_quotes.py checks a quote against that text and the page's own files.
  - merge_contradictions.py joined the sweeps and merge_resume.py the results the first account's journal held.
  - prep_verify.py wrote the skeptics' input files, one per group of clusters and one for the numbers.
  - merge_skeptics.py keeps a workflow's results from its journal, merges the skeptics' verdicts into the record at each candidate's index, and puts a second reading in place of an earlier number verdict; every merge checks its input first.
  - sample_review.py draws the review's sample and writes the re-checkers' input files; run on the record as it stood at 1c656d4, it draws the review's 58 verdicts again exactly and checks them against out/review-137.json.
  - apply_review.py applies the review of the skeptics' verdicts, keeping each overturned verdict under first.
  - check_verdict_quotes.py checks that each verdict quotes its own candidate's artifacts.
  - redact.py replaces what the folder's rule keeps out of the records and pages with an editor's words in square brackets.
  - render_contradictions2.py writes contradictions.md and one page per cluster under contradictions/.
  - render_inventory.py, render_clusters.py, render_toc.py and textbook_toc.py made the other files.
- out/clustering.json: the 14 clusters. out/toc-hand.json: the proposed table of contents.
- out/sweep-A-raw.json and out/sweep-B-raw.json: the finders' candidates for clusters 2 to 13 (372 and 269 candidates, Outreach included), with whatever verdicts came back first.
- out/contradictions-all.json: the merge of every sweep; out/clusters-verify-0-1-6.json: clusters 0, 1 and 6 as first verified; out/numbers-partial.json: the 247 number collisions and the 15 verdicts of #136's first run; out/numbers-verify-batches.json: the 87 number candidates the second run read.
- out/journal-results.json: what the first account's runs returned before they were stopped. out/journal-results-2.json and out/journal-results-3.json: the skeptics' verdicts of 2026-10-23, nine groups and then the tenth, as their journals held them.
- out/in-numbers.json: the 87 number candidates in the order the second run's indices count. out/in-reread.json and out/reread-results.json: the 10 number verdicts read again and their new verdicts. out/review-137.json: the review's sample, each re-checker's reading and each judge's ruling.
- out/contradictions-merged.json: the record the pages are rendered from. out/verdict-quotes.json: the last quote check of the verdicts.

## Where it stands on 2026-10-23

All 14 clusters are swept: 858 candidates, each with a skeptic's verdict after reading both sources. 102 of the 247 number collisions have one too: the 91 a reader classed as a contradiction or a later revision and 11 more #136's first run took. Ten of the first run's were cannot-tell because their values were missing from the plain text, which cuts each line of a page's script data at 600 characters; a skeptic read them again in the artifacts' own files (merge_skeptics.py reread), and they now say 6 scope-or-unit-differs, 2 confirmed-contradiction and 2 same-number-restated, each with its first verdict kept.

The verdicts were then reviewed. 54 of them, drawn by stratum and SHA-1 (tools/sample_review.py draws them again from the record as it stood at 1c656d4, since the rulings later moved verdicts between sides), and the 4 whose own quotes the script could not place were read by re-checkers told to overturn them, and a judge ruled on every dispute (out/review-137.json, applied by apply_review.py): of the verdicts drawn at random, 26 of 30 that put a candidate on the confirmed list held and 22 of 24 that kept one off; 3 of the 4 drawn because the script could not place one of their own quotes were overturned. In all 9 verdicts were overturned and 2 hints corrected. contradictions.md gives the rates with their Wilson intervals and lists every changed row. The rates are unweighted, since every stratum gave the same number of verdicts; weighted by the verdicts each stratum holds that the review did not read, about 82 % of the confirmed ones are expected to hold, and the number collisions, where both drawn confirmations were overturned, hold the most of those that may be wrong, which the page says too. A reviewer of the pipeline found the merge sound and eleven problems of presentation and of re-running, none high and all now fixed: among them the confirmed column counting duplicated texts and unsourced claims as disagreements, rows numbered from 1 where the skeptics count from 0, broken links on the cluster pages, and a renderer that wrote a clean-looking page when the paths it reads were unset. A privacy reader found a first name, a login in a grid path, a network range, a form's link, a staff title, a settings page's address and another group's folder name in the records; redact.py replaced them in every file under out/ and in the pages.

check_verdict_quotes.py finds each quote the 960 verdicts give in its own artifact but one: the ruling on row 88 of the verification cluster quotes the later page its explanation names, which the candidate does not, and the page says where that quote was found.

## What is left

1. Nothing of #136. The 145 number collisions that readers classed as another scope or another quantity have no skeptic's verdict, by design; the script found both of their quotes in the sources for 142 of them, one only in part for 2, and one not at all for 1. The verdicts the review did not draw were not read again, so a planner reads a row before relying on it, as the page says.
2. To render again: `SYNTH_TEXT=<text dir> SYNTH_SCHWINGNET=<clone> SYNTH_SYMPHONY=<clone> python3 -I -B tools/render_contradictions2.py out/contradictions-merged.json out/numbers-partial.json ../inventory.json ../contradictions.md <date>`, after `python3 -I -B tools/extract.py <clone> SchwingNet <text dir>` and the same for symphony-template, then `python3 -I -B tools/check_verdict_quotes.py out/contradictions-merged.json out/numbers-partial.json out/verdict-quotes.json`, and update the counts in artifacts/_synthesis/README.md and docs/research/artifact-textbook/README.md. The renderer stops when a path variable is missing, and the merge tools stop on an index or a verdict word they cannot place.

## After #136

Phases 2 to 4 (sourced research per cluster with every claim graded, the chapters under docs/textbook/, the experiment stubs) start only on the owner's go, each under an issue of its own. The owner's answers of 2026-10-23 to the 9 questions are on #121, and table-of-contents.md gives each beside its question (#151); to render the plan again, from this folder: `python3 -I -B tools/textbook_toc.py > out/toc-hand.json`, then `python3 -I -B tools/render_toc.py out/toc-hand.json ../inventory.json ../table-of-contents.md 2026-10-22`. No grid job, training run or paid usage is part of this work.
