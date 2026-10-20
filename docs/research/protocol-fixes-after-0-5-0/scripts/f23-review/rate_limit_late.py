"""If GitHub wrote a comment it refused for a rate limit (C4 false) and
listed it late, as F23 assumes it may after a 5xx: the fixed library puts
the labels back beside it, F23's own failure. The fault is added in
memory only."""
import sys
from validation import cycle, invariants, model as M, verbs
from validation.fake_github import LISTED_LATE, Fault
from validation.verbs import Verb

verbs.FAULTS["comment-limited-late"] = Fault(
    "POST", "/issues/*/comments", 403, applied=True, message="You have exceeded a secondary rate limit",
    then=Fault("GET", "/issues/*/comments", 200, answer=LISTED_LATE))
BOARD = Verb("board", "board", (cycle.SCHEDULE, ""))
DUE = [Verb("claim", "a", (1,)), Verb("label-on", "a", (1, "claimed")), Verb("label-on", "a", (1, "worker:a")),
       Verb("wait", "clock", (25,))]
model = M.seeded((1,), writers=("a", "b", "c", verbs.CAROL, verbs.DANA), labels=("todo",))
cycle.board_run(model)
steps = DUE + [Verb("board", "board", (cycle.SCHEDULE, "", ("comment-limited-late",))), BOARD,
               Verb("wait", "clock", (48,)), BOARD]
for step in steps:
    before = model.clone()
    outcome = verbs.apply(model, step, verbs.Scope())
    found = invariants.step_checks(before, model, step, outcome)
    if step.name == "board":
        print(step, "labels", sorted(model.issues[1].labels), "claude/1 kept:", "claude/1" in model.refs,
              "release comments:", sum("claim-released" in c.body for c in model.comments_on(1)),
              [(v.guarantee, v.detail) for v in found])
