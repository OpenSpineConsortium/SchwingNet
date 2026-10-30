"""The column as a chain of levels: the first of step e's methods (TODO.md, item P, step e).

The owner's words of 27 October 2026. At 16:40 UTC, of pymc-extras' automatic marginalisation
of its `DiscreteMarkovChain`, the column as a chain of levels with a missed body and an L6 or a
T13 as its transitions: "i absolutely want this". At 16:43 UTC: "make sure to account for this
feature existing as well https://www.pymc.io/projects/extras/en/latest/developer/extending_marginalization.html
essentially i want reverse-ablation as you gradually try more features/sophisticated methods/to
see how well they improve the accuracy. further you can consider how each will improve with more
data ...". This module is the chain and its exact answer in NumPy; chain_pymc.py holds it as the
two PyMC models the owner's page leads to, and chain_study.py scores it.

The chain. A field is B bodies read in order down a column, and the hidden state of each read
body is (column type, level). The types are the typical column (C3 to L5, 22 levels), the
six-lumbar column (an L6 after L5, 23) and the column with a thirteenth rib-bearing body (a T13
between T12 and L1, 23), so the states number 22 + 23 + 23 = 68 and a path never changes type:
the type is drawn once per column, with prior weight w_T. From one read body to the next the
level moves on k = 1, 2, ... positions down the type's own column, k - 1 bodies missed between
them, with the base law g(k) (step_law: each step misses j bodies with probability (1 - q) q^j,
cut at max_step - 1 and renormalised). A path whose bodies would run off the end of the column is
not a field, so the chain is conditioned on fitting by the h-transform: with h_{B-1} = 1 and

    h_t(T, p) = sum_k g(k) [p + k < n_T] h_{t+1}(T, p + k),

the transitions are P_t(p -> p + k) = g(k) h_{t+1}(p + k) / h_t(p) and the start is
pi(T, p) = w_T h_0(T, p) / sum_p' h_0(T, p'), so that every path of the chain fits, each type
keeps its weight w_T, and a path's probability is w_T prod_t g(k_t) over the fitting (start,
pattern) pairs of its type, normalised. With one step (g(1) = 1) and the typical type alone it is
step d's prior, every place that fits equally likely, and with g uniform over 1 to K it is TODO.md
item 4c's, every fitting (pattern, place) pair equally likely; the tests hold both within 1e-12.

The emissions. Given the path and the patient's size s, a field's values have rule.py's closed
form: a measure's values at the path's levels are jointly normal with the table's means scaled by
s^p and the covariance of the patient's offset, shared by every body of the measure, beside each
body's own draw and the error. The offset is shared, so the likelihood does not factor along the
chain, and the forward algorithm alone cannot sum the path out; the exact answer here enumerates
the chain's support paths instead and integrates the size on rule.py's nodes, as step d's
enumerated patterns do: path_logev with rule.py's own blocks, and prepare and logev, the same sum
read along the paths' shared beginnings, in a small part of its time and the smaller the more
bodies (the section that introduces them; chain_study's speed record gives the times). An L6 and
a T13 take table columns made by the generator's own construction (columns.profiles): L6 = L5 +
0.5 (L5 - L4) with L5's SD, T13 half-way (blend 0.5) between T12 and L1 in mean and SD. That is the generator's, stated, and the exact rule's anomalous
places, item 6, which the owner's other account works on, replace it when they land.

The weights, the probability of a missed body and the longest step are stated choices, not
measured prevalences: SKIP, MAX_STEP and WEIGHTS below.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import LEVELS
from . import columns as C
from . import rule as R

TYPES = ("typical", "six_lumbar", "t13")
NAMES = list(C.DRAW_LEVELS)                 # the levels a body can be named: C3 to L5, then L6 and T13
NAME_INDEX = {n: i for i, n in enumerate(NAMES)}
WEIGHTS = {"typical": 0.9, "six_lumbar": 0.05, "t13": 0.05}     # the types' prior weights, a stated choice
SKIP = 0.2                                  # the step law's ratio, a stated choice: cut at one body missed, a
                                            # step misses one with probability SKIP / (1 + SKIP), 1/6, before
                                            # the fit to the column
MAX_STEP = 2                                # the longest step: one body missed at most between two read


def type_levels(kind: str) -> List[str]:
    """The level names down a column of this type, as the generator lays it out."""
    if kind not in TYPES:
        raise ValueError("the chain's types are %r, not %r" % (TYPES, kind))
    return list(C.phenotype_levels(kind)[0])


def extended_table(mu: np.ndarray, sd: np.ndarray, blend: float = C.SYNTH["blend"]) -> Tuple[np.ndarray, np.ndarray]:
    """The table (measures, 22 levels) extended to NAMES: the 22 as given, then L6 and T13 built
    as the generator builds them (columns._profile, columns.profiles), so a table estimated from
    people is extended the same way as the table as printed."""
    mu, sd = np.asarray(mu, float), np.asarray(sd, float)
    if mu.shape != sd.shape or mu.shape[1] != len(LEVELS):
        raise ValueError("the table is (measures, %d levels): mu %r, sd %r" % (len(LEVELS), mu.shape, sd.shape))
    i4, i5, i12, i1 = (LEVELS.index(l) for l in ("L4", "L5", "T12", "L1"))
    l6_mu = mu[:, i5] + 0.5 * (mu[:, i5] - mu[:, i4])
    t13_mu = (1 - blend) * mu[:, i12] + blend * mu[:, i1]
    t13_sd = (1 - blend) * sd[:, i12] + blend * sd[:, i1]
    return np.column_stack([mu, l6_mu, t13_mu]), np.column_stack([sd, sd[:, i5], t13_sd])


def step_law(skip: float = SKIP, max_step: int = MAX_STEP) -> np.ndarray:
    """g(k) for k = 1 to max_step: a step misses j bodies with probability (1 - skip) skip^j, cut
    at max_step - 1 missed and renormalised; skip 0 is a field of consecutive bodies."""
    if not 0.0 <= skip < 1.0 or max_step < 1:
        raise ValueError("skip is in [0, 1) and max_step at least 1: %r, %r" % (skip, max_step))
    g = (1.0 - skip) * skip ** np.arange(max_step)
    return g / g.sum()


def uniform_steps(max_step: int) -> np.ndarray:
    """Every step from 1 to max_step equally likely: TODO.md item 4c's prior over patterns."""
    return np.full(max_step, 1.0 / max_step)


