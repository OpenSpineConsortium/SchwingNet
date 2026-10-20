"""Compose the Outlook digest of a repository's progress and the decisions
waiting on its owner, and read back what the owner answers from inside
Outlook: a button pressed on the digest's card, text typed into it, or a
plain reply to the email.

The digest is one HTML email whose head carries an Adaptive Card (version
1.0, the newest Outlook on iOS and Android renders) as an Outlook
actionable message. Each decision gets an Action.ShowCard whose buttons are
Action.Http calls to the action endpoint, so a choice is one press without
leaving Outlook; a text box beside them, and one more at the end, takes
anything else the owner wants Claude to hear. The HTML body under the card
says the same in plain text for a client that shows no card, and a reply
such as "12 accept" or a paragraph of new direction does what the buttons
do. docs/research/outlook-digest.md has the design and what Microsoft
requires before a card renders (a self-sent message, or a registered
provider whose cards are signed).

Nothing here sends mail, holds a credential or calls Claude: compose writes
the message to files for a person to read, and plan turns an answer into
the GitHub operations a workflow would make, printed, not made.

A decision is an open issue labelled decision whose body has a section

  ## Options
  - **Accept**: what happens if chosen
  - **Decline**: what happens if chosen
  Recommended: Accept

with two to four options; a proposed project, an issue labelled epic and
proposed as tools/drive_organize.py opens them, is a decision too, its
options Accept (drive_organize.py accept) and Decline (closed as not
planned, which the organizer reads as no).

  python3 tools/outlook_digest.py compose --issues ISSUES.json --repo OWNER/NAME
      --to ADDRESS --action-url URL [--sender ADDRESS] [--originator ID] --out DIR
  python3 tools/outlook_digest.py reply --eml REPLY.eml --issues ISSUES.json [--actor ADDRESS]
  python3 tools/outlook_digest.py action --body BODY.txt --issues ISSUES.json [--actor ADDRESS]

ISSUES.json is a list of issues as GitHub's REST API gives them (open
decisions and proposals, and the issues and pull requests closed since the
last digest, a pull request marked by its pull_request key); reply and
action print the operations plan makes, as JSON. Standard library only.
"""

import argparse
import datetime
import email
import email.message
import email.policy
import email.utils
import html
import json
import re
import sys
from pathlib import Path

CARD_DECISIONS = 4  # Outlook lays a card's actions out in one row; more than five crowd it
LIST_LINES = 10
TITLE_CHARS = 72
# A label goes into the JSON of a button's body as it is, so it holds no
# quote, backslash or brace.
LABEL = r"[A-Za-z0-9][A-Za-z0-9 '\-]{0,39}"
OPTION = re.compile(r"^\s*[-*]\s+\*\*(" + LABEL + r")\*\*\s*:\s*(.+?)\s*$")
RECOMMENDED = re.compile(r"^\s*Recommended:\s*\**(" + LABEL + r")\**\s*$", re.IGNORECASE)
COMMAND = re.compile(r"^\s*#?([1-9][0-9]{0,8})\s*[:.\-]?\s*(" + LABEL + r")\s*$")
DIGEST_ID = re.compile(r"symphony-digest-([0-9]{12})")
# What mail apps add under a reply, which is no prompt to Claude.
SIGNATURES = re.compile(r"^\s*(Get Outlook for (iOS|Android|Mac|Windows)|Sent from (my )?(iPhone|iPad|Android|Outlook|mobile|Mail for Windows).*)\s*$", re.IGNORECASE)
QUOTE_START = (
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}\s*$", re.IGNORECASE),
    re.compile(r"^On .{1,200} wrote:\s*$"),
    re.compile(r"^_{10,}\s*$"),
)
PROJECT_OPTIONS = (
    ("Accept", "the project is tracked: its folders join the sync and its tasks start once the files are in"),
    ("Decline", "the proposal is closed as not planned and never proposed again"),
)


