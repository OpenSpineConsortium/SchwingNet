"""The numerics of the DRR domain-gap study: how far FleXray's synthetic DRRs sit from each held real
X-ray corpus in a feature space, and how far two real corpora sit from each other, as the separation
tests, distances and maps a machine-learning reviewer expects.

The thread "Compare FleXray DRRs to real X-ray corpora" (2026-10-25) asked for them beside the
dimension-reduction maps; tools/domain_gap.py runs the study as one GPU job (grid/bench.sbatch, id
flexray_drr_gap) and calls these functions on numpy feature arrays, one row an image. They are plain
functions with no state, each deterministic given its seed (on a GPU, up to the order in which
floating-point sums are taken).

Rows of one person (a patient, a study, a CT subject) are not independent: two films of one spine
are more alike than two films of two spines, so a test that counted each row as its own sample
would call two corpora different for holding different people. Every test and interval here
therefore moves a person whole. The classifier two-sample test (c2st) scores every row out of fold
with folds that keep each person in one fold; its interval resamples persons with their rows; its
permutation test and the MMD's relabel persons, each person's rows moving together and the number
of persons on each side kept. A person is counted within its label, so a person name that two
corpora happen to share is two persons in a resample, while a fold still keeps both together. Two
samples of the same persons, as two renders of one CT under two engines are, are a paired sample
(paired=True on the interval, the permutation test and the MMD): a person drawn brings both its
units, and a relabelling swaps a person's two units or leaves them, since under no difference it is
the two sides of one person that are exchangeable, not the persons; the free resampling of twins
as independent persons holds the observed statistic below its own null and reads every shift as no
difference. The measures that carry no test (the Frechet distance, KID, PRDC, neighbour purity,
silhouette) describe the rows as the sample and say nothing about significance.

The pure rules, the AUC by ranks, the permutation p-value with its +1, Benjamini-Hochberg, the
percentile interval and the gap ratio, live in src/schwingnet/domain_gap.py under beethoven-qa's
gate; this module is the numpy around them, and imports that module only when a function needs
it. The bootstrap's replicates use a vectorised weighted form of the same rank AUC, which gives
the same number as the pure rule on the resampled rows, so a thousand replicates cost
milliseconds.

numpy is needed by every function and scikit-learn by the classifiers, folds, neighbours and maps;
torch only moves the MMD's permutations onto a GPU, and umap-learn only adds one map, so each is
imported where it is used and a missing optional one costs only its own result. tools/ never goes
on sys.path, since tools/profile.py would shadow the standard library's profile.
"""

import hashlib
import importlib
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != ROOT / "tools"]
for folder in (ROOT / "vendor" / "beethoven-qa" / "src", ROOT / "src"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import numpy as np  # noqa: E402

# Bootstrap replicates, permutations and KID subsets are summed in blocks of this many, so memory
# stays near BLOCK x rows doubles however many are asked for; each is drawn on its own, so the
# block size never changes what a seed gives.
BLOCK = 200
# Rows of the kernel matrix computed at a time, for the same reason.
KERNEL_ROWS = 1024
# The PCA in front of every classifier, and the one under t-SNE, UMAP and LDA.
CLASSIFIER_COMPONENTS = 64
MAP_COMPONENTS = 50
UMAP_MISSING = "skipped: umap-learn is not installed"


# --- the pure rules and the forms they take --------------------------------------------------


def gap():
    """src/schwingnet/domain_gap.py, the study's pure rules, imported when first needed."""
    return importlib.import_module("schwingnet.domain_gap")


def floats(values):
    """A tuple of Python floats, the form the pure module's type-checked functions take."""
    return tuple(np.asarray(values, dtype=np.float64).ravel().tolist())


def benjamini_hochberg(pvalues):
    """Benjamini-Hochberg adjusted p-values of a list or array, in its order, by the pure rule."""
    return np.asarray(gap().benjamini_hochberg(floats(pvalues)), dtype=np.float64)


def gap_ratio(cross, baseline):
    """A cross distance over the median of the real-real baseline distances, by the pure rule."""
    return float(gap().gap_ratio(float(cross), floats(baseline)))


def matrix(x, name="x", min_rows=1):
    """x as a finite float64 matrix, one row a sample, refused when it is not one."""
    array = np.asarray(x, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] < 1:
        raise ValueError(f"{name} must be a matrix of rows and features, not shape {array.shape}")
    if array.shape[0] < min_rows:
        raise ValueError(f"{name} needs at least {min_rows} rows, not {array.shape[0]}")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} holds NaN or infinity")
    return array


def same_columns(x, y):
    """Refuse two samples whose rows are not in one feature space."""
    if x.shape[1] != y.shape[1]:
        raise ValueError(f"the samples have {x.shape[1]} and {y.shape[1]} features")


def vector(values, name="scores"):
    """values as a finite float64 vector."""
    array = np.asarray(values, dtype=np.float64).ravel()
    if not np.isfinite(array).all():
        raise ValueError(f"{name} holds NaN or infinity")
    return array


def binary_labels(labels, rows):
    """labels as 0 and 1 integers, one a row, with both present."""
    array = np.asarray(labels).ravel()
    if array.shape[0] != rows:
        raise ValueError(f"{array.shape[0]} labels for {rows} rows")
    if not np.isin(array, (0, 1)).all():
        raise ValueError("labels must be 0 or 1")
    array = array.astype(np.int64)
    if array.min() == array.max():
        raise ValueError("both labels must be present")
    return array


