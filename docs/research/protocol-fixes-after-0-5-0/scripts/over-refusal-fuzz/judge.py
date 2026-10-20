"""Judge each command of a JSON list with one checkout's guard.refused_push:
python3.12 -I judge.py <library checkout> <commands.json> <out.json>."""
import json, sys
sys.path.insert(0, sys.argv[1])
from sdlc_protocol import guard
commands = json.load(open(sys.argv[2]))
out = []
for command in commands:
    reason = guard.refused_push(command, "/w", lambda place: ("claude/7", "main"),
                                lambda place: None, lambda place: True)
    out.append(reason or None)
json.dump(out, open(sys.argv[3], "w"))
