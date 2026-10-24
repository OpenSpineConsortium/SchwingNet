"""Draw chapter 35's three figures of the data holding, and the power arithmetic behind the third.

Source: issue #219, the owner's ask of 2026-10-24 for a chapter on how the workflow is built "with
interactive figures which plot the amount of each data type, where it is along the spine, and
power calculations for each type of detection/classification".

The inputs are committed files only: the dataset records under data/sources/, the registry under
data/registry/, the licence classes in data/licences.json, and the hand-written judgments of
docs/textbook/figures/35/corpora-overlay.json (each corpus's data type, the stretch of the spine it
shows, the persons and images read from its record, whether it was tried, and the holdings each
power task is set beside). A number in the overlay that its record does not carry, in its counts or
in its words, is refused unless the overlay's own note gives it or the parts it sums, so the
figures draw no number that has no source.

    python3 tools/data_figures.py write     # corpora.json, three .html, three .svg, three .json
    python3 tools/data_figures.py check     # exit 1 when a written file is not what the inputs give

The power arithmetic is pure and tested (tests/test_data_figures.py); the calculator page carries a
JavaScript twin of the same formulas:

- precision: the smallest n whose 95 percent Wilson interval at the expected proportion p has a
  half-width at most the margin;
- bound: the smallest n at which a Wilson lower bound at least the target is reached with the
  stated power, when the true proportion is p (exact binomial; with p = 1 it is n / (n + z^2));
- compare: the standard two-proportion sample size per arm,
  n = (z_a sqrt(2 pbar qbar) + z_b sqrt(p1 q1 + p2 q2))^2 / (p1 - p2)^2, with pbar the mean of the two.

Each n counts independent units; frames or bodies clustered in persons inflate it by the design
effect DE = 1 + (m - 1) ICC, and the persons needed are ceil(n x DE / m) for m units scored per
person.
"""

import argparse
import glob
import json
import math
import re
import sys
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "textbook" / "figures" / "35"
OVERLAY = OUT / "corpora-overlay.json"
COMMAND = "python3 tools/data_figures.py write"
AXIS = [f"C{i}" for i in range(1, 8)] + [f"T{i}" for i in range(1, 13)] + [f"L{i}" for i in range(1, 6)] + ["S1", "Co"]
TYPE_ORDER = ["paired", "annotated", "synthetic", "ct", "unannotated"]
TYPE_WORDS = {
    "paired": "paired 3D-2D",
    "annotated": "annotated 2D",
    "synthetic": "synthetic 2D",
    "ct": "CT volumes",
    "unannotated": "unannotated 2D",
}
REACH_WORDS = {"held": "held", "get": "to get", "gated": "gated", "embargoed": "embargoed", "none": "does not exist", "excluded": "excluded"}
MAX_N = 10000


# ---------------------------------------------------------------- the power arithmetic


def z_of(alpha: float) -> float:
    """The two-sided normal quantile for a significance level alpha."""
    return NormalDist().inv_cdf(1 - alpha / 2)


def wilson(x: float, n: int, z: float) -> tuple[float, float]:
    """The Wilson score interval of x successes in n trials."""
    p = x / n
    scale = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / scale
    half = z / scale * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return centre - half, centre + half


def precision_n(p: float, margin: float, alpha: float = 0.05) -> int | None:
    """The smallest n whose Wilson interval at p has a half-width at most margin."""
    z = z_of(alpha)
    for n in range(1, MAX_N + 1):
        low, high = wilson(p * n, n, z)
        if (high - low) / 2 <= margin + 1e-12:
            return n
    return None


