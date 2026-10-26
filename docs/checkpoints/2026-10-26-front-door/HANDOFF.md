# Handoff: the front door at the textbook link (2026-10-26)

Written 2026-10-26 about 03:05 UTC from the project thread "Stage the textbook for this project", at the owner's checkpoint of 03:01 UTC ("please push as much as possible now im running out of tokens then write a handoff for checkpointing asap!"). The work is on the branch claude/project-thread-24opi2, which is no claim: the owner's asks of 2026-10-26 in the project thread. Nothing of this work touches the grid, a fetch or a training, and nothing of it is public.

## Goal

The owner's words of 2026-10-26: at 00:13 UTC, "OK CAN YOU MAKE IT SO I NEVER HAVE TO DO THIS AGAIN AND THIS LINK STAYS UPDATED?", and at 00:18 UTC, "NO THIS ISNT WHAT I WANT I WANT IT TO DYNAMICALLY LOAD NEW FILES/ARTEFACTS LIKE ITS A FRONT DOOR INTO A REPO!"; at 00:37 UTC the owner chose "Live door via GitHub connector" on the thread's decision card. The link is https://claude.ai/artifact/XYY2CdsjvyRfxQfYq2EkkV. Done is: the door published at that link from the owner's computer, reading main and the board live through the owner's GitHub connector, with nothing staged or republished when the repository moves.

## Done

- #405 (merged 2026-10-26 02:04 UTC): tools/front_door.html, the door; tests/door_stand_in.py and tests/test_front_door_browser.py (11 tests in Chromium through Playwright, skipped where Playwright is absent); tools/textbook_publish.py publishing the door with `--url` adopting the link; the research in docs/research/textbook-as-an-artifact.md, section "The front door, 2026-10-26"; the memory docs/memory/the-textbook-artifact.md; the sentence in docs/project.md. An independent security review found seven things, all fixed with tests.
- #408 (merged 02:51 UTC): the publish prompt names the textbook reader at the link as the page the door replaces and needs no confirmation; a page that is neither is a TARGET_MISMATCH the command reads back and refuses to record. The owner's first run (02:35 UTC) had stopped there, since the prompt had not said what the link holds.
- #409 (ready, auto-merge armed at 03:00 UTC, CI running at this writing): the prompt clears the artifact's declaration first (a publish with capabilities {}) before the door's publish, since the Artifact tool refuses a declaration that drops a stored capability (the reader's files) silently, which is what stopped the owner's second run (02:54 UTC). The door reads nothing of the project's files, so files is dropped on purpose. 36 tests in tests/test_textbook_publish.py.
- Measured by the owner's two runs: Claude Code on the owner's computer carries the Artifact tool, reads the door whole, reads the artifact at the link, and holds to the prompt's steps; the Artifact tool's refusal when a declaration drops a stored capability, and the three ways out it names (the research note's paragraphs "The owner's first run" and "The owner's second run").

## Open

Not yet measured, each settled by the owner's next run: the publish with the GitHub connector declared from the owner's computer (a cloud thread's checks refuse it, so no thread tries it); the custom connector end to end; the shapes claude.ai's runtime hands the page for the three tools, which the page reads in every shape it knows; the runtime's limit on a tool result (the page cuts text at 1.5 MB and links a larger file on GitHub); what a viewer who is not the owner sees (by design, the connector's refusal and nothing of the repository).

## The owner's remaining steps, in order

Steps 1 to 3 were sent to the owner at 02:06 UTC and are not reported done; step 4 was run twice and stopped twice for reasons #408 and #409 fix.

1. Make a GitHub App: https://github.com/organizations/OpenSpineConsortium/settings/apps/new. Name `SchwingNet door`; Homepage URL `https://github.com/OpenSpineConsortium/SchwingNet`; Callback URL `https://claude.ai/api/mcp/auth_callback`; under Webhook untick Active; under Repository permissions set Contents to Read-only; under "Where can this GitHub App be installed?" pick Only on this account; click Create GitHub App.
2. On the page that opens, copy the Client ID, then click Generate a new client secret and copy the secret (shown once). In the left menu click Install App, then Install next to OpenSpineConsortium, pick Only select repositories, choose SchwingNet, click Install.
3. Add the connector: https://claude.ai/settings/connectors, click Add custom connector. Name exactly `GitHub`; Remote MCP server URL `https://api.githubcopilot.com/mcp/`; open Advanced settings and paste the Client ID and the client secret; click Add, then Connect, and authorize on GitHub.
4. Once #409 is on main, in Claude Code inside the SchwingNet clone on the owner's computer: `git pull`, then `python -X utf8 tools/textbook_publish.py local --url https://claude.ai/artifact/XYY2CdsjvyRfxQfYq2EkkV`. The session reads the door, reads the link, publishes once with capabilities {} (clearing the reader's declaration) and once with the door's; approve each publish when the Artifact tool asks; `/exit` lets the command record the link on the branch textbook-artifact.
5. Open the link and allow the page to use GitHub when asked. If the door shows a note instead of the repository, its words say what to do (the connector's name, a reconnect, the permissions menu); send them to a thread.

## Restart

A new thread reads this page, the research note's front door section, and tools/textbook_publish.py's docstring. If the owner reports the publish succeeded, the thread confirms the record on the branch textbook-artifact (`git fetch origin +refs/heads/textbook-artifact:refs/remotes/origin/textbook-artifact && git show origin/textbook-artifact:state.json`) and asks the owner whether the door opened the repository; what the first open shows settles the Open list above and goes into the research note. If the owner reports another stop, the session's words name the cause; the fix is a change to the prompt in tools/textbook_publish.py by pull request, as #408 and #409 were, never a publish from a thread. Never retry a publish that declares a connector from a cloud thread: its checks refuse it.
