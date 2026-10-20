"""A 4xx on the release comment, then the re-read refused: the library
against main's one-rule F20 mutant, with the fault added in memory only."""
import sys
sys.path.insert(0, sys.argv[0].rsplit("/", 1)[0])
import extra_mutants  # noqa: E402
from validation import cycle, invariants, model as M, mutants, verbs  # noqa: E402
from validation.fake_github import Fault  # noqa: E402
from validation.verbs import Verb  # noqa: E402

verbs.FAULTS["comment-422-then-unread"] = Fault("POST", "/issues/*/comments", 422, message="Validation Failed",
                                                then=Fault("GET", "/issues/*/comments", 500))
BOARD = Verb("board", "board", (cycle.SCHEDULE, ""))
DUE = [Verb("claim", "a", (1,)), Verb("label-on", "a", (1, "claimed")), Verb("label-on", "a", (1, "worker:a")),
       Verb("wait", "clock", (25,))]


def play(steps):
    model = M.seeded((1,), writers=("a", "b", "c", verbs.CAROL, verbs.DANA), labels=("todo",))
    cycle.board_run(model)
    found = []
    for step in steps:
        before = model.clone()
        outcome = verbs.apply(model, step, verbs.Scope())
        found += invariants.step_checks(before, model, step, outcome)
    return model, found


steps = DUE + [Verb("board", "board", (cycle.SCHEDULE, "", ("comment-422-then-unread",)))]
model, found = play(steps)
print("library: labels", sorted(model.issues[1].labels), "violations", [(v.guarantee, v.detail) for v in found])
model, found = play(steps + [BOARD])
print("library, next run: labels", sorted(model.issues[1].labels), "claude/1" in model.refs, [(v.guarantee, v.detail) for v in found])
for name in ("F20's mutant as it was on main", "a refusal's refused re-read put back"):
    mutants.MUTANTS.update(extra_mutants.EXTRA)
    with mutants.switched_on(mutants.MUTANTS[name]):
        model, found = play(steps)
    print(name, ": labels", sorted(model.issues[1].labels), [(v.guarantee, v.detail) for v in found])
