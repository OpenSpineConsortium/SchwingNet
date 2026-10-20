"""tools/profile_report.py: the programme's report, one table per question,
each arm against the baselines with the outcome beside the cost, made
only from the records committed in the programme's folder."""

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import profile_report  # noqa: E402
import usage  # noqa: E402

FOLDER = ROOT / "docs" / "research" / "beyond-cooperation"


def record(calls=10, failed=1, unanswered=0, repeated=2, tokens=1000, usd=1.5, active=100, in_tools=25, first=100,
           peak=400, mean=200, cached=0.5, compactions=0, drops=0, read_bytes=2048, reread_bytes=1024, rereads=1,
           files_named=4, partial=1):
    """A record of tools/profile.py with the counts the report reads."""
    return {"schema": "symphony-profile/1",
            "calls": {"total": calls, "failed": failed, "unanswered": unanswered, "repeated": repeated, "by_tool": {}},
            "tokens": {"total": tokens}, "estimated_usd": usd, "seconds": {"active": active, "in_tools": in_tools},
            "context": {"first": first, "peak": peak, "mean": mean, "cached_share": cached,
                        "compactions": compactions, "drops": drops},
            "reads": {"bytes": read_bytes, "reread_bytes": reread_bytes, "rereads": rereads,
                      "files_named": files_named, "partial": partial}}


def outcome(question="tools", arm="Batched calls", tasks=2, landed=1, modes=None, source="a test"):
    return {"schema": "symphony-arm-outcome/1", "question": question, "arm": arm, "tasks": tasks, "landed": landed,
            "modes": modes, "source": source}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def world(folder):
    """A baseline with its outcome, a second with none, and one arm's run
    of two transcripts, one task of two landed."""
    write(folder / "baseline-2026-10-01.json", record())
    write(folder / "baseline-2026-10-01.outcome.json", outcome(question="baseline", tasks=1, landed=1,
                                                             source="#1 merged"))
    write(folder / "baseline-2026-10-02.json", record(calls=50))
    run = folder / "runs" / "2026-10-05-batched-calls"
    write(run / "outcome.json", outcome(modes={"FM-1.3": 2, "FM-3.2": 0}))
    write(run / "a.profile.json", record(calls=30, failed=3, repeated=1, compactions=1, peak=300))
    write(run / "b.profile.json", record(calls=10, failed=1, repeated=0, compactions=2, peak=500))


def section(text, title):
    start = text.index(f"## {title}\n")
    end = text.find("\n## ", start + 1)
    return text[start:end if end != -1 else None]


def rows_of(text, title):
    return [line for line in section(text, title).splitlines() if line.startswith("| ") and "---" not in line][1:]


