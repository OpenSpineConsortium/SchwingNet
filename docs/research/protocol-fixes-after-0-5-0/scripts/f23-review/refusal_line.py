"""The run's line for a 4xx then a refused re-read, and for a 4xx alone,
with the fault added in memory only."""
from validation import cycle, model as M, verbs
from validation.fake_github import Fault
from validation.verbs import Verb

verbs.FAULTS["comment-422-then-unread"] = Fault("POST", "/issues/*/comments", 422, message="Validation Failed",
                                                then=Fault("GET", "/issues/*/comments", 500))
DUE = [Verb("claim", "a", (1,)), Verb("label-on", "a", (1, "claimed")), Verb("label-on", "a", (1, "worker:a")),
       Verb("wait", "clock", (25,))]
for fault in ("comment-422-then-unread", "comment-422", "comment-late"):
    model = M.seeded((1,), writers=("a",))
    cycle.board_run(model)
    for step in DUE:
        verbs.apply(model, step)
    record = cycle.board_run(model, faults=(verbs.FAULTS[fault],))
    for line in record.lines:
        if line.startswith("#1"):
            print(fault, "=>", line)
