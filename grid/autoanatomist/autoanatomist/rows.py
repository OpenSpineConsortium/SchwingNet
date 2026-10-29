"""Examples from rows: the data a session trains on, one row per column or CT, named row by row so
that adding data is appending rows and nothing already rendered or read is made again (the
owner's ask of 29 October 2026, 15:30 UTC: "I can add more training data without needed to
restart").

A row is a dict with a kind. phantom: id, phenotype, start, count, seed, spacing, sub, noise: a
column of `count` consecutive levels from `start`, drawn by phantom.draw_levels for the phenotype
and the seed, rendered at `spacing` mm with `sub` subsamples a voxel and `noise` HU of noise, tilted
at random by the row's own generator, read by the stand-in oracle. volume: id, ct, labels, names
(label value to level name) or scheme (one of scanimport's, read by oracle.names_of), sub (a
sub-label NIfTI, or nothing) and seed: a CT and its label NIfTI, read by scanimport.volume.load and
the oracle (the engine's export, once bordercall PR 30 lands, behind the same interface). Every
row's crops are jittered (crops.perturbed) by the row's own generator seeded from its seed, so a
row renders the same wherever it stands in the list and whatever stands beside it.

The cache: each row's crops as <cache_dir>/<row digest>.npz, the digest of the row's canonical JSON
with the crop's keys, shape, spacing and jitter, so a changed crop or a changed row is a new file
and an unchanged one is read back; written whole under another name and moved into place, so two
trials rendering one row at once never read a half-written file. digest(rows) names the list as a
whole for a ledger or a manifest. train.make_examples draws the smoke run's examples with one
generator over every phantom; rows draw each phantom with its own, so the two are not the same
examples, and the smoke run keeps its own.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Optional, Sequence

import numpy as np

from . import crops, naming, phantom
from .model import Config
from .oracle import ChordOracle, names_of
from .train import Examples

KINDS = ("phantom", "volume")
PHANTOM_DEFAULTS = {"phenotype": "typical", "start": "L1", "count": 3, "seed": 0, "spacing": 1.25, "sub": 1, "noise": 20.0}
VOLUME_FIELDS = ("ct", "labels", "names", "scheme", "sub", "seed")


def refuse(row: dict, why: str) -> ValueError:
    return ValueError("row %r: %s" % (row.get("id", "?"), why))


def whole(row: dict, name: str, value, low: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < low:
        raise refuse(row, "%s takes a whole number of at least %d, not %r" % (name, low, value))
    return int(value)


def canonical(row: dict) -> dict:
    """The row with every field typed and every default filled, refused in words where a field is
    missing, unknown or of the wrong kind; the form the digests are taken of."""
    if not isinstance(row, dict) or row.get("kind") not in KINDS:
        raise ValueError("a row is a dict whose kind is phantom or volume, not %r" % (row,))
    if not isinstance(row.get("id"), str) or not row["id"]:
        raise ValueError("a row needs an id, a non-empty string, not %r" % (row.get("id"),))
    if row["kind"] == "phantom":
        extra = set(row) - {"kind", "id"} - set(PHANTOM_DEFAULTS)
        if extra:
            raise refuse(row, "a phantom row takes id, %s, not %s" % (", ".join(PHANTOM_DEFAULTS), ", ".join(sorted(extra))))
        r = dict(PHANTOM_DEFAULTS, **{k: v for k, v in row.items() if k in PHANTOM_DEFAULTS})
        if not isinstance(r["phenotype"], str) or not isinstance(r["start"], str):
            raise refuse(row, "phenotype and start are names")
        if not isinstance(r["spacing"], (int, float)) or r["spacing"] <= 0:
            raise refuse(row, "spacing is millimetres above 0, not %r" % (r["spacing"],))
        if not isinstance(r["noise"], (int, float)) or r["noise"] < 0:
            raise refuse(row, "noise is HU, at least 0, not %r" % (r["noise"],))
        return {"kind": "phantom", "id": row["id"], "phenotype": r["phenotype"], "start": r["start"],
                "count": whole(row, "count", r["count"], 1), "seed": whole(row, "seed", r["seed"], 0),
                "spacing": float(r["spacing"]), "sub": whole(row, "sub", r["sub"], 1), "noise": float(r["noise"])}
    extra = set(row) - {"kind", "id"} - set(VOLUME_FIELDS)
    if extra:
        raise refuse(row, "a volume row takes id, %s, not %s" % (", ".join(VOLUME_FIELDS), ", ".join(sorted(extra))))
    for f in ("ct", "labels"):
        if not isinstance(row.get(f), str) or not row[f]:
            raise refuse(row, "%s is a NIfTI path" % f)
    names, scheme = row.get("names"), row.get("scheme")
    if (names is None) == (scheme is None):
        raise refuse(row, "a volume row names its levels by names (label value to level) or by scheme, one of the two")
    if names is not None:
        try:
            names = {int(k): str(v) for k, v in dict(names).items()}
        except (TypeError, ValueError):
            raise refuse(row, "names maps label values to level names, not %r" % (names,)) from None
        bad = sorted(v for v in names.values() if v not in naming.NAME_INDEX)
        if bad:
            raise refuse(row, "levels the naming layer has no name for: %s" % ", ".join(bad))
    elif not isinstance(scheme, str):
        raise refuse(row, "scheme is the name of one of scanimport's label schemes")
    sub = row.get("sub")
    if sub is not None and (not isinstance(sub, str) or not sub):
        raise refuse(row, "sub is a NIfTI path or nothing")
    return {"kind": "volume", "id": row["id"], "ct": row["ct"], "labels": row["labels"],
            "names": {str(k): v for k, v in sorted(names.items())} if names is not None else None, "scheme": scheme,
            "sub": sub, "seed": whole(row, "seed", row.get("seed", 0), 0)}


def dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def digest(rows: Sequence[dict]) -> str:
    """The sha256 of the rows' canonical JSON, in their order: the name of the data as a whole."""
    return hashlib.sha256(dumps([canonical(r) for r in rows]).encode("ascii")).hexdigest()


