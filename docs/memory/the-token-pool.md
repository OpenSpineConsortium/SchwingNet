The branch pool holds each Claude slot's latest usage readings (five-hour, seven-day, per-model limits such as Fable), written by tools/pool.py from runs, from pool.yml's one-word probes and from cswap through tokens.py usage; pool.py pick is the auto mode.

A runner cannot read a token's usage page, since a token from claude
setup-token is inference-only, so the five-hour and seven-day windows
come from Claude's own rate_limit_event (every run and pool.yml's probe)
and the Fable weekly limit only from cswap on the owner's machine
(`python3 scripts/tokens.py usage`). One file per slot and kind
(slot-N.run|probe|cswap.json) on the branch pool, one commit with no
history, no token, e-mail or text. A probe spends one word of the
window it reads, so pool.yml probes only on Run workflow or the panel's
Refresh, never on a schedule (the owner's choice, 2026-10-17). pick takes the least used five-hour, then
seven-day window, passing over a slot held at 90 percent until its
reset. .github/symphony/accounts.json gives each worker in Actions
main, a slot or auto (no file: main), and workers.yml records each run's
reading. SYMPHONY_CLAUDE_SETTINGS, which the Tokens tab's tiles write, gives each slot a model, an effort, a
fallback taken when the model's own weekly limit is spent, and resume or paused, which keep a slot out of auto
(docs/setup/claude-tokens.md, "Each token's settings"), and an id and its owner's login: workers.yml labels each
issue a run worked token:<id> for the panel's leaderboard. The pool has 32 slots, an organization's holding every
member's tokens (the owner, 2026-10-18); scripts/tokens.py and the bench keep to 1 to 8. coordbench's bench.yml takes auto in its accounts box from its
own branch pool (a copy of pool.py there), fed by its real jobs and by
`tokens.py usage --also coordbench`. The control
panel's Tokens tab is the token tiles alone (site #49); which agent runs on which token is set on the agents' tab. The picker moves to the protocol library after 0.5.1 is cut.
docs/research/claude-token-pool.md has the sources and the four steps;
from the token wizard's thread, 2026-10-17.

A worker's or an agent's line in .github/symphony/accounts.json may be a
list of slots, ["3", "5"]: auto over those the pool holds, main only where
the list names it, and a refusal where it holds none; the control panel's
tokenAssignBox writes it per repository, so one repository divides its
tokens between review, development and testing.
