# Field metrics

OpenSpineConsortium/coordbench measures ways of coordinating coding agents on CooperBench's task pairs, this template's claim protocol among them. Field metrics measure the same protocol where it is really used, in this repository, so the benchmark's numbers can be set beside what happens in practice. Only aggregates are kept: counts, durations, outcome rates, what the work cost in tokens and estimated dollars, what it did in tool calls, reads and context, and how often each kind of communication error appears. No code, no text, no title, no login, no session link, no file name, no branch name and no repository name ever goes into the files, and nothing leaves the repository unless the repository installed the Symphony App, whose collector reads two files and nothing else. Sharing is on by default and has one switch, below.

Two pieces do the work, both in tools/metrics.py:

- `collect` runs every day in .github/workflows/metrics.yml, with GitHub's own GITHUB_TOKEN and no other secret, and writes METRICS.json to the branch `metrics`, with PROFILE.json beside it, the sums of the sessions' and runs' profiles, which the collector does not read (The profile's sums, below).
- `judge` runs only when a maintainer runs it, on their own machine, with their own gh and their own Claude Code on their own subscription, and writes JUDGE.json, which `--push`, or `push` afterwards, adds to the same branch.

## What is computed, and from where

The window is the 30 days that end when the run starts. "The window's pull requests" are those GitHub changed in it: created, merged, closed, reviewed, commented on or pushed to. Everything is read from GitHub's REST API, and every identity, number and text the code reads stays in the run's memory.

