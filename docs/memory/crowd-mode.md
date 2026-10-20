Crowd mode: scripts/crowd.py sets a repository up for volunteers on their own Claude accounts, and GitHub then holds it to the rules through the variable CLAUDE_CROWD, the required check and queue.yml.

A crowd repository (docs/setup/crowdsourcing.md) holds no Claude credential
of anyone's. It has two switches: the repository variable CLAUDE_CROWD,
which the workflows can read at job level, and the line "- Crowd mode: on."
in docs/project.md, which every session loads and only the owner's review
changes. The template ships the line off and no variable, so nothing below
does anything in an ordinary copy.

`python3 scripts/crowd.py setup` does what GitHub lets a script do (the
organization's defaults, the repository and Actions settings, labels, teams,
the ruleset docs/setup/ruleset-crowd.json, the variable) and opens one pull
request from crowd/setup with the files under docs/setup/crowd/ and the edits
crowd.py holds as data. `finish` merges it once "check" passed on GitHub
Actions and pins that check to app 15368, and only when GitHub's activity
record shows the signed-in owner alone pushed the branch and its tree is,
blob for blob, what setup would write for the owner login, which is never
read from the pull request; `invite` refuses until then; `audit` checks
everything weekly, CODEOWNERS against the signed-in owner or `--owner`;
`doctor` walks a contributor to ready. Once crowd mode is on, a later setup
keeps any crowd file whose latest commit is not setup's own, and adds a new
area's rows to CODEOWNERS and OWNERSHIP.md in place.

What GitHub then enforces:

- claude.yml, coordinator.yml and workers.yml never start while
  CLAUDE_CROWD is true: each job that waits on no other puts
  `vars.CLAUDE_CROWD != 'true' &&` first in its `if`, and the rest wait on
  those. GitHub compares it without case and trims nothing, so "true "
  leaves the gate open, and the guard reads it the same way. An unset
  variable reads as empty, so outside crowd mode the gate stays open.
  add-worker.yml still adds a routine there, but refuses a worker in
  Actions, since the repository holds no Claude token.
- The required check runs `tools/crowd_check.py guard`, which fails while a
  Claude secret, or either variable that switched on the Actions worker and
  team mode before the registry of workers replaced them, reaches the
  repository and crowd mode shows anywhere; while the default branch says on and
  CLAUDE_CROWD is not true; and when a pull request changes
  .claude/session.md or CLAUDE.md's checkpoint block while the default
  branch says on. A checkpoint is a pull request comment there. The job
  check names no secret, since GitHub hands a job's runner every secret the
  job names and check runs the pull request's code: ci.yml's job values,
  which runs nothing of the repository's, compares each secret with nothing
  and hands check only the names that are set.
- board.yml's step that calls a coordinator routine's trigger never runs
  while CLAUDE_CROWD is true; the coordinator's releases and overlap
  comments in the same run need no Claude token and run all the same.
- .github/workflows/queue.yml takes todo or blocker off again when someone
  without Maintain or Admin adds one, opens an issue with one, or edits a
  queued issue's title or body.
- scripts/setup-repo.sh stops before any write while CLAUDE_CROWD is true
  or the clone's docs/project.md says crowd mode is on, and whenever it
  cannot read the variable, since it turns auto-merge on and can store a
  token.

What stays a convention, made loud but not prevented: any writer can delete
the variable, add a secret, disable a workflow, or push to another's claim
branch or to board. The check, queue.yml and the audit report each; the
protection against a writer's own workflow reading secrets is that none
exists.

Source: scripts/crowd.py, tools/crowd_check.py and the workflows, built
2026-10-10, and docs/history/crowdsourcing/research.md, Crowd mode as code;
never run against a live organization.
