"""The marked section keeps the rest of CLAUDE.md byte for byte."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import marked_section  # noqa: E402
from marked_section import MARK_BEGIN, MARK_END, upsert_marked_section  # noqa: E402

TOOL = ROOT / "tools" / "marked_section.py"
SECTION = "\n".join([MARK_BEGIN, "## Session checkpoint", "- one", MARK_END])
NEWER = "\n".join([MARK_BEGIN, "## Session checkpoint", "- two", MARK_END])


class Replace(unittest.TestCase):
    def test_replaces_between_the_first_pair_and_keeps_the_rest(self):
        before = "# Title\n\nprose\n\n" + SECTION + "\n\ntrailing\n"
        after = upsert_marked_section(before, NEWER)
        self.assertEqual(after, "# Title\n\nprose\n\n" + NEWER + "\n\ntrailing\n")

    def test_same_section_is_unchanged(self):
        before = "# Title\n\n" + SECTION + "\n"
        self.assertEqual(upsert_marked_section(before, SECTION), before)


class Append(unittest.TestCase):
    def test_after_one_blank_line_when_the_file_ends_with_a_newline(self):
        self.assertEqual(upsert_marked_section("# Title\n", SECTION), "# Title\n\n" + SECTION + "\n")

    def test_adds_two_newlines_when_the_file_has_none(self):
        self.assertEqual(upsert_marked_section("# Title", SECTION), "# Title\n\n" + SECTION + "\n")

    def test_adds_none_when_the_file_already_ends_blank(self):
        self.assertEqual(upsert_marked_section("# Title\n\n", SECTION), "# Title\n\n" + SECTION + "\n")


class Empty(unittest.TestCase):
    def test_none_and_empty_give_the_section_alone(self):
        self.assertEqual(upsert_marked_section(None, SECTION), SECTION + "\n")
        self.assertEqual(upsert_marked_section("", SECTION), SECTION + "\n")


class Unpaired(unittest.TestCase):
    def test_begin_without_end_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            upsert_marked_section("x\n" + MARK_BEGIN + "\nabandoned\n", SECTION)
        self.assertIn("unpaired", str(caught.exception))

    def test_end_without_begin_is_refused(self):
        with self.assertRaises(ValueError):
            upsert_marked_section("x\n" + MARK_END + "\n", SECTION)


class Crlf(unittest.TestCase):
    def test_a_crlf_file_stays_crlf_on_replace(self):
        before = ("# Title\r\n\r\n" + SECTION + "\r\n").replace("\n", "\r\n").replace("\r\r", "\r")
        after = upsert_marked_section(before, NEWER)
        self.assertNotIn("\r\r", after)
        self.assertEqual(after.replace("\r\n", "\n"), "# Title\n\n" + NEWER + "\n")
        self.assertEqual(after.count("\r\n"), after.count("\n"))

    def test_a_crlf_file_stays_crlf_on_append(self):
        after = upsert_marked_section("# Title\r\n", SECTION)
        self.assertEqual(after.count("\r\n"), after.count("\n"))
        self.assertTrue(after.endswith(MARK_END + "\r\n"))


class CommandLine(unittest.TestCase):
    def run_tool(self, path, stdin):
        return subprocess.run(
            [sys.executable, str(TOOL), str(path)],
            input=stdin, capture_output=True, text=True,
        )

    def test_appends_then_replaces_then_reports_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "CLAUDE.md"
            path.write_text("# Title\n", encoding="utf-8")
            first = self.run_tool(path, SECTION + "\n")
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout.strip(), f"{path}: section appended")
            second = self.run_tool(path, NEWER + "\n")
            self.assertEqual(second.stdout.strip(), f"{path}: section replaced")
            third = self.run_tool(path, NEWER + "\n")
            self.assertEqual(third.stdout.strip(), f"{path}: section unchanged")
            self.assertEqual(path.read_text(encoding="utf-8"), "# Title\n\n" + NEWER + "\n")

    def test_stdin_without_the_markers_exits_2(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "CLAUDE.md"
            path.write_text("# Title\n", encoding="utf-8")
            result = self.run_tool(path, "## no markers here\n")
            self.assertEqual(result.returncode, 2)
            self.assertIn(MARK_BEGIN, result.stderr)
            self.assertEqual(path.read_text(encoding="utf-8"), "# Title\n")

    def test_outcome_words(self):
        self.assertEqual(marked_section.outcome("a", "a"), "unchanged")
        self.assertEqual(marked_section.outcome(None, SECTION + "\n"), "appended")
        self.assertEqual(marked_section.outcome(SECTION, NEWER), "replaced")


if __name__ == "__main__":
    unittest.main()
