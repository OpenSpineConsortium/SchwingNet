"""The exact size of what one fetch will land, read from its source before a byte is downloaded.

The owner's size rule of 2026-10-23 (issue #160): every dataset chosen for the lab volume knows how
many bytes it needs, a fetch whose need would pass the room left under the volume's CephFS quota
is refused before it starts, and none is stopped part-way for space, so each lands whole or not
at all (grid/size-rule.sh decides, grid/platform-fetch.sbatch asks). This tool reads that size
the way each route lands its files:

    hf            reacquire.py hf-get: the files of a Hugging Face repository whose path matches
                  the --include glob (huggingface_hub's allow_patterns), landed as they are
    acq hf, acq zenodo
                  spinesurg-ct-nnunet's acquisition_fetch.py: the files whose path matches the
                  --include regular expression; a zip or a tar is unpacked into raw/ and then
                  deleted, so it needs its members' bytes, read from a zip's central directory by
                  HTTP range requests or bounded by a plain tar's own size, and room for the
                  largest archive while it unpacks; a compressed tar states no unpacked size, and
                  tarfile.open decompresses whatever it is given, so a .tar is taken as plain only
                  when its first block, read by a range request, shows a tar and no compressor
    acq s3        acquisition_fetch.py s3: every object under the bucket's prefix, since s5cmd
                  syncs the whole prefix and --include narrows only what is verified afterwards
    idc           acquisition_fetch.py idc: the series_bytes column of grid/idc_manifest.py's
                  manifest, idc-index's series_size_MB in units of 10**6 bytes
    zenodo-token  grid/zenodo_fetch.py: the files of a record read with the owner's token, as
                  they are
    gdown         gdown 6.4.2 on one Drive file: the length a one-byte range request on Drive's
                  download address states, with the confirmation form Drive shows for a file it
                  cannot scan read once, as gdown reads it; gdown downloads into a temporary file
                  beside the output and moves it over whatever is there, so a resend needs it all
    kaggle, kaggle-dataset
                  the kaggle 2.2.5 client's competitions and datasets download: the address
                  Kaggle's API redirects the client's own request to, asked with the token and
                  never followed with it, then the length a one-byte range request on that storage
                  states; the client writes <competition>.<ext> or <slug>.zip and resumes or
                  rewrites a shorter file in place

It prints one line, "<total bytes> <bytes still to land> <how>", and exits 0. The bytes still to
land leave out what an earlier try verified or landed whole, so a resend asks only for the rest.
A source whose size it cannot state exactly is one line and exit 3; a source that does not
answer, one line and exit 2. Runs in a Slurm job, in the grid's acq environment, on the standard
library alone; a token comes from the environment (HF_TOKEN, ZENODO_TOKEN, KAGGLE_API_TOKEN), is
sent only to its own host and is never printed. The Redivis route is sized by grid/redivis_fetch.py
--size, in the environment that holds the Redivis client.

    python grid/fetch_size.py hf --repo benjamindkilleen/fluoroseg --dest <landing>/raw
    python grid/fetch_size.py acq zenodo --collection zenodo_lumos --record 18173664 \
        --include . --data-root <data>
    python grid/fetch_size.py idc --manifest <landing>/meta/idc_nlst.csv --landing <landing>
    python grid/fetch_size.py gdown --id 1lJqVIuVFbdc9Bcmj17ac_cha-gW827Q6 --dest <landing>/raw/gdown_<date>
    python grid/fetch_size.py kaggle-dataset --dataset salmankey/scoliosis-yolov5-annotated-spine-x-ray-dataset \
        --dest <landing>/raw
"""

import argparse
import csv
import fnmatch
import http.client
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

