"""Weights and Biases for a run: written offline beside the run on the node, pushed where a key is.

Usage:
    python tools/wandb_log.py status
    python tools/wandb_log.py sync --run <run dir>

The owner's words of 2026-10-21: the grid's environment holds a W&B key, the runs are to be
pushed there, and something is to be seen on the W&B website as soon as training starts. So
where a key is found, the trainer and the evaluator log online, live, epoch by epoch; where the
node has no route out, W&B's start times out within a minute and the step logs offline into
<run dir>/wandb instead, which nothing can lose, and `sync` pushes those files from wherever
tools/flow.py runs (the login node in slurm mode) as soon as each step ends. Which of the two
happened is in wandb-mode.json beside the run and in the flow's last line. The key is never read into this repository, never printed and never put on a
command line: W&B reads it from the environment (WANDB_API_KEY), from ~/.netrc's api.wandb.ai
entry that `wandb login` writes, or from ~/.wandb/token.env (one line WANDB_API_KEY=..., mode
600, the grid's convention for tokens, as ~/.hf/token.env is), which `sync` reads into the push's
own environment only. Where none is found the run still has its offline files, `sync` writes
wandb-sync.json saying so, and the flow says it on its last line and in the ledger, never
silently.

The project is SchwingNet unless WANDB_PROJECT says otherwise, private as the plan asks; the
entity is the key's default unless WANDB_ENTITY names one. SCHWINGNET_WANDB=off turns logging
off for a run, and the record says so. Each step is a W&B run of its own, <run id>-<step>,
grouped by the run id, so the trainer's epochs and the evaluator's tables sit side by side.

A step that goes on after a cut (tools/train.py --resume) starts online with resume="allow", so
W&B carries the epochs after the cut on in the run that holds the epochs before it. Offline
nothing resumes: wandb 0.30 ignores resume there, with a warning, and starts the id afresh in a
folder of its own, wandb/offline-run-<time>-<id>, so until it is pushed a step cut and carried on
offline is two runs; and an online start's offline fall-back logs under <run id>-<step>-offline,
since the failed start may have registered the step's id. `sync` joins them: a step's offline
runs not yet pushed go in one `wandb sync --id <run id>-<step>`, which replays them into the
step's one run in the order they started, after the lines W&B holds of it already, so a half
pushed when its step was cut, or the epochs logged online before a fall-back, come first
(tests/test_wandb_log.py runs it against a stand-in for W&B's server). A run counts as pushed
once wandb has left its mark beside the run's log, the .wandb.synced it writes when the server
took the run, and is never sent again, since its lines would be added a second time: 0.30's sync
ends with exit 0 when the server refused a run, so the mark, not the exit, says a push went, and
a sync no server answers is given up after SYNC_SECONDS. A killed step leaves less offline than it
logged: wandb writes a run's log out in blocks of 32 KiB and the rest when the run finishes, so a
step Slurm kills mid-way keeps only the blocks written before the kill, and a short one nothing.
Its log then ends with a record cut in two, which 0.30's sync reads no further than: it pushes
what it read and marks nothing, so every later push would send those lines again, and nothing
after them in the step's sync would go. So `sync` first cuts such a log back to its last whole
record, keeping the bytes it cut beside it in run-<id>.wandb.cut, and leaves out a log with no
whole record, which the sync refuses outright, saying so in wandb-sync.json and on the flow's
line. A log a trainer still writes ends the same way, so nothing is cut back or pushed while a
trainer holds the run's train/.lock; the evaluator holds none, so whoever pushes by hand waits for
it to end.
"""

import argparse
import fcntl
import json
import os
import re
import stat
import struct
import subprocess
import sys
from pathlib import Path

