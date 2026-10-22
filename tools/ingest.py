"""Ingest a bank of frames into one shard on the volume: the frames at their content addresses,
one MANIFEST.json beside them, and a report of what was read, kept and dropped.

A bank is the format every builder of the real X-ray datasets writes (spinesurg-ct-nnunet's
docs/REAL_XRAY_DATASETS_SPEC.md): `images/<split>/<stem>.png`, `meta/<stem>.json` with the case,
the device, the view and the boxes with their level names. This tool reads one bank, hashes every
frame, and writes the shard `<grid root>/shards/<date>-<12 hex>/`: each frame as `<aa>/<sha256>.png`
(schwingnet.catalog.frame_path), the manifest in the shape schwingnet.catalog.ShardManifest, and
INGEST.json with the counts. The shard's name is its content, so the same bank ingested twice is
the same shard and the second run writes nothing; a bank that changed is a new shard that names the
old one as superseded. Nothing is deleted and nothing outside the shard is written.

Before anything is written the frames are checked: a frame's bytes seen twice in the bank under
one person count once (the second stem is reported as a duplicate, never silently kept, since two
copies would weight a person twice), and under two persons are refused, since which person they
are is not the tool's to decide; a train or review shard that holds a frozen test person, among
the duplicates too, is refused; the plan lists the frozen persons of the source the bank never
showed, so a case spelt otherwise than the frozen list spells it is seen before a shard is cut; and a
box with no trusted level (null in the bank) is kept as a frame fact and dropped as a label, as the
spec says, so a detector can still train on it while no level score counts it.

    pixi run --locked python tools/ingest.py plan --bank <dir> --source carmlspine --kind train
    pixi run --locked python tools/ingest.py run --bank <dir> --source carmlspine --kind train \\
        --split test --date 2026-10-21 --code-commit <sha> [--supersedes <shard name>] [--grid-root <dir>]

`plan` reads and checks and prints the manifest that `run` would write, writing nothing; `run`
writes the shard. `--supersedes latest` names the source's current shard for it, the one under
`<grid root>/shards/` that no other shard there supersedes, so a bank that grew (a raw copy that
came in parts, a zip unpacked after a first ingest) cuts a successor and not a sibling, and the
catalog, which reads a shard or its successor and never both, counts no frame twice (measured in
the chain's first run, issue #40: a second ingest of a grown bank without it gave a catalog of 287
frames for 167 files); where the new shard is that current one, nothing supersedes anything. The grid root is the registry entry's unless named, for a test or a stress run
on another volume. `--persons frozen` keeps only the frames of the frozen test persons
(data/splits/test-persons.json) and `--persons unfrozen` only the others', so a bank whose own
split folders mix them, as C-ArmLSpine's does, becomes one test shard and one train shard, each
read from the whole bank; the same bytes under two persons are still refused across the whole bank,
before either half is taken. This is an I/O tool around the gated rules; it runs on the grid in the shell or
as one CPU job (docs/setup/grid.md), never on the login node for a bank of any size.
"""

import argparse
import errno
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "vendor" / "beethoven-qa" / "src"))

