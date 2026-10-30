"""Every mnemonic of the four Panjabi papers, as one measure of one side.

The provenance record (archive/bordercall/reference/provenance/provenance.csv) names each
printed value by the paper's own mnemonic (EPWu, PDHr, FCAsl ...). The package names a
measure once, whatever its side, and keeps the side as a dimension of its own, so that a left
and a right pedicle width are one measure on two sides and never two independent measures
(TODO.md, item P step 4). This file is the map from the paper's mnemonic to that name, with
the kind of quantity it is (a length, an area or an angle: lengths scale with the patient's
size, areas with its square, angles not at all), what can read it on a patient (a SPINEPS mask
of a CT, an AP radiograph, a lateral radiograph, or only a CT read for it; the inventory in
provenance/README.md), and its definition as landmarks in the papers' words.

The seven measures the archive's rule uses keep the archive's names (endplate, endplate_depth,
endplate_lower, endplate_lower_depth, h_post, canal_w, canal_ap); the archive's pedicle and
pedicle_h are the left-right means of pedicle_w and pedicle_h here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mnemonic:
    mnemonic: str
    measure: str
    side: str                       # whole, right or left
    kind: str                       # length, area or angle
    planes: tuple                   # of mask, ap, lateral, ct
    definition: str


def _family(stem: str, measure: str, kind: str, planes: tuple, definition: str, sides: dict) -> list:
    return [Mnemonic(stem + suffix, measure, side, kind, planes, definition) for suffix, side in sides.items()]


RL = {"r": "right", "l": "left"}
WHOLE = {"": "whole"}
MASK = ("mask",)
MASK_AP = ("mask", "ap")
MASK_LAT = ("mask", "lateral")
CT = ("ct",)

MNEMONICS: list = []
# the vertebral body (cervical Table 2, thoracic Table 3, lumbar Table 2)
MNEMONICS += _family("EPWu", "endplate", "length", MASK_AP, "upper end-plate width: the distance between the lateral ends of the superior end-plate", WHOLE)
MNEMONICS += _family("EPDu", "endplate_depth", "length", MASK_LAT, "upper end-plate depth: the anteroposterior extent of the superior end-plate", WHOLE)
MNEMONICS += _family("EPWl", "endplate_lower", "length", MASK_AP, "lower end-plate width: the distance between the lateral ends of the inferior end-plate", WHOLE)
MNEMONICS += _family("EPDl", "endplate_lower_depth", "length", MASK_LAT, "lower end-plate depth: the anteroposterior extent of the inferior end-plate", WHOLE)
MNEMONICS += _family("VBHp", "h_post", "length", MASK_LAT, "posterior vertebral body height: the distance between the end-plates at the posterior wall", WHOLE)
MNEMONICS += _family("EPAu", "endplate_area", "area", MASK, "upper end-plate surface area", WHOLE)
MNEMONICS += _family("EPAl", "endplate_lower_area", "area", MASK, "lower end-plate surface area", WHOLE)
MNEMONICS += _family("EPItu", "endplate_incl", "angle", MASK_LAT, "upper end-plate inclination to the transverse plane", WHOLE)
MNEMONICS += _family("EPItl", "endplate_lower_incl", "angle", MASK_LAT, "lower end-plate inclination to the transverse plane", WHOLE)
MNEMONICS += _family("EPIt", "endplate_wedge", "angle", MASK_LAT, "wedge angle: the sum of the upper and lower end-plate inclinations to the transverse plane, printed by the thoracic paper as a mean with no standard error", WHOLE)
# the spinal canal (cervical Table 3, thoracic Table 4, lumbar Table 3)
MNEMONICS += _family("SCW", "canal_w", "length", MASK_AP, "spinal canal width: the transverse diameter of the canal at the level of the pedicles", WHOLE)
MNEMONICS += _family("SCD", "canal_ap", "length", MASK_LAT, "spinal canal depth: the anteroposterior diameter of the canal in the midline", WHOLE)
MNEMONICS += _family("SCA", "canal_area", "area", MASK, "spinal canal cross-sectional area", WHOLE)
# the pedicles (cervical Table 4, thoracic Table 5, lumbar Table 4)
MNEMONICS += _family("PDW", "pedicle_w", "length", MASK_AP, "pedicle width: the smallest transverse diameter of the pedicle", RL)
MNEMONICS += _family("PDH", "pedicle_h", "length", MASK_LAT, "pedicle height: the smallest craniocaudal diameter of the pedicle", RL)
MNEMONICS += _family("PDA", "pedicle_area", "area", MASK, "pedicle cross-sectional area at its narrowest", RL)
MNEMONICS += _family("PDIs", "pedicle_incl_sag", "angle", MASK, "pedicle axis inclination to the sagittal plane", RL)
MNEMONICS += _family("PDIt", "pedicle_incl_trans", "angle", MASK_LAT, "pedicle axis inclination to the transverse plane", RL)
# the processes (cervical Table 5, thoracic Table 7, lumbar Table 5)
MNEMONICS += _family("SPL", "spinous_length", "length", MASK_LAT, "spinous process length: from the posterior wall of the canal to the tip of the process", WHOLE)
MNEMONICS += _family("TPW", "transverse_width", "length", MASK_AP, "transverse process width: from the tip of one transverse process to the tip of the other", WHOLE)
MNEMONICS += _family("PIA", "pars_area", "area", MASK, "pars interarticularis cross-sectional area", RL)
# the uncovertebral joints (cervical Table 6)
MNEMONICS += _family("UJA", "uncovertebral_area_upper", "area", CT, "uncovertebral joint surface area, upper joint", {"ru": "right", "lu": "left"})
MNEMONICS += _family("UJA", "uncovertebral_area_lower", "area", CT, "uncovertebral joint surface area, lower joint", {"rl": "right", "ll": "left"})
MNEMONICS += _family("UJI", "uncovertebral_incl_frontal_upper", "angle", CT, "uncovertebral joint inclination to the frontal plane, upper joint", {"fu": "whole"})
MNEMONICS += _family("UJI", "uncovertebral_incl_sag_upper", "angle", CT, "uncovertebral joint inclination to the sagittal plane, upper joint", {"su": "whole"})
MNEMONICS += _family("UJI", "uncovertebral_incl_frontal_lower", "angle", CT, "uncovertebral joint inclination to the frontal plane, lower joint", {"fl": "whole"})
MNEMONICS += _family("UJI", "uncovertebral_incl_sag_lower", "angle", CT, "uncovertebral joint inclination to the sagittal plane, lower joint", {"sl": "whole"})
# the rib articulations (thoracic Table 6)
MNEMONICS += _family("CVA", "costovertebral_area_upper", "area", CT, "costovertebral articulation surface area, upper (superior) demifacet", {"ur": "right", "ul": "left"})
MNEMONICS += _family("CVA", "costovertebral_area_lower", "area", CT, "costovertebral articulation surface area, lower (inferior) demifacet", {"lr": "right", "ll": "left"})
MNEMONICS += _family("CVA", "costovertebral_area", "area", CT, "costovertebral articulation surface area, the total per rib", WHOLE)
MNEMONICS += _family("CTA", "costotransverse_area", "area", CT, "costotransverse articulation surface area", RL)
MNEMONICS += _family("CVA + CTA", "rib_articulation_area", "area", CT, "costovertebral and costotransverse articulation area, the total per rib", WHOLE)
# the articular facets (facets Tables 2 to 8)
MNEMONICS += _family("FCWs", "facet_w_sup", "length", MASK, "superior facet width: the transverse extent of the superior articular facet", RL)
MNEMONICS += _family("FCWi", "facet_w_inf", "length", MASK, "inferior facet width", RL)
MNEMONICS += _family("FCHs", "facet_h_sup", "length", MASK, "superior facet height: the craniocaudal extent of the superior articular facet", RL)
MNEMONICS += _family("FCHi", "facet_h_inf", "length", MASK, "inferior facet height", RL)
MNEMONICS += _family("FCAs", "facet_area_sup", "area", MASK, "superior facet surface area", RL)
MNEMONICS += _family("FCAi", "facet_area_inf", "area", MASK, "inferior facet surface area", RL)
MNEMONICS += _family("IFWs", "interfacet_w_sup", "length", MASK_AP, "superior interfacet width: from the centre of the right superior facet to the centre of the left", WHOLE)
MNEMONICS += _family("IFWi", "interfacet_w_inf", "length", MASK_AP, "inferior interfacet width", WHOLE)
MNEMONICS += _family("IFH", "interfacet_h", "length", MASK_LAT, "interfacet height: from the centre of the superior facet to the centre of the inferior facet of the same side", RL)
MNEMONICS += _family("Ts", "facet_trans_sup", "angle", MASK, "superior facet angle to the transverse plane", RL)
MNEMONICS += _family("Ti", "facet_trans_inf", "angle", MASK, "inferior facet angle to the transverse plane", RL)
MNEMONICS += _family("Ss", "facet_sag_sup", "angle", MASK, "superior facet angle to the sagittal plane (the right side negative by the paper's convention)", RL)
MNEMONICS += _family("Si", "facet_sag_inf", "angle", MASK, "inferior facet angle to the sagittal plane", RL)
MNEMONICS += _family("CAXs", "facet_card_x_sup", "angle", MASK, "card angle of the superior facet normal about the X axis", RL)
MNEMONICS += _family("CAXi", "facet_card_x_inf", "angle", MASK, "card angle of the inferior facet normal about the X axis", RL)
MNEMONICS += _family("CAYs", "facet_card_y_sup", "angle", MASK, "card angle of the superior facet normal about the Y axis", RL)
MNEMONICS += _family("CAYi", "facet_card_y_inf", "angle", MASK, "card angle of the inferior facet normal about the Y axis", RL)

# The pairs the facets paper prints with the right side's sign opposite the left's at every level,
# its sagittal-plane angle S and its Y-card angle CAY of both facets: their mean is taken with the
# right side negated, as (left - right) / 2, or the two sides cancel and the mean carries nothing
# (TODO.md, item P step e). Every other pair has one sign on both sides, and a test holds both.
MIRRORED = ("facet_sag_sup", "facet_sag_inf", "facet_card_y_sup", "facet_card_y_inf")

BY_MNEMONIC = {m.mnemonic: m for m in MNEMONICS}
MEASURES = []
for _m in MNEMONICS:
    if _m.measure not in MEASURES:
        MEASURES.append(_m.measure)
MEASURE_INFO = {name: next(m for m in MNEMONICS if m.measure == name) for name in MEASURES}

# the dimension tables the long CSV is written from: every present-study mean and standard error
# of these is a row; the comparison tables (cervical 7, thoracic 8, lumbar 6, facets 9 and 10)
# restate them and are not read, and the thoracic specimen table (Table 1) is the specimens
# table (table.py)
DIMENSION_TABLES = ["cervical-t2", "cervical-t3", "cervical-t4", "cervical-t5", "cervical-t6",
                    "thoracic-t3", "thoracic-t4", "thoracic-t5", "thoracic-t6", "thoracic-t7",
                    "lumbar-t2", "lumbar-t3", "lumbar-t4", "lumbar-t5",
                    "facets-t2", "facets-t3", "facets-t4", "facets-t5", "facets-t6", "facets-t7", "facets-t8"]

# Panjabi's series is twelve spines in each paper; the population SD is sem * sqrt(n)
SPECIMENS = 12
