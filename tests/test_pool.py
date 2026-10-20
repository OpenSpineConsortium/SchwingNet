"""tools/pool.py reads how much of each Claude slot's limits is used, from
a run's rate-limit events and from cswap, keeps the readings on the branch
pool, and picks the slot a run should take. No test has a token or a
Claude account: the events are written here in the shape Claude Code's
stream-json gives them, and the branch is a scratch repository's."""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))

import pool  # noqa: E402
import tokens  # noqa: E402

# The clock the fixtures stand on: the real one, rounded, since pool.main reads the real clock and a
# frozen date rots once its resets pass (the first did on 2026-10-20, three days after it was written).
NOW = datetime.now(timezone.utc).replace(microsecond=0)
SOON = int((NOW + timedelta(hours=2)).timestamp())
LATER = int((NOW + timedelta(days=3)).timestamp())
# Git's background maintenance races a scratch repository's cleanup, and
# git passes no GIT_CONFIG_COUNT to the receive-pack it starts for a local
# remote, so each repository is told in its own config as well.
QUIET = {"gc.auto": "0", "gc.autoDetach": "false", "maintenance.auto": "false",
         "maintenance.autoDetach": "false", "receive.autogc": "false"}


def event(five, seven, status="allowed"):
    return {"type": "rate_limit_event", "uuid": "u", "session_id": "s",
            "rate_limit_info": {"status": status, "resetsAt": SOON, "rateLimitType": "five_hour", "utilization": five,
                                "unifiedWindows": {"five_hour": {"utilization": five, "resetsAt": SOON},
                                                   "seven_day": {"utilization": seven, "resetsAt": LATER}}}}


def record(slot, five, seven, source="run", at=NOW, resets=None):
    windows = {"five_hour": pool.window(five, resets or SOON), "seven_day": pool.window(seven, LATER)}
    return pool.reading(slot, source, windows, now=at)


def environment():
    env = dict(os.environ)
    env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"})
    env["GIT_CONFIG_COUNT"] = str(len(QUIET))
    for index, (key, value) in enumerate(QUIET.items()):
        env[f"GIT_CONFIG_KEY_{index}"], env[f"GIT_CONFIG_VALUE_{index}"] = key, value
    return env


