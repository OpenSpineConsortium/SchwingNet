"""scripts/demo.sh shows what docs/start/capabilities.md says it shows:
the second push of a claim branch is refused, the push guard refuses the
five pushes the page names and allows a fresh claim, and the board renders
from its snapshot. It runs here in the required check, so the demo cannot
drift from the code it demonstrates; docs/start/demo.ipynb, which runs the
same parts from the public library, is checked to stay valid JSON with its
code cells parsing as Python, since its clone needs the network."""

import ast
import json
import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "demo.sh"
NOTEBOOK = ROOT / "docs" / "start" / "demo.ipynb"


def demo(*part):
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
               GIT_TERMINAL_PROMPT="0")
    done = subprocess.run(["bash", str(SCRIPT), *part], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=120)
    return done.returncode, done.stdout


class DemoTest(unittest.TestCase):
    def test_the_second_claim_is_refused(self):
        code, out = demo("race")
        self.assertEqual(code, 0, out)
        self.assertIn("alice: push of claude/7 accepted", out)
        self.assertIn("bob: push of claude/7 refused by origin", out)
        self.assertIn("claude/7 is held by: alice", out)

    def test_the_guard_refuses_what_the_page_names(self):
        code, out = demo("guard")
        self.assertEqual(code, 0, out)
        refusals = {
            "git push origin main": "a push to main is refused",
            "git push --force origin claude/7": "--force overwrites history",
            "git push origin +claude/7": "a + before a refspec",
            "git push origin claude/07": "claims nothing",
            "git push --force-with-lease origin claude/7": "claude/7 on origin is alice's claim",
        }
        for command, reason in refusals.items():
            self.assertRegex(out, f"REFUSED  {re.escape(command)}\n +.*{re.escape(reason)}")
        self.assertIn("allowed  git push origin claude/8", out)

    def test_the_board_renders(self):
        code, out = demo("board")
        self.assertEqual(code, 0, out)
        for heading in ("## Claims", "## Queue", "## Blockers"):
            self.assertIn(heading, out)

    def test_an_unknown_part_is_refused(self):
        code, _ = demo("everything")
        self.assertEqual(code, 64)

    def test_the_notebook_parses(self):
        notebook = json.loads(NOTEBOOK.read_text(encoding="ascii"))
        cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
        self.assertTrue(cells)
        for cell in cells:
            self.assertEqual(cell["outputs"], [], "commit the notebook without outputs")
            ast.parse("".join(cell["source"]))


if __name__ == "__main__":
    unittest.main()
