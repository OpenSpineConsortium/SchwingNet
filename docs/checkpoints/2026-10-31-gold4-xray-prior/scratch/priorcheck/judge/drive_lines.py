"""Scratch driver: synthetic ENHANCE-like and TS-like populations through lines_proto.report, to measure
the line count, the longest line and the run time (not a repository file)."""
import sys, time, re
import numpy as np
import truths as T
import lines_proto as LP

def population(rng, kind, n_whole, n_part, n_held_whole, n_held_part, quantise=True):
    rl0, rm0 = T.published()
    cov = T.truth(kind, rl0, rm0)
    def make(nw, npart):
        x = T.draw(rng, cov, nw + npart)
        if quantise:
            x[:, :, [0, 2]] = np.round(x[:, :, [0, 2]] * 2) / 2      # widths in half-millimetre steps, ties
        for s in range(nw, nw + npart):                                # incomplete spines: a few cells missing
            cells = rng.choice(T.L * T.M, size=rng.integers(1, 6), replace=False)
            for c in cells:
                x[s, c // T.M, c % T.M] = np.nan
        return x
    fit, held = make(n_whole, n_part), make(n_held_whole, n_held_part)
    units = ["u%d" % i for i in range(len(fit))]
    slices = rng.choice([0.6, 1.0, 1.5, 2.0, 3.0, 3.27, 5.0], size=len(fit), p=[.05, .15, .1, .1, .4, .15, .05])
    facts = [{"slice_mm": float(s), "code": "1cee7ea83e4c28db",
              "foramina": {l for l in range(5) if rng.random() < 0.55}} for s in slices]
    repeat = []
    base = T.draw(rng, cov, 57)
    for u in range(57):
        for k in range(2 if u < 44 else 3):
            repeat.append(("r%d" % u, base[u] + rng.normal(0, 1.2, size=base[u].shape)))
    return fit, held, units, facts, repeat

if __name__ == "__main__":
    name, kind, nw, npart, hw, hp, B, with_repeat = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:8]), sys.argv[8] == "1"
    rng = np.random.default_rng(7)
    fit, held, units, facts, repeat = population(rng, kind, nw, npart, hw, hp)
    t = time.time()
    lines = LP.report("%s C3..L5 check" % name, T.LEVELS, fit, held, units[:len(fit)], None, facts,
                      repeat if with_repeat else [], B=B)
    for line in lines:
        print(line)
    print("## lines %d, longest %d, seconds %.0f" % (len(lines), max(len(l) for l in lines), time.time() - t), file=sys.stderr)
    bad = [l for l in lines if re.search(r"\b[a-z][a-z0-9_]*:[A-Za-z0-9]", l)]
    print("## lines a redact colon rule would mask: %d" % len(bad), file=sys.stderr)
    for l in bad[:5]:
        print("##   " + l[:160], file=sys.stderr)
