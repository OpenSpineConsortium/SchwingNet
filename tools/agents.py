"""The agents this repository runs, and how one is brought in from elsewhere.

An agent is a Claude Code subagent definition: one Markdown file under
.claude/agents/, its name, a one-line description, the tools it may use
and the model it runs on in a front matter, and its instructions as the
body (docs/agents/AGENTS.md). A session here can hand work to any of them
by name; .github/workflows/agents.yml runs one in GitHub Actions as the
whole session (`claude --agent NAME`), on a pull request or by hand; a
worker in Actions runs under one when the registry below says so; and
coordbench and flowbench take the same file, so the agent a repository
uses for its work is the agent a benchmark measures.

The registry is .github/symphony/agents.json: for each agent its purpose
(review, develop, test or other), where it came from, the sha256 of the
file as it came, when it runs in Actions, and the workers in Actions that
run under it. Which Claude tokens an agent's runs may take is not here:
it is .github/symphony/accounts.json under the agent's name, the Tokens
tab's file (tools/pool.py), so an agent's name may not also be a
worker's.

  python3 tools/agents.py check                    every agent and the registry hold together
  python3 tools/agents.py list                     the agents, as JSON, for the console
  python3 tools/agents.py import SOURCE [--name N] [--purpose P] [--runs R]
  python3 tools/agents.py update NAME              fetch an imported agent's source again
  python3 tools/agents.py own NAME                 keep a hand-edited import as this repository's own
  python3 tools/agents.py remove NAME
  python3 tools/agents.py runs-on pull_request     the agents that run on that event, as a JSON list
  python3 tools/agents.py for-worker NAME          the agent a worker in Actions runs under, or nothing
  python3 tools/agents.py allowed-tools NAME       its tools as one --allowedTools word, for Actions
  python3 tools/agents.py export NAME [--out FILE] the agent as `claude --agents` JSON, for a benchmark

A SOURCE is a GitHub file, OWNER/REPO/PATH[@REF] (REF defaults to the
repository's default branch), an https address of the raw file, or a
local path. It is read with no credential: a file in a private
repository is copied by hand, or with the person's own `gh`, and then
imported by its local path. An imported agent must list its tools, may
not bypass permissions, and may carry neither hooks nor MCP servers,
since each would run something no reviewer saw in the agent's own text;
it lands by pull request, where code-owner review covers .claude/.
"""

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = Path(".claude") / "agents"
REGISTRY = Path(".github") / "symphony" / "agents.json"
WORKERS_DIR = Path(".github") / "symphony" / "workers"
VERSION = 1
NAME = re.compile(r"^[a-z0-9](?:[a-z0-9]|-(?=[a-z0-9])){0,38}$")
PURPOSES = ("review", "develop", "test", "other")
RUNS = ("manual", "pull_request")
BUILTIN = "symphony"
LOCAL = "local"
MODEL = re.compile(r"^(inherit|fable|opus|sonnet|haiku|claude-[a-z0-9.-]{1,60}(\[1m\])?)$")
TOOL = re.compile(r"^(mcp__[A-Za-z0-9_-]+|[A-Z][A-Za-z0-9_]*(\([^()\"'\\\n]{1,200}\))?)$")
GITHUB_SOURCE = re.compile(r"^([A-Za-z0-9-]{1,39})/([A-Za-z0-9._-]{1,100})/([^@\s]+\.md)(?:@([A-Za-z0-9._/-]{1,200}))?$")
MAX_BYTES = 64 * 1024
KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# The only front matter an imported agent may carry: anything else,
# hooks, MCP servers and permission modes among them, could run what its
# text does not show, and an allowlist does not miss a spelling YAML reads
# that a blocklist would.
IMPORTED_KEYS = ("name", "description", "tools", "model", "color")
COLOR = re.compile(r"^[a-z]{1,20}$")
FETCH_TIMEOUT = 30
# Typography that imported files often carry and the ASCII rule refuses
# (.claude/rules/writing.md); anything else outside ASCII is refused.
PLAIN = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": " - ",
         "\u2026": "...", "\u00a0": " ", "\u2022": "-", "\u2192": "->", "\r\n": "\n"}


class AgentError(Exception):
    """Why an agent or the registry does not hold together."""


# Reading an agent's file.

