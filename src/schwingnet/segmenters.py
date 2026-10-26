"""Which segmentation model labelled the CTs, and how each model's labels are read: the one home
for the names, the alphabets, the ids and the maps between them.

The owner's words of 2026-10-26, in the thread "Compare FleXray DRRs to real X-ray corpora" and,
relayed as standing for every thread, in the CNS slides thread: "MAKE SURE THESE USE SPINEPS
SEGMENTATIONS AS WELL NOT TOTAL SEGMENTATOR! EXISTING ONES IF POSSIBLE" and "OK SO WHEN REPLICATING
THEIR DATA SET YOU SHOULD USE MOOSE BUT FOR MY PRODUCTION RUNS I WANT SPINEPS, FURTHER THE
SEGMENTATION MODEL ON THE UNANNOTATED DATA SHOULD DEFINITELY BE A CONFIGURABLE BLOCK! MAKE SURE THE
DIFFERNCE IN THE LABELS IS HANDLED CORRECTLY EVERYWHERE!" So the segmenter is a block, `segmenter`,
with two values and no third: "spineps" (the default, the production runs) and "moose" (only when
replicating FleXray's own dataset, whose CT labels were made by running moosez, the MOOSE-Z
pipeline, on the ENHANCE-PET 1.6k volumes; the FleXray paper, arXiv 2609.26756v2, section on the
CT data engine). TotalSegmentator is not a value, by the owner's word. The training blocks
(schwingnet.blocks) and the render blocks (schwingnet.render_blocks) import the choices from here,
and the torch side that reads a mask file by scheme (tools/render_blocks.py) imports the maps, so
no block module spells a label itself.

The labels differ by scheme and the difference is kept here, once:

- SPINEPS writes masks in the VerSe alphabet (VERSE): C1 to C7 are 1 to 7, T1 to T12 8 to 19, L1
  to L5 20 to 24, L6 25, the sacrum 26, the coccyx 27 and T13 28. The canonical vertebral names
  (CANONICAL) are vertebra_c1 to vertebra_c7, vertebra_t1 to vertebra_t13, vertebra_l1 to
  vertebra_l6 and sacrum; the coccyx has no canonical name, so it is unsupervised and counted.
- MOOSE's stored ids (MOOSE_STORED, 0 to 117) are FleXray's configs/datasets/MOOSE.yml
  stored_labels, copied here as a literal and held equal to the file by a test: lowercase names,
  vertebra_l6 at 83, hip_left and hip_right at 84 and 85, sacrum at 86, and no T13. They are
  moosez's five CT models stacked in the order peripheral bones (1 to 31), ribs and sternum (32 to
  58), vertebrae, hips and sacrum (59 to 86), organs without the trachea (87 to 104) and cardiac
  (105 to 117); a test holds that too. moosez 3.2's README names four of the bones otherwise
  (fingers_left and fingers_right for phalange_left and phalange_right, toes_left and toes_right
  for toe_left and toe_right, MOOSEZ_RENAMED); its organs model adds the trachea, which MOOSE
  never stored, so it is unsupervised and counted; its lungs, muscles and digestive models label
  nothing MOOSE stores, so the segment stage never runs them (MOOSEZ_MODELS names only the models
  it needs).
- FleXray's protocol all_structures_flexray_v4 keeps 97 of the 117 stored names, aliased into its
  60 model labels, and drops 20 (MOOSE_DROPPED, the file's protocol_drop_labels): vertebra_l6,
  rib_left_13, rib_right_13 and seventeen soft-tissue names. A label volume written for either
  scheme carries MOOSE stored ids, which is exactly FleXray's own case, so a dropped name is in
  the volume and FleXray's own remap drops it, as it does in FleXray's training; what the volume
  cannot carry (T13, the coccyx, the trachea) is left out and recorded as unsupervised.

The maps: canonical_of gives the name a raw value of a scheme carries, None for background and
for what is unsupervised; moose_id_of the MOOSE stored id a name has, None for vertebra_t13 and
every other name MOOSE lacks; supervised_by_flexray whether the protocol keeps a name;
to_moose_ids the relabel table of a scheme, raw value to MOOSE stored id, leaving out what has no
id; moosez_to_moose_ids the same for one moosez model's own multilabel output; scheme_problems
says in words when a scheme does not exist.
"""

