---
name: experiments
description: State of the coordination experiments on 2026-10-18: the coordbench curse-of-coordination run, the flowbench pilot and beyond cooperation's steps
metadata:
  type: project
  modified: 2026-10-18T06:37:40.542Z
---

- coordbench curse-of-coordination run: 215 runs (coordbench#28, note #146), passes of 43: solo 33, coop 30, sdlc 32, coop-git 32, team 33; not significant, not for the grant. Bench agents inherit a ~80,000-token prompt; grant figures need standalone agents in Actions, k of n with Wilson intervals.
- flowbench pilot (flowbench#2, note #157): 24 runs, ~$7.86; symphony 8/8, script 8/8, solo 7/8; symphony used 0.75 of the script's tokens. Next: 96 runs on greg's word.
- Beyond cooperation (docs/research/beyond-cooperation/ in symphony-template): steps 1-4 merged (epics #127-#130, tasks #131-#144); builds and runs wait for greg.

**Why:** moved out of MEMORY.md on 2026-10-18 to keep the index under its size cap; these are settled results and holds.
**How to apply:** no new runs, pilots or batches without greg's word and number (the experiment grows by strata, his choice at each step); no coordination data in the grant or the competitors doc until he has run the full suite and tried xblossom. See [[curse-of-coordination-hold]] and [[beyond-cooperation-step-4]].
