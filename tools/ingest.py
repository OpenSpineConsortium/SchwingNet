"""Ingest a bank of frames into one shard on the volume: the frames at their content addresses,
one MANIFEST.json beside them, and a report of what was read, kept and dropped.

A bank is the format every builder of the real X-ray datasets writes (spinesurg-ct-nnunet's
docs/REAL_XRAY_DATASETS_SPEC.md): `images/<split>/<stem>.png`, `meta/<stem>.json` with the case,
the device, the view and the boxes with their level names. This tool reads one bank, hashes every
frame, and writes the shard `<grid root>/shards/<date>-<12 hex>/`: each frame as `<aa>/<sha256>.png`
(schwingnet.catalog.frame_path), the manifest in the shape schwingnet.catalog.ShardManifest, and
INGEST.json with the counts. The shard's name is its content, so the same bank ingested twice is the
same shard and the second run writes nothing; a bank that changed is a new shard that names the old
one as superseded. Nothing is deleted and nothing outside the shard is written, but for the staging
folders a killed ingest left behind, which are cleared once they are older than the stage's time
limit, and the reuse notes below. Reuse does not depend on the date or the commit (#260): where the
source's current shard, or one no other shard supersedes, holds exactly the manifest this bank
makes, apart from the date, the commit and what it supersedes, the run answers "already there" with
that shard and cuts no dated twin; and where an earlier run, of a bank whose every file had the same
path, size and modification time, with the same settings, the same frozen persons, the same registry
entry and the same ingest code, noted its report under `<grid root>/.reuse/`, and the shard
that note names is still one no other supersedes, the run reads no frame of the bank at all and
answers from the note, checking only that every file the manifest names is in place. A bank changed
in any file, a map added or a frame removed, is read again. A frame of more than 8 bits of grey is
refused by name, since the trainer's 8-bit reading would clip it white and tools/bank.py windows it;
the bank is made again.

Before anything is written the frames are checked: a frame's bytes seen twice in the bank under
one person count once (the second stem is reported as a duplicate, never silently kept, since two
copies would weight a person twice), and under two persons are refused, since which person they
are is not the tool's to decide; a train or review shard that holds a frozen test person, among
the duplicates too, is refused; the plan lists the frozen persons of the source the bank never
showed, so a case spelt otherwise than the frozen list spells it is seen before a shard is cut; and a
box with no trusted level (null in the bank) is kept as a frame fact and dropped as a label, as the
spec says, so a detector can still train on it while no level score counts it.

A frame may bring a projected level map (#228), the 3D prior the trainer's prior block learns
from: the meta names it as `level_map`, a path inside the bank, with `level_map_from` saying
whether the render's own geometry (`render`) or a pose registered to a real frame (`registered`)
projected it. The map is an 8-bit greyscale PNG of the frame's own size, 0 where no vertebra is
and 1 to 27 for the catalog's levels in order (schwingnet.catalog.LEVELS), decoded here with the
standard library and refused by name where it is anything else; it rides in the shard at its own
content address beside the frame, and the manifest's item carries its path, digest, projector and
labeller.
A frame without one is as before, and a manifest whose items carry none is byte for byte the
manifest this tool wrote before maps existed, so a bank already ingested reads as unchanged. A map
added to a bank already ingested changes the manifest and not the shard's name, which is the
frames' hashes alone, so it is ingested under a new date with `--supersedes latest`, as a bank that
grew is; the same date is refused, since a shard of that name is there with another manifest. A
duplicate frame's map, where the kept copy of the bytes carries none or another, is named in the
report's duplicates as level_map_dropped.

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
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "vendor" / "beethoven-qa" / "src"))

import bank as bank_tool  # noqa: E402  (tools/bank.py, whose listing of a folder the reuse key is made from)
import catalog as catalog_tool  # noqa: E402  (tools/catalog.py, the reading and writing around the rules)
from beethoven_qa.contracts import ViolationError  # noqa: E402
from schwingnet.catalog import (  # noqa: E402
    LEVELS,
    MANIFEST_SCHEMA,
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
REUSE = ".reuse"
# A staging folder older than the bank stage's time limit (two days) and a margin is a killed
# ingest's, never one still being filled.
STALE_STAGING_SECONDS = 3 * 24 * 3600
# What may differ between two manifests of the same frames with nothing else changed.
CIRCUMSTANCE = ("name", "ingest_date", "code_commit", "supersedes")
# What a bank's meta calls a level, mapped onto the catalog's 27 classes where the spelling differs.
LEVEL_NAMES = {"S1": "sacrum", "Sacrum": "sacrum", "SACRUM": "sacrum"}
# The meta's keys for a frame's projected level map and what projected it (the module docstring).
MAP_KEY, MAP_FROM_KEY = "level_map", "level_map_from"
PROJECTORS = ("render", "registered")


class IngestError(Exception):
    """A bank or a frame the ingest refuses, with the reason a person reads."""


def png_size(data):
    """The width and height of a PNG from its header, the only thing of a frame this tool reads;
    a file shorter than a whole IHDR chunk, 33 bytes, or whose IHDR is not the 13 bytes the format
    gives it, is no PNG, so every later read of the header finds its byte where it belongs."""
    if len(data) < 33 or data[:8] != PNG_SIGNATURE or data[8:16] != b"\x00\x00\x00\x0dIHDR":
        raise IngestError("not a PNG")
    width, height = struct.unpack(">II", data[16:24])
    if width == 0 or height == 0:
        raise IngestError("a PNG of zero size")
    return width, height


def refuse_wide_grey(data):
    """A frame of 16 bits of grey (colour type 0) is refused by name: the trainer's image library
    reads it as 16-bit integers and its conversion to 8-bit grey clips every value above 255, so
    the frame would train white (#260); tools/bank.py windows such a frame to 8 bits. Sixteen bits
    of colour, or of grey with alpha, the library reads at 8 bits a channel, which is no clip."""
    if data[24] == 16 and data[25] == 0:
        raise IngestError("a 16-bit grey frame, which the trainer's 8-bit reading clips white; bank it"
                          " again with tools/bank.py, which windows it to 8 bits (#260)")


def png_chunks(data):
    """Each chunk's type and bytes, in order up to IEND, each whole and under its own checksum, so
    a map this tool keeps is one the trainer's image library reads too: Pillow checks the checksums
    of the chunks before the first IDAT and stops at IEND, and this tool holds every chunk to its
    checksum, which is stricter; the signature was checked by png_size."""
    at = 8
    while at + 12 <= len(data):
        length = struct.unpack(">I", data[at : at + 4])[0]
        kind = data[at + 4 : at + 8]
        if at + 12 + length > len(data):
            raise IngestError(f"the PNG's {kind.decode('ascii', 'replace')} chunk is cut short")
        body = data[at + 8 : at + 8 + length]
        if struct.unpack(">I", data[at + 8 + length : at + 12 + length])[0] != zlib.crc32(kind + body) & 0xFFFFFFFF:
            raise IngestError(f"the PNG's {kind.decode('ascii', 'replace')} chunk fails its checksum")
        yield kind, body
        if kind == b"IEND":
            return
        at += 12 + length


def paeth(left, up, up_left):
    """The PNG Paeth predictor: whichever neighbour is nearest the gradient's estimate."""
    estimate = left + up - up_left
    near_left, near_up, near_up_left = abs(estimate - left), abs(estimate - up), abs(estimate - up_left)
    if near_left <= near_up and near_left <= near_up_left:
        return left
    return up if near_up <= near_up_left else up_left


def unfiltered(raw, width, height):
    """The rows of one-byte pixels under the five PNG filters, each row undone against the last."""
    stride = width + 1
    if len(raw) != stride * height:
        raise IngestError("the PNG's pixel data is not one byte per pixel over its size")
    rows, previous = [], bytes(width)
    for y in range(height):
        kind, line = raw[y * stride], bytearray(raw[y * stride + 1 : (y + 1) * stride])
        if kind == 1:
            for x in range(1, width):
                line[x] = (line[x] + line[x - 1]) & 255
        elif kind == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, previous, strict=True))
        elif kind == 3:
            for x in range(width):
                line[x] = (line[x] + (((line[x - 1] if x else 0) + previous[x]) >> 1)) & 255
        elif kind == 4:
            for x in range(width):
                left, up_left = (line[x - 1], previous[x - 1]) if x else (0, 0)
                line[x] = (line[x] + paeth(left, previous[x], up_left)) & 255
        elif kind != 0:
            raise IngestError(f"a PNG filter type {kind} does not exist")
        previous = bytes(line)
        rows.append(previous)
    return rows


