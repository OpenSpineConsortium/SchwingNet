"""The edit hook speaks only when an edit touched the documents and the
checks then fail; everything else passes in silence."""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_edit  # noqa: E402

MARKERS = "<!-- cswap:checkpoint:begin -->\n<!-- cswap:checkpoint:end -->\n"


def make_repo(folder, broken):
    """A minimal repository: CLAUDE.md with its marker pair, one memory
    fact, and an index that lists it or, when broken, forgets it."""
    root = Path(folder)
    (root / "CLAUDE.md").write_text("# t\n\n" + MARKERS, encoding="utf-8")
    memory = root / "docs" / "memory"
    memory.mkdir(parents=True)
    (memory / "a-fact.md").write_text("One fact.\n", encoding="utf-8")
    index = "# Memory index\n" + ("" if broken else "- [a fact](a-fact.md): one line\n")
    (memory / "MEMORY.md").write_text(index, encoding="utf-8")
    return root


def run_hook(root, file_path):
    payload = json.dumps({"tool_input": {"file_path": str(file_path)}, "cwd": str(root)})
    err = io.StringIO()
    with mock.patch.object(sys, "stdin", io.StringIO(payload)), \
         mock.patch.object(sys, "stderr", err), \
         mock.patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": str(root)}):
        code = check_edit.main()
    return code, err.getvalue()


class CheckEditTest(unittest.TestCase):
    def test_document_edit_with_broken_index_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_repo(folder, broken=True)
            code, message = run_hook(root, root / "docs" / "memory" / "a-fact.md")
        self.assertEqual(code, 2)
        self.assertIn("does not list", message)

    def test_document_edit_with_healthy_documents_is_silent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_repo(folder, broken=False)
            code, message = run_hook(root, root / "CLAUDE.md")
        self.assertEqual(code, 0)
        self.assertEqual(message, "")

    def test_edit_outside_the_documents_runs_no_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_repo(folder, broken=True)
            with mock.patch.object(check_edit.check_docs, "run_checks") as checks:
                code, _ = run_hook(root, root / "src" / "app.py")
        self.assertEqual(code, 0)
        checks.assert_not_called()

    def test_path_outside_the_root_is_not_a_document(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_repo(folder, broken=True)
            self.assertFalse(check_edit.is_document(root, "/elsewhere/docs/x.md"))

    def test_broken_payload_passes(self):
        with mock.patch.object(sys, "stdin", io.StringIO("not json")):
            self.assertEqual(check_edit.main(), 0)


if __name__ == "__main__":
    unittest.main()
