"""tools/token_run.py mints one token on an Actions runner for the
Tokens page: the sign-in link out on the issue, the person's code in, the
token out only sealed. claude here is a stand-in script that prints the
link as claude setup-token does, an OSC 8 hyperlink, waits for the code
and prints a token of the subscription token's shape, built from pieces
so this file never looks like a secret; GitHub is a list of comments."""

import base64
import io
import json
import os
import stat
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))

import sealbox  # noqa: E402
import token_run  # noqa: E402
import tokens  # noqa: E402

SECRET = bytes(range(32))
TOKEN = tokens.TOKEN_HEAD + "01-" + "Ab3_" * 24
LINK = "https://claude.com/cai/oauth/authorize?code=true&client_id=x&response_type=code&state=abc123"
CODE = "a1b2c3d4e5#state-f6"
STAND_IN = f'''#!/usr/bin/env python3
import sys
link = {LINK!r}
sys.stdout.write("Browser didn't open? \\x1b]8;id=1;" + link + "\\x07" + link + "\\x1b]8;;\\x07\\r\\n")
sys.stdout.write("Paste code here if prompted > ")
sys.stdout.flush()
code = sys.stdin.readline().strip()
if code != {CODE!r}:
    print("Invalid code")
    sys.exit(1)
print("Your OAuth token (valid for 1 year):")
print({TOKEN!r})
'''

# claude's screen reads keys raw and takes a chunk holding more than one key
# as a paste, so an Enter that arrives with the code is part of the paste
# and sends nothing; only an Enter of its own sends the code.
SCREEN_STAND_IN = f'''#!/usr/bin/env python3
import os, sys, time, tty
link = {LINK!r}
sys.stdout.write("Browser didn't open? " + link + "\\r\\n")
sys.stdout.flush()
# The question comes a moment after the link, in raw mode, which throws
# away any key typed before it: the run has to wait for the question.
time.sleep(1)
tty.setraw(0)
sys.stdout.write("Paste code here if prompted > ")
sys.stdout.flush()
typed = ""
while True:
    chunk = os.read(0, 4096).decode()
    if chunk == "\\r":
        break
    typed += chunk
if typed != {CODE!r}:
    print("Invalid code")
    sys.exit(1)
sys.stdout.write("Your OAuth token (valid for 1 year):\\r\\n" + {TOKEN!r} + "\\r\\n")
'''


class FakeGitHub(token_run.GitHub):
    def __init__(self, actor_code=None, poster="greg"):
        super().__init__("o/r", "t", "7")
        self.posted, self.deleted, self.closed = [], [], []
        self.waiting = [{"id": 99, "user": {"login": poster}, "body": f"{token_run.CODE_MARK}\n{actor_code}"}] if actor_code else []

    def comment(self, body):
        self.posted.append(body)

    def comments(self):
        # The code arrives only once the link is out, as the page posts it.
        return list(self.waiting) if self.posted else []

    def delete_comment(self, comment_id):
        self.deleted.append(comment_id)

    def close(self, done):
        self.closed.append(done)


class TokenRunTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.use_stand_in(STAND_IN)
        self.environ = {"ISSUE": "7", "KEY": base64.b64encode(sealbox.public_key(SECRET)).decode(), "KEY_ID": "k1",
                        "ACTOR": "Greg", "GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t"}
        token_run.WAIT_FOR_CODE = 5
        token_run.POLL_EVERY = 0.2

    def use_stand_in(self, script):
        self.claude = Path(self.folder) / "claude"
        self.claude.write_text(script)
        self.claude.chmod(self.claude.stat().st_mode | stat.S_IEXEC)

    def run_with(self, github):
        original = token_run.settings
        token_run.settings = lambda environ, **how: (github, *original(environ, **how)[1:])
        try:
            token_run.run(self.environ, start=lambda: token_run.Claude(command=(str(self.claude),)))
        finally:
            token_run.settings = original

    def test_the_token_leaves_only_sealed_for_the_pages_key(self):
        github = FakeGitHub(CODE)
        self.run_with(github)
        self.assertEqual(github.posted[0], f"{token_run.LINK_MARK}\n{LINK}")
        mark, key_id, sealed = github.posted[1].split("\n")
        self.assertEqual((mark, key_id), (token_run.SEALED_MARK, "k1"))
        self.assertEqual(sealbox.open_sealed(base64.b64decode(sealed), SECRET).decode(), TOKEN)
        self.assertNotIn(TOKEN, "".join(github.posted))
        self.assertEqual(github.deleted, [99])

    def test_the_enter_that_sends_the_code_is_a_key_of_its_own(self):
        self.use_stand_in(SCREEN_STAND_IN)
        github = FakeGitHub(CODE)
        self.run_with(github)
        mark, _, sealed = github.posted[1].split("\n")
        self.assertEqual(mark, token_run.SEALED_MARK)
        self.assertEqual(sealbox.open_sealed(base64.b64decode(sealed), SECRET).decode(), TOKEN)

    def test_claude_gets_a_terminal_type_where_the_runner_sets_none(self):
        self.use_stand_in("#!/bin/sh\necho \"term=$TERM\"\n")
        saved = os.environ.pop("TERM", None)
        try:
            claude = token_run.Claude(command=(str(self.claude),))
            while not claude.ended:
                claude.read(1)
            claude.finish()
        finally:
            if saved is not None:
                os.environ["TERM"] = saved
        self.assertIn("term=" + token_run.TERMINAL_TYPE, claude.seen)

    def test_a_code_from_anyone_else_is_never_typed(self):
        github = FakeGitHub(CODE, poster="someone-else")
        with self.assertRaisesRegex(token_run.RunError, "no code came"):
            self.run_with(github)
        self.assertEqual(len(github.posted), 1)

    def test_a_wrong_code_seals_nothing(self):
        github = FakeGitHub("wrong-code-1")
        with self.assertRaisesRegex(token_run.RunError, "claude said: .*Invalid code"):
            self.run_with(github)
        self.assertEqual(len(github.posted), 1)

    def test_settings_refuse_what_the_page_would_not_send(self):
        for name, value in (("ISSUE", "07"), ("KEY_ID", "a b"), ("KEY", "short")):
            with self.assertRaises((token_run.RunError, sealbox.SealError)):
                token_run.settings({**self.environ, name: value})


