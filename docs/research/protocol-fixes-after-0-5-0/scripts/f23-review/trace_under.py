"""Replay one trace with one mutant (from the lane or the scratch extras) on."""
import sys
sys.path.insert(0, sys.argv[0].rsplit("/", 1)[0])
import extra_mutants  # noqa: E402
from validation import mutants, replay  # noqa: E402
mutants.MUTANTS.update(extra_mutants.EXTRA)
trace = replay.load(sys.argv[1])
with mutants.switched_on(mutants.MUTANTS[sys.argv[2]]):
    record = replay.replay(trace)
for at, v in record.violations:
    print(at, v.guarantee, v.detail)
print("mismatches", len(record.mismatches))
