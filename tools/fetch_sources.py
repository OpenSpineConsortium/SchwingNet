"""Fetch the open X-ray datasets of grid/fetch-xray.json to the data root, one helper command per
entry, and record what came.

The list is the deliverable of docs/research/xray-datasets-missing.md turned into entries a job
can act on: each names its route (zenodo, hf, http, mendeley, figshare, kaggle, physionet or
manual), its link, its destination `<data_root>/<id>/raw` and what a person confirms on the page
first. The
downloads themselves are spinesurg-ct-nnunet's data_platform/reacquire/reacquire.py (the copy
under data/reproduce/reacquire/ is byte for byte the grid's), whose helpers resume a `.part`
file, verify Zenodo's md5 and Hugging Face's LFS sha256, and keep their state under `--state`;
this tool only decides which helper runs with which arguments, and then hashes every file that
is there, so FETCH.json beside the raw folder says what came, with what exit code and what
sha256, whatever the helper's own records say.

    python3 tools/fetch_sources.py                      # dry run: print every command, run nothing
    python3 tools/fetch_sources.py --only lumos,fracatlas
    python3 tools/fetch_sources.py --credentialed       # the opt-in PhysioNet list too
    python3 tools/fetch_sources.py --run --report grid/logs/01-fetch-STAGE-REPORT.md   # in a Slurm job

`--run` refuses the login node (a hostname starting with warrior, as reacquire.py refuses it) and
a shell outside a Slurm job: grid/01-fetch.sbatch is the way to run it. `--outside-slurm` lifts
the second refusal alone, for a container or a workstation where the chain is tested end to end
(issue #40), and hands the same flag to the helper; `--data-root <dir>` puts every landing under
another root than the list's, so such a run never names the grid's volume. An entry whose route is
manual, or whose Zenodo record is null, is skipped with one printed line and fails nothing; an
entry whose helper fails is reported and the next one runs; the exit code is 1 at the end when
any entry failed, so the chain's next stage, submitted with afterany, still runs on what came. An
entry marked `"unpack": true` has each zip archive that came verified opened into its raw folder,
member by member, since the bank stage reads files and not archives; a member already there with
its full size is left, so a rerun unpacks nothing twice. The helper is reacquire.py where the list
names it, else the repository's own copy under data/reproduce/reacquire/, which is the same file.

Secrets never reach a command line: the Kaggle token is read from a mode-0600 file into the
helper's environment alone, and PhysioNet's password stays in ~/.netrc, where wget reads it;
only the login name is passed, as PhysioNet's own documentation passes it. Standard library only.
"""

import argparse
import hashlib
import json
import os
import shlex
import socket
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIST = ROOT / "grid" / "fetch-xray.json"
REACQUIRE_COPY = ROOT / "data" / "reproduce" / "reacquire" / "reacquire.py"
HELPERS = ("zenodo-get", "http-get", "hf-get")
LOGIN_PREFIXES = ("warrior",)
STATE = "fetch-state"
RECORD = "FETCH.json"
SKIPPED, DONE, FAILED = "skipped", "done", "failed"


class FetchError(Exception):
    """An entry or a setting this tool refuses, with the reason a person reads."""


def on_login_node(hostname=None):
    name = (hostname or socket.gethostname()).split(".")[0]
    return name.startswith(LOGIN_PREFIXES)


def refuse_unless_job(outside_slurm=False):
    """None when the fetch may run here; else the one line that says where it runs instead. The
    login node is refused whatever the flags say; a shell outside a job only without
    --outside-slurm, which a container run of the chain passes."""
    hint = "cd ~/SchwingNet && bash grid/run-xray-chain.sh (grid/README.md)"
    if on_login_node():
        return f"refusing to fetch on the login node ({socket.gethostname()}). Submit instead: {hint}"
    if not os.environ.get("SLURM_JOB_ID") and not outside_slurm:
        return f"refusing to fetch outside a Slurm job. Submit instead: {hint} (or add --outside-slurm off the grid)"
    return None


def load_list(path=LIST):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("data_root", "reacquire", "open", "credentialed"):
        if key not in data:
            raise FetchError(f"{path}: no '{key}'")
    return data