class FakeOrg:
    """The organization's Actions secrets and variables as GitHub's API
    answers them, for the run's own store into the pool."""

    def __init__(self, secrets=(), variables=None, refuse=""):
        self.secrets = {name: None for name in secrets}
        self.variables = dict(variables or {})
        self.reached = {}
        self.lent = {}
        self.users = {}
        self.refuse = refuse
        self.calls = []

    def call(self, method, path, body=None):
        self.calls.append((method, path))
        if self.refuse and self.refuse in path and method != "GET":
            raise urllib.error.HTTPError(path, 403, "Forbidden", {}, io.BytesIO())
        base = "/orgs/acme/actions"
        if path.startswith("/users/"):
            return {"id": self.users.get(path.rsplit("/", 1)[1].lower(), 100)}
        if path.startswith("/repositories/"):
            # the organization's repositories by id, and one of another organization's
            if path.endswith("/permission"):
                # ashley writes to 77 and reads 78 alone
                number, actor = int(path.split("/")[2]), path.split("/")[4]
                return {"permission": "write" if (number, actor) == (77, "ashley") else "read", "role_name": "write" if (number, actor) == (77, "ashley") else "read"}
            number = int(path.rsplit("/", 1)[1])
            if number in (5, 11, 12, 42, 77, 78):
                return {"id": number, "owner": {"login": "Acme"}}
            if number == 99:
                return {"id": 99, "owner": {"login": "other"}}
            raise urllib.error.HTTPError(path, 404, "Not Found", {}, io.BytesIO())
        if path.startswith(base + "/secrets?"):
            return {"secrets": [{"name": n} for n in sorted(self.secrets)]}
        if path == base + "/secrets/public-key":
            return {"key": base64.b64encode(sealbox.public_key(SECRET)).decode(), "key_id": "org-key"}
        if "/secrets/" in path and "/repositories" in path:
            name = path.split("/secrets/")[1].split("/")[0]
            lent = self.lent.setdefault(name, [])
            if method == "GET":
                return {"repositories": [{"id": i} for i in lent]}
            repo = int(path.rsplit("/", 1)[1])
            if method == "PUT" and repo not in lent:
                lent.append(repo)
            if method == "DELETE" and repo in lent:
                lent.remove(repo)
            return None
        if path.startswith(base + "/secrets/") and method == "DELETE":
            self.secrets.pop(path.rsplit("/", 1)[1], None)
            return None
        if path.startswith(base + "/secrets/") and method == "PUT":
            self.secrets[path.rsplit("/", 1)[1]] = body
            self.lent[path.rsplit("/", 1)[1]] = list(body["selected_repository_ids"])
            return None
        if path.startswith(base + "/secrets/") and method == "GET":
            if path.rsplit("/", 1)[1] not in self.secrets:
                raise urllib.error.HTTPError(path, 404, "Not Found", {}, io.BytesIO())
            return {"name": path.rsplit("/", 1)[1], "visibility": "selected"}
        if path == base + "/variables" and method == "POST":
            self.variables[body["name"]] = body["value"]
            self.reached[body["name"]] = body["selected_repository_ids"]
            return None
        if "/repositories/" in path and method == "PUT":
            name = path.split("/variables/")[1].split("/")[0]
            if int(path.rsplit("/", 1)[1]) not in self.reached.setdefault(name, []):
                self.reached[name].append(int(path.rsplit("/", 1)[1]))
            return None
        if "/repositories/" in path and method == "DELETE":
            name = path.split("/variables/")[1].split("/")[0]
            if int(path.rsplit("/", 1)[1]) in self.reached.get(name, []):
                self.reached[name].remove(int(path.rsplit("/", 1)[1]))
            return None
        if path.startswith(base + "/variables/"):
            name = path.rsplit("/", 1)[1]
            if method == "PATCH":
                self.variables[name] = body["value"]
                return None
            if name not in self.variables:
                raise urllib.error.HTTPError(path, 404, "Not Found", {}, io.BytesIO())
            return {"name": name, "value": self.variables[name], "visibility": "selected"}
        raise AssertionError(f"unexpected call {method} {path}")


