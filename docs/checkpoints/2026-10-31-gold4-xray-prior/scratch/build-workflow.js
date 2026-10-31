export const meta = {
  name: 'prior-check-build',
  description: 'Spec, build, review and verify the trimmed gold tier prior check in SchwingNet',
  phases: [
    { title: 'Spec', detail: 'consolidate the design and its three critiques into one spec and a reading guide' },
    { title: 'Spec critic', detail: 'check the spec covers every critique item or defers it with a reason' },
    { title: 'Build', detail: 'implement the spec in SchwingNet with tests, note and memory' },
    { title: 'Review', detail: 'three lenses: statistics, safety and report shape, repository rules and tests' },
    { title: 'Fix', detail: 'apply the confirmed findings' },
    { title: 'Verify', detail: 'run the tests, a synthetic end to end run and the reading checks' },
  ],
}

const S = args.scratch
const CTX = `Context: the thread "Train on randomized spine phantoms" of the project symphony_3, 2026-10-31, in a cloud container.
Repositories: /home/claude/SchwingNet (git, branch claude/project-thread-dazoi0, reset to origin/main d629a8c; every change goes here, left uncommitted in the working tree; never commit, never push, never run anything on the grid, never dispatch a GitHub workflow, never write to GitHub) and /home/claude/bordercall (origin/main 1ef008f; read only, for reference).
Subject: the gold tier 3 correlation prior. SchwingNet grid/prior/gold3_prior.py fits, per population (enhance_pet and totalsegmentator; verse has too few whole spines), a matrix normal kron(R_level, R_measure) by Dutilleul's flip-flop on standardised whole spines over C3..L5 (22 levels) and T1..L5, on five measures (endplate, endplate_depth, endplate_lower, endplate_lower_depth, h_post), shrunk 0.05 toward the identity, using the vendored bordercall module grid/prior/schwingcheck/correlation.py. It runs on the grid as one CPU job, grid/morphometry-prior.sbatch, queued by grid/gate.sh's word_morphometry_prior (about line 2572), and its report lines reach a session only through the gate's printing (head -n 400, grid/report-shapes.awk with grid/shape-words.awk, sed -r -f grid/redact.sed, a 64,000 byte cut). The current record is /home/claude/bordercall/records/prior-2026-10-31/report.md (enhance_pet C3..L5: 693 fit and 158 held whole spines; width pair 0.301, depth pair 0.463). Existing tests: SchwingNet tests/test_gold3_prior.py and the sbatch test in tests/test_gate.py.
A design workflow asked whether the fitted R_measure understates how one vertebra's own measures move together, and designed a grid diagnostic. Its whole output is the JSON in ${args.design} (from the first '{': result.reads, result.design with verdict_so_far, hypotheses, diagnostic_job, decision_rule, model_options and who_to_tell, and result.critiques, three critiques by the lenses statistics, measurement and scope). A readable dump of every critique problem with its fix and evidence is ${args.critiques}. The prototypes and the critics' scripts and results are under ${args.proto} (judge/check_proto.py and judge/lines_proto2.py are the design's prototype; review/limit_stats.jsonl and review/rule_on_matched.jsonl are the statistics critic's truths matched to the published fits; critic/ holds naming_k56.py and icc_fit_groups.py).
The owner, greg, is asleep. GitHub Actions has refused jobs since 06:20 UTC for billing, so nothing reaches the grid or CI now; the work must be ready for when it returns.`

