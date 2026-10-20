export const meta = {
  name: 'cite-taxonomy-docs',
  description: 'Add numbered citations to sections of the taxonomy spec and manual, then adversarially check them',
  phases: [
    { title: 'Cite', detail: 'one agent per section group proposes citation markers and source records from the research notes' },
    { title: 'Check', detail: 'an adversarial checker per group verifies support, records and completeness' },
  ],
}
const R = '/tmp/claude-0/-home-user/fc677e8c-eac5-5c7b-b3c7-c77e3a8aea70/scratchpad/refs'
const CHECKER = R + '/check_edits.py'
const NOTES = `Research notes (a network mount: read only the files you need, by path; never run a recursive search over /mnt/project-files):
/mnt/project-files/research/taxonomy/notes/01-symphony-mechanism.md  Symphony as built: mechanism, GitHub primitives, cost, maturity
/mnt/project-files/research/taxonomy/notes/02-prior-positioning.md  Symphony's prior positioning and competitor facts
/mnt/project-files/research/taxonomy/notes/03-coordination-evidence.md  CooperBench, coordbench, the curse-of-coordination experiment
/mnt/project-files/research/taxonomy/notes/04-beethoven-launcher.md  Beethoven launcher (hpcworker, extension)
/mnt/project-files/research/taxonomy/notes/05-beethoven-engine.md  beethoven-qa, -agents, -research and the stack
/mnt/project-files/research/taxonomy/notes/06-ci-and-cloud-coding-agents.md  coding agents in CI or a vendor cloud
/mnt/project-files/research/taxonomy/notes/07-multi-agent-frameworks.md  orchestration frameworks, protocols, parallel coding-agent tools
/mnt/project-files/research/taxonomy/notes/08-need-evidence.md  where multi-agent and agent-written software fails; what coordination costs
/mnt/project-files/research/taxonomy/notes/09-actions-economics.md  GitHub Actions economics, limits and terms
/mnt/project-files/research/taxonomy/notes/10-claude-economics.md  Claude Code on a subscription in automation
/mnt/project-files/research/taxonomy/notes/11-ai-for-science.md  AI-scientist systems, reproducibility frameworks, HPC workflow tools
/mnt/project-files/research/taxonomy/notes/12-verification.md  verifying agent-written code and coordination protocols
/mnt/project-files/research/taxonomy/notes/13-taxonomy-literature.md  taxonomies a classification of agent software can build on
/mnt/project-files/research/taxonomy/verify/01-gh-aw-copilot.md  adversarial check: gh-aw work queue and Copilot cloud agent
/mnt/project-files/research/taxonomy/verify/02-claim-lock.md  adversarial check: the claim lock, idleness, re-claims
/mnt/project-files/research/taxonomy/verify/03-uniqueness.md  adversarial check: is Symphony's combination unique
The spec's own section 12 lists its main primary sources with their links: ${R}/packets/spec-sources.txt
Each note gives, for each fact, where it was read (a URL; a repository cloned at a commit with a path; or a search summary) and its grade. Do not modify any file under /mnt/project-files, and install nothing.`

const FIELDS = `Source record fields: key ("s1", "s2", ...); kind (one of paper, preprint, book, repository, repository-file, documentation, web-page, blog-post, dataset, standard, terms, news, project-record); authors (a list: people as "Family Initials", e.g. "Malone TW", or the organization's name, e.g. "GitHub"; empty list if none known); title (the work's own title, or for a repository file its path); container (journal or conference with volume and pages, "arXiv", the website or blog, or for a repository or repository file the repository "owner/name"); date (publication date, or for a repository file the commit's date: YYYY or YYYY-MM-DD; "" if unknown); version (the commit sha exactly as the note gives it, a release, or an arXiv id; "" if none); url (where the source can be read: a DOI link or the arXiv abstract for a paper; for a file read from a cloned repository at a commit, https://github.com/<owner>/<repo>/blob/<sha>/<path>; for a web page its address; "" only for a project-record); public_url (optional, "" if none: the public page with the same text, e.g. for a github/docs content file https://docs.github.com/en/<the path after content/, without .md>); read ("opened" if the research session read the primary itself, "search" if it only saw a search summary or a secondary page, "record" for a project record); path (project records only: the full path under /mnt/project-files; "" otherwise); supports (one short phrase: what it is cited for). Never invent a field: every value comes from a note or from the document's own links. The research session could not open docs.github.com, github.blog or arxiv.org, so a "Verified" GitHub docs fact was read in the github/docs repository: cite that file at the commit the note names.`

