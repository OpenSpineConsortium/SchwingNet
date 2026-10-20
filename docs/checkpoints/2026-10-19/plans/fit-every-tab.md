# Every tab on one screen: fit, zoom and focus

Source: the thread "Control panel sign-in", 2026-10-19 16:51 UTC, after greg's card answer "Chips" (very long lists as numbered chips coloured by state, or a map of sections, that a pinch or tap opens). Copied here at the handoff of 2026-10-19 so another account can read it. Two things changed after it was written: the survey's files (fit-survey/) were in that session's scratchpad and are not kept, so measure again; and site #93 (all three panels resizable, the site bar hiding like a taskbar) and site #95 (the Dependencies zoom stage) merged after it, so the frame steps below are partly done and the stage it names is the one #95 put in assets/js/symphony-panel.js (stageMake to stageResized).

This is one pull request in the site repository, opened after the Dependencies change has merged. It moves every other tab, the console's frame, its dialogs and /symphony/cost.html onto that change's zoom stage. The stage is a box with overflow hidden and touch-action none; a CSS transform scales its canvas to fit, and pointer events zoom and pan it. Everything was measured at 1280x800, 1440x900, 1920x1080, 1024x1366, 390x844 and 844x390 on the survey's mocked repository, acme/spine-viewer: 31 open tasks, 11 pull requests and 15 runs. The long lists were measured again with 300 tasks and 106 pull requests. The scripts, the numbers (long-results.json and the cbte-, prtl- and snfa- files) and the screenshots are in fit-survey/.

## What holds afterwards

- Nothing scrolls: not the page, not a box, not sideways. Today the page scrolls 1875-2158px on a phone, and 10 of the 14 tabs here have a box that scrolls at 1280x800.
- Each tab opens on all of its content, laid out to the stage's shape and then scaled to fit. On a big screen the scale goes up to 1.5, so type and buttons grow with the screen.
- To zoom: pinch, ctrl/cmd+wheel, trackpad pinch, or the + and - keys and buttons, about the pointer. A drag or a plain wheel pans only while zoomed in. 0, Esc or Fit returns.
- A tap or click focuses an item: the item is blown up, its neighbours peek at the edges, and a swipe or the arrow keys step to the next.

## Shared work, in the first commits

1. **The frame is one screen.**
   - On the console page, the breadcrumb band, the footer and the Symphony strip are hidden; their links go into the console's menu.
   - The console takes 100dvh less the site header; on a phone the header folds into the console's own row too. A phone's stage becomes 362x602 at 390x844 and 714x329 at 844x390. Today only 238px of a tab shows at 390x844, and none of it at 844x390.
   - Desktop rail: its rows share its height (grid-auto-rows minmax(0,1fr)). They go from 23px to 26px at 1280x800 and from 32px to 44px at 1920x1080, instead of leaving 174-332px empty.
   - The side column is clamp(170px,15vw,240px), so "Pull requests" is no longer cut at 1024px.
   - Phone held upright: the side column becomes one 44px row, and the rail an 8x2 grid of 45x44 icons with the counts as badges. Held sideways: 2 columns of icons down the left side.
   - The foot is one row: the message line, then Clear, Refresh and Forget as icons. The who-line goes into the menu.
   - A followed run opens as a drawer over the stage, instead of growing the foot to 84px, or 240px on a phone. The Ask bar is one row with its state in a drawer, and on a phone it is an icon in the foot.
   - The sign-in gate hides the foot, so its card fits 390x844 (588 of 780px). At 844x390 the card has two columns.
2. **The fit stage on every tab.**
   - Each panel becomes a stage canvas in reflow mode: the canvas is sized stage/s, its grids reflow to that size, and the transform scales it by s. That draws exactly what the surveys' CSS-zoom prototypes drew, so their numbers hold.
   - s comes from a scan from 1.5 down in 0.05 steps, then 4 halvings. A bisection fails here, because auto-fill grids change their column count with s (on Share at 390x844, bisection found 0.381 where the scan found 0.541).
   - The fit test: nothing in the canvas overflows or sticks out. The Tasks column grips sit at right:-8px and alone held a trial at 0.16, so they move inside the canvas.
   - The stage refits on resize, on a tab change and when the content changes: at most once per frame, cached, and never while the person is zoomed in.
   - The CSS-zoom text size (A- 100% A+, 0.7-1.7) goes, and Fit, - and + drive the stage. That removes the inherited zoom that pushed the Notebooks dialog off the window.
   - A transform captures position:fixed children, so anything fixed inside a tab moves out of the canvas.
   - will-change is set only during a gesture, so the text is redrawn sharp at rest.
