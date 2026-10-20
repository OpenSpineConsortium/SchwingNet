"""tools/outlook_digest.py: the digest's card renders on every Outlook that
renders one (version 1.0, no Action.Submit, buttons that post), answers
come back the same from a button, from text typed into the card and from a
plain reply, and nothing decides twice or for someone else."""

import datetime
import email
import email.policy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import outlook_digest as od  # noqa: E402

NOW = datetime.datetime(2026, 10, 20, 15, 0, tzinfo=datetime.timezone.utc)
DIGEST = "symphony-digest-202610201500"
URL = "https://signin.example.org/outlook/action"
DECISION_BODY = """Why this matters.

## Options
- **Accept**: Claude spends two days building the reader
- **Decline**: nothing is built
- **Smaller**: only the parser, half a day
Recommended: accept
"""


def issue(number, title, labels, body="", state="open", **more):
    return {"number": number, "title": title, "labels": [{"name": n} for n in labels], "body": body, "state": state, **more}


ISSUES = [
    issue(12, "Build the grant reader", ["decision"], DECISION_BODY),
    issue(14, "Thesis chapters", ["epic", "proposed", "drive"]),
    issue(15, "A decision with one option", ["decision"], "## Options\n- **Yes**: only this\n"),
    issue(16, "Plain task", ["todo"]),
    issue(20, "Fixed the walk", ["todo"], state="closed", state_reason="completed", closed_at="2026-10-20T10:00:00Z"),
    issue(21, "Dropped idea", [], state="closed", state_reason="not_planned", closed_at="2026-10-20T11:00:00Z"),
    issue(22, "Merged change", [], state="closed", closed_at="2026-10-20T12:00:00Z", pull_request={"merged_at": "2026-10-20T12:00:00Z"}),
    issue(23, "Closed unmerged", [], state="closed", closed_at="2026-10-20T13:00:00Z", pull_request={"merged_at": None}),
]


def actions_of(found):
    """Every action in a card, nested ShowCards' included."""
    for action in found.get("actions", []):
        yield action
        if action["type"] == "Action.ShowCard":
            yield from actions_of(action["card"])


class Reading(unittest.TestCase):
    def test_decisions_are_open_issues_that_ask_for_one(self):
        found = od.decisions_in(ISSUES)
        self.assertEqual([d.number for d in found], [12, 14])
        self.assertEqual([n for n, _ in found[0].options], ["Accept", "Decline", "Smaller"])
        self.assertEqual(found[0].recommended, "Accept")
        self.assertEqual(found[1].kind, "project")

    def test_done_counts_completed_issues_and_merged_pulls(self):
        self.assertEqual([i["number"] for i in od.done_in(ISSUES)], [22, 20])

    def test_a_label_that_could_break_the_json_is_no_option(self):
        options, _ = od.options_in('## Options\n- **Go"}**: x\n- **No**: y\n- **Yes**: z\n')
        self.assertEqual([n for n, _ in options], ["No", "Yes"])


