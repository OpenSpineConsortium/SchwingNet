"""The pipeline sandbox: deep learning pipelines built from typed blocks in a browser page, and the same rules in Python that check, compile and assemble it.

Source: the thread of 2026-10-30, the owner's words of 16:16 UTC (users "construct a pipline like this
from scratch in an interactive, lowlatency graph contruction GUI", blocks "generic enough to accept all
shapes and types and sizes of data", "rigiorous data transparency, reproducibility, and scaling
standards", and users who "import their own blocks if it meets the same requirements you set") and of
15:12 UTC (the page "as an html with actions tied to button clicks in a github repo"); the note
docs/research/pipeline-sandbox/README.md.

The page, docs/sandbox/pipeline-sandbox.html, is assembled from tools/sandbox/: contract.json (the
shapes every type, block and limit keeps), blocks/<id>.json (one manifest per block), templates/<id>.json
(pipelines to start from), engine.js (the rules: types, ops, propagation, jobs, the two routes, the
manifest check and the prediction), ui.js, page.css and shell.html. This module mirrors engine.js in
Python, problem for problem and digest for digest (tests/test_pipeline_sandbox.py runs both on the same
pipelines and manifests where node is installed), so that the required check holds every block and
template to the rules the page applies, and a request the page opens is one tools/experiments_panel.py
writes and accepts. Where the engine follows JavaScript (=== never takes a bool for a number, a missing
key reads as undefined, String() of a number), so does this module.

    python3 tools/pipeline_sandbox.py write                # docs/sandbox/pipeline-sandbox.html
    python3 tools/pipeline_sandbox.py check                # exit 1 with every problem
    python3 tools/pipeline_sandbox.py check-block PATH     # a manifest file, or a folder of them
    python3 tools/pipeline_sandbox.py compile SPEC.json    # the route, the requests and the plan, as JSON
    python3 tools/pipeline_sandbox.py digest SPEC.json     # the SHA-256 of the canonical pipeline
    python3 tools/pipeline_sandbox.py artifact --out PATH  # the claude.ai edition, a fragment

Nothing here runs anything: the page shows a plan and opens prefilled issues, and every grid job waits
for the owner's word and the number of jobs, as a request of the experiments panel does.
"""

import argparse
import ast
import functools
import hashlib
import importlib.util
import itertools
import json
import math
import re
import sys
import urllib.parse
from pathlib import Path

TOOLS = Path(__file__).resolve().parent


def sibling(name):
    """A tool beside this one, loaded by path: tools/ is no package and never joins sys.path, since
    tools/profile.py would shadow the standard library's profile for anything imported after it."""
    file = TOOLS / f"{name}.py"
    found = sys.modules.get(name)
    if found is not None and getattr(found, "__file__", None) == str(file):
        return found
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


panel = sibling("experiments_panel")
ROOT = TOOLS.parent
SANDBOX = "tools/sandbox"
CONTRACT = f"{SANDBOX}/contract.json"
BLOCKS = f"{SANDBOX}/blocks"
TEMPLATES = f"{SANDBOX}/templates"
PAGE = "docs/sandbox/pipeline-sandbox.html"
PAGE_INPUTS = ("page.css", "shell.html", "engine.js", "ui.js")
NEW_ISSUE = f"https://github.com/{panel.REPO}/issues/new"
WRITE = "python3 tools/pipeline_sandbox.py write"

# Section 3's defaults, used where the contract gives no list, as the engine's norm() does.
STAGES = ("source", "prepare", "split", "augment", "model", "train", "calibrate", "select", "evaluate", "analyse", "report")
KINDS = ("data", "model", "checkpoint", "metrics", "report")
AXES = ("N", "T", "C", "D", "H", "W", "F", "K", "P")
SPATIAL = ("D", "H", "W")
DTYPES = ("uint8", "int16", "int32", "float16", "float32", "bool")
TARGETS = ("none", "level", "mask", "points", "value")
PARTS = ("train", "validation", "test")
MODALITIES = ("any", "fluoro", "radiograph", "mixed", "ct", "drr", "table")
LICENCES = ("commercial", "commercial-share-alike", "non-commercial", "research-internal", "uncut")
JOB_CLASSES = ("none", "cpu", "gpu")
TODAY = ("live", "word", "flow", "pending", "planned")
CODE = ("existing", "own", "planned")
DETERMINISTIC = ("exact", "seeded", "declared")
NEEDS = ("python", "numpy", "scipy", "nibabel", "torch", "torchvision", "monai", "onnxruntime", "jax", "pymc", "metaflow", "wandb")
GLYPHS = ("catalog", "ct", "video", "folder", "synthetic", "recipe", "samples", "normalise", "denoise", "crop", "segment",
          "render", "realism", "features", "split", "splitFamilies", "augment", "network", "unet", "prior", "train",
          "calibrate", "select", "evaluate", "latency", "gap", "morphometry", "naming", "report", "wandb", "card", "fallback")
LIMITS = {"combinations": 64, "array_tasks": 1000, "nodes": 60, "edges": 120, "epochs_most": 200, "hours_most": 48,
          "manifest_bytes": 16384}

ID = re.compile(r"[a-z][a-z0-9_]{1,39}")
NODE_ID = re.compile(r"n[1-9][0-9]{0,3}")
PORT = re.compile(r"[a-z][a-z0-9_]{0,23}")
PARAM = re.compile(r"[a-z][a-z0-9_]{0,31}")
VALUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._,-]{0,79}")
NAMES_PATTERN = "^[a-z0-9_]{1,40}$"
SIZE_FIELD = re.compile(r"sizes\.([A-Za-z])")
SIZE_REF = re.compile(r"sizes\.(.+)")
PULL_REQUEST = re.compile(r"#[0-9]+")
ARRAY_INDEX = re.compile(r"0|[1-9][0-9]{0,9}")

TYPE_FIELDS = ("kind", "axes", "sizes", "dtype", "targets", "classes", "parts", "persons", "modality", "licence", "sources",
               "family", "rank", "trained")
SET_FIELDS = ("dtype", "targets", "classes", "modality", "family", "trained", "persons")
OP_ARITY = {"kind": 2, "set": 3, "size": 3, "axes": 2, "drop_axis": 2, "add_axis": 4, "parts": 2, "licence": 2, "cut": 2}
PATTERN_KEYS = ("kind", "rank", "time", "has_axes", "dtype", "targets", "parts", "needs_parts", "modality", "trained")
PARAM_KINDS = ("choice", "int", "float", "bool", "set", "names")
CONDITION_KEYS = ("in", "not_in", "min", "max", "above", "below", "empty", "nonempty")
EXPERIMENT_KEYS = ("recipe", "epochs", "seed", "hours", "blocks", "only")
CARD_FIELDS = ("origin", "where", "count", "persons", "split", "held_out", "licence")
TODAY_STRINGS = ("route", "word", "flow", "note")
STRUCTURAL = ("port", "accepts", "op", "ref", "param")
EXPECT_KEYS = ("route", "ready", "requests", "gpu_submissions", "cpu_submissions", "gpu_tasks")

# The experiment route's three blocks, the pipeline issue's fixed text and the experiment form's own
# defaults, used only where no node maps a value (experiments_panel.form_text).
CATALOG = "catalog_v1"
CLASSIFIER = "classifier"
TRAINER = "train_classifier"
PIPELINE_MARKER = "<!-- schwingnet-pipeline -->"
PIPELINE_CLOSING = ("Nothing answers this issue yet: the pipeline route waits on the owner's word "
                    "(docs/research/pipeline-sandbox/README.md).")
FORM_DEFAULTS = {"epochs": 20, "seed": 1, "hours": 4}

# What would end a page input's element early, or load something from elsewhere.
ENDS_EARLY = {"page.css": ("</style",), "shell.html": ("<script",), "engine.js": ("</script", "<script", "<!--"),
              "ui.js": ("</script", "<script", "<!--")}
LOADS = ("<script src", "<link", "@import", "fetch(", "xmlhttprequest")
JS_SPACE = " \t\n\v\f\r\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
JS_DECIMAL = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


# ---------------------------------------------------------------------------------------------------
# JavaScript's values in Python: undefined, ===, String() and Number().

class Undefined:
    """JavaScript's undefined: what a missing key reads as; JSON never holds it and canonical JSON skips it."""

    __slots__ = ()

    def __repr__(self):
        return "MISSING"

    def __bool__(self):
        return False


MISSING = Undefined()
BAD = object()  # a ref that names nothing, as the engine's BAD


def is_number_type(value):
    """typeof value === "number": an int or a float, never a bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_finite_number(value):
    """The engine's isNum: a number that is finite."""
    return is_number_type(value) and (isinstance(value, int) or math.isfinite(value))


def is_whole(value):
    """Number.isInteger."""
    return is_number_type(value) and (isinstance(value, int) or value.is_integer())


def same(a, b):
    """JavaScript's ===: a bool is never a number, 5 is 5.0, NaN is nothing, objects only themselves."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if is_number_type(a) and is_number_type(b):
        return a == b
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    return a is b


def times(a, b):
    """a * b as JavaScript's doubles give it: exact while it stays within 2 ** 53, then rounded as a double."""
    exact = a * b
    return exact if isinstance(exact, float) or abs(exact) <= 2 ** 53 else float(a) * float(b)


def plus(a, b):
    """a + b as JavaScript's doubles give it: exact while it stays within 2 ** 53, then rounded as a double."""
    exact = a + b
    return exact if isinstance(exact, float) or abs(exact) <= 2 ** 53 else float(a) + float(b)


def same_value_zero(a, b):
    """How a Set compares: === except that NaN is NaN."""
    if is_number_type(a) and is_number_type(b) and a != a and b != b:
        return True
    return same(a, b)


def index_of(values, value):
    """Array.prototype.indexOf, by ===."""
    for at, item in enumerate(values):
        if same(item, value):
            return at
    return -1


def contains(values, value):
    """Array.prototype.includes as indexOf reads it: === against each item."""
    return index_of(values, value) >= 0


def unique(values):
    """The values in order, each once, as a Set keeps them."""
    out = []
    for value in values:
        if not any(same_value_zero(value, kept) for kept in out):
            out.append(value)
    return out


def array_of(value):
    """A list as itself, anything else as an empty list (the engine's arrayOf)."""
    return value if isinstance(value, list) else []


def js_keys(obj):
    """Object.keys: the keys that read as array indices first, in number order, then the rest in order."""
    keys = list(obj)
    index = sorted((k for k in keys if ARRAY_INDEX.fullmatch(k) and int(k) < 4294967295), key=int)
    taken = set(index)
    return index + [k for k in keys if k not in taken]


def property_key(key):
    """The text a value becomes as an object's key."""
    return key if isinstance(key, str) else js_text(key)


def js_has(obj, key):
    """An own property of an object, by the text a key becomes."""
    return isinstance(obj, dict) and property_key(key) in obj


def js_get(obj, key):
    """The engine's get(): an own property's value, else undefined."""
    return obj.get(property_key(key), MISSING) if isinstance(obj, dict) else MISSING


def shortest_digits(x):
    """The shortest digits that read back as the positive double x, with the decimal point's place."""
    mantissa, _, exponent = repr(x).partition("e")
    whole, _, fraction = mantissa.partition(".")
    digits = whole + fraction
    point = len(whole) + (int(exponent) if exponent else 0)
    stripped = digits.lstrip("0")
    return stripped.rstrip("0"), point - (len(digits) - len(stripped))


def js_number_text(value):
    """String(number) as JavaScript writes it: plain digits up to 1e21, an exponent past 1e21 or below 1e-6."""
    try:
        x = float(value)
    except OverflowError:
        x = math.inf if value > 0 else -math.inf
    if x != x:
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    digits, point = shortest_digits(abs(x))
    count = len(digits)
    if count <= point <= 21:
        return sign + digits + "0" * (point - count)
    if 0 < point <= 21:
        return sign + digits[:point] + "." + digits[point:]
    if -6 < point <= 0:
        return sign + "0." + "0" * -point + digits
    exponent = point - 1
    mantissa = digits[0] + ("." + digits[1:] if count > 1 else "")
    return f"{sign}{mantissa}e{'+' if exponent >= 0 else '-'}{abs(exponent)}"


def js_text(value):
    """String(value) as JavaScript writes it."""
    if value is MISSING:
        return "undefined"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if is_number_type(value):
        return js_number_text(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return js_join(value, ",")
    return "[object Object]"


def js_join(values, separator):
    """Array.prototype.join: null and undefined as nothing, every other value as String() writes it."""
    return separator.join("" if item is None or item is MISSING else js_text(item) for item in values)


def string_number(text):
    """Number(text) for a string, as JavaScript reads one: trimmed, empty as 0, hex, octal and binary."""
    text = text.strip(JS_SPACE)
    if not text:
        return 0.0
    if text in ("Infinity", "+Infinity", "-Infinity"):
        return -math.inf if text[0] == "-" else math.inf
    for prefix, base, digits in (("0x", 16, "0-9a-fA-F"), ("0o", 8, "0-7"), ("0b", 2, "01")):
        if text[:2].lower() == prefix:
            if not re.fullmatch(f"[{digits}]+", text[2:]):
                return math.nan
            try:
                return float(int(text[2:], base))
            except OverflowError:
                return math.inf
    return float(text) if JS_DECIMAL.fullmatch(text) else math.nan


def to_number(value):
    """Number(value), as a comparison with a number reads its other side."""
    if value is MISSING:
        return math.nan
    if value is None:
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    if is_number_type(value):
        return value
    if isinstance(value, (str, list)):
        return string_number(js_text(value))
    return math.nan


def printable(text):
    """Every character printable ASCII, from space to tilde."""
    return all(" " <= ch <= "~" for ch in text)


def js_length(text):
    """A string's length in UTF-16 code units, as JavaScript counts it."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def clone(value):
    """A deep copy that drops undefined values from objects."""
    if isinstance(value, list):
        return [clone(item) for item in value]
    if isinstance(value, dict):
        return {key: clone(value[key]) for key in js_keys(value) if value[key] is not MISSING}
    return value


def deep_equal(a, b):
    """The engine's deepEqual: ===, else lists item by item, else objects key by key."""
    if same(a, b):
        return True
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(deep_equal(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict) and isinstance(b, dict):
        keys = sorted(a)
        return keys == sorted(b) and all(deep_equal(a[key], b[key]) for key in keys)
    return False


def compare_text(a, b):
    """Two values by the code points of their String() text, as Python sorts strings."""
    a, b = js_text(a), js_text(b)
    return (a > b) - (a < b)


def node_number(node_id):
    """The number of a node id ("n12" is 12); an id of another shape sorts after every node."""
    return int(node_id[1:]) if isinstance(node_id, str) and NODE_ID.fullmatch(node_id) else math.inf


def compare_node_ids(a, b):
    """Two node ids by their number, then by their text."""
    na, nb = node_number(a), node_number(b)
    if na != nb:
        return -1 if na < nb else 1
    return compare_text(a, b)


def show(value):
    """A value as a short ASCII word for a problem's text."""
    if value is MISSING:
        return "nothing"
    try:
        text = canonical(value)
    except CanonicalError:
        return "a value that is not plain ASCII JSON"
    return text[:57] + "..." if len(text) > 60 else text


def plural(count, word):
    """A count and its word, with an s unless the count is 1."""
    return f"{js_text(count)} {word}{'' if count == 1 else 's'}"


def plain(value):
    """A result as JSON holds it: undefined left out of objects and written null in lists, as JSON.stringify does."""
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items() if item is not MISSING}
    if isinstance(value, list):
        return [None if item is MISSING else plain(item) for item in value]
    return value


def js_int(text):
    """A JSON integer as JavaScript reads it: a double, exact up to 2 ** 53."""
    if len(text.lstrip("-")) <= 15:
        return int(text)
    value = float(text)
    return int(value) if value.is_integer() and abs(value) <= 2 ** 53 else value


def refuse_constant(name):
    """NaN and Infinity are no JSON, and JSON.parse refuses them too."""
    raise ValueError(f"{name} is not JSON")


def load_json(path):
    """A JSON file as JavaScript's JSON.parse reads it: no NaN or Infinity, integers as doubles."""
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_int=js_int, parse_constant=refuse_constant)


