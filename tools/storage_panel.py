"""The textbook's storage panel: the lab volume's and the owner's home's drive use, every dataset
spine-datasets knows, and the combinations of them that fit under the target, laid out as an
interactive figure of chapter 22 from a committed snapshot of spine-datasets' feed (issue #244).

Source: the owner's ask of 2026-10-24 20:34 UTC, to know the drive usage from the artifact, trial
combinations of datasets under 20 TB, trigger the removals and additions, and place some data on the
owner's 4 TB home.

The feed is PLAN.json on the branch storage-feed of OpenSpineConsortium/spine-datasets, which that
repository rebuilds whenever a record changes: the target in bytes, the pending request pull
requests, the lab volume's quota and use (datasets against everything else) with the time it was read,
the home's quota and use (null until a grid word reads it), and one entry per set with its id, name,
group, reach, whether it can be fetched, its status, where it is (lab, home or none), its bytes (the
measured size once frozen, else what its source states, else null), its licence class and the sets it
overlaps with. The panel never reads the feed at view time: `build` inlines the committed snapshot
docs/textbook/figures/22/storage-plan.json into the page, `fetch` refreshes that snapshot from GitHub's
contents API with the token in STORAGE_FEED_TOKEN (else GITHUB_TOKEN), following no redirect so the
token reaches no other address, and exits non-zero with one sentence when the feed is unreachable, so
.github/workflows/docs.yml falls back to the committed snapshot; `check` rebuilds from the committed
snapshot and fails when the committed page, picture or record differs, so a stale page fails the
required check (scripts/check.sh).

The selection the panel builds is the planner's own grammar: `-id` removes a set, `+id` adds one,
`id@home` and `id@lab` place one, tokens separated by spaces. The page's Apply button asks its host
window, through postMessage, to dispatch spine-datasets' workflow storage.yml with that selection;
`python3 tools/storage.py check` there refuses an over-cap or sizeless fetch, and any move to the home
while its use is unread, and the run only opens a request pull request the owner merges, so nothing is
fetched or removed from this page alone. Where no host answers within eight seconds, or the host
answers that it cannot, the page shows the workflow's link and the selection to paste, and asks the
page around it to show the link in its own bar (schwingnet.open), since a sandboxed frame cannot open
one. The site's host (tools/textbook_site.py, MESSAGE_JS) answers every dispatch and read "no
connector" and shows the link; the artifact edition's host carries the connector. This file implements
only the figure's side.

The arithmetic the page does (the final place of each set, the selection string, the totals after the
choices, the overlaps among the kept sets and the refusals the planner's check would make) is written
once in Python below (`final_location`, `tokens`, `selection`, `totals`, `overlaps`, `refusals`) and
mirrored in the page's MODEL_JS; tests/test_storage_panel.py runs both on one plan and compares.

    python3 tools/storage_panel.py build [--plan PATH] [--out DIR]   # storage.html, storage.svg, storage.json
    python3 tools/storage_panel.py fetch [--out PATH] [--url URL]    # the snapshot, from the feed
    python3 tools/storage_panel.py check [--plan PATH] [--out DIR]   # exit 1 when a committed file is stale
"""

import argparse
import base64
import binascii
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "docs" / "textbook" / "figures" / "22"
SNAPSHOT = FOLDER / "storage-plan.json"
FEED_REPO = "OpenSpineConsortium/spine-datasets"
FEED_PATH = "PLAN.json"
FEED_REF = "storage-feed"
FEED_URL = f"https://api.github.com/repos/{FEED_REPO}/contents/{FEED_PATH}?ref={FEED_REF}"
FEED_PAGE = f"https://github.com/{FEED_REPO}/blob/{FEED_REF}/{FEED_PATH}"
WORKFLOW = "storage.yml"
WORKFLOW_URL = f"https://github.com/{FEED_REPO}/actions/workflows/{WORKFLOW}"
FORMAT = "spine-datasets/storage 1"
FIGURE_ID = "22/storage"
COMMAND = "python3 tools/storage_panel.py build"
OUTPUTS = ("storage.html", "storage.svg", "storage.json")
TOKEN_VARIABLES = ("STORAGE_FEED_TOKEN", "GITHUB_TOKEN")
TIMEOUT = 30
PLACES = ("lab", "home")


# ---------------------------------------------------------------- the model, mirrored in MODEL_JS


def tb(n):
    """Bytes as terabytes with one decimal, rounded half up on whole tenths so Python and the page
    print the same figure; None is a size the feed does not know."""
    if n is None:
        return "size unknown"
    tenths = (int(n) + 50_000_000_000) // 100_000_000_000
    return f"{tenths // 10}.{tenths % 10} TB"


def is_held(s):
    return s.get("location") in PLACES


def final_location(s, choice):
    """Where a set ends up under a choice: a held set stays, moves (place) or goes (remove); a
    fetchable set that is added lands on the lab unless placed on the home; anything else is nowhere."""
    action = choice.get("action", "keep")
    place = choice.get("place")
    if is_held(s):
        if action == "remove":
            return "none"
        return place if place in PLACES else s["location"]
    if action == "add" and s.get("fetchable"):
        return place if place in PLACES else "lab"
    return "none"


def tokens(plan, choices):
    """The selection's tokens in the feed's order, one or two per set whose place changes."""
    out = []
    for s in plan["sets"]:
        before = s["location"] if is_held(s) else "none"
        after = final_location(s, choices.get(s["id"]) or {})
        if before == after:
            continue
        if after == "none":
            out.append("-" + s["id"])
        elif before == "none":
            out.append("+" + s["id"])
            if after == "home":
                out.append(s["id"] + "@home")
        else:
            out.append(f"{s['id']}@{after}")
    return out


def selection(plan, choices):
    return " ".join(tokens(plan, choices))


def totals(plan, choices):
    """The volume's and the home's use after the choices, and which sets the choices change; a
    changed set with no size is listed, not counted, since nothing can count it."""
    volume, home = plan["volume"], plan["home"]
    lab, datasets, home_delta = volume["used_bytes"], volume["datasets_bytes"], 0
    out = {"removed": [], "added": [], "moved": [], "to_home": [], "unsized": []}
    for s in plan["sets"]:
        before = s["location"] if is_held(s) else "none"
        after = final_location(s, choices.get(s["id"]) or {})
        if before == after:
            continue
        kind = "added" if before == "none" else "removed" if after == "none" else "moved"
        out[kind].append(s["id"])
        if after == "home":
            out["to_home"].append(s["id"])
        if s.get("bytes") is None:
            out["unsized"].append(s["id"])
            continue
        if before == "lab":
            lab -= s["bytes"]
            datasets -= s["bytes"]
        if before == "home":
            home_delta -= s["bytes"]
        if after == "lab":
            lab += s["bytes"]
            datasets += s["bytes"]
        if after == "home":
            home_delta += s["bytes"]
    home_before = home.get("used_bytes")
    out.update({
        "lab_before": volume["used_bytes"], "lab_after": lab, "datasets_after": datasets,
        "lab_quota": volume["quota_bytes"], "target": plan["target_bytes"],
        "home_before": home_before, "home_delta": home_delta,
        "home_after": None if home_before is None else home_before + home_delta,
        "home_quota": home["quota_bytes"],
    })
    return out