def chosen(data, only, credentialed):
    """The entries this run acts on: the open list, the opt-in list only when asked, and of those
    only the ids named; an id named and not found is refused, so a typo never skips a set."""
    entries = list(data["open"]) + (list(data["credentialed"]) if credentialed else [])
    if not only:
        return entries
    wanted = [name for name in only.split(",") if name]
    known = {entry["id"]: entry for entry in list(data["open"]) + list(data["credentialed"])}
    missing = [name for name in wanted if name not in known]
    if missing:
        raise FetchError(f"no entry named {', '.join(missing)} in {LIST.name}")
    gated = {entry["id"] for entry in data["credentialed"]}
    named_gated = [name for name in wanted if name in gated]
    if named_gated and not credentialed:
        raise FetchError(f"{', '.join(named_gated)} is on the credentialed list: add --credentialed to run it")
    return [known[name] for name in wanted]


def relocate(entries, old_root, new_root):
    """The same entries landing under another data root: each dest keeps its `<id>/raw` tail, so
    a container run lays its root out as the grid's and the registry's grid_root rule holds."""
    if not new_root:
        return entries
    moved = []
    for entry in entries:
        copy = dict(entry)
        copy["dest"] = str(Path(new_root) / entry["id"] / "raw")
        if not entry["dest"].startswith(old_root.rstrip("/") + "/"):
            raise FetchError(f"{entry['id']}: dest {entry['dest']} is not under the list's data root {old_root}")
        moved.append(copy)
    return moved


def reacquire_path(data, override):
    """The helper: the path named, else the list's where it exists, else the repository's own
    copy, which docs/research/datasets-reproduce.md holds byte for byte to the grid's."""
    if override:
        return Path(os.path.expanduser(override))
    listed = Path(os.path.expanduser(data["reacquire"]))
    return listed if listed.is_file() else REACQUIRE_COPY


def state_dir(entry):
    return str(Path(entry["dest"]).parent / STATE)


def mode_0600(path):
    """A credential file is this tool's to read only when nobody else can: 0600 or stricter."""
    path = Path(os.path.expanduser(path))
    if not path.is_file():
        raise FetchError(f"{path}: no such file")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise FetchError(f"{path}: mode {mode:04o}; chmod 600 it first")
    return path


def kaggle_token(path):
    """KAGGLE_API_TOKEN=<token> from a 0600 file, for the helper's environment; never printed."""
    for line in mode_0600(path).read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key == "KAGGLE_API_TOKEN" and value:
            return value.strip().strip('"').strip("'")
    raise FetchError(f"{path}: no KAGGLE_API_TOKEN= line")


def netrc_login(host, path="~/.netrc"):
    """The login name for a host from ~/.netrc, which wget reads the password from itself."""
    words = mode_0600(path).read_text(encoding="utf-8").split()
    for index, word in enumerate(words):
        if word == "machine" and index + 1 < len(words) and words[index + 1] == host:
            rest = words[index + 2:]
            if "login" in rest:
                return rest[rest.index("login") + 1]
    raise FetchError(f"{path}: no 'machine {host} login <user>' entry")


def mendeley_files(api_url, opener=None):
    """The files of a Mendeley Data record, from its public API: name, download URL, sha256.
    The shape (files[].content_details) is what the API answered in 2025 and is 'to confirm'
    in the entry; a different answer is reported as a failure, not guessed around."""
    with (opener or urllib.request.urlopen)(api_url, timeout=120) as response:
        listing = json.loads(response.read().decode("utf-8"))
    files = listing if isinstance(listing, list) else listing.get("files", [])
    found = []
    for item in files:
        details = item.get("content_details") or {}
        url = details.get("download_url") or details.get("downloadUrl")
        name = item.get("filename") or details.get("filename")
        if url and name:
            found.append({"name": name, "url": url, "sha256": details.get("sha256")})
    if not found:
        raise FetchError(f"{api_url}: the answer lists no file with a download URL")
    return found


def figshare_files(api_url, opener=None):
    """The files of a figshare article, from its public API (https://api.figshare.com/v2/articles/<id>):
    name, download URL, size and the md5 figshare computed on upload, which http-get verifies
    after the download; a file without one is fetched and reported as unverified."""
    try:
        with (opener or urllib.request.urlopen)(api_url, timeout=120) as response:
            article = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        # The record names the host, so a report says which one a proxy or a network refused.
        raise FetchError(f"{api_url}: {error}") from error
    if article.get("is_embargoed") or article.get("download_disabled"):
        raise FetchError(f"{api_url}: the article is embargoed or its download is disabled")
    found = []
    for item in article.get("files", []):
        url, name = item.get("download_url"), item.get("name")
        if url and name and not item.get("is_link_only"):
            found.append({"name": name, "url": url, "md5": item.get("computed_md5") or item.get("supplied_md5"),
                          "size": item.get("size")})
    if not found:
        raise FetchError(f"{api_url}: the answer lists no file with a download URL")
    return found


