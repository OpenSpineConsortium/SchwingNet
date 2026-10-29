# Handoff: the organization map, the epics and the Organization tab

Source: the thread "Map org repos, epics and dependencies" in the claude.ai project symphony_2, 2026-10-29, closed early on the owner's word of 23:05 UTC ("im about to run out of fable please just write what you have now"). The research is docs/research/organization-map.md; this page only says where things stand.

## Done and pushed

- On GitHub itself: two goals (SchwingNet#391, spine-program#121), 12 epics, 136 sub-issue links and 70 blocked-by links across SchwingNet, spine-program and spine-datasets, as the research note's sections 2 and 3 record; nothing closed, renamed or re-parented; no label that starts a Claude run.
- SchwingNet pull request #488 (draft, CI green, main merged in): .github/symphony/organization.json, tools/organization_map.py with tests/test_organization_map.py and its line in scripts/check.sh, two memories and the research note.
- openspineconsortium.github.io pull request #150 (draft, CI green): the control panel's Organization tab (tools/pages/symphony/control/index/body.html, assets/js/symphony-panel.js, assets/css/control.css and the rebuilt pages).
- symphony-app pull request #92 (draft, CI green): signin/panel-checks/e2e2/org.test.mjs, 14 browser checks of the tab, all passing against the site branch; the Dependencies tab's 170 pass against the changed script too.

## Left open

- The independent review of the tab (four lenses, two skeptics a finding) was stopped before every verdict was in, to spend nothing more; what it had found is in #150's body under Adversarial review. The one defect verified in a live run: the tab's open handler restarts a load in flight when the tab is left and opened again before the listing and the map have answered (initOrganizationTab, consoleOnOpen.organization in symphony-panel.js), so the listing and the map are read twice; the fix is to keep the in-flight load on the tab's state and reuse it while the repository is the same. A second, unverified: a map name that folds to nothing (graphFold strips non-ASCII) hands Mermaid an empty label; orgLabel should return a placeholder.
- #310 (the 70 obtain tasks) keeps todo and no epic; the owner's choice between splitting it by kind of set, raising the Dependencies tab's read cap, or leaving it stands as a decision card in the thread.
- The owner's reading of the map's groups and roles, and the three pull requests' merges.
- docs/memory/MEMORY.md is over its 25 KB limit (#271); #488 adds two lines.
