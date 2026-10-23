"""Write the census manifest of one IDC collection from idc-index, for acquisition_fetch.py idc.

spinesurg-ct-nnunet's tools/acquisition_fetch.py takes its IDC series from a manifest CSV with the
columns collection, PatientID, SeriesInstanceUID and instanceCount, which its
tools/acquisition_census.py writes from inputs that are not on local disk (aa3_meta.csv,
fdg_ct_series.json). This script writes the same columns for one collection straight from
idc-index's own table, every CT series of the collection, so a tier-2 collection can be fetched by
its id with no census; the census's refusals (localizers, thick slices, reformats) are applied
later by the screen, as the cards say. Each row also carries series_bytes, the series' size by
idc-index, which grid/fetch_size.py sums for the size rule (issue #160); acquisition_fetch.py reads
its four columns by name and leaves the fifth. Runs in the grid's acq environment inside a Slurm
job; standard library plus idc-index.

    python grid/idc_manifest.py --collection spine_mets_ct_seg \
        --out <data>/idc_spine_mets_ct_seg/meta/idc_spine_mets_ct_seg.csv
"""

import argparse
import csv
import sys
from pathlib import Path

FIELDS = ["collection", "PatientID", "SeriesInstanceUID", "instanceCount", "series_bytes"]


def series_bytes(size_mb):
    """A series' bytes from idc-index's series_size_MB, or "" where the index gives none.

    series_size_MB counts units of 10**6 bytes to six decimals, so it is a byte count exactly: on
    2026-10-23 IDC's bucket listed NLST series at 89168188, 470942 and 589880 bytes where the index
    said 89.168188, 0.470942 and 0.58988. A series with no size gets none, and grid/fetch_size.py
    then refuses the collection rather than guess."""
    if size_mb is None or size_mb != size_mb:
        return ""
    return round(float(size_mb) * 10**6)


def rows_of(series, collection):
    """The collection's CT series as manifest rows, in series order, each with its bytes."""
    rows = [
        {
            "collection": collection,
            "PatientID": record["PatientID"],
            "SeriesInstanceUID": record["SeriesInstanceUID"],
            "instanceCount": int(record["instanceCount"]),
            "series_bytes": series_bytes(record.get("series_size_MB")),
        }
        for record in series
        if record.get("collection_id") == collection and record.get("Modality") == "CT"
    ]
    return sorted(rows, key=lambda row: row["SeriesInstanceUID"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--collection", required=True, help="the IDC collection_id")
    parser.add_argument("--out", required=True, help="the manifest CSV to write")
    args = parser.parse_args(argv)
    from idc_index import index  # the acq environment's; imported here so --help needs nothing

    client = index.IDCClient()
    table = client.index
    chosen = table[(table["collection_id"] == args.collection) & (table["Modality"] == "CT")]
    rows = rows_of(chosen.to_dict("records"), args.collection)
    if not rows:
        version = client.get_idc_version()
        print(f"idc_manifest: no CT series of {args.collection} in IDC {version}", file=sys.stderr)
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    patients = len({r["PatientID"] for r in rows})
    sized = [r["series_bytes"] for r in rows if r["series_bytes"] != ""]
    print(
        f"idc_manifest: {args.collection}: {len(rows)} CT series of {patients} patients,"
        f" {sum(sized) / 10**9:.1f} GB by IDC {client.get_idc_version()}"
        f" ({len(rows) - len(sized)} series with no size), written to {out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
