"""The segmenter schemes: the VerSe alphabet SPINEPS writes, MOOSE's stored ids as FleXray's
MOOSE.yml declares them, and the maps between them at both edges (L6, which MOOSE stores and
FleXray drops; T13 and the coccyx, which MOOSE lacks).

These cases import no torch and no fxr: the one that reads MOOSE.yml itself reads the copy under
tests/fixtures/ (flexray-1.0.2-MOOSE.yml) wherever it runs, and the installed package's own file
too where flexray is installed, so a release that changes the file fails here; it parses the
file's simple `  id: name` lines with the standard library (no yaml dependency):

    PYTHONPATH=src:vendor/beethoven-qa/src python -m unittest tests.schwingnet.test_segmenters
"""

import importlib.util
import re
import unittest
from pathlib import Path

from schwingnet.segmenters import (
    CANONICAL,
    DEFAULT_SEGMENTER,
    FLEXRAY_SEGMENTER,
    MOOSE_DROPPED,
    MOOSE_IDS,
    MOOSE_STORED,
    MOOSEZ_MODELS,
    MOOSEZ_RENAMED,
    SEGMENTERS,
    VERSE,
    VERSE_UNSUPERVISED,
    alphabet,
    canonical_of,
    moose_id_of,
    moosez_to_moose_ids,
    scheme_problems,
    supervised_by_flexray,
    to_moose_ids,
    unsupervised_in,
)


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "flexray-1.0.2-MOOSE.yml"


def moose_yaml():
    """FleXray's MOOSE.yml where the flexray package is installed, else None."""
    spec = importlib.util.find_spec("fxr")
    if spec is None or not spec.submodule_search_locations:
        return None
    path = Path(next(iter(spec.submodule_search_locations))) / "configs" / "datasets" / "MOOSE.yml"
    return path if path.is_file() else None


def moose_yaml_copies():
    """Every copy of MOOSE.yml to hold the tables to: the fixture always, the installed package's
    own where there is one."""
    installed = moose_yaml()
    return [FIXTURE] if installed is None else [FIXTURE, installed]


def parse_moose_yaml(text):
    """The file's stored_labels and its protocol_drop_labels for all_structures_flexray_v4, read
    from the simple lines the file is made of: `  id: name` under stored_labels and `  - name`
    under the drop list."""
    stored, dropped, section = {}, [], None
    for line in text.splitlines():
        if line and not line.startswith(" "):
            section = line.rstrip(":")
            continue
        if section == "stored_labels":
            found = re.match(r"^  (\d+): (\S+)$", line)
            if found:
                stored[int(found.group(1))] = found.group(2)
        elif section == "protocol_drop_labels":
            found = re.match(r"^  - (\S+)$", line)
            if found:
                dropped.append(found.group(1))
    return stored, dropped


class Schemes(unittest.TestCase):
    def test_two_schemes_spineps_the_default_and_moose_for_the_replication(self):
        self.assertEqual(SEGMENTERS, ("spineps", "moose"))
        self.assertEqual(DEFAULT_SEGMENTER, "spineps")
        self.assertEqual(FLEXRAY_SEGMENTER, "moose")
        self.assertEqual(scheme_problems("spineps"), [])
        self.assertEqual(scheme_problems("moose"), [])
        self.assertEqual(
            scheme_problems("totalsegmentator"),
            ["segmenter 'totalsegmentator' is not one of spineps, moose"],
        )

    def test_the_canonical_names_are_the_vertebrae_to_t13_and_l6_and_the_sacrum(self):
        self.assertEqual(len(CANONICAL), 27)
        self.assertEqual(CANONICAL[:7], tuple(f"vertebra_c{n}" for n in range(1, 8)))
        self.assertEqual(CANONICAL[7:20], tuple(f"vertebra_t{n}" for n in range(1, 14)))
        self.assertEqual(CANONICAL[20:26], tuple(f"vertebra_l{n}" for n in range(1, 7)))
        self.assertEqual(CANONICAL[26], "sacrum")
        without_id = [name for name in CANONICAL if moose_id_of(name) is None]
        self.assertEqual(without_id, ["vertebra_t13"])