def overlaps(plan, choices):
    """Each pair of sets that both end up held and that the feed says share patients or series,
    once per pair, in the feed's order; read from the sets' own overlap lists, never all pairs."""
    active = {s["id"] for s in plan["sets"] if final_location(s, choices.get(s["id"]) or {}) != "none"}
    seen, out = set(), []
    for s in plan["sets"]:
        if s["id"] not in active:
            continue
        for o in s.get("overlap") or []:
            partner = o.get("with")
            if partner not in active or partner == s["id"]:
                continue
            a, b = sorted((s["id"], partner))
            if (a, b) in seen:
                continue
            seen.add((a, b))
            out.append({"a": a, "b": b, "patients": o.get("patients"), "series": o.get("series"),
                        "same_bytes": o.get("same_bytes")})
    return out


def refusals(plan, t):
    """The planner's check in words: what `python3 tools/storage.py check` would refuse of these
    totals, in a fixed order, one sentence each."""
    out = []
    if t["unsized"]:
        many = len(t["unsized"]) > 1
        out.append(f"{', '.join(t['unsized'])} {'have' if many else 'has'} no measured size, so the planner refuses "
                   f"the fetch or the move: the size rule reads a set's exact size before a byte lands.")
    if t["to_home"] and plan["home"].get("used_bytes") is None:
        out.append("The home's use has not been read yet, so the planner refuses any move to it until a grid word reads it.")
    if t["lab_after"] > t["target"]:
        out.append(f"The lab volume would hold {tb(t['lab_after'])}, over the target of {tb(t['target'])} "
                   f"by {tb(t['lab_after'] - t['target'])}.")
    if t["lab_after"] > t["lab_quota"]:
        out.append(f"The lab volume would hold {tb(t['lab_after'])}, over its quota of {tb(t['lab_quota'])}: "
                   "the size rule would refuse the fetch whole.")
    if t["home_after"] is not None and t["home_after"] > t["home_quota"]:
        out.append(f"The home would hold {tb(t['home_after'])}, over its quota of {tb(t['home_quota'])}.")
    return out


def validate(plan):
    """One sentence on what is wrong with a plan that is not the feed's format; None when it holds."""
    if not isinstance(plan, dict):
        return "the plan is not a JSON object"
    if plan.get("format") != FORMAT:
        return f"the plan's format is {plan.get('format')!r}, not {FORMAT!r}"
    for key in ("built_at", "target_bytes", "requests", "volume", "home", "sets"):
        if key not in plan:
            return f"the plan has no {key}"
    for key in ("quota_bytes", "used_bytes", "datasets_bytes", "other_bytes"):
        if not isinstance(plan["volume"].get(key), int):
            return f"the plan's volume has no whole {key}"
    if not isinstance(plan["home"].get("quota_bytes"), int):
        return "the plan's home has no whole quota_bytes"
    if not isinstance(plan["sets"], list) or not plan["sets"]:
        return "the plan lists no sets"
    for s in plan["sets"]:
        for key in ("id", "name", "location", "fetchable"):
            if not isinstance(s, dict) or key not in s:
                return f"a set has no {key}"
        if s.get("bytes") is not None and not isinstance(s["bytes"], int):
            return f"{s['id']}: bytes is not a whole number"
    return None


# ---------------------------------------------------------------- the feed


class FeedUnreachable(Exception):
    """Why the feed could not be read, in one sentence; the workflow prints it and builds from the
    committed snapshot."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """urllib would send a redirected request every header of the first, the token among them, to
    whatever address the redirect names; this handler refuses the redirect instead."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise FeedUnreachable(f"the feed answered {code} with a redirect, which this fetch does not follow, "
                              "so the token goes to no other address")


def read_feed(url, token, timeout=TIMEOUT):
    """The contents API's answer for the feed, as bytes."""
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "SchwingNet-storage-panel"})
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as answer:
            return answer.read()
    except FeedUnreachable:
        raise
    except urllib.error.HTTPError as e:
        raise FeedUnreachable(f"the feed answered HTTP {e.code} ({e.reason})") from None
    except urllib.error.URLError as e:
        raise FeedUnreachable(f"the feed could not be reached: {e.reason}") from None
    except (OSError, TimeoutError) as e:
        raise FeedUnreachable(f"the feed could not be read: {e}") from None


