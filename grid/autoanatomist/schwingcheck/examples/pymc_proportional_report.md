# CategoricalGibbsMetropolis(proposal="proportional") does not sample the target: its acceptance ratio is not Liu's

A draft of an issue for pymc-devs/pymc, written on 29 October 2026 against PyMC 6.3.2; the code is the same on `main` at that date (`pymc/step_methods/metropolis.py`, `CategoricalGibbsMetropolis.metropolis_proportional`). It names only PyMC's code, Liu's sampler and a bare Categorical. The reproduction is `pymc_proportional_repro.py` beside this file.

## Description

`CategoricalGibbsMetropolis` with `proposal="proportional"` proposes a new value `j` of a categorical variable with probability `p_j / (1 - p_i)`, `i` the current value, as Liu's Metropolized Gibbs sampler does (the docstring cites Liu 1996). Liu's sampler accepts that proposal with probability `min(1, (1 - p_i) / (1 - p_j))`, which leaves the target stationary. The code computes

```python
probs = special.softmax(log_probs, axis=0)
prob_curr, probs[given_cat] = probs[given_cat], 0.0
probs /= 1.0 - prob_curr                      # the proposal weights, renormalised over the other values
proposed_cat = self.rng.choice(candidates, p=probs)
accept_ratio = (1.0 - prob_curr) / (1.0 - probs[proposed_cat])
```

so the denominator is `1 - p_j / (1 - p_i)`, one less the *renormalised* proposal weight, where Liu's rule takes `1 - p_j`, one less the value's own probability. The resulting kernel is not reversible with respect to the target, and the chain converges to the stationary law of that kernel instead. The chains agree with one another, so R-hat does not show it.

Two further consequences of the same line:

- Where the current value is all but certain, `1 - prob_curr` is 0 in floating point, `probs /= 0` gives NaN, and `pm.sample` stops with `ValueError: Probabilities contain NaN` (or, where it is a rounding error rather than 0, "Probabilities do not sum to 1").
- On two values the proposal is the other value with certainty, so `probs[proposed_cat]` is 1 up to rounding and the acceptance ratio is `(1 - p_i) / 0` or `(1 - p_i) / eps`: whether the chain never moves or moves at every draw is decided by the rounding of the softmax. With `p = [0.5, 0.5]` the chain never leaves its start; with `p = [0.89, 0.11]` it swaps at every draw and reports each value half.

## Reproduction

`python pymc_proportional_repro.py` (PyMC 6.3.2, numpy 2.5.4, scipy 1.18.1) samples `pm.Categorical("x", p=[0.6, 0.3, 0.1])` alone, 4 chains of 4000 draws after 500 tuning steps, seed 13, with each proposal, and writes out the stationary law of the kernel the code's ratio defines:

```
PyMC 6.3.2
p = [0.6, 0.3, 0.1], uniform      shares [0.605 0.294 0.101], each chain's share of value 0 [0.6   0.606 0.614 0.6  ], moves per draw 0.498
p = [0.6, 0.3, 0.1], proportional shares [0.479 0.411 0.11 ], each chain's share of value 0 [0.482 0.472 0.48  0.482], moves per draw 0.932
stationary law of PyMC's proportional kernel: [0.48  0.408 0.112]
stationary law of Liu's kernel:                [0.6 0.3 0.1]
Liu's acceptance in PyMC's step: shares [0.594 0.306 0.099], moves per draw 0.717
metropolis.py:819: RuntimeWarning: divide by zero encountered in scalar divide  (accept_ratio = (1.0 - prob_curr) / (1.0 - probs[proposed_cat]))
p = [0.5, 0.5], proportional: shares [1. 0.], each chain's share of value 0 [1. 1. 1. 1.], moves per draw 0.000
p = [0.89, 0.11], proportional: shares [0.5 0.5], each chain's share of value 0 [0.5 0.5 0.5 0.5], moves per draw 1.000
metropolis.py:817: RuntimeWarning: divide by zero encountered in divide  (probs /= 1.0 - prob_curr)
p all but certain: pm.sample stopped with ParallelSamplingError: Chain 0 failed with: Probabilities contain NaN
```

The uniform proposal recovers 0.6, 0.3, 0.1. The proportional proposal gives about 0.48, 0.41, 0.11 with every chain agreeing, which is the stationary law of its own kernel (0.480, 0.408, 0.112), not the target. The same step with Liu's acceptance ratio in place of the code's (the subclass in the script, one line changed) recovers the target.

## Expected behavior

The proportional proposal should accept with `min(1, (1 - p_i) / (1 - p_j))`, `p_j` the proposed value's own probability (Liu, J. S., 1996, "Peskun's theorem and a modified discrete-state Gibbs sampler", Biometrika 83(3), 681-682; the docstring's "Metropolized Gibbs Sampler: An Improvement", technical report, 1996), so that the chain's stationary law is the target.

## Proposed fix

Keep the proposed value's own probability before renormalising, accept with it, and compute each `1 - p` as the sum of the other values' probabilities (a log-sum-exp of the other log probabilities) so that a value all but certain gives the small chance of a move its law allows rather than a division by zero:

```python
probs = special.softmax(log_probs, axis=0)
prob_curr = probs[given_cat]
offer = probs.copy()
offer[given_cat] = 0.0
away = offer.sum()                                  # 1 - prob_curr, computed as a sum, not a difference
if away <= 0.0:
    q.data[dim] = given_cat
    return logp_curr
proposed_cat = self.rng.choice(candidates, p=offer / away)
accept_ratio = away / (1.0 - probs[proposed_cat])  # Liu's ratio: (1 - p_i) / (1 - p_j)
if self.rng.uniform() >= accept_ratio:
    q.data[dim] = given_cat
    return logp_curr
```

(`1.0 - probs[proposed_cat]` can likewise be summed over the other values when a proposed value is itself all but certain.) A test that samples a bare Categorical of three values with the proportional proposal and checks the shares against `p` within Monte Carlo error would have caught this; the uniform proposal passes such a test today.

## Versions

PyMC 6.3.2, PyTensor 3.3.4, numpy 2.5.4, scipy 1.18.1, Python 3.12.3, Linux x86_64.
