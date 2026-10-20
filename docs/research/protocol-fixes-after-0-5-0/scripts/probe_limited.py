"""Play a due claim under the rate-limit comment faults with the fixed rule
and with the rule before finding 3's fix, and print what each run did."""
import sys
from unittest import mock

sys.path.insert(0, "/home/user/proto-f23")
sys.path.insert(0, "/home/user/proto-f23/tests")

from sdlc_protocol.adapters import github
import test_validation_invariants as T
from validation.verbs import Verb

DUE = [Verb("claim", "a", (1,)), Verb("label-on", "a", (1, "claimed")), Verb("label-on", "a", (1, "worker:a")),
       Verb("wait", "clock", (25,))]


def old_rule(problem):
    return problem.status is not None and 400 <= problem.status < 500


for fault in ("comment-limited-late", "comment-limited-for-the-run", "comment-limited-then-unread", "comment-422"):
    for name, patch in (("fixed", None), ("old rule", old_rule)):
        ctx = mock.patch.object(github, "wrote_nothing", patch) if patch else mock.patch.object(github, "VERSION_UNUSED", None, create=True)
        with ctx:
            model, found = T.played(DUE + [T.board_with(fault)])
            labels1 = sorted(model.issues[1].labels)
            comments1 = T.release_comments(model, 1)
            model2, found2 = T.played(DUE + [T.board_with(fault), T.BOARD])
        print(f"{fault:30} {name:9} run1 labels={labels1} release_comments={comments1} "
              f"violations={[(v.guarantee, v.detail) for v in found]}")
        print(f"{'':30} {'':9} run2 labels={sorted(model2.issues[1].labels)} claude/1={'claude/1' in model2.refs} "
              f"release_comments={T.release_comments(model2, 1)} violations={[(v.guarantee, v.detail) for v in found2]}")