def decode_feed(body):
    """The plan inside the contents API's answer, checked against the feed's format."""
    try:
        answer = json.loads(body)
    except ValueError:
        raise FeedUnreachable("the feed's answer was not JSON") from None
    content = answer.get("content") if isinstance(answer, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise FeedUnreachable("the feed's answer carried no content")
    try:
        plan = json.loads(base64.b64decode(content).decode("utf-8"))
    except (ValueError, binascii.Error):
        raise FeedUnreachable("the feed's content was not base64 JSON") from None
    wrong = validate(plan)
    if wrong:
        raise FeedUnreachable(f"the feed does not hold a plan: {wrong}")
    return plan


def write_snapshot(plan, path):
    """The snapshot in one canonical shape, ASCII with LF, so the same feed gives the same bytes."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(plan, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def feed_token():
    for name in TOKEN_VARIABLES:
        if os.environ.get(name):
            return os.environ[name]
    return None


def fetch(out, url=FEED_URL):
    """Refresh the snapshot from the feed; exit 2 with no token, 1 when the feed is unreachable, each
    with one sentence on stderr, so a workflow can print it and go on from the committed snapshot."""
    token = feed_token()
    if not token:
        print(f"no token: set {TOKEN_VARIABLES[0]} (or {TOKEN_VARIABLES[1]}) to read {FEED_REPO}'s feed", file=sys.stderr)
        return 2
    try:
        plan = decode_feed(read_feed(url, token))
    except FeedUnreachable as why:
        print(f"the storage feed was not read: {why}", file=sys.stderr)
        return 1
    write_snapshot(plan, out)
    print(f"wrote {out} ({len(plan['sets'])} sets, feed built {plan['built_at']})")
    return 0


# ---------------------------------------------------------------- the page


def esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


STYLE = """
:root{color-scheme:light;--bg:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--ink3:#8a8984;--rule:#e4e3df;--panel:#f3f1ec;
--data:#2a78d6;--other:#b3b1aa;--target:#d98c00;--red:#c2362e;--redbg:#fbe9e7;--ok:#1f8a55;--home:#7a52c7;--link:#1f5fbf}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){color-scheme:dark;--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;
--ink3:#8f8e87;--rule:#34332f;--panel:#242422;--data:#4a8fe8;--other:#6c6b66;--target:#f0b23a;--red:#f07167;--redbg:#3a2220;
--ok:#5fc48f;--home:#a98ae8;--link:#7fb0ff}}
:root[data-theme=dark]{color-scheme:dark;--bg:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--ink3:#8f8e87;--rule:#34332f;--panel:#242422;
--data:#4a8fe8;--other:#6c6b66;--target:#f0b23a;--red:#f07167;--redbg:#3a2220;--ok:#5fc48f;--home:#a98ae8;--link:#7fb0ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}
h1{font-size:18px;margin:0 0 4px}h2{font-size:15px;margin:18px 0 6px}h3{font-size:14px;margin:0 0 6px}
p{margin:6px 0}p.sub{color:var(--ink2);margin:0 0 10px}a{color:var(--link)}
.badge{display:inline-block;border:1px solid var(--rule);border-radius:10px;padding:0 8px;font-size:12px;color:var(--ink2);
margin-left:6px;vertical-align:middle;font-weight:400}
.badge.warn{border-color:var(--target);color:var(--target)}.badge.red{border-color:var(--red);color:var(--red)}
.drives{display:grid;grid-template-columns:1fr;gap:12px}@media (min-width:760px){.drives{grid-template-columns:1fr 1fr}}
.drive{border:1px solid var(--rule);border-radius:8px;padding:10px 12px;background:var(--panel)}
.band{position:relative;height:22px;background:var(--bg);border:1px solid var(--rule);border-radius:4px}
.band .seg{position:absolute;top:0;bottom:0}.band .seg.data{background:var(--data)}.band .seg.other{background:var(--other)}
.band .seg.home{background:var(--home)}.band .mark{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--target)}
.band.after{height:10px;margin-top:6px}.band.after .seg{background:var(--data);opacity:.85}.band.after.over .seg{background:var(--red)}
.band .empty{position:absolute;left:8px;top:0;line-height:20px;font-size:12px;color:var(--ink3)}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;color:var(--ink2);font-size:12px;margin-top:8px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.controls{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;margin:10px 0}
.controls label{display:inline-flex;gap:4px;align-items:center}
input[type=search],select,textarea,button{font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--rule);
border-radius:6px;padding:4px 8px}input[type=search]{min-width:200px;flex:1}
button{cursor:pointer}button:disabled{cursor:not-allowed;opacity:.55}button.primary{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.wrap{overflow-x:auto;max-height:70vh;overflow-y:auto;border:1px solid var(--rule);border-radius:8px}
table{border-collapse:collapse;font-size:12.5px;width:100%;min-width:720px}
td,th{padding:4px 6px;border-bottom:1px solid var(--rule);text-align:left;vertical-align:top}
th{color:var(--ink2);font-weight:600;position:sticky;top:0;background:var(--panel);z-index:1}
tr.head td{font-weight:600;color:var(--ink2);background:var(--panel);padding-top:8px}
tr.changed td{background:var(--panel)}tr.changed td:first-child{box-shadow:inset 3px 0 0 var(--data)}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}td.set{min-width:220px}
.choice label{display:inline-flex;gap:3px;align-items:center;margin-right:8px;white-space:nowrap}
.choice input:disabled+span{color:var(--ink3)}
.muted{color:var(--ink3)}.red{color:var(--red)}.ok{color:var(--ok)}code{font:12.5px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.totals{display:grid;grid-template-columns:1fr;gap:8px;margin:12px 0}@media (min-width:760px){.totals{grid-template-columns:1fr 1fr}}
.total{border:1px solid var(--rule);border-radius:8px;padding:8px 12px}.total.over{border-color:var(--red);background:var(--redbg)}
.refusals{border-left:3px solid var(--red);padding:6px 10px;margin:8px 0;background:var(--redbg)}.refusals p{margin:2px 0}
ul.notes{margin:6px 0;padding-left:18px}
textarea.sel{width:100%;min-height:54px;font:12.5px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;resize:vertical}
.actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0}
.status{color:var(--ink2);font-size:13px;margin:6px 0;min-height:1.4em}
.fallback{border:1px solid var(--target);border-radius:8px;padding:8px 12px;margin:8px 0;background:var(--panel)}
.fallback a{word-break:break-all}
.fallback code.paste{display:block;white-space:pre-wrap;word-break:break-all;margin:6px 0;padding:6px;background:var(--bg);border-radius:4px}
@media (max-width:600px){.opt{display:none}table{min-width:560px}}
"""

BODY = """
<h1>The storage panel</h1>
<p class="sub">What the lab volume and the owner's home hold, every set spine-datasets knows, and a selection that fits under the target.
Feed built <span id="built"></span><span id="built-age" class="badge"></span></p>
<section class="drives"><div class="drive" id="lab"></div><div class="drive" id="home"></div></section>
<h2>Pending requests</h2><div id="requests"></div>
<h2>The sets</h2>
<div class="controls"><input id="filter" type="search" placeholder="Filter by name, id or group" aria-label="Filter the sets">
<label><input type="checkbox" id="changed-only"> changed only</label><span id="shown" class="muted"></span>
<button id="reset" type="button" title="Put every set back as the feed has it">Reset the choices</button></div>
<div class="wrap"><table id="sets"><thead><tr><th>Set</th><th class="opt">Group</th><th>Status</th><th>Where</th><th>Size</th>
<th class="opt">Licence</th><th class="opt">Frozen</th><th>Choice</th><th>Place</th></tr></thead><tbody id="rows"></tbody></table></div>
<h2>After the choices</h2>
<div class="totals"><div class="total" id="t-lab"></div><div class="total" id="t-home"></div></div>
<div id="refusals"></div><div id="overlaps"></div>
<h2>The selection</h2>
<p class="sub">In the planner's grammar: <code>-id</code> removes a set, <code>+id</code> adds one, <code>id@home</code> and <code>id@lab</code> place one.</p>
<textarea id="selection" class="sel" readonly aria-label="The selection"></textarea>
<div class="actions"><button id="copy" type="button">Copy</button><button id="apply" type="button" class="primary">Apply through storage.yml</button>
<button id="refresh" type="button" title="Ask the page's host to read the feed again">Refresh from the feed</button></div>
<p class="status" id="status"></p><div class="fallback" id="fallback" hidden></div>
<p class="muted">Nothing runs from this page. Apply asks the page's host to dispatch spine-datasets' workflow storage.yml, whose check
refuses an over-cap or sizeless fetch and whose run only opens a request pull request that waits for the owner's merge.
Source: <code>python3 tools/storage_panel.py build</code> over the committed snapshot of the feed.</p>
"""

# The model, mirrored from the Python above: final_location, tokens, selection, totals, overlaps,
# refusals and tb, with the same names in camel case and the same words; the test runs both.
MODEL_JS = r"""
const Model = (function () {
  const PLACES = ["lab", "home"];
  function tb(n) {
    if (n === null || n === undefined) return "size unknown";
    const tenths = Math.floor((n + 50000000000) / 100000000000);
    return Math.floor(tenths / 10) + "." + (tenths % 10) + " TB";
  }
  function isHeld(s) { return PLACES.indexOf(s.location) >= 0; }
  function finalLocation(s, choice) {
    const action = choice.action || "keep", place = choice.place;
    if (isHeld(s)) {
      if (action === "remove") return "none";
      return PLACES.indexOf(place) >= 0 ? place : s.location;
    }
    if (action === "add" && s.fetchable) return PLACES.indexOf(place) >= 0 ? place : "lab";
    return "none";
  }
  function tokens(plan, choices) {
    const out = [];
    plan.sets.forEach(function (s) {
      const before = isHeld(s) ? s.location : "none", after = finalLocation(s, choices[s.id] || {});
      if (before === after) return;
      if (after === "none") out.push("-" + s.id);
      else if (before === "none") { out.push("+" + s.id); if (after === "home") out.push(s.id + "@home"); }
      else out.push(s.id + "@" + after);
    });
    return out;
  }
  function selection(plan, choices) { return tokens(plan, choices).join(" "); }
  function totals(plan, choices) {
    const volume = plan.volume, home = plan.home;
    let lab = volume.used_bytes, datasets = volume.datasets_bytes, homeDelta = 0;
    const out = { removed: [], added: [], moved: [], to_home: [], unsized: [] };
    plan.sets.forEach(function (s) {
      const before = isHeld(s) ? s.location : "none", after = finalLocation(s, choices[s.id] || {});
      if (before === after) return;
      out[before === "none" ? "added" : after === "none" ? "removed" : "moved"].push(s.id);
      if (after === "home") out.to_home.push(s.id);
      if (s.bytes === null || s.bytes === undefined) { out.unsized.push(s.id); return; }
      if (before === "lab") { lab -= s.bytes; datasets -= s.bytes; }
      if (before === "home") homeDelta -= s.bytes;
      if (after === "lab") { lab += s.bytes; datasets += s.bytes; }
      if (after === "home") homeDelta += s.bytes;
    });
    const homeBefore = home.used_bytes === undefined ? null : home.used_bytes;
    out.lab_before = volume.used_bytes; out.lab_after = lab; out.datasets_after = datasets;
    out.lab_quota = volume.quota_bytes; out.target = plan.target_bytes;
    out.home_before = homeBefore; out.home_delta = homeDelta;
    out.home_after = homeBefore === null ? null : homeBefore + homeDelta; out.home_quota = home.quota_bytes;
    return out;
  }
  function overlaps(plan, choices) {
    const active = {};
    plan.sets.forEach(function (s) { if (finalLocation(s, choices[s.id] || {}) !== "none") active[s.id] = true; });
    const seen = {}, out = [];
    plan.sets.forEach(function (s) {
      if (!active[s.id]) return;
      (s.overlap || []).forEach(function (o) {
        if (!active[o.with] || o.with === s.id) return;
        const pair = [s.id, o.with].sort(), key = pair[0] + "\n" + pair[1];
        if (seen[key]) return;
        seen[key] = true;
        out.push({ a: pair[0], b: pair[1], patients: o.patients === undefined ? null : o.patients,
          series: o.series === undefined ? null : o.series, same_bytes: o.same_bytes === undefined ? null : o.same_bytes });
      });
    });
    return out;
  }
  function refusals(plan, t) {
    const out = [];
    if (t.unsized.length) {
      out.push(t.unsized.join(", ") + " " + (t.unsized.length > 1 ? "have" : "has") + " no measured size, so the planner refuses " +
        "the fetch or the move: the size rule reads a set's exact size before a byte lands.");
    }
    if (t.to_home.length && (plan.home.used_bytes === null || plan.home.used_bytes === undefined)) {
      out.push("The home's use has not been read yet, so the planner refuses any move to it until a grid word reads it.");
    }
    if (t.lab_after > t.target) {
      out.push("The lab volume would hold " + tb(t.lab_after) + ", over the target of " + tb(t.target) + " by " + tb(t.lab_after - t.target) + ".");
    }
    if (t.lab_after > t.lab_quota) {
      out.push("The lab volume would hold " + tb(t.lab_after) + ", over its quota of " + tb(t.lab_quota) + ": the size rule would refuse the fetch whole.");
    }
    if (t.home_after !== null && t.home_after > t.home_quota) {
      out.push("The home would hold " + tb(t.home_after) + ", over its quota of " + tb(t.home_quota) + ".");
    }
    return out;
  }
  return { tb: tb, isHeld: isHeld, finalLocation: finalLocation, tokens: tokens, selection: selection,
    totals: totals, overlaps: overlaps, refusals: refusals };
})();
"""

UI_JS = r"""
(function () {
  const C = JSON.parse(document.getElementById("constants").textContent);
  let PLAN = JSON.parse(document.getElementById("plan").textContent);
  let choices = {};
  const HOST = window.parent !== window ? window.parent : null;
  const $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function exact(n) { return n === null || n === undefined ? "the feed gives no size" : n.toLocaleString("en-US") + " bytes"; }
  function pct(n, q) { return Math.max(0, Math.min(100, 100 * n / q)); }
  function ageWords(iso) {
    if (!iso) return null;
    const ms = Date.now() - Date.parse(iso);
    if (isNaN(ms)) return null;
    const h = Math.floor(ms / 3600000);
    if (h < 1) return "less than an hour ago";
    if (h < 48) return h + (h === 1 ? " hour ago" : " hours ago");
    return Math.floor(h / 24) + " days ago";
  }
  function ageBadge(iso, verb) {
    const words = ageWords(iso);
    if (!words) return '<span class="badge red">' + verb + ' at no recorded time</span>';
    const days = (Date.now() - Date.parse(iso)) / 86400000;
    return '<span class="badge ' + (days > 7 ? "red" : days > 2 ? "warn" : "") + '" title="' + esc(iso) + '">' + verb + " " + words + "</span>";
  }
  function homeUnread() { return PLAN.home.used_bytes === null || PLAN.home.used_bytes === undefined; }

  function drawDrives(t) {
    const v = PLAN.volume, q = v.quota_bytes, over = t.lab_after > t.target;
    $("lab").innerHTML = "<h3>Lab volume" + ageBadge(v.read_at, "read") + "</h3>" +
      '<div class="band" title="' + esc(exact(v.used_bytes)) + ' used of ' + esc(exact(q)) + '">' +
      '<span class="seg data" style="left:0;width:' + pct(v.datasets_bytes, q) + '%"></span>' +
      '<span class="seg other" style="left:' + pct(v.datasets_bytes, q) + "%;width:" + pct(v.other_bytes, q) + '%"></span>' +
      '<span class="mark" style="left:' + pct(PLAN.target_bytes, q) + '%" title="target ' + esc(exact(PLAN.target_bytes)) + '"></span></div>' +
      '<div class="band after' + (over ? " over" : "") + '" title="after the choices: ' + esc(exact(t.lab_after)) + '">' +
      '<span class="seg" style="left:0;width:' + pct(t.lab_after, q) + '%"></span></div>' +
      '<div class="legend"><span><i style="background:var(--data)"></i>datasets <b title="' + esc(exact(v.datasets_bytes)) + '">' + Model.tb(v.datasets_bytes) + "</b></span>" +
      '<span><i style="background:var(--other)"></i>other <b title="' + esc(exact(v.other_bytes)) + '">' + Model.tb(v.other_bytes) + "</b></span>" +
      '<span>used <b title="' + esc(exact(v.used_bytes)) + '">' + Model.tb(v.used_bytes) + '</b> of <b title="' + esc(exact(q)) + '">' + Model.tb(q) + "</b></span>" +
      '<span><i style="background:var(--target)"></i>target <b title="' + esc(exact(PLAN.target_bytes)) + '">' + Model.tb(PLAN.target_bytes) + "</b></span>" +
      '<span class="' + (over ? "red" : "") + '">after the choices <b title="' + esc(exact(t.lab_after)) + '">' + Model.tb(t.lab_after) + "</b></span></div>";
    const h = PLAN.home, hq = h.quota_bytes;
    let band, legend;
    if (homeUnread()) {
      band = '<div class="band"><span class="empty">not read yet</span></div>';
      legend = '<span>quota <b title="' + esc(exact(hq)) + '">' + Model.tb(hq) + "</b></span><span>nothing can be placed here until a grid word reads its use</span>";
    } else {
      const hover = t.home_after > hq;
      band = '<div class="band" title="' + esc(exact(h.used_bytes)) + ' used of ' + esc(exact(hq)) + '"><span class="seg home" style="left:0;width:' + pct(h.used_bytes, hq) + '%"></span></div>' +
        '<div class="band after' + (hover ? " over" : "") + '" title="after the choices: ' + esc(exact(t.home_after)) + '"><span class="seg" style="left:0;width:' + pct(t.home_after, hq) + '%"></span></div>';
      legend = '<span><i style="background:var(--home)"></i>used <b title="' + esc(exact(h.used_bytes)) + '">' + Model.tb(h.used_bytes) + '</b> of <b title="' + esc(exact(hq)) + '">' + Model.tb(hq) + "</b></span>" +
        '<span class="' + (hover ? "red" : "") + '">after the choices <b title="' + esc(exact(t.home_after)) + '">' + Model.tb(t.home_after) + "</b></span>";
    }
    $("home").innerHTML = "<h3>The owner's home" + (homeUnread() ? '<span class="badge warn">not read yet</span>' : ageBadge(h.read_at, "read")) + "</h3>" + band + '<div class="legend">' + legend + "</div>";
  }

  function drawRequests() {
    const list = PLAN.requests || [];
    if (!list.length) { $("requests").innerHTML = '<p class="muted">No request is pending.</p>'; return; }
    $("requests").innerHTML = '<ul class="notes">' + list.map(function (r) {
      return "<li><a href=\"" + esc(r.url) + '" target="_blank" rel="noopener">#' + esc(r.number) + "</a>: <code>" + esc(r.selection) + "</code></li>";
    }).join("") + "</ul>";
  }

  function radio(name, value, text, checked, disabled, title) {
    return '<label title="' + esc(title || "") + '"><input type="radio" name="' + esc(name) + '" value="' + esc(value) + '"' +
      (checked ? " checked" : "") + (disabled ? " disabled" : "") + "><span>" + esc(text) + "</span></label>";
  }
  function rowFor(s) {
    const c = choices[s.id] || {}, held = Model.isHeld(s);
    const sizeTitle = s.bytes === null || s.bytes === undefined ? "the feed gives no size" : exact(s.bytes) + (s.bytes_known ? ", measured" : ", stated by its source, not measured");
    let choice, place;
    if (held) {
      choice = radio("c-" + s.id, "keep", "keep", (c.action || "keep") !== "remove", false, "leave the set where it is") +
        radio("c-" + s.id, "remove", "remove", c.action === "remove", false, "take the set off the drive: -" + s.id);
    } else if (s.fetchable) {
      choice = radio("c-" + s.id, "keep", "leave", c.action !== "add", false, "do not fetch it") +
        radio("c-" + s.id, "add", "add", c.action === "add", false, "fetch it: +" + s.id);
    } else {
      choice = '<span class="muted" title="the feed says this set cannot be fetched yet: its status is ' + esc(s.status) + ", its reach " + esc(s.reach) + '">no control: ' + esc(s.status) + "</span>";
    }
    if (held || s.fetchable) {
      const at = c.place || (held ? s.location : "lab"), unread = homeUnread();
      place = radio("p-" + s.id, "lab", "lab", at === "lab", false, "on the lab volume") +
        radio("p-" + s.id, "home", "home", at === "home", unread, unread ? "the home's use has not been read yet, so nothing can be placed there" : "on the owner's 4 TB home");
    } else {
      place = '<span class="muted">-</span>';
    }
    const find = (s.name + " " + s.id + " " + s.group + " " + s.status + " " + s.location).toLowerCase();
    return '<tr data-id="' + esc(s.id) + '" data-find="' + esc(find) + '"><td class="set" title="' + esc(s.group + "; licence " + s.licence + "; " + (s.frozen ? "frozen" : "not frozen")) + '">' + esc(s.name) + "<br><code>" + esc(s.id) + "</code></td>" +
      '<td class="opt">' + esc(s.group) + "</td><td>" + esc(s.status) + (s.reach === s.status ? "" : ' <span class="muted">(' + esc(s.reach) + ")</span>") + "</td><td>" + esc(s.location) + "</td>" +
      '<td class="num" title="' + esc(sizeTitle) + '">' + (s.bytes === null || s.bytes === undefined ? '<span class="red">size unknown</span>' : Model.tb(s.bytes) + (s.bytes_known ? "" : ' <span class="muted">stated</span>')) + "</td>" +
      '<td class="opt">' + esc(s.licence) + '</td><td class="opt">' + (s.frozen ? "yes" : "no") + '</td><td class="choice">' + choice + '</td><td class="choice">' + place + "</td></tr>";
  }
  function section(title, sets) {
    if (!sets.length) return "";
    return '<tr class="head" data-head="1"><td colspan="9">' + esc(title) + " (" + sets.length + ")</td></tr>" + sets.map(rowFor).join("");
  }
  function drawTable() {
    const held = PLAN.sets.filter(Model.isHeld), fetchable = PLAN.sets.filter(function (s) { return !Model.isHeld(s) && s.fetchable; });
    const rest = PLAN.sets.filter(function (s) { return !Model.isHeld(s) && !s.fetchable; });
    $("rows").innerHTML = section("On the drives", held) + section("Can be fetched", fetchable) + section("Not fetchable yet", rest);
  }

  function changedIds() {
    const out = {};
    Model.tokens(PLAN, choices).forEach(function (tok) { out[tok.replace(/^[-+]/, "").replace(/@(lab|home)$/, "")] = true; });
    return out;
  }
  function applyFilter() {
    const words = $("filter").value.toLowerCase().split(/\s+/).filter(Boolean), only = $("changed-only").checked, changed = changedIds();
    let shown = 0, headRow = null, headShown = 0;
    Array.prototype.forEach.call($("rows").rows, function (row) {
      if (row.dataset.head) { if (headRow) headRow.hidden = headShown === 0; headRow = row; headShown = 0; return; }
      const text = row.dataset.find, hit = words.every(function (w) { return text.indexOf(w) >= 0; }) && (!only || changed[row.dataset.id]);
      row.hidden = !hit;
      row.classList.toggle("changed", !!changed[row.dataset.id]);
      if (hit) { shown++; headShown++; }
    });
    if (headRow) headRow.hidden = headShown === 0;
    $("shown").textContent = shown + " of " + PLAN.sets.length + " shown";
  }

  function drawTotals(t, refused, pairs) {
    const labOver = t.lab_after > t.target || t.lab_after > t.lab_quota;
    $("t-lab").className = "total" + (labOver ? " over" : "");
    $("t-lab").innerHTML = "<b>Lab volume after the choices:</b> <span title=\"" + esc(exact(t.lab_after)) + '" class="' + (labOver ? "red" : "") + '">' + Model.tb(t.lab_after) + "</span> of a " + Model.tb(t.lab_quota) + " quota, target " + Model.tb(t.target) +
      "; datasets " + Model.tb(t.datasets_after) + "<br>" + t.removed.length + " removed, " + t.added.length + " added, " + t.moved.length + " moved" +
      (t.unsized.length ? ', <span class="red">' + t.unsized.length + " with no size</span>" : "");
    const homeOver = t.home_after !== null && t.home_after > t.home_quota;
    $("t-home").className = "total" + (homeOver || (t.to_home.length && homeUnread()) ? " over" : "");
    $("t-home").innerHTML = "<b>Home after the choices:</b> " + (homeUnread()
      ? '<span class="muted">not read yet</span>' + (t.to_home.length ? ', <span class="red">' + t.to_home.length + " placed here anyway</span>" : "") + "; quota " + Model.tb(t.home_quota)
      : '<span title="' + esc(exact(t.home_after)) + '" class="' + (homeOver ? "red" : "") + '">' + Model.tb(t.home_after) + "</span> of a " + Model.tb(t.home_quota) + " quota; " + t.to_home.length + " placed here");
    const sel = Model.selection(PLAN, choices);
    if (refused.length) {
      $("refusals").innerHTML = '<div class="refusals"><p><b>The planner\'s check would refuse this selection:</b></p>' + refused.map(function (r) { return "<p>" + esc(r) + "</p>"; }).join("") + "</div>";
    } else {
      $("refusals").innerHTML = sel ? '<p class="ok">The planner\'s check would admit this selection; its run opens a request pull request for the owner to merge.</p>' : '<p class="muted">No choice differs from the feed.</p>';
    }
    if (pairs.length) {
      $("overlaps").innerHTML = "<p><b>Overlap among the kept sets:</b></p><ul class=\"notes\">" + pairs.map(function (p) {
        return "<li><code>" + esc(p.a) + "</code> and <code>" + esc(p.b) + "</code> share " + (p.patients === null ? "an unrecorded number of" : p.patients.toLocaleString("en-US")) + " patients and " +
          (p.series === null ? "an unrecorded number of" : p.series.toLocaleString("en-US")) + " series" + (p.same_bytes === null ? "" : ', <span title="' + esc(exact(p.same_bytes)) + '">' + Model.tb(p.same_bytes) + " the same</span>") + "</li>";
      }).join("") + "</ul>";
    } else {
      $("overlaps").innerHTML = '<p class="muted">The feed records no shared patients or series among the kept sets.</p>';
    }
    $("selection").value = sel;
    const apply = $("apply");
    apply.disabled = !sel || refused.length > 0;
    apply.title = !sel ? "nothing to apply: no choice differs from the feed" : refused.length ? "the planner's check would refuse this selection: " + refused[0] : "ask the host to dispatch storage.yml with this selection";
    $("copy").disabled = !sel;
    $("copy").title = sel ? "copy the selection" : "nothing to copy yet";
  }
  function recompute() {
    const t = Model.totals(PLAN, choices);
    drawDrives(t);
    drawTotals(t, Model.refusals(PLAN, t), Model.overlaps(PLAN, choices));
    applyFilter();
  }
  function drawAll() {
    $("built").textContent = PLAN.built_at || "at no recorded time";
    $("built-age").outerHTML = ageBadge(PLAN.built_at, "built").replace('class="badge', 'id="built-age" class="badge');
    drawRequests();
    drawTable();
    recompute();
  }

  function status(text, cls) { $("status").textContent = text; $("status").className = "status " + (cls || ""); }
  function fallback(html) { $("fallback").hidden = false; $("fallback").innerHTML = html; }
  // A sandboxed frame cannot open a link, so the page also asks the page around it to show the link in
  // its own bar (schwingnet.open, the site's convention), once when the fallback appears and again on
  // each click of a link in it.
  function askOpen(href, label) { if (HOST) HOST.postMessage({ type: "schwingnet.open", href: href, label: label }, "*"); }
  $("fallback").addEventListener("click", function (e) {
    const a = e.target && e.target.closest ? e.target.closest("a") : null;
    if (a && a.href) askOpen(a.href, a.textContent);
  });
  function dispatchFallback(why) {
    status("Not dispatched: " + why + ".", "red");
    askOpen(C.workflow_url, "storage.yml on spine-datasets");
    fallback("<p><b>Run it by hand.</b> Open storage.yml on spine-datasets, <a href=\"" + esc(C.workflow_url) + '" target="_blank" rel="noopener">' + esc(C.workflow_url) + "</a>, press Run workflow and paste this into its <code>selection</code> input:</p>" +
      '<code class="paste">' + esc($("selection").value) + "</code><p>The run checks the selection and opens a request pull request, which waits for the owner's merge; nothing is fetched or removed before that.</p>");
  }
  function readFallback(why) {
    status("Not refreshed: " + why + ".", "red");
    askOpen(C.feed_page, "PLAN.json on spine-datasets' branch storage-feed");
    fallback("<p>This page shows the snapshot of the feed built " + esc(PLAN.built_at) + ". The feed itself is PLAN.json on spine-datasets' branch storage-feed, <a href=\"" + esc(C.feed_page) + '" target="_blank" rel="noopener">' + esc(C.feed_page) + "</a>; the site builds this page from it again before each deploy.</p>");
  }
  let timer = null, readId = 0;
  addEventListener("message", function (e) {
    if (!HOST || e.source !== HOST || !e.data || typeof e.data !== "object") return;
    const m = e.data;
    if (m.type === "schwingnet.dispatch.result" && m.label === "storage") {
      clearTimeout(timer);
      if (m.ok) {
        $("fallback").hidden = true;
        status("Dispatched. The run checks the selection and opens a request pull request, which waits for the owner's merge.", "ok");
      } else dispatchFallback(m.error ? String(m.error) : "the host could not dispatch it");
    }
    if (m.type === "schwingnet.read.result" && m.id === "storage-" + readId) {
      clearTimeout(timer);
      if (!m.ok) { readFallback(m.error ? String(m.error) : "the host could not read the feed"); return; }
      let plan = null;
      try { plan = JSON.parse(m.text); } catch (err) { plan = null; }
      if (!plan || plan.format !== C.format || !Array.isArray(plan.sets)) { readFallback("the host's answer was not the feed's format"); return; }
      PLAN = plan;
      const ids = {}; PLAN.sets.forEach(function (s) { ids[s.id] = true; });
      Object.keys(choices).forEach(function (id) { if (!ids[id]) delete choices[id]; });
      $("fallback").hidden = true;
      drawAll();
      status("Refreshed from the feed built " + PLAN.built_at + ".", "ok");
    }
  });
  $("apply").addEventListener("click", function () {
    const sel = $("selection").value;
    if (!sel) return;
    if (!HOST) { dispatchFallback("this page has no host window to dispatch through"); return; }
    $("fallback").hidden = true;
    status("Asking the page's host to dispatch storage.yml ...");
    HOST.postMessage({ type: "schwingnet.dispatch", repo: C.repo, workflow: C.workflow, ref: "main", inputs: { selection: sel }, label: "storage", fallbackUrl: C.workflow_url }, "*");
    clearTimeout(timer);
    timer = setTimeout(function () { dispatchFallback("no answer came within 8 seconds"); }, 8000);
  });
  $("refresh").addEventListener("click", function () {
    if (!HOST) { readFallback("this page has no host window to read through"); return; }
    readId++;
    $("fallback").hidden = true;
    status("Asking the page's host to read the feed ...");
    HOST.postMessage({ type: "schwingnet.read", id: "storage-" + readId, repo: C.repo, path: C.feed_path, ref: C.feed_ref }, "*");
    clearTimeout(timer);
    timer = setTimeout(function () { readFallback("no answer came within 8 seconds"); }, 8000);
  });
  function selectText() {
    const box = $("selection");
    box.focus(); box.select();
    status("Copy is not allowed here, so the selection is highlighted: press Ctrl+C or Cmd+C.");
  }
  $("copy").addEventListener("click", function () {
    const text = $("selection").value;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { status("Copied.", "ok"); }, selectText);
    } else selectText();
  });
  $("rows").addEventListener("change", function (e) {
    const input = e.target;
    if (!input || input.type !== "radio") return;
    const id = input.name.slice(2), key = input.name.charAt(0) === "c" ? "action" : "place";
    choices[id] = choices[id] || {};
    choices[id][key] = input.value;
    recompute();
  });
  $("filter").addEventListener("input", applyFilter);
  $("changed-only").addEventListener("change", applyFilter);
  $("reset").addEventListener("click", function () { choices = {}; drawTable(); recompute(); status(""); $("fallback").hidden = true; });
  drawAll();
})();
"""


def inline_json(data):
    """Data inside a script element: no sequence that could end the element early."""
    return json.dumps(data, sort_keys=True).replace("</", "<\\/")


def page_of(plan):
    constants = {"repo": FEED_REPO, "workflow": WORKFLOW, "workflow_url": WORKFLOW_URL, "feed_page": FEED_PAGE,
                 "feed_path": FEED_PATH, "feed_ref": FEED_REF, "format": FORMAT}
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>The storage panel</title><style>{STYLE}</style></head><body><main>{BODY}</main>\n"
            f'<script type="application/json" id="constants">{inline_json(constants)}</script>\n'
            f'<script type="application/json" id="plan">{inline_json(plan)}</script>\n'
            f"<script>{MODEL_JS}</script>\n<script>{UI_JS}</script></body></html>\n")


# ---------------------------------------------------------------- the picture and the record


LIGHT = {"bg": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "ink3": "#8a8984", "rule": "#e4e3df", "panel": "#f3f1ec",
         "data": "#2a78d6", "other": "#b3b1aa", "target": "#d98c00", "home": "#7a52c7"}
DARK = {"bg": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "ink3": "#8f8e87", "rule": "#34332f", "panel": "#242422",
        "data": "#4a8fe8", "other": "#6c6b66", "target": "#f0b23a", "home": "#a98ae8"}


def svg_rules(c):
    return (f".bg{{fill:{c['bg']}}}.panel{{fill:{c['panel']};stroke:{c['rule']}}}text{{fill:{c['ink2']};font:12px system-ui,sans-serif}}"
            f".head{{fill:{c['ink']};font-weight:600;font-size:13px}}.ink3{{fill:{c['ink3']}}}.data{{fill:{c['data']}}}"
            f".other{{fill:{c['other']}}}.home{{fill:{c['home']}}}.target{{stroke:{c['target']};stroke-width:2}}")


SVG_STYLE = svg_rules(LIGHT) + "@media (prefers-color-scheme:dark){" + svg_rules(DARK) + "}"


def svg_of(plan):
    """The drive-use bands as the snapshot read them: the figure's image where the page cannot show."""
    v, h = plan["volume"], plan["home"]
    width, left, right, bar = 900, 170, 870, 26

    def x(n, quota):
        return left + (right - left) * min(n, quota) / quota

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 190" width="{width}" height="190" role="img" '
             'aria-label="Drive use from spine-datasets\' feed">', f"<style>{SVG_STYLE}</style>",
             f'<rect class="bg" width="{width}" height="190"/>',
             f'<text x="12" y="20" class="head">Drive use from spine-datasets\' feed, built {esc(plan["built_at"])}; the volume read '
             f'{esc(v.get("read_at") or "at no recorded time")}.</text>']
    y = 48
    lines.append(f'<text x="12" y="{y + 18}" class="head">Lab volume</text>')
    lines.append(f'<rect class="panel" x="{left}" y="{y}" width="{right - left}" height="{bar}" rx="4"/>')
    lines.append(f'<rect class="data" x="{left}" y="{y}" width="{x(v["datasets_bytes"], v["quota_bytes"]) - left:.1f}" height="{bar}" rx="4"/>')
    lines.append(f'<rect class="other" x="{x(v["datasets_bytes"], v["quota_bytes"]):.1f}" y="{y}" '
                 f'width="{x(v["used_bytes"], v["quota_bytes"]) - x(v["datasets_bytes"], v["quota_bytes"]):.1f}" height="{bar}"/>')
    tx = x(plan["target_bytes"], v["quota_bytes"])
    lines.append(f'<line class="target" x1="{tx:.1f}" x2="{tx:.1f}" y1="{y - 6}" y2="{y + bar + 6}"/>')
    lines.append(f'<text x="{left}" y="{y + bar + 20}">{tb(v["used_bytes"])} used of {tb(v["quota_bytes"])}: datasets '
                 f'{tb(v["datasets_bytes"])}, other {tb(v["other_bytes"])}; the target is {tb(plan["target_bytes"])}.</text>')
    y = 118
    lines.append(f'<text x="12" y="{y + 18}" class="head">The owner\'s home</text>')
    lines.append(f'<rect class="panel" x="{left}" y="{y}" width="{right - left}" height="{bar}" rx="4"/>')
    if h.get("used_bytes") is None:
        lines.append(f'<text x="{left + 10}" y="{y + 18}" class="ink3">not read yet</text>')
        lines.append(f'<text x="{left}" y="{y + bar + 20}">Quota {tb(h["quota_bytes"])}; nothing is placed here until a grid word reads its use.</text>')
    else:
        lines.append(f'<rect class="home" x="{left}" y="{y}" width="{x(h["used_bytes"], h["quota_bytes"]) - left:.1f}" height="{bar}" rx="4"/>')
        lines.append(f'<text x="{left}" y="{y + bar + 20}">{tb(h["used_bytes"])} used of {tb(h["quota_bytes"])}, read '
                     f'{esc(h.get("read_at") or "at no recorded time")}.</text>')
    lines.append(f'<text x="12" y="182" class="ink3">{len(plan["sets"])} sets in the feed; the interactive page trials which fit under the '
                 f'target and asks for the changes through storage.yml. {COMMAND}</text>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def record_of(plan, digest):
    """The figure's record in the site's convention (tools/textbook_site.py): where it came from, how
    to explore it and how it is drawn again."""
    v = plan["volume"]
    return {
        "id": FIGURE_ID,
        "title": "The storage panel: drive use and the sets that fit under the target",
        "caption": "The lab volume's and the owner's home's use as spine-datasets' feed read them, every set the feed knows "
                   "with its size, licence and state, and the choices (keep, remove, add, place on the lab or the home) that "
                   "build a selection the planner's check admits under the target; the interactive figure trials combinations "
                   "and asks for the changes only through storage.yml, whose run opens a request pull request the owner merges.",
        "chapter": "22",
        "grade": "Reported",
        "status": "current",
        "source": {
            "kind": "script",
            "artifact": None,
            "artifact_url": None,
            "made_by": "tools/storage_panel.py",
            "commit": None,
            "data": [SNAPSHOT.relative_to(ROOT).as_posix(), f"{FEED_REPO} {FEED_PATH} at ref {FEED_REF}"],
            "run": None,
            "notes": f"Drawn from a committed snapshot of {FEED_REPO}'s {FEED_PATH} on its branch {FEED_REF}, built "
                     f"{plan['built_at']} from that repository's records, with the lab volume read {v.get('read_at') or 'at no recorded time'} "
                     f"by the grid's status word; the snapshot's sha256 is {digest}. The sizes are the feed's own, measured where a set "
                     "is frozen and stated by its source otherwise, and the home's use is null until a grid word reads it. "
                     ".github/workflows/docs.yml refreshes the snapshot with the App's read token before each site build and builds "
                     "the page from the committed snapshot when the feed is unreachable; a reading is dated, never a final value, and "
                     "the page shows its age.",
        },
        "feed": {"repo": FEED_REPO, "path": FEED_PATH, "ref": FEED_REF, "format": plan["format"], "built_at": plan["built_at"],
                 "read_at": v.get("read_at"), "sha256": digest, "sets": len(plan["sets"])},
        "explore": [
            {"label": "The script", "href": "tools/storage_panel.py"},
            {"label": "The snapshot of the feed it draws from", "href": SNAPSHOT.relative_to(ROOT).as_posix()},
            {"label": "The feed on its branch", "href": FEED_PAGE},
            {"label": "The workflow the panel dispatches", "href": WORKFLOW_URL},
            {"label": "The size rule", "href": "docs/memory/the-size-rule.md"},
            {"label": "The chapter", "href": "docs/textbook/22-quotas-cost-and-the-budget-of-a-run.md"},
        ],
        "rerun": {"where": "actions", "command": COMMAND,
                  "cost": "CPU, a second: it redraws the page from the committed snapshot, which docs.yml refreshes from the feed before each site build",
                  "needs_owner_word": False},
    }


# ---------------------------------------------------------------- build and check


def load_plan(path):
    raw = Path(path).read_bytes()
    plan = json.loads(raw.decode("utf-8"))
    wrong = validate(plan)
    if wrong:
        raise SystemExit(f"{path}: {wrong}")
    return plan, hashlib.sha256(raw).hexdigest()


def outputs(plan_path):
    plan, digest = load_plan(plan_path)
    return {"storage.html": page_of(plan), "storage.svg": svg_of(plan),
            "storage.json": json.dumps(record_of(plan, digest), indent=1) + "\n"}


def build(plan_path, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files = outputs(plan_path)
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
    print("wrote " + ", ".join(str(out / name) for name in files))
    return 0


def check(plan_path, out):
    out = Path(out)
    stale = [name for name, text in outputs(plan_path).items()
             if not (out / name).exists() or (out / name).read_text(encoding="utf-8") != text]
    if stale:
        print(f"not what the snapshot gives, run {COMMAND}: " + ", ".join(stale))
        return 1
    print("up to date: " + ", ".join(OUTPUTS))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "check"):
        p = sub.add_parser(name)
        p.add_argument("--plan", default=str(SNAPSHOT), help="the snapshot of the feed to draw from")
        p.add_argument("--out", default=str(FOLDER), help="the figure's folder")
    p = sub.add_parser("fetch")
    p.add_argument("--out", default=str(SNAPSHOT), help="where the snapshot is written")
    p.add_argument("--url", default=FEED_URL, help="the contents API address of the feed")
    args = parser.parse_args(argv)
    if args.command == "build":
        return build(args.plan, args.out)
    if args.command == "check":
        return check(args.plan, args.out)
    return fetch(args.out, args.url)


if __name__ == "__main__":
    sys.exit(main())
