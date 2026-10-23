"""The reads a change needs, written as inputs for .github/workflows/synthesis.yml and joined back
into the records.

synth.py plan writes one input per artifact that is new or changed since the stamp (its text and
folder, its README row, its old record, the lines that changed and its cluster's file), one file
per cluster with its members' records for the finders, the numbers table, and the verdict items
that need a reader: each verdict whose quotes its page no longer holds, each passage of an
artifact that gives a settled figure as superseded or open, and each row an earlier run's finder
found whose verdict did not come back. A Claude session in the workflow reads each artifact into
a record and, as the finder, sets it against its cluster and the numbers table;
synth_actions.py batch then puts the finders' candidates beside the verdict items, and every item
gets a skeptic, a re-checker told to overturn the skeptic and a judge on each dispute.
synth.py join puts each record, candidate and verdict in its place, keeping what it replaces,
and refuses an answer that names a person's address. A read that did not come back waits: an
artifact whose record is missing is not stamped, so the next run reads it again, and a verdict
item with no verdict keeps waiting the same way. Nothing here runs Claude.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import extract  # noqa: E402
from render_contradictions2 import number_key, number_verdicts  # noqa: E402

RECORD_KEYS = ("kind", "genre", "date", "date_evidence", "question", "summary", "key_claims", "numbers", "datasets", "tools",
               "models", "decisions", "open_questions", "unsourced_assertions", "stale_markers", "external_sources",
               "cross_references", "confidentiality", "related_titles", "people_by_role", "coverage_notes", "notes")
LISTS = ("key_claims", "numbers", "datasets", "tools", "models", "decisions", "open_questions", "unsourced_assertions",
         "stale_markers", "external_sources", "cross_references", "related_titles", "people_by_role")
FROM_README = ("title", "account", "link", "link_id", "readme_summary")
NUMBER_STRATUM = "Number collisions"
CLUSTER_KINDS = ("contradiction", "stale", "unsourced-shared-claim", "superseded-number", "duplicate-text")
NUMBER_KINDS = ("contradiction", "updated-later", "unit-or-scope-mismatch", "probably-different-quantities")
TO_SKEPTICS = ("contradiction", "updated-later")
CLUSTER_SCALE = ("confirmed", "superseded-by-later", "refuted", "cannot-tell")
NUMBER_SCALE = ("confirmed-contradiction", "updated-later", "same-number-restated", "scope-or-unit-differs",
                "different-quantities", "cannot-tell")
# What one run may read, so a run stays a few sessions and a few hours of the plan's window:
# artifacts a run reads, verdict items it plans before the finders' (the rest wait for the next
# run), and items each skeptic reads. A finder gives at most the candidates FOUND names.
MAX_ARTIFACTS = 3
MAX_ITEMS = 24
BATCH = 12
FOUND = {"cluster": 10, "number": 10, "number_other": 20}
ROW = re.compile(r"^\|\s*(?P<title>[^|]+?)\s*\|\s*\[(?P<folder>[^\]]+)\]\([^)]*\)\s*\|\s*(?P<link>\S+)\s*\|\s*(?P<account>[^|]+?)\s*\|\s*(?P<what>.*?)\s*\|\s*$")


def readme_rows(clone, repo):
    """The artifacts/README.md index of a checkout, in order: each copied artifact's title,
    folder, link, account and summary."""
    rows = []
    path = os.path.join(clone, "artifacts", "README.md")
    for line in open(path, encoding="utf-8"):
        m = ROW.match(line.strip())
        if m:
            link = m.group("link")
            rows.append({"repo": repo, "folder": m.group("folder"), "title": m.group("title"), "account": m.group("account"),
                         "link": link, "link_id": link.rstrip("/").rsplit("/", 1)[-1], "readme_summary": m.group("what")})
    return rows


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def artifact_info(aid, text_dir, clones, records):
    if not aid or "/" not in aid:
        return None
    repo, folder = aid.split("/", 1)
    r = records.get(aid, {})
    return {"id": aid, "title": r.get("title"), "date": r.get("date"), "text": f"{text_dir}/{aid}.txt",
            "folder": os.path.join(clones[repo], "artifacts", folder)}


def cluster_of(clustering, aid):
    for c in clustering["judged"]["clusters"]:
        if aid in c["members"]:
            return c["name"]
    return None


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def listed_rows(aid, M, N):
    """The rows the contradictions page holds on an artifact, so its finder gives none of them
    again."""
    clusters = [{"stratum": c["cluster"], "index": i, "kind": x["kind"], "topic": x.get("topic"),
                 "artifact_a": x["artifact_a"], "artifact_b": x.get("artifact_b") or ""}
                for c in M["clusters"] for i, x in enumerate(c["candidates"]) if aid in (x["artifact_a"], x.get("artifact_b"))]
    numbers = [{"index": j, "kind": x["kind"], "quantity": x["quantity"], "artifact_a": x["artifact_a"], "value_a": x["value_a"],
                "artifact_b": x["artifact_b"], "value_b": x["value_b"]}
               for j, x in enumerate(N["candidates"]) if aid in (x["artifact_a"], x["artifact_b"])]
    return {"cluster_rows": clusters, "number_rows": numbers}


def inventory_inputs(changes, rows, records, clustering, text_dir, clones, out, files, numbers, M, N):
    """One input per new or changed artifact, at most MAX_ARTIFACTS a run; the rest wait. Each
    names its cluster's file, or every cluster's for a new artifact, whose reader chooses one,
    the numbers table and the rows already listed on it, for the finder."""
    clusters = [{"name": c["name"], "description": c["description"], "file": files[c["name"]]} for c in clustering["judged"]["clusters"]]
    by_id = {f"{r['repo']}/{r['folder']}": r for r in rows}
    units = []
    for k, ch in enumerate(changes[:MAX_ARTIFACTS]):
        aid = ch["id"]
        if aid not in by_id:
            raise SystemExit(f"plan refused: {aid} has no row in its artifacts/README.md index")
        cluster = cluster_of(clustering, aid)
        path = os.path.join(out, f"inventory-{k}.json")
        write_json(path, {"artifact": {**{f: by_id[aid][f] for f in FROM_README}, "id": aid,
                                       **{f: artifact_info(aid, text_dir, clones, records)[f] for f in ("text", "folder")}},
                          "before": records.get(aid), "changed": ch.get("hunks"),
                          "cluster": cluster, "cluster_file": files.get(cluster), "clusters": clusters, "numbers": numbers,
                          "listed": listed_rows(aid, M, N)})
        units.append({"file": path, "id": aid, "new": aid not in records, "cluster": cluster})
    return units, [ch["id"] for ch in changes[MAX_ARTIFACTS:]]


def cluster_files(clustering, records, text_dir, clones, out):
    files = {}
    for c in clustering["judged"]["clusters"]:
        members = []
        for aid in c["members"]:
            r = records.get(aid)
            if r:
                members.append({**artifact_info(aid, text_dir, clones, records), "summary": r["summary"],
                                "key_claims": [x["claim"] for x in r["key_claims"]],
                                "numbers": [{k: n.get(k) for k in ("value", "unit", "n", "context")} for n in r["numbers"]]})
        path = os.path.join(out, f"cluster-{slug(c['name'])}.json")
        write_json(path, {"name": c["name"], "description": c["description"], "members": members})
        files[c["name"]] = path
    return files


def numbers_table(records, out):
    """Every figure of every record, one to a line, so a finder's search finds a figure with its
    artifact and context."""
    path = os.path.join(out, "numbers-table.json")
    rows = [{"id": aid, **{k: n.get(k) for k in ("value", "unit", "n", "context")}} for aid, r in records.items() for n in r["numbers"]]
    with open(path, "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n]\n")
    return path


def stale_item(row, M, N, nv, info):
    stratum, index = row["row"].rsplit("|", 1)
    index = int(index)
    if stratum == NUMBER_STRATUM:
        x = N["candidates"][index]
        v = nv[number_key(x)]
        base = {"quantity": x["quantity"], "value_a": x["value_a"], "value_b": x["value_b"]}
    else:
        c = next(c for c in M["clusters"] if c["cluster"] == stratum)
        x, v = c["candidates"][index], c["verdicts"][index]
        base = {"kind": x["kind"], "topic": x.get("topic"), "statement_a": x.get("statement_a"), "statement_b": x.get("statement_b")}
    return {"key": f"stale:{stratum}|{index}", "stratum": stratum, "index": index, **base,
            "a": info(x["artifact_a"]), "b": info(x.get("artifact_b")), "quote_a": x["quote_a"], "quote_b": x.get("quote_b"),
            "earlier": v, "why": f"the verdict's two quotes were found as {' and '.join(row['was'])} when it was stamped and are found"
                                 f" as {' and '.join(row['now'])} now: a page it rests on has changed since it was read"}


def concept_item(chk, concept, info):
    """A passage of an artifact that gives a settled figure as superseded or open, set against
    the side of the figure's own verdict that carries the other value."""
    status = "superseded" if chk["outcome"] == "superseded" else "open"
    side = next((v["side"] for v in concept["values"] if v["status"] == ("current" if status == "superseded" else "open")
                 and v["figure"] not in chk["value"].replace(",", "")), "a")
    k = 0 if side == "a" else 1
    return {"key": f"concept:{chk['key']}", "stratum": NUMBER_STRATUM, "index": None, "quantity": concept["quantity"],
            "kind": "updated-later" if status == "superseded" else "contradiction",
            "a": info(concept["artifacts"][k]), "b": info(chk["source"]),
            "value_a": ", ".join(v["figure"] + ("%" if v["percent"] else "") for v in concept["values"] if v["side"] == side),
            "value_b": chk["value"], "quote_a": concept["quotes"][k], "quote_b": chk["text"],
            "why": f"a concept check: line {chk['line']} of {chk['source']} gives {chk['value']}, which number collision"
                   f" {concept['row']} ({concept['verdict']}) carries as {status}"}