# ---------------------------------------------------------------------------------------------------
# Numbers as Python writes them, canonical JSON and the digest (section 8).

def py_fixed(value, places):
    """format(value, ".<places>f"): the double's exact value rounded half to even."""
    return format(float(value), f".{places}f")


def py_g(value):
    """f"{value:g}", the request's hours word."""
    return f"{float(value):g}"


def py_round(value, places):
    """round(value, places), as Number(pyFixed(value, places)) reads it back."""
    return float(py_fixed(value, places))


class CanonicalError(ValueError):
    """A value canonical JSON cannot write: a character outside printable ASCII, or no finite number."""

    def __init__(self, path, why):
        super().__init__(f"{path or 'the value'} {why}")


def format_number(value, path="the value"):
    """An integer when whole and below 1e15, else six decimals with the zeros and the point stripped."""
    if not is_finite_number(value):
        raise CanonicalError(path, "is not a finite number")
    if is_whole(value) and abs(value) < 1e15:
        return str(int(value))
    return py_fixed(value, 6).rstrip("0").rstrip(".")


def float_plain(value):
    """A value written plainly: 0, or from 0.0001 to below 1e9 with at most six decimals, so no reader
    meets an exponent (section 5)."""
    if not is_finite_number(value):
        return False
    if value == 0:
        return True
    return 0.0001 <= value < 1e9 and float(py_fixed(value, 6)) == value


def write_string(text, path):
    """A key or a text as canonical JSON writes it."""
    if not printable(text):
        raise CanonicalError(path, "holds a character outside printable ASCII")
    return json.dumps(text)


def write_value(value, out, path):
    """One value of canonical JSON onto out; path names it in an error."""
    if value is None:
        out.append("null")
    elif isinstance(value, bool):
        out.append("true" if value else "false")
    elif is_number_type(value):
        out.append(format_number(value, path))
    elif isinstance(value, str):
        out.append(write_string(value, path))
    elif isinstance(value, list):
        out.append("[")
        for at, item in enumerate(value):
            if at:
                out.append(",")
            write_value(item, out, f"{path}[{at}]")
        out.append("]")
    elif isinstance(value, dict):
        out.append("{")
        for n, key in enumerate(sorted(k for k, item in value.items() if item is not MISSING)):
            if n:
                out.append(",")
            out.append(write_string(key, path + " key"))
            out.append(":")
            write_value(value[key], out, f"{path}.{key}")
        out.append("}")
    else:
        raise CanonicalError(path, "is not a JSON value")


def canonical(value):
    """Canonical JSON: keys sorted by code point, no spaces, numbers by format_number, ASCII strings only."""
    out = []
    write_value(value, out, "$")
    return "".join(out)


def sha256_hex(text):
    """The lowercase hex SHA-256 of a text's UTF-8 bytes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------------------------
# The contract, the blocks and the experiment route's data, each read with defaults so that a partial
# DATA object never raises.

def keys_or_list(value, fallback):
    """A contract list given as an object's keys or as a list, else the default."""
    if isinstance(value, dict):
        return js_keys(value)
    return list(value) if isinstance(value, list) else list(fallback)


def list_or(value, fallback):
    """A contract list as given, else the default."""
    return list(value) if isinstance(value, list) else list(fallback)


class Contract:
    """The contract as the engine reads it: every list with its default where the file gives none."""

    def __init__(self, contract):
        c = contract if isinstance(contract, dict) else {}
        stages = c.get("stages") if isinstance(c.get("stages"), list) else [{"id": s} for s in STAGES]
        self.stages = [s for s in (item.get("id", MISSING) if isinstance(item, dict) else item for item in stages)
                       if isinstance(s, str)]
        self.kinds = keys_or_list(c.get("kinds"), KINDS)
        self.axes = keys_or_list(c.get("axes"), AXES)
        self.spatial = list_or(c.get("spatial"), SPATIAL)
        self.dtypes = list_or(c.get("dtypes"), DTYPES)
        self.targets = list_or(c.get("targets"), TARGETS)
        self.parts = list_or(c.get("parts"), PARTS)
        self.modalities = list_or(c.get("modalities"), MODALITIES)
        self.licences = list_or(c.get("licences"), LICENCES)
        self.job_classes = list_or(c.get("job_classes"), JOB_CLASSES)
        self.today = list_or(c.get("today"), TODAY)
        self.code = list_or(c.get("code"), CODE)
        self.deterministic = list_or(c.get("deterministic"), DETERMINISTIC)
        self.needs = list_or(c.get("needs"), NEEDS)
        self.glyphs = list_or(c.get("glyphs"), GLYPHS)
        limits = c.get("limits") if isinstance(c.get("limits"), dict) else {}
        self.limits = {key: limits[key] if is_finite_number(limits.get(key, MISSING)) else default
                       for key, default in LIMITS.items()}
        self.probes = [p for p in array_of(c.get("probes")) if isinstance(p, dict)]


def normal_contract(contract):
    """A Contract, made from a contract's JSON where one is not given."""
    return contract if isinstance(contract, Contract) else Contract(contract)


def contract_of(data):
    """DATA's contract as the engine reads it."""
    return Contract(data.get("contract") if isinstance(data, dict) else None)


def block_map(data):
    """Each block's manifest by id, the first of an id kept."""
    found = {}
    for manifest in array_of(data.get("blocks") if isinstance(data, dict) else None):
        if isinstance(manifest, dict) and isinstance(manifest.get("id"), str) and manifest["id"] not in found:
            found[manifest["id"]] = manifest
    return found


def block_of(blocks, block_id):
    """A block's manifest by id; None for an unknown id or one that is no text."""
    return blocks.get(block_id) if isinstance(block_id, str) else None


class Experiment:
    """DATA.experiment as the engine reads it, with the experiments panel's own words where it gives none."""

    def __init__(self, data):
        x = data.get("experiment") if isinstance(data, dict) else None
        x = x if isinstance(x, dict) else {}

        def text(key, default):
            return x[key] if isinstance(x.get(key), str) else default

        self.repo = text("repo", panel.REPO)
        self.new_url = text("new", NEW_ISSUE)
        self.label = text("label", panel.ISSUE_LABEL)
        self.marker = text("marker", panel.ISSUE_MARKER)
        self.flow = text("flow", panel.FLOW_HEAD)
        self.fields = [f for f in array_of(x.get("fields")) if isinstance(f, str)]
        self.defaults = x["defaults"] if isinstance(x.get("defaults"), dict) else {}


def whole_or_float(value):
    """48.0 as 48, so the page carries the panel's limit as the SPEC writes it."""
    return int(value) if isinstance(value, float) and value.is_integer() else value


def experiment_data(root=ROOT):
    """DATA.experiment from the experiments panel: the issue's words, the Blocks fields with version 1's
    defaults, the limits and the recipe names (SPEC section 16)."""
    catalog = panel.block_catalog(root)
    return {"repo": panel.REPO, "new": NEW_ISSUE, "label": panel.ISSUE_LABEL, "marker": panel.ISSUE_MARKER,
            "flow": panel.FLOW_HEAD, "fields": catalog["fields"], "defaults": catalog["defaults"],
            "epochs_most": panel.EPOCHS_MOST, "hours_most": whole_or_float(panel.HOURS_MOST),
            "recipes": [r["name"] for r in panel.recipes(root)]}


def params_of(manifest):
    """A manifest's params that are objects with a text name."""
    params = manifest.get("params") if isinstance(manifest, dict) else None
    return [p for p in array_of(params) if isinstance(p, dict) and isinstance(p.get("name"), str)]


def param_named(manifest, name):
    """A manifest's param of that name, or None."""
    for p in params_of(manifest):
        if p["name"] == name:
            return p
    return None


def ports_of(manifest, key):
    """A manifest's inputs or outputs that are objects with a text name."""
    ports = manifest.get(key) if isinstance(manifest, dict) else None
    return [p for p in array_of(ports) if isinstance(p, dict) and isinstance(p.get("name"), str)]


def port_names(manifest, key):
    """The names of a manifest's inputs or outputs."""
    return [p["name"] for p in ports_of(manifest, key)]


def job_of(manifest):
    """A manifest's job, an empty object where it has none."""
    job = manifest.get("job") if isinstance(manifest, dict) else None
    return job if isinstance(job, dict) else {}


def compute_class(manifest):
    """cpu or gpu for a block that takes a job of its own, else None."""
    cls = job_of(manifest).get("class")
    return cls if isinstance(cls, str) and cls in ("cpu", "gpu") else None


# ---------------------------------------------------------------------------------------------------
# Type records (section 4) and patterns (section 6).

def empty_type():
    """The type record an output starts from when its block has no connected input (section 4)."""
    return {"kind": "data", "axes": [], "sizes": {}, "dtype": "any", "targets": "none", "classes": None, "parts": [],
            "persons": False, "modality": "any", "licence": "uncut", "sources": [], "family": None, "rank": 0,
            "trained": False}


def rank_of(axes, contract=None):
    """How many spatial axes (D, H, W) a list of axes holds."""
    spatial = contract.spatial if contract is not None else list(SPATIAL)
    return sum(1 for axis in array_of(axes) if contains(spatial, axis))


def copy_type(source):
    """A full, separate copy of a type; a missing field takes the empty type's value."""
    t = empty_type()
    if not isinstance(source, dict):
        return t
    for field in TYPE_FIELDS:
        if field in source and source[field] is not MISSING:
            t[field] = clone(source[field])
    for field, empty in (("axes", list), ("sizes", dict), ("parts", list), ("sources", list)):
        if not isinstance(t[field], empty):
            t[field] = empty()
    return t


def licence_later(a, b, contract):
    """Of two licence classes, the more restricted; an unknown class gives way to the other."""
    ia, ib = index_of(contract.licences, a), index_of(contract.licences, b)
    if ia < 0:
        return b
    if ib < 0:
        return a
    return a if ia >= ib else b


def licence_earlier(a, b, contract):
    """Of two licence classes, the less restricted; an unknown class gives way to the other."""
    ia, ib = index_of(contract.licences, a), index_of(contract.licences, b)
    if ia < 0:
        return b
    if ib < 0:
        return a
    return a if ia <= ib else b


def prune_sizes(t):
    """Only the sizes of axes the type still has, in the axes' order."""
    sizes = {}
    for axis in t["axes"]:
        key = property_key(axis)
        if key in t["sizes"]:
            sizes[key] = t["sizes"][key]
    t["sizes"] = sizes


def finish_type(t, contract):
    """The rank from the axes, the sizes pruned and the parts in the contract's order."""
    t["rank"] = rank_of(t["axes"], contract)
    prune_sizes(t)
    t["parts"] = [part for part in contract.parts if contains(t["parts"], part)]


def merge_lineage(t, other, contract):
    """Another input's sources, licence and person key carried into an output."""
    t["sources"] = t["sources"] + array_of(other.get("sources"))
    t["licence"] = licence_later(t["licence"], other.get("licence", MISSING), contract)
    t["persons"] = t["persons"] is True and other.get("persons") is True


def field_of(t, field, contract):
    """A type's field as (found, value): a TYPE_FIELDS name, or sizes.X, null when the size is unknown."""
    size = SIZE_FIELD.fullmatch(property_key(field))
    if size:
        axis = size.group(1)
        return True, clone(t["sizes"][axis]) if axis in t["sizes"] else None
    if not contains(TYPE_FIELDS, field):
        return False, None
    if field == "rank":
        return True, rank_of(t["axes"], contract)
    return True, clone(t.get(field, MISSING))


def problem(code, node, port, field, level, text):
    """A problem as section 10 shapes it; undefined parts are null."""
    def known(value):
        return None if value is MISSING else value
    return {"code": code, "node": known(node), "port": known(port), "field": known(field), "level": level or "error",
            "text": text}


def matches(pattern, type_record, contract):
    """Section 6: one "type" problem per key of the pattern the type does not meet."""
    c = normal_contract(contract)
    out = []

    def fail(key, text):
        out.append(problem("type", None, None, key, "error", text))

    if not isinstance(pattern, dict):
        fail("kind", "the input states no pattern, so it takes nothing")
        return out
    t = copy_type(type_record)
    kinds = array_of(pattern.get("kind"))
    if not contains(kinds, t["kind"]):
        fail("kind", f"takes {js_join(kinds, ' or ') or 'no kind'}, not {show(t['kind'])}")
    if "rank" in pattern:
        rank = rank_of(t["axes"], c)
        if not contains(array_of(pattern["rank"]), rank):
            fail("rank", f"takes {js_join(array_of(pattern['rank']), ' or ')}-D data, not {rank}-D")
    match_time(pattern, t, fail)
    if "has_axes" in pattern:
        missing = [a for a in array_of(pattern["has_axes"]) if not contains(t["axes"], a)]
        if missing:
            fail("has_axes", f"needs the axes {js_join(missing, ', ')}")
    match_lists(pattern, t, fail)
    if "trained" in pattern and not same(pattern["trained"], t["trained"]):
        fail("trained", "takes a trained model" if pattern["trained"] else "takes an untrained model")
    return out


def match_time(pattern, t, fail):
    """The pattern's time: yes needs a T axis, no refuses one."""
    time = pattern.get("time", MISSING)
    if same(time, "yes") and not contains(t["axes"], "T"):
        fail("time", "takes data with a time axis T")
    if same(time, "no") and contains(t["axes"], "T"):
        fail("time", "takes data without a time axis T")


def match_lists(pattern, t, fail):
    """The pattern's dtype, targets, parts, needs_parts and modality."""
    if "dtype" in pattern and not same(t["dtype"], "any") and not contains(array_of(pattern["dtype"]), t["dtype"]):
        fail("dtype", f"takes {js_join(array_of(pattern['dtype']), ' or ')}, not {show(t['dtype'])}")
    if "targets" in pattern and not contains(array_of(pattern["targets"]), t["targets"]):
        fail("targets", f"takes targets {js_join(array_of(pattern['targets']), ' or ')}, not {show(t['targets'])}")
    parts = pattern.get("parts", MISSING)
    if same(parts, "split") and not t["parts"]:
        fail("parts", "takes data split into parts, and this is unsplit")
    if same(parts, "unsplit") and t["parts"]:
        fail("parts", "takes unsplit data, and this is split")
    if "needs_parts" in pattern:
        lacking = [p for p in array_of(pattern["needs_parts"]) if not contains(t["parts"], p)]
        if lacking:
            fail("needs_parts", f"needs the parts {js_join(lacking, ', ')}")
    if ("modality" in pattern and not same(t["modality"], "any")
            and not contains(array_of(pattern["modality"]), t["modality"])):
        fail("modality", f"takes {js_join(array_of(pattern['modality']), ' or ')}, not {show(t['modality'])}")


def accepts(pattern, type_record, contract):
    """A type the pattern takes with no problem."""
    return not matches(pattern, type_record, contract)


# ---------------------------------------------------------------------------------------------------
# Ops (section 7).

def parse_ref(ref):
    """@param.NAME, @in.PORT.FIELD or @self.FIELD as a dict with its scope; "bad" for any other @ text."""
    if not isinstance(ref, str) or not ref.startswith("@"):
        return None
    bits = ref.split(".")
    if bits[0] == "@param" and len(bits) == 2:
        return {"scope": "param", "name": bits[1]}
    if bits[0] == "@in" and len(bits) >= 3:
        return {"scope": "in", "port": bits[1], "field": ".".join(bits[2:])}
    if bits[0] == "@self" and len(bits) >= 2:
        return {"scope": "self", "field": ".".join(bits[1:])}
    return {"scope": "bad"}


