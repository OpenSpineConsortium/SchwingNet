"""Which pushes bash runs for each command, by -c and on stdin, with a git
that records a push and runs nothing; and what the guard on a checkout
says of it. Usage: python3.12 -I runs.py <checkout> <commands.json>"""
import json, os, subprocess, sys, tempfile
checkout, listing = sys.argv[1], sys.argv[2]
sys.path.insert(0, checkout)
from sdlc_protocol import guard
here = os.path.dirname(os.path.abspath(__file__))
commands = json.load(open(listing))
for command in commands:
    found = []
    for how in ("-c", "stdin"):
        with tempfile.NamedTemporaryFile("r", delete=False) as log, tempfile.TemporaryDirectory() as work:
            env = {"PATH": os.path.join(here, "bin") + ":/usr/bin:/bin", "PUSH_LOG": log.name, "HOME": work}
            args = ["bash", "-c", command] if how == "-c" else ["bash"]
            subprocess.run(args, input=None if how == "-c" else command, text=True, cwd=work, env=env,
                           capture_output=True, timeout=20)
            found.append(open(log.name).read().strip().replace("\n", " | ") or "-")
            os.unlink(log.name)
    verdict = guard.refused_push(command, "/w", lambda place: ("claude/7", "main"), lambda place: None,
                                 lambda place: True)
    print(json.dumps(command))
    print("   bash -c:", found[0], "   stdin:", found[1])
    print("   guard:", "REFUSED" if verdict else "passed")
