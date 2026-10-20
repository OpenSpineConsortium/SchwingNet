"""Each part of step 2 undone in a copy of the tree one at a time: the named
tests must fail. Usage: step_2_undoings.py [repository root]; each copy is made in a
temporary folder, so the checkout is never touched."""
import shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[4]
HERE = Path(tempfile.mkdtemp(prefix="undoings-"))
E = "tests.test_economics."
P = "tests.test_profile."
M = "tests.test_metrics."
RUN_PROFILE = E + "Attribution.test_a_runs_profile_is_its_counts_alone"
KEPT = E + "Attribution.test_the_kept_form_of_a_record_is_what_is_read_of_it_and_reads_the_same"
SIDES = E + "AloneAndParallel.test_the_sides_and_the_overhead_are_what_the_profiles_sums_take_too"
BEFORE = E + "AloneAndParallel.test_work_from_before_the_window_counts_as_beside"
FOLD = P + "ToolNames.test_every_mcp_tool_is_one_row_and_any_other_tool_another"
HARNESS = P + "ToolNames.test_the_harness_list_holds_names_alone"
LISTED = P + "ToolNames.test_the_tools_by_name_are_printed_and_never_written"
PULL = P + "SumsOverPullRequests.test_a_pull_requests_profile_is_its_commits_lines_and_the_runs_that_name_it"
SIDE_SUMS = P + "SumsOverPullRequests.test_each_side_sums_its_profiled_pull_requests_and_the_parallel_one_the_coordinators_runs"
RATIOS = P + "SumsOverPullRequests.test_each_ratio_is_over_one_where_parallel_did_better"
GROUP = P + "SumsOverPullRequests.test_a_setting_sums_whatever_kind_its_pull_requests_are_and_its_median_peak_rounds_half_up"
WORLD = M + "ProfileSums.test_the_world_sums_to_what_its_lines_and_runs_say"
OFF = M + "ProfileSums.test_sharing_off_writes_off_alone_and_calls_nothing"
LEFT_OUT = M + "ProfileSums.test_the_sums_are_left_out_with_the_breakdown"
NO_OPTION = M + "ProfileSums.test_without_its_option_no_profile_is_written"
CACHE_V1 = M + "Economics.test_a_cache_kept_before_the_profile_is_read_again_from_the_artifacts"
FIRST = M + "WriteStep.test_the_profile_goes_beside_metrics_json_and_a_first_one_is_a_change"
UNCHANGED = M + "WriteStep.test_both_files_unchanged_apart_from_their_time_write_nothing"
MOVED = M + "WriteStep.test_a_moved_profile_alone_is_a_change"
KEPT_SUMS = M + "WriteStep.test_a_run_that_wrote_no_profile_keeps_the_branchs"
PATHS = M + "Workflow.test_the_profile_collect_writes_is_the_one_the_write_step_puts_on_the_branch"
JUDGE = M + "JudgePush.test_it_lands_as_a_fast_forward_that_keeps_metrics_json_and_profile_json"
SAMPLE = M + "Page.test_the_profile_sample_is_what_collect_writes_for_the_two_person_world"
EXPIRED = M + "Economics.test_an_old_record_whose_artifact_has_expired_still_counts"
FAILED_OLD = M + "Economics.test_an_old_record_whose_download_fails_is_kept_as_it_was"
LIMIT_OLD = M + "Economics.test_old_records_are_read_again_only_after_the_new_ones_within_the_limit"
FAULT = M + "ProfileSums.test_a_fault_in_the_sums_never_stops_metrics_json"
UNREAD = M + "ProfileSums.test_runs_not_read_again_yet_are_counted_as_unread"
BEYOND = M + "ProfileSums.test_beyond_the_world_each_run_and_line_counts_where_it_belongs"
ZERO_RUN = E + "Attribution.test_a_run_that_made_no_call_has_no_profile"
ZERO_LINE = P + "SumsOverPullRequests.test_a_line_or_a_run_of_zeros_is_no_profile"

ECO, PRO, MET, YML = "tools/economics.py", "tools/profile.py", "tools/metrics.py", ".github/workflows/metrics.yml"

