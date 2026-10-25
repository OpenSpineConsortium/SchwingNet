"""CatalogFlow: stage 3 of the X-ray chain, the catalog's build and split check, under Metaflow.

Started only by flows/launch.py (python flows/launch.py catalog -- --data-root ... --store ...),
which resumes the newest run of the same words and commit that did not finish.
grid/03-catalog.sbatch execs that launcher whenever Slurm runs it (issue #252).

One working step, since the build lock is held from the listing of the manifests to the marker
(issue #80): the step runs grid/03-catalog.sbatch with SCHWINGNET_FLOW_STEP=1 in the launcher's
working folder, so its lock, its report (logs/03-catalog-STAGE-REPORT.md) and its marker are
where they always were. A kill reruns the step whole on resume, which costs under a minute. The
stage's own refusal, a build or a split check that failed, is recorded and not raised, and the
end step's verdict carries it from the stage's XR_CATALOG_RC line, so the job's exit means what
it meant before.
"""

import os
import re
import subprocess
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, current, step
from metaflow.cards import Markdown

REPO = Path(os.environ.get("SCHWINGNET") or Path(__file__).resolve().parent.parent)
STAGE = REPO / "grid" / "03-catalog.sbatch"
REPORT = Path("logs") / "03-catalog-STAGE-REPORT.md"
RC_LINE = re.compile(r"^XR_CATALOG_RC=([0-9]{1,3}) ", re.M)


def launcher_folder():
    """The folder the launcher was started in, where the stage has always run."""
    return Path(os.environ.get("SCHWINGNET_WORKDIR") or os.getcwd())


def from_launcher(path):
    """A path parameter as the caller meant it: a relative one is read from the launcher's folder."""
    return str(launcher_folder() / path) if path and not Path(path).is_absolute() else path


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
    commit = Parameter("commit", default="", help="the checkout's commit, which the launcher passes")

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
