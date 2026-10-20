"""A stand-in for the GitHub CLI, for tests that run scripts calling gh.

No test has a signed-in gh or the network, so install() writes an executable
named gh into a folder the test puts first on PATH; it runs respond() below.
Each call is appended as one JSON line to the file FAKE_GH_LOG names: its
arguments, the key it was answered by, and what it read from stdin: a body
given with `--input -`, or the value a `secret set` or `variable set` with no
--body takes from the pipe. Answers come from the JSON file FAKE_GH_ROUTES names, a map
from a key to a list of answers {status, headers, body} given in order, the
last repeated: "METHOD path" for `gh api` (the query is part of the path),
or the leading words of any other command, such as "pr merge" or
"--version". The body is printed as it is, after the status line, the
headers and a blank line when the call asks with --include, as gh prints
them, and not at all for a call with --silent, which gh 2.89.0 keeps quiet
even when the call is refused; a route for a call with --jq gives the body
gh would print after the filter. The fake exits 1 when the status is 400
or more, as gh does, and prints a line naming the status on standard
error, where gh prints GitHub's answer; an answer may carry "stderr" to
print there instead, for a failure gh reports itself, such as a flag it
does not know. A call with no route answers 599 "fake gh: no route for
...", so an unexpected call fails the test that made it. An answer may
carry "after", routes that take the place of those of the same keys once
it is given, so a call that changes GitHub, such as a merge, changes what
later reads see.

A process per call costs tens of milliseconds, which hundreds of calls turn
into a slow suite, so routed_run() gives a test the same answers without
the process: it stands in for subprocess.run for gh alone. This module is a
helper, not a test module: discovery passes it by.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# gh api's options that take a value, so the path is told from the values.
VALUED = {"--method", "-X", "-H", "--header", "--input", "--jq", "-q", "-f", "--raw-field", "-F", "--field",
          "--hostname", "--template", "-t", "--cache"}
SCRIPT = """
import sys
sys.path.insert(0, {folder!r})
from fake_gh import main
main()
"""


def api_key(args):
    method, path, rest = "GET", None, iter(args[1:])
    for arg in rest:
        if arg in ("--method", "-X"):
            method = next(rest)
        elif arg in VALUED:
            next(rest)
        elif not arg.startswith("-") and path is None:
            path = arg
    return method + " " + (path or "")


def command_key(args):
    if args[0].startswith("-") or len(args) < 2 or args[1].startswith("-"):
        return args[0]
    return args[0] + " " + args[1]


def key_of(args):
    return api_key(args) if args[0] == "api" else command_key(args)


def logged_count(log, key):
    if not os.path.exists(log):
        return 0
    with open(log, encoding="utf-8") as handle:
        return sum(1 for line in handle if json.loads(line)["key"] == key)


def respond(args, stdin, log, routes_file):
    """One call answered as gh would: (exit code, stdout, stderr)."""
    args = list(args) or [""]
    key = key_of(args)
    seen = logged_count(log, key)
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"args": args, "key": key, "stdin": stdin}) + "\n")
    with open(routes_file, encoding="utf-8") as handle:
        answers = json.load(handle).get(key)
    if answers:
        chosen = answers[min(seen, len(answers) - 1)]
    else:
        chosen = {"status": 599, "body": {"message": "fake gh: no route for " + key}}
    if chosen.get("after"):
        changed(routes_file, chosen["after"])
    status = chosen.get("status", 200)
    body = chosen.get("body")
    text = body if isinstance(body, str) else ("" if body is None else json.dumps(body))
    if args[0] == "api" and "--silent" in args:
        text = ""
    if args[0] == "api" and "--include" in args:
        head = ["HTTP/2.0 %d FAKE" % status] + ["%s: %s" % item for item in (chosen.get("headers") or {}).items()]
        text = "\r\n".join(head) + "\r\n\r\n" + text
    error = chosen.get("stderr") or ("gh: fake answer (HTTP %d)\n" % status if status >= 400 else "")
    return (1 if status >= 400 else 0), text, error


def changed(routes_file, after):
    """The routes as a call left them: after's keys answered anew."""
    with open(routes_file, encoding="utf-8") as handle:
        routes = json.load(handle)
    routes.update(after)
    with open(routes_file, "w", encoding="utf-8") as handle:
        json.dump(routes, handle)


def reads_stdin(args):
    """Whether gh would read its standard input: a body given as --input -,
    or a secret or variable set with no --body, which gh takes from the pipe
    when no terminal is attached (scripts/tokens.py sends a token that way)."""
    if "--input" in args and args[args.index("--input") + 1] == "-":
        return True
    return args[:2] in (["secret", "set"], ["variable", "set"]) and not {"--body", "-b"} & set(args)


def main():
    args = sys.argv[1:] or [""]
    stdin = sys.stdin.read() if reads_stdin(args) else None
    code, out, err = respond(args, stdin, os.environ["FAKE_GH_LOG"], os.environ["FAKE_GH_ROUTES"])
    sys.stdout.write(out)
    sys.stderr.write(err)
    sys.exit(code)


def install(folder):
    """Write the fake gh into folder/bin and return that folder."""
    bin_dir = Path(folder) / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    gh = bin_dir / "gh"
    script = SCRIPT.format(folder=str(Path(__file__).resolve().parent))
    gh.write_text(f"#!{sys.executable} -IS\n" + script, encoding="utf-8")
    gh.chmod(0o755)
    return bin_dir


def write_routes(path, routes):
    Path(path).write_text(json.dumps(routes), encoding="utf-8")


def environment(folder, routes):
    """The variables a test runs under: the fake first on PATH, its log and
    its routes, which are written here."""
    folder = Path(folder)
    bin_dir = install(folder)
    write_routes(folder / "routes.json", routes)
    return {
        "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
        "FAKE_GH_LOG": str(folder / "gh-log.jsonl"),
        "FAKE_GH_ROUTES": str(folder / "routes.json"),
    }


def routed_run(real_run, log, routes_file):
    """A stand-in for subprocess.run that answers gh as the fake does, in
    this process, and runs every other command as it is."""
    def run(command, *args, **options):
        if not command or command[0] != "gh":
            return real_run(command, *args, **options)
        code, out, err = respond(command[1:], options.get("input"), log, routes_file)
        return subprocess.CompletedProcess(command, code, out.replace("\r\n", "\n"), err)
    return run


def calls(log_path):
    """Every call the fake answered, in order: args, key, stdin, and the
    body as JSON when stdin held one."""
    path = Path(log_path)
    if not path.exists():
        return []
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        call = json.loads(line)
        call["body"] = None
        if call.get("stdin"):
            try:
                call["body"] = json.loads(call["stdin"])
            except ValueError:
                pass
        found.append(call)
    return found


def answer(status=200, body=None, headers=None, after=None, stderr=None):
    """One answer, for a route's list; after, routes it puts in place;
    stderr, what gh prints on standard error in place of the fake's line."""
    found = {"status": status, "body": body, "headers": headers or {}}
    if after:
        found["after"] = after
    if stderr:
        found["stderr"] = stderr
    return found
