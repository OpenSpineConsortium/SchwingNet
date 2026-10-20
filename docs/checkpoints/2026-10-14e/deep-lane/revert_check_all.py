"""Every runner and bookkeeping fix of the fifth to ninth review
rounds reverted alone in the scratch clone, the test named for it
run first with the fix (it must pass) and then without (it must fail),
the file put back after each."""
import subprocess, sys
from pathlib import Path

W = Path(sys.argv[1])
ONLY = set(sys.argv[2:])
L, SH = "validation/lanes.py", "validation/shrink.py"
D = "tests.test_validation_deep."
R = D + "TheLaneAsOneRun."
REVERTS = {
    "U1 atomic write": (L, R + "test_the_results_file_is_replaced_whole_and_one_that_cannot_be_read_is_not_resumed",
        [('''    partial = file.with_name(file.name + ".partial")
    partial.write_text(json.dumps(results, indent=1, ensure_ascii=True) + "\\n", encoding="ascii")
    partial.replace(file)''', '''    file.write_text(json.dumps(results, indent=1, ensure_ascii=True) + "\\n", encoding="ascii")''')]),
    "U1 unreadable refused": (L, R + "test_the_results_file_is_replaced_whole_and_one_that_cannot_be_read_is_not_resumed",
        [('''        try:
            results = json.loads(file.read_text(encoding="ascii"))
        except ValueError as error:
            raise SystemExit(f"{file} cannot be read ({error}), so it is not resumed; run without --resume, "
                             f"or into another --out") from None''', '''        results = json.loads(file.read_text(encoding="ascii"))''')]),
    "U2 git in the record": (L, R + "test_a_resume_under_another_git_is_refused",
        [('''"code": deep.code_digest(), "git": git_version(), ''', '''"code": deep.code_digest(), ''')]),
    "U3a own pid": (L, R + "test_a_marker_naming_this_very_process_is_a_dead_run_s",
        [('''    if pid == os.getpid():
        return None
''', "")]),
    "X2 linked marker": (L, R + "test_the_marker_appears_with_its_process_s_id_in_it",
        [('''        try:
            os.link(mine, file)
        except FileExistsError:
            raise
        except OSError:
            with file.open("x", encoding="ascii") as marker:
                marker.write(f"{os.getpid()}\\n")
''', '''        with file.open("x", encoding="ascii") as marker:
            marker.write(f"{os.getpid()}\\n")
''')]),
    "U5 finished": (L, R + "test_a_run_that_did_not_finish_says_so_in_its_file",
        [('''        results["finished"], results["owed"] = False, None
''', '''        results["owed"] = None
''')]),
    "T4 pipe": (L, R + "test_a_result_larger_than_the_pipe_holds_lands",
        [('''            ready[connection] = part
''', "")]),
    "S2 stale files": (L, R + "test_a_resumed_search_s_files_replace_the_ones_its_stopped_run_wrote",
        [('''            (Path(out) / deep.TRACES / name).unlink(missing_ok=True)''', '''            pass''')]),
    "S3 out inside the code": (L, R + "test_an_out_folder_among_the_code_the_run_is_stamped_by_is_refused",
        [('''        if inside_the_code(self.out):''', '''        if False:''')]),
    "X1 ends by the signal": (L, R + "test_a_sigterm_to_the_runner_ends_its_workers_and_removes_the_marker",
        [('''        raise Terminated()''', '''        raise SystemExit(128 + signum)''')]),
    "kept_results inside the finally": (L, R + "test_a_resume_under_another_git_is_refused",
        [('''    try:
        results, began = kept_results(settings)
        results["asked"]''', '''    results, began = kept_results(settings)
    try:
        results["asked"]''')]),
    "N1 names under this run's traces": (L, R + "test_a_resumed_search_s_files_replace_the_ones_its_stopped_run_wrote",
        [('''        named = {Path(v["file"]).name for v in result["violations"]}
        for name in {Path(v["file"]).name for s in before for v in s["violations"]} - named:
            (Path(out) / deep.TRACES / name).unlink(missing_ok=True)''',
          '''        named = {v["file"] for v in result["violations"]}
        for file in {v["file"] for s in before for v in s["violations"]} - named:
            Path(file).unlink(missing_ok=True)''')]),
    "N2 owed": (L, R + "test_a_run_that_did_not_finish_says_so_in_its_file",
        [('''        results["owed"] = owed(settings, results)
        results["finished"] = not results["owed"]''', '''        results["finished"] = True''')]),
    "N3 waited for": (L, R + "test_the_parts_are_ended_and_waited_for",
        [('''    for child in children:
        child.join(max(0.0, ends - time.monotonic()))
''', "")]),
    "N6 no replay": (SH, D + "Shortening.test_a_trace_nothing_came_out_of_needs_no_replay_for_its_detail",
        [('''    detail = target[1] if trace == given else shown(start, scope, trace, target, known) or target[1]''',
          '''    detail = shown(start, scope, trace, target, known) or target[1]''')]),
    "N7 quiet in a part": (L, R + "test_a_part_ended_outside_its_work_ends_quietly",
        [('''        if os.getpid() != runner:
            raise SystemExit(128 + signum)
''', "")]),
    "N8 no hard links": (L, R + "test_a_folder_with_no_hard_links_still_takes_the_marker",
        [('''        try:
            os.link(mine, file)
        except FileExistsError:
            raise
        except OSError:
            with file.open("x", encoding="ascii") as marker:
                marker.write(f"{os.getpid()}\\n")
''', '''        os.link(mine, file)
''')]),
    "R7 files read under this run's folder": (L, R + "test_the_counterexamples_are_read_from_this_run_s_folder_however_a_run_spelt_it",
        [('''    files = counterexample_files(results, settings.out)''', '''    files = counterexample_files(results)''')]),
    "R7 files done by name": (L, R + "test_the_counterexamples_are_read_from_this_run_s_folder_however_a_run_spelt_it",
        [('''or file_names(c["files"]) == written}''', '''or c["files"] == counterexample_files(results)}''')]),
    "R8 resumed files named here": (L, R + "test_a_resumed_file_names_each_trace_file_as_this_run_spells_its_folder",
        [('''        name_files_here(results, settings.out)
''', "")]),
    "R7 held while a part is forked (parent)": (L, R + "test_a_sigterm_that_lands_as_a_part_is_forked_finds_the_part_listed", "UNHOLD"),
    "R7 held while a part is forked (part)": (L, R + "test_a_sigterm_that_reaches_a_part_as_it_is_forked_ends_it_before_its_work", "UNHOLD"),
    "R7 let in by the part": (L, R + "test_a_sigterm_that_reaches_a_part_as_it_is_forked_ends_it_before_its_work",
        [('''    being made ends it here, before its work."""
    release_signals()
''', '''    being made ends it here, before its work."""
''')]),
    "R7 killed after the grace": (L, R + "test_a_part_alive_after_the_grace_is_killed",
        [('''    for child in children:
        if child.is_alive():
            child.kill()
            child.join()
''', "")]),
    "R7 held while the run ends": (L, R + "test_a_signal_as_the_handler_is_put_back_waits_until_the_marker_is_removed",
        [('                with signals_held():\n                    end_workers()\n                    if in_main_thread:\n                        signal.signal(signal.SIGTERM, previous)\n                    marker.unlink(missing_ok=True)\n                    cleaned = True', '                end_workers()\n                if in_main_thread:\n                    signal.signal(signal.SIGTERM, previous)\n                marker.unlink(missing_ok=True)\n                cleaned = True')]),
    "R7 second signal, hold and loop": (L, R + "test_a_second_signal_while_the_run_ends_waits_until_it_has_ended",
        [('    finally:\n        stop.cleaning = True\n        cleaned = False\n        while not cleaned:\n            try:\n                with signals_held():\n                    end_workers()\n                    if in_main_thread:\n                        signal.signal(signal.SIGTERM, previous)\n                    marker.unlink(missing_ok=True)\n                    cleaned = True\n            except Exception:\n                raise\n            except BaseException as error:\n                if interrupted is None:\n                    interrupted = error\n        if terminated or stop.signalled:\n            os.kill(os.getpid(), signal.SIGTERM)\n            raise SystemExit(128 + signal.SIGTERM)\n        if interrupted is not None:\n            raise interrupted\n', '    finally:\n        end_workers()\n        if in_main_thread:\n            signal.signal(signal.SIGTERM, previous)\n        marker.unlink(missing_ok=True)\n    if terminated:\n        os.kill(os.getpid(), signal.SIGTERM)\n        raise SystemExit(128 + signal.SIGTERM)\n')]),
    "P8 F1 cleanup begun again": (L, R + "test_two_signals_that_land_as_a_part_is_forked_still_end_the_run_whole",
        [('    finally:\n        stop.cleaning = True\n        cleaned = False\n        while not cleaned:\n            try:\n                with signals_held():\n                    end_workers()\n                    if in_main_thread:\n                        signal.signal(signal.SIGTERM, previous)\n                    marker.unlink(missing_ok=True)\n                    cleaned = True\n            except Exception:\n                raise\n            except BaseException as error:\n                if interrupted is None:\n                    interrupted = error\n        if terminated or stop.signalled:\n            os.kill(os.getpid(), signal.SIGTERM)\n            raise SystemExit(128 + signal.SIGTERM)\n        if interrupted is not None:\n            raise interrupted\n', '    finally:\n        with signals_held():\n            end_workers()\n            if in_main_thread:\n                signal.signal(signal.SIGTERM, previous)\n            marker.unlink(missing_ok=True)\n    if terminated:\n        os.kill(os.getpid(), signal.SIGTERM)\n        raise SystemExit(128 + signal.SIGTERM)\n')]),
    "P8 F2 mask read first": (L, R + "test_a_handler_that_runs_as_the_hold_begins_leaves_nothing_held",
        [("""    before = signal.pthread_sigmask(signal.SIG_BLOCK, ())
    try:
        signal.pthread_sigmask(signal.SIG_BLOCK, HELD)
        yield""", """    before = signal.pthread_sigmask(signal.SIG_BLOCK, HELD)
    try:
        yield""")]),
    "P8 F4 own file's write": (L, R + "test_the_file_under_the_process_s_own_name_goes_however_the_marker_fails",
        [("""    try:
        mine.write_text(f"{os.getpid()}\\n", encoding="ascii")
        try:""", """    mine.write_text(f"{os.getpid()}\\n", encoding="ascii")
    try:
        try:""")]),
    "P8 daemon parts": (L, R + "test_an_exit_past_the_cleanup_ends_the_parts",
        [(", name=part, daemon=True)", ", name=part)")]),
    "P9 F1 a handler's exit in the cleanup taken": (L, R + "test_a_sigint_while_a_sigterm_ends_the_run_leaves_it_ended_by_the_sigterm",
        [('            except Exception:\n                raise\n            except BaseException as error:\n                if interrupted is None:\n                    interrupted = error\n',
          '            except Terminated:\n                terminated = True\n')]),
    "P9 F1 raised once it is done": (L, R + "test_a_sigint_held_until_the_cleanup_ends_is_raised_once_it_is_done",
        [('        if interrupted is not None:\n            raise interrupted\n', '        if interrupted is not None:\n            pass\n')]),
    "P9 F2 any handler's exit": (L, R + "test_a_caller_s_own_sigint_handler_while_a_sigterm_ends_the_run_leaves_it_ended_by_the_sigterm",
        [('            except BaseException as error:\n', '            except KeyboardInterrupt as error:\n')]),
    "P9 F3 recorded once the cleanup has begun": (L, R + "test_two_signals_as_the_cleanup_begins_still_end_the_run_whole",
        [('    finally:\n        stop.cleaning = True\n', '    finally:\n')]),
    "P9 F3 cleanup begun again": (L, R + "test_two_signals_as_the_cleanup_begins_still_end_the_run_whole",
        [('        cleaned = False\n        while not cleaned:\n            try:\n                with signals_held():\n                    end_workers()\n                    if in_main_thread:\n                        signal.signal(signal.SIGTERM, previous)\n                    marker.unlink(missing_ok=True)\n                    cleaned = True\n            except Exception:\n                raise\n            except BaseException as error:\n                if interrupted is None:\n                    interrupted = error\n',
          '        with signals_held():\n            end_workers()\n            if in_main_thread:\n                signal.signal(signal.SIGTERM, previous)\n            marker.unlink(missing_ok=True)\n')]),
    "R7 the runner told by its id": (L, R + "test_a_runner_multiprocessing_started_ends_by_the_signal",
        [('''        if os.getpid() != runner:''', '''        if multiprocessing.parent_process() is not None:''')]),
    "R7 own file goes": (L, R + "test_the_file_under_the_process_s_own_name_goes_however_the_marker_fails",
        [('''    finally:
        mine.unlink(missing_ok=True)''', '''    else:
        mine.unlink()''')]),
    "S1 the detail the shortened trace shows": (L, "tests.test_validation_soak.TheSoak.test_a_file_names_the_detail_its_own_steps_show",
        [("            shown = shorter.detail or detail\n", "            shown = detail\n")]),
    "T10 W1 a copy shares git's word": ("validation/model.py", "tests.test_validation_git_store.TheStore.test_under_lenient_rules_a_branch_git_calls_behind_is_owed_nothing_over_git_too",
        [("""        said = self.standings.get((head, main)) if self.standings else None
        if said is not None:
            return said
""", "")]),
    "T10 M2 the fake's standing through git": ("validation/model.py", "tests.test_validation_git_store.TheStore.test_standing_and_files_changed_come_from_git",
        [("        return self.standing_at(pull.sha) if pull.fork else self.standing(pull.head)\n",
          "        return self.standing_at(self.pull_head(pull))\n")]),
    "T11 W8 the split run's states share git's word": ("validation/cycle.py", "tests.test_validation_git_store.TheStore.test_under_lenient_rules_a_branch_git_calls_behind_is_owed_nothing_over_git_too",
        [("half.started_from = model.copied_whole()", "half.started_from = __import__('copy').deepcopy(model)"),
         ("half.planned = model.copied_whole()", "half.planned = __import__('copy').deepcopy(model)")]),
    "T11 W8 a copy of a split run shares it": ("validation/model.py", "tests.test_validation_git_store.TheStore.test_every_copy_shares_the_words_git_gave_at_every_level",
        [("            copied = self.copied_whole()\n            copied.store = None\n            return copied\n",
          "            copied = copy.deepcopy(self)\n            copied.store = None\n            copied.standings = self.standings\n            return copied\n")]),
}