const DECISIONS = `Decisions already made; do not reopen them:
1. The statistics critique refuted the design's verdict. The separable fit's bias explains at most a third to a half of the gap to the literature, and only at the largest shared factor the published fits allow; the measures (their definitions, their noise, the neck cut, the thick-slice slabs) are joint leading suspects with a whole-spine shared factor. Everything written says that, never "mostly the Kronecker".
2. Trim to diagnostics, as the scope critique asks: no person-effect model P, no blend, no EM, no fivefold model choice (S7), no automatic model choice and no flags that pick a model (S10). The job prints descriptive lines. A reading guide, written and frozen (its sha256 beside it) before any send, says how a session reads the lines jointly against the signatures of truths that reproduce the published fits (the statistics critic's limit_stats.jsonl and rule_on_matched.jsonl), declares a few primary contrasts to bound multiplicity, and says what each reading leads to and that greg makes every choice.
3. Add what the measurement critique asks, from inputs that need no new grid data: protocol classes from each kept study's slice_mm in its study rows; site and scanner from data/gold3-ct/enhance-pet/facts.jsonl (git-tracked; confirm which keys hold them; add the file to the sbatch's git archive list and to the gate's list of paths it checks at the commit); per class, the count and each measure's mean z by region; S1 (same level) and S4 (far apart, printed per pair, never averaged over pairs of opposite sign) again with every cell standardised within its protocol class, and on the autoPET 2.5 mm class alone; the canal test, the correlation over spines of the spine-mean z of the four plate measures with that of canal_ap and of canal_w, per class; the neck by level and branch (the flag:body_foramina rows) with counts, each width's mean z, the within-branch r and the share of vertebrae whose two widths agree within 1 mm, the pooled C3-C7 width covariance split into its within-branch and between-branch parts, and a refit with each cervical width cell centred within (level, branch), all per class; h_post's SD in mm by class; facing minus far across a disc for T2-T9, T10-T12 and L1-L4 and by class; refits on the same spines over T1..L5, T2..L4, T1..L4, T2..L5 and C3..C7 beside C3..L5; the normal-scores gap read two-sided; the share beyond 4 SD on robust z (median and MAD) as a description only; from the repeat units (data/splits/latent-prior-repeat-groups.json, fit part only): ICC(1) as an upper bound with a unit-bootstrap interval, the within-unit SD in mm, the ICC of size-free ratios (endplate over endplate_lower, endplate_depth over endplate_lower_depth, h_post over endplate_depth), each pair's within-unit error correlation, and the corrected same-level r only inside the autoPET 2.5 mm class; the anomaly removals split by reason (L6, T13, no L5) in gold3_prior.py's counts line.
4. Add what the statistics critique asks: external anchors (each level's mean and SD in mm of each measure, so a session can set them beside the card, CT papers and the other population); the model-free plate test (each level's SD of log(endplate over endplate_lower) and of log(endplate_depth over endplate_lower_depth)) and the share of whole spines holding a vertebra whose width or depth ratio is more than 20 per cent off its level's population ratio; a predictive check of the generator as it draws (bordercall schwingcheck/columns.py draw_columns, with its per-column size factor g at SYNTH scale_sd 0.07 and noise_mm 1.0, given the fitted prior and the data's own cell margins), set beside the same aggregates from the data; a unit-resampled bootstrap SE beside the parametric Gaussian null for the primary statistics.
5. Covariates (sex, stature) are deferred: they need the covariates join's per-person table on the grid and its guard against differencing within-sex aggregates across reports. The note says so and says when they would be added.
6. Reserve safety (scope critique 2.2): population_parts returns each part's kept raw ids and units; every reader in the check filters by those ids before any statistic is computed; a test that runs without numpy shows that a test-reserve study's rows change no line.
7. A check failure never fails the fit: the job's exit stays what the fit gives today; the check prints '<population> C3..L5 check: fault at S<n>, an error of the kind <Kind>' and the run goes on.
8. Report shape: every check line starts '<population> C3..L5 check: '; at most 196 characters with the '- ' the sbatch adds; a space after every colon; no slash; no run of five or more digits; no run of eight or more hex characters except the one 16-hex code stamp; no date written YYYYMMDD (the null's seed is never printed); none of the words patient, institution, operators, physician, accession; nothing after FAILED but 'an error of the kind <Kind>'. The whole report (today about 125 lines) stays at or under 380 lines and 60,000 bytes: the check takes at most about 160 lines for enhance_pet and 90 for totalsegmentator, and verse prints one 'not run' line.
9. Vendoring: grid/prior/schwingcheck holds bordercall's files at the commit grid/prior/VENDORED names (8ae5db9), held to their hashes by tests/test_gold3_prior.py. Never edit them in place. If the predictive check needs columns.py, vendor it from that same commit with its sha256 in VENDORED, provided its imports resolve inside the vendored package; if it cannot be vendored cleanly, write the predictive check's lines as not run with the reason, and do not reimplement the generator.
10. Research and memory ride in the same pull request: docs/research/gold3-prior-check/README.md (opening with its source: this thread, 2026-10-31, the design workflow and its three critiques) and READING.md, the reading guide, with READING.md.sha256 beside it; one line in docs/research/README.md; docs/memory/the-correlation-prior.md corrected to say that R_measure is a level-whitened separable quantity, not the same-level correlation, and that its measure part waits on this check, with its MEMORY.md index line updated. python3 flows/stage_registry.py check must still pass with a READING.md that belongs to no flow.
11. Repository rules (CLAUDE.md and .claude/rules/): ASCII and LF under docs/, tools/, grid/ and .github/; plain prose that says why; short functions with names that read as English; no new dependencies (numpy is on the grid's interpreters; CI's Python has no numpy, so numpy tests use skipUnless as tests/test_gold3_prior.py does); the job runs on Python 3.8 or later.`