@dataclass(frozen=True)
class Chain:
    """The chain of levels for fields of n_bodies: its states (type, position in the type's
    column, name), its start law init (S,) and its transitions P (n_bodies - 1, S, S), block
    diagonal by type, each row summing to one."""
    types: Tuple[str, ...]
    weights: Tuple[float, ...]
    steps: Tuple[float, ...]
    n_bodies: int
    state_type: np.ndarray
    state_pos: np.ndarray
    state_name: np.ndarray
    init: np.ndarray
    P: np.ndarray

    @property
    def n_states(self) -> int:
        return len(self.state_type)


def _fit(n: int, steps: np.ndarray, B: int) -> np.ndarray:
    """h (B, n): h[t, p] the base law's probability that a path at position p after body t still
    fits the column with its remaining bodies."""
    h = np.zeros((B, n))
    h[B - 1] = 1.0
    for t in range(B - 2, -1, -1):
        for k, g in enumerate(steps, start=1):
            h[t, :n - k] += g * h[t + 1, k:]
    return h


def build(types: Sequence[str] = TYPES, weights: Optional[Sequence[float]] = None,
          steps: Sequence[float] = (1.0,), n_bodies: int = 3) -> Chain:
    """The chain for fields of n_bodies over these types, with these prior weights (WEIGHTS's,
    renormalised over the types, by default) and this base law of steps, conditioned on fitting
    by the h-transform (the module's docstring)."""
    types = tuple(types)
    g = np.asarray(steps, float)
    if g.ndim != 1 or len(g) == 0 or np.any(g < 0) or abs(g.sum() - 1.0) > 1e-12:
        raise ValueError("steps is a law over 1 to K: %r" % (list(g),))
    w = np.array([WEIGHTS[t] for t in types] if weights is None else weights, float)
    if w.shape != (len(types),) or np.any(w <= 0):
        raise ValueError("one positive weight per type: %r for %r" % (list(w), types))
    w = w / w.sum()
    B = int(n_bodies)
    if B < 1:
        raise ValueError("a field has at least one body")
    st, sp, sn, init, blocks = [], [], [], [], []
    for ti, kind in enumerate(types):
        names = type_levels(kind)
        n = len(names)
        h = _fit(n, g, B)
        if h[0].sum() <= 0:
            raise ValueError("no field of %d bodies fits a %s column" % (B, kind))
        st += [ti] * n
        sp += list(range(n))
        sn += [NAME_INDEX[x] for x in names]
        init.append(w[ti] * h[0] / h[0].sum())
        Pt = np.zeros((max(B - 1, 0), n, n))
        for t in range(B - 1):
            for p in range(n):
                if h[t, p] <= 0:
                    Pt[t, p, p] = 1.0           # a state no fitting path reaches at t: any row will do
                    continue
                for k, gk in enumerate(g, start=1):
                    if p + k < n:
                        Pt[t, p, p + k] = gk * h[t + 1, p + k] / h[t, p]
        blocks.append(Pt)
    S = len(st)
    P = np.zeros((max(B - 1, 0), S, S))
    o = 0
    for Pt in blocks:
        n = Pt.shape[1]
        P[:, o:o + n, o:o + n] = Pt
        o += n
    return Chain(types=types, weights=tuple(w.tolist()), steps=tuple(g.tolist()), n_bodies=B,
                 state_type=np.array(st), state_pos=np.array(sp), state_name=np.array(sn),
                 init=np.concatenate(init), P=P)