def unread_rows(M, N):
    """The rows an earlier run's finder found whose verdict did not come back, as stratum|index:
    a cluster candidate carrying a delta mark with no verdict, and a number collision of a kind
    a skeptic reads carrying one with none."""
    nv = number_verdicts(N, M.get("numbers_extra", []))
    rows = [f"{c['cluster']}|{i}" for c in M["clusters"] for i, (x, v) in enumerate(zip(c["candidates"], c["verdicts"]))
            if v is None and x.get("delta")]
    return rows + [f"{NUMBER_STRATUM}|{j}" for j, x in enumerate(N["candidates"])
                   if x.get("delta") and x["kind"] in TO_SKEPTICS and number_key(x) not in nv]


def unread_item(row, M, N, info):
    stratum, index = row.rsplit("|", 1)
    index = int(index)
    if stratum == NUMBER_STRATUM:
        x = N["candidates"][index]
        base = {k: x.get(k) for k in ("quantity", "kind", "value_a", "value_b")}
    else:
        x = next(c for c in M["clusters"] if c["cluster"] == stratum)["candidates"][index]
        base = {k: x.get(k) for k in ("kind", "topic", "statement_a", "statement_b", "why_it_matters")}
    return {"key": f"unread:{row}", "stratum": stratum, "index": index, **base, "a": info(x["artifact_a"]),
            "b": info(x.get("artifact_b")), "quote_a": x["quote_a"], "quote_b": x.get("quote_b"),
            "why": f"found by a finder on {x['delta']['date']}, whose run gave it no verdict"}


