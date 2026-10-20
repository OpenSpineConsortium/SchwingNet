"""Probe: does one apostrophe in a here-document body hide a push from the guard?"""
import inspect
import sys

sys.path.insert(0, sys.argv[1])
from sdlc_protocol import guard  # noqa: E402

COMMANDS = {
    "plain push": "git push --force origin main",
    "after a here-document with an apostrophe": "cat > m.txt <<'EOF'\nIt's done\nEOF\ngit push --force origin main",
    "after a here-document with no apostrophe": "cat > m.txt <<'EOF'\nIt is done\nEOF\ngit push --force origin main",
    "inside $(cat <<EOF) with a lone double quote": 'git commit -m "$(cat <<\'EOF\'\nsay "hi\nEOF\n)" && git push --force origin main',
    "unclosed quote alone": "echo 'oops\ngit push --force origin main",
}
print("run signature:", inspect.signature(guard.run))
for name, command in COMMANDS.items():
    payload = {"tool_input": {"command": command}, "cwd": "."}
    try:
        code, said = guard.run(payload, cwd=".") if "cwd" in inspect.signature(guard.run).parameters else guard.run(payload)
    except Exception as problem:  # noqa: BLE001 - a probe reports whatever happens
        code, said = "raised", repr(problem)
    print(f"{name}: {code} {said.splitlines()[0][:100] if said else ''}")