def _log_choose(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def tail(n: int, x: int, p: float) -> float:
    """The probability of at least x successes in n trials at success rate p."""
    if x <= 0:
        return 1.0
    if x > n:
        return 0.0
    if p >= 1:
        return 1.0
    if p <= 0:
        return 0.0
    lp, lq = math.log(p), math.log(1 - p)
    return min(1.0, sum(math.exp(_log_choose(n, k) + k * lp + (n - k) * lq) for k in range(x, n + 1)))


def fewest_successes(n: int, target: float, z: float) -> int | None:
    """The fewest successes in n trials whose Wilson lower bound is at least target."""
    low, high = 0, n
    if wilson(n, n, z)[0] < target:
        return None
    while low < high:
        mid = (low + high) // 2
        if wilson(mid, n, z)[0] >= target:
            high = mid
        else:
            low = mid + 1
    return low


def bound_n(p: float, target: float, alpha: float = 0.05, power: float = 0.8) -> int | None:
    """The smallest n at which a Wilson lower bound of at least target is reached with the given
    power when the true proportion is p; None when no n up to MAX_N reaches it."""
    if p <= target:
        return None
    z = z_of(alpha)
    for n in range(1, MAX_N + 1):
        x = fewest_successes(n, target, z)
        if x is not None and tail(n, x, p) >= power:
            return n
    return None


def compare_n(p1: float, p2: float, alpha: float = 0.05, power: float = 0.8) -> int | None:
    """The standard two-proportion sample size per arm, two-sided, with no continuity correction."""
    if p1 == p2:
        return None
    za, zb = z_of(alpha), NormalDist().inv_cdf(power)
    pbar = (p1 + p2) / 2
    root = za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return math.ceil(root * root / (p1 - p2) ** 2)


def persons_needed(n: int, design_effect: float, per_person: float) -> int:
    """Independent units turned into persons: n inflated by the design effect, m units a person."""
    return math.ceil(n * design_effect / per_person - 1e-9)


def needed(settings: dict) -> dict:
    """The n and the persons a task's settings ask for, in the calculator's three modes."""
    mode = settings["mode"]
    if mode == "precision":
        n = precision_n(settings["p"], settings["margin"], settings["alpha"])
    elif mode == "bound":
        n = bound_n(settings["p"], settings["target"], settings["alpha"], settings["power"])
    else:
        n = compare_n(settings["p"], settings["p2"], settings["alpha"], settings["power"])
    persons = None if n is None else persons_needed(n, settings["de"], settings["m"])
    if persons is not None and mode == "compare":
        persons *= 2
    return {"n": n, "persons": persons}


# ---------------------------------------------------------------- the table of corpora


def span_levels(span: str | None) -> list[str]:
    """The axis positions a span such as 'C1-C7,L1-S1' covers, in axis order."""
    if not span:
        return []
    covered = set()
    for part in span.split(","):
        first, last = part.split("-")
        covered.update(AXIS[AXIS.index(first): AXIS.index(last) + 1])
    return [level for level in AXIS if level in covered]


def numbers_in(text: str) -> set[int]:
    """The whole numbers a text writes in digits, and one where it says one."""
    found = {int(m.replace(",", "")) for m in re.findall(r"(?<![A-Za-z0-9])\d[\d,]*", text)}
    return found | ({1} if re.search(r"\bone\b", text) else set())


def allowed_numbers(record: dict, entry: dict) -> set[int]:
    """Every number the record carries, and every number or sum of numbers the overlay's notes give."""
    found = set()
    for value in record.get("counts", {}).values():
        if isinstance(value, (int, float)) and float(value).is_integer():
            found.add(int(value))
    for key in ("what", "status", "level_truth", "notes"):
        found |= numbers_in(str(record.get(key, "")))
    for key in ("images_unit", "persons_note", "images_from"):
        listed = sorted(numbers_in(str(entry.get(key, ""))))
        found |= set(listed)
        if len(listed) > 1:
            found.add(sum(listed))
            found.add(sum(listed) - max(listed))
            found.add(math.prod(listed[:2]))
    return found


def licence_of(source: str, licences: dict) -> str:
    entries, aliases = licences["sources"], licences["aliases"]
    entry = entries.get(source) or entries.get(aliases.get(source, ""), {})
    return entry.get("class", "unknown")


def read_inputs() -> tuple[dict, dict, dict, dict]:
    records = {}
    for path in sorted(glob.glob(str(ROOT / "data" / "sources" / "*.json"))):
        record = json.loads(Path(path).read_text())
        records[record["id"]] = record
    registry = {}
    for path in sorted(glob.glob(str(ROOT / "data" / "registry" / "*.json"))):
        entry = json.loads(Path(path).read_text())
        registry[entry["source"]] = entry
    licences = json.loads((ROOT / "data" / "licences.json").read_text())
    overlay = json.loads(OVERLAY.read_text())
    return records, registry, licences, overlay


def corpus_row(source: str, entry: dict, records: dict, registry: dict, licences: dict) -> dict:
    record = records.get(source)
    if record is None and source not in registry:
        raise SystemExit(f"{source}: in the overlay but neither a record nor a registry entry")
    record = record or {"name": source, "reach": entry.get("reach", "get"), "group": registry[source]["modality"]}
    allowed = allowed_numbers(record, entry)
    if source in registry:
        allowed |= numbers_in(registry[source].get("notes", ""))
    if source == "isbi2015_cephalograms":
        allowed |= allowed_numbers(records["aariz_cephalograms"], entry)
    for key in ("persons", "images"):
        value = entry.get(key)
        if value is not None and value not in allowed:
            raise SystemExit(f"{source}: {key} {value} is in neither its record nor the overlay's note")
    reach = entry.get("reach") or record["reach"]
    sources = [f"data/sources/{source}.json"] if source in records else []
    if source in registry:
        sources.append(f"data/registry/{source}.json")
    sources.append("docs/textbook/figures/35/corpora-overlay.json")
    return {
        "id": source,
        "name": record.get("name", source),
        "type": entry["type"],
        "reach": reach,
        "licence": licence_of(source, licences),
        "persons": entry.get("persons"),
        "persons_note": entry.get("persons_note", ""),
        "images": entry.get("images"),
        "images_unit": entry.get("images_unit", ""),
        "levels": span_levels(entry.get("span")),
        "span_basis": entry.get("basis", "unknown"),
        "human": entry.get("human", True),
        "aggregate": entry.get("aggregate", False),
        "tried": entry["tried"],
        "status": status_of(reach, entry["tried"]),
        "why": entry.get("why", ""),
        "sources": sources,
    }


def status_of(reach: str, tried: str) -> str:
    """Tried, can be tried with what is held, will be tried once obtained, or not on the way."""
    if tried == "yes":
        return "tried"
    if reach == "held":
        return "can be tried"
    if reach in ("get", "gated", "embargoed"):
        return "will be tried once obtained"
    return "not on the way"


def build_table() -> dict:
    records, registry, licences, overlay = read_inputs()
    missing = set(records) - set(overlay["corpora"])
    if missing:
        raise SystemExit("records with no line in the overlay: " + ", ".join(sorted(missing)))
    rows = [corpus_row(s, e, records, registry, licences) for s, e in overlay["corpora"].items()]
    rows.sort(key=lambda r: (TYPE_ORDER.index(r["type"]), r["name"].lower()))
    tasks = {}
    for key, task in overlay["tasks"].items():
        result = needed(task["defaults"])
        tasks[key] = dict(task, needed_at_defaults=result)
    return {
        "about": "Built by tools/data_figures.py from data/sources/, data/registry/, data/licences.json and corpora-overlay.json; edit those, then run " + COMMAND + ".",
        "axis": AXIS,
        "types": overlay["types"],
        "corpora": rows,
        "tasks": tasks,
    }


# ---------------------------------------------------------------- the pages and the pictures


STYLE = """
:root{color-scheme:light;--bg:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--ink3:#8a8984;--rule:#e4e3df;
--t-paired:#2a78d6;--t-annotated:#eb6834;--t-synthetic:#1baf7a;--t-ct:#eda100;--t-unannotated:#e87ba4;--need:#e34948}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){color-scheme:dark;--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;
--ink3:#8f8e87;--rule:#34332f;--t-paired:#3987e5;--t-annotated:#d95926;--t-synthetic:#199e70;--t-ct:#c98500;--t-unannotated:#d55181;--need:#e66767}}
:root[data-theme=dark]{color-scheme:dark;--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--ink3:#8f8e87;--rule:#34332f;
--t-paired:#3987e5;--t-annotated:#d95926;--t-synthetic:#199e70;--t-ct:#c98500;--t-unannotated:#d55181;--need:#e66767}
"""

LIGHT = {"bg": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "ink3": "#8a8984", "rule": "#e4e3df", "need": "#e34948",
         "paired": "#2a78d6", "annotated": "#eb6834", "synthetic": "#1baf7a", "ct": "#eda100", "unannotated": "#e87ba4"}
DARK = {"bg": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "ink3": "#8f8e87", "rule": "#34332f", "need": "#e66767",
        "paired": "#3987e5", "annotated": "#d95926", "synthetic": "#199e70", "ct": "#c98500", "unannotated": "#d55181"}


def svg_rules(c: dict) -> str:
    """The static figures' colours as plain class rules, which every SVG renderer reads."""
    types = "".join(f".t-{t}{{fill:{c[t]}}}.o-{t}{{stroke:{c[t]}}}" for t in TYPE_ORDER)
    return (f".bg{{fill:{c['bg']}}}text{{fill:{c['ink2']};font:11px system-ui,sans-serif}}.head{{fill:{c['ink']};font-weight:600}}"
            f".rule{{stroke:{c['rule']}}}.ink3{{fill:{c['ink3']}}}.need-line{{stroke:{c['need']}}}text.need-text{{fill:{c['need']}}}{types}")


SVG_STYLE = svg_rules(LIGHT) + "@media (prefers-color-scheme:dark){" + svg_rules(DARK) + "}"

PAGE_CSS = """
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}h1{font-size:18px;margin:0 0 4px}p.sub{color:var(--ink2);margin:0 0 12px}
.controls{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;margin:8px 0 12px;color:var(--ink2)}
.controls label{display:inline-flex;gap:4px;align-items:center}button.chip{border:1px solid var(--rule);background:transparent;color:var(--ink);
border-radius:12px;padding:2px 10px;cursor:pointer;font:inherit}button.chip[aria-pressed=true]{background:var(--ink);color:var(--bg)}
select,input{font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--rule);border-radius:4px;padding:2px 4px}
input[type=number]{width:5.5em}.legend{display:flex;flex-wrap:wrap;gap:10px;color:var(--ink2);margin:4px 0 8px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.tip{position:fixed;pointer-events:none;background:var(--bg);color:var(--ink);border:1px solid var(--rule);border-radius:6px;
padding:6px 8px;font-size:12px;max-width:340px;box-shadow:0 2px 8px rgba(0,0,0,.15);display:none;z-index:5}
.note{color:var(--ink2);font-size:12px}table{border-collapse:collapse;font-size:12px}td,th{padding:2px 6px;border-bottom:1px solid var(--rule);text-align:left}
th{color:var(--ink2);font-weight:600}.num{text-align:right;font-variant-numeric:tabular-nums}svg text{fill:var(--ink2)}
.wrap{overflow-x:auto}
"""


def short_name(name: str) -> str:
    """A corpus's name cut to fit a figure's margin: no backticks, no parenthesis, 34 characters."""
    name = name.replace("`", "")
    if " (" in name and name.index(" (") > 3:
        name = name[: name.index(" (")]
    return name if len(name) <= 34 else name[:33].rstrip() + "..."


def esc(text: object) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def page(title: str, subtitle: str, body: str, data: dict, script: str) -> str:
    blob = json.dumps(data, sort_keys=True).replace("</", "<\\/")
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{esc(title)}</title><style>{STYLE}{PAGE_CSS}</style></head><body><main>"
        f"<h1>{esc(title)}</h1><p class=\"sub\">{esc(subtitle)}</p>{body}"
        "<div class=\"tip\" id=\"tip\"></div></main>"
        f"<script>const DATA={blob};\n{COMMON_JS}\n{script}</script></body></html>\n"
    )


