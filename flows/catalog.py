"""CatalogFlow: stage 3 of the X-ray chain, the catalog's build and split check, under Metaflow.

Started only by flows/launch.py (python flows/launch.py catalog -- --data-root ... --store ...),
which resumes the newest run of the same words, code and shard manifests that did not finish.
grid/03-catalog.sbatch execs that launcher whenever Slurm runs it (issue #252). A resume clones
every step that finished, the build among them where the run was cut in end, so the launcher keys
the run by every manifest the stage would build from, its path, size and sha256 (key_reads,
below): a shard landed, gone or rewritten since names another key, and the job starts a new run
that builds from what is there, while manifests as they were carry the cut run on, its build
cloned (the second review of #252, finding 2).

One working step, since the build lock is held from the listing of the manifests to the marker
(issue #80): the step runs grid/03-catalog.sbatch with SCHWINGNET_FLOW_STEP=1 in the launcher's
working folder, so its lock, its report (logs/03-catalog-STAGE-REPORT.md) and its marker are
where they always were. A kill in the step reruns it whole on resume, which costs under a minute,
and a kill in end clones it under the key above. The stage's own refusal, a build or a split check that failed, is recorded and not raised, and the
end step's verdict carries it from the stage's XR_CATALOG_RC line, so the job's exit means what
it meant before.
"""

import hashlib
import os
import re
import stat
import subprocess
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, current, step
from metaflow.cards import Markdown

REPO = Path(os.environ.get("SCHWINGNET") or Path(__file__).resolve().parent.parent)
STAGE = REPO / "grid" / "03-catalog.sbatch"
REPORT = Path("logs") / "03-catalog-STAGE-REPORT.md"
# The stage's own data root where the words name none, as grid/03-catalog.sbatch sets it.
DATA_ROOT = "/rs/rs_grp_oschome/go2432/data"
RC_LINE = re.compile(r"^XR_CATALOG_RC=([0-9]{1,3}) ", re.M)


def launcher_folder():
    """The folder the launcher was started in, where the stage has always run."""
    return Path(os.environ.get("SCHWINGNET_WORKDIR") or os.getcwd())


def from_launcher(path, folder=None):
    """A path parameter as the caller meant it: a relative one is read from the launcher's folder."""
    return str((folder or launcher_folder()) / path) if path and not Path(path).is_absolute() else path


def word_value(words, flag):
    """The value the words give a flag, the last one as click takes it; '' where they give none."""
    value, rest = "", list(words)
    while rest:
        word = rest.pop(0)
        if word == flag and rest:
            value = rest.pop(0)
        elif word.startswith(flag + "="):
            value = word[len(flag) + 1:]
    return value


def real_folder(path):
    """Whether a path is a folder itself, not a link to one, as find walks only into such."""
    try:
        return stat.S_ISDIR(os.lstat(path).st_mode)
    except OSError:
        return False


def folders_in(folder):
    """The names of the folders find walks into under a folder, in order: real ones, never a link
    to one; none where the folder cannot be read, of which find's listing says nothing."""
    try:
        with os.scandir(folder) as entries:
            return sorted(entry.name for entry in entries if entry.is_dir(follow_symlinks=False))
    except OSError:
        return []


def manifests_listed(data_root):
    """The manifests the stage builds from, as its find and awk list them: each
    <source>/shards/<shard>/MANIFEST.json under the data root, of any kind, reached through no
    link, where neither the source's name nor the shard's starts with a dot."""
    listed = []
    for source in folders_in(data_root):
        if source.startswith(".") or not real_folder(data_root / source / "shards"):
            continue
        for shard in folders_in(data_root / source / "shards"):
            manifest = data_root / source / "shards" / shard / "MANIFEST.json"
            if not shard.startswith(".") and os.path.lexists(manifest):
                listed.append(manifest)
    return listed


def manifest_line(data_root, manifest):
    """A manifest as the key names it: its path under the data root, its size and its sha256, read
    in one pass; 'unreadable' where it cannot be read, as the build would then refuse it."""
    name = manifest.relative_to(data_root).as_posix()
    try:
        with manifest.open("rb") as handle:
            sha256 = hashlib.file_digest(handle, "sha256").hexdigest()
            return f"{name} {handle.tell()} {sha256}"
    except OSError:
        return f"{name} unreadable"


def key_reads(words, folder):
    """What a run of these words reads that the words do not name, for the launcher's key: a line
    per manifest the stage would build from. Read in the launcher, before the run, from the
    launcher's folder, as the catalog step reads the same words. The step lists the manifests
    again under the build lock, so a shard that lands between the two is in the build and not in
    the key, and the next launch, whose key names it, runs anew rather than resume that run."""
    data_root = Path(from_launcher(word_value(words, "--data-root"), folder) or DATA_ROOT)
    return [manifest_line(data_root, manifest) for manifest in manifests_listed(data_root)]


def stage_rc(output):
    """The stage's own exit word, the last XR_CATALOG_RC line; None where it printed none."""
    found = RC_LINE.findall(output)
    return int(found[-1]) if found else None


def this_jobs_report(output):
    """The report this build wrote: the stage writes it only once it holds the lock, so a build
    that never held it reports its own output's last lines rather than another job's report."""
    if "XR_CATALOG lock " in output:
        try:
            return (launcher_folder() / REPORT).read_text(encoding="utf-8")
        except OSError:
            pass
    return "\n".join(output.splitlines()[-5:]) + "\n"


class CatalogFlow(FlowSpec):
    """Stage 3 of the X-ray chain: the catalog rebuilt from every shard and split-checked."""

    data_root = Parameter("data-root", default="", help="the data root; empty for the lab volume's")
    store = Parameter("store", default="", help="the catalog store; empty for <data root>/_catalog")
    commit = Parameter("commit", default="", help="the commit of the checkout that first started the run, which the launcher passes")

    @step
    def start(self):
        self.next(self.catalog)

    @step
    def catalog(self):
        """The whole stage in one step, under its own lock."""
        env = dict(os.environ, SCHWINGNET=str(REPO), DATA_ROOT=from_launcher(self.data_root),
                   STORE=from_launcher(self.store), SCHWINGNET_FLOW_STEP="1")
        done = subprocess.run(["bash", str(STAGE)], cwd=launcher_folder(), env=env, capture_output=True, text=True)
        self.output, self.code = done.stdout + done.stderr, done.returncode
        print(self.output, end="" if self.output.endswith("\n") else "\n", flush=True)
        self.rc = stage_rc(self.output)
        self.report = this_jobs_report(self.output)
        self.next(self.end)

    @card(type="blank")
    @step
    def end(self):
        """The report printed, and the verdict the stage's XR_CATALOG_RC gave."""
        self.verdict = 0 if self.rc == 0 and self.code == 0 else 1
        print(self.report, end="", flush=True)
        current.card.append(Markdown(f"# Stage 3, catalog\n\nThe stage said XR_CATALOG_RC={self.rc} and exited {self.code}."))
        current.card.append(Markdown(self.report))


if __name__ == "__main__":
    CatalogFlow()