class Decision:
    def __init__(self, number, title, kind, options, recommended):
        self.number = number
        self.title = title
        self.kind = kind
        self.options = options
        self.recommended = recommended

    def option(self, label):
        """The option whose label matches, ignoring case and spaces, or None."""
        wanted = " ".join(label.split()).lower()
        return next((name for name, _ in self.options if " ".join(name.split()).lower() == wanted), None)


def labels_of(issue):
    return {label.get("name", "") if isinstance(label, dict) else str(label) for label in issue.get("labels") or []}


def options_in(body):
    """The Options section's options and its recommended label, or ([], None)."""
    options, recommended, inside = [], None, False
    for line in (body or "").splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower() == "options"
            continue
        if not inside:
            continue
        found = OPTION.match(line)
        if found and len(options) < 4:
            options.append((found.group(1).strip(), found.group(2)))
        elif RECOMMENDED.match(line):
            recommended = RECOMMENDED.match(line).group(1).strip()
    if len(options) < 2:
        return [], None
    named = {name.lower(): name for name, _ in options}
    return options, named.get((recommended or "").lower())


def decision_of(issue):
    """The decision an open issue asks for, or None when it asks for none."""
    if issue.get("state", "open") != "open" or "pull_request" in issue:
        return None
    labels = labels_of(issue)
    number, title = issue["number"], issue.get("title", "")
    if {"epic", "proposed"} <= labels:
        return Decision(number, title, "project", list(PROJECT_OPTIONS), "Accept")
    if "decision" in labels:
        options, recommended = options_in(issue.get("body"))
        if options:
            return Decision(number, title, "decision", options, recommended)
    return None


def decisions_in(issues):
    found = [decision_of(issue) for issue in issues]
    return sorted((d for d in found if d), key=lambda d: d.number)


def done_in(issues):
    """Issues closed as completed and pull requests merged, newest first."""
    done = []
    for issue in issues:
        if issue.get("state") != "closed":
            continue
        merged = (issue.get("pull_request") or {}).get("merged_at")
        if "pull_request" in issue and not merged:
            continue
        if "pull_request" not in issue and issue.get("state_reason") not in (None, "completed"):
            continue
        done.append(issue)
    return sorted(done, key=lambda i: i.get("closed_at") or "", reverse=True)


def digest_id(now):
    return "symphony-digest-" + now.strftime("%Y%m%d%H%M")


def http_action(title, url, digest, number, choice, field):
    """An Action.Http that posts one answer. The typed text goes last, so a
    reader can still take it when a quote in it breaks the JSON (parse_action)."""
    text = "{{" + field + ".value}}" if field else ""
    body = '{"d":"%s","n":%d,"c":"%s","t":"%s"}' % (digest, number, choice, text)
    return {
        "type": "Action.Http",
        "title": title,
        "method": "POST",
        "url": url,
        "body": body,
        "headers": [{"name": "Content-Type", "value": "application/json"}],
    }


def text_input(field, placeholder):
    return {"type": "Input.Text", "id": field, "isMultiline": True, "placeholder": placeholder}


def decision_card(decision, digest, url):
    field = f"t{decision.number}"
    actions = []
    for name, _ in decision.options:
        title = name + (" (recommended)" if name == decision.recommended else "")
        actions.append(http_action(title, url, digest, decision.number, name, field))
    actions.append(http_action("Send what I wrote", url, digest, decision.number, "", field))
    return {
        "type": "Action.ShowCard",
        "title": f"Decide #{decision.number}",
        "card": {
            "type": "AdaptiveCard",
            "body": [text_input(field, "Optional: anything Claude should know, or what you want instead")],
            "actions": actions,
        },
    }


def plain(text):
    """A title with no Markdown link or emphasis, since a card renders them
    and anyone can title an issue."""
    return re.sub(r"[\[\]*_`]", "", text or "")


def option_lines(decision):
    lines = []
    for name, consequence in decision.options:
        mark = " (recommended)" if name == decision.recommended else ""
        lines.append(f"**{name}**{mark}: {consequence}")
    return lines