def crop_record(cfg: Config, jitter: bool) -> dict:
    return {"keys": list(cfg.keys), "shape": list(cfg.shape), "spacing": float(cfg.spacing), "jitter": bool(jitter)}


def row_digest(row: dict, cfg: Config, jitter: bool = True) -> str:
    """The name of one row's crops: the row with the crop that was taken of it."""
    return hashlib.sha256(dumps({"row": canonical(row), "crop": crop_record(cfg, jitter)}).encode("ascii")).hexdigest()


def load_volume(path: str):
    from scanimport import volume as V
    return V.load(path)


def render_row(row: dict, cfg: Config, jitter: bool = True) -> Examples:
    """One row's crops: the column rendered or the CT read, the oracle's readings, each cropped
    (jittered by the row's own generator), with its frames and readings kept."""
    r = canonical(row)
    rng = np.random.default_rng(r["seed"])
    if r["kind"] == "phantom":
        levels = phantom.draw_levels(r["phenotype"], seed=r["seed"], start=r["start"], count=r["count"])
        tilt = (tuple(float(v) for v in rng.normal(size=3)), float(rng.uniform(0.0, 15.0)))
        ph = phantom.render(levels, spacing=(r["spacing"],) * 3, tilt=tilt, sub=r["sub"], noise_hu=r["noise"], seed=r["seed"])
        hu, labels, affine, names, sub = ph.hu, ph.labels, ph.affine, ph.names, None
        meta = dict(r, levels=[lv.name for lv in levels], tilt=[list(tilt[0]), tilt[1]])
        kept = [ph]
    else:
        hu, affine = load_volume(r["ct"])
        labels, affine_l = load_volume(r["labels"])
        if hu.shape != labels.shape or not np.allclose(affine, affine_l, atol=1e-3):
            raise refuse(row, "the CT and the labels are not on one grid")
        names = {int(k): v for k, v in r["names"].items()} if r["names"] is not None else names_of(labels, r["scheme"])
        sub = load_volume(r["sub"])[0] if r["sub"] else None
        meta, kept = dict(r), []
    readings = ChordOracle(cfg.keys).read(labels, affine, names, sub)
    if not readings:
        raise refuse(row, "the oracle read no vertebra")
    out = {"hu": [], "masks": [], "targets": [], "values": [], "names": []}
    frames = []
    for rd in readings:
        if rd.level not in naming.NAME_INDEX:
            raise refuse(row, "the naming layer has no name for %s" % rd.level)
        cf = crops.from_reading(rd, spacing=cfg.spacing, shape=cfg.shape)
        if jitter:
            cf = crops.perturbed(cf, rng)
        out["hu"].append(crops.ct_channel(hu, affine, cf))
        out["masks"].append(crops.mask_channels(labels, affine, cf, rd.label))
        out["targets"].append(crops.targets(rd, cf, cfg.keys))
        out["values"].append(rd.values(list(cfg.keys)))
        out["names"].append(naming.NAME_INDEX[rd.level])
        frames.append(cf)
    return Examples(hu=np.stack(out["hu"]), masks=np.stack(out["masks"]), targets=np.stack(out["targets"]),
                    values=np.stack(out["values"]), names=np.array(out["names"]), spine=np.zeros(len(readings), int),
                    meta=[meta], frames=frames, readings=list(readings), phantoms=kept)


