---
name: errors-link-to-fix
description: App-wide rule (Ashley via greg, 2026-10-19) that every fixable error on Symphony's pages links to its exact fix
metadata:
  type: feedback
  modified: 2026-10-19T13:24:57.636Z
---

Every error a user can fix links to the exact page or button that fixes it. An error only someone else can fix names who, and offers the Ask button.

**Why:** Ashley's message on Add Token was owner-only prose with no link (2026-10-19). greg: "This philosophy should just be baked into the entire application."

**How to apply:**
- In the site's symphony-panel.js, say(), msgTask tell() and richText(node, text) draw every https address as a link (site #90, #91).
- Write the full https:// address of the fix into the message, never a bare github.com/... path.
- Give a fixable error its address when it is written.
