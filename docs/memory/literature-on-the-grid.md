The gate word `literature <list>` fetches a reading list under grid/literature/ onto the grid with Elsevier's key; Elsevier's text never leaves the grid.

- Keys: symphony-template's grid-accounts.yml action key with name elsevier (organization secrets ELSEVIER_API_KEY and ELSEVIER_INSTTOKEN, one line) and s2 (S2_API_KEY) writes ~/.elsevier/token.env and ~/.fluorocap/credentials.env through hpcworker's gate word key; no session ever sees a value.
- Fetch: grid/literature.sbatch runs grid/literature_fetch.py as plan, then fetch, under the size rule, into the landing literature_<list> of the data root, 0700, files 0600; PMC open-access copies, Elsevier's API after its entitlement check, Semantic Scholar's open copies; PMC articles outside the open-access subset are never scripted.
- Reading: a Claude session on the grid under the owner's account reads INDEX.md in the landing; a cloud session reads only the report the word prints (papers and reasons, no text).
- Each send alternates: queue, then print and keep the report; the send after fetches again only what is missing, so an Elsevier paper lands once its access opens (the text-mining amendment of Elsevier's 2026-10-16 e-mail).
- docs/research/literature-on-the-grid.md has the why and the results.
