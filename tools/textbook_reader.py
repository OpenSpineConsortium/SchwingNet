"""The textbook on claude.ai as a reader over the Claude project's files (issue #294): the pack of
the built edition and its copy into the project's files, which the reader page,
tools/textbook_reader.html, reads when it is opened.

A claude.ai artifact is published with the Artifact tool, and the tool publishes a file Claude
did not write only once Claude has read the whole of it; no permission or setting turns that off.
The edition tools/textbook_artifact.py builds is about 450 files and 109 MB, some 50 MB of it text,
more than a session can read, so on 2026-10-25 the session on the owner's computer published
nothing, as it should (docs/research/textbook-as-an-artifact.md). The owner chose that day that
the book reaches claude.ai through a reader instead: one small page that Claude reads in full and
the owner publishes once from the owner's computer (tools/textbook_publish.py local), and that,
when it is opened, reads the book from the files of the Claude project the textbook thread belongs
to, with the viewer's own access, through the artifact runtime's files capability. Nothing of the
book is in the page or in the artifact, and a viewer who cannot open the project's files reads
nothing. On 2026-10-26 the owner replaced the reader at its link with the front door,
tools/front_door.html, which reads the repository itself through the viewer's GitHub connector, so
the publish command publishes the door and this stage is run by nothing after a merge; the reader
and the stage stay as the record of #294 (docs/research/textbook-as-an-artifact.md).

GitHub cannot write to a Claude project's files, so a thread of the project puts the book there:

    python3 tools/textbook_reader.py stage [--clone .] [--root /mnt/project-files] [--sha SHA] [--anyway]

builds the site and the edition from main's commit with that commit's own builders, as the publish
did, packs the edition, and copies the pack into textbook/ of the project's files, the pointer
CURRENT.json written last, so a reader never finds an edition half copied, and the edition before
it kept, so a reader open on it keeps working until it is reloaded. A stage whose book inputs are
the ones already staged copies nothing.

The pack of an edition is two files: book-<commit>.bin, every file of the edition one after
another, the text gzipped where that is smaller, and book-<commit>.json, its index, which says
where each file starts, how many bytes it takes there and how many it has unpacked, its type and
its sha256. The files go in the order of their paths, so a chapter's figures (figures/<chapter>/)
and an exported artifact's files (artifacts/<folder>/) sit together and the reader takes what a
page needs in few reads.

    python3 tools/textbook_reader.py pack EDITION OUT --sha SHA --built DATE [--inputs FINGERPRINT]
"""

import argparse
import datetime as dt
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_NAME = "OpenSpineConsortium/SchwingNet"
# The pack's layout, which the reader page checks before it reads anything: a pack of another
# format is refused by name, so a reader and a copy of different ages never misread each other.
FORMAT = "textbook-reader/1"
FOLDER = "textbook"
POINTER = "CURRENT.json"
NOTE = "README.txt"
FILES_ROOT = "/mnt/project-files"
# What the book is built from. The site reads the chapters and figures, the synthesis's records and
# the exported artifacts under artifacts/, its own code and the stylesheet, and CODEOWNERS for the
# login its privacy pass hides. Its code is every module of tools/ the builders import, the claims
# register's queue and the book's search among them, and the search's package, which tools/rag.py
# loads by path; a test follows the builders' imports and fails on one this list leaves out, since a
# change to it alone would otherwise stage nothing new (issue #269). This module is listed too, since
# the pack is its own.
INPUTS = ["docs/textbook", "artifacts", "tools/textbook_site.py", "tools/textbook_artifact.py",
          "tools/living_docs.py", ".github/CODEOWNERS", "tools/claims_rank.py", "tools/rag.py",
          "src/schwingnet/rag.py", "tools/textbook_reader.py"]
# The builder's summaries, which are no files of the book.
NOT_BOOK = {"batches.json", "plan.json"}
TEXT = {".html", ".htm", ".js", ".mjs", ".json", ".css", ".svg", ".md", ".txt", ".csv", ".xml"}
TYPES = {".html": "text/html", ".htm": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
         ".json": "application/json", ".css": "text/css", ".svg": "image/svg+xml", ".md": "text/markdown",
         ".txt": "text/plain", ".csv": "text/csv", ".xml": "application/xml", ".png": "image/png",
         ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
         ".ico": "image/x-icon", ".woff": "font/woff", ".woff2": "font/woff2", ".pdf": "application/pdf",
         ".mp4": "video/mp4", ".webm": "video/webm"}