def plan(out, changes, stale, concept_checks, unread, concepts, records, rows, clustering, M, N, text_dir, clones, date):
    """Write the workflow's inputs and args.json, and say what the run will read. The verdict
    items past MAX_ITEMS wait for a later run, as the artifacts past MAX_ARTIFACTS do."""
    os.makedirs(out, exist_ok=True)
    info = lambda aid: artifact_info(aid, text_dir, clones, records)  # noqa: E731
    nv = number_verdicts(N, M.get("numbers_extra", []))
    by_id = {c["id"]: c for c in concepts}
    items = [stale_item(r, M, N, nv, info) for r in stale]
    items += [concept_item(c, by_id[c["concept"]], info) for c in concept_checks if not c["source"].startswith(("notes:", "registry:"))]
    items += [unread_item(r, M, N, info) for r in unread]
    files = cluster_files(clustering, records, text_dir, clones, out)
    numbers = numbers_table(records, out)
    units, waiting = inventory_inputs(changes, rows, records, clustering, text_dir, clones, out, files, numbers, M, N)
    path = os.path.join(out, "items.json")
    write_json(path, {"items": items[:MAX_ITEMS]})
    paths = {aid: info(aid) for aid in records}
    paths.update({u["id"]: info(u["id"]) for u in units})
    args = {"date": date, "inventory": units, "waiting": waiting, "items": path,
            "items_waiting": [it["key"] for it in items[MAX_ITEMS:]], "clusters": files, "numbers": numbers,
            "paths": paths, "batch": BATCH, "found": FOUND}
    write_json(os.path.join(out, "args.json"), args)
    return args