COMMON_JS = r"""
const TYPES=["paired","annotated","synthetic","ct","unannotated"];
const TW={paired:"paired 3D-2D",annotated:"annotated 2D",synthetic:"synthetic 2D",ct:"CT volumes",unannotated:"unannotated 2D"};
const RW={held:"held",get:"to get",gated:"gated",embargoed:"embargoed",none:"does not exist",excluded:"excluded"};
const fmt=v=>v==null?"not recorded":Number(v).toLocaleString("en-US");
const tip=document.getElementById("tip");
function showTip(e,html){tip.innerHTML=html;tip.style.display="block";const w=tip.offsetWidth,h=tip.offsetHeight;
let x=e.clientX+14,y=e.clientY+14;if(x+w>innerWidth-8)x=e.clientX-w-14;if(y+h>innerHeight-8)y=e.clientY-h-14;tip.style.left=x+"px";tip.style.top=y+"px"}
function hideTip(){tip.style.display="none"}
function sn(n){n=n.replace(/`/g,"");const i=n.indexOf(" (");if(i>3)n=n.slice(0,i);return n.length>34?n.slice(0,33)+"...":n}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function rowTip(r){return `<b>${esc(r.name)}</b><br>${TW[r.type]}; ${RW[r.reach]||r.reach}; licence class ${esc(r.licence)}<br>`+
`persons ${fmt(r.persons)}${r.persons_note?" ("+esc(r.persons_note)+")":""}<br>images ${fmt(r.images)} ${esc(r.images_unit)}<br>`+
`spine ${r.levels.length?r.levels[0]+" to "+r.levels[r.levels.length-1]+" ("+r.span_basis+")":"not along the spine or not recorded"}<br>`+
`${esc(r.status)}: ${esc(r.why)}<br><span class="note">${esc(r.sources[0])}</span>`}
function chips(id,values,words,on,cb){const box=document.getElementById(id);values.forEach(v=>{const b=document.createElement("button");
b.className="chip";b.textContent=words[v]||v;b.setAttribute("aria-pressed",on.has(v));b.onclick=()=>{on.has(v)?on.delete(v):on.add(v);
b.setAttribute("aria-pressed",on.has(v));cb()};box.appendChild(b)})}
const NS="http://www.w3.org/2000/svg";function el(n,a,p){const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e}
"""