# An edition another stage wrote within this long is never pruned, since that stage may be about to
# point CURRENT.json at it.
FRESH_SECONDS = 3600
WAIT_SECONDS = 10    # the project's files are a network mount; a file is read back this long after it is written

NOTE_TEXT = """This folder holds the SchwingNet textbook for its reader on claude.ai.

The reader is a private claude.ai artifact (tools/textbook_reader.html in the repository
OpenSpineConsortium/SchwingNet) that reads the book from here when it is opened, with the
opener's own access to this project's files. CURRENT.json names the edition it shows;
book-<commit>.bin holds that edition's files and book-<commit>.json says where each one is.
A thread of this project writes them with `python3 tools/textbook_reader.py stage` after the book
changes on main. Nothing here is edited by hand: the repository is the source.

Confidential: nothing here may be copied to a public place.
"""


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_out(where, *args):
    """git's output in a repository, stripped, or a stop that quotes git's own words."""
    done = subprocess.run(["git", "-C", str(where), *args], capture_output=True)
    if done.returncode != 0:
        words = (done.stderr or done.stdout).decode("utf-8", "replace").strip()
        raise SystemExit(f"git {args[0]} failed: {words}")
    return done.stdout.decode("utf-8", "replace").strip()


def media_type(path):
    return TYPES.get(Path(path).suffix.lower(), "application/octet-stream")


def book_files(edition):
    """Every file of the edition by its path inside the folder, in the order of the paths."""
    edition = Path(edition)
    found = [p for p in edition.rglob("*") if p.is_file() and p.relative_to(edition).as_posix() not in NOT_BOOK]
    return sorted((p.relative_to(edition).as_posix(), p) for p in found)


def stored(rel, data):
    """The bytes a file takes in the pack, gzipped where it is text and that is smaller, with no
    clock in the header, so one edition packs to the same bytes twice."""
    if Path(rel).suffix.lower() in TEXT:
        packed = gzip.compress(data, compresslevel=9, mtime=0)
        if len(packed) < len(data):
            return packed, True
    return data, False