# The join.

# The shapes of a credential, assembled from pieces as tools/check_docs.py's are, so this file
# never matches its own patterns: a session that read one somewhere has its answer refused.
CREDENTIAL_RE = re.compile("|".join(("sk-" + "ant-" + r"[A-Za-z0-9_-]{20,}", "gh" + r"[pousr]_[A-Za-z0-9]{30,}",
                                     "github_" + r"pat_[A-Za-z0-9_]{30,}", "-----BEGIN " + r"[A-Z ]*" + "PRIVATE KEY")))
PERSONAL = (extract.EMAIL_RE, extract.PHONE_RE, CREDENTIAL_RE)


def personal_problem(data):
    """Why an answer may not be kept, where it holds what the folder's rule keeps out (an
    e-mail address, a phone number or the shape of a credential), or None."""
    text = json.dumps(data, ensure_ascii=False)
    for pattern in PERSONAL:
        m = pattern.search(text)
        if m:
            return f"it holds what the folder's rule keeps out (at character {m.start()})"
    return None


def record_problem(rec):
    """What keeps a record from its place, or None: a missing field, or a list that is not one."""
    missing = [k for k in RECORD_KEYS if k not in rec]
    if missing:
        return f"the record lacks {missing}"
    bad = [k for k in LISTS if not isinstance(rec[k], list)]
    return f"{bad} of the record are not lists" if bad else None


def left_out(unit, answer, clusters):
    """Why an artifact's answer cannot be joined, or None: no record came back, the record
    does not hold together, or a new artifact's reader chose no cluster there is."""
    rec = (answer or {}).get("record")
    if not isinstance(rec, dict):
        return "no record came back"
    why = record_problem(rec) or personal_problem(rec) or personal_problem(answer.get("changed"))
    if not why and unit["new"] and answer.get("cluster") not in clusters:
        why = f"its reader chose no cluster of the {len(clusters)} ({answer.get('cluster')!r})"
    return why


def results_by_label(folder):
    """The answers in a folder, by label: each file holds one session's answer as
    {"label": ..., "result": ...}, written by synth_actions.py answer."""
    out = {}
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if name.endswith(".json"):
            entry = load_json(os.path.join(folder, name))
            if isinstance(entry, dict) and entry.get("label") and entry.get("result") is not None:
                out[entry["label"]] = entry["result"]
    return out


def readme_order(rows):
    return {f"{r['repo']}/{r['folder']}": i for i, r in enumerate(rows)}


