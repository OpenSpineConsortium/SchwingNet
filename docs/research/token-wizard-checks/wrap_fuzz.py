"""The thread's wrap fuzz (written against 2b289d9, and holding on every
commit since): claude's token screen wrapped at every width from 20 to 419
columns, for three token lengths, in Ink's form and in the 2.1 renderer's
placed-words form, fed to the masker at four chunk sizes (9,600 runs). It
prints the count of each outcome and every run that stored a wrong token
or refused at 400 columns or wider; "bad: 0" is the pass. Stand-in tokens
are built from pieces."""
import sys
from pathlib import Path

# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
CHECKOUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(CHECKOUT / part) for part in ("scripts", "tests", "tools")]
import tokens

HEAD = "sk-" + "ant-" + "oat01-"
CANDIDATES = [HEAD + "A" * 40 + "_" + "b" * 39 + "-Zz", HEAD + "Q" * 95, HEAD + "x" * 70]


def wrap(line, width, joiner):
    return joiner.join(line[i:i + width] for i in range(0, len(line), width))


def screens(token, width):
    """The two token lines of claude's screen, in Ink's form and in the placed-words form, wrapped at width."""
    ink = ("Your OAuth token (valid for 1 year):\r\n\r\n" + wrap(token, width, "\r\n") + "\r\n\r\n"
           "Store this token securely.\r\n\r\n" + wrap("Use this token by setting: export CLAUDE_CODE_OAUTH_TOKEN=" + token, width, "\r\n") + "\r\n")
    placed_line = wrap(" " + token, width, "\r\r\n\x1b[2G")
    placed = ("\x1b[2GYour\x1b[7GOAuth\r\r\n\r\r\n\x1b[2G\x1b[1m" + placed_line.lstrip(" ") + "\x1b[22m\r\r\n\r\r\n"
              "\x1b[2GStore\x1b[8Gthis\r\r\n" + "\x1b[2G" + wrap("Use this token by setting: export CLAUDE_CODE_OAUTH_TOKEN=" + token, width, "\r\r\n\x1b[2G") + "\r\r\n")
    return {"ink": ink, "placed": placed}


def outcome(text, size, token):
    masker = tokens.Masker()
    out = "".join(masker.feed(text[i:i + size]) for i in range(0, len(text), size)) + masker.feed("", final=True)
    if masker.cut_over_lines:
        return "refused-cut", out
    if len(masker.tokens) != 1:
        return "refused-count", out
    try:
        kept = tokens.whole_token(masker.tokens[0])
    except tokens.TokensError:
        return "refused-length", out
    return ("stored-right" if kept == token else "STORED-WRONG"), out


bad, counts = [], {}
for token in CANDIDATES:
    for width in range(20, 420):
        for form, text in screens(token, width).items():
            for size in (1, 7, 64, 4096):
                result, out = outcome(text, size, token)
                counts[result] = counts.get(result, 0) + 1
                if result == "STORED-WRONG" or (result != "stored-right" and width >= 400):
                    bad.append((len(token), width, form, size, result))
print(counts)
print("bad:", len(bad), bad[:10])