def png_grey_rows(data):
    """The pixel rows of an 8-bit greyscale PNG without interlace, which is what a level map is,
    decoded with the standard library, since this tool runs where no image library is; any other
    PNG is refused by name rather than guessed at."""
    width, height = png_size(data)
    depth, colour, compression, filtering, interlace = data[24:29]
    if (depth, colour, compression, filtering, interlace) != (8, 0, 0, 0, 0):
        raise IngestError(
            f"a level map is an 8-bit greyscale PNG without interlace, compression method 0 and filter"
            f" method 0, not bit depth {depth}, colour type {colour}, compression {compression},"
            f" filter {filtering}, interlace {interlace}"
        )
    bodies, closed = [], False
    for kind, body in png_chunks(data):
        if kind == b"IDAT":
            if closed:
                raise IngestError("the PNG's IDAT chunks are not consecutive")
            bodies.append(body)
        elif bodies:
            # The format keeps the IDAT chunks together, and Pillow stops reading pixel data at
            # the first other chunk after them, so a map with a chunk between them is refused here.
            closed = True
    try:
        raw = zlib.decompress(b"".join(bodies))
    except zlib.error as error:
        raise IngestError(f"the PNG's pixel data does not decompress: {error}") from error
    return unfiltered(raw, width, height)


def check_map(data, width, height):
    """A level map's bytes are the frame's own size with every value 0 or a level's code."""
    rows = png_grey_rows(data)
    if (len(rows[0]), len(rows)) != (width, height):
        raise IngestError(
            f"the level map is {len(rows[0])}x{len(rows)}, the frame {width}x{height}"
        )
    highest = max(max(row) for row in rows)
    if highest > len(LEVELS):
        raise IngestError(f"the level map holds the value {highest}; a level's code is 1 to {len(LEVELS)}")


