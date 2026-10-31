# Handoff: gold 4 TotalSegmentator, the X-ray stage plan, the prior check

Thread "Train on randomized spine phantoms" (claude.ai project symphony_3), written 2026-10-31 at about 14:40 UTC for an account or a local session to carry on. Nothing here is public.

## 1. Gold 4 TotalSegmentator (running or finished on the grid; read not done)

- Sent 2026-10-31 04:00 UTC as the gate word `totalseg gold4`: GPU array 40902775 (16 tasks) and CPU merge 40902777, under docs/research/gold4-totalseg/PREREG.md (DEVIATIONS.md item 1, merged in #526). At 05:19 UTC 579 of at most 1,328 CTs were done, none failed.
- When the merge ends, its records are /rs/rs_grp_oschome/go2432/gold4-totalseg/records.jsonl and the report is the word's answer.
- Next: read it. From a cloud session: dispatch symphony-template's .github/workflows/grid-accounts.yml with action=job, job=schwingnet-totalseg-gold4, request=gold4-check-3 (any new request name), then read logs/job-schwingnet-totalseg-gold4.json on symphony-template's branch `grid` (scratch/wait_grid_answer.sh does it). Locally on the grid: `bash ~/SchwingNet/grid/gate.sh totalseg gold4` as the gate runs it. If it says the chain still runs, wait; if it ended short of 1,328 with headway, the same word sends again.
- Then report to greg the counts by collection and the three bars of the PREREG, and tell whoever runs the Metaflow pipeline that records.jsonl is final (they were waiting on it). Grid Actions were refused from 06:20 to about 14:20 UTC (billing).

## 2. The X-ray stage plan (filed, nothing run)

- bordercall #67 is the umbrella; its sub-issues #68 to #75 are stages 0 to 7 (count and split the real frames by person; the latent shape model; warped-CT phantoms through FleXray; the fast classifier; the posterior and the frame path's timing; field-width and landmark fingerprints; the zero-shot real-frame read; end to end last). No labels, so no worker takes them.
- #67 ends with six decisions for greg, each with the default the plan follows: a hashed 0.3 test share; all three real L6 persons stay in test; no model reads Radiopaedia; no stage 5 bar, so no smallest field; no fine-tune bar, so no fine-tune; render and compare offline only. Stage 0 (#68) can start now.

## 3. The gold tier 3 prior check (designed, not built)

- The finding and the design are docs/research/gold3-prior-check/ (README.md, SPEC.md, READING.md). The prior's measure part stays held; its level part stands (bordercall records/prior-2026-10-31, refit by job 40903052 to the same lines).
- The build workflow stopped at the weekly limit. Left: scratch/prior_rows.py.partial (338 lines, the standard-library half: splits, the reserve drop, line shapes; unreviewed, meant for grid/prior/prior_rows.py), scratch/build-workflow.js (the orchestration with its 11 decisions), scratch/priorcheck2/ (the build task, the line catalog, the matched truths) and scratch/priorcheck/ (the prototype: kron_sim.py, judge/check_proto.py, the reduced run_naming copies and their results).
- Next: build prior_check.py and its tests from SPEC.md, vendor bordercall schwingcheck/columns.py at 8ae5db9 with the VENDORED line SPEC gives, add data/gold3-ct/enhance-pet/facts.jsonl to the sbatch's archive, freeze READING.md by its sha256, merge, send `morphometry prior`, read it with READING.md. Open questions are SPEC's last section.
- Bordercall follow-ups, not filed: correlation.py's docstring (a draw keeps mean and SD only without the size factor); the size factor counting size twice over a fitted prior; README's hold on the measure part until the check reports.
- Gate quirk: `morphometry prior` refits whenever main moved, not only when the prior's code changed; fix by judging the prior's files, as GOLD4_CODE does.

## Branch

claude/project-thread-dazoi0 in SchwingNet carries this folder, the research note and the memory lines; bordercall, symphony-template and spine-program had nothing uncommitted.
