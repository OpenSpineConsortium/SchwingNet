"""A release whose label step fails: the run's line and whether it reads
the issue's comments, as the PR's spec now says every failing run does."""
from validation import cycle, model as M, verbs
from validation.verbs import Verb

DUE = [Verb("claim", "a", (1,)), Verb("label-on", "a", (1, "claimed")), Verb("label-on", "a", (1, "worker:a")),
       Verb("wait", "clock", (25,))]
for fault in ("label-delete-500", "label-post-500", "label-post-lost"):
    model = M.seeded((1,), writers=("a",), labels=())
    cycle.board_run(model)
    for step in DUE:
        verbs.apply(model, step)
    record = cycle.board_run(model, faults=(verbs.FAULTS[fault],))
    reads = [c.status for c in record.calls if c.method == "GET" and c.path == "/issues/1/comments"]
    posts = [c.status for c in record.calls if c.method == "POST" and c.path == "/issues/1/comments"]
    print(fault, "| comment posts", posts, "| comment reads", reads, "| labels", sorted(model.issues[1].labels))
    print("   ", next(line for line in record.lines if line.startswith("#1")))