class Card(unittest.TestCase):
    def setUp(self):
        self.card = od.card("o/r", DIGEST, od.decisions_in(ISSUES), od.done_in(ISSUES), URL, "me@wayne.edu", now=NOW)

    def test_it_uses_only_what_outlook_renders(self):
        self.assertEqual(self.card["version"], "1.0")
        types = {a["type"] for a in actions_of(self.card)}
        self.assertLessEqual(types, {"Action.Http", "Action.ShowCard"})
        self.assertEqual(self.card["expectedActors"], ["me@wayne.edu"])
        self.assertNotIn("originator", self.card)

    def test_every_button_posts_an_answer_the_reader_takes(self):
        decisions = od.decisions_in(ISSUES)
        for action in actions_of(self.card):
            if action["type"] != "Action.Http":
                continue
            self.assertEqual(action["url"], URL)
            body = action["body"].replace("{{t12.value}}", 'it said "go" \\ now').replace("{{t14.value}}", "").replace("{{prompt.value}}", "new goal")
            found = od.parse_action(body)
            self.assertIsNotNone(found, action["body"])
            self.assertEqual(found["d"], DIGEST)
            ops = od.plan_action(found, decisions)
            self.assertFalse([op for op in ops if op["op"] == "refuse"], ops)

    def test_the_last_action_tells_claude_anything(self):
        last = self.card["actions"][-1]
        self.assertEqual(last["title"], "Tell Claude")
        self.assertEqual(last["card"]["body"][0]["id"], "prompt")

    def test_more_decisions_than_fit_are_left_to_a_reply(self):
        many = [issue(n, f"Q{n}", ["epic", "proposed"]) for n in range(1, 8)]
        found = od.card("o/r", DIGEST, od.decisions_in(many), [], URL, "me@x", now=NOW)
        self.assertEqual(len(found["actions"]), od.CARD_DECISIONS + 1)
        self.assertIn("Reply to answer the other 3", json.dumps(found))

    def test_a_title_renders_no_link(self):
        found = od.card("o/r", DIGEST, [], od.done_in([issue(40, "[Verify](https://evil)", [], state="closed")]), URL, "me@x", now=NOW)
        self.assertNotIn("[Verify]", json.dumps(found))

    def test_a_title_cannot_close_the_script(self):
        evil = [issue(30, "</script><img src=x>", ["epic", "proposed"])]
        found = od.card("o/r", DIGEST, od.decisions_in(evil), [], URL, "me@x", now=NOW)
        page = od.html_body(found, od.plain_text("o/r", DIGEST, od.decisions_in(evil), []))
        self.assertEqual(page.count("</script>"), 1)
        self.assertNotIn("<img", page)


class Answers(unittest.TestCase):
    def setUp(self):
        self.decisions = od.decisions_in(ISSUES)

    def test_accepting_a_project_runs_the_organizers_accept(self):
        ops = od.plan([(14, "accept", "")], "", self.decisions)
        self.assertEqual(ops[0], {"op": "accept_project", "epic": 14})

    def test_declining_a_project_closes_it_as_not_planned(self):
        ops = od.plan([(14, "Decline", "not now")], "", self.decisions)
        self.assertEqual(ops[-1], {"op": "close", "issue": 14, "reason": "not_planned"})
        self.assertIn("not now", ops[0]["body"])

    def test_a_decision_is_answered_once(self):
        ops = od.plan([(12, "Smaller", "")], "", self.decisions)
        self.assertIn("<!-- symphony-decision: Smaller -->", ops[0]["body"])
        self.assertEqual(ops[1], {"op": "unlabel", "issue": 12, "label": "decision"})
        after = od.decisions_in([i for i in ISSUES if i["number"] != 12])
        self.assertEqual(od.plan([(12, "Accept", "")], "", after)[0]["op"], "refuse")

    def test_an_unknown_option_or_another_actor_is_refused(self):
        self.assertEqual(od.plan([(12, "Maybe", "")], "", self.decisions)[0]["op"], "refuse")
        ops = od.plan([(12, "Accept", "")], "x", self.decisions, actor="other@x", expected="me@wayne.edu")
        self.assertEqual([op["op"] for op in ops], ["refuse"])
        ops = od.plan([(12, "Accept", "")], "", self.decisions, actor="ME@wayne.edu", expected="me@wayne.edu")
        self.assertEqual(ops[0]["op"], "comment")

    def test_a_prompt_opens_an_issue_no_worker_takes(self):
        ops = od.plan([], "Add the spine dataset as a goal.\nIt is on the grid.", self.decisions)
        self.assertEqual(ops, [{"op": "open_issue", "title": "From Outlook: Add the spine dataset as a goal.",
                                "body": "Add the spine dataset as a goal.\nIt is on the grid.", "labels": ["from-email"]}])

    def test_typed_text_cannot_change_the_issue_or_the_option(self):
        body = '{"d":"%s","n":12,"c":"Accept","t":"x","c":"Decline","n":14,"t":"y"}' % DIGEST
        found = od.parse_action(body)
        self.assertEqual((found["n"], found["c"]), (12, "Accept"))
        self.assertEqual(found["t"], 'x","c":"Decline","n":14,"t":"y')
        found = od.parse_action('{"d":"%s","n":12,"c":"","t":"C:\\new dir"}\n' % DIGEST)
        self.assertEqual(found["t"], "C:\\new dir")

    def test_two_answers_to_one_issue_do_only_the_first(self):
        ops = od.plan([(14, "Accept", ""), (14, "Decline", "")], "", self.decisions)
        self.assertEqual([op["op"] for op in ops], ["accept_project", "comment", "refuse"])

    def test_a_broken_or_foreign_body_is_no_answer(self):
        for raw in ("", "[]", '{"d":"x","n":1,"c":"","t":""}', '{"d":"%s","n":-1,"c":"","t":""}' % DIGEST,
                    '{"d":"%s","n":true,"c":"","t":""}' % DIGEST, '{"d":"%s","n":1,"c":"","t":"open' % DIGEST):
            self.assertIsNone(od.parse_action(raw), raw)


