---
name: fluoro-tasks-plan
description: The real-time fluoroscopy task plan (greg's ask of 2026-10-29 15:24 UTC) checkpointed at 17:27 UTC as SchwingNet draft PR 467; no issue created yet; where the control panel reads tasks from and the twelve-task draft order
metadata:
  type: project
  modified: 2026-10-29T17:29:02.109Z
---

greg, 2026-10-29 15:24 UTC: "create the tasks that need to be done for this project to be done where i can label vertebra from fluroscopic xray without any segmentations in real time, and create a demo video of it running on an mp4 video of fluroscopic spine panning, make them linear or github tasks so i can see them in the symphony control panel". Thread "Plan real-time fluoroscopy labelling as GitHub tasks" (cmsg_0155QZgnLnXyddb75umH2eJLXE7KGdhanfHJ7E7D2nQvfk).

State at the checkpoint (17:22 UTC "PUSH ALL WORK AND CHECKPOINT", 17:27 "STOP ALL ADVERSARIAL REVIEW AND PUSH"): NO issue, label or comment was created. The handoff is SchwingNet docs/checkpoints/2026-10-29-fluoro-tasks/HANDOFF.md on draft PR 467 (https://github.com/OpenSpineConsortium/SchwingNet/pull/467, branch claude/project-thread-wyzavv); the two finished readers' maps (frame model/latency/demo; the naming layer) are /mnt/project-files/fluoro-tasks/maps-2026-10-29.json, never in git.

Settled: the panel reads SchwingNet's open issues grouped by label (blocker; epic/goal; in-review; claimed; blocked; worker:<name>; todo = Queue), draws an epic's sub-issues and GitHub blocked-by relations; the label epic on an issue without "<!-- team:plan -->" in its body starts coordinator.yml's Claude planning, so the epic is created with the marker; todo starts no worker (none registered); "@claude" in text starts claude.yml, so none.

Draft order (details in the handoff): 1 latency record on a launched LatencyFlow (#138); 2 V1Flow run recorded (#256); 3 bordercall PR 29/26 then the 106-measure validation; 4 gold-CT reference table (census gold3 #463, the 2-CPU pilot); 5 the auto-anatomist as a Metaflow block with real extractors (PR 30), HPO and RL; 6 CT-to-fluoroscopy transfer and the image-only path (waits on realism stats, DRR run 3, #391 which only greg starts); 7 a detector stage; 8 a frozen real held-out fluoroscopy test set (greg names sets and readers); 9 naming that follows a pan under 97 ms p95 with ONNX parity; 10 the end-to-end path with a video reader; 11 the demo MP4 (greg chooses the clip; shown only after the provisional is filed). Every grid step on his word and count.

**Why:** the next thread must create the issues from the handoff, not re-plan, and must not start the coordinator's planning by accident.
**How to apply:** read the handoff, create the epic with the marker, the tasks as todo sub-issues in the Task form's shape with blocked-by links, method-free text; reply with links and the order. See [[metaflow-required-for-grid-dl]], [[item-p-state]], [[autoanatomist]].
