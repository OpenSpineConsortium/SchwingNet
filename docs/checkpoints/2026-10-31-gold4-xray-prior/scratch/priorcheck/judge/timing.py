import time, numpy as np
import check_proto as P, truths as T
from schwingcheck import correlation as CORR
rl0, rm0 = T.published()
rng = np.random.default_rng(1)
v = T.draw(rng, T.truth("separable", rl0, rm0), 693)
z, _, _ = CORR.standardise(v)
t = time.time(); rl, rm = CORR.flip_flop(z); print("flip_flop", round(time.time()-t, 3))
t = time.time(); obs = P.observed(z, T.LEVELS); print("observed", round(time.time()-t, 3))
t = time.time(); nl = P.null(rl, rm, 693, T.LEVELS, B=10); print("null x10", round(time.time()-t, 3))
t = time.time(); pe = P.person_effect(z); print("person EM", round(time.time()-t, 3))
t = time.time(); ns = P.normal_scores(v); print("normal scores", round(time.time()-t, 3))
units = ["u%d" % i for i in range(693)]
t = time.time(); cv = P.cv_scores(v, units); print("cv", round(time.time()-t, 3), cv)
