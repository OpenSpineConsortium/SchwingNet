"""Rewrite data/gold3-ct/members.json for rule version 3, from the admission the field test wrote.
Run from the SchwingNet root after `python3 tools/gold3_field.py write`, on the members file as rule 2
left it; run again, it keeps rule 2 as the previous rule and writes the same file."""
import json, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
MEMBERS = ROOT / "data/gold3-ct/members.json"
m = json.loads(MEMBERS.read_text())
adm = json.loads((ROOT / "data/gold3-ct/admission.json").read_text())


def tiers(member):
    rows = [s for s in adm["studies"] if s["member"] == member and "no_column" not in (s["head"], s["foot"])]
    gold3 = sum(1 for s in rows if s["verdict"] == "admitted")
    return {"rows": len(rows), "gold3": gold3, "silver3": len(rows) - gold3,
            "look": sum(1 for s in rows if s["verdict"] == "look"),
            "complete": sum(1 for s in rows if s["verdict"] == "admitted" and s["complete"]),
            "no_column": sum(1 for s in adm["studies"] if s["member"] == member and "no_column" in (s["head"], s["foot"])),
            "persons": len({s["person"] for s in rows if s["verdict"] == "admitted"})}


def n(x):
    return f"{x:,}"


m["about"] = m["about"].replace("rule version 2", "rule version 3")
v2 = m["whole_rule"] if m["whole_rule"]["version"] == 2 else m["whole_rule"]["previous"]
m["whole_rule"] = {
    "version": 3,
    "rule": ("Rule 2 with the owner's two ends of 2026-10-29: a CT is admitted when its field holds the foot of C2 "
             "and the top of the sacrum, whatever its masks hold. A level is drawn at 200 voxels or more. C2 drawn is "
             "in view unless the field's top cuts the level below it too; one not drawn is in view when the field's "
             "top lies above where C2's foot lies in 95 of 100 spines, counted from the head-most drawn level. The "
             "sacrum drawn is in view however little of it the field holds, a level above it that runs on to the "
             "field's foot flagged (level_past_sacrum_top); one not drawn is in view when the field's foot lies below "
             "where the sacrum's top lies in 95 of 100 spines, from the foot-most drawn level. The tables are "
             "measured on the members' own whole spines (the 5th and 95th percentiles). The field is measured over "
             "the column, and at the image's own edge over the column where a TotalSegmentator grid is padded. A "
             "study at neither end clearly in or out is a border case, silver 3 until a person's look. A level the "
             "release does not draw is completed by a segmenter, kept as a machine mask of its own and never "
             "raising a tier; one name the column skips between levels whose centres stand no farther apart than "
             "the study's own spacing of neighbours allows is a count variant, never a level to add. ENHANCE.PET's "
             "verdicts match version 1's tiers study for study but 1379, whose masks draw no C2 and whose field "
             "holds C2's foot: gold 3 while a segmenter adds C2."),
    "asked": adm["rule"]["asked"],
    "source": "tools/gold3_field.py (the rule, its thresholds and checks); docs/research/gold3-ct/ADMISSION.md (every count); docs/research/gold3-ct/README.md section 2 (why)",
    "previous": v2,
}

ep, ve, ts = m["members"]
ep_rows = [s for s in adm["studies"] if s["member"] == "enhance_pet"]
ep_gold = sum(1 for s in ep_rows if s["verdict"] == "admitted") - ep["gold4"]
ep_whole = sum(1 for s in ep_rows if s["verdict"] == "admitted" and not s["complete"]) - ep["gold4"]
AUTOPET_STUDIES, AUTOPET_PERSONS, REPAIRED = 1014, 900, {"1134", "1283", "1347"}
facts = [json.loads(line) for line in (ROOT / "data/gold3-ct/enhance-pet/facts.jsonl").read_text().splitlines() if line.strip()]
site_of = {r["id"]: r["site"] for r in facts if "repaired_from" not in r}
gold_by_site = Counter(site_of[s["id"]] for s in ep_rows if s["verdict"] == "admitted" and s["id"] not in REPAIRED)
autopet_low = gold_by_site["autoPET"] - (AUTOPET_STUDIES - AUTOPET_PERSONS)
autopet_high = min(gold_by_site["autoPET"], AUTOPET_PERSONS)
unkeyed = gold_by_site["Leipzig"] + gold_by_site["Careggi"]
ep.update({
    "persons_by_records": [autopet_low, autopet_high + unkeyed],
    "persons": (f"autoPET's {n(gold_by_site['autoPET'])} gold 3 studies are {n(autopet_low)} to {n(autopet_high)} persons; "
                f"Leipzig's {n(gold_by_site['Leipzig'])} and Careggi's {n(gold_by_site['Careggi'])} gold 3 studies carry no "
                f"person id, at most {n(unkeyed)} persons; the set is {n(autopet_low)} to {n(autopet_high + unkeyed)} gold 3 persons"),
    "gold3": ep_gold, "silver3": len(ep_rows) - ep_gold - ep["gold4"],
    "tier_per_study": (f"gold 3 for the {n(ep_gold)} the field test admits (rule 3): the {n(ep_whole)} whole by their "
                       f"masks and 1379, provisional while a segmenter adds the C2 its masks do not draw; gold 4 for the "
                       f"3 repaired (1134, 1283, 1347: names moved by a rule the ribs settle, or MOOSE's rerun); "
                       f"silver 3 for the {n(len(ep_rows) - ep_gold - ep['gold4'])} with no C2 in the field"),
})

t = tiers("verse")
ve.update({
    "gold3": t["gold3"], "silver3": t["silver3"],
    "tier_per_study": (f"by the field test (rule 3): gold 3 for the {n(t['gold3'])} series admitted, every one provisional "
                       f"while a segmenter adds the sacrum VerSe never draws; silver 3 for the {n(t['silver3'])} others, "
                       f"{n(t['look'])} of them border cases a person's look may admit"),
    "persons": f"374 series of 355 patients; the {n(t['gold3'])} admitted series are {n(t['persons'])} patients",
})
ve["persons_by_records"] = [t["persons"], t["persons"]]

t = tiers("totalsegmentator")
ts.update({
    "gold3": t["gold3"], "silver3": t["silver3"],
    "tier_per_study": (f"by the field test (rule 3): gold 3 for the {n(t['gold3'])} subjects admitted, {n(t['complete'])} "
                       f"of them provisional while a segmenter adds a level; silver 3 for the {n(t['silver3'])} others "
                       f"with part of the column, {n(t['look'])} of them border cases; {n(t['no_column'])} subjects "
                       "draw no vertebra above the sacrum and have no row. The release's masks are model output refined by hand, "
                       "counted as a person's annotation and flagged"),
    "persons": f"1,939 subject folders, one person each by release id; the {n(t['gold3'])} admitted are {n(t['persons'])} person keys once byte-identical duplicates share one",
})
ts["persons_by_records"] = [t["persons"], t["gold3"]]

text = json.dumps(m, indent=1, ensure_ascii=True) + "\n"
text = re.sub(r"\[\n\s+(-?\d+),\n\s+(-?\d+)\n\s+\]", r"[\1, \2]", text)
MEMBERS.write_text(text)
print({k: tiers(k) for k in ("verse", "totalsegmentator")}, {"enhance_pet": [ep["gold3"], ep["gold4"], ep["silver3"]]})