const RULES = `Rules for edits:
- Each edit is {unit_id, find, replace}. find is an exact substring of that unit's text (copy it character for character from the packet) that occurs exactly once in that unit; replace is the same words with citation markers added, written [[s1]] or [[s1,s4]]. Keep finds short (a few words around the insertion point). Two edits in one unit must not overlap.
- Change no other words, with one exception: where the text names a research note or verify file as its source ("research note 09", "research notes 06 and 07", "research/taxonomy/verify/03"), replace that mention with the markers of the primary sources the note gives for the claim, adjusting only the joining words. Examples: "(Verified, research note 01)" -> "(Verified [[s3,s4]])"; "(Inferred; research note 13)" -> "(Inferred [[s9]])"; "Verified: PROTOCOL.md, research note 01." -> "Verified: PROTOCOL.md [[s2,s3]]."; "Sources: research notes 06 and 07, and research/taxonomy/verify/01 and 03 (Verified from each project's repository or docs, 2026-10-15)." -> "Sources: [[s1,s2,s5]] (Verified from each project's repository or docs, 2026-10-15)." Cite a note or verify file itself (kind project-record, read "record") only when the claim is that file's own synthesis, inference or measurement, or when it gives no primary source for the claim. If an edit only deletes a mention and adds no marker, set "removes_only": true.
- Place a marker right after the words, name or link it supports, before closing punctuation: "79.4% accurate [[s5]]." or after the grade word: "(Verified [[s2]])". In a table, put the marker in the cell that states the fact; in a comparison table each system's name cell carries the marker of that system's repository, paper or docs.
- Text that already links a source (see "links in this unit" in the packet) gets a marker right after the link text too, citing that same URL, so the PDF's reference list carries it.
- Never edit a heading, a code block or an embedded drawing. Never change a grade word (Verified, Inferred, Reported, Open). Cross-references inside the documents ("section 9", "question R3", "the spec") are not sources and get no marker.
- Every claim graded Verified or Reported, every statement that names a paper, report, page or repository as its source, and every number taken from a source must end up with a marker. Inferred claims get markers for the facts they rest on when the text names those facts' sources. Open items need none.
- uncited: list any Verified or Reported claim for which no source can be found in the notes, with why. Do not invent a source to fill the gap.`

const SCHEMA = {
  type: 'object',
  properties: {
    edits: { type: 'array', items: { type: 'object', properties: {
      unit_id: { type: 'string' }, find: { type: 'string' }, replace: { type: 'string' }, removes_only: { type: 'boolean' } },
      required: ['unit_id', 'find', 'replace'] } },
    sources: { type: 'array', items: { type: 'object', properties: {
      key: { type: 'string' }, kind: { type: 'string' }, authors: { type: 'array', items: { type: 'string' } },
      title: { type: 'string' }, container: { type: 'string' }, date: { type: 'string' }, version: { type: 'string' },
      url: { type: 'string' }, public_url: { type: 'string' }, read: { type: 'string' }, path: { type: 'string' },
      supports: { type: 'string' } },
      required: ['key', 'kind', 'authors', 'title', 'container', 'date', 'version', 'url', 'read', 'supports'] } },
    uncited: { type: 'array', items: { type: 'object', properties: {
      unit_id: { type: 'string' }, claim: { type: 'string' }, why: { type: 'string' } }, required: ['claim', 'why'] } },
    changes: { type: 'array', items: { type: 'string' } },
    checker_problems: { type: 'integer' },
  },
  required: ['edits', 'sources', 'uncited', 'checker_problems'],
}

