---
name: metaflow-required-for-grid-dl
description: greg's rule of 2026-10-29 02:39 UTC: every deep learning grid job runs on his Metaflow block pipeline (flows/launch.py), REFORMS/CLAIM enforced; which words are moved and what is open
metadata:
  type: feedback
  modified: 2026-10-29T14:57:29.151Z
---

2026-10-29 02:36:55 UTC greg asked whether the work follows "the reforms/claim compliant enforecement and using my metaflow block based pipeline", with an HTML progress page. At 02:39:01 UTC, told the DRR study's run 2 did not use it: "dude wtf was the point of me making that pipeline if you arent using it! that should be a fucking requirement for all deep learning jobs i run on the grid". The coordinator wrote it into the project instructions. Card 03:23:57 UTC: v1's and the experiments' PREREGs are frozen as estimates with no accuracy bar; a bar he sets later is a new PREREG.

Thread "Require Metaflow for every grid DL job" enforces it, one SchwingNet PR per word:
- #454 merged 13:18 UTC (main a301b72): flows/registry.txt, frozen-PREREG check (exit 90, Covers: parts, `stage_registry.py frozen` in the required check), flows/stage.py (claim_report strict by default, still_held, run_began, finish), progress pages at <datastore>/progress/<Flow>/<run>/index.html; the sweep on it first.
- #456 (FluXray thread) put realism edit/stats on RealismFlow.
- #461 (branch claude/project-thread-ugyqtg): the DRR study (drr_gap, 18 jobs) and MOOSE (drr_seg) on launched flows; CI green, marked ready ~15:05 UTC. Run 3 is a FULL recomputation in its own folder flexray_drr_gap_run3 (gate.sh DRR_GAP_FOLDER -> DRR_GAP_OUT), run 2's flexray_drr_gap untouched, DEVIATIONS item 12; BENCH_RERUNS flexray_drr_gap:40859208 = greg's count of 12:51 UTC (18 GPU jobs + MOOSE only if masks missing, each once). The DRR thread (cmsg_0155QZgnLnXyddb75umH2eJLBxqLakYFYEkHi7ppeZp3F6) sends the word once #461 is on main; this thread sends nothing.
- Still plain jobs: start/v1, experiment, bench (three public benchmarks), anomaly timing, latency; then the gate refusing an unlaunched GPU job.

Local unpushed work (on #454's old head 45a145c; merge main in first): /home/user/sn-v1 wip/v1 6108ba2 (V1Flow, PREREG docs/research/v1-demo/PREREG.md); /home/user/sn-exp wip/exp 52cadb7 (flows/flow_tool.py); /home/user/sn-latency wip/latency 5407bef (LatencyFlow WIP).

The 14:25 UTC checkpoint was cancelled by greg at 14:53 UTC: "Just continue all without handing off but please use the grid where appropriate". Subagents hit the 5-hour limit at 14:25 UTC (resets 17:00 UTC).

**Why:** greg built the pipeline so every run is resumable, block-named and reported the same way; a job around it wastes that.
**How to apply:** before proposing or sending any GPU word, check that its sbatch starts through flows/launch.py; if not, say so and do not send it. See [[grid-words-and-counts]] and [[dl-jobs-run-on-metaflow]].
