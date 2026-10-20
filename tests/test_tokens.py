"""scripts/tokens.py stores a Claude account's subscription token as an
Actions secret without the token reaching the screen, a command line, a
file or a log: claude setup-token runs behind a pseudo-terminal whose
output is masked, the token goes to gh on a pipe, and GitHub's own listing
is read back by name. No test has a signed-in gh, a browser or claude: a
fake gh on PATH, or in the process (tests/fake_gh.py), answers the calls
and records them, and a fake claude prints the sign-in's screens with a
token built here from pieces, so this file never holds one."""

import ctypes
import getpass
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_docs  # noqa: E402
import fake_gh  # noqa: E402
import tokens  # noqa: E402
from fake_gh import answer  # noqa: E402

SCRIPT = ROOT / "scripts" / "tokens.py"
ORG = "octo"
REPO = "widgets"
# A stand-in token in the shape claude setup-token prints, built from pieces
# as tools/check_docs.py builds its own shapes, so no line here is one.
TOKEN = "sk-" + "ant-" + "oat01-" + "A" * 40 + "_" + "b" * 39 + "-Zz"
OTHER = "sk-" + "ant-" + "oat01-" + "C" * 60 + "-Qq"
API_KEY = "sk-" + "ant-" + "api03-" + "k" * 60 + "AA"
SCOPES_LINE = "  Token scopes: 'admin:org', 'gist', 'read:org', 'repo', 'workflow'\n"
SIGNED_IN = "github.com\n  Logged in to github.com account greg (keyring)\n  Active account: true\n" + SCOPES_LINE
CROWD_OFF = "# Project\n\n## Crowd mode\n\n- Crowd mode: off. Nobody has run setup.\n"
OLD = "2026-01-10T10:00:00Z"
NEW = "2026-10-16T01:00:00Z"
SIGN_IN_LINK = "https://claude.ai/oauth/authorize?code=true&client_id=abc&redirect_uri=http%3A%2F%2Flocalhost%3A5%2Fcallback"
# A browser that writes down how it was started.
FAKE_BROWSER = """import json, os, sys
with open(os.environ["FAKE_BROWSER_REPORT"], "w") as handle:
    json.dump(sys.argv[1:], handle)
"""
# What the fake claude prints: the screens of a real sign-in as the binary's
# strings give them, with an escape code around the token and a redraw, as
# Ink does, and the token twice, once on its own line and once in the
# export line.
FAKE_CLAUDE = '''
import json, os, subprocess, sys
token = {token!r}
w = sys.stdout.write
# As Claude Code's own opener does: the program BROWSER names, the link its
# one argument.
if os.environ.get("BROWSER"):
    subprocess.run([os.environ["BROWSER"], {link!r}])
w("\\x1b[?25lThis will guide you through long-lived (1-year) auth token setup for your Claude account.\\n")
w("Claude subscription required.\\n\\nBrowser didn't open? Use the url below to sign in (ctrl/cmd + click):\\n\\n")
w("https://claude.ai/oauth/authorize?code=true&client_id=abc\\n\\nPaste code here if prompted > ")
sys.stdout.flush()
code = sys.stdin.readline().strip()
for _ in range(2):
    w("\\n\\x1b[2K\\x1b[1A\\x1b[2K\\r\\x1b[32mLong-lived authentication token created successfully!\\x1b[39m\\n\\n")
    w("Your OAuth token (valid for 1 year):\\n\\n\\x1b[1m" + token + "\\x1b[22m\\n\\n")
    w("Store this token securely. You won't be able to see it again.\\n\\n")
    w("Use this token by setting: export CLAUDE_CODE_OAUTH_TOKEN=" + token + "\\n")
    sys.stdout.flush()
w("\\x1b[?25h")
sys.stdout.flush()
columns = os.get_terminal_size(1).columns if sys.stdout.isatty() else None
with open(os.environ["FAKE_CLAUDE_REPORT"], "w") as handle:
    json.dump({{"code": code, "columns": columns, "tty": sys.stdout.isatty(), "env_columns": os.environ.get("COLUMNS"),
               "browser": os.environ.get("BROWSER")}}, handle)
'''


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def secret(name, updated=OLD, visibility="selected", selected=1):
    return {"name": name, "updatedAt": updated, "visibility": visibility, "numSelectedRepos": selected}


def variable(name, value, updated=OLD, visibility="selected", selected=1):
    found = secret(name, updated, visibility, selected)
    found["value"] = value
    return found


def install_claude(folder, token=TOKEN):
    """The fake claude, first on PATH, that prints a sign-in's screens."""
    bin_dir = Path(folder) / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    claude = bin_dir / "claude"
    claude.write_text(f"#!{sys.executable} -IS\n" + FAKE_CLAUDE.format(token=token, link=SIGN_IN_LINK), encoding="utf-8")
    claude.chmod(0o755)
    return bin_dir


def code_pipe(text="thecode\n"):
    """A pipe standing for the keyboard, with the code already typed."""
    reader, writer = os.pipe()
    os.write(writer, text.encode())
    os.close(writer)
    return reader


class Collector:
    def __init__(self):
        self.text = ""

    def __call__(self, text):
        self.text += text


def has_token(text):
    return tokens.TOKEN_SHAPE.search(text) is not None


