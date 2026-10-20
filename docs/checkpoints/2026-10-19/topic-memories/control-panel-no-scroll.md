---
name: control-panel-no-scroll
description: greg's rule of 2026-10-19 for every control panel tab: nothing scrolls, everything fits the screen, zoom instead, buttons sized to the screen, tap a node to focus
metadata:
  type: feedback
  modified: 2026-10-19T13:09:32.176Z
---

greg, 2026-10-19 13:05 UTC, after seeing the new Dependencies look ("light years better"): "I literally never in any case want to scroll, I'd prefer to need to zoom but scrolling shouldn't be allowed. Just pinch and zoom on mobile, touch to focus ... if I select a node it will be blown up and only its immediate neighbors will be visible but I can swipe to navigate. Essentially the default view of every tab should be to just have all the shit out in front of you and let the user [zoom] in, and buttons should be dynamically sized to fit the screen they are on".

**Why:** he reads the panel on a phone and a laptop and finds scrolling, clipped charts and fixed-size buttons clumsy; he would rather zoom into a whole view.

**How to apply:**
- Every tab's default view fits the screen whole: no page scroll, no sideways scroll, no inner scroll box.
- Content too small to read is zoomed (pinch, ctrl+wheel or wheel, +/- buttons), never scrolled.
- Tiles, buttons and columns size from the screen (clamp, auto-fit grids), never fixed widths that overflow a phone.
- Charts: tap a node to focus it with only its immediate neighbours, swipe to move along them.
- The Dependencies tab came first: site branch claude/dependencies-zoom, checks claude/dependencies-zoom-checks (merged and live 2026-10-19 20:31 UTC: site #95, checks symphony-app #49, after merging with #93; greg skipped the merge's review at 95% usage). After it lands, the panel's own "What this page keeps and sends" (body.html, admin__lead) must match statement 35: Google Fonts, the pending sign-in record, the stored chart choice. The other tabs follow (held until greg's usage resets and he says go), planned from the survey at scratchpad fit-survey/plan.md.
- A sideways-scrolling strip of tiles counts as scrolling.
- greg 2026-10-19 16:51 (card): very long lists show as numbered chips coloured by state, or a map of sections, that a pinch or tap opens to full size; small lists keep their full cards. Plan: /mnt/project-files/control-panel/fit-every-tab-plan-2026-10-19.md.
- greg 2026-10-19 13:54: all three panels resizable (side, stage and the message foot, which had no grip), and on the control page the site bar hides like an auto-hiding taskbar, showing when the pointer reaches the top. Merged and live 2026-10-19: site #93, checks symphony-app #47. His setup-without-template-access point went to the Add token fixes thread.

Related: [[control-panel-foot-tasks]], [[dependencies-focus-strip]].
