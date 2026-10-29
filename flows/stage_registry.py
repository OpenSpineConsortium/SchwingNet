"""Which flows flows/launch.py starts, and the frozen PREREG each deep learning flow is held to.

Usage:
    python3 flows/stage_registry.py check        # every line of flows/registry.txt holds together
    python3 flows/stage_registry.py prereg KIND  # the kind's PREREG and its sha256, or why it is not frozen
    python3 flows/stage_registry.py frozen [--base REV]  # no frozen PREREG moved since REV (origin/main)

The owner's rule of 2026-10-29: every deep learning job on the grid runs on the block-based
Metaflow pipeline, started only by flows/launch.py, under a PREREG.md frozen before the run, with
the CLAIM 2024 and REFORMS report enforced and a progress page in the browser. flows/registry.txt
is the one list of the flows: each kind's class, the word the launcher ends with, the job script
under grid/ that starts it when Slurm runs it, and its PREREG, or "-" for a stage that trains and
runs no network, which only bank and catalog are (NO_NETWORK). The launcher refuses a deep kind
whose PREREG is missing or no longer the one frozen before any flow starts, so the job ends having
done nothing, and the flow's start step holds the run to it again, in the checkout the steps run
from.

A PREREG may cover only some of the runs of its kind: its line `Covers: <part>, <part>` names them,
and a flow whose runs differ in design, as the sweep's plans do, names the part a run is and the
sha256 of the part's bytes (its module's prereg_part, read by the launcher from the run's words,
and its start's own words), so a run of a part no frozen PREREG covers is refused like a PREREG
that moved. A part named alone is covered by its name; an entry `<part>=<sha256>` covers the part
only while its bytes are those the freeze saw, since a part's name says nothing of what it holds:
a plan edited or made again since the freeze is another design. The sweep's PREREG covers the
three smoke plans by their bytes; the six trials are another design and wait for a PREREG of
their own.

A PREREG is frozen as the Lab Recipe says ("Pre-register and freeze",
artifacts/the-lab-recipe-1t2gvp/index.md): `sha256sum PREREG.md > PREREG.md.sha256` in its folder,
both committed, never edited again; a departure goes in DEVIATIONS.md beside it, and a second design
is a new file with its own freeze. A PREREG that moved stops the job with exit 90, as the recipe's
first line of every producing job does. Standard library only, so the launcher reads it before
Metaflow is imported and the required check runs it with the runner's python.

The freeze is held by git too, since a PREREG.md edited and its PREREG.md.sha256 written again in
one change pass every check above: `frozen` fails where any PREREG.md or PREREG.md.sha256 under
docs/research/ that the base holds differs at HEAD, removed or changed, and where a DEVIATIONS.md
beside a PREREG frozen at the base does not begin with its text there, since departures are only
ever added below the last. A PREREG new since the base is free to change until it lands. The base
is where HEAD left REV, their merge base, where git can tell, so a branch behind REV is not blamed
for what REV added since; in a clone one commit deep, as CI's checkout of a pull request's merge
commit is, git cannot, and REV itself is the base. With no --base it is origin/main; where that is
missing, under GitHub Actions it is fetched one commit deep, as tools/crowd_check.py fetches a
base, and elsewhere the check says it was skipped, so a clone of one's own is never made shallow.
"""

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = Path("flows") / "registry.txt"
NO_PREREG = "-"
KIND = re.compile(r"[a-z][a-z0-9_]{0,39}")
CLASS = re.compile(r"[A-Z][A-Za-z0-9]{0,63}Flow")
WORD = re.compile(r"[A-Z][A-Z0-9_]{0,39}_RC")
SCRIPT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\.(?:sbatch|sh)")
HASH_LINE = re.compile(r"([0-9a-f]{64}) [ *]PREREG\.md\n?")
# A PREREG's path as the registry names it: relative to the checkout, each folder a plain name, so
# none is absolute, none climbs out with .. and none hides behind a dot.
PREREG_PATH = re.compile(r"(?:[A-Za-z0-9_][A-Za-z0-9._-]{0,63}/){1,8}PREREG\.md")
# The kinds that may name no PREREG: the stages that train and run no network, bank (each raw copy
# into a bank and a shard) and catalog (the versioned catalog and its split check), which decide
# nothing a design could be frozen for. Every other kind is held to a frozen PREREG, so a kind
# added with "-" is refused rather than run with none.
NO_NETWORK = ("bank", "catalog")
COVERS = re.compile(r"^Covers: (.+)$", re.M)
COVERED = re.compile(r"(?P<part>[A-Za-z0-9_.-]{1,64})(?:=(?P<sha256>[0-9a-f]{64}))?")
# Where the launcher stops a job whose PREREG is not the one frozen: the Lab Recipe's exit code.
EX_PREREG = 90