class World:
    """A fake gh for one organization with one repository, with the secrets
    and variables given, where every write is answered and a store shows in
    the next listing with a later date."""

    def __init__(self, test, secrets=(), variables=(), stored=NEW, scopes=SCOPES_LINE, crowd=None):
        self.folder = tempfile.mkdtemp(prefix="tokens-")
        test.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        self.secrets, self.variables = list(secrets), list(variables)
        self.stored = stored
        self.report = None
        # A copy of the template runs these tests too (tests/test_filled_copy.py),
        # a crowd copy among them, where the clone's own docs/project.md says
        # crowd mode is on and the wizard refuses; the tests read a project
        # file of their own that says off.
        self.project = Path(self.folder) / "docs" / "project.md"
        self.project.parent.mkdir(parents=True, exist_ok=True)
        self.project.write_text(CROWD_OFF, encoding="utf-8")
        self.log = str(Path(self.folder) / "gh-log.jsonl")
        self.routes_file = str(Path(self.folder) / "routes.json")
        status = SIGNED_IN.replace(SCOPES_LINE, scopes)
        routes = {
            "auth status": [answer(200, status)],
            f"GET users/{ORG}": [answer(200, "Organization\n")],
            f"GET repos/{ORG}/{REPO}": [answer(200, f"{ORG}/{REPO}\n")],
            f"GET repos/{ORG}/other": [answer(200, f"{ORG}/other\n")],
            f"GET repos/{ORG}/{REPO}/actions/variables/{tokens.CROWD_VARIABLE}": [
                answer(404, {"message": "Not Found"}) if crowd is None else answer(200, crowd + "\n")],
            f"GET repos/{ORG}/other/actions/variables/{tokens.CROWD_VARIABLE}": [answer(404, {"message": "Not Found"})],
            "secret list": [answer(200, self.secrets)],
            "variable list": [answer(200, self.variables)],
            "secret set": [answer(200, "", after=self.after_store())],
            "variable set": [answer(200, "")],
            "secret delete": [answer(200, "")],
            "variable delete": [answer(200, "")],
        }
        # Every selected secret or variable reaches the one repository.
        names = [tokens.slot_secret(slot) for slot in tokens.SLOTS] + [tokens.MAIN_SECRET]
        names += [tokens.slot_label(slot) for slot in tokens.SLOTS] + [tokens.ACCOUNTS_VARIABLE]
        for kind in ("secrets", "variables"):
            for name in names:
                routes[f"GET orgs/{ORG}/actions/{kind}/{name}/repositories"] = [answer(200, REPO + "\n")]
        fake_gh.write_routes(self.routes_file, routes)
        self.environment = fake_gh.environment(self.folder, routes)

    def after_store(self):
        """The listing once a store happened: every slot and the main secret
        listed, with the store's date on the ones the test stores."""
        listed = {item["name"]: dict(item) for item in self.secrets}
        for slot in tokens.SLOTS:
            listed.setdefault(tokens.slot_secret(slot), None)
        listed.setdefault(tokens.MAIN_SECRET, None)
        names = [name for name, item in listed.items() if item is not None or name in self.will_store()]
        found = [listed[name] if listed[name] is not None and name not in self.will_store() else secret(name, self.stored)
                 for name in names]
        return {"secret list": [answer(200, found)]}

    def will_store(self):
        return getattr(self, "storing", ())

    def expect_store(self, *names):
        """The names a store will add to the listing; set before the run."""
        self.storing = names
        routes = read_json(self.routes_file)
        routes["secret set"] = [answer(200, "", after=self.after_store())]
        fake_gh.write_routes(self.routes_file, routes)

    def run_in_process(self, test, function, *args, **options):
        """A command in this process against the fake, with the fake claude
        on PATH and a pipe for the keyboard: (printed text, the calls)."""
        bin_dir = install_claude(self.folder)
        report = str(Path(self.folder) / "claude-report.json")
        collector = Collector()
        printed = io.StringIO()
        environ = {"PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""), "FAKE_CLAUDE_REPORT": report}
        run = fake_gh.routed_run(subprocess.run, self.log, self.routes_file)
        with patch.dict(os.environ, environ), patch.object(tokens.subprocess, "run", run), \
                patch.object(tokens, "PROJECT", self.project), redirect_stdout(printed):
            reader = code_pipe()
            try:
                result = function(*args, write=collector, stdin_fd=reader, **options)
            finally:
                os.close(reader)
        self.report = read_json(report) if os.path.exists(report) else None
        return result, printed.getvalue() + collector.text, fake_gh.calls(self.log)

    def calls(self):
        return fake_gh.calls(self.log)


def target(repos=(REPO,), visibility="selected"):
    return tokens.Target("org", ORG, repos, visibility)


def call_keys(calls):
    return [call["key"] for call in calls]


def find(calls, key, name=None):
    return [call for call in calls if call["key"] == key and (name is None or name in call["args"])]


class TheMask(unittest.TestCase):
    """What claude prints reaches the screen with the token taken out,
    however the output is cut into pieces."""

    FRAME = ("\x1b[?25lYour OAuth token (valid for 1 year):\n\n\x1b[1m" + TOKEN + "\x1b[22m\n\n"
             "Store this token securely.\n\nUse this token by setting: export CLAUDE_CODE_OAUTH_TOKEN=" + TOKEN + "\n\x1b[?25h")
    # Claude Code 2.1's own renderer places each word by its column and
    # ends a line with \r\r\n, as a run of the real claude setup-token
    # behind the wizard's terminal showed on 2026-10-16; a token is one
    # word, so it comes between a column code and a line end.
    PLACED = ("\x1b[2GYour\x1b[7GOAuth\x1b[13Gtoken\x1b[19G(valid\x1b[26Gfor\x1b[30G1\x1b[32Gyear):\r\r\n\r\r\n"
              "\x1b[2G\x1b[1m" + TOKEN + "\x1b[22m\r\r\n\r\r\n\x1b[2GStore\x1b[8Gthis\x1b[13Gtoken\x1b[19Gsecurely.\r\r\n"
              "\x1b[2GUse\x1b[6Gthis\x1b[11Gtoken\x1b[17Gby\x1b[20Gsetting:\x1b[29Gexport\x1b[36GCLAUDE_CODE_OAUTH_TOKEN=" + TOKEN + "\r\r\n")

    def masked(self, text, size):
        masker = tokens.Masker()
        out = "".join(masker.feed(text[i:i + size]) for i in range(0, len(text), size))
        out += masker.feed("", final=True)
        return out, masker.tokens

    def masker_fed(self, text, size):
        masker = tokens.Masker()
        out = "".join(masker.feed(text[i:i + size]) for i in range(0, len(text), size))
        out += masker.feed("", final=True)
        return masker, out

    def test_the_token_never_reaches_the_screen_at_any_chunk_size(self):
        for frame in (self.FRAME, self.PLACED):
            for size in list(range(1, 48)) + [64, 100, 1000]:
                masker, out = self.masker_fed(frame, size)
                self.assertEqual(masker.tokens, [TOKEN], size)
                self.assertNotIn(TOKEN, out, size)
                self.assertFalse(has_token(out), size)
                self.assertEqual(out.count(tokens.MASK), 2, size)
                # Everything else is on the screen as claude printed it;
                # where the token came one character at a time, its first
                # "s" was on the screen before the mask took the rest.
                self.assertEqual(re.sub("s?" + re.escape(tokens.MASK), TOKEN, out), frame, size)
                # The words after the token are words, not a cut token's rest.
                self.assertFalse(masker.cut_over_lines, size)

    def test_a_run_past_the_hold_limit_is_masked_and_then_refused(self):
        # A token with no break after it for longer than any token: never
        # shown, and what was kept is too long to be one.
        text = "x " + TOKEN + "Q" * (tokens.HOLD_LIMIT + 40) + "\n"
        for size in (1, 100, 5000):
            masker, out = self.masker_fed(text, size)
            self.assertNotIn(TOKEN, out, size)
            self.assertFalse(has_token(out), size)
            self.assertEqual(len(masker.tokens), 1, size)
            self.assertGreater(len(masker.tokens[0]), tokens.HOLD_LIMIT, size)
            with self.assertRaises(tokens.TokensError) as caught:
                tokens.whole_token(masker.tokens[0])
            self.assertIn("ran on", str(caught.exception))

    def test_another_key_s_shape_is_masked_and_not_kept(self):
        text = "key " + API_KEY + " and token " + TOKEN + "\n"
        for size in (1, 7, 1000):
            masker, out = self.masker_fed(text, size)
            self.assertNotIn(API_KEY, out, size)
            self.assertNotIn(TOKEN, out, size)
            self.assertIn(tokens.OTHER_MASK, out, size)
            self.assertEqual(masker.tokens, [TOKEN], size)

    def test_a_token_cut_over_two_lines_is_noticed(self):
        # A terminal narrower than claude's would end the line inside the
        # token: the first piece is masked and kept, the rest stands alone
        # on the next line, which no shape finds and no word of claude's
        # does, so that is the sign, whatever the rest's length, and
        # however the line is begun (Ink's padding, the renderer's column
        # code with bold put back) or ended (a code before the line end).
        for at in (79, len(TOKEN) - 1, 50, 40):
            for before, after in (("\r\n", "\r\nStore this token securely.\n"), ("\r\r\n\x1b[2G\x1b[1m", "\x1b[22m\r\r\n\r\r\n\x1b[2GStore\x1b[8Gthis"),
                                  ("\n  ", "\n"), ("\n\t", ""), ("\n\x1b[<u\x1b]8;;\x1b\\", "\n")):
                cut = TOKEN[:at] + before + TOKEN[at:] + after
                for size in (1, 3, 30, 1000):
                    masker, out = self.masker_fed(cut, size)
                    self.assertTrue(masker.cut_over_lines, (at, repr(before), repr(after), size))
                    self.assertEqual(masker.tokens, [TOKEN[:at]], (at, size))
                    self.assertFalse(has_token(out), (at, size))
        # A line of words after the token, with blanks or cursor codes
        # between, is none, however long its first word; nor is a line
        # that begins with something else.
        for after in ("\r\r\n\x1b[2GStore\x1b[8Gthis", "\n\n" + "-" * 10 + " done", "\x1b[22m\r\n", "\n\nAuthentication_complete_for_this_account now\n",
                      "\r\r\n\r\r\n\x1b[2GStore\x1b[8Gthis\x1b[13Gtoken\r\r\n", "\n(done)\n", "\n\x1b[?25h"):
            for size in (1, 5, 1000):
                masker, out = self.masker_fed("\x1b[1m" + TOKEN + after, size)
                self.assertFalse(masker.cut_over_lines, (repr(after), size))
                self.assertEqual(masker.tokens, [TOKEN])
        # A run past the hold limit is refused by its length, not as a cut.
        masker, out = self.masker_fed("x " + TOKEN + "Q" * (tokens.HOLD_LIMIT + 40) + "\n", 50)
        self.assertFalse(masker.cut_over_lines)

    def test_a_token_of_another_length_is_refused(self):
        with self.assertRaises(tokens.TokensError) as caught:
            tokens.whole_token(TOKEN[:tokens.TOKEN_SHORTEST - 1])
        self.assertIn("shorter", str(caught.exception))
        self.assertNotIn(TOKEN[:20], str(caught.exception))
        self.assertEqual(tokens.whole_token(TOKEN), TOKEN)
        with self.assertRaises(tokens.TokensError):
            tokens.check_token(TOKEN[:tokens.TOKEN_SHORTEST - 1])

    def test_two_different_tokens_are_both_kept(self):
        out, found = self.masked("a " + TOKEN + " b " + OTHER + " c", 7)
        self.assertEqual(found, [TOKEN, OTHER])
        self.assertFalse(has_token(out))

    def test_text_that_only_looks_like_a_start_comes_through_whole(self):
        text = "task desk sk- sk-ant sk-ant-oat sk-ant-oatmeal and more\n"
        for size in (1, 3, 5, 100):
            out, found = self.masked(text, size)
            self.assertEqual(out, text, size)
            self.assertEqual(found, [], size)

    def test_a_tail_held_back_is_printed_at_the_end(self):
        masker = tokens.Masker()
        first = masker.feed("ready sk-")
        self.assertEqual(first, "ready ")
        self.assertEqual(masker.feed("", final=True), "sk-")

    def test_the_mask_is_no_secret_shape(self):
        for mask in (tokens.MASK, tokens.OTHER_MASK):
            for name, pattern in check_docs.SECRET_PATTERNS:
                self.assertIsNone(pattern.search(mask), name)
            self.assertIsNone(tokens.SECRET_SHAPE.search(mask))


class TheMint(unittest.TestCase):
    """claude setup-token behind the pseudo-terminal: the keyboard goes
    through, the terminal is wide, and the token comes back unseen."""

    def test_the_sign_in_runs_on_a_wide_terminal_and_the_token_comes_back_masked(self):
        folder = tempfile.mkdtemp(prefix="tokens-mint-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        bin_dir = install_claude(folder)
        report = str(Path(folder) / "report.json")
        collector = Collector()
        reader = code_pipe()
        with patch.dict(os.environ, {"FAKE_CLAUDE_REPORT": report, "COLUMNS": "80", "LINES": "24"}):
            try:
                found, status, cut = tokens.mint(stdin_fd=reader, write=collector, command=(str(bin_dir / "claude"), "setup-token"))
            finally:
                os.close(reader)
        self.assertEqual(found, [TOKEN])
        self.assertEqual(status, 0)
        self.assertFalse(cut)
        seen = read_json(report)
        self.assertEqual(seen["code"], "thecode")
        self.assertTrue(seen["tty"])
        self.assertEqual(seen["columns"], tokens.TERMINAL_SIZE[1])
        self.assertIsNone(seen["env_columns"], "the shell's COLUMNS would tell claude another width")
        self.assertNotIn(TOKEN, collector.text)
        self.assertFalse(has_token(collector.text))
        self.assertIn("Paste code here if prompted", collector.text)
        self.assertIn(tokens.MASK, collector.text)

    def test_a_claude_that_prints_no_token_is_reported_not_stored(self):
        folder = tempfile.mkdtemp(prefix="tokens-mint-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        bin_dir = Path(folder) / "bin"
        bin_dir.mkdir()
        claude = bin_dir / "claude"
        claude.write_text(f"#!{sys.executable} -IS\nimport sys\nsys.stdout.write('nothing today\\n')\nsys.exit(3)\n")
        claude.chmod(0o755)
        collector = Collector()
        reader = code_pipe("")
        try:
            with self.assertRaises(tokens.TokensError) as caught:
                tokens.minted_token(stdin_fd=reader, write=collector, command=(str(claude), "setup-token"))
        finally:
            os.close(reader)
        self.assertIn("exit 3", str(caught.exception))
        self.assertIn("--paste", str(caught.exception))

    def test_a_token_claude_wrapped_is_refused_not_stored(self):
        folder = tempfile.mkdtemp(prefix="tokens-mint-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        bin_dir = Path(folder) / "bin"
        bin_dir.mkdir()
        claude = bin_dir / "claude"
        # Cut at 79, past the length floor, with a rest of 17 characters;
        # and cut before the last character alone.
        for at in (79, len(TOKEN) - 1):
            claude.write_text(f"#!{sys.executable} -IS\nimport sys\nsys.stdout.write('Your token:\\n' + {TOKEN[:at]!r} + '\\r\\n' + {TOKEN[at:]!r} + '\\r\\n')\n")
            claude.chmod(0o755)
            collector = Collector()
            reader = code_pipe("")
            try:
                with self.assertRaises(tokens.TokensError) as caught:
                    tokens.minted_token(stdin_fd=reader, write=collector, command=(str(claude), "setup-token"))
            finally:
                os.close(reader)
            self.assertIn("cut over two lines", str(caught.exception))
            self.assertNotIn(TOKEN[:at], collector.text)
            self.assertNotIn(TOKEN[:20], str(caught.exception))

    def test_claude_is_found_where_its_own_installer_puts_it(self):
        folder = tempfile.mkdtemp(prefix="tokens-home-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        with patch.dict(os.environ, {"PATH": folder, "HOME": folder}):
            self.assertIsNone(tokens.claude_command())
            local = Path(folder) / ".claude" / "local" / "claude"
            local.parent.mkdir(parents=True)
            local.write_text("#!/bin/sh\n")
            local.chmod(0o755)
            self.assertEqual(tokens.claude_command(), str(local))

    def test_a_claude_that_is_not_there_is_named(self):
        collector = Collector()
        reader = code_pipe("")
        try:
            with self.assertRaises(tokens.TokensError) as caught:
                tokens.minted_token(stdin_fd=reader, write=collector, command=("/nonexistent/claude", "setup-token"))
        finally:
            os.close(reader)
        self.assertIn("could not be started", str(caught.exception))


class ThePaste(unittest.TestCase):
    def test_the_token_is_taken_out_of_what_was_pasted(self):
        self.assertEqual(tokens.check_token(TOKEN), TOKEN)
        self.assertEqual(tokens.check_token("export CLAUDE_CODE_OAUTH_TOKEN=" + TOKEN), TOKEN)
        self.assertEqual(tokens.pasted_token(ask=lambda prompt: "  " + TOKEN + "\n"), TOKEN)

    def test_an_api_key_is_refused(self):
        with self.assertRaises(tokens.TokensError) as caught:
            tokens.check_token(API_KEY)
        self.assertIn("API key", str(caught.exception))

    def test_a_window_that_cannot_hide_the_input_is_refused(self):
        import warnings

        def echoing(prompt):
            warnings.warn("Can not control echo on the terminal.", getpass.GetPassWarning, stacklevel=2)
            return TOKEN

        with patch.object(tokens.getpass, "getpass", echoing):
            with self.assertRaises(tokens.TokensError) as caught:
                tokens.hidden_input("Paste: ")
        self.assertIn("cannot hide", str(caught.exception))
        with patch.object(tokens.getpass, "getpass", lambda prompt: "  " + TOKEN + "\n"):
            self.assertEqual(tokens.pasted_token(), TOKEN)

    def test_anything_else_is_refused(self):
        for text in ("", "hello", "ghp_" + "x" * 40, TOKEN + " " + OTHER):
            with self.assertRaises(tokens.TokensError):
                tokens.check_token(text)


class Adding(unittest.TestCase):
    """add: the token minted behind the terminal goes to gh on its standard
    input, under the slot's name, with the place's visibility; the label and
    the list of slots follow; GitHub's listing is read back."""

    def test_a_new_slot_at_the_organization(self):
        world = World(self, secrets=[secret(tokens.slot_secret(1))])
        world.expect_store(tokens.slot_secret(2))
        state, printed, calls = world.run_in_process(self, tokens.add, tokens.Gh(), target(), None, "work", False, False)
        stores = find(calls, "secret set")
        self.assertEqual(len(stores), 1)
        self.assertEqual(stores[0]["stdin"], TOKEN)
        self.assertEqual(stores[0]["args"], ["secret", "set", tokens.slot_secret(2), "--org", ORG, "--visibility", "selected", "--repos", REPO])
        labels = find(calls, "variable set", tokens.slot_label(2))
        self.assertEqual(labels[0]["args"][-2:], ["--body", "work"])
        accounts = find(calls, "variable set", tokens.ACCOUNTS_VARIABLE)
        self.assertEqual(accounts[0]["args"][-2:], ["--body", "1,2"])
        self.assertEqual(world.report["code"], "thecode")
        self.assertNotIn(TOKEN, printed)
        self.assertFalse(has_token(printed))
        for call in calls:
            self.assertFalse(any(TOKEN in arg for arg in call["args"]), call["args"])
        self.assertIn("GitHub lists it", printed)
        self.assertIn(tokens.slot_secret(2), state.secrets)

    def test_a_slot_that_exists_keeps_its_list_and_grows_it(self):
        world = World(self, secrets=[secret(tokens.slot_secret(1))], variables=[variable(tokens.ACCOUNTS_VARIABLE, "1")])
        world.expect_store(tokens.slot_secret(1))
        _, printed, calls = world.run_in_process(self, tokens.add, tokens.Gh(), target(repos=("other",)), 1, "", False, False)
        store = find(calls, "secret set")[0]
        self.assertEqual(store["args"][-2:], ["--repos", "other,widgets"])
        self.assertIn("replaces it", printed)
        # The list of slots did not change, so it was not written.
        self.assertEqual(find(calls, "variable set", tokens.ACCOUNTS_VARIABLE), [])
        self.assertIn("unchanged", printed)

    def test_a_list_the_bench_refuses_is_written_again(self):
        # 01,02 names slots 1 and 2 to a reader that takes any number, and
        # stops the bench's real runs, which take only the words 1 to 8.
        for written, kept in (("01,02", False), ("1,2,9", False), ("1, 2", True)):
            world = World(self, secrets=[secret(tokens.slot_secret(1)), secret(tokens.slot_secret(2))],
                          variables=[variable(tokens.ACCOUNTS_VARIABLE, written)])
            run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
            printed = io.StringIO()
            with patch.object(tokens.subprocess, "run", run), redirect_stdout(printed):
                tokens.update_accounts(tokens.State(tokens.Gh(), target()))
            stores = find(world.calls(), "variable set", tokens.ACCOUNTS_VARIABLE)
            if kept:
                self.assertEqual(stores, [], written)
                self.assertIn("1,2 (unchanged)", printed.getvalue())
            else:
                self.assertEqual(len(stores), 1, written)
                self.assertEqual(stores[0]["args"][-2:], ["--body", "1,2"])

    def test_also_main_stores_the_same_token_under_the_workflows_name(self):
        world = World(self)
        world.expect_store(tokens.slot_secret(1), tokens.MAIN_SECRET)
        _, printed, calls = world.run_in_process(self, tokens.add, tokens.Gh(), target(), None, "", True, False)
        stores = find(calls, "secret set")
        self.assertEqual([call["args"][2] for call in stores], [tokens.slot_secret(1), tokens.MAIN_SECRET])
        self.assertEqual({call["stdin"] for call in stores}, {TOKEN})
        self.assertEqual(find(calls, "variable set", tokens.ACCOUNTS_VARIABLE)[0]["args"][-2:], ["--body", "1"])

    def test_a_pasted_token_goes_the_same_way(self):
        world = World(self)
        world.expect_store(tokens.slot_secret(1))
        _, printed, calls = world.run_in_process(self, tokens.add, tokens.Gh(), target(), None, "", False, True,
                                                 ask=lambda prompt: TOKEN)
        self.assertEqual(find(calls, "secret set")[0]["stdin"], TOKEN)
        self.assertIsNone(world.report, "claude did not run")

    def test_a_pasted_api_key_stores_nothing(self):
        world = World(self)
        with self.assertRaises(tokens.TokensError):
            world.run_in_process(self, tokens.add, tokens.Gh(), target(), None, "", False, True, ask=lambda prompt: API_KEY)
        self.assertEqual(find(world.calls(), "secret set"), [])

    def test_a_store_github_does_not_list_is_an_error(self):
        world = World(self)
        with self.assertRaises(tokens.TokensError) as caught:
            world.run_in_process(self, tokens.add, tokens.Gh(), target(), None, "", False, False)
        self.assertIn("does not list", str(caught.exception))
        # What fails after the store says the token was sent all the same.
        world = World(self)
        world.expect_store(tokens.slot_secret(1))
        routes = read_json(world.routes_file)
        routes["variable set"] = [answer(500, {"message": "down"})]
        fake_gh.write_routes(world.routes_file, routes)
        with self.assertRaises(tokens.TokensError) as caught:
            world.run_in_process(self, tokens.add, tokens.Gh(), target(), None, "", False, False)
        self.assertIn("500", str(caught.exception))
        self.assertIn("run status", str(caught.exception))
        self.assertEqual(find(world.calls(), "secret set")[0]["stdin"], TOKEN)

    def test_what_can_fail_fails_before_the_sign_in(self):
        # The list an existing secret reaches cannot be read (no admin:org
        # on that path): the sign-in is not spent on it.
        world = World(self, secrets=[secret(tokens.slot_secret(1))])
        routes = read_json(world.routes_file)
        routes[f"GET orgs/{ORG}/actions/secrets/{tokens.slot_secret(1)}/repositories"] = [
            answer(403, {"message": "Resource not accessible by integration"})]
        fake_gh.write_routes(world.routes_file, routes)
        with self.assertRaises(tokens.TokensError) as caught:
            world.run_in_process(self, tokens.add, tokens.Gh(), target(), 1, "", False, False)
        self.assertIn("403", str(caught.exception))
        self.assertIsNone(world.report, "claude did not run")
        self.assertEqual(find(world.calls(), "secret set"), [])
        # A repository the login cannot see is named before it too.
        world = World(self)
        with self.assertRaises(tokens.TokensError) as caught:
            world.run_in_process(self, tokens.add, tokens.Gh(), target(repos=("nothere",)), None, "", False, False)
        self.assertIn("nothere", str(caught.exception))
        self.assertIsNone(world.report, "claude did not run")

    def test_the_main_secret_alone(self):
        world = World(self, secrets=[secret(tokens.MAIN_SECRET, OLD, "all", 0)])
        world.expect_store(tokens.MAIN_SECRET)
        state, printed, calls = world.run_in_process(self, tokens.main_token, tokens.Gh(), target(), False)
        stores = find(calls, "secret set")
        self.assertEqual(len(stores), 1)
        self.assertEqual(stores[0]["stdin"], TOKEN)
        # An existing secret keeps its visibility, whatever the target says.
        self.assertEqual(stores[0]["args"], ["secret", "set", tokens.MAIN_SECRET, "--org", ORG, "--visibility", "all"])
        self.assertIn("replaces it", printed)
        self.assertIn("GitHub lists it", printed)
        self.assertFalse(has_token(printed))
        self.assertEqual(find(calls, "variable set"), [])
        self.assertEqual(world.report["code"], "thecode")

    def test_an_existing_visibility_is_kept(self):
        world = World(self, secrets=[secret("A", OLD, "all", 0), secret("B", OLD, "private", 0), secret("C", OLD, "selected", 1)])
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        routes = read_json(world.routes_file)
        routes[f"GET orgs/{ORG}/actions/secrets/C/repositories"] = [answer(200, "zeta\nalpha\n")]
        fake_gh.write_routes(world.routes_file, routes)
        with patch.object(tokens.subprocess, "run", run):
            state = tokens.State(tokens.Gh(), target())
            self.assertEqual(tokens.scope_args(state, "secrets", "A"), ["--visibility", "all"])
            self.assertEqual(tokens.scope_args(state, "secrets", "B"), ["--visibility", "private"])
            self.assertEqual(tokens.scope_args(state, "secrets", "C"), ["--visibility", "selected", "--repos", "alpha,widgets,zeta"])
            self.assertEqual(tokens.scope_args(state, "secrets", "D"), ["--visibility", "selected", "--repos", REPO])
            self.assertEqual(tokens.scope_args(tokens.State(tokens.Gh(), target(visibility="all")), "secrets", "D"), ["--visibility", "all"])

    def test_a_label_is_a_word_not_an_address(self):
        world = World(self)
        for label in ("me@example.org", "x" * 41, "-dash", "a\tb"):
            with self.assertRaises(tokens.TokensError):
                world.run_in_process(self, tokens.add, tokens.Gh(), target(), None, label, False, False)
        self.assertEqual(find(world.calls(), "secret set"), [])

    def test_the_repository_level_names_no_visibility(self):
        world = World(self)
        world.expect_store(tokens.slot_secret(1))
        place = tokens.Target("repo", ORG, name=REPO)
        _, printed, calls = world.run_in_process(self, tokens.add, tokens.Gh(), place, None, "", False, False)
        self.assertEqual(find(calls, "secret set")[0]["args"], ["secret", "set", tokens.slot_secret(1), "--repo", f"{ORG}/{REPO}"])
        self.assertEqual(find(calls, "variable set", tokens.ACCOUNTS_VARIABLE)[0]["args"][:5],
                         ["variable", "set", tokens.ACCOUNTS_VARIABLE, "--repo", f"{ORG}/{REPO}"])


class CrowdMode(unittest.TestCase):
    """A crowd repository holds no Claude token: the clone's mode line and
    the repository's variable each stop the wizard before any write."""

    def test_the_clone_s_mode_line_refuses(self):
        folder = tempfile.mkdtemp(prefix="tokens-crowd-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        project = Path(folder) / "project.md"
        project.write_text("# P\n\n## Crowd mode\n\n- Crowd mode: on. Set up 2026-10-01.\n")
        with self.assertRaises(tokens.TokensError) as caught:
            tokens.refuse_crowd(tokens.Gh(), target(), project=project)
        self.assertIn("crowd mode is on", str(caught.exception))

    def test_the_repository_s_variable_refuses_before_any_store(self):
        world = World(self, crowd="TRUE")
        with self.assertRaises(tokens.TokensError) as caught:
            world.run_in_process(self, tokens.add, tokens.Gh(), target(), None, "", False, False)
        self.assertIn("crowd mode", str(caught.exception))
        self.assertEqual(find(world.calls(), "secret set"), [])
        self.assertIsNone(world.report, "claude did not run")


class Status(unittest.TestCase):
    def test_the_state_is_names_dates_and_counts(self):
        world = World(self, secrets=[secret(tokens.slot_secret(1)), secret(tokens.slot_secret(3), NEW), secret(tokens.MAIN_SECRET, OLD, "all", 0)],
                      variables=[variable(tokens.slot_label(1), "greg"), variable(tokens.ACCOUNTS_VARIABLE, "1, 3")])
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        printed = io.StringIO()
        with patch.object(tokens.subprocess, "run", run), redirect_stdout(printed):
            tokens.print_status(tokens.State(tokens.Gh(), target()), now=datetime(2026, 10, 16, tzinfo=timezone.utc))
        text = printed.getvalue()
        self.assertIn(f"slot 1 (greg): {tokens.slot_secret(1)} set 2026-01-10, renew by 2027-01-10, seen by {REPO}", text)
        self.assertIn(f"slot 3: {tokens.slot_secret(3)} set 2026-10-16, renew by 2027-10-16", text)
        self.assertIn("free slots: 2, 4, 5, 6, 7, 8", text)
        self.assertIn(f"{tokens.ACCOUNTS_VARIABLE}: 1,3", text)
        self.assertIn(f"{tokens.MAIN_SECRET}: set 2026-01-10, renew by 2027-01-10 (the workflows' token)", text)

    def test_an_old_token_is_told_to_renew(self):
        now = datetime(2027, 2, 1, tzinfo=timezone.utc)
        self.assertIn("renew now", tokens.age_line(secret("x", OLD), now))
        self.assertIn("renew soon", tokens.age_line(secret("x", OLD), datetime(2026, 12, 20, tzinfo=timezone.utc)))
        self.assertNotIn("renew now", tokens.age_line(secret("x", NEW), now))

    def test_a_repository_s_own_list_of_slots_is_shown_as_outranking(self):
        # The to-do list of 2026-10-15b told the owner to make the list by
        # hand as coordbench's own variable, which would hide the
        # organization's list the wizard keeps.
        world = World(self, secrets=[secret(tokens.slot_secret(1))], variables=[variable(tokens.ACCOUNTS_VARIABLE, "1")])
        routes = read_json(world.routes_file)
        # The organization's list reaches a repository the options do not
        # name, as coordbench, which status reads too; the one named cannot
        # be read, and status goes on.
        routes[f"GET orgs/{ORG}/actions/variables/{tokens.ACCOUNTS_VARIABLE}/repositories"] = [answer(200, f"{REPO}\nbench\n")]
        routes["secret list"] = [answer(200, world.secrets), answer(200, []), answer(200, [])]
        routes["variable list"] = [answer(200, world.variables), answer(403, {"message": "Resource not accessible"}),
                                   answer(200, [{"name": tokens.ACCOUNTS_VARIABLE.lower(), "value": "\x1b[2J,1,2"}])]
        fake_gh.write_routes(world.routes_file, routes)
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        printed = io.StringIO()
        with patch.object(tokens.subprocess, "run", run), redirect_stdout(printed):
            tokens.print_status(tokens.State(tokens.Gh(), target()))
        text = printed.getvalue()
        self.assertIn(f"{ORG}/{REPO}: its own variables could not be read", text)
        self.assertIn(f"{ORG}/bench holds its own {tokens.ACCOUNTS_VARIABLE} (1,2, and a word that is not a slot", text)
        self.assertIn(f"https://github.com/{ORG}/bench/settings/variables/actions", text)
        self.assertNotIn("\x1b", text)
        self.assertEqual([call["args"] for call in find(world.calls(), "variable list")][1:], [
            ["variable", "list", "--repo", f"{ORG}/{REPO}", "--json", "name,value"],
            ["variable", "list", "--repo", f"{ORG}/bench", "--json", "name,value"]])
        # A repository that holds none is not named.
        world = World(self, variables=[variable(tokens.ACCOUNTS_VARIABLE, "1")])
        routes = read_json(world.routes_file)
        routes["secret list"] = [answer(200, []), answer(200, [])]
        routes["variable list"] = [answer(200, world.variables), answer(200, [])]
        fake_gh.write_routes(world.routes_file, routes)
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        printed = io.StringIO()
        with patch.object(tokens.subprocess, "run", run), redirect_stdout(printed):
            tokens.print_status(tokens.State(tokens.Gh(), target()))
        self.assertNotIn("holds its own", printed.getvalue())

    def test_a_list_is_read_as_the_bench_reads_it(self):
        # coordbench's plan.py splits the list on commas and blanks and
        # refuses a real run on any word that is not 1 to 8. A superscript
        # two passes isdigit() and fails int(), and int() refuses more than
        # 4,300 digits: neither may stop status.
        self.assertEqual(tokens.parse_slots("3, 1 1,2"), [3, 1, 2], "in the order the bench deals its jobs")
        self.assertEqual(tokens.parse_slots("01,02,9,0,08"), [])
        self.assertEqual(tokens.parse_slots("\u00b2,2"), [2])
        self.assertEqual(tokens.parse_slots("1" * 5000 + ",4"), [4])
        self.assertIsNone(tokens.slot_number("08"))
        for refused in ("01,02", "1,2,9", "1,2,junk", "\u00b2,2", "\x1b[2J,1"):
            self.assertTrue(tokens.holds_other_words(refused), refused)
        for taken in ("1,2", "2 1", " 1 , 2 ", "1\t2", ""):
            self.assertFalse(tokens.holds_other_words(taken), taken)
        self.assertEqual(tokens.slots_text("\x1b[2J,1,2"), "1,2, and a word that is not a slot, which stops the bench's real runs")
        self.assertEqual(tokens.slots_text("junk"), "no slot, and a word that is not a slot, which stops the bench's real runs")

    def test_a_label_made_by_hand_is_shown_only_as_a_word(self):
        world = World(self, secrets=[secret(tokens.slot_secret(1))],
                      variables=[variable(tokens.slot_label(1), "\x1b]0;title\x07work"), variable(tokens.slot_label(2), "work\n")])
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        printed = io.StringIO()
        with patch.object(tokens.subprocess, "run", run), redirect_stdout(printed):
            tokens.print_status(tokens.State(tokens.Gh(), target()))
        text = printed.getvalue()
        self.assertIn("slot 1 (a label not shown, not a word of a label's shape)", text)
        self.assertIn("the label of slot 2 (a label not shown, not a word of a label's shape) outlives its secret", text)
        self.assertNotIn("\x1b", text)
        with self.assertRaises(tokens.TokensError):
            tokens.check_label("work\n")

    def test_the_repositories_read_are_the_ones_that_read_what_is_kept(self):
        # Widgets is named, as Widgets, and listed as WIDGETS, one
        # repository whatever the case; lab is found on slot 1's listing
        # alone, so its own slot 1 outranks the organization's, while its own
        # list, if it held one, would be its only list, so it is not read;
        # the listing of the list's repositories fails, and status says so.
        world = World(self, secrets=[secret(tokens.slot_secret(1)), secret(tokens.MAIN_SECRET, OLD, "all", 0)],
                      variables=[variable(tokens.ACCOUNTS_VARIABLE, "01,02")])
        routes = read_json(world.routes_file)
        routes[f"GET orgs/{ORG}/actions/variables/{tokens.ACCOUNTS_VARIABLE}/repositories"] = [answer(403, {"message": "Forbidden"})]
        routes[f"GET orgs/{ORG}/actions/secrets/{tokens.slot_secret(1)}/repositories"] = [answer(200, f"{REPO.upper()}\nlab\n")]
        routes["secret list"] = [answer(200, world.secrets), answer(200, []),
                                 answer(200, [secret(tokens.slot_secret(1).lower(), NEW), secret(tokens.slot_secret(2), NEW)])]
        routes["variable list"] = [answer(200, world.variables), answer(200, [])]
        fake_gh.write_routes(world.routes_file, routes)
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        printed = io.StringIO()
        with patch.object(tokens.subprocess, "run", run), redirect_stdout(printed):
            tokens.print_status(tokens.State(tokens.Gh(), target(repos=("Widgets",))))
        text = printed.getvalue()
        self.assertIn(f"{tokens.ACCOUNTS_VARIABLE}: no slot, and a word that is not a slot, which stops the bench's real runs; "
                      "the next add or remove rewrites it", text)
        self.assertIn(f"the repositories that see {tokens.ACCOUNTS_VARIABLE} could not be listed", text)
        self.assertIn(f"{ORG}/lab holds its own {tokens.slot_secret(1)} (set 2026-10-16", text)
        self.assertNotIn(tokens.slot_secret(2) + " (", text)
        calls = world.calls()
        self.assertEqual([call["args"][3] for call in find(calls, "secret list") if "--repo" in call["args"]], [f"{ORG}/Widgets", f"{ORG}/lab"])
        self.assertEqual([call["args"][3] for call in find(calls, "variable list") if "--repo" in call["args"]], [f"{ORG}/Widgets"])
        # Each listing is asked for once, the slot line's and the reading's alike.
        self.assertEqual(len(find(calls, f"GET orgs/{ORG}/actions/secrets/{tokens.slot_secret(1)}/repositories")), 1)

    def test_a_repository_s_own_secret_is_shown_as_outranking(self):
        world = World(self, secrets=[secret(tokens.MAIN_SECRET, OLD, "all", 0)])
        routes = read_json(world.routes_file)
        routes["secret list"] = [answer(200, world.secrets), answer(200, [{"name": tokens.MAIN_SECRET, "updatedAt": NEW}])]
        fake_gh.write_routes(world.routes_file, routes)
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        printed = io.StringIO()
        with patch.object(tokens.subprocess, "run", run), redirect_stdout(printed):
            tokens.print_status(tokens.State(tokens.Gh(), target()))
        self.assertIn(f"{ORG}/{REPO} holds its own {tokens.MAIN_SECRET}", printed.getvalue())


class Removing(unittest.TestCase):
    def test_the_secret_and_the_label_go_and_the_list_follows(self):
        world = World(self, secrets=[secret(tokens.slot_secret(1)), secret(tokens.slot_secret(2))],
                      variables=[variable(tokens.slot_label(2), "work"), variable(tokens.ACCOUNTS_VARIABLE, "1,2")])
        routes = read_json(world.routes_file)
        routes["secret delete"] = [answer(200, "", after={"secret list": [answer(200, [secret(tokens.slot_secret(1))])]})]
        fake_gh.write_routes(world.routes_file, routes)
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        settings = Path(world.folder) / "settings.json"
        with patch.object(tokens.subprocess, "run", run), patch.object(tokens, "settings_path", lambda: settings), \
                redirect_stdout(io.StringIO()):
            tokens.remove(tokens.Gh(), target(), 2)
        calls = world.calls()
        self.assertEqual(find(calls, "secret delete")[0]["args"], ["secret", "delete", tokens.slot_secret(2), "--org", ORG])
        self.assertEqual(find(calls, "variable delete")[0]["args"][2], tokens.slot_label(2))
        self.assertEqual(find(calls, "variable set", tokens.ACCOUNTS_VARIABLE)[0]["args"][-2:], ["--body", "1"])


class TheOrder(unittest.TestCase):
    """The list of slots keeps the order it was given, which is the order
    the bench deals its jobs to the slots."""

    def run_with(self, world, function, *args):
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        with patch.object(tokens.subprocess, "run", run), redirect_stdout(io.StringIO()) as printed:
            function(*args)
        return printed.getvalue()

    def test_order_writes_the_list_as_given(self):
        world = World(self, secrets=[secret(tokens.slot_secret(slot)) for slot in (1, 2, 3)],
                      variables=[variable(tokens.ACCOUNTS_VARIABLE, "1,2,3")])
        self.run_with(world, tokens.reorder, tokens.Gh(), target(), "3,1,2")
        self.assertEqual(find(world.calls(), "variable set", tokens.ACCOUNTS_VARIABLE)[0]["args"][-2:], ["--body", "3,1,2"])

    def test_an_order_that_is_not_every_set_slot_once_is_refused(self):
        world = World(self, secrets=[secret(tokens.slot_secret(slot)) for slot in (1, 2, 3)])
        for text in ("3,1", "3,1,2,4", "3,1,1,2", "3,1,x,2", "03,1,2"):
            with self.assertRaises(tokens.TokensError) as caught:
                self.run_with(world, tokens.reorder, tokens.Gh(), target(), text)
            self.assertIn("1,2,3", str(caught.exception))
        self.assertEqual(find(world.calls(), "variable set"), [])

    def test_nothing_to_order_is_refused(self):
        world = World(self)
        with self.assertRaises(tokens.TokensError):
            self.run_with(world, tokens.reorder, tokens.Gh(), target(), "")

    def test_status_names_a_slot_listed_twice(self):
        self.assertIn("named twice", tokens.slots_text("1,1,2"))
        self.assertEqual(tokens.slots_text("3,1"), "3,1")

    def test_a_new_slot_joins_the_end_and_the_order_stays(self):
        world = World(self, secrets=[secret(tokens.slot_secret(slot)) for slot in (1, 2, 3)],
                      variables=[variable(tokens.ACCOUNTS_VARIABLE, "3,1")])
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        with patch.object(tokens.subprocess, "run", run), redirect_stdout(io.StringIO()):
            state = tokens.State(tokens.Gh(), target())
            self.assertEqual(tokens.ordered_slots(state), [3, 1, 2])
            tokens.update_accounts(state)
        self.assertEqual(find(world.calls(), "variable set", tokens.ACCOUNTS_VARIABLE)[0]["args"][-2:], ["--body", "3,1,2"])


class Forgetting(unittest.TestCase):
    def test_forget_and_profiles(self):
        folder = Path(tempfile.mkdtemp(prefix="tokens-forget-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = folder / "tokens.json"
        tokens.remember(path, tokens.read_settings(path), target(), 2, "Symphony 2", 4)
        with redirect_stdout(io.StringIO()) as printed:
            tokens.print_remembered(target(), path)
        self.assertIn("slot 2: browser profile Symphony 2, cswap account 4", printed.getvalue())
        with redirect_stdout(io.StringIO()) as printed:
            tokens.forget(target(), 2, path)
            tokens.print_remembered(target(), path)
        self.assertIn("forgotten", printed.getvalue())
        self.assertTrue(printed.getvalue().rstrip().endswith("nothing"))


class ThePlace(unittest.TestCase):
    def parse(self, *argv):
        return tokens.build_parser().parse_args(list(argv))

    def test_the_place_options_go_before_or_after_the_command(self):
        self.assertEqual(self.parse("--org", ORG, "add").org, ORG)
        self.assertEqual(self.parse("add", "--org", ORG).org, ORG)
        self.assertIsNone(self.parse("add").org)
        self.assertEqual(self.parse("status", "--repos", "a,b").repos, "a,b")
        self.assertEqual(self.parse("--repo", "o/n", "remove", "2").slot, 2)

    def test_the_origin_decides_when_nothing_is_said(self):
        folder = tempfile.mkdtemp(prefix="tokens-origin-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        subprocess.run(["git", "init", "-q", folder], check=True)
        subprocess.run(["git", "-C", folder, "remote", "add", "origin", f"git@github.com:{ORG}/{REPO}.git"], check=True)
        self.assertEqual(tokens.origin_repository(Path(folder)), (ORG, REPO))
        world = World(self)
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        with patch.object(tokens.subprocess, "run", run):
            place = tokens.target_from(self.parse(), tokens.Gh(), root=Path(folder))
        self.assertEqual((place.level, place.owner, place.repos), ("org", ORG, [REPO]))
        self.assertEqual(place.describe(), f"the organization {ORG}, seen by {REPO}")

    def test_a_personal_account_takes_the_repository_level(self):
        folder = tempfile.mkdtemp(prefix="tokens-origin-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        subprocess.run(["git", "init", "-q", folder], check=True)
        subprocess.run(["git", "-C", folder, "remote", "add", "origin", "https://github.com/ada/engine.git"], check=True)
        world = World(self)
        routes = read_json(world.routes_file)
        routes["GET users/ada"] = [answer(200, "User\n")]
        fake_gh.write_routes(world.routes_file, routes)
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        with patch.object(tokens.subprocess, "run", run):
            place = tokens.target_from(self.parse(), tokens.Gh(), root=Path(folder))
            with self.assertRaises(tokens.TokensError):
                tokens.target_from(self.parse("--repos", "x"), tokens.Gh(), root=Path(folder))
        self.assertEqual((place.level, place.full_name), ("repo", "ada/engine"))

    def test_an_organization_named_alone_takes_the_origin_s_repository(self):
        world = World(self)
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        with patch.object(tokens.subprocess, "run", run):
            with self.assertRaises(tokens.TokensError) as caught:
                tokens.target_from(self.parse("--org", "elsewhere"), tokens.Gh(), root=Path(tempfile.gettempdir()))
        self.assertIn("--repos", str(caught.exception))
        place = tokens.target_from(self.parse("--org", "elsewhere", "--visibility", "all"), tokens.Gh(), root=Path(tempfile.gettempdir()))
        self.assertEqual(place.describe(), "the organization elsewhere, seen by every repository")

    def test_options_that_cannot_go_together_are_usage_errors(self):
        here = Path(tempfile.gettempdir())
        for argv in (("--repo", "o/n", "--repos", "a"), ("--repo", "o/n", "--visibility", "all"),
                     ("--org", "x", "--repos", "a,b", "--visibility", "all"), ("--org", "x",), ("--repos", "a/b",)):
            with self.assertRaises(tokens.UsageError, msg=argv):
                tokens.check_options(self.parse(*argv), root=here)
        with self.assertRaises(tokens.UsageError):
            tokens.check_options(self.parse(), root=here)
        self.assertEqual(tokens.check_options(self.parse("--org", "x", "--repos", "a,b"), root=here), (["a", "b"], "selected", None))
        self.assertEqual(tokens.check_options(self.parse("--repo", "o/n"), root=here), ([], "selected", None))
        # As a process, before gh is asked anything: exit 2 with no fake gh on PATH.
        done = subprocess.run([sys.executable, str(SCRIPT), "--org", "x", "--repos", "a", "--visibility", "all", "status"],
                              capture_output=True, text=True, cwd=ROOT, env={"PATH": "/nonexistent"})
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn("drop one", done.stderr)

    def test_the_organization_needs_the_scope_before_any_sign_in(self):
        short = SIGNED_IN.replace(SCOPES_LINE, "  Token scopes: 'gist', 'read:org', 'repo', 'workflow'\n")
        with self.assertRaises(tokens.TokensError) as caught:
            tokens.check_scopes(short, target())
        self.assertIn("admin:org", str(caught.exception))
        tokens.check_scopes(short, tokens.Target("repo", ORG, name=REPO))
        # The scope is read whole: admin:org_hook is not admin:org.
        with self.assertRaises(tokens.TokensError):
            tokens.check_scopes(SIGNED_IN.replace(SCOPES_LINE, "  Token scopes: 'admin:org_hook', 'repo'\n"), target())
        tokens.check_scopes(SIGNED_IN, target())
        # A token of another kind lists no scopes; gh says what it lacks when a call is refused.
        tokens.check_scopes(SIGNED_IN.replace(SCOPES_LINE, "  Token scopes: none\n"), target())

    def test_the_status_read_is_the_active_account_on_github_com(self):
        # The plain gh auth status fails on any stale account of any host
        # it knows, so the wizard asks for the one account it uses.
        world = World(self)
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        with patch.object(tokens.subprocess, "run", run):
            status = tokens.check_signed_in(tokens.Gh())
        self.assertIn(SCOPES_LINE, status)
        self.assertEqual(find(world.calls(), "auth status")[0]["args"], ["auth", "status", "--hostname", "github.com", "--active"])
        # A gh too old for --active is asked for the host alone.
        world = World(self)
        routes = read_json(world.routes_file)
        routes["auth status"] = [answer(1, "", stderr="unknown flag: --active\n"), answer(200, SIGNED_IN)]
        routes["auth status"][0]["status"] = 400
        fake_gh.write_routes(world.routes_file, routes)
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        with patch.object(tokens.subprocess, "run", run):
            status = tokens.check_signed_in(tokens.Gh())
        self.assertIn(SCOPES_LINE, status)
        self.assertEqual([call["args"] for call in find(world.calls(), "auth status")],
                         [["auth", "status", "--hostname", "github.com", "--active"], ["auth", "status", "--hostname", "github.com"]])

    def test_not_signed_in_is_said_first(self):
        world = World(self)
        routes = read_json(world.routes_file)
        routes["auth status"] = [answer(1, "", stderr="You are not logged into any GitHub hosts. To log in, run: gh auth login\n")]
        routes["auth status"][0]["status"] = 401
        fake_gh.write_routes(world.routes_file, routes)
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        with patch.object(tokens.subprocess, "run", run):
            with self.assertRaises(tokens.TokensError) as caught:
                tokens.check_signed_in(tokens.Gh())
        self.assertIn("gh auth login", str(caught.exception))


class TheWizard(unittest.TestCase):
    def test_one_account_then_stop(self):
        world = World(self)
        world.expect_store(tokens.slot_secret(1), tokens.MAIN_SECRET)
        answers = iter(["", "greg", "", "y", "n"])
        _, printed, calls = world.run_in_process(self, tokens.wizard, tokens.Gh(), target(), ask=lambda prompt: next(answers), local=tokens.Local())
        stores = find(calls, "secret set")
        self.assertEqual([call["args"][2] for call in stores], [tokens.slot_secret(1), tokens.MAIN_SECRET])
        self.assertEqual(find(calls, "variable set", tokens.slot_label(1))[0]["args"][-2:], ["--body", "greg"])
        self.assertEqual(printed.count("sign in to claude.ai as the account this slot is for"), 1)
        self.assertFalse(has_token(printed))

    def test_the_closing_status_shows_the_list_the_run_wrote(self):
        # The list is written after the check's read, so a closing status
        # printed from that read said "not set" on the owner's first run.
        world = World(self)
        world.expect_store(tokens.slot_secret(1))
        routes = read_json(world.routes_file)
        written = [variable(tokens.ACCOUNTS_VARIABLE, "1")]
        routes["variable set"] = [answer(200, "", after={"variable list": [answer(200, written)]})]
        fake_gh.write_routes(world.routes_file, routes)
        answers = iter(["", "", "", "n", "n"])
        _, printed, calls = world.run_in_process(self, tokens.wizard, tokens.Gh(), target(), ask=lambda prompt: next(answers), local=tokens.Local())
        self.assertEqual(find(calls, "variable set", tokens.ACCOUNTS_VARIABLE)[0]["args"][-2:], ["--body", "1"])
        lines = [line.strip() for line in printed.splitlines() if line.strip().startswith(tokens.ACCOUNTS_VARIABLE + ":")]
        self.assertEqual(lines[0], f"{tokens.ACCOUNTS_VARIABLE}: not set")
        self.assertEqual(lines[-1], f"{tokens.ACCOUNTS_VARIABLE}: 1")

    def test_the_slot_question(self):
        world = World(self, secrets=[secret(tokens.slot_secret(1))])
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        with patch.object(tokens.subprocess, "run", run):
            state = tokens.State(tokens.Gh(), target())
        self.assertEqual(tokens.chosen_slot(state, lambda prompt: ""), 2)
        self.assertEqual(tokens.chosen_slot(state, lambda prompt: "1"), 1)
        self.assertIsNone(tokens.chosen_slot(state, lambda prompt: "n"))
        for answer in ("9", "08", "\u00b2", "1" * 5000):
            with self.assertRaises(tokens.TokensError):
                tokens.chosen_slot(state, lambda prompt: answer)


def install_browser(folder):
    """A fake Chromium browser at a path of its own, and where it reports."""
    program = Path(folder) / "browser dir" / "chrome"
    program.parent.mkdir(parents=True, exist_ok=True)
    program.write_text(f"#!{sys.executable} -IS\n" + FAKE_BROWSER, encoding="utf-8")
    program.chmod(0o755)
    return tokens.Browser("Chrome", program), str(Path(folder) / "browser-report.json")


def wait_for(path, seconds=10):
    """The launcher returns before the browser it starts writes, as a real
    launch does."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if os.path.exists(path) and os.path.getsize(path):
            return read_json(path)
        time.sleep(0.05)
    raise AssertionError(f"{path} was never written")


def sequence(accounts, sequence_numbers=None):
    """cswap's sequence.json as cswap 0.27.2 writes it."""
    return {"activeAccountNumber": 1, "lastUpdated": "2026-10-17T00:00:00", "sequence": sequence_numbers or [a["n"] for a in accounts],
            "accounts": {str(a["n"]): {key: value for key, value in a.items() if key != "n"} for a in accounts}}


ACCOUNTS = [{"n": 1, "email": "one@example.com", "organizationName": "Org One", "organizationUuid": "u1"},
            {"n": 2, "email": "two@example.com", "alias": "bench2", "organizationName": "", "organizationUuid": "u2"},
            {"n": 3, "email": "three@example.com", "alias": "x@y.z"}]


class TheProfile(unittest.TestCase):
    """The sign-in link goes to one browser profile through BROWSER, which
    claude opens its link with, and a launcher that lives for the one run."""

    def test_the_link_reaches_the_profile_and_the_token_stays_unseen(self):
        folder = tempfile.mkdtemp(prefix="tokens-profile-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        bin_dir = install_claude(folder)
        browser, browser_report = install_browser(folder)
        report = str(Path(folder) / "report.json")
        collector = Collector()
        reader = code_pipe()
        opener = tokens.Opener(browser, "Symphony 1")
        with patch.dict(os.environ, {"FAKE_CLAUDE_REPORT": report, "FAKE_BROWSER_REPORT": browser_report}):
            try:
                with tokens.launcher(opener) as env:
                    found = tokens.minted_token(stdin_fd=reader, write=collector, command=(str(bin_dir / "claude"), "setup-token"), env=env)
                    launcher_path = env["BROWSER"]
            finally:
                os.close(reader)
        self.assertEqual(found, TOKEN)
        self.assertEqual(wait_for(browser_report), ["--profile-directory=Symphony 1", SIGN_IN_LINK])
        self.assertEqual(read_json(report)["browser"], launcher_path)
        self.assertFalse(os.path.exists(launcher_path), "the launcher is gone once the sign-in is over")
        self.assertFalse(has_token(collector.text))

    def test_the_browser_outlives_the_hangup_of_claude_s_terminal(self):
        # When claude ends, its terminal closes and the kernel sends a
        # hangup to the processes on it, the browser the launcher started
        # among them; nohup ignored it only once it had run, so a browser
        # still starting was killed, one run in three under load.
        folder = tempfile.mkdtemp(prefix="tokens-hangup-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        program = Path(folder) / "chrome"
        pid_file, report = Path(folder) / "pid", Path(folder) / "report.json"
        program.write_text(f"#!{sys.executable} -IS\nimport json, os, sys, time\n"
                           f"open({str(pid_file)!r}, 'w').write(str(os.getpid()))\ntime.sleep(1)\n"
                           f"open({str(report)!r}, 'w').write(json.dumps(sys.argv[1:]))\n", encoding="utf-8")
        program.chmod(0o755)
        with tokens.launcher(tokens.Opener(tokens.Browser("Chrome", program), "Default")) as env:
            started = subprocess.run([env["BROWSER"], SIGN_IN_LINK], timeout=30)
        self.assertEqual(started.returncode, 0)
        deadline = time.monotonic() + 10
        while not (pid_file.exists() and pid_file.read_text()) and time.monotonic() < deadline:
            time.sleep(0.02)
        os.kill(int(pid_file.read_text()), signal.SIGHUP)
        self.assertEqual(wait_for(str(report)), ["--profile-directory=Default", SIGN_IN_LINK])

    def test_without_a_profile_claude_keeps_its_own_browser(self):
        with tokens.launcher(None) as env:
            self.assertEqual(env, {})

    def test_a_program_or_profile_the_launcher_cannot_carry_is_refused(self):
        for path in ("C:\\Users\\Zo\u00eb\\chrome.exe", 'C:\\a"b\\chrome.exe', "C:\\%TEMP%\\chrome.exe", "/opt/$HOME/chrome", "/opt/a`b`", "/opt/a!b", "/opt/a\nb", ""):
            with self.assertRaises(tokens.TokensError):
                tokens.Opener(tokens.Browser("Chrome", path), "Default")
        for profile in ("", "../x", "a\"b", "Profile & 2", "a" * 41, "\u00e9t\u00e9", " Lead"):
            with self.assertRaises(tokens.TokensError):
                tokens.Opener(tokens.Browser("Chrome", "/usr/bin/chrome"), profile)

    def test_the_browser_is_found_where_its_installer_puts_it(self):
        home = Path("/home/u")
        windows_env = {"LOCALAPPDATA": r"C:\Users\u\AppData\Local", "ProgramFiles": r"C:\Program Files",
                       "ProgramFiles(x86)": r"C:\Program Files (x86)"}
        edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        found = tokens.find_browser("win32", windows_env, home, which=lambda name: None, is_file=lambda path: path == edge)
        self.assertEqual((found.name, found.path), ("Edge", edge))
        self.assertEqual(str(found.data).replace("/", "\\"), r"C:\Users\u\AppData\Local\Microsoft\Edge\User Data")
        found = tokens.find_browser("linux", {}, home, which=lambda name: "/usr/bin/chromium" if name == "chromium" else None,
                                    is_file=lambda path: True)
        self.assertEqual((found.name, found.path, found.data), ("Chromium", "/usr/bin/chromium", home / ".config" / "chromium"))
        chrome = "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
        found = tokens.find_browser("wsl", {}, home, which=lambda name: None, is_file=lambda path: path == chrome)
        self.assertEqual((found.path, found.data), (chrome, None))
        self.assertIsNone(tokens.find_browser("darwin", {}, home, which=lambda name: None, is_file=lambda path: False))
        found = tokens.find_browser("linux", {"SYMPHONY_BROWSER": "/opt/vivaldi"}, home, which=lambda name: None, is_file=lambda path: False)
        self.assertEqual(found.path, "/opt/vivaldi")

    def test_the_browser_s_own_profiles_are_listed_by_folder(self):
        folder = Path(tempfile.mkdtemp(prefix="tokens-local-state-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        browser = tokens.Browser("Chrome", "/usr/bin/chrome", folder)
        self.assertEqual(tokens.browser_profiles(browser), [])
        (folder / "Local State").write_text("not json")
        self.assertEqual(tokens.browser_profiles(browser), [])
        cache = {"Profile 2": {"name": "Work"}, "Default": {"name": "Person 1"}, "../evil": {"name": "x"}, "Profile 3": {"name": "\x1b[2J"}}
        (folder / "Local State").write_text(json.dumps({"profile": {"info_cache": cache}}))
        self.assertEqual(tokens.browser_profiles(browser), [("Default", "Person 1"), ("Profile 2", "Work"), ("Profile 3", "Profile 3")])

    def test_the_profile_question(self):
        folder = Path(tempfile.mkdtemp(prefix="tokens-local-state-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        (folder / "Local State").write_text(json.dumps({"profile": {"info_cache": {"Default": {"name": "Me"}, "Profile 2": {"name": "Bench"}}}}))
        browser = tokens.Browser("Chrome", "/usr/bin/chrome", folder)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(tokens.chosen_profile(browser, 3, None, lambda prompt: ""), "Symphony 3")
            self.assertEqual(tokens.chosen_profile(browser, 3, "Profile 2", lambda prompt: ""), "Profile 2")
            self.assertEqual(tokens.chosen_profile(browser, 3, None, lambda prompt: "2"), "Profile 2")
            self.assertEqual(tokens.chosen_profile(browser, 3, None, lambda prompt: "Profile 9"), "Profile 9")
            self.assertIsNone(tokens.chosen_profile(browser, 3, "Profile 2", lambda prompt: "n"))
            self.assertIsNone(tokens.chosen_profile(None, 3, None, lambda prompt: self.fail("no browser, no question")))
            with self.assertRaises(tokens.TokensError):
                tokens.chosen_profile(browser, 3, None, lambda prompt: "a;b")

    def test_add_profile_needs_a_browser(self):
        with patch.object(tokens, "find_browser", lambda: None), self.assertRaises(tokens.TokensError) as caught:
            tokens.profile_opener("Profile 2")
        self.assertIn("SYMPHONY_BROWSER", str(caught.exception))
        self.assertIsNone(tokens.profile_opener(None))
        self.assertEqual(tokens.profile_opener("Default", tokens.Browser("Edge", "/usr/bin/edge")).profile, "Default")

    def test_a_windows_shell_reads_claude_through_a_pipe_and_catches_the_token(self):
        # No pseudo-terminal: claude keeps this console's keyboard and its
        # output comes on a pipe, through the same mask.
        folder = tempfile.mkdtemp(prefix="tokens-pipe-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        bin_dir = install_claude(folder)
        report = str(Path(folder) / "report.json")
        collector = Collector()
        reader = code_pipe()
        with patch.dict(os.environ, {"FAKE_CLAUDE_REPORT": report}):
            try:
                found = tokens.minted_token(mint_with=tokens.piped_mint, write=collector,
                                            command=(str(bin_dir / "claude"), "setup-token"), stdin=reader)
            finally:
                os.close(reader)
        self.assertEqual(found, TOKEN)
        seen = read_json(report)
        self.assertEqual(seen["code"], "thecode", "the keyboard reached claude")
        self.assertFalse(seen["tty"])
        self.assertNotIn(TOKEN, collector.text)
        self.assertFalse(has_token(collector.text))
        self.assertIn(tokens.MASK, collector.text)

    def test_a_claude_that_will_not_start_through_a_pipe_is_named(self):
        with self.assertRaises(tokens.TokensError) as caught:
            tokens.minted_token(mint_with=tokens.piped_mint, write=Collector(), command=("/nonexistent/claude", "setup-token"))
        self.assertIn("could not be started", str(caught.exception))

    def test_a_program_claude_left_holding_the_pipe_does_not_hold_the_wizard(self):
        # A browser claude started may keep the pipe open long after claude
        # ends; the run ends a moment after claude, with the token.
        folder = tempfile.mkdtemp(prefix="tokens-pipe-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        claude = Path(folder) / "claude"
        claude.write_text(f"#!/bin/sh\nsleep 30 &\nprintf 'Your token:\\n%s\\n' {TOKEN}\n", encoding="utf-8")
        claude.chmod(0o755)
        collector = Collector()
        began = time.monotonic()
        found = tokens.minted_token(mint_with=tokens.piped_mint, write=collector, command=(str(claude), "setup-token"),
                                    stdin=subprocess.DEVNULL)
        self.assertEqual(found, TOKEN)
        self.assertLess(time.monotonic() - began, 10)
        self.assertFalse(has_token(collector.text))

    def test_a_claude_ended_by_a_signal_is_reported_as_such(self):
        folder = tempfile.mkdtemp(prefix="tokens-pipe-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        claude = Path(folder) / "claude"
        claude.write_text("#!/bin/sh\nkill -9 $$\n", encoding="utf-8")
        claude.chmod(0o755)
        with self.assertRaises(tokens.TokensError) as caught:
            tokens.minted_token(mint_with=tokens.piped_mint, write=Collector(), command=(str(claude), "setup-token"),
                                stdin=subprocess.DEVNULL)
        self.assertIn("exit -9", str(caught.exception))

    def test_a_window_claude_cannot_read_the_keyboard_from_takes_the_paste(self):
        printed = io.StringIO()
        with patch.object(tokens, "pty_available", lambda: False), patch.object(tokens, "claude_command", lambda: r"C:\bin\claude.exe"), \
                patch.object(tokens.sys, "platform", "win32"), patch.object(tokens, "console_keyboard", lambda: False), \
                patch.object(tokens.subprocess, "Popen", lambda *a, **k: self.fail("nothing is started")), redirect_stdout(printed):
            token = tokens.get_token(argparse_namespace(), ask=lambda prompt: TOKEN,
                                     opener=tokens.Opener(tokens.Browser("Chrome", r"C:\chrome.exe"), "Default"))
        self.assertEqual(token, TOKEN)
        self.assertIn("Windows Terminal", printed.getvalue())

    def test_a_windows_shell_opens_the_profile_blank_then_mints(self):
        # A batch launcher would get a link cut at its = and &, so the
        # profile is opened first, on a blank page, so no second sign-in shows.
        started, minted = [], []

        def popen(command, **options):
            started.append(command)

        def fake_mint(**options):
            minted.append(options["command"])
            return [TOKEN], 0, False

        browser = tokens.Browser("Chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        printed = io.StringIO()
        with patch.object(tokens, "pty_available", lambda: False), patch.object(tokens, "claude_command", lambda: r"C:\bin\claude.exe"), \
                patch.object(tokens.sys, "platform", "win32"), patch.object(tokens.subprocess, "Popen", popen), \
                patch.object(tokens.time, "sleep", lambda seconds: None), patch.object(tokens, "piped_mint", fake_mint), \
                patch.object(tokens, "console_keyboard", lambda: True), \
                redirect_stdout(printed):
            token = tokens.get_token(argparse_namespace(), opener=tokens.Opener(browser, "Symphony 2"))
        self.assertEqual(token, TOKEN)
        self.assertEqual(started, [[browser.path, "--profile-directory=Symphony 2", "about:blank"]])
        self.assertEqual(minted, [(r"C:\bin\claude.exe", "setup-token")])
        self.assertFalse(has_token(printed.getvalue()))


def argparse_namespace(paste=False):
    import argparse
    return argparse.Namespace(paste=paste)


class Cswap(unittest.TestCase):
    """claude-swap's accounts, read from its sequence.json alone."""

    def home(self):
        folder = Path(tempfile.mkdtemp(prefix="tokens-cswap-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        return folder

    def write(self, root, data):
        root.mkdir(parents=True, exist_ok=True)
        (root / "sequence.json").write_text(data if isinstance(data, str) else json.dumps(data))

    def test_the_list_is_read_where_cswap_keeps_it(self):
        home = self.home()
        self.assertEqual(tokens.cswap_accounts("linux", {}, home), [])
        self.write(home / ".claude-swap-backup", sequence(ACCOUNTS[:1]))
        self.assertEqual([a.number for a in tokens.cswap_accounts("win32", {}, home)], [1])
        self.assertEqual([a.number for a in tokens.cswap_accounts("linux", {}, home)], [1], "the older folder, before cswap moves it")
        self.write(home / ".local" / "share" / "claude-swap", sequence(ACCOUNTS))
        accounts = tokens.cswap_accounts("wsl", {}, home)
        self.assertEqual([(a.number, a.alias, a.organization) for a in accounts], [(1, "", "Org One"), (2, "bench2", ""), (3, "x@y.z", "")])
        self.write(home / "xdg" / "claude-swap", sequence(ACCOUNTS[1:2]))
        self.assertEqual([a.number for a in tokens.cswap_accounts("linux", {"XDG_DATA_HOME": str(home / "xdg")}, home)], [2])
        self.assertEqual([a.number for a in tokens.cswap_accounts("darwin", {"XDG_DATA_HOME": str(home / "xdg")}, home)], [1])

    def test_what_does_not_hold_together_is_skipped(self):
        home = self.home()
        root = home / ".claude-swap-backup"
        for data in ("{", "[]", json.dumps({"sequence": "12"}), json.dumps({"sequence": 5, "accounts": {}}),
                     json.dumps({"sequence": True}), json.dumps({"sequence": [1], "accounts": []})):
            self.write(root, data)
            self.assertEqual(tokens.cswap_accounts("win32", {}, home), [])
        odd = sequence(ACCOUNTS, [1, "2", True, 0, 5000, 9, 2, 1])
        odd["accounts"]["2"]["alias"] = "\x1b[31mred"
        self.write(root, odd)
        self.assertEqual([(a.number, a.alias) for a in tokens.cswap_accounts("win32", {}, home)], [(1, ""), (2, "")], "a number listed twice is shown once")
        self.write(root, " " * (tokens.READ_LIMIT + 1))
        self.assertEqual(tokens.cswap_accounts("win32", {}, home), [])

    def test_the_account_question_and_the_label_it_offers(self):
        accounts = [tokens.CswapAccount(a["n"], a["email"], a.get("alias", ""), a.get("organizationName", "")) for a in ACCOUNTS]
        with redirect_stdout(io.StringIO()) as printed:
            self.assertIsNone(tokens.chosen_account([], None, lambda prompt: self.fail("no cswap, no question")))
            self.assertIsNone(tokens.chosen_account(accounts, None, lambda prompt: ""))
            self.assertEqual(tokens.chosen_account(accounts, 2, lambda prompt: "").number, 2)
            self.assertEqual(tokens.chosen_account(accounts, None, lambda prompt: "3").number, 3)
            for answer in ("4", "x", "\u0663", "1" * 5000):
                with self.assertRaises(tokens.TokensError):
                    tokens.chosen_account(accounts, None, lambda prompt: answer)
        self.assertIn("2: bench2 (two@example.com)", printed.getvalue())
        self.assertEqual([tokens.label_from(a) for a in accounts], ["", "bench2", ""], "an address is never a label")
        self.assertEqual(tokens.label_from(None), "")


class TheSettings(unittest.TestCase):
    """What the wizard remembers is a profile's folder and a cswap number
    per slot, on this machine, outside the repository."""

    def test_the_file_is_in_the_user_s_settings_folder(self):
        home = Path("/home/u")
        self.assertEqual(tokens.settings_path("linux", {}, home), home / ".config" / "symphony" / "tokens.json")
        self.assertEqual(tokens.settings_path("linux", {"XDG_CONFIG_HOME": "/x"}, home), Path("/x/symphony/tokens.json"))
        self.assertEqual(tokens.settings_path("linux", {"XDG_CONFIG_HOME": "rel"}, home), home / ".config" / "symphony" / "tokens.json")
        self.assertEqual(tokens.settings_path("win32", {"APPDATA": "/appdata"}, home), Path("/appdata/symphony/tokens.json"))

    def test_remembered_and_written_once(self):
        folder = Path(tempfile.mkdtemp(prefix="tokens-settings-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = folder / "symphony" / "tokens.json"
        settings = tokens.read_settings(path)
        self.assertEqual(tokens.remembered(settings, target(), 1), {"profile": None, "cswap": None})
        tokens.remember(path, settings, target(), 1, "Symphony 1", 2)
        self.assertEqual(oct(path.stat().st_mode & 0o777), "0o600")
        again = tokens.read_settings(path)
        self.assertEqual(tokens.remembered(again, target(), 1), {"profile": "Symphony 1", "cswap": 2})
        self.assertEqual(tokens.remembered(again, tokens.Target("repo", ORG, name=REPO), 1), {"profile": None, "cswap": None})
        before = path.stat().st_mtime_ns
        os.utime(path, ns=(0, 0))
        tokens.remember(path, again, target(), 1, "Symphony 1", 2)
        self.assertEqual(path.stat().st_mtime_ns, 0, "nothing changed, nothing written")
        self.assertNotEqual(before, 0)
        tokens.remember(path, again, target(), 1, None, None)
        self.assertEqual(tokens.remembered(tokens.read_settings(path), target(), 1), {"profile": None, "cswap": None})
        path.write_text(json.dumps({"version": 1, "slots": {"org:octo": {"1": {"profile": "a;b", "cswap": True}}}}))
        self.assertEqual(tokens.remembered(tokens.read_settings(path), target(), 1), {"profile": None, "cswap": None})

    def test_a_file_that_cannot_be_written_costs_only_the_remembering(self):
        folder = Path(tempfile.mkdtemp(prefix="tokens-settings-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        (folder / "symphony").write_text("a file where the folder would be")
        path = folder / "symphony" / "tokens.json"
        with redirect_stdout(io.StringIO()) as printed:
            tokens.remember(path, tokens.read_settings(path), target(), 1, "Default", None)
        self.assertIn("not remembered", printed.getvalue())


class TheWizardOnAMachine(unittest.TestCase):
    """The wizard with a browser and cswap: the account by its number, its
    alias as the label, the sign-in in the slot's profile, all remembered."""

    def test_one_account_from_cswap_in_a_profile_then_remembered(self):
        world = World(self)
        world.expect_store(tokens.slot_secret(1))
        browser, browser_report = install_browser(world.folder)
        accounts = [tokens.CswapAccount(a["n"], a["email"], a.get("alias", ""), a.get("organizationName", "")) for a in ACCOUNTS]
        settings = Path(world.folder) / "settings" / "tokens.json"
        local = tokens.Local(browser, accounts, settings)
        prompts = []
        answers = iter(["", "2", "y", "", "n", "n"])

        def ask(prompt):
            prompts.append(prompt)
            return next(answers)

        with patch.dict(os.environ, {"FAKE_BROWSER_REPORT": browser_report}):
            _, printed, calls = world.run_in_process(self, tokens.wizard, tokens.Gh(), target(), ask=ask, local=local)
        self.assertEqual(find(calls, "variable set", tokens.slot_label(1))[0]["args"][-2:], ["--body", "bench2"])
        self.assertEqual(wait_for(browser_report), ["--profile-directory=Symphony 1", SIGN_IN_LINK])
        self.assertFalse(any("Press Enter" in prompt for prompt in prompts), "a profile needs no preparing")
        self.assertIn("opens in Chrome's profile Symphony 1", printed)
        kept = settings.read_text()
        self.assertNotIn("@", kept)
        self.assertEqual(tokens.remembered(tokens.read_settings(settings), target(), 1), {"profile": "Symphony 1", "cswap": 2})
        self.assertFalse(has_token(printed) or has_token(kept))

        # The next run offers what was remembered.
        prompts.clear()
        answers = iter(["1", "", "", "n", "", "n", "n"])
        world.stored = "2026-10-17T01:00:00Z"
        world.expect_store(tokens.slot_secret(1))
        world.run_in_process(self, tokens.wizard, tokens.Gh(), target(), ask=ask, local=local)
        self.assertIn("[2, bench2, as last time;", prompts[1])
        self.assertIn("y for cswap's bench2; Enter for none", prompts[2])
        self.assertIn("Press Enter once the browser is signed in to that account ", prompts)
        self.assertEqual(tokens.remembered(tokens.read_settings(settings), target(), 1), {"profile": None, "cswap": 2})


class TheScript(unittest.TestCase):
    """The whole command as a process, against the fake gh on PATH."""

    def test_add_from_the_command_line(self):
        world = World(self, secrets=[secret(tokens.slot_secret(1))])
        world.expect_store(tokens.slot_secret(2))
        bin_dir = install_claude(world.folder)
        report = str(Path(world.folder) / "claude-report.json")
        environ = dict(os.environ)
        environ.update(world.environment)
        environ["PATH"] = str(bin_dir) + os.pathsep + environ["PATH"]
        environ["FAKE_CLAUDE_REPORT"] = report
        # The script as a process reads the project file beside it, so it
        # runs from a tree of the test's own, whose mode line says off.
        script = Path(world.folder) / "scripts" / "tokens.py"
        script.parent.mkdir(exist_ok=True)
        shutil.copy(SCRIPT, script)
        done = subprocess.run([sys.executable, str(script), "add", "--org", ORG, "--repos", REPO, "--label", "dev"],
                              input="thecode\n", capture_output=True, text=True, env=environ, cwd=world.folder)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn(TOKEN, done.stdout + done.stderr)
        self.assertFalse(has_token(done.stdout + done.stderr))
        self.assertIn(tokens.MASK, done.stdout)
        calls = world.calls()
        store = find(calls, "secret set")[0]
        self.assertEqual(store["stdin"], TOKEN)
        self.assertEqual(store["args"][2], tokens.slot_secret(2))
        self.assertEqual(find(calls, "variable set", tokens.ACCOUNTS_VARIABLE)[0]["args"][-2:], ["--body", "1,2"])
        self.assertEqual(read_json(report)["code"], "thecode")
        # The token went to gh on standard input, once, and on no call's
        # command line.
        self.assertEqual([call["key"] for call in calls if call["stdin"] == TOKEN], ["secret set"])
        for call in calls:
            self.assertFalse(any(TOKEN in arg or has_token(arg) for arg in call["args"]), call["args"])
            self.assertFalse(call["stdin"] and call["key"] != "secret set" and has_token(call["stdin"]), call["args"])
        self.assertFalse({"--body", "-b"} & set(store["args"]))

    def test_help_and_usage_errors(self):
        done = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(done.returncode, 0)
        for word in ("status", "add", "main", "remove", "--org", "--repos", "--visibility", "--repo"):
            self.assertIn(word, done.stdout)
        self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), "--nope"], capture_output=True, cwd=ROOT).returncode, 2)
        self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), "--repo", "bad", "status"], capture_output=True, cwd=ROOT).returncode, 2)
        self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), "remove", "9"], capture_output=True, cwd=ROOT).returncode, 2)

    def test_the_token_never_goes_on_a_command_line(self):
        text = SCRIPT.read_text()
        lines = [line for line in text.splitlines() if "secret" in line and "set" in line and "args" in line]
        self.assertTrue(lines)
        for line in lines:
            self.assertNotIn("--body", line)
        # One print of a token: show's, which gives this machine's own copy
        # back to the person who asked for it.
        printing = [line for line in text.splitlines() if "print(token" in line]
        self.assertEqual(printing, ["        print(token)"])
        self.assertIn("print(token)", text.split("def show(", 1)[1].split("\ndef ", 1)[0])
        self.assertNotIn("{token}", text)

    def test_the_source_holds_no_secret_shape(self):
        for path in (SCRIPT, Path(__file__)):
            for name, pattern in check_docs.SECRET_PATTERNS:
                self.assertIsNone(pattern.search(path.read_text()), f"{path.name}: {name}")


class FakeAdvapi:
    """advapi32's four credential calls, as Windows answers them, over a
    dict: what was written, under which name, kind and persistence."""

    def __init__(self):
        self.vault = {}
        self.error = 0
        self.freed = 0
        self.kept = []
        self.refuse = False

        def write(pointer, flags):
            credential = pointer._obj
            if self.refuse:
                self.error = 5
                return 0
            blob = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            self.vault[credential.TargetName] = {"blob": blob, "user": credential.UserName, "type": credential.Type,
                                                 "persist": credential.Persist, "comment": credential.Comment}
            return 1

        def read(name, kind, flags, pointer):
            if name not in self.vault:
                self.error = tokens.ERROR_NOT_FOUND
                return 0
            blob = self.vault[name]["blob"]
            buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
            credential = self.credential_class()
            credential.CredentialBlobSize = len(blob)
            credential.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
            self.kept += [buffer, credential]
            pointer._obj.contents = credential
            return 1

        def delete(name, kind, flags):
            if self.vault.pop(name, None) is None:
                self.error = tokens.ERROR_NOT_FOUND
                return 0
            return 1

        def free(pointer):
            self.freed += 1

        # What CredReadW hands back is built with the manager's own type.
        self.credential_class = tokens.credential_type()
        self.CredWriteW, self.CredReadW, self.CredDeleteW, self.CredFree = write, read, delete, free


class MemoryCopies:
    """A vault for the tests that use one, not Credential Manager's calls."""

    def __init__(self, fail=False):
        self.kept = {}
        self.fail = fail

    def put(self, name, value, user, comment):
        if self.fail:
            raise tokens.TokensError("refused")
        self.kept[name] = value

    def get(self, name):
        return self.kept.get(name)

    def drop(self, name):
        return self.kept.pop(name, None) is not None


class TheCopy(unittest.TestCase):
    """On Windows each token stored is kept in Credential Manager too, and
    show gives it back; no copy ever reaches the screen unasked."""

    def manager(self):
        fake = FakeAdvapi()
        manager = tokens.CredentialManager(advapi=fake, last_error=lambda: fake.error)
        fake.credential_class = manager.Credential
        return fake, manager

    def test_the_structure_is_windows_own(self):
        if ctypes.sizeof(ctypes.c_void_p) != 8:
            self.skipTest("the layout checked is the 64-bit one")
        credential = tokens.credential_type()
        self.assertEqual(ctypes.sizeof(credential), 80)
        self.assertEqual((credential.TargetName.offset, credential.LastWritten.offset, credential.CredentialBlob.offset,
                          credential.Persist.offset, credential.UserName.offset), (8, 24, 40, 48, 72))

    def test_put_get_and_drop(self):
        fake, manager = self.manager()
        manager.put("symphony/org:octo/X", TOKEN, "X", "a comment")
        kept = fake.vault["symphony/org:octo/X"]
        self.assertEqual(kept["blob"], TOKEN.encode("utf-16-le"))
        self.assertEqual((kept["type"], kept["persist"], kept["user"]), (1, 2, "X"))
        self.assertEqual(manager.get("symphony/org:octo/X"), TOKEN)
        self.assertEqual(fake.freed, 1)
        self.assertIsNone(manager.get("symphony/org:octo/Y"))
        self.assertTrue(manager.drop("symphony/org:octo/X"))
        self.assertFalse(manager.drop("symphony/org:octo/X"))
        fake.refuse = True
        with self.assertRaises(tokens.TokensError) as caught:
            manager.put("n", TOKEN, "n", "c")
        self.assertNotIn(TOKEN, str(caught.exception))

    def test_add_keeps_a_copy_under_the_place_and_the_name(self):
        world = World(self, secrets=[secret(tokens.slot_secret(1))])
        world.expect_store(tokens.slot_secret(2), tokens.MAIN_SECRET)
        copies = MemoryCopies()
        _, printed, _ = world.run_in_process(self, tokens.add, tokens.Gh(), target(), 2, "", True, False, copies=copies)
        self.assertEqual(copies.kept, {f"symphony/org:{ORG}/{tokens.slot_secret(2)}": TOKEN,
                                       f"symphony/org:{ORG}/{tokens.MAIN_SECRET}": TOKEN})
        self.assertIn("a copy kept in Windows Credential Manager", printed)
        self.assertFalse(has_token(printed))

    def test_no_copy_and_a_refused_copy_still_store(self):
        for copies in (False, MemoryCopies(fail=True)):
            world = World(self)
            world.expect_store(tokens.slot_secret(1))
            _, printed, calls = world.run_in_process(self, tokens.add, tokens.Gh(), target(), 1, "", False, False, copies=copies)
            self.assertEqual(len(find(calls, "secret set")), 1)
            self.assertIn("GitHub lists it", printed)
            self.assertEqual("no copy kept" in printed, copies is not False)

    def test_show_gives_the_copy_back(self):
        copies = MemoryCopies()
        copies.put(tokens.copy_name(target(), tokens.slot_secret(3)), TOKEN, "", "")
        with redirect_stdout(io.StringIO()) as printed:
            tokens.show(target(), "3", copies=copies)
        self.assertEqual(printed.getvalue(), TOKEN + "\n")
        clipped = []
        with patch.object(tokens.subprocess, "run", lambda command, **options: clipped.append((command, options["input"]))
                          or subprocess.CompletedProcess(command, 0)), redirect_stdout(io.StringIO()) as printed:
            tokens.show(target(), "3", copies=copies, clipboard=True)
        self.assertEqual(clipped, [(["clip"], TOKEN)])
        self.assertFalse(has_token(printed.getvalue()))
        for which in ("4", "main"):
            with self.assertRaises(tokens.TokensError) as caught:
                tokens.show(target(), which, copies=copies)
            self.assertIn("no copy", str(caught.exception))
        for which in ("9", "03", "x"):
            with self.assertRaises(tokens.UsageError):
                tokens.show(target(), which, copies=copies)
        with patch.object(tokens, "local_copies", lambda: None), self.assertRaises(tokens.TokensError) as caught:
            tokens.show(target(), "3")
        self.assertIn("not Windows", str(caught.exception))

    def test_remove_drops_the_copy_and_profiles_names_it(self):
        world = World(self, secrets=[secret(tokens.slot_secret(1)), secret(tokens.slot_secret(2))])
        copies = MemoryCopies()
        for name in (tokens.slot_secret(2), tokens.MAIN_SECRET):
            copies.put(tokens.copy_name(target(), name), TOKEN, "", "")
        settings = Path(world.folder) / "settings.json"
        with redirect_stdout(io.StringIO()) as printed:
            tokens.print_remembered(target(), settings, copies=copies)
        self.assertIn("slot 2: the default browser, a copy of its token (show 2)", printed.getvalue())
        self.assertIn("(show main)", printed.getvalue())
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        with patch.object(tokens.subprocess, "run", run), patch.object(tokens, "settings_path", lambda: settings), \
                redirect_stdout(io.StringIO()) as printed:
            tokens.remove(tokens.Gh(), target(), 2, copies=copies)
        self.assertEqual(list(copies.kept), [tokens.copy_name(target(), tokens.MAIN_SECRET)])
        self.assertIn("its copy on this machine deleted", printed.getvalue())

    def test_a_copy_that_is_not_utf16_is_refused_and_the_comment_is_short(self):
        fake, manager = self.manager()
        fake.vault["odd"] = {"blob": b"abc"}
        with self.assertRaises(tokens.TokensError):
            manager.get("odd")
        self.assertFalse(tokens.has_copy(manager, target(), "odd"))
        many = tokens.Target("org", ORG, [f"repository-{n}" for n in range(30)])
        with redirect_stdout(io.StringIO()):
            tokens.keep_copy(manager, many, tokens.slot_secret(1), TOKEN)
        # Credential Manager refuses a comment over 256 characters.
        self.assertLessEqual(len(fake.vault[tokens.copy_name(many, tokens.slot_secret(1))]["comment"]), 256)

    def test_show_asks_nothing_of_github(self):
        copies = MemoryCopies()
        copies.put(f"symphony/org:{ORG}/{tokens.slot_secret(2)}", TOKEN, "", "")
        def no_gh(*args, **options):
            raise AssertionError("show ran gh")
        with patch.object(tokens, "local_copies", lambda: copies), patch.object(tokens.subprocess, "run", no_gh), \
                redirect_stdout(io.StringIO()) as printed:
            self.assertEqual(tokens.main(["show", "2", "--org", ORG]), 0)
        self.assertEqual(printed.getvalue(), TOKEN + "\n")
        with patch.object(tokens, "local_copies", lambda: copies), redirect_stdout(io.StringIO()), \
                patch("sys.stderr", io.StringIO()):
            self.assertEqual(tokens.main(["show", "9", "--org", ORG]), 2)

    def test_elsewhere_no_copy_is_kept(self):
        with patch.object(tokens.sys, "platform", "linux"):
            self.assertIsNone(tokens.local_copies())
        self.assertIsNone(tokens.machine_copies(False))


class Sharing(unittest.TestCase):
    """share: the slots, their labels and the list seen by a benchmark's
    repository too, with no sign-in, each added to the list it has."""

    def test_share_adds_the_repository_to_each_selected_name(self):
        world = World(self, secrets=[secret(tokens.slot_secret(1)), secret(tokens.slot_secret(2), visibility="all"),
                                     secret(tokens.MAIN_SECRET)],
                      variables=[variable(tokens.slot_label(1), "runners"), variable(tokens.ACCOUNTS_VARIABLE, "1,2")])
        routes = read_json(world.routes_file)
        routes[f"GET repos/{ORG}/other"] = [answer(200, "4242\n")]
        for kind, name in (("secrets", tokens.slot_secret(1)), ("variables", tokens.slot_label(1)),
                           ("variables", tokens.ACCOUNTS_VARIABLE)):
            routes[f"PUT orgs/{ORG}/actions/{kind}/{name}/repositories/4242"] = [answer(204, "")]
        fake_gh.write_routes(world.routes_file, routes)
        run = fake_gh.routed_run(subprocess.run, world.log, world.routes_file)
        with patch.object(tokens.subprocess, "run", run), patch.object(tokens, "PROJECT", world.project), \
                redirect_stdout(io.StringIO()) as printed:
            tokens.share(tokens.Gh(), target(), ["other"])
        puts = [call["key"] for call in world.calls() if call["key"].startswith("PUT")]
        self.assertEqual(puts, [f"PUT orgs/{ORG}/actions/secrets/{tokens.slot_secret(1)}/repositories/4242",
                                f"PUT orgs/{ORG}/actions/variables/{tokens.slot_label(1)}/repositories/4242",
                                f"PUT orgs/{ORG}/actions/variables/{tokens.ACCOUNTS_VARIABLE}/repositories/4242"])
        self.assertIn(f"{tokens.slot_secret(2)}: seen by every repository already", printed.getvalue())

    def test_share_is_for_an_organization(self):
        with self.assertRaises(tokens.TokensError):
            tokens.share(None, tokens.Target("repo", ORG, name=REPO), ["other"])

    def test_the_commands_parse(self):
        args = tokens.build_parser().parse_args(["show", "main", "--copy"])
        self.assertEqual((args.command, args.which, args.copy), ("show", "main", True))
        args = tokens.build_parser().parse_args(["share", "coordbench,flowbench"])
        self.assertEqual(tokens.parse_repos(args.repos), ["coordbench", "flowbench"])
        self.assertTrue(tokens.build_parser().parse_args(["add", "--no-copy"]).no_copy)


if __name__ == "__main__":
    unittest.main()