| Key | What it is | Read from |
| --- | --- | --- |
| counts.claims | Distinct issues N with a pull request from `claude/N` among the window's, or a branch `claude/N` whose head commit was made in the window | /pulls, /branches, /commits/{sha} |
| counts.pull_requests_opened | Pull requests created in the window | /pulls |
| counts.merged | Pull requests merged in the window | /pulls |
| counts.closed_unmerged | Pull requests closed without a merge in the window, among them a released claim's, which GitHub closes when the board renames its branch (docs/agents/PROTOCOL.md, Release) | /pulls |
| counts.reviews | Reviews submitted in the window on the window's pull requests, by anyone but the pull request's author (GitHub files an author's reply in a review thread as a review of their own); a reply in a review thread by anyone else is filed as a review too, and counts as one | /pulls/{n}/reviews |
| counts.changes_requested | Those reviews that asked for changes and still stand: a changes-request dismissed since shows as dismissed, and is not counted | /pulls/{n}/reviews |
| counts.check_runs_passed | Check runs that finished in the window, with the conclusion success, on the commits of the window's pull requests that were made in the window, every attempt on each (GitHub lists the latest attempt of each check alone unless asked for all, which would hide a failure behind its re-run) | /pulls/{n}/commits, /commits/{sha}/check-runs?filter=all |
| counts.check_runs_failed | The same with the conclusion failure or timed_out; neutral, skipped, cancelled, stale and action_required count as neither | /pulls/{n}/commits, /commits/{sha}/check-runs?filter=all |
| counts.conflicts_seen | Pull requests seen in conflict with the default branch: open ones GitHub reports as `dirty` now, and any the board's "main moved" comment called conflicting in the window (a pull request only behind is no conflict) | /pulls/{n}, /issues/comments |
| counts.released_claims | Claims released in the window, by the coordinator's release comments: those whose first line is `<!-- sdlc-coordinator: claim-released -->` (the coordinator's step in the board's run, docs/agents/PROTOCOL.md, Release), whoever wrote them, and only that line is looked for. A release comment on an issue that had another less than a day before is the same release said again, and counts once | /issues/comments |
| counts.contributors | How many different people did something in the window on its pull requests: created one, submitted a review on one, or made a commit on one, by its author or committer date; a pull request enters the window on any change, so each person is dated by their own act, not by the pull request's. Apps and bots are left out, and a commit with no GitHub account counts by its author's email, so an agent that commits under one name counts once | /pulls, /pulls/{n}/reviews, /pulls/{n}/commits |
| durations_seconds.claim_to_first_pull_request_median, _p90 | From each claim to its first pull request opened in the window | /pulls/{n}/commits |
| durations_seconds.open_to_merge_median, _p90 | From opening to merging, for pull requests merged in the window | /pulls |
| durations_seconds.first_review_median, _p90 | From opening to the first review by someone other than the author, for pull requests opened in the window that have one | /pulls/{n}/reviews |
| rates.merge_rate | merged / (merged + closed_unmerged) | the counts |
| rates.first_check_pass_rate | Of the pull requests opened in the window, the share whose first head commit's counted check runs all passed, every attempt among them, so a check that passed only when run again did not pass first | /pulls/{n}/commits, /commits/{sha}/check-runs?filter=all |
| parallel.people | People who opened the pull requests the breakdown counts (those that ended in the window, and those open now that were opened or given a commit in it); apps and bots left out. counts.contributors counts commit identities too, among them the account claude every Claude Code cloud session commits as | /pulls, /pulls/{n}/commits |
| parallel.sessions, sessions_per_person_max | Claude Code sessions named on those pull requests (below), and the most named on one person's | /pulls, /pulls/{n}/commits |
| parallel.pull_requests_with_session, _without_session, _multi_session | Of those pull requests, the ones that name a session, none, and two or more | /pulls, /pulls/{n}/commits |
| parallel.sessions_across_people | Sessions named on more than one person's pull requests; 0 unless a session's line reached another person's work | /pulls, /pulls/{n}/commits |
| parallel.peak_parallel, peak_parallel_people, peak_sessions_one_person | The most people's pull requests at work at one moment of the window, the most people with one at work at one moment, and the most sessions of one person at work at one moment (pull requests sharing a session count once; those naming none are left out) | /pulls, /pulls/{n}/commits |
| parallel.conflict_marks, conflict_marks_unattributed | The board's conflicting main-moved comments posted in the window by an app or a bot, and those naming no merge the run listed (a direct push, or one older than the look-back) | /issues/comments, /pulls |
| parallel.open_conflicting, open_conflicting_drafts, open_conflicting_dirty | Open pull requests opened or given a commit in the window that GitHub calls unmergeable (mergeable false), the drafts among them, and those it calls dirty, the one state counts.conflicts_seen reads | /pulls/{n}, /pulls/{n}/commits |
| parallel.truncated | Pull requests that ended in the window whose work began before the look-back, so what was at work beside them before it was not read | /pulls/{n}/commits |
| parallel.files_unread | Pull requests whose changed files were needed and left unread to keep the board's reserve; while it is not 0, every count that needs them is null | /pulls/{n}/files |
| by_setting.SETTING.pull_requests | The pull requests of that work setting that ended, merged or closed, in the window | /pulls |
| by_setting.SETTING.merged, closed_unmerged | Of them, those merged and those closed without a merge; over the eight settings they add up to counts.merged and counts.closed_unmerged | /pulls |
| by_setting.SETTING.open | The setting's pull requests open now and opened or given a commit in the window, set by what was at work beside them so far; not among pull_requests | /pulls, /pulls/{n}/commits |
| by_setting.SETTING.conflicted | Of pull_requests, those an app's or a bot's main-moved comment called conflicting, at any time since the look-back's start | /issues/comments |
| by_setting.SETTING.released | Of pull_requests, those from claude/N whose issue N got a coordinator release comment while they were at work | /issues/comments |
| by_setting.SETTING.changes_requested | Of pull_requests, those with a standing changes request by someone other than their author | /pulls/{n}/reviews |
| by_setting.SETTING.claim_branches | Of pull_requests, those from a claude/N branch | /pulls |
| by_setting.SETTING.partners | People's pull requests at work beside each, summed | /pulls, /pulls/{n}/commits |
| by_setting.SETTING.work_seconds | Each one's work in seconds, from its start (below) to its merge or close, summed | /pulls, /pulls/{n}/commits |
| by_setting.SETTING.landings_under | Merges into the default branch, any pull request's but one from each one's own branch, while each was open and before the board first marked it conflicting, summed | /pulls, /issues/comments |
| by_setting.SETTING.landings_before_opening | Merges into the default branch, any pull request's but one from each one's own branch, between the start of each one's work and its opening, summed | /pulls, /pulls/{n}/commits |
| by_setting.SETTING.file_overlap | Of pull_requests, those that changed a file a pull request at work beside them changed too; 0 for the settings of apps and bots | /pulls/{n}/files |
| pairs.RELATION.pairs | Two people's pull requests at work together, each pair once, both ended, in the record whose window holds the later end | /pulls, /pulls/{n}/commits |
| pairs.RELATION.both_active | Of them, those in which each got a commit, by its author date, while both were at work | /pulls/{n}/commits |
| pairs.RELATION.file_overlap | Of them, those whose changed files meet | /pulls/{n}/files |
| pairs.RELATION.landings | Of them, those in which the first to end was merged into the default branch, from a branch other than the other's, while the other was open and before the board first marked it conflicting | /pulls, /issues/comments |
| pairs.RELATION.landings_file_overlap | Of the landings, those whose changed files meet | /pulls/{n}/files |
| pairs.RELATION.conflict_onsets | Of the landings, those after which the other's first conflicting mark names the first one's merge commit | /issues/comments, /pulls |
| pairs.RELATION.conflict_onsets_file_overlap | Of the onsets, those whose changed files meet | /pulls/{n}/files |
| economics.prices_as_of | The date of the price table the estimate uses (tools/economics.py, PRICES) | the tool |
| economics.pull_requests, merged | Pull requests of people and of the repository's Claude workflows (workflow_agents) that ended in the window, and of them those merged; automation's are left out | /pulls |
| economics.pull_requests_measured | Of them, those with any usage recorded against them: a Symphony-Usage trailer on one of their commits, or the record of an Actions run that names them or their claim's issue (What the work cost, below) | /pulls/{n}/commits, the usage records |
| economics.sessions | Claude Code sessions whose trailers are on commits made in the window, told apart by the eight characters of the session's id each trailer carries | /pulls/{n}/commits |
| economics.actions_runs, actions_runs_unread | Actions runs whose usage record was made in the window, and records left for the next run (more than 200 new ones, or a download refused, redirected, not HTTP at all, or cut short of the length or the chunks its answer gave); actions_runs_unread is null when the records could not be listed at all, as in a workflow without actions: read or under the board's reserve | /actions/artifacts, /actions/artifacts/{id}/zip |
| economics.tokens_input, tokens_cache_write, tokens_cache_read, tokens_output, tokens_total | The window's bill in tokens: the trailers on the commits made in the window and the runs recorded in it, by kind (cache writes kept five minutes and an hour together) and in all | as above |
| economics.tokens_unpriced | Of tokens_total, those of a model the price table does not know, left out of the estimate | as above |
| economics.estimated_usd | What the bill's tokens would cost at Anthropic's API list prices as of prices_as_of, whatever plan paid for them | as above |
| economics.coordinator_usd | The part of estimated_usd the coordinator workflow spent | the usage records |
| economics.claude_seconds | Seconds Claude was at work on the bill: each session's time between its commits, pauses of more than five minutes left out, and each run's duration | as above |
| economics.commits, check_failures, reverts | The commits of economics.pull_requests, their failed check runs (on their commits made in the window, as counts.check_runs_failed reads them), and the reverts merged in the window, pull requests titled as GitHub's revert button titles them | /pulls/{n}/commits, /commits/{sha}/check-runs?filter=all, /pulls |
| economics.tokens_by_family | tokens_total by model family: fable, opus, sonnet, haiku and other | as above |
| economics.tokens_per_merge, usd_per_merge, claude_seconds_per_merge, commits_per_merge | The bill, and the commits, divided by economics.merged | the keys above |
| coordination.SIDE.pull_requests, merged | economics.pull_requests split in two sides: alone, with no other pull request of a person or of the Claude workflows at work beside it for more than 60 seconds, and parallel, the rest; and of each side those merged | /pulls, /pulls/{n}/commits |
| coordination.SIDE.measured, measured_merged | Of the side's pull requests, those with usage recorded against them, and of those the merged | as economics.pull_requests_measured |
| coordination.SIDE.tokens, estimated_usd, claude_seconds | What the side's measured pull requests cost, each its trailers on any of its commits and the runs that name it; the parallel side adds the coordinator's runs recorded in the window that name none of the window's pull requests, the cost of coordinating | as above |
| coordination.SIDE.commits, check_failures, first_check_passed, first_check_counted | The side's commits and failed check runs, and, of its pull requests whose first check can be told, as rates.first_check_pass_rate tells it, those whose first check passed and how many | as above |
| coordination.SIDE.open_to_merge_median | From opening to merging, the median over the side's merged pull requests | /pulls |
| coordination.SIDE.active_seconds | Seconds at least one of the side's pull requests was at work, from its start (Who worked beside whom, below) to its end, overlaps counted once | /pulls, /pulls/{n}/commits |
| coordination.ratios.tokens_per_merge, usd_per_merge | alone's tokens, or dollars, per measured merge over parallel's: over 1, working in parallel spent less per merged pull request | coordination |
| coordination.ratios.latency | alone's open_to_merge_median over parallel's: over 1, work done in parallel merged sooner after opening | coordination |
| coordination.ratios.throughput | parallel's merges per hour of its active_seconds over alone's: over 1, work done in parallel delivered more per hour at work | coordination |
| coordination.ratios.first_check_pass | parallel's share of first checks passed over alone's: over 1, work done in parallel passed its first check more often | coordination |
| coordination.ratios.commits_per_merge | alone's commits per merge over parallel's: over 1, work done in parallel took fewer commits, fewer rounds of edits, per merge | coordination |
| coordination.ratios.failures_per_pull_request | alone's failed check runs per pull request over parallel's, one added to each side's failures and to its pull requests so a side with none still compares: over 1, work done in parallel failed fewer checks | coordination |

How the choices were made:

- The claim's time. GitHub's REST API never says when a branch was made. A claim branch's first commit adds the claim file and nothing else (docs/agents/PROTOCOL.md), so the claim's time is the earliest author date among the pull request's commits: that commit's. Author dates survive a rebase; committer dates do not.
- The first head commit. GitHub keeps no record of the head a pull request was opened with, so it is the newest of its commits committed by the time it opened, with a minute's grace for a fast clock. When a rebase has replaced them all, the pull request stays out of first_check_pass_rate. On a `claude/N` pull request opened at once, as the protocol asks, the first head is usually the claim commit.
- Check runs. They are read on every commit of the window's pull requests made in the window, not on the head alone: the default branch takes only a pull request whose check passed, so a merged pull request's head is green by construction, and the failures its earlier heads had would never be seen. And every attempt on a commit is read (filter=all), where GitHub's listing shows the latest attempt of each check alone, so a failure that a re-run fixed is still the failure it was.
- Conflicts come from two places because each misses some: GitHub computes `dirty` only for an open pull request and only as it stands now, and the board's comment marks the moment the default branch moved under one. Both are counted once per pull request.
- The budget. A run costs, per pull request of the window, one REST call for its commits, one for its reviews, one for the check runs of each of its commits made in the window, one more for the head it was opened with when that was made before the window, and while it is open one for its detail, or two when GitHub has not computed its mergeability yet; one per claim branch without a pull request in the window; and one per hundred pull requests, branches and comments listed. GITHUB_TOKEN has 1,000 requests an hour for the whole repository, which the board's runs share, so the run reads from each answer how many are left and stops before it would leave fewer than 300 for the board: it says so, with the calls it made and when the hour's budget comes back, writes nothing, and the workflow run fails; the branch keeps its last record, and the next run, the daily one or one by hand once the hour has turned, writes again when it fits. The breakdown reads only after all of that, so it never costs one of those keys: the rest of the pull request listing, through the look-back (the pull requests changed in the window before this one), one call per hundred; one call for the commits of each person's look-back pull request that ended after the earliest start of the window's people's work, finished or open, the only ones that may have been at work beside that work; the look-back's comments, one call per hundred, only when some of the window's work began before the window; and, last, one call for the changed files of each pull request at work beside another, plus one per hundred files. When those changed files would reach the board's reserve they are left unread: the run still writes, the counts that need them are null, parallel.files_unread says how many, and the log line says so. When any other read of the breakdown would reach it, or GitHub fails one, the run writes the record without parallel, by_setting, pairs, economics and coordination, and the log line says so. economics and coordination read after the breakdown, from the units it sorted: one call per hundred artifacts listed, back to the look-back's start, and one call for each usage record not read before, at most 200 a run; a record's file comes from the storage host GitHub redirects to, which costs no call. Under the board's reserve the listing is not made and only the records kept from earlier runs count (economics.actions_runs_unread is null, and the log line says so). The log of a run that fits says how many calls it took. It runs once a day at 03:43 UTC, before OpenSpineConsortium's collector reads the branch at 04:17, by hand from the Actions tab or with `gh workflow run metrics.yml --repo OWNER/NAME`, and on a push to the default branch that changes .github/symphony-metrics (the switch, below).
- Medians are rounded half up to whole seconds; the 90th percentile is the nearest rank, the smallest value at or above nine tenths of them. A wait against the clock (a later event dated earlier) is left out. Rates are rounded to four places. Where a value has nothing to measure it is null.

## What the work cost

Two kinds of run spend tokens on this repository's work, and each leaves what it spent where `collect` can read it with GITHUB_TOKEN alone; neither needs a routine, an API key or a server (tools/usage.py).

- A session, a person's or a routine's, local or in the cloud. .claude/settings.json runs `python3 tools/usage.py hook` before every Bash call; before a `git commit` it reads the session's transcript, and its helpers' beside it, and leaves the usage so far in the clone's git directory. The commit-msg hook, which .claude/hooks/session-start.sh puts in place where the clone has no commit-msg hook of its own, adds what the session spent since its last commit to the commit as one trailer line: `Symphony-Usage: v1 session=a1a1a1a1 seconds=2400 claude-opus-5-5=2100,61000,0,880000,18500`, per model the uncached input tokens, the cache writes kept five minutes and an hour, the cache reads and the output tokens, and the seconds the session was at work between the two commits, pauses of more than five minutes left out. The line travels with the commit, so it needs no API, and `collect` reads it from the pull request's commits. What a session spends after its last commit is on no commit and is not counted; nor is a session in a clone with a commit-msg hook of its own, which is left alone, nor one whose hooks are not this repository's. The same hooks add a second line after it, `Symphony-Profile: v1 session=a1a1a1a1 calls=42 failed=3 repeated=1 reads=12 rereads=4 read_bytes=58210 reread_bytes=9120 peak=181234 compactions=0 drops=0 tool_seconds=95`, the session's profile since its last commit by tools/profile.py: its tool calls, those that failed and those that repeated an earlier call exactly, the files its reads named and those it had read before, with the bytes the reads returned, the largest context of its calls since, its compactions and the context's falls by more than half, and its seconds in tools. It is read by the message's last paragraph alone, where the hook puts it, so a line quoted in a commit's body counts for nothing, and from a pull request's own commits, never from a squash commit, which moves every commit's trailers into its body. `collect` sums it per pull request into PROFILE.json (The profile's sums, below), and none of it reaches METRICS.json or the collector before the Apps' privacy statement lists its keys.
- A run in GitHub Actions: a worker's (.github/workflows/workers.yml), the coordinator's (coordinator.yml) or @claude's (claude.yml). After claude-code-action, the job runs `python3 tools/usage.py actions`, which reads the action's execution file, the Agent SDK's messages, and writes the run's record, which actions/upload-artifact keeps as an artifact whose name starts with symphony-usage-: the workflow and the job, the worker, the issue and the pull request it ran for, its seconds and turns, and its tokens by model, and, where the workflow copied tools/profile.py, tools/economics.py and the protocol library beside the recorder, as the template's workflows do, the run's profile, the same counts as a commit's Symphony-Profile line over the whole run, with no seconds, since the execution file has no clock. Inside Actions the hook and the trailer record nothing, so a run is never counted twice. `collect` lists those artifacts and downloads each record once: .github/workflows/metrics.yml carries the records read so far from one run to the next in GitHub's Actions cache (`--usage-cache`), so each day's run downloads only the new ones (a record a cache from before the profile kept is still counted, and is downloaded again for its profile once the new ones are read, within the same 200, while its artifact lasts), and an artifact lives as long as the repository's artifact retention, 90 days unless it was changed, more than the 60 days a run reads back.