from collections.abc import Mapping

from beartype import beartype
from beethoven_qa.contracts import ensure, require

SEGMENTERS = ("spineps", "moose")
DEFAULT_SEGMENTER = "spineps"
# The segmenter FleXray's own dataset was labelled with: the replication's, and only that.
FLEXRAY_SEGMENTER = "moose"
FLEXRAY_PROTOCOL = "all_structures_flexray_v4"

BACKGROUND = "background"
CANONICAL = (
    *(f"vertebra_c{n}" for n in range(1, 8)),
    *(f"vertebra_t{n}" for n in range(1, 14)),
    *(f"vertebra_l{n}" for n in range(1, 7)),
    "sacrum",
)
# The VerSe alphabet SPINEPS writes: the raw value of a mask and the canonical name it carries.
VERSE: dict[int, str] = {
    **{n: f"vertebra_c{n}" for n in range(1, 8)},
    **{7 + n: f"vertebra_t{n}" for n in range(1, 13)},
    **{19 + n: f"vertebra_l{n}" for n in range(1, 6)},
    25: "vertebra_l6",
    26: "sacrum",
    28: "vertebra_t13",
}
# The raw values SPINEPS writes that no canonical name holds, named so a record can say them.
VERSE_UNSUPERVISED: dict[int, str] = {27: "coccyx"}