PROJECT = "SchwingNet"
TOKEN_FILE = Path.home() / ".wandb" / "token.env"
NETRC = Path.home() / ".netrc"
# What an online start's offline fall-back adds to the step's id (Telemetry._start).
OFFLINE_SUFFIX = "-offline"
# How long one wandb sync may take before the push gives it up, so the flow says NOT PUSHED and
# goes on. 0.30's sync tries each request to a server that does not answer 21 times over a quarter
# of an hour, once a minute at the last, and a run makes several, while a step's run, its pictures
# with it, is megabytes (4.1 MB for three epochs on the synthetic catalog).
SYNC_SECONDS = 600
# wandb's offline log, run-<id>.wandb, as 0.30 writes it: a header of 7 bytes, then its records
# framed as LevelDB frames them, in blocks of 32 KiB, each record in pieces with a head of 7 bytes
# of their own (checksum, length, kind): one whole piece, or a first, middles and a last where the
# record does not fit what is left of its block.
LOG_HEADER = b":W&B\xe1\xbe\x00"
LOG_BLOCK = 32768
PIECE_HEAD = 7
WHOLE, FIRST, MIDDLE, LAST = 1, 2, 3, 4


def enabled():
    return os.environ.get("SCHWINGNET_WANDB", "on").lower() != "off"


def key_source():
    """Where a W&B key is, by name only: env, file, netrc or none. Its value is never read here
    but for the file, whose one line is handed to the push's environment and nowhere else."""
    if os.environ.get("WANDB_API_KEY"):
        return "env"
    if TOKEN_FILE.is_file():
        return "file"
    if NETRC.is_file() and "api.wandb.ai" in NETRC.read_text(encoding="utf-8", errors="replace"):
        return "netrc"
    return "none"


def token_file_env():
    """The token file's WANDB_API_KEY, refused if others may read the file."""
    mode = TOKEN_FILE.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise PermissionError(f"{TOKEN_FILE} is readable by others; chmod 600 it")
    for line in TOKEN_FILE.read_text(encoding="utf-8").splitlines():
        name, _, value = line.strip().removeprefix("export ").partition("=")
        if name == "WANDB_API_KEY" and value:
            return {"WANDB_API_KEY": value.strip().strip("'\"")}
    raise ValueError(f"{TOKEN_FILE} has no WANDB_API_KEY line")


def plain(text, limit=200):
    """An error's first line, whitespace collapsed, no table bar, nothing key-shaped, so it is
    safe in a committed file, a ledger row and a Markdown cell."""
    first = (str(text).strip().splitlines() or [""])[0]
    first = re.sub(r"[0-9A-Za-z_-]{32,}", "[redacted]", " ".join(first.split()))
    return first.replace("|", "/")[:limit]


