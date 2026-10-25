"""Fetch tables of one Redivis dataset into a landing, through the official Redivis client.

Stanford AIMI's sets (OL3I, CheXpert Plus) are served by Redivis: each set's files sit behind
file-index tables, whose rows name every file with its size and md5, and its tabular data behind
data tables. The client's directory download skips a file already on disk at its listed size and
md5 and fetches the rest, so a job requeued on preemption carries on where it stopped. The listed
bytes are summed and written to a manifest before any download, and the run refuses when they
exceed --max-gb, so a set larger than the owner chose never starts. Runs inside a Slurm job
(grid/platform-fetch.sbatch, route redivis) with REDIVIS_API_TOKEN in its environment; standard
library plus the redivis package.

With --size it downloads nothing and is the route's size reader for the owner's size rule
(grid/size-rule.sh, issue #163): its last line is "<total bytes> <bytes still to land> <how>", as
grid/fetch_size.py prints for the other routes. The total is the listed files' bytes and each CSV
table's export, which Redivis makes and states the size of before any byte of it is downloaded.
The client writes a file it fetches again in place of what is there, so a file adds no more than
its listed size less what is on disk at its landing path; a CSV export is counted whole, since its
name and its parts are known only once it is downloaded. A client that fails is one line and exit 2,
naming the kind of failure and never its text, which could carry an address.

    python grid/redivis_fetch.py --dest <data>/chexpert_plus/raw \
        --manifest <data>/chexpert_plus/meta --max-gb 3000 \
        --files aimi.chexpert_plus:5yyj:v1_0.png_train:s6cj \
        --csv aimi.chexpert_plus:5yyj:v1_0.df_chexpert_plus_240401:bavj
    python grid/redivis_fetch.py --size --dest ... --manifest ... --files ... --csv ...
"""

import argparse
import sys
from pathlib import Path

REFUSED_FOR_SIZE = 3
NO_ANSWER = 2


class NoSize(Exception):
    """Redivis lists or states no exact size for something the run would land."""


def folder_of(reference):
    """The landing folder of a table: its name without the dataset or the version suffix."""
    table = reference.split(".")[-1]
    return table.split(":")[0]


def over_cap(total_bytes, max_gb):
    """Whether the listed bytes pass the cap; no cap when max_gb is 0."""
    return max_gb > 0 and total_bytes > max_gb * 10**9


def write_manifest(path, rows):
    """One line per file: its table's folder, its path, size and md5 as Redivis lists them."""
    with open(path, "w", encoding="utf-8") as out:
        out.write("folder\tpath\tsize\tmd5_base64\n")
        for folder, name, size, md5 in rows:
            out.write(f"{folder}\t{name}\t{size}\t{md5}\n")


def landing_of(directory, listed):
    """Where the client lands a listed file inside its table's folder: its path within the
    directory, as Directory.download makes it."""
    return (Path("/") / listed.path).relative_to(getattr(directory, "path", None) or Path("/"))


def listed_files(redivis, references):
    """Each file table's directory, the manifest rows of its files and, for each, its size and
    where it lands under the destination."""
    directories, rows, landings = [], [], []
    for reference in references:
        directory = redivis.table(reference).to_directory()
        files = directory.list(mode="files", recursive=True)
        folder = folder_of(reference)
        for f in files:
            rows.append((folder, str(f.path), f.size or 0, f.properties.get("md5_hash", "")))
            landings.append((Path(folder) / landing_of(directory, f), f.size))
        directories.append((reference, folder, directory, len(files)))
    return directories, rows, landings


def still_to_land(dest, landings):
    """What the files add to the volume at most: each one's listed size less what its landing
    path holds, since the client skips a whole one and writes any other in place of what is there."""
    need = 0
    for path, size in landings:
        if not isinstance(size, int) or size < 0:
            raise NoSize("redivis lists a file with no size")
        target = dest / path
        have = target.stat().st_size if target.is_file() else 0
        need += max(size - have, 0)
    return need


def client_internals():
    """The redivis client's own export request and export job, which Table.download uses."""
    from redivis.classes.Export import Export
    from redivis.common.api_request import make_request

    return make_request, Export


