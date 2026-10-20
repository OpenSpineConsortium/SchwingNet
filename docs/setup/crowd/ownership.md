# Ownership

Who reviews which part of the repository, in crowd mode. Anyone with Write claims issues anywhere; .github/CODEOWNERS decides whose review a pull request needs, and the teams on GitHub say who is in each team, so an invitation changes no file here. OWNER_LOGIN reviews and merges the shared paths alone, the paths every session loads or runs; the team {{OWNER}}/maintainers reviews and merges everything else; each area's team reviews its own folders, and a maintainer merges once it has approved. Nobody merges their own pull request, except OWNER_LOGIN for the shared paths.

| Area | Paths | Reviewed by | Label | Merges |
| --- | --- | --- | --- | --- |
| The shared paths | .github/, .claude/, tools/, scripts/, tests/, CLAUDE.md, docs/project.md, docs/agents/, docs/memory/, docs/setup/, .mcp.json, and CLAUDE.md, CLAUDE.local.md, AGENTS.md and .claude/ in every folder, an area's included | OWNER_LOGIN | none | OWNER_LOGIN |
| Everything else | every path no other row names | {{OWNER}}/maintainers | none | {{OWNER}}/maintainers |
| AREA | src/AREA/, tests/test_AREA/ | {{OWNER}}/AREA-maintainers | area:AREA | {{OWNER}}/maintainers |

To add an area, the owner runs `python3 scripts/crowd.py setup {{REPO}} --area <name>` again: it makes the area's label and team and opens a pull request that adds the area's rows here and in .github/CODEOWNERS, keeping every area that already has a label.
