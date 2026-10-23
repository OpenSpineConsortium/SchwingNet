# Training data licences and recipes

Source: the thread "Training data licence provenance", 2026-10-23, the owner's ask of that day: as the work moves to training, every run must record which datasets went into it under which licence, so that networks for commercial use are built only from data whose terms allow it, networks that need non-commercial data are known as such, and the recipes that are possible are visible before anything runs.

## What was built

- data/licences.json classifies every dataset, the 111 records under data/sources/ and the registry sources that have no record of their own (113 entries), with aliases where a registry source is a record under another name (aariz, mimic_cxr_jpg). Each entry copies its licence line word for word, so a line that changes fails the check until it is classified again. For a registry source the line is the registry's access line, since that is what was read when the source entered the catalog a run trains from.
- Six classes, from the most permissive: open, share-alike, non-commercial, agreement, no-derivatives, unknown. tools/licences.py proposes a class from the line's words, taking the strictest reading any phrase gives; an entry the rule proposed says "reviewed": "rule". Only the owner's reading ("owner YYYY-MM-DD") may give a class looser than the rule's.
- Four recipes under data/recipes/: commercial (open, owner-reviewed only), commercial-share-alike (open and share-alike, owner-reviewed only), non-commercial (open, share-alike, non-commercial) and research-internal (every class but unknown). No recipe takes unknown.
- `python3 tools/licences.py derive --catalog C --recipe R --out C2` cuts a catalog to a recipe's sources and records the recipe and the parent catalog's sha256 inside the copy. Every `tools/flow.py run` writes PROVENANCE.json and PROVENANCE.md beside RUN.json before its first step, `record` keeps them with the run, and the ledger row names the run's licence class; `--recipe R` refuses, before anything is written, a catalog with a source the recipe does not take.
- data/LICENCES.md is rendered from the facts: the count per class, a matrix of which recipe takes which trainable source (yes, after review, or never), and every dataset's line. `bash scripts/check.sh` runs `python3 tools/licences.py check`.

## Where the trainable sources stand on 2026-10-23, by the rule alone

Of the 24 registry sources, 4 read open (aariz, carmlspine, carmlspine_sweeps, kub_stonex), 1 non-commercial (lumos), 6 agreement (bimcv_covid19, mimic_cxr_jpg, padchest and the three VinDr sets) and 13 unknown, most because the registry's line still says "to confirm". So no commercial recipe takes anything until the owner confirms the open classes, and the non-commercial recipe takes the four open ones and LUMOS.

spine-datasets' records (datasets/<id>.json) read several of these lines later than SchwingNet's: CathAction CC BY-NC-SA 4.0, Fraiwan and the canine set CC BY 4.0, PENGWIN task 2 CC BY 4.0 and VerSe's 2D projections "Other (Open)", each read on 2026-10-22. Carrying those readings into the registry's access lines, or the owner confirming them as owner readings here, would move those sources out of unknown; neither is done here, since a licence line is a fact the owner signs off.

## What the classes do not say

A class reads the licence's words. Whether a trained network is an adaptation under share-alike or no-derivatives terms, whether an agreement's research-use clause allows a spin-out to use weights trained under it, and whether attribution must travel with the weights, are questions for counsel and Wayne State's technology transfer office; the record keeps the facts they would ask for.
