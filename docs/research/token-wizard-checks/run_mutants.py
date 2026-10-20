"""The thread's mutants of the follow-up (written against 3675c99, which is
scripts/tokens.py as symphony-template#105 merged it): one mutation at a
time on a scratch copy of the tree's scripts/, tests/ and tools/, with
tests.test_tokens run there. The base must pass and every mutant must
fail; on 3675c99 all sixteen fail."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
WORK = Path(tempfile.mkdtemp(prefix="wizard-mutants-")) / "copy"
BASE = "none (the base must pass)"
MUTANTS = {
    BASE: ("    return SLOT_WORDS.get(text)", "    return SLOT_WORDS.get(text)"),
    "raw value printed": ("({slots_text(own[ACCOUNTS_VARIABLE].get('value', ''))})", "({own[ACCOUNTS_VARIABLE].get('value', '')})"),
    "no try on the variable read": ("        print(f\"  {full}: its own variables could not be read ({error})\")\n        return",
                                   "        raise"),
    "named repositories only": ("    for full, names in repositories_reading(state).items():", "    for full, names in {f: None for f in state.target.repositories()}.items():"),
    "labels raw": ("found[slot] = value if LABEL_SHAPE.fullmatch(value) else", "found[slot] = value if True else"),
    "list compared by slots": ("list_words(have.get(\"value\", \"\")) == words", "parse_slots(have.get(\"value\", \"\")) == state.slots_set()"),
    "int reader": ("    return SLOT_WORDS.get(text)", "    return int(text) if text.isdigit() and int(text) in SLOTS else None"),
    "match not fullmatch": ("if label and not LABEL_SHAPE.fullmatch(label):", "if label and not LABEL_SHAPE.match(label):"),
    "case-sensitive variable names": ("own = {item[\"name\"].upper(): item for item in state.gh.json([\"variable\"", "own = {item[\"name\"]: item for item in state.gh.json([\"variable\""),
    "case-sensitive secret names": ("own = {item[\"name\"].upper(): item for item in state.gh.json([\"secret\"", "own = {item[\"name\"]: item for item in state.gh.json([\"secret\""),
    "closing status not read again": ("    print_status(State(gh, target) if added else state)", "    print_status(state)"),
    "every read repository reads any name": ("                reading[full] = set(everywhere)", "                reading[full] = None"),
    "no listing cache": ("        if (kind, name) not in self.reached:", "        if True:"),
    "no rewrite note": ("rewrite = \"; the next add or remove rewrites it\" if holds_other_words(value) else \"\"", "rewrite = \"\""),
    "secrets' listings not read": ("    kept += [(\"secrets\", name, state.secrets[name]) for name in names if name in state.secrets]", "    kept += []"),
    "failed listing silent": ("            if kind == \"variables\":\n                print(", "            if False:\n                print("),
    "dedupe by case": ("full = known.setdefault(f\"{state.target.owner}/{repo}\".lower(), f\"{state.target.owner}/{repo}\")", "full = known.setdefault(f\"{state.target.owner}/{repo}\", f\"{state.target.owner}/{repo}\")"),
}
for name, (old, new) in MUTANTS.items():
    if WORK.exists():
        shutil.rmtree(WORK)
    (WORK / "scripts").mkdir(parents=True)
    shutil.copytree(REPO / "tests", WORK / "tests")
    shutil.copytree(REPO / "tools", WORK / "tools")
    source = (REPO / "scripts" / "tokens.py").read_text()
    assert source.count(old) == 1, name
    (WORK / "scripts" / "tokens.py").write_text(source.replace(old, new))
    result = subprocess.run([sys.executable, "-m", "unittest", "tests.test_tokens"], cwd=WORK, capture_output=True, text=True)
    last = result.stderr.strip().splitlines()[-1]
    if name == BASE:
        verdict = "passes" if result.returncode == 0 else "FAILS"
    else:
        verdict = "caught" if result.returncode else "SURVIVED"
    print(f"{name:37} {verdict} ({last})")
shutil.rmtree(WORK.parent, ignore_errors=True)
