# Handoff: the SPINEPS to FleXray anomaly route for #391 (2026-10-25)

Thread "Plan the FleXray audit for #391", checkpointed at the owner's word of 2026-10-25 22:35 UTC. The research is docs/research/spineps-anomaly-route.md; this page says only where things stand and what comes next. No grid job was sent by this thread.

## Done

- The #391 audit plan: symphony-template #488 (docs/research/flexray-audit-plan-2026-10-25.md, public half) and SchwingNet #395 (docs/research/flexray-audit-companion.md), both merged.
- The gate word's pass-through, both merged at 21:54 UTC: hpcworker #49 (tools/grid_gate.sh takes `schwingnet anomaly <stage>`) and symphony-template #491 (grid-accounts.yml takes `schwingnet-anomaly-<stage>`).
- SchwingNet #398, this branch (claude/project-thread-qp8k4u), a draft, pushed at the checkpoint and not merged:
  - the route note, with the CT finder scored from the records and the reviewers' findings folded in;
  - data/splits/anomaly-holdout.json: the holdout (VerSe 2 T13, 10 L6, 1 four-lumbar, 20 normals; CTSpinoPelvic1K 5 L6 and 5 normals), 6 VerSe and 7 CTSpinoPelvic1K disputed persons refused everywhere, and the four cross-validation folds of the other 73 clean VerSe L6;
  - tools/anomaly_route.py (freeze, score, select, check), grid/anomaly.sbatch and the gate word `anomaly select` in grid/gate.sh;
  - tests: tests/test_anomaly_route.py (8) and three in tests/test_gate.py pass; the full `bash scripts/check.sh` passed in a throwaway copy before the last round of fixes, apart from the seven beartype errors of tests/test_bank_depth.py that a container without the locked environment always shows.
- A second review (three readers and their skeptics) found four real defects, all fixed in the last commit: the dispute rule dropped the finder's own errors, validation_ts keyed TotalSegmentator CTs twice, the CTSpinoPelvic1K holdout normals were never drawn, and a stale test string.

## The owner's word and counts

- 21:00 UTC, the route, verbatim in the note's section 1. 21:11 UTC: the stitched-fields figure is a real anomalous example showing the count scoring 100 percent by error correction when every vertebra is detected (note section 6).
- 21:22 UTC, "Go: all 7 jobs, stage by stage": select (CPU), timing (GPU), pack (CPU), render (GPU), figure (GPU), tune (GPU), eval (GPU), each sent once its code has merged and the stage before looks sane, the owner told as each goes. The SPINEPS production array is not approved.
- 22:30 UTC, "Add it: 8 more GPU jobs": four-fold cross-validation, tune_f1 to tune_f4 and eval_f1 to eval_f4, sent only after the main fine-tune and its eval look sane. In all 15 jobs, 2 CPU and 13 GPU, 0 fetches.
- Item 15, the licence decision, still decides whether fine-tuned weights or names reach any SchwingNet network, the demo or a reported number.
- 22:31 UTC, the owner asked: "WAIT CAN YOU FIND ANY MORE FULL SPINE CORPUSES WITH ANOMALIES THAT ARE GROUND TRUTH?" A search (the records, CT, MRI and radiograph sets, the literature, each checked by a skeptic) was started and stopped at the checkpoint with nothing returned. It is the first thing to redo.

## Next

1. Redo the corpus search the owner asked for at 22:31 UTC and answer it; write what it finds under docs/research/ with a line in its README.
2. Merge SchwingNet #398: bring main in (it moved), run the anomaly tests and `python3 tools/check_docs.py`, write the review into the body, mark it ready in a call of its own, merge once green with the head sha copied from git, and check main.
3. Send the job word `update` through symphony-template's grid-accounts.yml (action job) so the gate's hpcworker clone knows the new word, read the status word (job schwingnet-status, answer at logs/job-schwingnet-status.json on symphony-template's branch grid), then send `schwingnet-anomaly-select` once and tell the owner. Its report is grid/logs/ANOMALY-select.md, printed by the next `anomaly select`.
4. Stage 2, timing, by pull request: the word, the GPU check at step 0, the list of paired CTs without a mask; then stages 3 to 7 and the folds as the note's section 8 lists, each sent after the one before looks sane.
