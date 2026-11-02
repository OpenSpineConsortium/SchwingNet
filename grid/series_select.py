"""Write the series manifest of one named selection of TCIA series, for acquisition_fetch.py idc or nbia.

The open paired sets of the paired CT and X-ray survey of 2026-11-01 (spine-datasets #183 to #186)
are a few thousand series out of collections of hundreds of gigabytes, so each is fetched as a list
of series rather than a collection. A selection is a rule, written here once, never a list of
patients, so no identifier is committed: the rule is applied on the grid to the catalogue as it
stands (idc-index's table for the IDC selections, NBIA's getSeries for CMB, whose films IDC v24
does not hold: 12 of NBIA's 130 CMB-MML CR series) and to what the grid already holds, and the
manifest it writes stays in the landing's meta folder.

    ctc_localizers       CT COLONOGRAPHY's CT localizers (Topogram, SCOUT, SURVIEW): the
                         projections of the abdomen and pelvis taken with each CT
    ctc_masked           the CT COLONOGRAPHY series CTSpine1K's COLONOG vertebra masks were drawn
                         on, matched by the NBIA folder names of its metadata/path.csv (patient,
                         series number and the last five characters of the series UID); for
                         grid/idc_headers.py, which reads their headers and not their pixels
    sbu_abdominal_films  COVID-19-NY-SBU's abdominal CR and DX films, and the CT localizers, of
                         the patients whose held CT is an abdomen and pelvis study
    cmb_xa_frames        every XA series of CMB-MML and CMB-AML, and the CT series of those
                         patients the grid does not hold yet
    cmb_mml_radiographs  every CR and DX series of CMB-MML, and the CT series of those patients
                         the grid does not hold yet

The manifest's columns are acquisition_fetch.py's four (collection, PatientID, SeriesInstanceUID,
instanceCount), then series_bytes, which grid/fetch_size.py idc sums for the size rule (idc-index's
series_size_MB in units of 10**6 bytes, or NBIA's FileSize), and series_aws_url, the IDC bucket
prefix grid/idc_headers.py lists (empty for NBIA rows). `size` prints what the nbia route needs
for the size rule: the manifest's bytes still to land and room for the largest series' zip while
acquisition_fetch.py unpacks it. Runs in the grid's acq environment inside a Slurm job; standard
library, plus idc-index for the IDC selections.

    python grid/series_select.py ctc_localizers --out <landing>/meta/ctc_localizers.csv
    python grid/series_select.py ctc_masked --labels <data>/ctspine1k --out <landing>/meta/ctc_masked.csv
    python grid/series_select.py sbu_abdominal_films --held <data>/idc/raw/covid_19_ny_sbu --out ...
    python grid/series_select.py cmb_xa_frames --held <data>/idc/raw/cmb_mml --out ...
    python grid/series_select.py size --manifest <csv> --landing <landing>
"""

import argparse
import csv
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

FIELDS = ["collection", "PatientID", "SeriesInstanceUID", "instanceCount", "series_bytes", "series_aws_url"]
NBIA = "https://services.cancerimagingarchive.net/nbia-api/services/v1/getSeries"
# A CT localizer by its series description, as the scanners of these collections name it: Siemens
# Topogram (and "AP Top", "APtop"), GE SCOUT, Philips SURVIEW, a plain LOCALIZER. idc-index gives
# no ImageType, so the name is what is read; on idc-index 24 this takes CT COLONOGRAPHY's 1,548
# localizer-named series of 724 patients, which NBIA's getSeries counted the same on 2026-11-01,
# and four "AP Top" ones.
LOCALIZER = re.compile(r"topo|scout|surview|locali[sz]er|\bap ?top\b", re.IGNORECASE)
# An abdominal film by its study description at Stony Brook: FLAT PLATE OF ABDOMEN PORTABLE, ABD
# SERIES FLAT AND ERECT PORTABLE, ABDOMEN SUPINE KUB, ABD UPRT VIEWONLY.
ABDOMINAL_FILM = re.compile(r"abdomen|abd series|abd uprt|\bkub\b", re.IGNORECASE)
FILMS = ("CR", "DX")
# NBIA's folder name for a series, as the TCIA Data Retriever writes it and CTSpine1K's path.csv
# keeps it: "<SeriesNumber>-<SeriesDescription>-<last five characters of SeriesInstanceUID>", with
# no description and its dash where the series has none (43 of the 784 COLONOG lines).
SERIES_FOLDER = re.compile(r"^(?P<number>-?[0-9.]+)-(?:(?P<description>.*)-)?(?P<tail>.{5})$")


