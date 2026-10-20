"""The thread's probe of the real claude setup-token's first screen
(written against c157d99): the real command behind a pseudo-terminal of
400 columns with the wizard's masker and pump, stopped by its process id
after eight seconds, before anyone can sign in, so no token ever exists.
What it checks is the screen before the sign-in and that nothing crashes;
docs/research/token-wizard.md says what it showed for Claude Code 2.1.301.
It needs claude on PATH and starts a sign-in screen, so run it only where
that is wanted, and never sign in while it runs."""
import codecs, fcntl, os, pty, signal, struct, sys, termios, threading, time
from pathlib import Path

# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
CHECKOUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(CHECKOUT / part) for part in ("scripts", "tests", "tools")]
import tokens

pid, master = pty.fork()
if pid == 0:
    fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 400, 0, 0))
    os.execvp("claude", ["claude", "setup-token"])

def killer():
    time.sleep(8)
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
threading.Thread(target=killer, daemon=True).start()
reader, writer = os.pipe()
os.close(writer)
masker = tokens.Masker()
decoder = codecs.getincrementaldecoder("utf-8")("replace")
out = []
tokens.pump(master, reader, lambda data: out.append(masker.feed(decoder.decode(data))))
out.append(masker.feed("", final=True))
_, status = os.waitpid(pid, 0)
text = "".join(out)
print("exit status:", status, "tokens seen:", len(masker.tokens))
print("--- screen, escapes shown ---")
print(repr(text)[:2500])
