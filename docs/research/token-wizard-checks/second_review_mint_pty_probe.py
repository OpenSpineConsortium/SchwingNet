"""The second review pass's typed-ahead probe (written against 5a65e4f):
mint() on a pseudo-terminal with the code typed after claude asks for it
and more keys typed after claude has ended, to see that the terminal's
modes come back and no typed-ahead key is left for the wizard's next
question. The stand-in token is built from pieces."""
import os, sys, pty, termios, tempfile, time, threading, select
from pathlib import Path

# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
CHECKOUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(CHECKOUT / part) for part in ("scripts", "tests", "tools")]
import tokens
T = "sk-" + "ant-" + "oat01-" + "C" * 80 + "-" + "d" * 12 + "AA"
d = tempfile.mkdtemp(prefix="mintpty-")
fake = os.path.join(d, "claude")
with open(fake, "w") as h:
    h.write(f"#!{sys.executable} -IS\nimport sys\nsys.stdout.write('Paste code here if prompted > '); sys.stdout.flush()\nline = sys.stdin.readline()\nsys.stdout.write('\\x1b[?2004h\\x1b[?1004hcode=' + line.strip() + '\\nYour OAuth token (valid for 1 year):\\n' + {T!r})\nsys.stdout.flush()\n")
os.chmod(fake, 0o755)
m2, s2 = pty.openpty()
def typist():
    time.sleep(0.7); os.write(m2, b"thecode\r")
    time.sleep(0.7); os.write(m2, b"yyy")
threading.Thread(target=typist, daemon=True).start()
before = termios.tcgetattr(s2)
got = []
found, status, cut = tokens.mint(stdin_fd=s2, write=got.append, command=(fake, "setup-token"))
after = termios.tcgetattr(s2)
out = "".join(got)
print("captured:", found == [T], "| status", status, "| cut", cut, "| code reached claude:", "code=thecode" in out)
print("token on screen:", T in out, "| reset written:", tokens.TERMINAL_RESET in out, "| reset after the last mask:", out.rfind(tokens.TERMINAL_RESET) > out.rfind(tokens.MASK), "| ends with newline:", out.endswith("\n"))
print("termios restored:", before == after)
r, _, _ = select.select([s2], [], [], 0.5)
print("typed-ahead left for the next prompt:", repr(os.read(s2, 100)) if r else "none (flushed or forwarded)")
