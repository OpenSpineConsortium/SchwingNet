"""tools/economics.py: prices, what each pull request cost from its commits'
trailers and the Actions runs that name it, the window's totals, and the
comparison of work done alone with work done in parallel, each ratio over
1 when working in parallel did better."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import economics  # noqa: E402

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


def at(hours):
    return T0 + timedelta(hours=hours)


def commit(message):
    return {"sha": "x", "commit": {"message": message}}


def trailer(session, seconds, **models):
    parts = [f"session={session}", f"seconds={seconds}"]
    parts += [f"{model.replace('_', '-')}={','.join(str(n) for n in counts)}" for model, counts in models.items()]
    return "Work\n\nSymphony-Usage: v1 " + " ".join(parts) + "\n"


def record(models, workflow="workers", job="worker", issue=None, pull=None, seconds=60.0):
    return economics.actions_record({"v": 1, "source": "actions", "workflow": workflow, "job": job, "issue": issue,
                                     "pull": pull, "seconds": seconds, "models": models})


class Prices(unittest.TestCase):
    def test_names_are_read_as_the_table_spells_them(self):
        self.assertEqual(economics.normalized("Claude-Opus-4-1-20250805"), "claude-opus-4-1")
        self.assertEqual(economics.normalized("claude-sonnet-5-5[1m]"), "claude-sonnet-5-5")
        self.assertEqual(economics.family("claude-haiku-5-5"), "haiku")
        self.assertEqual(economics.family("some-model"), "other")

    def test_a_usage_is_priced_by_kind_and_an_unknown_model_counted_apart(self):
        usd, unpriced = economics.priced({"claude-opus-5-5": [1_000_000, 0, 0, 1_000_000, 1_000_000],
                                          "mystery": [5, 0, 0, 0, 5]})
        self.assertAlmostEqual(usd, 4.0 + 0.20 + 20.0)
        self.assertEqual(unpriced, 10)
        usd, _ = economics.priced({"claude-sonnet-5-5": [0, 1_000_000, 1_000_000, 0, 0]})
        self.assertAlmostEqual(usd, 2.5 + 4.0)

    def test_every_price_row_has_five_rates_and_writes_cost_more_than_reads(self):
        for model, rates in economics.PRICES.items():
            self.assertEqual(len(rates), 5, model)
            self.assertLess(rates[3], rates[0], model)
            self.assertLess(rates[1], rates[2], model)


class Attribution(unittest.TestCase):
    def test_a_pull_request_costs_its_trailers_and_the_runs_that_name_it_or_its_claim(self):
        work = economics.Work(40, claim=12, commits=[commit(trailer("aaaa", 30, m=[1, 0, 0, 10, 2])),
                                                      commit(trailer("bbbb", 5, m=[1, 0, 0, 0, 1])), commit("plain")])
        records = [record({"m": [5, 0, 0, 0, 5]}, pull=40), record({"m": [7, 0, 0, 0, 0]}, issue=12),
                   record({"m": [100, 0, 0, 0, 0]}, issue=99)]
        spent = economics.spent_on(work, records)
        self.assertEqual(spent.models, {"m": [14, 0, 0, 10, 8]})
        self.assertEqual((spent.seconds, spent.sessions, spent.runs), (155.0, {"aaaa", "bbbb"}, 2))
        self.assertEqual(economics.unattributed([work], records), [records[2]])

    def test_a_record_that_does_not_hold_together_is_none(self):
        self.assertIsNone(economics.actions_record({"v": 2}))
        self.assertIsNone(economics.actions_record("text"))
        kept = economics.actions_record({"v": 1, "source": "actions", "models": {"m": [1, 2, 3, 4, "5"], "n": [1] * 5},
                                         "seconds": -3, "issue": "12"})
        self.assertEqual((kept["models"], kept["seconds"], kept["issue"]), ({"n": [1] * 5}, 0.0, None))

    def test_a_record_is_read_as_anyones_json_and_never_raised_on(self):
        # Any workflow run can upload a record: each part of the wrong kind,
        # or past the bound a JSON number holds exactly, is passed over.
        base = {"v": 1, "source": "actions"}
        for seconds in (float("inf"), float("nan"), 10 ** 400, 2 ** 53, True, -1, "60"):
            self.assertEqual(economics.actions_record({**base, "seconds": seconds})["seconds"], 0.0, seconds)
        self.assertEqual(economics.actions_record({**base, "seconds": 2 ** 53 - 1})["seconds"], float(2 ** 53 - 1))
        for models in ([1, 2], "m", 5, None):
            self.assertEqual(economics.actions_record({**base, "models": models})["models"], {}, models)
        counts = {"m": [1, 0, 0, 0, True], "n": [1, 0, 0, 0, 2 ** 53], "[" * 82: [1] * 5, "-x": [1] * 5,
                  "claude-opus-4-6[1m]": [1] * 5}
        self.assertEqual(economics.actions_record({**base, "models": counts})["models"],
                         {"claude-opus-4-6[1m]": [1] * 5})
        odd = economics.actions_record({**base, "workflow": ["coordinator"], "job": 5, "issue": True, "pull": 2 ** 60})
        self.assertEqual((odd["workflow"], odd["job"], odd["issue"], odd["pull"]), ("", "", None, None))

    def test_the_kept_form_of_a_record_is_what_is_read_of_it_and_reads_the_same(self):
        uploaded = {"v": 1, "source": "actions", "workflow": "coordinator", "job": "plan", "issue": 9, "pull": None,
                    "seconds": 95, "models": {"m": [1, 2, 3, 4, 5]}, "worker": "", "turns": 12, "deep": [[[]]]}
        kept = economics.kept_record(uploaded)
        self.assertEqual(kept, {"v": 1, "source": "actions", "workflow": "coordinator", "job": "plan", "issue": 9,
                                "pull": None, "seconds": 95.0, "models": {"m": [1, 2, 3, 4, 5]}, "profile": None})
        self.assertEqual(economics.kept_record(kept), kept)
        profiled = economics.kept_record({**uploaded, "profile": {"calls": 18, "peak": 80000, "paths": ["a.py"],
                                                                  "mcp__crm__lookup": 3}})
        self.assertEqual(profiled["profile"], {"calls": 18, "peak": 80000})
        self.assertEqual(economics.kept_record(profiled), profiled)
        self.assertIsNone(economics.kept_record({"v": 1, "source": "elsewhere"}))

    def test_a_runs_profile_is_its_counts_alone(self):
        # The block tools/usage.py writes from tools/profile.py: a commit's
        # Symphony-Profile counts over the whole run. Anyone's JSON again,
        # so a count of the wrong kind or past the bound is passed over, and
        # any other key, a path or a tool's name, never reaches the cache.
        base = {"v": 1, "source": "actions"}
        block = {"calls": 18, "failed": 0, "peak": 80000, "tool_seconds": 0, "rereads": True, "reads": -1,
                 "read_bytes": 2 ** 53, "drops": 1.5, "repeated": "2", "compactions": None, "paths": ["secret.py"],
                 "mcp__crm__lookup": 3}
        self.assertEqual(economics.actions_record({**base, "profile": block})["profile"],
                         {"calls": 18, "failed": 0, "peak": 80000, "tool_seconds": 0})
        for block in (None, [1, 2], "calls=1", 5, {}, {"paths": ["x"]}, {"calls": float("inf")}):
            self.assertIsNone(economics.actions_record({**base, "profile": block})["profile"], block)
        self.assertIsNone(economics.actions_record(base)["profile"])

    def test_a_run_that_made_no_call_has_no_profile(self):
        # usage.run_profile writes every count 0 for a run whose execution
        # file holds no call; read as a profile, it would pull the median
        # peak down and dilute the per-merge ratios.
        base = {"v": 1, "source": "actions"}
        zeros = dict.fromkeys(economics.usage.profiler().TRAILER_FIELDS, 0)
        self.assertIsNone(economics.actions_record({**base, "profile": zeros})["profile"])
        for kept in ({**zeros, "calls": 1}, {**zeros, "peak": 1}):
            self.assertEqual(economics.actions_record({**base, "profile": kept})["profile"], kept)


class Window(unittest.TestCase):
    def test_the_bill_is_the_windows_trailers_and_runs_and_the_delivery_its_pull_requests(self):
        works = [economics.Work(1, commits=[commit(trailer("s1", 100, claude_opus_5_5=[1000, 0, 0, 0, 1000]))],
                                merged=at(5), check_failures=1),
                 economics.Work(2, commits=[commit("x"), commit("y")])]
        records = [record({"claude-haiku-5-5": [10, 0, 0, 0, 10]}, workflow="coordinator", job="plan", issue=50,
                          seconds=20.0)]
        commits = [c for w in works for c in w.commits]
        found = economics.economics(works, commits, records, records, reverts=1, unread=3)
        self.assertEqual(tuple(found), economics.ECONOMICS_KEYS)
        self.assertEqual((found["prices_as_of"], found["actions_runs_unread"]), (economics.PRICES_AS_OF, 3))
        self.assertEqual((found["pull_requests"], found["pull_requests_measured"], found["merged"]), (2, 1, 1))
        self.assertEqual((found["tokens_input"], found["tokens_output"], found["tokens_total"]), (1010, 1010, 2020))
        self.assertEqual(found["tokens_by_family"], {"fable": 0, "opus": 2000, "sonnet": 0, "haiku": 20, "other": 0})
        self.assertAlmostEqual(found["estimated_usd"], 0.024 + 0.000006, places=4)
        self.assertAlmostEqual(found["coordinator_usd"], 0.0, places=4)
        self.assertEqual((found["claude_seconds"], found["commits"], found["check_failures"], found["reverts"]),
                         (120, 3, 1, 1))
        self.assertEqual((found["tokens_per_merge"], found["commits_per_merge"]), (2020, 3))
        self.assertEqual((found["sessions"], found["actions_runs"]), (1, 1))

    def test_nothing_merged_leaves_the_per_merge_figures_empty(self):
        found = economics.economics([economics.Work(1)], [], [], [], unread=None)
        self.assertIsNone(found["usd_per_merge"])
        self.assertIsNone(found["actions_runs_unread"])
        self.assertEqual(found["tokens_total"], 0)

    def test_a_commit_made_before_the_window_is_not_on_its_bill_but_counts_for_its_pull_request(self):
        early = commit(trailer("s9", 50, claude_opus_5_5=[500, 0, 0, 0, 0]))
        late = commit(trailer("s9", 50, claude_opus_5_5=[100, 0, 0, 0, 0]))
        works = [economics.Work(7, commits=[early, late], merged=at(3))]
        found = economics.economics(works, [late], [], [])
        self.assertEqual((found["tokens_total"], found["pull_requests_measured"]), (100, 1))
        self.assertEqual(found["tokens_per_merge"], 100)


class AloneAndParallel(unittest.TestCase):
    NOW = at(100)

    def works(self):
        def work(number, start, end, merged=True, tokens=1000, commits=1, failures=0, first=True, kind="person"):
            message = trailer(f"s{number}", 600, claude_sonnet_5_5=[tokens, 0, 0, 0, 0])
            return economics.Work(number, kind=kind, start=at(start), end=at(end), merged=at(end) if merged else None,
                                  opened=at(start), commits=[commit(message)] + [commit("x")] * (commits - 1),
                                  check_failures=failures, first_check=first)
        alone = [work(1, 0, 10, tokens=4000, commits=4, failures=2, first=False), work(2, 20, 30, tokens=2000)]
        parallel = [work(3, 40, 44, tokens=1000), work(4, 41, 45, tokens=1000, kind="workflow_agents"),
                    work(5, 42, 46, merged=False, tokens=500)]
        bot = [work(6, 0, 50, kind="automation")]
        return alone + parallel + bot

    def test_the_sides_split_by_whether_other_work_went_on_beside(self):
        found = economics.coordination(self.works(), [], self.NOW)
        self.assertEqual((found["alone"]["pull_requests"], found["parallel"]["pull_requests"]), (2, 3))
        self.assertEqual((found["alone"]["merged"], found["parallel"]["merged"]), (2, 2))
        self.assertEqual((found["alone"]["tokens"], found["parallel"]["tokens"]), (6000, 2500))
        self.assertEqual(found["alone"]["active_seconds"], 20 * 3600)
        self.assertEqual(found["parallel"]["active_seconds"], 6 * 3600)
        self.assertEqual(tuple(found["alone"]), economics.GROUP_KEYS)

    def test_each_ratio_is_over_one_where_parallel_did_better(self):
        ratios = economics.coordination(self.works(), [], self.NOW)["ratios"]
        self.assertEqual(tuple(ratios), economics.RATIO_KEYS)
        self.assertAlmostEqual(ratios["tokens_per_merge"], (6000 / 2) / (2500 / 2), places=4)
        self.assertAlmostEqual(ratios["latency"], (10 * 3600) / (4 * 3600), places=4)
        self.assertAlmostEqual(ratios["throughput"], (2 / 6) / (2 / 20), places=4)
        self.assertAlmostEqual(ratios["first_check_pass"], 1.0 / 0.5, places=4)
        self.assertAlmostEqual(ratios["commits_per_merge"], (5 / 2) / (3 / 2), places=4)
        self.assertAlmostEqual(ratios["failures_per_pull_request"], ((2 + 1) / 3) / ((0 + 1) / 4), places=4)

    def test_the_coordinators_runs_cost_the_parallel_side(self):
        records = [record({"claude-sonnet-5-5": [1_000_000, 0, 0, 0, 0]}, workflow="coordinator", job="plan", issue=77)]
        found = economics.coordination(self.works(), records, self.NOW, window_records=records)
        self.assertEqual(found["parallel"]["tokens"], 2500 + 1_000_000)
        self.assertAlmostEqual(found["parallel"]["estimated_usd"], 2.0 + 2500 * 2 / 1e6, places=4)

    def test_the_sides_and_the_overhead_are_what_the_profiles_sums_take_too(self):
        # tools/profile.py splits the same pull requests and charges the same
        # runs, so the two blocks always compare the same work.
        alone, parallel = economics.sides(self.works(), self.NOW)
        self.assertEqual(([w.number for w in alone], [w.number for w in parallel]), ([1, 2], [3, 4, 5]))
        records = [record({}, workflow="coordinator", job="plan", issue=77),
                   record({}, workflow="coordinator", job="settle", pull=3),
                   record({}, workflow="workers", job="worker", issue=78)]
        self.assertEqual(economics.overhead(self.works(), records), records[:1])

    def test_only_measured_merges_divide_the_tokens(self):
        works = self.works()
        works[1].commits = [commit("no trailer")]
        found = economics.coordination(works, [], self.NOW)
        self.assertEqual((found["alone"]["merged"], found["alone"]["measured_merged"]), (2, 1))
        self.assertAlmostEqual(found["ratios"]["tokens_per_merge"], (4000 / 1) / (2500 / 2), places=4)

    def test_a_side_with_nothing_gives_no_ratio(self):
        found = economics.coordination(self.works()[:2], [], self.NOW)
        self.assertEqual(found["parallel"]["pull_requests"], 0)
        self.assertTrue(all(value is None for value in found["ratios"].values()))

    def waited(self, *waits):
        """The alone side of merged pull requests one a day apart, each
        merged the given seconds after it opened."""
        works = []
        for number, wait in enumerate(waits, start=1):
            opened = at(24 * number)
            works.append(economics.Work(number, start=opened, end=opened + timedelta(seconds=abs(wait)),
                                        merged=opened + timedelta(seconds=wait), opened=opened))
        return economics.coordination(works, [], self.NOW)["alone"]

    def test_the_median_wait_to_merge_rounds_half_up_as_the_durations_do(self):
        self.assertEqual(self.waited(1, 2)["open_to_merge_median"], 2)
        self.assertEqual(self.waited(2, 3)["open_to_merge_median"], 3)
        self.assertEqual(self.waited(4, 1, 2)["open_to_merge_median"], 2)
        self.assertEqual(economics.median_seconds([2, 3]), 3)
        self.assertIsNone(economics.median_seconds([]))

    def test_a_merge_dated_before_its_opening_is_left_out_of_the_median(self):
        found = self.waited(0, 10, -100)
        self.assertEqual((found["merged"], found["open_to_merge_median"]), (3, 5))

    def test_a_wait_counts_in_whole_seconds_as_the_durations_do(self):
        opened = at(24)
        work = economics.Work(1, start=opened, end=opened + timedelta(seconds=2),
                              merged=opened + timedelta(seconds=1, milliseconds=600), opened=opened)
        found = economics.coordination([work], [], self.NOW)["alone"]
        self.assertEqual(found["open_to_merge_median"], 1)

    def test_work_from_before_the_window_counts_as_beside(self):
        works = self.works()[:1]
        earlier = [economics.Work(9, start=at(-5), end=at(2))]
        found = economics.coordination(works, [], self.NOW, others=earlier)
        self.assertEqual((found["alone"]["pull_requests"], found["parallel"]["pull_requests"]), (0, 1))


if __name__ == "__main__":
    unittest.main()
