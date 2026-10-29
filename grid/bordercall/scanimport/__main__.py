"""The command line: python -m scanimport <command> ... (the package docstring lists them)."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import List, Optional

from . import SEVEN
from . import column as C

XR_VIEWS = ("ap", "pa", "lateral")


def finish_directory(out: str, argv: List[str], inputs: dict) -> None:
    """Rewrite the directory's tables and manifest from every column it holds."""
    from . import tiers as T
    cols = C.read_columns(out)
    T.annotate(cols)
    C.write_tables(out, cols)
    counts = T.write(out, T.person_tiers(cols))
    C.write_manifest(out, ["python", "-m", "scanimport"] + argv, inputs, {"tiers": counts})


def cmd_ingest_ct(a, argv) -> None:
    from . import volume as V
    col = V.ingest(a.labels, a.scheme, a.study, a.source, a.annotation, a.made_by or a.scheme,
                   a.subject, a.subregion, a.label_map)
    path = C.write_column(col, a.out)
    inputs = C.digests(a.labels)
    for extra in (a.subregion, a.label_map):
        if extra:
            inputs.update(C.digests(extra))
    finish_directory(a.out, argv, inputs)
    report(col, path)


def cmd_ingest_xr(a, argv) -> None:
    from . import radiograph as R
    col = R.ingest(a.xr, a.study, a.source, a.annotation, a.subject, a.anterior, a.magnification,
                   a.magnification_sd)
    path = C.write_column(col, a.out)
    finish_directory(a.out, argv, {k: v for p in a.xr for k, v in C.digests(p).items()})
    report(col, path)


def nifti_sidecar(path: str) -> Optional[str]:
    """The dcm2niix sidecar that readers.sidecar_covariates reads beside a NIfTI, found by the
    reader's own rule (readers.sidecar_path), where there is one: its values become the study's
    covariates, so it is an input like the volume."""
    from . import readers as RD
    low = path.lower()
    if os.path.isdir(path) or not (low.endswith(".nii") or low.endswith(".nii.gz")):
        return None
    side = RD.sidecar_path(path)
    return side if os.path.isfile(side) else None


def cmd_ingest_raw_ct(a, argv) -> None:
    from . import intensity as I
    col = I.ingest(a.volume, a.study, a.source, a.subject, a.series, fit_edges=not a.half_maximum_only)
    path = C.write_column(col, a.out)
    inputs = C.digests(a.volume)
    side = nifti_sidecar(a.volume)
    if side:
        inputs.update(C.digests(side))
    finish_directory(a.out, argv, inputs)
    report(col, path)


def cmd_ingest_image(a, argv) -> None:
    """Every file that changes the column is hashed: the image, its corners, FleXray's arrays and
    the label_names.json that named their channels, given or found beside them."""
    from . import film as F
    col = F.ingest_image(a.image, a.study, a.source, a.annotation, corners=a.corners, flexray=a.flexray,
                         flexray_names=a.flexray_names, mask_content=a.mask_content, view=a.view,
                         subject_id=a.subject, anterior=a.anterior, pixel_mm=a.pixel_mm, modality=a.modality)
    path = C.write_column(col, a.out)
    inputs = C.digests(a.image)
    names = F.names_file(a.flexray, a.flexray_names) if a.flexray else None
    for extra in (a.corners, a.flexray, names):
        if extra:
            inputs.update(C.digests(extra))
    finish_directory(a.out, argv, inputs)
    report(col, path)


def report(col: C.Column, path: str) -> None:
    s = col.study
    taken = sum(1 for b in col.bodies for m in SEVEN if math.isfinite(b.values.get(m, math.nan)))
    print("%s: %d bodies (%s), %d chords taken; countable %s; phenotype %s" % (
        path, len(col.bodies), " ".join(col.levels), taken, s.get("countable"), s.get("phenotype")))
    for p in s.get("problems", []):
        print("  problem: %s" % p)


def cmd_check(a, argv) -> None:
    """Read every column back and say what each holds; non-zero exit on any problem: facts that
    differ from the labels, names that give no offsets, a missing field file, or a problem the
    import recorded."""
    bad = 0
    for d in a.directories:
        cols = C.read_columns(d)
        if not cols:
            print("%s: no columns" % d)
            bad += 1
        for col in cols:
            offs = C.offsets_of(col.levels)
            facts = C.facts_from_levels(col.levels, col.study.get("expresses", {}))
            mismatch = [k for k in ("countable", "phenotype", "has_c2", "has_sacrum") if facts[k] != col.study.get(k)]
            field = os.path.join(d, "fields", "%s.csv" % col.study["study_id"])
            notes = []
            if mismatch:
                notes.append("facts differ from the labels: %s" % ", ".join(mismatch))
            if offs is None:
                notes.append("names out of order or unnamed bodies: no offsets")
            if not os.path.exists(field):
                notes.append("no field file")
            notes += ["problem: %s" % p for p in col.study.get("problems", [])]
            print("%s %s: %d bodies, countable %s, %s%s" % (d, col.study["study_id"], len(col.bodies),
                                                          col.study.get("countable"), col.study.get("phenotype"),
                                                          "".join("\n  " + n for n in notes)))
            bad += bool(notes)
    sys.exit(1 if bad else 0)


