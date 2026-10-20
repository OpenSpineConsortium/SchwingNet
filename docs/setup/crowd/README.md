# Crowd mode files

The files in this folder are what `python3 scripts/crowd.py setup` lands in a repository it turns to crowd mode (docs/setup/crowdsourcing.md), in one pull request from the branch crowd/setup that the owner reads and `python3 scripts/crowd.py finish` merges. Nothing loads them where they are: Claude Code reads rules and skills only under .claude/, and GitHub reads code owners only from .github/, the root or the top of docs/. Template-init fills their placeholders in a copy like every other file's, so the pull request carries the copy's own names.

| File | Lands as | How |
| --- | --- | --- |
| rule.md | .claude/rules/crowd.md | Whole: the crowd rules every session loads |
| checkpoint-skill.md | .claude/skills/checkpoint/SKILL.md | Whole: a checkpoint becomes a pull request comment |
| coordinator.md | docs/agents/routines/coordinator.md | Whole: the coordinator made outside any Project, with the crowd prompt |
| worker.md | docs/agents/routines/worker.md | Whole: a contributor's own worker, with the crowd lines in its prompt |
| CODEOWNERS | .github/CODEOWNERS | Generated: OWNER_LOGIN becomes the owner's login, and each line naming AREA is repeated once per area, or dropped when there is none; the lines after the area lines give the instruction files of every folder to the owner |
| ownership.md | docs/agents/OWNERSHIP.md | Generated the same way |

The same pull request adds tests/test_AREA/__init__.py for each area, so test discovery finds the area's tests and its team owns them; takes the labels off the Task and Blocker forms, so only a maintainer queues work; turns docs/project.md's crowd mode line on, with the crowd's decisions; and makes small edits to CLAUDE.md and README.md. scripts/crowd.py holds those edits as data, and tests/test_crowd.py fails when the template's text drifts from them. Once crowd mode is on, a later setup makes none of those edits again and keeps any file here that someone changed after setup wrote it (its latest commit is not setup's), adding only a new area's rows to CODEOWNERS and OWNERSHIP.md; a changed file takes a newer version of its source by hand. The ruleset the setup applies and `python3 scripts/crowd.py audit` holds the repository to is docs/setup/ruleset-crowd.json, beside this folder.
