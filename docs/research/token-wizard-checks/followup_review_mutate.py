"""The follow-up's first review mutants (written against 41c6545): one
textual mutant at a time on a scratch copy of the tree's scripts/, tests/,
tools/ and docs/, with tests.test_tokens run there; it prints whether the
suite still passes. On 41c6545 the first three survived (the review's
finding 5) and the length bound and the ASCII check were caught."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
WORK = Path(tempfile.mkdtemp(prefix="wizard-mutants-")) / "copy"

MUTANTS = {
    "raw value printed": (
        'named = ",".join(str(slot) for slot in parse_slots(own[ACCOUNTS_VARIABLE].get("value", ""))) or "no slot"',
        'named = own[ACCOUNTS_VARIABLE].get("value", "") or "no slot"',
    ),
    "no try around the variable read": (
        '''    try:
        own = {item["name"]: item for item in state.gh.json(["variable", "list", "--repo", full, "--json", "name,value"])}
    except TokensError as error:
        print(f"  {full}: its own variables could not be read ({error})")
        return
''',
        '''    own = {item["name"]: item for item in state.gh.json(["variable", "list", "--repo", full, "--json", "name,value"])}
''',
    ),
    "failure stops status": (
        '''        print(f"  {full}: its own variables could not be read ({error})")
        return
''',
        '''        raise
''',
    ),
    "no length bound": (
        "text.isascii() and text.isdigit() and len(text) <= 9 and int(text) in SLOTS",
        "text.isascii() and text.isdigit() and int(text) in SLOTS",
    ),
    "no ascii check": (
        "text.isascii() and text.isdigit() and len(text) <= 9 and int(text) in SLOTS",
        "text.isdigit() and len(text) <= 9 and int(text) in SLOTS",
    ),
    "no slot word dropped": (
        '))) or "no slot"',
        ')))',
    ),
}


def run(name, old, new):
    if WORK.exists():
        shutil.rmtree(WORK)
    for part in ("scripts", "tests", "tools", "docs"):
        shutil.copytree(REPO / part, WORK / part, ignore=shutil.ignore_patterns("__pycache__"))
    script = WORK / "scripts" / "tokens.py"
    text = script.read_text(encoding="utf-8")
    if text.count(old) != 1:
        print(f"{name}: mutant text not found once ({text.count(old)})")
        return
    script.write_text(text.replace(old, new), encoding="utf-8")
    done = subprocess.run([sys.executable, "-m", "unittest", "tests.test_tokens"], cwd=WORK,
                          capture_output=True, text=True)
    tail = done.stderr.strip().splitlines()[-1] if done.stderr.strip() else ""
    verdict = "SURVIVES (suite passes)" if done.returncode == 0 else "killed"
    print(f"{name}: {verdict}; {tail}")


for name, (old, new) in MUTANTS.items():
    run(name, old, new)
shutil.rmtree(WORK.parent, ignore_errors=True)
