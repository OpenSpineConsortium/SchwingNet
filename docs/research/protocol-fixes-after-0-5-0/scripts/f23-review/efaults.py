"""The deep lane's E-faults space on the library at hand."""
import sys
import time
from validation import deep
space = deep.SPACES[sys.argv[1] if len(sys.argv) > 1 else "E-faults"]
began = time.time()
result = deep.search_space(space, budget=3000.0)
print(space.name, "states", result.states, "transitions", result.transitions, "seconds", round(time.time() - began),
      "stopped", result.stopped)
for f in result.found:
    print("FOUND", f.guarantee, f.detail, f.count)
    print("   ", ", ".join(str(v) for v in f.trace)[:800])