def join_inventory(args, found, inventory, history, clustering, rows, date):
    """Each artifact's new record in its place in the README order, the record it replaces kept
    in inventory-history.json, and a new artifact added to the cluster its reader chose. An
    artifact whose record did not come back, or cannot be placed, is left out, with why, and is
    read again by the next run, since its tree is not stamped."""
    by_id = {f"{r['repo']}/{r['folder']}": r for r in inventory["artifacts"]}
    clusters = {c["name"]: c for c in clustering["judged"]["clusters"]}
    readme = {f"{r['repo']}/{r['folder']}": r for r in rows}
    read, left = [], {}
    for k, unit in enumerate(args["inventory"]):
        aid, answer = unit["id"], found.get(f"inventory:{k}")
        why = left_out(unit, answer, clusters)
        if why:
            left[aid] = why
            continue
        rec = answer["record"]
        repo, folder = aid.split("/", 1)
        new = {"repo": repo, "folder": folder, **{f: readme[aid][f] for f in FROM_README}, **{k2: rec[k2] for k2 in RECORD_KEYS},
               "read_on": date, **({"changed": answer.get("changed")} if aid in by_id else {})}
        if aid in by_id:
            history.append({"id": aid, "replaced_on": date, "record": by_id[aid]})
        else:
            clusters[answer["cluster"]]["members"].append(aid)
            clustering["judged"].setdefault("placed_later", []).append(
                {"id": aid, "cluster": answer["cluster"], "date": date, "why": answer.get("cluster_why", "")})
        by_id[aid] = new
        read.append(aid)
    order = readme_order(rows)
    inventory["artifacts"] = sorted(by_id.values(), key=lambda r: order.get(f"{r['repo']}/{r['folder']}", len(order)))
    return read, left


def scale_of(stratum):
    return NUMBER_SCALE if stratum == NUMBER_STRATUM else CLUSTER_SCALE


def entries(found, label, field, keys):
    """A session's entries by key, only for the keys its input gave it, so an answer about
    another batch's item is never taken."""
    return {e["key"]: e for e in (found.get(label) or {}).get(field, []) if isinstance(e, dict) and e.get("key") in keys}


def disputed(skeptic, recheck):
    """The keys whose re-checker overturned the skeptic's verdict or its hint."""
    return sorted(k for k, r in recheck.items() if k in skeptic and not (r.get("holds") and r.get("hint_ok")))


def final_verdicts(batches, items, found):
    """Each verdict item's verdict: the skeptic's where the re-checker kept it and its hint,
    else the judge's ruling; with, for each item that has none, why. A verdict off its item's
    scale is no verdict."""
    final, missing = {}, {}
    for b, unit in enumerate(batches):
        keys = set(unit["keys"])
        skeptic = entries(found, f"skeptic:{b}", "items", keys)
        recheck = entries(found, f"recheck:{b}", "items", set(skeptic))
        ruling = entries(found, f"judge:{b}", "rulings", set(disputed(skeptic, recheck)))
        for key in sorted(keys):
            r = recheck.get(key)
            if key not in skeptic:
                missing[key] = "the skeptic gave no verdict"
            elif not r:
                missing[key] = "the re-checker did not read it"
            elif r.get("holds") and r.get("hint_ok"):
                final[key] = {**skeptic[key], "read": ["skeptic", "re-checker"]}
            elif key in ruling:
                final[key] = {**ruling[key], "read": ["skeptic", "re-checker", "judge"]}
            else:
                missing[key] = "disputed, and the judge gave no ruling"
            if key in final and final[key].get("verdict") not in scale_of(items[key]["stratum"]):
                missing[key] = f"its verdict {final.pop(key).get('verdict')!r} is not on its scale"
    return final, missing


def verdict_fields(item, v):
    keep = ("verdict", "quote_a", "quote_b", "explanation", "resolution_hint")
    sides = {"artifact_a": (item.get("a") or {}).get("id"), "artifact_b": (item.get("b") or {}).get("id")}
    if item["stratum"] == NUMBER_STRATUM:
        return {"quantity": item["quantity"], **sides, "value_a": item["value_a"], "value_b": item["value_b"], **{k: v.get(k, "") for k in keep}}
    return {"kind": item["kind"], "topic": item.get("topic"), **sides, **{k: v.get(k, "") for k in keep}}