def names(values, rows, what):
    """values as a numpy array of strings, one a row."""
    array = np.asarray([str(value) for value in values], dtype=object)
    if array.shape[0] != rows:
        raise ValueError(f"{array.shape[0]} {what} for {rows} rows")
    return array


def units(labels, persons):
    """Each row's unit, a person within its label numbered from 0 in order of first row, and each
    unit's label: what a cluster bootstrap resamples and a permutation relabels."""
    index, unit_of_row, unit_label = {}, np.empty(len(persons), dtype=np.int64), []
    for row, key in enumerate(zip(np.asarray(labels).tolist(), persons)):
        if key not in index:
            index[key] = len(unit_label)
            unit_label.append(key[0])
        unit_of_row[row] = index[key]
    return unit_of_row, np.asarray(unit_label)


def twin_units(labels, persons):
    """A paired sample's units: each row's unit and the units' labels (units), and two aligned
    arrays, every person's unit under label 1 and under label 0, so a resample or a relabelling
    moves a person's two units together; a person under one label alone is refused, since it has
    no twin to move with."""
    unit_of_row, unit_label = units(labels, persons)
    first = {}
    for row, key in enumerate(zip(np.asarray(labels).tolist(), persons)):
        first.setdefault(key, unit_of_row[row])
    people = list(dict.fromkeys(persons))
    alone = [p for p in people if (1, p) not in first or (0, p) not in first]
    if alone:
        raise ValueError("a paired sample has every person under both labels;"
                         f" {len(alone)} of {len(people)} are under one")
    ones = np.array([first[(1, p)] for p in people], dtype=np.int64)
    zeros = np.array([first[(0, p)] for p in people], dtype=np.int64)
    return unit_of_row, unit_label, ones, zeros


def twin_draws(rng, twins, count, size):
    """How many times each of count units is drawn in each of size resamples of a paired sample,
    twins being every person's unit under label 1 and under label 0 (twin_units): persons drawn
    with replacement, a drawn person bringing both its units, so one draw resamples the two sides
    to their own sizes."""
    ones, zeros = twins
    draws = np.zeros((size, count))
    for row in range(size):
        times = np.bincount(rng.integers(0, len(ones), size=len(ones)), minlength=len(ones))
        draws[row, ones] = times
        draws[row, zeros] = times
    return draws


def twin_swaps(rng, unit_label, ones, zeros):
    """The units' labels with each person's two units swapped between the labels or left, by a
    coin each: the relabelling of a paired sample under which, with no difference between the
    sides, the sample is exchangeable; every person stays on both sides, so the number of persons
    per side is kept."""
    swapped = unit_label.copy()
    flip = rng.integers(0, 2, size=len(ones)).astype(bool)
    swapped[ones[flip]] = 0
    swapped[zeros[flip]] = 1
    return swapped


def resampler(labels, persons, paired):
    """The units of a sample and a function drawing size resamples of them (a size x units matrix
    of how many times each unit is drawn): persons drawn with replacement within each label, or,
    paired, persons drawn once with both their units (twin_draws)."""
    if paired:
        unit_of_row, unit_label, ones, zeros = twin_units(labels, persons)
        return unit_of_row, unit_label, lambda rng, size: twin_draws(rng, (ones, zeros), len(unit_label), size)
    unit_of_row, unit_label = units(labels, persons)
    pools = [np.flatnonzero(unit_label == value) for value in (0, 1)]
    return unit_of_row, unit_label, lambda rng, size: unit_draws(rng, pools, len(unit_label), size)


def relabeller(labels, persons, paired):
    """The units of a sample and a function giving the units' labels under one random
    relabelling: the labels shuffled over the units with the number per label kept, or, paired,
    each person's two units swapped or left (twin_swaps)."""
    if paired:
        unit_of_row, unit_label, ones, zeros = twin_units(labels, persons)
        return unit_of_row, unit_label, lambda rng: twin_swaps(rng, unit_label, ones, zeros)
    unit_of_row, unit_label = units(labels, persons)
    return unit_of_row, unit_label, lambda rng: rng.permutation(unit_label)


def subsample(rows, max_points, seed):
    """Sorted row indices: all of them, or max_points drawn without replacement under seed."""
    if rows <= max_points:
        return np.arange(rows)
    return np.sort(np.random.default_rng(seed).choice(rows, size=max_points, replace=False))


# --- scaling and principal components ----------------------------------------------------------


def standardise(x):
    """Each column as z-scores (mean 0, population sd 1); a column of one value throughout becomes 0."""
    x = matrix(x)
    constant = np.ptp(x, axis=0) == 0
    scale = np.where(constant, 1.0, x.std(axis=0))
    scaled = (x - x.mean(axis=0)) / scale
    scaled[:, constant] = 0.0
    return scaled


def pca(x, k, seed=0):
    """The first k principal component scores of x, centred and not scaled, and the share of the
    total variance each explains, by an exact eigendecomposition with each component's largest
    loading made positive; the seed is taken for a uniform call and unused, the solver being exact."""
    x = matrix(x, min_rows=2)
    rows, features = x.shape
    if not 1 <= k <= min(rows, features):
        raise ValueError(f"k must be between 1 and {min(rows, features)}, not {k}")
    centred = x - x.mean(axis=0)
    loadings = top_loadings(centred, k)
    biggest = np.abs(loadings).argmax(axis=0)
    signs = np.sign(loadings[biggest, np.arange(k)])
    loadings = loadings * np.where(signs == 0, 1.0, signs)
    scores = centred @ loadings
    total = float((centred**2).sum())
    ratio = (scores**2).sum(axis=0) / total if total > 0 else np.zeros(k)
    return scores, ratio


