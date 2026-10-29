"""A launched flow's progress, as a page a person opens in a browser (the owner's rule of 2026-10-29).

Every run flows/launch.py starts keeps a folder <datastore root>/progress/<Flow>/<run>/: run.json,
the run's head (its kind, key, commit, code, PREREG and, for a resume, the run it carries on), which
the launcher writes once Metaflow has named the run, since a resumed run clones start and never runs
it; graph.json, the flow's steps in order, written by the first task that finds none; one file a
task under tasks/, <step>-<task>.json, which only that task writes, with its state, its times and
its last line; result.json, the end step's verdict, report lines and how many of the reports are
current; and launch.json, how the launcher saw the flow end. From them every write draws three
files: view.json, what the page says; index.html, the page; and PROGRESS.txt, the same in short
lines for the gate's status, how the run ended right after its head and each step's tasks cut
short, so the gate's cut of the file never loses the verdict. A file is
written whole and renamed into place, so a reader never meets half of one, and no two tasks write
the same task file. Two that draw a run's page, or the list of runs, at once each draw it from whole
files; the one renamed last stands, though it may have read the files a moment before the other
did, and the next write of any task draws it again, so a page is never more than one write behind.
<root>/progress/index.html lists the newest runs of every flow.

On the grid the folder is on the lab volume, which Open OnDemand's Files app reaches in a browser
(https://ondemand.grid.wayne.edu, on the university's VPN; flows/README.md says how, untried on the
grid yet); the page reloads itself every REFRESH seconds while its run lasts. Off the grid, the gate's status prints each run's PROGRESS.txt, and
tools/progress_page.py draws the same page from the status word's answer (view_of_lines), so a page
can be published from wherever the answer is read. A run still running whose files have not moved
for SILENT_SECONDS is silent: a job killed by Slurm writes nothing more, and a resume is a new run,
which names this one as its origin. Since nothing draws a dead run's page again, the word its files
hold says running for good, so silence is judged where the page is read (judged): the page on the
grid in the reader's browser when it is opened, the list of runs whenever any run draws it, the
gate's status from PROGRESS.txt's time when it prints it (grid/gate.sh, flow_progress), and
tools/progress_page.py from the status answer's time. A task a resume shows from its origin that
was still running there was cut with it and is shown cut, to be run again, never running. Standard
library only: the launcher, the flows, the page tool and the required check's tests all import it.
"""

import html
import json
import os
import re
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

FOLDER = "progress"
REFRESH = 30
SILENT_SECONDS = 600
RUNS_LISTED = 100
# The short lines put a run's end first, after its two head lines (outcome_lines), and show at most
# REPORTS_SHOWN report lines and TASKS_SHOWN tasks of a step, so a run of a whole smoke plan, 27
# rows, fits in the 40 lines the gate's status keeps of each run (grid/gate.sh, FLOW_PROGRESS_LINES);
# the page on the grid lists every one.
REPORTS_SHOWN = 6
TASKS_SHOWN = 8
LINES_KEPT = 6
STATES = ("waiting", "running", "cut", "done", "failed", "cloned")


# --- the files ------------------------------------------------------------------------------------

def run_folder(root, flow, run):
    return Path(root) / FOLDER / flow / str(run)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_whole(path, text):
    """A file written beside itself and renamed into place, so a reader never meets half of it. The
    part is named by the host and the process, since tasks on two nodes of the grid, whose process
    numbers can meet, draw the same list of runs on the lab volume."""
    path.parent.mkdir(parents=True, exist_ok=True)
    host = re.sub(r"[^A-Za-z0-9.-]", "_", socket.gethostname())
    part = path.with_name(f".{path.name}.{host}-{os.getpid()}.part")
    part.write_text(text, encoding="utf-8")
    os.replace(part, path)


def write_json(path, data):
    write_whole(path, json.dumps(data, indent=1, sort_keys=True) + "\n")


def read_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def one_line(value):
    """A value as one line, since PROGRESS.txt is read a line at a time: a line break in a task's
    label or line, or in a report's, would start a line of another shape."""
    return " ".join(str(value).split()) if value is not None else ""


def task_name(step, task):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", f"{step}-{task}") + ".json"


def write_head(root, head):
    write_json(run_folder(root, head["flow"], head["run"]) / "run.json", head)


def write_graph(root, flow, run, steps):
    path = run_folder(root, flow, run) / "graph.json"
    if not path.is_file():
        write_json(path, {"steps": list(steps)})