const SPEC_SCHEMA = { type: 'object', properties: {
  spec_path: { type: 'string' }, reading_path: { type: 'string' },
  vendoring: { type: 'string' }, line_budget: { type: 'string' },
  deferred: { type: 'array', items: { type: 'string' } },
  open_questions: { type: 'array', items: { type: 'string' } } },
  required: ['spec_path', 'reading_path', 'vendoring', 'line_budget', 'deferred', 'open_questions'] }

const GAPS_SCHEMA = { type: 'object', properties: {
  gaps: { type: 'array', items: { type: 'object', properties: {
    item: { type: 'string' }, status: { type: 'string', enum: ['addressed', 'deferred', 'missing', 'wrong'] }, note: { type: 'string' } },
    required: ['item', 'status', 'note'] } },
  edits_made: { type: 'array', items: { type: 'string' } }, verdict: { type: 'string' } },
  required: ['gaps', 'edits_made', 'verdict'] }

const IMPL_SCHEMA = { type: 'object', properties: {
  files_changed: { type: 'array', items: { type: 'string' } },
  tests_run: { type: 'array', items: { type: 'object', properties: { command: { type: 'string' }, result: { type: 'string' } }, required: ['command', 'result'] } },
  report_lines: { type: 'string' }, notes: { type: 'array', items: { type: 'string' } },
  unfinished: { type: 'array', items: { type: 'string' } } },
  required: ['files_changed', 'tests_run', 'report_lines', 'notes', 'unfinished'] }

const FINDINGS_SCHEMA = { type: 'object', properties: {
  findings: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string' }, severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
    file: { type: 'string' }, line: { type: 'integer' }, problem: { type: 'string' },
    evidence: { type: 'string' }, fix: { type: 'string' } },
    required: ['id', 'severity', 'file', 'problem', 'evidence', 'fix'] } },
  checked: { type: 'array', items: { type: 'string' } } },
  required: ['findings', 'checked'] }

const FIX_SCHEMA = { type: 'object', properties: {
  fixed: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, how: { type: 'string' } }, required: ['id', 'how'] } },
  not_fixed: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, why: { type: 'string' } }, required: ['id', 'why'] } },
  tests_run: { type: 'array', items: { type: 'object', properties: { command: { type: 'string' }, result: { type: 'string' } }, required: ['command', 'result'] } } },
  required: ['fixed', 'not_fixed', 'tests_run'] }

const VERIFY_SCHEMA = { type: 'object', properties: {
  passed: { type: 'boolean' },
  checks: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, result: { type: 'string' }, evidence: { type: 'string' } }, required: ['name', 'result', 'evidence'] } },
  remaining_problems: { type: 'array', items: { type: 'string' } } },
  required: ['passed', 'checks', 'remaining_problems'] }

phase('Spec')
const spec = await agent(`${CTX}

${DECISIONS}

Your task: write the implementation spec for the trimmed check, and the reading guide.
Read the design JSON, the critique dump, the prototypes (judge/check_proto.py, judge/lines_proto2.py), the statistics critic's matched truths (review/limit_stats.jsonl, review/rule_on_matched.jsonl and the files they cite), SchwingNet grid/prior/gold3_prior.py, grid/prior/schwingcheck/correlation.py, grid/morphometry-prior.sbatch, grid/gate.sh's word_morphometry_prior, grid/report-shapes.awk, grid/shape-words.awk, grid/redact.sed, tests/test_gold3_prior.py, data/gold3-ct/enhance-pet/facts.jsonl's keys, data/splits/latent-prior-repeat-groups.json, and bordercall's schwingcheck/columns.py at commit 8ae5db9 (git -C /home/claude/bordercall show 8ae5db9:schwingcheck/columns.py) and the morphometry row keys (bordercall morphometry/measure.py, anatomy.py, __main__.py) for slice_mm, canal_ap, canal_w and flag:body_foramina.
Write ${S}/SPEC.md: for each computation, its inputs (which rows, which ids, after which filters), its exact formula, its null or interval where it has one, and the exact report lines it prints with an example line and its length; the functions and files to add or change, with signatures; how population_parts returns the members; the vendoring decision for columns.py with the reason (confirm it resolves inside the vendored package, and how tests/test_gold3_prior.py checks VENDORED); the gate and sbatch changes; the tests to write, each with what it plants and what it asserts, including synthetic truths taken from the critic's matched-truth families so the tests check the signatures the guide relies on; the research note's outline; the memory change; and a line budget table per population with the measured or estimated count.
Write ${S}/READING.md, the reading guide in plain prose: the primary contrasts, how each hypothesis shows in the lines jointly (using the matched truths' signatures, with their numbers and the files they come from), what a reading leads to (keep the measure part held, point at the measures, the neck, the protocol, the generator's size factor), the statement that greg makes each choice, and what the check cannot settle. It is the draft of the repository's docs/research/gold3-prior-check/READING.md.
Return the two paths, the vendoring decision, the line budget, what is deferred and any open question you could not settle by reading.`, { label: 'spec', phase: 'Spec', schema: SPEC_SCHEMA })
if (!spec) { return { error: 'spec agent returned nothing' } }
log(`spec at ${spec.spec_path}; vendoring: ${spec.vendoring}`)