class RegistryError(Exception):
    """A line of the registry that does not hold together, or a kind it does not list."""


class PreregError(Exception):
    """A deep learning flow whose PREREG is missing or no longer the one frozen."""


def lines_of(repo=ROOT):
    """The registry's lines that name a flow, each as its five words and its line number."""
    path = Path(repo) / REGISTRY
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise RegistryError(f"{path}: cannot be read ({error})") from error
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if line.strip() and not line.startswith("#"):
            found.append((number, line.split()))
    return found


def entry_of(number, words):
    """One line's five words as a dict, each checked for its shape."""
    if len(words) != 5:
        raise RegistryError(f"{REGISTRY}:{number}: five words, kind class word script PREREG, not {len(words)}")
    kind, flow_class, word, script, prereg = words
    for value, shape, what in ((kind, KIND, "kind"), (flow_class, CLASS, "class"), (word, WORD, "word"), (script, SCRIPT, "script")):
        if not shape.fullmatch(value):
            raise RegistryError(f"{REGISTRY}:{number}: {value!r} is no {what} ({shape.pattern})")
    if prereg != NO_PREREG and not PREREG_PATH.fullmatch(prereg):
        raise RegistryError(f"{REGISTRY}:{number}: the PREREG is a relative path to a PREREG.md inside the checkout, "
                            f"with no . or .. folder, or -, not {prereg!r}")
    return {"kind": kind, "class": flow_class, "word": word, "script": script, "prereg": None if prereg == NO_PREREG else prereg}


def entries(repo=ROOT):
    """Every flow the registry lists, by kind, in its order; two lines of one kind or one script are refused."""
    found = {}
    for number, words in lines_of(repo):
        entry = entry_of(number, words)
        if entry["kind"] in found:
            raise RegistryError(f"{REGISTRY}:{number}: the kind {entry['kind']} is listed twice")
        if any(other["script"] == entry["script"] for other in found.values()):
            raise RegistryError(f"{REGISTRY}:{number}: the script {entry['script']} is listed twice")
        found[entry["kind"]] = entry
    return found


def entry(kind, repo=ROOT):
    listed = entries(repo)
    if kind not in listed:
        raise RegistryError(f"no flow {kind!r} in {REGISTRY}; the flows are {', '.join(listed)}")
    return listed[kind]


def frozen_hash(prereg_path):
    """The sha256 PREREG.md.sha256 records, or a PreregError saying why there is none."""
    record = prereg_path.with_name("PREREG.md.sha256")
    try:
        text = record.read_text(encoding="ascii")
    except (OSError, UnicodeDecodeError) as error:
        raise PreregError(f"{record.name} is not beside {prereg_path}, so the PREREG was never frozen ({error})") from error
    match = HASH_LINE.fullmatch(text)
    if not match:
        raise PreregError(f"{record} is not one line of `sha256sum PREREG.md`, so the PREREG's freeze cannot be read")
    return match.group(1)


def frozen_prereg(kind, repo=ROOT):
    """The kind's PREREG, (path under the checkout, sha256), once its bytes are the ones frozen; None
    for a stage that trains and runs no network; a PreregError where it is missing or moved."""
    prereg = entry(kind, repo)["prereg"]
    if prereg is None and kind in NO_NETWORK:
        return None
    if prereg is None:
        raise PreregError(f"the {kind} flow names no PREREG, which only {' and '.join(NO_NETWORK)}, the stages that train and "
                          f"run no network, may do; a PREREG frozen before its runs is its first file")
    path = Path(repo) / prereg
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise PreregError(f"the {kind} flow's PREREG {prereg} cannot be read ({error})") from error
    frozen = frozen_hash(path)
    if digest != frozen:
        raise PreregError(f"STOP: {prereg} changed since the freeze (sha256 {digest[:16]}, frozen {frozen[:16]}); "
                          f"a departure goes in DEVIATIONS.md beside it and a new design is a new file with its own freeze")
    return prereg, digest