def map_file(meta, bank):
    """The level map's path inside the bank and what projected it, where the meta names one."""
    named = meta.get(MAP_KEY)
    if named is None:
        return None, None
    parts = Path(named).parts if isinstance(named, str) and named else ()
    if not parts or Path(named).is_absolute() or ".." in parts:
        raise IngestError(f"meta's {MAP_KEY} is not a path inside the bank")
    projector = meta.get(MAP_FROM_KEY)
    if projector not in PROJECTORS:
        raise IngestError(f"meta's {MAP_FROM_KEY} is {projector!r}, not one of {', '.join(PROJECTORS)}")
    return bank / named, projector


def level_map_of(meta, bank, width, height, labeller):
    """The frame's projected level map as the manifest's row, checked against the frame, and the
    file it comes from; a pair of None where the meta names none."""
    path, projector = map_file(meta, bank)
    if path is None:
        return None, None
    try:
        data = path.read_bytes()
    except OSError as error:
        raise IngestError(f"the level map {path.name}: {error}") from error
    try:
        check_map(data, width, height)
    except IngestError as error:
        raise IngestError(f"the level map {path.name}: {error}") from error
    sha = hashlib.sha256(data).hexdigest()
    return {"path": frame_path(sha, "png"), "sha256": sha, "projector": projector, "labeller": labeller}, path


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


