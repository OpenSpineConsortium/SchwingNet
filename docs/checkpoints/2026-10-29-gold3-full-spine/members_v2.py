"""Rewrite data/gold3-ct/members.json for rule version 2, from the admission the field test wrote.
Run from the SchwingNet root after `python3 tools/gold3_field.py write`."""
import json, re, sys
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


m["about"] = ("The gold tier 3 CT dataset's members: CT studies whose field holds the whole spine, C2 to the sacrum, "
              "with a person's annotation (the owner's tiers of 2026-10-27; a machine mask never raises a tier), "
              "admitted by the field test of rule version 2 (whole_rule; data/gold3-ct/admission.json). "
              "tools/gold3_ct.py reads this file, builds the dataset's index from it and the files it names, and "
              "holds it to its shape. Confidential, like the rest of SchwingNet: nothing here goes to a public place.")
v1 = m["whole_rule"]
m["whole_rule"] = {
    "version": 2,
    "rule": ("A CT is admitted when its field holds C2 and the top of the sacrum, whatever its masks hold. A level is "
             "drawn at 200 voxels or more. C2 drawn is in view unless the field's top cuts the level below it too; "
             "the sacrum drawn is in view when the field holds 20 mm of it below its top; a sacrum the field's foot cuts "
             "short of that makes the end out when the foot-most level above it is cut too, and a border case "
             "otherwise, as is a sacrum in view beside a level above it that runs on to the field's foot. One "
             "not drawn is placed "
             "from the nearest drawn level by tables measured on the members' own whole spines (the 5th and 95th "
             "percentiles), with 20 mm of S1 asked below the sacrum's top. The field is measured over the column, "
             "and at the image's own edge over the column where a TotalSegmentator grid is padded. A study at neither end clearly "
             "in or out is a border case, silver 3 until a person's look. A level the release does not draw is "
             "completed by a segmenter, kept as a machine mask of its own and never raising a tier; one name "
             "the column skips between levels whose centres stand no farther apart than the study's own spacing "
             "of neighbours allows is a count variant, never a level to add. ENHANCE.PET's "
             "verdicts, each study judged once on its repaired mask where it has one, match version 1's tiers "
             "study for study."),
    "asked": adm["rule"]["asked"],
    "source": "tools/gold3_field.py (the rule, its thresholds and checks); docs/research/gold3-ct/ADMISSION.md (every count); docs/research/gold3-ct/README.md section 2 (why)",
    "previous": v1,
}
m["held"] = {
    "definition": ("A study is held when its CT and its masks are on the grid under the member's canonical root on the "
                   "data root (grid.root) and every one of those files hashes to the sha256 this repository records "
                   "for it. A copy anywhere else (a grid home, the Claude project's files, a public bucket, a "
                   "thread's container) is a copy, readable but not held; a file whose bytes differ from the record "
                   "is not held. A member's grid.held is checked (with the date and the job), unchecked or not_held; "
                   "never true until a grid check has compared the sums."),
    "why": ("Rows name files by sha256, so a study used for truth or training must be the file its facts were read "
            "from; a copy outside the data root may move or be cleaned away. data/sources/<source>.json's reach "
            "held (on the grid now) says the same at a source's level; this is it at a study's."),
    "said": "the owner asked for one definition of held on 2026-10-28 (#443's question, answered at 22:58 UTC)",
}
m["completion"] = {
    "rule": ("The levels from C2 to the sacrum an admitted study's release does not draw (admission.json, complete) "
             "are drawn by SPINEPS from the masks the census already holds on the grid, never re-run and never "
             "TotalSegmentator (the owner's science rule), kept as a machine arm of their own beside the release's "
             "masks, recorded by segmenter, version and sha256, never pooled with the release's masks and never "
             "raising a tier."),
    "state": "waits for one CPU grid job and the owner's word and count; nothing sent",
}
m["auto_anatomist"] = {
    "spines": "VerSe, TotalSegmentator and ENHANCE.PET (the owner, 2026-10-28 23:03 UTC: \"i meant verse+totalsegmentator+PET\")",
    "label": "a mask per vertebral level, named by level; no member carries measurements",
    "recipe": "non-commercial",
    "why": ("data/recipes/non-commercial.json allows open, share-alike and non-commercial with no owner review, so it "
            "takes all three whole (TotalSegmentator open, VerSe share-alike, ENHANCE.PET non-commercial as one); "
            "recommended on the owner's behalf for him to overrule. A commercial network would take TotalSegmentator "
            "alone, with ENHANCE.PET's Leipzig and Careggi only after a per-site split and every class first "
            "confirmed by the owner, and VerSe only under commercial-share-alike after counsel; loosening a class "
            "is the owner's alone."),
}

