"""The second review pass's masker probe (written against 5a65e4f): a wrap
that leaves fewer than CONTINUATION_RUN characters on the next line, the
over-limit path at several chunk sizes, plausible lines after the token
that the cut check might mistake for a rest, and a rest it might miss after
blanks or a terminal code. Parts 1 and 4 showed the cut check incomplete,
part 2 the wrong words, part 3 the false positive. The stand-in tokens are
built from pieces."""
import sys
from pathlib import Path

# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
CHECKOUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(CHECKOUT / part) for part in ("scripts", "tests", "tools")]
import tokens
T96 = "sk-" + "ant-" + "oat01-" + "A" * 40 + "_" + "b" * 39 + "-Zz"          # the tests' token, 96 chars
T108 = "sk-" + "ant-" + "oat01-" + "C" * 80 + "-" + "d" * 12 + "AA"            # a 108-char one
def fed(text, size):
    m = tokens.Masker()
    out = "".join(m.feed(text[i:i+size]) for i in range(0, len(text), size)) + m.feed("", final=True)
    return m, out
def accepted(m):
    if m.cut_over_lines: return "refused: cut"
    try: tokens.whole_token(m.tokens[0]); return "ACCEPTED (stored)"
    except tokens.TokensError as e: return "refused: " + str(e)[:40]
print("== 1. a wrap that leaves fewer than CONTINUATION_RUN characters on the second line ==")
for T, width in ((T96, 80), (T108, 100), (T108, 80), (T96, 60)):
    first = width - 1                      # the token starts at column 1
    text = "Your token:\r\n" + T[:first] + "\r\n" + T[first:] + "\r\n\r\nStore this token securely.\r\n"
    for size in (1, 7, 4096):
        m, out = fed(text, size)
        shown_rest = T[first:] in out
        print(f"  len={len(T)} width={width} rest={len(T)-first:2d} size={size:4d}: captured={len(m.tokens[0]) if m.tokens else None} cut={m.cut_over_lines} rest_on_screen={shown_rest} -> {accepted(m)}")
print("== 2. the over-limit path at several chunk sizes ==")
text = "x " + T108 + "Q" * 500 + "\n"
for size in (1, 50, 100, 401, 700, 4096):
    m, out = fed(text, size)
    print(f"  size={size:4d}: token_on_screen={T108 in out} shape_on_screen={bool(tokens.SECRET_SHAPE.search(out))} tokens={[len(t) for t in m.tokens]} cut={m.cut_over_lines} -> {accepted(m)}")
print("== 3. continuation false positives on plausible real output ==")
for label, after in (("export line then EOF with cursor-show", "\r\r\n\x1b[?25h"),
                     ("next line a 20+ char word", "\r\n" + "Authentication_complete" + " for this account\r\n"),
                     ("next line a 19-char word", "\r\n" + "Authenticationdone1" + " ok\r\n"),
                     ("Ink repaint right after", "\x1b[22m\x1b[2K\x1b[1A\x1b[2K\r\x1b[32mLong-lived authentication token created\r\n")):
    m, out = fed("\x1b[1m" + T108 + after, 3)
    print(f"  {label}: cut={m.cut_over_lines} tokens={len(m.tokens)}")
print("== 4. continuation false negatives: the rest indented by spaces, or after an OSC/other code ==")
for label, sep in (("rest after '\\r\\n' + two spaces (Ink padding)", "\r\n  "), ("rest after tab", "\r\n\t"),
                   ("rest after CSI < u", "\r\n\x1b[<u"), ("rest after OSC 8", "\r\n\x1b]8;;\x1b\\")):
    text = "  " + T108[:60] + sep + T108[60:] + "\r\n"
    m, out = fed(text, 5)
    print(f"  {label}: cut={m.cut_over_lines} captured={len(m.tokens[0]) if m.tokens else None} rest_on_screen={T108[60:] in out} -> {accepted(m)}")
