"""Draw nine-inch fluoroscopy fields cut from whole-spine films, stitched back into a panorama.

The owner asked on 2026-10-25 for a picture laid out like the stitched intraoperative
fluoroscopy figures of the scoliosis literature: for each case, a column of round spot frames
labelled a, b, c, ..., the same frames stitched into a panorama at their places, and the whole
film beside them. The project holds no real stepped sweep (chapter 34), so the frames here are
cut from a whole-spine film the way spine-program's simulator cuts them: round fields of a
nine-inch intensifier, 140 mm at the spine, stepped up the column from an anchor below L5 at a
chosen overlap in vertebral bodies. Each frame is shown inverted, as a fluoroscopy monitor shows
bone dark, so the three panels read as the published ones do; the caption says they are cut from
the film and not acquired.

The geometry follows tools/overlap_figures.py, which copies sweep_map.py's rules: the field is
140 mm, a lumbar pitch is 34 mm and a thoracic one 27 mm, the step is the field less the overlap,
and the first field's lower edge sits 0.7 of a pitch below the anchor. A film's scale comes from
its own lumbar pitch, since a film carries no pixel spacing the figure can trust.

    python3 tools/stitched_fields_figure.py --aasce DIR --pick 4 --out fig.png
    python3 tools/stitched_fields_figure.py --demo --out fig.png      # a drawn spine, no data

DIR is a BoostNet-layout folder: data/<split>/*.jpg beside labels/<split>/landmarks.csv and
filenames.csv, the AASCE 2019 release's 68 corners per film, four for each of T1 to L5.
"""
from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FIELD_MM = 140.0
LUMBAR_PITCH_MM = 34.0
THORACIC_PITCH_MM = 27.0
FIRST_FRAME_BELOW = 0.7
TOP_MARGIN = 0.5
LEVELS = [f"T{i}" for i in range(1, 13)] + [f"L{i}" for i in range(1, 6)]
PANEL_HEIGHT = 900
GAP = 14
CASE_GAP = 70
LABEL_RED = (200, 30, 30)


@dataclass
class Case:
    """One film with its vertebral centres, cranial first, in pixels."""

    image: Image.Image
    centres: list[tuple[float, float]]
    name: str


@dataclass
class Film:
    """A grey film on a black margin, with a mask that is white where the film itself is."""

    pixels: Image.Image
    inside: Image.Image


@dataclass
class Field:
    """One round field: its centre and radius in film pixels, and its letter."""

    x: float
    y: float
    radius: float
    letter: str = ""


# ----------------------------------------------------------------------------------------
# geometry
# ----------------------------------------------------------------------------------------
def column_with_anchor(centres):
    """The centres from the anchor up: S1 extrapolated one pitch below L5, then L5 to T1."""
    up = list(reversed(centres))
    (x5, y5), (x4, y4) = up[0], up[1]
    anchor = (2 * x5 - x4, 2 * y5 - y4)
    return [anchor] + up


def arc_lengths(points):
    """Cumulative distance along the polyline through the points."""
    lengths = [0.0]
    for (xa, ya), (xb, yb) in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.hypot(xb - xa, yb - ya))
    return lengths


def point_at(points, lengths, s):
    """The point at arc length s, extended straight past either end."""
    if s <= 0:
        return extend(points[1], points[0], -s)
    if s >= lengths[-1]:
        return extend(points[-2], points[-1], s - lengths[-1])
    for i in range(1, len(lengths)):
        if s <= lengths[i]:
            t = (s - lengths[i - 1]) / max(lengths[i] - lengths[i - 1], 1e-9)
            (xa, ya), (xb, yb) = points[i - 1], points[i]
            return xa + t * (xb - xa), ya + t * (yb - ya)
    return points[-1]


def extend(start, end, distance):
    """The point that distance beyond end, on the line from start through end."""
    (xa, ya), (xb, yb) = start, end
    norm = max(math.hypot(xb - xa, yb - ya), 1e-9)
    return xb + (xb - xa) / norm * distance, yb + (yb - ya) / norm * distance