ep, ve, ts = m["members"]
ep["access"] = "public bucket"
ep["grid"]["held"] = "not_held"
ep["grid"]["held_note"] = ("the masks were read from the public bucket; `fetch aws_enhance_pet_labels` has not run, "
                           "autoPET's CTs are on the grid as FDG-PET-CT-Lesions but no mask is matched to its CT, and "
                           "Leipzig's and Careggi's CTs are not on the grid")

t = tiers("verse")
ve.update({
    "name": "VerSe 19 and 20",
    "rows": "data/gold3-ct/verse/facts.jsonl",
    "rows_made_by": ("bordercall holdings/fullspine_facts.py from the release's expert masks (OSF, MICCAI nodes 923ap and "
                     "b2wxj), in the cloud containers of two threads on 2026-10-28 and 29; FACTS.json beside the rows records where, the "
                     "commit and the check of every mask's grid against its CT's header; series.json maps each series "
                     "to its patient; data/gold3-ct/verse.json keeps the 17 series the records read"),
    "studies_listed": 374, "gold3": t["gold3"], "gold4": 0, "silver3": t["silver3"],
    "tier_per_study": (f"by the field test (rule 2): gold 3 for the {n(t['gold3'])} series admitted, every one provisional "
                       f"while a segmenter adds the sacrum VerSe never draws; silver 3 for the {n(t['silver3'])} others, "
                       f"{n(t['look'])} of them border cases a person's look may admit"),
    "access": "public release (OSF), on the grid as VerSeFusion's copy",
    "persons": f"374 series of 355 patients; the {n(t['gold3'])} admitted series are {n(t['persons'])} patients",
})
ve["persons_by_records"] = [t["persons"], t["persons"]]
ve["grid"] = {
    "root": "/rs/rs_grp_oschome/go2432/data/versefusion/raw/VerSeFusion_data/raw",
    "other_copies": ["${HOME}/VerSeFusion/data/raw"],
    "canonical": "the data root's VerSeFusion copy, by the definition of held; the grid home's copy is another copy",
    "held": "unchecked",
    "held_note": "364 of 374 series are on the grid by the source records; the 10 VerSe'20 series never downloaded (grid/README.md) are not held",
    "pattern": "/rs/rs_grp_oschome/go2432/data/versefusion/raw/VerSeFusion_data/raw/**/*{id}*.nii.gz",
}
ve["caveats"] = [
    "VerSe draws no sacrum: every admitted series is gold 3 provisional until a segmenter's sacrum is added and the field test's placement is confirmed by it.",
    "VerSe's labellers leave a vertebra fused to the sacrum (Castellvi III or IV) undrawn, so a missing L5 is flagged (no_l5), never read as four lumbar.",
    "Five of the 17 series the records read are anomaly holdout persons and two fold 3 persons of the SPINEPS to FleXray route (data/splits/anomaly-holdout.json): carried, flagged, never trained on.",
    "has_T13 in older records is wrong (18 against 6 by the masks).",
    "Where a series is in both releases, verse20's mask is read and verse19's is set beside it (other_release): 99 series, every one with the same grid and the same levels in both.",
    "series.json, from VerSeFusion's demographics, marks 319 series as in VerSe 20, but the release's node b2wxj publishes 313 masks: verse112, verse139, verse141, verse151, verse251 and verse257 have no VerSe 20 mask and are read from verse19.",
]

