"""SchwingNet: the retraining, measurement and demo of the level-naming network.

The package holds the study's pure logic, gated by beethoven-qa (contracts on every public
function, CrossHair over them, the six code standards); what reads a corpus or runs a trainer
is a Slurm job the flow submits, never a contracted function here.
"""

__version__ = "0.0.0"