def top_loadings(centred, k):
    """The k leading right singular vectors of a centred matrix, as columns: from the feature
    covariance when rows outnumber features, else from the thin SVD."""
    rows, features = centred.shape
    if features <= rows:
        values, vectors = np.linalg.eigh(centred.T @ centred)
        return vectors[:, np.argsort(values)[::-1][:k]]
    return np.linalg.svd(centred, full_matrices=False)[2][:k].T


# --- the classifier two-sample test ----------------------------------------------------------


def person_folds(persons, labels, k, seed):
    """Each row's fold for k-fold cross-validation, every person wholly in one fold and the folds
    balanced per label, by scikit-learn's StratifiedGroupKFold shuffled under seed; each label
    needs two persons, and k is lowered to the fewest persons a label has, so that every fold can
    hold each label."""
    from sklearn.model_selection import StratifiedGroupKFold

    labels = np.asarray(labels).ravel()
    persons = names(persons, len(labels), "persons")
    fewest = min(len(set(persons[labels == value])) for value in np.unique(labels))
    if k < 2 or fewest < 2:
        raise ValueError(f"needs k >= 2 and two persons in every label (k {k}, fewest {fewest})")
    splitter = StratifiedGroupKFold(n_splits=min(k, fewest), shuffle=True, random_state=seed)
    folds = np.full(len(labels), -1, dtype=np.int64)
    for fold, (_, test) in enumerate(splitter.split(np.zeros((len(labels), 1)), labels, persons)):
        folds[test] = fold
    return folds


def classifier(model, features, rows, seed):
    """The c2st pipeline for one fold: StandardScaler, PCA to min(64, features, rows - 1) by an
    exact solver, then LogisticRegression(C=1, max_iter=2000) or KNeighborsClassifier(15)."""
    from sklearn.decomposition import PCA
    from sklearn.linear_model import LogisticRegression
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    components = max(1, min(CLASSIFIER_COMPONENTS, features, rows - 1))
    solver = "covariance_eigh" if rows > features else "full"
    reducer = PCA(n_components=components, svd_solver=solver, random_state=seed)
    if model == "logistic":
        head = LogisticRegression(C=1.0, max_iter=2000)
    elif model == "knn":
        head = KNeighborsClassifier(n_neighbors=min(15, rows))
    else:
        raise ValueError(f"model must be logistic or knn, not {model!r}")
    return make_pipeline(StandardScaler(), reducer, head)


def c2st(x, labels, persons, *, k=5, seed=0, model="logistic"):
    """Out-of-fold probabilities of label 1 from a classifier taught to tell the labels apart, each
    row scored by a model fitted on folds that hold none of its person's rows (person_folds)."""
    x = matrix(x, min_rows=4)
    labels = binary_labels(labels, len(x))
    folds = person_folds(persons, labels, k, seed)
    scores = np.empty(len(x))
    for fold in np.unique(folds):
        test = folds == fold
        if np.unique(labels[~test]).size < 2:
            raise ValueError(f"fold {fold} leaves one label out of its training rows")
        pipeline = classifier(model, x.shape[1], int((~test).sum()), seed)
        pipeline.fit(x[~test], labels[~test])
        column = list(pipeline.classes_).index(1)
        scores[test] = pipeline.predict_proba(x[test])[:, column]
    return scores


def rank_auc(scores, labels):
    """The AUC of scores for label 1 against label 0 by the pure rule (ranks, ties counted half)."""
    return float(gap().mann_whitney_auc(floats(scores[labels == 1]), floats(scores[labels == 0])))


def auc_with_interval(scores, labels, persons, *, boot=1000, seed=0, paired=False):
    """{"auc", "lo", "hi"}: the AUC of the scores by the pure rule and its 95% percentile interval
    from a person-cluster bootstrap, persons drawn with replacement within each label and their
    rows taken whole, or, paired, persons drawn once with their rows under both labels (twin_units),
    the interval of a paired sample. The scores are held fixed, so the interval is the sampling of
    persons and leaves out the variance of fitting the classifier: on Gaussian clouds of one law it
    ran about two-thirds as wide as the AUC's spread from sample to sample and covered 0.5 in 15 of
    20, so it describes the gap and c2st_permutation_p, which refits on every shuffle, is the test."""
    scores = vector(scores)
    labels = binary_labels(labels, len(scores))
    persons = names(persons, len(scores), "persons")
    if boot < 1:
        raise ValueError("boot must be at least 1")
    replicates = cluster_bootstrap_auc(scores, labels, persons, boot, seed, paired)
    lo, hi = gap().percentile_interval(floats(replicates), 0.95)
    return {"auc": rank_auc(scores, labels), "lo": float(lo), "hi": float(hi)}


def cluster_bootstrap_auc(scores, labels, persons, boot, seed, paired=False):
    """boot AUCs, each of the rows of persons drawn with replacement within their label, or, paired,
    of persons drawn with both their labels' rows; a drawn person's rows are weighted by the times
    it was drawn, which is the same as repeating them."""
    unit_of_row, unit_label, draw = resampler(labels, persons, paired)
    order = np.argsort(scores, kind="stable")
    ordered = scores[order]
    starts = np.flatnonzero(np.r_[True, ordered[1:] != ordered[:-1]])
    row_unit, positive = unit_of_row[order], labels[order] == 1
    rng, out = np.random.default_rng(seed), []
    for begin in range(0, boot, BLOCK):
        draws = draw(rng, min(BLOCK, boot - begin))
        weights = draws[:, row_unit]
        out.append(weighted_auc(weights * positive, weights * ~positive, starts))
    return np.concatenate(out)