phase('Spec critic')
const gaps = await agent(`${CTX}

${DECISIONS}

Your task: an adversarial completeness check of the spec ${spec.spec_path} and the reading guide ${spec.reading_path}.
Go through every problem in the critique dump (${args.critiques}), blocking, major and minor, and every 'missing' item in the design JSON's critiques, and mark each one addressed (say where in the spec), deferred (with the reason the decisions give), missing or wrong. Check that the spec's line budget is believable (count the lines it specifies per population), that every example line obeys decision 8, that nothing reads a test-reserve study, that no statistic depends on anything the job cannot read on the grid, and that the reading guide's signatures are quoted correctly from the critic's files.
Where something is missing or wrong, edit the spec or the guide yourself to fix it, keeping within the decisions, and list each edit. Return the item list, your edits and a one-line verdict.`, { label: 'spec-critic', phase: 'Spec critic', schema: GAPS_SCHEMA })
log(`spec critic: ${gaps ? gaps.verdict : 'no result'}`)

phase('Build')
const impl = await agent(`${CTX}

${DECISIONS}

Your task: implement the spec ${spec.spec_path} (as the critic left it; its notes: ${gaps ? JSON.stringify(gaps.edits_made) : 'none'}) in /home/claude/SchwingNet, on the branch claude/project-thread-dazoi0, leaving every change uncommitted in the working tree.
Write grid/prior/prior_check.py and the changes to gold3_prior.py, the sbatch, the gate, VENDORED (only if the spec vendors columns.py), the tests, docs/research/gold3-prior-check/README.md, READING.md (from ${spec.reading_path}, corrected to what you built) with READING.md.sha256 (sha256sum's format, matching the final file), the docs/research/README.md line, docs/memory/the-correlation-prior.md and its MEMORY.md line.
Then run, from /home/claude/SchwingNet: python3 -m unittest tests.test_gold3_prior tests.test_gold3_prior_check -v (with numpy; it is installed in this container's python3, check with python3 -c 'import numpy'), the gate's sbatch test in tests/test_gate.py (find its name and run that test alone, then the whole module), python3 tools/check_docs.py, python3 flows/stage_registry.py check, and a synthetic end-to-end run: build a rows tree for enhance_pet and totalsegmentator from the test helpers at a realistic size (enhance_pet about 850 kept studies with repeat units and the three sites' slice classes, totalsegmentator about 85), run gold3_prior.py with the default number of draws, time it, count the report lines and bytes, and pipe the lines through 'awk -f grid/shape-words.awk -f grid/report-shapes.awk' (read the gate to see exactly how it calls them) and 'sed -r -f grid/redact.sed', diffing to show no line changes. Fix what fails. Keep functions short and ASCII only.
Return the files changed, every command with its result, the report's line and byte counts and run time, notes, and anything unfinished.`, { label: 'build', phase: 'Build', schema: IMPL_SCHEMA })
if (!impl) { return { spec, gaps, error: 'build agent returned nothing' } }
log(`built: ${impl.files_changed.length} files; ${impl.report_lines}`)