class Telemetry:
    """One step's W&B run; every call is a no-op where W&B is off, absent or broken.

    Nothing W&B does may stop a training run: a failure at any call is caught, logging stops for
    the step, and the reason is written to wandb-mode.json and said by the flow. resume is for a
    step that goes on after a cut: online, W&B carries the step's run on from where it was cut;
    offline the step logs a run of its own, which `sync` joins to the first when it pushes them
    (the module docstring).
    """

    def __init__(self, run_dir, record, step, config, resume=False):
        self.run = None
        self.mode = "off"
        self.reason = None
        self.modes = Path(run_dir) / "wandb-mode.json"
        self.step = step
        self.resume = resume
        if not enabled():
            self.reason = "SCHWINGNET_WANDB=off"
        else:
            try:
                self._start(run_dir, record, step, config)
            except Exception as error:  # noqa: BLE001 - W&B never stops a run
                self.run, self.mode = None, "off"
                self.reason = f"W&B could not start ({type(error).__name__}: {plain(error, 120)})"
        self._note()

    def _start(self, run_dir, record, step, config):
        try:
            import wandb
        except ImportError:
            self.reason = "wandb is not in this environment"
            return
        self.wandb = wandb
        folder = Path(run_dir) / "wandb"
        folder.mkdir(parents=True, exist_ok=True)
        where = key_source()
        options = dict(
            project=os.environ.get("WANDB_PROJECT", PROJECT),
            entity=os.environ.get("WANDB_ENTITY") or None,
            group=record["run_id"],
            name=f"{record['run_id']}-{step}",
            job_type=step,
            dir=str(folder),
            config=dict(config, run_id=record["run_id"], code_commit=record["code_commit"], catalog_sha256=record["catalog_sha256"], catalog_version=record["catalog_version"], clean_tree=record["clean_tree"]),
        )
        # Only online does W&B resume a run: offline it ignores resume, with a warning, and starts
        # the id afresh in a folder of its own, which `sync` joins to the step's run when it pushes.
        resume = {"resume": "allow"} if self.resume else {}
        self.mode, self.reason = "offline", f"no W&B key ({where})"
        if where != "none" and os.environ.get("SCHWINGNET_WANDB_MODE", "online") == "online":
            try:
                if where == "file":
                    os.environ.update(token_file_env())
                self.run = wandb.init(mode="online", id=f"{record['run_id']}-{step}", settings=wandb.Settings(silent=True, console="off", init_timeout=60), **options, **resume)
                self.mode, self.reason = "online", None
            except Exception as error:  # noqa: BLE001 - any failure to reach W&B falls back to offline
                self.reason = f"online start failed ({type(error).__name__}: {plain(error, 120)}); logged offline"
                # The failed start still holds the run id in W&B's service; a fresh service frees it.
                wandb.teardown()
        if self.run is None:
            # An id of its own, since a failed online start may have registered the first one;
            # `sync` pushes it into the step's run all the same.
            suffix = "" if self.mode == "offline" and self.reason.startswith("no W&B key") else OFFLINE_SUFFIX
            self.run = wandb.init(mode="offline", id=f"{record['run_id']}-{step}{suffix}", settings=wandb.Settings(silent=True, console="off"), **options)

    def _note(self):
        try:
            note = {"step": self.step, "mode": self.mode, "why": self.reason, "url": getattr(self.run, "url", None) if self.mode == "online" else None}
            known = json.loads(self.modes.read_text(encoding="utf-8")) if self.modes.is_file() else {}
            self.modes.write_text(json.dumps(dict(known, **{self.step: note}), indent=1) + "\n", encoding="utf-8")
        except (OSError, ValueError):
            pass

    def _guard(self, action, default=None):
        """Run one W&B call; on any failure logging stops for this step and says why."""
        if not self.run:
            return default
        try:
            return action()
        except Exception as error:  # noqa: BLE001 - W&B never stops a run
            self.run, self.mode = None, "off"
            self.reason = f"W&B failed mid-run ({type(error).__name__}: {plain(error, 120)}); logging stopped"
            self._note()
            return default

    def log(self, values, step=None):
        self._guard(lambda: self.run.log(values, step=step))

    def images(self, named_paths):
        """Images by name, from files already on disk; a missing file is skipped."""
        return self._guard(lambda: {name: self.wandb.Image(str(p)) for name, p in named_paths.items() if Path(p).is_file()}, {})

    def videos(self, named_paths):
        return self._guard(lambda: {name: self.wandb.Video(str(p), format="gif") for name, p in named_paths.items() if Path(p).is_file()}, {})

    def table(self, columns, rows):
        return self._guard(lambda: self.wandb.Table(columns=list(columns), data=[list(r) for r in rows]))

    def summary(self, values):
        self._guard(lambda: self.run.summary.update(values))

    def finish(self):
        self._guard(lambda: self.run.finish())


def pushed(folder):
    """Whether wandb sync marked an offline run pushed: it leaves a .wandb.synced beside the run's
    log once the server took it, and nothing where the server refused it."""
    return any(Path(folder).glob("*.synced"))


def offline_runs(run_dir):
    """The step runs logged offline and not yet pushed."""
    return sorted(p for p in (Path(run_dir) / "wandb" / "wandb").glob("offline-run-*") if not pushed(p))


