"""Build the private Gold Tier 3 CT page from page-data.json, the store and the reader views.

Writes OUT/index.html, OUT/views/<id>.png (front and side side by side, one per bench study,
<id>r.png for a repaired mask) and OUT/<store>-page-copy.zip.json: the store with its grid locations and
the anomaly route's notes taken out, since the page is shared more widely than the records it is built from,
zipped and carried as base64 in JSON, since an artifact serves no archive type.
"""
import argparse
import base64
import hashlib
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile

from PIL import Image

SQLJS = "https://cdn.jsdelivr.net/npm/sql.js@1.10.3/dist/sql-asm.js"
CLASS_ORDER = ["l6_twelve_ribs", "l6_thirteen_ribs", "four_lumbar_twelve_ribs", "eleven_ribs", "thirteen_ribs",
               "asymmetric_ribs", "labelling_error", "open", "look", "repaired", "not_whole"]
GAP = 12
GRID_ROOT_NOTE = "(on the grid; see members.json)"
ROUTE_WORDING = {
    "class_reason": (("held out of the SPINEPS to FleXray route", "held out of the anomaly route"),
                     ("left to train by the route", "not held out")),
    "decided_by": (("docs/research/spineps-anomaly-route.md", "the anomaly route's note"), (" to train", " in")),
}
NEVER_PUBLISHED = ("/rs/", "go2432", "${HOME}", "$DATA_ROOT", "FleXray", "flexray", "SPINEPS", "spineps")
BACKGROUND = (17, 17, 17)


def side_by_side(front_path, side_path, out_path):
    front, side = Image.open(front_path).convert("RGB"), Image.open(side_path).convert("RGB")
    height = max(front.height, side.height)
    canvas = Image.new("RGB", (front.width + GAP + side.width, height), BACKGROUND)
    canvas.paste(front, (0, 0))
    canvas.paste(side, (front.width + GAP, 0))
    canvas.save(out_path, optimize=True)


def bench_items(rows, views, rep_views, outdir):
    os.makedirs(os.path.join(outdir, "views"), exist_ok=True)
    bench = []
    for row in rows:
        member, native = row["item"].split(":", 1)
        front = os.path.join(views, native + "-front.png")
        if member != "enhance_pet" or not os.path.exists(front):
            continue
        side_by_side(front, os.path.join(views, native + "-side.png"), os.path.join(outdir, "views", native + ".png"))
        entry = {"item": row["item"], "view": "views/%s.png" % native}
        rep_front = os.path.join(rep_views, native + "-front.png") if rep_views else ""
        if rep_front and os.path.exists(rep_front):
            side_by_side(rep_front, os.path.join(rep_views, native + "-side.png"),
                         os.path.join(outdir, "views", native + "r.png"))
            entry["repaired_view"] = "views/%sr.png" % native
        bench.append((CLASS_ORDER.index(row["class"]) if row["class"] in CLASS_ORDER else 99, row["item"], entry))
    return [entry for _, _, entry in sorted(bench, key=lambda t: (t[0], t[1]))]


def leaks(blob):
    return [word for word in NEVER_PUBLISHED if word.encode() in blob]


def page_copy(store, workdir):
    """The store as the page publishes it: grid locations and the route's notes out, then vacuumed."""
    copy = os.path.join(workdir, "copy.sqlite")
    shutil.copyfile(store, copy)
    db = sqlite3.connect(copy)
    db.execute("UPDATE source SET grid_root = ? WHERE grid_root IS NOT NULL", (GRID_ROOT_NOTE,))
    db.execute("UPDATE item SET ct_location = NULL")
    db.execute("UPDATE mask SET location = NULL")
    for column, pairs in ROUTE_WORDING.items():
        for old, new in pairs:
            db.execute(f"UPDATE anomaly SET {column} = replace({column}, ?, ?)", (old, new))
    db.commit()
    db.execute("VACUUM")
    db.close()
    raw = open(copy, "rb").read()
    if leaks(raw):
        sys.exit("the page's copy of the store still holds %s" % ", ".join(leaks(raw)))
    return raw


def packed_store(store, outdir):
    canonical = open(store, "rb").read()
    with tempfile.TemporaryDirectory() as workdir:
        raw = page_copy(store, workdir)
    stem = os.path.basename(store).rsplit(".sqlite", 1)[0] + "-page-copy"
    entry = zipfile.ZipInfo(stem + ".sqlite", date_time=(1980, 1, 1, 0, 0, 0))
    entry.external_attr = 0o644 << 16
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(entry, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    packed = buffer.getvalue()
    carrier = {"name": stem + ".zip", "encoding": "base64", "bytes": len(packed),
               "sha256": hashlib.sha256(packed).hexdigest(), "data": base64.b64encode(packed).decode("ascii")}
    with open(os.path.join(outdir, stem + ".zip.json"), "w") as handle:
        json.dump(carrier, handle, separators=(",", ":"))
    return {"file": stem + ".zip.json", "zip_name": stem + ".zip", "name": os.path.basename(store),
            "sha256": hashlib.sha256(canonical).hexdigest(),
            "published_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "zip_bytes": len(packed)}


def inline_json(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True).replace("</", "<\\/")


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--page-data", required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--views", required=True)
    parser.add_argument("--rep-views")
    parser.add_argument("--template", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--expect-bench", type=int)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    data = json.load(open(args.page_data))
    columns = data["studies"]["columns"]
    rows = [dict(zip(columns, r)) for r in data["studies"]["rows"]]
    os.makedirs(args.out, exist_ok=True)
    bench = bench_items(rows, args.views, args.rep_views, args.out)
    if args.expect_bench is not None and len(bench) != args.expect_bench:
        sys.exit("expected %d bench studies, drew %d" % (args.expect_bench, len(bench)))
    build = {"bench": bench, "store": packed_store(args.store, args.out), "sqljs": SQLJS, "source": args.source}
    page = open(args.template).read()
    page = page.replace("__PAGE_DATA__", inline_json(data)).replace("__BUILD_DATA__", inline_json(build))
    if leaks(page.encode()):
        sys.exit("the page still holds %s" % ", ".join(leaks(page.encode())))
    with open(os.path.join(args.out, "index.html"), "w") as handle:
        handle.write(page)
    print("%d bench studies, %d repaired views, store %s published as %s (%d bytes zipped, sha256 %s)" % (
        len(bench), sum(1 for b in bench if "repaired_view" in b), build["store"]["name"], build["store"]["file"],
        build["store"]["zip_bytes"], build["store"]["published_sha256"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