HUB = "https://huggingface.co"
ZENODO = "https://zenodo.org/api/records"
NO_ANSWER = 2
NO_SIZE = 3
HUB_KINDS = {"dataset": "datasets", "model": "models", "space": "spaces"}
# What acquisition_fetch.py's unpack opens, by the file name's ending as it reads it; any other
# file is moved into raw/ as it is.
COMPRESSED_TARS = (".tar.gz", ".tgz")
PLAIN_TAR = ".tar"
ZIP = ".zip"
# What a compressed stream begins with, for the compressors tarfile.open reads on its own.
COMPRESSOR_MAGIC = (
    (b"\x1f\x8b", "gzip"),
    (b"BZh", "bzip2"),
    (b"\xfd7zXZ\x00", "xz"),
    (b"\x28\xb5\x2f\xfd", "zstd"),
)
TAR_BLOCK = 512
USTAR_AT = 257
# Drive's download address as gdown 6.4.2 reaches it, with the confirmation Drive asks for a file
# it cannot scan for viruses given up front; the form on its page, read where it still asks.
DRIVE = "https://drive.usercontent.google.com/download"
KAGGLE_API = "https://api.kaggle.com/v1"
# The most of a page sent in place of a file that is read for its form.
PAGE_LIMIT = 1 << 20
# A length of more digits than the size rule counts is no length (grid/size-rule.sh, is_count).
CONTENT_RANGE = re.compile(r"^bytes 0-0/([0-9]{1,18})$")
LENGTH = re.compile(r"^[0-9]{1,18}$")


class NoSize(Exception):
    """The source answered, and no exact size of what would land follows from its answer."""


class NoAnswer(Exception):
    """The source did not answer, or answered with an error."""


class NotRanged(NoSize):
    """A server that answered a range request with the whole of what it serves: the length it
    stated for it, where it stated one plainly, the first part of the page it sent, where it
    sent a page, and the address it answered from, after every redirect, where the fetch says."""

    def __init__(self, length=None, page=None, address=None):
        super().__init__("the file server answers no range request")
        self.length, self.page, self.address = length, page, address


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse a redirect of a read that carries a token, so the token never reaches another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirected", headers, fp)