def support_paths(init: np.ndarray, P: np.ndarray) -> np.ndarray:
    """Every state path of positive probability, (N, B): from each start of positive probability,
    every move of positive probability, body by body."""
    paths = [[int(s)] for s in np.flatnonzero(init > 0)]
    for t in range(P.shape[0]):
        paths = [p + [int(n)] for p in paths for n in np.flatnonzero(P[t, p[-1]] > 0)]
    return np.array(paths, dtype=np.int64).reshape(len(paths), P.shape[0] + 1)


def path_log_prior(init: np.ndarray, P: np.ndarray, paths: np.ndarray) -> np.ndarray:
    """log p(path) of each state path (N,)."""
    lp = np.log(init[paths[:, 0]])
    for t in range(paths.shape[1] - 1):
        lp = lp + np.log(P[t, paths[:, t], paths[:, t + 1]])
    return lp


@dataclass(frozen=True)
class Paths:
    """The chain's paths as the rule sees them: each distinct path of names (H, B), indices into
    NAMES, its prior (the chain's probability summed over the state paths that read so, since a
    body's values depend on its name alone), the mass of each type in it (H, types), and for each
    one state path that reads so, the type, the start and the offsets down the type's own column,
    which say where rule.py finds its likelihood."""
    names: np.ndarray
    log_prior: np.ndarray
    type_mass: np.ndarray
    rep_type: np.ndarray
    rep_start: np.ndarray
    rep_offsets: Tuple[Tuple[int, ...], ...]

    def __len__(self) -> int:
        return len(self.log_prior)