def http_command(python, helper, url, dest, entry, checksum=None, size=None):
    command = [python, str(helper), "http-get", "--url", url, "--dest", dest, "--state", state_dir(entry)]
    for algo in ("md5", "sha256"):
        value = (checksum or {}).get(algo)
        if isinstance(value, str) and len(value) in (32, 64) and all(c in "0123456789abcdef" for c in value):
            command += [f"--{algo}", value]
    if isinstance(size, int) and size > 0:
        command += ["--bytes", str(size)]
    return command


def url_name(entry, index, url):
    names = entry.get("names") or []
    return names[index] if index < len(names) else url.rstrip("/").rsplit("/", 1)[-1] or f"file{index}"


def plan_entry(entry, python, helper, settings):
    """The commands of one entry as argv lists, or a skip line; the env the helper needs beside
    the inherited one is returned apart, so a token is never in the printed command."""
    route, dest = entry["route"], entry["dest"]
    if route == "manual" or (route == "zenodo" and entry.get("record") is None):
        why = "record number needed" if route == "zenodo" else next(
            (c for c in entry.get("confirm", []) if c.startswith("manual")), "manual: the link is not in the entry")
        return {"skip": why}
    if route == "zenodo":
        commands = [[python, str(helper), "zenodo-get", "--record", str(entry["record"]), "--dest", dest,
                     "--state", state_dir(entry)]]
        fallback = entry.get("fallback")
        if fallback and fallback.get("route") == "hf":
            commands.append([settings.acq_python, str(helper), "hf-get", "--repo", fallback["repo"], "--repo-type",
                             fallback.get("repo_type", "dataset"), "--dest", dest, "--state", state_dir(entry)])
            return {"commands": commands, "fallback": True}
        return {"commands": commands}
    if route == "hf":
        # hf-get imports huggingface_hub, which the repository's lock lacks and the data
        # platform's acq environment holds, so it runs under that python, as the IDC route does.
        return {"commands": [[settings.acq_python, str(helper), "hf-get", "--repo", entry["repo"], "--repo-type",
                              entry.get("repo_type", "dataset"), "--dest", dest, "--state", state_dir(entry)]]}
    if route == "http":
        if not entry.get("urls"):
            return {"skip": "manual: no URL in the entry yet"}
        return {"commands": [http_command(python, helper, url, os.path.join(dest, url_name(entry, i, url)),
                                          entry, entry.get("checksum")) for i, url in enumerate(entry["urls"])]}
    if route == "mendeley":
        return {"mendeley": entry["api"]}
    if route == "figshare":
        return {"figshare": entry["api"]}
    if route == "kaggle":
        return {"commands": [[settings.kaggle_bin, "datasets", "download", "-d", entry["kaggle"], "-p", dest]],
                "env_from": entry.get("token_file", "~/.fluorocap/credentials.env")}
    if route == "physionet":
        return {"physionet": entry["url"]}
    raise FetchError(f"{entry['id']}: unknown route {route!r}")


def physionet_commands(entry, login):
    # -r -N -c -np: recurse, keep timestamps, continue a partial file, never climb; the password
    # comes from ~/.netrc, which wget consults when --user is given without --password.
    return [["wget", "-r", "-N", "-c", "-np", "--user", login, "-P", entry["dest"], entry["url"]]]


def print_plan(entry, plan):
    print(f"== {entry['id']} -> {entry['dest']}")
    if "skip" in plan:
        print(f"   skip: {plan['skip']}")
        return
    if "mendeley" in plan:
        print(f"   mendeley: list {plan['mendeley']}, then http-get each file with its sha256 into {entry['dest']}")
    if "figshare" in plan:
        print(f"   figshare: list {plan['figshare']}, then http-get each file with its md5 and size into {entry['dest']}"
              + (", and unpack each zip there" if entry.get("unpack") else ""))
    if "physionet" in plan:
        print(f"   physionet: wget -r -N -c -np --user <login from ~/.netrc> -P {entry['dest']} {plan['physionet']}")
    for index, command in enumerate(plan.get("commands", [])):
        prefix = "   fallback: " if plan.get("fallback") and index else "   "
        print(prefix + shlex.join(command))
    if plan.get("env_from"):
        print(f"   with KAGGLE_API_TOKEN read from {plan['env_from']} (mode 0600) into the environment")
    size = entry.get("size_gb")
    print(f"   size: {size} GB" if size is not None else "   size: not known")
    for line in entry.get("confirm", []):
        print(f"   confirm: {line}")


def run_command(command, env=None, log=None):
    started = time.time()
    done = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if log is not None:
        log.write(done.stdout)
        log.flush()
    else:
        sys.stdout.write(done.stdout)
    return {"command": shlex.join(command), "exit": done.returncode, "seconds": round(time.time() - started, 1)}


