"""Print each red step's violation messages and the mismatches of one trace."""
import sys
from validation import replay
trace = replay.load(sys.argv[1])
record = replay.replay(trace)
for at, v in record.violations:
    print("VIOLATION", at, v.guarantee, getattr(v, "message", v))
for m in record.mismatches[: int(sys.argv[2]) if len(sys.argv) > 2 else 40]:
    print("MISMATCH", m)