def delta_mark(item, v, date):
    mark = {"date": date, "read": v["read"], "why": item["why"]}
    if v.get("sided_with"):
        mark["sided_with"] = v["sided_with"]
    if item.get("earlier"):
        mark["earlier"] = item["earlier"]
    return mark


def pair(a, b):
    return "|".join(sorted([a, b]))


def new_number_row(it, date, unread=None):
    return {"quantity": it["quantity"], "artifact_a": it["a"]["id"], "value_a": it["value_a"], "quote_a": it["quote_a"],
            "artifact_b": it["b"]["id"], "value_b": it["value_b"], "quote_b": it["quote_b"], "kind": it["kind"],
            "why": it.get("reader_why") or it["why"], "pair": pair(it["a"]["id"], it["b"]["id"]),
            "delta": {"date": date, **({"unread": unread} if unread else {})}}


def new_cluster_row(it, date, unread=None):
    return ({k: it.get(k) for k in ("kind", "topic", "statement_a", "quote_a", "statement_b", "quote_b")}
            | {"artifact_a": it["a"]["id"], "artifact_b": (it.get("b") or {}).get("id") or "",
               "why_it_matters": it.get("why_it_matters", ""), "delta": {"date": date, **({"unread": unread} if unread else {})}})


def join_verdicts(items, final, missing, M, N, date):
    """Each verdict in its row: a stale or unread one in place of the row's verdict, a concept
    check's or a finder's as a new row at the end of its list, so no row number moves. A
    finder's candidate with no verdict is added as a row with none, which the next run reads; a
    planned item with none waits. Returns how many were placed, the keys already rows, the keys
    that wait and the keys added as rows with no verdict."""
    clusters = {c["cluster"]: c for c in M["clusters"]}
    extras = M.setdefault("numbers_extra", [])
    rows = {number_key(x) for x in N["candidates"]}
    placed, already, waiting, unread = 0, [], [], []
    for key, it in sorted(items.items()):
        v = final.get(key)
        if v is not None and personal_problem(v):
            missing[key], v = f"its verdict was not kept: {personal_problem(v)}", None
        if v is None and not key.startswith("new:"):
            waiting.append(key)
            continue
        verdict = {**verdict_fields(it, v), "delta": delta_mark(it, v, date)} if v is not None else None
        if it["stratum"] == NUMBER_STRATUM:
            if it["index"] is None:
                row = new_number_row(it, date, None if verdict else missing.get(key))
                if number_key(row) in rows:
                    already.append(key)
                    continue
                rows.add(number_key(row))
                N["candidates"].append(row)
                if verdict:
                    extras.append(verdict)
            else:
                k = number_key(N["candidates"][it["index"]])
                at = next((j for j, e in enumerate(extras) if number_key(e) == k), None)
                if at is None:
                    extras.append(verdict)
                else:
                    extras[at] = verdict
        else:
            c = clusters[it["stratum"]]
            if it["index"] is None:
                c["candidates"].append(new_cluster_row(it, date, None if verdict else missing.get(key)))
                c["verdicts"].append(verdict)
            else:
                c["verdicts"][it["index"]] = verdict
                c["candidates"][it["index"]].get("delta", {}).pop("unread", None)
        if verdict:
            placed += 1
        else:
            unread.append(key)
    return {"placed": placed, "already": already, "waiting": waiting, "unread": unread}


def known_ids(args):
    return set(args["paths"])


