---
name: cloud-environment
description: A project's threads need a cloud environment with Full network access to fetch open papers; greg added one to symphony_4 on 2026-10-28 03:14 UTC and a new project needs its own; what stays refused even then
metadata:
  type: reference
---

Until 2026-10-28 the project had no cloud environment selected, so threads ran on the built-in one, whose proxy refused (CONNECT 403) pmc.ncbi.nlm.nih.gov, europepmc.org, ebi.ac.uk, Crossref, api.semanticscholar.org, publishers (amegroups, actaorthop, ojshostng, caims.in, journalijar, doi.org) and Actions artifact blob storage. greg chose on a card to "Open the network" (03:13 UTC) and added a cloud environment with Full network access in Project settings ("done", 03:14 UTC). Only threads started after that ran on it. A new project starts on the built-in environment again: in its settings, Environment, the Cloud environment menu, add or edit one (the gear beside it) with Network access Full (https://code.claude.com/docs/en/cloud-environments#network-access).

Still true with open network: PMC's article pages show a script a reCAPTCHA, and PMC's copyright notice forbids automated downloads except through OAI-PMH, FTP and the Cloud Service (S3 bucket pmc-oa-opendata, list with prefix "<PMCID>." including the dot); papers outside the open-access subset are for a person. Springer answers a script with a JavaScript challenge. Google's AI Mode share links sit behind a robot check. Never disguise a script as a browser or get around a check; the auto-mode classifier refuses it.

**Why:** a later thread would otherwise assume the old blocks, or try to route around them.
**How to apply:** in a new thread, test with one curl before saying a host is blocked; ask greg once for the environment if it is missing. Related: [[papers-in-hand]].
