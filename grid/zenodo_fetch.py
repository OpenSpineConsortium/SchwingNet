"""Fetch the files of one Zenodo record into a landing, with the owner's token where the record
asks for a sign-in.

A record whose authors approved the owner's access request (MAGIC-CT, record 18389015) opens only
to that account: the acq route's zenodo fetch reads public records alone, so this tool reads the
record's file list through Zenodo's API with ZENODO_TOKEN from the environment, writes the
manifest (name, size, md5 and address as the record lists them) before any download, refuses when
the listed bytes exceed --max-gb, and fetches each file through curl with the token in a config
file only this process can read, never on a command line, resuming a partial file and skipping a
file already on disk at the record's md5. A file whose bytes end up at another md5 is set aside
under a dated name, never deleted, so the next run fetches it afresh. Runs inside a Slurm job
(grid/platform-fetch.sbatch, route zenodo-token); standard library and curl only.

    ZENODO_TOKEN=... python3 grid/zenodo_fetch.py --record 18389015 \
        --dest <data>/zenodo_magic_ct/raw --manifest <data>/zenodo_magic_ct/meta --max-gb 50
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

API = "https://zenodo.org/api/records"
REFUSED_FOR_SIZE = 3
MISMATCH = 4


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse a redirect of the record read, so the token never travels to another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, f"redirected to {newurl}", headers, fp)


def read_record(record, token, timeout=120):
    """The record's JSON from Zenodo's API, read with the token when there is one."""
    request = urllib.request.Request(f"{API}/{record}", headers={"Accept": "application/json"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(request, timeout=timeout) as answer:
        return json.load(answer)


def listed_files(record_json):
    """Each file of the record as (name, size, md5, address); a checksum of another kind is kept
    with its prefix so the mismatch shows rather than passes."""
    rows = []
    for entry in record_json.get("files", []):
        checksum = entry.get("checksum", "")
        md5 = checksum[4:] if checksum.startswith("md5:") else checksum
        address = entry.get("links", {}).get("self", "")
        rows.append((entry["key"], int(entry.get("size") or 0), md5, address))
    return rows


def over_cap(total_bytes, max_gb):
    """Whether the listed bytes pass the cap; no cap when max_gb is 0."""
    return max_gb > 0 and total_bytes > max_gb * 10**9


def write_manifest(path, rows):
    """One line per file: name, size, md5 and address, as the record lists them."""
    with open(path, "w", encoding="utf-8") as out:
        out.write("name\tsize\tmd5\turl\n")
        for name, size, md5, address in rows:
            out.write(f"{name}\t{size}\t{md5}\t{address}\n")


def md5_of(path):
    digest = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def curl_config(address, target, token):
    """The lines of a curl config: the address, the output, resume, follow redirects (curl drops
    the Authorization header on a redirect to another host), fail on an HTTP error."""
    lines = [f'url = "{address}"', f'output = "{target}"', "continue-at = -", "location", "fail"]
    if token:
        lines.append(f'header = "Authorization: Bearer {token}"')
    return "\n".join(lines) + "\n"


def run_curl(address, target, token):
    """curl through a config file in memory-backed storage where there is one, mode 0600,
    removed afterwards; the token never appears in a process list."""
    folder = "/dev/shm" if os.path.isdir("/dev/shm") else None
    fd, cfg = tempfile.mkstemp(prefix="zenodo_", suffix=".curl", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(curl_config(address, target, token))
        return subprocess.run(["curl", "-sS", "-K", cfg], check=False).returncode
    finally:
        os.unlink(cfg)


def fetch_file(name, size, md5, address, dest, token, curl=run_curl):
    """One file into dest: skipped when already there at the record's md5, else fetched and
    checked; a mismatch is set aside under a dated name. Returns 'kept', 'fetched' or 'mismatch'."""
    target = dest / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size == size and md5_of(target) == md5:
        return "kept"
    rc = curl(address, str(target), token)
    if rc != 0:
        return f"curl exit {rc}"
    if md5_of(target) == md5:
        return "fetched"
    target.rename(target.with_name(f"{name}.mismatch-{time.strftime('%F')}"))
    return "mismatch"


def main(argv=None, read=read_record, curl=run_curl):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", required=True, help="the Zenodo record number")
    parser.add_argument("--dest", required=True, type=Path)
    parser.add_argument(
        "--manifest", required=True, type=Path, help="the folder the manifest goes in"
    )
    parser.add_argument(
        "--max-gb",
        type=float,
        default=0,
        help="refuse before downloading above this many GB; 0 is no cap",
    )
    parser.add_argument("--list-only", action="store_true")
    args = parser.parse_args(argv)
    token = os.environ.get("ZENODO_TOKEN", "")

    rows = listed_files(read(args.record, token))
    total = sum(size for _, size, _, _ in rows)
    args.manifest.mkdir(parents=True, exist_ok=True)
    write_manifest(args.manifest / "zenodo_files.tsv", rows)
    print(f"record {args.record}: {len(rows)} files, {total} bytes ({total / 10**9:.1f} GB)")
    if over_cap(total, args.max_gb):
        print(
            f"refusing: {total / 10**9:.1f} GB listed exceeds the cap of {args.max_gb:g} GB;"
            " nothing downloaded"
        )
        return REFUSED_FOR_SIZE
    if args.list_only:
        return 0
    failed = 0
    for name, size, md5, address in rows:
        outcome = fetch_file(name, size, md5, address, args.dest, token, curl)
        print(f"{name}: {outcome}")
        failed += outcome not in ("kept", "fetched")
    print(f"{len(rows) - failed} of {len(rows)} files on disk at the record's md5")
    return MISMATCH if failed else 0


if __name__ == "__main__":
    sys.exit(main())
