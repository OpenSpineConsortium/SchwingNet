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
  ~/.s2/token.env, a file of its own, since SchwingNet's Kaggle reader takes a file's first line
  where it finds no Kaggle line (symphony-template's docs/research/service-keys-to-the-grid.md has
  the route). A secret saved with a line break is never split: the route takes off a break at its
  end and refuses one inside, and the gate refuses a key that comes over two lines.
- The fetch: the gate word `literature <list>` (grid/gate.sh) queues grid/literature.sbatch, one
  batch job that runs grid/literature_fetch.py twice, as a plan and as a fetch, under the size rule.
  The plan asks each source what it holds for each paper and bounds every file by the size its
  server states or a cap of 50 MB; the fetch lands nothing until the rule admits that bound.
- The sources, in order: a paper marked held is skipped; a PMC id in the open-access subset gets
  Europe PMC's JATS XML and a PDF; an Elsevier DOI (10.1016/) goes through Elsevier's article API,
  entitlement first, then the full-text XML (view=FULL) and the PDF; any other paper with no PDF yet
  gets the open-access PDF Semantic Scholar names, unless the link is on PMC's, Europe PMC's or
  Elsevier's own pages (ScienceDirect, its asset and CDN hosts, Cell, The Lancet), or redirects
  onto one of them.

## Why it is shaped this way

- Elsevier's terms (its e-mail of 2026-10-16, kept in spine-program's
  13_aidas_program/memory/elsevier-grant-and-terms.md) ask for the key and token server side, never
  in browser code or an address bar, over HTTPS, in the headers X-ELS-APIKey and X-ELS-Insttoken. The
  tool reads them only from a plain file of the owner's account that no one else may read, sends
  them only in those headers and only to api.elsevier.com, refuses every redirect of such a call,
  and writes them nowhere. The landing literature_<list> is 0700 and every file in it 0600, and its
  README.md says that Elsevier's files stay on the grid, are read there only and never train a model.
- The owner's e-mail of 2026-10-16 from Elsevier says full text waits for the ScienceDirect
  text-mining amendment. The fetch therefore checks entitlement first, asks for the XML before the
  PDF and keeps an abstract-only XML as what it is: such a paper is listed as not got, its PDF is
  not asked for, since where Elsevier withholds the text it sends the PDF's first page alone, and
  the next send asks Elsevier again, so the paper lands once the amendment is signed.
- PMC's articles outside the open-access subset are free to read but PMC's terms bar automated
  retrieval of them, so the fetch lists them for the owner rather than scripting their pages.
- Every fetch on the grid knows its size before a byte lands (the owner's size rule of 2026-10-23),
  so the plan is a separate pass that writes only meta/PLAN.json, counts 1 MB for the index and
  readme it writes, and a body that passes its bound, ends before the length its server stated or
  is still coming after 15 minutes is deleted.
- The adversarial review of 2026-10-28 (four lenses, each finding checked by a second reader) found
  the cut-off bodies, the redirects onto unscripted hosts, the first-page PDF, a paper landed before
  being listed as not got when its source failed on a later send (meta/LANDED.json now keeps every
  landed file), a server's error that could echo a key into the report (key-shaped runs are withheld
  and the report is 0600), the S2 key beside the Kaggle lines, and a test address taken from a stray
  setting (only under LITERATURE_STAND_INS=yes now). All were fixed before the merge.

## How the researcher uses them

The researcher is a Claude session on the grid under the owner's account: it reads INDEX.md in the
landing literature_<list> of the data root (/rs/rs_grp_oschome/go2432/data/literature_<list>/),
which names each paper's files under text/<id>/ with the licence its source stated, or none. The
open-access files are free for it to read. Elsevier's are not yet: a Claude session sends what it
reads to Anthropic's API to answer, so the text would leave the grid for that answer, which is a
question for the ScienceDirect text-mining amendment the owner is asking about; INDEX.md marks each
Elsevier file "owner's word before a session reads it" and the landing's README.md says the same.
The same session runs as the owner and could open ~/.elsevier/token.env, while it reads PDFs from
publishers' hosts, so a session reading the landing is told never to open the key files.
A cloud session cannot reach the grid; it reads the report the gate word prints, which names papers
and reasons and never a key or a text. A new paper is added to a list under grid/literature/ by pull
request and fetched by sending the word again.

