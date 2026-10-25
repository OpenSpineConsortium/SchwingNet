"""tools/storage_panel.py: the planner's model (the selection string, the totals, the overlaps, the
refusals, the order of the sets and what the kept ones are worth) against cases worked by hand, the
page's JavaScript mirror of it against the Python on one plan, the build's determinism, the check's
failure on a changed page, and the fetch's refusals of a redirect and of a missing token."""

import base64
import contextlib
import copy
import hashlib
import http.server
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("storage_panel", ROOT / "tools" / "storage_panel.py")
panel = importlib.util.module_from_spec(spec)
sys.modules["storage_panel"] = panel
spec.loader.exec_module(panel)

TB = 1_000_000_000_000


def a_set(sid, **fields):
    s = {"id": sid, "name": sid.replace("_", " ").title(), "group": "ct", "reach": "held", "fetchable": False,
         "status": "held", "location": "lab", "bytes": TB, "bytes_known": True, "licence": "open", "rebuild": True,
         "frozen": True, "overlap": []}
    s.update(fields)
    return s


def a_value(**fields):
    """A set's value block as spine-datasets #249 writes it, every field unknown unless given."""
    v = {"people": None, "scans": None, "level_truth": "unknown", "level_truth_people": None, "level_truth_scans": None,
         "transitional_people": None, "regions": [], "spine": None, "masks_by_level": None, "masks_held": False,
         "segmented": False, "prior_source": False, "paired": False, "tier": None, "modality": "ct"}
    v.update(fields)
    return v


def plan_fixture():
    """Six sets: two held (one restricted, overlapping a fetchable twin), a fetchable twin with a stated
    size, a fetchable set with no size, a gated set nobody can fetch, and a fetchable set large enough
    to pass the target; the home not read yet, one request pending. Each set but the gated one has a
    value block, as the feed has since spine-datasets #249, and the plan the power block that goes with
    them; the gated set has none, as a feed written before #249 has none."""
    return {
        "format": panel.FORMAT, "built_at": "2026-10-24T20:52:07Z", "read_at": "2026-10-24T17:15:28Z",
        "target_bytes": 20 * TB,
        "requests": [{"number": 7, "url": "https://github.com/OpenSpineConsortium/spine-datasets/pull/7", "selection": "-old_set"}],
        "volume": {"quota_bytes": 21_990_230_000_000, "used_bytes": 17_553_250_000_000, "read_at": "2026-10-24T17:15:28Z",
                   "datasets_bytes": 7_626_035_136_479, "other_bytes": 9_927_214_863_521},
        "home": {"quota_bytes": 4 * TB, "used_bytes": None, "read_at": None},
        "power": {"assumed_accuracy": 0.5, "confidence": 0.95, "half_width": 0.05, "z": 1.959964, "people_needed": 385,
                  "level_truth_people_kept": 2500, "level_truth_people_unread": 0, "level_truth_scans_kept": 2520,
                  "transitional_people_kept": 3, "kept_is_upper_bound": True},
        "sets": [
            a_set("big_ct", bytes=980_000_000_000, licence="restricted",
                  overlap=[{"with": "twin_ct", "patients": 120, "series": 400, "same_scans": 90, "same_bytes": 50_000_000_000}],
                  value=a_value(people=980, scans=1000, level_truth="read", level_truth_people=500, level_truth_scans=520,
                                transitional_people=3, regions=["spine", "abdomen"], spine=True, masks_by_level="read",
                                masks_held=True, segmented=True, prior_source=True)),
            a_set("small_films", group="films", bytes=6_338_426_763,
                  value=a_value(people=2000, scans=2000, level_truth="read", level_truth_people=2000, level_truth_scans=2000,
                                paired=True, tier="A", modality="films")),
            a_set("twin_ct", reach="get", fetchable=True, status="todo", location="none", bytes=300_000_000_000,
                  bytes_known=False, frozen=False,
                  overlap=[{"with": "big_ct", "patients": 120, "series": 400, "same_scans": 90, "same_bytes": 50_000_000_000}],
                  value=a_value(people=300, scans=310, level_truth="read", level_truth_people=300, level_truth_scans=310,
                                regions=["abdomen", "pelvis"], spine=True, masks_by_level="automatic", segmented=True,
                                prior_source=True)),
            a_set("no_size_yet", reach="get", fetchable=True, status="requested", location="none", bytes=None,
                  bytes_known=False, frozen=False, licence="unknown",
                  value=a_value(people=50, level_truth="automatic", regions=["chest"], spine=False, masks_by_level="automatic",
                                segmented=True, prior_source=True)),
            a_set("gated_set", reach="gated", fetchable=False, status="needs-owner", location="none", bytes=None,
                  bytes_known=False, frozen=False, licence="restricted"),
            a_set("huge_ct", reach="get", fetchable=True, status="todo", location="none", bytes=3 * TB, frozen=False,
                  value=a_value(regions=["whole body"], spine=True, segmented=True)),
        ],
    }


