"""tools/wandb_log.py's push of a run's offline W&B files, run against the installed wandb (#252).

The push is the one way a step logged offline reaches W&B, so it is run here for real: the
installed wandb writes the offline runs and its own `wandb sync` pushes them, to a stand-in for
W&B's server on a port of 127.0.0.1 that answers what wandb 0.30's sync asks and keeps each run's
history lines at the offsets the client writes them to, as the server does. No key is used: the
stand-in takes any, so each push is handed a placeholder of a key's length, and nothing leaves
this machine.

What it holds to: every option the push passes is one the installed wandb takes, since 0.30
refuses one it removed (--include-offline) before it reads a file; a half of a step W&B marked
pushed when the step was cut is not sent again, and the next half follows it; a push the server
refused, which 0.30's sync still ends with exit 0, is said not pushed; a push no server answers,
which 0.30's sync goes on trying for more than 25 minutes, is given up after the module's bound;
and a push leaves nothing in the directory it was started from, the checkout for tools/flow.py,
though wandb sync writes logs of its own where it runs.

The tests need wandb, which the train and telemetry environments hold, and skip under the
required check's plain python3.
"""

import contextlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
MISSING = [name for name in ("wandb",) if importlib.util.find_spec(name) is None]
# A placeholder of the length wandb asks of a key, for the stand-in, which takes any.
PLACEHOLDER = "x" * 40
# One offline half of a step, as Telemetry writes one: run as a process of its own, so this one
# never holds a W&B service.
HALF = """\
import sys
import wandb
folder, run_id, first, last = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
run = wandb.init(mode="offline", id=run_id, dir=folder, project="SchwingNet", group="run0", job_type="train",
                 settings=wandb.Settings(silent=True, console="off"))
for step in range(first, last + 1):
    run.log({"loss": 1.0 / (step + 1)}, step=step)
run.finish()
"""


