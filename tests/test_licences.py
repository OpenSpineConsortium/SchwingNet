"""tools/licences.py: the classes a licence line is read into, the repository's facts and recipes
holding together, and the provenance record a run writes from its catalog, cut by a recipe or not."""

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("licences", ROOT / "tools" / "licences.py")
licences = importlib.util.module_from_spec(spec)
sys.modules["licences"] = licences
spec.loader.exec_module(licences)

# The few tables of the catalog (tools/catalog.py, SCHEMA) that the licence tool reads or cuts.
SCHEMA = """
CREATE TABLE source (source TEXT PRIMARY KEY);
CREATE TABLE shard (name TEXT PRIMARY KEY, source TEXT);
CREATE TABLE person (person TEXT PRIMARY KEY, source TEXT, part TEXT);
CREATE TABLE item (sha256 TEXT, shard TEXT, source TEXT, person TEXT, part TEXT);
CREATE TABLE label (item TEXT, shard TEXT, level TEXT);
CREATE TABLE embedding (item TEXT, model TEXT);
"""


def make_catalog(path, frames):
    """A catalog whose frames are (source, person, part) triples, each one shard per source."""
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    for source in sorted({f[0] for f in frames}):
        db.execute("INSERT INTO source VALUES (?)", (source,))
        db.execute("INSERT INTO shard VALUES (?, ?)", (f"{source}-shard", source))
    for number, (source, person, part) in enumerate(frames):
        sha = f"{number:064x}"
        db.execute("INSERT OR IGNORE INTO person VALUES (?, ?, ?)", (person, source, part))
        db.execute("INSERT INTO item VALUES (?, ?, ?, ?, ?)", (sha, f"{source}-shard", source, person, part))
        db.execute("INSERT INTO label VALUES (?, ?, 'L3')", (sha, f"{source}-shard"))
        db.execute("INSERT INTO embedding VALUES (?, 'm')", (sha,))
    db.commit()
    db.close()


FACTS = {
    "aliases": {"aariz": "aariz_cephalograms"},
    "sources": {
        key: {"licence": text, "class": cls, **licences.terms_of(cls), "reviewed": reviewed, "note": ""}
        for key, text, cls, reviewed in (
            ("aariz_cephalograms", "CC BY 4.0", "open", "owner 2026-10-23"),
            ("carmlspine", "CC BY 4.0", "open", "rule"),
            ("lumos", "CC BY-NC 4.0", "non-commercial", "rule"),
            ("vindr_spinexr", "PhysioNet Restricted Health Data License", "agreement", "rule"),
        )
    },
}
RECIPES = {
    "commercial": {"name": "commercial", "allow": ["open"], "reviewed_only": True, "why": "sold"},
    "non-commercial": {"name": "non-commercial", "allow": ["open", "share-alike", "non-commercial"], "reviewed_only": False, "why": "shared"},
}