class TheSelection(unittest.TestCase):
    def setUp(self):
        self.plan = plan_fixture()

    def sel(self, choices):
        return panel.selection(self.plan, choices)

    def test_no_choice_is_an_empty_selection(self):
        self.assertEqual(self.sel({}), "")

    def test_each_token_of_the_grammar(self):
        self.assertEqual(self.sel({"big_ct": {"action": "remove"}}), "-big_ct")
        self.assertEqual(self.sel({"twin_ct": {"action": "add"}}), "+twin_ct")
        self.assertEqual(self.sel({"twin_ct": {"action": "add", "place": "home"}}), "+twin_ct twin_ct@home")
        self.assertEqual(self.sel({"small_films": {"place": "home"}}), "small_films@home")

    def test_a_choice_that_changes_nothing_says_nothing(self):
        self.assertEqual(self.sel({"small_films": {"place": "lab"}}), "")
        self.assertEqual(self.sel({"small_films": {"action": "keep"}}), "")
        self.assertEqual(self.sel({"gated_set": {"action": "add"}}), "", "a set the feed cannot fetch is never added")
        self.assertEqual(self.sel({"big_ct": {"action": "remove", "place": "home"}}), "-big_ct", "a removed set goes nowhere")

    def test_tokens_follow_the_feeds_order(self):
        self.assertEqual(self.sel({"twin_ct": {"action": "add"}, "big_ct": {"action": "remove"}}), "-big_ct +twin_ct")

    def test_a_set_at_home_moves_back_to_the_lab(self):
        self.plan["home"]["used_bytes"] = TB
        self.plan["sets"][1]["location"] = "home"
        self.assertEqual(self.sel({"small_films": {"place": "lab"}}), "small_films@lab")
        self.assertEqual(self.sel({"small_films": {"place": "home"}}), "")


class TheTotals(unittest.TestCase):
    def setUp(self):
        self.plan = plan_fixture()

    def test_a_removal_leaves_the_volume_lighter(self):
        t = panel.totals(self.plan, {"big_ct": {"action": "remove"}})
        self.assertEqual(t["lab_after"], 17_553_250_000_000 - 980_000_000_000)
        self.assertEqual(t["datasets_after"], 7_626_035_136_479 - 980_000_000_000)
        self.assertEqual((t["removed"], t["added"], t["moved"], t["unsized"]), (["big_ct"], [], [], []))
        self.assertEqual(panel.refusals(self.plan, t), [])

    def test_an_addition_over_the_target_is_refused_in_the_planners_words(self):
        t = panel.totals(self.plan, {"huge_ct": {"action": "add"}})
        self.assertEqual(t["lab_after"], 20_553_250_000_000)
        self.assertEqual(panel.refusals(self.plan, t),
                         ["The lab volume would hold 20.6 TB, over the target of 20.0 TB by 0.6 TB."])

    def test_an_addition_over_the_quota_names_the_size_rule(self):
        self.plan["sets"][5]["bytes"] = 5 * TB
        t = panel.totals(self.plan, {"huge_ct": {"action": "add"}})
        self.assertEqual(panel.refusals(self.plan, t)[1],
                         "The lab volume would hold 22.6 TB, over its quota of 22.0 TB: the size rule would refuse the fetch whole.")

    def test_a_set_with_no_size_is_listed_not_counted(self):
        t = panel.totals(self.plan, {"no_size_yet": {"action": "add"}})
        self.assertEqual(t["lab_after"], t["lab_before"])
        self.assertEqual(t["unsized"], ["no_size_yet"])
        self.assertEqual(panel.refusals(self.plan, t), ["no_size_yet has no measured size, so the planner refuses the fetch or "
                                                        "the move: the size rule reads a set's exact size before a byte lands."])

    def test_the_home_takes_nothing_until_it_is_read(self):
        t = panel.totals(self.plan, {"small_films": {"place": "home"}})
        self.assertEqual(t["to_home"], ["small_films"])
        self.assertIsNone(t["home_after"])
        self.assertEqual(t["home_delta"], 6_338_426_763)
        self.assertEqual(t["lab_after"], 17_553_250_000_000 - 6_338_426_763)
        self.assertEqual(panel.refusals(self.plan, t),
                         ["The home's use has not been read yet, so the planner refuses any move to it until a grid word reads it."])

    def test_a_read_home_counts_and_has_a_quota(self):
        self.plan["home"]["used_bytes"] = 3_500_000_000_000
        t = panel.totals(self.plan, {"small_films": {"place": "home"}})
        self.assertEqual(t["home_after"], 3_500_000_000_000 + 6_338_426_763)
        self.assertEqual(panel.refusals(self.plan, t), [])
        t = panel.totals(self.plan, {"big_ct": {"place": "home"}})
        self.assertEqual(panel.refusals(self.plan, t), ["The home would hold 4.5 TB, over its quota of 4.0 TB."])

    def test_terabytes_round_half_up_on_tenths(self):
        self.assertEqual(panel.tb(0), "0.0 TB")
        self.assertEqual(panel.tb(49_999_999_999), "0.0 TB")
        self.assertEqual(panel.tb(50_000_000_000), "0.1 TB")
        self.assertEqual(panel.tb(21_990_230_000_000), "22.0 TB")
        self.assertEqual(panel.tb(None), "size unknown")


