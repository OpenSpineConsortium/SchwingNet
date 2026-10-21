#!/usr/bin/env python3
"""Re-acquire any imaging source in data_platform/sources.json, by id or all of them.

Dry run by default: prints, per source, the exact commands (variables resolved), the checks that prove the copy is
complete, and the manual steps a gated source needs. --run executes the commands inside a Slurm job and writes a
state folder per source (verified.jsonl / failed.jsonl / REACQUIRE_STATUS.json / commands.sh / log.txt), in the
manner of tools/acquisition_fetch.py. --verify runs only the checks.

    python3 reacquire.py --list                              # every source id with its route and mode
    python3 reacquire.py carmlspine ctspinopelvic1k           # dry run: print what would run
    python3 reacquire.py --grid --all --modes run submit      # dry run with the grid's HOME, for everything unattended
    cd data_platform/reacquire && mkdir -p logs && sbatch -D "$PWD" --export=ALL,IDS="carmlspine",MODE=--run reacquire.sbatch
    python3 reacquire.py --verify carmlspine                 # checks only (inside a job)

Helpers used by the commands in sources.json (inside a job only, like --run; --outside-slurm for tests):
    reacquire.py zenodo-get --record 22797014 --dest DIR [--include REGEX] [--state DIR]   md5 + size per file
    reacquire.py hf-get --repo ID --repo-type dataset [--revision SHA] [--include GLOB] --dest DIR [--state DIR]
    reacquire.py http-get --url URL --dest FILE [--md5 X] [--sha256 X] [--bytes N] [--impersonate] [--state DIR]
    reacquire.py github-zip --repo OWNER/NAME --dest FILE [--branch B] [--md5 X] [--bytes N] [--state DIR]
    reacquire.py nifti-check --ct-dir DIR --label-dir DIR --out JSON      gzip integrity of every CT; affine == label

Every download goes to <dest>.part, is checked (size, md5, sha256 as given) and only then renamed over <dest>, so a
bad download never replaces a good copy. A rerun of a submit-mode source inside the same Slurm job (a requeue) skips
the commands that already ran; --resume does the same across jobs.

The planning path (listing, printing, the login-node check, the checks) is standard library and Python 3.6-compatible.
hf-get needs huggingface_hub; http-get --impersonate needs curl_cffi; nifti-check uses nibabel when importable.
Never runs work on the login node (hostname warrior*): it prints the sbatch line instead (CLAUDE.md, Grid).
"""
import argparse
import fnmatch
import gzip
import hashlib
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import tarfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DPROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(DPROOT, "lib"))
UA = {"User-Agent": "spinesurg-ct-nnunet data_platform/reacquire (research)"}
LOGIN_PREFIXES = ("warrior",)
GRID_HOME = "/wsu/home/go/go24/go2432"


# ------------------------------------------------------------------------------------------------ loading
def load_sources(path=None):
    """sources.json (always present beside sources.yaml); sources.yaml when only that exists."""
    path = path or os.path.join(DPROOT, "sources.json")
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    try:
        import yaml
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except ImportError:
        import mini_yaml
        with open(path, encoding="utf-8") as fh:
            return mini_yaml.load(fh)


def env_defaults(home=None):
    home = home or os.environ.get("HOME") or os.path.expanduser("~")
    rs = os.environ.get("RS", "/rs/rs_grp_oschome/go2432")
    data = os.environ.get("DATA", rs + "/data")
    repo = os.environ.get("REPO", home + "/spinesurg-ct-nnunet")
    return dict(HOME=home, RS=rs, DATA=data, REPO=repo, DP=os.environ.get("DP", repo + "/data_platform"),
                CTSP_REPO=os.environ.get("CTSP_REPO", home + "/CTSpinoPelvic1K"),
                VFR_REPO=os.environ.get("VFR_REPO", home + "/VerSeFusion"),
                XRSP_REPO=os.environ.get("XRSP_REPO", home + "/XRSpinoPelvic1K"),
                SDET_REPO=os.environ.get("SDET_REPO", home + "/spine-detector"),
                ACQ=os.environ.get("ACQ", data + "/anomaly_harvest/acquisition"))


PY_ENVS = {"spineps": "{HOME}/mambaforge/envs/spineps/bin/python", "fluorogen": "{HOME}/mambaforge/envs/fluorogen/bin/python",
           "acq": "{RS}/envs/acq/bin/python", "vfr": "python3", "container": "python3"}


