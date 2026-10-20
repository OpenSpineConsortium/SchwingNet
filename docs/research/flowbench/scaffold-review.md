# flowbench: the adversarial review of the scaffold

Source: the thread "Agentic workflow benchmarks" of the project symphony,
2026-10-16. Before the harness left this repository, a reviewer agent of
that thread read it adversarially at symphony-template commit 0e7b000,
where it lived under docs/research/flowbench/scaffold/. The reviewer's
report was kept only in the session that ran it, so its findings and the
answer to each are written down here, checked against
OpenSpineConsortium/flowbench at a7fce3c, where the harness now lives. No
Claude Doc or artifact. A file named here without a repository is
flowbench's.

## What the review covered

The scaffold's 81 tests under Python 3.13 and 3.12; fake runs of all
three arms (solo, script with two builders, symphony) through the
commands flowbench's README gives, and a report over them; the task
reader over all 2,519 task files of SWE-bench/swe-bench-tasks at 3d07b46;
the swebench 5.0.2 package, read for its command line, its reporting and
its image building; and the installed Claude Code command line, read for
its flags. No real agent ran and no image was pulled.

It raised two blocking findings, eighteen to fix and eleven nits.
symphony-template#96 answered them, merged as cd1920a, and flowbench#1
carried the answers into flowbench with only their paths changed. Five
are answered only in part; the last section lists them.

## Blocking

1. The scorer passed `--task-repo` to `swebench eval` on every score.
   Given it, the harness rebuilds the instance's image before scoring: it
   removes the very tag the run had pulled and retagged, builds from the
   task's Dockerfile, which needs the network and many minutes, and falls
   back to the published image, from Docker Hub rather than
   mirror.gcr.io, when the build fails. The agents would have worked in
   one image and been scored in another, the scorer's timeout and the
   plan's survey estimate assumed no build, and the first smoke test had
   passed only by the fallback. Answered: score.py compiles the task
   repository once into the parquet files the harness reads (`score.py
   build`, which runs `swebench dataset build`) and scores from that
   dataset with no `--task-repo`, so the harness finds the image the
   agents worked in under its own name; the gold patch of
   astropy__astropy-12907 scored resolved by that route with no build.
   PARITY.md row 4, DESIGN.md, the README and this repository's memory
   fact (docs/memory/swe-bench-runs-from-github-and-pypi.md) were
   corrected, and flowbench's CLAUDE.md makes the route a rule.
2. A prediction that does not apply leaves the harness no report for the
   instance, which its summary then counts among its errors, and the
   scorer took that for a harness error, leaving the run out of the arm's
   count. That is the script arm's likeliest failure, a merge left half
   resolved, so its rate would have been inflated. Answered: score.py
   reads the instance's run_instance.log for the harness's marker of a
   patch that did not apply and records the reason patch_failed, not
   resolved and counted against the arm; only the summary's
   infrastructure failures and its other errors are the harness's
   (HARNESS_FAILURE_REASONS), checked in an order where every reason can
   be reached; tests/test_score.py covers both.

## To fix

1. Leaks were kept out by the prompts' words alone: the agents run on the
   host, with permissions bypassed, beside the task repository's
   checkout, the other runs' directories and the network. Answered in
   part: the audit (run.py, audit_streams and forbidden_for) reads every
   agent's stream, excludes and names a run whose agents named the task
   repository's path or name or the gold or test patch, and records a
   hidden test's name and every network command; PLAN.md and PARITY.md
   row 11 now say the checkout is never named to an agent and the audit
   holds them to it, where they said no agent could read it.
2. Every agent loaded the login's user settings, hooks, plugins and user
   MCP servers, and nothing pinned the effort the design holds equal.
   Answered: claude_command passes `--setting-sources project`,
   `--strict-mcp-config` with an empty server list, `--effort` (medium
   unless named) and `--disallowedTools WebFetch,WebSearch,Task,Agent`,
   and each agent's record keeps the tools and MCP servers its stream's
   first event lists. In part: the audit does not yet refuse a run whose
   tools go beyond that set.
