# The control panel as a console

The notes of the thread "Control panel redesign as a console" of the claude.ai Project "symphony2",
2026-10-18. The owner's ask, in his words: "the entire layout for the tokens page, and the control
board is not CONTROL PANEL DESIGNED! IT SHOULD ALL FIT ON ONE PAGE WITHOUT SCROLLING, MAYBE USE
INPAGE TABS? THINK LIKE A CONTROL BOARD WHERE A GENERAL WOULD INITIATE WAR MANUEVERS, LIKE NATURAL
INTUITIVE BUTTONS". The earlier notes on the panel, its sign-in and its sections are
control-panel.md beside this file; this one covers only the layout.

## What changed

Before: https://openspineconsortium.com/symphony/control/ was one long article, nine sections and
about four screens of explanation, read by scrolling, with the actions as small pill buttons inside
the prose; the Claude accounts were a second page, /symphony/control/tokens.html, with its own
sign-in box and its own repository picker.

After: the panel is one console that fills the window under the site's header and the Symphony
strip and never makes the page scroll at a laptop's size:

- A command bar: the repository picker, the four links to GitHub, who is signed in, Refresh and
  Forget the token (folded into the side column and a status line at the foot in the second pass,
  below).
- A rail of ten tabs on the left: Command, Board, Tasks, Pull requests, Runs, Workers, Ask Claude,
  Tokens, Repositories, About. Tasks, Pull requests and Workers carry their counts.
- Command, the tab it opens on: seven readouts (Queue, Given to workers, At work, In review,
  Blocked, Pull requests, Workers), each a button that opens its list, then eight large launch
  buttons: Run the workers now (green, the one that sets work going), Rewrite the board, Run the
  checks, Run the metrics now, Queue a task, Ask Claude, Claude accounts, Add a repository.
- Every other tab holds one subject, its list on the left and its form on the right where it has
  one (Queue a task beside the task lists, Add a worker beside the registry, Add a Claude account
  beside the slots). A list longer than the tab scrolls inside the tab, never the page.
- The long explanations are folded behind a "?" in each tab's head and open over the tab, so they
  move nothing; the privacy text is the About tab, word for word.
- The Tokens page is the Tokens tab. tokens.html stays at its address for the links and bookmarks
  that name it and sends the visitor on to /symphony/control/#tokens with its query. One sign-in
  and one repository picker now serve both.