def unit_draws(rng, pools, count, size):
    """How many times each unit is drawn in each of size resamples, every pool resampled to its
    own size with replacement: a size x count matrix, drawn one resample at a time so the block
    size never changes which resamples a seed gives."""
    draws = np.zeros((size, count))
    for row in range(size):
        for pool in pools:
            draws[row] += np.bincount(pool[rng.integers(0, len(pool), size=len(pool))], minlength=count)
    return draws


def weighted_auc(positive, negative, starts):
    """The AUC for each row of weights over scores sorted ascending whose runs of equal values
    begin at starts: each positive weight times the negative weight below it plus half the
    negative weight level with it, over the product of the two totals."""
    pos = np.add.reduceat(positive, starts, axis=1)
    neg = np.add.reduceat(negative, starts, axis=1)
    below = np.cumsum(neg, axis=1) - neg
    return (pos * (below + 0.5 * neg)).sum(axis=1) / (pos.sum(axis=1) * neg.sum(axis=1))


def c2st_permutation_p(x, labels, persons, *, observed_auc, perms=100, k=5, seed=0, model="logistic",
                       paired=False):
    """The permutation p-value of an observed c2st AUC: persons' labels shuffled with every row of a
    person moving together and the number of persons per label kept, or, paired, each person's two
    labels swapped or left (twin_swaps), the whole c2st rerun on each shuffle with the same k, seed
    and model as the observed one, and the pure +1 rule over the null AUCs; observed_auc must come
    from c2st with those same settings."""
    x = matrix(x, min_rows=4)
    labels = binary_labels(labels, len(x))
    persons = names(persons, len(x), "persons")
    if perms < 1:
        raise ValueError("perms must be at least 1")
    unit_of_row, unit_label, relabel = relabeller(labels, persons, paired)
    rng, null = np.random.default_rng(seed), []
    for _ in range(perms):
        shuffled = relabel(rng)[unit_of_row]
        scores = c2st(x, shuffled, persons, k=k, seed=seed, model=model)
        null.append(rank_auc(scores, shuffled))
    return float(gap().permutation_p(float(observed_auc), tuple(null)))


# --- kernel two-sample test and distances ------------------------------------------------------


def squared_distances(a, b):
    """Every squared Euclidean distance from a row of a to a row of b, clipped at 0 against rounding."""
    d2 = (a * a).sum(axis=1)[:, None] + (b * b).sum(axis=1)[None, :] - 2.0 * (a @ b.T)
    return np.maximum(d2, 0.0)


def self_distances(a):
    """squared_distances of a with itself, its diagonal exactly 0."""
    d2 = squared_distances(a, a)
    np.fill_diagonal(d2, 0.0)
    return d2


def mmd2_unbiased(x, y, bandwidth):
    """The unbiased estimate of the squared maximum mean discrepancy between the rows of x and of y
    under the Gaussian kernel exp(-d^2 / (2 h^2)), every pair of distinct rows counted once."""
    x, y = matrix(x, min_rows=2), matrix(y, "y", min_rows=2)
    same_columns(x, y)
    if not bandwidth > 0:
        raise ValueError("bandwidth must be positive")
    centre = np.vstack([x, y]).mean(axis=0)
    x, y = x - centre, y - centre
    m, n, scale = len(x), len(y), 2.0 * float(bandwidth) ** 2
    within_x = np.exp(-self_distances(x) / scale).sum() - m
    within_y = np.exp(-self_distances(y) / scale).sum() - n
    across = np.exp(-squared_distances(x, y) / scale).sum()
    return float(within_x / (m * (m - 1)) + within_y / (n * (n - 1)) - 2.0 * across / (m * n))


def median_bandwidth(z, max_points=2000, seed=0):
    """The median Euclidean distance between distinct rows of z, over at most max_points rows drawn
    under seed; the median of the non-zero distances where more than half are zero, and 1 where all are."""
    z = matrix(z, "z", min_rows=2)
    z = z[subsample(len(z), max_points, seed)]
    z = z - z.mean(axis=0)
    upper = np.sqrt(self_distances(z)[np.triu_indices(len(z), k=1)])
    median = float(np.median(upper))
    if median > 0:
        return median
    positive = upper[upper > 0]
    return float(np.median(positive)) if positive.size else 1.0


def mmd_test(x, y, persons_x, persons_y, *, perms=1000, seed=0, backend="auto", paired=False):
    """{"mmd2", "p", "bandwidth"}: the unbiased MMD^2 between x and y under a Gaussian kernel whose
    bandwidth is the pooled sample's median distance, and its permutation p-value with persons
    relabelled whole and the number of persons per side kept, or, paired, with each person, on
    both sides, swapped between the sides or left (twin_swaps). One pooled kernel matrix is summed
    into person blocks once, so each permutation costs a product of a 0/1 vector with that small
    matrix; backend "auto" uses torch on CUDA where it is there and numpy otherwise, "numpy" and
    "torch" (on CUDA when available, else the CPU) force one."""
    x, y = matrix(x, min_rows=2), matrix(y, "y", min_rows=2)
    same_columns(x, y)
    if perms < 1:
        raise ValueError("perms must be at least 1")
    side = np.r_[np.ones(len(x), dtype=np.int64), np.zeros(len(y), dtype=np.int64)]
    persons = [*names(persons_x, len(x), "persons_x"), *names(persons_y, len(y), "persons_y")]
    unit_of_row, unit_label, relabel = relabeller(side, persons, paired)
    if min((unit_label == 1).sum(), (unit_label == 0).sum()) < 2:
        raise ValueError("each side needs at least two persons")
    z = np.vstack([x, y])
    z -= z.mean(axis=0)
    bandwidth = median_bandwidth(z, seed=seed)
    rng = np.random.default_rng(seed)
    sides = np.stack([unit_label] + [relabel(rng) for _ in range(perms)])
    statistics = mmd_by_sides(z, bandwidth, unit_of_row, sides.astype(np.float64), backend)
    p = gap().permutation_p(float(statistics[0]), floats(statistics[1:]))
    return {"mmd2": float(statistics[0]), "p": float(p), "bandwidth": float(bandwidth)}


