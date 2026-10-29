"""A launched flow's progress, as a page a person opens in a browser (the owner's rule of 2026-10-29).

Every run flows/launch.py starts keeps a folder <datastore root>/progress/<Flow>/<run>/: run.json,
the run's head (its kind, key, commit, code, PREREG and, for a resume, the run it carries on), which
the launcher writes once Metaflow has named the run, since a resumed run clones start and never runs
it; graph.json, the flow's steps in order, written by the first task that finds none; one file a
task under tasks/, <step>-<task>.json, which only that task writes, with its state, its times and
its last line; result.json, the end step's verdict and report lines; and launch.json, how the
launcher saw the flow end. From them every write draws three files: view.json, what the page says;
index.html, the page; and PROGRESS.txt, the same in short lines for the gate's status. A file is
written whole and renamed into place, so a reader never meets half of one, and no two tasks write
the same file, so two that draw the page at once each draw it from whole files and the later wins.
<root>/progress/index.html lists the newest runs of every flow.

On the grid the folder is on the lab volume, which Open OnDemand's Files app reaches in a browser
(https://ondemand.grid.wayne.edu, on the university's VPN; flows/README.md says how, untried on the
grid yet); the page reloads itself every REFRESH seconds while its run lasts. Off the grid, the gate's status prints each run's PROGRESS.txt, and
tools/progress_page.py draws the same page from the status word's answer (view_of_lines), so a page
can be published from wherever the answer is read. A run whose files have not moved for
SILENT_SECONDS is shown as silent: a job killed by Slurm writes nothing more, and a resume is a new
run, which names this one as its origin. Standard library only: the launcher, the flows, the page
tool and the required check's tests all import it.
"""

import html
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

FOLDER = "progress"
REFRESH = 30
SILENT_SECONDS = 600
RUNS_LISTED = 100
TASKS_SHOWN = 40
LINES_KEPT = 6
STATES = ("waiting", "running", "done", "failed", "cloned")


# --- the files ------------------------------------------------------------------------------------