def save_part(path: str, ex: Examples) -> None:
    tmp = "%s.tmp-%d" % (path, os.getpid())
    with open(tmp, "wb") as f:
        np.savez(f, hu=ex.hu, masks=ex.masks, targets=ex.targets, values=ex.values, names=ex.names,
                 meta=np.array(json.dumps(ex.meta)))
    os.replace(tmp, path)


def load_part(path: str) -> Examples:
    with np.load(path) as z:
        return Examples(hu=z["hu"], masks=z["masks"], targets=z["targets"], values=z["values"], names=z["names"],
                        spine=np.zeros(len(z["names"]), int), meta=json.loads(str(z["meta"])))


def examples_for(rows: Sequence[dict], cfg: Config, cache_dir: Optional[str] = None, jitter: bool = True) -> Examples:
    """The examples of every row in order, each read from the cache where its file is there and
    rendered and cached otherwise; spine numbers the rows."""
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    parts: List[Examples] = []
    for row in rows:
        path = os.path.join(cache_dir, row_digest(row, cfg, jitter) + ".npz") if cache_dir else None
        if path and os.path.exists(path):
            parts.append(load_part(path))
            continue
        ex = render_row(row, cfg, jitter)
        if path:
            save_part(path, ex)
        parts.append(ex)
    if not parts:
        raise ValueError("no rows")
    return Examples(hu=np.concatenate([p.hu for p in parts]), masks=np.concatenate([p.masks for p in parts]),
                    targets=np.concatenate([p.targets for p in parts]), values=np.concatenate([p.values for p in parts]),
                    names=np.concatenate([p.names for p in parts]),
                    spine=np.concatenate([np.full(len(p), i) for i, p in enumerate(parts)]),
                    meta=[m for p in parts for m in p.meta], frames=[f for p in parts for f in p.frames],
                    readings=[r for p in parts for r in p.readings], phantoms=[ph for p in parts for ph in p.phantoms])


def cached(rows: Sequence[dict], cfg: Config, cache_dir: str, jitter: bool = True) -> Dict[str, bool]:
    """Which rows' files the cache holds, by id."""
    return {canonical(r)["id"]: os.path.exists(os.path.join(cache_dir, row_digest(r, cfg, jitter) + ".npz")) for r in rows}