def covered(path):
    """The parts a PREREG's first `Covers:` line names, in its order, each as (part, the sha256 its
    bytes are held to, or None where the entry names the part alone); none where it has no such
    line, and a PreregError for an entry of another shape, which covers nothing."""
    found = COVERS.search(Path(path).read_text(encoding="utf-8"))
    parts = []
    for word in re.split(r"[,\s]+", found.group(1)) if found else []:
        entry = COVERED.fullmatch(word) if word else None
        if word and entry is None:
            raise PreregError(f"{Path(path).name}'s Covers line holds {word!r}, which is neither a part nor <part>=<sha256>")
        if entry:
            parts.append((entry["part"], entry["sha256"]))
    return parts


def frozen_for(kind, part=None, part_sha256=None, repo=ROOT):
    """frozen_prereg, and where the run is one part of its kind, a PreregError unless the frozen
    PREREG names that part on its Covers line and, where its entry names the part's sha256, the
    part's bytes (part_sha256, None where they were not read) are those."""
    frozen = frozen_prereg(kind, repo)
    if frozen is None or part is None:
        return frozen
    parts = covered(Path(repo) / frozen[0])
    held = dict(parts)
    if part not in held:
        raise PreregError(f"{frozen[0]} covers {', '.join(name for name, _ in parts) or 'no part it names'}, "
                          f"not {part or 'a part with no name'}: a run of it waits for a PREREG of its own, frozen before it runs")
    if held[part] is not None and part_sha256 != held[part]:
        bytes_now = f"its bytes now have sha256 {part_sha256[:16]}" if part_sha256 else "its bytes were not read"
        raise PreregError(f"{frozen[0]} covers {part} as the bytes of sha256 {held[part][:16]}, and {bytes_now}: a {part} "
                          f"changed since the freeze is another design, which waits for a PREREG of its own")
    return frozen


def script_starts(repo, script, kind):
    """Whether the job script names the launcher with this kind, as each stage script does."""
    try:
        text = (Path(repo) / "grid" / script).read_text(encoding="utf-8")
    except OSError:
        return False
    return re.search(rf'flows/launch\.py"?\s+{re.escape(kind)}(?![a-z0-9_])', text) is not None


def flow_text(repo, kind):
    """The flow's own file, or "" where there is none."""
    flow = Path(repo) / "flows" / f"{kind}.py"
    return flow.read_text(encoding="utf-8") if flow.is_file() else ""


def prereg_problems(repo, kind, prereg, flow):
    """What keeps a kind's PREREG from holding: a path that leads out of the checkout, a freeze that
    does not hold, a Covers line of another shape, or one the flow names no part for."""
    if prereg is not None and not (Path(repo) / prereg).resolve().is_relative_to(Path(repo).resolve()):
        return [f"{kind}: {prereg} leads out of the checkout"]
    try:
        frozen = frozen_prereg(kind, repo)
        parts = covered(Path(repo) / frozen[0]) if frozen else []
    except PreregError as error:
        return [f"{kind}: {error}"]
    if parts and "def prereg_part(" not in flow:
        return [f"{kind}: {prereg} names the parts it covers, but flows/{kind}.py defines no prereg_part, so no run "
                f"would say which part it is and every run would pass as covered"]
    return []


def problems(repo=ROOT):
    """What keeps the registry from holding together, one line each; none where it does."""
    try:
        listed = entries(repo)
    except RegistryError as error:
        return [str(error)]
    found = []
    for kind, item in listed.items():
        flow = flow_text(repo, kind)
        if f"class {item['class']}(" not in flow:
            found.append(f"{kind}: flows/{kind}.py defines no class {item['class']}")
        if not script_starts(repo, item["script"], kind):
            found.append(f"{kind}: grid/{item['script']} names no flows/launch.py {kind}")
        found += prereg_problems(repo, kind, item["prereg"], flow)
    return found


# --- the freeze, held by git -----------------------------------------------------------------------

RESEARCH = "docs/research"
FROZEN_FILES = ("PREREG.md", "PREREG.md.sha256")
GROWS_ONLY = "DEVIATIONS.md"
DEFAULT_BASE = "origin/main"


def git(repo, *words, text=True):
    return subprocess.run(["git", "-C", str(repo), *words], capture_output=True, text=text)


def has_commit(repo, revision):
    return git(repo, "rev-parse", "-q", "--verify", f"{revision}^{{commit}}").returncode == 0


