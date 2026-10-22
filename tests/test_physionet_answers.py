"""A PhysioNet fetch that fails says which answer PhysioNet gave and what it means, in FETCH.json
and the stage report, without the password: wget's default lines name the HTTP status of each
request, read in the C locale and only from the start of wget's own line. The answers to the
project's URL decide, after any redirect: 401-then-403 is a login taken for an account without
access, 401-then-401 a login refused, a lone 401 with exit 6 a wget that had no password to
send, 403 a refusal before any login, 404 no such version; once files came, the failure is some
of the files'. A run keeps its first answers and a count of each code, never the whole list."""

import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(os.environ.get("FETCH_ROOT", Path(__file__).resolve().parent.parent))

FAKE_WGET = """#!/bin/bash
# wget's default lines for the answers in WGET_ANSWERS; never the login or the password
[ "$LC_ALL" = C ] || { echo "wget ran in the job's locale, not C"; exit 99; }
echo "--2026-10-21 21:49:01--  ${@: -1}"
for code in $WGET_ANSWERS; do
  echo "HTTP request sent, awaiting response... $code Answer"
  if [ "$code" = 401 ]; then echo 'Authentication selected: Basic realm="PhysioNet", charset="UTF-8"'; fi
  if [ "$code" = 200 ]; then echo "Saving to: 'physionet.org/files/vindr-pcxr/awaiting response... 404 a.dicom'"; fi
done
if [ "$WGET_EXIT" = 6 ]; then echo "Username/Password Authentication Failed."; fi
if [ "$WGET_EXIT" = 8 ]; then echo "ERROR ${code}: Answer."; fi
exit $WGET_EXIT
"""


def load():
    spec = importlib.util.spec_from_file_location("fetch_sources_tool", ROOT / "tools" / "fetch_sources.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


class PhysioNetAnswerTest(unittest.TestCase):
    def fetch(self, answers, exit_code, expect=1, locale="C.UTF-8", netrc_name=".netrc"):
        tool = load()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "bin").mkdir()
            wget = tmp / "bin" / "wget"
            wget.write_text(FAKE_WGET, encoding="utf-8")
            wget.chmod(0o755)
            netrc = tmp / netrc_name
            netrc.write_text("machine physionet.org login someone password not-to-be-seen\n", encoding="utf-8")
            netrc.chmod(0o600)
            helper = tmp / "reacquire.py"
            helper.write_text("", encoding="utf-8")
            report = tmp / "report.md"
            env = {"PATH": f"{tmp / 'bin'}:{os.environ['PATH']}", "HOME": str(tmp), "LC_ALL": locale,
                   "WGET_ANSWERS": answers, "WGET_EXIT": str(exit_code)}
            argv = ["--run", "--outside-slurm", "--only", "vindr_pcxr", "--credentialed", "--data-root",
                    str(tmp / "data"), "--reacquire", str(helper), "--netrc", str(netrc), "--report", str(report)]
            with mock.patch.object(tool.socket, "gethostname", return_value="wsu123"), \
                    mock.patch.dict(os.environ, env, clear=True), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = tool.main(argv)
            record = json.loads((tmp / "data" / "vindr_pcxr" / "FETCH.json").read_text(encoding="utf-8"))
            text = report.read_text(encoding="utf-8")
        self.assertEqual(code, expect)
        self.assertNotIn("not-to-be-seen", text + json.dumps(record))
        self.assertNotIn("someone", text)
        return record, text

    def test_a_login_taken_and_files_refused_names_401_then_403(self):
        record, text = self.fetch("401 403", 8)
        self.assertEqual(record["runs"][-1]["http"], {"first": [401, 403], "answers": 2,
                                                      "counts": {"401": 1, "403": 1}})
        self.assertIn("HTTP 401, 403: PhysioNet took the login and refused the files", text)
        self.assertIn("deprecated, cloud-only or region-blocked", text)

    def test_a_redirect_first_says_nothing_either_way(self):
        record, text = self.fetch("301 401 403", 8)
        self.assertIn("HTTP 301, 401, 403: PhysioNet took the login and refused the files", text)

    def test_a_wrong_password_is_told_apart(self):
        record, text = self.fetch("401 401", 6)
        self.assertIn("HTTP 401, 401: PhysioNet refused the login", text)

    def test_a_login_refused_and_then_a_403_is_still_a_refused_login(self):
        record, text = self.fetch("401 401 403", 8)
        self.assertIn("HTTP 401, 401, 403: PhysioNet refused the login", text)

    def test_a_lone_401_with_exit_6_is_a_wget_that_sent_no_login(self):
        record, text = self.fetch("401", 6)
        self.assertIn("HTTP 401: wget found no password for that login in $HOME/.netrc and sent no login", text)
        self.assertNotIn("refused the login", text)

    def test_a_refusal_before_any_login_is_told_apart(self):
        record, text = self.fetch("403", 8)
        self.assertIn("HTTP 403: PhysioNet refused before asking for a login", text)

    def test_a_wrong_version_is_told_apart(self):
        record, text = self.fetch("404", 8)
        self.assertIn("HTTP 404: no such project version", text)

    def test_files_that_came_before_a_failure_are_no_access_question(self):
        record, text = self.fetch("401 200 200 404", 8)
        http = record["runs"][-1]["http"]
        self.assertEqual(http["counts"], {"200": 2, "401": 1, "404": 1})
        self.assertIn("PhysioNet took the login and served 2 answers, so the login and the access held", text)
        self.assertNotIn("no such project version", text)

    def test_a_long_run_keeps_its_first_answers_and_counts(self):
        record, text = self.fetch("401 " + "200 " * 3000 + "503", 8)
        http = record["runs"][-1]["http"]
        self.assertEqual(http, {"first": [401, 200, 200, 200, 200, 200], "answers": 3002,
                                "counts": {"200": 3000, "401": 1, "503": 1}})
        line = next(line for line in text.splitlines() if line.startswith("- vindr_pcxr"))
        self.assertLess(len(line), 1000)
        self.assertIn("3,002 answers: 3,000 x 200, 1 x 401, 1 x 503", line)

    def test_no_answer_at_all_names_the_wget_exit(self):
        record, text = self.fetch("", 4)
        self.assertIn("no HTTP answer: wget exit 4, network failure", text)

    def test_a_server_error_names_the_wget_exit(self):
        record, text = self.fetch("503", 8)
        self.assertIn("HTTP 503: wget exit 8, server issued an error response", text)

    def test_a_success_records_its_answers_and_no_error(self):
        record, text = self.fetch("401 200", 0, expect=0)
        self.assertEqual(record["status"], "done")
        self.assertEqual(record["runs"][-1]["http"]["first"], [401, 200])
        self.assertNotIn("error", record)

    def test_wget_runs_in_the_c_locale_whatever_the_job_says(self):
        record, text = self.fetch("401 403", 8, locale="de_DE.UTF-8")
        self.assertIn("HTTP 401, 403: PhysioNet took the login", text)

    def test_a_netrc_wget_does_not_read_is_refused_before_any_fetch(self):
        record, text = self.fetch("401 403", 8, netrc_name="netrc")
        self.assertEqual(record["runs"], [])
        self.assertIn("wget reads the password only from $HOME/.netrc", text)


