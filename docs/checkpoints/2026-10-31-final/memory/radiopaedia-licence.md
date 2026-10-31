---
name: radiopaedia-licence
description: greg got a Radiopaedia licence (2026-10-31 01:44 UTC) as a new source of real fluoroscopy; how it may be fetched and used is still open
metadata:
  type: project
---

2026-10-31 01:44 UTC, greg: "i recently obtained a radiopedia license which im sure will provide a large new source of flurooscopic xrays".

2026-10-31 01:47 UTC, greg's answers: the licence allows fetching by script, so ignore the site's HTML flag saying it is not allowed. He also has a new IRB; its number is not yet given. The fetch, the licence record and the rule change went to the coordinator for a thread of its own. Still needed from greg: the IRB's number and scope, and the licence clause or reference.

The original questions, from 01:46 UTC:
- How does the licence deliver the cases (a bulk export, an API, or browsing)? The standing rule "Radiopaedia is never fetched by script" (SchwingNet CLAUDE.md durable decisions) holds until greg says otherwise. A change to it goes by pull request.
- Does it need an IRB supplement? The umbrella HPR 2026-269 covers only public data downloadable without an agreement; VinDr got HPR 2026-330.
- What licence class does it take in data/licences.json? Only the owner sets or loosens a class.

Planned use: unlabelled real fluoroscopy for the realism step and for pretraining the X-ray encoder. Once readers name the levels, it also feeds the person-disjoint validation and test slices. Hash its images against our corpora before any goes into a test split, since some public sets reuse Radiopaedia images.

**Why:** it may be the largest real fluoroscopy source for [[xray-stage-flexray-chain]].

**How to apply:** scripted fetching is allowed by greg's word, but the SchwingNet CLAUDE.md rule changes only by pull request, citing the licence clause. No fetch job runs before that pull request lands.

2026-10-31 01:52 UTC: greg said to skip the IRB/clause questions and the rule-change PR. A test request from the cloud container got HTTP 406 (Radiopaedia's bot wall). Spoofing a browser user agent was refused as bot-check circumvention, so no fetcher runs until Radiopaedia gives a route (API credentials or an allowlisted, honestly named client). Asked greg whether to draft that e-mail to Andrew Murphy (receipt 1967-5247). The approval record (SchwingNet data/sources/radiopaedia.json) says there is no export, collection is "at a gentle rate" (clause 3), and the scope is phase 1 only.

2026-10-31 02:21 UTC: on greg's word, the allowlist request went out to license@radiopaedia.org, as a reply in the approval thread. Watch for the answer (check Junk Email too).
