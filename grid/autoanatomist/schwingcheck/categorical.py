"""Liu's Metropolised Gibbs step for a categorical variable, as PyMC names it and as PyMC 6.3.2 does
not compute it.

    with model:
        step = MetropolisedGibbs([model["place"]])
        idata = pm.sample(step=[step, ...])

pm.CategoricalGibbsMetropolis(proposal="proportional") proposes a value j other than the current
value i with probability p_j / (1 - p_i), as Liu's Metropolised Gibbs sampler (1996) does, but it
accepts j with min(1, (1 - p_i) / (1 - p_j / (1 - p_i))), one less the renormalised probability in
the denominator where Liu's takes p_j itself. Its chains then sample the stationary law of their own
kernel and not the variable's, agreeing with one another so that R-hat does not see it; on two
values they never move or move at every step; and where the current value is all but certain,
1 - p_i is 0 in floating point and the step stops with NaN (fixed_k.py, the README's "The fixed-k
NUTS review").

MetropolisedGibbs is that step with Liu's acceptance, min(1, (1 - p_i) / (1 - p_j)), which leaves
the variable's law stationary. Each 1 - p is computed as the log-sum-exp of the other values' log
probabilities, never as a difference, so a value all but certain is left with the small chance of a
move its law gives, and where no other value has any probability the step stays where it is. Only
the proportional proposal changes; the uniform one, which PyMC computes right, is the parent's.

No result in this repository uses it: rule.py, the naming model and the chain sum the level out
exactly. It is here for a model with a discrete variable that cannot be summed out.
"""
from __future__ import annotations

import numpy as np
import pymc as pm
from scipy.special import logsumexp


def log_complements(log_p: np.ndarray) -> np.ndarray:
    """log(1 - p_c) for every value c, each the log-sum-exp of the others' log probabilities."""
    k = len(log_p)
    return np.array([logsumexp(np.delete(log_p, c)) if k > 1 else -np.inf for c in range(k)])


def liu_move(log_density: np.ndarray, current: int, rng: np.random.Generator) -> int:
    """One Metropolised Gibbs move of a categorical variable whose values have these unnormalised
    log densities: the value it moves to, or the current one."""
    log_p = log_density - logsumexp(log_density)
    log_away = log_complements(log_p)
    if not np.isfinite(log_away[current]):
        return current
    offer = np.exp(log_p - log_away[current])
    offer[current] = 0.0
    proposed = int(rng.choice(len(offer), p=offer / offer.sum()))
    if np.log(rng.uniform()) < log_away[current] - log_away[proposed]:
        return proposed
    return current


class MetropolisedGibbs(pm.CategoricalGibbsMetropolis):
    """pm.CategoricalGibbsMetropolis with Liu's acceptance on its proportional proposal, which is the
    default here; every other argument is the parent's."""

    def __init__(self, vars, **kwargs):
        kwargs.setdefault("proposal", "proportional")
        super().__init__(vars, **kwargs)

    def metropolis_proportional(self, q, logp, logp_curr, dim, k):
        current = int(q.data[dim])
        log_density = np.empty(k)
        for value in range(k):
            if value == current:
                log_density[value] = logp_curr
            else:
                q.data[dim] = value
                log_density[value] = logp(q)
        q.data[dim] = liu_move(log_density, current, self.rng)
        return log_density[int(q.data[dim])]
