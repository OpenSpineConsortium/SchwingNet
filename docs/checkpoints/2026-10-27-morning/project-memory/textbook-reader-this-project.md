---
name: textbook-reader-this-project
description: The live door into SchwingNet: the claude.ai door (https://claude.ai/artifact/XYY2CdsjvyRfxQfYq2EkkV) serves only the owner; for other readers it is moving to a GitHub-signed-in page on openspineconsortium.com (site draft #147, checkpoint 2026-10-27 04:47 UTC)
metadata:
  type: project
  modified: 2026-10-27T04:51:13.363Z
---

claude.ai door: tools/front_door.html on SchwingNet main (#405, #408, #409), mcp GitHub connector + sample. Owner's open steps unchanged: GitHub App "SchwingNet door" (Contents read, SchwingNet only), custom connector named exactly `GitHub` (callback https://claude.ai/api/mcp/auth_callback), then on the owner's computer `git pull` and `python -X utf8 tools/textbook_publish.py local --url https://claude.ai/artifact/XYY2CdsjvyRfxQfYq2EkkV`. NEVER publish an mcp-declaring page from a cloud thread. Handoff: SchwingNet docs/checkpoints/2026-10-26-front-door/HANDOFF.md.

Other readers (owner 2026-10-27 04:19 UTC: "let other people see this live front door like I can, after only running this publish command once"; individual claude.ai plan, no other org members): claude.ai gives connectors only to members of the owning org (email invitees and public links get none), so a connector-store GitHub App changes nothing. Answer: the door as a page on the public site, /symphony/door/?repo=OWNER/NAME, reader signs in with GitHub via the control panel's sign-in (SymphonyBoard user token, stateless Worker) and reads live with their own access; page holds nothing of SchwingNet. Superseded asks: 03:12 browser-only access requests (answered, SchwingNet #415 docs/research/reader-access.md), 04:12 email sharing, 04:17 card "Reader edition shared by email" (dropped).

State at the 04:47 UTC checkpoint: site draft https://github.com/OpenSpineConsortium/openspineconsortium.github.io/pull/147 (804c22d: assets/js/door.js, door.css, page, initDoor in symphony-panel.js with a GET-only client; check-only passes; NO tests, NO review yet; not subscribed). SchwingNet draft #419 (branch claude/project-thread-24opi2, f769337, pushed through the gate): .github/symphony/door.json (8 starting points), handoff docs/checkpoints/2026-10-27-door-for-readers/HANDOFF.md (next steps: Playwright tests, 3 reviews, check.sh, ready, merge; then owner adds callback URL https://openspineconsortium.com/symphony/door/ to SymphonyBoard, gives readers Read, sends the link).

**Why:** costs the owner should hear again: a seat per reader where charged, readers can clone, no Ask; outside readers before the filing are the owner's call (TTO question).

**How to apply:** a resumed thread reads the 2026-10-27 handoff first. Unknowns: code search with App user tokens; SymphonyBoard Contents read on SchwingNet; registered callback URLs; `schwingnet.*` message names now in public site code. Related: [[symphony-project-memory]].