def export_bytes(redivis, reference):
    """The bytes of a data table's CSV export, asked for as Table.download asks for it and waited
    on until Redivis has made it; nothing of it is downloaded."""
    make_request, export_class = client_internals()
    table = redivis.table(reference)
    answer = make_request(method="POST", path=f"{table.uri}/exports", payload={"format": "csv"})
    export = export_class(answer["id"], table=table, properties=answer)
    export.wait_for_finish(progress=False)
    size = export.properties.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise NoSize("redivis stated no size for a csv export")
    return size


def size_line(args, redivis, rows, landings):
    """The size reader's line for the files listed and the CSV tables asked for."""
    files_need = still_to_land(args.dest, landings)
    csv_total = sum(export_bytes(redivis, reference) for reference in args.csv)
    total = sum(size for _, _, size, _ in rows) + csv_total
    how = f"{len(rows)} files and {len(args.csv)} csv exports listed by redivis"
    return f"{total} {files_need + csv_total} {how}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dest", required=True, type=Path)
    parser.add_argument(
        "--manifest", required=True, type=Path, help="the folder the manifest goes in"
    )
    parser.add_argument(
        "--files", action="append", default=[], help="a file-index table's qualified reference"
    )
    parser.add_argument(
        "--csv",
        action="append",
        default=[],
        help="a data table's qualified reference, saved as CSV",
    )
    parser.add_argument(
        "--max-gb",
        type=float,
        default=0,
        help="refuse before downloading above this many GB; 0 is no cap",
    )
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument(
        "--size",
        action="store_true",
        help="download nothing; print the size rule's line, the exact size and what is still to land",
    )
    args = parser.parse_args(argv)

    import redivis

    if args.size:
        try:
            return size_only(args, redivis)
        except NoSize as reason:
            print(f"no exact size; {reason}")
            return REFUSED_FOR_SIZE
        except Exception as failure:  # the client's own errors are many kinds; none is printed
            print(f"the source did not answer; the redivis client failed with {type(failure).__name__}")
            return NO_ANSWER
    directories, rows, _ = listed_files(redivis, args.files)
    total = sum(size for _, _, size, _ in rows)
    args.manifest.mkdir(parents=True, exist_ok=True)
    write_manifest(args.manifest / "redivis_files.tsv", rows)
    for reference, folder, _, count in directories:
        print(f"{reference}: {count} files into {folder}/")
    print(f"listed: {len(rows)} files, {total} bytes ({total / 10**9:.1f} GB)")
    if over_cap(total, args.max_gb):
        print(
            f"refusing: {total / 10**9:.1f} GB listed exceeds the cap of {args.max_gb:g} GB;"
            " nothing downloaded"
        )
        return REFUSED_FOR_SIZE
    if args.list_only:
        return 0
    for reference, folder, directory, _ in directories:
        # overwrite=True: a file whose size and md5 already match is skipped, and a partial
        # one is fetched again
        directory.download(args.dest / folder, overwrite=True, progress=False)
        print(f"{reference}: downloaded")
    for reference in args.csv:
        target = args.dest / folder_of(reference)
        target.mkdir(parents=True, exist_ok=True)
        redivis.table(reference).download(str(target), format="csv", overwrite=True, progress=False)
        print(f"{reference}: saved as CSV")
    return 0


def size_only(args, redivis):
    """The size reader: the listing and its manifest, the owner's cap, then the line."""
    _, rows, landings = listed_files(redivis, args.files)
    total = sum(size for _, _, size, _ in rows)
    args.manifest.mkdir(parents=True, exist_ok=True)
    write_manifest(args.manifest / "redivis_files.tsv", rows)
    if over_cap(total, args.max_gb):
        # In whole words and figures, as the size rule's refusal line keeps them (plain_words).
        print(
            f"the files redivis lists come to {-(-total // 10**9)} gb over the cap of"
            f" {args.max_gb:g} gb the source line names"
        )
        return REFUSED_FOR_SIZE
    print(size_line(args, redivis, rows, landings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