# FleXray's fxr/configs/datasets/MOOSE.yml, stored_labels, as a literal (tests hold it equal).
MOOSE_STORED: dict[int, str] = {
    0: "background",
    1: "carpal_left",
    2: "carpal_right",
    3: "clavicle_left",
    4: "clavicle_right",
    5: "femur_left",
    6: "femur_right",
    7: "fibula_left",
    8: "fibula_right",
    9: "phalange_left",
    10: "phalange_right",
    11: "humerus_left",
    12: "humerus_right",
    13: "metacarpal_left",
    14: "metacarpal_right",
    15: "metatarsal_left",
    16: "metatarsal_right",
    17: "patella_left",
    18: "patella_right",
    19: "radius_left",
    20: "radius_right",
    21: "scapula_left",
    22: "scapula_right",
    23: "skull",
    24: "tarsal_left",
    25: "tarsal_right",
    26: "tibia_left",
    27: "tibia_right",
    28: "toe_left",
    29: "toe_right",
    30: "ulna_left",
    31: "ulna_right",
    32: "rib_left_1",
    33: "rib_left_2",
    34: "rib_left_3",
    35: "rib_left_4",
    36: "rib_left_5",
    37: "rib_left_6",
    38: "rib_left_7",
    39: "rib_left_8",
    40: "rib_left_9",
    41: "rib_left_10",
    42: "rib_left_11",
    43: "rib_left_12",
    44: "rib_left_13",
    45: "rib_right_1",
    46: "rib_right_2",
    47: "rib_right_3",
    48: "rib_right_4",
    49: "rib_right_5",
    50: "rib_right_6",
    51: "rib_right_7",
    52: "rib_right_8",
    53: "rib_right_9",
    54: "rib_right_10",
    55: "rib_right_11",
    56: "rib_right_12",
    57: "rib_right_13",
    58: "sternum",
    59: "vertebra_c1",
    60: "vertebra_c2",
    61: "vertebra_c3",
    62: "vertebra_c4",
    63: "vertebra_c5",
    64: "vertebra_c6",
    65: "vertebra_c7",
    66: "vertebra_t1",
    67: "vertebra_t2",
    68: "vertebra_t3",
    69: "vertebra_t4",
    70: "vertebra_t5",
    71: "vertebra_t6",
    72: "vertebra_t7",
    73: "vertebra_t8",
    74: "vertebra_t9",
    75: "vertebra_t10",
    76: "vertebra_t11",
    77: "vertebra_t12",
    78: "vertebra_l1",
    79: "vertebra_l2",
    80: "vertebra_l3",
    81: "vertebra_l4",
    82: "vertebra_l5",
    83: "vertebra_l6",
    84: "hip_left",
    85: "hip_right",
    86: "sacrum",
    87: "adrenal_gland_left",
    88: "adrenal_gland_right",
    89: "bladder",
    90: "brain",
    91: "gallbladder",
    92: "kidney_left",
    93: "kidney_right",
    94: "liver",
    95: "lung_lower_lobe_left",
    96: "lung_lower_lobe_right",
    97: "lung_middle_lobe_right",
    98: "lung_upper_lobe_left",
    99: "lung_upper_lobe_right",
    100: "pancreas",
    101: "spleen",
    102: "stomach",
    103: "thyroid_left",
    104: "thyroid_right",
    105: "heart_myocardium",
    106: "heart_atrium_left",
    107: "heart_atrium_right",
    108: "heart_ventricle_left",
    109: "heart_ventricle_right",
    110: "aorta",
    111: "iliac_artery_left",
    112: "iliac_artery_right",
    113: "iliac_vena_left",
    114: "iliac_vena_right",
    115: "inferior_vena_cava",
    116: "portal_splenic_vein",
    117: "pulmonary_artery",
}
MOOSE_IDS: dict[str, int] = {name: i for i, name in MOOSE_STORED.items()}
# The same file's protocol_drop_labels for all_structures_flexray_v4: stored, never supervised.
MOOSE_DROPPED = (
    "rib_left_13",
    "rib_right_13",
    "vertebra_l6",
    "adrenal_gland_left",
    "adrenal_gland_right",
    "bladder",
    "brain",
    "gallbladder",
    "pancreas",
    "stomach",
    "thyroid_left",
    "thyroid_right",
    "aorta",
    "iliac_artery_left",
    "iliac_artery_right",
    "iliac_vena_left",
    "iliac_vena_right",
    "inferior_vena_cava",
    "portal_splenic_vein",
    "pulmonary_artery",
)