From those, the record keeps two blocks. economics is the window's bill and what it bought: the bill is the trailers on the commits made in the window and the runs recorded in it, and what it bought is the pull requests of people and of the Claude workflows that ended in it. estimated_usd prices the bill's tokens at Anthropic's API list prices as of prices_as_of (tools/economics.py, PRICES), which is what the same work would cost on the API whatever plan actually paid, so it compares months and repositories but is not a subscription's bill; a model the table does not know is counted in tokens_unpriced and priced at nothing. pull_requests_measured beside pull_requests says how much of the work the bill covers: work done outside a session of this repository, or before the hooks were in it, has no usage on it.

coordination compares the same pull requests in two sides: alone, the ones with no other pull request of a person or of the Claude workflows at work beside them, and parallel, the rest, which is what coordination is for. Every ratio is over 1 where working in parallel did better: fewer tokens and dollars per merge (each side's measured pull requests only, so work whose cost is unknown divides nothing), a shorter wait from opening to merge (latency), more merges per hour at work (throughput), more first checks passed, fewer commits per merge and fewer failed checks. The coordinator's runs that name none of the window's pull requests, its planning of epics and its weekly tidy, count on the parallel side, as the price of coordinating. A ratio is null where a side has nothing to divide, as in the sample below, where every pull request of the two-person world had other work beside it. For example, an alone side of 2 merges for 6,000,000 tokens and a parallel side of 3 for 6,000,000 give tokens_per_merge (6,000,000 / 2) / (6,000,000 / 3) = 1.5: working in parallel spent a third less per merged pull request. Read the ratios with the sides' sizes beside them: a side of a handful of pull requests says little, and long-lived pull requests weigh heavily on active_seconds.

## The profile's sums

PROFILE.json is the second step of the research programme in docs/research/beyond-cooperation/: what the work did, beside what it cost. `collect --profile-out`, which the workflow runs, writes it from what it already read for economics and coordination, so it costs no call of its own. A pull request's profile is the Symphony-Profile lines on its own commits, whenever they were made, and the profiles of the Actions runs that name it or its claim's issue, as economics attributes their usage (What the work cost, above): each count summed, and its peak the largest of theirs. A pull request with any line or run that made a call or held any context is profiled; a line or a run whose counts are all 0, as a run that made no API call records, is no profile, as the economics count a pull request as measured only with tokens above 0. As in the economics, a run that names two pull requests, or a commit listed in two, counts in each of them, so a setting's or a side's sums can hold it twice; the coordination block's sides compare the same pull requests, so the ratios do too. The counts are tools/profile.py's, defined in docs/research/beyond-cooperation/README.md, section 4.

| Key | What it is |
| --- | --- |
| sessions | Claude Code sessions whose profile lines are on the commits of the pull requests that ended in the window, told apart by the eight characters each line carries |
| actions_runs | Actions runs whose profiles the sums hold: those that name one of those pull requests, and the coordinator's that count on the parallel side |
| actions_runs_unread | Actions runs whose profiles the sums may be short of, over the whole look-back: METRICS.json's economics.actions_runs_unread, and the runs a cache from before the profile kept without theirs, which are downloaded again only while their artifact is listed and unexpired, so one whose artifact has gone counts here until it leaves the look-back; null when the records could not be listed at all |
| by_setting.SETTING.pull_requests, merged | The pull requests that ended in the window in each of the eight work settings, sorted as METRICS.json's by_setting sorts them, and of them those merged |
| by_setting.SETTING.profiled, profiled_merged | Of them, those with a profile, and of those the merged |
| by_setting.SETTING.calls, failed, repeated | The profiled pull requests' tool calls, those that failed and those that repeated an earlier call in the same transcript exactly, summed |
| by_setting.SETTING.reads, rereads, read_bytes, reread_bytes | The files their reads named and those read before, the bytes the reads returned and those returned by reads that named only files read before, summed |
| by_setting.SETTING.compactions, drops | Their compactions and the falls of the context by more than half, summed |
| by_setting.SETTING.tool_seconds | Their seconds in tools, summed; a run in Actions records none, since its execution file has no clock |
| by_setting.SETTING.peak_median | The median over the profiled pull requests of each one's largest context, in tokens, rounded half up |
| coordination.SIDE.* | The same keys for the two sides METRICS.json's coordination compares, alone and parallel, with the same pull requests on each side; the parallel side adds the profiles of the coordinator's runs that name none of the window's pull requests of people and of the Claude workflows (a run that names only an automation's pull request counts here), as its tokens add their cost |
| coordination.ratios.calls_per_merge, reads_per_merge, rereads_per_merge | alone's calls, reads and re-reads per profiled merge over parallel's: over 1, work done in parallel took fewer per merged pull request |
| coordination.ratios.peak | alone's peak_median over parallel's: over 1, work done in parallel ran in a smaller context |