def item_of(meta, sha, extension, width, height, settings, level_map=None):
    """One manifest row from one frame's meta; the person is the bank's case under the key rule."""
    case = meta.get("case")
    if not case:
        raise IngestError("meta names no case")
    lat_from_ap_deg, gantry_deg = view_of(meta)
    labels, dropped = labels_of(meta, width, height, settings.labeller)
    row = {
        "level_map": level_map,
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


def read_frame(image, meta_path, settings, bank):
    """The frame's item, how many boxes it dropped, and the level map's file where it has one."""
    data = image.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    width, height = png_size(data)
    refuse_wide_grey(data)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise IngestError(f"{meta_path.name} is not a JSON object")
    level_map, map_path = level_map_of(meta, bank, width, height, settings.labeller)
    item, dropped = item_of(meta, sha, image.suffix.lstrip(".").lower(), width, height, settings, level_map)
    return item, dropped, map_path


def plan_shard(bank, settings, inputs):
    """Read and check the bank; return the items to write, where each comes from, and the report."""
    kept, sources, duplicates, dropped, persons = {}, {}, [], 0, set()
    first_seen, left_out = {}, set()
    for stem, image, meta_path in frames_of(bank, settings.split):
        item, dropped_here, map_path = checked_frame(image, meta_path, settings, bank)
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
            duplicates.append(duplicate_entry(stem, item, kept[item.sha256], sources[item.sha256]))
            continue
        kept[item.sha256], sources[item.sha256] = item, image
        if item.level_map:
            sources[item.level_map.sha256] = map_path
    # Every person the bank named is checked, the duplicates' too, never only the kept items'.
    refuse_test_persons(frozenset(persons), settings, inputs)
    if not kept:
        raise IngestError(f"{bank}: --persons {settings.persons} leaves no frame of the bank")
    items = list(kept.values())
    return items, sources, shard_report(items, duplicates, dropped, persons | left_out, left_out, settings, inputs)


def duplicate_entry(stem, item, first, first_image):
    """The report's line on a duplicate frame: which kept stem holds its bytes and, where it
    brought a level map the kept copy does not carry, that map's digest, so a registered map
    attached to the second stem of a repeated frame is not lost without a word."""
    entry = {"stem": stem, "same_bytes_as": first_image.name, "sha256": item.sha256}
    if item.level_map and (first.level_map is None or first.level_map.sha256 != item.level_map.sha256):
        entry["level_map_dropped"] = item.level_map.sha256
    return entry


def checked_frame(image, meta_path, settings, bank):
    try:
        return read_frame(image, meta_path, settings, bank)
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
            "labels": sum(len(i.labels) for i in items),
            "level_maps": sum(1 for i in items if i.level_map)}


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


def shard_manifests(grid_root):
    """Every shard's MANIFEST.json under `<grid root>/shards/`, in name order, never one inside a
    folder whose name starts with a dot, which is a staging folder and no shard (pathlib's glob
    matches such names)."""
    found = Path(grid_root).glob("shards/*/" + MANIFEST)
    return sorted(path for path in found if not path.parent.name.startswith("."))


def heads(grid_root):
    """Every shard of the source that no other shard there supersedes, by name, with its folder
    and its manifest as written; a manifest that cannot be read is refused, as latest_shard does."""
    manifests = {}
    for path in shard_manifests(grid_root):
        try:
            manifests[path.parent] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise IngestError(f"{path}: not a readable manifest: {error}") from error
    superseded = {data.get("supersedes") for data in manifests.values()}
    return sorted((data["name"], folder, data) for folder, data in manifests.items() if data["name"] not in superseded)


def same_frames_and_facts(one, other):
    """Whether two manifests hold the same frames, labels and facts, whatever their date, commit
    and the shard they supersede, which are circumstances of the run and not the shard's content."""
    def content(data):
        return {key: value for key, value in data.items() if key not in CIRCUMSTANCE}
    return content(one) == content(other)


def equivalent_head(grid_root, data):
    """A shard no other supersedes whose manifest is this one in all but its circumstances, the
    newest by name where there are several; None where there is none. A shard that something
    supersedes is never reused, since the catalog reads only the head of a chain."""
    found = [(name, existing) for name, _, existing in heads(grid_root) if same_frames_and_facts(existing, data)]
    return found[-1][1] if found else None