def split_front_matter(text):
    """The front matter's lines and the body; an agent's file opens on ---.
    Only a line that is exactly --- opens or closes it, as YAML front
    matter is read: an indented --- inside a value must not end it here
    while Claude Code reads on past it."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        raise AgentError("the file must open with a front matter between two lines of ---")
    for index in range(1, len(lines)):
        if lines[index].rstrip() == "---":
            return lines[1:index], "\n".join(lines[index + 1:])
    raise AgentError("the front matter has no closing ---")


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def parse_front_matter(lines):
    """The simple YAML Claude Code's agent files use: key: value lines, a
    list as "- item" lines under a key with no value, and nested blocks,
    which are kept as present but not read."""
    fields, key = {}, None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t":
            if key is None:
                raise AgentError(f"an indented line comes before any key: {line.strip()}")
            item = line.strip()
            if item.startswith("- ") and isinstance(fields[key], list):
                fields[key].append(unquote(item[2:]))
            else:
                fields[key] = {"nested": True}
            continue
        if ":" not in line:
            raise AgentError(f"a front matter line is not key: value: {line.strip()}")
        key, value = line.split(":", 1)
        key = key.strip()
        if not KEY.match(key):
            raise AgentError(f"{key!r} is not a plain key; quoted keys and merge keys are not read here")
        if key in fields:
            raise AgentError(f"{key} is given twice")
        value = value.strip()
        fields[key] = unquote(value) if value else []
    return fields


def tool_list(value):
    if isinstance(value, list):
        return [unquote(tool) for tool in value]
    if isinstance(value, str):
        return [tool.strip() for tool in value.split(",") if tool.strip()]
    return None


def read_agent(text, imported=False):
    """The agent a file defines, checked, as a dict: name, description,
    tools (None means every tool the session has), model and prompt."""
    lines, body = split_front_matter(text)
    fields = parse_front_matter(lines)
    problems = []
    name = fields.get("name")
    if not isinstance(name, str) or not NAME.match(name):
        problems.append("name must be lower case letters, digits and inner dashes, up to 39")
    description = fields.get("description")
    if not isinstance(description, str) or not description.strip():
        problems.append("description must say in one line when to use the agent")
    tools = tool_list(fields["tools"]) if "tools" in fields else None
    if "tools" in fields and tools is None:
        problems.append("tools must be a comma-separated line or a list")
    for tool in tools or []:
        if not TOOL.match(tool):
            problems.append(f"{tool!r} is not a tool's name")
    if not tools:
        problems.append("tools must list what the agent may use, so its reviewer sees it and a run in Actions allows nothing else")
    model = fields.get("model", "inherit")
    if not isinstance(model, str) or not MODEL.match(model):
        problems.append("model must be inherit, fable, opus, sonnet, haiku or a claude- model id")
    if imported:
        for key in sorted(set(fields) - set(IMPORTED_KEYS)):
            problems.append(f"an imported agent may not carry {key}; it may carry only " + ", ".join(IMPORTED_KEYS))
        if "color" in fields and not (isinstance(fields["color"], str) and COLOR.match(fields["color"])):
            problems.append("color must be a plain colour name")
    if not body.strip():
        problems.append("the body, the agent's instructions, is empty")
    if problems:
        raise AgentError("; ".join(problems))
    return {"name": name, "description": description.strip(), "tools": tools, "model": model,
            "prompt": body.strip() + "\n"}


def plain_text(text):
    """The text in ASCII with LF, as the repository keeps every file under
    .claude/, or an AgentError naming the first character that is not."""
    for fancy, plain in PLAIN.items():
        text = text.replace(fancy, plain)
    for number, line in enumerate(text.split("\n"), 1):
        for character in line:
            if ord(character) > 127 or (ord(character) < 32 and character != "\t"):
                raise AgentError(f"line {number} holds {character!r}, which is not ASCII; "
                                 "edit it out of a local copy and import that")
    return text if text.endswith("\n") else text + "\n"


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# The registry.

def load_registry(root):
    path = root / REGISTRY
    if not path.exists():
        return {"version": VERSION, "agents": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AgentError(f"{REGISTRY}: not JSON ({error})")
    if not isinstance(data, dict) or not isinstance(data.get("agents"), dict):
        raise AgentError(f'{REGISTRY}: must be {{"version": {VERSION}, "agents": {{...}}}}')
    return data


def save_registry(root, data):
    data["agents"] = dict(sorted(data["agents"].items()))
    (root / REGISTRY).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def worker_names(root):
    folder = root / WORKERS_DIR
    return sorted(path.stem for path in folder.glob("*.json")) if folder.is_dir() else []


def entry_problems(name, entry, workers):
    problems = []
    if not isinstance(entry, dict):
        return ["its entry must be an object"]
    known = {"purpose", "source", "sha256", "runs", "workers", "imported"}
    for key in sorted(set(entry) - known):
        problems.append(f"{key} is not a setting an agent has; the settings are " + ", ".join(sorted(known)))
    if entry.get("purpose") not in PURPOSES:
        problems.append("purpose must be one of " + ", ".join(PURPOSES))
    if entry.get("runs", "manual") not in RUNS:
        problems.append("runs must be one of " + ", ".join(RUNS))
    elif entry.get("runs") == "pull_request" and entry.get("purpose") == "develop":
        problems.append("a developer writes code, so it runs as a worker in Actions (workers), never on pull requests")
    source = entry.get("source")
    if not isinstance(source, str) or not source:
        problems.append(f"source must be {BUILTIN}, {LOCAL} or where it was imported from")
    elif source not in (BUILTIN, LOCAL) and not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", ""))):
        problems.append("an imported agent records the sha256 of its file as it came")
    runners = entry.get("workers", [])
    if not isinstance(runners, list) or not all(isinstance(w, str) for w in runners):
        problems.append("workers must be a list of names of workers in Actions")
    else:
        for worker in runners:
            if worker not in workers:
                problems.append(f"workers names {worker}, which .github/symphony/workers/ does not register")
    if name in workers:
        problems.append(f"{name} is also a worker's name: .github/symphony/accounts.json gives tokens by name, "
                        "so an agent and a worker may not share one")
    return problems


def check(root):
    """Every problem with the agents and the registry, one "path: problem" each."""
    problems = []
    try:
        data = load_registry(root)
    except AgentError as error:
        return [str(error)]
    workers = worker_names(root)
    folder = root / AGENTS_DIR
    files = {path.stem: path for path in folder.glob("*.md")} if folder.is_dir() else {}
    for path in sorted(folder.rglob("*.md")) if folder.is_dir() else []:
        if path.parent != folder:
            problems.append(f"{path.relative_to(root).as_posix()}: agents live directly under {AGENTS_DIR}, "
                            "where the check reads them; Claude Code would load this one unchecked")
    claimed = {}
    for name, entry in data["agents"].items():
        for problem in entry_problems(name, entry, workers):
            problems.append(f"{REGISTRY}: {name}: {problem}")
        if name not in files:
            problems.append(f"{REGISTRY}: {name}: there is no {AGENTS_DIR / (name + '.md')}")
        for worker in entry.get("workers", []) if isinstance(entry, dict) else []:
            if worker in claimed:
                problems.append(f"{REGISTRY}: {worker} runs under both {claimed[worker]} and {name}")
            claimed[worker] = name
    for name, path in sorted(files.items()):
        rel = path.relative_to(root).as_posix()
        entry = data["agents"].get(name)
        if entry is None:
            problems.append(f"{rel}: not in {REGISTRY}; add it with its purpose, or import it with tools/agents.py")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        imported = isinstance(entry, dict) and entry.get("source") not in (BUILTIN, LOCAL)
        try:
            agent = read_agent(text, imported=imported)
        except AgentError as error:
            problems.append(f"{rel}: {error}")
            continue
        if agent["name"] != name:
            problems.append(f"{rel}: its name is {agent['name']}, and the file must be named for it")
        if len(text.encode("utf-8")) > MAX_BYTES:
            problems.append(f"{rel}: over {MAX_BYTES // 1024} KB")
        if imported and sha256(text) != entry.get("sha256"):
            problems.append(f"{rel}: changed since it was imported from {entry['source']}; "
                            f"`python3 tools/agents.py update {name}` takes the source again, "
                            f"`python3 tools/agents.py own {name}` keeps the edit as this repository's own")
    return problems


# Bringing an agent in.

def source_url(source):
    """The address a SOURCE is read from, or None for a local path."""
    if source.startswith("https://"):
        return source
    if source.startswith("http://"):
        raise AgentError("an agent is read over https only")
    match = GITHUB_SOURCE.match(source)
    if match and not Path(source).exists():
        owner, repo, path, ref = match.groups()
        if ".." in path.split("/") or ".." in (ref or "").split("/"):
            raise AgentError(f"{source}: a path or ref with .. is refused, so the source recorded is the one read")
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref or 'HEAD'}/{path}"
    return None


class HttpsOnlyRedirects(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to https, so the https rule holds after one."""

    def redirect_request(self, request, fp, code, message, headers, new_url):
        if not new_url.startswith("https://"):
            raise AgentError(f"{request.full_url} redirects to {new_url}, which is not https")
        return super().redirect_request(request, fp, code, message, headers, new_url)