MUTANTS = [
    # economics.py
    ("a run's profile never read", ECO,
     '''        "profile": profile_counts(data.get("profile")),''', '''        "profile": None,''', [RUN_PROFILE, KEPT, WORLD]),
    ("every key of a run's profile kept", ECO,
     '''    counts = {key: block[key] for key in profiler.TRAILER_FIELDS if number(block.get(key))}''',
     '''    counts = {key: value for key, value in block.items() if number(value)}''', [RUN_PROFILE, KEPT]),
    ("a run's profile counts not checked", ECO,
     '''    counts = {key: block[key] for key in profiler.TRAILER_FIELDS if number(block.get(key))}''',
     '''    counts = {key: block[key] for key in profiler.TRAILER_FIELDS if key in block}''', [RUN_PROFILE]),
    ("an empty profile kept as {}", ECO, '''    return counts if profiler.measured(counts) else None''',
     '''    return counts''', [RUN_PROFILE]),
    ("a run that made no call kept as a profile", ECO, '''    return counts if profiler.measured(counts) else None''',
     '''    return counts or None''', [ZERO_RUN]),
    ("every unattributed run counted as overhead", ECO,
     '''    return [r for r in unattributed(works, window_records) if r["workflow"] == "coordinator"]''',
     '''    return unattributed(works, window_records)''', [SIDES]),
    ("work that did not end in the window never beside", ECO,
     '''    everyone = working + [o for o in others if o.kind in WORKING_KINDS and o.start is not None]''',
     '''    everyone = working''', [BEFORE]),
    # profile.py
    ("no tool name folded", PRO,
     '''    return MCP_TOOLS if name.startswith("mcp__") else OTHER_TOOLS''', '''    return name''', [FOLD, HARNESS]),
    ("every other tool folded with the MCP tools", PRO,
     '''    return MCP_TOOLS if name.startswith("mcp__") else OTHER_TOOLS''', '''    return MCP_TOOLS''', [FOLD, HARNESS]),
    ("the record built from the unfolded rows", PRO,
     '''        by_tool = {name: {k: round(v) for k, v in row.items()} for name, row in sorted(folded.items())}''',
     '''        by_tool = {name: {k: round(v) for k, v in row.items()} for name, row in sorted(self.by_tool.items())}''',
     [FOLD]),
    ("a folded row takes the last tool's counts", PRO, '''                into[key] += value''', '''                into[key] = value''', [FOLD]),
    ("the listing by name, not by calls", PRO,
     '''    rows = sorted(built.by_tool.items(), key=lambda item: (-item[1]["calls"], item[0]))[:count]''',
     '''    rows = sorted(built.by_tool.items())[:count]''', [LISTED]),
    ("no listing printed", PRO,
     '''    if args.tools:
        sys.stdout.write''', '''    if False:
        sys.stdout.write''', [LISTED]),
    ("a line with no count taken as a profile", PRO,
     '''    return [(session, counts) for session, counts in parse_trailer(message) if measured(counts)]''',
     '''    return parse_trailer(message)''', [PULL]),
    ("a line of zeros taken as a profile", PRO,
     '''    return [(session, counts) for session, counts in parse_trailer(message) if measured(counts)]''',
     '''    return [(session, counts) for session, counts in parse_trailer(message) if counts]''', [ZERO_LINE]),
    ("the runs' profiles left out of a pull request's", PRO,
     '''    found += [record["profile"] for record in records if record.get("profile") and economics.names(record, work)]''',
     '''    found += []''', [PULL, WORLD]),
    ("every run's profile put on every pull request", PRO,
     '''    found += [record["profile"] for record in records if record.get("profile") and economics.names(record, work)]''',
     '''    found += [record["profile"] for record in records if record.get("profile")]''', [PULL, WORLD]),
    ("a pull request's peaks added up", PRO,
     '''    total["peak"] = max(counts.get("peak", 0) for counts in found)''',
     '''    total["peak"] = sum(counts.get("peak", 0) for counts in found)''', [PULL, WORLD]),
    ("what a side spends beside its pull requests left out", PRO,
     '''    row.update({key: sum(profiles[w.number][key] for w in profiled) + (extra or {}).get(key, 0) for key in SUMS})''',
     '''    row.update({key: sum(profiles[w.number][key] for w in profiled) for key in SUMS})''', [SIDE_SUMS, WORLD]),
    ("every merge divides, profiled or not", PRO,
     '''           "profiled": len(profiled), "profiled_merged": sum(1 for w in profiled if w.merged is not None)}''',
     '''           "profiled": len(profiled), "profiled_merged": sum(1 for w in works if w.merged is not None)}''',
     [SIDE_SUMS, RATIOS, WORLD]),
    ("the largest peak in place of the median", PRO,
     '''    row["peak_median"] = economics.median_seconds([profiles[w.number]["peak"] for w in profiled])''',
     '''    row["peak_median"] = max([profiles[w.number]["peak"] for w in profiled], default=None)''',
     [SIDE_SUMS, WORLD, GROUP]),
    ("the median peak rounded down", PRO,
     '''    row["peak_median"] = economics.median_seconds([profiles[w.number]["peak"] for w in profiled])''',
     '''    row["peak_median"] = (int(__import__("statistics").median([profiles[w.number]["peak"] for w in profiled])) if profiled else None)''',
     [GROUP]),
    ("per merge over the side's merges", PRO,
     '''        return economics.per(side[key], side["profiled_merged"])''',
     '''        return economics.per(side[key], side["merged"])''', [RATIOS]),
    ("the per-merge ratios upside down", PRO,
     '''    per_merges = [economics.inverse(per_merge(alone, key), per_merge(parallel, key))''',
     '''    per_merges = [economics.inverse(per_merge(parallel, key), per_merge(alone, key))''', [RATIOS]),
    ("the peak ratio upside down", PRO,
     '''economics.inverse(alone["peak_median"], parallel["peak_median"])''',
     '''economics.inverse(parallel["peak_median"], alone["peak_median"])''', [RATIOS]),
    ("the coordinator's runs off the parallel side", PRO,
     '''    parallel_side = group(parallel, profiles, run_sums(economics.overhead(works, window_records)))''',
     '''    parallel_side = group(parallel, profiles)''', [SIDE_SUMS, WORLD]),
    ("the coordinator's runs on the alone side too", PRO,
     '''    alone_side = group(alone, profiles)''',
     '''    alone_side = group(alone, profiles, run_sums(economics.overhead(works, window_records)))''', [SIDE_SUMS]),
    # metrics.py
    ("every setting summing every pull request", MET,
     '''            "by_setting": {name: profile.group([w for w in works if settings[w.number] == name], profiles)''',
     '''            "by_setting": {name: profile.group(works, profiles)''', [WORLD]),
    ("a session that is no token's counted", MET,
     '''    return {"sessions": len(sessions - {""}), "actions_runs": len(summed),''',
     '''    return {"sessions": len(sessions), "actions_runs": len(summed),''', [WORLD]),
    ("the coordinator's runs not counted among the runs", MET,
     '''        id(record) in overhead or any(economics.names(record, w) for w in works))]''',
     '''        any(economics.names(record, w) for w in works))]''', [WORLD]),
    ("no PROFILE.json written when sharing is off", MET,
     '''        if args.profile_out:
            write_json(args.profile_out, PROFILE_OFF)''', '''        pass''', [OFF]),
    ("the sums written beside a left-out breakdown", MET,
     '''profile_keys(facts, units, window, records) if records is not None else {}''',
     '''profile_keys(facts, units, window, records) if records is not None else {"sessions": 0}''',
     [LEFT_OUT]),
    ("the sums worked out without the option, before METRICS.json", MET,
     '''    write_json(args.out, metrics_record(measured, window, protocol_version()))
    written = args.out''',
     '''    if records is not None:
        profile_keys(facts, units, window, records)
    write_json(args.out, metrics_record(measured, window, protocol_version()))
    written = args.out''', [NO_OPTION]),
    ("a fault in the sums stops the run", MET, '''        except Exception as fault:''', '''        except OSError as fault:''',
     [FAULT]),
    # the review's findings, fixed: the usage cache from before the profile
    ("a version 1 cache thrown away whole", MET, '''USAGE_CACHE_VERSIONS = (1, 2)''', '''USAGE_CACHE_VERSIONS = (2,)''',
     [CACHE_V1, EXPIRED]),
    ("an old record not marked old", MET,
     '''            kept[key] = {"at": entry["at"], "record": {**record, "profile": None}, "old": True}''',
     '''            kept[key] = {"at": entry["at"], "record": {**record, "profile": None}}''', [CACHE_V1, EXPIRED]),
    ("the old mark of a version 2 cache forgotten", MET,
     '''        if version != USAGE_CACHE_VERSION or entry.get("old") is True:''',
     '''        if version != USAGE_CACHE_VERSION:''', [LIMIT_OLD]),
    ("old records read again before the new ones", MET,
     '''    for artifact, when in fresh:
        if fetched >= USAGE_LIMIT:''', '''    fresh, old = old + fresh, []
    for artifact, when in fresh:
        if fetched >= USAGE_LIMIT:''', [LIMIT_OLD]),
    ("old records never read again", MET,
     '''    for artifact, when in old:
        if fetched >= USAGE_LIMIT:''', '''    for artifact, when in []:
        if fetched >= USAGE_LIMIT:''', [CACHE_V1]),
    ("an old record whose download fails dropped", MET,
     '''        except GitHubError:
            continue
        fetched += 1''', '''        except GitHubError:
            del kept[str(artifact["id"])]
            continue
        fetched += 1''', [FAILED_OLD]),
    ("PROFILE.json's unread leaves the old records out", MET, '''records.unread + records.unprofiled''',
     '''records.unread''', [UNREAD]),
    ("the old records never counted", MET, '''sum(1 for entry in entries if entry.get("old")))''', '''0)''', [UNREAD]),
    # the behaviours no test pinned before the review
    ("a pull request's runs from the window alone", MET,
     '''profile.pull_profile(work, records.all) for work in works}''',
     '''profile.pull_profile(work, records.in_window) for work in works}''', [BEYOND]),
    ("every profiled run counted among the runs", MET, '''"actions_runs": len(summed),''',
     '''"actions_runs": len([record for record in records.all if record["profile"]]),''', [BEYOND]),
    ("the overhead taken from the look-back too", MET,
     '''profile.coordination(working, profiles, window.end, others, records.in_window)}''',
     '''profile.coordination(working, profiles, window.end, others, records.all)}''', [BEYOND]),
    ("the sides take no open work beside them", MET,
     '''profile.coordination(working, profiles, window.end, others, records.in_window)}''',
     '''profile.coordination(working, profiles, window.end, (), records.in_window)}''', [BEYOND]),
    ("sessions from the window's commits alone", MET,
     '''    lines = [profile.commit_lines(commit) for work in works for commit in work.commits]''',
     '''    lines = [profile.commit_lines(commit) for work in works for commit in work.commits
             if window.holds(commit_time(commit, "committer"))]''', [BEYOND]),
    ("the usage cache's version kept at 1", MET, '''USAGE_CACHE_VERSION = 2\n''', '''USAGE_CACHE_VERSION = 1\n''', [CACHE_V1]),
    ("the judge's commit keeps METRICS.json alone", MET,
     '''            if not line.endswith("\\t" + JUDGE_FILE)]''', '''            if line.endswith("\\tMETRICS.json")]''', [JUDGE]),
    # the workflow
    ("a branch holding PROFILE.json read as the project's own", YML,
     '''grep -v -x -e METRICS.json -e PROFILE.json -e JUDGE.json''', '''grep -v -x -e METRICS.json -e JUDGE.json''',
     [UNCHANGED, MOVED, KEPT_SUMS]),
    ("PROFILE.json left out of the unchanged test", YML,
     '''               && { [ ! -e "$profile" ] || same_as_branch PROFILE.json "$profile"; }; then''',
     '''               ; then''', [FIRST, MOVED]),
    ("the run's PROFILE.json never put on the branch", YML,
     '''            if [ -e "$profile" ]; then
              sums="$(git hash-object -w "$profile")" || return 1''',
     '''            if false; then
              sums="$(git hash-object -w "$profile")" || return 1''', [FIRST, MOVED]),
    ("the branch's PROFILE.json dropped when the run wrote none", YML,
     '''            elif [ -n "$previous" ] && sums="$(git rev-parse --verify --quiet "$previous:PROFILE.json")"; then''',
     '''            elif false; then''', [KEPT_SUMS]),
    ("collect not asked for PROFILE.json", YML,
     ''' --profile-out "$RUNNER_TEMP/PROFILE.json"''', '''''', [PATHS]),
    # the page
    ("the page's sample one count off", "docs/setup/metrics.md",
     '''"parallel": {"pull_requests": 11, "merged": 10, "profiled": 7''',
     '''"parallel": {"pull_requests": 11, "merged": 10, "profiled": 6''', [SAMPLE]),
]


def try_mutant(number, name, path, old, new, tests):
    work = HERE / f"tree-{number}"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(SRC, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    target = work / path
    text = target.read_text()
    if text.count(old) != 1:
        shutil.rmtree(work)
        return [f"BROKEN  {name}: the text to undo is there {text.count(old)} times"], 1
    target.write_text(text.replace(old, new))
    lines, missed = [], 0
    for test in tests:
        try:
            done = subprocess.run([sys.executable, "-m", "unittest", test], cwd=work, capture_output=True, text=True,
                                  timeout=300)
            bites = done.returncode != 0
            how = done.stderr.strip().splitlines()[-1]
        except subprocess.TimeoutExpired:
            bites, how = True, "timed out at 300 s"
        lines.append(f"{'bites ' if bites else 'MISSED'}  {name} [{test.rsplit('.', 1)[-1]}]: {how}")
        missed += not bites
    shutil.rmtree(work)
    return lines, missed


with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(lambda args: try_mutant(*args), [(n, *m) for n, m in enumerate(MUTANTS)]))
missed = 0
for lines, count in results:
    print("\n".join(lines))
    missed += count
print(f"{len(MUTANTS)} undoings;", "all bite" if not missed else f"{missed} missed")
