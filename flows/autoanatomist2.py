"""The auto-anatomist's second screen as a Metaflow flow (docs/research/autoanatomist-screen2/PREREG.md).

Usage, through the launcher only (grid/autoanatomist2.sbatch, the gate's word `autoanatomist <plan>`
for a plan grid/gate.sh's AUTOANATOMIST2_PLANS names):
    python flows/launch.py autoanatomist2 --max-workers 1 -- --part trial|join --plan grid/screens/<plan>.json ...

The second screen is the first screen's flow (flows/autoanatomist.py) under a kind of its own, so
that it is held to a PREREG of its own: the registry holds one frozen PREREG per kind, and the first
screen's is frozen and is never edited (flows/stage_registry.py, frozen). Its parts, words, folders
and record are the first screen's; only the kind its runs are held to differs. Its report is written
as the study autoanatomist-screen, whose code answers restate the PREREG the chain's record names
(tools/autoanatomist_report.py, DESIGNS).
"""

from autoanatomist import AutoanatomistFlow
import autoanatomist as first

KIND = "autoanatomist2"


def prereg_part(words, folder):
    """The part a run of these words is, as the first screen's: the plan's name and its bytes."""
    return first.prereg_part(words, folder)


def key_reads(words, folder):
    """What a run of these words reads that the words do not name, as the first screen's."""
    return first.key_reads(words, folder)


class Autoanatomist2Flow(AutoanatomistFlow):
    KIND = KIND


if __name__ == "__main__":
    Autoanatomist2Flow()