AMOUNT_BODY = """
<div class="controls"><span>Measure</span><span id="measure"></span><span>Reach</span><span id="reach"></span>
<label>Licence class <select id="licence"><option value="">all</option></select></label>
<label><input type="checkbox" id="aggr"> show sub-sets and umbrellas</label></div>
<div class="controls"><span>Type</span><span id="types"></span></div>
<div class="legend" id="legend"></div><div id="tiles" class="legend"></div><div class="wrap"><svg id="chart" width="100%"></svg></div>
<p class="note" id="none"></p>
<p class="note">Bars are on a logarithmic axis, since the corpora run from one phantom to hundreds of thousands of images. Images count what each record counts (films, frames, projections, clips, CT volumes); the unit is in each bar's tooltip. Sub-sets (the two COBRA vendors) and the anomaly-harvest umbrella are left out of the sums. Source: <code>python3 tools/data_figures.py write</code> over data/sources/, data/registry/, data/licences.json and corpora-overlay.json.</p>
"""

AMOUNT_JS = r"""
const S={measure:"persons",reach:new Set(["held","get","gated","embargoed"]),types:new Set(TYPES),licence:"",aggr:false};
const mb=document.getElementById("measure");["persons","images"].forEach(m=>{const b=document.createElement("button");b.className="chip";b.textContent=m;
b.setAttribute("aria-pressed",S.measure===m);b.onclick=()=>{S.measure=m;mb.querySelectorAll("button").forEach(x=>x.setAttribute("aria-pressed",x===b));draw()};mb.appendChild(b)});
chips("reach",["held","get","gated","embargoed","none","excluded"],RW,S.reach,draw);
chips("types",TYPES,TW,S.types,draw);
const ls=document.getElementById("licence");[...new Set(DATA.corpora.map(r=>r.licence))].sort().forEach(c=>{const o=document.createElement("option");o.value=c;o.textContent=c;ls.appendChild(o)});
ls.onchange=()=>{S.licence=ls.value;draw()};document.getElementById("aggr").onchange=e=>{S.aggr=e.target.checked;draw()};
document.getElementById("legend").innerHTML=TYPES.map(t=>`<span><i style="background:var(--t-${t})"></i>${TW[t]}</span>`).join("");
function draw(){const rows=DATA.corpora.filter(r=>S.reach.has(r.reach)&&S.types.has(r.type)&&(!S.licence||r.licence===S.licence)&&(S.aggr||!r.aggregate));
const withV=rows.filter(r=>r[S.measure]!=null).sort((a,b)=>b[S.measure]-a[S.measure]);
document.getElementById("none").textContent=(rows.length-withV.length)+" of the "+rows.length+" corpora shown record no count of "+S.measure+": "+rows.filter(r=>r[S.measure]==null).map(r=>r.name).join("; ");
document.getElementById("tiles").innerHTML=TYPES.filter(t=>S.types.has(t)).map(t=>{const rs=withV.filter(r=>r.type===t&&!r.aggregate);
return `<span><i style="background:var(--t-${t})"></i>${TW[t]}: <b>${fmt(rs.reduce((s,r)=>s+r[S.measure],0))}</b> ${S.measure} in ${rs.length} corpora</span>`}).join("");
const svg=document.getElementById("chart");svg.innerHTML="";const W=Math.max(svg.clientWidth||900,560),L=230,R=70,rowH=16,top=24;
const H=top+withV.length*rowH+10;svg.setAttribute("height",H);svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
const max=Math.max(10,...withV.map(r=>r[S.measure])),lmax=Math.ceil(Math.log10(max));const x=v=>L+(W-L-R)*Math.log10(Math.max(v,1))/lmax;
for(let k=0;k<=lmax;k++){el("line",{x1:x(10**k),x2:x(10**k),y1:top-4,y2:H-6,stroke:"var(--rule)"},svg);
const t=el("text",{x:x(10**k),y:top-10,"text-anchor":"middle","font-size":11},svg);t.textContent=fmt(10**k)}
withV.forEach((r,i)=>{const y=top+i*rowH;const t=el("text",{x:L-6,y:y+11,"text-anchor":"end","font-size":11},svg);t.textContent=sn(r.name);
const w=Math.max(2,x(r[S.measure])-L);const b=el("rect",{x:L,y:y+2,width:w,height:rowH-4,rx:2,fill:`var(--t-${r.type})`,opacity:r.reach==="held"?1:0.45},svg);
const v=el("text",{x:L+w+4,y:y+11,"font-size":11},svg);v.textContent=fmt(r[S.measure]);
const hit=el("rect",{x:0,y:y,width:W,height:rowH,fill:"transparent"},svg);hit.onmousemove=e=>showTip(e,rowTip(r));hit.onmouseleave=hideTip})}
draw();addEventListener("resize",draw);
"""

SPINE_BODY = """
<div class="controls"><span>Reach</span><span id="reach"></span><span>Type</span><span id="types"></span>
<label><input type="checkbox" id="human" checked> people only</label></div>
<div class="legend" id="legend"></div>
<div class="wrap"><svg id="chart" width="100%"></svg></div>
<p class="note">Each row is one corpus, each column one position from C1 to the coccyx (S1 stands for the sacrum). A cell is filled where the corpus shows that level: solid where the record states the region, lighter where the region is read from the body part the collection images (a chest CT, a pelvic film). The shade is the corpus's own count of images, spread over its span, since no record counts images by level; a cell with no count is drawn as an outline. The top band counts the corpora shown that reach each level. The transitional classes T13 and L6 have no column; chapter 7 holds them.</p>
"""