def abdomen_and_pelvis(description):
    """Whether a CT study's description names both the abdomen and the pelvis."""
    text = description or ""
    return bool(re.search(r"abd", text, re.IGNORECASE) and re.search(r"pel", text, re.IGNORECASE))


def localizers(series, collection):
    """The collection's CT series whose description names a localizer."""
    return [s for s in series if s.get("collection_id") == collection and s.get("Modality") == "CT"
            and LOCALIZER.search(s.get("SeriesDescription") or "")]


def masked_keys(path_lines, labelled):
    """(PatientID, series number, UID tail) for each path.csv line whose patient has a mask file."""
    keys = set()
    for line in path_lines:
        parts = line.strip().split("/")
        if len(parts) != 3 or parts[0] not in labelled:
            continue
        match = SERIES_FOLDER.match(parts[2])
        if match:
            keys.add((parts[0], float(match["number"]), match["tail"]))
    return keys


def masked_series(series, keys, collection="ct_colonography"):
    """The collection's series that a key of masked_keys names, and the keys no series answers."""
    chosen, found = [], set()
    for s in series:
        if s.get("collection_id") != collection:
            continue
        try:
            number = float(s.get("SeriesNumber"))
        except (TypeError, ValueError):
            continue
        key = (s.get("PatientID"), number, (s.get("SeriesInstanceUID") or "")[-5:])
        if key in keys:
            chosen.append(s)
            found.add(key)
    return chosen, keys - found


def sbu_abdominal(series, held, collection="covid_19_ny_sbu"):
    """The abdominal films and CT localizers of the patients whose held CT is an abdomen and pelvis study."""
    mine = [s for s in series if s.get("collection_id") == collection]
    patients = {s["PatientID"] for s in mine
                if s.get("SeriesInstanceUID") in held and abdomen_and_pelvis(s.get("StudyDescription"))}
    films = [s for s in mine if s.get("Modality") in FILMS and s["PatientID"] in patients
             and ABDOMINAL_FILM.search(s.get("StudyDescription") or "")]
    with_film = {s["PatientID"] for s in films}
    scouts = [s for s in localizers(mine, collection) if s["PatientID"] in with_film]
    return films + scouts


def cmb_with_ct(series, modalities, held):
    """The series of the given modalities, and the CT series of their patients the grid does not hold."""
    picked = [s for s in series if s.get("Modality") in modalities]
    patients = {(s["collection_id"], s["PatientID"]) for s in picked}
    cts = [s for s in series if s.get("Modality") == "CT" and (s["collection_id"], s["PatientID"]) in patients
           and s.get("SeriesInstanceUID") not in held]
    return picked + cts


def series_bytes(size_mb):
    """idc-index's series_size_MB as bytes (units of 10**6 bytes to six decimals), "" where none."""
    if size_mb is None or size_mb != size_mb:
        return ""
    return round(float(size_mb) * 10**6)


def idc_row(s):
    return {"collection": s["collection_id"], "PatientID": s["PatientID"],
            "SeriesInstanceUID": s["SeriesInstanceUID"], "instanceCount": int(s["instanceCount"]),
            "series_bytes": series_bytes(s.get("series_size_MB")), "series_aws_url": s.get("series_aws_url") or ""}


def nbia_series(collection, fetch=None):
    """NBIA's getSeries for one collection, each row given idc-index's column names."""
    url = NBIA + "?" + urllib.parse.urlencode({"Collection": collection})
    if fetch is None:
        with urllib.request.urlopen(url, timeout=300) as answer:
            rows = json.load(answer)
    else:
        rows = fetch(url)
    return [{"collection_id": collection.lower().replace("-", "_"), "PatientID": r["PatientID"],
             "SeriesInstanceUID": r["SeriesInstanceUID"], "Modality": r.get("Modality"),
             "instanceCount": int(r["ImageCount"]), "file_size": int(r["FileSize"]),
             "SeriesDescription": r.get("SeriesDescription")} for r in rows]


def nbia_row(s):
    return {"collection": s["collection_id"], "PatientID": s["PatientID"],
            "SeriesInstanceUID": s["SeriesInstanceUID"], "instanceCount": s["instanceCount"],
            "series_bytes": s["file_size"], "series_aws_url": ""}


