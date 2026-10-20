"""The follow-up's second review count of gh calls (written against
37142b0, and run on the trees before and after a change to compare them):
the calls one status makes at an organization target with eight slots and
the main token set, all of selected visibility, one repository named. On
37142b0 it made 23 calls where 13 would do (the review's finding 3)."""
import io, subprocess, sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode = True
# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
CHECKOUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(CHECKOUT / part) for part in ("scripts", "tests", "tools")]
import tokens, fake_gh, test_tokens as t, unittest
class Count(unittest.TestCase):
    def test(self):
        names = [tokens.slot_secret(s) for s in tokens.SLOTS] + [tokens.MAIN_SECRET]
        world = t.World(self, secrets=[t.secret(n) for n in names], variables=[t.variable(tokens.ACCOUNTS_VARIABLE, ",".join(map(str, tokens.SLOTS)))])
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        with patch.object(tokens.subprocess, "run", run), redirect_stdout(io.StringIO()):
            tokens.print_status(tokens.State(tokens.Gh(), t.target()))
        keys = [c["key"] for c in world.calls()]
        reach = [k for k in keys if k.endswith("/repositories")]
        print(CHECKOUT.name, "calls", len(keys), "repository listings", len(reach), "distinct", len(set(reach)))
unittest.main(argv=sys.argv[:1], verbosity=0)