def cmd_tiers(a, argv) -> None:
    from . import tiers as T
    cols = [c for d in a.directories for c in C.read_columns(d)]
    rows = T.person_tiers(cols)
    os.makedirs(a.out, exist_ok=True)
    counts = T.write(a.out, rows)
    C.write_run(a.out, ["python", "-m", "scanimport"] + argv, {"tiers": counts})
    for t, n in counts.items():
        print("%-9s %d" % (t, n))
    print("%d persons, %d studies; %s" % (len(rows), len(cols), os.path.join(a.out, "tiers.csv")))


def cmd_name(a, argv) -> None:
    from . import bridge as B
    out = B.name_field(a.field, scale_known=False if a.scale_unknown else None, scale_extra_sd=a.scale_sd)
    if a.json:
        print(json.dumps(out, indent=1))
        return
    print("%s: %d bodies, measures %s" % (a.field, out["bodies"], ", ".join(out["measures"])))
    for n in out["notes"]:
        print("  note: %s" % n)
    print("named %s, posterior %.4f (mapping quality %.1f)" % (" ".join(out["names"]), out["posterior"], out["mapq"]))
    print("99%% set of first bodies: %s" % " ".join(out["credible_0.99"]))
    top = sorted(out["posterior_by_place"].items(), key=lambda kv: -kv[1])[:5]
    print("top places: %s" % ", ".join("%s %.4f" % kv for kv in top))


def cmd_score(a, argv) -> None:
    from . import bridge as B
    measures = a.measures or SEVEN
    res = B.score_directory(a.directories, measures, a.n, a.all)
    B.write_scores(a.out, res)
    C.write_run(a.out, ["python", "-m", "scanimport"] + argv, {"skipped": res["skipped"]})
    for s in res["summary"]:
        print("%-7s n=%-2d fields %-5d studies %-4d exact %.3f (se %.3f) within one %.3f answered@0.99 %.3f precision %s" % (
            s["group"], s["n"], s["fields"], s["studies"], s["exact"], s["exact_se"], s["within_one"],
            s["answered_099"], "%.3f" % s["precision_099"] if s["precision_099"] is not None else "-"))
    if res["skipped"]:
        print("skipped: %s" % ", ".join("%s %d" % kv for kv in res["skipped"].items()))