def source_env(src, base, state_root=None):
    """The variables one source's commands use. DEST is the source's layout path: <folder>/<subpath> when the layout
    names a subpath (raw/... for an upstream release, derived/<bank> for a bank), else <folder>/raw."""
    e = dict(base)
    lay = src.get("layout") or {}
    folder = lay.get("folder") or src["id"]
    sub = (lay.get("subpath") or "").strip("/")
    if "*" in sub:                                   # a wildcard subpath (derived/implant_*): its parent
        sub = os.path.dirname(sub).strip("/")
    froot = "%s/%s" % (e["DATA"], folder)
    dest = froot + "/" + sub if sub else froot + "/raw"
    e["DEST"] = os.environ.get("DEST_OVERRIDE", dest)
    e["STATE"] = os.path.join(state_root, src["id"]) if state_root else froot + "/meta/reacquire/" + src["id"]
    pyenv = (src.get("reacquire") or {}).get("py_env") or "spineps"
    e["PY"] = os.environ.get("PY", PY_ENVS.get(pyenv, "python3").format(**e))
    return e


VAR = re.compile(r"\$\{([A-Z_]+)\}")


def resolve(cmd, env):
    return VAR.sub(lambda m: env.get(m.group(1), m.group(0)), cmd)


def on_login_node():
    return socket.gethostname().split(".")[0].startswith(LOGIN_PREFIXES)


def refuse_unless_job(what, sbatch_hint, outside_slurm=False):
    """None when work may run here; else a message (and the caller returns 3)."""
    if on_login_node():
        return "refusing to run %s on the login node (%s). Submit instead:\n  %s" % (what, socket.gethostname(), sbatch_hint)
    if not os.environ.get("SLURM_JOB_ID") and not outside_slurm:
        return "refusing: %s outside a Slurm job. Submit instead:\n  %s" % (what, sbatch_hint)
    return None