def mmd_by_sides(z, bandwidth, unit_of_row, sides, backend):
    """The unbiased MMD^2 for each row of sides, a 0/1 vector over units (1 = the first sample),
    from the Gaussian kernel of z summed into unit blocks; with torch, the kernel and the
    permutations' products both run on its device."""
    torch, device = torch_device(backend)
    counts = np.bincount(unit_of_row).astype(np.float64)
    if torch is None:
        return mmd_from_blocks(unit_kernel_numpy(z, bandwidth, unit_of_row), counts, sides)
    blocks = unit_kernel_torch(torch, device, z, bandwidth, unit_of_row)
    within = within_sums_torch(torch, blocks, sides)
    return mmd_from_blocks(blocks.cpu().numpy(), counts, sides, within)


def torch_device(backend):
    """(torch, device) for the backend asked, or (None, None) for numpy."""
    if backend not in ("auto", "numpy", "torch"):
        raise ValueError(f"backend must be auto, numpy or torch, not {backend!r}")
    if backend == "numpy":
        return None, None
    try:
        import torch
    except ImportError:
        if backend == "torch":
            raise
        return None, None
    if torch.cuda.is_available():
        return torch, torch.device("cuda")
    return (torch, torch.device("cpu")) if backend == "torch" else (None, None)


def unit_kernel_numpy(z, bandwidth, unit_of_row):
    """The units x units matrix of Gaussian kernel sums, block (p, q) the sum over the rows of unit
    p and of unit q, a point's kernel with itself exactly 1; made KERNEL_ROWS rows at a time."""
    count, scale = int(unit_of_row.max()) + 1, 2.0 * bandwidth**2
    order = np.argsort(unit_of_row, kind="stable")
    z, row_unit = z[order], unit_of_row[order]
    column_starts = np.flatnonzero(np.r_[True, row_unit[1:] != row_unit[:-1]])
    squares, blocks = (z * z).sum(axis=1), np.zeros((count, count))
    for begin in range(0, len(z), KERNEL_ROWS):
        end = min(begin + KERNEL_ROWS, len(z))
        d2 = np.maximum(squares[begin:end, None] + squares[None, :] - 2.0 * (z[begin:end] @ z.T), 0.0)
        d2[np.arange(end - begin), np.arange(begin, end)] = 0.0
        by_column = np.add.reduceat(np.exp(-d2 / scale), column_starts, axis=1)
        here, first = np.unique(row_unit[begin:end], return_index=True)
        blocks[here] += np.add.reduceat(by_column, first, axis=0)
    return blocks


def unit_kernel_torch(torch, device, z, bandwidth, unit_of_row):
    """unit_kernel_numpy in float64 on a torch device, left there as a tensor; the rows are sorted
    by unit and each unit's sums taken as differences of running sums, which a GPU computes in a
    fixed order, so the result does not change from run to run."""
    count, scale = int(unit_of_row.max()) + 1, 2.0 * bandwidth**2
    order = np.argsort(unit_of_row, kind="stable")
    row_unit = unit_of_row[order]
    points = torch.as_tensor(z[order], dtype=torch.float64, device=device)
    column_ends = torch.as_tensor(run_ends(row_unit), device=device)
    squares = (points * points).sum(dim=1)
    blocks = torch.zeros((count, count), dtype=torch.float64, device=device)
    for begin in range(0, len(z), KERNEL_ROWS):
        end = min(begin + KERNEL_ROWS, len(z))
        cross = points[begin:end] @ points.T
        d2 = (squares[begin:end, None] + squares[None, :] - 2.0 * cross).clamp_min(0.0)
        index = torch.arange(end - begin, device=device)
        d2[index, index + begin] = 0.0
        by_column = run_sums(torch, torch.exp(-d2 / scale), column_ends, 1)
        local_ends = run_ends(row_unit[begin:end])
        here = torch.as_tensor(row_unit[begin:end][local_ends], device=device)
        blocks[here] += run_sums(torch, by_column, torch.as_tensor(local_ends, device=device), 0)
    return blocks


def run_ends(sorted_units):
    """The index of the last row of each run of equal units in a sorted array."""
    return np.r_[np.flatnonzero(sorted_units[1:] != sorted_units[:-1]), len(sorted_units) - 1]


def run_sums(torch, values, ends, dim):
    """The sums of consecutive runs of a tensor along dim, each run ending at an index of ends, as
    differences of the running sum taken at those ends."""
    running = values.cumsum(dim=dim).index_select(dim, ends)
    size = running.shape[dim]
    later = running.narrow(dim, 1, size - 1) - running.narrow(dim, 0, size - 1)
    return torch.cat([running.narrow(dim, 0, 1), later], dim=dim)


def within_sums(blocks, sides):
    """The kernel sum within the first sample, side' B side, for each 0/1 row of sides."""
    parts = [sides[begin:begin + BLOCK] for begin in range(0, len(sides), BLOCK)]
    return np.concatenate([((part @ blocks) * part).sum(axis=1) for part in parts])


