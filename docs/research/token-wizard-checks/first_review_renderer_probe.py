"""The first review's renderer probe (written against c157d99): Claude
Code 2.1's placed-words frame, cut at every chunk size from 1 to 59 and a
few larger, and a token line repainted five times. The stand-in token is
built from pieces."""
import sys
from pathlib import Path

# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
CHECKOUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(CHECKOUT / part) for part in ("scripts", "tests", "tools")]
import tokens
T = "sk-" + "ant-" + "oat01-" + "A" * 40 + "_" + "b" * 39 + "-Zz"
# Claude Code 2.1's renderer as the design note describes it: CSI n G before every word,
# a line ends with \r\r\n; the token is one word.
def placed(words):
    col, out = 1, ""
    for w in words:
        out += f"\x1b[{col}G" + w
        col += len(w) + 1
    return out + "\r\r\n"
frame = (placed(["Your", "OAuth", "token", "(valid", "for", "1", "year):"]) + placed([T]) +
         placed(["Store", "this", "token", "securely."]) +
         placed(["Use", "this", "token", "by", "setting:", "export", "CLAUDE_CODE_OAUTH_TOKEN=" + T]))
bad = []
for size in list(range(1, 60)) + [100, 4096]:
    m = tokens.Masker()
    out = "".join(m.feed(frame[i:i+size]) for i in range(0, len(frame), size)) + m.feed("", final=True)
    if T in out or tokens.TOKEN_SHAPE.search(out) or m.tokens != [T] or out.count(tokens.MASK) != 2:
        bad.append((size, m.tokens == [T], out.count(tokens.MASK)))
print("placed-words frame: failures at sizes", bad or "none")
# A frame where the renderer repaints the token line several times, erasing with CSI 2K / CSI 1A between
frame2 = "".join("\x1b[2K\x1b[1A\x1b[2K\r" + placed([T]) for _ in range(5))
m = tokens.Masker(); out = "".join(m.feed(frame2[i:i+7]) for i in range(0, len(frame2), 7)) + m.feed("", final=True)
print("repainted 5x: leak", T in out, "masks", out.count(tokens.MASK), "tokens", len(m.tokens))