The file is the repository's own record. The workflow puts it on the branch `metrics` beside METRICS.json, and OpenSpineConsortium's collector does not read it: its keys join METRICS.json only once the Apps' privacy statement (PRIVACY.md in OpenSpineConsortium/symphony-start), the exhaustive list of what the collector keeps, lists them and its site page is live, which is the owner's step. It is written under the same switch and in the same run as the breakdown: with sharing off it says off as METRICS.json does, and a run whose breakdown is left out writes its first four keys alone. It holds counts, bytes, seconds and token counts, and no session's characters and no tool's name. Read it as coordination is read, with the sides' sizes beside it: a side's sums are divided by its profiled merges and never by merges whose profile is unknown, and work done outside a session of this repository, or before the hooks were in it, carries no line. A count a line could not give, past the bound or not a number, is passed over, so it adds nothing to its sum.

## Who worked beside whom

Each pull request is sorted into a work setting by what else was at work beside it and whose that work was, so that one person's several Claude Code sessions, which share one GitHub login, are never pooled with several people.

- The person is the login of the pull request's author. An app's or a bot's pull request is no person's: it is counted under workflow_agents when its branch starts with claude/ (the workers in Actions, the coordinator workflow, @claude) and under automation otherwise, and it is at work beside nobody. A commit's author never stands for a person, since every Claude Code cloud session commits as the account claude.
- A session is named by a whole line of a commit message or of the description. That line is `Claude-Session: https://claude.ai/code/session_ID`, which a cloud session ends its commits with, or the link alone on its line, or the footer `_Generated by [Claude Code](https://claude.ai/code/session_ID)_`, which it ends its descriptions with. A session with no claude.ai link (a local session, a claude -p worker) can name itself with a line `Symphony-Session: TOKEN` of 8 to 64 letters, digits, dashes and underscores of its own choosing. A link inside a sentence names nothing. Two pull requests share a session when they name one in common.
- The work runs from the earliest author date of its commits, or from its opening when that is earlier, to its merge, its close, or now while it is open. An author date more than seven days before the opening is set aside as an old commit carried in. A pull request from a branch whose earlier pull request ended before it opened starts no earlier than that end, because GitHub can list commits the earlier one already landed.
- Two people's pull requests are at work beside each other when their work overlaps by more than 60 seconds, a clock's grace. An open pull request counts only when it was opened or given a commit in the window, and is otherwise beside nobody: the board comments on a pull request behind the default branch or in conflict with it at every push there, which GitHub counts as a change, so one parked for months would else be at work beside everything since it opened.
- The settings are decided in this order: solo, nothing beside it; several_people_and_sessions, beside both another person's work and the same person's work from a session it does not name; one_person_sessions, beside the same person's work from another session; undetermined, beside the same person's work where one of the two names no session, so it could be one session or two; several_people, beside another person's work; one_session, beside only the same session's other pull requests.
- A pair is two people's pull requests at work together. It is counted once, when both have ended, in the record whose window holds the later end, under one of four relations: same_session, one_person_sessions, several_people, undetermined. Its landing is the merge of the first to end into the default branch while the other was open. Its conflict onset is the other's first conflicting mark naming that merge's commit, which the board's marker carries.
- A landing is a merge into the default branch, the one branch the board marks the others against, and never one from a pull request's own branch, which carries its own earlier work: a branch used again starts its next pull request at the earlier one's merge, and that merge is no landing before the next one opened.
- Each setting's counts are over the pull requests that ended in the window, so each pull request counts once, whole, in the 30-day block where it ended. The run reads back one more window (the pull requests changed then, the commits of those that may have been at work beside the window's, and, when the window's work began before it, the comments) to see the part of their life before the window. A pull request GitHub's listing names twice is one pull request here.
- The breakdown's conflicts are the board's marks posted by an app or a bot, matched to the merge they name. counts.conflicts_seen keeps its own rule (any author's mark, and GitHub's dirty), so the two differ.
- The changed files are read last, and only for pull requests at work beside another and those beside them, to see whether their files meet. The names are dropped.

## The files

On the branch `metrics`, which holds METRICS.json, PROFILE.json and JUDGE.json and nothing else. METRICS.json, here with sharing on:

```json
{
  "schema": "sdlc-metrics/1",
  "generated_at": "2026-10-10T12:00:00Z",
  "window_days": 30,
  "sharing": "on",
  "protocol_version": "0.2.0 f530a66",
  "counts": {"claims": 11, "pull_requests_opened": 13, "merged": 11, "closed_unmerged": 1, "reviews": 2, "changes_requested": 1, "check_runs_passed": 0, "check_runs_failed": 0, "conflicts_seen": 4, "released_claims": 1, "contributors": 3},
  "durations_seconds": {"claim_to_first_pull_request_median": 600, "claim_to_first_pull_request_p90": 1472400, "open_to_merge_median": 7200, "open_to_merge_p90": 604800, "first_review_median": 3300, "first_review_p90": 5400},
  "rates": {"merge_rate": 0.9167, "first_check_pass_rate": null},
  "parallel": {"people": 2, "sessions": 4, "sessions_per_person_max": 4, "pull_requests_with_session": 11, "pull_requests_without_session": 1, "pull_requests_multi_session": 2, "sessions_across_people": 1, "peak_parallel": 2, "peak_parallel_people": 2, "peak_sessions_one_person": 2, "conflict_marks": 3, "conflict_marks_unattributed": 1, "open_conflicting": 2, "open_conflicting_drafts": 1, "open_conflicting_dirty": 1, "truncated": 1, "files_unread": 0},
  "by_setting": {
    "solo": {"pull_requests": 1, "merged": 1, "closed_unmerged": 0, "open": 0, "conflicted": 0, "released": 0, "changes_requested": 1, "claim_branches": 1, "partners": 0, "work_seconds": 7200, "landings_under": 1, "landings_before_opening": 0, "file_overlap": 0},
    "one_session": {"pull_requests": 2, "merged": 2, "closed_unmerged": 0, "open": 0, "conflicted": 0, "released": 0, "changes_requested": 0, "claim_branches": 2, "partners": 2, "work_seconds": 11580, "landings_under": 0, "landings_before_opening": 1, "file_overlap": 0},
    "one_person_sessions": {"pull_requests": 3, "merged": 3, "closed_unmerged": 0, "open": 0, "conflicted": 1, "released": 0, "changes_requested": 0, "claim_branches": 3, "partners": 5, "work_seconds": 6814800, "landings_under": 2, "landings_before_opening": 0, "file_overlap": 2},
    "several_people": {"pull_requests": 1, "merged": 0, "closed_unmerged": 1, "open": 2, "conflicted": 0, "released": 0, "changes_requested": 0, "claim_branches": 1, "partners": 1, "work_seconds": 10800, "landings_under": 1, "landings_before_opening": 0, "file_overlap": 1},
    "several_people_and_sessions": {"pull_requests": 1, "merged": 1, "closed_unmerged": 0, "open": 0, "conflicted": 1, "released": 0, "changes_requested": 0, "claim_branches": 0, "partners": 2, "work_seconds": 19800, "landings_under": 1, "landings_before_opening": 0, "file_overlap": 1},
    "undetermined": {"pull_requests": 2, "merged": 2, "closed_unmerged": 0, "open": 0, "conflicted": 1, "released": 1, "changes_requested": 0, "claim_branches": 2, "partners": 2, "work_seconds": 25200, "landings_under": 1, "landings_before_opening": 0, "file_overlap": 2},
    "workflow_agents": {"pull_requests": 1, "merged": 1, "closed_unmerged": 0, "open": 0, "conflicted": 0, "released": 0, "changes_requested": 0, "claim_branches": 1, "partners": 0, "work_seconds": 1500, "landings_under": 0, "landings_before_opening": 0, "file_overlap": 0},
    "automation": {"pull_requests": 1, "merged": 1, "closed_unmerged": 0, "open": 1, "conflicted": 0, "released": 0, "changes_requested": 0, "claim_branches": 0, "partners": 0, "work_seconds": 1800, "landings_under": 0, "landings_before_opening": 0, "file_overlap": 0}
  },
  "pairs": {
    "same_session": {"pairs": 2, "both_active": 1, "file_overlap": 1, "landings": 1, "landings_file_overlap": 1, "conflict_onsets": 0, "conflict_onsets_file_overlap": 0},
    "one_person_sessions": {"pairs": 3, "both_active": 1, "file_overlap": 1, "landings": 2, "landings_file_overlap": 1, "conflict_onsets": 2, "conflict_onsets_file_overlap": 1},
    "several_people": {"pairs": 1, "both_active": 0, "file_overlap": 1, "landings": 1, "landings_file_overlap": 1, "conflict_onsets": 0, "conflict_onsets_file_overlap": 0},
    "undetermined": {"pairs": 1, "both_active": 0, "file_overlap": 1, "landings": 1, "landings_file_overlap": 1, "conflict_onsets": 1, "conflict_onsets_file_overlap": 1}
  },
  "economics": {"prices_as_of": "2026-10-16", "pull_requests": 11, "pull_requests_measured": 6, "merged": 10, "sessions": 2, "actions_runs": 2, "actions_runs_unread": 0, "tokens_input": 9200, "tokens_cache_write": 219000, "tokens_cache_read": 3250000, "tokens_output": 65200, "tokens_total": 3543400, "tokens_unpriced": 0, "estimated_usd": 2.3672, "coordinator_usd": 0.1654, "claude_seconds": 8635, "commits": 16, "check_failures": 0, "reverts": 0, "tokens_by_family": {"fable": 0, "opus": 1927300, "sonnet": 1580900, "haiku": 35200, "other": 0}, "tokens_per_merge": 354340.0, "usd_per_merge": 0.23672, "claude_seconds_per_merge": 863.5, "commits_per_merge": 1.6},
  "coordination": {
    "alone": {"pull_requests": 0, "merged": 0, "measured": 0, "measured_merged": 0, "tokens": 0, "estimated_usd": 0.0, "claude_seconds": 0, "commits": 0, "check_failures": 0, "first_check_passed": 0, "first_check_counted": 0, "open_to_merge_median": null, "active_seconds": 0},
    "parallel": {"pull_requests": 11, "merged": 10, "measured": 6, "measured_merged": 6, "tokens": 4504400, "estimated_usd": 3.2709, "claude_seconds": 10940, "commits": 16, "check_failures": 0, "first_check_passed": 0, "first_check_counted": 0, "open_to_merge_median": 10800, "active_seconds": 6383400},
    "ratios": {"tokens_per_merge": null, "usd_per_merge": null, "latency": null, "throughput": null, "first_check_pass": null, "commits_per_merge": null, "failures_per_pull_request": null}
  }
}
```

protocol_version is the release and short commit of the vendored protocol, from tools/VENDORED's first line. With sharing off the file is this, and nothing more:

```json
{
  "schema": "sdlc-metrics/1",
  "sharing": "off"
}
```

PROFILE.json, for the same world, in which every pull request had other work beside it, so the alone side and the ratios are empty here too; with sharing off it is `{"schema": "symphony-profile-sums/1", "sharing": "off"}` and nothing more:

```json
{
  "schema": "symphony-profile-sums/1",
  "generated_at": "2026-10-10T12:00:00Z",
  "window_days": 30,
  "sharing": "on",
  "sessions": 2,
  "actions_runs": 2,
  "actions_runs_unread": 0,
  "by_setting": {
    "solo": {"pull_requests": 1, "merged": 1, "profiled": 1, "profiled_merged": 1, "calls": 50, "failed": 4, "repeated": 3, "reads": 15, "rereads": 6, "read_bytes": 70000, "reread_bytes": 20000, "compactions": 0, "drops": 0, "tool_seconds": 400, "peak_median": 200000},
    "one_session": {"pull_requests": 2, "merged": 2, "profiled": 1, "profiled_merged": 1, "calls": 30, "failed": 0, "repeated": 2, "reads": 10, "rereads": 4, "read_bytes": 40000, "reread_bytes": 12000, "compactions": 0, "drops": 0, "tool_seconds": 150, "peak_median": 120000},
    "one_person_sessions": {"pull_requests": 3, "merged": 3, "profiled": 2, "profiled_merged": 2, "calls": 100, "failed": 5, "repeated": 2, "reads": 31, "rereads": 7, "read_bytes": 140000, "reread_bytes": 19000, "compactions": 2, "drops": 1, "tool_seconds": 750, "peak_median": 170000},
    "several_people": {"pull_requests": 1, "merged": 0, "profiled": 0, "profiled_merged": 0, "calls": 0, "failed": 0, "repeated": 0, "reads": 0, "rereads": 0, "read_bytes": 0, "reread_bytes": 0, "compactions": 0, "drops": 0, "tool_seconds": 0, "peak_median": null},
    "several_people_and_sessions": {"pull_requests": 1, "merged": 1, "profiled": 1, "profiled_merged": 1, "calls": 12, "failed": 1, "repeated": 0, "reads": 4, "rereads": 1, "read_bytes": 10000, "reread_bytes": 1000, "compactions": 0, "drops": 0, "tool_seconds": 60, "peak_median": 100000},
    "undetermined": {"pull_requests": 2, "merged": 2, "profiled": 1, "profiled_merged": 1, "calls": 20, "failed": 1, "repeated": 0, "reads": 6, "rereads": 1, "read_bytes": 20000, "reread_bytes": 2000, "compactions": 0, "drops": 0, "tool_seconds": 100, "peak_median": 90000},
    "workflow_agents": {"pull_requests": 1, "merged": 1, "profiled": 1, "profiled_merged": 1, "calls": 18, "failed": 0, "repeated": 0, "reads": 5, "rereads": 1, "read_bytes": 15000, "reread_bytes": 3000, "compactions": 0, "drops": 0, "tool_seconds": 0, "peak_median": 80000},
    "automation": {"pull_requests": 1, "merged": 1, "profiled": 0, "profiled_merged": 0, "calls": 0, "failed": 0, "repeated": 0, "reads": 0, "rereads": 0, "read_bytes": 0, "reread_bytes": 0, "compactions": 0, "drops": 0, "tool_seconds": 0, "peak_median": null}
  },
  "coordination": {
    "alone": {"pull_requests": 0, "merged": 0, "profiled": 0, "profiled_merged": 0, "calls": 0, "failed": 0, "repeated": 0, "reads": 0, "rereads": 0, "read_bytes": 0, "reread_bytes": 0, "compactions": 0, "drops": 0, "tool_seconds": 0, "peak_median": null},
    "parallel": {"pull_requests": 11, "merged": 10, "profiled": 7, "profiled_merged": 7, "calls": 236, "failed": 11, "repeated": 7, "reads": 73, "rereads": 20, "read_bytes": 300000, "reread_bytes": 57000, "compactions": 2, "drops": 1, "tool_seconds": 1460, "peak_median": 120000},
    "ratios": {"calls_per_merge": null, "reads_per_merge": null, "rereads_per_merge": null, "peak": null}
  }
}
```