SPINE_JS = r"""
const S={reach:new Set(["held"]),types:new Set(TYPES),human:true};
chips("reach",["held","get","gated","embargoed","none","excluded"],RW,S.reach,draw);chips("types",TYPES,TW,S.types,draw);
document.getElementById("human").onchange=e=>{S.human=e.target.checked;draw()};
document.getElementById("legend").innerHTML=TYPES.map(t=>`<span><i style="background:var(--t-${t})"></i>${TW[t]}</span>`).join("")+
"<span>shade: more images, darker; outline: no count</span>";
function draw(){const A=DATA.axis;const rows=DATA.corpora.filter(r=>r.levels.length&&S.reach.has(r.reach)&&S.types.has(r.type)&&(!S.human||r.human)&&!r.aggregate);
const svg=document.getElementById("chart");svg.innerHTML="";const W=Math.max(svg.clientWidth||900,640),L=230,cw=(W-L-10)/A.length,rowH=14,band=60,top=band+30;
const H=top+rows.length*rowH+8;svg.setAttribute("height",H);svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
const cover=A.map(a=>rows.filter(r=>r.levels.includes(a)).length),cmax=Math.max(1,...cover);
A.forEach((a,i)=>{const h=band*cover[i]/cmax;el("rect",{x:L+i*cw+1,y:band-h+4,width:cw-2,height:h,rx:2,fill:"var(--ink3)"},svg);
const c=el("text",{x:L+i*cw+cw/2,y:band-h,"text-anchor":"middle","font-size":10},svg);c.textContent=cover[i];
const t=el("text",{x:L+i*cw+cw/2,y:band+20,"text-anchor":"middle","font-size":10},svg);t.textContent=a==="S1"?"S":a});
const lmax=Math.log10(Math.max(10,...rows.map(r=>r.images||1)));
rows.forEach((r,j)=>{const y=top+j*rowH;const t=el("text",{x:L-6,y:y+10,"text-anchor":"end","font-size":11},svg);t.textContent=sn(r.name);
A.forEach((a,i)=>{if(!r.levels.includes(a))return;const known=r.images!=null;const op=known?0.3+0.7*Math.log10(Math.max(r.images,1))/lmax:0;
el("rect",{x:L+i*cw+1,y:y+1,width:cw-2,height:rowH-2,rx:2,fill:`var(--t-${r.type})`,"fill-opacity":r.span_basis==="stated"?op:op*0.55,
stroke:`var(--t-${r.type})`,"stroke-width":known?0:1.2},svg)});
const hit=el("rect",{x:0,y:y,width:W,height:rowH,fill:"transparent"},svg);hit.onmousemove=e=>showTip(e,rowTip(r));hit.onmouseleave=hideTip})}
draw();addEventListener("resize",draw);
"""

POWER_BODY = """
<div class="controls"><label>Task <select id="task"></select></label>
<label>Mode <select id="mode"><option value="precision">estimate within a margin</option><option value="bound">clear a lower bound</option><option value="compare">detect a difference</option></select></label></div>
<div class="controls" id="inputs"></div>
<div id="out" style="font-size:15px;margin:6px 0"></div>
<div class="wrap"><svg id="chart" width="100%"></svg></div>
<p class="note" id="defaults"></p>
<p class="note"><b>Estimate within a margin:</b> the smallest n whose 95 percent Wilson interval at the expected proportion p, (p + z^2/2n +/- z sqrt(p(1-p)/n + z^2/4n^2)) / (1 + z^2/n), has a half-width at most the margin. <b>Clear a lower bound:</b> the smallest n at which the Wilson lower bound reaches the target with the stated power when the true proportion is p, by the exact binomial; with no error expected it is n / (n + z^2) at least the target, which gives 35 for 90 percent and 22 for 85 percent. <b>Detect a difference:</b> the standard two-proportion formula per arm, n = (z_a sqrt(2 pbar qbar) + z_b sqrt(p1 q1 + p2 q2))^2 / (p1 - p2)^2, both arms counted in the persons. Persons = ceil(n x DE / m), where m is the units scored per person and DE = 1 + (m - 1) ICC. The bars are the persons each corpus holds for the task, as its record or the size-and-power analysis states them; the red line is the persons needed. The same arithmetic, in Python, is tools/data_figures.py and its test.</p>
"""

