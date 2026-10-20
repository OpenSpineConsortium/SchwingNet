"""The follow-up's first review probe of status's paths (written against
41c6545): status at an organization target against the tests' fake gh,
with a failed read of a repository's own variables, a repository's own
list holding terminal codes, and hand-made labels holding them. On 41c6545
the labels reached the output with their codes (the review's finding 4)."""

import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
CHECKOUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(CHECKOUT / part) for part in ("scripts", "tests", "tools")]
import fake_gh  # noqa: E402
import tokens  # noqa: E402
from fake_gh import answer  # noqa: E402
import test_tokens as t  # noqa: E402  (its World and helpers, imported, not run)

ESC = "\x1b]0;owned\x07\x1b[2J"


def status(test, org_variables, repo_variables_answer):
    world = t.World(test, secrets=[t.secret(tokens.slot_secret(1))], variables=org_variables)
    routes = t.read_json(world.routes_file)
    routes["secret list"] = [answer(200, world.secrets), answer(200, [])]
    routes["variable list"] = [answer(200, world.variables), repo_variables_answer]
    fake_gh.write_routes(world.routes_file, routes)
    run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
    printed = io.StringIO()
    with patch.object(tokens.subprocess, "run", run), redirect_stdout(printed):
        tokens.print_status(tokens.State(tokens.Gh(), t.target(repos=(t.REPO, "other"))))
    return printed.getvalue()


class Paths(unittest.TestCase):
    def test_failed_read(self):
        text = status(self, [t.variable(tokens.ACCOUNTS_VARIABLE, "1")], answer(403, {"message": "no"}))
        print("--- failed read ---\n" + text)

    def test_codes_in_own_list(self):
        text = status(self, [], answer(200, [{"name": tokens.ACCOUNTS_VARIABLE, "value": ESC + ",1"}]))
        print("--- codes in a repository's own list ---\n" + repr(text))
        self.assertNotIn("\x1b", text)

    def test_codes_in_label(self):
        text = status(self, [t.variable(tokens.slot_label(1), ESC), t.variable(tokens.slot_label(2), ESC)], answer(200, []))
        print("--- codes in hand-made labels (pre-existing) ---\n" + repr(text))


if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1], verbosity=0)
