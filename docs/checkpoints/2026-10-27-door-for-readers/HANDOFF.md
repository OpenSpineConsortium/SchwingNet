# Handoff: the live door for other readers (2026-10-27)

Written 2026-10-27 about 04:55 UTC from the project thread "Stage the textbook for this project", at the owner's checkpoint of 04:47 UTC ("YO PLEASE CHECKPOINT ALL SESSIONS AND PUSH ALL FILES AND WRITE A HANDOFF SO A NEW ACCOUNT CAN PICK UP WHERE THESE LEFT OFF!"). The work is on the branch claude/project-thread-24opi2 in two repositories, which is no claim: the owner's asks in the project thread. Nothing of it touches the grid, a fetch or a training. The research behind it is docs/research/reader-access.md; this page only says where things stand.

## Goal

The owner's words of 2026-10-27 at 04:19 UTC: "all i want is to be able to let other people see this live front door like I can, after only running this publish command once ... i was just asking if github would be a good place to put it given that i am on a subscription individual claude plan i dont think i can have other people in my organization?" Earlier the same night: at 03:12 UTC readers who ask through GitHub and view in the browser only, and at 04:12 UTC sharing the door with chosen email addresses. The 04:19 message replaced both, and replaced the "Reader edition shared by email" the owner had tapped on the thread's decision card at 04:17 UTC.

Done is: a link the owner sends to a reader, which opens the live door into this repository for that reader with no step of the owner's beyond a one-time setting.

## What was settled