def run_folder(root, flow, run):
    return Path(root) / FOLDER / flow / str(run)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_whole(path, text):
    """A file written beside itself and renamed into place, so a reader never meets half of it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(f".{path.name}.{os.getpid()}.part")
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
    states = [task.get("state") for task in tasks]
    if not states:
        return "waiting"
    if "running" in states:
        return "running"
    if "failed" in states:
        return "failed"
    return "cloned" if all(task.get("cloned") for task in tasks) else "done"


def task_view(task):
    label = str(task.get("label") or task.get("task"))
    state = "cloned" if task.get("cloned") and task.get("state") == "done" else str(task.get("state"))
    lines = [str(line) for line in task.get("lines") or []]
    return {"label": label, "state": state, "line": lines[-1] if lines else ""}


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
    if updated and now - parse_time(updated) > SILENT_SECONDS:
        return "silent"
    return "running"


def parse_time(words):
    try:
        return datetime.strptime(words, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return 0.0


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
                verdict=(result or {}).get("verdict"), report=[str(line) for line in (result or {}).get("lines") or []],
                ended=(launch or {}).get("words"))
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


def step_line(step):
    counts, total = step["counts"], step["total"]
    if total <= 1:
        return f"step {step['name']}: {step['state']}"
    parts = ", ".join(f"{counts[state]} {state}" for state in ("done", "cloned", "running", "failed") if counts[state])
    return f"step {step['name']}: {step['state']}; {parts} of {total}"


def task_lines(step):
    if step["total"] <= 1 and not (step["tasks"] and step["tasks"][0]["line"]):
        return []
    shown = [task for task in step["tasks"] if task["state"] != "done" and task["state"] != "cloned"] + \
            [task for task in step["tasks"] if task["state"] in ("done", "cloned")]
    lines = []
    for task in shown[:TASKS_SHOWN]:
        lines.append(f"task {step['name']} {task['label']}: {task['state']}" + (f"; {task['line']}" if task["line"] else ""))
    if len(shown) > TASKS_SHOWN:
        lines.append(f"({len(shown) - TASKS_SHOWN} more tasks of {step['name']}; the page on the grid lists them)")
    return lines


def text_lines(view):
    lines = head_lines(view)
    for step in view["steps"]:
        lines.append(step_line(step))
        lines += task_lines(step)
    lines += [f"report: {line}" for line in view["report"]]
    if view.get("verdict") in (0, 1):
        lines.append(f"verdict: {view['verdict']}")
    if view.get("ended"):
        lines.append(f"ended: {view['ended']}")
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
    """What a page says, read back from the short lines, as the gate's status prints them; a line
    that is none of them is kept as a note, so nothing the status said is lost."""
    view = {"steps": [], "report": [], "notes": [], "verdict": None, "ended": None}
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
        elif line.startswith("report: "):
            view["report"].append(line[len("report: "):])
        elif line.startswith("verdict: ") and line[len("verdict: "):] in ("0", "1"):
            view["verdict"] = int(line[len("verdict: "):])
        elif line.startswith("ended: "):
            view["ended"] = line[len("ended: "):]
        elif line:
            view["notes"].append(line)
    return view


# --- the page -------------------------------------------------------------------------------------

STYLE = """
:root { --bg: #fbfaf7; --ink: #1d1c1a; --muted: #6b675f; --line: #dcd7cc; --card: #ffffff;
  --waiting: #8a857b; --running: #1f5fbf; --done: #2e7d4f; --cloned: #4f7d6a; --failed: #b3261e; --silent: #9a6b00; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg: #161513; --ink: #ece9e2; --muted: #a39e94;
  --line: #3a3732; --card: #201f1c; --waiting: #8f8a80; --running: #6ea2f0; --done: #6cc391; --cloned: #86b8a2;
  --failed: #f0857c; --silent: #e0b14d; } }
:root[data-theme="dark"] { --bg: #161513; --ink: #ece9e2; --muted: #a39e94; --line: #3a3732; --card: #201f1c;
  --waiting: #8f8a80; --running: #6ea2f0; --done: #6cc391; --cloned: #86b8a2; --failed: #f0857c; --silent: #e0b14d; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 960px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 1.35rem; margin: 0 0 4px; } h2 { font-size: 1.05rem; margin: 28px 0 8px; }
.muted { color: var(--muted); } .facts { font-size: .85rem; color: var(--muted); overflow-wrap: anywhere; }
.badge { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: .8rem; font-weight: 600;
  border: 1px solid currentColor; }
.waiting { color: var(--waiting); } .running { color: var(--running); } .done, .succeeded { color: var(--done); }
.cloned { color: var(--cloned); } .failed { color: var(--failed); } .silent { color: var(--silent); }
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


def bar(step):
    total = step["total"] or 1
    parts = "".join(f'<span class="{state}" style="width:{100 * step["counts"][state] / total:.1f}%;background:currentColor"></span>'
                    for state in ("done", "cloned", "running", "failed") if step["counts"][state])
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


def page_html(view, source):
    """The page of one run, from what it says; source says where its words were read."""
    title = f"{view.get('flow') or 'Flow'} {view.get('run') or ''}".strip()
    refresh = f'<meta http-equiv="refresh" content="{REFRESH}">' if view.get("state") == "running" else ""
    facts = view.get("facts") or head_lines(view)[1][len("run: "):]
    steps = "".join(step_item(step) for step in view["steps"]) or "<li class=\"waiting\">No step has written yet.</li>"
    report = "".join(f"<li>{esc(line)}</li>" for line in view["report"])
    notes = "".join(f"<li>{esc(line)}</li>" for line in view.get("notes") or [])
    verdict = {0: "0, all well", 1: "1, not all well"}.get(view.get("verdict"), "not yet")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
{refresh}<title>{esc(title)}</title><style>{STYLE}</style></head>
<body><main>
<h1>{esc(title)} {badge(view.get('state') or 'unknown')}</h1>
<p class="muted">{esc(view.get('kind') or '')} &middot; started {esc(shown_time(view.get('started')))} &middot; updated {esc(shown_time(view.get('updated')))}</p>
<p class="facts">{esc(facts)}</p>
<h2>Steps</h2><ol class="steps">{steps}</ol>
<h2>CLAIM 2024 and REFORMS report</h2>{f'<ul class="plain">{report}</ul>' if report else '<p class="muted">Not written yet: the end step writes it.</p>'}
<h2>Verdict</h2><p>{esc(verdict)}{(' &middot; ' + esc(view['ended'])) if view.get('ended') else ''}</p>
{f'<h2>Other lines</h2><ul class="plain">{notes}</ul>' if notes else ''}
<p class="muted">{esc(source)}</p>
</main></body></html>
"""


def overview_html(views):
    rows = "".join(
        f"<tr><td><a href=\"{esc(view['flow'])}/{esc(view['run'])}/index.html\">{esc(view['flow'])}/{esc(view['run'])}</a></td>"
        f"<td>{esc(view.get('kind') or '')}</td><td>{badge(view.get('state') or 'unknown')}</td>"
        f"<td>{esc(shown_time(view.get('started')))}</td><td>{esc(shown_time(view.get('updated')))}</td></tr>" for view in views)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{REFRESH}"><title>Flow runs</title><style>{STYLE}</style></head>
<body><main><h1>Flow runs</h1><p class="muted">The {RUNS_LISTED} newest runs of every flow flows/launch.py started, newest first.</p>
<table><thead><tr><th>run</th><th>kind</th><th>state</th><th>started</th><th>updated</th></tr></thead><tbody>{rows}</tbody></table>
</main></body></html>
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
    base = Path(root) / FOLDER
    folders = sorted(base.glob("*/*/view.json"), key=lambda path: path.stat().st_mtime, reverse=True)[:RUNS_LISTED]
    views = [view for view in (read_json(path) for path in folders) if view and view.get("flow") and view.get("run")]
    write_whole(base / "index.html", overview_html(views))