def is_ref(value):
    """A text that starts with @, which an op or a mapping reads as a ref."""
    return isinstance(value, str) and value.startswith("@")


class OpContext:
    """What a node's refs read: its params, its param and input names, its connected inputs and the type being built."""

    def __init__(self, params, param_names, input_names, inputs):
        self.params = params
        self.param_names = param_names
        self.input_names = input_names
        self.inputs = inputs
        self.building = None


def read_value(value, ctx, contract):
    """A literal as itself, a ref as what it names, BAD when it names nothing."""
    if not is_ref(value):
        return clone(value)
    ref = parse_ref(value)
    if ref["scope"] == "param":
        return clone(js_get(ctx.params, ref["name"])) if ref["name"] in ctx.param_names else BAD
    if ref["scope"] == "in":
        if ref["port"] not in ctx.input_names:
            return BAD
        t = ctx.inputs.get(ref["port"])
        if t is None:
            return None if field_of(empty_type(), ref["field"], contract)[0] else BAD
        found, read = field_of(t, ref["field"], contract)
        return read if found else BAD
    if ref["scope"] == "self" and ctx.building is not None:
        found, read = field_of(ctx.building, ref["field"], contract)
        return read if found else BAD
    return BAD


def valid_set_value(field, value, contract):
    """A value the set op may give the field."""
    if field == "dtype":
        return same(value, "any") or contains(contract.dtypes, value)
    if field == "targets":
        return contains(contract.targets, value)
    if field == "classes":
        return value is None or (is_whole(value) and value >= 1)
    if field == "modality":
        return contains(contract.modalities, value)
    if field == "family":
        return value is None or isinstance(value, str)
    return isinstance(value, bool)


def valid_size(value):
    """A size: null, or a whole number from 1."""
    return value is None or (is_whole(value) and value >= 1)


def valid_axis_list(value, contract):
    """A list of distinct axes of the contract."""
    return (isinstance(value, list) and all(contains(contract.axes, a) for a in value)
            and len(unique(value)) == len(value))


def valid_part_list(value, contract):
    """A list of distinct parts of the contract."""
    return (isinstance(value, list) and all(contains(contract.parts, p) for p in value)
            and len(unique(value)) == len(value))


def item(values, at):
    """values[at], or undefined past the end."""
    return values[at] if at < len(values) else MISSING


def apply_op(t, op, ctx, contract, fail):
    """One op on the type being built; a failure calls fail(text) and leaves the type as it was. A null
    value removes a size, adds an axis with no size and sets classes or family to null; any other op it
    leaves as it was, with no problem."""
    if not isinstance(op, list) or not isinstance(item(op, 0), str) or op[0] not in OP_ARITY:
        fail(f"an unknown op {show(op)}")
        return
    ctx.building = t
    name = op[0]

    def value(at):
        read = read_value(item(op, at), ctx, contract)
        if read is BAD:
            fail(f"{name} names an unknown reference {show(item(op, at))}")
        return read

    if name == "kind":
        op_kind(t, value, contract, fail)
    elif name == "set":
        op_set(t, op, value, contract, fail)
    elif name == "size":
        op_size(t, op, value, fail)
    elif name == "axes":
        op_axes(t, value, contract, fail)
    elif name == "drop_axis":
        op_drop_axis(t, op)
    elif name == "add_axis":
        op_add_axis(t, op, value, contract, fail)
    elif name == "parts":
        op_parts(t, value, contract, fail)
    else:
        op_licence(t, name, value, contract, fail)


def op_kind(t, value, contract, fail):
    """kind: the type becomes another kind."""
    v = value(1)
    if v is BAD or v is None:
        return
    if not contains(contract.kinds, v):
        fail(f"kind {show(v)} is not a kind")
        return
    t["kind"] = v


def op_set(t, op, value, contract, fail):
    """set: one of the fields set may change takes a value."""
    field = item(op, 1)
    if not contains(SET_FIELDS, field):
        fail(f"set names a field it cannot set: {show(field)}")
        return
    v = value(2)
    if v is BAD or (v is None and field not in ("classes", "family")):
        return
    if not valid_set_value(field, v, contract):
        fail(f"set {field} to {show(v)}, which it cannot be")
        return
    t[field] = v


def op_size(t, op, value, fail):
    """size: an axis's size, or null to forget it."""
    axis = item(op, 1)
    v = value(2)
    if v is BAD:
        return
    if v is None:
        if isinstance(axis, str):
            t["sizes"].pop(axis, None)
        return
    if not contains(t["axes"], axis):
        fail(f"size names the axis {show(axis)}, which the type lacks")
        return
    if not valid_size(v):
        fail(f"size {js_text(axis)} to {show(v)}, which is not a whole number from 1")
        return
    t["sizes"][property_key(axis)] = v


def op_axes(t, value, contract, fail):
    """axes: the whole list of axes, the sizes kept for those that stay."""
    v = value(1)
    if v is BAD or v is None:
        return
    if not valid_axis_list(v, contract):
        fail(f"axes {show(v)} is not a list of distinct axes")
        return
    t["axes"] = list(v)
    prune_sizes(t)


def op_drop_axis(t, op):
    """drop_axis: an axis and its size leave the type; an axis it lacks is no problem."""
    at = index_of(t["axes"], item(op, 1))
    if at >= 0:
        del t["axes"][at]
        t["sizes"].pop(property_key(item(op, 1)), None)


def op_add_axis(t, op, value, contract, fail):
    """add_axis: a new axis before another, or last, with its size or none."""
    axis = item(op, 1)
    if not contains(contract.axes, axis):
        fail(f"add_axis names {show(axis)}, which is not an axis")
        return
    if contains(t["axes"], axis):
        return
    v = value(3) if len(op) > 3 else None
    if v is BAD:
        return
    if not valid_size(v):
        fail(f"add_axis {js_text(axis)} of size {show(v)}, which is not a whole number from 1")
        return
    before = item(op, 2)
    at = -1 if before is None or before is MISSING else index_of(t["axes"], before)
    t["axes"].insert(len(t["axes"]) if at < 0 else at, axis)
    if v is not None:
        t["sizes"][property_key(axis)] = v


def op_parts(t, value, contract, fail):
    """parts: the split parts the data carries."""
    v = value(1)
    if v is BAD or v is None:
        return
    if not valid_part_list(v, contract):
        fail(f"parts {show(v)} is not a list of distinct parts")
        return
    t["parts"] = list(v)


def op_licence(t, name, value, contract, fail):
    """licence takes the later class (the more restricted use), cut the earlier (a recipe only narrows)."""
    v = value(1)
    if v is BAD or v is None:
        return
    if not contains(contract.licences, v):
        fail(f"{name} {show(v)} is not a licence class")
        return
    later = name == "licence"
    t["licence"] = licence_later(t["licence"], v, contract) if later else licence_earlier(t["licence"], v, contract)


def op_name_of(op):
    """The op's name for a problem's field, as the engine's `op && op[0]` reads it, else None."""
    if isinstance(op, (list, str)):
        first = op[0] if op else MISSING
    elif isinstance(op, dict):
        first = op.get("0", MISSING)
    else:
        first = MISSING
    return first if isinstance(first, str) else None


def compute_outputs(manifest, inputs, params, contract, fail):
    """Every output of a block from its connected input types (port -> type) and its params; each op
    problem goes to fail(port, op name, text)."""
    input_ports = ports_of(manifest, "inputs")
    ctx = OpContext(params, {p["name"] for p in params_of(manifest)}, {p["name"] for p in input_ports}, inputs)
    outs = {}
    for output in ports_of(manifest, "outputs"):
        base = output_base(output, input_ports, inputs)
        t = empty_type() if base is None else copy_type(inputs[base])
        for op in array_of(output.get("ops")):
            apply_op(t, op, ctx, contract, functools.partial(fail, output["name"], op_name_of(op)))
        finish_type(t, contract)
        for p in input_ports:
            if p["name"] != base and p["name"] in inputs:
                merge_lineage(t, inputs[p["name"]], contract)
        if same(manifest.get("stage", MISSING), "source") and isinstance(manifest.get("id"), str):
            t["sources"].append(manifest["id"])
        t["sources"] = sorted(unique([s for s in t["sources"] if isinstance(s, str)]))
        outs[output["name"]] = t
    return outs


def output_base(output, input_ports, inputs):
    """The input an output starts from: its `from` when connected, else the first connected input."""
    source = output.get("from")
    if isinstance(source, str) and source in inputs:
        return source
    for p in input_ports:
        if p["name"] in inputs:
            return p["name"]
    return None


# ---------------------------------------------------------------------------------------------------
# Params and rules (sections 5 and 10).

@functools.lru_cache(maxsize=256)
def full_regex(pattern):
    """A param's names pattern held to the whole name, as new RegExp("^(?:" + pattern + ")$") is; None when
    it does not compile. JavaScript's and Python's regular expressions agree on the plain classes,
    repeats and anchors a pattern of names uses."""
    try:
        return re.compile("^(?:" + pattern + r")\Z", re.ASCII)
    except (re.error, RecursionError, OverflowError, ValueError):
        return None


def names_pattern(p):
    """A names param's pattern, or the default one."""
    return p["pattern"] if "pattern" in p else NAMES_PATTERN


def in_order(values, options):
    """Values in the options' order, each once."""
    last = -1
    for value in values:
        at = index_of(options, value)
        if at <= last:
            return False
        last = at
    return True


def value_problem(p, v):
    """Why a value breaks its param's rules, or None when it keeps them."""
    kind = p.get("kind", MISSING)
    check = {"choice": choice_problem, "int": int_problem, "float": float_problem, "bool": bool_problem,
             "set": set_problem, "names": names_problem}.get(kind) if isinstance(kind, str) else None
    if check is None:
        return f"{js_text(p.get('name', MISSING))} has an unknown kind {show(kind)}"
    return check(p, js_text(p.get("name", MISSING)), v)


def choice_problem(p, name, v):
    """A choice is one of the choices."""
    choices = array_of(p.get("choices"))
    if contains(choices, v) and isinstance(v, str):
        return None
    return f"{name} {show(v)} is not one of {js_join(choices, ', ')}"


def int_problem(p, name, v):
    """A whole number from low to high."""
    if not is_whole(v):
        return f"{name} {show(v)} is not a whole number"
    low, high = p.get("low", MISSING), p.get("high", MISSING)
    if not (v >= to_number(low) and v <= to_number(high)):
        return f"{name} {show(v)} is outside {show(low)} to {show(high)}"
    return None


def float_problem(p, name, v):
    """A finite number from low, or above it, to high, written plainly."""
    if not is_finite_number(v):
        return f"{name} {show(v)} is not a number"
    low, high, above = p.get("low", MISSING), p.get("high", MISSING), p.get("above") is True
    if not (v > to_number(low) if above else v >= to_number(low)):
        return f"{name} {show(v)} is not {'above ' if above else 'at least '}{show(low)}"
    if not v <= to_number(high):
        return f"{name} {show(v)} is above {show(high)}"
    if not float_plain(v):
        return f"{name} {show(v)} is not 0 or a number from 0.0001 with at most 6 decimals"
    return None


def bool_problem(p, name, v):
    """true or false."""
    return None if isinstance(v, bool) else f"{name} {show(v)} is not true or false"


def set_problem(p, name, v):
    """A list of the options in their order, each once."""
    options = array_of(p.get("options"))
    if not isinstance(v, list):
        return f"{name} {show(v)} is not a list"
    if not all(isinstance(x, str) and contains(options, x) for x in v):
        return f"{name} {show(v)} names something outside {js_join(options, ', ')}"
    if not in_order(v, options):
        return f"{name} {show(v)} repeats a value or breaks the options' order"
    return None


def names_problem(p, name, v):
    """A list of distinct names that the pattern matches whole."""
    if not isinstance(v, list):
        return f"{name} {show(v)} is not a list"
    pattern = names_pattern(p)
    compiled = full_regex(pattern) if isinstance(pattern, str) else None
    if compiled is None:
        return f"{name} has a pattern that is not a regular expression"
    if not all(isinstance(x, str) and compiled.search(x) for x in v):
        return f"{name} {show(v)} holds a name that does not match {js_text(pattern)}"
    if len(unique(v)) != len(v):
        return f"{name} {show(v)} repeats a name"
    return None


def empty_value(v):
    """An empty list, 0, false, "" or "none"."""
    return ((isinstance(v, list) and not v) or (is_number_type(v) and v == 0) or v is False
            or (isinstance(v, str) and v in ("", "none")))


def condition_holds(cond, v):
    """One condition of a rule on one param's value."""
    if not isinstance(cond, dict):
        return False
    if "in" in cond and not any(deep_equal(x, v) for x in array_of(cond["in"])):
        return False
    if "not_in" in cond and any(deep_equal(x, v) for x in array_of(cond["not_in"])):
        return False
    for key, holds in (("min", lambda x, b: x >= b), ("max", lambda x, b: x <= b), ("above", lambda x, b: x > b),
                       ("below", lambda x, b: x < b)):
        if key in cond and not (is_finite_number(v) and holds(v, to_number(cond[key]))):
            return False
    if "empty" in cond and empty_value(v) != (cond["empty"] is True):
        return False
    if "nonempty" in cond and empty_value(v) == (cond["nonempty"] is True):
        return False
    return True


def rule_fails(rule, params):
    """A rule fails when every `when` condition holds and some `need` condition does not."""
    if not isinstance(rule, dict):
        return False
    when = rule["when"] if isinstance(rule.get("when"), dict) else {}
    need = rule["need"] if isinstance(rule.get("need"), dict) else {}
    if not all(condition_holds(when[k], js_get(params, k)) for k in js_keys(when)):
        return False
    return any(not condition_holds(need[k], js_get(params, k)) for k in js_keys(need))


def product(value_lists):
    """Every choice of one value from each list, the last list varying fastest, as itertools.product."""
    return [list(choice) for choice in itertools.product(*value_lists)]


def overlay(base, keys, values):
    """Params with a combination's values put over them."""
    params = clone(base)
    for key, value in zip(keys, values, strict=True):
        params[key] = clone(value)
    return params


def effective_params(node, manifest):
    """The manifest's defaults with the node's params on top; an unknown name given is kept."""
    out = {}
    for p in params_of(manifest):
        out[p["name"]] = clone(p.get("default", MISSING))
    given = node.get("params") if isinstance(node, dict) and isinstance(node.get("params"), dict) else {}
    for key in js_keys(given):
        if given[key] is not MISSING:
            out[key] = clone(given[key])
    return out


# ---------------------------------------------------------------------------------------------------
# The canonical spec and its digest (section 8).

def or_null(value):
    """undefined as null, as a canonical spec writes a missing field."""
    return None if value is MISSING else value


def spec_of(spec, data):
    """The canonical spec: nodes by number with every param filled, vary lists of one value or more,
    edges by (from, out, to, in); no layout, id, about or expect."""
    blocks = block_map(data)
    s = spec if isinstance(spec, dict) else {}
    nodes = [canonical_node(n, blocks) for n in array_of(s.get("nodes")) if isinstance(n, dict)]
    nodes.sort(key=functools.cmp_to_key(lambda a, b: compare_node_ids(a["id"], b["id"])))
    edges = [{"from": or_null(e.get("from", MISSING)), "out": or_null(e.get("out", MISSING)),
              "to": or_null(e.get("to", MISSING)), "in": or_null(e.get("in", MISSING))}
             for e in array_of(s.get("edges")) if isinstance(e, dict)]
    edges.sort(key=functools.cmp_to_key(compare_edges))
    return {"sandbox": 1, "name": s["name"] if isinstance(s.get("name"), str) else "", "nodes": nodes, "edges": edges}


