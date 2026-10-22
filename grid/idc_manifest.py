"""Write the census manifest of one IDC collection from idc-index, for acquisition_fetch.py idc.

spinesurg-ct-nnunet's tools/acquisition_fetch.py takes its IDC series from a manifest CSV with the
columns collection, PatientID, SeriesInstanceUID and instanceCount, which tools/acquisition_census.py
there writes from inputs that are not on local disk (aa3_meta.csv, fdg_ct_series.json). This
script writes the same columns for one collection straight from idc-index's own table, every CT
series of the collection, so a tier-2 collection can be fetched by its id with no census; the
census's refusals (localizers, thick slices, reformats) are applied later by the screen, as the
cards say. Runs in the grid's acq environment inside a Slurm job; standard library plus idc-index.

    python grid/idc_manifest.py --collection spine_mets_ct_seg --out <data>/idc_spine_mets_ct_seg/meta/idc_spine_mets_ct_seg.csv
"""

import argparse
import csv
import sys
from pathlib import Path


def rows_of(table, collection):
    """The CT series of the collection as manifest rows, in series order, with the stated size."""
    chosen = table[(table["collection_id"] == collection) & (table["Modality"] == "CT")]
    rows = [{"collection": collection, "PatientID": r["PatientID"], "SeriesInstanceUID": r["SeriesInstanceUID"],
             "instanceCount": int(r["instanceCount"])} for _, r in chosen.iterrows()]
    size_mb = float(chosen["series_size_MB"].sum()) if "series_size_MB" in chosen else 0.0
    return sorted(rows, key=lambda r: r["SeriesInstanceUID"]), size_mb


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--collection", required=True, help="the IDC collection_id")
    parser.add_argument("--out", required=True, help="the manifest CSV to write")
    args = parser.parse_args(argv)
    from idc_index import index  # the acq environment's; imported here so --help needs nothing
    client = index.IDCClient()
    rows, size_mb = rows_of(client.index, args.collection)
    if not rows:
        print(f"idc_manifest: no CT series of {args.collection} in IDC {client.get_idc_version()}", file=sys.stderr)
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["collection", "PatientID", "SeriesInstanceUID", "instanceCount"])
        writer.writeheader()
        writer.writerows(rows)
    patients = len({r["PatientID"] for r in rows})
    print(f"idc_manifest: {args.collection}: {len(rows)} CT series of {patients} patients,"
          f" {size_mb / 1024:.1f} GB stated by IDC {client.get_idc_version()}, written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
