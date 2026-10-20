"""check_docs passes a sound tree and names each way a tree can be unsound."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_docs  # noqa: E402
from check_docs import MARK_BEGIN, MARK_END, run_checks  # noqa: E402

CLAUDE_MD = "\n".join([
    "# Example",
    "",
    "## Shared memory",
    "",
    "@docs/memory/MEMORY.md",
    "",
    "```",
    "@docs/not-a-real-import.md",
    "```",
    "",
    "Write to `@docs/not-an-import-either.md` is a code span, not an import.",
    "",
    MARK_BEGIN,
    "## Session checkpoint (kept by cswap)",
    "### Durable decisions",
    "- (none recorded)",
    "### Constraints",
    "- (none recorded)",
    MARK_END,
    "",
])
MEMORY_MD = "# Memory index\n\n- [How this repository works](how-this-repository-works.md): where things live.\n"
FACT_MD = "The repository is the shared plane.\n"


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8", newline="")
    return path


def sound_tree(root):
    write(root, "CLAUDE.md", CLAUDE_MD)
    write(root, "docs/memory/MEMORY.md", MEMORY_MD)
    write(root, "docs/memory/how-this-repository-works.md", FACT_MD)
    write(root, "docs/project.md", "# Goal\n")


class SoundTree(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        sound_tree(self.root)

    def tearDown(self):
        self.folder.cleanup()

    def test_passes(self):
        problems, count = run_checks(self.root)
        self.assertEqual(problems, [])
        self.assertEqual(count, 4)

    def test_an_import_inside_a_fence_or_a_code_span_is_an_example(self):
        self.assertEqual(check_docs.imports(CLAUDE_MD), [(5, "docs/memory/MEMORY.md")])

    def test_an_import_anywhere_in_a_line_counts(self):
        self.assertEqual(check_docs.imports("- git workflow @docs/git-instructions.md\n"), [(1, "docs/git-instructions.md")])
        self.assertEqual(check_docs.imports("See @docs/a.md and @docs/b.md.\n"), [(1, "docs/a.md"), (1, "docs/b.md.")])
        self.assertEqual(check_docs.imports("Mail someone@example.com about it.\n"), [])

    def test_a_missing_import_is_named(self):
        write(self.root, "CLAUDE.md", CLAUDE_MD.replace("@docs/memory/MEMORY.md", "@docs/gone.md"))
        problems, _ = run_checks(self.root)
        self.assertEqual(problems, ["CLAUDE.md: line 5 imports @docs/gone.md, which does not exist"])

    def test_a_missing_import_in_the_middle_of_a_line_is_named(self):
        write(self.root, "CLAUDE.md", CLAUDE_MD.replace("@docs/memory/MEMORY.md", "See @docs/gone.md for the plan"))
        problems, _ = run_checks(self.root)
        self.assertEqual(problems, ["CLAUDE.md: line 5 imports @docs/gone.md, which does not exist"])

    def test_an_indented_import_counts(self):
        write(self.root, "CLAUDE.md", CLAUDE_MD.replace("@docs/memory/MEMORY.md", "  @docs/gone.md"))
        problems, _ = run_checks(self.root)
        self.assertEqual(len(problems), 1)
        self.assertIn("@docs/gone.md", problems[0])

    def test_a_duplicate_marker_fails(self):
        write(self.root, "CLAUDE.md", CLAUDE_MD + "\n" + MARK_BEGIN + "\n")
        problems, _ = run_checks(self.root)
        self.assertEqual(problems, [f"CLAUDE.md: marker {MARK_BEGIN} appears 2 times, expected once"])

    def test_a_missing_marker_fails(self):
        write(self.root, "CLAUDE.md", CLAUDE_MD.replace(MARK_END + "\n", ""))
        problems, _ = run_checks(self.root)
        self.assertEqual(problems, [f"CLAUDE.md: marker {MARK_END} appears 0 times, expected once"])

    def test_markers_in_the_wrong_order_fail(self):
        swapped = CLAUDE_MD.replace(MARK_BEGIN, "TEMP").replace(MARK_END, MARK_BEGIN).replace("TEMP", MARK_END)
        write(self.root, "CLAUDE.md", swapped)
        problems, _ = run_checks(self.root)
        self.assertEqual(problems, ["CLAUDE.md: the end marker comes before the begin marker"])

    def test_a_fact_the_index_forgets_fails(self):
        write(self.root, "docs/memory/forgotten.md", "A fact nobody indexed.\n")
        problems, _ = run_checks(self.root)
        self.assertEqual(problems, ["docs/memory/MEMORY.md: does not list forgotten.md"])

    def test_an_index_line_to_nothing_fails(self):
        write(self.root, "docs/memory/MEMORY.md", MEMORY_MD + "- [Gone](gone.md): nothing there.\n")
        problems, _ = run_checks(self.root)
        self.assertEqual(problems, ["docs/memory/MEMORY.md: links to gone.md, which does not exist"])

    def test_a_web_link_in_the_index_is_not_a_file(self):
        write(self.root, "docs/memory/MEMORY.md", MEMORY_MD + "\nSee [GitHub](https://github.com/) too.\n")
        problems, _ = run_checks(self.root)
        self.assertEqual(problems, [])

    def test_an_event_log_fails(self):
        write(self.root, "docs/history/run.events.json", "[]\n")
        problems, _ = run_checks(self.root)
        self.assertEqual(problems, ["docs/history/run.events.json: event log committed"])

    def test_a_secret_shaped_string_fails(self):
        # Assembled at run time so this test file never carries the shape.
        token = "gh" + "p_" + "A" * 36
        write(self.root, "docs/notes.md", f"token: {token}\n")
        problems, _ = run_checks(self.root)
        self.assertEqual(problems, ["docs/notes.md: line 1 looks like a GitHub token"])

    def test_every_secret_shape_is_caught(self):
        samples = [
            "sk-" + "ant-" + "a" * 24,
            "github_" + "pat_" + "B" * 32,
            "gh" + "o_" + "c" * 30,
            "AK" + "IA" + "Q" * 16,
            "-----BEGIN " + "RSA PRIVATE " + "KEY-----",
        ]
        write(self.root, "tools/sample.txt", "\n".join(samples) + "\n")
        problems, _ = run_checks(self.root)
        self.assertEqual(len(problems), 5)

    def test_this_tool_and_its_tests_do_not_look_like_secrets(self):
        files = [Path("tools/check_docs.py"), Path("tests/test_check_docs.py")]
        self.assertEqual(check_docs.check_secrets(ROOT, files), [])

    def test_a_crlf_document_fails(self):
        write(self.root, "docs/setup.md", b"# Setup\r\nline\r\n")
        problems, _ = run_checks(self.root)
        self.assertEqual(problems, ["docs/setup.md: line 1 has a CR (CRLF line ending)"])

    def test_a_non_ascii_document_fails(self):
        write(self.root, ".claude/rules/quote.md", "# Rule\n\nA curly quote: \u201cno\u201d\n")
        problems, _ = run_checks(self.root)
        self.assertEqual(problems, [".claude/rules/quote.md: line 3 is not ASCII"])

    def test_non_ascii_outside_the_document_folders_is_allowed(self):
        write(self.root, "data/names.txt", "Jos\u00e9\n")
        problems, _ = run_checks(self.root)
        self.assertEqual(problems, [])

    def test_a_binary_file_is_skipped(self):
        write(self.root, "data/blob.bin", bytes(range(256)))
        write(self.root, "docs/history/picture.png", bytes(range(256)))
        problems, _ = run_checks(self.root)
        self.assertEqual(problems, [])

    def test_python_caches_are_not_documents(self):
        write(self.root, "tools/__pycache__/x.cpython-312.pyc", b"\r\xff")
        problems, count = run_checks(self.root)
        self.assertEqual(problems, [])
        self.assertEqual(count, 4)

    def test_main_exits_1_and_prints_each_problem(self):
        write(self.root, "docs/history/run.events.json", "[]\n")
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            code = check_docs.main(["--root", str(self.root)])
        self.assertEqual(code, 1)
        self.assertIn("event log committed", out.getvalue())

    def test_main_exits_0_with_a_count(self):
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            code = check_docs.main(["--root", str(self.root)])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(), "docs ok (4 files)\n")


class TheTemplateItself(unittest.TestCase):
    @unittest.skipUnless((ROOT / "CLAUDE.md").is_file(), "the template's CLAUDE.md is not here")
    def test_the_template_passes_its_own_check(self):
        problems, count = run_checks(ROOT)
        self.assertEqual(problems, [])
        self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main()