JUDGE.json, only after a maintainer has run the judge and pushed its file:

```json
{
  "schema": "sdlc-judge/1",
  "generated_at": "2026-10-10T18:02:40Z",
  "model": "claude-sonnet-5-5",
  "prompt_variant": "appF-7",
  "conversations": 18,
  "counts": {"C1a": 2, "C1b": 1, "C2": 0, "C3a": 1, "C3b": 0, "C4a": 0, "C4b": 3},
  "groups": {"unresponsiveness": 3, "hallucination": 1, "repetition": 3},
  "window_days": 30,
  "limit": null,
  "multi_speaker": 4,
  "by_setting": {
    "solo": {"pull_requests": 9, "conversations": 6, "multi_speaker": 1, "counts": {"C1a": 0, "C1b": 0, "C2": 0, "C3a": 0, "C3b": 0, "C4a": 0, "C4b": 1}},
    "one_session": {"pull_requests": 5, "conversations": 4, "multi_speaker": 0, "counts": {"C1a": 0, "C1b": 0, "C2": 0, "C3a": 0, "C3b": 0, "C4a": 0, "C4b": 1}},
    "one_person_sessions": {"pull_requests": 3, "conversations": 3, "multi_speaker": 0, "counts": {"C1a": 1, "C1b": 0, "C2": 0, "C3a": 0, "C3b": 0, "C4a": 0, "C4b": 1}},
    "several_people": {"pull_requests": 2, "conversations": 2, "multi_speaker": 2, "counts": {"C1a": 1, "C1b": 1, "C2": 0, "C3a": 0, "C3b": 0, "C4a": 0, "C4b": 0}},
    "several_people_and_sessions": {"pull_requests": 1, "conversations": 1, "multi_speaker": 1, "counts": {"C1a": 0, "C1b": 0, "C2": 0, "C3a": 1, "C3b": 0, "C4a": 0, "C4b": 0}},
    "undetermined": {"pull_requests": 0, "conversations": 0, "multi_speaker": 0, "counts": {"C1a": 0, "C1b": 0, "C2": 0, "C3a": 0, "C3b": 0, "C4a": 0, "C4b": 0}},
    "workflow_agents": {"pull_requests": 1, "conversations": 0, "multi_speaker": 0, "counts": {"C1a": 0, "C1b": 0, "C2": 0, "C3a": 0, "C3b": 0, "C4a": 0, "C4b": 0}},
    "automation": {"pull_requests": 2, "conversations": 1, "multi_speaker": 0, "counts": {"C1a": 0, "C1b": 0, "C2": 0, "C3a": 0, "C3b": 0, "C4a": 0, "C4b": 0}}
  }
}
```

