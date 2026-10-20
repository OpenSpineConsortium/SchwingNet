"""tools/living_docs.py holds the lessons to the code: a command's promised
output must be found, in order, in what it prints, a blank line between a
command and its output still pairs them (the bug that once let every lesson
pass unchecked), each lesson's notebook is its commands cell for cell, and
the site builds every page with the lesson's commands and its Colab link."""

import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import living_docs  # noqa: E402

LESSON = """# A lesson

Intro.

```bash setup
export LAB="$(mktemp -d)"
```

```bash run
cd "$LAB"
echo one
echo two
```

```output
one
two
```

```bash run
cd "$LAB"
echo unchecked
```
"""


class Matching(unittest.TestCase):
    def test_lines_are_found_in_order_within_actual_lines(self):
        self.assertIsNone(living_docs.missing_lines("a\nc", "  xa\nb\ncx\n"))

    def test_a_line_out_of_order_is_missing(self):
        self.assertEqual(living_docs.missing_lines("c\na", "a\nc\n"), "a")

    def test_two_expected_lines_may_share_one_actual_line(self):
        self.assertIsNone(living_docs.missing_lines("## Overlaps\nin this order", "## Overlaps (in this order)"))


class Parsing(unittest.TestCase):
    def test_a_blank_line_between_a_command_and_its_output_still_pairs_them(self):
        path = Path(tempfile.mkdtemp()) / "01-x.md"
        path.write_text(LESSON, encoding="utf-8")
        self.assertEqual(living_docs.steps(path), [('cd "$LAB"\necho one\necho two', "one\ntwo"), ('cd "$LAB"\necho unchecked', None)])

    def test_a_wrong_output_fails_the_lesson(self):
        path = Path(tempfile.mkdtemp()) / "01-x.md"
        path.write_text(LESSON.replace("one\ntwo\n```", "one\nthree\n```"), encoding="utf-8")
        problems = living_docs.test_lesson(path, ROOT / "tools")
        self.assertEqual(len(problems), 1)
        self.assertIn("never printed 'three'", problems[0])


class Notebooks(unittest.TestCase):
    def test_each_command_is_a_bash_cell_from_the_practice_folder(self):
        path = Path(tempfile.mkdtemp()) / "01-x.md"
        path.write_text(LESSON, encoding="utf-8")
        made = living_docs.notebook_of(path)
        code = ["".join(c["source"]) for c in made["cells"] if c["cell_type"] == "code"]
        self.assertIn("ls-remote", code[0])
        self.assertEqual(code[1:], ['%%bash\ncd "$LAB"\necho one\necho two', '%%bash\ncd "$LAB"\necho unchecked'])

    def test_links_into_the_repository_move_one_folder_deeper(self):
        text = "[l2](02-x.md), [p](../agents/PROTOCOL.md), [w](https://x.org), ![f](a.svg)"
        self.assertEqual(living_docs.rewrite_links_for_notebook(text),
                         "[l2](02-x.ipynb), [p](../../agents/PROTOCOL.md), [w](https://x.org), ![f](a.svg)")


class Html(unittest.TestCase):
    def test_alt_text_and_script_links_cannot_inject(self):
        made = living_docs.inline('![q" onerror="x](y.png) [a](javascript:alert(1))', lambda t: t)
        self.assertNotIn('" onerror', made)
        self.assertIn('href="#"', made)

    def test_an_escaped_pipe_and_a_pipe_in_code_stay_in_their_cell(self):
        self.assertEqual(living_docs.cells_of("| a \\| b | `x|y` | c |"), ["a | b", "`x|y`", "c"])

    def test_the_committed_notebooks_match_their_lessons(self):
        self.assertEqual(living_docs.notebooks(Namespace(check=True)), 0)


class TheSite(unittest.TestCase):
    def test_every_page_is_built_with_its_links(self):
        out = Path(tempfile.mkdtemp()) / "site"
        results = out.parent / "tests.json"
        results.write_text(json.dumps({"tests": [{"id": "test_x.A.test_b", "outcome": "passed", "seconds": 0.1}]}))
        self.assertEqual(living_docs.site(Namespace(out=str(out.parent), tests=None, repo="", sha="")), 1)
        living_docs.site(Namespace(out=str(out), tests=str(results), repo="o/n", sha="abc1234def"))
        lesson = (out / "01-first-claim.html").read_text(encoding="utf-8")
        self.assertIn("colab.research.google.com/github/o/n/blob/abc1234def/docs/learn/notebooks/01-first-claim.ipynb", lesson)
        self.assertIn('href="02-push-guard.html"', lesson)
        self.assertIn("ran in CI at commit abc1234", lesson)
        self.assertIn("1 of 1 tests passed", (out / "tests.html").read_text(encoding="utf-8"))
        self.assertIn("tools/living_docs.py", (out / "reference.html").read_text(encoding="utf-8"))
        self.assertTrue((out / "capabilities-claim.svg").exists())


if __name__ == "__main__":
    unittest.main()
