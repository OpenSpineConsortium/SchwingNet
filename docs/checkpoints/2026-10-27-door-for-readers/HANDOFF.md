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

## Finished, 2026-10-27, thread "Finish the one-click reader page"

The owner started this thread at 08:38 UTC to carry out steps 1 to 5 of the list this page held. The work went into the site pull request, https://github.com/OpenSpineConsortium/openspineconsortium.github.io/pull/147.

- Step 1. tests/test_door_browser.py is in the site repository. It holds 25 Playwright tests against a stand-in for api.github.com and skips where Playwright is absent, as on the site's CI. Python Playwright is not preinstalled in a cloud session: `pip install playwright==1.63.0`, matching the node copy, then `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`.
- Step 2. The review ran with three readers (security, parity, site) and a critic, and every defect was checked by two skeptics. Seven held and were fixed, each with a test that fails on the old code:
  - a deep link lost its hash across the first sign-in;
  - a slow read landed over a later open;
  - a remembered repository opened without ?repo=;
  - a mistyped ?repo= was dropped silently;
  - WebRTC leaves a sealed frame, which no CSP governs in Chromium; the frame's first script now takes its constructors away, which narrows the channel without closing it;
  - the "no repository" note faded;
  - a large Markdown file froze the page.
  Most notes were taken up as well: frame-src now sits in the built head, DNS hints are taken out of sealed pages, and search is held to the repository. #147's "## Adversarial review" section lists each finding and the residuals.
- Step 3 is still open. Whether code search takes the App's user token, whether SymphonyBoard holds Contents read here, and the App's callback list are answered only by the first real sign-in.
- Step 4. door.js answers schwingnet.open, schwingnet.read and schwingnet.dispatch. The names were kept, since the exported pages send them, and the site's master already names the repository in symphony-panel.js (grid words, the W&B project, the RAG repository). This is put to the owner as a residual.
- Step 5. The owner's three steps follow the merge of #147: the callback URL on the SymphonyBoard App, Read for each reader, and the link https://openspineconsortium.com/symphony/door/?repo=OpenSpineConsortium/SchwingNet.

## Not measured

What step 3 above leaves open; the page against the real GitHub API, measured only against the stand-ins of tests/test_door_browser.py; the sign-in Worker accepting the new page, which it does for any page on the origin by its own reading, not by a run.
