"""Print each Bash command of a transcript that two trees of tools/profile.py
split into different commands (commands_of), to check a change to the
splitting by eye. Arguments: a folder holding main/ and new/, copies of the
two trees, and the transcript."""
import importlib.util, json, sys
from pathlib import Path

def load(root, name):
    sys.path.insert(0, f"{root}/tools")
    spec = importlib.util.spec_from_file_location(f"{name}_profile", f"{root}/tools/profile.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.path.pop(0)
    for key in [k for k in sys.modules if k in ("usage", "sdlc_protocol") or k.startswith("sdlc_protocol.")]:
        del sys.modules[key]
    return module

T = sys.argv[1]
old, new = load(f"{T}/main", "main"), load(f"{T}/new", "new")
for line in open(sys.argv[2], encoding="utf-8", errors="replace"):
    try:
        entry = json.loads(line)
    except ValueError:
        continue
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        continue
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Bash":
            command = (block.get("input") or {}).get("command") or ""
            a, b = old.commands_of(command), new.commands_of(command)
            if a != b:
                print("=" * 60)
                print(command[:1200])
                print("--- old:", [c[:3] for c in a][:12])
                print("--- new:", [c[:3] for c in b][:12])