def paths_of(chain: Chain) -> Paths:
    """The chain's distinct name paths in NumPy's sorted order, each with its prior, its types'
    mass and a state path of the first type in the chain's order that reads so."""
    sp = support_paths(chain.init, chain.P)
    lp = path_log_prior(chain.init, chain.P, sp)
    names = chain.state_name[sp]
    uniq, first, inv = np.unique(names, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    prob = np.zeros(len(uniq))
    np.add.at(prob, inv, np.exp(lp))
    mass = np.zeros((len(uniq), len(chain.types)))
    np.add.at(mass, (inv, chain.state_type[sp[:, 0]]), np.exp(lp))
    order = np.lexsort((np.arange(len(sp)), chain.state_type[sp[:, 0]]))      # the first type wins
    rep = np.full(len(uniq), -1)
    for i in order:
        if rep[inv[i]] < 0:
            rep[inv[i]] = i
    pos = chain.state_pos[sp[rep]]
    return Paths(names=uniq, log_prior=np.log(prob), type_mass=mass / prob[:, None],
                 rep_type=chain.state_type[sp[rep, 0]], rep_start=pos[:, 0],
                 rep_offsets=tuple(tuple(int(o) for o in row - row[0]) for row in pos))


def _groups(paths: Paths) -> Dict[Tuple[int, Tuple[int, ...]], List[int]]:
    """The paths by (type, offsets), the unit rule.py scores at every start at once."""
    out: Dict[Tuple[int, Tuple[int, ...]], List[int]] = {}
    for h in range(len(paths)):
        out.setdefault((int(paths.rep_type[h]), paths.rep_offsets[h]), []).append(h)
    return out


def path_logev(X: np.ndarray, paths: Paths, chain: Chain, mu_ext: np.ndarray, sd_ext: np.ndarray,
               subsets: Dict[str, Sequence[int]], noise: np.ndarray, power: np.ndarray,
               nodes: Tuple[np.ndarray, np.ndarray], block: int = 128) -> Dict[str, np.ndarray]:
    """log p(field | path), the size integrated on the nodes, (fields, paths) under each subset of
    the measures: rule.py's loglik for every (type, offsets) the paths hold, on the type's own
    column of the extended table cut to the starts needed, its blocks built once and the fields
    put through them `block` at a time."""
    X = np.asarray(X, float)
    F = X.shape[0]
    sizes, logw = nodes
    out = {k: np.full((F, len(paths)), np.nan) for k in subsets}
    for (ti, offsets), hs in _groups(paths).items():
        cols = [NAME_INDEX[x] for x in type_levels(chain.types[ti])]
        starts = paths.rep_start[hs]
        lo, hi = int(starts.min()), int(starts.max())
        sub = cols[lo:hi + offsets[-1] + 1]
        mu, sd = np.ascontiguousarray(mu_ext[:, sub]), np.ascontiguousarray(sd_ext[:, sub])
        blocks = R.table_blocks(offsets, mu, sd, R.SYNTH, sizes, noise, power)
        at = starts - lo
        for f0, f1, ll in R.loglik_blocks(X, blocks, len(sizes), hi - lo + 1, block):     # (M, f, J, K)
            ll = ll[..., at]
            for k, idx in subsets.items():
                out[k][f0:f1, hs] = R.logsumexp(ll[list(idx)].sum(0) + logw[None, :, None], 1)
    return out


def posterior(logev: np.ndarray, log_prior: np.ndarray) -> np.ndarray:
    """The posterior over paths (fields, paths)."""
    return R.posterior(logev, log_prior)


def body_posterior(post: np.ndarray, names: np.ndarray, t: int) -> np.ndarray:
    """The posterior of body t's name, (fields, NAMES), summed over the paths."""
    out = np.zeros((post.shape[0], len(NAMES)))
    np.add.at(out.T, names[:, t], post.T)
    return out


def known_pattern_posterior(X: np.ndarray, offsets: np.ndarray, mu: np.ndarray, sd: np.ndarray,
                            subsets: Dict[str, Sequence[int]], noise: np.ndarray, power: np.ndarray,
                            nodes: Tuple[np.ndarray, np.ndarray], t: int) -> Dict[str, np.ndarray]:
    """The rule that knows each field's gaps (item 4c's third rule): the typical column's places
    under the field's own offsets, every place that fits equally likely, as body t's name
    posterior (fields, NAMES)."""
    X, offsets = np.asarray(X, float), np.asarray(offsets, int)
    out = {k: np.zeros((len(X), len(NAMES))) for k in subsets}
    pats, inv = np.unique(offsets, axis=0, return_inverse=True)
    for i, pat in enumerate(pats):
        f = np.flatnonzero(inv.reshape(-1) == i)
        post = R.name(X[f], pat, mu, sd, R.SYNTH, subsets=subsets, noise=noise, power=power, nodes=nodes)
        for k, p in post.items():
            out[k][f[:, None], (np.arange(p.shape[1]) + pat[t])[None, :]] = p
    return out


# ---- the same exact sum, read along the paths' shared beginnings ---------------------------

# path_logev builds rule.py's blocks for every (type, offsets) the paths hold and multiplies each
# field through every one of them, so the work grows with the paths times the bodies times the
# places of each pattern, and at 9 bodies on all 32 measures it took about 2.6 s a field. The same
# closed form is four sums over the bodies, q1, q2, a and ld (rule.table_blocks), and each body's
# term depends on its name alone, so a path's sums are the sums of its bodies' terms, and paths
# that begin with the same names share those sums up to where they part. Only q2 and a enter
# non-linearly, and only within a measure (-0.5 (q1 - q2^2 / (1 + a) + ld + log1p(a))), so q1 and ld
# are summed over the subset's measures before the paths are walked; a depends on the values only
# through which are read, so for a field with every value read it is the table's alone and is
# taken once per path. The paths are walked in NumPy's sorted order, each from where it parts from
# the one before, which visits every distinct beginning once.

@dataclass(frozen=True)
class PathRule:
    """The chain's exact answer for one table, its errors and powers, the subsets of measures and
    the nodes of the size, built once as a service would hold it (prepare), for logev to name
    fields with: the distinct name paths (H, B) and their prior, how many leading names each path
    shares with the one before it, a mask of the subsets' measures (S, M), the table's side of the
    closed form at every name, measure and node (NAMES, M, J), and for a field with every value
    read, 1 / (1 + a) of every path, measure and node (H, M, J) and -0.5 sum log1p(a) over each
    subset's measures (H, S, J)."""
    names: np.ndarray
    log_prior: np.ndarray
    shared: np.ndarray
    keys: Tuple[str, ...]
    mask: np.ndarray
    logw: np.ndarray
    scaled_mu: np.ndarray
    inv_delta: np.ndarray
    u_inv_delta: np.ndarray
    log_delta: np.ndarray
    u2_inv_delta: np.ndarray
    gain: np.ndarray
    log_term: np.ndarray

    @property
    def n_paths(self) -> int:
        return len(self.log_prior)


def shared_beginnings(names: np.ndarray) -> np.ndarray:
    """How many leading names each row shares with the row before it (0 for the first)."""
    names = np.asarray(names)
    out = np.zeros(len(names), np.int64)
    if len(names) > 1:
        same = np.cumprod(names[1:] == names[:-1], axis=1)
        out[1:] = same.sum(1)
    return out


def prepare(paths: Paths, mu_ext: np.ndarray, sd_ext: np.ndarray, subsets: Dict[str, Sequence[int]],
            noise: np.ndarray, power: np.ndarray, nodes: Tuple[np.ndarray, np.ndarray],
            rho: float = R.SYNTH["rho"]) -> PathRule:
    """Everything logev needs that does not depend on the fields: rule.table_blocks' terms at
    every name of the extended table, and each path's a for a field with every value read."""
    sizes, logw = nodes
    mu_ext, sd_ext = np.asarray(mu_ext, float), np.asarray(sd_ext, float)
    M = mu_ext.shape[0]
    noise = R.errors_of(R.SYNTH, M, noise)
    g = R.size_factors(sizes, power, M)[None]                           # (1, M, J)
    mu, sd = mu_ext.T[:, :, None], sd_ext.T[:, :, None]                 # (NAMES, M, 1)
    delta = g * g * (1.0 - rho * rho) * sd * sd + (noise * noise)[None, :, None]
    inv = 1.0 / delta
    u = g * rho * sd
    keys = tuple(subsets)
    mask = np.zeros((len(keys), M))
    for i, k in enumerate(keys):
        mask[i, list(subsets[k])] = 1.0
    names = np.ascontiguousarray(paths.names, np.int64)
    shared = shared_beginnings(names)
    u2 = np.ascontiguousarray(u * u * inv)
    gain = np.empty((len(names), M, len(sizes)))
    log_term = np.empty((len(names), len(keys), len(sizes)))
    _kernels()[1](u2, names, shared, mask, gain, log_term)
    return PathRule(names=names, log_prior=np.asarray(paths.log_prior, float), shared=shared, keys=keys, mask=mask,
                    logw=np.asarray(logw, float), scaled_mu=np.ascontiguousarray(g * mu), inv_delta=np.ascontiguousarray(inv),
                    u_inv_delta=np.ascontiguousarray(u * inv), log_delta=np.ascontiguousarray(np.log(delta)),
                    u2_inv_delta=u2, gain=gain, log_term=log_term)


def logev(rule: PathRule, X: np.ndarray) -> Dict[str, np.ndarray]:
    """log p(field | path), the size integrated on the rule's nodes, (fields, paths) under each
    subset: path_logev's answer, field by field. A value not read (NaN) drops out of its measure's
    sums, as in rule.py."""
    X = np.asarray(X, float)
    F, M, B = X.shape
    if B != rule.names.shape[1] or M != rule.mask.shape[1]:
        raise ValueError("fields of %d bodies and %d measures for a rule of %d and %d"
                         % (B, M, rule.names.shape[1], rule.mask.shape[1]))
    walk, _, terms_of = _kernels()
    out = np.empty((len(rule.keys), F, rule.n_paths))
    S, N, J = len(rule.keys), rule.scaled_mu.shape[0], len(rule.logw)
    c, q2, a = np.empty((B, N, S, J)), np.empty((B, N, M, J)), np.empty((B, N, M, J))
    for f in range(F):
        read = np.isfinite(X[f])
        x = np.ascontiguousarray(np.where(read, X[f], 0.0).T)            # (B, M)
        w = np.ascontiguousarray(read.T.astype(float))
        complete = bool(read.all())
        terms_of(x, w, rule.scaled_mu, rule.inv_delta, rule.u_inv_delta, rule.log_delta, rule.u2_inv_delta,
                 rule.mask, complete, c, q2, a)
        walk(c, q2, a, rule.names, rule.shared, rule.gain, rule.log_term, rule.logw, rule.mask, complete, out[:, f])
    return {k: out[i] for i, k in enumerate(rule.keys)}


_KERNELS = None


def _kernels():
    """The loops over the paths and over a field's bodies, compiled by Numba (which PyMC's
    PyTensor already brings) on first use, so that the module imports without it."""
    global _KERNELS
    if _KERNELS is None:
        import numba
        LOG2PI = R.LOG2PI

        @numba.njit(cache=False)
        def add_along(stack, terms, t, n):
            """stack[t] = stack[t - 1] + terms[t, n], stack[0] = terms[0, n]: one body more on a path."""
            R_, J = stack.shape[1], stack.shape[2]
            if t == 0:
                for i in range(R_):
                    for j in range(J):
                        stack[0, i, j] = terms[0, n, i, j]
            else:
                for i in range(R_):
                    for j in range(J):
                        stack[t, i, j] = stack[t - 1, i, j] + terms[t, n, i, j]

        @numba.njit(cache=False)
        def walk(c, q2, a, names, shared, gain, log_term, logw, mask, complete, out):
            H, B = names.shape
            S, M = mask.shape
            J = logw.shape[0]
            cs = np.empty((B, S, J))
            qs = np.empty((B, M, J))
            sa = np.empty((B, M, J))
            terms = np.empty((S, J))
            v = np.empty(J)
            last = B - 1
            for h in range(H):
                for t in range(shared[h], B):
                    n = names[h, t]
                    add_along(cs, c, t, n)
                    add_along(qs, q2, t, n)
                    if not complete:
                        add_along(sa, a, t, n)
                for s in range(S):
                    for j in range(J):
                        terms[s, j] = cs[last, s, j]
                if complete:
                    for s in range(S):
                        for j in range(J):
                            terms[s, j] += log_term[h, s, j]
                for m in range(M):
                    if complete:
                        for j in range(J):
                            q = qs[last, m, j]
                            v[j] = 0.5 * q * q * gain[h, m, j]
                    else:
                        for j in range(J):
                            q = qs[last, m, j]
                            A = sa[last, m, j]
                            v[j] = 0.5 * q * q / (1.0 + A) - 0.5 * np.log1p(A)
                    for s in range(S):
                        if mask[s, m] != 0.0:
                            for j in range(J):
                                terms[s, j] += v[j]
                for s in range(S):
                    top = -np.inf
                    for j in range(J):
                        x = terms[s, j] + logw[j]
                        terms[s, j] = x
                        if x > top:
                            top = x
                    acc = 0.0
                    for j in range(J):
                        acc += np.exp(terms[s, j] - top)
                    out[s, h] = top + np.log(acc)

        @numba.njit(cache=False)
        def path_a(u2, names, shared, mask, gain, log_term):
            H, B = names.shape
            S, M = mask.shape
            J = u2.shape[2]
            sa = np.empty((B, M, J))
            last = B - 1
            for h in range(H):
                for t in range(shared[h], B):
                    n = names[h, t]
                    if t == 0:
                        for m in range(M):
                            for j in range(J):
                                sa[0, m, j] = u2[n, m, j]
                    else:
                        for m in range(M):
                            for j in range(J):
                                sa[t, m, j] = sa[t - 1, m, j] + u2[n, m, j]
                for s in range(S):
                    for j in range(J):
                        log_term[h, s, j] = 0.0
                for m in range(M):
                    for j in range(J):
                        A = sa[last, m, j]
                        gain[h, m, j] = 1.0 / (1.0 + A)
                    for s in range(S):
                        if mask[s, m] != 0.0:
                            for j in range(J):
                                log_term[h, s, j] -= 0.5 * np.log1p(sa[last, m, j])

        @numba.njit(cache=False)
        def terms_of(x, w, scaled_mu, inv_delta, u_inv_delta, log_delta, u2_inv_delta, mask, complete, c, q2, a):
            """Each body's terms at every name: c, -0.5 (q1 + ld + log 2 pi) summed over each subset's
            measures (B, NAMES, S, J); q2 (B, NAMES, M, J); and a where some value is not read."""
            B, M = x.shape
            N, _, J = scaled_mu.shape
            S = mask.shape[0]
            e = np.empty(J)
            for t in range(B):
                for n in range(N):
                    for s in range(S):
                        for j in range(J):
                            c[t, n, s, j] = 0.0
                    for m in range(M):
                        wt = w[t, m]
                        xt = x[t, m]
                        for j in range(J):
                            r = xt - scaled_mu[n, m, j]
                            q2[t, n, m, j] = wt * r * u_inv_delta[n, m, j]
                            e[j] = -0.5 * wt * (r * r * inv_delta[n, m, j] + log_delta[n, m, j] + LOG2PI)
                        if not complete:
                            for j in range(J):
                                a[t, n, m, j] = wt * u2_inv_delta[n, m, j]
                        for s in range(S):
                            if mask[s, m] != 0.0:
                                for j in range(J):
                                    c[t, n, s, j] += e[j]

        _KERNELS = (walk, path_a, terms_of)
    return _KERNELS


# ---- fields drawn by the chain's own law ----------------------------------------------------

def draw_paths(kind: str, steps: Sequence[float], n_bodies: int, n: int, rng) -> np.ndarray:
    """n paths of positions down a column of this type, (n, B), by the chain's law given the type:
    a start that fits, then each step by the conditioned transitions."""
    ch = build((kind,), (1.0,), steps, n_bodies)
    start = rng.choice(ch.n_states, size=n, p=ch.init)
    out = np.empty((n, ch.n_bodies), np.int64)
    out[:, 0] = start
    for t in range(ch.n_bodies - 1):
        for i in range(n):
            out[i, t + 1] = rng.choice(ch.n_states, p=ch.P[t, out[i, t]])
    return ch.state_pos[out]


def draw_fields(cols: C.Columns, steps: Sequence[float], n_bodies: int, per_column: int, seed: int):
    """per_column fields from each column, drawn by the chain's law given the column's type, which
    is its phenotype: X (fields, measures, bodies), the names read (fields, bodies) as indices into
    NAMES by the column's own names, the offsets (fields, bodies) and the column of each field."""
    rng = np.random.default_rng(seed)
    X, names, offsets, col = [], [], [], []
    for c in range(len(cols)):
        pos = draw_paths(cols.phenotype[c], steps, n_bodies, per_column, rng)
        for row in pos:
            X.append(cols.values[c, row, :].T)
            names.append([NAME_INDEX[cols.levels[c][p]] for p in row])
            offsets.append(row - row[0])
            col.append(c)
    return np.array(X), np.array(names), np.array(offsets), np.array(col)


# ---- the forward algorithm, given the offsets ---------------------------------------------

def state_loglik(X: np.ndarray, chain: Chain, mu_ext: np.ndarray, sd_ext: np.ndarray, log_s: np.ndarray,
                 z: np.ndarray, rho: float, noise: np.ndarray, power: np.ndarray) -> np.ndarray:
    """log p(body's values | state, size, offsets), (draws, fields, B, S): given the patient's size
    and offsets the bodies are independent, each measure's value normal about s^p (mu + rho sd z)
    with variance s^2p (1 - rho^2) sd^2 + noise^2. log_s is (draws, fields), z (draws, fields, M);
    a value not read adds nothing."""
    X = np.asarray(X, float)
    read = np.isfinite(X)
    x = np.where(read, X, 0.0)                                              # (F, M, B)
    lvl = chain.state_name
    mu, sd = mu_ext[:, lvl], sd_ext[:, lvl]                                 # (M, S)
    s = np.exp(np.asarray(power, float)[None, None, :] * np.asarray(log_s, float)[..., None])   # (D, F, M)
    mean = s[..., None] * (mu[None, None] + rho * sd[None, None] * np.asarray(z, float)[..., None])   # (D, F, M, S)
    var = (s * s)[..., None] * (1 - rho * rho) * sd[None, None] ** 2 + (np.asarray(noise, float) ** 2)[None, None, :, None]
    r = x[None, :, :, :, None] - mean[:, :, :, None, :]                     # (D, F, M, B, S)
    ll = -0.5 * (r * r / var[:, :, :, None, :] + np.log(2 * np.pi * var)[:, :, :, None, :])
    return (ll * read[None, :, :, :, None]).sum(2)                          # (D, F, B, S)


def forward_backward(log_e: np.ndarray, init: np.ndarray, P: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """The forward-backward algorithm in log space over the last two axes (..., B, S): each body's
    state marginals (..., B, S) and the log evidence (...)."""
    with np.errstate(divide="ignore"):
        logP, log_init = np.log(P), np.log(init)
    B = log_e.shape[-2]
    a = [log_init + log_e[..., 0, :]]
    for t in range(1, B):
        a.append(_lse(a[-1][..., :, None] + logP[t - 1], -2) + log_e[..., t, :])
    b = [np.zeros_like(a[-1])]
    for t in range(B - 2, -1, -1):
        b.insert(0, _lse(logP[t] + (log_e[..., t + 1, :] + b[0])[..., None, :], -1))
    alpha, beta = np.stack(a, -2), np.stack(b, -2)
    logev = _lse(alpha[..., -1, :], -1)
    return np.exp(alpha + beta - logev[..., None, None]), logev


def _lse(a: np.ndarray, axis: int) -> np.ndarray:
    top = np.max(a, axis=axis, keepdims=True)
    top = np.where(np.isfinite(top), top, 0.0)
    with np.errstate(divide="ignore"):
        return np.squeeze(top, axis) + np.log(np.exp(a - top).sum(axis))


def state_body_posterior(marg: np.ndarray, chain: Chain, t: int) -> np.ndarray:
    """Body t's name posterior (..., NAMES) from the state marginals (..., B, S)."""
    out = np.zeros(marg.shape[:-2] + (len(NAMES),))
    for s, n in enumerate(chain.state_name):
        out[..., n] += marg[..., t, s]
    return out
