# Ask the book: retrieval over the textbook as blocks

The thread "Make the textbook drive the research", 2026-10-24. The owner's words at 21:48 UTC: "A RAG trained on the textbook should help. Use a similar plug and play method package". Issue #250, pull request #251; the fact every session should know is docs/memory/the-textbook-rag.md.

A programme, since the question it measures, how well the book finds its own answers, changes with every chapter and with every new block name.

## Where it stands

- Built: the search as six parts chosen by name (src/schwingnet/rag.py), the tool that builds, asks, evaluates and checks it (tools/rag.py), the Ask the book box on the front page and every chapter of the site, which scores in the reader's browser, and the answer through the viewer's own `sample` in the claude.ai artifact. Version 1, the default, is section, plain, bm25, top, cite and none.
- Measured: finding, over the 54 questions of docs/textbook/rag/questions.json at commit 5dd29a9, for all 24 sets of the four search parts (the table below, recorded in docs/textbook/rag/eval.json). scripts/check.sh fails when version 1 falls below a recall at 5 of 0.8 or an MRR of 0.7.
- Not measured: answering. No answer Claude wrote from the passages has been read against them, and the answer in the artifact was seen only with a stand-in for the runtime, never in a real claude.ai viewer.

## The instrument

The questions were written by this thread from the chapters themselves, varied across the book, each with the chapter files that answer it and, for ten of them, the figure that does. For a question, recall at 5 is the share of its answering chapters among the chapters of the first five passages found; the reciprocal rank is one over the place of the first passage from an answering chapter among the first ten, and 0 when none is there; figure at 5 says whether the question's figure is among the figures the first five passages place or are. Each is a mean over the questions, figure at 5 over the ten. `python3 tools/rag.py eval --grid --write` measures every set and records it; `--vary chunk=window --vary index=tfidf` measures named alternatives against version 1.

The browser's copy of the scoring is held to the package's by tests/fixtures/rag-scoring.json, four builds and seven queries each, ranked ids and scores to the last bit, checked by the package's tests and by node. This thread also compared the two by hand on the whole book, all 54 questions under two block sets, and the first 50 scores of each agreed to the bit; that comparison is not a test.

## The measurements

| Block set | Passages | Recall at 5 | MRR | Figure at 5 | Missed | Commit |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| version 1 | 1228 | 0.877 | 0.764 | 0.400 | 3 | 5dd29a9 |
| retrieve=spread | 1228 | 0.886 | 0.764 | 0.300 | 3 | 5dd29a9 |
| index=tfidf | 1228 | 0.883 | 0.780 | 0.500 | 1 | 5dd29a9 |
| index=tfidf retrieve=spread | 1228 | 0.910 | 0.781 | 0.300 | 1 | 5dd29a9 |
| tokens=stem | 1228 | 0.877 | 0.754 | 0.400 | 3 | 5dd29a9 |
| tokens=stem retrieve=spread | 1228 | 0.895 | 0.756 | 0.200 | 3 | 5dd29a9 |
| tokens=stem index=tfidf | 1228 | 0.920 | 0.785 | 0.400 | 2 | 5dd29a9 |
| tokens=stem index=tfidf retrieve=spread | 1228 | 0.938 | 0.786 | 0.200 | 1 | 5dd29a9 |
| chunk=window | 1293 | 0.846 | 0.716 | 0.600 | 6 | 5dd29a9 |
| chunk=window retrieve=spread | 1293 | 0.873 | 0.718 | 0.300 | 5 | 5dd29a9 |
| chunk=window index=tfidf | 1293 | 0.892 | 0.719 | 0.400 | 2 | 5dd29a9 |
| chunk=window index=tfidf retrieve=spread | 1293 | 0.910 | 0.719 | 0.200 | 2 | 5dd29a9 |
| chunk=window tokens=stem | 1293 | 0.892 | 0.743 | 0.500 | 4 | 5dd29a9 |
| chunk=window tokens=stem retrieve=spread | 1293 | 0.892 | 0.745 | 0.300 | 4 | 5dd29a9 |
| chunk=window tokens=stem index=tfidf | 1293 | 0.904 | 0.805 | 0.300 | 2 | 5dd29a9 |
| chunk=window tokens=stem index=tfidf retrieve=spread | 1293 | 0.932 | 0.806 | 0.200 | 1 | 5dd29a9 |
| chunk=figure | 1323 | 0.886 | 0.771 | 0.500 | 3 | 5dd29a9 |
| chunk=figure retrieve=spread | 1323 | 0.886 | 0.771 | 0.500 | 3 | 5dd29a9 |
| chunk=figure index=tfidf | 1323 | 0.873 | 0.800 | 0.600 | 2 | 5dd29a9 |
| chunk=figure index=tfidf retrieve=spread | 1323 | 0.910 | 0.802 | 0.500 | 1 | 5dd29a9 |
| chunk=figure tokens=stem | 1323 | 0.858 | 0.752 | 0.500 | 4 | 5dd29a9 |
| chunk=figure tokens=stem retrieve=spread | 1323 | 0.867 | 0.755 | 0.300 | 4 | 5dd29a9 |
| chunk=figure tokens=stem index=tfidf | 1323 | 0.901 | 0.790 | 0.600 | 2 | 5dd29a9 |
| chunk=figure tokens=stem index=tfidf retrieve=spread | 1323 | 0.929 | 0.792 | 0.500 | 1 | 5dd29a9 |