def clear_stale_staging(grid_root, now=None):
    """Remove the staging folders a killed ingest left under shards/, those older than the stage's
    time limit; the number removed."""
    now = time.time() if now is None else now
    cleared = 0
    for folder in sorted(Path(grid_root).glob("shards/.ingest-*")):
        if folder.is_dir() and now - folder.stat().st_mtime > STALE_STAGING_SECONDS:
            shutil.rmtree(folder, ignore_errors=True)
            cleared += not folder.exists()
    return cleared


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reuse_key(bank, settings, inputs):
    """The hash of everything a shard's manifest follows from: every file of the bank by its path,
    size and modification time (tools/bank.py's listing, the bank's own stamp left out), the
    settings, the frozen persons, the source's registry entry and the ingest code; None for an
    empty or missing bank, which is read and refused. A bank changed in any file, a level map
    added, a frame removed or a meta edited, has another key and is read again."""
    listing = bank_tool.bank_listing(bank)
    if not listing:
        return None
    entry = inputs.registry[settings.source]
    facts = {
        "bank_listing_sha256": bank_tool.listing_sha256(listing),
        "settings": [settings.source, settings.kind.value, settings.split, settings.persons, settings.person_prefix,
                     settings.labeller, settings.modality.value, settings.device_class.value],
        "test_persons_sha256": inputs.test_persons_sha256,
        "registry_entry": json.loads(entry.model_dump_json()),
        "code_sha256": [file_sha256(Path(__file__)), file_sha256(ROOT / "src" / "schwingnet" / "catalog.py")],
    }
    return hashlib.sha256(json.dumps(facts, sort_keys=True).encode("utf-8")).hexdigest()


def reuse_note(grid_root, key):
    return Path(grid_root) / REUSE / f"{key}.json"