class TheOverlaps(unittest.TestCase):
    def setUp(self):
        self.plan = plan_fixture()

    def test_a_pair_both_held_is_noted_once(self):
        self.assertEqual(panel.overlaps(self.plan, {"twin_ct": {"action": "add"}}),
                         [{"a": "big_ct", "b": "twin_ct", "patients": 120, "series": 400, "same_scans": 90,
                           "same_bytes": 50_000_000_000}])

    def test_a_feed_written_before_same_scans_gives_none(self):
        for s in self.plan["sets"]:
            for o in s["overlap"]:
                del o["same_scans"]
        self.assertIsNone(panel.overlaps(self.plan, {"twin_ct": {"action": "add"}})[0]["same_scans"])

    def test_a_pair_with_one_side_gone_is_no_overlap(self):
        self.assertEqual(panel.overlaps(self.plan, {}), [])
        self.assertEqual(panel.overlaps(self.plan, {"twin_ct": {"action": "add"}, "big_ct": {"action": "remove"}}), [])


class TheWorth(unittest.TestCase):
    """What the kept sets are worth, worked by hand on the fixture: big_ct (500 people with level truth,
    a prior source covering abdomen and spine) and small_films (2,000, an X-ray and CT pair of tier A)
    on the drives; twin_ct (300, sharing 120 patients and 90 scans with big_ct, covering pelvis too)
    a fetch away."""

    def setUp(self):
        self.plan = plan_fixture()

    def test_with_no_choice_the_power_part_is_the_feeds_power_block(self):
        w = panel.worth(self.plan, {})
        power = self.plan["power"]
        self.assertEqual(w["power"], {"most": 2500, "least": 2500, "unread": 0, "scans": 2520, "transitional": 3,
                                      "by_modality": [["films", 1, 2000, 2000], ["ct", 1, 500, 500]]})
        self.assertEqual((w["power"]["most"], w["power"]["unread"], w["power"]["scans"], w["power"]["transitional"]),
                         (power["level_truth_people_kept"], power["level_truth_people_unread"],
                          power["level_truth_scans_kept"], power["transitional_people_kept"]))
        self.assertEqual(w["changes"], [])

    def test_the_least_takes_off_what_an_overlapping_pair_may_share(self):
        w = panel.worth(self.plan, {"twin_ct": {"action": "add"}})
        self.assertEqual((w["power"]["most"], w["power"]["least"]), (2800, 2680), "120 patients shared, the more of 120 and 90")
        self.assertEqual(w["power"]["by_modality"], [["films", 1, 2000, 2000], ["ct", 2, 800, 680]])

    def test_a_pair_with_no_count_above_zero_may_share_all_of_the_smaller(self):
        for s in self.plan["sets"]:
            for o in s["overlap"]:
                o.update(patients=0, series=0, same_scans=0)
        w = panel.worth(self.plan, {"twin_ct": {"action": "add"}})
        self.assertEqual((w["power"]["most"], w["power"]["least"]), (2800, 2500))

    def test_the_least_is_never_below_the_largest_set_alone(self):
        self.assertEqual(panel.people_with_truth(
            [a_set(sid, value=a_value(level_truth="read", level_truth_people=100)) for sid in ("a", "b", "c")],
            [{"a": x, "b": y, "patients": 100, "same_scans": None} for x, y in (("a", "b"), ("a", "c"), ("b", "c"))]),
            [300, 100])

    def test_an_addition_names_what_it_brings(self):
        w = panel.worth(self.plan, {"twin_ct": {"action": "add"}})
        self.assertEqual(w["changes"], [{"id": "twin_ct", "kind": "added", "people": 300, "truth": "read", "modality": "ct",
                                         "only": ["pelvis"], "prior": True, "bytes": 300_000_000_000}])
        self.assertEqual(w["anatomy"]["gained"], ["pelvis"])
        self.assertEqual(w["anatomy"]["regions"], [["abdomen", 2], ["pelvis", 1], ["spine", 1]])
        self.assertEqual((w["synthesis"]["priors"], w["synthesis"]["priors_before"], w["synthesis"]["prior_bytes"]),
                         (2, 1, 1_280_000_000_000))

    def test_a_removal_names_what_it_costs(self):
        w = panel.worth(self.plan, {"big_ct": {"action": "remove"}, "small_films": {"place": "home"}})
        self.assertEqual(w["changes"], [{"id": "big_ct", "kind": "removed", "people": 500, "truth": "read", "modality": "ct",
                                         "only": ["abdomen", "spine"], "prior": True, "bytes": 980_000_000_000}],
                         "a move between the drives changes nothing the sets are worth")
        self.assertEqual((w["anatomy"]["lost"], w["anatomy"]["spine"], w["anatomy"]["spine_before"], w["anatomy"]["no_region"]),
                         (["abdomen", "spine"], 0, 1, 1))
        self.assertEqual((w["synthesis"]["priors"], w["synthesis"]["priors_before"]), (0, 1))
        self.assertEqual(w["power"]["by_modality"], [["films", 1, 2000, 2000]])

    def test_the_labels_and_the_pairs_are_counted_by_kept_set(self):
        w = panel.worth(self.plan, {"no_size_yet": {"action": "add"}, "huge_ct": {"action": "add"}})
        self.assertEqual(w["labels"], {"truth": {"read": 2, "automatic": 1, "no": 0, "unknown": 1}, "masks_read": 1,
                                       "masks_automatic": 1, "masks_held": 1, "segmented": 3})
        self.assertEqual(w["power"]["unread"], 2, "automatic and unknown truth give no count of people")
        self.assertEqual((w["synthesis"]["paired"], w["synthesis"]["tiers"], w["synthesis"]["prior_unsized"]), (1, [["A", 1]], 1))

    def test_a_feed_before_the_value_block_counts_nothing_and_guesses_nothing(self):
        for s in self.plan["sets"]:
            s.pop("value", None)
        self.plan.pop("power")
        w = panel.worth(self.plan, {"twin_ct": {"action": "add"}})
        self.assertEqual((w["power"]["most"], w["power"]["unread"]), (0, 3))
        self.assertEqual(w["labels"]["truth"]["unknown"], 3)
        self.assertEqual(panel.worth_lines(self.plan), [])
        self.assertIsNone(panel.validate(self.plan))

    def test_people_needed_is_the_feeds_formula(self):
        self.assertEqual(panel.people_needed(0.5, 0.05, 1.959964), 385)
        self.assertEqual(panel.people_needed(0.9, 0.05, 1.959964), 139)
        self.assertEqual(panel.people_needed(0.5, 0.03, 1.959964), 1068)
        for args in ((0, 0.05, 1.96), (1, 0.05, 1.96), (0.5, 0, 1.96), (0.5, 0.05, 0), (float("nan"), 0.05, 1.96)):
            self.assertIsNone(panel.people_needed(*args), args)

    def test_a_count_is_a_whole_number_of_zero_or_more(self):
        self.assertEqual([panel.count_of(n) for n in (0, 7, 5.0, -1, 2.5, True, "3", None, float("nan"), float("inf"))],
                         [0, 7, 5, None, None, None, None, None, None, None])

    def test_the_order_puts_the_largest_first_and_the_unknown_last(self):
        def ids(key):
            return [s["id"] for s in panel.ordered(self.plan["sets"], key)]
        self.assertEqual(ids("truth_per_tb"), ["small_films", "twin_ct", "big_ct", "no_size_yet", "gated_set", "huge_ct"])
        self.assertEqual(ids("size"), ["huge_ct", "big_ct", "twin_ct", "small_films", "no_size_yet", "gated_set"])
        self.assertEqual(ids("feed"), [s["id"] for s in self.plan["sets"]])
        twins = [a_set(sid, value=a_value(level_truth="read", level_truth_people=10)) for sid in ("first", "second")]
        self.assertEqual([s["id"] for s in panel.ordered(twins, "truth_people")], ["first", "second"], "a tie keeps the feed's order")