class MissingPermissionTest(unittest.TestCase):
    """GitHub answers 404 on an organization's variables when the App's
    installation lacks Variables, naming the permission in a header."""

    def refusing(self, headers):
        org = FakeOrg()

        def call(method, path, body=None):
            if "/variables" in path:
                raise urllib.error.HTTPError(path, 404, "Not Found", headers, io.BytesIO())
            return org.call(method, path, body)
        return token_run.Pool("acme", "app", 42, call=call)

    def test_a_missing_variables_permission_says_where_to_accept_it(self):
        pool = self.refusing({"X-Accepted-GitHub-Permissions": "organization_actions_variables=write"})
        with self.assertRaises(token_run.RunError) as said:
            pool.store("sk-ant-oat01-x", "ashley")
        text = str(said.exception)
        self.assertIn("GitHub answered 404 when the run tried to mark slot 1 as yours", text)
        self.assertIn("organization variables write", text)
        self.assertIn("https://github.com/organizations/acme/settings/installations", text)

    def test_a_refusal_with_no_permission_named_says_only_what_failed(self):
        pool = self.refusing({})
        with self.assertRaises(token_run.RunError) as said:
            pool.store("sk-ant-oat01-x", "ashley")
        self.assertEqual(str(said.exception),
                         "GitHub answered 404 when the run tried to mark slot 1 as yours in SYMPHONY_CLAUDE_SETTINGS in acme's pool")


class PoolStoreTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        claude = Path(self.folder) / "claude"
        claude.write_text(STAND_IN)
        claude.chmod(claude.stat().st_mode | stat.S_IEXEC)
        self.command = (str(claude),)
        self.environ = {"ISSUE": "7", "ACTOR": "ashley", "GITHUB_REPOSITORY": "acme/r", "GITHUB_TOKEN": "t",
                        "STORE_ORG": "acme", "APP_TOKEN": "app", "REPO_ID": "42",
                        "TOKEN_FILE": os.path.join(self.folder, "held")}
        token_run.WAIT_FOR_CODE = 5
        token_run.POLL_EVERY = 0.2

    def store(self, org, poster="ashley"):
        github = FakeGitHub(CODE, poster=poster)
        original = token_run.settings
        token_run.settings = lambda environ, **how: (github, *original(environ, **how)[1:])
        try:
            token_run.run(self.environ, start=lambda: token_run.Claude(command=self.command))
            self.assertEqual(oct(os.stat(self.environ["TOKEN_FILE"]).st_mode & 0o777), "0o600")
            token_run.store(self.environ, pool=token_run.Pool("acme", "app", 42, call=org.call))
        finally:
            token_run.settings = original
        return github

    def test_the_token_goes_into_the_first_free_slot_marked_as_the_persons(self):
        org = FakeOrg(secrets=["SYMPHONY_CLAUDE_1", "SYMPHONY_CLAUDE_2"],
                      variables={"SYMPHONY_CLAUDE_ACCOUNTS": "1,2",
                                 "SYMPHONY_CLAUDE_SETTINGS": json.dumps({"1": {"model": "claude-opus-5-5"}})})
        github = self.store(org)
        self.assertEqual(github.posted[1], f"{token_run.STORED_MARK}\n3")
        put = org.secrets["SYMPHONY_CLAUDE_3"]
        self.assertEqual((put["key_id"], put["visibility"], put["selected_repository_ids"]), ("org-key", "selected", [42]))
        self.assertEqual(sealbox.open_sealed(base64.b64decode(put["encrypted_value"]), SECRET).decode(), TOKEN)
        self.assertEqual(org.variables["SYMPHONY_CLAUDE_ACCOUNTS"], "1,2,3")
        settings = json.loads(org.variables["SYMPHONY_CLAUDE_SETTINGS"])
        self.assertEqual(settings["1"], {"model": "claude-opus-5-5"})
        self.assertEqual(settings["3"]["owner"], "ashley")
        self.assertRegex(settings["3"]["id"], r"^[0-9a-f]{8}$")
        self.assertEqual(settings["3"]["uid"], 100)
        self.assertNotIn(TOKEN, "".join(github.posted))
        self.assertFalse(os.path.exists(self.environ["TOKEN_FILE"]))

    def test_a_slot_taken_while_the_run_looked_is_never_written_over(self):
        org = FakeOrg()
        listed = org.call

        def another_run_takes_slot_1(method, path, body=None):
            got = listed(method, path, body)
            if path.startswith("/orgs/acme/actions/secrets?"):
                org.secrets["SYMPHONY_CLAUDE_1"] = "theirs"
            return got
        org.call = another_run_takes_slot_1
        with self.assertRaisesRegex(token_run.RunError, "slot 1 was taken"):
            self.store(org)
        self.assertEqual(org.secrets["SYMPHONY_CLAUDE_1"], "theirs")
        self.assertFalse(os.path.exists(self.environ["TOKEN_FILE"]))

    def test_no_slot_that_holds_a_token_is_ever_written(self):
        org = FakeOrg(secrets=[f"SYMPHONY_CLAUDE_{n}" for n in range(1, 33)])
        with self.assertRaisesRegex(token_run.RunError, "all 32 slots"):
            self.store(org)
        self.assertFalse([c for c in org.calls if c[0] != "GET"])

    def test_variables_made_new_reach_the_repository(self):
        org = FakeOrg()
        self.store(org)
        self.assertEqual(org.variables["SYMPHONY_CLAUDE_ACCOUNTS"], "1")
        self.assertEqual(org.reached["SYMPHONY_CLAUDE_SETTINGS"], [42])

    def test_settings_that_are_not_json_by_slot_are_left_for_an_owner(self):
        org = FakeOrg(variables={"SYMPHONY_CLAUDE_SETTINGS": "[1, 2]"})
        with self.assertRaisesRegex(token_run.RunError, "slot 1.*not JSON by slot"):
            self.store(org)
        self.assertEqual(org.variables["SYMPHONY_CLAUDE_SETTINGS"], "[1, 2]")

    def test_a_refusal_from_github_is_said_in_words_the_page_shows(self):
        org = FakeOrg(refuse="/secrets/SYMPHONY_CLAUDE_")
        with self.assertRaisesRegex(token_run.RunError, "403 when the run tried to store the token in slot 1"):
            self.store(org)

    def test_store_mode_needs_its_organization_token_and_repository(self):
        for name, value in (("STORE_ORG", "-bad"), ("APP_TOKEN", ""), ("REPO_ID", "042")):
            with self.assertRaises(token_run.RunError):
                token_run.pool_of({**self.environ, name: value})

    def test_a_run_that_stopped_early_tells_the_page_once(self):
        github = FakeGitHub()
        github.comments = lambda: [{"user": {"login": "github-actions[bot]"}, "body": c} for c in github.posted]
        original = token_run.settings
        token_run.settings = lambda environ, **how: (github, *original(environ, **how)[1:])
        try:
            token_run.fail({**self.environ, "FAIL_WHY": "crowd mode"})
            token_run.fail(self.environ)
        finally:
            token_run.settings = original
        self.assertEqual(github.posted, [f"{token_run.FAILED_MARK}\ncrowd mode"])

    def test_an_unforeseen_failure_reaches_the_page_by_its_kind_alone(self):
        github = FakeGitHub()
        original_settings, original_store = token_run.settings, token_run.STAGES["store"]
        token_run.settings = lambda environ, **how: (github, None, "", "ashley")

        def broken(environ):
            raise KeyError("sk-" + "x" * 10)
        token_run.STAGES["store"] = broken
        try:
            self.assertEqual(token_run.main(["store"]), 1)
        finally:
            token_run.settings, token_run.STAGES["store"] = original_settings, original_store
        self.assertEqual(len(github.posted), 1)
        self.assertIn("(KeyError)", github.posted[0])
        self.assertNotIn("sk-", github.posted[0])

    def test_claude_never_sees_the_runs_tokens(self):
        script = Path(self.folder) / "env"
        script.write_text("#!/bin/sh\necho \"gh=${GITHUB_TOKEN:-none} app=${APP_TOKEN:-none}\"\n")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        saved = {k: os.environ.get(k) for k in token_run.WITHHELD}
        os.environ.update({k: "visible" for k in token_run.WITHHELD})
        try:
            claude = token_run.Claude(command=(str(script),))
            while not claude.ended:
                claude.read(1)
            claude.finish()
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.assertIn("gh=none app=none", claude.seen)


