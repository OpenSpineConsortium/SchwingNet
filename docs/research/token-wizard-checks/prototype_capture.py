"""The thread's first prototype of the wizard's capture (2026-10-15, before
any commit): a command run behind a pseudo-terminal of 500 columns, its
output passed through a masker before it reaches the screen, the keyboard
forwarded raw, and each token found printed only as a hash and a length.
Run it as python3 prototype_capture.py python3 prototype_fake_claude.py;
scripts/tokens.py grew from it."""
import fcntl, hashlib, os, pty, re, select, signal, struct, sys, termios, tty

HEAD = "sk-" + "ant-" + "oat"
TOKEN = re.compile(re.escape(HEAD) + r"\d{2}-[A-Za-z0-9_-]{20,}")
# a suffix that could be the start of a token, held back until more arrives
PARTIAL = re.compile(r"(?:s|sk|sk-|sk-a|sk-an|sk-ant|sk-ant-|sk-ant-o|sk-ant-oa|" + re.escape(HEAD) + r"\d{0,2}-?[A-Za-z0-9_-]*)$")
MASK = "sk-ant-oat**-****************  (hidden by the wizard)"

class Masker:
    def __init__(self):
        self.shown_tail = ""
        self.held = ""
        self.found = []
    def feed(self, chunk, final=False):
        text = self.shown_tail + self.held + chunk
        out = []
        pos = len(self.shown_tail)
        start = 0
        for m in TOKEN.finditer(text):
            if m.group(0) not in self.found:
                self.found.append(m.group(0))
            out.append(text[start:m.start()])
            out.append(MASK)
            start = m.end()
        out.append(text[start:])
        masked = "".join(out)
        # everything before shown_tail's length is already on screen; but masking may have
        # changed lengths before that point only if a token started inside shown_tail
        # (then its visible head is already shown; the mask replaces the rest). Recompute:
        if TOKEN.search(text) and any(m.start() < pos for m in TOKEN.finditer(text)):
            # the first token began inside shown_tail: show the mask after what was shown
            first = next(m for m in TOKEN.finditer(text) if m.start() < pos)
            masked = text[:first.start()] + MASK + "".join(self._mask_rest(text[first.end():]))
            new = masked[len(text[:first.start()]):]
            # drop the part of the masked head already on screen: nothing to drop; print the mask whole
            emit = new
        else:
            emit = masked[pos:]
        if not final:
            m = PARTIAL.search(emit)
            if m and len(m.group(0)) < 200 and not TOKEN.search(m.group(0)):
                self.held = m.group(0)
                emit = emit[:m.start()]
            else:
                self.held = ""
        else:
            self.held = ""
        if emit:
            self.shown_tail = (self.shown_tail + emit)[-12:]
        return emit
    def _mask_rest(self, rest):
        start = 0
        out = []
        for m in TOKEN.finditer(rest):
            if m.group(0) not in self.found:
                self.found.append(m.group(0))
            out.append(rest[start:m.start()]); out.append(MASK); start = m.end()
        out.append(rest[start:])
        return out

def run(argv):
    pid, fd = pty.fork()
    if pid == 0:
        fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 500, 0, 0))
        os.execvp(argv[0], argv)
    masker = Masker()
    stdin_fd = sys.stdin.fileno()
    raw = None
    if os.isatty(stdin_fd):
        raw = termios.tcgetattr(stdin_fd)
        tty.setraw(stdin_fd)
    decoder = __import__("codecs").getincrementaldecoder("utf-8")("replace")
    stdin_open = True
    try:
        while True:
            fds = [fd] + ([stdin_fd] if stdin_open else [])
            r, _, _ = select.select(fds, [], [])
            if fd in r:
                try:
                    data = os.read(fd, 4096)
                except OSError:
                    data = b""
                if not data:
                    break
                sys.stdout.write(masker.feed(decoder.decode(data)))
                sys.stdout.flush()
            if stdin_fd in r:
                data = os.read(stdin_fd, 4096)
                if not data:
                    stdin_open = False
                    continue
                os.write(fd, data)
    finally:
        if raw is not None:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, raw)
    sys.stdout.write(masker.feed("", final=True))
    _, status = os.waitpid(pid, 0)
    return status, masker.found

if __name__ == "__main__":
    status, found = run(sys.argv[1:])
    print("\n--- exit status %d, tokens found: %d" % (status, len(found)))
    for t in found:
        print("sha256:", hashlib.sha256(t.encode()).hexdigest()[:16], "len", len(t))