def file_records(dest):
    """Every regular file under the raw folder with its size and sha256, in path order; a
    `.part` the helper left is listed as unfinished and not hashed."""
    records, total = [], 0
    for path in sorted(p for p in Path(dest).rglob("*") if p.is_file()):
        relative = str(path.relative_to(dest))
        size = path.stat().st_size
        if path.name.endswith(".part") or path.name.endswith(".bad"):
            records.append({"path": relative, "bytes": size, "unfinished": True})
            continue
        total += size
        records.append({"path": relative, "bytes": size, "sha256": sha256_of(path)})
    return records, total


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def expand_plan(entry, plan, python, helper, settings):
    """A plan that still needs the network (a Mendeley listing) or a file (a netrc login)
    becomes commands here, inside the job, so a dry run touches neither."""
    if "mendeley" in plan:
        files = mendeley_files(plan["mendeley"])
        plan["commands"] = [http_command(python, helper, f["url"], os.path.join(entry["dest"], f["name"]), entry,
                                         {"sha256": f.get("sha256")}) for f in files]
    if "figshare" in plan:
        files = figshare_files(plan["figshare"])
        plan["commands"] = [http_command(python, helper, f["url"], os.path.join(entry["dest"], f["name"]), entry,
                                         {"md5": f.get("md5")}, f.get("size")) for f in files]
    if "physionet" in plan:
        plan["commands"] = physionet_commands(entry, netrc_login("physionet.org", settings.netrc))
    if getattr(settings, "outside_slurm", False):
        # The helper refuses a shell outside a Slurm job as this tool does, and lifts it on the
        # same word; the flag goes only to the helper's own commands, never to kaggle or wget.
        plan["commands"] = [c + ["--outside-slurm"] if len(c) > 2 and c[2] in HELPERS else c
                            for c in plan["commands"]]
    env = None
    if plan.get("env_from"):
        env = dict(os.environ, KAGGLE_API_TOKEN=kaggle_token(plan["env_from"]))
    return plan["commands"], env


def unpack_archives(dest):
    """Every zip under the raw folder opened in place, member by member, beside the archive; a
    member already there with its full size is left, a member whose name climbs out of the folder
    is refused, and the archive itself stays, since its md5 is what the record verifies."""
    unpacked = []
    root = Path(dest).resolve()
    for archive in sorted(p for p in root.rglob("*.zip") if p.is_file()):
        with zipfile.ZipFile(archive) as opened:
            for member in opened.infolist():
                if member.is_dir():
                    continue
                target = (archive.parent / member.filename).resolve()
                if root not in target.parents:
                    raise FetchError(f"{archive}: member {member.filename} would land outside {root}")
                if target.is_file() and target.stat().st_size == member.file_size:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with opened.open(member) as source, open(target, "wb") as sink:
                    shutil_copy(source, sink)
                unpacked.append(str(target.relative_to(root)))
    return unpacked


def shutil_copy(source, sink):
    for block in iter(lambda: source.read(1 << 20), b""):
        sink.write(block)


def run_entry(entry, plan, python, helper, settings):
    """Run one entry's commands; a fallback runs only when the first command failed."""
    outcome = {"id": entry["id"], "dest": entry["dest"], "started": now(), "runs": []}
    Path(entry["dest"]).mkdir(parents=True, exist_ok=True)
    Path(state_dir(entry)).mkdir(parents=True, exist_ok=True)
    try:
        commands, env = expand_plan(entry, plan, python, helper, settings)
    except (FetchError, OSError, ValueError, urllib.error.URLError) as error:
        outcome.update(status=FAILED, error=str(error), ended=now())
        return outcome
    for index, command in enumerate(commands):
        if plan.get("fallback") and index and outcome["runs"][-1]["exit"] == 0:
            break
        outcome["runs"].append(run_command(command, env))
        if plan.get("fallback") and index == 0 and outcome["runs"][-1]["exit"] != 0:
            print(f"   {entry['id']}: the first route failed; trying the fallback")
    # The last command that ran decides: a fallback that succeeded after the first route failed
    # is done, and so is a list of URLs only when every one of them came.
    exits = [r["exit"] for r in outcome["runs"]]
    outcome["status"] = DONE if exits and (exits[-1] == 0 if plan.get("fallback") else all(e == 0 for e in exits)) else FAILED
    if outcome["status"] == DONE and entry.get("unpack"):
        try:
            outcome["unpacked"] = unpack_archives(entry["dest"])
        except (FetchError, OSError, zipfile.BadZipFile) as error:
            outcome.update(status=FAILED, error=f"unpack: {error}")
    files, total = file_records(entry["dest"])
    outcome.update(files=files, bytes=total, ended=now())
    return outcome


