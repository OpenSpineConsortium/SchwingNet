# The control panel's + style, saved layout, repository picker and Share

The thread "Control panel redesign" of the claude.ai Project "symphony2" wrote these notes on 2026-10-18. The owner sent a list of changes to https://openspineconsortium.com/symphony/control/ that day, in his own words:
- "remove this side panel, integrate it into a +Add Task button like the Add token"
- "dynamic resizing of the windows ... SAVE MY PREFERENCES, INCLUDING TEXT SIZES, AND HOW I LIKE THE PANELS SIZES"
- remove the Ask Claude tab, since the bar at the foot does the asking
- the Runs tab's buttons are too large
- "ALL NEW THINGS A USER CREATES TO FOLLOW THE + STYLE"
- "I DONT WANT ANY FUCKING FORMS ON THE CONTROL PANEL"
- "ALL BUTTONS TO HAVE THOSE GEARS, X FOR DELETE, AND CLICKABLE FOR STATUS/SETTINGS"
- import agents by the + style
- the Share tab made "more refined and professional"
- the repository chosen better than by typing OWNER/NAME
- the site's footer should not be scrolled to under the panel

control-panel-console.md beside this file covers the console's layout as it was before this list.

## What changed, in three site pull requests

1. openspineconsortium.github.io#60, layout:
   - The Command tab's summary paragraph is hidden. It is kept for screen readers and the assistant, and a warning in it still shows.
   - The boundaries can be dragged: the side column, the Tasks board's column width, the token side panel and the Ask Claude answer drawer. A double click resets one, and the arrow keys move a focused one.
   - A-, 100% and A+ in the status line scale the console's text, buttons and boxes together with CSS zoom.
   - Sizes and zoom are kept in this browser's localStorage under symphony_panel_layout.
   - The site's footer and breadcrumbs are hidden on desktop for the console page.
   - The Runs tab's rows and the launch buttons are compact.
2. openspineconsortium.github.io#61, the + style:
   - No form sits on a tab. + Add task, + Add worker and + Import agent each open a dialog.
   - Every card opens its status on a press or on Enter. Its gear opens its settings and its X removes it:
     - an issue: give it to a worker or ask @claude on it; the X closes it as not planned
     - a worker: change its file by pull request; the X opens the pull request that deletes it
     - an agent: run it and set its tokens; the X opens a pull request that removes it
     - a pull request: the X closes it
   - The Ask Claude tab is gone. The task dialog asks @claude at once or queues the same words for the workers.
3. openspineconsortium.github.io#62 has two parts.
   - Repositories:
     - The side column's + Add repository lists every repository SymphonyBoard is installed on, grouped by account. It reads GET /user/installations and /user/installations/{id}/repositories, and with a pasted token /user/repos instead.
     - The person's own list comes first, a search narrows it, and a whole OWNER/NAME is read by name.
     - The Repositories tab is gone.
   - Share:
     - Share lists the people with access and the invitations waiting, one line each with the role.
     - A gear changes the role, and an X takes the access away or withdraws the invitation.
     - + Add people holds the invitation and the mail buttons.

## Decisions

- A dialog, not a side panel. A modal dialog (showModal) leaves the tab under it as it was, and Enter in its one-line boxes presses its own primary button. A form's implicit submission would otherwise press Cancel.
- Changing or removing a worker or an agent is a pull request on a branch symphony/... The required check reads the file again, and nothing changes until a person merges it. A branch that exists already is built on, never moved, so nothing a reviewer pushed there is lost.
- The panel draws no avatars. Loading avatars.githubusercontent.com would send a request to a second host, which the Apps' privacy statement does not list.
- An older assistant prompt in a repository's copy may still name the tabs "ask" or "repos". The panel maps them to + Add task and the repository picker.
- The layout is a per-browser convenience, so localStorage is right for it. It holds sizes and the zoom, and nothing about a person or a repository.

## Checks

symphony-app's signin/panel-checks/e2e2 browser checks follow the dialogs (symphony-app#28, and #29 for the third pull request, openspineconsortium.github.io#62). console-tabs.mjs presses the button that opens the dialog a selector is in. Each pull request had an adversarial review before it opened, and its findings were fixed in the same pull request.

## Where it stands

All three site pull requests merged on 2026-10-18, each rebuilt on master after the one before it, with their checks (symphony-app#28, #29 and #30). The Apps' privacy statement listed each change first: version 20 (symphony-start#58) the layout key, version 22 (symphony-start#59) the cards' writes, the repository picker and the Share tab's reads and writes.

The Folders tab, which landed on master meanwhile, needs no repository, so the picker opens by itself where nothing is listed except over that tab.
