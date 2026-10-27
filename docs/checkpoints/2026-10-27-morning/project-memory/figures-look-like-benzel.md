---
name: figures-look-like-benzel
description: The owner's figure rule of 2026-10-26 01:17 UTC: every figure looks like one from Benzel's textbook, and the code that draws it is reproducible and transparent
metadata:
  type: feedback
---

The owner wrote in the CNS slides thread on 2026-10-26 at 01:17 UTC: "please make sure the figures look like figures from benzel and the code for generating the figures is reproducible and transparent".

**Why:** the talk's and the textbook's figures must read as clinical anatomy (Benzel's Biomechanics of Spine Stabilization: clean line drawings, labelled levels, restrained plots), and every number in a figure must be reproducible by a command from a record in the repository.

**How to apply:** a figure stage draws from recorded run outputs with a committed tool (the command, its inputs' digests and the output's record beside the figure, as docs/textbook/figures/ keeps them), in the textbook-drawing style: line art over raster where anatomy is drawn, one typeface, labelled vertebral levels, no decoration, no emoji, colour only where it carries meaning. This holds for the anomaly route's figure stage and bordercall's stitched figures. See [[owner-trusts-only-c2-countable-spines]].
