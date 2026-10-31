"""The QA loop on the gold tiers, as a Metaflow flow (docs/research/qa-loop-gold/PREREG.md).

Usage, through the launcher only (grid/qaloop_gold.sbatch, the gate's word `qaloop <plan>` for a plan
grid/gate.sh's QALOOP_GOLD_PLANS names):
    python flows/launch.py qaloop_gold --max-workers 1 -- --plan grid/qaloop/<plan>.json \\
        --chain <job> --out <loop root> --data <data root> --gold4 <gold 4 run folder>

The loop of flows/qaloop.py under a kind of its own, so that it is held to a PREREG of its own: the
registry holds one frozen PREREG per kind, and the loop's is frozen and never edited
(flows/stage_registry.py, frozen). Its plans carry a gold block, so every round also renders the
gold tiers' CTs as radiographs at the C-arm's geometry (tools/gold_xray.py) and asks the three gold
gates, and the network's reading of the held-out gold CTs is recorded beside the phantoms'. Its
folders, record and report are the loop's; its report is written as the study qa-loop, whose design
check takes this PREREG too (tools/qaloop_report.py, DESIGNS).
"""

from qaloop import QaloopFlow
import qaloop as loop

KIND = "qaloop_gold"


def prereg_part(words, folder):
    """The part a run of these words is, as the loop's: the plan's name and its bytes."""
    return loop.prereg_part(words, folder)


def key_reads(words, folder):
    """What a run of these words reads that the words do not name, as the loop's."""
    return loop.key_reads(words, folder)


class QaloopGoldFlow(QaloopFlow):
    KIND = KIND


if __name__ == "__main__":
    QaloopGoldFlow()