3. As root, claude refuses bypassPermissions unless IS_SANDBOX=1, which
   the session happened to set, and of the variables that bill something
   other than the login only ANTHROPIC_API_KEY was dropped. Answered: the
   preflight refuses a real run as root without IS_SANDBOX=1 and says
   why, and agent_environment drops ANTHROPIC_API_KEY,
   ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL and the Bedrock, Vertex and
   Foundry switches (BILLING_VARIABLES).
4. Files the image already held untracked would come out of the patch as
   new files, which the harness's git apply refuses. Answered: prepare
   writes each such file into the workspace's .git/info/exclude
   (exclude_from_patch), with test and tool caches, .orig and .rej, and
   git runs with core.fileMode=false, as the harness's own diff does.
5. Builders worked in git worktrees, which hold none of the image's
   untracked build products and whose .git file names a host path no
   container mounts. Answered: make_builder_copies gives each builder a
   whole copy of the workspace on a branch of its own with a container of
   its own, and collect_builders fetches the branches into the workspace
   before the stack stage, naming a builder that left work uncommitted;
   the real-image rehearsal with two builders ran this way.
6. Timeouts and a turn cap of 200 counted as orchestration failures, and
   the cap contradicted PLAN.md's "no turn cap". Answered: status_of
   tells a timeout and a turn limit apart, the record and the report
   count both apart from orchestration failures, and the default cap is
   none.
7. A failure while preparing left a directory the report skipped, an
   instance whose attempts all failed left the count silently, and
   requeue had no limit. Answered: write_failed_prepare writes a result
   and an audit naming the harness error; `report.py --instances` gives
   the rate over the sample, an instance with no clean scored run
   counting as not resolved, beside the rate over the runs finished; and
   requeue stops at three attempts.
8. A lane could die with its item stuck as running: reading the task sat
   outside the error handling and a docker timeout was not caught.
   Answered: the lane takes any failure of a run as that item's harness
   error and goes on, docker timeouts become RunError, and `backlog.py
   reset --lane` puts a dead lane's running items back.
9. Containers, workspaces and worktrees were never removed, and the image
   pull-ahead and removal the documents described were not built.
   Answered: prepare removes the containers it started when a later step
   fails; finish removes the containers, the workspace and the builders'
   copies unless `--keep`; a lane pulls each image when it first needs
   it, `run.py pull` pulls ahead, and `--remove-image` removes an image
   once the backlog no longer needs it.
10. A parallel stage's agents share one workspace and one container, so
    their test runs can collide and a reviewer can read another's
    findings. Answered by record rather than code: PARITY.md row 16 says
    so with the reason (a reviewer reads the shared change, and a copy
    per reviewer costs a copy of the repository per agent), the review
    and verify prompts tell each agent to change nothing and to read no
    other agent's files, and every stream is kept, so interference would
    show.
11. A subagent's tokens live in a transcript of their own, and a solo
    agent that spawns reviewers is no longer one agent. Answered: the
    Task and Agent tools are off for every agent of every arm.
12. An agent with no stream fell out of the token total, and the cost
    still read as estimated from tokens. Answered: record.py counts it
    as agents_uncounted and leaves the output unknown, and the report
    takes such a run's tokens as unknown.
13. The review table counted the solo arm, and its test passed with the
    fault present because its records lacked the stages run.py writes.
    Answered: report.py counts only runs that ran a review stage, and
    the tests' records carry their stages.
14. PLAN.md's analysis promised what report.py did not compute.
    Answered: report.py gained the rate over the sample, tokens per
    resolved instance and the paired token ratio with a bootstrap over
    repositories, PLAN.md's primary cost comparison; PLAN.md's
    "Analysis, in report.py as it stands" lists what it computes and
    names what it does not (tokens by kind, time blocked, the gate's
    check failures) as outside this run's analysis unless added before
    the first real run.
