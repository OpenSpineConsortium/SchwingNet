export const meta = {
  name: 'find-anomaly-ground-truth-corpora',
  description: 'Find every full-spine corpus with reader-confirmed vertebral count anomalies (L6, T13, four lumbar, eleven thoracic), held or not, and verify each',
  phases: [{ title: 'Search', detail: 'records reader and three web sweeps' }, { title: 'Verify', detail: 'a skeptic per sweep checks each candidate' }, { title: 'Synthesize', detail: 'one ranked table' }],
}

const SCRATCH = '/tmp/claude-0/-home-claude/615a65dd-1c84-50a7-b0b4-353f715ff8c1/scratchpad/corpora'
const RULES = `READ ONLY in every repository under /home/claude: never edit, commit or push; scratch files only under ${SCRATCH}/ (make it). Use absolute paths, never cd. The web: load WebSearch and WebFetch with ToolSearch (query "select:WebSearch,WebFetch"); this container's proxy refuses arxiv.org, doi.org, figshare, Zenodo, Mendeley, Hugging Face, docs.github.com and most publishers, so read a paper or a dataset page through a search result's text, a GitHub repository (raw.githubusercontent.com works), PubMed Central (www.ncbi.nlm.nih.gov/pmc) or Europe PMC (www.ebi.ac.uk/europepmc), and say plainly when a page could not be opened. Never download a dataset. Never put SchwingNet's method, its name or anything from its repository into a search query: search only in general terms about public spine datasets.`

const GOAL = `The owner asked, verbatim: "CAN YOU FIND ANY MORE FULL SPINE CORPUSES WITH ANOMALIES THAT ARE GROUND TRUTH?" The context: a held-out test of whether models name vertebrae right on spines with a numbering variant (lumbosacral transitional vertebra counted as an extra lumbar L6 or a sacralised L5 giving four lumbar; a 13th rib-bearing thoracic T13; eleven thoracic), where the only reader-confirmed sets in hand are VerSe'19 and '20 (Loeffler 2021's supplementary table: about 85 L6 and 6 T13 among 355 people) and CTSpinoPelvic1K (16 reader-confirmed L6). Wanted: corpora whose images cover the whole spine, or at least the thoracolumbar AND lumbosacral junctions together (so the count from C2 or from the last rib to the sacrum can be checked), where the variant is GROUND TRUTH: stated per case by readers (a published table, a label file, a per-vertebra label map that includes L6 or T13, a Castellvi grade with the count), not inferred by an algorithm. Any modality counts: CT first, then whole-spine MRI and long-film or full-spine radiographs, then CT/CBCT paired with radiographs or fluoroscopy. Per candidate: name, link, modality, number of cases, how many with each variant if stated, how truth was made (readers, how many, the protocol), field of view, access (open, registration, data use agreement, request by e-mail), licence, size if stated, and the source you read.`

const CANDIDATES = {
  type: 'object',
  properties: {
    candidates: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          link: { type: 'string' },
          modality: { type: 'string' },
          cases: { type: 'string' },
          variants: { type: 'string', description: 'counts of L6, T13, four lumbar, eleven thoracic, Castellvi, if stated' },
          truth: { type: 'string', description: 'how the variant labels were made' },
          field_of_view: { type: 'string' },
          access: { type: 'string' },
          licence: { type: 'string' },
          held_already: { type: 'string', description: 'yes/no/unknown, with where the records say so' },
          source: { type: 'string', description: 'what you read: path or URL' },
          confidence: { type: 'string', enum: ['confirmed', 'likely', 'unverified'] },
        },
        required: ['name', 'modality', 'variants', 'truth', 'access', 'held_already', 'source', 'confidence'],
      },
    },
    ruled_out: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, why: { type: 'string' } }, required: ['name', 'why'] } },
    notes: { type: 'string' },
  },
  required: ['candidates'],
}