class ThePlan(unittest.TestCase):
    def test_the_feeds_format_holds_and_another_does_not(self):
        self.assertIsNone(panel.validate(plan_fixture()))
        self.assertIn("format", panel.validate({"format": "other"}))
        self.assertIn("no sets", panel.validate(dict(plan_fixture(), sets=[])))
        self.assertEqual(panel.validate([]), "the plan is not a JSON object")


class TheBuild(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.plan_path = self.tmp / "plan.json"
        plan = plan_fixture()
        plan["sets"][1]["name"] = "Films </script><b>with a tag in the name"
        panel.write_snapshot(plan, self.plan_path)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def build(self, name):
        out = self.tmp / name
        self.assertEqual(panel.main(["build", "--plan", str(self.plan_path), "--out", str(out)]), 0)
        return out

    def test_the_same_snapshot_gives_the_same_bytes(self):
        one, two = self.build("one"), self.build("two")
        for name in panel.OUTPUTS:
            self.assertEqual((one / name).read_bytes(), (two / name).read_bytes(), name)

    def test_the_page_inlines_the_plan_and_fetches_nothing(self):
        html = (self.build("site") / "storage.html").read_text(encoding="utf-8")
        self.assertIn('<script type="application/json" id="plan">', html)
        self.assertIn('"id": "big_ct"'.replace(" ", ""), html.replace(" ", ""))
        self.assertEqual(html.count("</script>"), 4, "a tag in a set's name never ends the data early")
        self.assertIn("<\\/script>", html)
        self.assertNotIn("fetch(", html)
        self.assertNotIn('src="http', html)
        self.assertNotIn("<link", html)
        self.assertTrue(all(ord(c) < 128 for c in html))
        self.assertIn("schwingnet.dispatch", html)
        self.assertIn("schwingnet.read", html)
        self.assertIn(panel.WORKFLOW_URL, html)

    def test_the_record_names_the_snapshot_by_its_hash(self):
        out = self.build("rec")
        record = json.loads((out / "storage.json").read_text(encoding="utf-8"))
        self.assertEqual(record["id"], "22/storage")
        self.assertEqual(record["feed"]["sha256"], hashlib.sha256(self.plan_path.read_bytes()).hexdigest())
        self.assertEqual(record["feed"]["built_at"], "2026-10-24T20:52:07Z")
        self.assertEqual(record["rerun"]["command"], panel.COMMAND)
        for link in record["explore"]:
            if not link["href"].startswith("https://"):
                self.assertTrue((ROOT / link["href"]).exists(), link["href"])
        svg = (out / "storage.svg").read_text(encoding="utf-8")
        self.assertIn("17.6 TB used of 22.0 TB", svg)
        self.assertIn("not read yet", svg)

    def test_the_check_fails_on_a_changed_or_missing_file(self):
        out = self.build("chk")
        args = ["check", "--plan", str(self.plan_path), "--out", str(out)]
        self.assertEqual(panel.main(args), 0)
        page = out / "storage.html"
        page.write_text(page.read_text(encoding="utf-8").replace("The storage panel", "An edited panel"), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as said:
            self.assertEqual(panel.main(args), 1)
        self.assertIn("storage.html", said.getvalue())
        self.assertIn(panel.COMMAND, said.getvalue())
        (out / "storage.svg").unlink()
        with contextlib.redirect_stdout(io.StringIO()) as said:
            self.assertEqual(panel.main(args), 1)
        self.assertIn("storage.svg", said.getvalue())


class TheCommittedFigure(unittest.TestCase):
    def test_the_committed_files_are_what_the_snapshot_gives(self):
        for name, text in panel.outputs(panel.SNAPSHOT).items():
            self.assertEqual((panel.FOLDER / name).read_text(encoding="utf-8"), text, name)

    def test_the_snapshot_is_the_feeds_format_in_canonical_shape(self):
        raw = panel.SNAPSHOT.read_text(encoding="utf-8")
        plan = json.loads(raw)
        self.assertIsNone(panel.validate(plan))
        self.assertEqual(raw, json.dumps(plan, indent=1, sort_keys=True) + "\n")


class Feed(http.server.BaseHTTPRequestHandler):
    """A stand-in for GitHub's contents API: a redirect, a good answer, an empty one, a wrong one."""

    seen = []

    def do_GET(self):
        Feed.seen.append((self.path, self.headers.get("Authorization")))
        if self.path.startswith("/redirect"):
            self.send_response(302)
            self.send_header("Location", "/target")
            self.end_headers()
            return
        bodies = {
            "/good": {"content": base64.b64encode(json.dumps(plan_fixture()).encode()).decode(), "encoding": "base64"},
            "/empty": {"content": "", "encoding": "base64"},
            "/wrong": {"content": base64.b64encode(json.dumps({"format": "other"}).encode()).decode()},
            "/target": {"content": base64.b64encode(json.dumps(plan_fixture()).encode()).decode()},
        }
        if self.path not in bodies:
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(bodies[self.path]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class TheFetch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Feed)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Feed.seen.clear()
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "snapshot.json"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def fetch(self, path, token="t0ken"):
        env = {k: v for k, v in os.environ.items() if k not in panel.TOKEN_VARIABLES}
        if token:
            env["STORAGE_FEED_TOKEN"] = token
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stderr(io.StringIO()) as err, \
                contextlib.redirect_stdout(io.StringIO()):
            code = panel.main(["fetch", "--out", str(self.out), "--url", self.base + path])
        return code, err.getvalue()

    def test_no_token_is_exit_2_and_nothing_written(self):
        code, said = self.fetch("/good", token=None)
        self.assertEqual(code, 2)
        self.assertIn("no token", said)
        self.assertFalse(self.out.exists())
        self.assertEqual(Feed.seen, [])

    def test_a_redirect_is_refused_and_never_followed(self):
        code, said = self.fetch("/redirect")
        self.assertEqual(code, 1)
        self.assertIn("redirect", said)
        self.assertEqual([p for p, _a in Feed.seen], ["/redirect"], "the token went to no other address")
        self.assertFalse(self.out.exists())

    def test_a_good_answer_writes_the_canonical_snapshot(self):
        code, said = self.fetch("/good")
        self.assertEqual((code, said), (0, ""))
        self.assertEqual(Feed.seen, [("/good", "Bearer t0ken")])
        self.assertEqual(self.out.read_text(encoding="utf-8"), json.dumps(plan_fixture(), indent=1, sort_keys=True) + "\n")

    def test_an_unreachable_or_wrong_feed_is_one_sentence(self):
        self.assertIn("HTTP 404", self.fetch("/missing")[1])
        self.assertIn("no content", self.fetch("/empty")[1])
        self.assertIn("does not hold a plan", self.fetch("/wrong")[1])
        self.assertFalse(self.out.exists())


class TheMirror(unittest.TestCase):
    """The page's JavaScript model gives what the Python gives, on the fixture and on the committed
    snapshot, for the same choices, every order of the sets and a range of tests to power; node runs
    it where node is installed."""

    NEEDS = [[0.5, 0.05, 1.959964], [0.9, 0.05, 1.959964], [0.97, 0.02, 2.575829], [0.5, 0.03, 1.644854], [0, 0.05, 1.96],
             [0.5, 0, 1.96], [0.999, 0.001, 1.959964]]

    HARNESS = """
const fs = require("fs");
const plan = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const extra = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
process.stdout.write(JSON.stringify({
  cases: cases.map(function (choices) {
    const t = Model.totals(plan, choices);
    return { selection: Model.selection(plan, choices), totals: t, refusals: Model.refusals(plan, t), overlaps: Model.overlaps(plan, choices),
      worth: Model.worth(plan, choices) };
  }),
  orders: extra.sorts.map(function (key) { return Model.ordered(plan.sets, key).map(function (s) { return s.id; }); }),
  needs: extra.needs.map(function (n) { return Model.peopleNeeded(n[0], n[1], n[2]); })
}));
"""

    def python_side(self, plan, cases):
        out = []
        for choices in cases:
            t = panel.totals(plan, choices)
            out.append({"selection": panel.selection(plan, choices), "totals": t, "refusals": panel.refusals(plan, t),
                        "overlaps": panel.overlaps(plan, choices), "worth": panel.worth(plan, choices)})
        return json.loads(json.dumps({
            "cases": out,
            "orders": [[s["id"] for s in panel.ordered(plan["sets"], key)] for key, _words in panel.SORTS],
            "needs": [panel.people_needed(*n) for n in self.NEEDS]}))

    def compare(self, plan, cases):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed here; CI's runner has it")
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "mirror.js"
            script.write_text(panel.MODEL_JS + self.HARNESS, encoding="utf-8")
            (Path(tmp) / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            (Path(tmp) / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
            extra = {"sorts": [key for key, _words in panel.SORTS], "needs": self.NEEDS}
            (Path(tmp) / "extra.json").write_text(json.dumps(extra), encoding="utf-8")
            run = subprocess.run([node, str(script)] + [str(Path(tmp) / name) for name in ("plan.json", "cases.json", "extra.json")],
                                 capture_output=True, text=True, check=True, timeout=60)
        self.assertEqual(json.loads(run.stdout), self.python_side(plan, cases))

    def test_the_fixture(self):
        plan = plan_fixture()
        read_home = copy.deepcopy(plan)
        read_home["home"]["used_bytes"] = 3_500_000_000_000
        cases = [{}, {"big_ct": {"action": "remove"}}, {"huge_ct": {"action": "add"}}, {"no_size_yet": {"action": "add"}},
                 {"small_films": {"place": "home"}}, {"twin_ct": {"action": "add", "place": "home"}, "big_ct": {"place": "home"}},
                 {"twin_ct": {"action": "add"}}, {"gated_set": {"action": "add"}, "small_films": {"action": "remove", "place": "home"}}]
        self.compare(plan, cases)
        self.compare(read_home, cases)
        older_feed = copy.deepcopy(plan)
        for s in older_feed["sets"]:
            for o in s["overlap"]:
                del o["same_scans"]
        self.compare(older_feed, cases)
        no_counts = copy.deepcopy(plan)
        for s in no_counts["sets"]:
            for o in s["overlap"]:
                o.update(patients=0, series=0, same_scans=0)
        self.compare(no_counts, cases)
        before_value = copy.deepcopy(plan)
        for s in before_value["sets"]:
            s.pop("value", None)
        before_value.pop("power")
        self.compare(before_value, cases)
        odd_values = copy.deepcopy(plan)
        odd_values["sets"][0]["value"].update(level_truth_people=500.0, regions=["spine", "spine", 3, ""], tier=7, modality="")
        odd_values["sets"][1]["value"] = ["not", "a", "block"]
        odd_values["sets"][2]["value"].update(level_truth_people=True, level_truth="maybe", spine="yes")
        self.compare(odd_values, cases)

    def test_the_committed_snapshot(self):
        plan = json.loads(panel.SNAPSHOT.read_text(encoding="utf-8"))
        held = [s["id"] for s in plan["sets"] if panel.is_held(s)]
        sized = [s["id"] for s in plan["sets"] if s["fetchable"] and s["bytes"] is not None]
        unsized = [s["id"] for s in plan["sets"] if s["fetchable"] and s["bytes"] is None]
        cases = [{}, {held[0]: {"action": "remove"}}, {held[1]: {"place": "home"}}]
        if sized:
            cases.append({sized[0]: {"action": "add"}, held[0]: {"action": "remove"}})
            cases.append({sid: {"action": "add"} for sid in sized})
        if unsized:
            cases.append({unsized[0]: {"action": "add", "place": "home"}})
        cases.append({sid: {"action": "remove"} for sid in held[::3]})
        self.compare(plan, cases)

    def test_the_committed_snapshot_agrees_with_the_feeds_power_block(self):
        plan = json.loads(panel.SNAPSHOT.read_text(encoding="utf-8"))
        power, w = plan["power"], panel.worth(plan, {})["power"]
        self.assertEqual((w["most"], w["unread"], w["scans"], w["transitional"]),
                         (power["level_truth_people_kept"], power["level_truth_people_unread"],
                          power["level_truth_scans_kept"], power["transitional_people_kept"]))
        self.assertEqual(panel.people_needed(power["assumed_accuracy"], power["half_width"], power["z"]), power["people_needed"])


if __name__ == "__main__":
    unittest.main()