def base_of(repo, base=None, environ=None):
    """The revision HEAD is held to: the one given, which must be there; else origin/main, fetched
    one commit deep under GitHub Actions where the checkout lacks it; else None, where nothing is
    fetched and the check is skipped."""
    environ = os.environ if environ is None else environ
    if base is not None:
        if not has_commit(repo, base):
            raise RegistryError(f"no commit {base} in {repo} to hold the frozen PREREGs to")
        return base
    if has_commit(repo, DEFAULT_BASE):
        return DEFAULT_BASE
    if environ.get("GITHUB_ACTIONS") != "true":
        return None
    done = git(repo, "fetch", "--no-tags", "--quiet", "--depth=1", "origin", "main")
    if done.returncode != 0:
        raise RegistryError(f"could not fetch main from origin to hold the frozen PREREGs to ({done.stderr.strip()[:200]}); run the check again")
    return git(repo, "rev-parse", "FETCH_HEAD").stdout.strip()


def merge_base(repo, base):
    """Where HEAD left the base, or the base itself where git cannot tell, as in a clone one commit deep."""
    done = git(repo, "merge-base", base, "HEAD")
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else base


def research_blobs(repo, revision):
    """The PREREG.md, PREREG.md.sha256 and DEVIATIONS.md files under docs/research at a revision,
    each path with its blob."""
    done = git(repo, "ls-tree", "-r", "-z", revision, "--", RESEARCH)
    if done.returncode != 0:
        raise RegistryError(f"git could not list {RESEARCH} at {revision}: {done.stderr.strip()[:200]}")
    blobs = {}
    for record in filter(None, done.stdout.split("\0")):
        head, path = record.split("\t", 1)
        if Path(path).name in (*FROZEN_FILES, GROWS_ONLY):
            blobs[path] = head.split()[2]
    return blobs


def blob_bytes(repo, blob):
    return git(repo, "cat-file", "blob", blob, text=False).stdout


def frozen_at(blobs, folder):
    """Whether a folder held a frozen PREREG: its PREREG.md and the PREREG.md.sha256 beside it."""
    return all(f"{folder}/{name}" in blobs for name in FROZEN_FILES)


def frozen_problems(repo, base):
    """What HEAD changed of what the base froze, one line each: a PREREG.md or PREREG.md.sha256 the
    base holds that HEAD removed or changed, and a DEVIATIONS.md beside a PREREG frozen at the base
    that HEAD removed or that no longer begins with its text there."""
    at_base, at_head = research_blobs(repo, base), research_blobs(repo, "HEAD")
    found = []
    for path, blob in sorted(at_base.items()):
        now = at_head.get(path)
        if now == blob:
            continue
        name, folder = Path(path).name, str(Path(path).parent)
        if name in FROZEN_FILES:
            found.append(f"{path} {'is gone' if now is None else 'changed'} since {base}: a frozen PREREG is never "
                         f"edited; a departure goes in {GROWS_ONLY} beside it and a new design is a new file with its own freeze")
        elif frozen_at(at_base, folder) and (now is None or not blob_bytes(repo, now).startswith(blob_bytes(repo, blob))):
            found.append(f"{path} {'is gone' if now is None else 'no longer begins with its text'} at {base}: it only "
                         f"grows, each departure dated and added below the last")
    return found


def frozen_check(base=None, repo=ROOT, environ=None):
    """The command `frozen`: 0 where no frozen PREREG moved since the base or the check was skipped, 1 otherwise."""
    try:
        given = base_of(repo, base, environ)
        if given is None:
            print(f"registry: no {DEFAULT_BASE} here and not under GitHub Actions, so whether a frozen PREREG moved was not "
                  f"checked; CI checks it, or name a base with --base")
            return 0
        held = merge_base(repo, given)
        found = frozen_problems(repo, held)
    except RegistryError as error:
        print(f"registry: {error}", file=sys.stderr)
        return 1
    for line in found:
        print(f"registry: {line}", file=sys.stderr)
    if not found:
        print(f"registry: every PREREG frozen where HEAD left {given} ({held[:12]}) is as it was, and every {GROWS_ONLY} "
              f"beside one only grew")
    return 1 if found else 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["frozen"]:
        return frozen_check()
    if len(argv) == 3 and argv[:2] == ["frozen", "--base"]:
        return frozen_check(argv[2])
    if argv == ["check"]:
        found = problems()
        for line in found:
            print(f"registry: {line}", file=sys.stderr)
        if not found:
            print(f"registry: {len(entries())} flows, each with its class, its job script and, where it trains or runs a network, its frozen PREREG")
        return 1 if found else 0
    if len(argv) == 2 and argv[0] == "prereg":
        try:
            frozen = frozen_prereg(argv[1])
        except (RegistryError, PreregError) as error:
            print(f"registry: {error}", file=sys.stderr)
            return EX_PREREG if isinstance(error, PreregError) else 64
        print(f"{frozen[0]} {frozen[1]}" if frozen else "-")
        return 0
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main())