- Each tab has an address (#command, #board, #tasks, #pulls, #runs, #workers, #ask, #tokens,
  #repos, #about), so a link or a reload opens it again; nothing about the tab is stored.
- The deck is dark inside the cream site, so it reads as an instrument, not an article.

## Nearly fullscreen (the second pass, same day)

greg, after the first version, in his words: "the layout on how this looks with 3 different
navigation panels is way to cluttered, you can barely see the control panel, which should be
nearly fullscreen with the exvception of the topmsot panel"; then "why is the control panel so
squished vertically? it should stretch down to take up the height of the page"; then "i cant read
the full fucking repo name, and i think this panel can be more condensed, and if it has to stay
for messages, make sure it is frozen, meaning its always visible". He also said that pressing
Add a Claude account moved the window and printed partly off screen.

The three bars he counted were the site's header, the Symphony strip and the console's own command
bar; a growing message line above the deck was a fourth thing that pushed the deck down. The Website
docs and navigation thread made the strip a drop-down that opens over the page on hover (site #41).
This pass (site #48) made these changes:

- The command bar is gone. The repository and the four GitHub links sit at the top of the rail's
  column. The repository's whole name shows wrapped, owner on its own line, with the select laid
  invisibly over it so a press opens the browser's own list.
- The page's message is a status line at the console's foot. It is always there, with a faint
  placeholder outside the live region when it is empty. It never sits above the tabs and never
  covers a control. A long message, such as Add a Claude account's sign-in step with its button
  and code box on one line, scrolls inside it. Clear empties the line, except while a step waits
  on a box the person has to fill.
- Who is signed in, Refresh and Forget the token sit at the right end of that line.
- The console now runs from the 64 px header to the window's bottom edge, measured at 1000 x 700,
  1366 x 657, 1536 x 730 and 1920 x 969, with the window at 0. The whole rail, eleven tabs with
  Share, fits at 1366 x 657.
- Below 900 px the status line is sticky at the bottom. The console's measured height no longer
  wins over the phone layout's auto height; before this, a tab's form drew over its list on a phone.

The review before the pull request found these problems, each fixed: the shown name went stale
after the last repository was removed or after another account signed in (it is drawn wherever the
select is filled); Clear wiped the sign-in step mid-flow; the inline rule missed the step's
paragraphs; the placeholder sat inside the live region; the page scrolled a few pixels at 520 to
523 px tall; and two messages still said "the bar above".

Merging master along the way found that the Tokens tiles (site #44) declared a second `var MODELS`
in the script's one function. The tiles' list overwrote the cost page's price table, so
/symphony/cost.html threw. Site #46 renamed the tiles' list TILE_MODELS, ahead of this change.

## Graphical sections and the frame's last pieces (the third pass, same day)

greg asked, in a message the coordinator split among the threads, for several things. This thread
took four of them: a message that flashes when it arrives, a full screen mode without the site's
header, a place for a frozen Ask Claude bar, and Tasks, Pull requests, Runs and Workers drawn as
pictures rather than text, with a worker added without a form.

- Site #51. When a message arrives or changes, the status line flashes white; when it empties, it
  does not. A Full screen button beside the title uses the browser's fullscreen and hides the site's
  header. If the browser itself is full screen (F11), the button says how to leave. An empty
  `#cp-askbar` sits above the status line for the Ask Claude bar thread to fill. It is hidden while
  it is empty or while nobody is signed in.
- Site #56. Tasks is a board of six columns, one per list, each with its own scroll. The list
  buttons slide the board sideways to their column. Every task is a card with its number, title,
  label chips and actions. Pull requests are cards with a Ready or Draft pill. Runs are cards
  with a large mark for passed, failed or running. Workers are cards with an emblem for where each
  runs and chips for its settings. A worker is added by pressing tiles. The two selects stay hidden
  behind the tiles and remain what the add reads; a tile sets its select through a change event,
  so every listener hears it.
- The cards are CSS over the same tables. Each cell carries a `cell--<part>` class, so the data,
  ids, handlers and the browser checks' selectors are unchanged.
- Pull request cards carry `data-number` so the Ask Claude bar's "merge #N" finds the Merge
  button. They also carry `data-pull`, so the task filter does not read them as tasks.
- The review caught one problem, now fixed: a card's grid display overrode the filter's hidden
  rows.
- Site #59. The Agents tab (site #55) is drawn as cards too, with the purpose as a pill. The
  leaderboard (site #53) gives its first three places gold, silver and bronze. The rail now has
  fourteen tabs, so in a window up to 820 px tall its rows close up and all of them fit at
  1366x657; in shorter windows the rail scrolls.

## Design decisions

- One page with in-page tabs, not several pages: one sign-in, one repository, and switching costs
  no request. Each tab's reads still happen once per repository, as before; the Tokens tab reads the
  branch pool only when it is opened, so a person who never opens it sends none of its reads.
- The height is measured, not guessed: the script sets the deck's height to the window's height
  below the header and strip on load, on resize and once the fonts have loaded, since the strip's
  height depends on them. Below 900 px wide or 520 px high the deck gives up: the page scrolls as
  before, the rail becomes a row, and each tab is shown whole.
- Every element id the script and the browser checks use is kept, so no behaviour moved. Where the
  page points at something in another tab (the assistant's focus on a task row, its filter, a board
  section, "Ask Claude on it" from a row), it opens that tab first and then scrolls as before.
- The tab's address (#tokens) matches no element's id, the rail buttons being rail-NAME, since a
  browser scrolls the window to an element the address names and would carry the bar and the strip
  out of sight; a scroll margin on the button did not stop it (the review below). An address that
  names no tab, such as the skip link's #main, leaves the tab as it is.
- Where the page scrolls to a row or a heading, it scrolls the tab's own box and puts the window
  back, since scrollIntoView moves every box around the node, the window too.
- A new sign-in reads the Tokens tab afresh, so another account never sees the last one's slots.
- Between 901 and 1279 pixels wide the bar takes a second row for its links rather than cut them,
  and the rail and the side forms narrow.
- The rail's buttons are ARIA tabs (aria-selected, arrow keys move between them), the panels
  tabpanels, so a screen reader and a browsing Claude read the same structure.

## Measured

Playwright with Chromium against a mocked api.github.com (the panel checks' fixtures in
OpenSpineConsortium/symphony-app, signin/panel-checks/e2e2, widened to 24 tasks): at 1366 x 657,
a 1366 x 768 laptop's window under the browser's own bars, and at 1920 x 969, every tab's console
ends at the window's bottom edge (656.7 of 657 and 968.7 of 969 pixels) with the window unscrolled;
the readouts, the eight launch buttons and the whole rail fit at both sizes. The site's footer is
still below the deck, reachable by scrolling, as the site's build requires.

## For the threads that add sections

A new section is one rail button and one panel in tools/pages/symphony/control/index/body.html of
the site: `<button type="button" role="tab" data-tab="NAME" id="rail-NAME" aria-controls="tab-NAME">` in
the rail, and `<section class="console__panel" id="tab-NAME" data-tab-panel="NAME" role="tabpanel"
aria-labelledby="rail-NAME" hidden>` in the stage, with a `console__head` and a `console__scroll` inside;
`console__panel--split` gives a list on the left and a form on the right. The Dependencies section
and the Folders page are expected to arrive this way.

The panel's browser checks press a tab's rail button before they read or press anything inside it,
since a hidden tab's contents are not visible to Playwright: symphony-app's
signin/panel-checks/e2e2/console-tabs.mjs wraps the page's actions and its locators so that each
opens the tab holding its selector first, and each suite installs it once after launching the
browser.

## Review

An adversarial review of the first version, run in the thread before the pull request, found the
window scrolled 107 pixels on every signed-in load, since the tab's address named a rail button;
scrollIntoView from "Ask Claude on it" and the assistant moving the window; the Tokens tab keeping
the last sign-in's readings after a new one; any other address sending the person to Command; the
bar cutting its links between 901 and about 1250 pixels; Home and End doing nothing on the rail;
and words that still said "below" or "Tokens page". Each is fixed as the decisions above say, and
the four addresses (/symphony/control/, ?repo=, #board, tokens.html?repo=) now load with the window
at 0 at 1366 x 657 and 1000 x 700. Two edges stay: a sign-in begun on the old tokens.html before
this change and finished after it is refused once and asks to try again, and a return from Sign in
with GitHub opens Command, since GitHub's callback carries no address fragment.
