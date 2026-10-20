"""Render docs/research/beyond-cooperation/baseline-2026-10-15.md from the
record, so that every figure the prose quotes is the record's. Arguments:
the repository root. Prints what it assumed, for a check by eye."""

import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "tools"))
import profile  # noqa: E402

record = json.loads((root / "docs/research/beyond-cooperation/baseline-2026-10-15.json").read_text())
report = profile.report(record)
s, c, r, t, calls, tokens = (record[k] for k in ("seconds", "context", "reads", "calls", "calls", "tokens"))
by_tool = calls["by_tool"]
taken = record["ended_at"]
date, time = taken[:10], taken[11:16]

assert c["first"] == 120867, c["first"]
assert c["compactions"] == 1 and c["drops"] == 1, c
# The prose that depends on what happened in the thread, set by hand after a look at the record.
h = record["helpers"]
HELPERS = {1: "one helper transcript, the review agent's, whose calls are in the rows and whose context is not",
           2: "two helper transcripts, the review agent's and its own after a usage limit stopped it and it was resumed, whose calls are in the rows and whose context is not"}[h["transcripts"]]
own_output = tokens["output"] - h["output_tokens"]
rows_seconds = sum(row["seconds_in_tool"] for row in by_tool.values())
own_seconds = rows_seconds - h["seconds_in_tool"]
PROMPTS = (f"started by a brief and carrying {record['prompts']} prompts in all, the owner's messages, the coordinator's relays and the "
           f"harness's own notifications delivered as user turns, which the count does not tell apart")
FAILURES = None  # set below from the counts, or by hand when they differ from the known ones
failed = {name: row["failed"] for name, row in by_tool.items() if row["failed"]}
known = {"Bash": 2, "WebFetch": 3, "mcp__github__get_file_contents": 2, "mcp__github__update_pull_request": 1}
later = {"Bash": 2, "WebFetch": 11, "mcp__github__get_file_contents": 2, "mcp__github__update_pull_request": 1}
if failed == known:
    FAILURES = (f"Three of the {calls['failed']} failed calls were WebFetch calls to hosts this environment cannot resolve (dev.to, grith.ai, "
                "web.archive.org); two were shell commands, a wrong output path and a syntax slip, found and fixed in the same minute; two were "
                "the helper's reads of another repository the session's GitHub tools do not reach, and one a reviewer request GitHub refuses on one's own pull request.")
elif failed == later:
    FAILURES = (f"Eleven of the {calls['failed']} failed calls were WebFetch calls to hosts this environment cannot resolve (dev.to, grith.ai, "
                "web.archive.org, huggingface.co, alphaxiv.org, neurips.cc, datasets-server.huggingface.co, sites.google.com and "
                "mlanthology.org, the last eight while reading about MAST); two were shell commands, a wrong output path and a syntax slip, "
                "found and fixed in the same minute; two were the helper's reads of another repository the session's GitHub tools do not reach, and one a reviewer request GitHub "
                "refuses on one's own pull request.")
elif failed == {"Bash": 6, "WebFetch": 11, "mcp__github__get_file_contents": 2, "mcp__github__update_pull_request": 1}:
    FAILURES = (f"Eleven of the {calls['failed']} failed calls were WebFetch calls to hosts this environment cannot resolve (dev.to, grith.ai, "
                "web.archive.org, huggingface.co, alphaxiv.org, neurips.cc, datasets-server.huggingface.co, sites.google.com and "
                "mlanthology.org, the last eight while reading about MAST); six were shell commands, a wrong output path and a syntax slip "
                "early on, and later two edit scripts whose assertion did not find the text they were to replace, a rehearsal whose test "
                "failed and a test run before its fix, each found and fixed in the next call; two were the helper's reads of another "
                "repository the session's GitHub tools do not reach, and one a reviewer request GitHub refuses on one's own pull request.")
elif failed == {"Bash": 7, "WebFetch": 11, "mcp__github__get_file_contents": 2, "mcp__github__update_pull_request": 1}:
    FAILURES = (f"Eleven of the {calls['failed']} failed calls were WebFetch calls to hosts this environment cannot resolve (dev.to, grith.ai, "
                "web.archive.org, huggingface.co, alphaxiv.org, neurips.cc, datasets-server.huggingface.co, sites.google.com and "
                "mlanthology.org, the last eight while reading about MAST); seven were shell commands, a wrong output path and a syntax slip "
                "early on, and later two edit scripts whose assertion did not find the text they were to replace, a rehearsal whose test "
                "failed, a test run before its fix and a script of the reviewer's run without its arguments, each found and fixed in the "
                "next call; two were the helper's reads of another repository the session's GitHub tools do not reach, and one a reviewer "
                "request GitHub refuses on one's own pull request.")
else:
    sys.exit(f"failed by tool {failed} matches no known case: write the failures paragraph")
