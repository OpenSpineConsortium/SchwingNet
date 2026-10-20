"""The follow-up's second review mutants (written against 37142b0): each
run against tests.test_tokens on a scratch copy of the tree's scripts/,
tests/, tools/ and docs/. On 37142b0 the five mutants survived (the
review's finding 4: five new behaviours had no test) and the base passed."""
import shutil, subprocess, sys, tempfile
from pathlib import Path
# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
WORK = Path(tempfile.mkdtemp(prefix="wizard-mutants-")) / "copy"
MUTANTS = {
    "no rewrite note on the list line": ('rewrite = "; the next add or remove rewrites it" if holds_other_words(value) else ""', 'rewrite = ""'),
    "secrets' listings not consulted": ('kept = [("variables", ACCOUNTS_VARIABLE)] + [("secrets", name) for name in names if name in state.secrets]', 'kept = [("variables", ACCOUNTS_VARIABLE)]'),
    "failed listing of the variable silent": ('''            if kind == "variables":
                print(f"  the repositories that see {name} could not be listed ({error})")
''', ''),
    "own secrets compared by case": ('own = {item["name"].upper(): item for item in state.gh.json(["secret", "list"', 'own = {item["name"]: item for item in state.gh.json(["secret", "list"'),
    "repositories deduplicated by case": ('            if full.lower() not in seen:\n                seen.add(full.lower())', '            if full not in seen:\n                seen.add(full)'),
    "base run (no change)": ('def list_words(text):', 'def list_words(text):'),
}
def run(name, old, new):
    shutil.rmtree(WORK, ignore_errors=True)
    for part in ("scripts", "tests", "tools", "docs"):
        shutil.copytree(REPO / part, WORK / part, ignore=shutil.ignore_patterns("__pycache__"))
    script = WORK / "scripts" / "tokens.py"
    text = script.read_text(encoding="utf-8")
    if text.count(old) != 1:
        print(f"{name}: text found {text.count(old)} times"); return
    script.write_text(text.replace(old, new), encoding="utf-8")
    done = subprocess.run([sys.executable, "-B", "-m", "unittest", "tests.test_tokens"], cwd=WORK, capture_output=True, text=True)
    tail = done.stderr.strip().splitlines()[-1] if done.stderr.strip() else ""
    print(f"{name}: {'SURVIVES' if done.returncode == 0 else 'killed'} ({tail})")
for name, (old, new) in MUTANTS.items():
    run(name, old, new)
shutil.rmtree(WORK.parent, ignore_errors=True)