def whole_records(data):
    """An offline log read by its framing alone: where its last whole record ends, how many whole
    records it holds, and whether a record cut short follows them, as a kill leaves one; None for
    a log of another shape, which is left to wandb as it is."""
    if not data.startswith(LOG_HEADER):
        return None
    at = end = len(LOG_HEADER)
    records, open_record = 0, False
    while at < len(data):
        room = LOG_BLOCK - at % LOG_BLOCK
        if room < PIECE_HEAD:
            at += room  # too little of the block is left for a piece's head: padding
            continue
        if at + PIECE_HEAD > len(data):
            return end, records, True
        _, length, kind = struct.unpack_from("<IHB", data, at)
        if kind not in (WHOLE, FIRST, MIDDLE, LAST) or PIECE_HEAD + length > room or (kind in (WHOLE, FIRST)) == open_record:
            return None
        if at + PIECE_HEAD + length > len(data):
            return end, records, True
        at += PIECE_HEAD + length
        open_record = kind in (FIRST, MIDDLE)
        records, end = (records, end) if open_record else (records + 1, at)
    return end, records, open_record


def cut_back(log):
    """Whether an offline log holds a whole record to push. A log a kill left with a record cut
    short is first cut back to its last whole record, the bytes cut off kept beside it in <log>.cut:
    0.30's sync reads such a log as far as that record, pushes what it read and marks nothing, so
    every push would send it again and nothing after it in its step's sync would go."""
    data = log.read_bytes()
    read = whole_records(data)
    if read is None:
        return True
    end, records, cut = read
    if cut and records:
        with log.with_name(log.name + ".cut").open("ab") as kept:
            kept.write(data[end:])
        with log.open("r+b") as handle:
            handle.truncate(end)
    return records > 0


def ready(runs):
    """The offline runs to push, each cut back where a kill left a record cut short (cut_back), and
    apart from them the empty ones: a log with no whole record, which 0.30's sync refuses, stopping
    there, or no log at all, as a step killed while wandb started leaves."""
    to_push, empty = [], []
    for folder in runs:
        logs = sorted(Path(folder).glob("run-*.wandb"))
        (to_push if logs and cut_back(logs[0]) else empty).append(folder)
    return to_push, empty


def trainer_running(run_dir):
    """Whether a trainer holds the run's train/.lock, as tools/train.py does to its end; a lock that
    cannot be read counts as held. A log a trainer still writes ends with a record cut short, as a
    killed one does, so the push waits for it."""
    path = Path(run_dir) / "train" / ".lock"
    if not path.is_file():
        return False
    try:
        with path.open("rb") as handle:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except OSError:
        return True
    return False


def step_of(folder):
    """The W&B id of the step an offline run is of: the id its log is named by (run-<id>.wandb),
    less the suffix an online start's offline fall-back takes; None for a folder with no log."""
    logs = sorted(Path(folder).glob("run-*.wandb"))
    return logs[0].name.removeprefix("run-").removesuffix(".wandb").removesuffix(OFFLINE_SUFFIX) if logs else None


def sync_commands(runs):
    """One wandb sync per step, with the step's offline runs: given --id, wandb replays every run it
    is given into that one W&B run, in the order the runs started, whatever their folders are
    called. A folder with no log goes alone and plain; wandb finds nothing in it to push."""
    steps = {}
    for folder in runs:
        steps.setdefault(step_of(folder), []).append(folder)
    return [(folders, [sys.executable, "-m", "wandb", "sync", *(("--id", step) if step else ()), *map(str, folders)]) for step, folders in steps.items()]


def as_text(output):
    """What a process printed, as text: a cut one's output comes as bytes."""
    return output.decode("utf-8", "replace") if isinstance(output, bytes) else output or ""


def run_sync(command, env, run_dir):
    """One wandb sync, given up after SYNC_SECONDS; its exit code, None where given up, and all it
    printed. wandb-core, which the sync starts, ends with it. It runs in the run directory, since it
    writes logs of its own under a wandb folder of the directory it runs in, and the flow pushes
    from the checkout, whose next run it would refuse with them there."""
    try:
        done = subprocess.run(command, cwd=run_dir, env=env, capture_output=True, text=True, check=False, timeout=SYNC_SECONDS)
    except subprocess.TimeoutExpired as cut:
        return None, as_text(cut.stdout) + as_text(cut.stderr)
    return done.returncode, done.stdout + done.stderr


