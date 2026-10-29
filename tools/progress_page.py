"""A launched flow's progress page, drawn off the grid from the gate's status answer.

Usage:
    python3 tools/progress_page.py STATUS [--run RUN] --out PAGE.html
    python3 tools/progress_page.py STATUS --list

On the grid each run flows/launch.py starts keeps its page, index.html, beside its files under
<datastore root>/progress/<Flow>/<run>/, which Open OnDemand's Files app opens in a browser
(flows/stage_progress.py). Off the grid the gate's status word prints each newest run's page in
short lines, under the heading `## flow <kind> <run>, progress (<time> UTC)`: its head, how it
ended (the verdict, the launcher's last word, the reports counted and the first of their lines)
and its steps, each with its first few tasks, its task and report lines judged as a stage
report's are and every line masked (grid/gate.sh, flow_progress). This
reads that answer, a file holding the status word's output as the grid's job log gives it, and
draws the same page from the section of the run named, or of the first run the answer shows,
which is the newest: the page the grid draws, less what status withheld and the tasks and
report lines the short lines leave to the page on the grid. The page is a picture of the answer:
a run the answer shows running whose files had not moved for ten minutes by the time the status
word ran, from its first line, is drawn silent (stage_progress.judged), as status itself judges it
from the file's time, and the page neither reloads nor judges again when opened. --list prints the
runs the answer holds. Nothing is fetched and nothing leaves the machine; the page is a file to open or
to publish. Standard library only.
"""

import argparse
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADING = re.compile(r"^## flow (?P<kind>[a-z0-9_]+) (?P<run>[A-Za-z0-9_.-]+), progress \((?P<time>[^)]*)\)$")
# The status word's first line, which says when it ran (grid/gate.sh).
ANSWERED = re.compile(r"^schwingnet status at commit \S+ on \S+ (?P<day>\d{4}-\d\d-\d\d) (?P<time>\d\d:\d\d:\d\d) UTC$")


def load_progress():
    """flows/stage_progress.py by its file, the module the grid draws the page with."""
    spec = importlib.util.spec_from_file_location("schwingnet_stage_progress", ROOT / "flows" / "stage_progress.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sections(text):
    """Every flow's section of a status answer, in its order: (kind, run, time, its lines)."""
    found, current = [], None
    for line in text.splitlines():
        heading = HEADING.match(line.strip())
        if heading:
            current = (heading["kind"], heading["run"], heading["time"], [])
            found.append(current)
        elif current is not None and line.startswith("  "):
            current[3].append(line[2:])
        else:
            current = None
    return found


def answered_at(text, progress):
    """When the status word ran, in seconds since the epoch, from its first line; None where the
    answer holds no such line, and the state is then taken as status gave it."""
    for line in text.splitlines():
        found = ANSWERED.match(line.strip())
        if found:
            return progress.parse_time(f"{found['day']}T{found['time']}Z") or None
    return None


def page_of(section, progress, source, now=None):
    kind, run, time, lines = section
    view = progress.view_of_lines(lines)
    view.setdefault("kind", kind)
    view.setdefault("run", run)
    view.setdefault("flow", None)
    view.setdefault("state", "unknown")
    if now is not None:
        view["state"] = progress.judged(view["state"], view.get("updated"), now)
    return progress.page_html(view, f"Drawn off the grid from the status answer {source}, its section of {time}.", live=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("status", help="a file holding the gate's status answer")
    parser.add_argument("--run", help="the run whose page to draw; the first the answer shows where none is named")
    parser.add_argument("--out", help="the page to write")
    parser.add_argument("--list", action="store_true", help="print the runs the answer holds")
    args = parser.parse_args(argv)
    text = Path(args.status).read_text(encoding="utf-8", errors="replace")
    found = sections(text)
    if args.list:
        for kind, run, time, lines in found:
            print(f"{run} {kind} ({time}), {len(lines)} lines")
        return 0
    if not args.out:
        parser.error("--out names the page to write, or --list prints the runs")
    chosen = [section for section in found if args.run in (None, section[1])]
    if not chosen:
        print(f"progress_page: no flow's progress {'of run ' + args.run + ' ' if args.run else ''}in {args.status}", file=sys.stderr)
        return 1
    progress = load_progress()
    Path(args.out).write_text(page_of(chosen[0], progress, Path(args.status).name, answered_at(text, progress)), encoding="utf-8")
    print(f"progress_page: {args.out}, the page of run {chosen[0][1]} ({chosen[0][0]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