# ------------------------------------------------------------------------------------------------ state
class State(object):
    def __init__(self, d):
        self.dir = d
        os.makedirs(d, exist_ok=True)

    def _append(self, name, rec):
        rec = dict(rec, t=time.strftime("%Y-%m-%dT%H:%M:%S"), job=os.environ.get("SLURM_JOB_ID", ""))
        with open(os.path.join(self.dir, name), "a") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    def ok(self, unit, **info):
        self._append("verified.jsonl", dict(unit=unit, **info))

    def fail(self, unit, why, **info):
        self._append("failed.jsonl", dict(unit=unit, why=str(why)[:800], **info))

    def done_units(self):
        p = os.path.join(self.dir, "verified.jsonl")
        out = {}
        if os.path.exists(p):
            with open(p) as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        d = json.loads(line)
                        out[d["unit"]] = d
        return out

    def status(self, **st):
        st["t"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        with open(os.path.join(self.dir, "REACQUIRE_STATUS.json"), "w") as fh:
            json.dump(st, fh, indent=1, sort_keys=True)


# ------------------------------------------------------------------------------------------------ checks
def file_hash(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def list_sha256(root):
    """The content-list hash of tools/data_manifest.py walk(): sorted dirs, sorted files, '<rel>\\t<size>\\n'."""
    rows, total = [], 0
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for f in sorted(fn):
            p = os.path.join(dp, f)
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            rows.append((os.path.relpath(p, root).replace("\\", "/"), sz))
            total += sz
    h = hashlib.sha256()
    for rel, sz in rows:
        h.update(("%s\t%d\n" % (rel, sz)).encode())
    return h.hexdigest(), len(rows), total


def _cmp(got, expect, op="=="):
    if op == ">=":
        return got >= expect
    return got == expect


def archive_members(path):
    """Read every member of a tar(.gz) or zip in full; returns the member count or raises on corruption."""
    if path.endswith(".zip"):
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
            if bad:
                raise IOError("bad zip member %s" % bad)
            return len(zf.namelist())
    n = 0
    with tarfile.open(path, "r:*") as tf:
        for m in tf:
            if m.isfile():
                fh = tf.extractfile(m)
                while fh.read(1 << 20):
                    pass
            n += 1
    return n


def run_check(chk, env):
    t = chk.get("type")
    path = resolve(chk.get("path", ""), env)
    res = dict(type=t, path=path, expect=chk.get("expect"))
    try:
        if t == "note":
            res.update(ok=None, note=resolve(chk.get("text", ""), env))
        elif t == "exists":
            res.update(ok=os.path.exists(path), got=os.path.exists(path))
        elif t == "bytes":
            got = os.path.getsize(path)
            res.update(ok=got == chk["expect"], got=got)
        elif t in ("md5", "sha256"):
            got = file_hash(path, t)
            res.update(ok=got == chk["expect"], got=got)
        elif t == "count":
            pat = chk.get("glob", "*")
            n = 0
            if not os.path.isdir(path):
                raise OSError("no directory %s" % path)
            for dp, dn, fn in os.walk(path):
                for f in fn:
                    if fnmatch.fnmatch(f, pat):
                        p = os.path.join(dp, f)
                        if chk.get("nonempty") and os.path.getsize(p) == 0:
                            continue
                        if chk.get("min_bytes") and os.path.getsize(p) < int(chk["min_bytes"]):
                            continue
                        n += 1
                if not chk.get("recursive", False):
                    break
            res.update(ok=_cmp(n, chk["expect"], chk.get("op", "==")), got=n)
        elif t == "count_dirs":
            rx = re.compile(chk.get("pattern", ".*"))
            n = sum(1 for d in os.listdir(path) if os.path.isdir(os.path.join(path, d)) and rx.search(d))
            res.update(ok=_cmp(n, chk["expect"], chk.get("op", "==")), got=n)
        elif t == "json_field":
            with open(path) as fh:
                got = json.load(fh)
            for k in str(chk["field"]).split("."):
                got = got.get(k) if isinstance(got, dict) else None
            res.update(ok=got == chk["expect"], got=got)
        elif t == "jsonl_count":
            # distinct 'unit' values of a verified.jsonl, optionally only rows whose <field> equals <value>
            units = set()
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if chk.get("field") and str(d.get(chk["field"])) != str(chk.get("value")):
                    continue
                units.add(d.get("unit"))
            res.update(ok=_cmp(len(units), chk["expect"], chk.get("op", "==")), got=len(units))
        elif t == "archive_ok":
            got, bad = {}, []
            for f in sorted(os.listdir(path)):
                if fnmatch.fnmatch(f, chk.get("glob", "*")):
                    try:
                        got[f] = archive_members(os.path.join(path, f))
                    except Exception as exc:   # noqa: BLE001  (a corrupt archive is the finding, not a crash)
                        bad.append("%s: %r" % (f, exc))
            res.update(ok=not bad and _cmp(len(got), chk["expect"], chk.get("op", "==")), got=dict(members=got, bad=bad))
        elif t == "sha256sums":
            bad, n = [], 0
            for line in open(os.path.join(path, chk.get("file", "SHA256SUMS.txt"))):
                parts = line.strip().split(None, 1)
                if len(parts) != 2:
                    continue
                h, name = parts[0], parts[1].lstrip("*")
                n += 1
                p = os.path.join(path, name)
                if not os.path.exists(p) or file_hash(p, "sha256") != h:
                    bad.append(name)
            res.update(ok=not bad and n > 0, got=dict(checked=n, failed=bad[:20], n_failed=len(bad)))
        elif t == "list_sha256":
            h, n, b = list_sha256(path)
            res.update(ok=h == chk["expect"], got=dict(list_sha256=h, files=n, bytes=b),
                       note=chk.get("note") or ("expected %s files, %s bytes" % (chk.get("files"), chk.get("bytes"))))
        else:
            res.update(ok=None, note="unknown check type")
    except (OSError, ValueError, KeyError) as exc:
        res.update(ok=False, got="error: %r" % (exc,))
    return res


def describe_check(chk, env):
    """One line naming every key the check uses, so a dry run reads the way the check runs."""
    t = chk.get("type")
    path = resolve(chk.get("path", ""), env)
    extra = []
    for k in ("field", "value", "glob", "recursive", "nonempty", "min_bytes", "op", "pattern", "file", "files", "bytes"):
        if k in chk:
            extra.append("%s=%s" % (k, json.dumps(chk[k])))
    s = "%s %s%s expect %s" % (t, path, (" [" + ", ".join(extra) + "]") if extra else "", json.dumps(chk.get("expect")))
    if chk.get("note"):
        s += "  (%s)" % chk["note"]
    return s


# ------------------------------------------------------------------------------------------------ helpers (network)
def _urlopen(url, headers=None, timeout=120):
    import urllib.request
    req = urllib.request.Request(url, headers=dict(UA, **(headers or {})))
    return urllib.request.urlopen(req, timeout=timeout)


def download(url, dst, size=None, impersonate=False, check=None):
    """Resume into dst.part with an HTTP Range request; check the .part (size when known, then check(part)); rename over
    dst only when it passes. A complete .part that the server answers with 416 is taken as complete."""
    part = dst + ".part"
    os.makedirs(os.path.dirname(os.path.abspath(dst)) or ".", exist_ok=True)
    have = os.path.getsize(part) if os.path.exists(part) else 0
    if not (size is not None and have == int(size)):
        if impersonate:
            from curl_cffi import requests as cr
            hdr = {"Range": "bytes=%d-" % have} if have else {}
            r = cr.get(url, impersonate="chrome", stream=True, headers=hdr, timeout=600)
            if r.status_code == 416 and have:
                pass                                   # the .part already holds every byte the server has
            else:
                mode = "ab" if (have and r.status_code == 206) else "wb"
                with open(part, mode) as fh:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)
        else:
            import urllib.error
            hdr = {"Range": "bytes=%d-" % have} if have and not url.startswith("file:") else {}
            try:
                with _urlopen(url, hdr) as r:
                    code = getattr(r, "status", None) or r.getcode()
                    mode = "ab" if (have and code == 206) else "wb"
                    with open(part, mode) as fh:
                        while True:
                            b = r.read(1 << 20)
                            if not b:
                                break
                            fh.write(b)
            except urllib.error.HTTPError as exc:
                if not (exc.code == 416 and have):
                    raise
    got = os.path.getsize(part)
    if size is not None and got != int(size):
        raise IOError("size %d != expected %s for %s (kept %s to resume)" % (got, size, url, part))
    if check is not None:
        try:
            check(part)
        except Exception:
            os.replace(part, dst + ".bad")             # complete but wrong: never resumed, never renamed over dst
            raise
    os.replace(part, dst)
    return got


def _hash_check(md5=None, sha256=None):
    def check(p):
        for algo, want in (("md5", md5), ("sha256", sha256)):
            if want:
                got = file_hash(p, algo)
                if got != want:
                    raise IOError("%s %s != %s" % (algo, got, want))
    return check if (md5 or sha256) else None


def zenodo_files(record, opener=None):
    opener = opener or _urlopen
    with opener("https://zenodo.org/api/records/%s" % record) as r:
        meta = json.loads(r.read().decode("utf-8"))
    files = meta.get("files") or []
    if isinstance(files, dict):                     # newer API: {"entries": {...}}
        files = list((files.get("entries") or {}).values())
    out = []
    for f in files:
        key = f.get("key") or f.get("filename")
        links = f.get("links") or {}
        url = links.get("content") or links.get("self") or links.get("download") or \
            "https://zenodo.org/records/%s/files/%s?download=1" % (record, key)
        if url.endswith("/files/" + key):
            url += "/content"
        ck = f.get("checksum") or ""
        out.append(dict(key=key, size=f.get("size") or f.get("filesize"), md5=ck.split(":", 1)[1] if ck.startswith("md5:") else ck or None, url=url))
    return meta, out


def cmd_zenodo_get(argv, opener=None, fetch=None):
    ap = argparse.ArgumentParser(prog="reacquire.py zenodo-get")
    ap.add_argument("--record", action="append", required=True)
    ap.add_argument("--dest", required=True)
    ap.add_argument("--include", default=".")
    ap.add_argument("--state", default=None)
    a = ap.parse_args(argv)
    st = State(a.state or os.path.join(a.dest, ".reacquire_state"))
    done = st.done_units()
    rx = re.compile(a.include)
    bad = 0
    for rec in a.record:
        _, files = zenodo_files(rec, opener)
        chosen = [f for f in files if rx.search(f["key"])]
        report = dict(record=rec, n_files=len(chosen), files=[])
        for f in chosen:
            unit = "zenodo:%s/%s" % (rec, f["key"])
            dst = os.path.join(a.dest, f["key"])
            if unit in done and os.path.exists(dst) and os.path.getsize(dst) == done[unit].get("size"):
                report["files"].append(dict(key=f["key"], ok=True, skipped=True))
                continue
            try:
                if not (os.path.exists(dst) and f["size"] and os.path.getsize(dst) == int(f["size"])):
                    if fetch is None:
                        download(f["url"], dst, f["size"], check=_hash_check(md5=f["md5"]))
                    else:
                        fetch(f["url"], dst, f["size"])
                md5 = file_hash(dst, "md5")
                if f["md5"] and md5 != f["md5"]:
                    os.replace(dst, dst + ".bad")      # a full-size file with the wrong md5 must not block the next run
                    raise IOError("md5 %s != record %s (moved to %s.bad)" % (md5, f["md5"], dst))
                st.ok(unit, size=os.path.getsize(dst), md5=md5)
                report["files"].append(dict(key=f["key"], ok=True, md5=md5))
            except Exception as exc:      # noqa: BLE001  (one file failing is recorded; the rest continue)
                bad += 1
                st.fail(unit, exc)
                report["files"].append(dict(key=f["key"], ok=False, why=str(exc)[:300]))
        report["all_verified"] = all(x["ok"] for x in report["files"]) and bool(report["files"])
        with open(os.path.join(st.dir, "zenodo_%s.json" % rec), "w") as fh:
            json.dump(report, fh, indent=1)
        print("zenodo %s: %d files, %s" % (rec, len(chosen), "all verified" if report["all_verified"] else "NOT all verified"))
    return 1 if bad else 0


def cmd_http_get(argv, fetch=None):
    ap = argparse.ArgumentParser(prog="reacquire.py http-get")
    ap.add_argument("--url", required=True)
    ap.add_argument("--dest", required=True)
    ap.add_argument("--md5")
    ap.add_argument("--sha256")
    ap.add_argument("--bytes", type=int)
    ap.add_argument("--impersonate", action="store_true", help="curl_cffi with a Chrome TLS fingerprint")
    ap.add_argument("--state", default=None)
    a = ap.parse_args(argv)
    return http_get(a.url, a.dest, md5=a.md5, sha256=a.sha256, nbytes=a.bytes, impersonate=a.impersonate, state=a.state, fetch=fetch)


def http_get(url, dest, md5=None, sha256=None, nbytes=None, impersonate=False, state=None, fetch=None):
    st = State(state or os.path.join(os.path.dirname(os.path.abspath(dest)), ".reacquire_state"))
    unit = "http:" + url
    check = _hash_check(md5=md5, sha256=sha256)
    try:
        have = os.path.exists(dest) and (nbytes is None or os.path.getsize(dest) == nbytes)
        if have and nbytes is None and check is None:
            have = False                               # nothing to trust an existing file by: fetch again
        if have and check is not None:
            try:
                check(dest)                            # an existing complete copy is kept when it verifies
            except IOError:
                have = False
        if not have:
            if fetch is None:
                download(url, dest, nbytes, impersonate, check=check)
            else:
                fetch(url, dest, nbytes)
        info = dict(size=os.path.getsize(dest))
        for algo, want in (("md5", md5), ("sha256", sha256)):
            if want:
                got = file_hash(dest, algo)
                info[algo] = got
                if got != want:
                    raise IOError("%s %s != %s" % (algo, got, want))
        if nbytes and info["size"] != nbytes:
            raise IOError("size %d != %d" % (info["size"], nbytes))
        st.ok(unit, dest=dest, **info)
        print("verified", dest, json.dumps(info))
        return 0
    except Exception as exc:              # noqa: BLE001
        st.fail(unit, exc, dest=dest)
        print("FAILED", dest, exc)
        return 1


def cmd_github_zip(argv, opener=None):
    """The codeload zip of a GitHub repository's default branch (as tools/thoracic_xr_fetch.py fetched it), checked."""
    ap = argparse.ArgumentParser(prog="reacquire.py github-zip")
    ap.add_argument("--repo", required=True, help="OWNER/NAME")
    ap.add_argument("--dest", required=True)
    ap.add_argument("--branch", default=None, help="default: the repository's default branch from the GitHub API")
    ap.add_argument("--md5")
    ap.add_argument("--sha256")
    ap.add_argument("--bytes", type=int)
    ap.add_argument("--state", default=None)
    a = ap.parse_args(argv)
    br = a.branch
    if not br:
        with (opener or _urlopen)("https://api.github.com/repos/%s" % a.repo) as r:
            br = json.loads(r.read().decode("utf-8")).get("default_branch") or "master"
    url = "https://codeload.github.com/%s/zip/refs/heads/%s" % (a.repo, br)
    print("github-zip %s branch %s -> %s" % (a.repo, br, url))
    return http_get(url, a.dest, md5=a.md5, sha256=a.sha256, nbytes=a.bytes, state=a.state)


def cmd_hf_get(argv):
    ap = argparse.ArgumentParser(prog="reacquire.py hf-get")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--repo-type", default="dataset", choices=["dataset", "model", "space"])
    ap.add_argument("--revision", default=None)
    ap.add_argument("--include", default=None, help="glob, e.g. 'deepfluoro/*'")
    ap.add_argument("--dest", required=True)
    ap.add_argument("--state", default=None)
    a = ap.parse_args(argv)
    from huggingface_hub import HfApi, snapshot_download
    st = State(a.state or os.path.join(a.dest, ".reacquire_state"))
    api = HfApi()
    info = api.repo_info(a.repo, repo_type=a.repo_type, revision=a.revision)
    rev = getattr(info, "sha", None) or a.revision
    snapshot_download(a.repo, repo_type=a.repo_type, revision=rev, local_dir=a.dest,
                      allow_patterns=[a.include] if a.include else None)
    bad, n = 0, 0
    for f in api.list_repo_tree(a.repo, repo_type=a.repo_type, revision=rev, recursive=True, expand=True):
        path = getattr(f, "path", None)
        if path is None or not hasattr(f, "size") or (a.include and not fnmatch.fnmatch(path, a.include)):
            continue
        n += 1
        p = os.path.join(a.dest, path)
        lfs = getattr(f, "lfs", None)
        want_sha = (lfs.get("sha256") if isinstance(lfs, dict) else getattr(lfs, "sha256", None)) if lfs else None
        unit = "hf:%s@%s/%s" % (a.repo, rev, path)
        try:
            if not os.path.exists(p) or os.path.getsize(p) != f.size:
                raise IOError("missing or size differs")
            if want_sha and file_hash(p, "sha256") != want_sha:
                raise IOError("LFS sha256 differs")
            st.ok(unit, size=f.size, sha256=want_sha)
        except IOError as exc:
            bad += 1
            st.fail(unit, exc)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", a.repo)
    with open(os.path.join(st.dir, "hf_%s.json" % safe), "w") as fh:
        json.dump(dict(repo=a.repo, revision=rev, files=n, failed=bad, all_verified=bad == 0 and n > 0), fh, indent=1)
    print("hf %s@%s: %d files, %d failed" % (a.repo, rev, n, bad))
    return 1 if bad else 0


def cmd_nifti_check(argv):
    """Gzip integrity of every *_ct.nii.gz (the whole stream is read, so a truncated file fails), and, with nibabel,
    the CT's shape and affine against its label (<id>_label.nii.gz). Writes a JSON report; exit 1 on any failure."""
    ap = argparse.ArgumentParser(prog="reacquire.py nifti-check")
    ap.add_argument("--ct-dir", required=True)
    ap.add_argument("--label-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--atol", type=float, default=1e-3, help="affine tolerance (mm)")
    a = ap.parse_args(argv)
    try:
        import nibabel as nib
        import numpy as np
    except ImportError:
        nib = np = None
    rows, bad = [], []
    for f in sorted(os.listdir(a.ct_dir)):
        if not f.endswith("_ct.nii.gz"):
            continue
        cid = f[:-len("_ct.nii.gz")]
        ct = os.path.join(a.ct_dir, f)
        lab = os.path.join(a.label_dir, cid + "_label.nii.gz")
        row = dict(case=cid, gzip_ok=False, affine_ok=None, shape_ok=None)
        try:
            with gzip.open(ct, "rb") as fh:
                while fh.read(1 << 22):
                    pass
            row["gzip_ok"] = True
            if nib is not None and os.path.exists(lab):
                ci, li = nib.load(ct), nib.load(lab)
                row["shape_ok"] = tuple(ci.shape[:3]) == tuple(li.shape[:3])
                row["affine_ok"] = bool(np.allclose(ci.affine, li.affine, atol=a.atol))
            elif not os.path.exists(lab):
                row["why"] = "no label file"
        except Exception as exc:      # noqa: BLE001
            row["why"] = repr(exc)[:300]
        if not row["gzip_ok"] or row["shape_ok"] is False or row["affine_ok"] is False or row.get("why"):
            bad.append(cid)
        rows.append(row)
    rep = dict(ct_dir=a.ct_dir, label_dir=a.label_dir, n_checked=len(rows), n_bad=len(bad), bad=bad[:100],
               nibabel=nib is not None, rows=rows)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(rep, fh, indent=1)
    print("nifti-check: %d checked, %d bad%s" % (len(rows), len(bad), "" if nib is not None else " (nibabel absent: gzip only)"))
    return 1 if bad or not rows else 0


HELPERS = {"zenodo-get": cmd_zenodo_get, "http-get": cmd_http_get, "hf-get": cmd_hf_get, "github-zip": cmd_github_zip,
           "nifti-check": cmd_nifti_check}


# ------------------------------------------------------------------------------------------------ the driver
def print_source(src, env, out=None):
    rq = src.get("reacquire") or {}
    w = (out or sys.stdout).write
    w("\n=== %s  [%s / %s]  route=%s  mode=%s  access=%s\n" % (src["id"], src.get("kind"), src.get("status"), rq.get("route"),
                                                              rq.get("mode"), src.get("access")))
    w("    %s\n" % src.get("name", ""))
    w("    DEST=%s\n    STATE=%s\n    PY=%s\n" % (env["DEST"], env["STATE"], env["PY"]))
    if rq.get("covered_by"):
        w("    covered by: %s (re-acquiring that source re-acquires this one)\n" % rq["covered_by"])
    if rq.get("command"):
        w("  commands:\n")
        for c in rq["command"]:
            w("  $ %s\n" % resolve(c, env))
    for c in rq.get("chain") or []:
        w("  (rebuild the screen afterwards) $ %s\n" % resolve(c, env))
    if rq.get("equivalent"):
        w("  (equivalent repository wrapper) $ %s\n" % rq["equivalent"])
    if rq.get("verify"):
        w("  checks:\n")
        for chk in rq["verify"]:
            if chk.get("type") == "note":
                w("    - [manual] %s\n" % resolve(chk.get("text", ""), env))
            else:
                w("    - %s\n" % describe_check(chk, env))
    if rq.get("gated_steps"):
        w("  manual steps (never run by this driver):\n")
        for g in rq["gated_steps"]:
            w("    * %s\n" % resolve(g, env))


def sbatch_line(ids, mode, all_spec=None, here=None):
    here = here or HERE
    idspec = all_spec if all_spec else " ".join(ids)
    return ('cd "%s" && mkdir -p logs && sbatch -D "%s" --export=ALL,IDS="%s",MODE=%s reacquire.sbatch' % (here, here, idspec, mode))


ACQ_COLLECTION = re.compile(r"acquisition_fetch\.(?:sh|py)\s+\S+\s+--collection\s+(\S+)")


def overlapping(sel):
    """Runnable sources that would share one acquisition state folder (<root>/<collection>/fetch/)."""
    seen, clash = {}, []
    for e in sel:
        rq = e.get("reacquire") or {}
        if rq.get("mode") not in ("run", "submit"):
            continue
        for c in rq.get("command") or []:
            for coll in ACQ_COLLECTION.findall(c):
                if coll in seen and seen[coll] != e["id"]:
                    clash.append((coll, seen[coll], e["id"]))
                seen.setdefault(coll, e["id"])
    return clash


def run_source(src, env, do_cmds=True, resume=False):
    rq = src.get("reacquire") or {}
    st = State(env["STATE"])
    mode = rq.get("mode")
    if mode == "manual" and do_cmds:
        st.status(id=src["id"], status="manual_required", gated_steps=rq.get("gated_steps") or [],
                  covered_by=rq.get("covered_by"))
        print("%s: manual source; nothing run (steps written to %s)%s" % (
            src["id"], st.dir, ("; covered by " + rq["covered_by"]) if rq.get("covered_by") else ""))
        return 0
    rc_all = 0
    if do_cmds:
        script = ["#!/bin/bash", "set -euo pipefail"] + ["export %s=%s" % (k, shlex.quote(v)) for k, v in sorted(env.items())]
        for c in rq.get("command") or []:
            script.append(c)
        with open(os.path.join(st.dir, "commands.sh"), "w") as fh:
            fh.write("\n".join(script) + "\n")
        log = open(os.path.join(st.dir, "log.txt"), "a")
        full_env = dict(os.environ, **env)
        done = st.done_units()
        job = os.environ.get("SLURM_JOB_ID", "")
        for i, c in enumerate(rq.get("command") or []):
            unit = "cmd:%d" % i
            prev = done.get(unit)
            # a requeue keeps its SLURM_JOB_ID: a submit-mode command that already ran in this job is not submitted twice
            if prev and prev.get("command") == c and ((mode == "submit" and job and prev.get("job") == job) or resume):
                log.write("\n### %s skip %s (already ran in job %s)\n" % (time.strftime("%F %T"), unit, prev.get("job")))
                continue
            log.write("\n### %s $ %s\n" % (time.strftime("%F %T"), c))
            log.flush()
            rc = subprocess.call([os.environ.get("BASH_BIN", "bash"), "-c", "set -euo pipefail; " + c], env=full_env,
                                 stdout=log, stderr=subprocess.STDOUT)
            if rc == 0:
                st.ok(unit, command=c)
            else:
                st.fail(unit, "exit %d" % rc, command=c)
                rc_all = rc
                break
        log.close()
        if mode == "submit":
            st.status(id=src["id"], status="submitted" if rc_all == 0 else "submit_failed", rc=rc_all,
                      note="the work runs in the submitted job(s); run reacquire.py --verify %s after they end" % src["id"])
            print("%s: submitted (rc=%d); verify later" % (src["id"], rc_all))
            return rc_all
    results = [run_check(chk, env) for chk in rq.get("verify") or []]
    for r in results:
        unit = "check:%s:%s" % (r["type"], r.get("path", ""))
        if r["ok"] is True:
            st.ok(unit, got=r.get("got"))
        elif r["ok"] is False:
            st.fail(unit, "got %s, expected %s" % (json.dumps(r.get("got"))[:300], json.dumps(r.get("expect"))[:200]))
    failed = [r for r in results if r["ok"] is False]
    manual = [r for r in results if r["ok"] is None]
    status = "commands_failed" if rc_all else ("verify_failed" if failed else ("verified" if not manual else "verified_with_manual_checks"))
    st.status(id=src["id"], status=status, rc=rc_all, checks=results)
    print("%s: %s (%d checks, %d failed, %d manual)" % (src["id"], status, len(results), len(failed), len(manual)))
    return 1 if (rc_all or failed) else 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in HELPERS:
        rest = [x for x in argv[1:] if x != "--outside-slurm"]
        msg = refuse_unless_job("reacquire.py %s" % argv[0], "put the command in a source's commands, or in an sbatch --wrap",
                                outside_slurm="--outside-slurm" in argv[1:])
        if msg:
            print(msg)
            return 3
        return HELPERS[argv[0]](rest)
    ap = argparse.ArgumentParser(description="Re-acquire imaging sources listed in data_platform/sources.json (dry run by default).")
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--modes", nargs="*", default=None, help="with --all: only these modes (run submit manual)")
    ap.add_argument("--status", nargs="*", default=None, help="with --all: only sources with these status values")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--run", action="store_true", help="execute (inside a Slurm job only)")
    ap.add_argument("--verify", action="store_true", help="run only the checks")
    ap.add_argument("--resume", action="store_true", help="with --run: skip commands already recorded as done (any job)")
    ap.add_argument("--grid", action="store_true", help="dry run with the grid's HOME (%s) whatever this machine's is" % GRID_HOME)
    ap.add_argument("--sources", default=None)
    ap.add_argument("--state-root", default=None, help="write state under <dir>/<id> instead of the source folder's meta/")
    ap.add_argument("--outside-slurm", action="store_true", help="allow --run/--verify without SLURM_JOB_ID (tests, a workstation)")
    a = ap.parse_args(argv)
    doc = load_sources(a.sources)
    S = dict((e["id"], e) for e in doc["sources"])
    for e in doc["sources"]:
        for al in e.get("aliases") or []:
            S.setdefault(al, e)
    if a.list:
        for e in doc["sources"]:
            rq = e.get("reacquire") or {}
            mode = rq.get("mode") or ""
            if rq.get("covered_by"):
                mode += "->" + rq["covered_by"]
            print("%-42s %-20s %-22s %-14s %s" % (e["id"], mode, (rq.get("route") or "")[:22], e.get("status"), e.get("name", "")[:60]))
        return 0
    all_spec = None
    if a.all:
        sel = [e for e in doc["sources"] if (not a.modes or (e.get("reacquire") or {}).get("mode") in a.modes)
               and (not a.status or e.get("status") in a.status)]
        all_spec = "--all" + (" --modes " + " ".join(a.modes) if a.modes else "") + (" --status " + " ".join(a.status) if a.status else "")
    else:
        missing = [i for i in a.ids if i not in S]
        if missing:
            print("unknown source id(s): %s (see --list)" % ", ".join(missing))
            return 2
        sel = [S[i] for i in a.ids]
    if not sel:
        print("nothing selected (give ids or --all)")
        return 2
    clash = overlapping(sel)
    if clash:
        print("refusing: these runnable sources share one acquisition state folder and would fetch into it concurrently:")
        for coll, x, y in clash:
            print("  --collection %s: %s and %s" % (coll, x, y))
        return 2
    base = env_defaults(GRID_HOME if a.grid else None)
    if a.run or a.verify:
        msg = refuse_unless_job("--run/--verify", sbatch_line([e["id"] for e in sel], "--run" if a.run else "--verify", all_spec),
                                outside_slurm=a.outside_slurm)
        if msg:
            print(msg)
            return 3
        rc = 0
        for e in sel:
            rc |= run_source(e, source_env(e, base, a.state_root), do_cmds=a.run, resume=a.resume)
        return 1 if rc else 0
    for e in sel:
        print_source(e, source_env(e, base, a.state_root))
    print("\n(dry run: nothing executed; %d sources%s. To run:\n  %s)" % (
        len(sel), "" if a.grid else "; paths use this machine's HOME, add --grid for the grid's",
        sbatch_line([e["id"] for e in sel], "--run", all_spec, here=(base["DP"] + "/reacquire") if a.grid else None)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
