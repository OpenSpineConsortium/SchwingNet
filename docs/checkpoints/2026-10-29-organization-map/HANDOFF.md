# Handoff: the organization map, the epics and the Organization tab

Source: the thread "Map org repos, epics and dependencies" in the claude.ai project symphony_2, 2026-10-29, closed early on the owner's word of 23:05 UTC ("im about to run out of fable please just write what you have now"). The research is docs/research/organization-map.md; this page only says where things stand.

## Done and pushed

- On GitHub itself: two goals (SchwingNet#391, spine-program#121), 12 epics, 136 sub-issue links and 70 blocked-by links across SchwingNet, spine-program and spine-datasets, as the research note's sections 2 and 3 record; nothing closed, renamed or re-parented; no label that starts a Claude run.
- SchwingNet pull request #488 (draft, CI green, main merged in): .github/symphony/organization.json, tools/organization_map.py with tests/test_organization_map.py and its line in scripts/check.sh, two memories and the research note.
- openspineconsortium.github.io pull request #150 (draft, CI green): the control panel's Organization tab (tools/pages/symphony/control/index/body.html, assets/js/symphony-panel.js, assets/css/control.css and the rebuilt pages).
- symphony-app pull request #92 (draft, CI green): signin/panel-checks/e2e2/org.test.mjs, 14 browser checks of the tab, all passing against the site branch; the Dependencies tab's 170 pass against the changed script too.

## Done since, in the thread "Finish the organization map" (symphony_5, 2026-10-30)

- The independent review's 18 findings on the tab are fixed in #150's second commit, each with the check that holds it, and #92 carries six checks more (20 in all, with the Dependencies suite's 170 passing against the changed script); #150's body lists finding by finding what was done.

## Left open
- #310 (the 70 obtain tasks) keeps todo and no epic; the owner's choice between splitting it by kind of set, raising the Dependencies tab's read cap, or leaving it stands as a decision card in the thread.
- The owner's reading of the map's groups and roles, and the three pull requests' merges.
- docs/memory/MEMORY.md is over its 25 KB limit (#271); #488 adds two lines.
