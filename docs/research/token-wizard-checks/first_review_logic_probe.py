"""The first review's logic probe (written against c157d99): the scope
check against admin:org_hook and against a listing whose inactive account
comes first, the pairings of options refused only after a gh call, the
repositories dropped with --visibility all, and three readings (a pasted
export line ending in a carriage return, the mask pasted back, a date with
fractional seconds). Cases 1 to 4 showed the review's findings 2, 6 and 7.
No call reaches GitHub: gh is a stand-in."""
import sys, io, argparse, subprocess
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

# The tree probed: the commit README.md names for this script, extracted
# with git archive, or this repository when no folder is given.
CHECKOUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(CHECKOUT / part) for part in ("scripts", "tests", "tools")]
import tokens, fake_gh
from unittest.mock import patch

class FakeGh:
    def __init__(self, out): self.out = out
    def run(self, args, stdin=None):
        return subprocess.CompletedProcess(args, 0, self.out, "")

# 1. admin:org_hook passes the substring check
status = "github.com\n  Logged in to github.com account a (keyring)\n  - Active account: true\n  - Token scopes: 'admin:org_hook', 'repo'\n"
try:
    tokens.check_scopes(FakeGh(status), tokens.Target("org", "o", ["r"]))
    print("1. admin:org_hook only: check_scopes PASSED (wrong: admin:org is missing)")
except tokens.TokensError as e:
    print("1. refused:", e)

# 2. two accounts on github.com: the inactive one listed first without the scope
status2 = ("github.com\n  Logged in to github.com account old (keyring)\n  - Active account: false\n  - Token scopes: 'gist', 'repo'\n\n"
           "  Logged in to github.com account me (keyring)\n  - Active account: true\n  - Token scopes: 'admin:org', 'repo'\n")
try:
    tokens.check_scopes(FakeGh(status2), tokens.Target("org", "o", ["r"]))
    print("2. inactive-first listing: passed")
except tokens.TokensError as e:
    print("2. inactive-first listing: REFUSED although the active account has admin:org:", str(e)[:60])

# 3. usage error --repo with --repos: exit code and whether gh was called first
calls = []
class Rec:
    def run(self, args, stdin=None):
        calls.append(list(args)); return subprocess.CompletedProcess(args, 0, "github.com\n  - Token scopes: 'repo'\n", "")
with patch.object(tokens, "Gh", Rec):
    err = io.StringIO()
    with redirect_stderr(err):
        code = tokens.main(["--repo", "o/n", "--repos", "a", "status"])
print("3. --repo with --repos: exit", code, "| gh calls made before the refusal:", calls, "|", err.getvalue().strip())

# 4. --org X --repos a --visibility all: are the repos kept or ignored?
ns = tokens.build_parser().parse_args(["--org", "o", "--repos", "a,b", "--visibility", "all", "status"])
t = tokens.target_from(ns, FakeGh(""))
print("4. target repos", t.repos, "visibility", t.visibility, "describe:", t.describe())
class S:  # a state with nothing in it
    secrets = {}; variables = {}; target = t
print("   scope_args for a new secret:", tokens.scope_args(S, "secrets", "X"), " (the --repos are dropped silently)")

# 5. check_token on a paste with a trailing CR (Windows clipboard) and with the whole export line plus a prompt echo
print("5.", tokens.check_token("export CLAUDE_CODE_OAUTH_TOKEN=" + "sk-ant-oat01-" + "A"*80 + "\r") == "sk-ant-oat01-" + "A"*80)

# 6. a pasted 'token' that is the mask the wizard prints (someone copying from the screen)
try:
    tokens.check_token(tokens.MASK); print("6. mask accepted?!")
except tokens.TokensError as e:
    print("6. mask refused:", str(e)[:50])

# 7. age_line with a date GitHub might give with fractional seconds
print("7.", tokens.age_line({"updatedAt": "2026-01-10T10:00:00.123456Z"}, None))
