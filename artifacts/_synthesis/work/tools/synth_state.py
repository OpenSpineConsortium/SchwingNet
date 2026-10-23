"""What the synthesis was read from, and what has changed in it since.

Each record of the synthesis was read from a text: an inventory record from one artifact's
folder, a verdict from the two artifacts its quotes come from. work/out/state.json keeps the
git tree of each artifact folder as its inventory record read it, the hash of each dataset
record under data/sources/, the quotes of the inventory and of the verdicts that the texts
did not hold when it was stamped, and the concept checks it had seen. From today's checkouts
a run then names by script what is new, changed or gone, which lines of a changed artifact's
text changed, and which quotes today's texts no longer hold, so that only what a change
touched is read again. A git tree names a folder's every file by content, so a folder whose
tree is the same has not changed by one byte, whatever its commit dates say.
"""
import difflib
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import extract  # noqa: E402
import verify_quotes as vq  # noqa: E402
from check_verdict_quotes import rows_of  # noqa: E402

REPOS = ("SchwingNet", "symphony-template")
FINE = ("own", "empty")
# A changed artifact's reader is given its changed lines when they are few enough to read
# beside the old record; past these it reads the whole new text against the old record.
MAX_HUNKS = 60
MAX_HUNK_LINES = 200


def git(clone, *args, binary=False):
    done = subprocess.run(["git", "-C", str(clone), *args], check=True, capture_output=True, text=not binary)
    return done.stdout


def folder_trees(clone, repo, ref="HEAD"):
    """Each artifact folder's git tree at ref, keyed repo/folder. A folder whose name starts
    with an underscore holds no artifact: artifacts/_synthesis/ is this record itself."""
    out = {}
    for entry in git(clone, "ls-tree", "-z", f"{ref}:artifacts").split("\0"):
        if not entry:
            continue
        meta, name = entry.split("\t", 1)
        _mode, kind, sha = meta.split()
        if kind == "tree" and not name.startswith("_"):
            out[f"{repo}/{name}"] = sha
    return out


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dataset_hashes(root):
    """Each record under data/sources/ by its id, with the hash of its bytes."""
    src = Path(root) / "data" / "sources"
    return {p.stem: file_hash(p) for p in sorted(src.glob("*.json"))}


def text_at(clone, tree, folder):
    """The plain text extract.py gives of an artifact folder as it stood at a git tree, so a
    changed artifact's old text is rebuilt from history and never has to be kept."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / folder
        root.mkdir()
        archive = git(clone, "archive", "--format=tar", tree, binary=True)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(root, filter="data")
        out = Path(tmp) / "text.txt"
        extract.extract_folder(root, out)
        return out.read_text(encoding="utf-8")


def changed_lines(old, new):
    """The hunks that turn the old text into the new one, each with where it starts in the new
    text, the lines it removes and the lines it adds; None when there are too many to read
    beside the old record, so the reader takes the new text whole."""
    a, b = old.splitlines(), new.splitlines()
    hunks = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if i2 - i1 > MAX_HUNK_LINES or j2 - j1 > MAX_HUNK_LINES:
            return None
        hunks.append({"at": j1 + 1, "removed": a[i1:i2], "added": b[j1:j2]})
    return hunks if len(hunks) <= MAX_HUNKS else None


def quote_id(quote):
    return hashlib.sha1(vq.norm(quote).encode("utf-8")).hexdigest()[:16]


def inventory_quotes(record):
    """The words an inventory record says its artifact holds: each number's quote and each
    key claim's evidence."""
    return [n["quote"] for n in record.get("numbers", []) if (n.get("quote") or "").strip()] + \
           [c["evidence_in_artifact"] for c in record.get("key_claims", []) if (c.get("evidence_in_artifact") or "").strip()]


def absent_inventory_quotes(inventory, text_dir):
    """For each inventoried artifact, the quotes of its record today's text and files do not
    hold, as {id: {quote_id: quote}}."""
    out = {}
    for r in inventory["artifacts"]:
        aid = f"{r['repo']}/{r['folder']}"
        text = vq.text_of(text_dir, aid)
        raw = vq.raw_of(aid)
        gone = {quote_id(q): q for q in inventory_quotes(r) if vq.found(q, text, raw) not in vq.HIT}
        if gone:
            out[aid] = gone
    return out


def verdict_places(M, N, text_dir):
    """Where each verdict's two quotes are found today, keyed stratum|index as the pages count
    rows; own and empty are where they should be, anything else is for a person to read."""
    places = {}
    for stratum, i, a, b, v in rows_of(M, N):
        places[f"{stratum}|{i}"] = [vq.place(text_dir, v.get("quote_a"), a, b), vq.place(text_dir, v.get("quote_b"), b, a)]
    return places


def odd_places(places):
    return {k: p for k, p in places.items() if set(p) - set(FINE)}


def load(path):
    if not os.path.exists(path):
        return {"artifacts": {}, "datasets": {}, "inventory_absent": {}, "verdict_places": {}, "checks": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write(path, state):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, sort_keys=True, ensure_ascii=True)
        f.write("\n")


def delta(state, trees, datasets):
    """What is new, changed or gone among the artifact folders and the dataset records since
    the state was stamped."""
    was, had = state.get("artifacts", {}), state.get("datasets", {})
    return {
        "new": sorted(set(trees) - set(was)),
        "changed": sorted(a for a in trees if a in was and trees[a] != was[a]),
        "gone": sorted(set(was) - set(trees)),
        "datasets_new": sorted(set(datasets) - set(had)),
        "datasets_changed": sorted(d for d in datasets if d in had and datasets[d] != had[d]),
        "datasets_gone": sorted(set(had) - set(datasets)),
    }


def stale_verdicts(state, places):
    """Verdicts whose quotes are found somewhere other than they were at the stamp: newly
    lost (stale, to be read again) or newly found (resolved), each with both readings."""
    was = state.get("verdict_places", {})
    stale, resolved = [], []
    for key, now in sorted(places.items()):
        before = was.get(key, ["own", "own"])
        worse = [p for p, q in zip(now, before) if p not in FINE and p != q]
        if worse:
            stale.append({"row": key, "was": before, "now": now})
        elif key in was and not set(now) - set(FINE):
            resolved.append({"row": key, "was": before, "now": now})
    return stale, resolved


def newly_absent(state, absent):
    """Inventory quotes today's texts lose that the stamp's texts held, by artifact. The
    state keeps only the quotes' ids; their words are in inventory.json."""
    was = state.get("inventory_absent", {})
    out = {}
    for aid, quotes in absent.items():
        new = {k: q for k, q in quotes.items() if k not in set(was.get(aid, []))}
        if new:
            out[aid] = new
    return out


def absent_ids(absent):
    return {aid: sorted(quotes) for aid, quotes in absent.items()}
