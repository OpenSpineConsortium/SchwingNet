# Importable agents: bring your own agent, and benchmark it

Source: the thread "Importable agents" of the project symphony2, 2026-10-18, started for the owner's message of 2026-10-18 08:30 UTC in the thread "Symphony beyond cooperation": "make the agents importable so users can provide their own agents", with agents for code review, code development and testing, and Symphony as "both a tool for code development and agent benchmarking, which can rely on native coordbench and flowbench integration". No Claude Doc or artifact.

## What was decided, and why

- An agent is a Claude Code subagent file, .claude/agents/<name>.md: a front matter with its name, description, tools and model, and its instructions as the body. Claude Code already reads that format in every session, `claude --agent NAME` runs a whole session as one (checked against Claude Code 2.1.302's `--help` on 2026-10-18), and `claude --agents FILE` takes the same definitions as JSON, so one file serves a person's session, a run in Actions and a benchmark, with no runtime of Symphony's own. This was the coordinator's default where the ask forked, and it holds.
- Importing is a pull request. `python3 tools/agents.py import SOURCE` reads OWNER/REPO/PATH.md[@REF] from raw.githubusercontent.com, an https address or a local file, with no credential, and the Agents workflow and the console's Import box run the same command and open the pull request. An agent's instructions are code that runs with the repository's tools, so it is reviewed like code: code-owner review covers .claude/, every agent lists its tools, and an import carries only name, description, tools, model and color, an allowlist, since a permission mode, hooks, MCP servers or skills could run something its text does not show, and a blocklist missed spellings YAML reads (below).
- What an agent is for, where it came from and when it runs are in .github/symphony/agents.json, beside the file, since the worker registry's settings are the protocol library's (tools/sdlc_protocol/workers.py refuses an unknown key) and a change there is symphony-protocol's to make. A worker in Actions runs under an agent by the agent's `workers` list; workers.yml adds `--agent` and nothing else.
- Tokens per purpose, which is how the owner divides usage between review, development and testing, need no file of this thread's: an agent's runs choose their token by the agent's name in .github/symphony/accounts.json, through tools/pool.py, exactly as a worker's do. The token thread owns that file and its per-repository, per-login rules; the Agents tab draws the choice with that thread's tokenAssignBox(repo, agentName). An agent's name may not be a worker's, so one line in that file never means two things.
- The template's three agents say runs: manual, so adopting this spends nothing until someone switches one on.
- The benchmarks take the file as it is: coordbench's `--agent-file` (coordbench#30) and a flowbench stage's `"agent"` key (flowbench#3). Both strip the model and keep their own denied tools, so an arm that runs a team's agent differs from its baseline by the agent's instructions and tool list only, which is what a parity row can state. No run was started; each waits for the owner's word and number, and the curse-of-coordination hold of 2026-10-18 is untouched, since this is a harness option and not a coordination study.

## What the adversarial review changed

A review of the first version, before any pull request, found two high findings and three medium ones, all fixed before the template's pull request opened:

- The Agents workflow first ran on pull_request with the Claude secrets and a writable token, so a pull request could edit the workflow and run its own version with them, and the reviewer ran the pull request's check with a token that could push. It now runs on pull_request_target, so the workflow and the agent are the default branch's, on the job's read-only GITHUB_TOKEN rather than the Claude App's (no id-token), and the reviewer reads only through gh and runs no code; a developer runs only as a worker, under the claim protocol.
- The front matter reader was a blocklist that missed what YAML reads: a quoted key ("hooks"), a merge key, a trailing comment after bypassPermissions, a block scalar, and an indented --- that ended the front matter early while Claude Code read on. It now takes only plain keys and an exact --- line, and an import only an allowlist of keys.
- The reviewer's tools allowed python3, git push and gh api, so a prompt-injected reviewer could push or merge; they are now git log, show and diff and gh pr view, diff, checks, review and comment. Every agent must list its tools, and a run whose tools cannot be read fails rather than falling back to the action's defaults.
- Smaller: a run by a worker's bot is allowed (allowed_bots), a source with .. is refused, a redirect away from https is refused, an agent file in a subfolder fails the check, the default token is the accounts file's default, and coordbench refuses an agent that drops an arm's coordination tools.

## Options left to the owner

- Agents on other runtimes (Codex, OpenHands, an Agent SDK program): each needs either an API key, which the project refuses, or a driver of its own in each benchmark. Not built.
- Importing a whole folder or a plugin's agents/ in one step: one file at a time today, since each file is reviewed on its own.
- A leaderboard of agents by benchmark result: the leaderboard the owner asked for is the token thread's; this thread would hand it each run's agent name and sha256, which both benchmarks now record.

## Checked

- tests/test_agents.py (28 tests): the template's agents hold together, one per purpose, none runs on its own; reading, the import's refusals (no tools, hooks, MCP servers, bypassed permissions, a quote inside a tool, plain http, a taken name, a worker's name), the hand-edit check, update, own and remove, the registry's rules, export and allowed-tools.
- coordbench's and flowbench's whole suites pass with their new tests.
