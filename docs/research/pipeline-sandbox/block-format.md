# Writing a block for the pipeline sandbox

Source: the thread "Build a deep learning pipeline sandbox", 2026-10-30, on the owner's words of 16:16 UTC, "make sure users can import their own blocks if it meets the same requirements you set". This page is the format those requirements check, for whoever writes a block; README.md in this folder says why the sandbox is built this way. The rules are code: tools/sandbox/engine.js (in the page) and tools/pipeline_sandbox.py (in the repository) apply them alike, and where this page and the code differ, the code is right and this page is wrong.

## 1. The files and the check

A block is a JSON manifest, tools/sandbox/blocks/<id>.json, whose file name is its id. A block whose code is its own adds that code as tools/sandbox/blocks/<id>.py, a module with a docstring and a top-level `def run(inputs, params, context)`, and its test as tests/test_sandbox_block_<id>.py. Check one with

    python3 tools/pipeline_sandbox.py check-block tools/sandbox/blocks/<id>.json

then run `python3 tools/pipeline_sandbox.py write`, since the page carries every block, and open a pull request with the page. The page's Import a block dialog runs the same manifest check in the browser, without the file checks, and keeps a block that passes in that browser only.

## 2. Identifiers

- A block id: 2 to 40 characters, lower-case letters, digits and underscores, starting with a letter (`^[a-z][a-z0-9_]{1,39}$`, the gate's word shape).
- A port name: `^[a-z][a-z0-9_]{0,23}$`. A param name: `^[a-z][a-z0-9_]{0,31}$`.
- A choice or set value, and every value that can reach an experiment request: `^[A-Za-z0-9][A-Za-z0-9._,-]{0,79}$`.
- Every string is ASCII with no control character (R12).

## 3. The type record

Every port carries a type record with all of these fields:

| Field | Values |
|---|---|
| kind | data, model, checkpoint, metrics, report |
| axes | the ordered axis names, from N (samples), T (time), C (channels), D, H, W (space), F (features), K (points), P (coordinates of a point); none for metrics and report |
| sizes | {axis: whole number from 1}, for the axes whose size is known |
| dtype | uint8, int16, int32, float16, float32, bool, or any |
| targets | none, level, mask, points, value |
| classes | a whole number from 1, or null |
| parts | the split parts present, in the order train, validation, test |
| persons | whether the person key rides along |
| modality | any, fluoro, radiograph, mixed, ct, drr, table |
| licence | commercial, commercial-share-alike, non-commercial, research-internal, uncut (from the least to the most restricted use) |
| sources | the ids of the source blocks upstream |
| family | the model family, or null |
| rank | how many of D, H and W are in the axes; computed, never set |
| trained | whether a checkpoint is trained |

A source block starts from the empty type: kind data, no axes, no sizes, dtype any, targets none, classes null, no parts, persons false, modality any, licence uncut, no sources, family null, rank 0, trained false. A model or a checkpoint keeps the axes, sizes, dtype, targets, classes, parts, persons, modality, licence and sources of the data it was built for, which is how a network adapts to its data.

## 4. The manifest

| Key | What it holds |
|---|---|
| block | 1, the format's version |
| id, version | the id (section 2) and a whole version from 1; a change that alters what the block does takes the next version |
| title, summary, does | 1 to 60 characters; one line of at most 120; at most 800 |
| stage | source, prepare, split, augment, model, train, calibrate, select, evaluate, analyse or report |
| glyph | one of the drawings the page has: catalog, ct, video, folder, synthetic, recipe, samples, normalise, denoise, crop, segment, render, realism, features, split, splitFamilies, augment, network, unet, prior, train, calibrate, select, evaluate, latency, gap, morphometry, naming, report, wandb, card, fallback |
| inputs | `[{"name", "accepts": pattern, "optional": bool, "what"}]`; none for a source, at least one otherwise |
| outputs | `[{"name", "from": an input's name or null, "ops": [op, ...], "what"}]`; at least one |
| params, rules | section 6 |
| reads | `{"parts": [...]}`: the split parts the block learns from or selects on; a transform applied sample by sample reads none; only evaluate and report blocks may read test |
| job | `{"class": none, cpu or gpu, "hours": a number above 0 or "@param.NAME", "with_upstream": bool, "array": bool, "cpus": 1 to 64, "memory_gb": 1 to 512}`; class none may give 0 for hours, cpus and memory |
| deterministic | exact, seeded (with `seed_param` naming an int param) or declared (with `nondeterminism` saying in at least 20 characters what varies and why that is tolerated) |
| generic | section 7; null only for a block whose inputs take neither data nor a model |
| resolve | null, or a sentence with `{field}` or `{sizes.X}` placeholders filled from the first output's type, as the classifier's "a {family} whose {rank}-D stem takes {sizes.C} channel(s) ..." |
| needs | libraries from: python, numpy, scipy, nibabel, torch, torchvision, monai, onnxruntime, jax, pymc, metaflow, wandb |
| code, implemented_by | existing (the repository files that do it), own (exactly ["tools/sandbox/blocks/<id>.py"]) or planned (no code on this branch) |
| today | `{"status", "route", "word", "flow", "note"}`: live (an experiment request carries it; route experiment), word (a gate word runs it; word names it), flow (a launched flow runs it in a fixed plan; flow names it), pending (built on an unmerged pull request; the note names it as #number) or planned (nothing runs it); planned code goes with planned or pending |
| experiment | null, or what the block puts in an experiment request: `recipe`, `epochs`, `seed`, `hours` as refs, `blocks` ({training block field: ref or value}) and `only` ({param: [allowed values]}); {} rides along at no cost |
| card | null, or for a source block the data card: origin, where, count, persons, split, held_out, licence (non-empty texts) and from (the repository files its facts come from) |

## 5. Patterns, ops and refs

A pattern says what an input accepts; `kind` is required and every other key is optional:

| Key | Holds when |
|---|---|
| kind | the type's kind is in the list |
| rank | the type's rank is in the list |
| time | yes: T is in the axes; no: T is not; any: either |
| has_axes | every listed axis is in the axes |
| dtype | the type's dtype is in the list, or is any |
| targets | the type's targets is in the list |
| parts | split: some part is present; unsplit: none is; any: either |
| needs_parts | every listed part is present |
| modality | the type's modality is in the list, or is any |
| trained | the type's trained equals it |

An output starts from a copy of the type on its `from` input (when connected), else the first connected input, else the empty type, and its ops run in order:

| Op | Does |
|---|---|
| `["kind", K]` | sets the kind |
| `["set", field, value]` | sets dtype, targets, classes, modality, family, trained or persons |
| `["size", axis, value]` | sets an axis's size; null removes it |
| `["axes", [axis, ...]]` | replaces the axes; the sizes of axes left out go |
| `["drop_axis", axis]` | removes an axis and its size |
| `["add_axis", axis, before, size]` | inserts an axis before another (at the end when before is null or absent); size may be null |
| `["parts", [part, ...]]` | sets the parts |
| `["licence", value]` | keeps the more restricted of the two |
| `["cut", value]` | keeps the less restricted of the two: a recipe can only narrow what is admitted |

A value is a literal or a ref: `@param.NAME` (the node's value of that param), `@in.PORT.FIELD` (a field of the type on an input, `sizes.X` allowed; null when the port is not connected) or `@self.FIELD` (the type being built). After the ops the rank is recomputed, sizes are pruned to the axes, and the lineage of every other connected input is merged in: sources united, the more restricted licence, persons only when both carry it. A source block adds its own id to sources.

## 6. Params and rules

| Kind | Fields |
|---|---|
| choice | `choices` (values of section 2), `default` among them |
| int | `low`, `high`, `default` in range |
| float | `low`, `high`, optional `above` (strictly above low), `default` in range; every value 0 or from 0.0001, with at most 6 decimals and never in exponent form |
| bool | `default` |
| set | `options`, `default` a list in option order with no repeat |
| names | `pattern` (default `^[a-z0-9_]{1,40}$`), `default` a list with no repeat |

Every param has `name`, `kind`, `vary` and `what`. `vary: true` lets a node sweep the param over several values: each value is one arm, the arms fan out downstream until a select block joins them, and a pipeline holds at most 64 arms in all.

A rule is `{"when": {param: condition}, "need": {param: condition}, "say": "..."}` and fails when every `when` holds and some `need` does not. A condition holds any of `in`, `not_in` (lists), `min`, `max` (inclusive), `above`, `below` (strict), `empty` and `nonempty`. An if-and-only-if is two rules.

## 7. Genericity and the probes

`generic` is `{"rank": [0 to 3, ...], "time": any, yes or no, "channels": "any" or [counts], "sizes": "any" or "fixed", "why": "..."}`. `why` is needed, at least 20 characters saying what the code does today and what would widen it, whenever the block takes less than every rank from 1 to 3, every channel count and every size. Each data input that names a rank names this one.

The claim is tested. A block whose first input admits data is given each of the contract's probes of a rank it claims and a time axis it takes: frames, 2-D grey 64 (N, C, H, W; 1 x 64 x 64; uint8), frames, 2-D colour 224 (3 x 224 x 224; float32), volumes, 3-D grey 96 (N, C, D, H, W; 1 x 96 x 96 x 96; int16), clips, 2-D grey (N, T, C, H, W; 16 frames of 1 x 64 x 64; uint8) and a table (N, F; 32 features; float32). Each probe takes the targets the input asks for and, for an input that asks for unsplit data, no parts; the block must accept it and compute every output with no problem (R8).

## 8. The requirements, R1 to R13

R1 identity, R2 ports, R3 params, R4 rules, R5 reads, R6 job, R7 determinism, R8 genericity, R9 needs, R10 code, R11 today, R12 text (ASCII, no control character, the canonical manifest at most 16,384 bytes) and R13 the data card. contract.json says each in a sentence, which the page shows beside the import dialog, and a failure names the requirement's code and the manifest key it sits under.

## 9. An example

A preprocessing block with its own code, which passes the manifest check of both engines and, until its two files are written, fails `check-block` naming them:

    {
     "block": 1, "id": "clahe", "version": 1,
     "title": "Contrast-limited equalisation", "stage": "prepare", "glyph": "normalise",
     "summary": "Equalises each image's histogram in tiles, so faint bone edges stand out.",
     "does": "Contrast-limited adaptive histogram equalisation of each 2-D image, or of each slice of a volume or frame of a clip: tiles of tile by tile pixels, each tile's histogram clipped at clip_limit before it is spread. It keeps every axis and size and writes float32 in 0 to 1.",
     "inputs": [{"name": "data", "accepts": {"kind": ["data"], "rank": [2, 3], "time": "any", "has_axes": ["C"]},
                 "optional": false, "what": "images, clips or volumes with a channel axis"}],
     "outputs": [{"name": "data", "from": "data", "ops": [["set", "dtype", "float32"]],
                  "what": "the same data, equalised, as float32 in 0 to 1"}],
     "params": [
      {"name": "clip_limit", "kind": "float", "low": 0.001, "high": 1, "default": 0.01, "vary": true,
       "what": "the clip of a tile's histogram, as a share of its pixels"},
      {"name": "tile", "kind": "int", "low": 4, "high": 256, "default": 32, "vary": true, "what": "a tile's side in pixels"}],
     "rules": [{"when": {"tile": {"min": 129}}, "need": {"clip_limit": {"max": 0.1}},
                "say": "a tile over 128 pixels takes a clip of at most 0.1"}],
     "reads": {"parts": []},
     "job": {"class": "cpu", "hours": 1, "with_upstream": false, "array": false, "cpus": 4, "memory_gb": 16},
     "deterministic": "exact", "seed_param": "", "nondeterminism": "",
     "generic": {"rank": [2, 3], "time": "any", "channels": "any", "sizes": "any",
                 "why": "It equalises 2-D planes, slice by slice in a volume and frame by frame in a clip; a table or a signal has no tiles, so ranks 0 and 1 are left out."},
     "resolve": null, "needs": ["python", "numpy"],
     "code": "own", "implemented_by": ["tools/sandbox/blocks/clahe.py"],
     "today": {"status": "planned", "route": "", "word": "", "flow": "", "note": "a block of its own; it runs once the pipeline route exists"},
     "experiment": null, "card": null
    }

## 10. What the code entry receives

The check holds only the name and the arguments of `run(inputs, params, context)`; what each holds is settled with the PipelineFlow of README.md, section 8, which is not built. The plan is that `inputs` maps each input port to the folder its upstream step wrote, `params` holds the node's values with the defaults filled, and `context` gives the pipeline's digest, the node's id, the seed, the arm's values and the folder to write to, so that a block reads and writes only through what it is handed and its output carries the digest and the lineage.