15. The order visited the strata by name, so a small sample was the
    alphabetically first strata (no sympy and no scikit-learn among the
    first eight), and PLAN.md called n = 8 never significant. Answered:
    tasks.py's order visits the strata in an order drawn from the seed,
    which makes the first eight pytest-7490, sphinx-11445,
    matplotlib-24149, django-14752, scikit-learn-14894, astropy-12907,
    django-12708 and pylint-7080; PLAN.md now says an exact McNemar test
    at n = 8 reaches p < 0.05 when six or more instances are discordant,
    all one way.
16. The record named no scorer version and no commits. Answered:
    provenance_of records the harness's version, the task repository's
    commit and flowbench's own.
17. A second review round would have overwritten the first's findings.
    Answered: findings are written as findings-<stage>-<lens>.json, read
    back with their stage, and the record counts review rounds.
18. A usage limit was recognized by one phrase of the result text, which
    missed "You've hit your limit". Answered: status_of classifies on the
    result's subtype as well as a wider set of phrases, and a usage limit
    or a failed login is the harness's failure, not the arm's.

## Nits

All eleven answered: the harness's report path in DESIGN.md; `--option
builders=K` in place of a flag that does not exist; PARITY.md row 7
naming both limits, 45 minutes per agent and 120 per run; the patch's
base said to be the commit the workspace starts at, under the image's
build commit (PARITY.md row 3); the run token's line stripped from each
agent's kept result text (strip_token), with the bundle, once built,
dropping that text; a lock on the event log's counter; the test command
as a wrapper script per container in place of a quoted one-liner
(write_wrapper); an exclusion for a folder nothing makes, dropped; the
build prompt saying what an empty branch name means; the report saying
when an arm has no bootstrap interval and naming each arm's cost
sources; and the memory fact corrected with the first blocking finding.

## Found sound

The tests on both Pythons and every file ASCII and LF; the fake runs'
records complete and consistent, the patch holding only the change, and
no prompt naming the task repository or a gold patch; the scorer's
flags, summary file and report path matching swebench 5.0.2, with one
run id per attempt as its cache requires; the task reader over every
task file (the pool of 93 in both Verified and Lite, 19 strata); the
review prompt the same text in the script and symphony arms; the Wilson
interval, the exact McNemar test and the bootstrap over repositories;
tokens counted once per message and prices equal to coordbench's; the
backlog's take serialized by a file lock, its four-lane race test
passing; containers that see only the workspace; and no credential
anywhere.

## Checking the scorer on a gold patch

The known-good check, which the plan's survey step repeats for every
instance before an agent meets it: a prediction file of one line whose
instance_id is the instance, whose model_name_or_path is any name
(flowbench-gold-none was used) and whose model_patch is the task's
gold.patch, scored from a directory of its own by the route score.py
takes:

    swebench dataset build <checkout of SWE-bench/swe-bench-tasks> -o data
    swebench eval data/SWE-bench_Verified -p prediction.jsonl \
        --run-id gold -i astropy__astropy-12907 -j 1 -t 1800

On 2026-10-16 that scored astropy__astropy-12907 resolved, with no
infrastructure failure, no error and no image build.

## Open after the answers

- Nothing stops an agent on the host route from reading the task
  repository's checkout or reaching the network: the audit excludes a
  run whose agents named the checkout or a patch, but a read that names
  neither passes, and network commands are recorded, not refused. The
  review's remedy, a checkout the agents' user cannot read, is not
  built.
- The record keeps each agent's tools and MCP servers, but the audit
  does not refuse a run whose tools go beyond the allowed set.
- A parallel stage's agents still share one workspace, by the arms'
  design (PARITY.md row 16); the pilot's transcripts will show whether
  they disturb each other.
- The run's 120-minute limit is checked between stages, so a run can
  overrun it by up to one stage; the documents do not say so yet.
- PLAN.md does not yet say that equal allocation weighs a stratum of one
  instance as much as the largest, which the review asked it to.