def within_sums_torch(torch, blocks, sides):
    """within_sums on the torch device that holds blocks."""
    out = []
    for begin in range(0, len(sides), BLOCK):
        part = torch.as_tensor(sides[begin:begin + BLOCK], dtype=torch.float64, device=blocks.device)
        out.append(((part @ blocks) * part).sum(dim=1).cpu().numpy())
    return np.concatenate(out)


def mmd_from_blocks(blocks, counts, sides, within=None):
    """The unbiased MMD^2 for each 0/1 row of sides, from the unit kernel sums, the rows per unit
    and the within_sums (computed here unless given): the within sums less their diagonal (one per
    row) over m(m-1) and n(n-1), the across sum over mn."""
    within_x = within_sums(blocks, sides) if within is None else within
    row_sums, total, rows = blocks.sum(axis=1), float(blocks.sum()), float(counts.sum())
    reach = sides @ row_sums
    across = reach - within_x
    within_y = total - 2.0 * reach + within_x
    m = sides @ counts
    n = rows - m
    return (within_x - m) / (m * (m - 1)) + (within_y - n) / (n * (n - 1)) - 2.0 * across / (m * n)


def psd_sqrt(matrix_):
    """The symmetric square root of a symmetric positive semi-definite matrix, by eigh with its
    eigenvalues clipped at 0 against rounding."""
    values, vectors = np.linalg.eigh((matrix_ + matrix_.T) / 2.0)
    return (vectors * np.sqrt(np.clip(values, 0.0, None))) @ vectors.T


def frechet_distance(x, y):
    """The Frechet distance between Gaussians fitted to x and y, ||mu1 - mu2||^2 + Tr(S1 + S2 -
    2 (S1 S2)^(1/2)), the trace of the root taken as the sum of square roots of the eigenvalues of
    the symmetric S1^(1/2) S2 S1^(1/2), which has the eigenvalues of S1 S2; clipped at 0."""
    x, y = matrix(x, min_rows=2), matrix(y, "y", min_rows=2)
    same_columns(x, y)
    difference = x.mean(axis=0) - y.mean(axis=0)
    first = np.atleast_2d(np.cov(x, rowvar=False))
    second = np.atleast_2d(np.cov(y, rowvar=False))
    root = psd_sqrt(first)
    middle = root @ second @ root
    eigenvalues = np.clip(np.linalg.eigvalsh((middle + middle.T) / 2.0), 0.0, None)
    value = difference @ difference + np.trace(first) + np.trace(second) - 2.0 * np.sqrt(eigenvalues).sum()
    return float(max(value, 0.0))


def kid(x, y, *, subsets=100, subset_size=None, seed=0):
    """{"kid", "sd"}: the kernel inception distance, the mean over subsets of the unbiased MMD^2
    under the cubic kernel k(a, b) = (a.b / d + 1)^3 between subset_size rows of x and of y drawn
    without replacement (min(1000, rows) by default), and the subsets' standard deviation (ddof 1);
    on the features as given, since this kernel is not translation invariant. Where neither sample
    has more rows than the subset, every subset is the whole of both and sd is 0, as in the usual
    implementations; a smaller subset_size gives a spread."""
    x, y = matrix(x, min_rows=2), matrix(y, "y", min_rows=2)
    same_columns(x, y)
    size = min(1000, len(x), len(y)) if subset_size is None else int(subset_size)
    if not 2 <= size <= min(len(x), len(y)) or subsets < 1:
        raise ValueError(f"subset_size must be between 2 and {min(len(x), len(y))} and subsets at least 1")
    features = x.shape[1]
    within_x, within_y = (x @ x.T / features + 1.0) ** 3, (y @ y.T / features + 1.0) ** 3
    across = (x @ y.T / features + 1.0) ** 3
    rng, values = np.random.default_rng(seed), []
    for begin in range(0, subsets, BLOCK):
        pick_x, pick_y = subset_indicators(rng, len(x), len(y), size, min(BLOCK, subsets - begin))
        sum_x = ((pick_x @ within_x) * pick_x).sum(axis=1) - pick_x @ np.diag(within_x)
        sum_y = ((pick_y @ within_y) * pick_y).sum(axis=1) - pick_y @ np.diag(within_y)
        sum_xy = ((pick_x @ across) * pick_y).sum(axis=1)
        values.append((sum_x + sum_y) / (size * (size - 1)) - 2.0 * sum_xy / (size * size))
    values = np.concatenate(values)
    return {"kid": float(values.mean()), "sd": float(values.std(ddof=1)) if len(values) > 1 else 0.0}


def subset_indicators(rng, rows_x, rows_y, size, count):
    """count pairs of 0/1 vectors marking size rows of x and size rows of y, each set drawn
    without replacement."""
    pick_x, pick_y = np.zeros((count, rows_x)), np.zeros((count, rows_y))
    for subset in range(count):
        pick_x[subset, rng.choice(rows_x, size=size, replace=False)] = 1.0
        pick_y[subset, rng.choice(rows_y, size=size, replace=False)] = 1.0
    return pick_x, pick_y


def kth_neighbour_distance(z, k):
    """Each row's Euclidean distance to its k-th nearest other row (the k+1-th smallest counting
    itself at distance 0, as Naeem et al.'s code takes it)."""
    distances = np.sqrt(self_distances(z))
    return np.partition(distances, k, axis=1)[:, k]


