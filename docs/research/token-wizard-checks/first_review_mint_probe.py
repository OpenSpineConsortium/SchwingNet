"""The first review's mint probe (written against c157d99): mint() against
a fake claude that turns on bracketed paste and focus events and prints the
token as its very last bytes, with no newline. Standard input is a pipe, so
raw mode is not entered; second_review_mint_pty_probe.py runs it on a
pseudo-terminal. The stand-in token is built from pieces."""
import os, sys, tempfile, json
from pathlib import Path

# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
CHECKOUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(CHECKOUT / part) for part in ("scripts", "tests", "tools")]
import tokens
T = "sk-" + "ant-" + "oat01-" + "A" * 40 + "_" + "b" * 39 + "-Zz"
d = tempfile.mkdtemp(prefix="mint-")
fake = os.path.join(d, "claude")
with open(fake, "w") as h:
    h.write(f"#!{sys.executable} -IS\nimport sys\nsys.stdout.write('\\x1b[?2004h\\x1b[?1004hYour OAuth token (valid for 1 year):\\n' + {T!r})\nsys.stdout.flush()\n")
os.chmod(fake, 0o755)
r, w = os.pipe(); os.close(w)
got = []
found, status = tokens.mint(stdin_fd=r, write=got.append, command=(fake, "setup-token"))
out = "".join(got)
print("a) token at EOF, no newline: captured", found == [T], "| leak", T in out, "| bracketed paste left on in output:", "\x1b[?2004h" in out and "\x1b[?2004l" not in out)
os.close(r)