def reply_eml(text, html_only=False):
    msg = email.message.EmailMessage()
    msg["From"] = "me@wayne.edu"
    msg["Subject"] = "RE: Symphony digest"
    msg["In-Reply-To"] = f"<{DIGEST}@wayne.edu>"
    if html_only:
        msg.set_content("<html><body><p>" + text.replace("\n", "<br>") + "</p></body></html>", subtype="html")
    else:
        msg.set_content(text)
    return bytes(msg)


class Replies(unittest.TestCase):
    def setUp(self):
        self.decisions = od.decisions_in(ISSUES)

    def test_lines_that_answer_and_the_rest_as_a_prompt(self):
        text = ("12 smaller\n#14: decline\n3 things matter more this week.\n\n"
                "From: Symphony <me@wayne.edu>\nSent: Monday\nSubject: digest\n\n12 accept\n")
        found = od.parse_reply(reply_eml(text), self.decisions)
        self.assertEqual(found["d"], DIGEST)
        self.assertEqual(found["answers"], [(12, "Smaller"), (14, "Decline")])
        self.assertEqual(found["prompt"], "3 things matter more this week.")

    def test_quoted_lines_and_other_clients_quote_marks(self):
        for tail in ("On Mon, Oct 20, 2026 at 3:00 PM Symphony wrote:\n> 12 accept", "-----Original Message-----\n12 accept",
                     "________________________________\n12 accept"):
            found = od.parse_reply(reply_eml("Go ahead with the reader.\n" + tail), self.decisions)
            self.assertEqual((found["answers"], found["prompt"]), ([], "Go ahead with the reader."))

    def test_a_mail_apps_signature_is_no_prompt(self):
        found = od.parse_reply(reply_eml("12 accept\n\nGet Outlook for iOS\nSent from my iPhone"), self.decisions)
        self.assertEqual((found["answers"], found["prompt"]), ([(12, "Accept")], ""))

    def test_a_reply_that_names_no_digest_decides_nothing(self):
        msg = email.message.EmailMessage()
        msg["From"] = "me@wayne.edu"
        msg.set_content("12 accept\nand a new goal")
        found = od.parse_reply(bytes(msg), self.decisions)
        self.assertEqual(found, {"d": None, "answers": [], "prompt": ""})

    def test_an_html_reply_reads_the_same(self):
        found = od.parse_reply(reply_eml("14 accept\nAlso index the slides.", html_only=True), self.decisions)
        self.assertEqual(found["answers"], [(14, "Accept")])
        self.assertEqual(found["prompt"], "Also index the slides.")


class Compose(unittest.TestCase):
    def test_compose_writes_the_message_and_sends_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            issues = Path(tmp, "issues.json")
            issues.write_text(json.dumps(ISSUES), encoding="utf-8")
            od.main(["compose", "--issues", str(issues), "--repo", "o/r", "--to", "me@wayne.edu", "--action-url", URL, "--out", tmp])
            msg = email.message_from_bytes(Path(tmp, "digest.eml").read_bytes(), policy=email.policy.default)
            self.assertEqual(msg["From"], "me@wayne.edu")
            self.assertRegex(msg["Message-ID"], r"^<symphony-digest-[0-9]{12}@wayne\.edu>$")
            page = msg.get_body(preferencelist=("html",)).get_content()
            self.assertIn('<script type="application/adaptivecard+json">', page)
            self.assertIn("Reply with a line per answer", msg.get_body(preferencelist=("plain",)).get_content())
            self.assertEqual(json.loads(Path(tmp, "card.json").read_text())["type"], "AdaptiveCard")


if __name__ == "__main__":
    unittest.main()