Version 1 misses three questions outright: what counts as one person in a split (chapter 09), how many vertebrae must be in view to name a level exactly (chapter 11) and what makes a comparison invalid (chapter 19). In each the question's words are not the chapter's: the chapter answers in its own terms, and a search that matches words cannot see that they mean the same. That is the gap an embedding name is for.

## What each choice changed

Each line holds the other three search parts fixed and averages over every set of them, so a change is set beside the same set without it.

- Index, tfidf for bm25 (12 pairs): recall at 5 +0.031 and MRR +0.030 on average, the MRR never lower (from +0.001 to +0.062). The largest single gain. Why tf-idf with passages scaled to length one ranks better here than BM25 with its usual settings was not tested; k1 and b were not tuned, by design, so that the comparison is of the two as usually set.
- Tokens, stem for plain (12 pairs): recall +0.014 and MRR +0.014 on average, but it depends on the index: with bm25 alone it lowers the MRR (0.764 to 0.754), with tfidf it raises it, and with windows, tfidf and spread it adds 0.087. Figure at 5 falls by 0.058.
- Retrieve, spread for top (12 pairs): recall +0.018, never lower, and the MRR unchanged (+0.001), since the first passage is the same either way; figure at 5 falls by 0.158, since a chapter's figures sit in its own passages and spread keeps no more than two of them.
- Chunk, window for section (8 pairs): recall -0.006 and MRR -0.025 on average, the worst with plain and bm25 (MRR 0.716), yet windows with stem, tfidf and spread rank best of all 24 (MRR 0.806). Why windows cut across headings to that effect was not tested.
- Chunk, figure for section (8 pairs): figure at 5 +0.162, since a figure's record, its caption, grade, status and notes, becomes a passage a question about the figure can find; MRR +0.008 and recall -0.009.

The best recall is stem with tfidf and spread, 0.938 against version 1's 0.877, with an MRR of 0.786; the best MRR is windows with stem, tfidf and spread, 0.806 with a recall of 0.932.

## Why version 1 stays the default

As the training blocks keep version 1 as the reference every run is set beside, the default changes only by a pull request that shows the eval. The best set's lead is 0.061 in recall at 5, about three questions' worth over 54, and the questions were written by the same thread that built the search, from the chapters' own phrasing, so they may favour any set that matches words closely. A lead of three questions on such a set is a candidate for version 2, stem with tfidf and spread, not a settled result; questions from readers would settle it. The browser's copy carries every search part, and the box reads the blocks, the stop words and the suffix rules from the index the site builds, so a new default reaches the site with one name changed.

One hazard was met on the way: the chapter section that describes the search (chapter 33, Asking the book) used the word words often enough that version 1 found it, not chapter 02, for "Which words does the book refuse to use", which cost 0.019 of recall until the section was reworded. A chapter about the book itself competes with questions about the book.

## What would change it

- An embed name: a local embedding model, run in the train environment and never through an API key, measured on these questions beside the word-matching sets, the misses above first.
- Questions from readers, for instance those that reach the repository through Ask Claude, whose issue carries the question and the passages found.
- An answer measure: Claude's answers from the passages read against the passages, for whether each claim it makes is in a passage it cites.