POWER_JS = r"""
function ncdfInv(p){const a=[-39.69683028665376,220.9460984245205,-275.9285104469687,138.357751867269,-30.66479806614716,2.506628277459239],
b=[-54.47609879822406,161.5858368580409,-155.6989798598866,66.80131188771972,-13.28068155288572],c=[-0.007784894002430293,-0.3223964580411365,-2.400758277161838,-2.549732539343734,4.374664141464968,2.938163982698783],
d=[0.007784695709041462,0.3224671290700398,2.445134137142996,3.754408661907416],pl=0.02425;let q,r;
if(p<pl){q=Math.sqrt(-2*Math.log(p));return(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)}
if(p>1-pl){q=Math.sqrt(-2*Math.log(1-p));return-(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)}
q=p-0.5;r=q*q;return(((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)}
const zOf=al=>ncdfInv(1-al/2);
function wilson(x,n,z){const p=x/n,s=1+z*z/n,c=(p+z*z/(2*n))/s,h=z/s*Math.sqrt(p*(1-p)/n+z*z/(4*n*n));return[c-h,c+h]}
function lgamma(x){const g=[76.18009172947146,-86.50532032941677,24.01409824083091,-1.231739572450155,0.1208650973866179e-2,-0.5395239384953e-5];
let y=x,t=x+5.5;t-=(x+0.5)*Math.log(t);let s=1.000000000190015;for(let j=0;j<6;j++)s+=g[j]/++y;return-t+Math.log(2.5066282746310005*s/x)}
const lch=(n,k)=>lgamma(n+1)-lgamma(k+1)-lgamma(n-k+1);
function tail(n,x,p){if(x<=0)return 1;if(x>n)return 0;if(p>=1)return 1;if(p<=0)return 0;const lp=Math.log(p),lq=Math.log(1-p);let s=0;for(let k=x;k<=n;k++)s+=Math.exp(lch(n,k)+k*lp+(n-k)*lq);return Math.min(1,s)}
function fewest(n,t,z){if(wilson(n,n,z)[0]<t)return null;let lo=0,hi=n;while(lo<hi){const m=(lo+hi)>>1;if(wilson(m,n,z)[0]>=t)hi=m;else lo=m+1}return lo}
const MAXN=10000;
function precisionN(p,mg,al){const z=zOf(al);for(let n=1;n<=MAXN;n++){const w=wilson(p*n,n,z);if((w[1]-w[0])/2<=mg+1e-12)return n}return null}
function boundN(p,t,al,pw){if(p<=t)return null;const z=zOf(al);for(let n=1;n<=MAXN;n++){const x=fewest(n,t,z);if(x!==null&&tail(n,x,p)>=pw)return n}return null}
function compareN(p1,p2,al,pw){if(p1===p2)return null;const za=zOf(al),zb=ncdfInv(pw),pb=(p1+p2)/2;const r=za*Math.sqrt(2*pb*(1-pb))+zb*Math.sqrt(p1*(1-p1)+p2*(1-p2));return Math.ceil(r*r/((p1-p2)**2))}
const FIELDS={precision:["p","margin","alpha","m","de"],bound:["p","target","alpha","power","m","de"],compare:["p","p2","alpha","power","m","de"]};
const LABEL={p:"expected proportion p",margin:"margin (half-width)",target:"lower bound to clear",p2:"second proportion p2",alpha:"alpha",power:"power",m:"units per person m",de:"design effect DE"};
let V={};const ts=document.getElementById("task"),ms=document.getElementById("mode");
Object.entries(DATA.tasks).forEach(([k,t])=>{const o=document.createElement("option");o.value=k;o.textContent=t.title;ts.appendChild(o)});
function load(){const t=DATA.tasks[ts.value];V=Object.assign({target:0.9,p2:0.8,margin:0.05,power:0.8},t.defaults);ms.value=V.mode;
document.getElementById("defaults").textContent="Defaults for this task: "+t.defaults_source+". Unit: "+t.unit+".";inputs()}
function inputs(){const box=document.getElementById("inputs");box.innerHTML="";FIELDS[ms.value].forEach(f=>{const l=document.createElement("label");l.textContent=LABEL[f]+" ";
const i=document.createElement("input");i.type="number";i.step=f==="m"||f==="de"?"0.1":"0.01";i.value=V[f];i.oninput=()=>{V[f]=parseFloat(i.value);calc()};l.appendChild(i);box.appendChild(l)});calc()}
function calc(){const m=ms.value;let n=null;if(m==="precision")n=precisionN(V.p,V.margin,V.alpha);else if(m==="bound")n=boundN(V.p,V.target,V.alpha,V.power);else n=compareN(V.p,V.p2,V.alpha,V.power);
let persons=n==null?null:Math.ceil(n*V.de/V.m-1e-9);if(persons!=null&&m==="compare")persons*=2;
document.getElementById("out").innerHTML=n==null?"<b>Not reachable</b> with these inputs (p at or below the bound, equal proportions, or more than "+MAXN.toLocaleString("en-US")+" units).":
`<b>${n.toLocaleString("en-US")}</b> independent ${m==="compare"?"units per arm":"units"}, so <b>${persons.toLocaleString("en-US")}</b> persons${m==="compare"?" over both arms":""} at m ${V.m} and DE ${V.de}.`;
drawBars(persons)}
function drawBars(need){const t=DATA.tasks[ts.value],hs=t.holdings;const svg=document.getElementById("chart");svg.innerHTML="";const W=Math.max(svg.clientWidth||900,560),L=260,R=80,rowH=24,top=26;
const H=top+hs.length*rowH+10;svg.setAttribute("height",H);svg.setAttribute("viewBox",`0 0 ${W} ${H}`);const max=Math.max(10,need||1,...hs.map(h=>h.persons)),lmax=Math.ceil(Math.log10(max));
const x=v=>L+(W-L-R)*Math.log10(Math.max(v,1))/lmax;for(let k=0;k<=lmax;k++){el("line",{x1:x(10**k),x2:x(10**k),y1:top-4,y2:H-6,stroke:"var(--rule)"},svg);
const tx=el("text",{x:x(10**k),y:top-10,"text-anchor":"middle","font-size":11},svg);tx.textContent=(10**k).toLocaleString("en-US")}
hs.forEach((h,i)=>{const y=top+i*rowH;const tx=el("text",{x:L-6,y:y+15,"text-anchor":"end","font-size":11},svg);tx.textContent=h.label;
const w=Math.max(2,x(h.persons)-L);el("rect",{x:L,y:y+4,width:w,height:rowH-8,rx:2,fill:h.kind.startsWith("real")?"var(--t-paired)":"var(--ink3)",opacity:h.reach==="held"?1:0.45},svg);
const v=el("text",{x:L+w+4,y:y+15,"font-size":11},svg);v.textContent=h.persons.toLocaleString("en-US");
const hit=el("rect",{x:0,y:y,width:W,height:rowH,fill:"transparent"},svg);hit.onmousemove=e=>showTip(e,`<b>${esc(h.label)}</b><br>${esc(h.kind)}; ${esc(h.reach)}<br>${esc(h.note)}<br><span class="note">${esc(h.source)}</span>`);hit.onmouseleave=hideTip});
if(need){el("line",{x1:x(need),x2:x(need),y1:top-4,y2:H-6,stroke:"var(--need)","stroke-width":2},svg);const lab=el("text",{x:Math.min(x(need)+4,W-R),y:H-8,"font-size":11},svg);lab.textContent="needed "+need.toLocaleString("en-US")}}
ts.onchange=load;ms.onchange=()=>{V.mode=ms.value;inputs()};load();addEventListener("resize",calc);
"""