def candidate_problem(x, aid, known, kinds, number):
    """Why a finder's candidate cannot be read, or None."""
    if x.get("kind") not in kinds:
        return f"its kind {x.get('kind')!r} is not one of {list(kinds)}"
    a, b = x.get("artifact_a"), x.get("artifact_b") or ""
    if a not in known or (b and b not in known) or (number and not b):
        return f"it names an artifact the run does not know ({a!r}, {b!r})"
    if aid not in (a, b):
        return f"neither side is {aid}, the artifact its finder read"
    if not (x.get("quote_a") or "").strip():
        return "it quotes nothing from its first artifact"
    return None


def joined_units(args, found):
    """The artifacts whose record the join will take, by their index in the plan, each with
    its cluster: a changed artifact's own, a new one's as its reader chose."""
    names = set(args["clusters"])
    out = {}
    for k, unit in enumerate(args["inventory"]):
        answer = found.get(f"inventory:{k}")
        if not left_out(unit, answer, names):
            out[k] = unit.get("cluster") or answer.get("cluster")
    return out


def found_items(args, found):
    """The candidates the finders found, keyed for the skeptics: each cluster candidate, and
    each number candidate of a kind a skeptic reads, with both artifacts' paths; and each
    candidate dropped, with why. A candidate of an artifact whose record will not be joined,
    or past its finder's limits, is dropped the same way."""
    out, dropped = [], []
    known, paths, joined = known_ids(args), args["paths"], joined_units(args, found)
    side = lambda x: {"a": paths[x["artifact_a"]], "b": paths.get(x.get("artifact_b") or "")}  # noqa: E731
    for k, unit in enumerate(args["inventory"]):
        result, aid = found.get(f"candidates:{k}") or {}, unit["id"]
        about = f"found by the finder that read {aid} on {args['date']}"
        for n, x in enumerate(result.get("cluster_candidates", [])):
            why = ("its artifact's record is not joined" if k not in joined
                   else candidate_problem(x, aid, known, CLUSTER_KINDS, False)
                   or (f"past the finder's {FOUND['cluster']}" if n >= FOUND["cluster"] else None))
            if why:
                dropped.append({"key": f"new:{aid}:cluster:{n}", "why": why})
            else:
                out.append({**x, "key": f"new:{aid}:cluster:{n}", "stratum": joined[k], "index": None, **side(x), "why": about})
        to_skeptics = 0
        for n, x in enumerate(result.get("number_candidates", [])):
            why = "its artifact's record is not joined" if k not in joined else candidate_problem(x, aid, known, NUMBER_KINDS, True)
            if not why and x["kind"] in TO_SKEPTICS:
                to_skeptics += 1
                if to_skeptics > FOUND["number"]:
                    why = f"past the finder's {FOUND['number']} of the kinds a skeptic reads"
            if why:
                dropped.append({"key": f"new:{aid}:number:{n}", "why": why})
            elif x["kind"] in TO_SKEPTICS:
                out.append({**x, "key": f"new:{aid}:number:{n}", "stratum": NUMBER_STRATUM, "index": None, **side(x),
                            "reader_why": x.get("why", ""), "why": about})
    return out, dropped


def kept_numbers(args, found, N, date):
    """The finders' number candidates of a kind no skeptic reads, added as rows with no verdict,
    as the first sweep's were; one that is a row already, or that cannot be read, is left out."""
    rows = {number_key(x) for x in N["candidates"]}
    known, added, joined = known_ids(args), 0, joined_units(args, found)
    for k, unit in enumerate(args["inventory"]):
        if k not in joined:
            continue
        others = [x for x in (found.get(f"candidates:{k}") or {}).get("number_candidates", []) if x.get("kind") not in TO_SKEPTICS]
        for x in others[:FOUND["number_other"]]:
            if candidate_problem(x, unit["id"], known, NUMBER_KINDS, True):
                continue
            row = {**{f: x[f] for f in ("quantity", "artifact_a", "value_a", "quote_a", "artifact_b", "value_b", "quote_b", "kind", "why")},
                   "pair": pair(x["artifact_a"], x["artifact_b"]), "delta": {"date": date}}
            if number_key(row) not in rows:
                rows.add(number_key(row))
                N["candidates"].append(row)
                added += 1
    return added
