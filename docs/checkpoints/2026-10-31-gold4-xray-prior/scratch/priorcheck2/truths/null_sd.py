"""The sampling spread of the check's primary statistics under the separable truth fitted to the
published ENHANCE.PET C3..L5 prior (unshrunk), at the fit's n (693 for enhance_pet, 67 for
totalsegmentator): draw n spines, standardise per cell, fit as the job fits, compute each statistic
as the job computes it (C minus K, K the shrunk Kronecker of the fit). This is the parametric null
the job prints beside each primary, so a session can read a misfit's size against its noise before
the job runs."""
import json
import sys
sys.dont_write_bytecode = True
import numpy as np

sys.path.insert(0, "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck")
sys.path.insert(0, "/tmp/claude-0/-home-claude/3a9f8f67-4b49-5dd0-98ba-d0bd1c4358ce/scratchpad/priorcheck2/truths")
import kron_sim as K          # noqa: E402
import limit_check as LC      # noqa: E402


def one(rng, chol, n):
    x = rng.standard_normal((n, K.L * K.M)) @ chol.T
    z = K.standardise(x.reshape(n, K.L, K.M))[0]
    rl, rm = K.flip_flop(z)
    flat = z.reshape(n, -1)
    C = flat.T @ flat / (n - 1)
    Kd = np.kron(K.shrunk(rl, 0.05), K.shrunk(rm, 0.05))
    sc, sk = LC.stats(C), LC.stats(Kd)
    out = {k: sc[k] - sk[k] for k in ("six", "facing-far w", "facing-far d", "lag core range")}
    d = np.array(sc["far CxL"]) - np.array(sk["far CxL"])
    out["far CxL pair"] = float(d[1])
    out["far CxL mean"] = float(d.mean())
    out["far core lag6 mean"] = float(np.mean(np.array(sc["far core lag6"]) - np.array(sk["far core lag6"])))
    idx = list(range(5, 22))
    _, rms = K.flip_flop(z[:, idx, :])
    out["refit T1..L5 width change"] = float(rms[0, 2] - rm[0, 2])
    return out


def main():
    obs = K.observed_targets()
    tl, tm = K.unshrink(obs["enhance_C3L5"].r_level), K.unshrink(obs["enhance_C3L5"].r_measure)
    chol = np.linalg.cholesky(np.kron(tl, tm))
    for n, B in ((693, 120), (67, 120)):
        rng = np.random.default_rng(31 + n)
        draws = [one(rng, chol, n) for _ in range(B)]
        keys = draws[0].keys()
        print(json.dumps({"n": n, "B": B, **{k: {"mean": round(float(np.mean([d[k] for d in draws])), 4),
                                                    "sd": round(float(np.std([d[k] for d in draws], ddof=1)), 4)} for k in keys}}), flush=True)


if __name__ == "__main__":
    main()