3. **Forms by density.**
   - When a list's full form would read below a 10px median at fit, it steps down: full card, then compact card (number and a 2-line title), then chip (number, coloured by state).
   - The stage picks the richest form that keeps 10px and sets it as data-form on the canvas. The surveys judged 9.4px borderline and 10-11px readable.
   - Zooming in past the point where the next richer form would read switches to it. The layout is redone about the item under the pointer, with hysteresis so it does not flicker.
4. **Focus**, one module for every tab.
   - Tap or click any [data-focus] item to show it at about 70% of the stage, with its full content and its controls (gear, X, Merge, Invite, Run) at 44px or more on touch.
   - Swipe left/right (48px threshold) or use the arrow keys to step through its group; up/down steps between groups.
   - Esc, Back, a tap outside or a pinch below the fit returns to the same place.
   - Focus replaces dlg-item, the Tokens side panel and the Notebooks side panel. Forms that edit stay dialogs.
5. **Sizes from the screen.**
   - .console sets --u: clamp(11px, calc(.3vw + .55vh + 4px), 17px), and paddings and heights are in em.
   - Under (pointer:coarse), every frame control and focused control is at least 44px.
   - Grids use repeat(auto-fit, minmax(min(100%,Nem),1fr)). Where the item count is known, JS picks the columns that fill the stage (Agents at 1920: 3x2, not 5+1).
   - Container queries set the density steps, and gear and X are clamp(28px,5vmin,44px).
   - On touch, the whole overview item is the target, and gear and X appear only in focus.
6. **Dialogs** are their own fit stage in the top layer, out of reach of the tab's transform.
   - Below 520px tall, forms go two columns: Add worker drops from 807px to 548px at 844x390, and the token gear from 757px to 552px.
   - What still overflows is scaled, at s 0.68-0.91.

## By tab: what the default view shows

- **Command:** the 7 readouts in one row (4+3 on a phone); the 8 launch buttons fill the rest at 4x2, 3x3 or 2x4, by a container query on the box's aspect. Fit is 1 at every size (buttons 168x68 at 390x844). Today 61-73% of a computer's stage is empty.
- **Board:** each table row becomes a chip of its first cell, coloured by state, with the sections in columns of clamp(260px,30cqw,420px); the 7 charts become thumbnails that open in Dependencies.
  - Fit is 1 at 1440, 1920 and 1024x1366, and 0.69 at 1280x800. On phones (0.31 and 0.19) the chips wrap to the stage's width before scaling.
  - Today's document would need 0.12-0.2. Focus on a chip shows its full row, and on a heading the whole table.
- **Tasks:** the six lists share the width, and the density rule picks the form (see Long lists). Focus shows the full card with what blocks it; up/down moves within a list and left/right between lists. The head's jump chips dim the other lists instead of scrolling.
- **Explore:** the whole project as a nested treemap: goals hold epics, epics hold tasks, plus "Not in an epic"; 45 tiles, about 91px square at 1280x800, 154px at 1920x1080 and 60px (number and state) at 390x844.
  - Zooming a tile past about 70% of the stage goes into its pull request, runs, jobs and steps, so drilling is zooming. A plain wheel now pans when zoomed, instead of drilling.
  - The 224-line log becomes a minimap fitted to the stage's height, beside a 12.8px reading window that follows the pointer. The outline becomes an overlay.