## Where it stands

The first run, on 2026-10-28: the key route sent both keys at 01:00 and 01:01 UTC (the first sends
at 00:32 stopped before the gate, since the organization secrets did not reach symphony-template's
job until the owner gave them Selected repositories), and grid job 40819848 ran
`literature synthetic_spine` on csc1 at commit 76838c4, 8 minutes 36 seconds by sacct's elapsed time. Of the 42 papers,
3 were held already, 17 were got (19 files, 13.2 MB) and 22 were not got. Thirteen of the 17 came
as Europe PMC's JATS XML; for eleven of those the PDF link answered 403, so their figures, and a
table printed as an image such as Pierro 2017's, were not landed. The tool's first source for those
PDFs, PMC's open-access web service, closed with the PMC Article Dataset Changes announced on 12
February 2026, which leaves Europe PMC's rendered PDFs as the links that answered 403; the fetch now
takes them from PMC's Cloud Service instead (below). Four came as the open-access PDF Semantic
Scholar named (tan2004, chen2011, yadav2020, ahn2001).

- Elsevier answered 403 to the entitlement check for both of its papers, bach2019 and shin2024.
  shin2024 is open access, which Elsevier serves to any key it accepts, and Elsevier documents a 403
  here as a request it could not authenticate or whose entitlements it could not validate, while a
  recognised requester without rights gets 200 with entitled false: so Elsevier refused the request
  before it looked at any article's rights. Two causes fit equally well: the institutional token is
  not bound to this key ("Institution Token is not associated with API Key" in public reports), or
  the key's ScienceDirect configuration is not switched on ("Requestor configuration settings
  undefined or insufficient"), which may be tied to the text-mining amendment Elsevier's email of
  16 October says full text waits for. Elsevier's own status word was lost to the report's scrub,
  which withheld every run of 20 or more letters, digits, underscores or hyphens. The scrub now lets
  a word of capitals and underscores through, which no key these services issue looks like, and the
  report now carries Elsevier's status text beside it, so the next send names Elsevier's status word
  and its status text, which tell the causes apart. The questions for Elsevier (case 260924-003406)
  are which API key the institutional token is bound to, and whether that key is enabled for the
  ScienceDirect APIs.
- Semantic Scholar answered 429 to four keyed lookups (kunkel2011, tang2016, robertson2000 and
  yu2015) even after waits of 3 and 6 seconds, though every call came more than a second after the
  last, the keyed limit Semantic Scholar documents. The fetch now asks up to six times in all, again
  after about 2, 4, 8, 16 and 32 seconds spread by half either way, waits as long as a Retry-After of
  up to two minutes asks, and gives up at once on a longer one, naming the wait it was asked for. A
  503 is asked again the same way. Every paper those four touched was found by hand.
- Europe PMC answered the job's search with no matching record for kunkel2011, although PMC holds
  it as PMC3171774; the cause is not known.

