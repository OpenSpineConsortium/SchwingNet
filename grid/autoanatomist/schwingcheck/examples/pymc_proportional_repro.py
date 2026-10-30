"""CategoricalGibbsMetropolis(proposal="proportional") samples the wrong law: a reproduction.

Run with PyMC installed:  python pymc_proportional_repro.py

A Categorical alone, its probabilities fixed, is sampled with the proportional proposal and with
the uniform one. The uniform proposal gives the Categorical its own law; the proportional one
gives the stationary law of its own transition kernel, which this script also writes out from the
acceptance ratio the code computes, and which is not the Categorical's. On two values the
proportional chain either never moves or moves at every draw, and where one value is all but
certain the step divides by zero and pm.sample stops. With Liu's acceptance ratio in place of
PyMC's, the same proposal gives the Categorical its own law.
"""
import numpy as np
import pymc as pm
from scipy import special


def shares(p, proposal, draws=4000, chains=4, seed=13, step_cls=pm.CategoricalGibbsMetropolis):
    with pm.Model() as model:
        x = pm.Categorical("x", p=np.asarray(p, float))
        step = step_cls([x], proposal=proposal)
        idata = pm.sample(draws=draws, tune=500, chains=chains, step=step, random_seed=seed,
                          progressbar=False, compute_convergence_checks=False)
    values = idata.posterior["x"].values  # (chains, draws)
    share = np.array([(values == c).mean() for c in range(len(p))])
    per_chain_first = (values == 0).mean(axis=1)
    moves = (values[:, 1:] != values[:, :-1]).mean()
    return share, per_chain_first, moves


def pymc_kernel(p):
    """The transition matrix of PyMC's proportional step, from the ratio its code computes, with
    the softmax of the exact log probabilities (PyMC takes the softmax of its compiled log density;
    on two values the rounding of that softmax decides the outcome, see below)."""
    p = special.softmax(np.log(np.asarray(p, float)))
    k = len(p)
    P = np.zeros((k, k))
    for i in range(k):
        others = p.copy()
        prob_curr, others[i] = others[i], 0.0
        others = others / (1.0 - prob_curr)
        for j in range(k):
            if j == i:
                continue
            ratio = (1.0 - prob_curr) / (1.0 - others[j])
            accept = min(1.0, ratio) if np.isfinite(ratio) else 0.0
            P[i, j] = others[j] * accept
        P[i, i] = 1.0 - P[i].sum()
    return P


def liu_kernel(p):
    """The same proposal with Liu's acceptance, min(1, (1 - p_i) / (1 - p_j))."""
    p = np.asarray(p, float) / np.sum(p)
    k = len(p)
    P = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            if j == i:
                continue
            propose = p[j] / (1.0 - p[i])
            P[i, j] = propose * min(1.0, (1.0 - p[i]) / (1.0 - p[j]))
        P[i, i] = 1.0 - P[i].sum()
    return P


def stationary(P):
    w, v = np.linalg.eig(P.T)
    i = int(np.argmin(np.abs(w - 1.0)))
    pi = np.real(v[:, i])
    return pi / pi.sum()


class LiuCategoricalGibbsMetropolis(pm.CategoricalGibbsMetropolis):
    """PyMC's step with the acceptance ratio Liu (1996) gives for this proposal."""

    def metropolis_proportional(self, q, logp, logp_curr, dim, k):
        given_cat = int(q.data[dim])
        log_probs = np.zeros(k)
        log_probs[given_cat] = logp_curr
        for candidate_cat in range(k):
            if candidate_cat != given_cat:
                q.data[dim] = candidate_cat
                log_probs[candidate_cat] = logp(q)
        probs = special.softmax(log_probs, axis=0)
        prob_curr = probs[given_cat]
        offer = probs.copy()
        offer[given_cat] = 0.0
        if offer.sum() <= 0.0:
            q.data[dim] = given_cat
            return logp_curr
        offer /= offer.sum()
        proposed_cat = self.rng.choice(k, p=offer)
        accept_ratio = (1.0 - prob_curr) / (1.0 - probs[proposed_cat])  # Liu's: p_j itself, not renormalised
        if self.rng.uniform() >= accept_ratio:
            q.data[dim] = given_cat
            return logp_curr
        q.data[dim] = proposed_cat
        return log_probs[proposed_cat]


def main():
    print("PyMC", pm.__version__)
    p = [0.6, 0.3, 0.1]
    for proposal in ("uniform", "proportional"):
        share, first, moves = shares(p, proposal)
        print("p = %s, %-12s shares %s, each chain's share of value 0 %s, moves per draw %.3f"
              % (p, proposal, np.round(share, 3), np.round(first, 3), moves))
    print("stationary law of PyMC's proportional kernel:", np.round(stationary(pymc_kernel(p)), 3))
    print("stationary law of Liu's kernel:               ", np.round(stationary(liu_kernel(p)), 3))
    share, first, moves = shares(p, "proportional", step_cls=LiuCategoricalGibbsMetropolis)
    print("Liu's acceptance in PyMC's step: shares %s, moves per draw %.3f" % (np.round(share, 3), moves))
    for p in ([0.5, 0.5], [0.89, 0.11]):
        share, first, moves = shares(p, "proportional")
        print("p = %s, proportional: shares %s, each chain's share of value 0 %s, moves per draw %.3f"
              % (p, np.round(share, 3), np.round(first, 3), moves))
    try:
        shares([1.0 - 1e-17, 1e-17], "proportional", draws=200)
        print("p all but certain: sampled")
    except Exception as e:  # pm.sample stops: Probabilities contain NaN
        print("p all but certain: pm.sample stopped with %s: %s" % (type(e).__name__, str(e)[:80]))


if __name__ == "__main__":
    main()