conversations is how many pull request conversations got a readable answer; each counts under at most one code, as App F labels at most one category per conversation, and many under none. by_setting counts the judged pull requests that ended in the window by work setting, in the eight settings collect sorts them into, with their readable conversations, multi_speaker (those with two or more people, the only ones App F's unanswered-question codes can apply to) and the seven codes. Open pull requests, and those that ended before the window, count only in the totals. window_days is the window the run listed. limit is the run's --limit when the limit left pull requests unjudged, so that the run judged only the newest, and null when it judged every listed pull request, as under a limit that cut nothing.

## How each measure lines up with the benchmark's

coordbench's PARITY.md lists every measure CooperBench takes, by row, with how coordbench takes it. CooperBench runs two agents on one task pair with hidden tests and merges their two patches once at the end; a project here runs any number of people and agents through issues, claim branches and pull requests against its own checks, so most field measures are the protocol's own and few have a CooperBench twin. Plainly:

| Field measure | Benchmark measure | How they compare |
| --- | --- | --- |
| counts.conflicts_seen | CooperBench's conflict rate (PARITY.md row 55, from row 54's naive-merge conflict flag); the sdlc arm's merge_conflicts (row 97, coordbench's own; row 135 names the arm) | Equivalent in what it asks, different in how: CooperBench asks whether git conflicts when it merges the two final patches; the field counts pull requests that met the default branch in conflict, as the sdlc arm's gate meets them. It is no share of pull_requests_opened, since it draws on every pull request changed and every comment made in the window; for rates use by_setting's conflicted over landings_under, or pairs' conflict_onsets over landings. |
| counts.claims, pull_requests_opened, merged | The sdlc arm's claims, prs_opened and merges (row 97, coordbench's own) | Same events; CooperBench has no claims or pull requests. |
| durations_seconds.open_to_merge_* | The sdlc arm's time_to_first_merge_seconds; CooperBench's pair duration_seconds and median task time (rows 30 and 32) | Different clocks: the field measures each pull request from opening to merge, the benchmark the pair from its start. |
| counts.contributors | The number of agents in a run (row 15; CooperBench runs 2, 3 or 4) | A count of people and commit identities, not of configured agents. Every Claude Code cloud session commits as the account claude, which counts once more; parallel.people counts the people who opened pull requests. |
| JUDGE.json counts and groups | App F's communication errors (rows 66 to 75): C1a, C1b and C2 under Unresponsiveness, C3a and C3b under Hallucination, C4a and C4b under Repetition | The same seven codes, names and groups, and App F's text word for word (variant appF-7, coordbench's default) except its Output paragraph. Three differences: the conversation is a pull request's description, comments, review comments and reviews, among people, agents and bots, not two agents' messages; the answer is the codes alone, so coordbench's check that two quotes are found verbatim cannot run, and the field's counts are the judge's labels without it, so they can only be as many as coordbench would accept from the same model, or more; and the judge model is the maintainer's Claude, coordbench's one unavoidable deviation too (row 66). |
| counts.reviews, changes_requested; durations first_review_* | none | CooperBench has no review. |
| counts.check_runs_passed, check_runs_failed; rates.first_check_pass_rate | none | These are the project's own checks, not hidden tests; CooperBench's feature passed and tests_passed (rows 2 and 3) run held-out tests on the merged patches, which a project does not have. |
| counts.released_claims; durations claim_to_first_pull_request_* | none | CooperBench has no claims; coordbench's sdlc arm logs claim and pr_opened events but reports no wait between them. |
| rates.merge_rate | none | CooperBench's success (rows 0 and 1) is both features' tests passing on the merged patches, which the field cannot run; a merge here says only that the project's own rules let it land. |
| by_setting (the eight work settings) | Solo and Coop (rows 5 and 8) | Different: CooperBench gives the same pair of tasks to one agent and to two; here the setting is observed, the work differs between settings, and solo is other work done with nothing beside it, so a difference between settings is no coordination gap. one_session, one session's several pull requests at once, is the nearest to Solo's one agent doing two features. |
| pairs.*.conflict_onsets over pairs.*.landings, and their _file_overlap | The conflict rate (row 55), over pairs with a merge report | Same question, different instrument: CooperBench merges two finished patches once; here a pair's outcome is GitHub's mergeability when the first lands, as the board's marker records it, over the landing pairs, the field's pairs with a known result. |
| pairs.*.file_overlap, by_setting.*.file_overlap | Work overlap (row 77; coordbench's overlapping_hunks) | Different: by file, not by hunk, so coarser; coordbench-style, never reported as CooperBench's Work overlap share (PARITY.md decision 10). |
| parallel.peak_parallel, peak_parallel_people | The number of agents (row 15) | Not measured in either as a success curve; here the most pull requests and people at work at once. |
| JUDGE.json by_setting | App F's groups (rows 66 and 75) | As the totals, per setting, over the judged pull requests that ended in the window; multi_speaker names the conversations the unanswered-question codes can apply to. |
| Summing by_setting (open aside) and pairs across repositories and blocks | Pooling by summing counts (row 14) | Same: whole numbers of pull requests or pairs, and each pull request and each pair counts in the one block where it ended. parallel and by_setting's open describe their block alone and are never summed. |
| Intervals on by_setting rates | Wilson intervals (row 124) | Same, over pull requests only, never over pairs, which are not independent. |

Not measured in the field at all: pair success and the coordination gap (rows 0, 1 and 8), cost and tokens (rows 24 to 29), messages and turns (rows 36 to 47) and the failure symptoms and causes (rows 76 to 88), since each needs the agents' own logs or patches, which never leave a project.

## Reading the breakdown

The breakdown records how work ran in the field; it is no experiment, and these limits go with every reading of it.

- The settings are observed, not assigned. People choose which work to run in parallel and with whom, so the tasks differ between settings: a difference between settings is not the setting's effect, and it is not CooperBench's coordination gap, which gives the same tasks to one agent and to two (PARITY.md rows 5 and 8).
- Exposure. Long-lived work is likelier to be called parallel and likelier to conflict, and failing work lingers and gathers partners. Compare conflicted over landings_under, a hazard per landing it was at risk from, and conflict_onsets over landings, with work_seconds and partners beside them; never conflicted over pull_requests alone. On the template, solo pull requests ran a median of 0.03 h, one_session ones 2.35 h and one_person_sessions ones 1.66 h.
- At work is not typing. A pull request opened or given a commit in the window and parked since is at work beside everything that overlaps it until it ends, and GitHub never shows when a session ended. both_active says which pairs had commits on both sides during the overlap: 5 of the template's 13 same-session pairs, and 0 of its one one_person_sessions pair.
- Sessions are named by self-reported lines, Claude Code's attribution: the trailer and the description's link or footer. A local session or a claude -p worker writes no such line unless it writes Symphony-Session. If attribution is turned off, or its shape changes, work moves into undetermined, and pull_requests_without_session shows it happening. A link pasted alone on its line names a session wrongly, and a description names the last session that wrote it. A hand-over gives one pull request several sessions (pull_requests_multi_session), so later pairs can read as same_session.
- One login is one person. One human with two GitHub logins counts as two people, so their work reads as several_people, and two humans sharing a login count as one. The Claude account a session ran on is never visible, so one_person_sessions pools one person's several Claude accounts with one account's several sessions.
- The repository's own Claude workflows are recognized by their author, an app or a bot, and a claude/ branch. Whether claude-code-action opens the pull requests of the workers in Actions, the coordinator workflow and @claude as an app is not measured; if it opens them under a person's login, they count as that person's work, with no session.
- The conflict instrument is the board (tools/sdlc_protocol/board.py and its GitHub adapter). It marks only after a push to the default branch, only pull requests whose mergeability GitHub computed within one 3-second retry, and never pull requests GitHub calls draft or blocked; a burst of merges is marked against the last one. Only marks posted by an app or a bot count in the breakdown, while counts.conflicts_seen keeps marks from any author. The gap between open_conflicting and open_conflicting_dirty, with open_conflicting_drafts, shows in the field how much the dirty state misses. A pair's conflict is the board's record at a landing, never a naive merge of two final patches.
- Pairs are not independent: a pull request with k partners sits in k pairs, so crowded work weighs more. Rates over pairs are descriptive, with intervals from a bootstrap over repositories; Wilson intervals belong to counts of pull requests.
- Records overlap. Each day's record covers a rolling 30 days, so two days' records share 29 of them. Take one record per repository per 30-day block, chosen by generated_at, not by when it was collected, since a failed or dropped run leaves the last record standing. by_setting's counts other than open, and pairs, then add up across blocks, since each pull request and each pair counts in the one block where it ended; parallel and by_setting's open describe their block alone (its distinct people and sessions, its peaks, the pull requests open when it was taken) and never add up. The workflow carries JUDGE.json forward unchanged, so count a judge's record once, by its generated_at, and leave out those whose limit is set.
- Truncation and censoring. For a pull request whose work began before the look-back, what was at work beside it, its marks and its releases from before the look-back are not read (parallel.truncated). Open pull requests are outside pull_requests (by_setting's open), and the ones that linger are likelier failures. An open pull request neither opened nor given a commit in the window is beside nobody, and outside open too.
- Structural zeros. changes_requested needs a reviewer other than the author, and App F's unanswered-question codes need a second speaker; one person's sessions share one login, and so one speaker's letter. Compare those measures only within several_people and several_people_and_sessions, with multi_speaker beside them.
- Pooling across repositories. Settings gather in some repositories: several_people appears only where a team works. Stratify by the repository's hash before pooling (Simpson's paradox). Repositories with a single person give the only comparison with the person held fixed: solo, one_session and one_person_sessions.
- Small cells. In a small repository a count can describe one pull request, and the counts show how a project works, for instance that one person had three sessions at work at once. The branch `metrics` is as visible as the repository.
- Caps and budget. GitHub lists at most 250 commits of a pull request and 3,000 of its files. Under the board's reserve the file counts are null, and parallel.files_unread says how many lists were left unread; when the breakdown's other reads would reach the reserve, or GitHub fails one of them, that day's record carries no breakdown at all.
- Two ways of working. Claim branches open a draft at once and live through the board; session branches open when ready, so conflicts met before opening are fixed in private (landings_before_opening), and claim_branches says which pull requests are which. released depends on the board's run releasing at all, as it does on every run unless the board workflow is off; it counts pull requests, where counts.released_claims counts comments.
- Mixed records. Copies of the template made before the breakdown write none, and a run whose breakdown reads other than the changed files would have reached the board's reserve, or failed, writes none that day. A record without parallel, by_setting and pairs is not broken out, which is not the same as zero.
- A listing read twice. GitHub pages its listing by page number, so an update while a run reads it can name a pull request twice. The breakdown counts it once; the keys before it take the listing as it came, as they always have, so by_setting's merged and closed_unmerged can then fall short of counts.merged and counts.closed_unmerged.
- People mediate. A person relays between their own sessions, and people talk out of band. Of the field's settings, one_person_sessions is the nearest to coordbench's sdlc arm (PARITY.md row 135); several_people has no benchmark twin.
- Settings move while work is open. An open pull request can change setting by the time it ends; only the counts of finished pull requests are final.

## What is never collected

No source code, diff or file name; no issue, pull request, comment or commit text; no title, label name or branch name; no login, name or email; no URL, issue number or pull request number; no repository name. No Claude Code session link or id, and no file name or path: the session lines and the changed files are read only to sort the pull requests into settings and pairs, and are dropped with the run. The identities and numbers the code reads to count are dropped with the run. The judge's conversations go only to the maintainer's own local claude process, which asks the model on the maintainer's own account as any of their Claude Code sessions does, and only the counts are written. A repository appears in OpenSpineConsortium's data only as a salted hash.

What the work cost reaches METRICS.json only as sums and rates, and what it did reaches PROFILE.json only as sums, medians and ratios. The pieces both are summed from stay in the repository, as visible as its commits and its Actions runs: a session's Symphony-Usage trailer, on the commit, holds token counts by model, seconds and the first eight characters of the session's id, and no word of the conversation; its Symphony-Profile trailer holds counts, bytes, context sizes, seconds and the same eight characters, and no tool's name, path or word; a run's usage record, an artifact of the run, holds token counts by model, seconds, turns, the workflow, the job and the worker, the issue and pull request it ran for and the run's profile, and nothing of the execution file it was read from, which holds the conversation and is never uploaded. `collect` keeps the records it read in the Actions cache of the repository and drops their worker names and numbers from the record it writes.

The branch `metrics` is as visible as the repository: in a public repository anyone can read its three files, which hold aggregates only.

## The switch

Sharing is on unless one of these says off; off from either wins.

- The file .github/symphony-metrics on the default branch: its first word is `on` or `off`. A missing file means on; any first word but `on`, or a file that cannot be read, means off. A repository set up before the rename to Symphony may carry the same switch as .github/sdlc-metrics, which is read the same way, and off in either file wins: an on in one never lifts an off in the other. Change it by pull request like any file:

  ```
  printf 'off\n' > .github/symphony-metrics
  git add .github/symphony-metrics && git commit -m "Turn field metrics off"
  ```

- The repository variable SDLC_METRICS, which the workflow hands to the tool: `off` (any word but `on`) turns sharing off whatever the file says, and it needs no pull request:

  ```
  gh variable set SDLC_METRICS --repo OWNER/NAME --body off
  ```

With sharing off the run writes `{"schema": "sdlc-metrics/1", "sharing": "off"}`, and PROFILE.json says off the same way, and makes no API call, so the collector sees only that. The switch stops the usage records at their source too: with the file saying off, or SDLC_METRICS off in the environment, a session puts no Symphony-Usage or Symphony-Profile trailer on its commits and puts no commit-msg hook in place, and an Actions run uploads no record (the workflows hand the variable to the recorder). A person who wants no usage of theirs on their commits, whatever the repository says, sets `SDLC_METRICS=off` in the environment their sessions start in. The run comes at once after a merge of off, since the workflow starts on a push to the default branch that changes .github/symphony-metrics; the variable starts no run, so after setting it run the workflow once by hand:

```
gh workflow run metrics.yml --repo OWNER/NAME
```

Either way the off record is on the branch before the collector's daily read at 04:17 UTC. The daily run alone, at 03:43, would leave the last on record there for the collector to read once more, with any JUDGE.json beside it.

Disabling the workflow (`gh workflow disable metrics.yml --repo OWNER/NAME`) does not stop sharing: the branch keeps what it last held, and the collector reads an on record left there every day as that day's. To stop both, in this order: turn the switch off, run the workflow once so the branch holds the off record (or delete the branch `metrics`), and only then disable it.

## Running the judge

On your own computer, in a clone of the repository, with gh signed in as you (`gh auth login`) and Claude Code signed in to your own subscription (`claude`, then /login). The judge refuses to run while ANTHROPIC_API_KEY is set, since claude would then bill the API, which this project never does, and just the same while ANTHROPIC_AUTH_TOKEN, CLAUDE_CODE_USE_BEDROCK, CLAUDE_CODE_USE_VERTEX or CLAUDE_CODE_USE_FOUNDRY is set, since each sends the conversations to an API or a cloud account and bills it; the refusal names the variable to unset. ANTHROPIC_BASE_URL alone, which would send them to a gateway, is dropped from claude's environment, and a dry run says so when it is set. Try the judge before running it whole:

```
unset ANTHROPIC_API_KEY
python3 tools/metrics.py judge --dry-run
python3 tools/metrics.py judge --limit 20
```

Then judge and push in one go, or judge, read JUDGE.json and push it afterwards; `push` never judges again:

```
python3 tools/metrics.py judge --push
```

```
python3 tools/metrics.py judge
python3 tools/metrics.py push
```

- `--dry-run` reads the window's pull requests with gh and prints, for the first conversation, exactly what would go to the model (the command, the system prompt and the conversation on stdin) and the JUDGE.json a run would write; it calls no model, writes no file and pushes nothing.
- The judge also counts its conversations by work setting (by_setting in JUDGE.json), for the pull requests that ended in the window, sorted as collect sorts them. To sort them it reads each listed pull request's commits with gh, one call each, whatever --limit says, and the setting never reaches the model. A dry run prints how many of the pull requests it would judge fall in each setting.
- A run asks your claude once per pull request conversation (twice when the reply is not JSON), with `claude -p --output-format json`, the conversation on stdin and App F as the whole system prompt, read from a file (`--system-prompt-file`) in the temporary folder claude runs in, which holds nothing else, so no project's CLAUDE.md is read; with no tool, no MCP server, no settings and so no hook, no skill and no saved session. Claude Code may still read your own user instructions; the one mode that skips them, `--bare`, signs in only with an API key. Each call spends your plan's usage; `--limit` caps the number of pull requests, newest first, and `--model` picks the model (default claude-sonnet-5-5, coordbench's default). A model name is letters, digits, dots, dashes and underscores, at most 64, with an optional `[tag]` after them, the shape the collector keeps; anything else, such as a cloud model ARN with an account number in it, is refused, because the name goes into JUDGE.json as it is. When claude fails (signed out, an unknown model, a usage limit), the judge stops, repeats what claude said, and writes nothing.
- People are named A, B, C in each conversation in the order they first speak, and mentions of them become the same letters; apps and bots are "bot". The protocol's own automated comments are left out: the board's "main moved" and "idle" comments and the coordinator's release comments, known by their markers (`<!-- sdlc-board: main-moved SHA -->`, `<!-- sdlc-board: idle -->`, `<!-- sdlc-coordinator: claim-released -->`), which the protocol posts by rule, the board's again and again, so App F would read them as spammy repetition that nobody wrote. The model is told to answer with codes alone, and anything else a reply carries is dropped before counting.
- `--push` commits JUDGE.json onto the branch `metrics` of origin as an ordinary commit on top of what is there, keeping METRICS.json and PROFILE.json exactly as they are, and pushes it with a plain push, which the push guard (tools/guard_push.py) lets through; when the workflow rewrote the branch in between, the judge reads it again and tries once more. The commit message ends with `[skip ci]`, so a workflow the repository starts on every push stays off a tree of JSON files alone (two or three: PROFILE.json is there from the first run that writes it). The next run of the workflow keeps JUDGE.json. JUDGE.json names no repository, so the push can only go to origin, and origin must be the repository judged: the judge compares the two before it reads a pull request and refuses `--push` when they differ (a clone of another project, or a fork clone whose gh default is the upstream), so a mismatch costs nothing; run it in a clone of the repository judged.
- `push` sends a JUDGE.json already written (`--out`, default ./JUDGE.json) after the same origin check, without judging again: after a push the judge gave up on, which its last words name, or after a run kept without `--push` so the file could be read first. `--repo` names the repository the file was judged for, as `judge --repo` did. The file must be one the judge wrote, since the branch takes its aggregates and nothing else.
- `--repo`, `--window-days` and `--out` change what the defaults say (the repository gh sees here, 30 days, ./JUDGE.json, which .gitignore keeps out of commits).

## Who reads the files

OpenSpineConsortium's collector lives in the private repository OpenSpineConsortium/symphony-app. Once a day, at 04:17 UTC, after this repository's run at 03:43, it lists the repositories that installed the Symphony App, reads METRICS.json and JUDGE.json at the ref `metrics` of each and no other path, PROFILE.json not among them, keeps only those whose sharing is on, and stores each day's files under HMAC-SHA256 of the repository's node id with a salt only the collector holds, never under the repository's name. A repository whose switch is off shows the collector `"sharing": "off"` and nothing more. A repository without the App is never read; its branch `metrics` is written all the same and stays the project's own record.

## The branch and the rules

.github/workflows/metrics.yml writes the branch the way the board's workflow writes `board`: one commit built from the files alone, which replaces the branch with `--force-with-lease` naming the commit the run read, so a judge's push that landed meanwhile makes the lease fail, and the run reads the branch again, keeps the new JUDGE.json and tries once more. It replaces only a branch that holds nothing but METRICS.json, PROFILE.json and JUDGE.json: a branch `metrics` with any other file is the project's own, there before the workflow came (a repository that adopted the template, or an owner who started one), and replacing it would lose it, so the run prints those files, pushes nothing and fails. Rename that branch (`git branch -m metrics NAME` in a clone, then push NAME and delete `metrics`, or the repository's branches page) and the next run starts a branch `metrics` of its own. The commit holds the run's METRICS.json and PROFILE.json, or the branch's PROFILE.json where the run wrote none, and the branch's JUDGE.json, and the run writes it only when METRICS.json or PROFILE.json changed apart from its generated_at. A ruleset must therefore target only the default branch, as docs/setup/github.md says for `board`: one over all branches would refuse the run's push and leave the metrics stale. CI's push trigger leaves the branch out (.github/workflows/ci.yml), since the judge's push, made with a person's credentials, would otherwise start the checks on a tree that holds JSON files alone, and the judge's commit message ends with `[skip ci]`, which keeps any other workflow a repository starts on every push off that tree too.

The workflow is skipped in the template repository itself, wherever the marker folder .template/ still is, and in a fork, since a fork made with gh or the API carries the original's branch `metrics`, frozen on the day it was made, and a run there would write metrics of the fork's own beside the original's JUDGE.json. It names no secret but GITHUB_TOKEN, so it runs in crowd mode as anywhere (docs/setup/crowdsourcing.md), and the judge, like everything else there, runs on the maintainer's own Claude account.
