---
name: greg-lambda-schedule-fep
description: greg, 2026-10-30 16:37 UTC: bidirectional lambda or several lambda variables, from FEP (Lambda-ABF paper, arXiv 2307.08006); the answer given and the arms proposed for a second annealer screen
metadata:
  type: project
  modified: 2026-10-30T17:00:45.024Z
---

greg asked the thread "Restart the auto-anatomist probe" (project symphony_3) whether a bidirectional lambda schedule, or two or more lambda-type variables, has merit, drawing on FEP alchemical potentials, and attached Lambda-ABF (Lagardere, Henin et al., arXiv 2307.08006v2: lambda-dynamics with an adaptive biasing force, lambda_e and lambda_v staggered on one global lambda, a lambda-dependent restraint zero at both ends).

Answer given at 16:45 UTC with a figure (/mnt/project-files/autoanatomist/lambda-schedules-fep.png, drawn from ladder.Anneal on bordercall PR 40, script in the session scratchpad only):
- Several lambdas exist already: the ladder's three rungs (identity, blur, CT threshold) on one lambda, plus w. The frozen screen's arms are FEP's ordering question; lambda_then_w is FEP's order (information out before the channel), w_first the "naked charge" order.
- Bidirectional: some merit, but a network's end weights depend on the path while an FEP free energy does not, and only the end state (lambda 1, w 0) is used. Proposed one arm: a cyclic re-anneal (lambda back to 0.5, w up to 0.3, down again).
- Best idea: adaptive lambda (up when held-out error at the next lambda is close, back when it jumps), using dE/dlambda, which train.error_curve already computes.
- Also: a mid-path restraint, a loss weighted (1 - cos 2 pi lambda)/2. Less merit now: a random lambda per crop (needs lambda as a network input).
- Keep the first screen frozen; a second screen of three or four arms at most (each two-seed arm can pass by luck up to 1 in 6).

greg, 17:03 UTC, asked what w is (the mask branch's weight: the decoder reads (1 - w) CT features + w mask features) and whether an adaptive biasing force can act on the learned points and curves (a chord has no parameters of its own; an arc's sagitta can deform), extended to 2-D, 3-D and N-D primitives, which another session of his renders (lines, arcs, planes, volumes). Answered: force = -dloss/dparameter per primitive parameter; an arc needs a loss that sees its shape (distance to the mask's surface in training, so the mask is a potential softened by lambda, switched off by w); ABF's running mean force per bin of each parameter, mid-anneal, zero at both ends; on the width it equals the calibration gap; bin each parameter alone. Plan: the restraint arm becomes this adaptive force on the width first, the screen stays at four arms; arcs and planes once the rendering thread's primitives land.

**Why:** a later session must not re-derive this or redo the figure.

**How to apply:** greg chose on 2026-10-30 at 16:52 UTC (decision card) to build the four arms (cyclic, adaptive, split-rung, restraint) for a second screen after the demo fix, with tests and a frozen plan; the first screen stays frozen as it is. greg dropped the per-job word and job count project-wide at 16:59 UTC ("stop asking me everytime you submit a job"), so once built and merged the second screen is submitted and reported, not asked about. See [[autoanatomist-screen-ready]], [[demo-ask-2026-10-29]].