def manifest_sha256(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()


def record_reuse(grid_root, key, report, folder):
    """Note the report a run with this key gave and the manifest its shard holds, in a dot folder
    of the source's own beside shards/, which therefore holds shards alone, so the next run with
    the same key is answered without reading the bank. It is written for a shard found already there as for one written,
    so a shard cut before the note existed, or under another key, is answered from the second run
    on."""
    data = json.loads((Path(folder) / MANIFEST).read_text(encoding="utf-8"))
    note = {"key": key, "manifest_sha256": manifest_sha256(data), "report": report}
    path = reuse_note(grid_root, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(f"{path.name}.{os.getpid()}.part")
    part.write_text(json.dumps(note, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(part, path)


def reused_by_stamp(grid_root, key):
    """The report a run with the same key gave, answered without reading the bank, where the
    shard it names is still one no other supersedes and holds the manifest it held then; None
    otherwise. Every file the shard's manifest names must be in place, which costs a look at
    each and no read."""
    if key is None:
        return None
    try:
        note = json.loads(reuse_note(grid_root, key).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    report = note.get("report") if isinstance(note, dict) else None
    if not isinstance(report, dict) or note.get("key") != key:
        return None
    found = {name: (folder, data) for name, folder, data in heads(grid_root)}
    if report.get("shard") not in found:
        return None
    folder, data = found[report["shard"]]
    if manifest_sha256(data) != note.get("manifest_sha256"):
        return None
    manifest = ShardManifest.model_validate(data)
    missing = [p for p in present_paths(manifest) if not (folder / p).is_file()]
    if missing:
        raise IngestError(f"{folder}: {len(missing)} files its manifest names are missing (first {missing[0]})")
    report.update({"outcome": "already there", "verified": len(manifest.items), "folder": str(folder),
                   "verified_by": "presence: the bank's files, the settings and the inputs are unchanged"})
    return report


def present_paths(manifest):
    for item in manifest.items:
        yield item.path
        if item.level_map:
            yield item.level_map.path


def latest_shard(grid_root):
    """The head of the source's shard chain, with what it supersedes: the shard under
    `<grid root>/shards/` that none of the others there supersedes, the newest by name where the
    chain forked; a pair of None with no shard."""
    manifests = {}
    for path in shard_manifests(grid_root):
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
    rows = [item_record(i) for i in items]
    schema = MANIFEST_SCHEMA if any(i.level_map for i in items) else 1
    data = {"schema_version": schema, "name": name, "source": settings.source, "kind": settings.kind.value,
            "ingest_date": settings.date, "code_commit": settings.code_commit,
            "supersedes": settings.supersedes, "items": rows}
    return ShardManifest.model_validate(data), data


def item_record(item):
    """The item as the manifest writes it: a frame without a level map carries no key for one, so
    a shard ingested before maps existed (#228) is written byte for byte as it was, and a bank
    ingested again is "already there" and not a manifest that differs."""
    record = json.loads(item.model_dump_json())
    if record.get("level_map") is None:
        record.pop("level_map", None)
    return record


def shard_files(items, sources):
    """Every file the shard holds with where it comes from, each path once: the frames and, where
    an item carries one, its level map; two frames may share one map's bytes, which is one file."""
    seen = set()
    for item in items:
        pairs = [(item.path, sources[item.sha256])]
        if item.level_map:
            pairs.append((item.level_map.path, sources[item.level_map.sha256]))
        for path, source in pairs:
            if path not in seen:
                seen.add(path)
                yield path, source


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
        for path, source in shard_files(items, sources):
            target = staging / path
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(source, target)
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
    """Every frame of the manifest, and every level map, is in place with the bytes its name
    promises; the count returned is the frames'."""
    for item in manifest.items:
        named = [(item.path, item.sha256)]
        if item.level_map:
            named.append((item.level_map.path, item.level_map.sha256))
        for relative, sha in named:
            path = Path(folder) / relative
            if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
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
        p.add_argument("--labeller", default="projected", help="who drew the boxes and made the level maps, as the manifest records it")
        p.add_argument("--persons", default="all", choices=["all", "frozen", "unfrozen"],
                       help="only the frozen test persons' frames, only the others', or every frame")
        p.add_argument("--modality", default=None)
        p.add_argument("--device-class", default=None)
        p.add_argument("--grid-root", default=None, help="the source's folder; the registry's unless named")
        p.add_argument("--registry", default=None, help="another registry folder, for a test")
    return top


def ingest(args, settings, inputs, key, cleared):
    """Read the bank and plan the shard, or write it with `run`; the report. A shard already there
    under another date or commit with the same content is the answer, and no twin is cut."""
    items, sources, report = plan_shard(Path(args.bank), settings, inputs)
    manifest, data = manifest_of(items, settings)
    existing = equivalent_head(settings.grid_root, data)
    if existing is not None:
        manifest, data = ShardManifest.model_validate(existing), existing
    folder = shard_folder(settings.grid_root, manifest.name)
    report.update({"shard": manifest.name, "folder": folder, "kind": manifest.kind.value})
    if key is not None:
        report["reuse_key"] = key
    if args.command == "run":
        report["outcome"] = write_shard(folder, items, sources, data, report)
        report["verified"] = verify_shard(folder, manifest)
        report["staging_cleared"] = cleared
        if key is not None:
            note_reuse(Path(args.bank), settings, inputs, key, report, folder)
    return report


def note_reuse(bank, settings, inputs, key, report, folder):
    """The note is a saving and no part of the shard: where it cannot be written, or the bank no
    longer lists as it did when the key was made, so the shard may hold a later state of it than
    the key names, the run says so and the next one reads the bank."""
    try:
        if reuse_key(bank, settings, inputs) != key:
            report["reuse_note"] = "not written: the bank changed while it was read"
            return
        record_reuse(settings.grid_root, key, report, folder)
    except (OSError, ValueError) as error:
        report["reuse_note"] = f"not written: {error}"


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        inputs = catalog_tool.load_inputs(args.registry or catalog_tool.REGISTRY)
        if args.source not in inputs.registry:
            raise IngestError(f"{args.source} has no registry entry")
        settings = Settings(args, inputs.registry[args.source])
        key = reuse_key(args.bank, settings, inputs)
        cleared = clear_stale_staging(settings.grid_root) if args.command == "run" else 0
        reused = reused_by_stamp(settings.grid_root, key) if args.command == "run" else None
        if reused is not None:
            reused["staging_cleared"] = cleared
            print(json.dumps(reused, indent=1, sort_keys=True))
            return 0
        print(json.dumps(ingest(args, settings, inputs, key, cleared), indent=1, sort_keys=True))
        return 0
    except (catalog_tool.CatalogError, IngestError, OSError, ValueError, ViolationError) as error:
        # A pydantic ValidationError is a ValueError; a ViolationError is a rule of the catalog
        # refusing what the bank or the command line gave. Either is one line, never a traceback.
        print(f"ingest: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
