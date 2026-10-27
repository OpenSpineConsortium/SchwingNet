# The textbook reader: handoff of 2026-10-27, reserved for accounts other than gregoryjschwing@gmail.com

Source: the project thread "View the textbook live in claude.ai", 2026-10-27, from 08:38 to 11:35 UTC. At 11:33 UTC the owner handed all remaining work to other accounts, and this item is reserved for them. Nothing here restarts until the owner says so, and nothing is sent to the grid.

## What the owner asked

- 10:48 UTC: "what i wanted was to natively view the textbook in claude.ai without needing to ever need to republish the front door artefact, and maybe embed it into the osc website".
- 10:55 UTC: "i also want the website link."
- 11:10 UTC: the button's label, "Read the Textbook".
- 11:14 UTC: "make sure all that work wasnt wasted ... improve the experience by using that rreader".

## What is merged

- SchwingNet #427: tools/front_door_loader.html is now the page published at the claude.ai link. Each time it opens, it reads tools/front_door.html from main through the viewer's GitHub connector and runs it, so a change to the door never needs a republish. The research is docs/research/textbook-as-an-artifact.md, section "The loader".
- Site #147: the reader /symphony/door/ on openspineconsortium.com. You sign in with GitHub and read any repository your account can read, live. Its starting points come from SchwingNet's .github/symphony/door.json (#419).
- Site #148 and #149: two buttons on the home page.
  - "Read the Textbook" opens /symphony/door/?door=Textbook. The reader remembers in the browser the repository opened last, so from the second visit on it lands straight on the textbook.
  - "The Textbook in claude.ai" opens https://claude.ai/artifact/XYY2CdsjvyRfxQfYq2EkkV.
- The public site never names SchwingNet. This was the owner's choice, recorded as option 0 on the thread's decision card.

## Open PRs

None from this item.

## The owner's two one-time steps, neither done yet

1. For the website reader, add the callback URL `https://openspineconsortium.com/symphony/door/` to the SymphonyBoard App's settings (https://github.com/organizations/OpenSpineConsortium/settings/apps/symphonyboard), then save. Until this is done, Sign in with GitHub on the reader fails.
2. For claude.ai:
   - In a SchwingNet clone on the owner's computer, run `git pull`.
   - Then run `python3 tools/textbook_publish.py local --url https://claude.ai/artifact/XYY2CdsjvyRfxQfYq2EkkV` and approve the publish.
   - This needs the GitHub custom connector in claude.ai first (the door's four steps).
   - The record on the branch textbook-artifact holds no live link (it is retired), hence the `--url`.
   - This publish is also the first test of whether claude.ai's runtime runs scripts the loader makes at run time. If it does not, publish the door itself again by setting PAGE_SOURCE back to tools/front_door.html.

## Not yet measured

- Whether the reader's code search takes the App's user token.
- Whether SymphonyBoard holds Contents read on SchwingNet.
- The claude.ai connector flow end to end.
