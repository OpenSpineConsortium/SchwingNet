---
name: dependencies-focus-strip
description: The control panel's Dependencies tab gained a focus strip (shipped 2026-10-19); read when touching the graph charts or control-board-graph work.
metadata:
  type: project
  modified: 2026-10-19T00:56:58.229Z
---

The control panel's Dependencies tab (site symphony-panel.js graphRender/graphStrip/graphSelect, control.css) finishes greg's 2026-10-17 ask ([[control-board-graph-research]]): where a repo has two charts or more, a chip strip (#cp-graph-focus) above them shows one epic's chart at a time, the zoomed-out Goals chart, or All. Each chart is wrapped in `section.graph__section[data-focus]`; graphSelect toggles each section's `hidden` and the chips' aria-pressed. The choice persists per repository in localStorage key `symphony_panel_graph_focus`, restored on load and Refresh, falling back to the first chart when a saved key names a chart that is gone. One chart shows no strip. The assistant's "show dependencies" jumps to the first chart without changing the saved choice.

**Why chips, not + tiles:** these charts are derived from the repo's epics, not things the user adds, so the console's own filter-chip idiom (Folders tab) fits better than the add-a-card + tile style. The sticky-per-repo behaviour follows the panel's saved-sizes rule.

Shipped: site PR #74 (openspineconsortium.github.io), symphony-app PR #37 (panel-checks AA-AE + mutants g51-g55). Both merged, trees verified. Covered by the panel-checks graph suite (76 checks) and five mutants.
