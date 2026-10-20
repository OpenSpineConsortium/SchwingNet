"""The second review pass's options probe as a process (written against
5a65e4f): scripts/tokens.py copied into scratch clones whose origin is an
organization and then a person, run with python3 -I against the tests'
fake gh (tests/fake_gh.py), printing each run's exit, the gh calls it made
and its last error line. No call reaches GitHub."""
import os, sys, json, subprocess, tempfile
from pathlib import Path

# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
CHECKOUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(CHECKOUT / part) for part in ("scripts", "tests", "tools")]
import fake_gh
def clone(origin):
    d = Path(tempfile.mkdtemp(prefix="clone-"))
    subprocess.run(["git", "init", "-q", str(d)]); subprocess.run(["git", "-C", str(d), "remote", "add", "origin", origin])
    (d / "scripts").mkdir(); (d / "docs").mkdir()
    (d / "scripts" / "tokens.py").write_bytes((CHECKOUT / "scripts" / "tokens.py").read_bytes())
    (d / "docs" / "project.md").write_text("# P\n\n## Crowd mode\n\n- Crowd mode: off.\n")
    return d
status = "github.com\n  Logged in to github.com account me (keyring)\n  - Active account: true\n  - Token scopes: 'admin:org', 'repo'\n"
def world(folder):
    routes = {"auth status": [fake_gh.answer(200, status)], "GET users/octo": [fake_gh.answer(200, "Organization\n")],
              "GET users/ada": [fake_gh.answer(200, "User\n")], "secret list": [fake_gh.answer(200, [])], "variable list": [fake_gh.answer(200, [])]}
    return fake_gh.environment(folder, routes)
def run(d, argv):
    w = Path(tempfile.mkdtemp(prefix="w-")); env = dict(os.environ); env.update(world(w))
    done = subprocess.run([sys.executable, "-I", str(d / "scripts" / "tokens.py")] + argv, capture_output=True, text=True, env=env, cwd=str(d))
    keys = [c["key"] for c in fake_gh.calls(env["FAKE_GH_LOG"])]
    last = (done.stderr.strip().splitlines() or [""])[-1][:95]
    print(f"  {' '.join(argv):50s} -> exit {done.returncode}; gh: {keys}; {last}")
org = clone("git@github.com:octo/widgets.git")
print("== organization origin (octo/widgets) ==")
for argv in (["--org", "octo", "--visibility", "all", "status"], ["--repos", "coordbench", "status"], ["--visibility", "all", "status"], ["status"],
             ["--org", "octo", "status"], ["--org", "elsewhere", "status"], ["--repo", "o/n", "--visibility", "selected", "status"],
             ["--org", "x", "--repos", "a", "--visibility", "private", "status"], ["--visibility", "selected", "status"]):
    run(org, argv)
person = clone("https://github.com/ada/engine.git")
print("== personal origin (ada/engine) ==")
for argv in (["--repos", "x", "status"], ["--visibility", "all", "status"], ["status"], ["--org", "octo", "--repos", "a", "status"]):
    run(person, argv)