def canonical_node(n, blocks):
    """A node as the canonical spec holds it, its params filled from its block's defaults."""
    manifest = block_of(blocks, n.get("block", MISSING))
    vary_given = n.get("vary")
    vary = {}
    for key in sorted(vary_given) if isinstance(vary_given, dict) else []:
        if isinstance(vary_given[key], list) and vary_given[key]:
            vary[key] = clone(vary_given[key])
    if manifest is not None:
        params = effective_params(n, manifest)
    else:
        params = clone(n["params"]) if isinstance(n.get("params"), dict) else {}
    return {"id": or_null(n.get("id", MISSING)), "block": or_null(n.get("block", MISSING)),
            "version": or_null(n.get("version", MISSING)), "params": params, "vary": vary}


def compare_edges(a, b):
    """Two edges by from, out, to and in, as the canonical spec sorts them."""
    return (compare_node_ids(a["from"], b["from"]) or compare_text(a["out"], b["out"])
            or compare_node_ids(a["to"], b["to"]) or compare_text(a["in"], b["in"]))


def canonical_text(spec, data):
    """The canonical spec's JSON, or None when it holds what canonical JSON cannot write."""
    try:
        return canonical(spec_of(spec, data))
    except CanonicalError:
        return None


def digest(spec, data):
    """The lowercase hex SHA-256 of the canonical spec, or "" when it cannot be written (propagate says why)."""
    text = canonical_text(spec, data)
    return "" if text is None else sha256_hex(text)


# ---------------------------------------------------------------------------------------------------
# Propagation (section 10).

class Problems:
    """A list of problems: one per occurrence, or, merged, one per (code, field) with the texts of repeats joined."""

    def __init__(self, merge=False):
        self.list = []
        self.merge = merge
        self.index = {}

    def add(self, found):
        """One problem kept, or merged into the one of its (code, field)."""
        if self.merge:
            key = tuple("\0" if part is None else js_text(part) for part in (found["code"], found["field"]))
            if key in self.index:
                known = self.index[key]
                if found["text"] not in known["text"].split("; "):
                    known["text"] += "; " + found["text"]
                return
            self.index[key] = found
        self.list.append(found)


class Graph:
    """The nodes with valid, unique ids, the others apart, and the edges between two nodes of the graph."""

    def __init__(self, canon):
        self.by_id, self.invalid = {}, []
        for n in canon["nodes"]:
            node_id = n["id"]
            if not isinstance(node_id, str) or not NODE_ID.fullmatch(node_id) or node_id in self.by_id:
                self.invalid.append(n)
            else:
                self.by_id[node_id] = n
        self.edges = [e for e in canon["edges"] if self.has(e["from"]) and self.has(e["to"])]

    def has(self, node_id):
        """A node of the graph."""
        return isinstance(node_id, str) and node_id in self.by_id

    def get(self, node_id):
        """A node by id, or None."""
        return self.by_id.get(node_id) if isinstance(node_id, str) else None

    def edges_into(self, node_id, port=MISSING):
        """The edges into a node, or into one of its inputs."""
        return [e for e in self.edges if same(e["to"], node_id) and (port is MISSING or same(e["in"], port))]

    def sorted_nodes(self):
        """The nodes by number."""
        return sorted(self.by_id.values(), key=functools.cmp_to_key(lambda a, b: compare_node_ids(a["id"], b["id"])))


def topological_order(graph):
    """Kahn's sort, ties by node number; what it cannot place, on or after a cycle, comes back as left."""
    indegree = {node_id: 0 for node_id in graph.by_id}
    after = {node_id: [] for node_id in graph.by_id}
    for e in graph.edges:
        indegree[e["to"]] += 1
        after[e["from"]].append(e["to"])
    ready = [node_id for node_id, count in indegree.items() if count == 0]
    order = []
    by_number = functools.cmp_to_key(compare_node_ids)
    while ready:
        ready.sort(key=by_number)
        node_id = ready.pop(0)
        order.append(node_id)
        for down in after[node_id]:
            indegree[down] -= 1
            if indegree[down] == 0:
                ready.append(down)
    placed = set(order)
    return order, sorted((node_id for node_id in graph.by_id if node_id not in placed), key=by_number)


def total_combinations(prop):
    """The product of every node's combinations."""
    total = 1
    for node_id in js_keys(prop["nodes"]):
        total = times(total, prop["nodes"][node_id]["combinations"])
    return total


class Propagation:
    """One run of section 10 over a spec: the steps in the engine's order, each problem kept where it occurs."""

    def __init__(self, spec, data):
        self.contract = contract_of(data)
        self.blocks = block_map(data)
        self.canon = spec_of(spec, data)
        self.graph = Graph(self.canon)
        self.per_node = {node_id: Problems() for node_id in self.graph.by_id}
        self.graph_problems = Problems()
        self.nodes = {node_id: {"inputs": {}, "outputs": {}, "problems": [], "fan": 1, "combinations": 1}
                      for node_id in self.graph.by_id}

    def report(self, code, node, port, field, level, text):
        """A problem, kept with its node or with the graph."""
        found = problem(code, node, port, field, level, text)
        if isinstance(node, str) and node in self.per_node:
            self.per_node[node].add(found)
        else:
            self.graph_problems.add(found)

    def manifest_of(self, node_id):
        """The manifest of a node's block, or None."""
        n = self.graph.get(node_id)
        return block_of(self.blocks, n["block"]) if n is not None else None

    def run(self):
        """Section 10 in order: ids and text, blocks, order and cycles, edges, inputs, params, types, limits."""
        self.check_ids_and_text()
        self.check_blocks()
        order, left = topological_order(self.graph)
        for node_id in left:
            self.report("cycle", node_id, None, None, "error",
                        "the node is on a cycle, or after one, so nothing can run it in order")
        self.check_edges()
        self.check_inputs()
        for node_id, n in self.graph.by_id.items():
            self.check_params(node_id, n)
        for node_id in order:
            self.type_node(node_id)
        for node_id in left:
            self.nodes[node_id]["fan"] = self.nodes[node_id]["combinations"]
        self.check_limits()
        return {"order": order, "nodes": self.nodes, "problems": self.assembled()}

    def assembled(self):
        """Each node's problems in canonical node order, then the graph's."""
        problems = []
        for node_id in self.graph.by_id:
            self.nodes[node_id]["problems"] = self.per_node[node_id].list
        for n in self.canon["nodes"]:
            if self.graph.has(n["id"]) and self.graph.by_id[n["id"]] is n:
                problems += self.per_node[n["id"]].list
        return problems + self.graph_problems.list

    def check_ids_and_text(self):
        """Node ids that are no id or are used twice, and text canonical JSON cannot write."""
        for n in self.graph.invalid:
            node_id = n["id"]
            twice = isinstance(node_id, str) and NODE_ID.fullmatch(node_id)
            self.report("node", node_id if isinstance(node_id, str) else None, None, None, "error",
                        f"two nodes are named {node_id}; each node needs its own id" if twice
                        else f"the node id {show(node_id)} is not n1 to n9999")
        if not printable(self.canon["name"]):
            self.report("text", None, None, "name", "error", "the pipeline's name holds a character outside printable ASCII")
        for node_id, n in self.graph.by_id.items():
            try:
                canonical(n)
            except CanonicalError as error:
                self.report("text", node_id, None, None, "error",
                            f"the node holds a value canonical JSON cannot write ({error})")
        for e in self.canon["edges"]:
            try:
                canonical(e)
            except CanonicalError:
                self.report("text", e["to"] if self.graph.has(e["to"]) else None, None, None, "error",
                            "an edge holds text outside printable ASCII")

    def check_blocks(self):
        """Each node's block is known, and the version it asks for is the page's."""
        for node_id, n in self.graph.by_id.items():
            manifest = block_of(self.blocks, n["block"])
            if manifest is None:
                self.report("block", node_id, None, None, "error", f"the block {show(n['block'])} is not known here")
            elif not same(n["version"], manifest.get("version", MISSING)):
                self.report("version", node_id, None, None, "warn",
                            f"the node asks for version {show(n['version'])} of {manifest['id']}; this page has "
                            f"version {show(manifest.get('version', MISSING))}")

    def check_edges(self):
        """Each edge joins an output its upstream block has to an input its downstream block has."""
        for e in self.canon["edges"]:
            port = e["in"] if isinstance(e["in"], str) else None
            if not self.graph.has(e["to"]):
                self.report("port", None, port, None, "error", f"an edge goes to {show(e['to'])}, which is not a node")
                continue
            if not self.graph.has(e["from"]):
                self.report("port", e["to"], port, None, "error", f"an edge comes from {show(e['from'])}, which is not a node")
                continue
            up, down = self.manifest_of(e["from"]), self.manifest_of(e["to"])
            why = []
            if up is not None and not contains(port_names(up, "outputs"), e["out"]):
                why.append(f"{up['id']} has no output {show(e['out'])}")
            if down is not None and not contains(port_names(down, "inputs"), e["in"]):
                why.append(f"{down['id']} has no input {show(e['in'])}")
            if why:
                self.report("port", e["to"], port, None, "error", f"the edge from {e['from']}: {' and '.join(why)}")

    def check_inputs(self):
        """Each input takes one edge at most, and each required input has one."""
        for node_id in self.graph.by_id:
            manifest = self.manifest_of(node_id)
            for p in ports_of(manifest, "inputs") if manifest is not None else []:
                count = len(self.graph.edges_into(node_id, p["name"]))
                if count > 1:
                    self.report("port", node_id, p["name"], None, "error",
                                f"the input {p['name']} has {count} edges; it takes one")
                if count == 0 and p.get("optional") is not True:
                    self.report("input", node_id, p["name"], None, "error", f"the input {p['name']} is not connected")

    def check_params(self, node_id, n):
        """Section 10 steps 4 and 5: each given and varied value against its param, the combinations and the rules."""
        varied = js_keys(n["vary"])
        combinations = 1
        for key in varied:
            combinations = times(combinations, len(n["vary"][key]))
        self.nodes[node_id]["combinations"] = combinations
        manifest = self.manifest_of(node_id)
        if manifest is None:
            return
        known = {}
        for p in params_of(manifest):
            known.setdefault(p["name"], p)
        self.check_given(node_id, n, manifest, known)
        self.check_varied(node_id, n, manifest, known, varied)
        limit = self.contract.limits["combinations"]
        if combinations > limit:
            self.report("vary", node_id, None, None, "error",
                        f"the node varies into {js_text(combinations)} combinations; at most {js_text(limit)}")
        own = [key for key in varied if key in known]
        combos = product([n["vary"][key] for key in own]) if combinations <= limit else []
        for rule in array_of(manifest.get("rules")):
            if rule_fails(rule, n["params"]) or any(rule_fails(rule, overlay(n["params"], own, values)) for values in combos):
                say = rule["say"] if isinstance(rule, dict) and isinstance(rule.get("say"), str) else "a rule fails"
                self.report("rule", node_id, None, None, "error", say)

    def check_given(self, node_id, n, manifest, known):
        """Each value a node gives one of its block's params holds."""
        for key in js_keys(n["params"]):
            p = known.get(key)
            if p is None:
                self.report("param", node_id, None, key, "error", f"{manifest['id']} has no param {show(key)}")
                continue
            why = value_problem(p, n["params"][key])
            if why:
                self.report("param", node_id, None, key, "error", why)

    def check_varied(self, node_id, n, manifest, known, varied):
        """Each varied param may vary, and each of its values holds."""
        for key in varied:
            p = known.get(key)
            if p is None:
                self.report("param", node_id, None, key, "error", f"{manifest['id']} has no param {show(key)} to vary")
                continue
            if p.get("vary") is not True:
                self.report("vary", node_id, None, key, "error", f"{p['name']} is not a param this block can vary")
            for value in n["vary"][key]:
                why = value_problem(p, value)
                if why:
                    self.report("param", node_id, None, key, "error", why)

    def type_node(self, node_id):
        """Section 10 steps 6 to 8 for one node in order: its fan, its input types against their patterns,
        its outputs and what it reads."""
        n, entry, manifest = self.graph.by_id[node_id], self.nodes[node_id], self.manifest_of(node_id)
        widest = 0
        for up in unique([e["from"] for e in self.graph.edges_into(node_id)]):
            widest = max(widest, self.nodes[up]["fan"])
        select = manifest is not None and same(manifest.get("stage", MISSING), "select")
        entry["fan"] = times(1 if select else (widest or 1), entry["combinations"])
        if manifest is None:
            return
        inputs = self.input_types(node_id, manifest)
        for p in ports_of(manifest, "inputs"):
            if p["name"] not in inputs:
                continue
            entry["inputs"][p["name"]] = copy_type(inputs[p["name"]])
            for q in matches(p.get("accepts", MISSING), inputs[p["name"]], self.contract):
                self.report("type", node_id, p["name"], q["field"], "error", f"the input {p['name']} {q['text']}")

        def op_failed(port, op_name, text):
            self.report("op", node_id, port, op_name, "error", f"the output {port}: {text}")

        entry["outputs"] = compute_outputs(manifest, inputs, n["params"], self.contract, op_failed)
        self.check_reads(node_id, manifest, inputs)

    def input_types(self, node_id, manifest):
        """Each connected input's type, from the first edge into it in canonical order."""
        inputs = {}
        for p in ports_of(manifest, "inputs"):
            feeds = self.graph.edges_into(node_id, p["name"])
            if not feeds:
                continue
            t = js_get(self.nodes[feeds[0]["from"]]["outputs"], feeds[0]["out"])
            if t is not MISSING:
                inputs[p["name"]] = copy_type(t)
        return inputs

    def check_reads(self, node_id, manifest, inputs):
        """Only evaluation and report read test, and every part a block reads is in its data."""
        reads_value = manifest.get("reads")
        reads = array_of(reads_value.get("parts") if isinstance(reads_value, dict) else None)
        stage = manifest.get("stage", MISSING)
        if contains(reads, "test") and not same(stage, "evaluate") and not same(stage, "report"):
            self.report("test", node_id, None, None, "error", f"{manifest['id']} reads the test part outside evaluation and report")
        for port, t in inputs.items():
            if not same(t["kind"], "data"):
                continue
            lacking = [part for part in reads if not contains(t["parts"], part)]
            if lacking:
                self.report("parts", node_id, port, None, "error",
                            f"{manifest['id']} reads {js_join(lacking, ', ')}, which the data on {port} does not have")

    def check_limits(self):
        """The pipeline's nodes, edges and combinations within the contract's limits."""
        limits = self.contract.limits
        nodes, edges = len(self.canon["nodes"]), len(self.canon["edges"])
        if nodes > limits["nodes"]:
            self.report("limit", None, None, None, "error", f"the pipeline has {nodes} nodes; at most {js_text(limits['nodes'])}")
        if edges > limits["edges"]:
            self.report("limit", None, None, None, "error", f"the pipeline has {edges} edges; at most {js_text(limits['edges'])}")
        total = total_combinations({"nodes": self.nodes})
        if total > limits["combinations"]:
            self.report("limit", None, None, None, "error",
                        f"the pipeline varies into {js_text(total)} combinations in all; at most {js_text(limits['combinations'])}")


def propagate(spec, data):
    """Section 10: {order, nodes: {id: {inputs, outputs, problems, fan, combinations}}, problems}, each
    problem kept once per occurrence, each node's in canonical order and then the graph's."""
    return Propagation(spec, data).run()


# ---------------------------------------------------------------------------------------------------
# Jobs (section 11).

def hours_of(job, params):
    """A job's hours per task: a number, or the param a ref names; 0 where it names none."""
    hours = job.get("hours", MISSING)
    if is_finite_number(hours):
        return hours
    ref = parse_ref(hours)
    if ref is not None and ref["scope"] == "param":
        value = js_get(params, ref["name"])
        return value if is_finite_number(value) else 0
    return 0