def prdc(real, fake, *, k=5):
    """{"precision", "recall", "density", "coverage"} as Naeem et al. 2020 define them on
    k-nearest-neighbour balls in Euclidean space: precision the share of fake rows inside some real
    row's ball, recall the share of real rows inside some fake row's ball, density the real balls
    holding each fake row counted and divided by k, averaged, and coverage the share of real rows
    whose own ball holds a fake row; strict inequality throughout, as their code has it."""
    real, fake = matrix(real, "real", min_rows=k + 1), matrix(fake, "fake", min_rows=k + 1)
    same_columns(real, fake)
    if k < 1:
        raise ValueError("k must be at least 1")
    centre = np.vstack([real, fake]).mean(axis=0)
    real, fake = real - centre, fake - centre
    real_radii, fake_radii = kth_neighbour_distance(real, k), kth_neighbour_distance(fake, k)
    distances = np.sqrt(squared_distances(real, fake))
    inside_real = distances < real_radii[:, None]
    return {
        "precision": float(inside_real.any(axis=0).mean()),
        "recall": float((distances < fake_radii[None, :]).any(axis=1).mean()),
        "density": float(inside_real.sum(axis=0).mean() / k),
        "coverage": float((distances.min(axis=1) < real_radii).mean()),
    }


# --- neighbourhoods and clusters -------------------------------------------------------------


def neighbours(z, k):
    """Each row's k nearest other rows (Euclidean), itself left out even where a duplicate ties with it."""
    from sklearn.neighbors import NearestNeighbors

    z = matrix(z, "z", min_rows=k + 1)
    if k < 1:
        raise ValueError("k must be at least 1")
    index = NearestNeighbors(n_neighbors=k + 1).fit(z).kneighbors(z, return_distance=False)
    keep = index != np.arange(len(z))[:, None]
    keep[keep.all(axis=1), -1] = False
    return index[keep].reshape(len(z), k)


def knn_purity(z, groups, *, k=15):
    """For each group, the mean share of its points' k nearest neighbours that are in the same group."""
    z = matrix(z, "z")
    groups = names(groups, len(z), "groups")
    same = groups[neighbours(z, k)] == groups[:, None]
    share = same.mean(axis=1)
    return {group: float(share[groups == group].mean()) for group in sorted(set(groups))}


def neighbour_family_share(z, groups, families, *, k=15):
    """For each group, the share of its points' k nearest neighbours in each family; families is a
    mapping from group to family or one family a row, and every family seen is listed."""
    z = matrix(z, "z")
    groups = names(groups, len(z), "groups")
    if isinstance(families, Mapping):
        family = names([families[group] for group in groups], len(z), "families")
    else:
        family = names(families, len(z), "families")
    around = family[neighbours(z, k)]
    seen = sorted(set(family))
    return {
        group: {name: float((around[groups == group] == name).mean()) for name in seen}
        for group in sorted(set(groups))
    }


def stratified_rows(groups, max_points, seed):
    """Sorted row indices: all of them, or about max_points with each group keeping its share and
    at least two rows (or all it has), so a small group is never left out."""
    if len(groups) <= max_points:
        return np.arange(len(groups))
    rng, chosen = np.random.default_rng(seed), []
    for group in sorted(set(groups)):
        rows = np.flatnonzero(groups == group)
        quota = min(len(rows), max(2, round(max_points * len(rows) / len(groups))))
        chosen.append(rng.choice(rows, size=quota, replace=False))
    return np.sort(np.concatenate(chosen))


def silhouette(z, groups, *, max_points=5000, seed=0):
    """{"overall", "per_group": {...}}: the mean cosine silhouette of the points, over all and per
    group, on a stratified sample of at most about max_points rows."""
    from sklearn.metrics import silhouette_samples

    z = matrix(z, "z", min_rows=3)
    groups = names(groups, len(z), "groups")
    if len(set(groups)) < 2:
        raise ValueError("silhouette needs at least two groups")
    rows = stratified_rows(groups, max_points, seed)
    values, kept = silhouette_samples(z[rows], groups[rows].astype(str), metric="cosine"), groups[rows]
    per_group = {group: float(values[kept == group].mean()) for group in sorted(set(kept))}
    return {"overall": float(values.mean()), "per_group": per_group}


def person_balanced_weights(groups, persons):
    """A weight a row in which every person of a group weighs the same and every group weighs the
    same in all, so neither a large corpus nor a person with many images pulls the fit its way."""
    rows_of = {}
    for key in zip(groups, persons):
        rows_of[key] = rows_of.get(key, 0) + 1
    persons_in = {}
    for group, _ in rows_of:
        persons_in[group] = persons_in.get(group, 0) + 1
    weights = np.array([1.0 / (rows_of[key] * persons_in[key[0]]) for key in zip(groups, persons)])
    return weights * len(weights) / weights.sum()


def real_classifier(features, rows, seed):
    """The real-group classifier: StandardScaler, PCA to min(64, features, rows - 1), multinomial
    LogisticRegression(C=1, max_iter=2000)."""
    return classifier("logistic", features, rows, seed)


def fit_real(x_real, groups_real, persons_real, seed):
    """The real-group classifier fitted on real rows with person-balanced weights."""
    model = real_classifier(x_real.shape[1], len(x_real), seed)
    weights = person_balanced_weights(groups_real, persons_real)
    model.fit(x_real, groups_real.astype(str), logisticregression__sample_weight=weights)
    return model


