#!/usr/bin/env python3
"""The report of the research programme beyond cooperation: one table per
question of docs/research/beyond-cooperation/README.md, section 2, each
arm's row against the baselines', with the outcome beside the cost
(section 6, step 3).

It reads only records committed in the programme's folder, so it spends no
token and the same folder always gives the same page:

- baseline-DATE.json, a record of tools/profile.py (schema
  symphony-profile/1), and beside it, where the work's outcome is known,
  baseline-DATE.outcome.json;
- runs/DATE-ARM/, an arm's run (step 4): its outcome.json and one record of
  tools/profile.py per transcript, each named *.profile.json.

An outcome (schema symphony-arm-outcome/1) says which question the arm
answers, how many tasks it ran and how many landed (the pull request
merged with its check green and no revert, or the task's tests passed),
how the rest failed, as counts of MAST's failure modes, or null where
nobody judged them, and in a line of its own where it comes from. Costs
are read per landed task, since fewer tokens is trivially reached by
doing nothing; every table carries the repeated calls
and the compactions beside its costs, the two MAST modes the records
measure (FM-1.3 and FM-1.4), so an arm that moves its cost into them shows
it.

Usage: python3 tools/profile_report.py FOLDER [--check]. It writes
FOLDER/report.md, or with --check exits 1, writing nothing, when that page
differs from what the records give."""

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import NamedTuple

PROFILE_SCHEMA = "symphony-profile/1"
OUTCOME_SCHEMA = "symphony-arm-outcome/1"
PAGE = "report.md"
RUN_FOLDER = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9][a-z0-9-]{0,62}")
BASELINE = re.compile(r"baseline-([0-9]{4}-[0-9]{2}-[0-9]{2})\.json")
ARM_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .,:/()+-]{0,79}")
# MAST's fourteen failure modes (section 3).
MODES = tuple(f"FM-{group}.{number}" for group, count in ((1, 5), (2, 6), (3, 3)) for number in range(1, count + 1))
# The questions of section 2, by the key an outcome names, in the page's order.
QUESTIONS = {"profiling": "Profiling", "context": "Context compression", "tools": "Decreased tool usage",
             "reading": "Decreased code reading through hashing and retrieval"}


class ReportError(Exception):
    """A record or an outcome the page cannot be made from."""


class Row(NamedTuple):
    """One line of a table: a baseline or an arm's run, its profile
    records and its outcome (None where it is not recorded)."""

    label: str
    question: str
    records: list
    outcome: object


# --- reading the folder -----------------------------------------------------------

def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        raise ReportError(f"{path}: {problem}") from problem


def whole(value, least=0):
    return isinstance(value, int) and not isinstance(value, bool) and value >= least


# The counts the report reads from a record, by their path in it. A record
# with no main transcript has an empty context block (tools/profile.py), so
# a count may be absent, and is then 0.
READ = (("calls", "total"), ("calls", "failed"), ("calls", "unanswered"), ("calls", "repeated"),
        ("tokens", "total"), ("estimated_usd",), ("seconds", "active"), ("seconds", "in_tools"),
        ("context", "first"), ("context", "peak"), ("context", "mean"), ("context", "cached_share"),
        ("context", "compactions"), ("context", "drops"), ("reads", "bytes"), ("reads", "reread_bytes"),
        ("reads", "rereads"), ("reads", "files_named"), ("reads", "partial"))