def https_only_opener():
    return urllib.request.build_opener(HttpsOnlyRedirects)


def fetch(source, opener=None):
    """The text of the agent at SOURCE, read with no credential."""
    url = source_url(source)
    if url is None:
        path = Path(source)
        if not path.is_file():
            raise AgentError(f"{source}: no such file, and not OWNER/REPO/PATH.md[@REF] or an https address")
        data = path.read_bytes()
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "symphony-agents"})
        try:
            with (opener or https_only_opener().open)(request, timeout=FETCH_TIMEOUT) as response:
                data = response.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise AgentError(f"{url}: GitHub answered {error.code}; a private repository's file is "
                             "copied by hand and imported by its local path")
        except (urllib.error.URLError, OSError) as error:
            raise AgentError(f"{url}: could not be read ({error})")
    if len(data) > MAX_BYTES:
        raise AgentError(f"{source}: over {MAX_BYTES // 1024} KB, too long for an agent")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise AgentError(f"{source}: not UTF-8 text")


def renamed(text, name):
    """The text with its front matter's name line set to NAME."""
    lines = text.split("\n")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            break
        if re.match(r"^name\s*:", lines[index]):
            lines[index] = f"name: {name}"
            return "\n".join(lines)
    raise AgentError("the front matter has no name to change")


