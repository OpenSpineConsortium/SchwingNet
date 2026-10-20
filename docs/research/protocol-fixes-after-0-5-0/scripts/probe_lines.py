"""Print the board run's log lines for a due claim under a fault."""
import sys

sys.path.insert(0, "/home/user/proto-f23")

from validation import cycle, model as M, verbs
from validation.verbs import Scope, Verb

for fault in sys.argv[1:]:
    model = M.seeded((1,), writers=("a",))
    cycle.board_run(model)
    for step in [Verb("claim", "a", (1,)), Verb("label-on", "a", (1, "claimed")), Verb("label-on", "a", (1, "worker:a")),
                 Verb("wait", "clock", (25,))]:
        verbs.apply(model, step, Scope())
    record = cycle.board_run(model, cycle.SCHEDULE, "", (verbs.FAULTS[fault],))
    print(fault)
    for line in record.lines:
        if "#1" in line or "REST" in line:
            print("   ", line)