class KeeperTest(unittest.TestCase):
    """One token per person, lent to the repositories they choose."""

    def setUp(self):
        self.org = FakeOrg(secrets=["SYMPHONY_CLAUDE_1", "SYMPHONY_CLAUDE_2"],
                           variables={"SYMPHONY_CLAUDE_ACCOUNTS": "1,2",
                                      "SYMPHONY_CLAUDE_SETTINGS": json.dumps({"1": {"owner": "greg"}, "2": {"owner": "Ashley"}})})
        self.org.lent = {"SYMPHONY_CLAUDE_1": [1], "SYMPHONY_CLAUDE_2": [5]}
        self.keeper = token_run.Keeper("acme", "app", 42, call=self.org.call)
        self.github = FakeGitHub()
        self.folder = tempfile.mkdtemp()
        self.environ = {"ISSUE": "7", "ACTOR": "ashley", "GITHUB_REPOSITORY": "acme/r", "GITHUB_TOKEN": "t",
                        "STORE_ORG": "acme", "APP_TOKEN": "app", "REPO_ID": "42",
                        "GITHUB_OUTPUT": os.path.join(self.folder, "out")}
        self.original = token_run.settings
        token_run.settings = lambda environ, **how: (self.github, *self.original(environ, **how)[1:])

    def tearDown(self):
        token_run.settings = self.original

    def test_a_person_with_a_token_has_it_lent_here_and_makes_no_other(self):
        revoked = []
        slot = token_run.look(self.environ, keeper=self.keeper, call=lambda *a: revoked.append(a))
        self.assertEqual(slot, "2")
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_2"], [5, 42])
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_1"], [1])
        self.assertEqual(self.github.posted, [f"{token_run.LENT_MARK}\n2\n5,42"])
        self.assertEqual(revoked, [("DELETE", "/installation/token")])
        self.assertIn("found=true", Path(self.environ["GITHUB_OUTPUT"]).read_text())

    def test_a_person_with_none_goes_on_to_the_sign_in(self):
        slot = token_run.look({**self.environ, "ACTOR": "newcomer"}, keeper=self.keeper, call=lambda *a: None)
        self.assertEqual(slot, "")
        self.assertEqual(self.github.posted, [])
        self.assertIn("found=false", Path(self.environ["GITHUB_OUTPUT"]).read_text())

    def test_a_token_is_taken_back_from_one_repository(self):
        self.org.lent["SYMPHONY_CLAUDE_2"] = [5, 42]
        token_run.manage({**self.environ, "MANAGE": "revoke", "TARGET_REPO_ID": "5"}, keeper=self.keeper)
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_2"], [42])
        self.assertEqual(self.github.posted, [f"{token_run.LENT_MARK}\n2\n42"])

    def test_deleting_takes_the_token_and_its_place_away(self):
        token_run.manage({**self.environ, "MANAGE": "delete"}, keeper=self.keeper)
        self.assertNotIn("SYMPHONY_CLAUDE_2", self.org.secrets)
        self.assertIn("SYMPHONY_CLAUDE_1", self.org.secrets)
        self.assertEqual(self.org.variables["SYMPHONY_CLAUDE_ACCOUNTS"], "1")
        self.assertEqual(json.loads(self.org.variables["SYMPHONY_CLAUDE_SETTINGS"]), {"1": {"owner": "greg"}})
        # the secret went before the mark, so a run cut short leaves no token nobody owns
        gone = self.org.calls.index(("DELETE", "/orgs/acme/actions/secrets/SYMPHONY_CLAUDE_2"))
        unmarked = max(i for i, c in enumerate(self.org.calls) if c == ("PATCH", "/orgs/acme/actions/variables/SYMPHONY_CLAUDE_SETTINGS"))
        self.assertLess(gone, unmarked)

    def test_a_repository_no_slot_reaches_loses_the_two_variables(self):
        # the variables reach every repository a slot was lent to; 1 is slot 1's too, so it keeps them
        self.org.reached = {"SYMPHONY_CLAUDE_ACCOUNTS": [1, 5, 42], "SYMPHONY_CLAUDE_SETTINGS": [1, 5, 42]}
        self.org.lent["SYMPHONY_CLAUDE_2"] = [1, 5, 42]
        token_run.manage({**self.environ, "MANAGE": "revoke", "TARGET_REPO_ID": "5"}, keeper=self.keeper)
        self.assertEqual(self.org.reached["SYMPHONY_CLAUDE_ACCOUNTS"], [1, 42])
        self.assertEqual(self.org.reached["SYMPHONY_CLAUDE_SETTINGS"], [1, 42])
        token_run.manage({**self.environ, "MANAGE": "revoke", "TARGET_REPO_ID": "1"}, keeper=self.keeper)
        self.assertEqual(self.org.reached["SYMPHONY_CLAUDE_ACCOUNTS"], [1, 42])
        token_run.manage({**self.environ, "MANAGE": "delete"}, keeper=self.keeper)
        # 42 was slot 2's alone, so it loses them too; 1 stays slot 1's
        self.assertEqual(self.org.reached["SYMPHONY_CLAUDE_ACCOUNTS"], [1])
        self.assertEqual(self.org.reached["SYMPHONY_CLAUDE_SETTINGS"], [1])

    def test_a_delete_from_a_repository_the_token_never_reached_adds_it_nowhere(self):
        self.org.reached = {"SYMPHONY_CLAUDE_ACCOUNTS": [1, 5], "SYMPHONY_CLAUDE_SETTINGS": [1, 5]}
        # the run is in 42, which slot 2 (lent to 5) never reached
        token_run.manage({**self.environ, "MANAGE": "delete"}, keeper=self.keeper)
        self.assertEqual(self.org.reached["SYMPHONY_CLAUDE_ACCOUNTS"], [1])
        self.assertEqual(self.org.reached["SYMPHONY_CLAUDE_SETTINGS"], [1])

    def test_a_mark_a_store_wrote_into_a_freed_slot_made_before_ids_stays(self):
        self.test_a_mark_a_store_wrote_into_the_freed_slot_stays(old={"owner": "Ashley"})

    def test_a_mark_a_store_wrote_into_the_freed_slot_stays(self, old=None):
        settings = {"1": {"owner": "greg"}, "2": old or {"owner": "Ashley", "id": "aaaa"}}
        self.org.variables["SYMPHONY_CLAUDE_SETTINGS"] = json.dumps(settings)
        original = self.org.call
        def call(method, path, body=None):
            answer = original(method, path, body)
            # another run's store takes slot 2 the moment its secret is gone
            if method == "DELETE" and path.endswith("/secrets/SYMPHONY_CLAUDE_2"):
                self.org.variables["SYMPHONY_CLAUDE_SETTINGS"] = json.dumps({**settings, "2": {"owner": "newcomer", "id": "bbbb"}})
                self.org.secrets["SYMPHONY_CLAUDE_2"] = {}
            return answer
        self.keeper.api = call
        self.keeper.delete("2")
        self.assertEqual(json.loads(self.org.variables["SYMPHONY_CLAUDE_SETTINGS"])["2"]["owner"], "newcomer")
        self.assertEqual(self.org.variables["SYMPHONY_CLAUDE_ACCOUNTS"], "1,2")

    def test_nobody_reaches_a_token_that_is_not_their_own(self):
        with self.assertRaisesRegex(token_run.RunError, "no token in acme"):
            token_run.manage({**self.environ, "ACTOR": "mallory", "MANAGE": "delete"}, keeper=self.keeper)
        self.assertEqual(sorted(self.org.secrets), ["SYMPHONY_CLAUDE_1", "SYMPHONY_CLAUDE_2"])

    def test_a_login_that_passed_to_another_account_owns_nothing(self):
        self.org.variables["SYMPHONY_CLAUDE_SETTINGS"] = json.dumps({"2": {"owner": "ashley", "uid": 7}})
        self.org.users["ashley"] = 8
        with self.assertRaisesRegex(token_run.RunError, "no token in acme"):
            token_run.manage({**self.environ, "MANAGE": "delete"}, keeper=self.keeper)
        self.org.users["ashley"] = 7
        token_run.manage({**self.environ, "MANAGE": "list"}, keeper=self.keeper)
        self.assertEqual(self.github.posted, [f"{token_run.LENT_MARK}\n2\n5"])

    def test_the_look_stops_when_the_apps_token_cannot_be_given_up(self):
        def refuse(*_):
            raise OSError("no answer")
        with self.assertRaisesRegex(token_run.RunError, "could not give up the App's token"):
            token_run.look(self.environ, keeper=self.keeper, call=refuse)
        self.assertFalse(Path(self.environ["GITHUB_OUTPUT"]).exists())

    def test_a_second_sign_in_at_the_same_time_makes_no_second_token(self):
        with self.assertRaisesRegex(token_run.RunError, "made a token in another run"):
            self.keeper.store("x", "ashley")
        self.assertEqual(sorted(self.org.secrets), ["SYMPHONY_CLAUDE_1", "SYMPHONY_CLAUDE_2"])

    def test_only_list_revoke_and_delete_are_taken(self):
        with self.assertRaisesRegex(token_run.RunError, "lists, revokes or deletes"):
            token_run.manage({**self.environ, "MANAGE": "lend-all"}, keeper=self.keeper)
        with self.assertRaisesRegex(token_run.RunError, "take the token back from"):
            token_run.manage({**self.environ, "MANAGE": "revoke", "TARGET_REPO_ID": "x"}, keeper=self.keeper)