const SWEEPS = [
  { key: 'records', prompt: `${GOAL}

${RULES}

Your part: the owner's own records, so nothing already held or already ruled out is proposed as new. Read: /home/claude/SchwingNet/data/sources/*.json (117 dataset records), /home/claude/SchwingNet/docs/research/datasets-inventory.md, data-access-requirements.md, dataset-chooser.md, xray-dataset-requests.md, xray-datasets-missing.md, final-dataset-recipe.md, /home/claude/SchwingNet/data/reproduce/sources.json (211 sources), /home/claude/spinesurg-ct-nnunet/SchwingNet/results/transitional_registry/REGISTRY.md and its subfolders' markdown, and in /home/claude/symphony-template/docs: research/dataset-census-and-roadmap.md, research/spine-dataset-status-audit.md, research/dataset-access-paths-2026-10-22.md, research/spine-datasets-on-chinese-hosts.md, checkpoints/2026-10-20-claude-code/topic-memories/anomaly-harvest-directive.md. Grep these for transitional, LSTV, L6, T13, Castellvi, lumbarisation, sacralisation, numbering, enumeration, whole spine, full spine. List every corpus the records name that has or may have reader truth for a numbering variant, with whether it is held on the grid, requested, refused or ruled out, and why. Mark held_already from the records.` },
  { key: 'ct', prompt: `${GOAL}

${RULES}

Your part: CT and CBCT corpora on the web. Search widely: vertebra segmentation and labelling datasets that label L6 or T13 (VerSe-like label maps with id 25 or 28), whole-body CT databases where the whole spine is in view and a published study read the vertebral count (for example decedent or autopsy CT databases, whole-body trauma CT, PET-CT whole-body sets, and studies of lumbosacral transitional vertebra or thoracolumbar transitional prevalence that released their reads or case lists for a public collection such as TCIA or IDC), spine surgery planning sets, and challenge datasets (MICCAI, ISBI, CSI, xVertSeg, CTSpine1K, Spine-Mets, RibFrac with spine). Prefer sets with a per-case table of the count. Also note public collections where the image is public and a separate paper published per-case reads of the count on it, which would make reader truth for an existing public image set.` },
  { key: 'mri-xr', prompt: `${GOAL}

${RULES}

Your part: MRI and radiograph corpora on the web. Search widely: whole-spine or lumbar-plus-thoracolumbar MRI datasets with vertebra labels that include transitional anatomy (for example the SPIDER lumbar MRI set and its labelling protocol for transitional vertebrae, whole-spine sagittal MRI sets, RSNA lumbar challenges), lumbosacral transitional vertebra classification datasets (Castellvi) on Kaggle, GitHub, Zenodo, figshare, Mendeley or institutional pages, full-spine or long-film radiograph datasets (scoliosis and AASCE-like sets, BUU spine, standing whole-spine films) with vertebra numbering truth, and paired CT plus radiograph or fluoroscopy sets. For each, find whether the transitional or count label is per case and made by readers.` },
  { key: 'papers', prompt: `${GOAL}

${RULES}

Your part: the literature trail. Find recent papers (2018 to 2026) on automated vertebra labelling, vertebral counting or transitional vertebra detection in CT, MRI or radiographs, and on the prevalence of numerical variants of the spine, and for each read what data it used and whether that data is public or available on request with its reads: data availability statements, supplementary tables listing cases with the variant, GitHub repositories with label files. Include papers that evaluated on VerSe with corrected labels, papers that relabelled public sets for L6 or T13, and groups that state data is available on reasonable request (these count as request-by-e-mail candidates; name the corresponding author's institution, not personal e-mail addresses).` },
]

const VERDICTS = {
  type: 'object',
  properties: {
    verified: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          real: { type: 'boolean', description: 'the dataset exists and is reachable as described' },
          ground_truth: { type: 'string', enum: ['reader-per-case', 'reader-partial', 'algorithmic', 'none', 'unknown'] },
          full_spine: { type: 'string', enum: ['whole-spine', 'both-junctions', 'one-junction', 'unknown'] },
          variant_counts: { type: 'string' },
          access: { type: 'string' },
          corrections: { type: 'string', description: 'what the candidate entry got wrong' },
          source: { type: 'string' },
        },
        required: ['name', 'real', 'ground_truth', 'full_spine', 'variant_counts', 'access', 'source'],
      },
    },
  },
  required: ['verified'],
}

phase('Search')
const results = await pipeline(
  SWEEPS,
  s => agent(s.prompt, { label: `search:${s.key}`, phase: 'Search', schema: CANDIDATES }),
  (found, s) => {
    const cands = (found && found.candidates) || []
    if (s.key === 'records' || !cands.length) return { sweep: s.key, found, verified: null }
    return agent(`${RULES}

A searcher proposed the corpora below as full-spine sets with reader ground truth for vertebral numbering variants (L6, T13, four lumbar, eleven thoracic). Be a skeptic: for each, open the source it cites or find a better one, and decide whether it really exists as described, whether the variant label is per case and made by readers (not an algorithm, not a single global prevalence figure), whether the images cover both junctions, how many cases carry each variant, and how it is obtained. Default to ground_truth "unknown" and real false when you cannot confirm. Correct every wrong field.

Candidates:
${JSON.stringify(cands, null, 1)}`, { label: `verify:${s.key}`, phase: 'Verify', schema: VERDICTS })
      .then(v => ({ sweep: s.key, found, verified: v }))
  },
)

phase('Synthesize')
const table = await agent(`${GOAL}

${RULES}

Below are the owner's records sweep and three web sweeps, each web sweep checked by a skeptic. Write the answer as markdown, ASCII only, plain prose that says why, no emoji:
1. One sentence answering the question directly: how many genuinely new corpora with per-case reader truth for a numbering variant exist, and the best ones.
2. A table of the NEW candidates (not held already per the records), ranked by usefulness for testing L6 and T13 naming on whole or junction-to-junction spines: name, modality, cases, variants, how truth was made, access, licence, link. Use the skeptic's corrected fields wherever it disagrees with the searcher; drop anything the skeptic found unreal; put "reader-partial" and "unknown" truth below the per-case ones, marked.
3. A short list of image sets that are public but whose variant truth would need our own reading (for example whole-body CT databases), with how many cases and why they are worth reading.
4. What the records already hold or have ruled out, in one short list, so the owner sees nothing is proposed twice.
5. What could not be checked from this container, by name.
Keep it under 900 words.

Records sweep:
${JSON.stringify(results.find(r => r && r.sweep === 'records'), null, 1)}

Web sweeps with verdicts:
${JSON.stringify(results.filter(r => r && r.sweep !== 'records'), null, 1)}`, { label: 'synthesize', phase: 'Synthesize' })

return { table, results }
