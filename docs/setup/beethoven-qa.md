# beethoven-qa in a Symphony repository

A repository made from this template can carry OpenSpineConsortium/beethoven-qa, the Beethoven engine's definition of done (contracts on every public function, CrossHair with Z3 over them, the six code standards), beside Symphony's claim protocol. The two were measured together on 2026-10-20 (docs/research/beethoven-and-symphony.md): the template's check passes with the copy and its kit in place, and the one collision, both shipping `.claude/hooks/session-start.sh`, is gone from beethoven-qa 6.0.0 (its pull request of 2026-10-20; until it is merged and tagged, take nothing), whose kit hook is `.claude/hooks/beethoven-qa-session-start.sh`. This page is the order of steps; beethoven-qa's own docs/CONSUMING.md has each step in full.

## What each side keeps

| | Symphony (this template) | beethoven-qa |
|---|---|---|
| how work is claimed | an issue, the branch `claude/<issue>`, a draft pull request with the claim file (docs/agents/PROTOCOL.md) | nothing; it takes the pull request as it finds it |
| the required check | `check` (scripts/check.sh) | `standards (every group green)` from the kit's standards.yml, and the gate job of the repository's own CI lane; name that job in ASCII, since the template's document check holds .github to ASCII and beethoven-research's job name carries an arrow |
| who merges | the owner, or auto-merge for a worker whose file says so | the kit's automerge.yml arms auto-merge once a pull request is ready; the checks alone decide |
| hooks in a session | `.claude/settings.json`: the board at session start, the push guard, the usage trailer, the edit check | its session-start hook (pixi and the locked environment, in a cloud session) and the plugin's coaching hook after every edit |
| the push | tools/guard_push.py, a Claude Code hook before the command runs | `.githooks/pre-push`, a git hook that runs the whole gate before anything leaves the machine |
| rulesets | docs/setup/ruleset-main.json, applied by Symphony Setup or scripts/setup-repo.sh | `.github/rulesets/main.json`, applied by the kit's rulesets.yml with the secret RULESETS_TOKEN |

A draft pull request with a claim file satisfies both: Symphony's protocol check wants the claim file while the pull request is a draft and gone once it is ready, and beethoven-qa's automerge.yml does nothing to a draft. The two push guards stack, since one is Claude Code's and the other is git's. The two rulesets both target the default branch; the required checks are their union, and the repository's owner applies both once.

## The steps

1. Take the copy and the kit, from the repository's root, with `gh` signed in, from a clone of the release the first time (its docs/CONSUMING.md, step 1): `gh repo clone OpenSpineConsortium/beethoven-qa <clone> -- --branch v6.0.0 --depth 1`, then `pixi run --locked --manifest-path <clone>/pixi.toml python -m beethoven_qa vendor --into . --ref v6.0.0 --kit`; every later release is taken by the copy itself. The kit's five files land at `.githooks/pre-push`, `.github/workflows/automerge.yml`, `.github/workflows/rulesets.yml`, `.claude/hooks/beethoven-qa-session-start.sh` and `.github/workflows/standards.yml`; the template's own `.claude/hooks/session-start.sh` stays.
2. Add `pixi.toml` and `pyproject.toml`'s `[tool.beethoven-qa]` table as CONSUMING.md's steps 2 and 3 say, naming the repository's own package (never tools/, which is the template's), and lock on purpose with pixi. The lock is the repository's own and the only lock it holds.
3. In `.claude/settings.json`, add the kit's hook after the template's in the `SessionStart` list, and the coaching hook:

   ```json
   "SessionStart": [
     {"hooks": [{"type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/session-start.sh"}]},
     {"matcher": "startup|resume", "hooks": [{"type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/beethoven-qa-session-start.sh", "timeout": 900}]}
   ]
   ```

   and under `PostToolUse`, beside the template's edit check, `bash "$CLAUDE_PROJECT_DIR"/vendor/beethoven-qa/plugin/hooks/coach.sh` on `Edit|Write|MultiEdit`.
4. Write `interface/INTERFACE.json` importing `python` 1, `cli` 3, `kit` 3 and `plugin` 1 from the copy (CONSUMING.md, step 3), so the copy's boundary lane holds.
5. scripts/check.sh runs the copy's vendor-check where pixi is on the path and says so where it is not; the repository's own gate lane (CONSUMING.md step 5) runs vendor-check and the gate under pixi on GitHub's machines, and the kit's standards.yml the standards. Add the gate job's name and `standards (every group green)` to the repository's ruleset beside `check`.
6. The owner's one-time steps, as for any beethoven-qa consumer: Allow auto-merge ticked in the repository's settings, the secret RULESETS_TOKEN shared with it, and the first pull request merged by hand when green so the rule is applied.

## What stays Symphony's

The legacy code a research repository brings in as its record (a pipeline that must stay byte-equal to what a paper reported) is listed under `[tool.beethoven-qa.unproven]` with that reason, and new code is written to the definition of done; the gate's `--module` limits a run to the module being worked on. Nothing of beethoven-qa changes how an issue is claimed, how the board reads a branch, or how a pull request is told about overlapping work.