class IssueRunTest(unittest.TestCase):
    """A run GitHub started on an issue anyone may open: the author is the
    actor, the issue's first lines are the request, and the run closes it."""

    def setUp(self):
        self.org = FakeOrg(secrets=["SYMPHONY_CLAUDE_2"],
                           variables={"SYMPHONY_CLAUDE_ACCOUNTS": "2",
                                      "SYMPHONY_CLAUDE_SETTINGS": json.dumps({"2": {"owner": "ashley", "uid": 7}}),
                                      "SYMPHONY_LEND_TO": "11, 12"})
        self.org.lent = {"SYMPHONY_CLAUDE_2": [5]}
        self.org.users["ashley"] = 7
        self.github = FakeGitHub()
        self.folder = tempfile.mkdtemp()
        self.environ = {"ISSUE": "7", "ACTOR": "ashley", "GITHUB_REPOSITORY": "acme/r", "GITHUB_TOKEN": "t",
                        "STORE_ORG": "acme", "APP_TOKEN": "app", "REPO_ID": "42",
                        "GITHUB_EVENT_NAME": "issues", "GITHUB_OUTPUT": os.path.join(self.folder, "out")}
        self.original = token_run.settings
        token_run.settings = lambda environ, **how: (self.github, *self.original(environ, **how)[1:])
        self.original_keeper_of = token_run.keeper_of
        org = self.org
        # the keeper the run builds itself talks to the fake organization
        def keeper_of(environ):
            keeper = token_run.Keeper("acme", "app", 42, call=org.call)
            if token_run.no_say(environ):
                keeper.targets = token_run.standing_list(keeper)
                keeper.keeping = token_run.ORGANIZATION
            target = token_run.lend_target(environ, keeper, environ.get("ACTOR", ""))
            if target is not None:
                keeper.targets = [target]
            return keeper
        token_run.keeper_of = keeper_of

    def tearDown(self):
        token_run.settings = self.original
        token_run.keeper_of = self.original_keeper_of

    def opened(self, body):
        path = os.path.join(self.folder, "event.json")
        Path(path).write_text(json.dumps({"issue": {"number": 7, "body": body}}))
        return {**self.environ, "GITHUB_EVENT_PATH": path}

    def test_the_issues_first_lines_are_the_request(self):
        self.assertEqual(token_run.request(self.opened(f"{token_run.LEND_MARK}\r\norganization\r\n")), ("lend", ["organization"]))
        self.assertEqual(token_run.request(self.opened(f"{token_run.MANAGE_MARK}\nrevoke 5 extra words")), ("manage", ["revoke", "5"]))
        self.assertEqual(token_run.request(self.opened("Hello, I have a bug")), ("", []))
        self.assertEqual(token_run.request({**self.environ, "GITHUB_EVENT_NAME": "workflow_dispatch"}), ("", []))
        self.assertEqual(token_run.asked(self.opened(f"{token_run.MANAGE_MARK}\ndelete")), ("delete", ""))

    def test_a_lend_with_no_say_goes_where_the_standing_list_says(self):
        environ = self.opened(f"{token_run.LEND_MARK}\norganization")
        slot = token_run.look(environ, call=lambda *a: None)
        self.assertEqual(slot, "2")
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_2"], [5, 11, 12])
        # the lender is told nothing of the repositories, and the issue is closed as done
        self.assertEqual(self.github.posted, [f"{token_run.LENT_MARK}\n2\norganization"])
        self.assertEqual(json.loads(self.org.variables["SYMPHONY_CLAUDE_SETTINGS"])["2"]["keeping"], "organization")
        self.assertEqual(self.github.closed, [True])

    def test_a_new_token_lent_with_no_say_is_kept_by_the_organization(self):
        environ = self.opened(f"{token_run.LEND_MARK}\norganization")
        environ["ACTOR"] = "newcomer"
        keeper = token_run.keeper_of(environ)
        slot = keeper.store("x", "newcomer")
        self.assertEqual(slot, "1")
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_1"], [11, 12])
        self.assertEqual(json.loads(self.org.variables["SYMPHONY_CLAUDE_SETTINGS"])["1"]["keeping"], "organization")
        token_run.say_lent(self.github, keeper, "1")
        self.assertEqual(self.github.posted, [f"{token_run.LENT_MARK}\n1\norganization"])

    def test_a_lend_with_no_say_and_no_standing_list_goes_nowhere_yet(self):
        del self.org.variables["SYMPHONY_LEND_TO"]
        environ = self.opened(f"{token_run.LEND_MARK}\norganization")
        environ["ACTOR"] = "newcomer"
        keeper = token_run.keeper_of(environ)
        keeper.store("x", "newcomer")
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_1"], [])

    def test_a_standing_list_that_is_not_ids_stops_the_run(self):
        self.org.variables["SYMPHONY_LEND_TO"] = "11, acme/private"
        with self.assertRaisesRegex(token_run.RunError, "not a repository id"):
            token_run.keeper_of(self.opened(f"{token_run.LEND_MARK}\norganization"))

    def kept(self):
        self.org.variables["SYMPHONY_CLAUDE_SETTINGS"] = json.dumps({"2": {"owner": "ashley", "uid": 7, "keeping": "organization"}})

    def test_a_kept_token_is_not_lent_where_its_lender_picks(self):
        self.kept()
        slot = token_run.look(self.opened(token_run.LEND_MARK), call=lambda *a: None)
        self.assertEqual(slot, "2")
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_2"], [5])
        self.assertEqual(self.github.posted, [f"{token_run.LENT_MARK}\n2\norganization"])

    def test_a_kept_token_is_still_placed_by_a_lend_with_no_say(self):
        self.kept()
        token_run.look(self.opened(f"{token_run.LEND_MARK}\norganization"), call=lambda *a: None)
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_2"], [5, 11, 12])

    def test_a_kept_token_is_not_revoked_but_may_be_deleted(self):
        self.kept()
        with self.assertRaisesRegex(token_run.RunError, "keeping"):
            token_run.manage(self.opened(f"{token_run.MANAGE_MARK}\nrevoke 5"))
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_2"], [5])
        token_run.manage(self.opened(f"{token_run.MANAGE_MARK}\ndelete"))
        self.assertNotIn("SYMPHONY_CLAUDE_2", self.org.secrets)

    def dispatched(self, lend_to):
        return {**self.environ, "GITHUB_EVENT_NAME": "workflow_dispatch", "LEND_TO": lend_to}

    def test_a_dispatch_lends_to_the_repository_it_names(self):
        # the Tokens page runs the workflow here for a repository of the organization without one
        slot = token_run.look(self.dispatched("77"), call=lambda *a: None)
        self.assertEqual(slot, "2")
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_2"], [5, 77])
        self.assertEqual(self.github.posted, [f"{token_run.LENT_MARK}\n2\n5,77"])
        keeper = token_run.keeper_of(self.dispatched("77"))
        self.assertEqual(keeper.store("x", "newcomer"), "1")
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_1"], [77])

    def test_lend_to_counts_for_nothing_from_an_issue(self):
        environ = {**self.opened(token_run.LEND_MARK), "LEND_TO": "77"}
        token_run.look(environ, call=lambda *a: None)
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_2"], [5, 42])

    def test_lend_to_outside_the_organization_or_unknown_stops_the_run(self):
        for wanted, why in (("99", "no repository of acme"), ("123456", "no repository of acme"), ("acme/private", "not a repository id"), ("78", "may not write to")):
            with self.assertRaisesRegex(token_run.RunError, why):
                token_run.keeper_of(self.dispatched(wanted))
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_2"], [5])

    def test_a_plain_lend_issue_lends_here_alone(self):
        slot = token_run.look(self.opened(token_run.LEND_MARK), call=lambda *a: None)
        self.assertEqual(slot, "2")
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_2"], [5, 42])
        self.assertEqual(self.github.posted, [f"{token_run.LENT_MARK}\n2\n5,42"])

    def test_a_manage_issue_is_answered_and_closed(self):
        token_run.manage(self.opened(f"{token_run.MANAGE_MARK}\ndelete"))
        self.assertNotIn("SYMPHONY_CLAUDE_2", self.org.secrets)
        self.assertEqual(self.github.closed, [True])
        with self.assertRaisesRegex(token_run.RunError, "lists, revokes or deletes"):
            token_run.manage(self.opened(f"{token_run.MANAGE_MARK}\n"))

    def test_a_dispatched_run_closes_no_issue(self):
        environ = {**self.environ, "GITHUB_EVENT_NAME": "workflow_dispatch", "MANAGE": "list"}
        token_run.manage(environ)
        self.assertEqual(self.github.closed, [])

    def test_a_failed_issue_run_is_closed_as_not_done(self):
        token_run.fail(self.opened(token_run.LEND_MARK))
        self.assertTrue(self.github.posted[0].startswith(token_run.FAILED_MARK))
        self.assertEqual(self.github.closed, [False])

    def test_a_slot_kept_by_login_alone_waits_for_a_run_with_write_access(self):
        # a slot with no uid: an issue anyone may open cannot take it, a dispatch keeps its id
        self.org.variables["SYMPHONY_CLAUDE_SETTINGS"] = json.dumps({"2": {"owner": "ashley"}})
        with self.assertRaisesRegex(token_run.RunError, "by login alone"):
            token_run.look(self.opened(token_run.LEND_MARK), call=lambda *a: None)
        self.assertEqual(self.org.lent["SYMPHONY_CLAUDE_2"], [5])
        self.org.users["ashley"] = 7
        token_run.look({**self.environ, "GITHUB_EVENT_NAME": "workflow_dispatch"}, call=lambda *a: None)
        self.assertEqual(json.loads(self.org.variables["SYMPHONY_CLAUDE_SETTINGS"])["2"]["uid"], 7)
        self.github.posted = []
        token_run.look(self.opened(token_run.LEND_MARK), call=lambda *a: None)
        self.assertEqual(self.github.posted, [f"{token_run.LENT_MARK}\n2\n5,42"])

    def test_a_run_that_fails_in_the_script_closes_its_issue_as_not_done(self):
        environ = self.opened(f"{token_run.MANAGE_MARK}\nlend-all")
        saved = dict(os.environ)
        os.environ.update(environ)
        try:
            self.assertEqual(token_run.main(["manage"]), 1)
        finally:
            os.environ.clear()
            os.environ.update(saved)
        self.assertTrue(self.github.posted[-1].startswith(token_run.FAILED_MARK))
        self.assertEqual(self.github.closed, [False])

    def test_the_code_is_found_past_a_hundred_comments(self):
        pages = {1: [{"id": i, "user": {"login": "x"}, "body": "noise"} for i in range(100)],
                 2: [{"id": 200, "user": {"login": "ashley"}, "body": CODE}]}
        github = token_run.GitHub("acme/r", "t", "7")
        github.call = lambda method, path, body=None: pages.get(int(path.rsplit("page=", 1)[1]), [])
        self.assertEqual(token_run.code_from(github.comments(), "ashley"), (CODE, 200))

    def test_a_code_pasted_bare_on_the_issue_counts(self):
        comments = [{"id": 1, "user": {"login": "Ashley"}, "body": "thanks, signing in"},
                    {"id": 2, "user": {"login": "mallory"}, "body": CODE},
                    {"id": 3, "user": {"login": "ashley"}, "body": f"  {CODE}  "}]
        self.assertEqual(token_run.code_from(comments, "ashley"), (CODE, 3))


if __name__ == "__main__":
    unittest.main()