# moosez 3.2's CT models whose labels MOOSE stores, each model's own multilabel values and names
# as its README's table gives them (ENHANCE-PET/MOOSE, README.md, "Available Segmentation
# Models"), in the order the segment stage merges them: soft tissue first, bones after, the
# vertebrae last, so where two models' masks overlap a bone wins and a vertebra wins over a rib.
# The lungs model's five lobes are the organs model's 9 to 13, and the muscles and digestive
# models label nothing MOOSE stores, so none of the three is here.
_BONES = (
    "carpal_left",
    "carpal_right",
    "clavicle_left",
    "clavicle_right",
    "femur_left",
    "femur_right",
    "fibula_left",
    "fibula_right",
    "fingers_left",
    "fingers_right",
    "humerus_left",
    "humerus_right",
    "metacarpal_left",
    "metacarpal_right",
    "metatarsal_left",
    "metatarsal_right",
    "patella_left",
    "patella_right",
    "radius_left",
    "radius_right",
    "scapula_left",
    "scapula_right",
    "skull",
    "tarsal_left",
    "tarsal_right",
    "tibia_left",
    "tibia_right",
    "toes_left",
    "toes_right",
    "ulna_left",
    "ulna_right",
)
_ORGANS = (
    "adrenal_gland_left",
    "adrenal_gland_right",
    "bladder",
    "brain",
    "gallbladder",
    "kidney_left",
    "kidney_right",
    "liver",
    "lung_lower_lobe_left",
    "lung_lower_lobe_right",
    "lung_middle_lobe_right",
    "lung_upper_lobe_left",
    "lung_upper_lobe_right",
    "pancreas",
    "spleen",
    "stomach",
    "thyroid_left",
    "thyroid_right",
    "trachea",
)
_CARDIAC = (
    "heart_myocardium",
    "heart_atrium_left",
    "heart_atrium_right",
    "heart_ventricle_left",
    "heart_ventricle_right",
    "aorta",
    "iliac_artery_left",
    "iliac_artery_right",
    "iliac_vena_left",
    "iliac_vena_right",
    "inferior_vena_cava",
    "portal_splenic_vein",
    "pulmonary_artery",
)
_RIBS = (
    *(f"rib_left_{n}" for n in range(1, 14)),
    *(f"rib_right_{n}" for n in range(1, 14)),
    "sternum",
)
_VERTEBRAE = (*CANONICAL[:19], *CANONICAL[20:26], "hip_left", "hip_right", "sacrum")
MOOSEZ_MODELS: dict[str, dict[int, str]] = {
    "clin_ct_organs": dict(enumerate(_ORGANS, start=1)),
    "clin_ct_cardiac": dict(enumerate(_CARDIAC, start=1)),
    "clin_ct_peripheral_bones": dict(enumerate(_BONES, start=1)),
    "clin_ct_ribs": dict(enumerate(_RIBS, start=1)),
    "clin_ct_vertebrae": dict(enumerate(_VERTEBRAE, start=1)),
}
# The README's names for four bones MOOSE.yml stores under the older names, the same positions
# in the peripheral bones model (9, 10, 28 and 29), so they are the same structures renamed.
MOOSEZ_RENAMED: dict[str, str] = {
    "fingers_left": "phalange_left",
    "fingers_right": "phalange_right",
    "toes_left": "toe_left",
    "toes_right": "toe_right",
}


def _words(found: list[str]) -> bool:
    return all(isinstance(line, str) and line for line in found)


@beartype
@ensure(lambda result: _words(result), "each said in words")
@ensure(lambda result, scheme: (scheme in SEGMENTERS) == (not result), "the two schemes hold")
def scheme_problems(scheme: str) -> list[str]:
    """Every way a segmenter's name falls outside what exists, in words; empty when it holds."""
    if scheme in SEGMENTERS:
        return []
    return [f"segmenter {scheme!r} is not one of {', '.join(SEGMENTERS)}"]


@beartype
@require(lambda scheme: scheme in SEGMENTERS, "a segmenter that exists")
@ensure(lambda result, scheme: scheme != "spineps" or result == {**VERSE, **VERSE_UNSUPERVISED})
@ensure(lambda result: 0 not in result, "background has no name of its own")
def alphabet(scheme: str) -> dict[int, str]:
    """Every raw value a scheme's masks may carry, with the name it carries: SPINEPS's VerSe
    values with the coccyx, or MOOSE's stored ids but background."""
    if scheme == "spineps":
        return {**VERSE, **VERSE_UNSUPERVISED}
    return {i: name for i, name in MOOSE_STORED.items() if i != 0}


@beartype
@require(lambda scheme: scheme in SEGMENTERS, "a segmenter that exists")
@require(lambda value: 0 <= value <= 32_767, "a raw label value, as an int16 mask holds it")
@ensure(lambda result, value: value != 0 or result is None, "0 is background in every scheme")
@ensure(
    lambda result: result is None or result in CANONICAL or result in MOOSE_IDS,
    "a canonical or MOOSE name, or unsupervised",
)
def canonical_of(scheme: str, value: int) -> str | None:
    """The canonical or MOOSE name a raw label value of a scheme carries; None for background
    and for a value no name of the scheme holds, or whose name (the coccyx) has no canonical
    form, which is unsupervised."""
    if scheme == "spineps":
        return VERSE.get(value)
    name = MOOSE_STORED.get(value)
    return None if name is None or name == BACKGROUND else name