print("failed by tool:", failed)
print("unanswered:", calls["unanswered"], "prompts:", record["prompts"], "taken:", taken)

kb = lambda n: f"{n / 1024:,.0f}"
share = lambda a, b: f"{100 * a / b:.0f}"
rate = own_output / s["outside_tools"]
reread_share = share(r["reread_bytes"], r["bytes"])
unanswered = (" The one unanswered call is the command that took this profile, whose answer was not yet written when it read the file."
              if calls["unanswered"] == 1 else "")
if calls["unanswered"] not in (0, 1):
    print("WARNING: unanswered is", calls["unanswered"])

text = f"""# Baseline, 2026-10-15: the thread that wrote the instrument

Source: the thread "Symphony beyond cooperation" of the symphony Project, which profiled its own transcript; the record was taken on {date} and the page rendered from it the same day.

The record beside this page, baseline-2026-10-15.json, is the profile of the Claude Code cloud session that wrote tools/profile.py and this programme's plan, taken from its own transcript on {date} at {time} UTC, while the thread was still at work on what its reviews found, with `python3 tools/profile.py <transcript> --json baseline-2026-10-15.json`. The report the same command printed:

```
{report}```

How to read it, as a baseline of this project's own way of working:

- What the session is. A thread of a claude.ai Project in the cloud, {PROMPTS}, with {HELPERS}; the harness wrote {record['attachments']} attachment lines, hook output, reminders and its records of what it loaded, which the growth attribution cannot tell from the tools' answers they came with. The session's conversation was condensed once (the compaction, and the one drop), after a peak of {c['peak']:,} tokens; the last call carried {c['last']:,}.
- The start. The first API call carried {c['first']:,} tokens before any work: 43,468 read from the prompt cache, the part of the harness's own context that an earlier request with the same prefix had written, and 77,397 written for this call, the rest of the harness's context, the project's instructions (about 18,000 tokens), the Project's memory and the thread's first message; how they divide between the harness's prompt, its tools and the thread's content, the usage does not record. Every later call carried it, which is why {share(c['cached_share'], 1)} percent of the context tokens were cache reads and the uncached input over the whole session was {tokens['input']:,} tokens. The plan's section 5 says what that costs and what it is the first measure of.
- The time. Of {s['active']:,} active seconds, {s['in_tools']:,} were in tools, two at once counted once, and {s['outside_tools']:,} outside them, the model's and the harness's; the harness counted {s['thinking']:,} seconds of thinking. The session's own {own_output:,} output tokens (the record's {tokens['output']:,} less the helpers' {h['output_tokens']:,}) over those {s['outside_tools']:,} seconds are about {rate:.0f} tokens a second, which is the model writing: this thread's time went to its own output, thinking and text, and not to its tools. Per tool the seconds are summed and the helpers' calls are in the rows: of the {rows_seconds:,} seconds in the rows, {h['seconds_in_tool']:,} are the helpers' calls', and the session's own {own_seconds:,} against the {s['in_tools']:,}-second union say its calls seldom ran beside one another.
- The reading. {r['calls']:,} calls named {r['files_named']:,} files, {r['files']:,} of them distinct, {r['rereads']:,} of them files the session had read before; {r['partial']:,} calls read part of a file (head, tail, a sed range), the auto-mode instruction to read through the shell at work, and {record['shell']['filter']:,} shell commands were filters or here-document consumers (head and tail after a pipe, cat writing a file from a here-document). Of the {kb(r['bytes'])} KB the reads returned, {kb(r['reread_bytes'])} KB came back from calls that only re-read, about {reread_share} percent, which is the most a hashing index (the plan's section 2, last row) could have saved this session before its own cost is counted. {calls['repeated']:,} of the {calls['total']:,} tool calls repeated an earlier call exactly, MAST's step repetition read by code (the plan's section 3), an upper bound on waste.
- The context. It grew by {c['growth']:,} tokens over the session, {by_tool['Bash']['context_tokens_estimated']:,} of them attributed to the shell by the session's own calls (the shell's row, {by_tool['Bash']['calls']:,} calls returning {kb(by_tool['Bash']['result_bytes'])} KB, has the helpers' calls in it too); the rest to the notifications, the web and the tool search.
- The failures. {FAILURES}{unanswered}

What a baseline of one session cannot say: whether these figures are typical of the project's threads, which the profile trailer of the plan's step 1 answers over every commit, or what they would be under any arm of section 2, which is what the arms are for. And what this record cannot do: be made again, since the transcript it was read from lives in the session's container and is not kept; the tool's tests are the reproducible part, and a kept transcript (coordbench's harness keeps one per run) gives the first baseline that can be regenerated.
"""
out = root / "docs/research/beyond-cooperation/baseline-2026-10-15.md"
out.write_text(text, encoding="ascii")
print("rendered", out, len(text.splitlines()), "lines")