def import_agent(root, source, name=None, purpose=None, runs="manual", opener=None, now=None):
    """Write the agent at SOURCE under .claude/agents/ and record it; the
    agent's name, or the error that says why it was not brought in."""
    text = plain_text(fetch(source, opener))
    agent = read_agent(text, imported=True)
    if name and name != agent["name"]:
        if not NAME.match(name):
            raise AgentError("--name must be lower case letters, digits and inner dashes, up to 39")
        text = renamed(text, name)
        agent = read_agent(text, imported=True)
    name = agent["name"]
    data = load_registry(root)
    old = data["agents"].get(name)
    if old and old.get("source") != source:
        raise AgentError(f"{name} is already here, from {old.get('source')}; import it under another --name")
    entry = dict(old or {})
    entry.update({"purpose": purpose or entry.get("purpose") or guess_purpose(agent), "source": source,
                  "sha256": sha256(text), "runs": runs if runs != "manual" or not old else entry.get("runs", "manual"),
                  "imported": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")})
    entry.setdefault("workers", [])
    problems = entry_problems(name, entry, worker_names(root))
    if problems:
        raise AgentError("; ".join(problems))
    (root / AGENTS_DIR).mkdir(parents=True, exist_ok=True)
    (root / AGENTS_DIR / f"{name}.md").write_text(text, encoding="utf-8")
    data["agents"][name] = entry
    save_registry(root, data)
    return name


def guess_purpose(agent):
    words = (agent["name"] + " " + agent["description"]).lower()
    for purpose, hints in (("review", ("review", "audit", "critic")), ("test", ("test", "qa", "verif")),
                           ("develop", ("develop", "implement", "build", "code", "fix"))):
        if any(hint in words for hint in hints):
            return purpose
    return "other"


def entry_of(root, name):
    data = load_registry(root)
    if name not in data["agents"]:
        raise AgentError(f"{name}: no such agent in {REGISTRY}")
    return data, data["agents"][name]


def update_agent(root, name, opener=None):
    _, entry = entry_of(root, name)
    if entry.get("source") in (BUILTIN, LOCAL):
        raise AgentError(f"{name} is this repository's own; it has no source to fetch")
    return import_agent(root, entry["source"], name=name, purpose=entry.get("purpose"),
                        runs=entry.get("runs", "manual"), opener=opener)


def own_agent(root, name):
    data, entry = entry_of(root, name)
    entry["source"] = LOCAL
    entry.pop("sha256", None)
    save_registry(root, data)


def remove_agent(root, name):
    data, _ = entry_of(root, name)
    del data["agents"][name]
    save_registry(root, data)
    path = root / AGENTS_DIR / f"{name}.md"
    if path.exists():
        path.unlink()


# What the workflows, the console and the benchmarks read.

def listing(root):
    data = load_registry(root)
    found = []
    for name, entry in data["agents"].items():
        path = root / AGENTS_DIR / f"{name}.md"
        try:
            agent = read_agent(path.read_text(encoding="utf-8"), imported=entry.get("source") not in (BUILTIN, LOCAL))
        except (OSError, AgentError):
            agent = {"description": "", "tools": None, "model": ""}
        found.append({"name": name, "purpose": entry.get("purpose"), "source": entry.get("source"),
                      "runs": entry.get("runs", "manual"), "workers": entry.get("workers", []),
                      "description": agent["description"], "tools": agent["tools"], "model": agent["model"]})
    return found


def runs_on(root, event):
    return [name for name, entry in load_registry(root)["agents"].items() if entry.get("runs", "manual") == event]


def for_worker(root, worker):
    for name, entry in load_registry(root)["agents"].items():
        if worker in entry.get("workers", []):
            return name
    return ""


def allowed_tools(root, name):
    """The agent's tools as Claude Code's --allowedTools takes them, so a
    run in Actions, which cannot ask, may use what the agent lists and
    nothing else; empty for an agent that lists none."""
    _, entry = entry_of(root, name)
    path = root / AGENTS_DIR / f"{name}.md"
    agent = read_agent(path.read_text(encoding="utf-8"), imported=entry.get("source") not in (BUILTIN, LOCAL))
    return ",".join(agent["tools"] or [])


def export(path_or_name, root=ROOT):
    """The agent as the JSON `claude --agents` reads, {name: {description,
    prompt, tools, model}}, from a file or the name of one here."""
    path = Path(path_or_name)
    if not path.is_file():
        path = root / AGENTS_DIR / f"{path_or_name}.md"
    if not path.is_file():
        raise AgentError(f"{path_or_name}: no agent file there and no agent of that name")
    agent = read_agent(path.read_text(encoding="utf-8"))
    definition = {"description": agent["description"], "prompt": agent["prompt"]}
    if agent["tools"]:
        definition["tools"] = agent["tools"]
    if agent["model"] != "inherit":
        definition["model"] = agent["model"]
    return {agent["name"]: definition}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=str(ROOT))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    commands.add_parser("list")
    importing = commands.add_parser("import")
    importing.add_argument("source")
    importing.add_argument("--name")
    importing.add_argument("--purpose", choices=PURPOSES)
    importing.add_argument("--runs", choices=RUNS, default="manual")
    for command in ("update", "own", "remove", "for-worker", "allowed-tools"):
        commands.add_parser(command).add_argument("name")
    commands.add_parser("runs-on").add_argument("event", choices=RUNS)
    exporting = commands.add_parser("export")
    exporting.add_argument("name")
    exporting.add_argument("--out")
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        if args.command == "check":
            problems = check(root)
            for problem in problems:
                print(problem, file=sys.stderr)
            if problems:
                return 1
            print(f"agents ok: {len(load_registry(root)['agents'])}")
        elif args.command == "list":
            print(json.dumps(listing(root), indent=2))
        elif args.command == "import":
            print(import_agent(root, args.source, args.name, args.purpose, args.runs))
        elif args.command == "update":
            print(update_agent(root, args.name))
        elif args.command == "own":
            own_agent(root, args.name)
        elif args.command == "remove":
            remove_agent(root, args.name)
        elif args.command == "runs-on":
            print(json.dumps(runs_on(root, args.event)))
        elif args.command == "for-worker":
            print(for_worker(root, args.name))
        elif args.command == "allowed-tools":
            print(allowed_tools(root, args.name))
        elif args.command == "export":
            text = json.dumps(export(args.name, root), indent=2) + "\n"
            if args.out:
                Path(args.out).write_text(text, encoding="utf-8")
            else:
                sys.stdout.write(text)
    except AgentError as error:
        print(f"agents: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