class TheReadings(unittest.TestCase):
    def test_the_last_event_of_a_run_is_its_reading(self):
        messages = [{"type": "system"}, event(0.2, 0.1), {"type": "assistant"}, event(0.35, 0.12), {"type": "result"}]
        found = pool.observed(messages, "2", "run", now=NOW)
        self.assertEqual(found["windows"]["five_hour"], {"utilization": 0.35, "resetsAt": pool.iso(datetime.fromtimestamp(SOON, timezone.utc))})
        self.assertEqual(found["windows"]["seven_day"]["utilization"], 0.12)
        self.assertEqual((found["slot"], found["source"], found["status"]), ("2", "run", "allowed"))

    def test_an_array_and_json_lines_read_alike(self):
        messages = [event(0.5, 0.25)]
        self.assertEqual(pool.messages_in(json.dumps(messages)), messages)
        self.assertEqual(pool.messages_in("\n".join(json.dumps(each) for each in messages) + "\nnot json\n"), messages)

    def test_a_run_with_no_event_gives_no_reading(self):
        self.assertIsNone(pool.observed([{"type": "result"}], "1", "run"))
        self.assertIsNone(pool.observed([{"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}}], "1", "run"))

    def test_the_top_level_window_stands_in_without_unified_windows(self):
        info = {"status": "rejected", "rateLimitType": "seven_day", "utilization": 1.0, "resetsAt": LATER}
        found = pool.observed([{"type": "rate_limit_event", "rate_limit_info": info}], "3", "probe", now=NOW)
        self.assertEqual(found["windows"]["seven_day"]["utilization"], 1.0)
        self.assertEqual(found["status"], "rejected")

    def test_a_refusal_fills_its_window_and_wins_over_an_older_reading(self):
        refused = {"type": "rate_limit_event",
                   "rate_limit_info": {"status": "rejected", "rateLimitType": "five_hour", "resetsAt": SOON}}
        found = pool.observed([event(0.2, 0.1), refused], "1", "run", now=NOW)
        self.assertEqual(found["windows"]["five_hour"]["utilization"], 1.0)
        self.assertEqual(found["status"], "rejected")
        slot, until = pool.pick({"1": [found]}, ["1"], now=NOW)
        self.assertEqual(until, datetime.fromtimestamp(SOON, timezone.utc))

    def test_a_model_window_the_event_names_is_a_model_limit(self):
        info = {"status": "allowed_warning", "rateLimitType": "seven_day_opus", "utilization": 0.85, "resetsAt": LATER}
        found = pool.observed([{"type": "rate_limit_event", "rate_limit_info": info}], "1", "run", now=NOW)
        self.assertEqual([(each["name"], each["utilization"]) for each in found["scoped"]], [("Opus", 0.85)])

    def test_cswap_gives_the_per_model_limits_and_no_email(self):
        row = {"number": 4, "email": "someone@example.invalid", "usageFetchedAt": "2026-10-17T21:50:00Z",
               "usage": {"fiveHour": {"pct": 42.0, "resetsAt": "2026-10-17T23:00:00Z"},
                         "sevenDay": {"pct": 10.5, "resetsAt": "2026-10-20T00:00:00Z"},
                         "scoped": [{"name": "Fable", "pct": 80.0, "resetsAt": "2026-10-22T21:00:00Z"}]}}
        found = pool.from_cswap(row, "2")
        self.assertEqual(found["windows"]["five_hour"]["utilization"], 0.42)
        self.assertEqual(found["scoped"], [{"name": "Fable", "utilization": 0.8, "resetsAt": "2026-10-22T21:00:00Z"}])
        self.assertEqual(found["at"], "2026-10-17T21:50:00Z")
        self.assertNotIn("example.invalid", json.dumps(found))

    def test_cswap_falls_back_to_the_last_good_usage(self):
        row = {"number": 1, "usage": None, "lastGoodFetchedAt": "2026-10-17T20:00:00Z",
               "lastGoodUsage": {"fiveHour": {"pct": 5}}}
        self.assertEqual(pool.from_cswap(row, "1")["windows"]["five_hour"]["utilization"], 0.05)
        self.assertIsNone(pool.from_cswap({"number": 1, "usage": "token expired"}, "1"))

    def test_a_model_name_of_another_shape_is_left_out(self):
        row = {"usage": {"scoped": [{"name": "<script>", "pct": 1}, {"name": "Fable", "pct": 2}]}}
        self.assertEqual([each["name"] for each in pool.from_cswap(row, "1")["scoped"]], ["Fable"])


class ThePick(unittest.TestCase):
    def test_the_most_room_in_five_hours_then_seven_days(self):
        found = {"1": [record("1", 0.6, 0.1)], "2": [record("2", 0.2, 0.5)], "3": [record("3", 0.2, 0.3)]}
        self.assertEqual(pool.pick(found, ["1", "2", "3"], now=NOW), ("3", None))

    def test_a_slot_with_no_reading_comes_last(self):
        found = {"1": [record("1", 0.6, 0.5)], "2": [record("2", 0.3, 0.2)]}
        self.assertEqual(pool.pick(found, ["3", "1", "2"], now=NOW), ("2", None))
        self.assertEqual(pool.pick({}, ["3", "1"], now=NOW), ("3", None))

    def test_a_slot_at_the_threshold_is_passed_over(self):
        found = {"1": [record("1", 0.95, 0.1)], "2": [record("2", 0.5, 0.5)]}
        self.assertEqual(pool.pick(found, ["1", "2"], now=NOW), ("2", None))

    def test_every_slot_held_gives_the_one_free_first(self):
        early = int((NOW + timedelta(minutes=30)).timestamp())
        found = {"1": [record("1", 1.0, 0.1)], "2": [record("2", 0.99, 0.2, resets=early)]}
        slot, until = pool.pick(found, ["1", "2"], now=NOW)
        self.assertEqual(slot, "2")
        self.assertEqual(until, datetime.fromtimestamp(early, timezone.utc))

    def test_a_window_past_its_reset_is_empty(self):
        past = int((NOW - timedelta(minutes=1)).timestamp())
        found = {"1": [record("1", 1.0, 0.1, resets=past)], "2": [record("2", 0.3, 0.1)]}
        self.assertEqual(pool.pick(found, ["1", "2"], now=NOW), ("1", None))

    def test_the_newest_reading_of_each_window_counts(self):
        found = {"1": [record("1", 0.1, 0.1, at=NOW - timedelta(hours=1)), record("1", 0.97, 0.1, source="cswap")]}
        windows, _ = pool.current(found["1"], NOW)
        self.assertEqual((windows["five_hour"]["utilization"], windows["five_hour"]["source"]), (0.97, "cswap"))

    def test_a_full_model_limit_holds_the_slot(self):
        held = record("1", 0.1, 0.1, source="cswap")
        held["scoped"] = [{"name": "Fable", "utilization": 1.0, "resetsAt": pool.iso(NOW + timedelta(days=2))}]
        found = {"1": [held], "2": [record("2", 0.5, 0.5)]}
        self.assertEqual(pool.pick(found, ["1", "2"], now=NOW), ("2", None))

    def test_workers_of_one_run_are_dealt_different_free_slots(self):
        found = {"1": [record("1", 0.6, 0.1)], "2": [record("2", 0.2, 0.1)], "3": [record("3", 0.95, 0.1)]}
        dealt = [pool.pick(found, ["1", "2", "3"], now=NOW, spread=place)[0] for place in range(3)]
        self.assertEqual(dealt, ["2", "1", "2"])

    def test_a_full_window_with_no_reset_holds_for_five_hours_from_its_reading(self):
        held = record("1", 0.1, 0.1)
        held["windows"]["five_hour"] = {"utilization": 1.0}
        found = {"1": [held], "2": [record("2", 0.97, 0.1, resets=LATER)]}
        slot, until = pool.pick(found, ["1", "2"], now=NOW)
        self.assertEqual((slot, until), ("1", NOW + pool.UNKNOWN_HOLD))
        self.assertEqual(pool.pick(found, ["1"], now=NOW + timedelta(hours=6)), ("1", None))

    def test_the_list_of_slots(self):
        self.assertEqual(pool.parse_slots("3, 1,3 main"), ["3", "1", "main"])
        for text in ("33", "01", "x"):
            with self.assertRaises(pool.PoolError):
                pool.parse_slots(text)
        with self.assertRaises(pool.PoolError):
            pool.pick({}, [], now=NOW)


class TheBranch(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="pool-"))
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        self.env = environment()
        self.origin = self.folder / "origin.git"
        self.git("init", "--quiet", "--bare", str(self.origin))
        self.clone = self.folder / "clone"
        self.git("init", "--quiet", str(self.clone))
        for repository in (self.origin, self.clone):
            for key, value in QUIET.items():
                self.git("-C", str(repository), "config", key, value)
        self.git("-C", str(self.clone), "remote", "add", "origin", str(self.origin))

    def git(self, *args):
        return subprocess.run(["git", *args], check=True, capture_output=True, text=True, env=self.env).stdout

    def written(self, slot, five):
        path = self.folder / "readings" / f"slot-{slot}.run.json"
        pool.write(path, record(slot, five, 0.1))
        return path

    def test_readings_join_the_ones_there(self):
        old = os.environ.copy()
        os.environ.update(self.env)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(old)))
        pool.publish([self.written("1", 0.2)], cwd=self.clone)
        pool.publish([self.written("2", 0.4)], cwd=self.clone)
        pool.publish([self.written("1", 0.6)], cwd=self.clone)
        names = self.git("-C", str(self.origin), "ls-tree", "--name-only", "pool").split()
        self.assertEqual(names, ["slot-1.run.json", "slot-2.run.json"])
        kept = json.loads(self.git("-C", str(self.origin), "show", "pool:slot-1.run.json"))
        self.assertEqual(kept["windows"]["five_hour"]["utilization"], 0.6)
        self.assertEqual(self.git("-C", str(self.origin), "rev-list", "--count", "pool").strip(), "1")

    def test_two_jobs_on_one_slot_leave_the_newest_reading(self):
        older, newer = self.folder / "a" / "slot-1.run.json", self.folder / "b" / "slot-1.run.json"
        pool.write(newer, record("1", 0.7, 0.1, at=NOW))
        pool.write(older, record("1", 0.2, 0.1, at=NOW - timedelta(hours=1)))
        self.assertEqual(pool.newest_by_name([newer, older]), {"slot-1.run.json": newer})
        self.assertEqual(pool.newest_by_name([older, newer]), {"slot-1.run.json": newer})

    def test_a_name_that_is_not_a_reading_is_refused(self):
        stray = self.folder / "notes.json"
        stray.write_text("{}")
        with self.assertRaises(pool.PoolError):
            pool.publish([stray], cwd=self.clone)


class StrayFiles(unittest.TestCase):
    def test_a_file_that_is_not_a_reading_is_left_out(self):
        folder = Path(tempfile.mkdtemp(prefix="pool-stray-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        good = record("1", 0.2, 0.1)
        pool.write(folder / "slot-1.run.json", good)
        for name, body in (("slot-2.run.json", dict(record("2", 0.1, 0.1), windows=[1])),
                           ("slot-3.run.json", dict(record("3", 0.1, 0.1), slot="4")),
                           ("slot-5.probe.json", record("5", 0.1, 0.1)),
                           ("slot-6.run.json", dict(record("6", 0.1, 0.1), scoped="x"))):
            pool.write(folder / name, body)
        (folder / "slot-7.run.json").write_text("not json")
        self.assertEqual(list(pool.load(folder)), ["1"])
        self.assertEqual(pool.pick(pool.load(folder), ["1", "2"], now=NOW), ("1", None))


class TheAssignments(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="pool-assign-"))
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        self.path = self.folder / "accounts.json"
        self.readings = self.folder / "readings"
        self.readings.mkdir()
        pool.write(self.readings / "slot-1.run.json", record("1", 0.8, 0.1))
        pool.write(self.readings / "slot-2.run.json", record("2", 0.1, 0.1))

    def choose(self, worker, text="1,2"):
        return pool.choose(worker, text, self.path, self.readings, now=NOW)

    def test_no_file_runs_every_worker_on_main(self):
        self.assertEqual(self.choose("runner"), ("main", "default", None))

    def test_a_named_slot_auto_and_the_default(self):
        self.path.write_text(json.dumps({"default": "auto", "workers": {"docs": "3", "lead": "main"}}))
        self.assertEqual(self.choose("docs"), ("3", "assigned", None))
        self.assertEqual(self.choose("lead"), ("main", "assigned", None))
        self.assertEqual(self.choose("runner"), ("2", "auto", None))
        self.assertEqual(self.choose("runner", "")[0], "main")

    def test_auto_with_every_slot_held_says_until_when(self):
        self.path.write_text(json.dumps({"workers": {"runner": "auto"}}))
        pool.write(self.readings / "slot-2.run.json", record("2", 0.95, 0.1))
        self.assertEqual(self.choose("runner"), ("1", "auto", None))
        pool.write(self.readings / "slot-1.run.json", record("1", 0.99, 0.1))
        self.assertIsNotNone(self.choose("runner")[2])

    def test_auto_spreads_the_workers_of_one_run(self):
        self.path.write_text(json.dumps({"default": "auto"}))
        dealt = [pool.choose("runner", "1,2", self.path, self.readings, now=NOW, spread=place)[0] for place in (0, 1)]
        self.assertEqual(dealt, ["2", "1"])

    def test_a_list_is_auto_over_its_own_slots(self):
        self.path.write_text(json.dumps({"workers": {"review": ["1", "3"], "tests": ["4", "main"], "lone": ["4"]}}))
        self.assertEqual(self.choose("review", "1,2,3")[:2], ("1", "auto"))
        pool.write(self.readings / "slot-1.run.json", record("1", 0.99, 0.1))
        self.assertIsNotNone(self.choose("review", "1,2")[2])
        self.assertEqual(self.choose("tests", "1,2")[0], "main")
        with self.assertRaisesRegex(pool.PoolError, "holds none of them"):
            self.choose("lone", "1,2")

    def test_a_file_that_does_not_hold_together_is_refused(self):
        for body in ("[]", '{"workers": {"a": "33"}}', '{"workers": {"a": []}}', '{"workers": {"a": ["1", "1"]}}',
                     '{"workers": {"a": ["auto"]}}', '{"workers": {"a": [1]}}', '{"default": "x"}', '{"extra": 1}', "not json"):
            self.path.write_text(body)
            with self.assertRaises(pool.PoolError):
                self.choose("a")

    def test_the_repositorys_own_file_holds_together_where_there_is_one(self):
        pool.assignments(ROOT / pool.ASSIGNMENTS)

    def test_choose_prints_step_outputs(self):
        self.path.write_text(json.dumps({"workers": {"runner": "4"}}))
        with redirect_stdout(io.StringIO()) as printed, patch_stderr():
            self.assertEqual(pool.main(["choose", "--worker", "runner", "--pool", "1", "--assignments", str(self.path)]), 0)
        self.assertEqual(printed.getvalue(), "slot=4\n")


class TheSettings(unittest.TestCase):
    """SYMPHONY_CLAUDE_SETTINGS, as the Tokens tab's tiles write it."""

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="pool-settings-"))
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        self.path = self.folder / "accounts.json"
        self.path.write_text(json.dumps({"default": "auto", "workers": {"docs": "3"}}))
        self.readings = self.folder / "readings"
        self.readings.mkdir()
        pool.write(self.readings / "slot-1.run.json", record("1", 0.8, 0.1))
        pool.write(self.readings / "slot-2.run.json", record("2", 0.1, 0.1))

    def run_of(self, worker, settings, model=""):
        return pool.choose_run(worker, "1,2", self.path, self.readings, now=NOW,
                               settings=pool.parse_settings(json.dumps(settings), lambda words: None), model=model)

    def fable_spent(self, slot):
        held = record(slot, 0.1, 0.1, source="cswap")
        held["scoped"] = [{"name": "Fable", "utilization": 1.0, "resetsAt": pool.iso(NOW + timedelta(days=2))}]
        pool.write(self.readings / f"slot-{slot}.cswap.json", held)

    def test_a_slot_gives_its_model_and_effort(self):
        run = self.run_of("runner", {"2": {"model": "claude-opus-5-5", "effort": "high", "fallback": "claude-sonnet-5-5"}}, "haiku")
        self.assertEqual((run["slot"], run["model"], run["effort"], run["fallback"]),
                         ("2", "claude-opus-5-5", "high", "claude-sonnet-5-5"))
        self.assertEqual(self.run_of("runner", {}, "haiku")["model"], "haiku")
        self.assertEqual(self.run_of("docs", {"3": {"effort": "low"}})["effort"], "low")

    def test_a_spent_model_switches_to_the_fallback(self):
        self.fable_spent("2")
        settings = {"2": {"model": "claude-fable-5-1", "fallback": "claude-opus-5-5"}}
        run = self.run_of("runner", settings)
        self.assertEqual((run["slot"], run["model"], run["fallback"]), ("2", "claude-opus-5-5", ""))
        settings["2"].pop("fallback")
        self.assertEqual(self.run_of("runner", settings)["slot"], "1")

    def test_another_models_limit_holds_no_run_of_this_one(self):
        self.fable_spent("2")
        self.assertEqual(self.run_of("runner", {"2": {"model": "claude-sonnet-5-5"}})["slot"], "2")
        self.assertEqual(self.run_of("runner", {})["slot"], "1")

    def test_paused_and_waiting_for_resume_sit_out(self):
        self.assertEqual(self.run_of("runner", {"2": {"paused": True}})["slot"], "1")
        pool.write(self.readings / "slot-2.run.json", record("2", 0.95, 0.1, resets=SOON))
        waiting = {"2": {"resume": False}}
        later = NOW + timedelta(hours=3)
        settings = pool.parse_settings(json.dumps(waiting), lambda words: None)
        found = pool.load(self.readings)
        self.assertEqual(pool.pick_run(found, ["2"], settings, now=later)[1].year, 9999)
        self.assertEqual(pool.pick_run(found, ["2"], now=later)[1], None)
        waiting["2"]["resumedAt"] = pool.iso(NOW + timedelta(minutes=1))
        settings = pool.parse_settings(json.dumps(waiting), lambda words: None)
        self.assertEqual(pool.pick_run(found, ["2"], settings, now=later)[1], None)

    def test_values_that_do_not_hold_together_are_left_out(self):
        said = []
        text = json.dumps({"1": {"model": "opus; rm -rf /", "effort": "huge", "fallback": "x y", "resume": "no",
                                 "resumedAt": "soon"}, "33": {}, "2": "x"})
        self.assertEqual(pool.parse_settings(text, said.append), {"1": {}})
        self.assertEqual(len(said), 6)
        # a name of the right shape that no model answers to, or one with a
        # newline after it, is left out like any other
        for model in ("claude-opus-55", "claude-opus-5-5\n", "opus"):
            self.assertEqual(pool.parse_settings(json.dumps({"1": {"model": model}}), said.append), {"1": {}})
        for text in ("not json", "[]", ""):
            self.assertEqual(pool.parse_settings(text, said.append), {})

    def test_the_workers_own_model_takes_no_newline(self):
        with redirect_stdout(io.StringIO()) as printed, patch_stderr():
            pool.main(["choose", "--worker", "docs", "--pool", "1", "--assignments", str(self.path),
                       "--model", "haiku\nslot=8"])
        self.assertEqual(printed.getvalue(), "slot=3\n")

    def test_choose_prints_the_settings_as_step_outputs(self):
        settings = json.dumps({"3": {"model": "claude-opus-5-5", "effort": "max", "fallback": "claude-sonnet-5-5"}})
        with redirect_stdout(io.StringIO()) as printed, patch_stderr():
            self.assertEqual(pool.main(["choose", "--worker", "docs", "--pool", "1", "--assignments", str(self.path),
                                        "--settings", settings, "--model", "$(bad)"]), 0)
        self.assertEqual(printed.getvalue(),
                         "slot=3\nmodel=claude-opus-5-5\neffort=max\nfallback=claude-sonnet-5-5\n")


    def test_a_tokens_id_and_owner_are_kept_when_they_hold_their_shape(self):
        said = []
        found = pool.parse_settings(json.dumps({"3": {"id": "0a1b2c3d", "owner": "Gregory-Schwing-MD-PhD"},
                                                "4": {"id": "0A1B2C3D", "owner": "-greg"},
                                                "5": {"id": "0a1b2c3d\n", "owner": "greg\nslot=8"}}), said.append)
        self.assertEqual(found["3"], {"id": "0a1b2c3d", "owner": "Gregory-Schwing-MD-PhD"})
        self.assertEqual(found.get("4", {}), {})
        self.assertEqual(found.get("5", {}), {})
        self.assertEqual(len(said), 4)

    def test_the_id_is_a_step_output_for_the_credit(self):
        settings = json.dumps({"3": {"id": "0a1b2c3d"}})
        with redirect_stdout(io.StringIO()) as printed, patch_stderr():
            pool.main(["settings", "--slot", "3", "--settings", settings])
        self.assertEqual(printed.getvalue(), "id=0a1b2c3d\n")

    def test_the_pool_has_room_for_32(self):
        self.assertEqual(pool.parse_slots("1,32,main"), ["1", "32", "main"])
        with self.assertRaises(pool.PoolError):
            pool.parse_slots("33")
        self.assertTrue(pool.FILE_NAME.match("slot-32.run.json"))
        self.assertFalse(pool.FILE_NAME.match("slot-33.run.json"))
        self.assertFalse(pool.FILE_NAME.match("slot-01.run.json"))

