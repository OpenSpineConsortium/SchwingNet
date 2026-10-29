"""Every result as an ArviZ InferenceData, written to NetCDF with its provenance in the attributes.

    rec = records.build(post, truth, group, X, offsets, measures, levels, rates, command=..., seeds=..., ...)
    records.write(rec, "records/exact-rescore/n3.nc")
    rec = records.read("records/exact-rescore/n3.nc")

In ArviZ 1 an InferenceData is an xarray DataTree: one group per kind of thing, each an
xarray Dataset with named dimensions. The groups here are

    posterior        p (field, place): the exact posterior over places of every field; call,
                     top and mapq (field)
    observed_data    x (field, measure, body): the values the field was scored on, NaN where
                     none was read
    truth            place and column (field): the true place and the column each field came
                     from, so a rate can be recomputed from the record
    constant_data    mu and sd (measure, level), offsets (body), the prior over places
    rates            every rate of score.summary as a scalar or a small array

and the root's attributes carry the command that made the record, the seeds, the synthesis
settings, the digests (sha256) of the long table and of this package's code, and the versions
of Python, numpy, xarray and ArviZ, so the record says what made it. NetCDF attributes hold
strings, numbers and flat arrays, so nested rates are stored as JSON text.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from typing import Dict, Optional, Sequence

import numpy as np

from . import __version__, LEVELS

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = "h5netcdf"


def code_digest() -> str:
    """sha256 over this package's own source files, in name order."""
    h = hashlib.sha256()
    for name in sorted(os.listdir(HERE)):
        if name.endswith(".py"):
            with open(os.path.join(HERE, name), "rb") as fh:
                h.update(name.encode() + b"\0" + fh.read() + b"\0")
    return h.hexdigest()


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return _jsonable(o.tolist())
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return o


def build(post: np.ndarray, truth: np.ndarray, group: np.ndarray, X: np.ndarray, offsets: Sequence[int],
          measures: Sequence[str], levels: Sequence[str], rates: dict, command: str, seeds: Dict[str, int],
          synth: dict, mu: Optional[np.ndarray] = None, sd: Optional[np.ndarray] = None,
          digests: Optional[Dict[str, str]] = None, log_prior: Optional[np.ndarray] = None, extra_attrs: Optional[dict] = None,
          noise: Optional[np.ndarray] = None):
    import arviz as az
    import xarray as xr
    from .rule import credible_sets
    post = np.asarray(post, float)
    F, K = post.shape
    places = list(levels)[:K]
    call = post.argmax(1)
    top = post.max(1)
    size, _ = credible_sets(post)
    posterior = xr.Dataset(
        {"p": (("field", "place"), post), "call": ("field", call), "top": ("field", top),
         "credible_size": ("field", size)},
        coords={"field": np.arange(F), "place": places})
    observed = xr.Dataset({"x": (("field", "measure", "body"), np.asarray(X, float))},
                          coords={"field": np.arange(F), "measure": list(measures), "body": np.arange(X.shape[2])})
    truth_ds = xr.Dataset({"place": ("field", np.asarray(truth, int)), "column": ("field", np.asarray(group, int))},
                          coords={"field": np.arange(F)})
    const = {"offsets": ("body", np.asarray(offsets, int)),
             "log_prior": ("place", np.zeros(K) - np.log(K) if log_prior is None else np.asarray(log_prior, float))}
    coords = {"body": np.arange(len(offsets)), "place": places}
    if mu is not None:
        const["mu"] = (("measure", "level"), np.asarray(mu, float))
        const["sd"] = (("measure", "level"), np.asarray(sd, float))
        coords["measure"] = list(measures)
        coords["level"] = list(levels)
    if noise is not None:                    # each measure's own error, which the rule read
        const["noise"] = ("measure", np.asarray(noise, float))
        coords["measure"] = list(measures)
    constant = xr.Dataset(const, coords=coords)
    flat = {}
    for k, v in rates.items():
        if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
            flat[k] = ((), float(v))
    rates_ds = xr.Dataset(flat, attrs={"json": json.dumps(_jsonable(rates), sort_keys=True)})
    tree = xr.DataTree.from_dict({"/posterior": posterior, "/observed_data": observed, "/truth": truth_ds,
                                  "/constant_data": constant, "/rates": rates_ds})
    digests = dict(digests or {})
    digests.setdefault("schwingcheck", code_digest())
    tree.attrs.update({
        "command": command, "seeds": json.dumps(_jsonable(seeds), sort_keys=True),
        "synth": json.dumps(_jsonable(synth), sort_keys=True), "digests": json.dumps(digests, sort_keys=True),
        "measures": json.dumps(list(measures)), "levels": json.dumps(list(levels)), "offsets": json.dumps([int(o) for o in offsets]),
        "n_fields": int(F), "places": int(K), "schwingcheck": __version__,
        "python": platform.python_version(), "numpy": np.__version__, "xarray": xr.__version__, "arviz": az.__version__})
    tree.attrs.update({k: (json.dumps(_jsonable(v)) if isinstance(v, (dict, list, tuple)) else v) for k, v in (extra_attrs or {}).items()})
    return tree


def write(tree, path: str) -> str:
    """Write the record through a temporary file beside it, which takes the record's name only
    once it is whole (os.replace), so that a write that fails part way leaves the record that was
    there before, or none, and never a half-written one."""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    part = os.path.join(folder, ".%s.%d.part" % (os.path.basename(path), os.getpid()))
    try:
        tree.to_netcdf(part, engine=ENGINE)
        os.replace(part, path)
    finally:
        if os.path.exists(part):
            os.remove(part)
    return path


def read(path: str):
    import xarray as xr
    return xr.open_datatree(path, engine=ENGINE)


def rates_of(tree) -> dict:
    """The full rates dictionary a record carries."""
    return json.loads(tree["rates"].ds.attrs["json"])


def attrs_of(tree) -> dict:
    out = dict(tree.attrs)
    for k in ("seeds", "synth", "digests", "measures", "levels", "offsets"):
        if k in out:
            out[k] = json.loads(out[k])
    return out