def get(url, token="", byte_range=None, timeout=120):
    """One HTTP GET: its body, no more than the range's bytes when one is asked, and its headers."""
    request = urllib.request.Request(url, headers={"User-Agent": "schwingnet-fetch-size"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    if byte_range:
        request.add_header("Range", f"bytes={byte_range[0]}-{byte_range[1]}")
    opener = urllib.request.build_opener(NoRedirect) if token else urllib.request.build_opener()
    try:
        with opener.open(request, timeout=timeout) as answer:
            if byte_range and answer.status != 206:
                # Reading on would download the whole file to learn what its end says; a page is
                # read only as far as its form, which is all a page in place of a file holds.
                raise NotRanged(stated_length(answer.headers), first_page(answer), answer.geturl())
            limit = byte_range[1] - byte_range[0] + 1 if byte_range else -1
            headers = answer.headers
            # The address the answer came from, after every redirect, kept beside its headers,
            # since a client names what it lands by that address (size_kaggle).
            headers.address = answer.geturl()
            return answer.read(limit), headers
    except urllib.error.HTTPError as error:
        raise NoAnswer(f"http {error.code}") from None
    except http.client.HTTPException:
        # A body cut short or a status line that is none: the answer is no answer, and a reader
        # that let it through would end the whole run in place of one set.
        raise NoAnswer("an answer cut short") from None
    except (urllib.error.URLError, OSError):
        raise NoAnswer("no connection") from None


def stated_length(headers):
    """The length an answer states for its whole body, where it states it plainly: no encoding
    between the bytes sent and the bytes that land, as urllib and the fetchers write them."""
    encoding = (headers.get("Content-Encoding") or "identity").strip().lower()
    length = (headers.get("Content-Length") or "").strip()
    return int(length) if encoding == "identity" and LENGTH.match(length) else None


def first_page(answer):
    """The first part of a page an answer sends in place of a file, else None."""
    kind = (answer.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    return answer.read(PAGE_LIMIT) if kind == "text/html" else None


def ranged_answer(url, fetch=get, token=""):
    """(total, address): the exact size of the file at an address, the total a one-byte range
    request states, or the length an answer that ignores the range states for the whole file, and
    the address the answer came from after every redirect, the one asked where the fetch says
    nothing of it. A page sent in place of the file is no size of it."""
    try:
        _, headers = fetch(url, token, (0, 0))
    except NotRanged as answer:
        if answer.page is None and answer.length is not None:
            return answer.length, answer.address or url
        raise
    match = CONTENT_RANGE.match((headers.get("Content-Range") or "").strip())
    if not match:
        raise NoSize("the file server states no length beside its range")
    return int(match.group(1)), getattr(headers, "address", None) or url


def first_byte_total(url, fetch=get, token=""):
    """The exact size of the file at an address (ranged_answer)."""
    return ranged_answer(url, fetch, token)[0]


def next_page(link):
    """The address of the next page a Link header names, or None."""
    match = re.search(r'<([^>]+)>;\s*rel="next"', link or "")
    return match.group(1) if match else None


def hub_files(repo, repo_type, token, fetch=get):
    """Every file of a Hub repository as (path, bytes), page by page as the tree API gives them."""
    url = f"{HUB}/api/{HUB_KINDS[repo_type]}/{repo}/tree/main?recursive=true"
    files = []
    while url:
        if not url.startswith(HUB + "/"):
            raise NoAnswer("the hub named a next page on another host")
        body, headers = fetch(url, token)
        for entry in json.loads(body):
            if entry.get("type") == "file":
                lfs = entry.get("lfs") or {}
                files.append((entry["path"], int(lfs.get("size") or entry.get("size") or 0)))
        url = next_page(headers.get("Link", ""))
    return files


def hub_glob(pattern):
    """huggingface_hub's reading of an allow pattern: one ending in / takes everything under it."""
    if pattern and pattern.endswith("/"):
        return pattern + "*"
    return pattern


def whole_at(path, size):
    """Whether a file of exactly this size is already at the path, which a fetch keeps."""
    return path.is_file() and path.stat().st_size == size


def size_hf(args, fetch=get):
    """hf-get's files, as they land: the repository's files its glob takes."""
    token = os.environ.get("HF_TOKEN", "")
    pattern = hub_glob(args.include)
    files = [
        (path, size)
        for path, size in hub_files(args.repo, args.repo_type, token, fetch)
        if pattern is None or fnmatch.fnmatch(path, pattern)
    ]
    if not files:
        raise NoSize("no file of the repository matches the include pattern")
    total = sum(size for _, size in files)
    landed = sum(size for path, size in files if whole_at(args.dest / path, size))
    return total, total - landed, f"{len(files)} files listed by the hub"


class RemoteFile(io.RawIOBase):
    """A file on a server, read by range requests as far as zipfile asks for it."""

    def __init__(self, url, size, fetch):
        super().__init__()
        self.url, self.size, self.fetch, self.position = url, size, fetch, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        start = {io.SEEK_SET: 0, io.SEEK_CUR: self.position, io.SEEK_END: self.size}[whence]
        if start + offset < 0:
            raise OSError("a seek before the start of the file")
        self.position = start + offset
        return self.position

    def read(self, count=-1):
        end = self.size if count is None or count < 0 else min(self.size, self.position + count)
        if end <= self.position:
            return b""
        body, _ = self.fetch(self.url, "", (self.position, end - 1))
        self.position += len(body)
        return body


def zip_members_bytes(url, size, fetch=get):
    """The bytes a zip's members unpack to, read from its central directory alone."""
    try:
        with zipfile.ZipFile(RemoteFile(url, size, fetch)) as archive:
            return sum(member.file_size for member in archive.infolist() if not member.is_dir())
    except (zipfile.BadZipFile, EOFError, OSError):
        raise NoSize("a zip whose central directory cannot be read") from None


def check_plain_tar(url, size, fetch=get):
    """Refuse a file named .tar that is not a plain tar: acquisition_fetch.py opens it with
    tarfile.open's default mode, which decompresses a gzip, bzip2, xz or zstd stream it finds, and
    then its members may pass its own size."""
    if size == 0:
        return
    head, _ = fetch(url, "", (0, min(size, TAR_BLOCK) - 1))
    for magic, compressor in COMPRESSOR_MAGIC:
        if head.startswith(magic):
            raise NoSize(f"a .tar compressed with {compressor} states no unpacked size")
    if head[USTAR_AT : USTAR_AT + 5] != b"ustar":
        raise NoSize("a .tar whose first block is no ustar header")


def unpacked(name, size, url, fetch=get):
    """What one listed file becomes in raw/ under acquisition_fetch.py's unpack: (bytes, archive)"""
    if name.endswith(COMPRESSED_TARS):
        raise NoSize("a compressed tar states no unpacked size")
    if name.endswith(PLAIN_TAR):
        check_plain_tar(url, size, fetch)
        # A plain tar's members, headers and padding aside, are no larger than the tar itself, save
        # a sparse member, which unpacks larger than it is stored, and a hard link tarfile copies
        # where it cannot link; neither is read here.
        return size, True
    if name.endswith(ZIP):
        return zip_members_bytes(url, size, fetch), True
    return size, False


def verified_units(landing):
    """The units an earlier try verified, from acquisition_fetch.py's fetch/verified.jsonl."""
    path = landing / "fetch" / "verified.jsonl"
    if not path.exists():
        return set()
    lines = path.read_text(encoding="utf-8").splitlines()
    return {json.loads(line)["unit"] for line in lines if line.strip()}


def acq_listing(args, fetch=get):
    """The files acquisition_fetch.py would fetch, as (unit, name, bytes, address)."""
    wanted = re.compile(args.include)
    if args.route == "hf":
        return [
            (
                path,
                path,
                size,
                f"{HUB}/datasets/{args.repo}/resolve/main/{urllib.parse.quote(path)}",
            )
            for path, size in hub_files(args.repo, "dataset", "", fetch)
            if wanted.search(path)
        ]
    if args.route == "zenodo":
        rows = []
        for record in args.record:
            body, _ = fetch(f"{ZENODO}/{record}", "")
            for entry in json.loads(body).get("files", []):
                if wanted.search(entry["key"]):
                    rows.append(
                        (
                            f"{record}/{entry['key']}",
                            entry["key"],
                            int(entry["size"]),
                            entry["links"]["self"],
                        )
                    )
        return rows
    # s5cmd syncs every object under the prefix whatever --include says; the pattern only narrows
    # what acquisition_fetch.py verifies afterwards, so every object lands and counts.
    return [(key, key, size, "") for key, size in s3_objects(args.bucket, fetch)]


def s3_objects(bucket_url, fetch=get):
    """Every object under an s3://bucket/prefix as (its key under the prefix, bytes)."""
    parsed = urllib.parse.urlparse(bucket_url)
    prefix = parsed.path.strip("/")
    prefix = prefix + "/" if prefix else ""
    objects, token = [], None
    while True:
        query = {"list-type": "2", "prefix": prefix}
        if token:
            query["continuation-token"] = token
        body, _ = fetch(
            f"https://{parsed.netloc}.s3.amazonaws.com/?{urllib.parse.urlencode(query)}", ""
        )
        fields = {}
        for element in ElementTree.fromstring(body):
            tag = element.tag.rsplit("}", 1)[-1]
            if tag == "Contents":
                parts = {child.tag.rsplit("}", 1)[-1]: child.text for child in element}
                objects.append((parts["Key"][len(prefix) :], int(parts["Size"])))
            else:
                fields[tag] = element.text
        token = fields.get("NextContinuationToken")
        if fields.get("IsTruncated") != "true" or not token:
            return objects


def size_acq(args, fetch=get):
    """acquisition_fetch.py's files as they end in raw/, and room for the largest archive."""
    if args.route not in ("hf", "zenodo", "s3"):
        raise NoSize(f"no size reader for the {args.route} route of the acquisition fetcher")
    landing = (args.root or args.data_root) / args.collection
    rows = acq_listing(args, fetch)
    if not rows and args.route == "s3":
        raise NoSize("the bucket lists no object under its prefix")
    if not rows:
        raise NoSize("no file of the source matches the include pattern")
    if args.route == "s3":
        total = sum(size for _, _, size, _ in rows)
        landed = sum(size for _, key, size, _ in rows if whole_at(landing / "raw" / key, size))
        return total, total - landed, f"{len(rows)} objects listed by s3"
    done = verified_units(landing)
    total = need = 0
    largest = largest_left = 0
    zips = 0
    for unit, name, size, address in rows:
        lands, archive = unpacked(name, size, address, fetch)
        zips += name.endswith(ZIP)
        kept = size if archive and args.keep_archives else 0
        total += lands + kept
        need += 0 if unit in done else lands + kept
        if archive and not args.keep_archives:
            # An archive is unpacked while it is still there and deleted after, one at a time,
            # so the fetch needs room for the largest of them on top of what it lands.
            largest = max(largest, size)
            largest_left = largest_left if unit in done else max(largest_left, size)
    source = "the hub" if args.route == "hf" else "zenodo"
    how = f"{len(rows)} files listed by {source} with {zips} zips read"
    return total + largest, need + largest_left, how


def size_idc(args):
    """The manifest's series at idc-index's own byte counts, less the series already verified."""
    with open(args.manifest, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise NoSize("the manifest lists no series")
    if "series_bytes" not in rows[0]:
        raise NoSize("the manifest has no series bytes column")
    try:
        sizes = [(row["SeriesInstanceUID"], int(row["series_bytes"])) for row in rows]
    except ValueError:
        raise NoSize("a series of the manifest has no byte count") from None
    done = verified_units(args.landing)
    total = sum(size for _, size in sizes)
    need = sum(size for series, size in sizes if series not in done)
    return total, need, f"{len(rows)} series listed by idc"


def size_zenodo_token(args, fetch=get):
    """zenodo_fetch.py's files, as they land: the record's files, read with the owner's token."""
    body, _ = fetch(f"{ZENODO}/{args.record}", os.environ.get("ZENODO_TOKEN", ""))
    listed = json.loads(body).get("files", [])
    files = [(entry["key"], int(entry.get("size") or 0)) for entry in listed]
    if not files:
        raise NoSize("the record lists no file")
    total = sum(size for _, size in files)
    landed = sum(size for key, size in files if whole_at(args.dest / key, size))
    return total, total - landed, f"{len(files)} files listed by zenodo"


def drive_address(file_id):
    """Drive's download address for one file, its confirmation given."""
    return f"{DRIVE}?{urllib.parse.urlencode({'id': file_id, 'export': 'download', 'confirm': 't'})}"


class DriveForm(HTMLParser):
    """The form Drive's page shows where it cannot scan a file for viruses, as gdown reads it: the
    form download-form, its action and its hidden inputs."""

    def __init__(self):
        super().__init__()
        self.action, self.fields, self.inside = None, {}, False

    def handle_starttag(self, tag, attrs):
        named = dict(attrs)
        if tag == "form" and named.get("id") == "download-form":
            self.action, self.inside = named.get("action") or "", True
        elif tag == "input" and self.inside and named.get("type") == "hidden" and named.get("name"):
            self.fields[named["name"]] = named.get("value") or ""

    def handle_endtag(self, tag):
        if tag == "form":
            self.inside = False


def confirmed_address(page):
    """The address the confirmation form on Drive's page sends to, on Drive's own download host."""
    form = DriveForm()
    form.feed(page.decode("utf-8", "replace"))
    if not form.action or not form.action.startswith(DRIVE + "?") and form.action != DRIVE:
        raise NoSize("drive answered with a page and no download form")
    parts = urllib.parse.urlsplit(form.action.replace("&amp;", "&"))
    query = dict(urllib.parse.parse_qsl(parts.query))
    query.update(form.fields)
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def size_gdown(args, fetch=get):
    """gdown's one file: what Drive states for it. gdown run without --continue writes the whole
    file into a temporary one beside the output before it moves it over whatever is there, so all
    of it is still to land however much a try before left."""
    address = drive_address(args.id)
    try:
        total = first_byte_total(address, fetch)
    except NotRanged as answer:
        if answer.page is None:
            raise
        total = first_byte_total(confirmed_address(answer.page), fetch)
    return total, total, "the drive file answers"


def post_for_location(url, token, payload, timeout=120):
    """One JSON request to Kaggle's API with the token, which it answers with a redirect to the
    file's storage: the address the redirect names, never followed, so the token reaches the API's
    own host alone, as the client's session drops it when it follows the redirect itself."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "User-Agent": "schwingnet-fetch-size",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout):
            raise NoSize("the api answered with no redirect to the file")
    except urllib.error.HTTPError as error:
        location = error.headers.get("Location") if 300 <= error.code < 400 else None
        if not location:
            raise NoAnswer(f"http {error.code}") from None
        return urllib.parse.urljoin(url, location)
    except (urllib.error.URLError, OSError):
        raise NoAnswer("no connection") from None


def kaggle_storage(service, payload, post):
    """Where Kaggle's API sends the client for a download, asked with the token the job loaded."""
    token = os.environ.get("KAGGLE_API_TOKEN", "")
    if not token:
        raise NoSize("no kaggle token in the environment, so the api cannot be asked")
    return post(f"{KAGGLE_API}/{service}", token, payload)


def kaggle_need(path, total):
    """What the Kaggle client still writes into PATH: it skips a whole file newer than the
    storage's, resumes a shorter one it can prove is the same object and otherwise rewrites it in
    place, so no more than the file less what is there."""
    have = path.stat().st_size if path.is_file() else 0
    return max(total - have, 0)


def size_kaggle(args, fetch=get, post=post_for_location):
    """kaggle competitions download -c: the competition's archive, landed as
    <competition>.<what follows the last dot of the storage address>, as the client names it."""
    location = kaggle_storage(
        "competitions.CompetitionApiService/DownloadDataFiles",
        {"competitionName": args.competition},
        post,
    )
    # Named by the address the storage answers from after every redirect, as the client names it
    # from the answer it followed, never by the API's first redirect alone.
    total, address = ranged_answer(location, fetch)
    name = f"{args.competition}.{address.split('?')[0].split('.')[-1]}"
    return total, kaggle_need(args.dest / name, total), "the archive kaggle's storage states"


def kaggle_dataset_request(dataset):
    """The client's request for OWNER/SLUG or OWNER/SLUG/VERSION, and the name it lands as."""
    parts = dataset.split("/")
    if len(parts) not in (2, 3) or not all(parts):
        raise NoSize("a kaggle dataset named without its owner")
    payload = {"ownerSlug": parts[0], "datasetSlug": parts[1]}
    if len(parts) == 3:
        if not parts[2].isdigit() or not parts[2].isascii():
            raise NoSize("a kaggle dataset version that is no number")
        payload["datasetVersionNumber"] = int(parts[2])
    return payload, f"{parts[1]}.zip"


def size_kaggle_dataset(args, fetch=get, post=post_for_location):
    """kaggle datasets download -d: the dataset's archive, landed as <slug>.zip and never unpacked."""
    payload, name = kaggle_dataset_request(args.dataset)
    location = kaggle_storage("datasets.DatasetApiService/DownloadDataset", payload, post)
    total = first_byte_total(location, fetch)
    return total, kaggle_need(args.dest / name, total), "the archive kaggle's storage states"


def parsed(route, argv):
    """The arguments a route's fetcher takes that bear on the size; the rest are left to it."""
    parser = argparse.ArgumentParser(prog=f"fetch_size.py {route}")
    if route == "hf":
        parser.add_argument("--repo", required=True)
        parser.add_argument("--repo-type", default="dataset", choices=sorted(HUB_KINDS))
        parser.add_argument("--include", default=None)
        parser.add_argument("--dest", required=True, type=Path)
    elif route == "acq":
        parser.add_argument("route")
        parser.add_argument("--collection", required=True)
        parser.add_argument("--root", type=Path, default=None)
        parser.add_argument("--data-root", type=Path, required=True)
        parser.add_argument("--repo")
        parser.add_argument("--record", nargs="*", default=[])
        parser.add_argument("--bucket")
        parser.add_argument("--include", default=".")
        parser.add_argument("--keep-archives", action="store_true")
    elif route == "idc":
        parser.add_argument("--manifest", required=True, type=Path)
        parser.add_argument("--landing", required=True, type=Path)
    elif route == "gdown":
        parser.add_argument("--id", required=True)
        parser.add_argument("--dest", required=True, type=Path)
    elif route == "kaggle":
        parser.add_argument("--competition", required=True)
        parser.add_argument("--dest", required=True, type=Path)
    elif route == "kaggle-dataset":
        parser.add_argument("--dataset", required=True)
        parser.add_argument("--dest", required=True, type=Path)
    else:
        parser.add_argument("--record", required=True)
        parser.add_argument("--dest", required=True, type=Path)
    known, _ = parser.parse_known_args(argv)
    return known


SIZERS = {
    "hf": lambda args, fetch, post: size_hf(args, fetch),
    "acq": lambda args, fetch, post: size_acq(args, fetch),
    "idc": lambda args, fetch, post: size_idc(args),
    "zenodo-token": lambda args, fetch, post: size_zenodo_token(args, fetch),
    "gdown": lambda args, fetch, post: size_gdown(args, fetch),
    "kaggle": size_kaggle,
    "kaggle-dataset": size_kaggle_dataset,
}


def main(argv=None, fetch=get, post=post_for_location):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in SIZERS:
        print(f"no exact size; no size reader for this route; one of {' '.join(SIZERS)}")
        return NO_SIZE
    try:
        total, need, how = SIZERS[argv[0]](parsed(argv[0], argv[1:]), fetch, post)
    except NoSize as reason:
        print(f"no exact size; {reason}")
        return NO_SIZE
    except NoAnswer as reason:
        print(f"the source did not answer; {reason}")
        return NO_ANSWER
    except (ValueError, KeyError, TypeError, ElementTree.ParseError):
        print("the source did not answer; an answer that is not a listing")
        return NO_ANSWER
    print(f"{total} {need} {how}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
