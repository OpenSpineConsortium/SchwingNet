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
off for a run, and the record says so. Each step is a W&B run of its own, grouped by the run id,
so the trainer's epochs and the evaluator's tables sit side by side.
"""

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

PROJECT = "SchwingNet"
TOKEN_FILE = Path.home() / ".wandb" / "token.env"
NETRC = Path.home() / ".netrc"


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


class Telemetry:
    """One step's W&B run in offline mode; every call is a no-op where W&B is off or absent."""

    def __init__(self, run_dir, record, step, config):
        self.run = None
        self.reason = None
        if not enabled():
            self.reason = "SCHWINGNET_WANDB=off"
            return
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
            id=f"{record['run_id']}-{step}",
            job_type=step,
            dir=str(folder),
            config=dict(config, run_id=record["run_id"], code_commit=record["code_commit"], catalog_sha256=record["catalog_sha256"], catalog_version=record["catalog_version"], clean_tree=record["clean_tree"]),
        )
        self.mode, self.reason = "offline", f"no W&B key ({where})"
        if where != "none" and os.environ.get("SCHWINGNET_WANDB_MODE", "online") == "online":
            try:
                if where == "file":
                    os.environ.update(token_file_env())
                self.run = wandb.init(mode="online", settings=wandb.Settings(silent=True, console="off", init_timeout=60), **options)
                self.mode, self.reason = "online", None
            except Exception as error:  # noqa: BLE001 - any failure to reach W&B falls back to offline
                said = " ".join(str(error).split())[:120]
                self.reason = f"online start failed ({type(error).__name__}: {said}); logged offline"
                # The failed start still holds the run id in W&B's service; a fresh service frees it.
                wandb.teardown()
        if self.run is None:
            self.run = wandb.init(mode="offline", settings=wandb.Settings(silent=True, console="off"), **options)
        note = {"step": step, "mode": self.mode, "why": self.reason, "url": getattr(self.run, "url", None) if self.mode == "online" else None}
        modes = Path(run_dir) / "wandb-mode.json"
        known = json.loads(modes.read_text(encoding="utf-8")) if modes.is_file() else {}
        modes.write_text(json.dumps(dict(known, **{step: note}), indent=1) + "\n", encoding="utf-8")

    def log(self, values, step=None):
        if self.run:
            self.run.log(values, step=step)

    def images(self, named_paths):
        """Images by name, from files already on disk; a missing file is skipped."""
        if self.run:
            return {name: self.wandb.Image(str(p)) for name, p in named_paths.items() if Path(p).is_file()}
        return {}

    def videos(self, named_paths):
        if self.run:
            return {name: self.wandb.Video(str(p), format="gif") for name, p in named_paths.items() if Path(p).is_file()}
        return {}

    def table(self, columns, rows):
        return self.wandb.Table(columns=list(columns), data=[list(r) for r in rows]) if self.run else None

    def summary(self, values):
        if self.run:
            self.run.summary.update(values)

    def finish(self):
        if self.run:
            self.run.finish()


def offline_runs(run_dir):
    """The step runs logged offline and not yet pushed; wandb sync leaves a .synced file behind."""
    return sorted(p for p in (Path(run_dir) / "wandb" / "wandb").glob("offline-run-*") if not any(p.glob("*.synced")))


def sync(run_dir):
    """Push the run's offline W&B files where a key is found; the outcome in wandb-sync.json."""
    run_dir = Path(run_dir)
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
    else:
        env = dict(os.environ, **(token_file_env() if where == "file" else {}))
        done = subprocess.run([sys.executable, "-m", "wandb", "sync", "--include-offline", *map(str, runs)], env=env, capture_output=True, text=True, check=False)
        outcome["synced"] = done.returncode == 0
        outcome["urls"] = sorted(set(live) | set(previous.get("urls", [])) | {word for word in (done.stdout + done.stderr).split() if word.startswith("https://wandb.ai/")})
        if done.returncode != 0:
            outcome["why"] = f"wandb sync exited {done.returncode}: {(done.stderr or done.stdout).strip()[-300:]}"
    (run_dir / "wandb-sync.json").write_text(json.dumps(outcome, indent=1) + "\n", encoding="utf-8")
    return outcome


def verdict(outcome):
    """The one line the flow prints last and writes into the ledger."""
    if outcome["synced"]:
        return "W&B: pushed " + (", ".join(outcome.get("urls", [])) or "(no link printed)")
    return f"W&B NOT PUSHED: {outcome.get('why', 'unknown')}; offline files kept in wandb/"


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