def svg_open(width: int, height: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{esc(title)}">',
        f"<style>{SVG_STYLE}</style>",
        f'<rect class="bg" width="{width}" height="{height}"/>',
    ]


def log_x(left: int, right: int, top_value: float):
    decades = max(1, math.ceil(math.log10(max(top_value, 10))))
    return decades, lambda v: left + (right - left) * math.log10(max(v, 1)) / decades


def axis_lines(lines: list, decades: int, x, top: int, bottom: int) -> None:
    for k in range(decades + 1):
        lines.append(f'<line x1="{x(10**k):.1f}" x2="{x(10**k):.1f}" y1="{top - 4}" y2="{bottom}" class="rule"/>')
        lines.append(f'<text x="{x(10**k):.1f}" y="{top - 9}" text-anchor="middle">{10**k:,}</text>')


def amount_svg(table: dict) -> str:
    rows = [r for r in table["corpora"] if r["persons"] is not None and not r["aggregate"] and r["reach"] in REACH_WORDS]
    rows.sort(key=lambda r: -r["persons"])
    width, left, top, row = 900, 250, 64, 15
    height = top + row * len(rows) + 30
    decades, x = log_x(left, width - 70, rows[0]["persons"])
    lines = svg_open(width, height, "Persons by corpus and data type")
    lines.append(f'<text x="10" y="16">Persons each corpus records, on a log axis, coloured by data type; faint bars are corpora not held.</text>')
    for i, t in enumerate(TYPE_ORDER):
        lines.append(f'<rect x="{10 + i * 130}" y="24" width="10" height="10" rx="2" class="t-{t}"/><text x="{24 + i * 130}" y="33">{TYPE_WORDS[t]}</text>')
    axis_lines(lines, decades, x, top, height - 20)
    for i, r in enumerate(rows):
        y = top + i * row
        w = max(2.0, x(r["persons"]) - left)
        opacity = 1 if r["reach"] == "held" else 0.45
        lines.append(f'<text x="{left - 6}" y="{y + 11}" text-anchor="end">{esc(short_name(r["name"]))}</text>')
        lines.append(f'<rect x="{left}" y="{y + 2}" width="{w:.1f}" height="{row - 4}" rx="2" class="t-{r["type"]}" opacity="{opacity}"/>')
        lines.append(f'<text x="{left + w + 4:.1f}" y="{y + 11}">{r["persons"]:,}</text>')
    lines.append(f'<text x="10" y="{height - 6}">Corpora whose record counts no persons are left out here; the interactive page switches to images. {COMMAND}</text>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def spine_svg(table: dict) -> str:
    rows = [r for r in table["corpora"] if r["levels"] and r["human"] and not r["aggregate"] and r["reach"] == "held"]
    axis = table["axis"]
    width, left, band = 900, 250, 60
    top, row = band + 34, 13
    cell = (width - left - 10) / len(axis)
    height = top + row * len(rows) + 24
    lines = svg_open(width, height, "Where along the spine each held corpus lies")
    lines.append('<text x="10" y="16">Held corpora of people, C1 to the coccyx; the band counts the corpora reaching each level.</text>')
    cover = [sum(1 for r in rows if a in r["levels"]) for a in axis]
    peak = max(cover) or 1
    for i, a in enumerate(axis):
        h = band * cover[i] / peak
        lines.append(f'<rect x="{left + i * cell + 1:.1f}" y="{band - h + 22:.1f}" width="{cell - 2:.1f}" height="{h:.1f}" rx="2" class="ink3"/>')
        lines.append(f'<text x="{left + i * cell + cell / 2:.1f}" y="{band - h + 18:.1f}" text-anchor="middle">{cover[i]}</text>')
        lines.append(f'<text x="{left + i * cell + cell / 2:.1f}" y="{band + 34:.1f}" text-anchor="middle">{"S" if a == "S1" else a}</text>')
    top += 6
    peak_images = max([r["images"] or 1 for r in rows] + [10])
    for j, r in enumerate(rows):
        y = top + j * row
        lines.append(f'<text x="{left - 6}" y="{y + 10}" text-anchor="end">{esc(short_name(r["name"]))}</text>')
        known = r["images"] is not None
        shade = 0.3 + 0.7 * math.log10(max(r["images"] or 1, 1)) / math.log10(peak_images) if known else 0
        if r["span_basis"] != "stated":
            shade *= 0.55
        for i, a in enumerate(axis):
            if a in r["levels"]:
                stroke = "" if known else f' class="t-{r["type"]} o-{r["type"]}" stroke-width="1.2"'
                lines.append(f'<rect x="{left + i * cell + 1:.1f}" y="{y + 1}" width="{cell - 2:.1f}" height="{row - 2}" rx="2" fill-opacity="{shade:.2f}"{stroke or f' class="t-{r["type"]}"'}/>')
    lines.append(f'<text x="10" y="{height - 6}">Solid: region stated by the record; lighter: read from the body part; outline: no image count. {COMMAND}</text>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def power_svg(table: dict) -> str:
    tasks = table["tasks"]
    width, left, top, row = 900, 330, 44, 18
    count = sum(len(t["holdings"]) + 1 for t in tasks.values())
    height = top + row * count + 30
    peak = max([h["persons"] for t in tasks.values() for h in t["holdings"]] + [t["needed_at_defaults"]["persons"] or 1 for t in tasks.values()])
    decades, x = log_x(left, width - 70, peak)
    lines = svg_open(width, height, "Persons needed against persons held, by task")
    lines.append('<text x="10" y="16">Persons each task needs at the calculator\'s defaults (red mark) against the persons each corpus holds for it; log axis. Blue: real frames or films; grey: CT.</text>')
    axis_lines(lines, decades, x, top, height - 20)
    y = top
    for task in tasks.values():
        need = task["needed_at_defaults"]["persons"]
        d = task["defaults"]
        mode = {"precision": f"p {d['p']}, margin {d.get('margin')}", "bound": f"p {d['p']}, bound {d.get('target')}, power {d['power']}", "compare": f"{d['p']} against {d.get('p2')}, power {d['power']}"}[d["mode"]]
        lines.append(f'<text x="10" y="{y + 12}" class="head">{esc(task["title"])}</text>')
        if need:
            lines.append(f'<line x1="{x(need):.1f}" x2="{x(need):.1f}" y1="{y + 2}" y2="{y + row * (len(task["holdings"]) + 1) - 2}" class="need-line" stroke-width="2"/>')
            lines.append(f'<text x="{x(need) + 4:.1f}" y="{y + 12}" class="need-text">needs {need:,} ({esc(mode)}, DE {d["de"]}, m {d["m"]})</text>')
        y += row
        for h in task["holdings"]:
            w = max(2.0, x(h["persons"]) - left)
            fill = "t-paired" if h["kind"].startswith("real") else "ink3"
            opacity = 1 if h["reach"] == "held" else 0.45
            lines.append(f'<text x="{left - 6}" y="{y + 12}" text-anchor="end">{esc(h["label"])}</text>')
            lines.append(f'<rect x="{left}" y="{y + 3}" width="{w:.1f}" height="{row - 6}" rx="2" class="{fill}" opacity="{opacity}"/>')
            lines.append(f'<text x="{left + w + 4:.1f}" y="{y + 12}">{h["persons"]:,}</text>')
            y += row
    lines.append(f'<text x="10" y="{height - 6}">The interactive page recomputes the need for any inputs. {COMMAND}</text>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


FIGURES = {
    "data-types": {
        "title": "The amount of each data type, by corpus",
        "caption": "Persons or images per corpus from the dataset records, coloured by data type (paired 3D-2D, annotated 2D, synthetic 2D, CT volumes, unannotated 2D), filtered by reach and licence class. Read which types are large and which are a handful of persons.",
        "body": AMOUNT_BODY, "js": AMOUNT_JS, "svg": amount_svg,
    },
    "spine-coverage": {
        "title": "Where along the spine each corpus lies",
        "caption": "One strip per corpus from C1 to the coccyx, shaded by the corpus's image count where its record gives one and outlined where only the region is known, with a band counting the corpora at each level. Read where the holding is thick (lumbar, sacrum) and where it is thin (cervical and thoracic on real frames).",
        "body": SPINE_BODY, "js": SPINE_JS, "svg": spine_svg,
    },
    "power-calculator": {
        "title": "Persons needed for each detection and classification task",
        "caption": "A calculator for five tasks (detection recall, level naming, transitional naming, counting exactness, anomaly classification): Wilson-interval precision, a Wilson lower bound reached with power, or two proportions compared, inflated by the design effect, set beside the persons each corpus holds for the task.",
        "body": POWER_BODY, "js": POWER_JS, "svg": power_svg,
    },
}


def record_of(slug: str, spec: dict) -> dict:
    data = ["data/sources/", "data/registry/", "data/licences.json", "docs/textbook/figures/35/corpora-overlay.json", "docs/textbook/figures/35/corpora.json"]
    if slug == "power-calculator":
        data.append("artifacts/state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay/")
    return {
        "id": f"35/{slug}",
        "title": spec["title"],
        "caption": spec["caption"],
        "chapter": "35",
        "grade": "Inferred",
        "status": "current",
        "source": {
            "kind": "script",
            "artifact": "artifacts/state-of-the-literature-datasets-held-missing-size-and-power-8hg1ay/" if slug == "power-calculator" else "artifacts/schwingnet-data-registry/",
            "artifact_url": "https://claude.ai/artifact/8Hg1AyjzCf7VhCjPAQw8sY" if slug == "power-calculator" else "https://claude.ai/artifact/L4pJez6yLFzaX8x5jiA3JL",
            "made_by": "tools/data_figures.py",
            "commit": None,
            "data": data,
            "run": None,
            "notes": "Drawn new from committed files. The counts are the records' own (Reported); the data type, the span along the spine and the tried status of each corpus are the chapter's reading of each record, written into corpora-overlay.json (Inferred); the script refuses any count its record or the overlay's note does not give. The artifact named is the earlier rendering of the same records" + (" and the source of the power targets and holdings" if slug == "power-calculator" else "") + ".",
        },
        "explore": [
            {"label": "The script", "href": "tools/data_figures.py"},
            {"label": "The table it draws from", "href": "docs/textbook/figures/35/corpora.json"},
            {"label": "The judgments per corpus", "href": "docs/textbook/figures/35/corpora-overlay.json"},
            {"label": "The dataset records", "href": "data/sources/"},
            {"label": "The chapter", "href": "docs/textbook/35-how-the-workflow-is-built.md"},
        ],
        "rerun": {"where": "actions", "command": COMMAND, "cost": "CPU, a few seconds", "needs_owner_word": False},
    }


def outputs() -> dict[str, str]:
    table = build_table()
    files = {"corpora.json": json.dumps(table, indent=1, sort_keys=True) + "\n"}
    for slug, spec in FIGURES.items():
        data = {"axis": table["axis"], "corpora": table["corpora"], "tasks": table["tasks"]}
        files[f"{slug}.html"] = page(spec["title"], spec["caption"], spec["body"], data, spec["js"])
        files[f"{slug}.svg"] = spec["svg"](table)
        files[f"{slug}.json"] = json.dumps(record_of(slug, spec), indent=1) + "\n"
    return files


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["write", "check"])
    args = parser.parse_args(argv)
    files = outputs()
    stale = []
    for name, text in files.items():
        path = OUT / name
        if args.command == "write":
            path.write_text(text)
        elif not path.exists() or path.read_text() != text:
            stale.append(name)
    if stale:
        print("not what the inputs give, run " + COMMAND + ": " + ", ".join(stale))
        return 1
    print(("wrote " if args.command == "write" else "up to date: ") + ", ".join(sorted(files)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
