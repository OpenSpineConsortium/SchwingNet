"""The correlation two measures would show in a sample that pools the sexes, if within each sex
they were uncorrelated: k*g1*g2 / sqrt((1+k*g1^2)(1+k*g2^2)), k = p(1-p). g from the
covariates report (job 40878978), autoPET adults at T10 and over T10-L5 per person."""
import itertools, math
p = 478 / (478 + 376); k = p * (1 - p)
g_t10 = {"endplate": 1.372, "endplate_depth": 1.499, "endplate_lower": 1.540, "endplate_lower_depth": 1.528, "h_post": 0.946}
g_mean = {"endplate": 1.666, "endplate_depth": 1.825, "endplate_lower": 1.713, "endplate_lower_depth": 1.799, "h_post": 1.042}
print("k = %.4f" % k)
for name, g in (("T10", g_t10), ("T10-L5 person mean", g_mean)):
    for a, b in itertools.combinations(g, 2):
        r = k * g[a] * g[b] / math.sqrt((1 + k * g[a] ** 2) * (1 + k * g[b] ** 2))
        print("%-20s %-22s %-22s floor %.3f" % (name, a, b, r))
