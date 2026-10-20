"""The follow-up's second review probe of the closing status (written
against 37142b0, as three scripts, one per case, joined here): the wizard
against the tests' fake gh and fake claude, filling one slot and stopping,
on the owner's first run (an empty organization), with slot 1 set and the
list "1", and with slot 1 set and the list "01" that the bench refuses.
It prints where the run wrote the list and what the closing status said
about it. On 37142b0 the closing status showed the list as it was before
the write (the review's finding 1): "not set" on the first run."""

import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
CHECKOUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(CHECKOUT / part) for part in ("scripts", "tests", "tools")]
import tokens  # noqa: E402
import test_tokens as t  # noqa: E402

# (what the case is, the slots set before, the list before or None, the slot the run fills)
CASES = (
    ("the owner's first run, an empty organization", [], None, 1),
    ("slot 1 set, the list 1", [1], "1", 2),
    ("slot 1 set, the list 01, which the bench refuses", [1], "01", 2),
)


class ClosingStatus(unittest.TestCase):
    def test_closing_status(self):
        for label, slots, value, fills in CASES:
            with self.subTest(label):
                self.show(label, slots, value, fills)

    def show(self, label, slots, value, fills):
        variables = [] if value is None else [t.variable(tokens.ACCOUNTS_VARIABLE, value)]
        world = t.World(self, secrets=[t.secret(tokens.slot_secret(slot)) for slot in slots], variables=variables)
        world.expect_store(tokens.slot_secret(fills))
        answers = iter(["", "", "", "n", "n"])
        _, printed, calls = world.run_in_process(self, tokens.wizard, tokens.Gh(), t.target(),
                                                 ask=lambda prompt: next(answers))
        keys = [(c["key"], c["args"][2] if len(c["args"]) > 2 else "") for c in calls]
        wrote = [i for i, (key, name) in enumerate(keys) if key == "variable set" and name == tokens.ACCOUNTS_VARIABLE]
        lists_after = [i for i, (key, _) in enumerate(keys) if key == "variable list" and wrote and i > wrote[0]]
        print(f"== {label} ==")
        print("list written at call", wrote, "with", [c["args"][-1] for c in calls if c["key"] == "variable set"])
        print("variable list calls after that write:", lists_after)
        lines = [line for line in printed.splitlines() if tokens.ACCOUNTS_VARIABLE + ":" in line]
        print("status lines about the list:")
        for line in lines:
            print("   ", line)


if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1], verbosity=0)
