"""The first review's masker probe (written against c157d99): a token
followed by a long run of token characters, a token at the end of the
output, a token wrapped at 60 columns, two tokens, and a token split after
its first letter. Cases D and F showed the two faults the first review
ranked highest. The stand-in token is built from pieces."""
import sys
from pathlib import Path

# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
CHECKOUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(CHECKOUT / part) for part in ("scripts", "tests", "tools")]
import tokens
T = "sk-" + "ant-" + "oat01-" + "A" * 40 + "_" + "b" * 39 + "-Zz"   # 96 chars, the tests' token
def run(label, pieces, final=True):
    m = tokens.Masker()
    out = "".join(m.feed(p) for p in pieces)
    if final:
        out += m.feed("", final=True)
    leak = T in out
    print(f"{label}: leak={leak} tokens={len(m.tokens)} held={len(m.held)} out_tail={out[-60:]!r}")
    return out, m
print("token length", len(T), "HOLD_LIMIT", tokens.HOLD_LIMIT)
# 1. token followed by a run of token-class chars longer than HOLD_LIMIT in ONE chunk, newline in the next
run("A: token + 300 dashes, then newline", ["Your token: " + T + "-" * 300, "\n"])
run("B: token + 292 dashes (total 400)", ["x " + T + "-" * 292, "\n"])
run("C: token + 293 dashes (total 401)", ["x " + T + "-" * 293, "\n"])
# 2. same but the run arrives in several chunks (each chunk re-evaluates the whole tail)
run("D: token then 100-char runs x4 then newline", ["x " + T] + ["Q" * 100] * 4 + ["\n"])
# 3. the token is the very last thing claude prints (no newline), then EOF
run("E: token at EOF, final flush", ["Your token: " + T])
# 4. an 80-column wrap inside the token (what a narrow Ink box would do)
wrapped = "x " + T[:60] + "\r\n" + T[60:] + "\r\n"
out, m = run("F: token wrapped at 60", [wrapped])
print("   captured:", [len(t) for t in m.tokens], " screen shows rest:", T[60:] in out)
# 5. a mask already on screen, then a token starting right after it
run("G: two tokens back to back with a space", ["a " + T + " " + T + "\n"])
# 6. token split so that 's' is emitted and the rest comes later
run("H: 's' then the rest", ["Your token: s", T[1:] + "\n"])