def first_compute_upstream(graph, blocks, node_id, manifest):
    """The first connected upstream node, by the block's input order, that is a compute node."""
    for p in ports_of(manifest, "inputs"):
        feeds = graph.edges_into(node_id, p["name"])
        if not feeds:
            continue
        up = graph.get(feeds[0]["from"])
        cls = compute_class(block_of(blocks, up["block"]) if up is not None else None)
        if cls:
            return {"id": feeds[0]["from"], "class": cls}
    return None


def jobs(spec, data, prop=None):
    """Section 11: a row per cpu or gpu node in order, a rider in its host's job, and the totals per class."""
    contract, blocks, graph = contract_of(data), block_map(data), Graph(spec_of(spec, data))
    if not (isinstance(prop, dict) and isinstance(prop.get("order"), list)):
        prop = propagate(spec, data)
    rows, row_of, problems = [], {}, Problems()
    for node_id in prop["order"]:
        n = graph.get(node_id)
        manifest = block_of(blocks, n["block"]) if n is not None else None
        cls = compute_class(manifest)
        if not cls or not js_has(prop["nodes"], node_id):
            continue
        job, tasks = job_of(manifest), prop["nodes"][node_id]["fan"]
        row = {"node": node_id, "block": manifest["id"], "class": cls, "submissions": 0, "tasks": tasks,
               "hours": hours_of(job, n["params"]), "rides_with": None}
        host = job_host(graph, blocks, node_id, manifest, cls, row_of) if job.get("with_upstream") is True else None
        if host is not None:
            row["rides_with"] = host["node"]
            host["hours"] = plus(host["hours"], row["hours"])
        else:
            row["submissions"] = 1 if job.get("array") is True else tasks
            if job.get("array") is True and tasks > contract.limits["array_tasks"]:
                problems.add(problem("limit", node_id, None, None, "error",
                                     f"the array job has {js_text(tasks)} tasks; at most {js_text(contract.limits['array_tasks'])}"))
        rows.append(row)
        row_of[node_id] = row
    return {"rows": rows, "totals": job_totals(rows), "problems": problems.list}


def job_host(graph, blocks, node_id, manifest, cls, row_of):
    """The row a with_upstream node rides in: its first compute upstream's of the same class, or that one's host."""
    up = first_compute_upstream(graph, blocks, node_id, manifest)
    if not up or up["class"] != cls or up["id"] not in row_of:
        return None
    host = row_of[up["id"]]
    return row_of[host["rides_with"]] if host["rides_with"] else host


def job_totals(rows):
    """Submissions, tasks and hours per class, a rider counted in its host's job."""
    totals = {"cpu": {"submissions": 0, "tasks": 0, "hours": 0}, "gpu": {"submissions": 0, "tasks": 0, "hours": 0}}
    for row in rows:
        if row["rides_with"]:
            continue
        total = totals[row["class"]]
        total["submissions"] = plus(total["submissions"], row["submissions"])
        total["tasks"] = plus(total["tasks"], row["tasks"])
        total["hours"] = plus(total["hours"], times(row["tasks"], row["hours"]))
    for total in totals.values():
        total["hours"] = py_round(total["hours"], 2)
    return totals


# ---------------------------------------------------------------------------------------------------
# Routes and compile (section 12).

def word_value(value):
    """A block's value as one word of a request: a list joined by "," ("none" when empty), a number as
    canonical JSON writes it."""
    if isinstance(value, list):
        return ",".join(word_value(x) for x in value) or "none"
    if is_number_type(value):
        return format_number(value) if is_finite_number(value) else js_text(value)
    if value is None or value is MISSING:
        return "none"
    return js_text(value)


def differs_from_default(value, default):
    """A Blocks value other than version 1's default, so its word goes in the request."""
    if isinstance(value, list) or isinstance(default, list):
        return not (isinstance(value, list) and isinstance(default, list) and deep_equal(value, default))
    if is_number_type(value) and is_number_type(default):
        return not same(value, default)
    return not deep_equal(value, default)


def mapped_value(value, params, entry):
    """A value an experiment mapping names for one node: a ref read from its params or its input and
    output types, else the literal; null where a port or field is missing."""
    if not is_ref(value):
        return clone(value)
    ref = parse_ref(value)
    if ref["scope"] == "param":
        return clone(js_get(params, ref["name"]))
    if ref["scope"] == "in":
        t = js_get(entry["inputs"], ref["port"]) if entry is not MISSING else MISSING
        if not t:
            return None
        found, read = field_of(t, ref["field"], None)
        return read if found else None
    if ref["scope"] == "self" and entry is not MISSING:
        keys = js_keys(entry["outputs"])
        found, read = field_of(entry["outputs"][keys[0]], ref["field"], None) if keys else (False, None)
        return read if found else None
    return None


def experiment_why(graph, blocks, prop, problems, contract):
    """Why the pipeline is off the experiment route: one {code, text} per rule it breaks, none when it is on it."""
    nodes = graph.sorted_nodes()
    why = []
    errors = sum(1 for p in problems if p["level"] == "error")
    if errors:
        why.append({"code": "errors", "text": f"the pipeline has {plural(errors, 'error')} to fix first"})
    unmapped = [n for n in nodes if not isinstance(js_get(block_of(blocks, n["block"]), "experiment"), dict)]
    if unmapped:
        names = ", ".join(unique([js_text(n["block"]) for n in unmapped]))
        why.append({"code": "not_mapped", "text": f"an experiment request cannot carry {names}"})
    why += shape_why(nodes, graph)
    outside, unplain = values_why(nodes, blocks)
    if outside:
        why.append({"code": "only", "text": "outside what the experiment route runs: " + "; ".join(unique(outside))})
    if unplain:
        why.append({"code": "float_plain", "text": "a number the request would carry is not 0 or from 0.0001 with at "
                    "most 6 decimals: " + "; ".join(unique(unplain))})
    total = total_combinations(prop)
    if total > contract.limits["combinations"]:
        why.append({"code": "too_many", "text": f"the pipeline varies into {js_text(total)} runs; one request each, at most "
                    f"{js_text(contract.limits['combinations'])}"})
    return why


def shape_why(nodes, graph):
    """The route's shape: one catalog, classifier and trainer, no block twice, every node reached from the catalog."""
    why = []
    for block_id, code, words in ((CATALOG, "catalog", "the frame catalog (catalog_v1)"), (CLASSIFIER, "classifier", "classifier"),
                                  (TRAINER, "train", "trainer (train_classifier)")):
        count = sum(1 for n in nodes if same(n["block"], block_id))
        if count != 1:
            why.append({"code": code, "text": f"the experiment route needs exactly one {words}; this has {count}"})
    seen = {}
    for n in nodes:
        seen[js_text(n["block"])] = seen.get(js_text(n["block"]), 0) + 1
    twice = sorted(block_id for block_id, count in seen.items() if count > 1)
    if twice:
        why.append({"code": "duplicate", "text": "a block is used twice: " + ", ".join(twice)})
    reached = {n["id"] for n in nodes if same(n["block"], CATALOG)}
    grew = True
    while grew:
        grew = False
        for e in graph.edges:
            if e["from"] in reached and e["to"] not in reached:
                reached.add(e["to"])
                grew = True
    cut = [n["id"] for n in nodes if n["id"] not in reached]
    if cut:
        why.append({"code": "unconnected", "text": "not reached from the catalog: " + ", ".join(cut)})
    return why


def values_why(nodes, blocks):
    """The values a request would carry: those outside a block's `only`, and floats that are not plain."""
    outside, unplain = [], []
    for n in nodes:
        manifest = block_of(blocks, n["block"])
        mapping = js_get(manifest, "experiment")
        if not isinstance(mapping, dict):
            continue
        if isinstance(mapping.get("only"), dict):
            outside += only_outside(n, mapping["only"])
        unplain += unplain_values(n, manifest, mapping)
    return outside, unplain


def only_outside(n, only):
    """A node's values outside what its block's `only` lets through."""
    found = []
    for key in js_keys(only):
        allowed = array_of(only[key])
        for value in [js_get(n["params"], key)] + (list(n["vary"][key]) if key in n["vary"] else []):
            if not any(deep_equal(a, value) for a in allowed):
                found.append(f"{n['id']} {key} {show(value)} (the route takes {', '.join(show(a) for a in allowed)})")
    return found


def unplain_values(n, manifest, mapping):
    """The floats a node would put in a request that are not written plainly."""
    slots = [mapping[key] for key in ("recipe", "epochs", "seed", "hours") if key in mapping]
    if isinstance(mapping.get("blocks"), dict):
        slots += [mapping["blocks"][key] for key in js_keys(mapping["blocks"])]
    found = []
    for slot in slots:
        ref = parse_ref(slot)
        if ref is not None and ref["scope"] == "param":
            p = param_named(manifest, ref["name"])
            if p is None or not same(p.get("kind", MISSING), "float"):
                continue
            values = n["vary"][ref["name"]] if ref["name"] in n["vary"] else [js_get(n["params"], ref["name"])]
            found += [f"{n['id']} {ref['name']} {show(v)}" for v in values if is_number_type(v) and not float_plain(v)]
        elif is_number_type(slot) and not is_whole(slot) and not float_plain(slot):
            found.append(f"{n['id']} {show(slot)}")
    return found


def build_requests(graph, blocks, prop, experiment):
    """One request per combination of every varied param over the graph, node by number then param by
    name, the last varying fastest."""
    nodes = graph.sorted_nodes()
    dims = [{"node": n["id"], "param": key, "values": n["vary"][key]} for n in nodes for key in sorted(n["vary"])]
    return [request_for(choice, nodes, dims, blocks, prop, experiment) for choice in product([d["values"] for d in dims])]


def mapped_request(nodes, params_by_node, blocks, prop):
    """What the nodes' experiment mappings give for one combination: recipe, epochs, seed, hours and the
    Blocks fields; a later node's value wins over an earlier one's."""
    values = {"recipe": "none", "epochs": MISSING, "seed": MISSING, "hours": MISSING}
    mapped = {}
    for n in nodes:
        mapping = js_get(block_of(blocks, n["block"]), "experiment")
        if not isinstance(mapping, dict):
            continue
        params, entry = params_by_node[n["id"]], js_get(prop["nodes"], n["id"])
        for key in ("recipe", "epochs", "seed", "hours"):
            if key in mapping:
                values[key] = mapped_value(mapping[key], params, entry)
        if isinstance(mapping.get("blocks"), dict):
            for key in js_keys(mapping["blocks"]):
                mapped[key] = mapped_value(mapping["blocks"][key], params, entry)
    if values["recipe"] is None or values["recipe"] is MISSING or values["recipe"] == "":
        values["recipe"] = "none"
    for key in ("epochs", "seed"):
        if values[key] is None or values[key] is MISSING:
            values[key] = FORM_DEFAULTS[key]
    if not is_finite_number(values["hours"]):
        values["hours"] = FORM_DEFAULTS["hours"]
    return values, mapped


def request_for(choice, nodes, dims, blocks, prop, experiment):
    """One request: its values, the issue's title and body (experiments_panel's own), its link and command."""
    params_by_node = {n["id"]: clone(n["params"]) for n in nodes}
    combination = []
    for dim, value in zip(dims, choice, strict=True):
        params_by_node[dim["node"]][dim["param"]] = clone(value)
        combination.append({"node": dim["node"], "param": dim["param"], "value": clone(value)})
    values, mapped = mapped_request(nodes, params_by_node, blocks, prop)
    blocks_all, named = {}, []
    for field in experiment.fields:
        default = js_get(experiment.defaults, field)
        if field in mapped:
            blocks_all[field] = clone(mapped[field])
            if differs_from_default(mapped[field], default):
                named.append(f"{field}={word_value(mapped[field])}")
        else:
            blocks_all[field] = clone(default)
    epochs, seed, hours = values["epochs"], values["seed"], values["hours"]
    epochs_word = format_number(epochs) if is_number_type(epochs) else js_text(epochs)
    seed_word = format_number(seed) if is_number_type(seed) else js_text(seed)
    hours_word, recipe_word = py_g(hours), js_text(values["recipe"])
    title = panel.request_title(named, epochs_word)
    body = panel.issue_body(named, epochs_word, seed_word, hours_word, recipe_word)
    lines = body.split("\n")
    query = urllib.parse.urlencode([("title", title), ("labels", experiment.label), ("body", body)])
    return {"recipe": recipe_word, "epochs": epochs, "seed": seed, "hours": hours, "hours_word": hours_word,
            "blocks": blocks_all, "named": named, "title": title, "body": body, "url": f"{experiment.new_url}?{query}",
            "lines": lines[1:lines.index("") if "" in lines else -1],
            "command": panel.flow_command(named, epochs_word, seed_word, hours_word, recipe_word, head=experiment.flow),
            "combination": combination}


def pipeline_issue(name, hex_digest, route, totals, text):
    """The pipeline route's issue: the digest, the route, the jobs and the canonical spec, waiting on the owner."""
    gpu, cpu = totals["gpu"], totals["cpu"]
    jobs_line = (f"jobs: {js_text(gpu['submissions'])} GPU submission(s) ({js_text(gpu['tasks'])} tasks, "
                 f"{format_number(gpu['hours'])} GPU-hours), {js_text(cpu['submissions'])} CPU submission(s)")
    body = "\n".join([PIPELINE_MARKER, "", f"digest: {hex_digest}", f"route: {route}", jobs_line, "", "```json",
                      "" if text is None else text, "```", "", PIPELINE_CLOSING]) + "\n"
    return {"title": f"Pipeline: {name} ({hex_digest[:12]})", "body": body}


def compile_spec(spec, data, prop=None):
    """Section 12: {digest, route, ready, why, requests, plan, jobs, pipeline_issue, problems}. Named so
    that Python's own compile stays itself; the engine calls it compile."""
    blocks, experiment = block_map(data), Experiment(data)
    canon = spec_of(spec, data)
    graph = Graph(canon)
    if not (isinstance(prop, dict) and isinstance(prop.get("order"), list)):
        prop = propagate(spec, data)
    planned = jobs(spec, data, prop)
    problems = prop["problems"] + planned["problems"]
    try:
        text = canonical(canon)
    except CanonicalError:
        text = None
    hex_digest = "" if text is None else sha256_hex(text)
    why = experiment_why(graph, blocks, prop, problems, contract_of(data))
    route = "pipeline" if why else "experiment"
    requests = build_requests(graph, blocks, prop, experiment) if route == "experiment" else []
    plan = [dict(row, stage=js_get(blocks.get(row["block"]), "stage"), today=clone(js_get(blocks.get(row["block"]), "today")))
            for row in planned["rows"]]
    totals = clone(planned["totals"])
    if route == "experiment":
        hours = 0
        for request in requests:
            hours = plus(hours, request["hours"])
        totals["gpu"] = {"submissions": len(requests), "tasks": len(requests), "hours": py_round(hours, 2)}
    return {"digest": hex_digest, "route": route, "ready": route == "experiment", "why": why, "requests": requests,
            "plan": plan, "jobs": totals, "pipeline_issue": pipeline_issue(canon["name"], hex_digest, route, totals, text),
            "problems": problems}


# ---------------------------------------------------------------------------------------------------
# The manifest check (section 13): at most one problem per (code, field), its text naming every failure.

def check_manifest(manifest, contract):
    """R1 to R13 on a manifest's shape, as the page checks an imported block: [{code, field, text}], at
    most one per (code, field), its text naming every failure. The files R10 and R13 name are
    code_problems' to check, since the page cannot see them."""
    c = normal_contract(contract)
    found = Problems(merge=True)

    def bad(code, field, text):
        found.add({"code": code, "node": None, "port": None, "field": field, "level": "error", "text": text})

    if isinstance(manifest, dict):
        check_shape(manifest, c, found, bad)
    else:
        bad("field", None, "a block manifest is a JSON object")
    return [{"code": p["code"], "field": p["field"], "text": p["text"]} for p in found.list]