The 22 not got, each checked on the source's own page by one reader and again by a second, with a
critic over both (the thread's workflow of 2026-10-28):

- The owner had sent 10 of them as PDFs at 01:02 UTC, for spine-program #238's reading: zindrick1987,
  krag1988, olsewski1990, hou1993, robertson2000, mitra2002, yu2015, hinck1966, tang2016 and
  bach2019. These are closed except tang2016, of which CDC Stacks holds a copy whose version is not
  stated (stacks.cdc.gov/view/cdc/216558).
- Six are free to read on PMC outside the open-access subset, which PMC's terms leave to a person:
  gilad1985 (PMC1166429), amonookuofi1985 (PMC1165137), amonookuofi1982 (PMC1168228), kunkel2011
  (PMC3171774), lien2007 (PMC2200778) and makino2012 (PMC3535235).
- Five are free from their publishers: griffith2016 (Quant Imaging Med Surg, CC BY-NC-ND 4.0),
  twomey1985 (Acta Orthopaedica's whole archive is free, so no interlibrary loan is needed),
  alonge2021 (Afr J Med Med Sci 50(2), June 2021, 69-76: issue 2, which the list leaves out), ahmed2019 ("Radiological
  Anatomy of the Lumbar Canal: A MRI study", J Chalmeda Anand Rao Inst Med Sci 17(1), pages 21-26 as
  printed) and chaudhary2015 ("A Radiographic Study of Interpedicular Distance of the Lumbar Vertebrae
  Measured in Plain Antero-Posterior Radiographs", Int J Adv Res 3(8):33-36, 2015). None of these
  three has a DOI or a PMID, which is why the list found none; the last was thought not to exist.
- One is closed with no free copy: eisenstein1977 (J Bone Joint Surg Br), through the library.
- Three citations of the list name one author as "et al.": both Amonoo-Kuofi papers and Eisenstein.

So all 42 are found: 20 on the grid or held, 10 sent by the owner, 11 free to read by hand and one
through the library. The owner was asked on 2026-10-28 to send the twelve as he sent the ten.

Which of the twelve a program may fetch, checked the same day by one reader and one skeptic per
paper, through WebFetch alone, with no bot check passed or sought:

- Five a script may download from the publisher with a plain GET: griffith2016
  (qims.amegroups.org/article/download/13035/13345, which redirects to the publisher's CDN),
  twomey1985 (actaorthop.org/actao/article/download/23300/27230/71833), alonge2021
  (www.ojshostng.com/index.php/ajmms/article/download/1782/1196), ahmed2019
  (caims.in/assets/journal/2019_1/CAIMS%20JOURNAL___05.pdf) and chaudhary2015
  (www.journalijar.com/uploads/2015/08/684_IJAR-4961.pdf). The cloud session's proxy refused every
  one of these hosts until the owner gave the project's threads full network access that day, and
  the grid word reached none of these addresses: alonge2021, ahmed2019 and chaudhary2015 have no DOI
  or PMC id, so no source was asked; for griffith2016 Semantic Scholar names
  qims.amegroups.com/article/viewFile/13035/pdf, which redirects to qims.amegroups.org and returns a
  page, not the PDF; for twomey1985 it names Taylor & Francis's PDF, which answered 403.
- The six PMC papers only a person may get. Their PDF links answer a script with a reCAPTCHA or a
  "Preparing to download" page. PMC's copyright notice, read that day, forbids automated downloading
  except through its OAI-PMH, FTP and Cloud services, which carry only the Article Datasets (the
  open-access subset, the author manuscripts and the historical OCR set), and a listing of the Cloud
  Service bucket holds none of the six. Springer's copies of lien2007 and makino2012 are paywalled
  (its page asks USD 39.95 for the PDF, although Unpaywall calls them bronze); Wiley's page for
  kunkel2011 could not be read, and Europe PMC lists its DOI link as subscription required while
  Unpaywall knows no free publisher copy; the three J Anat scans of 1982 and 1985 have no DOI.
- eisenstein1977 only through the library: Bone & Joint's PDF and article pages are paywalled,
  although Semantic Scholar marks a bronze copy; OpenAlex calls it closed.

PMC's Cloud Service is also where a script may take the PDF of a paper in the open-access subset: a
public S3 bucket, pmc-oa-opendata, holding each article under PMCID.version/ as PDF, JATS XML, plain
text and figures (a listing for bonczar2024, PMC11624215, showed its 736,145-byte PDF on
2026-10-28). The fetch now lists the bucket for the PMC id and a dot, since the id alone also lists
longer ids that begin with it, and takes the newest version's PDF, so the next send should land the
PDFs the bucket holds for the eleven papers that came as XML alone.
