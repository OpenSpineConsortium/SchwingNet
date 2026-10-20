"""The prototype's fake claude setup-token (2026-10-15): Ink's screens as the
binary's strings give them, a code read from the keyboard, the final frame
painted twice, and the window's width reported on standard error. The
stand-in token is built from pieces."""
import os, sys, time
tok = "sk-" + "ant-" + "oat01-" + ("A" * 40) + "_" + ("b" * 39) + "-Z"
w = sys.stdout.write
w("\x1b[?25l")  # hide cursor as Ink does
w("This will guide you through long-lived (1-year) auth token setup for your Claude account.\n")
w("Claude subscription required.\n\n")
w("Browser didn't open? Use the url below to sign in (ctrl/cmd + click):\n\nhttps://claude.ai/oauth/authorize?code=true&client_id=abc\n\n")
w("Paste code here if prompted > ")
sys.stdout.flush()
code = sys.stdin.readline().strip()
w("\n")
# a redraw like Ink's: erase lines and print the final frame twice
for _ in range(2):
    w("\x1b[2K\x1b[1A\x1b[2K\r")
    w("\x1b[32m" + "Long-lived authentication token created successfully!" + "\x1b[39m\n\n")
    w("Your OAuth token (valid for 1 year):\n\n")
    w("\x1b[1m" + tok + "\x1b[22m\n\n")
    w("Store this token securely. You won't be able to see it again.\n\n")
    w("Use this token by setting: export CLAUDE_CODE_OAUTH_TOKEN=" + tok + "\n")
    sys.stdout.flush()
    time.sleep(0.05)
w("\x1b[?25h")
sys.stdout.flush()
sys.stderr.write("code was %r, columns %s\n" % (code, os.get_terminal_size().columns if sys.stdout.isatty() else "no tty"))