def write_record(entry, outcome):
    path = Path(entry["dest"]).parent / RECORD
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(outcome, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def report_lines(outcomes, started):
    lines = [f"# Stage 1, fetch: {now()}", "", f"Started {started}; one line per entry, the record is each"
             f" source's {RECORD} beside its raw folder.", ""]
    for outcome in outcomes:
        if outcome["status"] == SKIPPED:
            lines.append(f"- {outcome['id']}: skipped ({outcome['why']})")
            continue
        exits = ", ".join(str(r["exit"]) for r in outcome.get("runs", [])) or "none"
        files = [f for f in outcome.get("files", []) if "sha256" in f]
        lines.append(f"- {outcome['id']}: {outcome['status']}; exit codes {exits}; {len(files)} files,"
                     f" {outcome.get('bytes', 0) / 1e9:.2f} GB under {outcome['dest']}"
                     + (f"; {outcome['error']}" if outcome.get("error") else ""))
    failed = [o["id"] for o in outcomes if o["status"] == FAILED]
    lines += ["", "Failed: " + (", ".join(failed) if failed else "none") + ".",
              "Re-run one source: `bash grid/run-xray-chain.sh --only <id>` (grid/README.md).", ""]
    return lines


def parser():
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    top.add_argument("--list", default=str(LIST), help="the entries; grid/fetch-xray.json unless named")
    top.add_argument("--only", default="", help="comma-separated ids; every open entry unless named")
    top.add_argument("--credentialed", action="store_true", help="include the opt-in PhysioNet list")
    top.add_argument("--run", action="store_true", help="run the commands (inside a Slurm job only)")
    top.add_argument("--outside-slurm", action="store_true",
                     help="allow --run without SLURM_JOB_ID (a container or a workstation; never the login node)")
    top.add_argument("--data-root", default=None, help="land every entry under <dir>/<id>/raw instead of the list's root")
    top.add_argument("--python", default=sys.executable, help="the python the helper runs under (PYDRV)")
    top.add_argument("--reacquire", default=None,
                     help="reacquire.py; the list's path where it exists, else data/reproduce/reacquire/reacquire.py")
    top.add_argument("--acq-python", default="/rs/rs_grp_oschome/go2432/envs/acq/bin/python",
                     help="the data platform's acq environment, which holds huggingface_hub for hf-get")
    top.add_argument("--kaggle-bin", default=os.path.expanduser("~/mambaforge/envs/spineps/bin/kaggle"))
    top.add_argument("--netrc", default="~/.netrc")
    top.add_argument("--report", default=None, help="write STAGE-REPORT.md here after a run")
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        data = load_list(args.list)
        entries = relocate(chosen(data, args.only, args.credentialed), data["data_root"], args.data_root)
        helper = reacquire_path(data, args.reacquire)
        plans = [(entry, plan_entry(entry, args.python, helper, args)) for entry in entries]
        for entry, plan in plans:
            print_plan(entry, plan)
        if not args.run:
            print(f"dry run: {len(plans)} entries planned, nothing fetched; add --run inside a Slurm job")
            return 0
        refusal = refuse_unless_job(args.outside_slurm)
        if refusal:
            print(refusal, file=sys.stderr)
            return 3
        if not helper.is_file():
            raise FetchError(f"{helper}: no reacquire.py there; pull spinesurg-ct-nnunet on the grid"
                             f" (the repository's copy is {REACQUIRE_COPY})")
        return run_all(plans, args, helper)
    except FetchError as error:
        print(f"fetch_sources: {error}", file=sys.stderr)
        return 2


def run_all(plans, args, helper):
    started, outcomes = now(), []
    for entry, plan in plans:
        if "skip" in plan:
            print(f"{entry['id']}: skipped, {plan['skip']}")
            outcomes.append({"id": entry["id"], "status": SKIPPED, "why": plan["skip"]})
            continue
        print(f"{entry['id']}: fetching at {now()}", flush=True)
        outcome = run_entry(entry, plan, args.python, helper, args)
        print(f"{entry['id']}: {outcome['status']} at {now()}, record {write_record(entry, outcome)}", flush=True)
        outcomes.append(outcome)
    lines = report_lines(outcomes, started)
    if args.report:
        Path(args.report).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 1 if any(o["status"] == FAILED for o in outcomes) else 0


if __name__ == "__main__":
    sys.exit(main())
