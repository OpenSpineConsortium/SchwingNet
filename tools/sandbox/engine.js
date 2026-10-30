/*
 * The pipeline sandbox's engine (docs/research/pipeline-sandbox/README.md): the type records, the
 * patterns and ops that move them, the canonical spec and its digest, propagation, the job plan,
 * the two routes, the manifest check and the prediction. It touches no page and no clock and draws
 * no random number, so the same spec gives the same answer in the page and under node, and
 * tools/pipeline_sandbox.py mirrors it in Python to the same digests and problems.
 *
 * Choices the spec leaves open, written here so the Python mirror makes the same ones.
 *
 * Numbers. Every number Python formats (format(v, ".6f"), f"{v:g}", round(v, 2)) is formatted here
 * from the double's exact decimal value with ties to even, as CPython does, never with toFixed or
 * toPrecision, which round a tie such as 0.0078125 up and write 1e21 with an exponent.
 *
 * The canonical spec. A node of a known block keeps as params the defaults overlaid with what it
 * gives, an unknown name kept; its version as given, null when absent; its vary lists that are
 * lists of one value or more. An id that is not n1 to n9999 sorts after every node, then by its
 * text. A spec canonical JSON cannot write has the digest "".
 *
 * Propagation keeps one problem per occurrence (section 10 counts them; none is merged):
 * - node (error, node = the id or null): an id that is not n1 to n9999, or a second node of one id;
 *   the node is left out of the graph, and so are the edges that touch an id not in it.
 * - text (error): field "name" for the spec's name, node = id for a node, node = the edge's `to`
 *   for an edge, when canonical JSON cannot write it.
 * - block, version (warn), cycle: one per node; Kahn's sort leaves out every node on or after a
 *   cycle, each gets "cycle", and its fan is its own combinations.
 * - port (node = the edge's `to`, port = its `in`): one per edge whose `out` or `in` is not a port;
 *   node null for an edge to no node; one per input that has two edges or more (port = the input),
 *   the first edge in canonical order feeding its type. input: one per required input with no edge.
 * - param (field = the param): one per given value outside its kind, one per unknown name given or
 *   varied, one per varied value outside its kind. vary: one per varied param whose manifest says
 *   vary false (field = the param); one per node over limits.combinations (field null), and then
 *   the node's rules are checked for its base params alone.
 * - rule: one per failing rule. type: one per failed key per connected input (port, field = key).
 * - op (port = the output, field = the op's name, or null when the op has no name): one per op
 *   that cannot run (an unknown op, field, ref or value, a size of an axis the type lacks); the op
 *   leaves the type as it was. A null value, written or read from an unconnected port, removes a
 *   size, adds an axis with no size and sets classes or family to null; any other op it leaves as
 *   it was, with no problem.
 * - test: one per node of a block reading "test" outside evaluate and report. parts (port = the
 *   input): one per connected data input that lacks a part the block reads.
 * - limit (all null): one for nodes, one for edges, one for the combinations in all.
 * - The fan counts every edge into the node between two nodes of the graph.
 *
 * Jobs. A with_upstream node rides with the first of its own inputs, in manifest order, whose edge
 * comes from a cpu or gpu node; it rides only when that node's class is its own, and a rider of a
 * rider rides with that rider's host. A rider's row has 0 submissions and its own tasks and hours;
 * its hours per task are added to the host's row, and it counts in no total. jobs() returns
 * {rows, totals, problems}: the array "limit" (node = the array's node) is reported there and in
 * compile(), not in propagate().
 *
 * Compile. ready is true on the experiment route alone. "unconnected" names the nodes no edge path
 * reaches from a catalog_v1 node. "only" holds for the base value and every varied value of the
 * param. "float_plain" looks at refs to float params (their varied values, else the base) and at
 * literal numbers that are not whole. Where two nodes map one value, the higher node number wins;
 * epochs, seed and hours fall back to 20, 1 and 4 where no node maps them. The request's hours stay
 * the mapped number (hours_word is f"{hours:g}"), and jobs.gpu.hours is round(sum, 2). A request also
 * carries recipe, epochs, seed, hours, hours_word, blocks (every field, in DATA.experiment.fields'
 * order), named, title, body, url, lines, command and combination ([{node, param, value}]). The
 * pipeline issue's body ends with a newline after its closing sentence, its GPU-hours written as in
 * section 8. compile() also returns problems: propagation's and jobs'.
 *
 * The manifest check keeps at most one problem per (code, field), the texts of repeats joined by
 * "; ". Its field is the manifest's top-level key the failure sits under ("inputs", "outputs",
 * "params", "rules", "reads", "job", "deterministic", "seed_param", "nondeterminism", "generic",
 * "needs", "code", "implemented_by", "today", "experiment", "card", "resolve", or the R1 key); a
 * text problem names the key whose value holds the character, and a key outside ASCII, a size
 * problem or a manifest that is no object has field null. Codes: the R1 shapes are "field" (the id
 * "id"); a bad input or output is "port"; a pattern "accepts"; an op "op"; a ref that names no param,
 * port, field or axis "ref" (in outputs and in experiment); an unknown experiment key, a bad blocks
 * or only shape, or a resolve that is no text "field". A pattern's parts may be split, unsplit or
 * any. A job of class none may give 0 hours, cpus and memory_gb. The probe test runs only when the
 * first input admits data and no port, accepts, op, ref or param problem was found; each probe takes
 * that input's own targets (its first, where the probe's is not among them) and, where it asks for
 * unsplit data, no parts. Planned code goes with today.status planned or pending.
 *
 * The prediction never offers a source or the anchor's own block. It scores transition
 * 2 (c + 2h) / (total + 1), stage 1 for the next stage the
 * pipeline lacks (else 0.6 - 0.04 per stage from it, at least 0.3, for a later stage; 0.25 for the
 * same stage; 0 for an earlier one), 0.5 for a stage the pipeline lacks, and -2 for a block on the
 * board outside evaluate, analyse and report; scores are rounded to 3 decimals before the sort.
 */