def check_shape(m, c, found, bad):
    """Section 13 in the engine's order. The probes run only when no port, accepts, op, ref or param
    problem came first, since a broken port would fail every probe for the same reason."""
    check_identity(m, c, bad)
    params = check_param_list(m, bad)
    input_names = check_input_ports(m, c, bad)
    check_output_ports(m, c, bad, params, input_names)
    check_rule_list(m, bad, params)
    check_read_parts(m, c, bad)
    check_job(m, c, bad, params)
    check_determinism(m, c, bad, params)
    check_generic(m, c, bad, any(p["code"] in STRUCTURAL for p in found.list))
    if "resolve" in m and m["resolve"] is not None and not isinstance(m["resolve"], str):
        bad("field", "resolve", "resolve is null or a text")
    check_experiment(m, c, bad, params, input_names)
    check_needs(m, c, bad)
    check_code(m, c, bad)
    check_today(m, c, bad)
    check_text(m, c, bad)
    check_card(m, bad)


def text_length(value, low, high):
    """A text of low to high characters, counted as JavaScript counts them."""
    return isinstance(value, str) and low <= js_length(value) <= high


def nonempty_text(value):
    """A text with at least one character."""
    return isinstance(value, str) and value != ""


def check_identity(m, c, bad):
    """R1: the format, the id, the version, the words and the stage and glyph from the contract."""
    if not same(m.get("block", MISSING), 1):
        bad("field", "block", "block is 1, the manifest format")
    block_id = m.get("id", MISSING)
    if not isinstance(block_id, str) or not ID.fullmatch(block_id):
        bad("id", "id", f"id {show(block_id)} is not lowercase letters, digits and _, 2 to 40 long, starting with a letter")
    version = m.get("version", MISSING)
    if not is_whole(version) or version < 1:
        bad("field", "version", "version is a whole number from 1")
    if not text_length(m.get("title", MISSING), 1, 60):
        bad("field", "title", "title is a text of 1 to 60 characters")
    if not contains(c.stages, m.get("stage", MISSING)):
        bad("field", "stage", f"stage {show(m.get('stage', MISSING))} is not one of {js_join(c.stages, ', ')}")
    if not text_length(m.get("summary", MISSING), 1, 120):
        bad("field", "summary", "summary is one line of 1 to 120 characters")
    if not text_length(m.get("does", MISSING), 1, 800):
        bad("field", "does", "does is a text of 1 to 800 characters")
    if not contains(c.glyphs, m.get("glyph", MISSING)):
        bad("field", "glyph", f"glyph {show(m.get('glyph', MISSING))} is not one of the contract's glyphs")


class ParamIndex:
    """The params a manifest names well: their names, and each param by its name."""

    def __init__(self):
        self.names = set()
        self.by_name = {}


def check_param_list(m, bad):
    """R3: params is a list of objects, each with a unique name, a known kind and a default its own rules take."""
    index = ParamIndex()

    def say(text):
        bad("param", "params", text)

    params = m.get("params", MISSING)
    if not isinstance(params, list):
        say("params is a list")
        return index
    for i, p in enumerate(params):
        if not isinstance(p, dict):
            say(f"param {i} is not an object")
            continue
        name = p.get("name", MISSING)
        if not isinstance(name, str) or not PARAM.fullmatch(name):
            say(f"param {i} has the name {show(name)}, not lowercase letters, digits and _ up to 32")
        elif name in index.names:
            say(f"two params are named {name}")
        else:
            index.names.add(name)
            index.by_name[name] = p
        label = name if isinstance(name, str) else f"param {i}"
        if "vary" in p and not isinstance(p["vary"], bool):
            say(f"{label} has vary that is not true or false")
        if "what" in p and not isinstance(p["what"], str):
            say(f"{label} has what that is not a text")
        check_param(p, i, say)
    return index


def check_param(p, i, say):
    """One param: its kind's own fields, then a default that its rules take."""
    label = p["name"] if isinstance(p.get("name"), str) else f"param {i}"
    kind = p.get("kind", MISSING)
    if not contains(PARAM_KINDS, kind):
        say(f"{label} has kind {show(kind)}, not one of {', '.join(PARAM_KINDS)}")
        return
    if not kind_fields_hold(p, kind, label, say):
        return
    if "default" not in p:
        say(f"{label} has no default")
        return
    why = value_problem(p, p["default"])
    if why:
        say(f"{label} has a default that does not hold: {why}")


def distinct_values(values):
    """A non-empty list of distinct values of letters, digits and . _ , -."""
    return (isinstance(values, list) and len(values) > 0 and len(unique(values)) == len(values)
            and all(isinstance(v, str) and VALUE.fullmatch(v) for v in values))


def kind_fields_hold(p, kind, label, say):
    """The fields a kind needs: choices or options, low and high, a pattern that compiles."""
    if kind in ("choice", "set"):
        key = "choices" if kind == "choice" else "options"
        if not distinct_values(p.get(key, MISSING)):
            say(f"{label} needs {key}: a non-empty list of distinct values of letters, digits and . _ , -")
            return False
    elif kind == "int":
        low, high = p.get("low", MISSING), p.get("high", MISSING)
        if not (is_whole(low) and is_whole(high) and low <= high):
            say(f"{label} needs whole numbers low and high, low at most high")
            return False
    elif kind == "float":
        low, high = p.get("low", MISSING), p.get("high", MISSING)
        if not (is_finite_number(low) and is_finite_number(high) and low <= high):
            say(f"{label} needs numbers low and high, low at most high")
            return False
        if "above" in p and not isinstance(p["above"], bool):
            say(f"{label} has above that is not true or false")
    elif kind == "names" and "pattern" in p:
        if not isinstance(p["pattern"], str) or full_regex(p["pattern"]) is None:
            say(f"{label} has a pattern that is not a regular expression")
            return False
    return True


def check_pattern(pattern, label, c, say):
    """R2: an input's accepts pattern, every key known and every list drawn from the contract (section 6)."""
    if not isinstance(pattern, dict):
        say(f"{label} has no accepts pattern")
        return
    for key in js_keys(pattern):
        if not contains(PATTERN_KEYS, key):
            say(f"{label} accepts an unknown key {show(key)}")

    def list_of(key, allowed):
        if key in pattern and not (isinstance(pattern[key], list) and all(contains(allowed, x) for x in pattern[key])):
            say(f"{label} accepts {key} {show(pattern[key])}, not a list from {js_join(allowed, ', ')}")

    if not isinstance(pattern.get("kind"), list) or not pattern["kind"]:
        say(f"{label} accepts no kind; kind is a non-empty list")
    else:
        list_of("kind", c.kinds)
    list_of("rank", [0, 1, 2, 3])
    if "time" in pattern and not contains(["any", "yes", "no"], pattern["time"]):
        say(f"{label} accepts time {show(pattern['time'])}, not any, yes or no")
    list_of("has_axes", c.axes)
    list_of("dtype", c.dtypes)
    list_of("targets", c.targets)
    if "parts" in pattern and not contains(["split", "unsplit", "any"], pattern["parts"]):
        say(f"{label} accepts parts {show(pattern['parts'])}, not split or unsplit")
    list_of("needs_parts", c.parts)
    list_of("modality", c.modalities)
    if "trained" in pattern and not isinstance(pattern["trained"], bool):
        say(f"{label} accepts trained that is not true or false")


def port_label(word, port, i):
    """An input or output as a problem names it: by its name, else by its place."""
    name = port.get("name", MISSING)
    return f"{word} {name if isinstance(name, str) else i}"


def check_input_ports(m, c, bad):
    """R2 for the inputs: objects with unique names and patterns; none on a source, one or more elsewhere.
    Returns the input names."""
    names = []
    inputs = m.get("inputs", MISSING)
    if not isinstance(inputs, list):
        bad("port", "inputs", "inputs is a list")
        return names
    for i, p in enumerate(inputs):
        if not isinstance(p, dict):
            bad("port", "inputs", f"input {i} is not an object")
            continue
        label, name = port_label("input", p, i), p.get("name", MISSING)
        if not isinstance(name, str) or not PORT.fullmatch(name):
            bad("port", "inputs", f"input {i} has the name {show(name)}, not lowercase letters, digits and _ up to 24")
        elif name in names:
            bad("port", "inputs", f"two inputs are named {name}")
        else:
            names.append(name)
        if "optional" in p and not isinstance(p["optional"], bool):
            bad("port", "inputs", f"{label} has optional that is not true or false")
        if "what" in p and not isinstance(p["what"], str):
            bad("port", "inputs", f"{label} has what that is not a text")
        check_pattern(p.get("accepts", MISSING), label, c, functools.partial(bad, "accepts", "inputs"))
    source = same(m.get("stage", MISSING), "source")
    if source and inputs:
        bad("port", "inputs", "a source block has no input")
    if not source and not inputs:
        bad("port", "inputs", "a block that is not a source has at least one input")
    return names


def ref_problem(value, params, input_names, c):
    """Why a ref names nothing, or None: @param.NAME of a param, @in.PORT.FIELD of an input, @self.FIELD
    of a type's field or sizes.AXIS."""
    ref = parse_ref(value)
    if ref is None or ref["scope"] == "bad":
        return f"{show(value)} is not @param.NAME, @in.PORT.FIELD or @self.FIELD"
    if ref["scope"] == "param":
        return None if ref["name"] in params.names else f"{show(value)} names no param"
    if ref["scope"] == "in" and ref["port"] not in input_names:
        return f"{show(value)} names no input"
    size = SIZE_REF.fullmatch(ref["field"])
    if size:
        return None if contains(c.axes, size.group(1)) else f"{show(value)} names no axis"
    return None if contains(TYPE_FIELDS, ref["field"]) else f"{show(value)} names no field of a type"


def check_op(op, label, c, params, input_names, say_op, say_ref):
    """R2 for one op: a known name with its arity, and each slot a valid literal or a ref that names something."""
    if not isinstance(op, list) or not isinstance(item(op, 0), str) or op[0] not in OP_ARITY:
        say_op(f"{label} has an unknown op {show(op)}")
        return
    name = op[0]
    if len(op) != OP_ARITY[name]:
        say_op(f"{label} has {name} with {len(op)} items; it takes {OP_ARITY[name]}")
        return

    def slot(value, valid, what):
        if is_ref(value):
            why = ref_problem(value, params, input_names, c)
            if why:
                say_ref(f"{label}: {why}")
        elif not valid(value):
            say_op(f"{label} has {name} with {show(value)}, not {what}")

    def axis(value):
        if not contains(c.axes, value):
            say_op(f"{label} has {name} on {show(value)}, not an axis")

    if name == "kind":
        slot(op[1], lambda v: contains(c.kinds, v), "a kind")
    elif name == "set":
        if not contains(SET_FIELDS, op[1]):
            say_op(f"{label} sets {show(op[1])}, not one of {', '.join(SET_FIELDS)}")
        else:
            slot(op[2], lambda v: valid_set_value(op[1], v, c), f"a value {op[1]} can take")
    elif name in ("size", "drop_axis", "add_axis"):
        axis(op[1])
        if name == "add_axis" and op[2] is not None and not contains(c.axes, op[2]):
            say_op(f"{label} has add_axis before {show(op[2])}, not an axis or null")
        if name != "drop_axis":
            slot(op[-1], valid_size, "a whole number from 1 or null")
    elif name == "axes":
        slot(op[1], lambda v: valid_axis_list(v, c), "a list of distinct axes")
    elif name == "parts":
        slot(op[1], lambda v: valid_part_list(v, c), "a list of distinct parts")
    else:
        slot(op[1], lambda v: contains(c.licences, v), "a licence class")


def check_output_ports(m, c, bad, params, input_names):
    """R2 for the outputs: one or more, unique names, `from` an input, and every op valid."""
    outputs = m.get("outputs", MISSING)
    if not isinstance(outputs, list):
        bad("port", "outputs", "outputs is a list")
        return
    if not outputs:
        bad("port", "outputs", "a block has at least one output")
    names = []
    for i, o in enumerate(outputs):
        if not isinstance(o, dict):
            bad("port", "outputs", f"output {i} is not an object")
            continue
        label, name = port_label("output", o, i), o.get("name", MISSING)
        if not isinstance(name, str) or not PORT.fullmatch(name):
            bad("port", "outputs", f"output {i} has the name {show(name)}, not lowercase letters, digits and _ up to 24")
        elif name in names:
            bad("port", "outputs", f"two outputs are named {name}")
        else:
            names.append(name)
        if "from" in o and o["from"] is not None and not contains(input_names, o["from"]):
            bad("port", "outputs", f"{label} is from {show(o['from'])}, which is not an input")
        if "what" in o and not isinstance(o["what"], str):
            bad("port", "outputs", f"{label} has what that is not a text")
        if not isinstance(o.get("ops"), list):
            bad("op", "outputs", f"{label} has no ops list")
            continue
        for op in o["ops"]:
            check_op(op, label, c, params, input_names, functools.partial(bad, "op", "outputs"),
                     functools.partial(bad, "ref", "outputs"))


def check_condition(cond, label, say):
    """A rule's condition: known keys, lists for in and not_in, numbers for the bounds, true for empty and nonempty."""
    if not isinstance(cond, dict):
        say(f"{label} is not a condition object")
        return
    for key in js_keys(cond):
        if not contains(CONDITION_KEYS, key):
            say(f"{label} has an unknown condition {show(key)}")
    for key in ("in", "not_in"):
        if key in cond and not isinstance(cond[key], list):
            say(f"{label} has {key} that is not a list")
    for key in ("min", "max", "above", "below"):
        if key in cond and not is_finite_number(cond[key]):
            say(f"{label} has {key} that is not a number")
    for key in ("empty", "nonempty"):
        if key in cond and cond[key] is not True:
            say(f"{label} has {key} that is not true")


def check_rule_list(m, bad, params):
    """R4: every rule's when and need name the block's params with valid conditions, and its say is a text."""
    def say(text):
        bad("rule", "rules", text)

    rules = m.get("rules", MISSING)
    if not isinstance(rules, list):
        say("rules is a list")
        return
    for i, r in enumerate(rules):
        label = f"rule {i}"
        if not isinstance(r, dict):
            say(f"{label} is not an object")
            continue
        for side in ("when", "need"):
            conditions = r.get(side, MISSING)
            if not isinstance(conditions, dict):
                say(f"{label} has no {side} object")
                continue
            for key in js_keys(conditions):
                if key not in params.names:
                    say(f"{label} {side} names {show(key)}, which is not a param")
                check_condition(conditions[key], f"{label} {side} {key}", say)
        if not nonempty_text(r.get("say", MISSING)):
            say(f"{label} has no say")


def check_read_parts(m, c, bad):
    """R5: the parts a block reads come from the contract, once each, and only evaluate and report read test."""
    reads = m.get("reads", MISSING)
    parts = reads.get("parts", MISSING) if isinstance(reads, dict) else MISSING
    if (not isinstance(parts, list) or not all(contains(c.parts, p) for p in parts)
            or len(unique(parts)) != len(parts)):
        bad("reads", "reads", f"reads.parts is a list of distinct parts from {js_join(c.parts, ', ')}")
        return
    stage = m.get("stage", MISSING)
    if contains(parts, "test") and not same(stage, "evaluate") and not same(stage, "report"):
        bad("reads", "reads", "only evaluate and report blocks read the test part")


def numeric_param(params, ref):
    """A ref @param.NAME of an int or float param."""
    parsed = parse_ref(ref)
    if parsed is None or parsed["scope"] != "param":
        return False
    p = params.by_name.get(parsed["name"])
    return p is not None and contains(["int", "float"], p.get("kind", MISSING))