def held_series(folder):
    """The series UIDs a held IDC landing holds, one folder per series under one per patient."""
    root = Path(folder)
    return {series.name for patient in root.iterdir() if patient.is_dir()
            for series in patient.iterdir() if series.is_dir()}


def idc_table():
    from idc_index import index  # the acq environment's; imported here so tests and --help need nothing

    client = index.IDCClient()
    return client.index.to_dict("records"), client.get_idc_version()


def select(name, args):
    """The manifest rows of one selection, and a line saying where they came from."""
    if name.startswith("cmb_"):
        series = nbia_series("CMB-MML") + nbia_series("CMB-AML")
        held = held_series(args.held) if args.held else set()
        wanted = ("XA",) if name == "cmb_xa_frames" else FILMS
        if name == "cmb_mml_radiographs":
            series = [s for s in series if s["collection_id"] == "cmb_mml"]
        return [nbia_row(s) for s in cmb_with_ct(series, wanted, held)], "NBIA getSeries"
    series, version = idc_table()
    if name == "ctc_localizers":
        chosen = localizers(series, "ct_colonography")
    elif name == "ctc_masked":
        labels = Path(args.labels)
        labelled = {p.name[: -len("_seg.nii.gz")] for p in (labels / "raw_data" / "labels" / "COLONOG").iterdir()
                    if p.name.endswith("_seg.nii.gz")}
        lines = (labels / "metadata" / "path.csv").read_text(encoding="utf-8").splitlines()
        keys = masked_keys(lines, labelled)
        chosen, unmatched = masked_series(series, keys)
        print(f"series_select: {len(labelled)} COLONOG masks, {len(keys)} path.csv series, "
              f"{len(unmatched)} matched no series of idc-index", file=sys.stderr)
    elif name == "sbu_abdominal_films":
        chosen = sbu_abdominal(series, held_series(args.held))
    else:
        raise SystemExit(f"series_select: no selection {name}")
    return [idc_row(s) for s in chosen], f"idc-index {version}"


def manifest_rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def verified(landing):
    path = Path(landing) / "fetch" / "verified.jsonl"
    if not path.exists():
        return set()
    return {json.loads(line)["unit"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


ZIP_BYTES_PER_MEMBER = 1024


def nbia_need(rows, done):
    """'<total> <need> <how>' for the nbia route: every series' bytes, and room for the largest zip.

    acquisition_fetch.py nbia downloads each series as one zip into the landing's fetch/tmp,
    unpacks it and deletes it, one series at a time, so beside the DICOM files the landing holds
    at most one zip: its members' bytes and, at most, a kilobyte of headers for each member."""
    def zip_room(r):
        return int(r["series_bytes"]) + ZIP_BYTES_PER_MEMBER * int(r["instanceCount"])

    left = [r for r in rows if r["SeriesInstanceUID"] not in done]
    total = sum(int(r["series_bytes"]) for r in rows) + max((zip_room(r) for r in rows), default=0)
    need = sum(int(r["series_bytes"]) for r in left) + max((zip_room(r) for r in left), default=0)
    return f"{total} {need} {len(rows)} series listed by NBIA with room for the largest zip"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("selection", help="a selection named above, or size")
    parser.add_argument("--out", help="the manifest CSV to write")
    parser.add_argument("--held", help="a held IDC landing whose series are not fetched again")
    parser.add_argument("--labels", help="the CTSpine1K folder (raw_data/labels/COLONOG, metadata/path.csv)")
    parser.add_argument("--manifest", help="size: the manifest to size")
    parser.add_argument("--landing", help="size: the landing whose fetch/verified.jsonl names what is done")
    args = parser.parse_args(argv)
    if args.selection == "size":
        rows = manifest_rows(args.manifest)
        if not rows or any(not str(r["series_bytes"]).isdigit() for r in rows):
            print("no exact size; a series of the manifest has no byte count")
            return 3
        print(nbia_need(rows, verified(args.landing)))
        return 0
    rows, origin = select(args.selection, args)
    if not rows:
        print(f"series_select: {args.selection} chose no series from {origin}", file=sys.stderr)
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["collection"], r["PatientID"], r["SeriesInstanceUID"])))
    patients = len({(r["collection"], r["PatientID"]) for r in rows})
    sized = [int(r["series_bytes"]) for r in rows if r["series_bytes"] != ""]
    print(f"series_select: {args.selection}: {len(rows)} series of {patients} patients, {sum(sized)} bytes"
          f" by {origin} ({len(rows) - len(sized)} series with no size), written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