def nearest_real(x_real, groups_real, persons_real, x_query, *, seed=0):
    """For the query rows, the share a classifier of the real groups alone (scaler, PCA 64,
    multinomial logistic regression, persons and groups weighted equally) assigns to each real
    group: which real corpus the synthetic images look most like; every real group is listed."""
    x_real, x_query = matrix(x_real, "x_real", min_rows=3), matrix(x_query, "x_query")
    same_columns(x_real, x_query)
    groups = names(groups_real, len(x_real), "groups_real")
    persons = names(persons_real, len(x_real), "persons_real")
    if len(set(groups)) < 2:
        raise ValueError("nearest_real needs at least two real groups")
    predicted = fit_real(x_real, groups, persons, seed).predict(x_query)
    return {group: float(np.mean(predicted == group)) for group in sorted(set(groups))}


def real_group_accuracy(x_real, groups_real, persons_real, *, k=5, seed=0):
    """{"accuracy", "balanced_accuracy", "chance"}: how well nearest_real's classifier tells the real
    groups apart out of fold, every person wholly in one fold (person_folds), so a share it gives a
    query can be read against how sure it is on real images; chance is one over the groups."""
    x_real = matrix(x_real, "x_real", min_rows=4)
    groups = names(groups_real, len(x_real), "groups_real")
    persons = names(persons_real, len(x_real), "persons_real")
    folds = person_folds(persons, groups.astype(str), k, seed)
    predicted = np.empty(len(x_real), dtype=object)
    for fold in np.unique(folds):
        test = folds == fold
        model = fit_real(x_real[~test], groups[~test], persons[~test], seed)
        predicted[test] = model.predict(x_real[test])
    seen = sorted(set(groups))
    recalls = [np.mean(predicted[groups == group] == group) for group in seen]
    return {"accuracy": float(np.mean(predicted == groups)), "balanced_accuracy": float(np.mean(recalls)),
            "chance": 1.0 / len(seen)}


# --- maps -----------------------------------------------------------------------------------


def reductions(z, *, seed=0, methods=("pca", "tsne", "umap", "lda"), groups=None):
    """Two-dimensional maps of z by name, each an n x 2 array, or a sentence saying why it was
    skipped: pca on z itself; tsne (perplexity 30, PCA init, automatic learning rate, 1000
    iterations), umap (30 neighbours, min_dist 0.1) and lda (supervised by groups, so it shows
    separation it was taught, and the figure must say so) on z's first 50 principal components."""
    z = matrix(z, "z", min_rows=4)
    base = pca(z, min(MAP_COMPONENTS, *z.shape), seed)[0]
    makers = {"pca": lambda: pca(z, 2, seed)[0], "tsne": lambda: tsne_map(base, seed),
              "umap": lambda: umap_map(base, seed), "lda": lambda: lda_map(base, groups)}
    unknown = [method for method in methods if method not in makers]
    if unknown:
        raise ValueError(f"unknown maps {unknown}; known: {sorted(makers)}")
    return {method: makers[method]() for method in methods}


def tsne_map(base, seed):
    """scikit-learn's t-SNE of the principal components, the perplexity lowered for a small sample."""
    from sklearn.manifold import TSNE

    perplexity = max(1.0, min(30.0, (len(base) - 1) / 3.0))
    return TSNE(n_components=2, perplexity=perplexity, init="pca", learning_rate="auto",
                max_iter=1000, random_state=seed).fit_transform(base)


def umap_map(base, seed):
    """UMAP of the principal components, single-threaded so the seed fixes it, or why it was skipped."""
    try:
        import umap
    except ImportError:
        return UMAP_MISSING
    reducer = umap.UMAP(n_components=2, n_neighbors=min(30, len(base) - 1), min_dist=0.1,
                        random_state=seed, n_jobs=1)
    return np.asarray(reducer.fit_transform(base), dtype=np.float64)


def lda_map(base, groups):
    """Linear discriminant analysis of the principal components onto two axes, or why it was
    skipped: scikit-learn keeps only the axes the group means span, so groups whose means lie on
    one line, as a replication's twins of the production renders do, give one axis and no map."""
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

    if groups is None:
        return "skipped: lda is supervised and needs groups"
    labels = names(groups, len(base), "groups").astype(str)
    if len(set(labels)) < 3:
        return "skipped: lda draws two axes only from three or more groups"
    mapped = LinearDiscriminantAnalysis(n_components=2).fit_transform(base, labels)
    if mapped.shape[1] < 2:
        return "skipped: lda found one axis, the group means lying on one line"
    return mapped


def trust(z_high, z_low, *, k=10, max_points=5000, seed=0):
    """scikit-learn's trustworthiness of a map: how far each point's k nearest neighbours in the map
    were its neighbours in the features, 1 for a faithful map, on at most max_points rows drawn
    under seed; k is lowered below half the rows, which the measure needs."""
    from sklearn.manifold import trustworthiness

    high, low = matrix(z_high, "z_high", min_rows=3), matrix(z_low, "z_low", min_rows=3)
    if len(high) != len(low):
        raise ValueError(f"{len(high)} rows in the features and {len(low)} in the map")
    rows = subsample(len(high), max_points, seed)
    neighbours_used = min(k, (len(rows) - 1) // 2)
    if neighbours_used < 1:
        raise ValueError("too few rows for trustworthiness")
    return float(trustworthiness(high[rows], low[rows], n_neighbors=neighbours_used))


def split_half(persons, salt):
    """0 or 1 for each row by a hash of its person and salt, about half each with no person in both:
    the real-real baseline of a corpus against itself. The hashed text differs from the one
    schwingnet.domain_gap.choose ranks persons by, so which half a person falls in is unrelated to
    whether choose kept it."""
    halves = [int(hashlib.sha256(f"{salt}:half:{person}".encode()).hexdigest(), 16) & 1 for person in persons]
    return np.asarray(halves, dtype=np.int64)
