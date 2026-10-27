# Literature on the grid: Elsevier's key and a fetch that keeps the text there

Source: the thread "Get full texts through Elsevier key" in the project symphony_4, 2026-10-27, for
the owner's word of 23:00 UTC: "On your word, a session adds Elsevier to the key route and writes a
fetch that runs as a grid job. It reads the key from a file only you can read and keeps the text on
the grid, as you told Elsevier." He asked for both to be tested, for the researcher to be able to use
them, and for the list of the papers it cannot get, so that he can get those himself. The reading
list is the 42 papers of spine-program's synthetic_spine/sources.csv (commit 11d2aca).

## What was built

- The key route: symphony-template's grid-accounts.yml action key takes the names elsevier and s2.
  elsevier sends the organization secrets ELSEVIER_API_KEY and ELSEVIER_INSTTOKEN as one line, the
  key, one space and the token; s2 sends S2_API_KEY. hpcworker's gate word `key elsevier` writes both
  lines of ~/.elsevier/token.env, mode 600 in a 700 folder, and `key s2` writes S2_API_KEY into
  ~/.fluorocap/credentials.env beside the Kaggle lines (symphony-template's
  docs/research/service-keys-to-the-grid.md has the route).
- The fetch: the gate word `literature <list>` (grid/gate.sh) queues grid/literature.sbatch, one
  batch job that runs grid/literature_fetch.py twice, as a plan and as a fetch, under the size rule.
  The plan asks each source what it holds for each paper and bounds every file by the size its
  server states or a cap of 50 MB; the fetch lands nothing until the rule admits that bound.
- The sources, in order: a paper marked held is skipped; a PMC id in the open-access subset gets
  Europe PMC's JATS XML and a PDF; an Elsevier DOI (10.1016/) goes through Elsevier's article API,
  entitlement first, then the full-text XML (view=FULL) and the PDF; any other paper with no PDF yet
  gets the open-access PDF Semantic Scholar names, unless the link is on PMC's, Europe PMC's or
  Elsevier's own pages.

## Why it is shaped this way

- Elsevier's terms (its e-mail of 2026-10-16, kept in spine-program's
  13_aidas_program/memory/elsevier-grant-and-terms.md) ask for the key and token server side, never
  in browser code or an address bar, over HTTPS, in the headers X-ELS-APIKey and X-ELS-Insttoken. The
  tool reads them only from a plain file of the owner's account that no one else may read, sends
  them only in those headers and only to api.elsevier.com, refuses every redirect of such a call,
  and writes them nowhere. The landing literature_<list> is 0700 and every file in it 0600, and its
  README.md says that Elsevier's files stay on the grid, are read there only and never train a model.
- The owner's e-mail of 2026-10-16 from Elsevier says full text waits for the ScienceDirect
  text-mining amendment. The fetch therefore checks entitlement first and keeps an abstract-only
  answer as what it is: such a paper is listed as not got, with Elsevier's own status word, and the
  next send asks Elsevier again, so the paper lands once the amendment is signed.
- PMC's articles outside the open-access subset are free to read but PMC's terms bar automated
  retrieval of them, so the fetch lists them for the owner rather than scripting their pages.
- Every fetch on the grid knows its size before a byte lands (the owner's size rule of 2026-10-23),
  so the plan is a separate pass that writes only meta/PLAN.json, and a body that passes its bound
  is deleted.

## How the researcher uses them

The researcher is a Claude session on the grid under the owner's account, the only reader that may
see Elsevier's text: it reads INDEX.md in the landing literature_<list> of the data root
(/rs/rs_grp_oschome/go2432/data/literature_<list>/), which names each paper's files under
text/<id>/. A cloud session cannot reach the grid; it reads the report the gate word prints, which
names papers and reasons and never a key or a text. A new paper is added to a list under
grid/literature/ by pull request and fetched by sending the word again.

## Where it stands

The code and its tests are merged with this note; the first run waits for the key route's sends and
one `literature synthetic_spine`, which the owner's word of 2026-10-27 covers. Of the 42 papers, the
list itself already says that 3 are held (Panjabi), 3 have no DOI or PMC id, 10 sit in PMC outside
the open-access subset and 13 have no PMC copy; bach2019 (World Neurosurgery) is the one paper that
only Elsevier's route can bring, and shin2024 (Brain and Spine) is open access at both PMC and
Elsevier, so its Elsevier answer shows whether the key and token reach full text at all. What the run
got and could not get is added here from its report.