@beartype
@ensure(
    lambda result, name: result is None or (1 <= result <= 117 and MOOSE_STORED[result] == name),
    "the id names it",
)
@ensure(
    lambda result, name: (result is None) == (name == BACKGROUND or name not in MOOSE_IDS),
    "every stored structure has its id, nothing else has one",
)
def moose_id_of(name: str) -> int | None:
    """The MOOSE stored id a canonical or MOOSE name has; None for vertebra_t13, the coccyx and
    every other name MOOSE lacks, and for background, which is no structure."""
    if name == BACKGROUND:
        return None
    return MOOSE_IDS.get(name)


@beartype
@ensure(lambda result, name: not result or name in MOOSE_IDS, "only a stored name is supervised")
@ensure(lambda result, name: not result or name not in MOOSE_DROPPED, "never a dropped name")
def supervised_by_flexray(name: str) -> bool:
    """Whether FleXray's protocol all_structures_flexray_v4 keeps the name as one of the 97 stored
    names it supervises, or drops it (vertebra_l6, the thirteenth ribs, the soft tissue it never
    learnt) or never stored it (vertebra_t13, the coccyx, the trachea)."""
    return name in MOOSE_IDS and name != BACKGROUND and name not in MOOSE_DROPPED


def _ids_name(table: Mapping[int, int], names: Mapping[int, str]) -> bool:
    # Each MOOSE id in the table is the id of the name the raw value carries.
    return all(MOOSE_STORED[v] == MOOSEZ_RENAMED.get(names[k], names[k]) for k, v in table.items())


@beartype
@require(lambda scheme: scheme in SEGMENTERS, "a segmenter that exists")
@ensure(lambda result: all(1 <= v <= 117 for v in result.values()), "MOOSE stored ids")
@ensure(lambda result: 0 not in result, "background is never relabelled")
@ensure(lambda result, scheme: _ids_name(result, alphabet(scheme)), "each id names its value")
def to_moose_ids(scheme: str) -> dict[int, int]:
    """The relabel table of a scheme, each raw value to the MOOSE stored id of the name it
    carries, leaving out what has no MOOSE id (T13 and the coccyx under SPINEPS); the identity
    on MOOSE's own ids. A label volume relabelled through it holds MOOSE stored ids, which is
    what FleXray's own code reads."""
    table = {}
    for value, name in alphabet(scheme).items():
        moose_id = moose_id_of(name)
        if moose_id is not None:
            table[value] = moose_id
    return table


@beartype
@require(lambda model: model in MOOSEZ_MODELS, "a moosez model the segment stage runs")
@ensure(lambda result: all(1 <= v <= 117 for v in result.values()), "MOOSE stored ids")
@ensure(lambda result, model: _ids_name(result, MOOSEZ_MODELS[model]), "each id names its value")
def moosez_to_moose_ids(model: str) -> dict[int, int]:
    """The relabel table of one moosez model's multilabel output, its own value to the MOOSE
    stored id of the name it carries (the README's renamed bones through MOOSEZ_RENAMED),
    leaving out what MOOSE never stored (the trachea)."""
    table = {}
    for value, name in MOOSEZ_MODELS[model].items():
        moose_id = moose_id_of(MOOSEZ_RENAMED.get(name, name))
        if moose_id is not None:
            table[value] = moose_id
    return table


@beartype
@require(lambda scheme: scheme in SEGMENTERS, "a segmenter that exists")
@ensure(lambda result, scheme: not (set(result) & set(to_moose_ids(scheme))), "none has an id")
def unsupervised_in(scheme: str) -> dict[int, str]:
    """The raw values a scheme names that no MOOSE id holds, with their names, so a record can
    say what a mask carried that the label volume left out: T13 and the coccyx under SPINEPS,
    nothing under MOOSE."""
    table = to_moose_ids(scheme)
    return {value: name for value, name in alphabet(scheme).items() if value not in table}