class TheMainTokensSettings(unittest.TestCase):
    """@claude and the coordinator run on main and take its tile's settings."""

    def settings(self, text):
        with redirect_stdout(io.StringIO()) as printed, patch_stderr():
            self.assertEqual(pool.main(["settings", "--slot", "main", "--settings", text]), 0)
        return printed.getvalue()

    def test_mains_settings_as_step_outputs(self):
        text = json.dumps({"main": {"model": "claude-opus-5-5", "effort": "high", "fallback": "claude-sonnet-5-5"}, "1": {"effort": "low"}})
        self.assertEqual(self.settings(text), "model=claude-opus-5-5\neffort=high\nfallback=claude-sonnet-5-5\n")

    def test_none_or_a_bad_variable_prints_nothing(self):
        for text in ("", "not json", json.dumps({"main": {"model": "x; y", "effort": "huge"}})):
            self.assertEqual(self.settings(text), "")


def patch_stderr():
    from unittest.mock import patch
    return patch("sys.stderr", io.StringIO())


class TheCommandLine(unittest.TestCase):
    def test_observe_show_and_pick(self):
        folder = Path(tempfile.mkdtemp(prefix="pool-cli-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        execution = folder / "execution.json"
        execution.write_text(json.dumps([event(0.7, 0.2)]))
        readings = folder / "readings"
        readings.mkdir()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(pool.main(["observe", "--execution-file", str(execution), "--slot", "1", "--out", str(readings)]), 0)
            self.assertEqual(pool.main(["observe", "--execution-file", str(folder / "none.json"), "--slot", "2", "--out", str(readings)]), 0)
        self.assertEqual([path.name for path in readings.iterdir()], ["slot-1.run.json"])
        fresh = folder / "not-yet"
        with redirect_stdout(io.StringIO()):
            pool.main(["observe", "--execution-file", str(execution), "--slot", "1", "--source", "probe", "--out", str(fresh)])
        self.assertEqual([path.name for path in fresh.iterdir()], ["slot-1.probe.json"])
        pool.write(readings / "slot-2.probe.json", record("2", 0.1, 0.1, source="probe", at=datetime.now(timezone.utc)))
        with redirect_stdout(io.StringIO()) as printed:
            self.assertEqual(pool.main(["pick", str(readings), "--slots", "1,2"]), 0)
        self.assertEqual(printed.getvalue().strip(), "2")
        with redirect_stdout(io.StringIO()) as printed:
            pool.main(["show", str(readings)])
        shown = json.loads(printed.getvalue())
        self.assertEqual([row["slot"] for row in shown["slots"]], ["1", "2"])


class TheWizardSendsCswapUsage(unittest.TestCase):
    def target(self):
        return tokens.Target("org", "octo", ["widgets"])

    def test_each_remembered_account_becomes_its_slots_reading(self):
        folder = Path(tempfile.mkdtemp(prefix="pool-wizard-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = folder / "tokens.json"
        tokens.remember(path, tokens.read_settings(path), self.target(), 1, None, 3)
        tokens.remember(path, tokens.read_settings(path), self.target(), 2, None, 5)
        rows = [{"number": 3, "email": "a@example.invalid", "usage": {"fiveHour": {"pct": 12}}},
                {"number": 5, "usage": "token expired"}]
        readings, missing = tokens.usage_readings(self.target(), rows, tokens.read_settings(path), pool)
        self.assertEqual([(each["slot"], each["windows"]["five_hour"]["utilization"]) for each in readings], [("1", 0.12)])
        self.assertEqual(missing, [(2, 5)])

    def test_the_readings_go_on_the_branch_head(self):
        calls = []

        class FakeGh:
            def read(self, args):
                calls.append(args)
                return True, "headsha\n"

            def must(self, args, stdin=None):
                calls.append((args, stdin))
                return {"commits/headsha": "basetree", "trees": "newtree", "commits": "newcommit"}[
                    next(key for key in ("commits/headsha", "trees", "commits") if args[1].endswith(key) or args[3].endswith(key))] + "\n"

            def run(self, args):
                calls.append(args)
                return subprocess.CompletedProcess(args, 0, "", "")

        commit = tokens.send_usage(FakeGh(), "octo/widgets", [record("1", 0.12, 0.1, source="cswap")], pool)
        self.assertEqual(commit, "newcommit")
        tree_body = json.loads(next(stdin for args, stdin in (each for each in calls if isinstance(each, tuple)) if args[3].endswith("trees")))
        self.assertEqual(tree_body["base_tree"], "basetree")
        self.assertEqual([each["path"] for each in tree_body["tree"]], ["slot-1.cswap.json"])
        self.assertIn("force=false", calls[-1])

    def test_usage_goes_to_this_repository_and_each_one_also_names(self):
        from unittest import mock
        sent = []
        record_ = record("1", 0.12, 0.1, source="cswap")
        with mock.patch.object(tokens, "origin_repository", return_value=("octo", "widgets")), \
                mock.patch.object(tokens, "cswap_rows", return_value=[]), \
                mock.patch.object(tokens, "usage_readings", return_value=([record_], [])), \
                mock.patch.object(tokens, "send_usage", side_effect=lambda gh, repo, readings, pool: sent.append(repo) or "abcdef1"), \
                redirect_stdout(io.StringIO()):
            tokens.usage(None, self.target(), path=Path(tempfile.gettempdir()) / "no-such-tokens.json",
                         also=["coordbench", "widgets"])
        self.assertEqual(sent, ["octo/widgets", "octo/coordbench"])


if __name__ == "__main__":
    unittest.main()
