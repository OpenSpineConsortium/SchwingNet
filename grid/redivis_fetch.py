"""Fetch tables of one Redivis dataset into a landing, through the official Redivis client.

Stanford AIMI's sets (OL3I, CheXpert Plus) are served by Redivis: each set's files sit behind
file-index tables, whose rows name every file with its size and md5, and its tabular data behind
data tables. The client's directory download skips a file already on disk at its listed size and
md5 and fetches the rest, so a job requeued on preemption carries on where it stopped. The listed
bytes are summed and written to a manifest before any download, and the run refuses when they
exceed --max-gb, so a set larger than the owner chose never starts. Runs inside a Slurm job
(grid/platform-fetch.sbatch, route redivis) with REDIVIS_API_TOKEN in its environment; standard
library plus the redivis package.

    python grid/redivis_fetch.py --dest <data>/chexpert_plus/raw \
        --manifest <data>/chexpert_plus/meta --max-gb 3000 \
        --files aimi.chexpert_plus:5yyj:v1_0.png_train:s6cj \
        --csv aimi.chexpert_plus:5yyj:v1_0.df_chexpert_plus_240401:bavj
"""

import argparse
import sys
from pathlib import Path

REFUSED_FOR_SIZE = 3


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


def listed_files(redivis, references):
    """Each file table's directory and the manifest rows of its files."""
    directories, rows = [], []
    for reference in references:
        directory = redivis.table(reference).to_directory()
        files = directory.list(mode="files", recursive=True)
        folder = folder_of(reference)
        for f in files:
            rows.append((folder, str(f.path), f.size or 0, f.properties.get("md5_hash", "")))
        directories.append((reference, folder, directory, len(files)))
    return directories, rows


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
    args = parser.parse_args(argv)

    import redivis

    directories, rows = listed_files(redivis, args.files)
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


if __name__ == "__main__":
    sys.exit(main())
