Field metrics: .github/workflows/metrics.yml writes the protocol's aggregates, never a name or any text, to METRICS.json on the branch metrics daily with GITHUB_TOKEN alone, what the work cost among them; a maintainer's judge adds App F counts as JUDGE.json; .github/symphony-metrics or the variable SDLC_METRICS turns sharing off.

tools/metrics.py collect reads the last 30 days of pull requests, reviews,
check runs, claude/<n> branches and comments from the REST API and writes
counts, medians and 90th percentiles in seconds, and two rates, under the
keys docs/setup/metrics.md lists and no other; tests/test_metrics.py fails
when a key, a name, a title, a branch or a body from its fixtures reaches
the file. Off from the file or the variable writes {"schema":
"sdlc-metrics/1", "sharing": "off"} and calls no API; the file is read
under its name before the rename too, .github/sdlc-metrics, and an off in
either file wins over an on in the other.

collect also sorts the pull requests that ended in the window into eight
work settings and four kinds of pairs, by the opener's login and the
session lines of their commits and descriptions (Claude-Session, the link
alone, the footer, or Symphony-Session), read in memory only. One person's
several sessions (one_person_sessions) are never pooled with several people
(several_people). The breakdown reads back one more window, reads changed
files last and only for pull requests with a partner, and writes counts
only. It reads only once every other key is measured, so a run whose
breakdown reads other than the changed files would reach the board's
reserve, or fail, still writes the other keys, without parallel,
by_setting and pairs (changed files left unread only make their counts
null), and without economics and coordination, which read after it; and
an open pull request counts
only when it was opened or given a commit in the window, since the board's
comment at every push to the default branch renews a parked one's
updated_at.

The run is daily at 03:43 UTC, before OpenSpineConsortium's collector reads
the branch at 04:17, and on a push to the default branch that changes
.github/symphony-metrics, so a merge of off is read as off the same day; the
variable starts no run, so the owner runs the workflow once after setting
it. Disabling the workflow stops no sharing: the branch keeps its last
record, so the switch goes off and one run writes it before the workflow
is disabled. The job never runs in a fork, whose copy of the branch is the
original's, frozen.

The branch metrics is written like board: one commit from the files alone,
pushed with --force-with-lease naming the commit the run fetched, so the
JUDGE.json a maintainer pushed meanwhile is kept, never lost; a branch
metrics that holds any file but METRICS.json, PROFILE.json and JUDGE.json
is the project's own, and the run prints
those files, says to rename the branch and pushes nothing; a ruleset must
leave the branch out, and CI's push trigger leaves it out. The judge
(`python3 tools/metrics.py judge`) runs only on a maintainer's machine, with
their own gh and their own `claude -p` on their own subscription, refuses
while ANTHROPIC_API_KEY or another variable that bills an API or a cloud
account is set, sends each pull request's conversation (people as A, B, C;
the board's and the coordinator's own comments left out) only to that
local claude, keeps codes only, and pushes JUDGE.json (--push, or push
afterwards) to origin, which must be the repository judged, as an ordinary
commit the push guard lets through.

What the work cost comes from two records, neither needing a routine, an
API key or a server (tools/usage.py). A session's PreToolUse hook on Bash
reads its transcript before each git commit, and the commit-msg hook the
session-start hook installs adds a trailer, `Symphony-Usage: v1
session=<8> seconds=<n> <model>=input,cache5m,cache1h,cacheread,output`,
the usage since the session's last commit; a run in Actions (workers.yml,
coordinator.yml, claude.yml) reads claude-code-action's execution file
with a copy of usage.py made before the session and uploads its record as
an artifact named symphony-usage-*. collect lists and downloads those
records (actions: read; the redirect is fetched without the token, which
urllib would otherwise send to the storage host), at most 200 new a run,
carrying what it read in the Actions cache (--usage-cache). economics is
the window's bill (trailers on commits made in it, runs recorded in it)
over what it delivered (pull requests of people and of the Claude
workflows that ended in it), priced at the API list prices of
tools/economics.py's PRICES; coordination splits those pull requests into
alone and parallel (other such work beside for more than 60 seconds), the
coordinator's unattributed runs on the parallel side, and gives seven
ratios, each over 1 where parallel did better: tokens and dollars per
measured merge, latency, throughput, first check passed, commits per
merge, failures per pull request. The switch stops the records at their
source too, and SDLC_METRICS=off in a person's environment keeps their
sessions' usage off their commits. A second line after the usage one,
Symphony-Profile, carries the session's profile since its last commit,
and a run's record its profile where the workflow copied profile.py
beside the recorder (profiling-sessions.md); collect --profile-out sums
both per pull request into PROFILE.json, by work setting and alone against
parallel, which the workflow writes beside METRICS.json and the collector
does not read until the Apps' privacy statement lists its keys. The usage
cache's version 2 keeps each run's profile; a record a version 1 cache
kept still counts, marked old, and is downloaded again for its profile
after the new ones, within the 200, while its artifact lasts, so no run
drops out of the economics when the cache's form changes.

Two conventions the counts rest on: the coordinator, the board's run or a
coordinator routine, starts each release comment with
`<!-- sdlc-coordinator: claim-released -->` (it is the vendored protocol's
claims.RELEASE_MARKER, on which the board also renames a released claim's
branch, and released_claims counts a release said again within a day
once), and the board's "main moved" comment says "conflicting with" for a
conflict; change either and metrics.py with it.
OpenSpineConsortium's collector, in symphony-app, reads only the two files at
the ref metrics of repositories that installed the Symphony App and
stores them under a salted hash of the repository.
