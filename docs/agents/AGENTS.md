# Agents

An agent is a set of instructions with the tools it may use, which a Claude session runs as: a reviewer, a developer, a tester, or whatever a team writes or brings in. Here an agent is a Claude Code subagent file under .claude/agents/, so every session in this repository can hand it work by name, the Agents workflow runs it in GitHub Actions, a worker in Actions can run under it, and coordbench and flowbench measure the same file. One file serves the work and the benchmark, which is what makes this repository both a place to develop code and a place to compare agents on it.

## The file

```
---
name: reviewer
description: Reviews one pull request for correctness and the repository's rules. Use for code review.
tools: Read, Grep, Glob, Bash(git:*), Bash(gh pr diff:*), Bash(gh pr review:*)
model: inherit
---

The agent's instructions, as plain prose.
```

- name: lower case letters, digits and inner dashes, up to 39, and the file is `.claude/agents/<name>.md`. It may not be a worker's name, since .github/symphony/accounts.json gives Claude tokens by name to agents and workers alike.
- description: one line saying when to use it; a session reads it to decide which agent to hand work to.
- tools: the tools it may use, a comma-separated line or a list, in Claude Code's names (`Read`, `Bash(git:*)`, `mcp__server__tool`); every agent lists them. In Actions, where no one can answer a prompt, these are the only tools the run allows. A grant of an interpreter, `Bash(python3:*)` or `Bash(bash:*)`, lets the agent run anything, so the reviewer has none and reads only through git and gh.
- model: `inherit`, `fable`, `opus`, `sonnet`, `haiku` or a model id. A token's tile on the Tokens tab, when it sets a model, wins over this in Actions; a benchmark always runs its own model, so that only the instructions and tools differ between arms.

Claude Code reads other keys too (permissionMode, hooks, mcpServers, skills); an agent written here may use them, an imported one may carry only name, description, tools, model and color, below. Every key is a plain word: a quoted key or a merge key is refused, since YAML would read it as another key, and only a line that is exactly `---` opens or closes the front matter. An agent lives directly under .claude/agents/; a file in a folder below it fails the check, since Claude Code would load it unchecked.

## The registry

.github/symphony/agents.json says what each agent is for and where it came from:

```
{"version": 1, "agents": {
  "reviewer": {"purpose": "review", "source": "symphony", "runs": "manual", "workers": []}
}}
```

- purpose: review, develop, test or other, so the console groups the agents and a person can give each purpose its own tokens.
- source: `symphony` for the agents the template brings, `local` for one written here, or where an imported one came from, with the sha256 of its file as it came.
- runs: `manual` (sessions and Run workflow only) or `pull_request` (the Agents workflow runs it on every pull request opened, reopened or marked ready, drafts and forks left out); a developer is never `pull_request`. The template's agents all say manual, so none spends a token until someone switches it on.
- workers: workers in Actions (.github/symphony/workers/) that run under this agent: workers.yml starts their sessions with `--agent <name>`, the worker prompt still the task. A worker runs under one agent at most.

`bash scripts/check.sh` holds every file and entry to these rules (`python3 tools/agents.py check`), and an imported agent to its sha256, so a hand edit is a choice: `python3 tools/agents.py update NAME` takes the source again, `python3 tools/agents.py own NAME` keeps the edit as this repository's own.

## The agents the template brings

- reviewer (review): reads one pull request through gh, holds it to the claim protocol and the rules, traces each finding to a real path before reporting it, reads what the required check reported, and posts one review. It never runs the pull request's code, pushes or merges, and its tools allow none of those.
- developer (develop): takes one issue through the claim protocol, from the claim to a ready pull request that passes the check.
- tester (test): runs the checks and the nearest tests on a pull request, writes the tests the change is missing, and reports failures with how to reproduce them, as a comment and a patch.

## Bringing your own

An agent comes in from another repository, from an address, or from a file, always by pull request:

- From a clone: `python3 tools/agents.py import OWNER/REPO/PATH.md[@REF] [--name N] [--purpose P]`, or an https address of the raw file, or a local path; then commit .claude/agents/<name>.md and .github/symphony/agents.json in a pull request.
- From GitHub: Actions, the Agents workflow, Run workflow, with "import" set to the source. The run imports it on the default branch and opens the pull request from symphony/agent-<name>.
- From the console: the Agents tab's Import box, which starts that same run.

An agent is read with no credential, over https only, redirects included, so a private repository's file is copied by hand, or with your own `gh`, and imported by its local path; a source with `..` in its path or ref is refused, so the source recorded is the one read. An imported agent carries only name, description, tools, model and color, since a permission mode, hooks, MCP servers or skills would run something its reviewer does not see in its text; typographic quotes and dashes are made plain, and anything else outside ASCII is refused. It joins only when someone merges its pull request, and code-owner review covers .claude/. The workflow's import rebuilds and force-pushes its branch on every run, so a fix to an open import pull request is made by importing again or on a branch of your own.

## Running an agent

- In a session: ask for it by name ("have the reviewer look at #12"); Claude Code hands the work to the subagent.
- In Actions by hand: the Agents workflow, Run workflow, with the agent's name and the pull request or issue number; any agent but a developer.
- On every pull request: set its runs to pull_request.
- As a worker: list the worker under its workers; this is how a developer runs in Actions, under the claim protocol.

The Agents workflow runs on pull_request_target, so the workflow, the registry and the agent are always the default branch's: a pull request cannot rewrite the agent that reviews it. Its session works on the job's own GITHUB_TOKEN, which may read the code, comment and review but not push or merge, and never mints the Claude App's token, so an agent that a diff talks into something can still only comment; text in a pull request is data to the agents, never instructions. The tester runs the pull request's code with the Claude token in reach, which is why only pull requests from this repository's own branches start it: whoever opened one could already run code with the repository's secrets by pushing a workflow, and a fork's pull request starts nothing. Which token a run takes is the agent's line in .github/symphony/accounts.json, chosen by tools/pool.py as a worker's is, and the Tokens tab sets it; with no line, the file's default, else CLAUDE_CODE_OAUTH_TOKEN. Each run keeps its usage record for the field metrics, as every Claude run here does.

## Benchmarking an agent

The file under .claude/agents/ is what both benchmarks take, and `python3 tools/agents.py export NAME` prints it as the JSON `claude --agents` reads:

- coordbench: `python3 coordbench/run.py run --agent-file my-agent.md ...` runs every agent of a CooperBench pair as it, under any arm, on the claude-cli driver; result.json names the agent and its sha256. An agent written for a benchmark's container fits best: the template's developer follows the claim protocol, whose board, labels and pull requests a CooperBench container does not have. An agent that lists tools must keep the arm's coordination tools (`mcp__...`) when the arm has any, or the run is refused, since dropping them would change the arm and not only the agent.
- flowbench: a stage of an arm says `"agent": "agents/reviewer.md"`, and that stage's agents run as it, so a team's reviewer can stand in for the script arm's lenses.

In both the run's model and denied tools hold over the file's, so a comparison measures the instructions and nothing else. No benchmark run starts without the owner's word and the number of runs.
