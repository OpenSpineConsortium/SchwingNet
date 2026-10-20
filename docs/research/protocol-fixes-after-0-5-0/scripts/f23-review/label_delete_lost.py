"""A label's DELETE GitHub makes and answers with a 502, or with no
answer, at the release's first label: what the run leaves and what the
invariants say. The faults are added in memory only."""
from validation import cycle, invariants, model as M, verbs
from validation.fake_github import Fault
from validation.verbs import Verb

verbs.FAULTS["label-delete-lost"] = Fault("DELETE", "/issues/*/labels/*", 502, applied=True)
verbs.FAULTS["label-delete-unanswered"] = Fault("DELETE", "/issues/*/labels/*", None, applied=True, message="timed out")
BOARD = Verb("board", "board", (cycle.SCHEDULE, ""))
DUE = [Verb("claim", "a", (1,)), Verb("label-on", "a", (1, "claimed")), Verb("label-on", "a", (1, "worker:a")),
       Verb("wait", "clock", (25,))]
for fault in ("label-delete-lost", "label-delete-unanswered", "label-delete-500"):
    model = M.seeded((1,), writers=("a", "b", "c", verbs.CAROL, verbs.DANA))
    cycle.board_run(model)
    for step in DUE + [Verb("board", "board", (cycle.SCHEDULE, "", (fault,))), BOARD]:
        before = model.clone()
        outcome = verbs.apply(model, step, verbs.Scope())
        found = invariants.step_checks(before, model, step, outcome)
        if step.name == "board":
            print(fault, "|", step, "| labels", sorted(model.issues[1].labels), "| claude/1 kept:", "claude/1" in model.refs,
                  "|", [(v.guarantee, v.detail) for v in found])