def count(value):
    """Whether a value is a count the page can print: a finite number not
    below 0, never JSON's true or false, nor the NaN and Infinity json
    reads."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def profile_record(path):
    record = read_json(path)
    if not isinstance(record, dict) or record.get("schema") != PROFILE_SCHEMA:
        raise ReportError(f"{path}: not a record of tools/profile.py ({PROFILE_SCHEMA})")
    for keys in READ:
        value = record
        for key in keys:
            value = value.get(key) if isinstance(value, dict) else "not a block"
        if value is not None and not count(value):
            raise ReportError(f"{path}: {'.'.join(keys)} must be a number not below 0")
    return record


def outcome_of(path, question=None):
    """An outcome file, checked: the question it answers (a baseline's is
    "baseline"), its arm's name, its tasks, those landed and the MAST
    modes counted, or null where they were not judged."""
    outcome = read_json(path)
    if not isinstance(outcome, dict) or outcome.get("schema") != OUTCOME_SCHEMA:
        raise ReportError(f"{path}: not an outcome ({OUTCOME_SCHEMA})")
    asked = outcome.get("question")
    allowed = (question,) if question else tuple(QUESTIONS)
    if asked not in allowed:
        raise ReportError(f"{path}: question must be {question or ' or '.join(QUESTIONS)}")
    if not isinstance(outcome.get("arm"), str) or not ARM_NAME.fullmatch(outcome["arm"]):
        raise ReportError(f"{path}: arm must be a name of 1 to 80 letters, digits and plain punctuation")
    if "modes" not in outcome:
        raise ReportError(f"{path}: modes must be given, null where they were not judged")
    tasks, landed, modes = outcome.get("tasks"), outcome.get("landed"), outcome["modes"]
    if not whole(tasks, 1) or not whole(landed) or landed > tasks:
        raise ReportError(f"{path}: tasks must be 1 or more and landed from 0 to tasks")
    if modes is not None and not (isinstance(modes, dict) and set(modes) <= set(MODES)
                                  and all(whole(count) for count in modes.values())):
        raise ReportError(f"{path}: modes must be null or counts of MAST's codes FM-1.1 to FM-3.3")
    if not isinstance(outcome.get("source"), str) or not outcome["source"].strip() or not outcome["source"].isascii():
        raise ReportError(f"{path}: source must say, in ASCII, where the outcome comes from")
    return outcome


def baselines(folder):
    rows = []
    for path in sorted(folder.glob("baseline-*.json")):
        found = BASELINE.fullmatch(path.name)
        if path.name.endswith(".outcome.json"):
            if not path.with_name(path.name.replace(".outcome.json", ".json")).exists():
                raise ReportError(f"{path}: an outcome with no record beside it")
            continue
        if not found:
            raise ReportError(f"{path}: a baseline's record is named baseline-YYYY-MM-DD.json")
        beside = path.with_name(f"baseline-{found[1]}.outcome.json")
        outcome = outcome_of(beside, "baseline") if beside.exists() else None
        rows.append(Row(f"baseline {found[1]}", "baseline", [profile_record(path)], outcome))
    return rows


def arm_runs(folder):
    rows = []
    for run in sorted(path for path in (folder / "runs").glob("*") if path.is_dir()):
        if not RUN_FOLDER.fullmatch(run.name):
            raise ReportError(f"{run}: a run's folder is named DATE-ARM, in lower case")
        outcome = outcome_of(run / "outcome.json")
        records = [profile_record(path) for path in sorted(run.glob("*.profile.json"))]
        if not records:
            raise ReportError(f"{run}: no *.profile.json record")
        rows.append(Row(f"{outcome['arm']} ({run.name})", outcome["question"], records, outcome))
    return rows


# --- the measures -----------------------------------------------------------------

def total(records, *keys):
    """A count summed over the records, by its path in the record."""
    found = 0
    for record in records:
        value = record
        for key in keys:
            value = value.get(key, 0) if isinstance(value, dict) else 0
        found += value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0
    return found


def mean(records, *keys):
    return total(records, *keys) / len(records)


def per_landed(row, amount):
    """An amount per landed task, None where the outcome is not recorded
    or nothing landed."""
    landed = row.outcome["landed"] if row.outcome else 0
    return amount / landed if landed else None


def modes_text(row):
    if row.outcome is None:
        return "not recorded"
    if row.outcome["modes"] is None:
        return "not judged"
    counted = [f"{code} x{count}" for code, count in sorted(row.outcome["modes"].items()) if count]
    return ", ".join(counted) or "none"


def number(value, places=0):
    if value is None:
        return "-"
    return f"{value:,.{places}f}"


def percent(part, whole_amount):
    return f"{100 * part / whole_amount:.0f}%" if whole_amount else "-"


def outcome_cells(row):
    landed = f"{row.outcome['landed']} of {row.outcome['tasks']}" if row.outcome else "not recorded"
    return [row.label, str(len(row.records)), landed, modes_text(row)]


def mast_cells(row):
    repeated, compactions = total(row.records, "calls", "repeated"), total(row.records, "context", "compactions")
    return [number(repeated), number(compactions)]


# Each question's own columns, after the outcome's and before MAST's.
COLUMNS = {
    "profiling": (("Tokens per landed task",
                   lambda row: number(per_landed(row, total(row.records, "tokens", "total")))),
                  ("USD per landed task", lambda row: number(per_landed(row, total(row.records, "estimated_usd")), 2)),
                  ("Active seconds per landed task",
                   lambda row: number(per_landed(row, total(row.records, "seconds", "active")))),
                  ("Share of active time in tools", lambda row: percent(total(row.records, "seconds", "in_tools"),
                                                                        total(row.records, "seconds", "active")))),
    "context": (("First context (mean)", lambda row: number(mean(row.records, "context", "first"))),
                ("Peak context (mean)", lambda row: number(mean(row.records, "context", "peak"))),
                ("Mean context (mean)", lambda row: number(mean(row.records, "context", "mean"))),
                ("Served from cache (mean)", lambda row: percent(mean(row.records, "context", "cached_share"), 1)),
                ("Drops", lambda row: number(total(row.records, "context", "drops")))),
    "tools": (("Calls per landed task", lambda row: number(per_landed(row, total(row.records, "calls", "total")), 1)),
              ("Failed per landed task",
               lambda row: number(per_landed(row, total(row.records, "calls", "failed")), 1)),
              ("Unanswered", lambda row: number(total(row.records, "calls", "unanswered")))),
    "reading": (("KB read per landed task",
                 lambda row: number(per_landed(row, total(row.records, "reads", "bytes") / 1024), 1)),
                ("KB re-read per landed task",
                 lambda row: number(per_landed(row, total(row.records, "reads", "reread_bytes") / 1024), 1)),
                ("Re-reads of files named", lambda row: percent(total(row.records, "reads", "rereads"),
                                                                total(row.records, "reads", "files_named"))),
                ("Partial reads", lambda row: number(total(row.records, "reads", "partial")))),
}
HEAD = ("Row", "Records", "Landed", "MAST modes judged")
MAST = ("Repeated calls (FM-1.3)", "Compactions (FM-1.4)")


# --- the page ---------------------------------------------------------------------

def table(question, rows):
    names = [*HEAD, *(name for name, _ in COLUMNS[question]), *MAST]
    lines = ["| " + " | ".join(names) + " |", "|" + " --- |" * len(names)]
    for row in rows:
        cells = [*outcome_cells(row), *(cell(row) for _, cell in COLUMNS[question]), *mast_cells(row)]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def page(folder):
    """The report's text, from the records in folder."""
    base, arms = baselines(folder), arm_runs(folder)
    lines = ["# The report: each arm against the baseline", "",
             "Source: generated by tools/profile_report.py from the records in this folder (README.md, section 6, "
             "step 3); do not edit it by hand. Regenerate it with `python3 tools/profile_report.py "
             "docs/research/beyond-cooperation`; the checks fail when it differs from what the records give.", "",
             "Each table answers one question of section 2. The baselines come first, then each arm's runs, "
             "oldest first. A row's costs are per landed task (the pull request merged with its check green and "
             "no revert, or the task's tests passed), so a row whose outcome is not recorded, or where nothing "
             "landed, shows none; the means are over the row's records, one per transcript. Repeated calls and "
             "compactions stand beside every cost, the two MAST failure modes the records measure (section 3): "
             "an arm that lowers a cost by raising them has moved the cost, not removed it.", ""]
    for key, title in QUESTIONS.items():
        rows = base + [row for row in arms if row.question == key]
        lines += [f"## {title}", ""]
        lines += table(key, rows) if rows else ["No record yet."]
        if not any(row.question == key for row in arms):
            lines += ["", "No arm has run for this question yet (section 6, steps 4 and 5)."]
        lines.append("")
    lines += ["## Where each row comes from", ""]
    lines += [f"- {row.label}: {' '.join(row.outcome['source'].split())}" if row.outcome
              else f"- {row.label}: no outcome recorded" for row in base + arms]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--check", action="store_true", help=f"exit 1 when {PAGE} is not what the records give")
    args = parser.parse_args(argv)
    try:
        text = page(args.folder)
    except ReportError as problem:
        print(f"profile_report: {problem}", file=sys.stderr)
        return 2
    target = args.folder / PAGE
    if args.check:
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current != text:
            print(f"profile_report: {target} is not what the records give; run python3 tools/profile_report.py "
                  f"{args.folder}", file=sys.stderr)
            return 1
        return 0
    target.write_text(text, encoding="ascii")
    print(f"profile_report: {target} written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