class TheRule(unittest.TestCase):
    def test_the_strictest_reading_of_a_line_is_its_class(self):
        cases = {
            "CC BY 4.0": "open",
            "US government work, public domain (NCHS)": "open",
            "CC BY-SA 4.0": "share-alike",
            "CC BY-NC 4.0": "non-commercial",
            "Creative Commons Attribution Non Commercial 4.0 International": "non-commercial",
            "labels CC BY-NC-SA 4.0; the CT images CC BY 3.0 (TCIA)": "non-commercial",
            "CC BY 4.0 by one reading, non-commercial by another; to confirm on the page": "non-commercial",
            "a data use agreement (non-commercial)": "agreement",
            "PhysioNet Restricted Health Data License 1.5.0": "agreement",
            "Kaggle competition rules (non-commercial)": "agreement",
            "CC BY 4.0 (the tracks); README.rtf CC BY-ND": "no-derivatives",
            "CC BY-NC-ND 4.0": "no-derivatives",
            "not recorded": "unknown",
            "CC BY 4.0 (to confirm on the page)": "unknown",
            "IEEE DataPort open access": "unknown",
            "Open-i (NLM), open, no agreement; the FAQ's terms to confirm": "unknown",
            "Zenodo, open (the held record of the same authors is CC BY 4.0)": "unknown",
            "mixed: CC BY (Bern, PMC), unlicensed re-encodes (YouTube)": "unknown",
            "": "unknown",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(licences.classify(text), expected)

    def test_a_class_says_what_it_allows(self):
        self.assertEqual(licences.terms_of("open"), {"commercial": "yes", "derivatives": "yes"})
        self.assertEqual(licences.terms_of("non-commercial"), {"commercial": "no", "derivatives": "yes"})
        self.assertEqual(licences.terms_of("no-derivatives"), {"commercial": "no", "derivatives": "no"})
        self.assertEqual(licences.terms_of("unknown"), {"commercial": "unknown", "derivatives": "unknown"})

    def test_only_the_owner_may_read_a_line_more_permissively_than_the_rule(self):
        entry = {"licence": "CC BY 4.0 (to confirm on the page)", "class": "open", **licences.terms_of("open"), "reviewed": "rule"}
        self.assertTrue(any("only the owner" in p for p in licences.entry_problems("x", entry, entry["licence"])))
        entry["reviewed"] = "owner 2026-10-23"
        self.assertEqual(licences.entry_problems("x", entry, entry["licence"]), [])
        stricter = {"licence": "CC BY 4.0", "class": "agreement", **licences.terms_of("agreement"), "reviewed": "rule"}
        self.assertEqual(licences.entry_problems("x", stricter, "CC BY 4.0"), [])

    def test_a_changed_line_is_proposed_again_and_the_owners_reading_otherwise_kept(self):
        kept = {"licence": "CC BY 4.0", "class": "agreement", **licences.terms_of("agreement"), "reviewed": "owner 2026-10-23", "note": ""}
        facts = {"aliases": {}, "sources": {"a": kept, "b": dict(kept)}}
        updated, changed = licences.proposed_facts(facts, {"a": "CC BY 4.0", "b": "CC BY-NC 4.0", "c": "not recorded"})
        self.assertEqual(changed, ["b", "c"])
        self.assertEqual(updated["sources"]["a"], kept)
        self.assertEqual((updated["sources"]["b"]["class"], updated["sources"]["b"]["reviewed"]), ("non-commercial", "rule"))


class TheRepository(unittest.TestCase):
    def test_every_dataset_has_an_entry_and_the_page_is_current(self):
        facts = licences.read_json(licences.FACTS)
        self.assertEqual(licences.problems(facts, licences.licence_lines(), licences.load_recipes()), [])
        self.assertEqual(licences.PAGE.read_text(encoding="utf-8"), licences.render(facts, licences.load_recipes()))

    def test_every_registry_source_resolves_to_an_entry(self):
        facts = licences.read_json(licences.FACTS)
        for path in sorted(licences.REGISTRY.glob("*.json")):
            with self.subTest(source=path.stem):
                self.assertIsNotNone(licences.entry_for(facts, path.stem)[1])

    def test_no_recipe_takes_an_unknown_licence(self):
        self.assertIn("unknown", licences.recipe_problems("x", {"name": "x", "allow": ["unknown"], "reviewed_only": False, "why": "y"})[0])
        for name, recipe in licences.load_recipes().items():
            self.assertNotIn("unknown", recipe["allow"], name)


class TheRunRecord(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.catalog = self.tmp / "catalog.sqlite"
        make_catalog(self.catalog, [
            ("aariz", "aariz:1", "train"), ("aariz", "aariz:2", "validation"),
            ("carmlspine", "carmlspine:1", "train"),
            ("lumos", "lumos:1", "train"), ("lumos", "lumos:1", "train"),
            ("vindr_spinexr", "vindr:1", "test"),
        ])

    def test_the_run_is_as_strict_as_what_it_trained_on_and_a_test_source_is_only_listed(self):
        record = licences.provenance(self.catalog, FACTS, RECIPES)
        rows = {row["source"]: row for row in record["sources"]}
        self.assertEqual(rows["aariz"]["inventory"], "aariz_cephalograms")
        self.assertEqual(rows["aariz"]["frames"], {"train": 1, "validation": 1})
        self.assertEqual((rows["lumos"]["frames"], rows["lumos"]["persons"]), ({"train": 2}, {"train": 1}))
        self.assertEqual(record["run_class"], "non-commercial")
        self.assertEqual(record["commercial_use"], "no")
        self.assertEqual(record["fits_recipes"], ["non-commercial"])
        self.assertEqual(rows["aariz"]["recipes"], ["commercial", "non-commercial"])
        self.assertEqual(rows["carmlspine"]["recipes"], ["non-commercial"], "commercial takes only the owner's reading")
        self.assertIsNone(record["recipe"])
        self.assertEqual(record["unclassified"], [])

    def test_a_source_with_no_entry_is_unclassified_and_the_run_unknown(self):
        make_catalog(self.tmp / "other.sqlite", [("nowhere", "n:1", "train")])
        record = licences.provenance(self.tmp / "other.sqlite", FACTS, RECIPES)
        self.assertEqual((record["unclassified"], record["run_class"], record["commercial_use"]), (["nowhere"], "unknown", "unknown"))

    def test_a_catalog_cut_by_a_recipe_holds_only_its_sources_and_says_so(self):
        cut = self.tmp / "cut.sqlite"
        facts_path, recipes_dir = self.tmp / "licences.json", self.tmp / "recipes"
        facts_path.write_text(json.dumps(FACTS), encoding="utf-8")
        recipes_dir.mkdir()
        for name, recipe in RECIPES.items():
            (recipes_dir / f"{name}.json").write_text(json.dumps(recipe), encoding="utf-8")
        saved = licences.FACTS, licences.RECIPES
        licences.FACTS, licences.RECIPES = facts_path, recipes_dir
        try:
            kept, dropped = licences.derive(self.catalog, "commercial", cut)
            with self.assertRaises(licences.LicenceError):
                licences.run_provenance(self.catalog, "commercial")
            record = licences.run_provenance(cut, "commercial")
            licences.write_provenance(self.tmp / "run", record)
        finally:
            licences.FACTS, licences.RECIPES = saved
        self.assertEqual((kept, dropped), (["aariz"], ["carmlspine", "lumos", "vindr_spinexr"]))
        self.assertEqual(record["recipe"]["name"], "commercial")
        self.assertEqual(record["recipe"]["parent_catalog_sha256"], licences.sha256_of(self.catalog))
        self.assertEqual((record["run_class"], record["commercial_use"], record["fits_recipes"]), ("open", "yes", ["commercial", "non-commercial"]))
        db = sqlite3.connect(cut)
        left = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("item", "label", "embedding", "person", "shard", "source")}
        db.close()
        self.assertEqual(left, {"item": 2, "label": 2, "embedding": 2, "person": 2, "shard": 1, "source": 1})
        written = json.loads((self.tmp / "run" / "PROVENANCE.json").read_text(encoding="utf-8"))
        self.assertEqual(written["run_class"], "open")
        self.assertIn("Cut by recipe: commercial", (self.tmp / "run" / "PROVENANCE.md").read_text(encoding="utf-8"))
        with self.assertRaises(licences.LicenceError):
            licences.derive(self.catalog, "commercial", cut)


if __name__ == "__main__":
    unittest.main()