def check_job(m, c, bad, params):
    """R6: the job's class, hours, cpus, memory, with_upstream and array (section 5)."""
    def say(text):
        bad("job", "job", text)

    job = m.get("job", MISSING)
    if not isinstance(job, dict):
        say("job is an object")
        return
    cls = job.get("class", MISSING)
    none = same(cls, "none")
    if not contains(c.job_classes, cls):
        say(f"job class {show(cls)} is not one of {js_join(c.job_classes, ', ')}")
    hours = job.get("hours", MISSING)
    if is_finite_number(hours):
        if (hours < 0) if none else (hours <= 0):
            say("job hours is above 0")
    elif not numeric_param(params, hours):
        say("job hours is a number above 0 or @param.NAME of an int or float param")
    least = 0 if none else 1
    if not whole_between(job.get("cpus", MISSING), least, 64):
        say("job cpus is a whole number from 1 to 64")
    if not whole_between(job.get("memory_gb", MISSING), least, 512):
        say("job memory_gb is a whole number from 1 to 512")
    if not isinstance(job.get("with_upstream", MISSING), bool):
        say("job with_upstream is true or false")
    if not isinstance(job.get("array", MISSING), bool):
        say("job array is true or false")


def whole_between(value, low, high):
    """A whole number from low to high."""
    return is_whole(value) and low <= value <= high


def check_determinism(m, c, bad, params):
    """R7: exact, seeded with an int seed param, or declared with the reason in 20 characters or more."""
    d = m.get("deterministic", MISSING)
    if not contains(c.deterministic, d):
        bad("determinism", "deterministic", f"deterministic {show(d)} is not one of {js_join(c.deterministic, ', ')}")
        return
    if same(d, "seeded"):
        seed = m.get("seed_param", MISSING)
        p = params.by_name.get(seed) if isinstance(seed, str) else None
        if p is None or not same(p.get("kind", MISSING), "int"):
            bad("determinism", "seed_param", "a seeded block names its int seed param in seed_param")
    if same(d, "declared") and not text_length(m.get("nondeterminism", MISSING), 20, math.inf):
        bad("determinism", "nondeterminism",
            "a declared block says what varies and why it is tolerated, in 20 characters or more")


def admits(port, kind):
    """An input whose pattern takes the kind."""
    return (isinstance(port, dict) and isinstance(port.get("accepts"), dict)
            and contains(array_of(port["accepts"].get("kind")), kind))


def utf16_order(value):
    """The key JavaScript's default sort compares by: String() of the value, in UTF-16 code units."""
    return js_text(value).encode("utf-16-be", "surrogatepass")


def same_numbers(a, b):
    """The distinct values of two lists, each sorted as JavaScript's default sort does, are equal."""
    return deep_equal(sorted(unique(a), key=utf16_order), sorted(unique(b), key=utf16_order))


def check_generic(m, c, bad, structural):
    """R8: what a block that takes data or a model says it takes, why when it is narrower than everything,
    each data input's rank, and every contract probe it admits run through its first input and outputs."""
    def say(text):
        bad("generic", "generic", text)

    inputs = array_of(m.get("inputs", MISSING))
    g = m.get("generic", MISSING)
    if not any(admits(p, "data") or admits(p, "model") for p in inputs):
        if g is not None and g is not MISSING:
            say("generic is null for a block that takes no data and no model")
        return
    if not isinstance(g, dict):
        say("generic is required: the block takes data or a model")
        return
    if not generic_fields_hold(g, say):
        return
    everything = all(contains(g["rank"], r) for r in (1, 2, 3)) and same(g["channels"], "any") and same(g["sizes"], "any")
    if not everything and not text_length(g.get("why", MISSING), 20, math.inf):
        say("generic.why says, in 20 characters or more, what the code takes today and what would widen it")
    for p in inputs:
        if (admits(p, "data") and "rank" in p["accepts"] and isinstance(p["accepts"]["rank"], list)
                and not same_numbers(p["accepts"]["rank"], g["rank"])):
            say(f"the input {show(p.get('name', MISSING))} accepts rank {show(p['accepts']['rank'])}, "
                f"not generic.rank {show(g['rank'])}")
    first = inputs[0] if inputs else MISSING
    if structural or not admits(first, "data") or not isinstance(first.get("name"), str):
        return
    run_probes(m, c, g, first, say)


def generic_fields_hold(g, say):
    """generic's rank, time, channels and sizes each valid; why, when given, a text."""
    valid = True
    rank = g.get("rank", MISSING)
    if (not isinstance(rank, list) or not all(whole_between(r, 0, 3) for r in rank)
            or len(unique(rank)) != len(rank)):
        say("generic.rank is a list of distinct ranks from 0 to 3")
        valid = False
    if not contains(["any", "yes", "no"], g.get("time", MISSING)):
        say("generic.time is any, yes or no")
        valid = False
    channels = g.get("channels", MISSING)
    if not same(channels, "any") and not (isinstance(channels, list) and channels
                                          and all(is_whole(x) and x >= 1 for x in channels)
                                          and len(unique(channels)) == len(channels)):
        say("generic.channels is any or a list of distinct channel counts")
        valid = False
    if not same(g.get("sizes", MISSING), "any") and not same(g.get("sizes", MISSING), "fixed"):
        say("generic.sizes is any or fixed")
        valid = False
    if "why" in g and not isinstance(g["why"], str):
        say("generic.why is a text")
    return valid


def probe_for(accepts, t):
    """R8's probes hold the shapes a block takes: rank, time, channels, sizes and dtype. What its data must
    mean, the targets and whether it is split yet, the probe takes from the block's own first input, so a
    block that reads masks, or splits data not yet split, can say so in its pattern."""
    if not isinstance(accepts, dict):
        return t
    targets = accepts.get("targets", MISSING)
    if isinstance(targets, list) and targets and not contains(targets, t["targets"]):
        t["targets"] = clone(targets[0])
    if same(accepts.get("parts", MISSING), "unsplit"):
        t["parts"] = []
    return t


def run_probes(m, c, g, first, say):
    """The probe test: each contract probe whose rank and time generic admits, given the first input's own
    targets and parts (probe_for), must pass that input's pattern and compute every output with no
    problem, the params at their defaults."""
    defaults = effective_params(None, m)
    for probe in c.probes:
        t = probe_for(first["accepts"], copy_type(probe.get("type", MISSING)))
        timed = contains(t["axes"], "T")
        if not contains(g["rank"], rank_of(t["axes"], c)):
            continue
        if (same(g["time"], "yes") and not timed) or (same(g["time"], "no") and timed):
            continue
        why = [q["text"] for q in matches(first["accepts"], t, c)]

        def op_failed(port, op_name, text, why=why):
            why.append(f"output {port}: {text}")

        compute_outputs(m, {first["name"]: t}, defaults, c, op_failed)
        if why:
            say(f"the probe {show(probe.get('name', MISSING))} fails: {'; '.join(why)}")


def check_experiment(m, c, bad, params, input_names):
    """The experiment mapping, when there is one: known keys, refs that name something, and `only` over params."""
    e = m.get("experiment", MISSING)
    if "experiment" not in m or e is None:
        return
    if not isinstance(e, dict):
        bad("field", "experiment", "experiment is null or an object")
        return
    for key in js_keys(e):
        if not contains(EXPERIMENT_KEYS, key):
            bad("field", "experiment", f"experiment has an unknown key {show(key)}")

    def ref(value, label):
        why = ref_problem(value, params, input_names, c) if is_ref(value) else None
        if why:
            bad("ref", "experiment", f"experiment {label}: {why}")

    for key in ("recipe", "epochs", "seed", "hours"):
        if key in e:
            ref(e[key], key)
    if "blocks" in e:
        if not isinstance(e["blocks"], dict):
            bad("field", "experiment", "experiment.blocks is an object of Blocks fields")
        else:
            for key in js_keys(e["blocks"]):
                ref(e["blocks"][key], "blocks." + key)
    if "only" in e:
        check_only(e["only"], params, bad)


def check_only(only, params, bad):
    """experiment.only: an object of the block's params, each with a non-empty list of values."""
    if not isinstance(only, dict):
        bad("field", "experiment", "experiment.only is an object of params and their allowed values")
        return
    for key in js_keys(only):
        if key not in params.names:
            bad("ref", "experiment", f"experiment.only names {show(key)}, which is not a param")
        if not isinstance(only[key], list) or not only[key]:
            bad("field", "experiment", f"experiment.only.{key} is a non-empty list")


def check_needs(m, c, bad):
    """R9: the libraries a block needs come from the contract's list, once each."""
    needs = m.get("needs", MISSING)
    if not isinstance(needs, list):
        bad("needs", "needs", "needs is a list")
        return
    outside = [x for x in needs if not contains(c.needs, x)]
    if outside:
        bad("needs", "needs", f"needs names {', '.join(show(x) for x in outside)}, outside the contract's list")
    if len(unique(needs)) != len(needs):
        bad("needs", "needs", "needs names a library twice")


def own_code_path(block_id):
    """Where a block of its own code keeps its module."""
    return f"{SANDBOX}/blocks/{js_text(block_id)}.py"


def own_test_path(block_id):
    """Where a block of its own code keeps its test."""
    return f"tests/test_sandbox_block_{js_text(block_id)}.py"


def check_code(m, c, bad):
    """R10's shape: the code's kind, and implemented_by as that kind needs it (code_problems checks the files)."""
    code, paths = m.get("code", MISSING), m.get("implemented_by", MISSING)
    if not contains(c.code, code):
        bad("code", "code", f"code {show(code)} is not one of {js_join(c.code, ', ')}")
    if not isinstance(paths, list) or not all(nonempty_text(p) for p in paths):
        bad("code", "implemented_by", "implemented_by is a list of repository paths")
        return
    if same(code, "existing") and not paths:
        bad("code", "implemented_by", "existing code names the files that implement it")
    if same(code, "own") and paths != [own_code_path(m.get("id", MISSING))]:
        bad("code", "implemented_by",
            f"a block of its own code is implemented by exactly {own_code_path(m.get('id', MISSING))}")
    today = m.get("today", MISSING)
    status = today.get("status", MISSING) if isinstance(today, dict) else MISSING
    # Planned code is code not on this branch: nothing here runs it yet, or an unmerged pull request
    # builds it (pending, its note naming the pull request).
    if same(code, "planned") and not (same(status, "planned") or same(status, "pending")):
        bad("code", "code", "planned code goes with today.status planned or pending")


def check_today(m, c, bad):
    """R11: what runs the block today, and the word, flow or pull request its status needs."""
    def say(text):
        bad("today", "today", text)

    today = m.get("today", MISSING)
    if not isinstance(today, dict):
        say("today is an object")
        return
    status = today.get("status", MISSING)
    if not contains(c.today, status):
        say(f"today.status {show(status)} is not one of {js_join(c.today, ', ')}")
    for key in TODAY_STRINGS:
        if not isinstance(today.get(key, MISSING), str):
            say(f"today.{key} is a text, possibly empty")
    if same(status, "live") and not (same(today.get("route", MISSING), "experiment")
                                     and isinstance(m.get("experiment"), dict)):
        say("a live block has today.route experiment and an experiment mapping")
    if same(status, "word") and not nonempty_text(today.get("word", MISSING)):
        say("a word block names its gate word")
    if same(status, "flow") and not nonempty_text(today.get("flow", MISSING)):
        say("a flow block names its flow")
    note = today.get("note", MISSING)
    if same(status, "pending") and not (isinstance(note, str) and PULL_REQUEST.search(note)):
        say("a pending block's note names its pull request as #<number>")
    code = m.get("code", MISSING)
    if same(status, "planned") and not same(code, "planned") and not same(code, "own"):
        say("a planned block has code planned or own")


def text_problems(value):
    """A text, a list or an object anywhere in the value with a character outside printable ASCII."""
    if isinstance(value, str):
        return not printable(value)
    if isinstance(value, list):
        return any(text_problems(x) for x in value)
    if isinstance(value, dict):
        return any(not printable(key) or text_problems(value[key]) for key in js_keys(value))
    return False


def check_text(m, c, bad):
    """R12: printable ASCII everywhere, and canonical JSON of at most limits.manifest_bytes bytes."""
    clean = True
    for key in js_keys(m):
        if not printable(key):
            bad("text", None, "a key holds a character outside printable ASCII")
            clean = False
        elif text_problems(m[key]):
            bad("text", key, f"{key} holds a character outside printable ASCII")
            clean = False
    if not clean:
        return
    try:
        text = canonical(m)
    except CanonicalError as error:
        bad("text", None, f"the manifest cannot be written as canonical JSON: {error}")
        return
    if len(text) > c.limits["manifest_bytes"]:
        bad("size", None, f"the canonical manifest has {len(text)} bytes; at most {js_text(c.limits['manifest_bytes'])}")


def check_card(m, bad):
    """R13: a source block's data card, every field a non-empty text and from a list of the files it rests on."""
    card = m.get("card", MISSING)
    if not same(m.get("stage", MISSING), "source"):
        if card is not None and card is not MISSING:
            bad("card", "card", "card is null for a block that is not a source")
        return
    if not isinstance(card, dict):
        bad("card", "card", "a source block has a data card")
        return
    for key in CARD_FIELDS:
        if not nonempty_text(card.get(key, MISSING)):
            bad("card", "card", f"card.{key} is a non-empty text")
    sources = card.get("from", MISSING)
    if not (isinstance(sources, list) and sources and all(nonempty_text(p) for p in sources)):
        bad("card", "card", "card.from lists the repository files its facts come from")


# ---------------------------------------------------------------------------------------------------
# What only the repository can tell: the files R10 and R13 name (section 5).

def inside_repository(path):
    """A path relative to the repository root that stays inside it."""
    return (isinstance(path, str) and path != "" and not path.startswith("/") and "\\" not in path
            and ":" not in path and ".." not in path.split("/"))


def code_problems(manifest, root=ROOT):
    """R10 and R13 in the repository: every path a block names stays inside it; existing code's files and
    a card's sources are there; a block of its own code has its module, with a docstring and a top-level
    run(inputs, params, context), and its test. [{code, field, text}]"""
    if not isinstance(manifest, dict):
        return []
    root, found = Path(root), []
    code = manifest.get("code", MISSING)
    paths = manifest.get("implemented_by", MISSING)
    for path in paths if isinstance(paths, list) else []:
        if not nonempty_text(path):
            continue
        if not inside_repository(path):
            found.append({"code": "code", "field": "implemented_by", "text": f"{path} is not a path inside the repository"})
        elif same(code, "existing") and not (root / path).exists():
            found.append({"code": "code", "field": "implemented_by", "text": f"{path} is not in the repository"})
    block_id = manifest.get("id", MISSING)
    if same(code, "own") and isinstance(block_id, str) and ID.fullmatch(block_id):
        found += own_code_problems(block_id, root)
    card = manifest.get("card", MISSING)
    sources = card.get("from", MISSING) if isinstance(card, dict) else MISSING
    for path in sources if isinstance(sources, list) else []:
        if nonempty_text(path) and not (inside_repository(path) and (root / path).exists()):
            found.append({"code": "card", "field": "card", "text": f"card.from names {path}, which is not in the repository"})
    return found


def own_code_problems(block_id, root):
    """A block of its own code: tools/sandbox/blocks/<id>.py with a docstring and run(inputs, params,
    context), and tests/test_sandbox_block_<id>.py."""
    found = []
    module, test = own_code_path(block_id), own_test_path(block_id)
    if not (root / module).is_file():
        found.append({"code": "code", "field": "implemented_by", "text": f"{module} is not in the repository"})
    else:
        why = run_problem(root / module)
        if why:
            found.append({"code": "code", "field": "implemented_by", "text": f"{module} {why}"})
    if not (root / test).is_file():
        found.append({"code": "code", "field": "implemented_by", "text": f"{test}, the block's test, is not in the repository"})
    return found


