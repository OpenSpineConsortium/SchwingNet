"""tools/run_code.py names a run by the code it executes, and its lists miss nothing that code runs.

A run is carried on after main has moved only where none of the files its digest covers changed
(issue #252, finding 27), so the lists must hold everything a kind executes: these tests follow each
kind's code from its entry, through its imports, a relative one read against its file's package as
Python reads it, the tools it loads and the scripts it names, and fail on any file that is neither
in the kind's digest nor left out with a reason. Bank and catalog have a second entry, the PYDRV
grid/gate.sh exports, through which their steps run every tool on the grid. The following is
by reading the source, a little wider than what runs: a path named in a message counts as reached,
and then it is left out by name, with that reason. A scratch repository then shows the digest kept
by a commit that changes none of a kind's files and changed by one that changes any. The standard
library alone, so the tests run under the required check's plain python3.
"""

import ast
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The python grid/gate.sh hands every job as PYDRV, by its path in the checkout: the bank and catalog
# stages run each tool of their steps through it, so their code starts there too (issue #252, the
# second review's finding 4).
PYDRV = tuple(re.findall(r"^export PYDRV=\$REPO/(\S+)$", (ROOT / "grid" / "gate.sh").read_text(encoding="utf-8"), re.M))
ENTRIES = {"row": ("tools/flow.py",), "state": ("tools/block_sweep.py",), "sweep": ("flows/sweep.py",), "v1": ("flows/v1.py",),
           "bank": ("flows/bank.py", *PYDRV), "catalog": ("flows/catalog.py", *PYDRV), "realism": ("flows/realism.py",)}
SCRIPT_WORD = re.compile(r"(?<![\w.-])((?:tools|grid|flows)/[\w.-]+\.(?:py|sh|sbatch|awk))(?![\w/-])")
# A script that finds its neighbours from where it lies, as grid/bin/train-cpu-python does:
# here=$(cd "$(dirname "$0")/.." && pwd), then "$here/box.sh".
PLACE = re.compile(r'^(\w+)=\$\(cd "\$\(dirname "\$0"\)(/[^"]*)?" && pwd\)$')
# Where the packages the repository's code imports by name lie, as module_files finds them.
PACKAGE_FOLDERS = {"schwingnet": "src", "beethoven_qa": "vendor/beethoven-qa/src"}
FOLDERS = ("tools", "grid", "flows")
CODE = (".py", ".sh", ".sbatch", ".awk")
# A scratch repository's git never runs maintenance of its own, which races a test's cleanup.
QUIET_GIT = {"GIT_CONFIG_COUNT": "4", "GIT_CONFIG_KEY_0": "gc.auto", "GIT_CONFIG_VALUE_0": "0",
             "GIT_CONFIG_KEY_1": "gc.autoDetach", "GIT_CONFIG_VALUE_1": "false",
             "GIT_CONFIG_KEY_2": "maintenance.auto", "GIT_CONFIG_VALUE_2": "false",
             "GIT_CONFIG_KEY_3": "maintenance.autoDetach", "GIT_CONFIG_VALUE_3": "false"}


