# Handoff: Continue Bayesian synthetic validation, 2026-10-30

This is the symphony_3 project thread that ran the gold tier 3 C2 and sacrum completion (the gate
word `totalseg complete`) and drove bordercall PR 38. It was written on greg's order of 2026-10-30
at 20:35 UTC to stop and hand off. No checkout holds uncommitted or unpushed work.

## State

- The first job, 40882547 (15:55 UTC, at 2fe153f), failed on all 37 prepared studies because
  tools/profile.py shadowed the standard library's profile. Its report stands on the grid as
  logs/TOTALSEG-complete.md.
- The fix merged as SchwingNet #499 (b49583b). It strips tools/ from sys.path, reruns failed
  studies, finds ENHANCE.PET's Vertebrae file, and adds TOTALSEG_RERUNS="complete:40882547" to
  grid/gate.sh. The next send of the word moves that report aside and queues one GPU job, on greg's
  tap of 16:49 UTC. At 16:59 UTC greg said to send grid jobs without asking him.
- The rerun was not sent. A review of the path found two faults that would fail it again; they are
  in docs/research/gold3-ct/completion/RERUN-REVIEW.md, items 1 and 2.
- bordercall PR 38 is a draft (branch claude/project-thread-o3ng22-all-measures, head 7817492: every
  engine measure the bounds card shares is scored, and the gold tier 3 write-up is corrected). Its
  gold tier 3 scores used the engine from before bordercall PR 44 (job 40878978, at c656299). Body
  and end-plate steps pass; pedicle and canal steps fail, which PR 44's wall rework should change;
  the disc steps fail for an unexplained reason. Its body says what it holds.

## Next steps, in order

1. In one SchwingNet pull request, fix RERUN-REVIEW.md items 1 and 2 (and 4 to 6 where cheap), each
   with a test. Ask greg about item 3, the sacrum with S1; on his word, add it with an item in
   docs/research/gold3-ct/completion/DEVIATIONS.md.
2. Once that merges, send the word: symphony-template's .github/workflows/grid-accounts.yml, action
   job, job schwingnet-totalseg-complete, a new request name. The answer lands on symphony-template's
   branch grid as logs/job-schwingnet-totalseg-complete.json, with the job id. TOTALSEG_RERUNS still
   names 40882547, so it queues exactly one job.
3. Once the job ends, send the word again to read logs/TOTALSEG-complete.md. Record the counts by a
   follow-up pull request:
   - data/gold3-ct/members.json, completion.totalseg_arm, whose state is stale since 2fe153f;
   - docs/research/gold3-ct/README.md, sections 2c and 7;
   - DEVIATIONS.md, since the arm now takes three jobs.
4. bordercall PR 38: once bordercall PR 44 merges, re-pin its engine and rescore gold tier 3 as job
   40878978 did. Then find why the disc steps fail.

## Where things are

- Merged: SchwingNet #497 (c656299) and #499 (b49583b); symphony-template #510 (f2f75fd) and
  hpcworker #53 (0f323d4). Those two, with SchwingNet's grid/gate.sh, are the gates that know the
  word.
- Project memory notes: totalseg-complete-sent, gold3-on-bounds-card and
  rule-selection-result-2026-10-30.
