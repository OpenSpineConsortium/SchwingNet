"""The follow-up's first review probe of parity (written against 41c6545):
the wizard's reading of SYMPHONY_CLAUDE_ACCOUNTS beside the bench's
(coordbench bench/cooperbench/actions/plan.py, chosen_accounts, retyped
here from its source: words split on [,\\s]+, each one exactly "1" to "8"),
and what update_accounts does with a hand-made list the bench refuses. On
41c6545 the wizard read "01,02", "1,2,9", "1,2,junk" and a superscript two
as slots and left them, where the bench refuses each."""

import io
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.dont_write_bytecode = True
# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
CHECKOUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(CHECKOUT / part) for part in ("scripts", "tests", "tools")]
import tokens  # noqa: E402

BENCH_SLOTS = tuple(str(n) for n in range(1, 9))
SEPARATORS = re.compile(r"[,\s]+")


def bench_reads(text):
    words = [word for word in SEPARATORS.split((text or "").strip()) if word]
    bad = [word for word in words if word not in BENCH_SLOTS]
    return f"refused at {bad[0]!r}" if bad else words


for value in ("1,2", "01,02", "1,2,9", "1,2,junk", "1,1,2", "3, 1 1,9,0,08", "1;2", "\u00b2,2"):
    print(f"{value!r:22} wizard {tokens.parse_slots(value)!s:12} bench {bench_reads(value)}")


class FakeGh:
    def __init__(self):
        self.calls = []

    def must(self, args, stdin=None):
        self.calls.append(args)
        return ""


class FakeState:
    """Slots 1 and 2 set at a repository target, the list made by hand."""

    def __init__(self, value):
        self.gh = FakeGh()
        self.target = tokens.Target("repo", "octo", name="coordbench")
        self.secrets = {tokens.slot_secret(1): {}, tokens.slot_secret(2): {}}
        self.variables = {tokens.ACCOUNTS_VARIABLE: {"name": tokens.ACCOUNTS_VARIABLE, "value": value}}

    def slots_set(self):
        return [1, 2]


for value in ("01,02", "1,2,9", "1,2,junk", "2 1"):
    state = FakeState(value)
    printed = io.StringIO()
    with redirect_stdout(printed):
        tokens.update_accounts(state, scope=[])
    print(f"update_accounts with {value!r}: printed {printed.getvalue().strip()!r}, writes {len(state.gh.calls)}; bench {bench_reads(value)}")