(function () {
  "use strict";

  var SB = {};
  SB.version = 1;

  // ------------------------------------------------------------------------------------------------
  // Constants: the spec's shapes and the experiment route's fixed text (tools/experiments_panel.py).

  var STAGES = ["source", "prepare", "split", "augment", "model", "train", "calibrate", "select", "evaluate",
    "analyse", "report"];
  var KINDS = ["data", "model", "checkpoint", "metrics", "report"];
  var AXES = ["N", "T", "C", "D", "H", "W", "F", "K", "P"];
  var SPATIAL = ["D", "H", "W"];
  var DTYPES = ["uint8", "int16", "int32", "float16", "float32", "bool"];
  var TARGETS = ["none", "level", "mask", "points", "value"];
  var PARTS = ["train", "validation", "test"];
  var MODALITIES = ["any", "fluoro", "radiograph", "mixed", "ct", "drr", "table"];
  var LICENCES = ["commercial", "commercial-share-alike", "non-commercial", "research-internal", "uncut"];
  var JOB_CLASSES = ["none", "cpu", "gpu"];
  var TODAY = ["live", "word", "flow", "pending", "planned"];
  var CODE = ["existing", "own", "planned"];
  var DETERMINISTIC = ["exact", "seeded", "declared"];
  var NEEDS = ["python", "numpy", "scipy", "nibabel", "torch", "torchvision", "monai", "onnxruntime", "jax", "pymc",
    "metaflow", "wandb"];
  var GLYPHS = ["catalog", "ct", "video", "folder", "synthetic", "recipe", "samples", "normalise", "denoise", "crop",
    "segment", "render", "realism", "features", "split", "splitFamilies", "augment", "network", "unet", "prior", "train",
    "calibrate", "select", "evaluate", "latency", "gap", "morphometry", "naming", "report", "wandb", "card", "fallback"];
  var LIMITS = {combinations: 64, array_tasks: 1000, nodes: 60, edges: 120, epochs_most: 200, hours_most: 48,
    manifest_bytes: 16384};

  var ID_RE = /^[a-z][a-z0-9_]{1,39}$/;
  var NODE_RE = /^n[1-9][0-9]{0,3}$/;
  var PORT_RE = /^[a-z][a-z0-9_]{0,23}$/;
  var PARAM_RE = /^[a-z][a-z0-9_]{0,31}$/;
  var VALUE_RE = /^[A-Za-z0-9][A-Za-z0-9._,-]{0,79}$/;
  var NAMES_PATTERN = "^[a-z0-9_]{1,40}$";

  var TYPE_FIELDS = ["kind", "axes", "sizes", "dtype", "targets", "classes", "parts", "persons", "modality", "licence",
    "sources", "family", "rank", "trained"];
  var SET_FIELDS = ["dtype", "targets", "classes", "modality", "family", "trained", "persons"];
  var OP_ARITY = {kind: 2, set: 3, size: 3, axes: 2, drop_axis: 2, add_axis: 4, parts: 2, licence: 2, cut: 2};
  var PATTERN_KEYS = ["kind", "rank", "time", "has_axes", "dtype", "targets", "parts", "needs_parts", "modality",
    "trained"];
  var PARAM_KINDS = ["choice", "int", "float", "bool", "set", "names"];
  var CONDITION_KEYS = ["in", "not_in", "min", "max", "above", "below", "empty", "nonempty"];
  var EXPERIMENT_KEYS = ["recipe", "epochs", "seed", "hours", "blocks", "only"];
  var CARD_FIELDS = ["origin", "where", "count", "persons", "split", "held_out", "licence"];
  var TODAY_STRINGS = ["route", "word", "flow", "note"];

  // The experiment route's blocks, and the stages a block may repeat on one board without a penalty.
  var CATALOG = "catalog_v1";
  var CLASSIFIER = "classifier";
  var TRAINER = "train_classifier";
  var REPEATABLE = ["evaluate", "analyse", "report"];

  // tools/experiments_panel.py: ISSUE_MARKER, ISSUE_LABEL, FLOW_HEAD and issue_body's two paragraphs.
  // Each "<" of the two markers is spelled as the escape \u003c, so that the page's script element
  // never holds an HTML comment opener.
  var REPO = "OpenSpineConsortium/SchwingNet";
  var MARKER = "\u003c!-- schwingnet-experiment --\u003e";
  var FLOW_HEAD = "python3 tools/flow.py run --catalog <catalog> --out <runs> --mode slurm";
  var REQUESTED = "Requested from the textbook's experiments panel (chapter 35). The workflow reads only the lines " +
    "above, checks each value against data/recipes/ and src/schwingnet/blocks.py, and answers with the exact flow " +
    "command and the gate word that queues it; nothing runs on the grid without the owner's word and the number of jobs.";
  var COMMAND_INTRO = "The command this names:";
  var PIPELINE_MARKER = "\u003c!-- schwingnet-pipeline --\u003e";
  var PIPELINE_CLOSING = "Nothing answers this issue yet: the pipeline route waits on the owner's word " +
    "(docs/research/pipeline-sandbox/README.md).";
  // The experiment form's own defaults (experiments_panel.form_text), used only when no node maps one.
  var FORM_DEFAULTS = {epochs: 20, seed: 1, hours: 4};

  // ------------------------------------------------------------------------------------------------
  // Small helpers. Maps keyed by text a viewer wrote never read an inherited property.

  function has(o, k) {
    return o !== null && typeof o === "object" && Object.prototype.hasOwnProperty.call(o, k);
  }

  function get(o, k) {
    return has(o, k) ? o[k] : undefined;
  }

  function put(o, k, v) {
    Object.defineProperty(o, k, {value: v, enumerable: true, writable: true, configurable: true});
    return o;
  }

  function isObj(v) {
    return v !== null && typeof v === "object" && !Array.isArray(v);
  }

  function isStr(v) {
    return typeof v === "string";
  }

  function isNum(v) {
    return typeof v === "number" && isFinite(v);
  }

  function isInt(v) {
    return typeof v === "number" && Number.isInteger(v);
  }

  function arrayOf(v) {
    return Array.isArray(v) ? v : [];
  }

  function clone(v) {
    if (Array.isArray(v)) return v.map(clone);
    if (isObj(v)) {
      var out = {};
      Object.keys(v).forEach(function (k) {
        if (v[k] !== undefined) put(out, k, clone(v[k]));
      });
      return out;
    }
    return v;
  }

  function deepEqual(a, b) {
    if (a === b) return true;
    if (Array.isArray(a) && Array.isArray(b)) {
      if (a.length !== b.length) return false;
      for (var i = 0; i < a.length; i++) if (!deepEqual(a[i], b[i])) return false;
      return true;
    }
    if (isObj(a) && isObj(b)) {
      var ka = Object.keys(a).sort(), kb = Object.keys(b).sort();
      if (!deepEqual(ka, kb)) return false;
      for (var j = 0; j < ka.length; j++) if (!deepEqual(a[ka[j]], b[ka[j]])) return false;
      return true;
    }
    return false;
  }

  // Strings in code point order, as Python sorts them.
  function cmpStr(a, b) {
    a = String(a);
    b = String(b);
    var i = 0, j = 0;
    while (i < a.length && j < b.length) {
      var ca = a.codePointAt(i), cb = b.codePointAt(j);
      if (ca !== cb) return ca < cb ? -1 : 1;
      i += ca > 0xffff ? 2 : 1;
      j += cb > 0xffff ? 2 : 1;
    }
    if (i < a.length) return 1;
    if (j < b.length) return -1;
    return 0;
  }

  function sortedKeys(o) {
    return isObj(o) ? Object.keys(o).sort(cmpStr) : [];
  }

  function unique(list) {
    var seen = new Set(), out = [];
    list.forEach(function (x) {
      if (!seen.has(x)) {
        seen.add(x);
        out.push(x);
      }
    });
    return out;
  }

  function repeat(s, n) {
    var out = "";
    for (var i = 0; i < n; i++) out += s;
    return out;
  }

  function printable(s) {
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i);
      if (c < 0x20 || c > 0x7e) return false;
    }
    return true;
  }

  // A value as a short ASCII word for a problem's text.
  function show(v) {
    if (v === undefined) return "nothing";
    try {
      var s = canonical(v);
      return s.length > 60 ? s.slice(0, 57) + "..." : s;
    } catch (e) {
      return "a value that is not plain ASCII JSON";
    }
  }

  function plural(n, word) {
    return n + " " + word + (n === 1 ? "" : "s");
  }

  // The number of a node id ("n12" is 12); an id of another shape sorts after every node.
  function nodeNumber(id) {
    return isStr(id) && NODE_RE.test(id) ? Number(id.slice(1)) : Infinity;
  }

  function cmpNodeIds(a, b) {
    var na = nodeNumber(a), nb = nodeNumber(b);
    if (na !== nb) return na < nb ? -1 : 1;
    return cmpStr(a, b);
  }

  // ------------------------------------------------------------------------------------------------
  // Numbers as Python writes them. A finite double is exactly digits / 10^scale; rounding is done on
  // those digits, ties to even, which is what format(), round() and f"{v:g}" do in CPython.

  function limbsOf(s) {
    var out = [];
    for (var end = s.length; end > 0; end -= 7) out.push(Number(s.slice(Math.max(0, end - 7), end)));
    return out;
  }

  function multiplyLimbs(limbs, m) {
    var carry = 0;
    for (var i = 0; i < limbs.length; i++) {
      var v = limbs[i] * m + carry;
      var low = v % 1e7;
      limbs[i] = low;
      carry = (v - low) / 1e7;
    }
    while (carry > 0) {
      var rest = carry % 1e7;
      limbs.push(rest);
      carry = (carry - rest) / 1e7;
    }
  }

  function digitsOf(limbs) {
    var s = String(limbs[limbs.length - 1]);
    for (var i = limbs.length - 2; i >= 0; i--) s += ("000000" + limbs[i]).slice(-7);
    return s;
  }

  function exactDecimal(x) {
    var neg = x < 0 || (x === 0 && 1 / x < 0);
    var a = Math.abs(x);
    if (a === 0) return {neg: neg, digits: "0", scale: 0};
    var twos = 0, halves = 0;
    while (a >= 9007199254740992) {
      a /= 2;
      twos += 1;
    }
    while (!Number.isInteger(a)) {
      a *= 2;
      halves += 1;
    }
    var limbs = limbsOf(String(a));
    var i;
    for (i = 0; i < twos; i += 20) multiplyLimbs(limbs, Math.pow(2, Math.min(20, twos - i)));
    for (i = 0; i < halves; i += 10) multiplyLimbs(limbs, Math.pow(5, Math.min(10, halves - i)));
    return {neg: neg, digits: digitsOf(limbs), scale: halves};
  }

  // Compare the fraction 0.<tail> with one half: 1 above, 0 equal, -1 below.
  function againstHalf(tail) {
    var c = tail.charCodeAt(0) - 48;
    if (c !== 5) return c > 5 ? 1 : -1;
    for (var i = 1; i < tail.length; i++) if (tail.charCodeAt(i) !== 48) return 1;
    return 0;
  }

  function isOddDigits(s) {
    return (s.charCodeAt(s.length - 1) - 48) % 2 === 1;
  }

  function incrementDigits(s) {
    var a = s.split("");
    for (var i = a.length - 1; i >= 0; i--) {
      if (a[i] === "9") {
        a[i] = "0";
      } else {
        a[i] = String.fromCharCode(a[i].charCodeAt(0) + 1);
        return a.join("");
      }
    }
    return "1" + a.join("");
  }

  function roundDigits(head, tail) {
    if (!tail.length) return head;
    var half = againstHalf(tail);
    return half > 0 || (half === 0 && isOddDigits(head)) ? incrementDigits(head) : head;
  }

  // Python's format(x, ".<places>f").
  function pyFixed(x, places) {
    var e = exactDecimal(x);
    var whole;
    if (e.scale <= places) {
      whole = e.digits + repeat("0", places - e.scale);
    } else {
      var cut = e.scale - places;
      var digits = e.digits.length > cut ? e.digits : repeat("0", cut - e.digits.length + 1) + e.digits;
      whole = roundDigits(digits.slice(0, digits.length - cut), digits.slice(digits.length - cut));
    }
    whole = whole.replace(/^0+(?=[0-9])/, "");
    if (places > 0) {
      while (whole.length <= places) whole = "0" + whole;
      whole = whole.slice(0, whole.length - places) + "." + whole.slice(whole.length - places);
    }
    return (e.neg ? "-" : "") + whole;
  }

  // Python's f"{x:g}": six significant digits, trailing zeros dropped, an exponent below 1e-4 or
  // from 1e6.
  function pyG(x) {
    var e = exactDecimal(x);
    if (e.digits === "0") return (e.neg ? "-" : "") + "0";
    var precision = 6;
    var decpt = e.digits.length - e.scale;
    var keep = e.digits;
    if (keep.length > precision) {
      keep = roundDigits(keep.slice(0, precision), keep.slice(precision));
      if (keep.length > precision) {
        keep = keep.slice(0, precision);
        decpt += 1;
      }
    }
    keep = keep.replace(/0+$/, "");
    var s;
    if (decpt <= -4 || decpt > precision) {
      var exp = decpt - 1, size = Math.abs(exp);
      s = keep.charAt(0) + (keep.length > 1 ? "." + keep.slice(1) : "") + "e" + (exp < 0 ? "-" : "+") +
        (size < 10 ? "0" : "") + size;
    } else if (decpt <= 0) {
      s = "0." + repeat("0", -decpt) + keep;
    } else if (decpt >= keep.length) {
      s = keep + repeat("0", decpt - keep.length);
    } else {
      s = keep.slice(0, decpt) + "." + keep.slice(decpt);
    }
    return (e.neg ? "-" : "") + s;
  }

  // Python's round(x, places).
  function pyRound(x, places) {
    return Number(pyFixed(x, places));
  }

  function CanonicalError(path, why) {
    this.name = "CanonicalError";
    this.path = path;
    this.message = (path || "the value") + " " + why;
  }
  CanonicalError.prototype = Object.create(Error.prototype);
  CanonicalError.prototype.constructor = CanonicalError;

  // Section 8: an integer when whole and below 1e15, else six decimals with the zeros and the point
  // stripped.
  function formatNumber(v, path) {
    if (typeof v !== "number" || !isFinite(v)) throw new CanonicalError(path, "is not a finite number");
    if (Number.isInteger(v) && Math.abs(v) < 1e15) return String(v === 0 ? 0 : v);
    return pyFixed(v, 6).replace(/0+$/, "").replace(/\.$/, "");
  }

  // A value is written plainly when it is 0, or from 0.0001 to below 1e9 with at most six decimals,
  // so that no reader meets an exponent (section 5).
  function floatPlain(v) {
    if (!isNum(v)) return false;
    if (v === 0) return true;
    return v >= 0.0001 && v < 1e9 && Number(pyFixed(v, 6)) === v;
  }

  // ------------------------------------------------------------------------------------------------
  // Canonical JSON (section 8) and SHA-256.

  function writeString(s, path) {
    if (!printable(s)) throw new CanonicalError(path, "holds a character outside printable ASCII");
    return JSON.stringify(s);
  }

  function writeValue(v, out, path) {
    if (v === null) {
      out.push("null");
    } else if (v === true || v === false) {
      out.push(v ? "true" : "false");
    } else if (typeof v === "number") {
      out.push(formatNumber(v, path));
    } else if (typeof v === "string") {
      out.push(writeString(v, path));
    } else if (Array.isArray(v)) {
      out.push("[");
      for (var i = 0; i < v.length; i++) {
        if (i) out.push(",");
        writeValue(v[i], out, path + "[" + i + "]");
      }
      out.push("]");
    } else if (typeof v === "object") {
      var keys = Object.keys(v).filter(function (k) { return v[k] !== undefined; }).sort(cmpStr);
      out.push("{");
      keys.forEach(function (k, n) {
        if (n) out.push(",");
        out.push(writeString(k, path + " key"));
        out.push(":");
        writeValue(v[k], out, path + "." + k);
      });
      out.push("}");
    } else {
      throw new CanonicalError(path, "is not a JSON value");
    }
  }

  function canonical(value) {
    var out = [];
    writeValue(value, out, "$");
    return out.join("");
  }

  var SHA_K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];

  // The UTF-8 bytes of a string; a lone surrogate becomes U+FFFD, as TextEncoder writes it.
  function utf8(text) {
    var n = text.length, i, ascii = true;
    for (i = 0; i < n; i++) {
      if (text.charCodeAt(i) > 0x7f) {
        ascii = false;
        break;
      }
    }
    if (ascii) {
      var plain = new Uint8Array(n);
      for (i = 0; i < n; i++) plain[i] = text.charCodeAt(i);
      return plain;
    }
    var out = [];
    for (i = 0; i < n; i++) {
      var c = text.charCodeAt(i);
      if (c >= 0xd800 && c <= 0xdbff && i + 1 < n) {
        var d = text.charCodeAt(i + 1);
        if (d >= 0xdc00 && d <= 0xdfff) {
          c = 0x10000 + ((c - 0xd800) << 10) + (d - 0xdc00);
          i += 1;
        } else {
          c = 0xfffd;
        }
      } else if (c >= 0xd800 && c <= 0xdfff) {
        c = 0xfffd;
      }
      if (c < 0x80) {
        out.push(c);
      } else if (c < 0x800) {
        out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
      } else if (c < 0x10000) {
        out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
      } else {
        out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
      }
    }
    return Uint8Array.from(out);
  }

  function rotr(x, n) {
    return (x >>> n) | (x << (32 - n));
  }

  function sha256(text) {
    var bytes = utf8(String(text));
    var n = bytes.length;
    var total = Math.ceil((n + 9) / 64) * 64;
    var buf = new Uint8Array(total);
    buf.set(bytes);
    buf[n] = 0x80;
    var high = Math.floor(n / 0x20000000), low = (n % 0x20000000) * 8;
    for (var b = 0; b < 4; b++) {
      buf[total - 1 - b] = (low >>> (8 * b)) & 0xff;
      buf[total - 5 - b] = (high >>> (8 * b)) & 0xff;
    }
    var h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
    var w = new Int32Array(64);
    for (var off = 0; off < total; off += 64) {
      var t;
      for (t = 0; t < 16; t++) {
        var p = off + 4 * t;
        w[t] = (buf[p] << 24) | (buf[p + 1] << 16) | (buf[p + 2] << 8) | buf[p + 3];
      }
      for (t = 16; t < 64; t++) {
        var w15 = w[t - 15], w2 = w[t - 2];
        var s0 = rotr(w15, 7) ^ rotr(w15, 18) ^ (w15 >>> 3);
        var s1 = rotr(w2, 17) ^ rotr(w2, 19) ^ (w2 >>> 10);
        w[t] = (w[t - 16] + s0 + w[t - 7] + s1) | 0;
      }
      var a = h[0], bb = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
      for (t = 0; t < 64; t++) {
        var big1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        var ch = (e & f) ^ (~e & g);
        var t1 = (hh + big1 + ch + SHA_K[t] + w[t]) | 0;
        var big0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        var maj = (a & bb) ^ (a & c) ^ (bb & c);
        var t2 = (big0 + maj) | 0;
        hh = g;
        g = f;
        f = e;
        e = (d + t1) | 0;
        d = c;
        c = bb;
        bb = a;
        a = (t1 + t2) | 0;
      }
      h[0] = (h[0] + a) | 0;
      h[1] = (h[1] + bb) | 0;
      h[2] = (h[2] + c) | 0;
      h[3] = (h[3] + d) | 0;
      h[4] = (h[4] + e) | 0;
      h[5] = (h[5] + f) | 0;
      h[6] = (h[6] + g) | 0;
      h[7] = (h[7] + hh) | 0;
    }
    return h.map(function (x) { return ("0000000" + (x >>> 0).toString(16)).slice(-8); }).join("");
  }

  // ------------------------------------------------------------------------------------------------
  // The contract, the blocks and the experiment route's data, each read with defaults so a partial
  // DATA object never throws.

  var contractCache = typeof WeakMap === "function" ? new WeakMap() : null;

  function listOr(v, fallback) {
    return Array.isArray(v) ? v.slice() : fallback.slice();
  }

  function norm(contract) {
    var c = isObj(contract) ? contract : {};
    if (contractCache && contractCache.has(c)) return contractCache.get(c);
    var stageList = Array.isArray(c.stages) ? c.stages : STAGES.map(function (id) { return {id: id}; });
    var stages = [], titles = new Map();
    stageList.forEach(function (s) {
      var id = isObj(s) ? s.id : s;
      if (!isStr(id)) return;
      stages.push(id);
      var title = isObj(s) && isStr(s.title) ? s.title : id.charAt(0).toUpperCase() + id.slice(1);
      titles.set(id, title);
    });
    var limits = {};
    Object.keys(LIMITS).forEach(function (k) {
      limits[k] = isObj(c.limits) && isNum(c.limits[k]) ? c.limits[k] : LIMITS[k];
    });
    var out = {
      stages: stages,
      titles: titles,
      kinds: isObj(c.kinds) ? Object.keys(c.kinds) : listOr(c.kinds, KINDS),
      axes: isObj(c.axes) ? Object.keys(c.axes) : listOr(c.axes, AXES),
      spatial: listOr(c.spatial, SPATIAL),
      dtypes: listOr(c.dtypes, DTYPES),
      targets: listOr(c.targets, TARGETS),
      parts: listOr(c.parts, PARTS),
      modalities: listOr(c.modalities, MODALITIES),
      licences: listOr(c.licences, LICENCES),
      job_classes: listOr(c.job_classes, JOB_CLASSES),
      today: listOr(c.today, TODAY),
      code: listOr(c.code, CODE),
      deterministic: listOr(c.deterministic, DETERMINISTIC),
      needs: listOr(c.needs, NEEDS),
      glyphs: listOr(c.glyphs, GLYPHS),
      limits: limits,
      probes: arrayOf(c.probes).filter(isObj)
    };
    if (contractCache) contractCache.set(c, out);
    return out;
  }

  function contractOf(data) {
    return norm(isObj(data) ? data.contract : null);
  }

  function blockMap(data) {
    var map = new Map();
    arrayOf(isObj(data) ? data.blocks : null).forEach(function (m) {
      if (isObj(m) && isStr(m.id) && !map.has(m.id)) map.set(m.id, m);
    });
    return map;
  }

  function experimentOf(data) {
    var x = isObj(data) && isObj(data.experiment) ? data.experiment : {};
    return {
      repo: isStr(x.repo) ? x.repo : REPO,
      newUrl: isStr(x["new"]) ? x["new"] : "https://github.com/" + REPO + "/issues/new",
      label: isStr(x.label) ? x.label : "experiment",
      marker: isStr(x.marker) ? x.marker : MARKER,
      flow: isStr(x.flow) ? x.flow : FLOW_HEAD,
      fields: arrayOf(x.fields).filter(isStr),
      defaults: isObj(x.defaults) ? x.defaults : {}
    };
  }

  function stageIndex(C, stage) {
    return C.stages.indexOf(stage);
  }

  function stageTitle(C, stage) {
    return C.titles.get(stage) || String(stage);
  }

  function paramsOf(manifest) {
    return arrayOf(isObj(manifest) ? manifest.params : null).filter(function (p) {
      return isObj(p) && isStr(p.name);
    });
  }

  function paramNamed(manifest, name) {
    var found = null;
    paramsOf(manifest).forEach(function (p) {
      if (!found && p.name === name) found = p;
    });
    return found;
  }

  function portsOf(manifest, key) {
    return arrayOf(isObj(manifest) ? manifest[key] : null).filter(function (p) {
      return isObj(p) && isStr(p.name);
    });
  }

  function portNames(manifest, key) {
    return portsOf(manifest, key).map(function (p) { return p.name; });
  }

  function jobOf(manifest) {
    return isObj(manifest) && isObj(manifest.job) ? manifest.job : {};
  }

  function computeClass(manifest) {
    var cls = jobOf(manifest)["class"];
    return cls === "cpu" || cls === "gpu" ? cls : null;
  }

  // ------------------------------------------------------------------------------------------------
  // Type records (section 4).

  function emptyType() {
    return {kind: "data", axes: [], sizes: {}, dtype: "any", targets: "none", classes: null, parts: [],
      persons: false, modality: "any", licence: "uncut", sources: [], family: null, rank: 0, trained: false};
  }

  function rankOf(axes, C) {
    var spatial = C ? C.spatial : SPATIAL;
    return arrayOf(axes).filter(function (a) { return spatial.indexOf(a) >= 0; }).length;
  }

  // A full, separate copy of a type; a missing field takes the empty type's value.
  function copyType(src) {
    var t = emptyType();
    if (!isObj(src)) return t;
    TYPE_FIELDS.forEach(function (f) {
      if (has(src, f) && src[f] !== undefined) t[f] = clone(src[f]);
    });
    if (!Array.isArray(t.axes)) t.axes = [];
    if (!isObj(t.sizes)) t.sizes = {};
    if (!Array.isArray(t.parts)) t.parts = [];
    if (!Array.isArray(t.sources)) t.sources = [];
    return t;
  }

  function licenceLater(a, b, C) {
    var ia = C.licences.indexOf(a), ib = C.licences.indexOf(b);
    if (ia < 0) return b;
    if (ib < 0) return a;
    return ia >= ib ? a : b;
  }

  function licenceEarlier(a, b, C) {
    var ia = C.licences.indexOf(a), ib = C.licences.indexOf(b);
    if (ia < 0) return b;
    if (ib < 0) return a;
    return ia <= ib ? a : b;
  }

  function pruneSizes(t) {
    var sizes = {};
    t.axes.forEach(function (a) {
      if (has(t.sizes, a)) put(sizes, a, t.sizes[a]);
    });
    t.sizes = sizes;
  }

  function finishType(t, C) {
    t.rank = rankOf(t.axes, C);
    pruneSizes(t);
    t.parts = C.parts.filter(function (p) { return t.parts.indexOf(p) >= 0; });
  }

  function mergeLineage(t, other, C) {
    t.sources = t.sources.concat(arrayOf(other.sources));
    t.licence = licenceLater(t.licence, other.licence, C);
    t.persons = t.persons === true && other.persons === true;
  }

  function fieldOf(t, field, C) {
    var size = /^sizes\.([A-Za-z])$/.exec(field);
    if (size) return {ok: true, value: has(t.sizes, size[1]) ? clone(t.sizes[size[1]]) : null};
    if (TYPE_FIELDS.indexOf(field) < 0) return {ok: false};
    if (field === "rank") return {ok: true, value: rankOf(t.axes, C)};
    return {ok: true, value: clone(t[field])};
  }

  // A short reading of a type for an edge label: "N x 1 x 64 x 64 uint8, level 27, train/validation/test".
  function typeSummary(type) {
    if (!isObj(type)) return "no type";
    var t = copyType(type);
    var bits = [];
    var built = t.kind === "model" || t.kind === "checkpoint";
    if (t.kind !== "data") bits.push(t.kind + (built && isStr(t.family) && t.family ? " " + t.family : ""));
    var shape = t.axes.map(function (a) {
      return has(t.sizes, a) && isNum(t.sizes[a]) ? formatNumber(t.sizes[a]) : String(a);
    }).join(" x ");
    var dtype = t.axes.length && t.dtype && t.dtype !== "any" ? String(t.dtype) : "";
    if (shape || dtype) bits.push(shape && dtype ? shape + " " + dtype : shape || dtype);
    if (t.targets && t.targets !== "none") bits.push(t.targets + (isNum(t.classes) ? " " + formatNumber(t.classes) : ""));
    if (t.parts.length) bits.push(t.parts.join("/"));
    else if (t.kind === "data") bits.push("unsplit");
    var text = bits.join(", ") || t.kind;
    return printable(text) ? text : text.replace(/[^\x20-\x7e]/g, "?");
  }

  function showResolved(v) {
    if (v === null || v === undefined || v === "") return "?";
    if (typeof v === "number") return isFinite(v) ? formatNumber(v) : "?";
    if (typeof v === "boolean") return v ? "yes" : "no";
    if (Array.isArray(v)) return v.length ? v.map(showResolved).join(", ") : "none";
    if (isObj(v)) return Object.keys(v).sort(cmpStr).map(function (k) { return k + "=" + showResolved(v[k]); }).join(", ") || "?";
    return String(v);
  }

  // A block's resolve text with {field} and {sizes.X} read from the type given (its first output's).
  function resolveText(manifest, type) {
    var text = isObj(manifest) && isStr(manifest.resolve) ? manifest.resolve : "";
    var t = isObj(type) ? copyType(type) : null;
    return text.replace(/\{([A-Za-z_]+(?:\.[A-Za-z_]+)?)\}/g, function (all, key) {
      if (!t) return "?";
      var found = fieldOf(t, key, null);
      return found.ok ? showResolved(found.value) : "?";
    });
  }

  // ------------------------------------------------------------------------------------------------
  // Patterns (section 6).

  function problem(code, node, port, field, level, text) {
    return {code: code, node: node === undefined ? null : node, port: port === undefined ? null : port,
      field: field === undefined ? null : field, level: level || "error", text: text};
  }

  function matches(pattern, type, contract) {
    var C = norm(contract);
    var out = [];
    function fail(key, text) {
      out.push(problem("type", null, null, key, "error", text));
    }
    if (!isObj(pattern)) {
      fail("kind", "the input states no pattern, so it takes nothing");
      return out;
    }
    var t = copyType(type);
    var kinds = arrayOf(pattern.kind);
    if (kinds.indexOf(t.kind) < 0) fail("kind", "takes " + (kinds.join(" or ") || "no kind") + ", not " + show(t.kind));
    if (has(pattern, "rank")) {
      var rank = rankOf(t.axes, C);
      if (arrayOf(pattern.rank).indexOf(rank) < 0) {
        fail("rank", "takes " + arrayOf(pattern.rank).join(" or ") + "-D data, not " + rank + "-D");
      }
    }
    if (pattern.time === "yes" && t.axes.indexOf("T") < 0) fail("time", "takes data with a time axis T");
    if (pattern.time === "no" && t.axes.indexOf("T") >= 0) fail("time", "takes data without a time axis T");
    if (has(pattern, "has_axes")) {
      var missing = arrayOf(pattern.has_axes).filter(function (a) { return t.axes.indexOf(a) < 0; });
      if (missing.length) fail("has_axes", "needs the axes " + missing.join(", "));
    }
    if (has(pattern, "dtype") && t.dtype !== "any" && arrayOf(pattern.dtype).indexOf(t.dtype) < 0) {
      fail("dtype", "takes " + arrayOf(pattern.dtype).join(" or ") + ", not " + show(t.dtype));
    }
    if (has(pattern, "targets") && arrayOf(pattern.targets).indexOf(t.targets) < 0) {
      fail("targets", "takes targets " + arrayOf(pattern.targets).join(" or ") + ", not " + show(t.targets));
    }
    if (pattern.parts === "split" && !t.parts.length) fail("parts", "takes data split into parts, and this is unsplit");
    if (pattern.parts === "unsplit" && t.parts.length) fail("parts", "takes unsplit data, and this is split");
    if (has(pattern, "needs_parts")) {
      var lacking = arrayOf(pattern.needs_parts).filter(function (p) { return t.parts.indexOf(p) < 0; });
      if (lacking.length) fail("needs_parts", "needs the parts " + lacking.join(", "));
    }
    if (has(pattern, "modality") && t.modality !== "any" && arrayOf(pattern.modality).indexOf(t.modality) < 0) {
      fail("modality", "takes " + arrayOf(pattern.modality).join(" or ") + ", not " + show(t.modality));
    }
    if (has(pattern, "trained") && pattern.trained !== t.trained) {
      fail("trained", pattern.trained ? "takes a trained model" : "takes an untrained model");
    }
    return out;
  }

  function accepts(pattern, type, C) {
    return matches(pattern, type, C).length === 0;
  }

  // ------------------------------------------------------------------------------------------------
  // Ops (section 7).

  var BAD = {};

  function parseRef(ref) {
    if (!isStr(ref) || ref.charAt(0) !== "@") return null;
    var bits = ref.split(".");
    if (bits[0] === "@param" && bits.length === 2) return {scope: "param", name: bits[1]};
    if (bits[0] === "@in" && bits.length >= 3) return {scope: "in", port: bits[1], field: bits.slice(2).join(".")};
    if (bits[0] === "@self" && bits.length >= 2) return {scope: "self", field: bits.slice(1).join(".")};
    return {scope: "bad"};
  }

  function isRef(v) {
    return isStr(v) && v.charAt(0) === "@";
  }

  // A value or ref read for one node: ctx = {params, paramNames, inputNames, inputs (Map), self}.
  function readValue(v, ctx, C) {
    if (!isRef(v)) return clone(v);
    var ref = parseRef(v);
    if (ref.scope === "param") {
      return ctx.paramNames.has(ref.name) ? clone(get(ctx.params, ref.name)) : BAD;
    }
    if (ref.scope === "in") {
      if (!ctx.inputNames.has(ref.port)) return BAD;
      var t = ctx.inputs.get(ref.port);
      if (!t) return fieldOf(emptyType(), ref.field, C).ok ? null : BAD;
      var found = fieldOf(t, ref.field, C);
      return found.ok ? found.value : BAD;
    }
    if (ref.scope === "self" && ctx.self) {
      var own = fieldOf(ctx.self, ref.field, C);
      return own.ok ? own.value : BAD;
    }
    return BAD;
  }

  function validSetValue(field, v, C) {
    switch (field) {
      case "dtype": return v === "any" || C.dtypes.indexOf(v) >= 0;
      case "targets": return C.targets.indexOf(v) >= 0;
      case "classes": return v === null || (isInt(v) && v >= 1);
      case "modality": return C.modalities.indexOf(v) >= 0;
      case "family": return v === null || isStr(v);
      default: return typeof v === "boolean";
    }
  }

  function validSize(v) {
    return v === null || (isInt(v) && v >= 1);
  }

  function validAxisList(v, C) {
    return Array.isArray(v) && v.every(function (a) { return C.axes.indexOf(a) >= 0; }) &&
      unique(v).length === v.length;
  }

  function validPartList(v, C) {
    return Array.isArray(v) && v.every(function (p) { return C.parts.indexOf(p) >= 0; }) &&
      unique(v).length === v.length;
  }

  // One op on the type being built; a failure calls fail(text) and leaves the type as it was. A null
  // value, written or read from an unconnected port, removes a size, adds an axis with no size and
  // sets classes or family to null; any other op it leaves as it was, with no problem.
  function applyOp(t, op, ctx, C, fail) {
    if (!Array.isArray(op) || !isStr(op[0]) || !has(OP_ARITY, op[0])) {
      fail("an unknown op " + show(op));
      return;
    }
    ctx.self = t;
    var name = op[0];
    function value(i) {
      var v = readValue(op[i], ctx, C);
      if (v === BAD) fail(name + " names an unknown reference " + show(op[i]));
      return v;
    }
    var v, axis, i;
    switch (name) {
      case "kind":
        v = value(1);
        if (v === BAD || v === null) return;
        if (C.kinds.indexOf(v) < 0) return fail("kind " + show(v) + " is not a kind");
        t.kind = v;
        return;
      case "set":
        if (SET_FIELDS.indexOf(op[1]) < 0) return fail("set names a field it cannot set: " + show(op[1]));
        v = value(2);
        if (v === BAD) return;
        if (v === null && op[1] !== "classes" && op[1] !== "family") return;
        if (!validSetValue(op[1], v, C)) return fail("set " + op[1] + " to " + show(v) + ", which it cannot be");
        t[op[1]] = v;
        return;
      case "size":
        axis = op[1];
        v = value(2);
        if (v === BAD) return;
        if (v === null) {
          if (isStr(axis)) delete t.sizes[axis];
          return;
        }
        if (t.axes.indexOf(axis) < 0) return fail("size names the axis " + show(axis) + ", which the type lacks");
        if (!validSize(v)) return fail("size " + axis + " to " + show(v) + ", which is not a whole number from 1");
        put(t.sizes, axis, v);
        return;
      case "axes":
        v = value(1);
        if (v === BAD || v === null) return;
        if (!validAxisList(v, C)) return fail("axes " + show(v) + " is not a list of distinct axes");
        t.axes = v.slice();
        pruneSizes(t);
        return;
      case "drop_axis":
        i = t.axes.indexOf(op[1]);
        if (i >= 0) {
          t.axes.splice(i, 1);
          delete t.sizes[op[1]];
        }
        return;
      case "add_axis":
        axis = op[1];
        if (C.axes.indexOf(axis) < 0) return fail("add_axis names " + show(axis) + ", which is not an axis");
        if (t.axes.indexOf(axis) >= 0) return;
        v = op.length > 3 ? value(3) : null;
        if (v === BAD) return;
        if (!validSize(v)) return fail("add_axis " + axis + " of size " + show(v) + ", which is not a whole number from 1");
        i = op[2] === null || op[2] === undefined ? -1 : t.axes.indexOf(op[2]);
        t.axes.splice(i < 0 ? t.axes.length : i, 0, axis);
        if (v !== null) put(t.sizes, axis, v);
        return;
      case "parts":
        v = value(1);
        if (v === BAD || v === null) return;
        if (!validPartList(v, C)) return fail("parts " + show(v) + " is not a list of distinct parts");
        t.parts = v.slice();
        return;
      default:
        v = value(1);
        if (v === BAD || v === null) return;
        if (C.licences.indexOf(v) < 0) return fail(name + " " + show(v) + " is not a licence class");
        t.licence = name === "licence" ? licenceLater(t.licence, v, C) : licenceEarlier(t.licence, v, C);
    }
  }

  // Every output of a block from its connected input types (a Map port -> type) and its params;
  // fail(port, text) receives each op problem.
  function computeOutputs(manifest, inputs, params, C, fail) {
    var inputPorts = portsOf(manifest, "inputs");
    var ctx = {
      params: params,
      paramNames: new Set(paramsOf(manifest).map(function (p) { return p.name; })),
      inputNames: new Set(inputPorts.map(function (p) { return p.name; })),
      inputs: inputs,
      self: null
    };
    var outs = {};
    portsOf(manifest, "outputs").forEach(function (o) {
      var base = null;
      if (isStr(o.from) && inputs.has(o.from)) {
        base = o.from;
      } else {
        inputPorts.forEach(function (p) {
          if (base === null && inputs.has(p.name)) base = p.name;
        });
      }
      var t = base === null ? emptyType() : copyType(inputs.get(base));
      arrayOf(o.ops).forEach(function (op) {
        applyOp(t, op, ctx, C, function (text) { fail(o.name, isStr(op && op[0]) ? op[0] : null, text); });
      });
      finishType(t, C);
      inputPorts.forEach(function (p) {
        if (p.name !== base && inputs.has(p.name)) mergeLineage(t, inputs.get(p.name), C);
      });
      if (manifest.stage === "source" && isStr(manifest.id)) t.sources.push(manifest.id);
      t.sources = unique(t.sources.filter(isStr)).sort(cmpStr);
      put(outs, o.name, t);
    });
    return outs;
  }

  // ------------------------------------------------------------------------------------------------
  // Params and rules (sections 5 and 10).

  var regexCache = new Map();

  function fullRegex(pattern) {
    if (regexCache.has(pattern)) return regexCache.get(pattern);
    var re = null;
    try {
      re = new RegExp("^(?:" + pattern + ")$");
    } catch (e) {
      re = null;
    }
    regexCache.set(pattern, re);
    return re;
  }

  function namesPattern(p) {
    return has(p, "pattern") ? p.pattern : NAMES_PATTERN;
  }

  function inOrder(list, options) {
    var last = -1;
    for (var i = 0; i < list.length; i++) {
      var at = options.indexOf(list[i]);
      if (at <= last) return false;
      last = at;
    }
    return true;
  }

  // Why a value breaks its param's rules, or null when it keeps them.
  function valueProblem(p, v) {
    var name = p.name;
    switch (p.kind) {
      case "choice":
        if (arrayOf(p.choices).indexOf(v) >= 0 && isStr(v)) return null;
        return name + " " + show(v) + " is not one of " + arrayOf(p.choices).join(", ");
      case "int":
        if (!isInt(v)) return name + " " + show(v) + " is not a whole number";
        if (!(v >= p.low && v <= p.high)) return name + " " + show(v) + " is outside " + show(p.low) + " to " + show(p.high);
        return null;
      case "float":
        if (!isNum(v)) return name + " " + show(v) + " is not a number";
        if (p.above === true ? !(v > p.low) : !(v >= p.low)) {
          return name + " " + show(v) + " is not " + (p.above === true ? "above " : "at least ") + show(p.low);
        }
        if (!(v <= p.high)) return name + " " + show(v) + " is above " + show(p.high);
        if (!floatPlain(v)) return name + " " + show(v) + " is not 0 or a number from 0.0001 with at most 6 decimals";
        return null;
      case "bool":
        return typeof v === "boolean" ? null : name + " " + show(v) + " is not true or false";
      case "set":
        if (!Array.isArray(v)) return name + " " + show(v) + " is not a list";
        if (!v.every(function (x) { return isStr(x) && arrayOf(p.options).indexOf(x) >= 0; })) {
          return name + " " + show(v) + " names something outside " + arrayOf(p.options).join(", ");
        }
        if (!inOrder(v, arrayOf(p.options))) return name + " " + show(v) + " repeats a value or breaks the options' order";
        return null;
      case "names":
        if (!Array.isArray(v)) return name + " " + show(v) + " is not a list";
        var re = isStr(namesPattern(p)) ? fullRegex(namesPattern(p)) : null;
        if (!re) return name + " has a pattern that is not a regular expression";
        if (!v.every(function (x) { return isStr(x) && re.test(x); })) {
          return name + " " + show(v) + " holds a name that does not match " + namesPattern(p);
        }
        if (unique(v).length !== v.length) return name + " " + show(v) + " repeats a name";
        return null;
      default:
        return name + " has an unknown kind " + show(p.kind);
    }
  }

  function emptyValue(v) {
    return (Array.isArray(v) && v.length === 0) || v === 0 || v === false || v === "" || v === "none";
  }

  function conditionHolds(cond, v) {
    if (!isObj(cond)) return false;
    if (has(cond, "in") && !arrayOf(cond["in"]).some(function (x) { return deepEqual(x, v); })) return false;
    if (has(cond, "not_in") && arrayOf(cond.not_in).some(function (x) { return deepEqual(x, v); })) return false;
    if (has(cond, "min") && !(isNum(v) && v >= cond.min)) return false;
    if (has(cond, "max") && !(isNum(v) && v <= cond.max)) return false;
    if (has(cond, "above") && !(isNum(v) && v > cond.above)) return false;
    if (has(cond, "below") && !(isNum(v) && v < cond.below)) return false;
    if (has(cond, "empty") && emptyValue(v) !== (cond.empty === true)) return false;
    if (has(cond, "nonempty") && emptyValue(v) === (cond.nonempty === true)) return false;
    return true;
  }

  function ruleFails(rule, params) {
    if (!isObj(rule)) return false;
    var when = isObj(rule.when) ? rule.when : {}, need = isObj(rule.need) ? rule.need : {};
    var fires = Object.keys(when).every(function (k) { return conditionHolds(when[k], get(params, k)); });
    if (!fires) return false;
    return Object.keys(need).some(function (k) { return !conditionHolds(need[k], get(params, k)); });
  }

  // The cartesian product of [{key, values}] in order, the last list varying fastest, as
  // itertools.product does; each item is a list of the values chosen.
  function product(dims) {
    var out = [[]];
    dims.forEach(function (d) {
      var next = [];
      out.forEach(function (row) {
        d.values.forEach(function (v) { next.push(row.concat([v])); });
      });
      out = next;
    });
    return out;
  }

  function overlay(base, keys, values) {
    var params = clone(base);
    keys.forEach(function (k, i) { put(params, k, clone(values[i])); });
    return params;
  }

  function effectiveParams(node, manifest) {
    var out = {};
    paramsOf(manifest).forEach(function (p) { put(out, p.name, clone(p["default"])); });
    var given = isObj(node) && isObj(node.params) ? node.params : {};
    Object.keys(given).forEach(function (k) {
      if (given[k] !== undefined) put(out, k, clone(given[k]));
    });
    return out;
  }

  // ------------------------------------------------------------------------------------------------
  // The canonical spec and its digest (section 8).

  function orNull(v) {
    return v === undefined ? null : v;
  }

  function specOf(spec, data) {
    var blocks = blockMap(data);
    var s = isObj(spec) ? spec : {};
    var nodes = arrayOf(s.nodes).filter(isObj).map(function (n) {
      var m = isStr(n.block) ? blocks.get(n.block) : undefined;
      var vary = {};
      sortedKeys(n.vary).forEach(function (k) {
        var values = n.vary[k];
        if (Array.isArray(values) && values.length) put(vary, k, clone(values));
      });
      return {id: orNull(n.id), block: orNull(n.block), version: orNull(n.version),
        params: m ? effectiveParams(n, m) : (isObj(n.params) ? clone(n.params) : {}), vary: vary};
    });
    nodes.sort(function (a, b) { return cmpNodeIds(a.id, b.id); });
    var edges = arrayOf(s.edges).filter(isObj).map(function (e) {
      return {from: orNull(e.from), out: orNull(e.out), to: orNull(e.to), "in": orNull(e["in"])};
    });
    edges.sort(function (a, b) {
      return cmpNodeIds(a.from, b.from) || cmpStr(a.out, b.out) || cmpNodeIds(a.to, b.to) || cmpStr(a["in"], b["in"]);
    });
    return {sandbox: 1, name: isStr(s.name) ? s.name : "", nodes: nodes, edges: edges};
  }

  function canonicalText(spec, data) {
    try {
      return canonical(specOf(spec, data));
    } catch (e) {
      return null;
    }
  }

  // The digest, or "" when the spec cannot be written as canonical JSON (propagate says why).
  function digest(spec, data) {
    var text = canonicalText(spec, data);
    return text === null ? "" : sha256(text);
  }

  // ------------------------------------------------------------------------------------------------
  // Propagation (section 10).

  // A list of problems. Propagation and jobs keep one problem per occurrence, as sections 10 and 11
  // count them; the manifest check (merge true) keeps one per (code, field), the texts of repeats
  // joined, since section 13 compares those pairs and counts no occurrence.
  function ProblemList(merge) {
    this.list = [];
    this.merge = merge === true;
    this.index = new Map();
  }
  ProblemList.prototype.add = function (p) {
    if (this.merge) {
      var key = [p.code, p.field].map(function (x) { return x === null ? "\u0000" : String(x); }).join("\u0001");
      if (this.index.has(key)) {
        var known = this.index.get(key);
        if (known.text.split("; ").indexOf(p.text) < 0) known.text += "; " + p.text;
        return;
      }
      this.index.set(key, p);
    }
    this.list.push(p);
  };

  function graphOf(canon) {
    var byId = new Map(), invalid = [];
    canon.nodes.forEach(function (n) {
      if (!isStr(n.id) || !NODE_RE.test(n.id)) {
        invalid.push(n);
      } else if (byId.has(n.id)) {
        invalid.push(n);
      } else {
        byId.set(n.id, n);
      }
    });
    var edges = canon.edges.filter(function (e) { return byId.has(e.from) && byId.has(e.to); });
    return {byId: byId, invalid: invalid, edges: edges};
  }

  function edgesInto(graph, id, port) {
    return graph.edges.filter(function (e) { return e.to === id && (port === undefined || e["in"] === port); });
  }

  // Kahn's sort with ties broken by node number; what it cannot place is on or after a cycle.
  function topoOrder(graph) {
    var indeg = new Map(), out = new Map();
    graph.byId.forEach(function (n, id) {
      indeg.set(id, 0);
      out.set(id, []);
    });
    graph.edges.forEach(function (e) {
      indeg.set(e.to, indeg.get(e.to) + 1);
      out.get(e.from).push(e.to);
    });
    var ready = [];
    indeg.forEach(function (d, id) { if (d === 0) ready.push(id); });
    var order = [];
    while (ready.length) {
      ready.sort(cmpNodeIds);
      var id = ready.shift();
      order.push(id);
      out.get(id).forEach(function (to) {
        indeg.set(to, indeg.get(to) - 1);
        if (indeg.get(to) === 0) ready.push(to);
      });
    }
    var placed = new Set(order);
    var left = [];
    graph.byId.forEach(function (n, id) { if (!placed.has(id)) left.push(id); });
    return {order: order, left: left.sort(cmpNodeIds)};
  }

  function propagate(spec, data) {
    var C = contractOf(data), blocks = blockMap(data), canon = specOf(spec, data);
    var graph = graphOf(canon);
    var perNode = new Map(), graphProblems = new ProblemList();
    var result = {order: [], nodes: {}, problems: []};
    graph.byId.forEach(function (n, id) {
      perNode.set(id, new ProblemList());
      put(result.nodes, id, {inputs: {}, outputs: {}, problems: [], fan: 1, combinations: 1});
    });
    function report(code, node, port, field, level, text) {
      var p = problem(code, node, port, field, level, text);
      if (node !== null && perNode.has(node)) perNode.get(node).add(p);
      else graphProblems.add(p);
    }

    // Ids, and text that canonical JSON cannot write.
    graph.invalid.forEach(function (n) {
      var id = isStr(n.id) ? n.id : null;
      report("node", id, null, null, "error", isStr(n.id) && NODE_RE.test(n.id) ?
        "two nodes are named " + n.id + "; each node needs its own id" : "the node id " + show(n.id) + " is not n1 to n9999");
    });
    if (!isStr(canon.name) || !printable(canon.name)) {
      report("text", null, null, "name", "error", "the pipeline's name holds a character outside printable ASCII");
    }
    graph.byId.forEach(function (n, id) {
      try {
        canonical(n);
      } catch (e) {
        report("text", id, null, null, "error", "the node holds a value canonical JSON cannot write (" + e.message + ")");
      }
    });
    canon.edges.forEach(function (e) {
      try {
        canonical(e);
      } catch (err) {
        report("text", graph.byId.has(e.to) ? e.to : null, null, null, "error", "an edge holds text outside printable ASCII");
      }
    });

    // 1. Blocks and versions.
    graph.byId.forEach(function (n, id) {
      var m = isStr(n.block) ? blocks.get(n.block) : undefined;
      if (!m) {
        report("block", id, null, null, "error", "the block " + show(n.block) + " is not known here");
      } else if (n.version !== m.version) {
        report("version", id, null, null, "warn", "the node asks for version " + show(n.version) + " of " + m.id +
          "; this page has version " + show(m.version));
      }
    });
    function manifestOf(id) {
      var n = graph.byId.get(id);
      return n && isStr(n.block) ? blocks.get(n.block) : undefined;
    }

    // 2. Order.
    var topo = topoOrder(graph);
    result.order = topo.order;
    topo.left.forEach(function (id) {
      report("cycle", id, null, null, "error", "the node is on a cycle, or after one, so nothing can run it in order");
    });

    // 3. Edges.
    canon.edges.forEach(function (e) {
      var up = graph.byId.get(e.from), down = graph.byId.get(e.to);
      var port = isStr(e["in"]) ? e["in"] : null;
      if (!down) {
        report("port", null, port, null, "error", "an edge goes to " + show(e.to) + ", which is not a node");
        return;
      }
      if (!up) {
        report("port", e.to, port, null, "error", "an edge comes from " + show(e.from) + ", which is not a node");
        return;
      }
      var mu = manifestOf(e.from), md = manifestOf(e.to);
      var why = [];
      if (mu && portNames(mu, "outputs").indexOf(e.out) < 0) why.push(mu.id + " has no output " + show(e.out));
      if (md && portNames(md, "inputs").indexOf(e["in"]) < 0) why.push(md.id + " has no input " + show(e["in"]));
      if (why.length) report("port", e.to, port, null, "error", "the edge from " + e.from + ": " + why.join(" and "));
    });
    graph.byId.forEach(function (n, id) {
      var m = manifestOf(id);
      if (!m) return;
      portsOf(m, "inputs").forEach(function (p) {
        var count = edgesInto(graph, id, p.name).length;
        if (count > 1) report("port", id, p.name, null, "error", "the input " + p.name + " has " + count + " edges; it takes one");
        if (count === 0 && p.optional !== true) report("input", id, p.name, null, "error", "the input " + p.name + " is not connected");
      });
    });

    // 4 and 5. Params, vary and rules.
    graph.byId.forEach(function (n, id) {
      var entry = result.nodes[id];
      var varied = Object.keys(n.vary);
      var combinations = 1;
      varied.forEach(function (k) { combinations *= n.vary[k].length; });
      entry.combinations = combinations;
      var m = manifestOf(id);
      if (!m) return;
      var known = new Map();
      paramsOf(m).forEach(function (p) { if (!known.has(p.name)) known.set(p.name, p); });
      Object.keys(n.params).forEach(function (k) {
        var p = known.get(k);
        if (!p) {
          report("param", id, null, k, "error", m.id + " has no param " + show(k));
          return;
        }
        var why = valueProblem(p, n.params[k]);
        if (why) report("param", id, null, k, "error", why);
      });
      varied.forEach(function (k) {
        var p = known.get(k);
        if (!p) {
          report("param", id, null, k, "error", m.id + " has no param " + show(k) + " to vary");
          return;
        }
        if (p.vary !== true) report("vary", id, null, k, "error", p.name + " is not a param this block can vary");
        n.vary[k].forEach(function (v) {
          var why = valueProblem(p, v);
          if (why) report("param", id, null, k, "error", why);
        });
      });
      if (combinations > C.limits.combinations) {
        report("vary", id, null, null, "error", "the node varies into " + combinations + " combinations; at most " +
          C.limits.combinations);
      }
      var own = varied.filter(function (k) { return known.has(k); });
      var combos = combinations <= C.limits.combinations ?
        product(own.map(function (k) { return {values: n.vary[k]}; })) : [];
      arrayOf(m.rules).forEach(function (rule) {
        var fails = ruleFails(rule, n.params) || combos.some(function (values) {
          return ruleFails(rule, overlay(n.params, own, values));
        });
        if (fails) report("rule", id, null, null, "error", isObj(rule) && isStr(rule.say) ? rule.say : "a rule fails");
      });
    });

    // 6, 7 and 8. Types, reads and fan, in order.
    result.order.forEach(function (id) {
      var n = graph.byId.get(id), entry = result.nodes[id], m = manifestOf(id);
      var upstream = unique(edgesInto(graph, id).map(function (e) { return e.from; }));
      var widest = 0;
      upstream.forEach(function (u) { widest = Math.max(widest, result.nodes[u].fan); });
      entry.fan = (m && m.stage === "select" ? 1 : (widest || 1)) * entry.combinations;
      if (!m) return;
      var inputs = new Map();
      portsOf(m, "inputs").forEach(function (p) {
        var feed = edgesInto(graph, id, p.name)[0];
        if (!feed) return;
        var t = get(result.nodes[feed.from].outputs, feed.out);
        if (t) inputs.set(p.name, copyType(t));
      });
      portsOf(m, "inputs").forEach(function (p) {
        if (!inputs.has(p.name)) return;
        put(entry.inputs, p.name, copyType(inputs.get(p.name)));
        matches(p.accepts, inputs.get(p.name), C).forEach(function (q) {
          report("type", id, p.name, q.field, "error", "the input " + p.name + " " + q.text);
        });
      });
      entry.outputs = computeOutputs(m, inputs, n.params, C, function (port, opName, text) {
        report("op", id, port, opName, "error", "the output " + port + ": " + text);
      });
      var reads = arrayOf(isObj(m.reads) ? m.reads.parts : null);
      if (reads.indexOf("test") >= 0 && m.stage !== "evaluate" && m.stage !== "report") {
        report("test", id, null, null, "error", m.id + " reads the test part outside evaluation and report");
      }
      inputs.forEach(function (t, port) {
        if (t.kind !== "data") return;
        var lacking = reads.filter(function (part) { return t.parts.indexOf(part) < 0; });
        if (lacking.length) report("parts", id, port, null, "error", m.id + " reads " + lacking.join(", ") +
          ", which the data on " + port + " does not have");
      });
    });
    topo.left.forEach(function (id) {
      result.nodes[id].fan = result.nodes[id].combinations;
    });

    // 9. Graph limits.
    if (canon.nodes.length > C.limits.nodes) {
      report("limit", null, null, null, "error", "the pipeline has " + canon.nodes.length + " nodes; at most " + C.limits.nodes);
    }
    if (canon.edges.length > C.limits.edges) {
      report("limit", null, null, null, "error", "the pipeline has " + canon.edges.length + " edges; at most " + C.limits.edges);
    }
    var total = totalCombinations(result);
    if (total > C.limits.combinations) {
      report("limit", null, null, null, "error", "the pipeline varies into " + total + " combinations in all; at most " +
        C.limits.combinations);
    }

    graph.byId.forEach(function (n, id) {
      result.nodes[id].problems = perNode.get(id).list;
    });
    canon.nodes.forEach(function (n) {
      if (perNode.has(n.id) && graph.byId.get(n.id) === n) result.problems = result.problems.concat(perNode.get(n.id).list);
    });
    result.problems = result.problems.concat(graphProblems.list);
    return result;
  }

  function totalCombinations(prop) {
    var total = 1;
    Object.keys(prop.nodes).forEach(function (id) { total *= prop.nodes[id].combinations; });
    return total;
  }

  // ------------------------------------------------------------------------------------------------
  // Jobs (section 11).

  function hoursOf(job, params) {
    if (isNum(job.hours)) return job.hours;
    var ref = parseRef(job.hours);
    if (ref && ref.scope === "param") {
      var v = get(params, ref.name);
      return isNum(v) ? v : 0;
    }
    return 0;
  }

  // The first connected upstream node, by the block's input order, that is a compute node.
  function firstComputeUpstream(graph, blocks, id, manifest) {
    var found = null;
    portsOf(manifest, "inputs").forEach(function (p) {
      if (found) return;
      var feed = edgesInto(graph, id, p.name)[0];
      if (!feed) return;
      var up = graph.byId.get(feed.from);
      var mu = up && isStr(up.block) ? blocks.get(up.block) : undefined;
      var cls = computeClass(mu);
      if (cls) found = {id: feed.from, cls: cls};
    });
    return found;
  }

  function jobs(spec, data, prop) {
    var C = contractOf(data), blocks = blockMap(data), canon = specOf(spec, data);
    prop = isObj(prop) && Array.isArray(prop.order) ? prop : propagate(spec, data);
    var graph = graphOf(canon);
    var rows = [], rowOf = new Map(), problems = new ProblemList();
    prop.order.forEach(function (id) {
      var n = graph.byId.get(id);
      var m = n && isStr(n.block) ? blocks.get(n.block) : undefined;
      var cls = computeClass(m);
      if (!cls || !has(prop.nodes, id)) return;
      var job = jobOf(m), tasks = prop.nodes[id].fan;
      var row = {node: id, block: m.id, "class": cls, submissions: 0, tasks: tasks, hours: hoursOf(job, n.params),
        rides_with: null};
      var host = null;
      if (job.with_upstream === true) {
        var up = firstComputeUpstream(graph, blocks, id, m);
        if (up && up.cls === cls && rowOf.has(up.id)) {
          host = rowOf.get(up.id);
          if (host.rides_with) host = rowOf.get(host.rides_with);
        }
      }
      if (host) {
        row.rides_with = host.node;
        host.hours += row.hours;
      } else {
        row.submissions = job.array === true ? 1 : tasks;
        if (job.array === true && tasks > C.limits.array_tasks) {
          problems.add(problem("limit", id, null, null, "error", "the array job has " + tasks + " tasks; at most " +
            C.limits.array_tasks));
        }
      }
      rows.push(row);
      rowOf.set(id, row);
    });
    var totals = {cpu: {submissions: 0, tasks: 0, hours: 0}, gpu: {submissions: 0, tasks: 0, hours: 0}};
    rows.forEach(function (r) {
      if (r.rides_with) return;
      var sum = totals[r["class"]];
      sum.submissions += r.submissions;
      sum.tasks += r.tasks;
      sum.hours += r.tasks * r.hours;
    });
    totals.cpu.hours = pyRound(totals.cpu.hours, 2);
    totals.gpu.hours = pyRound(totals.gpu.hours, 2);
    return {rows: rows, totals: totals, problems: problems.list};
  }

  // ------------------------------------------------------------------------------------------------
  // Routes and compile (section 12).

  function flowCommand(named, epochs, seed, hours, recipe, head) {
    var words = [head, "--epochs " + epochs, "--seed " + seed, "--hours " + hours];
    if (recipe && recipe !== "none") words.push("--recipe " + recipe);
    named.forEach(function (w) { words.push("--block " + w); });
    return words.join(" ");
  }

  // tools/experiments_panel.py issue_body, byte for byte.
  function issueBody(named, epochs, seed, hours, recipe, X) {
    var lines = [X.marker, "recipe: " + (recipe || "none"), "epochs: " + epochs, "seed: " + seed, "hours: " + hours];
    named.forEach(function (w) { lines.push("block: " + w); });
    return lines.join("\n") + "\n\n" + REQUESTED + "\n\n" + COMMAND_INTRO + "\n\n    " +
      flowCommand(named, epochs, seed, hours, recipe, X.flow) + "\n";
  }

  function requestTitle(named, epochs) {
    return "Experiment: " + (named.length ? named.join(" ") : "version 1 (no block named)") + ", " + epochs + " epochs";
  }

  function formEncode(pairs) {
    if (typeof URLSearchParams === "function") return new URLSearchParams(pairs).toString();
    return pairs.map(function (pair) {
      return pair.map(function (s) {
        return encodeURIComponent(s).replace(/[!'()~]/g, function (c) {
          return "%" + c.charCodeAt(0).toString(16).toUpperCase();
        }).replace(/%20/g, "+");
      }).join("=");
    }).join("&");
  }

  function wordValue(v) {
    if (Array.isArray(v)) return v.map(wordValue).join(",") || "none";
    if (typeof v === "number") return isFinite(v) ? formatNumber(v) : String(v);
    if (v === null || v === undefined) return "none";
    return String(v);
  }

  function differsFromDefault(v, d) {
    if (Array.isArray(v) || Array.isArray(d)) {
      return !(Array.isArray(v) && Array.isArray(d) && deepEqual(v, d));
    }
    if (typeof v === "number" && typeof d === "number") return v !== d;
    return !deepEqual(v, d);
  }

  // A mapped value for one node: a ref read from its params (or its input and output types), else the literal.
  function mappedValue(v, params, entry) {
    if (!isRef(v)) return clone(v);
    var ref = parseRef(v);
    if (ref.scope === "param") return clone(get(params, ref.name));
    if (ref.scope === "in") {
      var t = entry ? get(entry.inputs, ref.port) : undefined;
      if (!t) return null;
      var found = fieldOf(t, ref.field, null);
      return found.ok ? found.value : null;
    }
    if (ref.scope === "self" && entry) {
      var keys = Object.keys(entry.outputs);
      var own = keys.length ? fieldOf(entry.outputs[keys[0]], ref.field, null) : {ok: false};
      return own.ok ? own.value : null;
    }
    return null;
  }

  function experimentWhy(canon, graph, blocks, prop, problems, C) {
    var why = [];
    var nodes = [];
    graph.byId.forEach(function (n) { nodes.push(n); });
    nodes.sort(function (a, b) { return cmpNodeIds(a.id, b.id); });
    function block(n) {
      return isStr(n.block) ? blocks.get(n.block) : undefined;
    }
    var errors = problems.filter(function (p) { return p.level === "error"; }).length;
    if (errors) why.push({code: "errors", text: "the pipeline has " + plural(errors, "error") + " to fix first"});
    var unmapped = nodes.filter(function (n) { return !isObj(get(block(n), "experiment")); });
    if (unmapped.length) {
      why.push({code: "not_mapped", text: "an experiment request cannot carry " +
        unique(unmapped.map(function (n) { return String(n.block); })).join(", ")});
    }
    function count(id) {
      return nodes.filter(function (n) { return n.block === id; }).length;
    }
    [[CATALOG, "catalog", "the frame catalog (catalog_v1)"], [CLASSIFIER, "classifier", "classifier"],
      [TRAINER, "train", "trainer (train_classifier)"]].forEach(function (need) {
      var k = count(need[0]);
      if (k !== 1) why.push({code: need[1], text: "the experiment route needs exactly one " + need[2] + "; this has " + k});
    });
    var seen = new Map();
    nodes.forEach(function (n) { seen.set(String(n.block), (seen.get(String(n.block)) || 0) + 1); });
    var twice = [];
    seen.forEach(function (k, id) { if (k > 1) twice.push(id); });
    if (twice.length) why.push({code: "duplicate", text: "a block is used twice: " + twice.sort(cmpStr).join(", ")});
    var reached = new Set(nodes.filter(function (n) { return n.block === CATALOG; }).map(function (n) { return n.id; }));
    var grew = true;
    while (grew) {
      grew = false;
      graph.edges.forEach(function (e) {
        if (reached.has(e.from) && !reached.has(e.to)) {
          reached.add(e.to);
          grew = true;
        }
      });
    }
    var cut = nodes.filter(function (n) { return !reached.has(n.id); });
    if (cut.length) {
      why.push({code: "unconnected", text: "not reached from the catalog: " + cut.map(function (n) { return n.id; }).join(", ")});
    }
    var outside = [], unplain = [];
    nodes.forEach(function (n) {
      var m = block(n);
      var E = get(m, "experiment");
      if (!isObj(E)) return;
      if (isObj(E.only)) {
        Object.keys(E.only).forEach(function (k) {
          var allowed = arrayOf(E.only[k]);
          var values = [get(n.params, k)].concat(has(n.vary, k) ? n.vary[k] : []);
          values.forEach(function (v) {
            if (!allowed.some(function (a) { return deepEqual(a, v); })) {
              outside.push(n.id + " " + k + " " + show(v) + " (the route takes " + allowed.map(show).join(", ") + ")");
            }
          });
        });
      }
      var slots = ["recipe", "epochs", "seed", "hours"].filter(function (k) { return has(E, k); }).map(function (k) { return E[k]; });
      if (isObj(E.blocks)) Object.keys(E.blocks).forEach(function (k) { slots.push(E.blocks[k]); });
      slots.forEach(function (slot) {
        var ref = parseRef(slot);
        if (ref && ref.scope === "param") {
          var p = paramNamed(m, ref.name);
          if (!p || p.kind !== "float") return;
          var values = has(n.vary, ref.name) ? n.vary[ref.name] : [get(n.params, ref.name)];
          values.forEach(function (v) {
            if (typeof v === "number" && !floatPlain(v)) unplain.push(n.id + " " + ref.name + " " + show(v));
          });
        } else if (typeof slot === "number" && !Number.isInteger(slot) && !floatPlain(slot)) {
          unplain.push(n.id + " " + show(slot));
        }
      });
    });
    if (outside.length) why.push({code: "only", text: "outside what the experiment route runs: " + unique(outside).join("; ")});
    if (unplain.length) {
      why.push({code: "float_plain", text: "a number the request would carry is not 0 or from 0.0001 with at most 6 decimals: " +
        unique(unplain).join("; ")});
    }
    var total = totalCombinations(prop);
    if (total > C.limits.combinations) {
      why.push({code: "too_many", text: "the pipeline varies into " + total + " runs; one request each, at most " +
        C.limits.combinations});
    }
    return why;
  }

  function buildRequests(graph, blocks, prop, X) {
    var nodes = [];
    graph.byId.forEach(function (n) { nodes.push(n); });
    nodes.sort(function (a, b) { return cmpNodeIds(a.id, b.id); });
    var dims = [];
    nodes.forEach(function (n) {
      Object.keys(n.vary).sort(cmpStr).forEach(function (k) { dims.push({node: n.id, param: k, values: n.vary[k]}); });
    });
    return product(dims).map(function (choice) {
      var paramsByNode = new Map();
      nodes.forEach(function (n) { paramsByNode.set(n.id, clone(n.params)); });
      var combination = dims.map(function (d, i) {
        put(paramsByNode.get(d.node), d.param, clone(choice[i]));
        return {node: d.node, param: d.param, value: clone(choice[i])};
      });
      var recipe = "none", epochs, seed, hours, mapped = {};
      nodes.forEach(function (n) {
        var E = get(blocks.get(n.block), "experiment");
        if (!isObj(E)) return;
        var params = paramsByNode.get(n.id), entry = get(prop.nodes, n.id);
        if (has(E, "recipe")) recipe = mappedValue(E.recipe, params, entry);
        if (has(E, "epochs")) epochs = mappedValue(E.epochs, params, entry);
        if (has(E, "seed")) seed = mappedValue(E.seed, params, entry);
        if (has(E, "hours")) hours = mappedValue(E.hours, params, entry);
        if (isObj(E.blocks)) Object.keys(E.blocks).forEach(function (k) { put(mapped, k, mappedValue(E.blocks[k], params, entry)); });
      });
      if (recipe === null || recipe === undefined || recipe === "") recipe = "none";
      if (epochs === undefined || epochs === null) epochs = FORM_DEFAULTS.epochs;
      if (seed === undefined || seed === null) seed = FORM_DEFAULTS.seed;
      if (!isNum(hours)) hours = FORM_DEFAULTS.hours;
      var blocksAll = {}, named = [];
      X.fields.forEach(function (f) {
        var d = get(X.defaults, f);
        if (has(mapped, f)) {
          put(blocksAll, f, clone(mapped[f]));
          if (differsFromDefault(mapped[f], d)) named.push(f + "=" + wordValue(mapped[f]));
        } else {
          put(blocksAll, f, clone(d));
        }
      });
      var epochsWord = typeof epochs === "number" ? formatNumber(epochs) : String(epochs);
      var seedWord = typeof seed === "number" ? formatNumber(seed) : String(seed);
      var hoursWord = pyG(hours);
      var recipeWord = String(recipe);
      var title = requestTitle(named, epochsWord);
      var body = issueBody(named, epochsWord, seedWord, hoursWord, recipeWord, X);
      var lines = body.split("\n");
      lines = lines.slice(1, lines.indexOf(""));
      return {
        recipe: recipeWord, epochs: epochs, seed: seed, hours: hours, hours_word: hoursWord, blocks: blocksAll,
        named: named, title: title, body: body,
        url: X.newUrl + "?" + formEncode([["title", title], ["labels", X.label], ["body", body]]),
        lines: lines, command: flowCommand(named, epochsWord, seedWord, hoursWord, recipeWord, X.flow),
        combination: combination
      };
    });
  }

  function pipelineIssue(name, hex, route, totals, text) {
    var gpu = totals.gpu, cpu = totals.cpu;
    var body = [PIPELINE_MARKER, "", "digest: " + hex, "route: " + route,
      "jobs: " + gpu.submissions + " GPU submission(s) (" + gpu.tasks + " tasks, " + formatNumber(gpu.hours) +
      " GPU-hours), " + cpu.submissions + " CPU submission(s)", "", "```json", text === null ? "" : text, "```", "",
      PIPELINE_CLOSING].join("\n") + "\n";
    return {title: "Pipeline: " + name + " (" + hex.slice(0, 12) + ")", body: body};
  }

  function compile(spec, data, prop) {
    var C = contractOf(data), blocks = blockMap(data), X = experimentOf(data);
    var canon = specOf(spec, data), graph = graphOf(canon);
    prop = isObj(prop) && Array.isArray(prop.order) ? prop : propagate(spec, data);
    var J = jobs(spec, data, prop);
    var problems = prop.problems.concat(J.problems);
    var text = null;
    try {
      text = canonical(canon);
    } catch (e) {
      text = null;
    }
    var hex = text === null ? "" : sha256(text);
    var why = experimentWhy(canon, graph, blocks, prop, problems, C);
    var route = why.length ? "pipeline" : "experiment";
    var requests = route === "experiment" ? buildRequests(graph, blocks, prop, X) : [];
    var plan = J.rows.map(function (r) {
      var m = blocks.get(r.block);
      return {node: r.node, block: r.block, "class": r["class"], submissions: r.submissions, tasks: r.tasks,
        hours: r.hours, rides_with: r.rides_with, stage: get(m, "stage"), today: clone(get(m, "today"))};
    });
    var totals = clone(J.totals);
    if (route === "experiment") {
      var sum = 0;
      requests.forEach(function (r) { sum += r.hours; });
      totals.gpu = {submissions: requests.length, tasks: requests.length, hours: pyRound(sum, 2)};
    }
    return {
      digest: hex, route: route, ready: route === "experiment", why: why, requests: requests, plan: plan,
      jobs: totals, pipeline_issue: pipelineIssue(canon.name, hex, route, totals, text), problems: problems
    };
  }

  // ------------------------------------------------------------------------------------------------
  // The manifest check (section 13): at most one problem per (code, field), its text naming every failure.

  function checkManifest(manifest, contract) {
    var C = norm(contract);
    var found = new ProblemList(true);
    function bad(code, field, text) {
      found.add({code: code, node: null, port: null, field: field, level: "error", text: text});
    }
    function result() {
      return found.list.map(function (p) { return {code: p.code, field: p.field, text: p.text}; });
    }
    if (!isObj(manifest)) {
      bad("field", null, "a block manifest is a JSON object");
      return result();
    }
    var M = manifest;
    checkIdentity(M, C, bad);
    var params = checkParams(M, C, bad);
    var inputNames = checkInputs(M, C, bad);
    checkOutputs(M, C, bad, params, inputNames);
    checkRules(M, bad, params);
    checkReads(M, C, bad);
    checkJob(M, C, bad, params);
    checkDeterminism(M, C, bad, params);
    var structural = found.list.some(function (p) {
      return ["port", "accepts", "op", "ref", "param"].indexOf(p.code) >= 0;
    });
    checkGeneric(M, C, bad, structural);
    if (has(M, "resolve") && M.resolve !== null && !isStr(M.resolve)) bad("field", "resolve", "resolve is null or a text");
    checkExperiment(M, C, bad, params, inputNames);
    checkNeeds(M, C, bad);
    checkCode(M, C, bad);
    checkToday(M, C, bad);
    checkText(M, C, bad);
    checkCard(M, bad);
    return result();
  }

  function textLength(v, low, high) {
    return isStr(v) && v.length >= low && v.length <= high;
  }

  function checkIdentity(M, C, bad) {
    if (M.block !== 1) bad("field", "block", "block is 1, the manifest format");
    if (!isStr(M.id) || !ID_RE.test(M.id)) {
      bad("id", "id", "id " + show(M.id) + " is not lowercase letters, digits and _, 2 to 40 long, starting with a letter");
    }
    if (!isInt(M.version) || M.version < 1) bad("field", "version", "version is a whole number from 1");
    if (!textLength(M.title, 1, 60)) bad("field", "title", "title is a text of 1 to 60 characters");
    if (C.stages.indexOf(M.stage) < 0) bad("field", "stage", "stage " + show(M.stage) + " is not one of " + C.stages.join(", "));
    if (!textLength(M.summary, 1, 120)) bad("field", "summary", "summary is one line of 1 to 120 characters");
    if (!textLength(M.does, 1, 800)) bad("field", "does", "does is a text of 1 to 800 characters");
    if (C.glyphs.indexOf(M.glyph) < 0) bad("field", "glyph", "glyph " + show(M.glyph) + " is not one of the contract's glyphs");
  }

  function checkParam(p, i, C, say) {
    var label = isStr(p.name) ? p.name : "param " + i;
    if (PARAM_KINDS.indexOf(p.kind) < 0) {
      say(label + " has kind " + show(p.kind) + ", not one of " + PARAM_KINDS.join(", "));
      return;
    }
    if (p.kind === "choice") {
      var choices = p.choices;
      if (!Array.isArray(choices) || !choices.length || unique(choices).length !== choices.length ||
          !choices.every(function (c) { return isStr(c) && VALUE_RE.test(c); })) {
        say(label + " needs choices: a non-empty list of distinct values of letters, digits and . _ , -");
        return;
      }
    } else if (p.kind === "int") {
      if (!isInt(p.low) || !isInt(p.high) || p.low > p.high) {
        say(label + " needs whole numbers low and high, low at most high");
        return;
      }
    } else if (p.kind === "float") {
      if (!isNum(p.low) || !isNum(p.high) || p.low > p.high) {
        say(label + " needs numbers low and high, low at most high");
        return;
      }
      if (has(p, "above") && typeof p.above !== "boolean") say(label + " has above that is not true or false");
    } else if (p.kind === "set") {
      var options = p.options;
      if (!Array.isArray(options) || !options.length || unique(options).length !== options.length ||
          !options.every(function (o) { return isStr(o) && VALUE_RE.test(o); })) {
        say(label + " needs options: a non-empty list of distinct values of letters, digits and . _ , -");
        return;
      }
    } else if (p.kind === "names") {
      if (has(p, "pattern") && (!isStr(p.pattern) || !fullRegex(p.pattern))) {
        say(label + " has a pattern that is not a regular expression");
        return;
      }
    }
    if (!has(p, "default")) {
      say(label + " has no default");
      return;
    }
    var why = valueProblem(p, p["default"]);
    if (why) say(label + " has a default that does not hold: " + why);
  }

  function checkParams(M, C, bad) {
    var names = new Set(), byName = new Map();
    function say(text) {
      bad("param", "params", text);
    }
    if (!Array.isArray(M.params)) {
      say("params is a list");
      return {names: names, byName: byName};
    }
    M.params.forEach(function (p, i) {
      if (!isObj(p)) {
        say("param " + i + " is not an object");
        return;
      }
      if (!isStr(p.name) || !PARAM_RE.test(p.name)) {
        say("param " + i + " has the name " + show(p.name) + ", not lowercase letters, digits and _ up to 32");
      } else if (names.has(p.name)) {
        say("two params are named " + p.name);
      } else {
        names.add(p.name);
        byName.set(p.name, p);
      }
      if (has(p, "vary") && typeof p.vary !== "boolean") say((isStr(p.name) ? p.name : "param " + i) + " has vary that is not true or false");
      if (has(p, "what") && !isStr(p.what)) say((isStr(p.name) ? p.name : "param " + i) + " has what that is not a text");
      checkParam(p, i, C, say);
    });
    return {names: names, byName: byName};
  }

  function checkPattern(pattern, label, C, say) {
    if (!isObj(pattern)) {
      say(label + " has no accepts pattern");
      return;
    }
    Object.keys(pattern).forEach(function (k) {
      if (PATTERN_KEYS.indexOf(k) < 0) say(label + " accepts an unknown key " + show(k));
    });
    function listOf(key, allowed) {
      if (!has(pattern, key)) return;
      var v = pattern[key];
      if (!Array.isArray(v) || !v.every(function (x) { return allowed.indexOf(x) >= 0; })) {
        say(label + " accepts " + key + " " + show(v) + ", not a list from " + allowed.join(", "));
      }
    }
    if (!Array.isArray(pattern.kind) || !pattern.kind.length) say(label + " accepts no kind; kind is a non-empty list");
    else listOf("kind", C.kinds);
    listOf("rank", [0, 1, 2, 3]);
    if (has(pattern, "time") && ["any", "yes", "no"].indexOf(pattern.time) < 0) say(label + " accepts time " + show(pattern.time) + ", not any, yes or no");
    listOf("has_axes", C.axes);
    listOf("dtype", C.dtypes);
    listOf("targets", C.targets);
    if (has(pattern, "parts") && ["split", "unsplit", "any"].indexOf(pattern.parts) < 0) {
      say(label + " accepts parts " + show(pattern.parts) + ", not split or unsplit");
    }
    listOf("needs_parts", C.parts);
    listOf("modality", C.modalities);
    if (has(pattern, "trained") && typeof pattern.trained !== "boolean") say(label + " accepts trained that is not true or false");
  }

  function checkInputs(M, C, bad) {
    var names = [];
    if (!Array.isArray(M.inputs)) {
      bad("port", "inputs", "inputs is a list");
      return names;
    }
    M.inputs.forEach(function (p, i) {
      if (!isObj(p)) {
        bad("port", "inputs", "input " + i + " is not an object");
        return;
      }
      var label = "input " + (isStr(p.name) ? p.name : i);
      if (!isStr(p.name) || !PORT_RE.test(p.name)) bad("port", "inputs", "input " + i + " has the name " + show(p.name) + ", not lowercase letters, digits and _ up to 24");
      else if (names.indexOf(p.name) >= 0) bad("port", "inputs", "two inputs are named " + p.name);
      else names.push(p.name);
      if (has(p, "optional") && typeof p.optional !== "boolean") bad("port", "inputs", label + " has optional that is not true or false");
      if (has(p, "what") && !isStr(p.what)) bad("port", "inputs", label + " has what that is not a text");
      checkPattern(p.accepts, label, C, function (text) { bad("accepts", "inputs", text); });
    });
    if (M.stage === "source" && M.inputs.length) bad("port", "inputs", "a source block has no input");
    if (M.stage !== "source" && !M.inputs.length) bad("port", "inputs", "a block that is not a source has at least one input");
    return names;
  }

  // Whether a ref names a param or port that exists: @param.NAME, @in.PORT.FIELD, @self.FIELD.
  function refProblem(v, params, inputNames, C) {
    var ref = parseRef(v);
    if (!ref || ref.scope === "bad") return show(v) + " is not @param.NAME, @in.PORT.FIELD or @self.FIELD";
    if (ref.scope === "param") return params.names.has(ref.name) ? null : show(v) + " names no param";
    if (ref.scope === "in" && inputNames.indexOf(ref.port) < 0) return show(v) + " names no input";
    var field = ref.field;
    var size = /^sizes\.(.+)$/.exec(field);
    if (size) return C.axes.indexOf(size[1]) >= 0 ? null : show(v) + " names no axis";
    return TYPE_FIELDS.indexOf(field) >= 0 ? null : show(v) + " names no field of a type";
  }

  function checkOp(op, label, C, params, inputNames, sayOp, sayRef) {
    if (!Array.isArray(op) || !isStr(op[0]) || !has(OP_ARITY, op[0])) {
      sayOp(label + " has an unknown op " + show(op));
      return;
    }
    var name = op[0];
    if (op.length !== OP_ARITY[name]) {
      sayOp(label + " has " + name + " with " + op.length + " items; it takes " + OP_ARITY[name]);
      return;
    }
    function slot(v, valid, what) {
      if (isRef(v)) {
        var why = refProblem(v, params, inputNames, C);
        if (why) sayRef(label + ": " + why);
      } else if (!valid(v)) {
        sayOp(label + " has " + name + " with " + show(v) + ", not " + what);
      }
    }
    function axis(v) {
      if (C.axes.indexOf(v) < 0) sayOp(label + " has " + name + " on " + show(v) + ", not an axis");
    }
    var licence = function (v) { return C.licences.indexOf(v) >= 0; };
    switch (name) {
      case "kind":
        slot(op[1], function (v) { return C.kinds.indexOf(v) >= 0; }, "a kind");
        break;
      case "set":
        if (SET_FIELDS.indexOf(op[1]) < 0) {
          sayOp(label + " sets " + show(op[1]) + ", not one of " + SET_FIELDS.join(", "));
          break;
        }
        slot(op[2], function (v) { return validSetValue(op[1], v, C); }, "a value " + op[1] + " can take");
        break;
      case "size":
        axis(op[1]);
        slot(op[2], validSize, "a whole number from 1 or null");
        break;
      case "axes":
        slot(op[1], function (v) { return validAxisList(v, C); }, "a list of distinct axes");
        break;
      case "drop_axis":
        axis(op[1]);
        break;
      case "add_axis":
        axis(op[1]);
        if (op[2] !== null && C.axes.indexOf(op[2]) < 0) sayOp(label + " has add_axis before " + show(op[2]) + ", not an axis or null");
        slot(op[3], validSize, "a whole number from 1 or null");
        break;
      case "parts":
        slot(op[1], function (v) { return validPartList(v, C); }, "a list of distinct parts");
        break;
      default:
        slot(op[1], licence, "a licence class");
    }
  }

  function checkOutputs(M, C, bad, params, inputNames) {
    if (!Array.isArray(M.outputs)) {
      bad("port", "outputs", "outputs is a list");
      return;
    }
    if (!M.outputs.length) bad("port", "outputs", "a block has at least one output");
    var names = [];
    M.outputs.forEach(function (o, i) {
      if (!isObj(o)) {
        bad("port", "outputs", "output " + i + " is not an object");
        return;
      }
      var label = "output " + (isStr(o.name) ? o.name : i);
      if (!isStr(o.name) || !PORT_RE.test(o.name)) bad("port", "outputs", "output " + i + " has the name " + show(o.name) + ", not lowercase letters, digits and _ up to 24");
      else if (names.indexOf(o.name) >= 0) bad("port", "outputs", "two outputs are named " + o.name);
      else names.push(o.name);
      if (has(o, "from") && o.from !== null && inputNames.indexOf(o.from) < 0) bad("port", "outputs", label + " is from " + show(o.from) + ", which is not an input");
      if (has(o, "what") && !isStr(o.what)) bad("port", "outputs", label + " has what that is not a text");
      if (!Array.isArray(o.ops)) {
        bad("op", "outputs", label + " has no ops list");
        return;
      }
      o.ops.forEach(function (op) {
        checkOp(op, label, C, params, inputNames, function (text) { bad("op", "outputs", text); },
          function (text) { bad("ref", "outputs", text); });
      });
    });
  }

  function checkCondition(cond, label, say) {
    if (!isObj(cond)) {
      say(label + " is not a condition object");
      return;
    }
    Object.keys(cond).forEach(function (k) {
      if (CONDITION_KEYS.indexOf(k) < 0) say(label + " has an unknown condition " + show(k));
    });
    ["in", "not_in"].forEach(function (k) {
      if (has(cond, k) && !Array.isArray(cond[k])) say(label + " has " + k + " that is not a list");
    });
    ["min", "max", "above", "below"].forEach(function (k) {
      if (has(cond, k) && !isNum(cond[k])) say(label + " has " + k + " that is not a number");
    });
    ["empty", "nonempty"].forEach(function (k) {
      if (has(cond, k) && cond[k] !== true) say(label + " has " + k + " that is not true");
    });
  }

  function checkRules(M, bad, params) {
    function say(text) {
      bad("rule", "rules", text);
    }
    if (!Array.isArray(M.rules)) {
      say("rules is a list");
      return;
    }
    M.rules.forEach(function (r, i) {
      var label = "rule " + i;
      if (!isObj(r)) {
        say(label + " is not an object");
        return;
      }
      ["when", "need"].forEach(function (side) {
        if (!isObj(r[side])) {
          say(label + " has no " + side + " object");
          return;
        }
        Object.keys(r[side]).forEach(function (k) {
          if (!params.names.has(k)) say(label + " " + side + " names " + show(k) + ", which is not a param");
          checkCondition(r[side][k], label + " " + side + " " + k, say);
        });
      });
      if (!isStr(r.say) || !r.say.length) say(label + " has no say");
    });
  }

  function checkReads(M, C, bad) {
    var parts = isObj(M.reads) ? M.reads.parts : undefined;
    if (!Array.isArray(parts) || !parts.every(function (p) { return C.parts.indexOf(p) >= 0; }) || unique(parts).length !== parts.length) {
      bad("reads", "reads", "reads.parts is a list of distinct parts from " + C.parts.join(", "));
      return;
    }
    if (parts.indexOf("test") >= 0 && M.stage !== "evaluate" && M.stage !== "report") {
      bad("reads", "reads", "only evaluate and report blocks read the test part");
    }
  }

  function numericParam(params, ref) {
    var parsed = parseRef(ref);
    if (!parsed || parsed.scope !== "param") return false;
    var p = params.byName.get(parsed.name);
    return Boolean(p) && (p.kind === "int" || p.kind === "float");
  }

  function checkJob(M, C, bad, params) {
    function say(text) {
      bad("job", "job", text);
    }
    if (!isObj(M.job)) {
      say("job is an object");
      return;
    }
    var J = M.job, none = J["class"] === "none";
    if (C.job_classes.indexOf(J["class"]) < 0) say("job class " + show(J["class"]) + " is not one of " + C.job_classes.join(", "));
    if (isNum(J.hours)) {
      if (none ? J.hours < 0 : J.hours <= 0) say("job hours is above 0");
    } else if (!numericParam(params, J.hours)) {
      say("job hours is a number above 0 or @param.NAME of an int or float param");
    }
    if (!isInt(J.cpus) || J.cpus < (none ? 0 : 1) || J.cpus > 64) say("job cpus is a whole number from 1 to 64");
    if (!isInt(J.memory_gb) || J.memory_gb < (none ? 0 : 1) || J.memory_gb > 512) say("job memory_gb is a whole number from 1 to 512");
    if (typeof J.with_upstream !== "boolean") say("job with_upstream is true or false");
    if (typeof J.array !== "boolean") say("job array is true or false");
  }

  function checkDeterminism(M, C, bad, params) {
    var d = M.deterministic;
    if (C.deterministic.indexOf(d) < 0) {
      bad("determinism", "deterministic", "deterministic " + show(d) + " is not one of " + C.deterministic.join(", "));
      return;
    }
    if (d === "seeded") {
      var p = isStr(M.seed_param) ? params.byName.get(M.seed_param) : undefined;
      if (!p || p.kind !== "int") bad("determinism", "seed_param", "a seeded block names its int seed param in seed_param");
    }
    if (d === "declared" && !(isStr(M.nondeterminism) && M.nondeterminism.length >= 20)) {
      bad("determinism", "nondeterminism", "a declared block says what varies and why it is tolerated, in 20 characters or more");
    }
  }

  function admits(port, kind) {
    return isObj(port) && isObj(port.accepts) && arrayOf(port.accepts.kind).indexOf(kind) >= 0;
  }

  function sameNumbers(a, b) {
    var x = unique(a).sort(), y = unique(b).sort();
    return deepEqual(x, y);
  }

  // R8's probes hold the shapes a block takes: rank, time, channels, sizes and dtype. What its data
  // must mean, the targets and whether it is split yet, the probe takes from the block's own first
  // input, so a block that reads masks, or splits data not yet split, can say so in its pattern.
  function probeFor(accepts, t) {
    if (!isObj(accepts)) return t;
    var targets = accepts.targets;
    if (Array.isArray(targets) && targets.length && targets.indexOf(t.targets) < 0) t.targets = clone(targets[0]);
    if (accepts.parts === "unsplit") t.parts = [];
    return t;
  }

  function checkGeneric(M, C, bad, structural) {
    function say(text) {
      bad("generic", "generic", text);
    }
    var inputs = arrayOf(M.inputs);
    var takes = inputs.some(function (p) { return admits(p, "data") || admits(p, "model"); });
    var G = M.generic;
    if (!takes) {
      if (G !== null && G !== undefined) say("generic is null for a block that takes no data and no model");
      return;
    }
    if (!isObj(G)) {
      say("generic is required: the block takes data or a model");
      return;
    }
    var valid = true;
    if (!Array.isArray(G.rank) || !G.rank.every(function (r) { return isInt(r) && r >= 0 && r <= 3; }) ||
        unique(G.rank).length !== G.rank.length) {
      say("generic.rank is a list of distinct ranks from 0 to 3");
      valid = false;
    }
    if (["any", "yes", "no"].indexOf(G.time) < 0) {
      say("generic.time is any, yes or no");
      valid = false;
    }
    if (G.channels !== "any" && !(Array.isArray(G.channels) && G.channels.length &&
        G.channels.every(function (c) { return isInt(c) && c >= 1; }) && unique(G.channels).length === G.channels.length)) {
      say("generic.channels is any or a list of distinct channel counts");
      valid = false;
    }
    if (G.sizes !== "any" && G.sizes !== "fixed") {
      say("generic.sizes is any or fixed");
      valid = false;
    }
    if (has(G, "why") && !isStr(G.why)) say("generic.why is a text");
    if (!valid) return;
    var everything = [1, 2, 3].every(function (r) { return G.rank.indexOf(r) >= 0; }) && G.channels === "any" && G.sizes === "any";
    if (!everything && !(isStr(G.why) && G.why.length >= 20)) {
      say("generic.why says, in 20 characters or more, what the code takes today and what would widen it");
    }
    inputs.forEach(function (p) {
      if (admits(p, "data") && has(p.accepts, "rank") && Array.isArray(p.accepts.rank) && !sameNumbers(p.accepts.rank, G.rank)) {
        say("the input " + show(p.name) + " accepts rank " + show(p.accepts.rank) + ", not generic.rank " + show(G.rank));
      }
    });
    if (structural || !admits(inputs[0], "data") || !isStr(inputs[0].name)) return;
    var first = inputs[0];
    var defaults = effectiveParams(null, M);
    C.probes.forEach(function (probe) {
      var t = probeFor(first.accepts, copyType(probe.type));
      var hasTime = t.axes.indexOf("T") >= 0;
      if (G.rank.indexOf(rankOf(t.axes, C)) < 0) return;
      if ((G.time === "yes" && !hasTime) || (G.time === "no" && hasTime)) return;
      var why = matches(first.accepts, t, C).map(function (q) { return q.text; });
      computeOutputs(M, new Map([[first.name, t]]), defaults, C, function (port, opName, text) {
        why.push("output " + port + ": " + text);
      });
      if (why.length) say("the probe " + show(probe.name) + " fails: " + why.join("; "));
    });
  }

  function checkExperiment(M, C, bad, params, inputNames) {
    if (!has(M, "experiment") || M.experiment === null) return;
    var E = M.experiment;
    if (!isObj(E)) {
      bad("field", "experiment", "experiment is null or an object");
      return;
    }
    Object.keys(E).forEach(function (k) {
      if (EXPERIMENT_KEYS.indexOf(k) < 0) bad("field", "experiment", "experiment has an unknown key " + show(k));
    });
    function ref(v, label) {
      if (!isRef(v)) return;
      var why = refProblem(v, params, inputNames, C);
      if (why) bad("ref", "experiment", "experiment " + label + ": " + why);
    }
    ["recipe", "epochs", "seed", "hours"].forEach(function (k) {
      if (has(E, k)) ref(E[k], k);
    });
    if (has(E, "blocks")) {
      if (!isObj(E.blocks)) bad("field", "experiment", "experiment.blocks is an object of Blocks fields");
      else Object.keys(E.blocks).forEach(function (k) { ref(E.blocks[k], "blocks." + k); });
    }
    if (has(E, "only")) {
      if (!isObj(E.only)) {
        bad("field", "experiment", "experiment.only is an object of params and their allowed values");
      } else {
        Object.keys(E.only).forEach(function (k) {
          if (!params.names.has(k)) bad("ref", "experiment", "experiment.only names " + show(k) + ", which is not a param");
          if (!Array.isArray(E.only[k]) || !E.only[k].length) bad("field", "experiment", "experiment.only." + k + " is a non-empty list");
        });
      }
    }
  }

  function checkNeeds(M, C, bad) {
    if (!Array.isArray(M.needs)) {
      bad("needs", "needs", "needs is a list");
      return;
    }
    var outside = M.needs.filter(function (x) { return C.needs.indexOf(x) < 0; });
    if (outside.length) bad("needs", "needs", "needs names " + outside.map(show).join(", ") + ", outside the contract's list");
    if (unique(M.needs).length !== M.needs.length) bad("needs", "needs", "needs names a library twice");
  }

  function checkCode(M, C, bad) {
    var code = M.code, list = M.implemented_by;
    if (C.code.indexOf(code) < 0) bad("code", "code", "code " + show(code) + " is not one of " + C.code.join(", "));
    if (!Array.isArray(list) || !list.every(function (p) { return isStr(p) && p.length > 0; })) {
      bad("code", "implemented_by", "implemented_by is a list of repository paths");
      return;
    }
    if (code === "existing" && !list.length) bad("code", "implemented_by", "existing code names the files that implement it");
    if (code === "own" && !(list.length === 1 && list[0] === "tools/sandbox/blocks/" + M.id + ".py")) {
      bad("code", "implemented_by", "a block of its own code is implemented by exactly tools/sandbox/blocks/" + M.id + ".py");
    }
    // Planned code is code not on this branch: nothing here runs it yet, or an unmerged pull
    // request builds it (pending, its note naming the pull request).
    if (code === "planned" && !(isObj(M.today) && (M.today.status === "planned" || M.today.status === "pending"))) {
      bad("code", "code", "planned code goes with today.status planned or pending");
    }
  }

  function checkToday(M, C, bad) {
    function say(text) {
      bad("today", "today", text);
    }
    var T = M.today;
    if (!isObj(T)) {
      say("today is an object");
      return;
    }
    if (C.today.indexOf(T.status) < 0) say("today.status " + show(T.status) + " is not one of " + C.today.join(", "));
    TODAY_STRINGS.forEach(function (k) {
      if (!isStr(T[k])) say("today." + k + " is a text, possibly empty");
    });
    if (T.status === "live" && !(T.route === "experiment" && isObj(M.experiment))) {
      say("a live block has today.route experiment and an experiment mapping");
    }
    if (T.status === "word" && !(isStr(T.word) && T.word.length)) say("a word block names its gate word");
    if (T.status === "flow" && !(isStr(T.flow) && T.flow.length)) say("a flow block names its flow");
    if (T.status === "pending" && !(isStr(T.note) && /#[0-9]+/.test(T.note))) say("a pending block's note names its pull request as #<number>");
    if (T.status === "planned" && M.code !== "planned" && M.code !== "own") say("a planned block has code planned or own");
  }

  function textProblems(v) {
    if (isStr(v)) return !printable(v);
    if (Array.isArray(v)) return v.some(textProblems);
    if (isObj(v)) return Object.keys(v).some(function (k) { return !printable(k) || textProblems(v[k]); });
    return false;
  }

  function checkText(M, C, bad) {
    var clean = true;
    Object.keys(M).forEach(function (k) {
      if (!printable(k)) {
        bad("text", null, "a key holds a character outside printable ASCII");
        clean = false;
      } else if (textProblems(M[k])) {
        bad("text", k, k + " holds a character outside printable ASCII");
        clean = false;
      }
    });
    if (!clean) return;
    var text;
    try {
      text = canonical(M);
    } catch (e) {
      bad("text", null, "the manifest cannot be written as canonical JSON: " + e.message);
      return;
    }
    if (text.length > C.limits.manifest_bytes) {
      bad("size", null, "the canonical manifest has " + text.length + " bytes; at most " + C.limits.manifest_bytes);
    }
  }

  function checkCard(M, bad) {
    var card = M.card;
    if (M.stage !== "source") {
      if (card !== null && card !== undefined) bad("card", "card", "card is null for a block that is not a source");
      return;
    }
    if (!isObj(card)) {
      bad("card", "card", "a source block has a data card");
      return;
    }
    CARD_FIELDS.forEach(function (k) {
      if (!(isStr(card[k]) && card[k].length)) bad("card", "card", "card." + k + " is a non-empty text");
    });
    if (!(Array.isArray(card.from) && card.from.length && card.from.every(function (p) { return isStr(p) && p.length > 0; }))) {
      bad("card", "card", "card.from lists the repository files its facts come from");
    }
  }

  // ------------------------------------------------------------------------------------------------
  // Prediction (section 14).

  function transitionStats(templates) {
    var counts = new Map();
    arrayOf(templates).forEach(function (tp) {
      if (!isObj(tp)) return;
      var blockOf = new Map();
      arrayOf(tp.nodes).forEach(function (n) {
        if (isObj(n) && isStr(n.id) && isStr(n.block) && !blockOf.has(n.id)) blockOf.set(n.id, n.block);
      });
      arrayOf(tp.edges).forEach(function (e) {
        if (!isObj(e)) return;
        var a = blockOf.get(e.from), b = blockOf.get(e.to);
        if (!a || !b) return;
        if (!counts.has(a)) counts.set(a, new Map());
        var row = counts.get(a);
        row.set(b, (row.get(b) || 0) + 1);
      });
    });
    var out = {};
    Array.from(counts.keys()).sort(cmpStr).forEach(function (a) {
      var row = {};
      Array.from(counts.get(a).keys()).sort(cmpStr).forEach(function (b) { put(row, b, counts.get(a).get(b)); });
      put(out, a, row);
    });
    return out;
  }

  function countOf(table, a, b) {
    var row = get(table, a);
    var n = get(row, b);
    return isNum(n) && n > 0 ? n : 0;
  }

  function rowTotal(table, a) {
    var row = get(table, a), total = 0;
    if (isObj(row)) Object.keys(row).forEach(function (b) { total += countOf(table, a, b); });
    return total;
  }

  // At most five blocks to grow to the right of the anchor, best first, ties by block id.
  function predict(spec, anchorId, data, stats, history) {
    var C = contractOf(data), blocks = blockMap(data), canon = specOf(spec, data);
    var prop = propagate(spec, data);
    var anchor = null;
    canon.nodes.forEach(function (n) { if (anchor === null && n.id === anchorId) anchor = n; });
    var am = anchor && isStr(anchor.block) ? blocks.get(anchor.block) : undefined;
    var entry = am ? get(prop.nodes, anchorId) : undefined;
    var firstOut = am ? portsOf(am, "outputs")[0] : undefined;
    var type = entry && firstOut ? get(entry.outputs, firstOut.name) : undefined;
    if (!type) return [];
    var present = new Set(), onBoard = new Set();
    canon.nodes.forEach(function (n) {
      var m = isStr(n.block) ? blocks.get(n.block) : undefined;
      if (m) present.add(m.stage);
      onBoard.add(n.block);
    });
    var candidates = [];
    blocks.forEach(function (m) {
      if (m.stage === "source" || m.id === am.id) return;
      if (portsOf(m, "inputs").some(function (p) { return accepts(p.accepts, type, C); })) candidates.push(m);
    });
    var A = stageIndex(C, am.stage);
    var candidateStages = new Set(candidates.map(function (m) { return stageIndex(C, m.stage); }));
    var next = -1;
    for (var s = A + 1; s < C.stages.length; s++) {
      if (!present.has(C.stages[s]) && candidateStages.has(s)) {
        next = s;
        break;
      }
    }
    var templateTotal = rowTotal(stats, am.id);
    var total = templateTotal + 2 * rowTotal(history, am.id);
    var scored = candidates.map(function (m) {
      var c = countOf(stats, am.id, m.id), h = countOf(history, am.id, m.id);
      var transition = 2 * (c + 2 * h) / (total + 1);
      var S = stageIndex(C, m.stage);
      var stage;
      if (S >= 0 && S === next) stage = 1;
      else if (S > A) stage = Math.max(0.3, 0.6 - 0.04 * Math.abs(S - (next >= 0 ? next : A)));
      else if (S === A && S >= 0) stage = 0.25;
      else stage = 0;
      var lack = S >= 0 && !present.has(m.stage) ? 0.5 : 0;
      var penalty = onBoard.has(m.id) && REPEATABLE.indexOf(m.stage) < 0 ? 2 : 0;
      var score = transition + stage + lack - penalty;
      var why;
      var title = isStr(m.title) ? m.title : m.id, anchorTitle = isStr(am.title) ? am.title : am.id;
      var stageWord = stageTitle(C, m.stage).toLowerCase();
      if (penalty > 0 && penalty >= Math.max(transition, stage, lack)) {
        why = title + " is already on the board";
      } else if (transition > 0 && transition >= stage && transition >= lack) {
        why = 2 * h >= c ? "after " + anchorTitle + ", your own pipelines went to " + title + " (" + plural(h, "time") + ")" :
          "after " + anchorTitle + ", the templates go to " + title + " (" + c + " of " + templateTotal + ")";
      } else if (lack) {
        why = "the pipeline has no " + stageWord + " step yet";
      } else if (S > A) {
        why = stageTitle(C, m.stage) + " comes after " + stageTitle(C, am.stage);
      } else if (S === A) {
        why = "another " + stageWord + " step";
      } else {
        why = stageTitle(C, m.stage) + " usually comes before " + stageTitle(C, am.stage);
      }
      return {block: m.id, score: Math.round(score * 1000) / 1000, why: why};
    });
    scored.sort(function (a, b) {
      if (a.score !== b.score) return a.score > b.score ? -1 : 1;
      return cmpStr(a.block, b.block);
    });
    return scored.slice(0, 5);
  }

  // ------------------------------------------------------------------------------------------------
  // The API (SPEC.md section 15), and the helpers the page and the tests use.

  SB.canonical = canonical;
  SB.sha256 = sha256;
  SB.specOf = specOf;
  SB.digest = digest;
  SB.effectiveParams = effectiveParams;
  SB.propagate = propagate;
  SB.jobs = jobs;
  SB.compile = compile;
  SB.checkManifest = checkManifest;
  SB.matches = matches;
  SB.transitionStats = transitionStats;
  SB.predict = predict;
  SB.typeSummary = typeSummary;
  SB.resolveText = resolveText;

  SB.emptyType = emptyType;
  SB.formatNumber = function (v) { return formatNumber(v, "the number"); };
  SB.hoursWord = pyG;
  SB.pyFixed = pyFixed;
  SB.pyRound = pyRound;
  SB.floatPlain = floatPlain;
  SB.valueProblem = valueProblem;
  SB.issueBody = function (named, epochs, seed, hours, recipe, data) {
    return issueBody(named, epochs, seed, hours, recipe, experimentOf(data));
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = SB;
  } else {
    window.SandboxEngine = SB;
  }
}());
