"""tools/domain_gap_stats.py, the numerics of the DRR domain-gap study, on Gaussian clouds drawn
person by person (several rows a person around the person's own offset, the person effect), so
every control has persons in it. Two clouds from one law must look alike: the c2st AUC interval
covers 0.5, the MMD p-value stays above 0.01, KID and the Frechet distance sit near 0. Shifted
clouds must not: the AUC passes 0.9, the MMD p-value reaches its floor, the distance is positive.
A law with a strong person effect must not fool the person-level tests the way a test that counts
rows as independent is fooled. The vectorised forms are checked against the pure rules of
src/schwingnet/domain_gap.py and against direct sums, PRDC against Naeem et al.'s definitions
written as loops, and every map against its shape.

It needs numpy and scikit-learn, and the pure module's pydantic, icontract and beartype, as the
study's job environment holds them (a venv beside train-gpu's packages, grid/bench.sbatch), so it
runs there and is skipped under the required check's python:

    python -m unittest tests/test_domain_gap_stats.py
"""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("numpy", "sklearn", "pydantic", "icontract", "beartype")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]
HAS_TORCH = importlib.util.find_spec("torch") is not None
HAS_UMAP = importlib.util.find_spec("umap") is not None


def load_tool():
    """tools/domain_gap_stats.py by path, without tools/ on sys.path."""
    path = ROOT / "tools" / "domain_gap_stats.py"
    spec = importlib.util.spec_from_file_location("domain_gap_stats_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cloud(rng, persons, rows, dims, *, shift=0.0, person_sd=0.5, noise_sd=1.0, prefix="p"):
    """rows rows for each of persons persons: the person's own Gaussian offset plus row noise, shifted."""
    import numpy as np

    offsets = rng.normal(0.0, person_sd, size=(persons, dims))
    x = np.repeat(offsets, rows, axis=0) + rng.normal(0.0, noise_sd, size=(persons * rows, dims)) + shift
    return x, [f"{prefix}{person}" for person in range(persons) for _ in range(rows)]


def two_clouds(seed, *, shift, persons=40, rows=5, dims=6, person_sd=0.5, noise_sd=1.0):
    """Two clouds of different persons, the second shifted, as one sample with labels 0 and 1."""
    import numpy as np

    rng = np.random.default_rng(seed)
    first, first_persons = cloud(rng, persons, rows, dims, person_sd=person_sd, noise_sd=noise_sd, prefix="a")
    second, second_persons = cloud(rng, persons, rows, dims, shift=shift, person_sd=person_sd,
                                   noise_sd=noise_sd, prefix="b")
    labels = np.r_[np.zeros(len(first), dtype=int), np.ones(len(second), dtype=int)]
    return np.vstack([first, second]), labels, first_persons + second_persons


def direct_mmd2(x, y, kernel):
    """The unbiased MMD^2 as the textbook writes it, pair by pair."""
    m, n = len(x), len(y)
    within_x = sum(kernel(x[i], x[j]) for i in range(m) for j in range(m) if i != j) / (m * (m - 1))
    within_y = sum(kernel(y[i], y[j]) for i in range(n) for j in range(n) if i != j) / (n * (n - 1))
    across = sum(kernel(a, b) for a in x for b in y) / (m * n)
    return within_x + within_y - 2.0 * across


def direct_prdc(real, fake, k):
    """Naeem et al. 2020's precision, recall, density and coverage written as loops."""
    import numpy as np

    def radius(points, i):
        return sorted(np.linalg.norm(points[i] - points[j]) for j in range(len(points)) if j != i)[k - 1]

    real_r = [radius(real, i) for i in range(len(real))]
    fake_r = [radius(fake, j) for j in range(len(fake))]
    d = [[float(np.linalg.norm(a - b)) for b in fake] for a in real]
    precision = np.mean([any(d[i][j] < real_r[i] for i in range(len(real))) for j in range(len(fake))])
    recall = np.mean([any(d[i][j] < fake_r[j] for j in range(len(fake))) for i in range(len(real))])
    density = np.mean([sum(d[i][j] < real_r[i] for i in range(len(real))) for j in range(len(fake))]) / k
    coverage = np.mean([min(d[i]) < real_r[i] for i in range(len(real))])
    return {"precision": precision, "recall": recall, "density": density, "coverage": coverage}


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}: the study's job environment holds them")
class DomainGapStatsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stats = load_tool()
        cls.gap = cls.stats.gap()

    # --- the classifier two-sample test --------------------------------------------------------

    def test_same_law_auc_interval_covers_half(self):
        x, labels, persons = two_clouds(1, shift=0.0)
        scores = self.stats.c2st(x, labels, persons, seed=0)
        result = self.stats.auc_with_interval(scores, labels, persons, boot=1000, seed=0)
        self.assertLessEqual(result["lo"], 0.5)
        self.assertGreaterEqual(result["hi"], 0.5)
        self.assertLessEqual(result["lo"], result["auc"])
        self.assertLessEqual(result["auc"], result["hi"])
        p = self.stats.c2st_permutation_p(x, labels, persons, observed_auc=result["auc"], perms=20, seed=0)
        self.assertGreater(p, 0.05)

    def test_shifted_law_is_separable(self):
        x, labels, persons = two_clouds(2, shift=1.5)
        for model in ("logistic", "knn"):
            scores = self.stats.c2st(x, labels, persons, seed=0, model=model)
            self.assertTrue(((scores >= 0) & (scores <= 1)).all())
            result = self.stats.auc_with_interval(scores, labels, persons, boot=500, seed=0)
            self.assertGreater(result["auc"], 0.9, model)
            self.assertGreater(result["lo"], 0.5, model)
            p = self.stats.c2st_permutation_p(x, labels, persons, observed_auc=result["auc"], perms=20,
                                              seed=0, model=model)
            self.assertAlmostEqual(p, 1 / 21, msg=model)

    def test_auc_is_the_pure_rule(self):
        import numpy as np

        rng = np.random.default_rng(3)
        scores = np.round(rng.random(60), 1)  # rounded, so ties are many
        labels = np.r_[np.zeros(25, dtype=int), np.ones(35, dtype=int)]
        persons = [f"q{i // 3}" for i in range(60)]
        result = self.stats.auc_with_interval(scores, labels, persons, boot=50, seed=0)
        expected = self.gap.mann_whitney_auc(tuple(scores[labels == 1].tolist()),
                                             tuple(scores[labels == 0].tolist()))
        self.assertAlmostEqual(result["auc"], expected, places=12)

    def test_person_folds_keep_each_person_whole_and_both_labels(self):
        import numpy as np

        x, labels, persons = two_clouds(4, shift=0.0, persons=23, rows=3)
        folds = self.stats.person_folds(persons, labels, 5, 0)
        for person in set(persons):
            self.assertEqual(len(set(folds[[p == person for p in persons]])), 1, person)
        self.assertEqual(sorted(set(folds.tolist())), list(range(5)))
        for fold in range(5):
            self.assertEqual(set(labels[folds == fold].tolist()), {0, 1})
        np.testing.assert_array_equal(folds, self.stats.person_folds(persons, labels, 5, 0))
        few = self.stats.person_folds(["a", "a", "b", "c", "d", "e"], np.array([0, 0, 0, 1, 1, 1]), 5, 0)
        self.assertEqual(len(set(few.tolist())), 2)  # k lowered to the two persons label 0 has
        with self.assertRaises(ValueError):
            self.stats.person_folds(["a", "a", "b", "c"], np.array([0, 0, 1, 1]), 5, 0)

    def test_cluster_bootstrap_weights_equal_repeated_rows(self):
        import numpy as np

        rng = np.random.default_rng(5)
        scores = np.round(rng.random(40), 1)
        labels = np.r_[np.zeros(18, dtype=int), np.ones(22, dtype=int)]
        repeats = rng.integers(0, 4, size=40)
        repeats[0], repeats[-1] = 1, 1  # both labels present
        order = np.argsort(scores, kind="stable")
        ordered = scores[order]
        starts = np.flatnonzero(np.r_[True, ordered[1:] != ordered[:-1]])
        weights = repeats[order][None, :].astype(float)
        positive = labels[order] == 1
        fast = self.stats.weighted_auc(weights * positive, weights * ~positive, starts)[0]
        repeated_scores, repeated_labels = np.repeat(scores, repeats), np.repeat(labels, repeats)
        slow = self.gap.mann_whitney_auc(tuple(repeated_scores[repeated_labels == 1].tolist()),
                                         tuple(repeated_scores[repeated_labels == 0].tolist()))
        self.assertAlmostEqual(fast, slow, places=12)

    def test_bootstrap_draws_persons_within_their_label(self):
        import numpy as np

        labels = np.array([0, 0, 0, 1, 1, 1, 1])
        persons = ["a", "a", "b", "c", "c", "c", "d"]
        unit_of_row, unit_label = self.stats.units(labels, persons)
        self.assertEqual(unit_of_row.tolist(), [0, 0, 1, 2, 2, 2, 3])
        self.assertEqual(unit_label.tolist(), [0, 0, 1, 1])
        pools = [np.flatnonzero(unit_label == value) for value in (0, 1)]
        draws = self.stats.unit_draws(np.random.default_rng(0), pools, 4, 300)
        self.assertTrue((draws[:, :2].sum(axis=1) == 2).all())  # label 0 keeps its two persons
        self.assertTrue((draws[:, 2:].sum(axis=1) == 2).all())

    def test_cluster_interval_is_wider_than_row_interval_under_a_person_effect(self):
        x, labels, persons = two_clouds(6, shift=0.4, persons=12, rows=15, person_sd=2.0, noise_sd=0.3)
        scores = self.stats.c2st(x, labels, persons, seed=0)
        by_person = self.stats.auc_with_interval(scores, labels, persons, boot=1000, seed=0)
        by_row = self.stats.auc_with_interval(scores, labels, [str(i) for i in range(len(x))], boot=1000, seed=0)
        self.assertEqual(by_person["auc"], by_row["auc"])
        self.assertGreater(by_person["hi"] - by_person["lo"], 1.5 * (by_row["hi"] - by_row["lo"]))

    # --- MMD -------------------------------------------------------------------------------------

    def test_mmd2_unbiased_matches_direct_sum(self):
        import numpy as np

        rng = np.random.default_rng(7)
        x, y = rng.normal(size=(7, 3)) + 5.0, rng.normal(size=(9, 3)) + 5.5
        h = 1.3

        def gaussian(a, b):
            return float(np.exp(-np.sum((a - b) ** 2) / (2 * h * h)))

        self.assertAlmostEqual(self.stats.mmd2_unbiased(x, y, h), direct_mmd2(x, y, gaussian), places=12)

    def test_mmd_test_observed_is_mmd2_unbiased(self):
        import numpy as np

        rng = np.random.default_rng(8)
        x, y = rng.normal(size=(30, 4)), rng.normal(size=(25, 4)) + 0.3
        px, py = [f"x{i // 3}" for i in range(30)], [f"y{i // 5}" for i in range(25)]
        result = self.stats.mmd_test(x, y, px, py, perms=50, seed=0, backend="numpy")
        pooled = self.stats.median_bandwidth(np.vstack([x, y]), seed=0)
        self.assertAlmostEqual(result["bandwidth"], pooled, places=12)
        self.assertAlmostEqual(result["mmd2"], self.stats.mmd2_unbiased(x, y, result["bandwidth"]), places=10)
        self.assertGreater(result["p"], 0)
        self.assertLessEqual(result["p"], 1)

    def test_mmd_permutation_by_blocks_matches_direct(self):
        import numpy as np

        rng = np.random.default_rng(9)
        z = rng.normal(size=(20, 3))
        unit_of_row = np.array([0, 0, 1, 2, 2, 2, 3, 4, 4, 5, 6, 6, 7, 7, 7, 8, 9, 9, 9, 9])
        blocks = self.stats.unit_kernel_numpy(z, 1.1, unit_of_row)
        counts = np.bincount(unit_of_row).astype(float)
        side = np.array([1, 0, 1, 1, 0, 0, 1, 0, 0, 1], dtype=float)
        fast = self.stats.mmd_from_blocks(blocks, counts, side[None, :])[0]
        rows = side[unit_of_row] == 1
        self.assertAlmostEqual(fast, self.stats.mmd2_unbiased(z[rows], z[~rows], 1.1), places=10)

    def test_mmd_test_same_and_shifted(self):
        import numpy as np

        x, labels, persons = two_clouds(10, shift=0.0)
        persons = np.asarray(persons)
        same = self.stats.mmd_test(x[labels == 0], x[labels == 1], persons[labels == 0], persons[labels == 1],
                                   perms=300, seed=0, backend="numpy")
        self.assertGreater(same["p"], 0.01)
        x, labels, persons = two_clouds(11, shift=1.0)
        persons = np.asarray(persons)
        shifted = self.stats.mmd_test(x[labels == 0], x[labels == 1], persons[labels == 0], persons[labels == 1],
                                      perms=300, seed=0, backend="numpy")
        self.assertLessEqual(shifted["p"], 0.01)
        self.assertGreater(shifted["mmd2"], same["mmd2"])

    def test_mmd_person_level_holds_where_row_level_is_fooled(self):
        """One law, a strong person effect: each person a tight knot far from the others. Counted as
        persons the two sides are alike; counted as independent rows they look different, which is
        the error person-level permutation exists to avoid."""
        import numpy as np

        x, labels, persons = two_clouds(12, shift=0.0, persons=8, rows=15, dims=4, person_sd=3.0, noise_sd=0.3)
        persons = np.asarray(persons)
        first, second = x[labels == 0], x[labels == 1]
        by_person = self.stats.mmd_test(first, second, persons[labels == 0], persons[labels == 1],
                                        perms=500, seed=0, backend="numpy")
        rows = [str(i) for i in range(len(x))]
        by_row = self.stats.mmd_test(first, second, rows[:len(first)], rows[len(first):],
                                     perms=500, seed=0, backend="numpy")
        self.assertGreater(by_person["p"], 0.01)
        self.assertLessEqual(by_row["p"], 0.01)

    @unittest.skipUnless(HAS_TORCH, "torch is not installed")
    def test_mmd_backends_agree(self):
        import numpy as np

        x, labels, persons = two_clouds(13, shift=0.3, persons=15, rows=4)
        persons = np.asarray(persons)
        args = (x[labels == 0], x[labels == 1], persons[labels == 0], persons[labels == 1])
        on_numpy = self.stats.mmd_test(*args, perms=200, seed=0, backend="numpy")
        on_torch = self.stats.mmd_test(*args, perms=200, seed=0, backend="torch")
        self.assertAlmostEqual(on_numpy["mmd2"], on_torch["mmd2"], places=10)
        self.assertAlmostEqual(on_numpy["p"], on_torch["p"], places=12)

    # --- distances ---------------------------------------------------------------------------------

    def test_frechet_distance(self):
        import numpy as np
        from scipy import linalg

        rng = np.random.default_rng(14)
        x = rng.normal(size=(200, 5)) @ rng.normal(size=(5, 5))
        y = rng.normal(size=(150, 5)) @ rng.normal(size=(5, 5)) + 0.7
        self.assertAlmostEqual(self.stats.frechet_distance(x, x), 0.0, places=8)
        s1, s2 = np.cov(x, rowvar=False), np.cov(y, rowvar=False)
        mu = x.mean(axis=0) - y.mean(axis=0)
        reference = mu @ mu + np.trace(s1 + s2 - 2 * linalg.sqrtm(s1 @ s2).real)
        self.assertAlmostEqual(self.stats.frechet_distance(x, y), reference, places=6)
        same_x, same_labels, _ = two_clouds(15, shift=0.0, persons=100, rows=5)
        shifted_x, shifted_labels, _ = two_clouds(15, shift=1.0, persons=100, rows=5)
        same = self.stats.frechet_distance(same_x[same_labels == 0], same_x[same_labels == 1])
        shifted = self.stats.frechet_distance(shifted_x[shifted_labels == 0], shifted_x[shifted_labels == 1])
        self.assertLess(same, 0.2)
        self.assertGreater(shifted, 4.0)  # about ||shift||^2 = 6
        self.assertGreater(shifted, 20 * same)

    def test_frechet_distance_of_diagonal_gaussians(self):
        """For diagonal covariances the distance is ||mu1 - mu2||^2 + sum (sqrt a - sqrt b)^2."""
        import numpy as np

        rng = np.random.default_rng(16)
        x = rng.normal(size=(400, 3)) * [1.0, 2.0, 0.5]
        y = rng.normal(size=(300, 3)) * [3.0, 1.0, 0.5] + [1.0, 0.0, -2.0]
        a, b = np.var(x, axis=0, ddof=1), np.var(y, axis=0, ddof=1)
        # The sample covariances are near diagonal, not exactly, so the closed form is close, not equal.
        mu = x.mean(axis=0) - y.mean(axis=0)
        expected = mu @ mu + np.sum((np.sqrt(a) - np.sqrt(b)) ** 2)
        self.assertAlmostEqual(self.stats.frechet_distance(x, y), expected, delta=0.05 * expected)

    def test_kid(self):
        import numpy as np

        rng = np.random.default_rng(17)
        x, y = rng.normal(size=(12, 4)), rng.normal(size=(12, 4)) + 0.5

        def cubic(a, b):
            return float((a @ b / 4 + 1.0) ** 3)

        whole = self.stats.kid(x, y, subsets=3, subset_size=12, seed=0)
        self.assertAlmostEqual(whole["kid"], direct_mmd2(x, y, cubic), places=10)
        self.assertAlmostEqual(whole["sd"], 0.0, places=10)
        same_x, same_labels, _ = two_clouds(18, shift=0.0, persons=100, rows=5)
        shifted_x, shifted_labels, _ = two_clouds(18, shift=1.0, persons=100, rows=5)
        same = self.stats.kid(same_x[same_labels == 0], same_x[same_labels == 1], subsets=50,
                              subset_size=200, seed=0)
        shifted = self.stats.kid(shifted_x[shifted_labels == 0], shifted_x[shifted_labels == 1], subsets=50,
                                 subset_size=200, seed=0)
        self.assertLess(abs(same["kid"]), 0.05)
        self.assertGreater(shifted["kid"], 10 * max(abs(same["kid"]), same["sd"]))
        self.assertGreater(shifted["sd"], 0)

    def test_prdc(self):
        import numpy as np

        rng = np.random.default_rng(19)
        real = rng.normal(size=(300, 4))
        identical = self.stats.prdc(real, real.copy(), k=5)
        self.assertEqual(identical["precision"], 1.0)
        self.assertEqual(identical["recall"], 1.0)
        self.assertEqual(identical["coverage"], 1.0)
        self.assertAlmostEqual(identical["density"], 1.0, delta=0.15)
        small_real, small_fake = rng.normal(size=(25, 3)), rng.normal(size=(20, 3)) + 0.8
        fast = self.stats.prdc(small_real, small_fake, k=3)
        slow = direct_prdc(small_real, small_fake, 3)
        for key in ("precision", "recall", "density", "coverage"):
            self.assertAlmostEqual(fast[key], slow[key], places=12, msg=key)
        far = self.stats.prdc(real, real + 10.0, k=5)
        self.assertEqual(far, {"precision": 0.0, "recall": 0.0, "density": 0.0, "coverage": 0.0})

    def test_benjamini_hochberg(self):
        import numpy as np

        adjusted = self.stats.benjamini_hochberg(np.array([0.01, 0.04, 0.03, 0.005]))
        np.testing.assert_allclose(adjusted, [0.02, 0.04, 0.04, 0.02])
        self.assertAlmostEqual(self.stats.gap_ratio(3.0, np.array([1.0, 2.0, 4.0])), 1.5)

    # --- neighbourhoods, clusters and the real-group classifier -------------------------------------

    def separated(self):
        """Three groups far apart in different directions (the silhouette is cosine), two real and
        one synthetic, of a hundred rows each, five a person."""
        import numpy as np

        rng = np.random.default_rng(20)
        centres = {name: 8.0 * np.eye(5)[axis] for axis, name in enumerate(("film_a", "fluoro_b", "drr"))}
        rows, groups, persons = [], [], []
        for name, centre in centres.items():
            x, who = cloud(rng, 20, 5, 5, shift=centre, prefix=name)
            rows.append(x)
            groups += [name] * len(x)
            persons += who
        return np.vstack(rows), np.asarray(groups), persons

    def test_neighbourhoods_and_silhouette(self):
        z, groups, _ = self.separated()
        purity = self.stats.knn_purity(z, groups, k=15)
        self.assertEqual(sorted(purity), ["drr", "film_a", "fluoro_b"])
        self.assertTrue(all(value > 0.99 for value in purity.values()))
        families = {"film_a": "film", "fluoro_b": "fluoroscopy", "drr": "synthetic"}
        share = self.stats.neighbour_family_share(z, groups, families, k=15)
        self.assertAlmostEqual(share["drr"]["synthetic"], 1.0)
        for row in share.values():
            self.assertAlmostEqual(sum(row.values()), 1.0)
        by_row = self.stats.neighbour_family_share(z, groups, [families[g] for g in groups], k=15)
        self.assertEqual(share, by_row)
        result = self.stats.silhouette(z, groups, max_points=120, seed=0)
        self.assertGreater(result["overall"], 0.5)
        self.assertEqual(sorted(result["per_group"]), ["drr", "film_a", "fluoro_b"])

    def test_neighbours_leave_the_point_out_even_with_duplicates(self):
        import numpy as np

        z = np.array([[0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [5.0, 5.0], [5.0, 5.1]])
        around = self.stats.neighbours(z, 2)
        for row in range(len(z)):
            self.assertNotIn(row, around[row].tolist())
            self.assertEqual(len(set(around[row].tolist())), 2)

    def test_nearest_real_and_its_accuracy(self):
        import numpy as np

        z, groups, persons = self.separated()
        real = groups != "drr"
        rng = np.random.default_rng(21)
        query, _ = cloud(rng, 10, 3, 5, shift=8.0 * np.eye(5)[1], prefix="q")  # drawn like fluoro_b
        share = self.stats.nearest_real(z[real], groups[real], np.asarray(persons)[real], query, seed=0)
        self.assertEqual(sorted(share), ["film_a", "fluoro_b"])
        self.assertAlmostEqual(sum(share.values()), 1.0)
        self.assertGreater(share["fluoro_b"], 0.9)
        accuracy = self.stats.real_group_accuracy(z[real], groups[real], np.asarray(persons)[real], seed=0)
        self.assertGreater(accuracy["balanced_accuracy"], 0.95)
        self.assertEqual(accuracy["chance"], 0.5)

    def test_person_balanced_weights(self):
        import numpy as np

        weights = self.stats.person_balanced_weights(["a", "a", "a", "b", "b"], ["p", "p", "q", "r", "s"])
        self.assertAlmostEqual(weights.sum(), 5.0)
        self.assertAlmostEqual(weights[0] + weights[1], weights[2])  # each person of a weighs the same
        self.assertAlmostEqual(weights[:3].sum(), weights[3:].sum())  # each group weighs the same
        np.testing.assert_allclose(weights[3], weights[4])

    # --- maps and helpers -----------------------------------------------------------------------

    def test_reductions_and_trust(self):
        import numpy as np

        z, groups, _ = self.separated()
        maps = self.stats.reductions(z, seed=0, groups=groups)
        self.assertEqual(list(maps), ["pca", "tsne", "umap", "lda"])
        for name, value in maps.items():
            if name == "umap" and not HAS_UMAP:
                self.assertIsInstance(value, str)
                continue
            self.assertEqual(value.shape, (len(z), 2), name)
            self.assertTrue(np.isfinite(value).all(), name)
            score = self.stats.trust(z, value, k=10)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
        self.assertGreater(self.stats.trust(z, maps["pca"], k=10), 0.8)
        unsupervised = self.stats.reductions(z, seed=0, methods=("pca", "lda"))
        self.assertIsInstance(unsupervised["lda"], str)
        np.testing.assert_allclose(unsupervised["pca"], maps["pca"])
        with self.assertRaises(ValueError):
            self.stats.reductions(z, methods=("mds",))

    def test_standardise_and_pca(self):
        import numpy as np
        from sklearn.decomposition import PCA

        rng = np.random.default_rng(22)
        x = np.c_[rng.normal(3.0, 2.0, size=(50, 4)), np.full(50, 0.1)]
        scaled = self.stats.standardise(x)
        np.testing.assert_allclose(scaled[:, :4].mean(axis=0), 0.0, atol=1e-12)
        np.testing.assert_allclose(scaled[:, :4].std(axis=0), 1.0)
        self.assertTrue((scaled[:, 4] == 0).all())
        scores, ratio = self.stats.pca(x, 3)
        self.assertEqual(scores.shape, (50, 3))
        np.testing.assert_allclose(ratio, PCA(n_components=3).fit(x).explained_variance_ratio_, rtol=1e-8)
        self.assertTrue((np.diff(ratio) <= 0).all())
        wide = rng.normal(size=(6, 20))
        reference = PCA(n_components=4).fit(wide).explained_variance_ratio_
        np.testing.assert_allclose(self.stats.pca(wide, 4)[1], reference, rtol=1e-8)
        with self.assertRaises(ValueError):
            self.stats.pca(x, 6)

    def test_split_half(self):
        persons = [f"case{i // 3}" for i in range(600)]
        halves = self.stats.split_half(persons, "salt-a")
        self.assertEqual(set(halves.tolist()), {0, 1})
        for start in range(0, 600, 3):
            self.assertEqual(len(set(halves[start:start + 3].tolist())), 1)
        self.assertTrue(0.4 < halves.mean() < 0.6)
        self.assertNotEqual(halves.tolist(), self.stats.split_half(persons, "salt-b").tolist())
        self.assertEqual(halves.tolist(), self.stats.split_half(persons, "salt-a").tolist())

    def test_deterministic_under_seed(self):
        import numpy as np

        x, labels, persons = two_clouds(23, shift=0.5, persons=15, rows=4)
        np.testing.assert_array_equal(self.stats.c2st(x, labels, persons, seed=3),
                                      self.stats.c2st(x, labels, persons, seed=3))
        persons = np.asarray(persons)
        args = (x[labels == 0], x[labels == 1], persons[labels == 0], persons[labels == 1])
        self.assertEqual(self.stats.mmd_test(*args, perms=100, seed=4, backend="numpy"),
                         self.stats.mmd_test(*args, perms=100, seed=4, backend="numpy"))
        self.assertEqual(self.stats.kid(x[:30], x[30:], subsets=10, seed=5),
                         self.stats.kid(x[:30], x[30:], subsets=10, seed=5))

    def test_refuses_bad_input(self):
        import numpy as np

        x, labels, persons = two_clouds(24, shift=0.0, persons=5, rows=2)
        with self.assertRaises(ValueError):
            self.stats.c2st(x, np.full(len(x), 2), persons)
        with self.assertRaises(ValueError):
            self.stats.c2st(x, labels, persons, model="forest")
        bad = x.copy()
        bad[0, 0] = np.nan
        with self.assertRaises(ValueError):
            self.stats.frechet_distance(bad, x)
        with self.assertRaises(ValueError):
            self.stats.mmd_test(x[:4], x[4:8], ["a"] * 4, ["b", "b", "c", "c"], perms=5)
        with self.assertRaises(ValueError):
            self.stats.kid(x, x[:, :3])


if __name__ == "__main__":
    unittest.main()

