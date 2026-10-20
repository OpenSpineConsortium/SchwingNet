# How long a claim waits: the three waits measured in a real copy

Measured on 2026-10-16 in the thread "Protocol fixes toward 0.5.0", for item 5 of part 2.1 of the 2026-10-15b handoff, the measurement pass, which is three pull requests: the API calls of one board run (symphony-protocol#38, whose figures are the library README's "What a board run costs"); these three waits, the claim-to-first-pull-request, open-to-merge and first-review medians from a real copy; and retry on GitHub's rate limits in the library (symphony-protocol#40). No Claude Doc, artifact or upload lies behind this note: the figures come from GitHub's API, as a copy's own metrics workflow recorded them and as the template's collector, tools/metrics.py, recomputed them. The readiness research of 2026-10-14 had found the three waits defined by the field metrics and no figure for them kept where the project reads (docs/checkpoints/2026-10-14c/notes/readiness-research-2026-10-14.md), though a copy's own branch metrics holds them, each run's record replacing the one before.

## The answer

On a private copy of the owner's, over the 30 days to 08:29:47 UTC on 2026-10-16, which hold the whole of the copy's life, a little over four days:

| Wait | Pull requests | Median | p90 | Middle half | Shortest | Longest |
| --- | --- | --- | --- | --- | --- | --- |
| Claim to first pull request | 38 | 84 s | 90 s | 54 s to 86 s | 8 s | 17,496 s (4.9 h) |
| Open to merge | 37 | 576 s (9.6 min) | 12,921 s (3.6 h) | 474 s to 1,618 s (27 min) | 5 s | 18,660 s (5.2 h) |
| First review | 0 | none | none | none | none | none |

The medians and the p90s are the field metrics' own: a median is rounded half up to whole seconds, and a p90 is the nearest rank, the smallest value at or above nine tenths of them (docs/setup/metrics.md). The middle half, which the field metrics do not define, runs between the lower and upper quartiles that Python's statistics.quantiles gives with method="inclusive"; another method gives other values. One of the 37 merged pull requests is an app's automation, opened and merged within 5 seconds: without it, the people's 36 have a median of 584 s, the same p90 and a middle half of 478 s to 1,626 s.

A session's draft opens about a minute and a half after its claim commit, which is a lower bound on what a claim costs (below). A pull request merges about ten minutes after it opens, a quarter of them after more than 27 minutes and a tenth after more than three and a half hours, and that wait holds the work and any wait for the merge alike (below). Nothing reviewed any pull request there, so the third wait has no value on this copy.

## Where the figures come from

- The copy. It runs the protocol from the template's files, with tools/VENDORED naming sdlc-protocol 0.4.1 at 438844f; its sessions claim an issue by pushing the branch claude/<n> and open the draft at once, as docs/agents/PROTOCOL.md says. Its workflows are board.yml, metrics.yml, protocol.yml and tidy.yml, so it has no check of its own (below). The repository was made at 00:43 UTC on 2026-10-12 (step 1), so the window holds the whole of its life, and every pull request it has, 42, was opened in the window or after it: the 39 opened in the window came over four days, 24 of them on the first. Of the 39 opened in the window, 38 came from claim branches and one from an app; of the 37 merged in it, 36 and the app's. This note leaves the copy unnamed, since its own rules keep it private until the owner says otherwise.
- The record. The copy's own metrics workflow wrote METRICS.json to its branch metrics with a generated_at of 08:29:47 UTC, the moment its collector began and the end of its window; the medians and p90s above are that record's durations_seconds. The workflow replaces the branch, with one commit and no history, only when a run's record differs from the one there in more than generated_at, as the next run's will now that the window has moved; this note keeps the figures.
- The recomputation. The template's collector, tools/metrics.py at main 918193e, run on the copy with `--now` at the record's time, wrote the same six figures, in 265 calls of the session's own token and none of the copy's GITHUB_TOKEN. `--now` sets the end of the window and nothing else: the collector reads every pull request changed since the window began, those opened after it ended included, and an open one as it is when the collector runs. By then three pull requests had been opened after 08:29:47 and one open at that moment had ended, so the recomputation counts 41 claims where the record has 38 and 6 sessions where it has 7, with three more of the parallel block's counts and one of the settings' down by one in the same way; it writes the template's own protocol_version and prices_as_of beside them. The six waits are the same, since each takes only pull requests opened or merged in the window.
- The spread and the counts. The column of pull requests, the middle half, the shortest and the longest, the counts by branch and by login, and the people's own open-to-merge figures come from the short script under "How to measure again". It takes the same lists the collector takes its medians from (claim_waits, merge_waits and review_waits) and only counts and sorts them, and it prints the table's six figures again. The collector's tests hold its medians and p90s; the script is not tested.

## What each wait measures there

- Claim to first pull request: from the claim's time, the earliest author date among the pull request's commits, which on a claim branch is the claim file's own commit, to the draft's opening, once for each claim whose pull request opened in the window. It holds what a session does between the claim commit and the draft: the push, and the labels and the plan comment of the protocol's Announce where they come before the draft. It leaves out what comes before the commit, reading the board, picking the issue and writing the claim file, so 84 seconds is a lower bound on what a claim costs a session and not the whole of it. One draft opened 4.9 hours after its claim commit.
- Open to merge: from the opening to the merge, for each pull request merged in the window. Since a claim opens its draft at once, this holds the session's work on the issue and whatever wait the merge had. Who pressed merge is not recorded: a person's sessions act on GitHub under the person's login, so the login GitHub keeps for a merge cannot tell a session's from the person's, and the protocol leaves the merge to the owner (docs/agents/PROTOCOL.md, Finish). The wait may hold a person's wait for the merge beside the session's work, and these figures cannot tell the two apart.
- No check of the work stands before these merges. No workflow of the copy's tests the work or holds a claim's pull request to the protocol (tools/check_protocol.py runs in the template's own check, which the copy does not have). Every check run that finished in the window is the board workflow's, 130 passed and 71 skipped, but for one skipped run of the metrics workflow. So the record's 130 check runs passed and none failed, and its first_check_pass_rate of 1.0, the share of pull requests whose first head passed every counted run on it, say only that the board never failed there, and nothing of the work. Every pull request that ended in the window merged (merge_rate 1.0).
- First review: from the opening to the first review by anyone but the author. None of the 42 pull requests read, 39 opened in the window and 3 since, carries a review of any kind, the author's own included: nothing in the protocol asks for one before the merge, which it leaves to the owner. The wait can be measured only on a copy where someone, or something, submits reviews.

## What the figures do and do not say

- One copy in its first four days, with 24 of its 39 pull requests opened on the first: a sample of one copy in its first days, not a figure for copies in general, nor for this one later.
- The record's people are logins (docs/setup/metrics.md). One login opened 37 of the 39 pull requests opened in the window and all 36 of the people's pull requests merged in it; a second login opened one, still open when the window ended; an app opened the remaining one. So what the record says of several people's work rests on that one pull request. The sessions it counts, 7, are those named on 12 of the people's 38 pull requests, and the other 26 name none (parallel.pull_requests_with_session and pull_requests_without_session). Up to five of the people's pull requests were at work at one moment (parallel.peak_parallel).
- 84 seconds is that lower bound, in a session's wall time, kept here for the first time. With the board's calls per run, it answers the time half of the question the taxonomy spec asks as R3, what one coordination step costs (docs/checkpoints/2026-10-15b/taxonomy/spec.md), for this one copy and from below.
- Whether work beside other work was slower here, these figures cannot say. The record's coordination block splits 36 of the 37 merged pull requests, the app's left out, into 6 done alone and 30 beside other open work, which here is mostly the same login's own (the settings: 6 solo, 23 undetermined and 7 several_people). Its two ratios of time point opposite ways: latency 1.02, from open-to-merge medians of 593 s alone and 584 s beside other work (that record's coordination block cut its medians to whole seconds, where the durations round theirs half up; the template takes both by one rule since symphony-template#110), and throughput 0.23, fewer merges per hour at work beside other work. Its ratios of failures and of first checks compare two sides with no failed check at all. A side of six says little either way (docs/setup/metrics.md).

## How to measure again

The copy is OWNER/NAME below; the owner can say which it is.

1. Read the copy's own record: `gh api 'repos/OWNER/NAME/contents/METRICS.json?ref=metrics' --jq .content | base64 -d`. It holds this note's figures only until the copy's metrics workflow next writes the branch. The copy's workflows are listed by `gh api 'repos/OWNER/NAME/contents/.github/workflows' --jq '.[].name'`, and when it was made by `gh api repos/OWNER/NAME --jq .created_at`.
2. Recompute the record at its time with the template's collector, from a checkout of the template at 918193e, where it was run, with GITHUB_TOKEN set to a token that can read the copy's contents, pull requests, issues, checks and actions, as metrics.yml's can, and SDLC_METRICS unset or on, since off, in the environment or in the checkout's .github/symphony-metrics, writes the record of sharing off and reads nothing: `python3 tools/metrics.py collect --repo OWNER/NAME --out /tmp/recomputed.json --now 2026-10-16T08:29:47Z`. It gives the six waits again; the counts that depend on what is open, or on pull requests opened since, move with the copy (above). The vendored client asks nothing again after an error of GitHub's own, so a run that stops on an HTTP error of 500 or more is simply run again.
3. The spread and the counts, from the same checkout with the same token, by the script below, saved in a scratch directory as waits.py and run from the checkout's root as `python3 <scratch>/waits.py OWNER/NAME 2026-10-16T08:29:47Z`, again after an error of GitHub's own as in step 2. Run at 15:25 UTC on 2026-10-16, it printed this, in 233 calls:

```
42 pull requests read: opened before the window 0, in it 39, after it 3; open at its end and ended since 1; listed but last changed before it 0
opened in the window by day: [('2026-10-12', 24), ('2026-10-13', 5), ('2026-10-14', 4), ('2026-10-15', 6)]
opened in the window: 39, 38 from claim branches; by each login [37, 1], by apps and bots 1
merged in the window: 37, 36 from claim branches; by each login [36], by apps and bots 1
claim to first pull request: n=38 median=84 p90=90 middle half=[54, 86] shortest=[8] longest=[17496]
open to merge: n=37 median=576 p90=12921 middle half=[474, 1618] shortest=[5] longest=[18660]
open to merge, people's pull requests only: n=36 median=584 p90=12921 middle half=[478, 1626] shortest=[10] longest=[18660]
first review: n=0 median=None p90=None middle half=[] shortest=[] longest=[]
check runs finished in the window, by name and conclusion: [(('board', 'skipped'), 71), (('board', 'success'), 130), (('metrics', 'skipped'), 1)]
0 reviews, 233 calls
```

```python
import collections, os, statistics, sys
sys.path.insert(0, "tools")
import metrics

repo, end = sys.argv[1], metrics.parse_time(sys.argv[2])
window = metrics.Window.ending(end, 30)
api = metrics.Budgeted(os.environ["GITHUB_TOKEN"], repo)
facts, _claims, _comments, rest = metrics.read_repository(api, window)


def created(f):
    return metrics.time_of(f.pull, "created_at")


def ended_after_the_window(f):
    ended = metrics.time_of(f.pull, "merged_at") or metrics.time_of(f.pull, "closed_at")
    return created(f) <= window.end and ended is not None and ended > window.end


def by_login(found):
    people = collections.Counter(f.pull["user"]["login"] for f in found if metrics.kind_of(f.pull) == metrics.PERSON)
    return sorted(people.values(), reverse=True), len(found) - sum(people.values())


def spread(name, values):
    ordered = sorted(values)
    quartiles = statistics.quantiles(ordered, n=4, method="inclusive") if len(ordered) > 1 else ordered * 3
    print(f"{name}: n={len(ordered)} median={metrics.median_seconds(ordered)} p90={metrics.p90_seconds(ordered)}"
          f" middle half={[round(q) for q in quartiles[::2]]} shortest={ordered[:1]} longest={ordered[-1:]}")


opened = [f for f in facts if window.holds(created(f))]
merged = [f for f in facts if window.holds(metrics.time_of(f.pull, "merged_at"))]
people_merged = [f for f in merged if metrics.kind_of(f.pull) == metrics.PERSON]
print(f"{len(facts)} pull requests read: opened before the window {sum(created(f) < window.start for f in facts)},"
      f" in it {len(opened)}, after it {sum(created(f) > window.end for f in facts)};"
      f" open at its end and ended since {sum(ended_after_the_window(f) for f in facts)};"
      f" listed but last changed before it {sum(1 for _ in rest)}")
print("opened in the window by day:", sorted(collections.Counter(str(created(f).date()) for f in opened).items()))
for name, found in (("opened in the window", opened), ("merged in the window", merged)):
    logins, apps = by_login(found)
    claimed = sum(metrics.claim_number(f.pull) is not None for f in found)
    print(f"{name}: {len(found)}, {claimed} from claim branches; by each login {logins}, by apps and bots {apps}")
spread("claim to first pull request", metrics.claim_waits(opened))
spread("open to merge", metrics.merge_waits(merged))
spread("open to merge, people's pull requests only", metrics.merge_waits(people_merged))
spread("first review", metrics.review_waits(opened))
runs = collections.Counter((r.get("name"), r.get("conclusion")) for r in metrics.window_runs(facts, window))
print("check runs finished in the window, by name and conclusion:", sorted(runs.items()))
print(f"{sum(len(f.reviews) for f in facts)} reviews, {api.calls} calls")
```

A later window moves every figure, and the copy's next record replaces the one this note read. The recomputation with `--now` at 08:29:47 gives the six waits again for as long as nothing changes on the pull requests opened or merged in the window, a review added to one of them included.