const docName = g => g.startsWith('spec') ? 'the Symphony and Beethoven Taxonomy Spec' : 'the Symphony and Beethoven Taxonomy Manual (a how-to that goes with the spec)'

function citePrompt(g) {
  return `You are adding numbered references to one part of ${docName(g)}, so it can be exported as a PDF with a numbered reference list whose entries carry links. The part's text is in ${R}/packets/${g}.txt (one unit per block, with its unit id, where it sits, and the links it already has) and the same units as JSON in ${R}/packets/${g}.json. Read the packet first, then the notes its claims rest on.

${NOTES}

${RULES}

${FIELDS}

Before you return, write your result as JSON (the same shape you return; set checker_problems to the count the checker prints) to ${R}/out/${g}-cite.json and run: python3 ${CHECKER} ${R}/packets/${g}.json ${R}/out/${g}-cite.json
Fix every PROBLEM it prints and re-run until it reports 0 problems; read its NOW lines to see that each edited unit still reads well. Then return the result.`
}

function checkPrompt(g) {
  return `You are the adversarial checker of citations another agent added to one part of ${docName(g)}, which will be exported as a PDF with a numbered reference list. The part's text is in ${R}/packets/${g}.txt and ${R}/packets/${g}.json. The other agent's result (edits that add [[sN]] markers, and source records) is in ${R}/out/${g}-cite.json. Assume it has errors: your job is to find and fix them, not to approve it.

${NOTES}

${RULES}

${FIELDS}

Check every edit and every source record:
1. Support. Open the note(s) behind each claim and confirm that each cited source is the one the note says supports that exact claim, at the grade the text gives. A claim graded Verified must cite a source the research session read itself ("read": "opened"); a Reported one may cite a "search" source. Where a URL is reachable from here (github.com and raw.githubusercontent.com, code.claude.com, anthropic.com; arxiv.org, docs.github.com and github.blog are blocked), spot-check several by fetching them. Remove or replace any citation that does not support its claim.
2. The records. Title, authors, date, version and URL match what the note gives; a repository-file URL pins the commit the note read; a paper has its DOI or arXiv link when the note gives one; nothing invented. Fix what is wrong; delete a source you cannot confirm and say so in uncited.
3. Completeness. Every claim graded Verified or Reported, every mention of a research note or verify file, every named paper, report, page or repository with a known primary source, every number taken from a source, and every existing link carries a marker. Add what is missing (new keys continue after the highest key used).
4. Wording. Apart from the markers and the removal of note mentions, no word changed; grades untouched; each sentence still reads cleanly; nothing in a heading, code block or drawing.

Write your corrected full result (same JSON shape; add "changes": a list of what you changed and why; set checker_problems to the count the checker prints) to ${R}/out/${g}-check.json, run python3 ${CHECKER} ${R}/packets/${g}.json ${R}/out/${g}-check.json until it reports 0 problems, and return that result.`
}

const groups = args.groups
log(`Citing ${groups.length} section groups: ${groups.join(', ')}`)
const results = await pipeline(
  groups,
  g => agent(citePrompt(g), { label: `cite ${g}`, phase: 'Cite', schema: SCHEMA }),
  (cited, g) => cited ? agent(checkPrompt(g), { label: `check ${g}`, phase: 'Check', schema: SCHEMA }).then(r => ({ group: g, cited: !!cited, result: r })) : { group: g, cited: false, result: null },
)
return results.map(r => r ? { group: r.group, ok: !!r.result, edits: r.result ? r.result.edits.length : 0, sources: r.result ? r.result.sources.length : 0, uncited: r.result ? r.result.uncited : null, changes: r.result ? (r.result.changes || []).length : 0, problems: r.result ? r.result.checker_problems : null } : null)