class Page(unittest.TestCase):
    def test_the_committed_page_is_what_the_records_give(self):
        with redirect_stderr(io.StringIO()) as said:
            code = profile_report.main([str(FOLDER), "--check"])
        self.assertEqual(code, 0, said.getvalue())
        text = (FOLDER / profile_report.PAGE).read_text(encoding="ascii")
        self.assertTrue(text.startswith("# The report: each arm against the baseline\n\nSource: "))

    def test_it_reads_the_records_profile_py_writes(self):
        self.assertEqual(profile_report.PROFILE_SCHEMA, usage.profiler().SCHEMA)

    def test_each_question_has_its_table_the_baselines_first_and_its_arms_alone(self):
        with tempfile.TemporaryDirectory() as folder:
            world(Path(folder))
            text = profile_report.page(Path(folder))
        for title in profile_report.QUESTIONS.values():
            labels = [row.split(" | ")[0][2:] for row in rows_of(text, title)]
            arm = ["Batched calls (2026-10-05-batched-calls)"] if title == "Decreased tool usage" else []
            self.assertEqual(labels, ["baseline 2026-10-01", "baseline 2026-10-02", *arm], title)
        tools = rows_of(text, "Decreased tool usage")
        self.assertEqual(tools[0], "| baseline 2026-10-01 | 1 | 1 of 1 | not judged | 10.0 | 1.0 | 0 | 2 | 0 |")
        self.assertEqual(tools[1], "| baseline 2026-10-02 | 1 | not recorded | not recorded | - | - | 0 | 2 | 0 |",
                         "no outcome, so no cost per landed task")
        self.assertEqual(tools[2], "| Batched calls (2026-10-05-batched-calls) | 2 | 1 of 2 | FM-1.3 x2 "
                                   "| 40.0 | 4.0 | 0 | 1 | 3 |",
                         "two transcripts summed over the one task that landed")
        context = rows_of(text, "Context compression")
        self.assertNotIn("Batched", "".join(context))
        self.assertIn("No arm has run for this question yet", section(text, "Profiling"))
        self.assertNotIn("No arm has run", section(text, "Decreased tool usage"))
        self.assertTrue(text.endswith("- baseline 2026-10-01: #1 merged\n- baseline 2026-10-02: no outcome recorded\n"
                                      "- Batched calls (2026-10-05-batched-calls): a test\n"))

    def test_every_table_carries_the_repeated_calls_and_the_compactions(self):
        with tempfile.TemporaryDirectory() as folder:
            world(Path(folder))
            text = profile_report.page(Path(folder))
        for title in profile_report.QUESTIONS.values():
            head = section(text, title).splitlines()[2]
            self.assertTrue(head.endswith("| Repeated calls (FM-1.3) | Compactions (FM-1.4) |"), title)

    def test_the_means_and_the_shares(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder) / "runs" / "2026-10-05-trimmed"
            write(run / "outcome.json", outcome(question="context", tasks=2, landed=0, modes={}))
            write(run / "a.profile.json", record(first=100, peak=300, mean=150, cached=0.9, drops=1))
            write(run / "b.profile.json", record(first=200, peak=500, mean=250, cached=0.7, drops=0))
            text = profile_report.page(Path(folder))
        self.assertEqual(rows_of(text, "Context compression"),
                         ["| Batched calls (2026-10-05-trimmed) | 2 | 0 of 2 | none "
                          "| 150 | 400 | 200 | 80% | 1 | 4 | 0 |"])
        self.assertIn("No record yet.", section(text, "Profiling"))

    def test_a_page_that_differs_fails_the_check_and_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as folder:
            world(Path(folder))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(profile_report.main([folder]), 0)
            page = Path(folder) / profile_report.PAGE
            self.assertEqual(profile_report.main([folder, "--check"]), 0)
            page.write_text(page.read_text().replace("10.0", "9.0", 1))
            stale = page.read_text()
            with redirect_stderr(io.StringIO()) as said:
                self.assertEqual(profile_report.main([folder, "--check"]), 1)
            self.assertEqual(page.read_text(), stale)
            self.assertIn("is not what the records give", said.getvalue())
            page.unlink()
            with redirect_stderr(io.StringIO()):
                self.assertEqual(profile_report.main([folder, "--check"]), 1)

    def test_an_outcome_or_a_record_that_does_not_hold_together_is_refused(self):
        cases = {
            "another schema": dict(outcome(), schema="x/1"),
            "a question section 2 does not ask": outcome(question="speed"),
            "a baseline's question on an arm": outcome(question="baseline"),
            "more landed than run": outcome(tasks=1, landed=2),
            "no task": outcome(tasks=0, landed=0),
            "a count that is no whole number": outcome(landed=True),
            "a mode MAST does not name": outcome(modes={"FM-4.1": 1}),
            "a mode counted below 0": outcome(modes={"FM-1.3": -1}),
            "an arm named by markup": outcome(arm="| a | b"),
            "no source": dict(outcome(), source=" "),
            "no modes, not even null": {key: value for key, value in outcome().items() if key != "modes"},
        }
        for name, data in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as folder:
                run = Path(folder) / "runs" / "2026-10-05-x"
                write(run / "outcome.json", data)
                write(run / "a.profile.json", record())
                with self.assertRaises(profile_report.ReportError):
                    profile_report.page(Path(folder))
        bad_records = {"a count given as text": {"tokens": {"total": "12"}},
                       "a count below 0": {"calls": {"total": -5}},
                       "infinity": {"estimated_usd": float("inf")},
                       "not a number": {"context": {"peak": float("nan")}},
                       "true for a count": {"reads": {"bytes": True}},
                       "a block that is a number": {"seconds": 5}}
        for name, bad in bad_records.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as folder:
                write(Path(folder) / "baseline-2026-10-01.json", {**record(), **bad})
                with self.assertRaises(profile_report.ReportError):
                    profile_report.page(Path(folder))
        with tempfile.TemporaryDirectory() as folder:
            write(Path(folder) / "baseline-2026-10-01.json", dict(record(), context={}))
            self.assertIn("| baseline 2026-10-01 | 1 | not recorded |", profile_report.page(Path(folder)),
                          "a record with no main transcript has an empty context block")
        for name, path in {"an outcome with no record": "baseline-2026-10-01.outcome.json",
                           "a baseline named otherwise": "baseline-2026-1-1.json"}.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as folder:
                write(Path(folder) / path, outcome(question="baseline") if "outcome" in path else record())
                with self.assertRaises(profile_report.ReportError):
                    profile_report.page(Path(folder))
        for name, build in {"a run with no record": lambda run: None,
                            "a record of something else": lambda run: write(run / "a.profile.json", {"schema": "y"}),
                            "a record that is no JSON": lambda run: (run / "a.profile.json").write_text("{")}.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as folder:
                run = Path(folder) / "runs" / "2026-10-05-x"
                write(run / "outcome.json", outcome())
                build(run)
                with self.assertRaises(profile_report.ReportError):
                    profile_report.page(Path(folder))
        with tempfile.TemporaryDirectory() as folder:
            write(Path(folder) / "runs" / "Batched" / "outcome.json", outcome())
            with redirect_stderr(io.StringIO()) as said:
                self.assertEqual(profile_report.main([folder]), 2)
            self.assertIn("a run's folder is named DATE-ARM", said.getvalue())

    def test_the_same_records_give_the_same_page_wherever_they_are(self):
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            world(Path(one))
            shutil.copytree(one, two, dirs_exist_ok=True)
            self.assertEqual(profile_report.page(Path(one)), profile_report.page(Path(two)))


if __name__ == "__main__":
    unittest.main()
