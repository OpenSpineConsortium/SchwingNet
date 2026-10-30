---
name: greg-one-network-swappable
description: greg's rule of 2026-10-30 02:49 UTC: the auto-anatomist's parts are encapsulated and swappable, one network for every measure set (never two for the seven and the 32), the prior accepts PyMC code natively and adapts to what is provided
metadata:
  type: feedback
  modified: 2026-10-30T02:51:39.012Z
---

greg, 2026-10-30 02:49 UTC (thread "Plan evaluating latent shape priors against explainable metrics"): "yes just please build them up encapsulated and swappable, like i dont want two networks for the seven and 32 measure pool, make sure it just accepts pymc code like natively, and adapts to what is provided, the same for others it should be seemless like a fighter jet and maintain this swappable configurable easy switching".

**Why:** the arms, feature sets and priors are to be compared by flipping a block value, never by maintaining parallel code; a PyMC model written for schwingcheck (chain_pymc.py) should drop into the auto-anatomist's naming layer as it is.

**How to apply:** every shape follows from the configuration: a block measures=seven|pool|pool-ratios sets the landmark channels, the PDM's points, arm E's width and the rule's table; a block prior=exact|pymc:<dotted path> takes a callable that builds a pm.Model over the measures provided, jaxified for the loss (pymc.sampling.jax.get_jaxified_logp) and sampled at evaluation; no block value makes a second network; the contract is bordercall research_notes/latent-shape-prior-evaluation/README.md section 10. See [[greg-screen-arms-in-parallel]] and [[owner-rules]].