class NetrcTest(unittest.TestCase):
    def login(self, text):
        tool = load()
        with tempfile.TemporaryDirectory() as tmp:
            netrc = Path(tmp) / ".netrc"
            netrc.write_text(text, encoding="utf-8")
            netrc.chmod(0o600)
            try:
                return tool.netrc_login("physionet.org", netrc)
            except tool.FetchError as error:
                return error

    def test_an_entry_with_no_password_is_refused(self):
        said = self.login("machine physionet.org login someone\n")
        self.assertIn("has no password, so wget would send no login", str(said))

    def test_the_login_of_a_full_entry_is_read_and_the_password_never_returned(self):
        self.assertEqual(self.login("machine other.org login x password y\nmachine physionet.org login someone"
                                    " password secret-value\n"), "someone")

    def test_an_unknown_word_is_passed_over_as_wget_passes_it(self):
        # Python's netrc refused such a file, which stopped every PhysioNet fetch (issue #100)
        self.assertEqual(self.login("machine physionet.org login someone password secret-value bogus\n"), "someone")

    def test_the_forms_wget_reads(self):
        text = ("# the grid's netrc\n"
                "machine urs.earthdata.nasa.gov\n  login a\n  password b\n\n"
                "macdef init\nmachine physionet.org login wrong password wrong\n\n"
                "machine physionet.org\n\tlogin someone # a note\n\tpassword \"pass word\\\"#1\"\n"
                "machine physionet.org login later password later\n"
                "default login anon password anon\n")
        self.assertEqual(self.login(text), "someone")

    def test_default_never_stands_in_since_wget_given_a_user_ignores_it(self):
        said = self.login("machine other.org login x password y\ndefault login anon password z\n")
        self.assertIn("no 'machine physionet.org login <user>' entry", str(said))

    def test_an_entry_with_no_login_is_dropped_as_wget_drops_it(self):
        self.assertEqual(self.login("machine physionet.org password p\nmachine physionet.org login a password b\n"), "a")

    def test_keywords_are_read_only_as_written(self):
        self.assertEqual(self.login("Machine physionet.org login a password b\nmachine physionet.org login c password d\n"), "c")

    def test_the_values_wget_skips_and_the_marks_it_takes_out(self):
        self.assertEqual(self.login("machine physionet.org port login login a password b\n"), "a")
        self.assertEqual(self.login("machine physionet.org login dom\\\\user password b\n"), "dom\\user")
        self.assertEqual(self.login('machine physionet.org login "a"Xlogin b password c\n'), "b")
        self.assertEqual(self.login("macdef init machine physionet.org login wrong password w\nmachine x\n\n"
                                    "machine physionet.org login right password r\n"), "right")

    def test_a_byte_that_is_no_utf_8_in_another_entry_is_read_past(self):
        tool = load()
        with tempfile.TemporaryDirectory() as tmp:
            netrc = Path(tmp) / ".netrc"
            netrc.write_bytes(b"machine other.org login x password caf\xe9\nmachine physionet.org login a password b\n")
            netrc.chmod(0o600)
            self.assertEqual(tool.netrc_login("physionet.org", netrc), "a")

    def test_a_file_that_cannot_be_read_names_no_token(self):
        tool = load()
        with tempfile.TemporaryDirectory() as tmp:
            netrc = Path(tmp) / ".netrc"
            netrc.mkdir(mode=0o700)
            with self.assertRaises(tool.FetchError) as said:
                tool.netrc_login("physionet.org", netrc)
        self.assertNotIn("password", str(said.exception))

    def test_the_password_is_read_as_wget_reads_it(self):
        tool = load()
        entries = tool.netrc_entries('machine physionet.org login someone password "pass word\\"#1"\n')
        self.assertEqual(entries, [("physionet.org", "someone", 'pass word"#1')])

if __name__ == "__main__":
    unittest.main()
