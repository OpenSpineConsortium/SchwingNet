# Claude Code plugin marketplaces: what the official docs say (read 2026-10-10)

Sources: code.claude.com/docs/en/plugins/marketplace-reference.md, create-marketplace.md,
host-marketplace.md, manifest-reference.md, components.md, install.md, org.md,
settings-reference.md (extraKnownMarketplaces, enabledPlugins), settings, memory.md.
Read through a summarising fetch; check exact wording on the live page before quoting.

## The marketplace file

- Path: .claude-plugin/marketplace.json at the marketplace root (the repository root for a
  git marketplace). Relative plugin sources resolve from that root, not from .claude-plugin/.
- Required top-level fields: name, owner (object with name; email and url optional), plugins.
  Optional: description (validate warns when missing), version, metadata.pluginRoot,
  forceRemoveDeletedPlugins, renames. Unknown keys are ignored at load; validate warns.
- name: letters, digits, ".", "_", "-", starting with a letter or digit; reserved names such as
  claude-plugins-official and anthropic-marketplace are refused.
- Plugin entry, required: name (the install id typed before "@") and source. Optional:
  description, version, category, tags, strict (default true), defaultEnabled (default true),
  displayName, and any plugin.json field (author, homepage, keywords, license, repository,
  commands, agents, skills, hooks). Hooks in an entry must be an inline object.
- Source forms: a relative path string starting with "./" for a plugin inside the marketplace
  repository (works for github and git marketplaces, which clone the whole tree); objects
  {"source": "github", "repo": "owner/repo", "ref": ..., "sha": ...}, {"source": "git-subdir",
  "url": ..., "path": ...}, {"source": "url", ...}, npm, archive, command for plugins elsewhere.
- Minimal example:
  {"name": "my-marketplace", "description": "...", "owner": {"name": "..."},
   "plugins": [{"name": "my-first-plugin", "source": "./plugins/my-first-plugin", "description": "..."}]}
- The entry name and the plugin.json name must be equal, or installs by the manifest name fail.
- A version set in plugin.json wins over the entry; set it in one place. Bump it per release, or
  omit it and users track commits.
- plugin.json names beginning with claude-, anthropic-, anthropics- or cc-plugin- fail validation.

## Commands

- /plugin marketplace add OWNER/REPO; /plugin install NAME@MARKETPLACE; or in one step (2.1.275+)
  /plugin install NAME --marketplace OWNER/REPO.
- Shell: claude plugin marketplace add <source>; claude plugin install NAME@MARKETPLACE --scope project;
  claude plugin validate <dir>.
- Scope: user by default; --scope project writes the entry into .claude/settings.json, which is
  committed, so it is enabled for everyone who works in that repository.

## Presetting a repository's users

- .claude/settings.json: "extraKnownMarketplaces": {"<marketplace name>": {"source": {"source":
  "github", "repo": "owner/repo"}}} and "enabledPlugins": {"<plugin>@<marketplace>": true}.
- Entries in a repository's settings apply only after the user accepts the workspace trust dialog
  for that folder. A plugin listed by a relative path loads from the marketplace copy once the
  entry applies; a plugin whose entry points at an external source needs an explicit install.

## Plugin layout

- .claude-plugin/plugin.json (optional manifest): name (required, kebab-case), version,
  description, author {name, email, url}, homepage, repository, license, keywords, displayName,
  defaultEnabled, component keys (skills, commands, agents, hooks, mcpServers, lspServers).
- Everything else at the plugin root: skills/<name>/SKILL.md, commands/*.md, agents/*.md,
  hooks/hooks.json, .mcp.json, bin/ (added to the Bash PATH while enabled), settings.json (only
  the keys agent and subagentStatusLine take effect; every other key is dropped).
- hooks/hooks.json: {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command",
  "command": "\"${CLAUDE_PLUGIN_ROOT}\"/scripts/check-command.sh"}]}]}}, the same shape as
  settings.json's hooks object. Hooks load at session start, not when a skill is used.
- Namespacing: skills are /<plugin>:<directory> (a frontmatter name replaces the last segment),
  commands /<plugin>:<file>, agents <plugin>:<name>, MCP tools mcp__plugin_<plugin>_<server>__<tool>.

## What a plugin cannot ship

- Project rules (.claude/rules/*.md): no plugin component exists for them; they stay repository
  files (inferred from absence; no page says otherwise).
- A CLAUDE.md at the plugin root is not loaded; validate warns. Instructions go in a skill; a rule
  that must always hold goes in a hook.
- Permissions: a plugin's settings.json keys other than agent and subagentStatusLine are dropped.
  permissions stay in the repository's .claude/settings.json; allow rules and most env values
  apply only after each teammate trusts the folder, deny and ask rules apply at once.

## Private marketplaces

- A private repository can be a marketplace; Claude Code clones it with the git credentials on
  the user's machine and never prompts. GitHub shorthand probes SSH then HTTPS;
  CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1 skips the probe. Each user needs read access.
- Background auto-update needs a credential that works without a prompt; an environment
  GITHUB_TOKEN alone does not authenticate it.

## Unverified

- Whether a project enabledPlugins entry alone prompts teammates (only the trust dialog is documented).
- CLI flags beyond those on the install and create pages.
