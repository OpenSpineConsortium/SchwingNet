# Reading lists for the gate word literature

Each file here is one reading list, `<list>.csv`, that the gate word `literature <list>` fetches onto
the grid (grid/literature.sbatch, grid/literature_fetch.py). The columns:

- id: the paper's name in its source, lower-case letters, digits and _, each once.
- doi: its DOI, where one is known.
- pmcid: its PMC id, PMC and digits, where PMC holds it.
- held: where the paper is held already, so it is not fetched; empty otherwise.

A list is added or changed by pull request, since the gate runs main.

## synthetic_spine.csv

The 42 papers of spine-program's synthetic_spine/sources.csv at commit 11d2aca (sha256
d3341ac7db8a9ecf4a8b792620219b724e65f19e2d787bcc322f97dbf5437028), the published per-level
morphometry series behind its tables: the id is that file's paper column, the DOI its doi column, the
PMC id the last part of its pmc_link. The three Panjabi papers are held already as PDFs under
bordercall's archive/bordercall/reference/papers/, so they are marked held. Three papers have no DOI
and no PMC id (alonge2021, ahmed2019, chaudhary2015: not found in Crossref or PubMed), so the fetch
lists them for the owner at once.