class Verse(unittest.TestCase):
    def test_the_alphabet_spineps_writes(self):
        self.assertEqual(VERSE[1], "vertebra_c1")
        self.assertEqual(VERSE[7], "vertebra_c7")
        self.assertEqual(VERSE[8], "vertebra_t1")
        self.assertEqual(VERSE[19], "vertebra_t12")
        self.assertEqual(VERSE[20], "vertebra_l1")
        self.assertEqual(VERSE[24], "vertebra_l5")
        self.assertEqual(VERSE[25], "vertebra_l6")
        self.assertEqual(VERSE[26], "sacrum")
        self.assertEqual(VERSE[28], "vertebra_t13")
        self.assertNotIn(27, VERSE)
        self.assertEqual(VERSE_UNSUPERVISED, {27: "coccyx"})
        self.assertEqual(len(VERSE), 27)
        self.assertEqual(alphabet("spineps"), {**VERSE, 27: "coccyx"})

    def test_canonical_of_a_spineps_value(self):
        self.assertEqual(canonical_of("spineps", 25), "vertebra_l6")
        self.assertEqual(canonical_of("spineps", 28), "vertebra_t13")
        self.assertEqual(canonical_of("spineps", 26), "sacrum")
        self.assertIsNone(canonical_of("spineps", 27), "the coccyx has no canonical name")
        self.assertIsNone(canonical_of("spineps", 0))
        self.assertIsNone(canonical_of("spineps", 29))

    def test_the_spineps_relabel_table_reaches_moose_ids_but_for_t13_and_the_coccyx(self):
        table = to_moose_ids("spineps")
        self.assertEqual({v: table[v] for v in range(1, 8)}, {v: 58 + v for v in range(1, 8)})
        self.assertEqual({v: table[v] for v in range(8, 20)}, {v: 58 + v for v in range(8, 20)})
        self.assertEqual({v: table[v] for v in range(20, 25)}, {v: 58 + v for v in range(20, 25)})
        self.assertEqual(table[25], 83, "L6 is stored by MOOSE, at 83")
        self.assertEqual(table[26], 86)
        self.assertNotIn(27, table)
        self.assertNotIn(28, table)
        self.assertEqual(len(table), 26)
        self.assertEqual(unsupervised_in("spineps"), {27: "coccyx", 28: "vertebra_t13"})


class Moose(unittest.TestCase):
    def test_the_stored_ids_at_the_edges(self):
        self.assertEqual(len(MOOSE_STORED), 118)
        self.assertEqual(MOOSE_STORED[0], "background")
        self.assertEqual(MOOSE_STORED[59], "vertebra_c1")
        self.assertEqual(MOOSE_STORED[82], "vertebra_l5")
        self.assertEqual(MOOSE_STORED[83], "vertebra_l6")
        self.assertEqual((MOOSE_STORED[84], MOOSE_STORED[85]), ("hip_left", "hip_right"))
        self.assertEqual(MOOSE_STORED[86], "sacrum")
        self.assertEqual(MOOSE_STORED[105], "heart_myocardium")
        self.assertEqual(MOOSE_STORED[117], "pulmonary_artery")
        self.assertNotIn("vertebra_t13", MOOSE_IDS)
        self.assertEqual(len(set(MOOSE_STORED.values())), 118, "every name once")

    def test_moose_id_of_a_name(self):
        self.assertEqual(moose_id_of("vertebra_l6"), 83)
        self.assertEqual(moose_id_of("sacrum"), 86)
        self.assertEqual(moose_id_of("hip_left"), 84)
        self.assertEqual(moose_id_of("hip_right"), 85)
        self.assertEqual(moose_id_of("rib_left_13"), 44)
        self.assertIsNone(moose_id_of("vertebra_t13"), "MOOSE has no T13")
        self.assertIsNone(moose_id_of("coccyx"))
        self.assertIsNone(moose_id_of("trachea"))
        self.assertIsNone(moose_id_of("background"))

    def test_canonical_of_a_moose_value_is_its_stored_name(self):
        self.assertEqual(canonical_of("moose", 83), "vertebra_l6")
        self.assertEqual(canonical_of("moose", 86), "sacrum")
        self.assertEqual(canonical_of("moose", 44), "rib_left_13")
        self.assertEqual(canonical_of("moose", 94), "liver")
        self.assertIsNone(canonical_of("moose", 0))
        self.assertIsNone(canonical_of("moose", 118))

    def test_the_moose_relabel_table_is_the_identity_on_the_structures(self):
        self.assertEqual(to_moose_ids("moose"), {i: i for i in range(1, 118)})
        self.assertEqual(unsupervised_in("moose"), {})
        self.assertEqual(alphabet("moose"), {i: MOOSE_STORED[i] for i in range(1, 118)})

    def test_flexrays_protocol_keeps_97_names_and_drops_l6_and_the_thirteenth_ribs(self):
        self.assertEqual(len(MOOSE_DROPPED), 20)
        for name in ("vertebra_l6", "rib_left_13", "rib_right_13", "aorta", "brain"):
            self.assertIn(name, MOOSE_DROPPED)
            self.assertFalse(supervised_by_flexray(name), name)
        for name in ("vertebra_l5", "rib_left_12", "sacrum", "hip_left", "liver", "skull"):
            self.assertTrue(supervised_by_flexray(name), name)
        for name in ("vertebra_t13", "coccyx", "trachea", "background"):
            self.assertFalse(supervised_by_flexray(name), name)
        kept = [name for name in MOOSE_STORED.values() if supervised_by_flexray(name)]
        self.assertEqual(len(kept), 97)
        self.assertEqual(sorted(set(MOOSE_DROPPED) - set(MOOSE_STORED.values())), [])