def card(repo, digest, decisions, done, url, to, originator=None, now=None):
    """The digest's Adaptive Card, as a dict."""
    when = (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%d")
    body = [
        {"type": "TextBlock", "text": f"Symphony: {repo}", "size": "large", "weight": "bolder", "wrap": True},
        {"type": "TextBlock", "text": f"{when}: {len(done)} done, {len(decisions)} waiting on you", "isSubtle": True, "wrap": True},
    ]
    if done:
        body.append({"type": "TextBlock", "text": "Done since the last digest", "weight": "bolder"})
        facts = [{"title": f"#{i['number']}", "value": plain(i.get("title"))} for i in done[:LIST_LINES]]
        body.append({"type": "FactSet", "facts": facts})
        if len(done) > LIST_LINES:
            body.append({"type": "TextBlock", "text": f"and {len(done) - LIST_LINES} more", "isSubtle": True})
    if decisions:
        body.append({"type": "TextBlock", "text": "Waiting on you", "weight": "bolder"})
    for decision in decisions:
        items = [{"type": "TextBlock", "text": f"#{decision.number} {plain(decision.title)}", "weight": "bolder", "wrap": True}]
        items += [{"type": "TextBlock", "text": line, "wrap": True} for line in option_lines(decision)]
        body.append({"type": "Container", "separator": True, "items": items})
    if len(decisions) > CARD_DECISIONS:
        body.append({"type": "TextBlock", "wrap": True, "isSubtle": True,
                     "text": f"Reply to answer the other {len(decisions) - CARD_DECISIONS}, a line such as \"{decisions[-1].number} {decisions[-1].options[0][0]}\" for each."})
    actions = [decision_card(d, digest, url) for d in decisions[:CARD_DECISIONS]]
    actions.append({
        "type": "Action.ShowCard",
        "title": "Tell Claude",
        "card": {
            "type": "AdaptiveCard",
            "body": [text_input("prompt", "A new goal, a task, a change of direction, or something Claude should know")],
            "actions": [http_action("Send to Claude", url, digest, 0, "", "prompt")],
        },
    })
    found = {
        "type": "AdaptiveCard",
        "version": "1.0",
        "hideOriginalBody": True,
        "correlationId": digest,
        "expectedActors": [to],
        "body": body,
        "actions": actions,
    }
    if originator:
        found["originator"] = originator
    return found


def plain_text(repo, digest, decisions, done):
    """The digest as plain lines, the body a client with no card shows."""
    lines = [f"Symphony: {repo}", ""]
    if done:
        lines.append("Done since the last digest:")
        lines += [f"  #{i['number']} {i.get('title', '')}" for i in done[:LIST_LINES]]
        if len(done) > LIST_LINES:
            lines.append(f"  and {len(done) - LIST_LINES} more")
        lines.append("")
    if decisions:
        lines.append("Waiting on you. Reply with a line per answer, such as \"12 accept\":")
        for decision in decisions:
            lines.append(f"  #{decision.number} {decision.title}")
            lines += ["    " + line.replace("**", "") for line in option_lines(decision)]
        lines.append("")
    lines.append("Anything else you write in a reply goes to Claude as a new prompt for this project.")
    lines.append(f"Symphony digest id: {digest}")
    return "\n".join(lines)


def html_body(found_card, text):
    # No "<" inside the script at all, so no title can end it or open a tag.
    script = json.dumps(found_card, indent=1).replace("<", "\\u003c")
    return (
        "<html><head><meta http-equiv=\"Content-Type\" content=\"text/html; charset=utf-8\">"
        f"<script type=\"application/adaptivecard+json\">{script}</script></head>"
        f"<body><pre style=\"font-family:inherit;white-space:pre-wrap\">{html.escape(text)}</pre></body></html>"
    )


def message(repo, digest, found_card, text, to, sender, now):
    """The digest as an email message, for a person to read; nothing sends it."""
    msg = email.message.EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = f"Symphony digest for {repo}, {now.strftime('%Y-%m-%d')}"
    msg["Date"] = email.utils.format_datetime(now)
    domain = sender.rpartition("@")[2] or "symphony.invalid"
    msg["Message-ID"] = f"<{digest}@{domain}>"
    msg.set_content(text)
    msg.add_alternative(html_body(found_card, text), subtype="html")
    return msg


def parse_action(raw):
    """The answer an Action.Http posted, as {d, n, c, t}, or None. Outlook puts
    the typed text into the body as it was typed, so the body is read by
    position, never as JSON: the digest, the issue and the choice from the
    fixed head the composer wrote, and the text as everything between "t":"
    and the body's closing "}, since the composer writes it last. Text that
    looks like JSON ("n":7 typed into the box) is only text, and a backslash
    in it stays a backslash."""
    raw = raw.strip()
    head = re.match(r'^\{"d":"(symphony-digest-[0-9]{12})","n":(0|[1-9][0-9]{0,8}),"c":"(' + LABEL + r')?","t":"', raw)
    if not head or not raw.endswith('"}') or len(raw) < head.end() + 2:
        return None
    return {"d": head.group(1), "n": int(head.group(2)), "c": head.group(3) or "", "t": raw[head.end():-2].strip()}


def reply_text(msg):
    part = msg.get_body(preferencelist=("plain",))
    if part is not None:
        return part.get_content()
    part = msg.get_body(preferencelist=("html",))
    if part is None:
        return ""
    markup = re.sub(r"(?is)<(script|style|head).*?</\1>", "", part.get_content())
    markup = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", markup)
    return html.unescape(re.sub(r"<[^>]+>", "", markup))


def strip_quote(text):
    """The lines the person wrote, above the quoted digest."""
    kept = []
    lines = text.replace("\r\n", "\n").split("\n")
    for index, line in enumerate(lines):
        if any(pattern.match(line) for pattern in QUOTE_START):
            break
        following = "\n".join(lines[index + 1:index + 5])
        if re.match(r"^\s*From:\s", line) and re.search(r"(?m)^\s*(Sent|Date):\s", following):
            break
        if line.lstrip().startswith(">") or SIGNATURES.match(line):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def parse_reply(raw, decisions):
    """A reply to a digest, as {d, answers: [(number, label)], prompt}."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    threads = " ".join(str(msg.get(h, "")) for h in ("In-Reply-To", "References"))
    text = reply_text(msg)
    found = DIGEST_ID.search(threads) or DIGEST_ID.search(text)
    by_number = {d.number: d for d in decisions}
    answers, rest = [], []
    for line in strip_quote(text).split("\n"):
        command = COMMAND.match(line)
        decision = by_number.get(int(command.group(1))) if command else None
        label = decision.option(command.group(2)) if decision else None
        if label:
            answers.append((decision.number, label))
        else:
            rest.append(line)
    if not found:
        return {"d": None, "answers": [], "prompt": ""}
    return {"d": "symphony-digest-" + found.group(1), "answers": answers, "prompt": "\n".join(rest).strip()}


def first_line(text):
    line = next((l.strip() for l in text.splitlines() if l.strip()), "")
    return line if len(line) <= TITLE_CHARS else line[:TITLE_CHARS - 3].rstrip() + "..."


def prompt_ops(text):
    if not text:
        return []
    return [{"op": "open_issue", "title": "From Outlook: " + first_line(text), "body": text, "labels": ["from-email"]}]


def answer_ops(decision, label, text):
    note = f"\n\n{text}" if text else ""
    if decision.kind == "project" and label == "Accept":
        return [{"op": "accept_project", "epic": decision.number}, {"op": "comment", "issue": decision.number, "body": f"Accepted in Outlook.{note}"}]
    if decision.kind == "project":
        return [{"op": "comment", "issue": decision.number, "body": f"Declined in Outlook.{note}"}, {"op": "close", "issue": decision.number, "reason": "not_planned"}]
    marker = f"<!-- symphony-decision: {label} -->"
    return [{"op": "comment", "issue": decision.number, "body": f"{marker}\nChosen in Outlook: {label}.{note}"}, {"op": "unlabel", "issue": decision.number, "label": "decision"}]


def plan(answers, prompt, decisions, actor=None, expected=None):
    """The GitHub operations an answer asks for. answers is a list of
    (number, label, text); a label of "" sends the text alone to that issue.
    An actor other than the one expected, or a decision no longer open, is
    refused, and so is a second answer to one issue in the same reply, since
    which of two contradicting lines was meant is not for code to guess.
    A decision is answered once because answering it takes its label off;
    a proposed project stays a decision until accept takes proposed off."""
    if expected and (actor or "").lower() != expected.lower():
        return [{"op": "refuse", "why": "the answer did not come from the digest's recipient"}]
    by_number = {d.number: d for d in decisions}
    ops, seen = [], set()
    for number, label, text in answers:
        decision = by_number.get(number)
        if number in seen:
            ops.append({"op": "refuse", "why": f"#{number} was answered twice; nothing was done for its second answer"})
            continue
        seen.add(number)
        if decision is None:
            ops.append({"op": "refuse", "why": f"#{number} is no longer waiting on a decision"})
        elif not label:
            if text:
                ops.append({"op": "comment", "issue": number, "body": f"From Outlook:\n\n{text}"})
        elif decision.option(label) is None:
            ops.append({"op": "refuse", "why": f"#{number} has no option {label!r}"})
        else:
            ops += answer_ops(decision, decision.option(label), text)
    return ops + prompt_ops(prompt)


def plan_action(found, decisions, actor=None, expected=None):
    if found["n"] == 0:
        return plan([], found["t"], decisions, actor, expected)
    return plan([(found["n"], found["c"], found["t"])], "", decisions, actor, expected)


def read_issues(path):
    found = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(found, list):
        raise SystemExit(f"{path}: expected a list of issues")
    return found


def compose(args):
    issues = read_issues(args.issues)
    now = datetime.datetime.now(datetime.timezone.utc)
    digest = digest_id(now)
    decisions, done = decisions_in(issues), done_in(issues)
    found_card = card(args.repo, digest, decisions, done, args.action_url, args.to, args.originator, now)
    text = plain_text(args.repo, digest, decisions, done)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "card.json").write_text(json.dumps(found_card, indent=2) + "\n", encoding="utf-8")
    (out / "digest.html").write_text(html_body(found_card, text), encoding="utf-8")
    sender = args.sender or args.to
    (out / "digest.eml").write_bytes(bytes(message(args.repo, digest, found_card, text, args.to, sender, now)))
    print(f"{digest}: {len(done)} done, {len(decisions)} decisions; written to {out}, nothing sent")


def reply(args):
    decisions = decisions_in(read_issues(args.issues))
    found = parse_reply(Path(args.eml).read_bytes(), decisions)
    if found["d"] is None:
        raise SystemExit("not a reply to a digest: it names no digest id")
    answers = [(number, label, "") for number, label in found["answers"]]
    print(json.dumps(plan(answers, found["prompt"], decisions, args.actor, args.expected), indent=2))


def action(args):
    decisions = decisions_in(read_issues(args.issues))
    found = parse_action(Path(args.body).read_text(encoding="utf-8"))
    if found is None:
        raise SystemExit("not an answer from a digest's card")
    print(json.dumps(plan_action(found, decisions, args.actor, args.expected), indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    made = sub.add_parser("compose", help="write the digest's card, HTML and email to a folder; nothing is sent")
    made.add_argument("--issues", required=True)
    made.add_argument("--repo", required=True)
    made.add_argument("--to", required=True)
    made.add_argument("--sender", help="the From address; the recipient's own when omitted, a self-sent digest")
    made.add_argument("--action-url", required=True, help="the HTTPS endpoint the card's buttons post to")
    made.add_argument("--originator", help="the provider id Microsoft's dashboard gives, for a digest not sent to oneself")
    made.add_argument("--out", required=True)
    for name, helped in (("reply", "plan what a reply to a digest asks for"), ("action", "plan what a card's button posted")):
        read = sub.add_parser(name, help=helped)
        read.add_argument("--eml" if name == "reply" else "--body", required=True)
        read.add_argument("--issues", required=True)
        read.add_argument("--actor", help="who answered: the bearer token's sub, or the reply's From")
        read.add_argument("--expected", help="the digest's recipient; any other actor is refused")
    args = parser.parse_args(argv)
    {"compose": compose, "reply": reply, "action": action}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