def lumbar_pitch_px(centres):
    """The median distance between neighbouring lumbar centres (L1 to L5), in pixels."""
    lumbar = centres[-5:]
    steps = sorted(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(lumbar, lumbar[1:]))
    return steps[len(steps) // 2]


def place_fields(centres, overlap_bodies):
    """Round fields stepped from the anchor up the column, lettered cranial first."""
    points = column_with_anchor(centres)
    lengths = arc_lengths(points)
    px_per_mm = lumbar_pitch_px(centres) / LUMBAR_PITCH_MM
    radius = FIELD_MM * px_per_mm / 2
    lumbar_px = LUMBAR_PITCH_MM * px_per_mm
    s = -FIRST_FRAME_BELOW * lumbar_px + radius
    top = lengths[-1] + TOP_MARGIN * THORACIC_PITCH_MM * px_per_mm
    fields = []
    while True:
        x, y = point_at(points, lengths, s)
        fields.append(Field(x, y, radius))
        if s + radius >= top:
            break
        pitch_mm = LUMBAR_PITCH_MM if s < lengths[6] else THORACIC_PITCH_MM
        s += max(FIELD_MM - overlap_bodies * pitch_mm, 0.5 * pitch_mm) * px_per_mm
    for i, field in enumerate(reversed(fields)):
        field.letter = chr(ord("a") + i)
    return fields


# ----------------------------------------------------------------------------------------
# drawing
# ----------------------------------------------------------------------------------------
def gray(image):
    """The film as an 8-bit grey image."""
    return image.convert("L")


def round_frame(film, field):
    """One field cut from the film as a round frame on black, inverted like a monitor.

    Each frame is stretched on its own between the 1st and 99th percentiles of what it shows,
    as a fluoroscope's automatic brightness control sets each exposure, and whatever lies off
    the film stays black rather than turning white when the frame is inverted.
    """
    size = int(round(2 * field.radius))
    left, top = int(field.x - field.radius), int(field.y - field.radius)
    box = (left, top, left + size, top + size)
    pixels = np.asarray(film.pixels.crop(box), dtype=float)
    circle = Image.new("L", (size, size), 0)
    ImageDraw.Draw(circle).ellipse((0, 0, size - 1, size - 1), fill=255)
    shown = (np.asarray(circle) > 0) & (np.asarray(film.inside.crop(box)) > 0)
    frame = np.zeros_like(pixels)
    if shown.any():
        low, high = np.percentile(pixels[shown], [1, 99])
        stretched = np.clip((pixels - low) / max(high - low, 1.0), 0, 1)
        frame[shown] = 255 * (1 - stretched[shown])
    return Image.fromarray(frame.astype("uint8")), circle


def frames_column(film, fields, height, font):
    """The frames stacked cranial first, each scaled to share the column's height."""
    side = height // len(fields)
    column = Image.new("RGB", (side, height), (0, 0, 0))
    for i, field in enumerate(reversed(fields)):
        frame, _ = round_frame(film, field)
        column.paste(frame.resize((side, side)).convert("RGB"), (0, i * side))
        letter(ImageDraw.Draw(column), (4, i * side + side - 22), field.letter, font)
    return column


def stitched_panorama(film, fields, font):
    """The frames pasted at their places on black, the anchor's first, each later one on top."""
    left, top, right, bottom = fields_box(fields)
    panorama = Image.new("L", (right - left, bottom - top), 0)
    for field in fields:
        frame, mask = round_frame(film, field)
        corner = (int(field.x - field.radius) - left, int(field.y - field.radius) - top)
        panorama.paste(frame, corner, mask)
    panorama = panorama.convert("RGB")
    draw = ImageDraw.Draw(panorama)
    for field in fields:
        at = (int(field.x - field.radius) - left + 6, int(field.y) - top)
        letter(draw, at, field.letter, font)
    return panorama


def fields_box(fields):
    """The bounding box of every field, in film pixels."""
    left = min(f.x - f.radius for f in fields)
    right = max(f.x + f.radius for f in fields)
    top = min(f.y - f.radius for f in fields)
    bottom = max(f.y + f.radius for f in fields)
    return int(left), int(top), int(math.ceil(right)), int(math.ceil(bottom))


def film_panel(film, fields):
    """The film over the same rows as the panorama, a little wider than its fields."""
    left, top, right, bottom = fields_box(fields)
    pad = (right - left) // 4
    return film.crop((left - pad, top, right + pad, bottom)).convert("RGB")


def letter(draw, at, text, font):
    """A small white letter with a dark outline, as the published frames carry."""
    draw.text(at, text, fill=(255, 255, 255), font=font, stroke_width=2, stroke_fill=(0, 0, 0))


def scaled(image, height):
    """The image scaled to the given height."""
    width = max(1, round(image.width * height / image.height))
    return image.resize((width, height), Image.LANCZOS)


def case_strip(case, overlap_bodies, fonts):
    """One case: the frames, their panorama and the film, side by side at one height."""
    fields = place_fields(case.centres, overlap_bodies)
    film, pad = padded_film(gray(case.image), fields)
    fields = shifted(fields, pad)
    panels = [
        frames_column(film, fields, PANEL_HEIGHT, fonts["small"]),
        scaled(stitched_panorama(film, fields, fonts["big"]), PANEL_HEIGHT),
        scaled(film_panel(film.pixels, fields), PANEL_HEIGHT),
    ]
    width = sum(p.width for p in panels) + GAP * (len(panels) - 1)
    strip = Image.new("RGB", (width, PANEL_HEIGHT), (255, 255, 255))
    x = 0
    for panel in panels:
        strip.paste(panel, (x, 0))
        x += panel.width + GAP
    return strip


def padded_film(image, fields):
    """The film on black wide enough that no field runs off its edge, with that padding."""
    left, top, right, bottom = fields_box(fields)
    pad = int(max(0, -left, -top, right - image.width, bottom - image.height)) + 2
    size = (image.width + 2 * pad, image.height + 2 * pad)
    pixels = Image.new("L", size, 0)
    pixels.paste(image, (pad, pad))
    inside = Image.new("L", size, 0)
    inside.paste(255, (pad, pad, pad + image.width, pad + image.height))
    return Film(pixels, inside), pad


def shifted(fields, pad):
    """The fields moved by the film's padding."""
    return [Field(f.x + pad, f.y + pad, f.radius, f.letter) for f in fields]


def compose(cases, overlap_bodies, caption):
    """Every case in a row, lettered A, B, C ... below, with one caption line."""
    fonts = load_fonts()
    strips = [case_strip(case, overlap_bodies, fonts) for case in cases]
    width = sum(s.width for s in strips) + CASE_GAP * (len(strips) + 1)
    height = PANEL_HEIGHT + 150
    figure = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(figure)
    x = CASE_GAP
    for i, strip in enumerate(strips):
        figure.paste(strip, (x, 20))
        label = chr(ord("A") + i)
        draw.text((x + strip.width // 2, PANEL_HEIGHT + 40), label, fill=LABEL_RED,
                  font=fonts["case"], anchor="mt")
        x += strip.width + CASE_GAP
    draw.text((CASE_GAP, height - 30), caption, fill=(60, 60, 60), font=fonts["small"])
    return figure


def load_fonts():
    """DejaVu Sans where the system has it, Pillow's own font otherwise."""
    def font(size, bold=False):
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            return ImageFont.load_default(size)
    return {"small": font(20), "big": font(34), "case": font(64, bold=True)}


# ----------------------------------------------------------------------------------------
# inputs
# ----------------------------------------------------------------------------------------
def read_boostnet(folder, split="training", wanted=None):
    """The films of a BoostNet-layout folder with their 17 centres, cranial first.

    Only the films named in wanted are opened when it is given, so a folder may hold just the
    few films a figure needs beside the split's whole label files.
    """
    folder = Path(folder)
    labels = folder / "labels" / split
    with open(labels / "filenames.csv", newline="") as names_file:
        names = [row[0] for row in csv.reader(names_file)]
    with open(labels / "landmarks.csv", newline="") as rows_file:
        rows = [[float(v) for v in row] for row in csv.reader(rows_file)]
    for name, row in zip(names, rows):
        if wanted and name not in wanted:
            continue
        image = Image.open(folder / "data" / split / name)
        yield Case(image, centres_from_corners(row, image.size), name)


def centres_from_corners(row, size):
    """The centre of each of the 17 bodies from 68 corners given as x's then y's, 0 to 1."""
    width, height = size
    xs, ys = row[:68], row[68:]
    centres = []
    for k in range(17):
        cx = sum(xs[4 * k:4 * k + 4]) / 4 * width
        cy = sum(ys[4 * k:4 * k + 4]) / 4 * height
        centres.append((cx, cy))
    return sorted(centres, key=lambda c: c[1])


def demo_case(seed, curve):
    """A drawn AP spine on a soft background, for a figure that needs no data."""
    rng = np.random.default_rng(seed)
    width, height = 900, 2600
    canvas = Image.new("L", (width, height), 40)
    draw = ImageDraw.Draw(canvas)
    centres, y = [], 380.0
    for k, level in enumerate(LEVELS):
        pitch = 112 if level.startswith("L") else 86 + 1.4 * k
        x = width / 2 + curve * 120 * math.sin((y - 300) / 2000 * 2 * math.pi)
        half_w = 48 + 2.6 * k
        draw.rounded_rectangle((x - half_w, y - pitch * 0.36, x + half_w, y + pitch * 0.36),
                               radius=10, fill=170)
        centres.append((x, y))
        y += pitch
    x5, y5 = centres[-1]
    draw.polygon([(x5 - 120, y5 + 70), (x5 + 120, y5 + 70), (x5 + 40, y5 + 330),
                  (x5 - 40, y5 + 330)], fill=150)
    noise = rng.normal(0, 10, (height, width))
    image = np.asarray(canvas.filter(ImageFilter.GaussianBlur(4)), dtype=float) + noise
    image = Image.fromarray(np.clip(image, 0, 255).astype("uint8"))
    return Case(image, centres, f"demo-{seed}")


def pick_evenly(cases, count):
    """count cases spread evenly through the list, so the figure is not the first few films."""
    cases = list(cases)
    step = max(1, len(cases) // count)
    return cases[::step][:count]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--aasce", help="a BoostNet-layout folder")
    source.add_argument("--demo", action="store_true", help="drawn spines, no data")
    parser.add_argument("--split", default="training")
    parser.add_argument("--names", nargs="*", help="the films to draw, by file name")
    parser.add_argument("--pick", type=int, default=4)
    parser.add_argument("--overlap", type=float, default=2.0, help="bodies of overlap")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.demo:
        cases = [demo_case(i, curve) for i, curve in enumerate([0.0, 0.6, -0.5, 1.0][:args.pick])]
        source = "drawn spines, not films"
    else:
        cases = list(read_boostnet(args.aasce, args.split, args.names))
        cases = cases if args.names else pick_evenly(cases, args.pick)
        source = "AASCE 2019 whole-spine AP films"
    caption = (f"Nine-inch fields (140 mm) cut from {source}, stepped from an anchor below L5 at "
               f"{args.overlap:g} bodies of overlap, shown inverted; stitched panorama; the film. "
               "Not acquired fluoroscopy.")
    compose(cases, args.overlap, caption).save(args.out)
    print(f"wrote {args.out}: {len(cases)} cases")


if __name__ == "__main__":
    main()