def cmd_compare(a, argv) -> None:
    from . import compare as K
    rows = K.compare(a.directories, counted_only=not a.all)
    path = K.write(a.out, rows, counted_only=not a.all)
    C.write_run(a.out, ["python", "-m", "scanimport"] + argv, {"counted_only": not a.all})
    print("bodies from %s" % ("studies counted from C2 only" if not a.all else
                              "every named body, counted from C2 or not (--all)"))
    for m, s in K.ratio_spread(rows).items():
        print("%-21s levels %-2d mean log(import/Panjabi) %+.4f, spread %s" % (
            m, s["levels"], s["mean_log_ratio"], s["sd_log_ratio"]))
    print(path)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scanimport")
    sub = p.add_subparsers(dest="cmd", required=True)
    from .schemes import SCHEMES
    c = sub.add_parser("ingest-ct", help="a CT's label volume to a column")
    c.add_argument("--labels", required=True, help="NIfTI label volume, or a TotalSegmentator folder")
    c.add_argument("--scheme", required=True, choices=SCHEMES)
    c.add_argument("--subregion", help="SPINEPS's subregion volume, on the same grid")
    c.add_argument("--label-map", help="JSON {value: structure name} for a multilabel volume")
    c.add_argument("--study", required=True)
    c.add_argument("--subject", help="the person's id in the source, to pair studies (default: the study)")
    c.add_argument("--source", required=True)
    c.add_argument("--annotation", required=True, choices=("human", "machine"),
                   help="who drew the labels: a person (or a person checked them), or a machine")
    c.add_argument("--made-by", help="what drew them (VerSe readers, SPINEPS 1.x, ...)")
    c.add_argument("--out", required=True)
    c.set_defaults(func=cmd_ingest_ct)
    x = sub.add_parser("ingest-xr", help="a radiograph's corner annotation(s) to a column")
    x.add_argument("--xr", required=True, action="append", help="schwingnet-spine-xr/1 JSON, once per view")
    x.add_argument("--study", required=True)
    x.add_argument("--subject")
    x.add_argument("--source", required=True)
    x.add_argument("--anterior", choices=("left", "right"), help="which side of a lateral image is anterior")
    x.add_argument("--magnification", type=float, help="the image's magnification, where its geometry gives it: a "
                                                         "finite number of 1 or more")
    x.add_argument("--magnification-sd", type=float, help="spread of log magnification, a finite number of 0 or more")
    x.add_argument("--annotation", required=True, choices=("human", "machine"),
                   help="who drew the corners, the caller's statement, never inferred")
    x.add_argument("--out", required=True)
    x.set_defaults(func=cmd_ingest_xr)

    r = sub.add_parser("ingest-raw-ct", help="a CT's intensities, with no labels, to a column (intensity.py)")
    r.add_argument("--volume", required=True, help="NIfTI file, folder of one DICOM series, or one DICOM file")
    r.add_argument("--series", help="the Series Instance UID, where the folder holds several; held to the series "
                                    "read, whatever --volume is, and refused for a NIfTI, which names none")
    r.add_argument("--study", required=True)
    r.add_argument("--subject", help="the person's id in the source, to pair studies (default: the study)")
    r.add_argument("--source", required=True)
    r.add_argument("--half-maximum-only", action="store_true",
                   help="leave each edge at the half-maximum, without the blurred-step fit (edges.py)")
    r.add_argument("--out", required=True)
    r.set_defaults(func=cmd_ingest_raw_ct)

    g = sub.add_parser("ingest-image", help="one radiograph or frame with its corners or FleXray masks (film.py)")
    g.add_argument("--image", required=True, help="one DICOM radiograph, or a PNG, JPEG, TIFF or BMP")
    g.add_argument("--corners", help="its schwingnet-spine-xr/1 annotation")
    g.add_argument("--flexray", help="FleXray's masks, probabilities or logits for it (.npy, channels x 256 x 256)")
    g.add_argument("--flexray-names", help="FleXray's label_names.json, if not beside the arrays (it is hashed "
                                           "either way)")
    g.add_argument("--mask-content", choices=("whole", "body"), default="whole",
                   help="whole vertebrae (how FleXray's channels are read here: they name bodies, never measure "
                        "them) or bodies alone")
    g.add_argument("--view", choices=XR_VIEWS, help="ap, pa or lateral, where no annotation says it")
    g.add_argument("--study", required=True)
    g.add_argument("--subject")
    g.add_argument("--source", required=True)
    g.add_argument("--anterior", choices=("left", "right"), help="which side of a lateral image is anterior")
    g.add_argument("--pixel-mm", type=float, help="the pixel's length at the detector, a finite number above 0, in "
                                                    "place of the header's; the "
                                                    "header's magnification, where it states or implies one, "
                                                    "still applies, else the default")
    g.add_argument("--modality", help="film, fluoroscopy, or drr or synthetic for a made image; held to the "
                                      "annotation's and written into it where it states none (default: the "
                                      "annotation's, else film)")
    g.add_argument("--annotation", choices=("human", "machine"),
                   help="who drew the corners, required with --corners and held to the reader id; the study's "
                        "annotation is machine once a model names or draws the bodies")
    g.add_argument("--out", required=True)
    g.set_defaults(func=cmd_ingest_image)

    k = sub.add_parser("check", help="read every column back and report")
    k.add_argument("directories", nargs="+")
    k.set_defaults(func=cmd_check)
    t = sub.add_parser("tiers", help="the owner's tiers, person by person")
    t.add_argument("directories", nargs="+")
    t.add_argument("--out", required=True)
    t.set_defaults(func=cmd_tiers)
    n = sub.add_parser("name", help="name one field file with the exact rule")
    n.add_argument("field")
    n.add_argument("--scale-unknown", action="store_true", help="the values are in pixels, scale unknown")
    n.add_argument("--scale-sd", type=float, help="extra spread of log scale; the field file's own by default")
    n.add_argument("--json", action="store_true")
    n.set_defaults(func=cmd_name)
    s = sub.add_parser("score", help="score the rule on every countable import against its own names")
    s.add_argument("directories", nargs="+")
    s.add_argument("--n", type=int, nargs="+", default=[1, 3, 5, 9, 15])
    s.add_argument("--measures", nargs="+", choices=SEVEN)
    s.add_argument("--all", action="store_true", help="score studies not counted from C2 too")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_score)
    m = sub.add_parser("compare", help="every chord beside Panjabi's, level by level")
    m.add_argument("directories", nargs="+")
    m.add_argument("--all", action="store_true", help="compare studies not counted from C2 too")
    m.add_argument("--out", required=True)
    m.set_defaults(func=cmd_compare)
    return p


def main(argv: List[str] = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    a = parser().parse_args(argv)
    a.func(a, argv)


if __name__ == "__main__":
    main()