def run_problem(path):
    """Why a block's module is not one the sandbox can call, or None."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError, ValueError) as error:
        return f"cannot be read as Python ({type(error).__name__})"
    if not ast.get_docstring(tree):
        return "has no module docstring"
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "run":
            args = node.args
            names = [a.arg for a in args.posonlyargs + args.args]
            if names == ["inputs", "params", "context"] and not (args.vararg or args.kwarg or args.kwonlyargs):
                return None
            return "defines run with other arguments than (inputs, params, context)"
    return "has no top-level def run(inputs, params, context)"


def block_file_problems(manifest, contract, root=ROOT):
    """Everything section 13 and R10's files say about one manifest: [{code, field, text}]."""
    return check_manifest(manifest, contract) + code_problems(manifest, root)


# ---------------------------------------------------------------------------------------------------
# DATA and the page (section 16).

def load_folder(root, folder):
    """Every .json file of a folder in name order: [(path, stem, value, problem)], value None where the
    file is no JSON."""
    directory = Path(root) / folder
    found = []
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        rel = f"{folder}/{path.name}"
        try:
            found.append((rel, path.stem, load_json(path), None))
        except (OSError, ValueError, RecursionError) as error:
            found.append((rel, path.stem, None, f"{rel}: not JSON as JavaScript reads it ({error})"))
    return found


def by_id(files, problems):
    """The objects of a folder with a text id, sorted by id; every other file a problem."""
    kept = []
    for rel, _stem, value, error in files:
        if error:
            problems.append(error)
        elif not isinstance(value, dict) or not isinstance(value.get("id"), str):
            problems.append(f"{rel}: not a JSON object with an id")
        else:
            kept.append(value)
    return sorted(kept, key=lambda value: value["id"])


def sandbox_data(root=ROOT):
    """DATA as the page embeds it, and every file that kept it from being read: (data or None, problems)."""
    root, problems = Path(root), []
    try:
        contract = load_json(root / CONTRACT)
    except (OSError, ValueError, RecursionError) as error:
        return None, [f"{CONTRACT}: cannot be read as JSON ({error})"]
    if not isinstance(contract, dict):
        return None, [f"{CONTRACT}: not a JSON object"]
    blocks = by_id(load_folder(root, BLOCKS), problems)
    templates = by_id(load_folder(root, TEMPLATES), problems)
    try:
        experiment = experiment_data(root)
    except (OSError, ValueError, SyntaxError, KeyError, TypeError) as error:
        problems.append(f"{panel.BLOCKS_PY}: the experiment route's fields cannot be read ({error})")
        experiment = None
    return {"contract": contract, "blocks": blocks, "templates": templates, "experiment": experiment,
            "repo": panel.REPO}, problems


def page_inputs(root=ROOT):
    """The four files the page is assembled from, as text, and why any cannot go in as it is: (texts, problems)."""
    texts, problems = {}, []
    for name in PAGE_INPUTS:
        rel = f"{SANDBOX}/{name}"
        path = Path(root) / rel
        if not path.is_file():
            problems.append(f"{rel}: missing; the page is assembled from it")
            continue
        try:
            text = path.read_bytes().decode("ascii")
        except (OSError, UnicodeDecodeError):
            problems.append(f"{rel}: holds a byte outside ASCII; the page is ASCII")
            continue
        if "\r" in text:
            problems.append(f"{rel}: holds a carriage return; the page is LF only")
        lowered = text.lower()
        problems += [f"{rel}: holds {word}, which would end its element early or open a script inside it"
                     for word in ENDS_EARLY[name] if word in lowered]
        if name == "shell.html" and lowered.count("<!--") != lowered.count("-->"):
            problems.append(f"{rel}: opens a comment it does not close, which would hide the script")
        problems += loads_in(rel, lowered)
        texts[name] = text
    return texts, problems


def loads_in(where, lowered):
    """A problem for each word that would load something from elsewhere."""
    return [f"{where}: holds {word}; the page loads nothing from elsewhere" for word in LOADS if word in lowered]


def data_json(data):
    """DATA as the page embeds it: keys sorted, no spaces, ASCII, and every "</" written "<\\/" so that no
    text ends the script."""
    return json.dumps(plain(data), sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).replace("</", "<\\/")


def repository_page(texts, data_text):
    """The page as docs/sandbox/pipeline-sandbox.html holds it (section 16, byte for byte)."""
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="robots" '
            'content="noindex, nofollow"><title>Pipeline Sandbox</title><meta name="claude:viewport-fit-sides" '
            'content="cover"><style>' + texts["page.css"] + "</style></head><body>" + texts["shell.html"]
            + "<script>const SANDBOX_DATA=" + data_text + ";\n" + texts["engine.js"] + "\n" + texts["ui.js"]
            + "</script></body></html>\n")


def artifact_page(texts, data_text):
    """The claude.ai edition, a fragment the Artifact tool wraps (section 16, byte for byte)."""
    return ('<title>Pipeline Sandbox</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n<style>'
            + texts["page.css"] + "</style>\n" + texts["shell.html"] + "\n<script>const SANDBOX_DATA=" + data_text
            + ";\n" + texts["engine.js"] + "\n" + texts["ui.js"] + "</script>\n")


EDITIONS = {"repository": repository_page, "artifact": artifact_page}


def build_page(root=ROOT, edition="repository"):
    """The page from tools/sandbox/, or None and why it cannot be built: (text or None, problems). It
    refuses a missing or unreadable input, an input that would break the page, and anything that loads."""
    texts, problems = page_inputs(root)
    data, data_problems = sandbox_data(root)
    problems += data_problems
    data_text = None
    if data is not None:
        try:
            data_text = data_json(data)
        except ValueError as error:
            problems.append(f"{SANDBOX}: the data cannot be written as JSON ({error})")
    if data_text is not None:
        lowered = data_text.lower()
        if "<script" in lowered:
            problems.append(f"{SANDBOX}: a manifest or template holds <script, which would open a script inside the page's")
        problems += loads_in(f"{SANDBOX} (the blocks, templates and contract)", lowered)
    if problems:
        return None, problems
    return EDITIONS[edition](texts, data_text), []


# ---------------------------------------------------------------------------------------------------
# The repository check (section 16).

def licence_problems(contract, root):
    """The contract's licences are data/recipes/' names from the narrowest to the widest, then uncut."""
    ordered = sorted(panel.recipes(root), key=lambda r: (len(r["allow"]), r["name"]))
    expected = [r["name"] for r in ordered] + ["uncut"]
    licences = contract.get("licences") if isinstance(contract, dict) else None
    if not same_list(licences, expected):
        return [f"{CONTRACT}: licences is {show(licences)}; data/recipes/ gives {show(expected)}"]
    return []


def same_list(value, expected):
    """A list equal item by item to the expected one."""
    return isinstance(value, list) and deep_equal(value, expected)


def block_problems(root, contract):
    """Every manifest under tools/sandbox/blocks/: section 13, R10's files, and an id that is its file's name and nobody else's."""
    problems, seen = [], {}
    for rel, stem, value, error in load_folder(root, BLOCKS):
        if error:
            problems.append(error)
            continue
        problems += [f"{rel}: {p['code']} {p['field'] or '-'}: {p['text']}" for p in block_file_problems(value, contract, root)]
        block_id = value.get("id") if isinstance(value, dict) else None
        if not isinstance(block_id, str):
            continue
        if block_id != stem:
            problems.append(f"{rel}: the id {block_id} is not the file's name")
        if block_id in seen:
            problems.append(f"{rel}: the id {block_id} is {seen[block_id]}'s too")
        seen.setdefault(block_id, rel)
    return problems


def expect_of(result):
    """What a template's expect pins, read from its compile."""
    return {"route": result["route"], "ready": result["ready"], "requests": len(result["requests"]),
            "gpu_submissions": result["jobs"]["gpu"]["submissions"],
            "cpu_submissions": result["jobs"]["cpu"]["submissions"], "gpu_tasks": result["jobs"]["gpu"]["tasks"]}


def where_of(p):
    """A problem's place as a short prefix: the node, the port and the field it names."""
    parts = [js_text(p[key]) for key in ("node", "port", "field") if p.get(key) is not None]
    return f"{' '.join(parts)}: " if parts else ""


def template_problems(root, data):
    """Every template: an id that is its file's name, no error, the compile its expect pins, and every
    request one the experiment workflow accepts."""
    problems, seen = [], set()
    for rel, stem, value, error in load_folder(root, TEMPLATES):
        if error:
            problems.append(error)
            continue
        if not isinstance(value, dict):
            problems.append(f"{rel}: a template is a JSON object")
            continue
        template_id = value.get("id")
        if not isinstance(template_id, str) or not ID.fullmatch(template_id):
            problems.append(f"{rel}: the id {show(value.get('id', MISSING))} is not lowercase letters, digits and _")
        elif template_id != stem:
            problems.append(f"{rel}: the id {template_id} is not the file's name")
        if isinstance(template_id, str) and template_id in seen:
            problems.append(f"{rel}: the id {template_id} is used twice")
        if isinstance(template_id, str):
            seen.add(template_id)
        problems += [f"{rel}: {line}" for line in compiled_problems(value, data, root)]
    return problems


def compiled_problems(template, data, root):
    """A template's errors, its expect against its compile, and its requests against the experiment workflow."""
    result = compile_spec(template, data)
    lines = [f"{p['code']} {where_of(p)}{p['text']}" for p in result["problems"] if p["level"] == "error"]
    expect, got = template.get("expect"), expect_of(result)
    if not isinstance(expect, dict):
        lines.append(f"expect is not an object; compile gives {show(got)}")
    else:
        lines += [f"expect {key} is {show(expect.get(key, MISSING))}; compile gives {show(got[key])}"
                  for key in EXPECT_KEYS if key not in expect or not deep_equal(expect[key], got[key])]
    for n, request in enumerate(result["requests"], 1):
        _record, refused = panel.check_request(request["body"], root)
        lines += [f"request {n} ({request['title']}): the experiment workflow refuses it: {why}" for why in refused]
    return lines


def glyph_keys(ui_text):
    """The names written as keys in ui.js: `name:`, `"name":` or `'name':`."""
    bare = re.findall(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*:", ui_text)
    quoted = re.findall(r"[\"']([A-Za-z_$][\w$]*)[\"']\s*:", ui_text)
    return set(bare) | set(quoted)


def glyph_problems(root, contract):
    """Every glyph of the contract is drawn: its name is a key in ui.js."""
    path = Path(root) / SANDBOX / "ui.js"
    glyphs = contract.get("glyphs") if isinstance(contract, dict) else None
    if not path.is_file() or not isinstance(glyphs, list):
        return []
    keys = glyph_keys(path.read_text(encoding="utf-8", errors="replace"))
    missing = [js_text(name) for name in glyphs if not isinstance(name, str) or name not in keys]
    return [f"{SANDBOX}/ui.js: no glyph for {', '.join(missing)} (a key `name:` of its glyph table)"] if missing else []


def page_problems(root):
    """The page builds, and the file holds exactly what it builds."""
    text, problems = build_page(root)
    if text is None:
        return problems
    path = Path(root) / PAGE
    if not path.is_file():
        return [f"{PAGE}: missing; run {WRITE}"]
    if path.read_bytes() != text.encode("ascii"):
        return [f"{PAGE}: not what tools/sandbox/ gives; run {WRITE}"]
    return []


def repository_problems(root=ROOT):
    """Everything `check` holds (section 16), as lines "path: why"."""
    root = Path(root)
    data, problems = sandbox_data(root)
    if data is None:
        return list(dict.fromkeys(problems + page_problems(root)))
    contract = data["contract"]
    problems = licence_problems(contract, root) + block_problems(root, contract)
    if data["experiment"] is not None:
        problems += template_problems(root, data)
    problems += glyph_problems(root, contract)
    problems += page_problems(root)
    return list(dict.fromkeys(problems))


# ---------------------------------------------------------------------------------------------------
# The command line.

def refuse(problems):
    """Every problem to stderr, and exit code 1."""
    for line in problems:
        print(line, file=sys.stderr)
    return 1


def run_write(args):
    """write: the page, or every reason it cannot be written."""
    text, problems = build_page(args.root)
    if text is None:
        return refuse(problems + [f"{PAGE}: not written; the page is never written broken"])
    path = Path(args.root) / PAGE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("ascii"))
    print(f"wrote {PAGE}")
    return 0


def run_check(args):
    """check: every problem, or one line saying what holds."""
    problems = repository_problems(args.root)
    if problems:
        return refuse(problems)
    data, _ = sandbox_data(args.root)
    print(f"{SANDBOX}: {len(data['blocks'])} blocks and {len(data['templates'])} templates hold; {PAGE}: current")
    return 0


def run_check_block(args):
    """check-block: a manifest file, or every manifest of a folder, against section 13 and R10's files."""
    data, problems = sandbox_data(args.root)
    if data is None:
        return refuse(problems)
    target = Path(args.path)
    paths = sorted(target.glob("*.json")) if target.is_dir() else [target]
    found = []
    for path in paths:
        try:
            manifest = load_json(path)
        except (OSError, ValueError, RecursionError) as error:
            found.append(f"{path}: not JSON as JavaScript reads it ({error})")
            continue
        found += [f"{path}: {p['code']} {p['field'] or '-'}: {p['text']}"
                  for p in block_file_problems(manifest, data["contract"], args.root)]
        if isinstance(manifest, dict) and manifest.get("id") != path.stem:
            found.append(f"{path}: the id {show(manifest.get('id', MISSING))} is not the file's name")
    if found:
        return refuse(found)
    print(f"{len(paths)} manifest(s) hold")
    return 0


def spec_and_data(args):
    """The spec a command names and DATA, or the lines that say why they cannot be read."""
    data, problems = sandbox_data(args.root)
    if data is None:
        return None, None, problems
    try:
        return load_json(args.spec), data, []
    except (OSError, ValueError, RecursionError) as error:
        return None, None, [f"{args.spec}: not JSON as JavaScript reads it ({error})"]


def run_compile(args):
    """compile: section 12 for a spec file, as JSON."""
    spec, data, problems = spec_and_data(args)
    if problems:
        return refuse(problems)
    print(json.dumps(plain(compile_spec(spec, data)), indent=1, sort_keys=True))
    return 0


def run_digest(args):
    """digest: the SHA-256 of a spec file's canonical spec."""
    spec, data, problems = spec_and_data(args)
    if problems:
        return refuse(problems)
    hex_digest = digest(spec, data)
    if not hex_digest:
        return refuse([f"{args.spec}: holds what canonical JSON cannot write; propagate says where"])
    print(hex_digest)
    return 0


def run_artifact(args):
    """artifact: the claude.ai edition, written to --out."""
    text, problems = build_page(args.root, "artifact")
    if text is None:
        return refuse(problems)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_bytes(text.encode("ascii"))
    print(f"wrote {args.out}")
    return 0


COMMANDS = {"write": run_write, "check": run_check, "check-block": run_check_block, "compile": run_compile,
            "digest": run_digest, "artifact": run_artifact}


def main(argv=None):
    """The command line: write, check, check-block, compile, digest and artifact, each with --root."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, words in (("write", "write " + PAGE), ("check", "exit 1 with every problem")):
        commands.add_parser(name, help=words)
    commands.add_parser("check-block", help="a manifest file, or a folder of them").add_argument("path")
    commands.add_parser("compile", help="section 12 as JSON").add_argument("spec")
    commands.add_parser("digest", help="the SHA-256 of the canonical pipeline").add_argument("spec")
    commands.add_parser("artifact", help="the claude.ai edition, a fragment").add_argument("--out", required=True)
    for command in commands.choices.values():
        command.add_argument("--root", type=Path, default=ROOT, help="the repository to read (a worktree, for a test)")
    args = parser.parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