def unhold(text):
    start = text.index("            with signals_held():\n                # A signal that lands")
    end = text.index("                running[part] = (process, ours)\n", start) + len("                running[part] = (process, ours)\n")
    body = [line for line in text[start:end].splitlines(keepends=True)[1:] if not line.lstrip().startswith("#")]
    return text[:start] + "".join(line[4:] for line in body) + text[end:]


def run(test):
    done = subprocess.run([sys.executable, "-m", "unittest", test], cwd=W, capture_output=True, text=True, timeout=600)
    return done.returncode, [l for l in done.stderr.splitlines() if l.startswith(("OK", "FAILED"))]


bad = 0
for name, (path, test, swaps) in REVERTS.items():
    if ONLY and not any(word in name for word in ONLY):
        continue
    code, last = run(test)
    if code:
        bad += 1
        print(f"{name}: FAILS WITH THE FIX {last}", flush=True)
        continue
    file = W / path
    keep = file.read_text()
    try:
        if swaps == "UNHOLD":
            text = unhold(keep)
        else:
            text = keep
            for old, new in swaps:
                assert text.count(old) == 1, (name, old[:60])
                text = text.replace(old, new)
        file.write_text(text)
        code, last = run(test)
        bad += code == 0
        print(f"{name}: passes with the fix; {'fails without it' if code else 'PASSES WITHOUT IT'} {last}", flush=True)
    finally:
        file.write_text(keep)
print("all hold" if bad == 0 else f"{bad} do not hold")
