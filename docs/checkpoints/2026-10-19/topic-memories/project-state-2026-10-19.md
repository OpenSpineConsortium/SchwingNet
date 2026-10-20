---
name: project-state-2026-10-19
description: Who owns what and where each workstream stood on 2026-10-19 03:00 UTC (moved out of MEMORY.md to keep the index small); read before routing or resuming any thread's work
metadata:
  type: project
---

Snapshot of 2026-10-19 03:00 UTC; a newer checkpoint or PR wins. Moved here from MEMORY.md on 2026-10-19 13:15 UTC when the index neared its size limit.

- symphony-protocol: 0.5.1 PUBLISHED 01:48 UTC (greg approved). Both live rulesets already pin "check" to GitHub Actions. Protocol thread landing #45 (locks) and #51 (Dependencies). Template #236/#237 merged. Next: org-level settings via Setup App, one settings list.
- Control panel: Control panel sign-in owns sign-in, Worker, symphony-app checks/manifests, privacy versions (v31 live: start #74, site #82 with the Notebooks tab; v32 = Setup App's token lending, start #73 + app manifest #40, DRAFT until greg's own yes; protocol thread's start #72 needs it), Dependencies (focus chips, site #74), Folders/Explorer (#63; catalog route #67), Explore (#64), Ask Claude button, Share tab Ask to join (#77), Notebooks tab (live, site #82; checks app #41; see control-panel-notebooks). Done 2026-10-19: phone/foot fixes (site #78), iOS note (template #243), Mendeley plan (template #252). Cards posted 2026-10-19 07:10 UTC, awaiting greg's tap: Setup lending permissions (#73/#40/#72), a Make private button (SymphonyBoard Administration), iPhone way 1 (manifest/touch-icon head tags live in tools/build_site.py, which Website docs and navigation owns: hand over through the coordinator). Overnight report: /mnt/project-files/control-panel/2026-10-19-overnight.md.
- Folders/OneDrive: Entra app "SymphonyBoard Folders" client id 463afc21-8bbd-429b-a93d-3d3617966f0b (multi-tenant + personal); Worker vars MICROSOFT_CLIENT_ID/SECRET in Cloudflare. greg is NOT a WSU admin: WSU accounts need C&IT admin consent (letter in symphony-template#229 docs/setup/folders-admin-consent.md; in-screen request filed). Connector-mode catalog uses Claude's existing WSU approval (#227, merged).
- Drive organizer thread: building Word citations, tested on a made-up document first; project proposals need greg's go (reads ~40 files).
- Add token fixes thread: #235/#72/#240/#75/#77 merged; building issue-started lend/manage jobs, standing lend list, no-say lend; design in template #242.
- Claude tokens (tools/pool.py, tools/token_run.py, workers.yml): organization secrets SYMPHONY_CLAUDE_1-32 and CLAUDE_CODE_OAUTH_TOKEN, renew by 2027-10-17. TILE_MODELS in symphony-panel.js must equal KNOWN_MODELS in tools/pool.py.
- Agents: .claude/agents/ (reviewer, developer, tester); importing opens a PR; nothing spends until run.
- Every signed-in page must be a SymphonyBoard Callback URL. The Apps' privacy statement (symphony-start PRIVACY.md) goes live before a feature ships; the site page needs a rebuild after each version.
- Website: Website docs and navigation owns SITE in tools/build_site.py; no scheduled rebuild.
- Grid (hpcworker): runner chain stopped; grid.yml restarts it.
- Chrome Web Store: every merge to an extension repo's main is a store submission.
- Word documents: tools/docx_review.py; never overwrite a file greg changed.
- Experiments: nothing runs without greg's word and number.
- Handoff 2026-10-18b in symphony-template#230.