- **Pull requests:** a compact card (branch and time on one row, checks and Merge on the next) is 182px tall instead of 212px. Fit is 0.944 at 1280x800 (1.0 with the new frame) and 1 at the other computer sizes. Focus shows the check list and Merge at 44px.
- **Runs:** one line per run on phones too (15 runs in 617px: s 1 at 390x844, 0.81 at 844x390), and a run's name is never cut.
  - The tab asks for as many runs as fit at s 1 (32 at 1280x800, 72 at 1920x1080; at least 15, at most 100), instead of leaving 238-638px empty.
  - Focus shows the run's jobs and steps.
- **Workers and Agents:** the second space reserved for gear and X goes, so names stop breaking one letter per line (Workers cards at 1440 drop from 400-442px to 198-204px). Columns follow the item count. Phone overview cards fit at 0.85-1. Focus shows the chips, the tokens box, Run, gear and X.
- **Tokens:** the icon goes beside the name, with no minimum height (tiles 187 to 151px, fit 1.0 at 1280x800). The lent-to list becomes one tile.
  - The side panel becomes focus, which ends the drop from 6 to 4 columns.
  - Phone tiles (name, 5h and 7d bars, state) fit at 1.
- **Leaderboard:** the two tables side by side, fitting at 1 at 1280 and 1440 (0.644 and 0.756 today). On phones the rows stay rows with short headers: 3161 to 929px, s 0.83 (12px).
- **Share:** cards fill the stage (minmax(min(100%,440px),1fr), 250px on a phone) instead of one 760px column. Fit is 0.98-1.46 on computers. On phones (0.54 and 0.44), compact cards, with gear, X and Invite in focus.
- **Folders:** the tracked list moves atop the steps column, the columns go 1.5fr/1fr, and the explorer loses its 52vh caps. Fit is 0.78-1.26 on computers (12-18px median). On phones (0.55 and 0.33), focus shows one pane (steps, tree or list) and a swipe moves between them.
- **Notebooks:** no cap on the file list, and the kind chips wrap: fit 0.95-1.39 on computers.
  - On phones the opened notebook takes the stage as its focus (0.747 at 390x844).
  - The gear dialog takes the window, with all 61 files in a grid: 0.77-1.06 on computers. On phones the picker has a focus of its own.
- **About:** newspaper columns of 30em, the stage's height deep. Fit is 0.77-1.2 on computers (11.7-18.2px). On phones (6.4px) focus shows one section, and a swipe moves to the next.
- **Cost page:** three columns: measured, calculator, systems.
  - The whole-page fit (0.46-0.65 on computers, 6.6-9.4px) is a map; a tap reads one column at 0.54-1.0.
  - On a phone a tap shows one section, with inputs kept at 44px.

## Long lists, measured

Each cell is the fit scale with the median text in px in brackets, on the one-screen frame, from long-fit.mjs and long-fit2.mjs. "<0.15" means it does not fit even at the scan's floor.

| List and form | 1280x800 | 1440x900 | 1920x1080 | 1024x1366 | 390x844 | 844x390 |
|---|---|---|---|---|---|---|
| 31 tasks, cards as merged | 0.35 (4.9) | 0.42 (5.8) | 0.53 (7.3) | 0.52 (7.1) | <0.15 | <0.15 |
| 31 tasks, compact | 1.0 (12.4) | 1.17 (14.6) | 1.49 (18.6) | 1.04 (13.0) | 0.33 (4.1) | 0.28 (3.5) |
| 31 tasks, chips | 0.81 (10.9) | 0.94 (12.7) | 1.33 (17.9) | 0.62 (8.4) | 0.58 (7.8) | 0.26 (3.4) |
| 300 tasks, compact | <0.15 | 0.17 (2.1) | 0.23 (2.8) | 0.30 (3.8) | <0.15 | <0.15 |
| 300 tasks, chips | 0.71 (8.9) | 0.83 (10.4) | 1.2 (15.0) | 0.62 (7.8) | 0.34 (4.3) | 0.23 (2.8) |
| 11 PRs, cards as merged | 0.83 (10.8) | 0.97 (12.7) | 1.22 (16.0) | 0.92 (12.1) | 0.34 (4.5) | 0.29 (3.8) |
| 106 PRs, cards as merged | 0.27 (3.5) | 0.31 (4.1) | 0.42 (5.5) | 0.33 (4.3) | <0.15 | <0.15 |
| 106 PRs, chips | 1.5 (18.7) | 1.5 (18.7) | 1.5 (18.7) | 1.43 (17.9) | 0.64 (8.0) | 0.71 (8.9) |

