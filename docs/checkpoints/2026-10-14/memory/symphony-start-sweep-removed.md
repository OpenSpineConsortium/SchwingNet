---
name: symphony-start-sweep-removed
description: The sweep is gone from symphony-start (PR #42, 2026-10-13); the form is the one way in; stale sweep wording remains in symphony-template and symphony-marketplace docs.
metadata:
  type: project
  modified: 2026-10-13T18:42:20.752Z
---

On 2026-10-13 18:41 the sweep was removed from OpenSpineConsortium/symphony-start: symphony-start#42 merged as e14903d (on top of the empty-repository adoption, #41, fcedd3e), and the site's privacy page went to version 7 in openspineconsortium.github.io#16 (db905fc). Installing SymphonyBoard alone is no longer a request; the install's redirect lands on the form and the press is the request. scripts/sweep.py keeps its name as the shared GitHub client and adoption rules library (resolve.py, adopted.py and adopt-run.yml's kind read import it); nothing on the front door runs on a schedule any more.

Still stale, left undone on purpose (the owner's optional item 6 and nearby): symphony-template docs/start/claude-code.md step 1 ("needs a first commit") and step 5 ("The sweep is the fallback..."), docs/memory/the-front-door-is-one-press.md and its MEMORY.md line (sweep as fallback), the CLAUDE.md decision lines that call the sweep the fallback, and symphony-marketplace plugins/sdlc/skills/new/SKILL.md (the same first-commit line). One small PR per repository clears them.

**Why:** a thread that touches those docs or PRIVACY.md should not reintroduce the sweep or describe it as live.

**How to apply:** when editing symphony-start's README, CLAUDE.md or PRIVACY.md, or the template's start docs, describe the form as the only path; PRIVACY.md's next version is 8.