def shortfall(code, said, folders):
    """Why one sync fell short, or None where wandb marked every run it was given pushed."""
    last = plain(next((line for line in reversed(said.splitlines()) if line.strip()), ""))
    if code is None:
        return f"wandb sync did not end within {SYNC_SECONDS} s, as when W&B cannot be reached from this node ({last})"
    if code:
        return f"wandb sync exited {code}: {last}"
    left = [folder for folder in folders if not pushed(folder)]
    return f"wandb sync left {len(left)} of {len(folders)} offline runs unpushed: {last}" if left else None


def push(runs, env, run_dir):
    """Each step's sync in turn; all they printed, and why the first that fell short did, None
    where none did. A sync given up ends the push, since W&B did not answer."""
    printed, why = [], None
    for folders, command in sync_commands(runs):
        code, said = run_sync(command, env, run_dir)
        printed.append(said)
        why = why or shortfall(code, said, folders)
        if code is None:
            break
    return "".join(printed), why


def sync(run_dir):
    """Push the run's offline W&B files where a key is found; the outcome in wandb-sync.json."""
    # Whole, since the sync runs in the run directory and is handed the runs' folders from there.
    run_dir = Path(run_dir).absolute()
    runs = offline_runs(run_dir)
    where = key_source()
    modes = json.loads((run_dir / "wandb-mode.json").read_text(encoding="utf-8")) if (run_dir / "wandb-mode.json").is_file() else {}
    previous = json.loads((run_dir / "wandb-sync.json").read_text(encoding="utf-8")) if (run_dir / "wandb-sync.json").is_file() else {}
    live = sorted(note["url"] for note in modes.values() if note.get("mode") == "online" and note.get("url"))
    outcome = {"key": where, "offline_runs": [p.name for p in runs], "online_urls": live, "synced": False}
    if not enabled():
        outcome["why"] = "SCHWINGNET_WANDB=off"
    elif not runs and (live or previous.get("synced")):
        outcome.update(synced=True, urls=sorted(set(live) | set(previous.get("urls", []))))
    elif not runs:
        outcome["why"] = "no W&B run in this run directory"
    elif where == "none":
        outcome["why"] = "no W&B key: not in WANDB_API_KEY, ~/.wandb/token.env or ~/.netrc"
    elif trainer_running(run_dir):
        outcome["why"] = "a trainer still holds train/.lock, so its offline log is still being written; it is pushed once the trainer ends"
    else:
        runs, empty = ready(runs)
        if empty:
            outcome["empty_runs"] = [p.name for p in empty]
        env = dict(os.environ, **(token_file_env() if where == "file" else {}))
        printed, why = push(runs, env, run_dir)
        outcome["synced"] = why is None
        outcome["urls"] = sorted(set(live) | set(previous.get("urls", [])) | {word for word in printed.split() if word.startswith("https://wandb.ai/")})
        if why:
            outcome["why"] = why
    (run_dir / "wandb-sync.json").write_text(json.dumps(outcome, indent=1) + "\n", encoding="utf-8")
    return outcome


def verdict(outcome):
    """The one line the flow prints last and writes into the ledger."""
    empty = len(outcome.get("empty_runs", []))
    runs = "1 offline run" if empty == 1 else f"{empty} offline runs"
    note = f"; {runs} held nothing to push (killed before wandb wrote a block)" if empty else ""
    if outcome["synced"]:
        return "W&B: pushed " + (", ".join(outcome.get("urls", [])) or "(no link printed)") + note
    return f"W&B NOT PUSHED: {outcome.get('why', 'unknown')}; offline files kept in wandb/{note}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    s = sub.add_parser("sync")
    s.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    if args.command == "status":
        print(json.dumps({"enabled": enabled(), "key": key_source()}))
        return 0
    outcome = sync(args.run)
    print(verdict(outcome))
    return 0 if outcome["synced"] or outcome["key"] == "none" or not enabled() else 1


if __name__ == "__main__":
    raise SystemExit(main())