def load_run_code():
    spec = importlib.util.spec_from_file_location("schwingnet_tool_run_code", ROOT / "tools" / "run_code.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def docstrings(tree):
    """The ids of the docstring constants, whose paths are prose and never run."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def module_files(name):
    """The files importing a module runs: each package's __init__ on the way, then the module."""
    parts = name.split(".")
    base = PACKAGE_FOLDERS.get(parts[0])
    if base is None:
        return []
    found = []
    for depth in range(1, len(parts) + 1):
        stem = "/".join(parts[:depth])
        for candidate in (f"{base}/{stem}/__init__.py", f"{base}/{stem}.py"):
            if (ROOT / candidate).is_file():
                found.append(candidate)
                break
    return found


def joined_words(node):
    """The constant words of a chain of path joins (ROOT / "tools" / "flow.py"), None for others."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return joined_words(node.left) + joined_words(node.right)
    return [node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None]


def package_of(path):
    """The package a module of the repository's packages lies in, as a list of names, which its
    relative imports are read against; None for a file in none, where a relative import fails."""
    for package, folder in PACKAGE_FOLDERS.items():
        if path.startswith(f"{folder}/{package}/") and path.endswith(".py"):
            return path[len(folder) + 1:-len(".py")].split("/")[:-1]
    return None


def imported_names(node, path):
    """The modules an import statement names, a relative one (from . import x) read against the
    package of the file that holds it, as Python reads it."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    start = node.module
    if node.level > 0:
        package = package_of(path)
        if package is None or node.level > len(package):  # no package, or above the top one
            return []
        start = ".".join(package[:len(package) - node.level + 1] + ([node.module] if node.module else []))
    return [start, *(f"{start}.{alias.name}" for alias in node.names)] if start else []


def import_references(node, tools_on_path, path):
    """What an import statement runs; tools/ingest.py puts tools/ on its path and imports its
    neighbours by their bare names, and a flow of flows/, run as a script, imports its neighbours
    in flows/ the same way, its own folder first on Python's path."""
    names = imported_names(node, path)
    found = [file for name in names for file in module_files(name)]
    found += [f"tools/{name}.py" for name in names if tools_on_path and (ROOT / "tools" / f"{name}.py").is_file()]
    found += [f"flows/{name}.py" for name in names if path.startswith("flows/") and (ROOT / "flows" / f"{name}.py").is_file()]
    return found


def node_references(node, skip, tools_on_path, path):
    """The repository files one node of a module's tree names as code."""
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return import_references(node, tools_on_path, path)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("load_tool", "run_tool") and node.args:
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return [f"tools/{first.value.removesuffix('.py')}.py"]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        words = joined_words(node)
        return [f"{word}/{after}" for word, after in zip(words, words[1:]) if word in FOLDERS and after]
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
        return SCRIPT_WORD.findall(node.value)
    return []


def source_of(name):
    return (ROOT / name).read_text(encoding="utf-8")


def python_references(path, text):
    tree = ast.parse(text)
    skip, tools_on_path = docstrings(tree), 'sys.path.insert(0, str(ROOT / "tools"))' in text
    return {name for node in ast.walk(tree) for name in node_references(node, skip, tools_on_path, path)}


def placed_references(path, lines):
    """The files a script names through a variable it sets to a folder by where it lies itself."""
    found = set()
    for place in filter(None, (PLACE.match(line.strip()) for line in lines)):
        folder = os.path.normpath(os.path.join(os.path.dirname(path), (place.group(2) or "").lstrip("/")))
        word = re.compile(r"\$\{?" + place.group(1) + r"\}?/([\w./-]+)")
        found |= {os.path.normpath(f"{folder}/{after}") for line in lines for after in word.findall(line)}
    return {name for name in found if not name.startswith("..")}


def script_references(path, text):
    """The scripts a shell script names on its lines that are not comments."""
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    return {name for line in lines for name in SCRIPT_WORD.findall(line)} | placed_references(path, lines)


def reached(kind, left_out, read=source_of):
    """Every repository file the kind's code reaches from its entries; a file left out is reached
    and not followed, since what it names it runs, if it runs at all, outside the kind's run. read
    gives a file's text, the checkout's unless a test says otherwise."""
    seen, todo = set(), list(ENTRIES[kind])
    while todo:
        name = todo.pop()
        if name in seen or not (ROOT / name).is_file():
            continue
        seen.add(name)
        if name not in left_out:
            text = read(name)
            todo.extend(python_references(name, text) if name.endswith(".py") else script_references(name, text))
    return seen


def git(folder, *words):
    environ = {**os.environ, **QUIET_GIT, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.org"}
    return subprocess.run(["git", "-C", str(folder), *words], capture_output=True, text=True, check=True, env=environ).stdout


class ListsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = load_run_code()

    def test_every_file_a_kind_reaches_is_in_its_digest_or_left_out_with_a_reason(self):
        for kind in self.code.KINDS:
            with self.subTest(kind=kind):
                left_out = self.code.LEFT_OUT[kind]
                found = reached(kind, left_out)
                covered = set(self.code.files(kind))
                self.assertEqual(sorted(found - covered - set(left_out)), [], f"{kind} reaches these, which its digest neither covers nor leaves out")
                self.assertEqual(sorted(set(left_out) - found), [], f"{kind} leaves these out, which its code no longer reaches")
                self.assertEqual(sorted(set(left_out) & covered), [], f"{kind} both covers and leaves out these")
                self.assertTrue(all(reason.strip() for reason in left_out.values()))

    def test_every_code_file_a_kind_lists_is_one_its_run_reaches(self):
        for kind, names in self.code.KINDS.items():
            with self.subTest(kind=kind):
                found = reached(kind, self.code.LEFT_OUT[kind])
                listed = [name for name in names if name.endswith(CODE)]
                self.assertEqual(sorted(set(listed) - found), [], f"{kind} lists code its run never reaches")

    def test_each_kind_names_tracked_files_and_folders_that_hold_some(self):
        for kind, names in self.code.KINDS.items():
            with self.subTest(kind=kind):
                covered = self.code.files(kind)
                for folder in (name for name in names if name.endswith("/")):
                    self.assertTrue(any(name.startswith(folder) for name in covered), f"{kind}: {folder} holds no tracked file")

    def test_a_relative_import_reaches_what_the_same_import_written_absolute_does(self):
        # The second review of #252, finding 5: the walk read only absolute imports, so `from . import
        # sources` in a module a kind lists left src/schwingnet/sources.py out of every list unseen
        left_out = self.code.LEFT_OUT["row"]
        for line in ("from . import sources as _sources", "from schwingnet import sources as _sources"):
            with self.subTest(line=line):
                def read(name, line=line):
                    return source_of(name) + (f"\n{line}\n" if name == "src/schwingnet/witness.py" else "")

                found = reached("row", left_out, read)
                self.assertEqual(sorted(found - set(self.code.files("row")) - set(left_out)), ["src/schwingnet/sources.py"])

    def test_a_relative_import_is_read_against_the_package_of_its_file(self):
        def names(line, path):
            return imported_names(ast.parse(line).body[0], path)

        self.assertEqual(names("from .catalog import Item", "src/schwingnet/flow.py"), ["schwingnet.catalog", "schwingnet.catalog.Item"])
        self.assertEqual(names("from . import contracts", "vendor/beethoven-qa/src/beethoven_qa/gate.py"),
                         ["beethoven_qa", "beethoven_qa.contracts"])
        self.assertEqual(names("from . import blocks", "src/schwingnet/__init__.py"), ["schwingnet", "schwingnet.blocks"])
        # above the top package, or in a file of no package, Python refuses the import, which runs nothing
        self.assertEqual(names("from .. import blocks", "src/schwingnet/flow.py"), [])
        self.assertEqual(names("from . import train", "tools/flow.py"), [])

    def test_the_gates_pydrv_is_where_the_bank_and_catalog_steps_run_their_tools(self):
        # The second review of #252, finding 4: every tool call of a bank or catalog step on the grid
        # runs through the PYDRV grid/gate.sh exports, which execs grid/box.sh
        self.assertEqual(PYDRV, ("grid/bin/train-cpu-python",))
        for kind in ("bank", "catalog"):
            with self.subTest(kind=kind):
                found = reached(kind, self.code.LEFT_OUT[kind])
                self.assertLessEqual({"grid/bin/train-cpu-python", "grid/box.sh"}, found & set(self.code.files(kind)))

    def test_a_state_holds_the_rows_it_starts_and_a_sweep_its_state(self):
        kinds = self.code.KINDS
        self.assertLessEqual(set(kinds["row"]), set(kinds["state"]))
        self.assertLessEqual(set(kinds["state"]), set(kinds["sweep"]))

    def test_the_version_1_flow_holds_the_run_it_starts(self):
        """A change to anything tools/flow.py runs names a new v1 flow run, as it names a new run."""
        self.assertLessEqual(set(self.code.KINDS["row"]), set(self.code.KINDS["v1"]))

    def test_the_command_line_prints_the_digest_and_the_files(self):
        said = subprocess.run([sys.executable, str(ROOT / "tools" / "run_code.py"), "digest", "row"], capture_output=True, text=True, check=False)
        self.assertEqual(said.returncode, 0, said.stderr)
        self.assertRegex(said.stdout, r"^[0-9a-f]{64}\n$")
        self.assertEqual(said.stdout.strip(), self.code.digest("row"))
        listed = subprocess.run([sys.executable, str(ROOT / "tools" / "run_code.py"), "files", "sweep"], capture_output=True, text=True, check=False)
        self.assertIn("flows/sweep.py", listed.stdout.splitlines())
        refused = subprocess.run([sys.executable, str(ROOT / "tools" / "run_code.py"), "digest", "nothing"], capture_output=True, text=True, check=False)
        self.assertEqual(refused.returncode, 2)


class DigestTest(unittest.TestCase):
    """A scratch repository holding a stand-in for every file the kinds name."""

    @classmethod
    def setUpClass(cls):
        cls.code = load_run_code()

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo, True)
        git(self.repo, "init", "-q")
        names = {name for names in self.code.KINDS.values() for name in names}
        for name in sorted(names):
            self.write(f"{name}one.json" if name.endswith("/") else name, f"{name}\n")
        self.write("docs/notes.md", "a note\n")
        self.commit("the code")

    def write(self, name, text):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", message)

    def test_a_merge_that_changes_none_of_a_kinds_files_keeps_its_digest(self):
        before = {kind: self.code.digest(kind, self.repo) for kind in self.code.KINDS}
        self.write("docs/notes.md", "another note\n")
        self.write("tools/textbook_site.py", "print('a page')\n")
        self.commit("docs and a tool no run runs")
        self.assertEqual({kind: self.code.digest(kind, self.repo) for kind in self.code.KINDS}, before)

    def test_a_change_to_any_file_a_kind_covers_names_another_run(self):
        row, sweep, bank = (self.code.digest(kind, self.repo) for kind in ("row", "sweep", "bank"))
        self.write("tools/train.py", "the trainer, changed\n")
        self.commit("the trainer")
        self.assertNotEqual(self.code.digest("row", self.repo), row)
        self.assertNotEqual(self.code.digest("sweep", self.repo), sweep)
        self.assertEqual(self.code.digest("bank", self.repo), bank, "no bank runs the trainer")

    def test_a_folder_counts_its_tracked_files_and_never_an_untracked_one(self):
        bank = self.code.digest("bank", self.repo)
        self.write("data/registry/stray.json", "not added\n")
        self.assertEqual(self.code.digest("bank", self.repo), bank)
        self.commit("a new registry entry")
        self.assertNotEqual(self.code.digest("bank", self.repo), bank)
        self.assertIn("data/registry/stray.json", self.code.files("bank", self.repo))

    def test_the_kinds_name_differs_so_two_kinds_of_one_list_name_two_digests(self):
        self.assertNotEqual(self.code.digest("row", self.repo), self.code.digest("state", self.repo))

    def test_a_file_a_kind_names_that_is_not_tracked_is_refused_in_words(self):
        git(self.repo, "rm", "-q", "tools/train.py")
        self.commit("the trainer gone")
        with self.assertRaisesRegex(self.code.RunCodeError, r"row: tools/train\.py not tracked"):
            self.code.digest("row", self.repo)
        with self.assertRaisesRegex(self.code.RunCodeError, r"no kind 'trainer'"):
            self.code.files("trainer", self.repo)


if __name__ == "__main__":
    unittest.main()