t = tiers("totalsegmentator")
ts.update({
    "rows": "data/gold3-ct/totalsegmentator/facts.jsonl",
    "rows_made_by": ("bordercall holdings/fullspine_facts.py from the release's masks (Zenodo record 22688904, "
                     "Totalsegmentator_dataset_v300.zip, read by byte ranges), in the thread's container on 2026-10-28; "
                     "FACTS.json beside the rows records where, the commit and the check of every subject's masks "
                     "against its CT's header; subjects.json carries meta.csv's age, institute and split"),
    "studies_listed": 1939, "gold3": t["gold3"], "gold4": 0, "silver3": t["silver3"],
    "tier_per_study": (f"by the field test (rule 2): gold 3 for the {n(t['gold3'])} subjects admitted, {n(t['complete'])} "
                       f"of them provisional while a segmenter adds a level; silver 3 for the {n(t['silver3'])} others "
                       f"with part of the column, {n(t['look'])} of them border cases; {n(t['no_column'])} subjects "
                       "draw no vertebra above the sacrum and have no row. The release's masks are model output refined by hand, "
                       "counted as a person's annotation and flagged"),
    "access": "public release (Zenodo), on the grid as totalsegmentator_v300",
    "persons": f"1,939 subject folders, one person each by release id; the {n(t['gold3'])} admitted are {n(t['persons'])} person keys once byte-identical duplicates share one",
})
ts["persons_by_records"] = [t["persons"], t["gold3"]]
ts["grid"] = {
    "root": "/rs/rs_grp_oschome/go2432/data/totalsegmentator_v300",
    "other_copies": ["${HOME}/data/TotalSegmentator_v3"],
    "canonical": "the data root's totalsegmentator_v300, by the definition of held; the grid home's copy is another copy",
    "held": "unchecked",
    "pattern": "<root>/{id}/ct.nii.gz with <root>/{id}/segmentations/*.nii.gz",
}
ts["scheme"].update({
    "vertebrae": "the release's named files, vertebrae_C1 to vertebrae_L6 and sacrum.nii.gz (v3 ships an L6 file for every subject and no separate S1, which the sacrum holds); no T13",
    "expresses_l6": True,
})
ts["caveats"] = [
    "v3 names an L6 and no T13, so an L6 its masks draw is a candidate and a thirteenth thoracic body cannot be named; a count needs a reader from C2, SPINEPS and VERIDAH, or Hofmann's 70 reads.",
    "286 of the 1,924 subjects meta.csv gives an age for are under 18 at the scan (15 have none), whose unfused S1 can read as a free body: flagged (child), never left out.",
    "A subject whose masks are byte for byte another's is one scan under two ids: its row names duplicate_of and shares the first's person. Only s2107, s2109 and s2110 are; the release's notes count 1,935 distinct scans of 1,939 folders, and s1445 with s1446 and s2093 with s2094 share a grid but not their masks, so they stay apart until their CTs' sums show them one scan.",
    "Some v3 CTs are padded inside their grid with slices that hold no image; the field test takes the plane where the spinal cord and the column stop together as the field's edge there (tools/gold3_field.py, image_planes), from the masks, until a read of the CTs records each image's own extent.",
    "meta.csv's ages are not checked against the spine: s1411, s1532 and s2065 are recorded 21 to 25 with a child's column (flagged small_column), and s1776, s1774 and s1839 are recorded 115, 117 and 118.",
]

text = json.dumps(m, indent=1, ensure_ascii=True) + "\n"
text = re.sub(r"\[\n\s+(-?\d+),\n\s+(-?\d+)\n\s+\]", r"[\1, \2]", text)
MEMBERS.write_text(text)
print({k: tiers(k) for k in ("verse", "totalsegmentator")})
