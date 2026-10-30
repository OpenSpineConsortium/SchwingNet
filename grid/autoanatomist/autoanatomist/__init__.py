"""The auto-anatomist: a network that learns to take a measurement oracle's chords on raw CT.

Confidential, as the rest of this repository: a pre-filing draft. Nothing here has seen a
patient; every volume in its tests and its smoke runs is a synthetic phantom drawn in code.

The owner's ask of 29 October 2026, 02:17 UTC: "finally start implementing this assuming i have
an oracle for measurements on any spine which can render lines indicating how the measurement is
made on the vertebral masks based on independently programmed utility code". The design notes
that came with it, a conversation with another assistant, are design notes and not facts; what
this package takes from them, and what it changes, is said module by module.

The pieces, in the order the data meets them:

- specs.py: each measurement defined once, as the points that make it and the rule that turns
  the points into the value, the same rule in NumPy and in JAX, so a drawn line and its number
  never disagree.
- oracle.py: the oracle's interface (labels in; per vertebra, every measurement with its value,
  its points and why it is missing where it is), and a stand-in built over scanimport.geometry,
  bordercall's own tested chord code, whose values it returns unchanged. The real extractors the
  thread "Extract morphometrics from gold tier 3 CT" builds are meant to plug in behind the same
  interface.
- render.py: the oracle's lines drawn on a reslice of the mask or of the CT in the vertebra's own
  frame.
- phantom.py: paired synthetic CTs and masks, each level's body, canal and end-plates sized from
  a column of schwingcheck's generator, so the phenotypes (L6, T13, four lumbar bodies) and the
  table's spread reach the images.
- crops.py: a vertebra's neighbourhood resampled into a crop in a frame of its own, and points
  carried between the crop and the world.
- gates.py: soft thresholds and soft morphology in JAX, differentiable in the threshold, the
  width and the radius.
- ladder.py: the degradation ladder, lambda from 0 (the instance mask) to 1 (a soft threshold of
  the CT, which needs no mask), and the schedules of lambda and of the fusion weight w.
- naming.py: the chain of levels in JAX: the exact answer by the paths, as schwingcheck.chain
  computes it in NumPy, and a forward pass with a temperature (soft Viterbi), both differentiable
  in the measured values and their errors.
- model.py: the network: a CT encoder and a privileged mask encoder whose features are blended,
  F = (1 - w) F_ct + w F_mask, landmark heatmaps read by soft-argmax, and the measurements
  computed from the landmarks by specs.py's rules.
- train.py: the losses, one training step, the schedules and the error as a function of lambda.
- project.py: nanodrr's camera to the bit, FluXray's poses, any reading projected onto the
  detector with each measurement's 2-D value by the same rule, and a view's readability.
- blocks.py: every training part as a KEY=VALUE block, parsed and refused in words, spelled
  canonically and digested; no block named is the smoke run.
- calibrate.py: the spread's calibration, a factor per measure fit on validation (scale or
  quantile) and applied unchanged.
- rows.py: examples from rows (a phantom by its seeds, or a CT with its labels), each rendered by
  its own generator and cached by its digest, so adding data is appending rows.
- session.py: a session built from blocks that trains from its step, saves itself as plain arrays
  and is restored to the bit, continues its anneal and carries its calibration, for a search's
  trial, a continued run and a run on more data alike.

What is built is code and its tests. No network has been trained beyond a minutes-long smoke run on
phantoms, no weight is kept, nothing ran on the grid and no WSU data was read (the owner's hold
of 28 October 2026, lifted on 29 October at 17:05 UTC for work that waits for his word and count).
"""
from __future__ import annotations

__version__ = "0.2.0"