- **Tasks:**
  - On a computer, 31 tasks show as compact cards at 12-19px. 300 show as chips at 8-15px; there the list widths should follow their counts, since the trial gave Queue's 97 the same width as Epics' 8 (long-300-tasks-chips-1280x800.png; not measured).
  - On a phone, 31 show as chips: 0.58 (7.8px) in this trial with the lists stacked, and 0.76 to 1 with 24px headings and 4px gaps in the earlier survey.
  - 300 on a phone are 3-4px even as chips. So each list shows its count and a strip of state dots, and focus goes to a list first: Queue's 97 chips at reading size, then the card.
- **Pull requests:** cards are fine up to about a dozen. Beyond that the PRs show as chips coloured by their checks, with an outline for ready or draft, at 18.7px on computers. On phones the head row, not the count, holds the fit at 0.64, so it folds into the stage title. Runs never grow long, because the number read follows the stage.

## Checks

- Add a fit.test.mjs beside the panel checks in e2e2. It runs every tab at the six sizes, with 31 and with 300 tasks, and asserts:
  - neither the page nor any box scrolls;
  - every item lies inside the stage;
  - each tab reads at a 10px median, shows a denser form, or offers focus;
  - every coarse-pointer control is 44px or more;
  - ctrl+wheel, a two-finger pinch and + change the scale, Fit restores it, a swipe in focus steps to the neighbour, and Esc returns.
- Update the existing checks that scroll an element into view, or open dlg-item or the side panels.

## Risks

- Anything fixed or sticky inside a tab breaks under the transform; the fit test catches what sticks out.
- Refit cost with 300 items is not measured. Up to 27 layouts make one scan, so the next scan starts from the last s and runs on idle.
- The plain wheel changes meaning in Explore, from drill to pan, and focus replaces dlg-item and the side panels. The Dependencies stage may lack a reflow mode; this change adds it there, so there is still one stage.

## The one question for the owner

Some content can be shown whole only at a size nobody can read: 300 tasks on a phone are 2.8-4.3px even as numbered chips, and About and the cost page on a phone are 3-6px. In those cases, may the default view show every item in a condensed form, such as counts, coloured chips or dots, or a map of the sections, which a pinch or a tap opens to full size? The alternative is the full content scaled down regardless. This plan assumes the condensed form.

## Addendum, 2026-10-19 14:35 UTC (the thread, after the survey)

greg asked at 13:54, after the survey started: "i cant resize the message board panel, just the control panel and window which shows the tab, i should be able to resize all 3, when im in the control panel the top nav panel should hide and reappear when the mouse is over it, like windows does with its taskbar". That is being built in its own pull request (site claude/panel-resize-autohide, checks claude/panel-resize-autohide-checks) before this plan starts, and it changes the frame above:
- The foot stays resizable by its grip. A followed run may still open as a drawer, but the person's foot height is kept.
- The site bar hides on the console page at every size and slides back when the pointer reaches the top or the handle is tapped; it is no longer folded into the console's row on phones.
- The text size (A- 100% A+) was greg's own ask of 2026-10-18 (panel sizes and text size kept in the browser); keep a text size control, beside the stage's Fit, - and +, rather than dropping it.

Order: this plan starts only after the Dependencies zoom (site claude/dependencies-zoom) and the resize change have merged, and builds on both. Split it into three pull request pairs, each with its own checks and review: (1) the frame and the shared fit stage with Command, Board and About; (2) the lists: Tasks, Pull requests, Runs, Workers, Agents, Tokens, Leaderboard, Share; (3) Explore, Folders, Notebooks, the dialogs and the cost page.

- 2026-10-19 16:51 UTC: greg chose "Chips" on the card: a list or page too long to read whole shows as numbered chips coloured by state, or a map of sections, that a pinch or tap opens to full size.