def load():
    spec = importlib.util.spec_from_file_location("wandb_log_under_test", ROOT / "tools" / "wandb_log.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def environment(home, base_url=None, key=None):
    """This process's environment with no W&B setting of its own: W&B's files under home, its
    errors reported nowhere, and the server and key only where given."""
    kept = {name: value for name, value in os.environ.items() if not name.startswith("WANDB_")}
    kept.update(HOME=str(home), SCHWINGNET_WANDB="on", WANDB_ERROR_REPORTING="false", WANDB_CONFIG_DIR=str(home / "config"),
                WANDB_CACHE_DIR=str(home / "cache"), WANDB_DATA_DIR=str(home / "data"))
    kept.update({"WANDB_BASE_URL": base_url} if base_url else {})
    kept.update({"WANDB_API_KEY": key} if key else {})
    return kept


def closed_port():
    """A port of 127.0.0.1 nothing listens on, as a node with no route out meets W&B."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class StandIn(ThreadingHTTPServer):
    """W&B's server as wandb 0.30's sync meets it: a run made or found by its upsert, which tells
    the client how many history lines the run holds; each line kept where the file stream puts it,
    every write noted; uploads taken and dropped. Refusing, it refuses every upsert, as the server
    refuses a key it does not know."""

    def __init__(self, refusing=False):
        super().__init__(("127.0.0.1", 0), StandInHandler)
        self.refusing, self.lock = refusing, threading.Lock()
        self.history, self.writes = {}, []
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}"

    def steps(self, run):
        return [json.loads(line)["_step"] if line else None for line in self.history.get(run, [])]

    def lines_written(self, run):
        return sum(count for name, _, count in self.writes if name == run)

    def bucket(self, variables):
        name = variables.get("name") or variables.get("id")
        inserted = name not in self.history
        lines = self.history.setdefault(name, [])
        project, entity = variables.get("project") or "SchwingNet", variables.get("entity") or "stand-in"
        bucket = {"id": name, "name": name, "displayName": name, "description": None, "config": "{}", "sweepName": None,
                  "summaryMetrics": "{}", "logLineCount": 0, "historyLineCount": len(lines), "eventsLineCount": 0,
                  "historyTail": json.dumps(lines[-1:]), "eventsTail": "[]", "tags": [], "notes": None, "wandbConfig": "{}",
                  "project": {"id": project, "name": project, "entity": {"id": entity, "name": entity}}}
        return {"upsertBucket": {"bucket": bucket, "inserted": inserted}}

    def graphql(self, body):
        operation, variables = body.get("operationName"), body.get("variables") or {}
        if operation == "UpsertBucket" and self.refusing:
            return 403, {"errors": [{"message": "permission denied"}], "data": None}
        if operation == "UpsertBucket":
            return 200, {"data": self.bucket(variables)}
        if operation == "CreateRunFiles":
            files = [{"name": name, "uploadUrl": f"{self.url}/upload/{name}"} for name in variables.get("files", [])]
            return 200, {"data": {"createRunFiles": {"runID": "stand-in", "uploadHeaders": [], "files": files}}}
        if operation == "ServerFeaturesQuery":
            return 200, {"data": {"serverInfo": {"features": []}}}
        return 200, {"data": {}}

    def stream(self, run, files):
        history = files.get("wandb-history.jsonl")
        if not history:
            return
        lines, offset, content = self.history.setdefault(run, []), history["offset"], history["content"]
        lines.extend([None] * (offset + len(content) - len(lines)))
        lines[offset:offset + len(content)] = content
        self.writes.append((run, offset, len(content)))


class StandInHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def answer(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802 - http.server's own name
        self.answer(200, {})

    def do_PUT(self):  # noqa: N802 - a run file's upload
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.answer(200, {})

    def do_POST(self):  # noqa: N802 - GraphQL, the file stream, and the client's own metrics, read and dropped
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        with self.server.lock:
            if self.path.rstrip("/").endswith("/graphql"):
                self.answer(*self.server.graphql(json.loads(raw)))
            elif self.path.endswith("/file_stream"):
                self.server.stream(self.path.split("/")[-2], json.loads(raw).get("files", {}))
                self.answer(200, {"exitcode": None, "limits": {}})
            else:
                self.answer(200, {})


@unittest.skipIf(MISSING, f"needs wandb, which the train and telemetry environments hold ({', '.join(MISSING)} missing)")
class PushTest(unittest.TestCase):
    def setUp(self):
        self.tool = load()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.run_dir = self.tmp / "run"
        (self.tmp / "home").mkdir()
        self.server = StandIn()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        for name, value in (("TOKEN_FILE", self.tmp / "token.env"), ("NETRC", self.tmp / "netrc")):
            patch = mock.patch.object(self.tool, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def half(self, run_id, first, last):
        """One offline half of a step, written by the installed wandb under run/wandb as Telemetry
        writes it; its folder."""
        before = set(self.folders())
        done = subprocess.run([sys.executable, "-c", HALF, str(self.run_dir / "wandb"), run_id, str(first), str(last)],
                              env=environment(self.tmp / "home"), capture_output=True, text=True, timeout=180, check=False)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        (made,) = set(self.folders()) - before
        return made

    def folders(self):
        return sorted((self.run_dir / "wandb" / "wandb").glob("offline-run-*"))

    def push(self, base_url=None, run_dir=None):
        """The module's push of the run, against the stand-in unless another server is given; its
        outcome and each wandb sync it ran, with that sync's exit."""
        calls, real = [], subprocess.run

        def kept(command, **options):
            done = real(command, **options)
            calls.append((command, done.returncode))
            return done

        with mock.patch.dict(os.environ, environment(self.tmp / "home", base_url or self.server.url, PLACEHOLDER), clear=True), \
                mock.patch.object(self.tool.subprocess, "run", kept):
            outcome = self.tool.sync(run_dir or self.run_dir)
        return outcome, calls

    def test_every_option_the_push_passes_is_one_the_installed_wandb_takes(self):
        """A dry run of each sync the push runs, every option and folder as the push gives them,
        which wandb answers by listing the runs it would send, with no server and no key."""
        for run_id, first, last in (("run0-train", 0, 2), ("run0-train-offline", 3, 4), ("run0-evaluate", 0, 0)):
            self.half(run_id, first, last)
        answers, real = [], subprocess.run

        def dry(command, **options):
            done = real([*command[:4], "--dry-run", *command[4:]], **options)
            answers.append(done)
            return done

        with mock.patch.dict(os.environ, environment(self.tmp / "home", f"http://127.0.0.1:{closed_port()}", PLACEHOLDER), clear=True), \
                mock.patch.object(self.tool.subprocess, "run", dry):
            self.tool.sync(self.run_dir)
        self.assertTrue(answers, "the push ran no wandb sync")
        for done in answers:
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertIn("Would sync", done.stdout + done.stderr)
        listed = "".join(done.stdout + done.stderr for done in answers)
        for folder in self.folders():
            self.assertIn(folder.name, listed)

    def test_a_half_pushed_when_its_step_was_cut_is_not_sent_again_and_the_next_half_follows_it(self):
        """The flow pushes after every step, a cut one too; the resumed half, which offline W&B
        starts in a folder of its own, follows the pushed one, which is never sent twice."""
        self.half("run0-train", 0, 2)
        outcome, _ = self.push()
        self.assertTrue(outcome["synced"], outcome)
        self.assertEqual(self.server.steps("run0-train"), [0, 1, 2])
        later = self.half("run0-train", 3, 4)
        outcome, calls = self.push()
        self.assertTrue(outcome["synced"], outcome)
        self.assertEqual([[word for word in command if "offline-run-" in word] for command, _ in calls], [[str(later)]])
        self.assertEqual(self.server.steps("run0-train"), [0, 1, 2, 3, 4])
        self.assertEqual(self.server.lines_written("run0-train"), 5, "a line sent twice")

    def test_a_push_leaves_nothing_in_the_directory_it_was_started_from(self):
        """tools/flow.py pushes from the checkout, which its next run refuses with anything untracked
        in it, and wandb sync writes logs of its own under a wandb folder of the directory it runs in;
        the run directory is given relative to that directory, as the flow may give it."""
        self.half("run0-train", 0, 2)
        checkout = self.tmp / "checkout"
        checkout.mkdir()
        with contextlib.chdir(checkout):
            outcome, _ = self.push(run_dir=os.path.relpath(self.run_dir, checkout))
        self.assertTrue(outcome["synced"], outcome)
        self.assertEqual(self.server.steps("run0-train"), [0, 1, 2])
        self.assertEqual(sorted(path.name for path in checkout.rglob("*")), [])

    def test_a_push_the_server_refuses_is_said_not_pushed_though_wandb_sync_ends_with_0(self):
        self.server.refusing = True
        made = self.half("run0-train", 0, 2)
        outcome, _ = self.push()
        self.assertFalse(outcome["synced"], outcome)
        self.assertIn("permission denied", outcome["why"])
        self.assertTrue(self.tool.verdict(outcome).startswith("W&B NOT PUSHED"))
        self.assertEqual(self.tool.offline_runs(self.run_dir), [made], "kept for the next push")
        self.assertEqual(self.server.history.get("run0-train"), None)

    def test_a_push_no_server_answers_is_given_up_after_the_bound_and_said(self):
        self.half("run0-train", 0, 2)
        started = time.monotonic()
        with mock.patch.object(self.tool, "SYNC_SECONDS", 5, create=True):
            outcome, _ = self.push(f"http://127.0.0.1:{closed_port()}")
        self.assertLess(time.monotonic() - started, 60)
        self.assertFalse(outcome["synced"], outcome)
        self.assertIn("did not end within 5 s", outcome["why"])
        self.assertTrue(self.tool.verdict(outcome).startswith("W&B NOT PUSHED"))


if __name__ == "__main__":
    unittest.main()