class Moosez(unittest.TestCase):
    def test_moose_stored_is_moosezs_five_models_stacked(self):
        order = (
            "clin_ct_peripheral_bones",
            "clin_ct_ribs",
            "clin_ct_vertebrae",
            "clin_ct_organs",
            "clin_ct_cardiac",
        )
        stacked = []
        for model in order:
            for value in sorted(MOOSEZ_MODELS[model]):
                name = MOOSEZ_MODELS[model][value]
                if name != "trachea":
                    stacked.append(MOOSEZ_RENAMED.get(name, name))
        self.assertEqual(stacked, [MOOSE_STORED[i] for i in range(1, 118)])
        self.assertEqual(set(MOOSEZ_MODELS), set(order))
        self.assertEqual(len(MOOSEZ_MODELS["clin_ct_vertebrae"]), 28)
        self.assertEqual(len(MOOSEZ_MODELS["clin_ct_ribs"]), 27)
        self.assertEqual(len(MOOSEZ_MODELS["clin_ct_peripheral_bones"]), 31)
        self.assertEqual(len(MOOSEZ_MODELS["clin_ct_organs"]), 19)
        self.assertEqual(len(MOOSEZ_MODELS["clin_ct_cardiac"]), 13)

    def test_each_models_values_reach_moose_ids_the_renamed_bones_through_their_older_names(self):
        vertebrae = moosez_to_moose_ids("clin_ct_vertebrae")
        self.assertEqual({v: vertebrae[v] for v in range(1, 26)}, {v: 58 + v for v in range(1, 26)})
        self.assertEqual((vertebrae[26], vertebrae[27], vertebrae[28]), (84, 85, 86))
        ribs = moosez_to_moose_ids("clin_ct_ribs")
        self.assertEqual((ribs[1], ribs[13], ribs[14], ribs[26], ribs[27]), (32, 44, 45, 57, 58))
        bones = moosez_to_moose_ids("clin_ct_peripheral_bones")
        self.assertEqual((bones[9], bones[10], bones[28], bones[29]), (9, 10, 28, 29))
        self.assertEqual(MOOSE_STORED[bones[9]], "phalange_left")
        self.assertEqual(MOOSE_STORED[bones[28]], "toe_left")
        organs = moosez_to_moose_ids("clin_ct_organs")
        self.assertNotIn(19, organs, "the trachea is not a MOOSE name")
        self.assertEqual(len(organs), 18)
        self.assertEqual(moosez_to_moose_ids("clin_ct_cardiac"), {v: 104 + v for v in range(1, 14)})
        self.assertEqual(
            MOOSEZ_RENAMED,
            {
                "fingers_left": "phalange_left",
                "fingers_right": "phalange_right",
                "toes_left": "toe_left",
                "toes_right": "toe_right",
            },
        )


class TheFile(unittest.TestCase):
    def test_moose_stored_and_the_drop_list_are_moose_yml(self):
        for path in moose_yaml_copies():
            stored, dropped = parse_moose_yaml(path.read_text(encoding="utf-8"))
            self.assertEqual(stored, MOOSE_STORED, path)
            self.assertEqual(dropped, list(MOOSE_DROPPED), path)
        self.assertEqual(len(MOOSE_STORED), 118, "background and 117 stored names")

    def test_the_parser_reads_the_simple_lines_and_nothing_else(self):
        text = (
            "dataset_name: MOOSE\nstored_labels:\n  0: background\n  1: carpal_left\n"
            "protocol_label_aliases:\n  all_structures_flexray_v4:\n    carpal_left: carpals\n"
            "protocol_drop_labels:\n  all_structures_flexray_v4:\n  - rib_left_13\n"
        )
        self.assertEqual(
            parse_moose_yaml(text), ({0: "background", 1: "carpal_left"}, ["rib_left_13"])
        )


if __name__ == "__main__":
    unittest.main()
