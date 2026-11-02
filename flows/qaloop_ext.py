"""The QA loop with external real arms, as a Metaflow flow (docs/research/qa-loop-external/PREREG.md).

Usage, through the launcher only (grid/qaloop_ext.sbatch, the gate's word `qaloop <plan>` for a plan
grid/gate.sh's QALOOP_EXT_PLANS names):
    python flows/launch.py qaloop_ext --max-workers 1 -- --plan grid/qaloop/<plan>.json ...

The loop of flows/qaloop.py, whose round reads the plan's external real arms (tools/realx_pairs.py) for
the gates alone, under a kind of its own, so that it is held to a PREREG of its own: the
registry holds one frozen PREREG per kind, and the loop's is frozen and never edited
(flows/stage_registry.py, frozen). Its rounds, gates, controller, folders, record and report are the
loop's; only the kind its runs are held to differs. Its report is written as the study qa-loop,
whose design check takes either PREREG (tools/qaloop_report.py, DESIGNS).
"""

from qaloop import QaloopFlow
import qaloop as loop

KIND = "qaloop_ext"


def prereg_part(words, folder):
    """The part a run of these words is, as the loop's: the plan's name and its bytes."""
    return loop.prereg_part(words, folder)


def key_reads(words, folder):
    """What a run of these words reads that the words do not name, as the loop's."""
    return loop.key_reads(words, folder)


class QaloopExtFlow(QaloopFlow):
    KIND = KIND


if __name__ == "__main__":
    QaloopExtFlow()