def pack(edition, out, repo, sha, built, inputs=""):
    """book.bin and book.json in out, from the edition folder, and the index."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files, at = {}, 0
    with open(out / "book.bin", "wb") as data:
        for rel, path in book_files(edition):
            raw = path.read_bytes()
            body, gz = stored(rel, raw)
            data.write(body)
            files[rel] = {"at": at, "n": len(body), "size": len(raw), "gz": gz, "type": media_type(rel),
                          "sha256": hashlib.sha256(raw).hexdigest()}
            at += len(body)
    if "index.html" not in files:
        raise SystemExit(f"{edition}: no index.html; not an edition tools/textbook_artifact.py built")
    index = {"format": FORMAT, "repo": repo, "sha": sha, "built": built, "inputs": inputs, "start": "index.html",
             "bytes": at, "files": files}
    (out / "book.json").write_text(json.dumps(index, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    return index


def unpacked(index, data, rel):
    """One file's bytes out of a pack, as the reader takes them: its span of the data, gunzipped
    where the index says it was gzipped."""
    entry = index["files"][rel]
    body = data[entry["at"]:entry["at"] + entry["n"]]
    return gzip.decompress(body) if entry["gz"] else body


# The copy into the project's files

def inputs_fingerprint(root, sha):
    """The sha256 of git's listing of the book's inputs at a commit, every blob's hash and path:
    two commits that hold the same inputs give the same fingerprint, whatever else they changed,
    and a stage whose fingerprint CURRENT.json already carries has nothing new to copy."""
    listing = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", sha, "--", *INPUTS],
                             capture_output=True, text=True, check=True).stdout
    return hashlib.sha256(listing.encode("utf-8")).hexdigest()


def drop_tree(clone, tree):
    """A build's worktree gone, from the clone's list and from the disk, whatever state it was left in."""
    subprocess.run(["git", "-C", str(clone), "worktree", "remove", "--force", str(tree)], capture_output=True)
    shutil.rmtree(tree, ignore_errors=True)
    subprocess.run(["git", "-C", str(clone), "worktree", "prune"], capture_output=True)


def run_builder(script, *args):
    """A builder run by this interpreter in UTF-8 mode, as CI runs it, whatever the computer's own
    encoding is."""
    done = subprocess.run([sys.executable, "-X", "utf8", str(script), *map(str, args)], stdout=subprocess.DEVNULL)
    if done.returncode != 0:
        raise SystemExit(f"{script.name} failed; nothing was staged")


def build(clone, sha, built, work):
    """The site and the edition from a commit, by that commit's own builders in a worktree of the
    clone made in the work folder; the worktree and the site go again, and the edition stays."""
    work = Path(work)
    tree, site, out = work / "tree", work / "site", work / "edition"
    drop_tree(clone, tree)
    shutil.rmtree(site, ignore_errors=True)
    shutil.rmtree(out, ignore_errors=True)
    git_out(clone, "worktree", "add", "--quiet", "--detach", str(tree), sha)
    try:
        run_builder(tree / "tools" / "textbook_site.py", site, "--repo", REPO_NAME, "--sha", sha, "--root", tree)
        run_builder(tree / "tools" / "textbook_artifact.py", site, out, "--repo", REPO_NAME, "--sha", sha,
                    "--built", built)
    finally:
        drop_tree(clone, tree)
        shutil.rmtree(site, ignore_errors=True)
    return out


def read_pointer(folder):
    """CURRENT.json as the folder holds it, or an empty one where it is not there or not this
    format's."""
    try:
        pointer = json.loads((Path(folder) / POINTER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return pointer if isinstance(pointer, dict) and pointer.get("format") == FORMAT else {}


def whole(folder, pointer):
    """Whether the files a pointer names are there at the sizes it gives."""
    folder = Path(folder)
    try:
        return ((folder / pointer["index"]).stat().st_size == pointer["index_bytes"]
                and (folder / pointer["data"]).stat().st_size == pointer["bytes"])
    except (KeyError, OSError):
        return False


def same_file(source, target):
    return target.is_file() and target.stat().st_size == source.stat().st_size and sha256(target) == sha256(source)


def copy_checked(source, target, wait=WAIT_SECONDS):
    """A file copied into the project's files and read back after a pause, its bytes compared with
    the source's by sha256; a copy that does not read back whole stops the stage before anything
    points at it. A file already there with the same bytes is left alone, so a reader on it reads on."""
    if same_file(source, target):
        return
    shutil.copyfile(source, target)
    time.sleep(wait)
    if not same_file(source, target):
        raise SystemExit(f"{target} did not read back as written; CURRENT.json was left as it was")


def write_checked(target, text, wait=WAIT_SECONDS):
    target.write_text(text, encoding="utf-8")
    time.sleep(wait)
    if target.read_text(encoding="utf-8") != text:
        raise SystemExit(f"{target} did not read back as written")


def prune(folder, keep, now=None):
    """The editions in the folder other than those kept, removed, unless one was written within the
    hour, which another stage may be about to point at."""
    now = time.time() if now is None else now
    gone = []
    for path in sorted(Path(folder).glob("book-*")):
        if path.stem in keep or path.suffix not in (".bin", ".json"):
            continue
        if now - path.stat().st_mtime < FRESH_SECONDS:
            continue
        path.unlink()
        gone.append(path.name)
    return gone


def place(folder, pack_dir, index, staged, wait=WAIT_SECONDS):
    """A pack copied into the book's folder under its edition's name and read back, the pointer
    written after it, the note beside them, and the editions no longer kept removed; the pointer
    and the names removed."""
    folder, pack_dir = Path(folder), Path(pack_dir)
    folder.mkdir(parents=True, exist_ok=True)
    before = read_pointer(folder)
    name = f"book-{index['sha'][:12]}"
    for suffix in (".bin", ".json"):
        copy_checked(pack_dir / f"book{suffix}", folder / f"{name}{suffix}", wait)
    pointer = {"format": FORMAT, "repo": index["repo"], "sha": index["sha"], "built": index["built"],
               "inputs": index["inputs"], "staged": staged, "index": f"{name}.json", "data": f"{name}.bin",
               "index_bytes": (pack_dir / "book.json").stat().st_size, "bytes": index["bytes"],
               "files": len(index["files"])}
    write_checked(folder / POINTER, json.dumps(pointer, indent=1, sort_keys=True) + "\n", wait)
    if not (folder / NOTE).is_file() or (folder / NOTE).read_text(encoding="utf-8") != NOTE_TEXT:
        (folder / NOTE).write_text(NOTE_TEXT, encoding="utf-8")
    keep = {name}
    if before.get("data"):
        keep.add(Path(before["data"]).stem)
    return pointer, prune(folder, keep)


def stage(clone, root=FILES_ROOT, sha="", anyway=False, wait=WAIT_SECONDS, now=None):
    """main's commit, or the one given, built, packed and copied into textbook/ of the project's
    files, the pointer last; what it did, in one line. now, a datetime, stands in for the clock in
    the pointer's staged time."""
    clone, root = Path(clone).resolve(), Path(root)
    if not root.is_dir():
        raise SystemExit(f"no project files at {root}: run this in a thread of the Claude project the reader reads, "
                         "whose files are there")
    if not sha:
        git_out(clone, "fetch", "--quiet", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main")
        sha = git_out(clone, "rev-parse", "refs/remotes/origin/main")
    sha = git_out(clone, "rev-parse", f"{sha}^{{commit}}")
    built = git_out(clone, "show", "-s", "--format=%cI", sha)
    inputs = inputs_fingerprint(clone, sha)
    folder = root / FOLDER
    before = read_pointer(folder)
    if before.get("inputs") == inputs and whole(folder, before) and not anyway:
        return (f"The edition built from {before['sha'][:7]} is already in {folder}, and the book's inputs at "
                f"{sha[:7]} are the same; --anyway copies it again.")
    staged = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with tempfile.TemporaryDirectory(prefix="textbook-reader-") as temp:
        edition = build(clone, sha, built, temp)
        index = pack(edition, Path(temp) / "pack", REPO_NAME, sha, built, inputs)
        pointer, gone = place(folder, Path(temp) / "pack", index, staged, wait)
    return (f"Staged the edition built from {sha[:7]} into {folder}: {pointer['files']} files, "
            f"{pointer['bytes'] / 1e6:.1f} MB packed" + (f"; removed {', '.join(gone)}" if gone else ""))


# the command

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    staging = commands.add_parser("stage", help="build main's book and copy it into the project's files")
    staging.add_argument("--clone", default=str(ROOT), help="the clone to build from, this one by default")
    staging.add_argument("--root", default=FILES_ROOT, help="where the project's files are mounted")
    staging.add_argument("--sha", default="", help="the commit to build, main's head by default")
    staging.add_argument("--anyway", action="store_true", help="copy even where these inputs are already staged")

    packing = commands.add_parser("pack", help="pack an edition folder into book.bin and book.json")
    packing.add_argument("edition", help="the folder tools/textbook_artifact.py wrote")
    packing.add_argument("out", help="the folder to write book.bin and book.json into")
    packing.add_argument("--repo", default=REPO_NAME)
    packing.add_argument("--sha", required=True, help="the commit the edition was built from")
    packing.add_argument("--built", required=True, help="that commit's date, ISO 8601")
    packing.add_argument("--inputs", default="", help="the fingerprint of the book's inputs at that commit")

    args = parser.parse_args(argv)
    if args.command == "pack":
        index = pack(args.edition, args.out, args.repo, args.sha, args.built, args.inputs)
        print(f"{len(index['files'])} files, {index['bytes'] / 1e6:.1f} MB packed")
        return 0
    print(stage(args.clone, args.root, args.sha, args.anyway))
    return 0


if __name__ == "__main__":
    sys.exit(main())