def write_task(root, flow, run, task):
    write_json(run_folder(root, flow, run) / "tasks" / task_name(task["step"], task["task"]), task)


def write_result(root, flow, run, result):
    write_json(run_folder(root, flow, run) / "result.json", result)


def write_launch(root, flow, run, ended):
    write_json(run_folder(root, flow, run) / "launch.json", ended)


# --- what the page says ---------------------------------------------------------------------------

def tasks_of(folder):
    found = []
    for path in sorted((folder / "tasks").glob("*.json")):
        task = read_json(path)
        if task and isinstance(task.get("step"), str):
            found.append(task)
    return found


def origins(root, flow, origin, hops=10):
    """The folders of the run a resume carries on, and of the run that one carried on, the newest first."""
    found, seen = [], set()
    while origin and len(seen) < hops and origin not in seen:
        seen.add(origin)
        found.append(run_folder(root, flow, origin))
        origin = (read_json(found[-1] / "run.json") or {}).get("origin")
    return found


def origin_tasks(folders):
    """The tasks of each of a resume's origins, the newest origin's first, so a step this run cloned
    shows what its origin did."""
    return [[dict(task, cloned=True) for task in tasks_of(folder)] for folder in folders]


def task_key(task):
    """What one task of a step is across a run and its origins: its label, a foreach branch's row,
    which names the same work in every run. Metaflow gives every task of a resume a new id, so an
    unlabelled task, one a step that is no foreach runs once, stands for the whole step."""
    return task["step"], task.get("label") or None


def merged_tasks(own, cloned):
    """This run's tasks and its origins' (cloned, one list per origin, the newest first), one for
    each step and label: this run's where it has one, else the newest origin's, since a resume
    clones what its origin finished and runs again what it did not, and a run's own entry is newer
    than any origin's. An unlabelled step's tasks come whole from the newest run that has any, as
    their ids never meet across runs."""
    merged, whole_steps = {}, set()
    for run_tasks in (own, *cloned):
        unlabelled = {task["step"] for task in run_tasks if task_key(task)[1] is None} - whole_steps
        for task in run_tasks:
            key = task_key(task)
            if key[1] is None and key[0] in unlabelled:
                merged.setdefault(key, []).append(task)
            elif key[1] is not None and key not in merged:
                merged[key] = [task]
        whole_steps |= unlabelled
    return [task for tasks in merged.values() for task in tasks]


def graph_of(folder, folders):
    """The flow's steps in order, as the run's first task wrote them, or as its origin's did where
    no task of a resume has run yet."""
    for each in (folder, *folders):
        steps = (read_json(each / "graph.json") or {}).get("steps")
        if steps:
            return steps
    return []


def step_state(tasks):
    """A step's state from its tasks' as the page shows them (task_view): running while any runs,
    then failed, then cut, then cloned where its origins made every task, else done."""
    states = [task_view(task)["state"] for task in tasks]
    if not states:
        return "waiting"
    for state in ("running", "failed", "cut"):
        if state in states:
            return state
    return "cloned" if all(state == "cloned" for state in states) else "done"


def task_state(task):
    """A task's state as the page shows it. A task taken from an origin (merged_tasks) that finished
    there is cloned; one that failed there stays failed, since a row's fault @catch records is the
    result a resume clones; and one still running there, or in any other state, was cut when its
    run was and is shown cut, since only this run can run it again and its own task, once it
    starts, takes the origin's place."""
    state = one_line(task.get("state"))
    if not task.get("cloned"):
        return state
    return {"done": "cloned", "failed": "failed"}.get(state, "cut")


def task_view(task):
    label = one_line(task.get("label") or task.get("task"))
    lines = [one_line(line) for line in task.get("lines") or []]
    return {"label": label, "state": task_state(task), "line": lines[-1] if lines else ""}


def steps_view(graph, tasks):
    """Every step in the graph's order with its tasks, this run's and those its origins made that
    resume cloned (merged_tasks)."""
    names = list(graph) + sorted({task["step"] for task in tasks} - set(graph))
    steps = []
    for name in names:
        tasks_of_step = [task for task in tasks if task["step"] == name]
        counts = {state: sum(1 for task in tasks_of_step if task_view(task)["state"] == state) for state in STATES}
        steps.append({"name": name, "state": step_state(tasks_of_step), "counts": counts, "total": len(tasks_of_step),
                      "tasks": [task_view(task) for task in tasks_of_step]})
    return steps