import catalog as catalog_tool  # noqa: E402  (tools/catalog.py, the reading and writing around the rules)
from beethoven_qa.contracts import ViolationError  # noqa: E402
from schwingnet.catalog import (  # noqa: E402
    LEVELS,
    DeviceClass,
    Item,
    Modality,
    ShardKind,
    ShardManifest,
    content_digest,
    frame_path,
    shard_folder,
    shard_name,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MANIFEST = "MANIFEST.json"
REPORT = "INGEST.json"
# What a bank's meta calls a level, mapped onto the catalog's 27 classes where the spelling differs.
LEVEL_NAMES = {"S1": "sacrum", "Sacrum": "sacrum", "SACRUM": "sacrum"}


class IngestError(Exception):
    """A bank or a frame the ingest refuses, with the reason a person reads."""


def png_size(data):
    """The width and height of a PNG from its header, the only thing of the image this tool reads."""
    if len(data) < 24 or data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        raise IngestError("not a PNG")
    width, height = struct.unpack(">II", data[16:24])
    if width == 0 or height == 0:
        raise IngestError("a PNG of zero size")
    return width, height


def unit_box(box, width, height):
    """A pixel box [x0, y0, x1, y1] as the frame's unit square, clipped to it."""
    x0, y0, x1, y1 = (float(v) for v in box)
    clip = lambda v: min(1.0, max(0.0, v))  # noqa: E731  (a one-line clamp reads best inline)
    return (clip(x0 / width), clip(y0 / height), clip(x1 / width), clip(y1 / height))


def level_name(text):
    if text is None:
        return None
    name = LEVEL_NAMES.get(str(text), str(text))
    return name if name in LEVELS else None


def labels_of(meta, width, height, labeller):
    """The boxes of a frame as catalog labels: a box with no trusted level is a frame fact only."""
    labels, dropped = [], 0
    for box in boxes_of(meta):
        level = level_name(box.get("level"))
        if level is None or box.get("kept") is False:
            dropped += 1
            continue
        x0, y0, x1, y1 = unit_box(box["box"], width, height)
        if x1 <= x0 or y1 <= y0:
            dropped += 1
            continue
        labels.append({"level": level, "box": [x0, y0, x1, y1], "labeller": labeller})
    return labels, dropped


def mapping_of(meta, key):
    """A field the spec makes an object, as a dict ({} where it is absent), refused by name where
    a bank wrote something else, so a frame of another shape is one line and never a traceback."""
    value = meta.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise IngestError(f"meta's {key} is a {type(value).__name__}, not an object")
    return value


def boxes_of(meta):
    boxes = meta.get("boxes")
    if boxes is None:
        return []
    if not isinstance(boxes, list) or not all(isinstance(box, dict) for box in boxes):
        raise IngestError("meta's boxes is not a list of objects")
    return boxes


def angle_of(meta):
    """The positioner angle a builder wrote beside the view, None where it wrote none, refused by
    name where it is not a number; Item holds it to its range, so no value is cast here."""
    angle = meta.get("angle")
    if angle is None:
        return None
    if isinstance(angle, bool) or not isinstance(angle, (int, float)):
        raise IngestError(f"meta's angle is a {type(angle).__name__}, not a number")
    return angle


def view_of(meta):
    """The frame's angle from AP and its gantry angle. The spec holds both under `view`. The
    C-ArmLSpine builders write no such object and keep the C-arm's positioner angle as `angle`
    (the DICOM PositionerPrimaryAngle, whose sign is the spec's lat_from_ap_deg): the spot bank's
    (spinesurg-ct-nnunet tools/carmlspine_labels.py) writes `view` as the frame's tag (AP, LAT,
    OBL, LAT2), read from that angle (tools/carmlspine_io.py view_of_angle); the case134 sweep's
    (tools/case134_sweep.py) writes no `view` and names itself a spin with `mode`, where the same
    angle is the spin's gantry angle, as COBRA's spin export writes it."""
    view = meta.get("view")
    if view is None or isinstance(view, str):
        angle = angle_of(meta)
        return angle, angle if meta.get("mode") == "cbct_spin" else None
    view = mapping_of(meta, "view")
    return view.get("lat_from_ap_deg"), view.get("gantry_deg")


def device_of(meta, device_class):
    device = mapping_of(meta, "device")
    return {
        "device_class": device_class.value,
        "make": device.get("make") or None,
        "model": device.get("model") or None,
        "detector": device.get("detector") or None,
    }


def exposure_of(meta):
    """The spec keeps kVp and mAs with the device; the C-ArmLSpine builder writes kvp beside it."""
    device = mapping_of(meta, "device")
    kvp = device.get("kvp") if device.get("kvp") is not None else meta.get("kvp")
    return {"kvp": kvp, "mas": device.get("mas"), "px_mm": meta.get("px_mm")}


def item_of(meta, sha, extension, width, height, settings):
    """One manifest row from one frame's meta; the person is the bank's case under the key rule."""
    case = meta.get("case")
    if not case:
        raise IngestError("meta names no case")
    lat_from_ap_deg, gantry_deg = view_of(meta)
    labels, dropped = labels_of(meta, width, height, settings.labeller)
    row = {
        "path": frame_path(sha, extension),
        "sha256": sha,
        "person": f"{settings.person_prefix}:{case}",
        "modality": settings.modality.value,
        "device": device_of(meta, settings.device_class),
        "exposure": exposure_of(meta),
        "lat_from_ap_deg": lat_from_ap_deg,
        "gantry_deg": gantry_deg,
        "acquired": meta.get("acquired"),
        "labels": labels,
    }
    return Item.model_validate(row), dropped


def frames_of(bank, split):
    """Every frame of the bank's split, as (stem, image path, meta path), in stem order: the PNG
    files alone, and none whose name starts with a dot, which a desktop or an editor leaves
    behind and no builder writes."""
    folder = bank / "images" / split
    found = folder.glob("*.png") if split else folder.rglob("*.png")
    images = sorted(p for p in found if not any(part.startswith(".") for part in p.relative_to(folder).parts))
    if not images:
        raise IngestError(f"{bank}: no frame under images/{split or ''}")
    for image in images:
        meta = bank / "meta" / (image.stem + ".json")
        if not meta.is_file():
            raise IngestError(f"{image}: no meta file {meta}")
        yield image.stem, image, meta


def read_frame(image, meta_path, settings):
    data = image.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    width, height = png_size(data)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise IngestError(f"{meta_path.name} is not a JSON object")
    return item_of(meta, sha, image.suffix.lstrip(".").lower(), width, height, settings)


def plan_shard(bank, settings, inputs):
    """Read and check the bank; return the items to write, where each comes from, and the report."""
    kept, sources, duplicates, dropped, persons = {}, {}, [], 0, set()
    first_seen, left_out = {}, set()
    for stem, image, meta_path in frames_of(bank, settings.split):
        item, dropped_here = checked_frame(image, meta_path, settings)
        # The same bytes under two persons are refused across the whole bank, before --persons
        # leaves any frame out, so splitting a bank in two never hides one.
        first_item, first_image = first_seen.setdefault(item.sha256, (item, image))
        refuse_two_persons(item, first_item, first_image, image)
        if not wanted(item.person, settings.persons, inputs.test_persons):
            left_out.add(item.person)
            continue
        dropped += dropped_here
        persons.add(item.person)
        if item.sha256 in kept:
            duplicates.append({"stem": stem, "same_bytes_as": sources[item.sha256].name, "sha256": item.sha256})
            continue
        kept[item.sha256], sources[item.sha256] = item, image
    # Every person the bank named is checked, the duplicates' too, never only the kept items'.
    refuse_test_persons(frozenset(persons), settings, inputs)
    if not kept:
        raise IngestError(f"{bank}: --persons {settings.persons} leaves no frame of the bank")
    items = list(kept.values())
    return items, sources, shard_report(items, duplicates, dropped, persons | left_out, left_out, settings, inputs)


def checked_frame(image, meta_path, settings):
    try:
        return read_frame(image, meta_path, settings)
    except (IngestError, ValueError, KeyError) as error:
        raise IngestError(f"{image}: {error}") from error


def wanted(person, which, frozen):
    """Whether --persons keeps a frame: every person, only the frozen test persons, or only the
    others, so one bank whose own split mixes them becomes a test shard and a train shard."""
    return which == "all" or (person in frozen) == (which == "frozen")


def shard_report(items, duplicates, dropped, seen, left_out, settings, inputs):
    return {"frames_read": len(items) + len(duplicates), "frames_kept": len(items),
            "duplicates": duplicates, "boxes_without_level": dropped,
            "persons": len({i.person for i in items}),
            "persons_filter": settings.persons, "persons_left_out": len(left_out),
            "frozen_persons_not_seen": frozen_not_seen(frozenset(seen), settings, inputs),
            "labels": sum(len(i.labels) for i in items)}


def refuse_two_persons(item, first, first_image, image):
    """The same bytes under two persons is an identity question for a person to settle, never a
    duplicate to drop: the kept copy would carry one person's part and the other's frame."""
    if item.person != first.person:
        raise IngestError(f"{image}: the same bytes as {first_image.name}, under another person"
                          f" ({item.person}, not {first.person})")


def refuse_test_persons(persons, settings, inputs):
    held = sorted(persons & inputs.test_persons)
    if settings.kind is not ShardKind.TEST and held:
        raise IngestError(f"a {settings.kind.value} shard would hold the frozen test persons {held}")
    if settings.kind is ShardKind.TEST and persons - inputs.test_persons:
        raise IngestError(f"a test shard would hold {sorted(persons - inputs.test_persons)}, not frozen")


def frozen_not_seen(persons, settings, inputs):
    """The frozen persons of this source the bank never showed: on a real bank, a spelling of
    the case that differs from the frozen list's is seen here before a train shard is cut."""
    prefix = settings.person_prefix + ":"
    return sorted(p for p in inputs.test_persons if p.startswith(prefix) and p not in persons)


def latest_shard(grid_root):
    """The head of the source's shard chain, with what it supersedes: the shard under
    `<grid root>/shards/` that none of the others there supersedes, the newest by name where the
    chain forked; a pair of None with no shard."""
    manifests = {}
    for path in sorted(Path(grid_root).glob("shards/*/" + MANIFEST)):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise IngestError(f"{path}: not a readable manifest: {error}") from error
        manifests[data["name"]] = data.get("supersedes")
    heads = sorted(set(manifests) - {s for s in manifests.values() if s})
    return (heads[-1], manifests[heads[-1]]) if heads else (None, None)


def manifest_of(items, settings):
    digest = content_digest(tuple(i.sha256 for i in items))
    name = shard_name(settings.source, settings.date, digest)
    if settings.supersedes == "latest":
        # The same bank again is the head itself, whose manifest must come out byte for byte, so
        # it keeps what the head supersedes; a changed bank supersedes the head.
        head, head_supersedes = latest_shard(settings.grid_root)
        settings.supersedes = head_supersedes if head == name else head
    data = {"schema_version": 1, "name": name, "source": settings.source, "kind": settings.kind.value,
            "ingest_date": settings.date, "code_commit": settings.code_commit,
            "supersedes": settings.supersedes, "items": [json.loads(i.model_dump_json()) for i in items]}
    return ShardManifest.model_validate(data), data


def write_shard(folder, items, sources, data, report):
    """Write the shard beside its final name and rename it into place; a shard already there
    with the same manifest is left as it is and reported."""
    final = Path(folder)
    if final.exists():
        return finish_existing(final, data)
    final.parent.mkdir(parents=True, exist_ok=True)
    # A staging folder of this run's own, named by the system: a name built from the pid could
    # be another run's folder still being filled, which must never be removed or written into.
    staging = Path(tempfile.mkdtemp(dir=final.parent, prefix=f".ingest-{final.name}-"))
    try:
        os.chmod(staging, 0o755)  # mkdtemp makes it private; a shard is read by the whole lab
        for item in items:
            target = staging / item.path
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(sources[item.sha256], target)
            os.chmod(target, 0o444)
        (staging / MANIFEST).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        (staging / REPORT).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(staging / MANIFEST, 0o444)
        return move_into_place(staging, final, data)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def move_into_place(staging, final, data):
    """Rename the staging folder to the shard's name; where another run of the same bank got
    there first, keep its shard, drop the staging folder and answer as a second run does."""
    try:
        os.rename(staging, final)
    except OSError as error:
        if error.errno not in (errno.ENOTEMPTY, errno.EEXIST) or not final.is_dir():
            raise
        shutil.rmtree(staging, ignore_errors=True)
        return finish_existing(final, data)
    return "written"


def finish_existing(final, data):
    try:
        existing = json.loads((final / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise IngestError(f"{final}: a folder is there without a readable {MANIFEST}: {error}") from error
    if existing != data:
        raise IngestError(f"{final}: a shard of that name is there and its manifest differs")
    return "already there"


def verify_shard(folder, manifest):
    """Every frame of the manifest is in place with the bytes its name promises."""
    for item in manifest.items:
        path = Path(folder) / item.path
        if hashlib.sha256(path.read_bytes()).hexdigest() != item.sha256:
            raise IngestError(f"{path}: the bytes do not match the name")
    return len(manifest.items)


def manifest_pattern(field):
    """The spelling ShardManifest holds a field to, so the command line is checked by the same
    rule before a bank is read, and a wrong date or commit is one line and not a traceback."""
    return re.compile(ShardManifest.model_fields[field].metadata[0].pattern)


def spelled(value, pattern, what):
    if not pattern.match(value):
        raise IngestError(f"{what} {value!r} is not spelled as the manifest takes it ({pattern.pattern})")
    return value


def choice(value, kind, fallback):
    """An enum member from a word on the command line, else the registry's; refused by name."""
    if not value:
        return fallback
    try:
        return kind(value)
    except ValueError as error:
        raise IngestError(f"{value!r} is none of {', '.join(k.value for k in kind)}") from error


class Settings:
    """What one ingest is told: the source's registry entry decides the modality and device."""

    def __init__(self, args, entry):
        self.source = args.source
        self.kind = ShardKind(args.kind)
        self.split = args.split
        self.date = spelled(args.date, manifest_pattern("ingest_date"), "the date")
        self.code_commit = spelled(args.code_commit, manifest_pattern("code_commit"), "the commit")
        self.supersedes = args.supersedes
        self.person_prefix = args.person_prefix or entry.source
        self.labeller = args.labeller
        self.persons = args.persons
        self.modality = choice(args.modality, Modality, entry.modality)
        self.device_class = choice(args.device_class, DeviceClass, entry.device_class)
        self.grid_root = (args.grid_root or entry.grid_root).rstrip("/")
        if not self.grid_root.endswith("/" + entry.source):
            raise IngestError(f"the grid root {self.grid_root} is not the folder named {entry.source}")


def parser():
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = top.add_subparsers(dest="command", required=True)
    for name in ("plan", "run"):
        p = sub.add_parser(name)
        p.add_argument("--bank", required=True, help="the bank's folder (images/, meta/)")
        p.add_argument("--source", required=True, help="the registry entry's source id")
        p.add_argument("--kind", required=True, choices=[k.value for k in ShardKind])
        p.add_argument("--split", default="", help="the bank's split folder to read; every one unless named")
        p.add_argument("--date", required=True, help="the ingest date, YYYY-MM-DD")
        p.add_argument("--code-commit", required=True, help="the commit of the code that made the bank")
        p.add_argument("--supersedes", default=None, help="the shard this one replaces; 'latest' names the source's current one")
        p.add_argument("--person-prefix", default=None, help="the person key's prefix; the source id unless named")
        p.add_argument("--labeller", default="projected", help="who drew the boxes, as the manifest records it")
        p.add_argument("--persons", default="all", choices=["all", "frozen", "unfrozen"],
                       help="only the frozen test persons' frames, only the others', or every frame")
        p.add_argument("--modality", default=None)
        p.add_argument("--device-class", default=None)
        p.add_argument("--grid-root", default=None, help="the source's folder; the registry's unless named")
        p.add_argument("--registry", default=None, help="another registry folder, for a test")
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        inputs = catalog_tool.load_inputs(args.registry or catalog_tool.REGISTRY)
        if args.source not in inputs.registry:
            raise IngestError(f"{args.source} has no registry entry")
        settings = Settings(args, inputs.registry[args.source])
        items, sources, report = plan_shard(Path(args.bank), settings, inputs)
        manifest, data = manifest_of(items, settings)
        folder = shard_folder(settings.grid_root, manifest.name)
        report.update({"shard": manifest.name, "folder": folder, "kind": manifest.kind.value})
        if args.command == "run":
            report["outcome"] = write_shard(folder, items, sources, data, report)
            report["verified"] = verify_shard(folder, manifest)
        print(json.dumps(report, indent=1, sort_keys=True))
        return 0
    except (catalog_tool.CatalogError, IngestError, OSError, ValueError, ViolationError) as error:
        # A pydantic ValidationError is a ValueError; a ViolationError is a rule of the catalog
        # refusing what the bank or the command line gave. Either is one line, never a traceback.
        print(f"ingest: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