const LENSES = [
  { key: 'statistics', prompt: `the statistics lens: does every computation in grid/prior/prior_check.py compute what the spec and the line say (standardisation, the flip-flop refits, sub-range refits on the same spines, the nulls and their seeds, the unit bootstrap, ICC(1) with unequal group sizes, the within-unit error correlation, the disattenuation inside the 2.5 mm class only, the within and between decomposition, centring within (level, branch), normal scores with ties, robust z, the log-ratio SDs and the 20 per cent share, the predictive check's draw through draw_columns with g and noise), and does the reading guide read the lines the way the matched truths support? Reproduce each finding by running the code on a small synthetic case where you can.` },
  { key: 'safety', prompt: `the safety and report-shape lens: can any test-reserve or held study reach any line other than the held-out score line; does every reader filter by the kept ids; can any line carry a study id, a unit, a person key, a path, a per-spine value or a count small enough to single out a person (a cell under 10 must print n/a); does every line survive grid/shape-words.awk, grid/report-shapes.awk and grid/redact.sed unchanged as the gate calls them (read the gate); the line and byte budget at the realistic synthetic size; the exit codes (a check fault never fails the fit); the sbatch's git archive list and the gate's path list at the commit; Python 3.8 compatibility (no 3.9+ syntax or APIs); the run time inside the job's 2 hours with 2 CPUs and 8G.` },
  { key: 'rules', prompt: `the repository-rules and tests lens: do the tests plant what they claim and assert the signatures the reading guide relies on; do the numpy tests skip cleanly without numpy and does the reserve test run without numpy; are VENDORED and its hash test right if columns.py was vendored; do docs/research/gold3-prior-check/README.md and READING.md open with their source, say what is not known, quote numbers with the files they come from, avoid overclaiming (decision 1), and match READING.md.sha256; is docs/research/README.md's line there; is the memory file corrected and its MEMORY.md line updated within the index's limits; ASCII and LF everywhere; plain prose; no file referred to that does not exist; python3 tools/check_docs.py and python3 flows/stage_registry.py check pass.` },
]

phase('Review')
const reviews = await parallel(LENSES.map(l => () => agent(`${CTX}

${DECISIONS}

The spec is ${spec.spec_path} and the reading guide draft ${spec.reading_path}. The build agent reported: ${JSON.stringify(impl).slice(0, 6000)}
Your task: review the uncommitted changes in /home/claude/SchwingNet (git -C /home/claude/SchwingNet diff, and git status for new files) through ${l.prompt}
Report only findings you reproduced or can show with exact lines; say what you checked that held. Do not edit any file.`, { label: `review:${l.key}`, phase: 'Review', schema: FINDINGS_SCHEMA })))
const findings = reviews.filter(Boolean).flatMap((r, i) => r.findings.map(f => ({ ...f, lens: LENSES[i] ? LENSES[i].key : 'unknown' })))
log(`review: ${findings.length} findings (${findings.filter(f => f.severity !== 'minor').length} blocking or major)`)

phase('Fix')
let fix = null
if (findings.length) {
  fix = await agent(`${CTX}

${DECISIONS}

The spec is ${spec.spec_path}. Reviewers found these problems in the uncommitted changes in /home/claude/SchwingNet:
${JSON.stringify(findings, null, 1)}
Your task: confirm each finding against the code yourself; fix every one that holds, blocking and major first, minors where the fix is small and safe; refuse any that does not hold, saying why. Keep within the decisions. Then rerun the test modules, the gate's sbatch test, python3 tools/check_docs.py, python3 flows/stage_registry.py check and the synthetic end-to-end run with its line, byte and shape checks, and fix what fails. If you change READING.md, regenerate READING.md.sha256. Leave everything uncommitted.`, { label: 'fix', phase: 'Fix', schema: FIX_SCHEMA })
}

phase('Verify')
const verify = await agent(`${CTX}

${DECISIONS}

Your task: an independent final check of the uncommitted changes in /home/claude/SchwingNet before a person commits them. Do not trust earlier reports; run everything yourself:
- python3 -m unittest tests.test_gold3_prior tests.test_gold3_prior_check -v with numpy, and again with numpy hidden (for example a python3 -c that inserts a meta path finder refusing numpy before running unittest) to show the numpy tests skip and the reserve test still runs;
- the gate's sbatch test and the whole of tests/test_gate.py;
- python3 tools/check_docs.py; python3 flows/stage_registry.py check; python3 flows/stage_registry.py frozen --base origin/main --repo .;
- sha256sum -c inside docs/research/gold3-prior-check for READING.md.sha256;
- a synthetic end-to-end run at the realistic size (enhance_pet about 850 kept studies with repeat units and the three sites' slice classes, totalsegmentator about 85, verse 3), with the default draws: its run time, the report's line count (at most 380) and bytes (at most 60,000), the longest line (at most 196 with '- '), and the gate's own shape pipeline leaving every line unchanged;
- a reserve probe: plant extreme values in a test-reserve study's rows and show the report is byte-identical apart from the timing line;
- grep the diff for non-ASCII bytes and CRLF;
- git -C /home/claude/SchwingNet status and diff --stat, listing every changed file.
Fix nothing: report each check's result with its evidence, whether the whole passes, and every remaining problem.`, { label: 'verify', phase: 'Verify', schema: VERIFY_SCHEMA })

return { spec, gaps, impl, findings, fix, verify }