def newest_time(folder):
    """When any file of the run last moved, as UTC words; the page's 'updated'."""
    times = [path.stat().st_mtime for path in folder.rglob("*.json") if path.name != "view.json"]
    return datetime.fromtimestamp(max(times), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if times else None


def run_state(result, launch, steps, updated, now):
    if result and result.get("verdict") in (0, 1):
        return "succeeded" if result["verdict"] == 0 else "failed"
    if launch:
        return "failed"
    return judged("running", updated, now)


def judged(state, updated, now):
    """A run's state as a reader at now takes it: one still running whose files last moved at
    updated, more than SILENT_SECONDS before now, is silent. The page's own word is written while
    the run still moves, so it is judged again wherever the page is read (the module's words)."""
    moved = parse_time(updated)
    if state == "running" and moved and now - moved > SILENT_SECONDS:
        return "silent"
    return state


def parse_time(words):
    try:
        return datetime.strptime(words, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return 0.0


def report_summary(result):
    """The reports the end step checked, counted, as finish records them; None where it counted none."""
    total, failing = (result or {}).get("reports"), (result or {}).get("not_current")
    if not all(isinstance(n, int) and not isinstance(n, bool) for n in (total, failing)) or total <= 0:
        return None
    return f"{total - failing} of {total} current" + (f", {failing} not current or not written" if failing else "")


def view_of_folder(root, flow, run, now=None):
    """What the page of one run says, from its files."""
    folder = run_folder(root, flow, run)
    head = read_json(folder / "run.json") or {"flow": flow, "run": str(run)}
    before = origins(root, flow, head.get("origin"))
    result, launch = read_json(folder / "result.json"), read_json(folder / "launch.json")
    steps = steps_view(graph_of(folder, before), merged_tasks(tasks_of(folder), origin_tasks(before)))
    updated = newest_time(folder)
    view = {key: head.get(key) for key in ("flow", "run", "kind", "key", "commit", "code", "prereg", "prereg_sha256", "origin", "started")}
    view.update(flow=flow, run=str(run), updated=updated, steps=steps,
                state=run_state(result, launch, steps, updated, now if now is not None else time.time()),
                verdict=(result or {}).get("verdict"), report=[one_line(line) for line in (result or {}).get("lines") or []],
                report_summary=report_summary(result), ended=one_line((launch or {}).get("words")) or None)
    return view


# --- the short lines, which the gate's status prints and tools/progress_page.py reads back --------

def shown_time(words):
    return f"{words[:10]} {words[11:19]} UTC" if isinstance(words, str) and len(words) >= 19 else "not recorded"


def head_lines(view):
    first = (f"flow {view['flow']}/{view['run']} {view.get('kind') or 'unknown'}: {view['state']}, "
             f"started {shown_time(view.get('started'))}, updated {shown_time(view.get('updated'))}")
    facts = [f"key {view['key']}" if view.get("key") else None, f"commit {view['commit']}" if view.get("commit") else None,
             f"code {view['code']}" if view.get("code") else None,
             f"resumed from {view['origin']}" if view.get("origin") else None,
             f"PREREG {view['prereg']} sha256 {str(view.get('prereg_sha256'))[:12]}" if view.get("prereg") else None]
    return [first, "run: " + ", ".join(fact for fact in facts if fact)]


# The counts a step's line and bar show, in this order.
SHOWN_COUNTS = ("done", "cloned", "running", "cut", "failed")


def step_line(step):
    counts, total = step["counts"], step["total"]
    if total <= 1:
        return f"step {step['name']}: {step['state']}"
    parts = ", ".join(f"{counts[state]} {state}" for state in SHOWN_COUNTS if counts[state])
    return f"step {step['name']}: {step['state']}; {parts} of {total}"


# The order a step's tasks are shown in: a failed one first, then those still running or waiting,
# then those done, so the tasks a reader needs are inside TASKS_SHOWN.
TASK_ORDER = {"failed": 0, "running": 1, "cut": 1, "waiting": 2, "done": 3, "cloned": 3}


def task_lines(step):
    if step["total"] <= 1 and not (step["tasks"] and step["tasks"][0]["line"]):
        return []
    shown = sorted(step["tasks"], key=lambda task: TASK_ORDER.get(task["state"], 2))
    lines = []
    for task in shown[:TASKS_SHOWN]:
        lines.append(f"task {step['name']} {task['label']}: {task['state']}" + (f"; {task['line']}" if task["line"] else ""))
    if len(shown) > TASKS_SHOWN:
        lines.append(f"({len(shown) - TASKS_SHOWN} more tasks of {step['name']}; the page on the grid lists them)")
    return lines


def outcome_lines(view):
    """How the run ended, right after its head, so no cut of the short lines loses it: the verdict,
    how the launcher saw the flow end, the reports counted, and at most REPORTS_SHOWN of their
    lines, those not current first, as the end step orders them (flows/stage.py, finish)."""
    lines = [f"verdict: {view['verdict']}"] if view.get("verdict") in (0, 1) else []
    lines += [f"ended: {view['ended']}"] if view.get("ended") else []
    lines += [f"reports: {view['report_summary']}"] if view.get("report_summary") else []
    lines += [f"report: {line}" for line in view["report"][:REPORTS_SHOWN]]
    if len(view["report"]) > REPORTS_SHOWN:
        lines.append(f"({len(view['report']) - REPORTS_SHOWN} more report lines; the page on the grid lists them)")
    return lines


def text_lines(view):
    """The page in short lines: the head, how the run ended, then every step with its tasks."""
    lines = head_lines(view) + outcome_lines(view)
    for step in view["steps"]:
        lines.append(step_line(step))
        lines += task_lines(step)
    return lines


HEAD = re.compile(r"flow (?P<flow>[A-Za-z0-9]+)/(?P<run>[A-Za-z0-9_.-]+) (?P<kind>\S+): (?P<state>[a-z]+), "
                  r"started (?P<started>.+?), updated (?P<updated>.+)")
STEP = re.compile(r"step (?P<name>[A-Za-z0-9_]+): (?P<state>[a-z]+)(?:; (?P<counts>.*) of (?P<total>\d+))?")
TASK = re.compile(r"task (?P<step>[A-Za-z0-9_]+) (?P<label>.+?): (?P<state>[a-z]+)(?:; (?P<line>.*))?")


def iso_of(shown):
    match = re.fullmatch(r"(\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d) UTC", shown.strip())
    return f"{match.group(1)}T{match.group(2)}Z" if match else None


def counts_of(words):
    counts = {state: 0 for state in STATES}
    for part in (words or "").split(", "):
        number, _, state = part.partition(" ")
        if number.isdigit() and state in counts:
            counts[state] = int(number)
    return counts


def view_of_lines(lines):
    """What a page says, read back from the short lines, as the gate's status prints them, with the
    line status adds where it judged the run silent; a line that is none of them is kept as a note,
    so nothing the status said is lost."""
    view = {"steps": [], "report": [], "report_summary": None, "notes": [], "verdict": None, "ended": None, "silence": None}
    for line in (line.strip() for line in lines):
        match = HEAD.fullmatch(line)
        if match:
            view.update(match.groupdict(), started=iso_of(match["started"]), updated=iso_of(match["updated"]))
        elif line.startswith("run: "):
            view["facts"] = line[len("run: "):]
        elif STEP.fullmatch(line):
            step = STEP.fullmatch(line)
            total = int(step["total"]) if step["total"] else (0 if step["state"] == "waiting" else 1)
            view["steps"].append({"name": step["name"], "state": step["state"], "counts": counts_of(step["counts"]), "total": total, "tasks": []})
        elif TASK.fullmatch(line) and view["steps"]:
            task = TASK.fullmatch(line)
            view["steps"][-1]["tasks"].append({"label": task["label"], "state": task["state"], "line": task["line"] or ""})
        elif line.startswith("reports: "):
            view["report_summary"] = line[len("reports: "):]
        elif line.startswith("report: "):
            view["report"].append(line[len("report: "):])
        elif line.startswith("verdict: ") and line[len("verdict: "):] in ("0", "1"):
            view["verdict"] = int(line[len("verdict: "):])
        elif line.startswith("ended: "):
            view["ended"] = line[len("ended: "):]
        elif line.startswith("silent: "):
            view["silence"] = line[len("silent: "):]
        elif line:
            view["notes"].append(line)
    return view


# --- the page -------------------------------------------------------------------------------------

STYLE = """
:root { --bg: #fbfaf7; --ink: #1d1c1a; --muted: #6b675f; --line: #dcd7cc; --card: #ffffff;
  --waiting: #8a857b; --running: #1f5fbf; --done: #2e7d4f; --cloned: #4f7d6a; --failed: #b3261e; --silent: #9a6b00;
  --cut: #7a5a99; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg: #161513; --ink: #ece9e2; --muted: #a39e94;
  --line: #3a3732; --card: #201f1c; --waiting: #8f8a80; --running: #6ea2f0; --done: #6cc391; --cloned: #86b8a2;
  --failed: #f0857c; --silent: #e0b14d; --cut: #b9a0d6; } }
:root[data-theme="dark"] { --bg: #161513; --ink: #ece9e2; --muted: #a39e94; --line: #3a3732; --card: #201f1c;
  --waiting: #8f8a80; --running: #6ea2f0; --done: #6cc391; --cloned: #86b8a2; --failed: #f0857c; --silent: #e0b14d;
  --cut: #b9a0d6; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 960px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 1.35rem; margin: 0 0 4px; } h2 { font-size: 1.05rem; margin: 28px 0 8px; }
.muted { color: var(--muted); } .facts { font-size: .85rem; color: var(--muted); overflow-wrap: anywhere; }
.badge { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: .8rem; font-weight: 600;
  border: 1px solid currentColor; }
.waiting { color: var(--waiting); } .running { color: var(--running); } .done, .succeeded { color: var(--done); }
.cloned { color: var(--cloned); } .failed { color: var(--failed); } .silent { color: var(--silent); } .cut { color: var(--cut); }
ol.steps { list-style: none; padding: 0; margin: 0; }
ol.steps > li { position: relative; padding: 10px 12px 10px 28px; margin: 0 0 8px; background: var(--card);
  border: 1px solid var(--line); border-radius: 8px; }
ol.steps > li::before { content: ""; position: absolute; left: 11px; top: 16px; width: 9px; height: 9px;
  border-radius: 50%; background: currentColor; }
ol.steps > li + li::after { content: ""; position: absolute; left: 14px; top: -9px; height: 9px; border-left: 2px solid var(--line); }
.step { display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; justify-content: space-between; color: var(--ink); }
.step b { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .92rem; }
.bar { height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; margin-top: 8px; display: flex; }
.bar span { display: block; height: 100%; }
table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: .85rem; }
td, th { text-align: left; padding: 4px 6px; border-top: 1px solid var(--line); vertical-align: top; overflow-wrap: anywhere; }
th { color: var(--muted); font-weight: 600; }
ul.plain { padding-left: 18px; } code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .85rem; }
"""


def esc(value):
    return html.escape(str(value), quote=True)


def badge(state):
    return f'<span class="badge {esc(state)}">{esc(state)}</span>'


def run_badge(view, live):
    """A run's badge. On a live page, one the grid keeps, a running run's carries when its files last
    moved, so SILENCE_SCRIPT judges it again when the page is opened (judged)."""
    state = view.get("state") or "unknown"
    if not (live and state == "running" and view.get("updated")):
        return badge(state)
    return f'<span class="badge {esc(state)}" data-updated="{esc(view["updated"])}">{esc(state)}</span>'


# The word a live page holds was written while its run still moved, and nothing draws a dead run's
# page again, so the browser judges each running badge as judged does when the page is opened. A
# browser that runs no script shows the word as written, which the gate's status still judges.
SILENCE_SCRIPT = f"""<script>
(function () {{
  var marks = document.querySelectorAll("[data-updated]");
  for (var i = 0; i < marks.length; i++) {{
    var moved = Date.parse(marks[i].getAttribute("data-updated"));
    if (moved && Date.now() - moved > {SILENT_SECONDS} * 1000) {{
      marks[i].textContent = "silent";
      marks[i].className = "badge silent";
      marks[i].title = "no file of this run has moved for more than {SILENT_SECONDS // 60} minutes";
    }}
  }}
}})();
</script>"""


def bar(step):
    total = step["total"] or 1
    parts = "".join(f'<span class="{state}" style="width:{100 * step["counts"][state] / total:.1f}%;background:currentColor"></span>'
                    for state in SHOWN_COUNTS if step["counts"][state])
    return f'<div class="bar">{parts}</div>' if step["total"] > 1 else ""


def task_table(step):
    if not step["tasks"] or (step["total"] <= 1 and not step["tasks"][0]["line"]):
        return ""
    rows = "".join(f"<tr><td>{esc(task['label'])}</td><td>{badge(task['state'])}</td><td>{esc(task['line'])}</td></tr>"
                   for task in step["tasks"])
    return f"<table><thead><tr><th>task</th><th>state</th><th>last line</th></tr></thead><tbody>{rows}</tbody></table>"


def step_item(step):
    counts = step_line(step).split("; ", 1)[1] if "; " in step_line(step) else ""
    return (f'<li class="{esc(step["state"])}"><div class="step"><b>{esc(step["name"])}</b>'
            f'<span>{esc(counts)} {badge(step["state"])}</span></div>{bar(step)}{task_table(step)}</li>')


def page_html(view, source, live=True):
    """The page of one run, from what it says; source says where its words were read. live is the
    page the grid keeps beside the run's files, which reloads itself while the run lasts and judges
    its silence when opened; a page drawn off the grid from a status answer is a picture of that
    answer, judged at its time (tools/progress_page.py), and does neither."""
    title = f"{view.get('flow') or 'Flow'} {view.get('run') or ''}".strip()
    refresh = f'<meta http-equiv="refresh" content="{REFRESH}">' if live and view.get("state") == "running" else ""
    silence = f'<p class="silent">{esc(view["silence"])}</p>' if view.get("silence") else ""
    facts = view.get("facts") or head_lines(view)[1][len("run: "):]
    steps = "".join(step_item(step) for step in view["steps"]) or "<li class=\"waiting\">No step has written yet.</li>"
    report = "".join(f"<li>{esc(line)}</li>" for line in view["report"])
    summary = f"<p>{esc(view['report_summary'])}</p>" if view.get("report_summary") else ""
    notes = "".join(f"<li>{esc(line)}</li>" for line in view.get("notes") or [])
    verdict = {0: "0, all well", 1: "1, not all well"}.get(view.get("verdict"), "not yet")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
{refresh}<title>{esc(title)}</title><style>{STYLE}</style></head>
<body><main>
<h1>{esc(title)} {run_badge(view, live)}</h1>
<p class="muted">{esc(view.get('kind') or '')} &middot; started {esc(shown_time(view.get('started')))} &middot; updated {esc(shown_time(view.get('updated')))}</p>
{silence}<p class="facts">{esc(facts)}</p>
<h2>Steps</h2><ol class="steps">{steps}</ol>
<h2>CLAIM 2024 and REFORMS report</h2>{summary}{f'<ul class="plain">{report}</ul>' if report else '<p class="muted">Not written yet: the end step writes it.</p>'}
<h2>Verdict</h2><p>{esc(verdict)}{(' &middot; ' + esc(view['ended'])) if view.get('ended') else ''}</p>
{f'<h2>Other lines</h2><ul class="plain">{notes}</ul>' if notes else ''}
<p class="muted">{esc(source)}</p>
</main>{SILENCE_SCRIPT if live else ''}</body></html>
"""


def overview_html(views):
    rows = "".join(
        f"<tr><td><a href=\"{esc(view['flow'])}/{esc(view['run'])}/index.html\">{esc(view['flow'])}/{esc(view['run'])}</a></td>"
        f"<td>{esc(view.get('kind') or '')}</td><td>{run_badge(view, True)}</td>"
        f"<td>{esc(shown_time(view.get('started')))}</td><td>{esc(shown_time(view.get('updated')))}</td></tr>" for view in views)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{REFRESH}"><title>Flow runs</title><style>{STYLE}</style></head>
<body><main><h1>Flow runs</h1><p class="muted">The {RUNS_LISTED} newest runs of every flow flows/launch.py started, newest first.</p>
<table><thead><tr><th>run</th><th>kind</th><th>state</th><th>started</th><th>updated</th></tr></thead><tbody>{rows}</tbody></table>
</main>{SILENCE_SCRIPT}</body></html>
"""


# --- drawing --------------------------------------------------------------------------------------

def draw(root, flow, run):
    """The run's view.json, index.html and PROGRESS.txt from its files, then the list of runs."""
    folder = run_folder(root, flow, run)
    view = view_of_folder(root, flow, run)
    write_json(folder / "view.json", view)
    write_whole(folder / "index.html", page_html(view, f"Drawn on the grid from {folder} at {shown_time(utc_now())}."))
    write_whole(folder / "PROGRESS.txt", "\n".join(text_lines(view)) + "\n")
    draw_overview(root)
    return view


def draw_overview(root):
    """The list of runs, each run's state judged as of this draw, since a run whose job died never
    draws its own view again (judged); the page judges them again when opened."""
    base = Path(root) / FOLDER
    folders = sorted(base.glob("*/*/view.json"), key=lambda path: path.stat().st_mtime, reverse=True)[:RUNS_LISTED]
    views = [view for view in (read_json(path) for path in folders) if view and view.get("flow") and view.get("run")]
    now = time.time()
    views = [dict(view, state=judged(view.get("state"), view.get("updated"), now)) for view in views]
    write_whole(base / "index.html", overview_html(views))