- The claude.ai door (tools/front_door.html at https://claude.ai/artifact/XYY2CdsjvyRfxQfYq2EkkV) can serve only the owner. claude.ai's runtime gives connectors only to the owner and members of the claude.ai organization that holds the artifact. Anyone invited by email or arriving by a public link gets none, and on an individual plan there are no other members. Putting the GitHub App in a connector store changes nothing, since the refusal is the runtime's, not GitHub's. The door stays the owner's own and the owner's open steps for it (docs/checkpoints/2026-10-26-front-door/HANDOFF.md) still hold.
- GitHub is the place for the shared door, as a page on the organization's public site (OpenSpineConsortium/openspineconsortium.github.io, served at https://openspineconsortium.com). The reader signs in with GitHub through the control panel's existing sign-in (the SymphonyBoard App's user token through the stateless sign-in Worker) and reads the repository live with their own GitHub access. The page and its script hold nothing of SchwingNet. The repository comes from the address (?repo=OWNER/NAME), and a reader the owner has not given access sees nothing.
- What it costs, as reader-access.md says: each reader needs Read on SchwingNet (the control panel's Share tab, or GitHub's Add people). That is a seat where the organization's plan charges for one, and it lets the reader clone everything. There is no Ask, since the Claude side lived in claude.ai's runtime. The note's recommendation stands: approving an outside reader before the provisional is filed is the owner's call, and whether one needs a confidentiality agreement is a question for the technology transfer office.

## Done

- SchwingNet #415 (merged 2026-10-27 03:52 UTC): docs/research/reader-access.md, the memory paragraph "Who the door serves" in docs/memory/the-textbook-artifact.md.
- Site draft pull request https://github.com/OpenSpineConsortium/openspineconsortium.github.io/pull/147, commit 804c22d. It holds:
  - assets/js/door.js (1,131 lines): the door's transport-free code adapted to the site, defining window.SymphonyDoor.start(api) and doing nothing at load;
  - assets/css/door.css;
  - tools/pages/symphony/door/index/body.html and the built symphony/door/index.html (robots noindex);
  - a hidden SITE node in tools/build_site.py;
  - initDoor() in assets/js/symphony-panel.js, which hands door.js a GET-only client held to the chosen repository and to code search, so door.js never holds the token;
  - the whole site restamped, as every build does.
  `build_site.py --check-only` passes with 0 problems and both scripts parse. It was written by an implementer agent whose workflow was stopped at the checkpoint, so nobody has reviewed it yet.
- This pull request: .github/symphony/door.json, this repository's starting points for the site reader (the same eight as the claude.ai door's DOORS), this page, and a line in reader-access.md.

## Open, in order

1. Write tests/test_door_browser.py in the site repository. It uses Playwright and skips where Playwright is absent, since the site's CI has none. Run it with `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 -m unittest discover -s tests -t .` in the site clone. Setup:
   - serve the site folder over http.server;
   - put a token in sessionStorage under symphony_panel_token through add_init_script;
   - stand in for api.github.com with context.route, using small fixture repositories: a README with a relative link, a picture, an SVG, a nested folder, a document with headings, an exported page under artifacts/x/index.html whose script tries fetch('https://example.com/') and an outside image and posts schwingnet.read, a board branch and a door.json;
   - also stand in for GET /user and the repository list the panel calls on enter.

   Assert:
   - the README renders and a relative link opens;
   - a picture shows as blob: and an SVG as data:;
   - Changes and Find render, and the board reads ref=board;
   - a missing path and an unreadable repository say so, and ?repo= picks the repository;
   - a sealed page has sandbox exactly allow-scripts and its head starts with the CSP meta;
   - no request from a sealed page reaches example.com, and schwingnet.read is answered at its ref and refused at another;
   - "..", "%2e%2e", "%2F" and empty segments in the hash and in a document link send no request outside /repos/O/R/contents/;
   - no console errors, and no horizontal scroll at 400 px.
2. Review it adversarially, by three independent readers given the code and not a conclusion:
   - Security. The reader's token sits in sessionStorage or localStorage on the same origin as the control panel, whose token can hold Administration and other writes. Check:
     - any way repository content (Markdown, file names, door.json, exported pages and their messages, search results, commit messages, the hash) runs script on that origin;
     - any way it reads or sends the token;
     - any authenticated request outside the intended GET endpoints (traversal, encoded slashes, ref or query injection);
     - any way a sealed page sends content to another host (the meta's position, nested frames, about:blank, blob: workers, prefetch, form, navigation, window.open, CSS url(), fonts).
   - Parity. Compare door.js with tools/front_door.html function by function beyond the asked removals (Ask, permissions, connector steps). Check the REST usage against GitHub's documented behaviour (contents API shapes, the raw media type, the 1,000-entry folder limit, commits, code search's text-match type and its rate limit) and the error mapping (401, 403, 404, 429, SSO). Also check initDoor's wiring (enter, finishOauth, watchOtherTabs, signOut, the dispatch order before cp-app).
   - Site. Check the two-click reach, that /docs/ and /docs/buttons.html stay generic, phone width, and both themes.
   Fix what holds up, run `python3 -X utf8 tools/build_site.py` and `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers bash scripts/check.sh`, and write the "## Adversarial review" section into #147's body. Then mark #147 ready in a call of its own and merge once green, on the owner's standing permission (the org ruleset asks for no approval of a pull request under the owner's login).
3. Settle what this sandbox could not:
   - whether GitHub's code search accepts the App's user token;
   - whether the SymphonyBoard App holds Contents read on SchwingNet, since a user-to-server token reads only what both the person and the App's installation reach;
   - which callback URLs the App already has (GitHub keeps at most 10 and matches them exactly).
   The first reader's sign-in answers all three.
4. Look again at the message names: the exported pages speak schwingnet.open, schwingnet.read and schwingnet.dispatch, so door.js carries those strings on the public site. The control panel's script already names the repository in a comment, but say so to the owner and offer neutral aliases if the name itself should stay off the site until the filing.
5. Once #147 is merged, give the owner these steps, numbered, with exact links:
   1. Add the callback URL https://openspineconsortium.com/symphony/door/ in the SymphonyBoard App's settings (https://github.com/organizations/OpenSpineConsortium/settings/apps/symphonyboard, Callback URL, Add Callback URL, Save changes).
   2. Give each reader Read on SchwingNet (the control panel's Share tab, or https://github.com/OpenSpineConsortium/SchwingNet/settings/access, Add people, Read).
   3. Send the reader https://openspineconsortium.com/symphony/door/?repo=OpenSpineConsortium/SchwingNet.

## Not measured

Every item under Open, step 3; the page against the real GitHub API, measured only against stand-ins and only once step 1 exists; the sign-in Worker accepting the new page, which it does for any page on the origin by its own reading, not by a run.
