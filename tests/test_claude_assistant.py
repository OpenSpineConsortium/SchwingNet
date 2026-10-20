"""claude.yml answers an issue labelled assistant, the control panel's
assistant, with the Claude step's settings changed to ones that only read
(docs/setup/claude-action.md, The assistant issue). The workflow is read
as text, the standard library having no YAML parser, the way
tests/test_crowd_check.py reads it, and nothing here runs the action.

What is pinned is what the review of 2026-10-17 found could let an
assistant run write or run a program: the push script the action's tag
mode always allows, the file commands its acceptEdits mode approves with
no rule, git fetch's --upload-pack and sed's e command, the allows of the
repository's own .claude/settings.json, which the action loads too and
which a deny holds over, and the labels of a pull request, which a comment
on it carries as its issue's.
"""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "claude.yml"
PROMPT = ROOT / ".github" / "symphony" / "assistant.md"
SETTINGS = ROOT / ".claude" / "settings.json"

# A setting of the step is one line of claude_args whose value the label
# chooses: the assistant's value, then what every other run gets.
CHOICE = re.compile(r"\$\{\{ env\.ASSISTANT == 'true' && '(?P<assistant>[^']*)' \|\| (?P<other>.*?) \}\}")
# A tile setting is one line of claude_args that passes the main token's
# model, effort or fallback from the Tokens tab, only when the tile sets it,
# to the assistant and every other run alike.
TILE = re.compile(r"\$\{\{ steps\.main\.outputs\.(?P<name>model|effort|fallback) != '' && "
                  r"format\('(?P<flag>--[a-z-]+) \{0\}', steps\.main\.outputs\.(?P=name)\) \|\| '' \}\}$")
TILE_READ = 'python3 tools/pool.py settings --slot main --settings "$SETTINGS" >> "$GITHUB_OUTPUT" || true'
TOOL_LIST = re.compile(r'--(?:allowedTools|disallowedTools) "([^"]*)"')
BASH_RULE = re.compile(r"Bash\((.*?)(?::\*)?\)$")
GH_COMMAND = re.compile(r"\bgh [a-z]+ [a-z]+\b")

LABEL_READ = "ASSISTANT: ${{ !github.event.issue.pull_request && contains(github.event.issue.labels.*.name, 'assistant') }}"
TOKEN_LINE = "claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"
ACTIONS_READ = "additional_permissions: |\n            ${{ env.ASSISTANT == 'true' && 'actions: read' || '' }}"
OTHER_TOOLS = ("(vars.CLAUDE_ALLOWED_TOOLS || 'Read,Write,Edit,MultiEdit,Glob,Grep,Bash(git:*),Bash(gh:*),"
               "Bash(bash scripts/check.sh),Bash(python3:*)')")
ALLOWED = {
    "Read", "Glob", "Grep",
    "Bash(git log:*)", "Bash(git show:*)", "Bash(git diff:*)", "Bash(git branch:*)", "Bash(git ls-files:*)",
    "Bash(gh issue view:*)", "Bash(gh issue list:*)", "Bash(gh pr view:*)", "Bash(gh pr list:*)",
    "Bash(gh run list:*)", "Bash(gh run view:*)",
}
DENIED = {
    "Edit", "Write", "MultiEdit", "NotebookEdit",
    "Bash(git add:*)", "Bash(git commit:*)", "Bash(git rm:*)",
    "Bash(*/scripts/git-push.sh:*)",
    "Bash(git fetch:*)", "Bash(sed:*)", "Bash(python3:*)", "Bash(bash:*)",
}
# The git commands that read, which the repository's settings may allow
# the assistant without a deny; everything else they allow needs one.
READS = ("git show", "git status", "git diff", "git log", "git branch", "git rev-parse", "git ls-files")


def claude_args():
    """The lines of the Claude step's claude_args block, stripped."""
    block = WORKFLOW.read_text(encoding="utf-8").split("claude_args: |\n", 1)[1]
    lines = []
    for line in block.splitlines():
        if not line.startswith("            "):
            break
        lines.append(line.strip())
    return lines


def choices():
    """Each setting's two values by the flag its line carries, the flag
    read from the assistant's value where the whole line is chosen."""
    found = {}
    for line in claude_args():
        if TILE.match(line):
            continue
        match = CHOICE.search(line)
        assert match, line
        assistant, other = match.group("assistant"), match.group("other")
        flag = line.split()[0] if line.startswith("--") else assistant.split()[0]
        found[flag] = (assistant, other, line)
    return found


def rules(text):
    """The tools a quoted list names."""
    return {tool.strip() for tool in text.split(",") if tool.strip()}


def prefix(rule):
    """The command a Bash rule names, or None for another tool's rule."""
    match = BASH_RULE.match(rule)
    return match.group(1) if match else None


class TheLabel(unittest.TestCase):
    def test_the_label_is_read_from_an_issue_and_never_a_pull_request(self):
        """A comment on a pull request carries the pull request's labels as
        its issue's, so one labelled assistant would get the assistant's
        settings and, on a branch without the prompt file, a red run."""
        self.assertIn(LABEL_READ, WORKFLOW.read_text(encoding="utf-8"))

    def test_every_setting_is_chosen_by_the_label_and_the_token_line_stands_once(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(text.count(TOKEN_LINE), 1)
        self.assertEqual(text.count("CLAUDE_CODE_OAUTH_TOKEN }}"), 1)
        self.assertEqual(set(choices()), {"--max-turns", "--allowedTools", "--disallowedTools",
                                          "--permission-mode", "--append-system-prompt-file"})
        for flag, (assistant, other, line) in choices().items():
            if not line.startswith("--"):
                self.assertEqual(other, "''", f"{flag}: a whole line the assistant alone gets is empty for the rest")


class TheTileSettings(unittest.TestCase):
    def test_the_main_tokens_model_effort_and_fallback_pass_only_when_the_tile_sets_them(self):
        tiles = {m.group("name"): m.group("flag") for m in map(TILE.match, claude_args()) if m}
        self.assertEqual(tiles, {"model": "--model", "effort": "--effort", "fallback": "--fallback-model"})

    def test_the_settings_are_read_once_from_the_variable_and_a_failed_read_leaves_the_defaults(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        step = text.split("        id: main\n", 1)[1].split("      - uses: anthropics/claude-code-action", 1)[0]
        self.assertEqual(text.count("        id: main\n"), 1)
        self.assertIn("SETTINGS: ${{ vars.SYMPHONY_CLAUDE_SETTINGS }}", step)
        self.assertIn(TILE_READ, step)
        self.assertLess(text.index(TILE_READ), text.index("claude_args: |"))

    def test_the_command_the_step_runs_is_one_pool_py_has(self):
        """The step's || true would hide a command pool.py lacks, and the
        settings would then be dropped with no word."""
        run = subprocess.run([sys.executable, str(ROOT / "tools" / "pool.py"), "settings", "--slot", "main",
                              "--settings", '{"main": {"model": "claude-opus-5-5"}}'],
                             capture_output=True, text=True, check=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout, "model=claude-opus-5-5\n")


class TheTurns(unittest.TestCase):
    def test_ten_for_the_assistant_and_fifty_for_every_other_run(self):
        assistant, other, _ = choices()["--max-turns"]
        self.assertEqual((assistant, other), ("10", "'50'"))


class TheTools(unittest.TestCase):
    def test_the_assistant_allows_only_tools_that_read(self):
        assistant, other, _ = choices()["--allowedTools"]
        self.assertEqual(rules(assistant), ALLOWED)
        self.assertEqual(other, OTHER_TOOLS, "every other run keeps its list")

    def test_no_allowed_command_runs_a_program_it_is_handed(self):
        """git fetch runs its --upload-pack, sed its e command, and a shell
        or an interpreter runs anything; cat needs no rule, being in the
        CLI's own read-only set, and Read takes a line range."""
        for rule in ALLOWED:
            command = prefix(rule)
            if command:
                self.assertTrue(command.startswith(("git ", "gh ")), rule)
                self.assertNotIn(" ".join(command.split()[:2]), ("git fetch", "git push", "git -c", "git -C"), rule)

    def test_the_assistant_denies_what_the_action_allows_whatever_the_list_says(self):
        """The action's tag mode always allows git add, git commit, git rm
        and its own scripts/git-push.sh, the one push, under the action's
        path, which only a wildcard can name from the workflow."""
        assistant, _, _ = choices()["--disallowedTools"]
        denied = rules(TOOL_LIST.search(assistant).group(1))
        self.assertEqual(denied, DENIED)

    def test_the_assistant_denies_every_allow_of_the_repositorys_settings_that_is_not_a_read(self):
        """The action loads .claude/settings.json as the project's settings,
        so its allows reach the assistant; a deny holds over them."""
        assistant, _, _ = choices()["--disallowedTools"]
        denied = [prefix(rule) for rule in rules(TOOL_LIST.search(assistant).group(1)) if prefix(rule)]
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        for rule in settings["permissions"]["allow"]:
            command = prefix(rule)
            self.assertIsNotNone(command, rule)
            if command.startswith(READS):
                continue
            self.assertTrue(any(command.startswith(deny) for deny in denied),
                            f"{rule}: allowed by the settings and denied by nothing of the assistant's")
        self.assertNotIn("deny", settings["permissions"], "a deny there would reach every session")

    def test_the_permission_mode_is_set_back_to_default(self):
        """The action prepends --permission-mode acceptEdits, which approves
        edits and the file commands mkdir, touch, rm, mv, cp and sed inside
        the checkout with no rule; its parser keeps the last value given, so
        the assistant's default stands, and a headless run refuses whatever
        no rule allows."""
        assistant, _, _ = choices()["--permission-mode"]
        self.assertEqual(assistant, "--permission-mode default")


class ThePrompt(unittest.TestCase):
    def test_the_prompt_file_is_appended_and_exists(self):
        assistant, _, _ = choices()["--append-system-prompt-file"]
        self.assertEqual(assistant, "--append-system-prompt-file .github/symphony/assistant.md")
        self.assertTrue(PROMPT.is_file())

    def test_the_prompt_names_only_commands_the_assistant_may_run(self):
        text = re.sub(r"\s+", " ", PROMPT.read_text(encoding="utf-8"))
        allowed = {prefix(rule) for rule in ALLOWED if prefix(rule)}
        for command in set(GH_COMMAND.findall(text)):
            self.assertIn(command, allowed, command)
        self.assertIn("git show origin/board:STATE.md", text)
        self.assertNotIn("git fetch origin", text, "no fetch is allowed, so the board is read as checked out")
        self.assertNotIn("gh pr checks", text, "checks: read is not asked for")

    def test_the_vocabulary_is_the_one_the_page_acts_on(self):
        """The page (openspineconsortium.github.io, assets/js/symphony-panel.js,
        assistantRun) does the reads by itself and offers the changes as
        buttons; a verb the prompt names and the page does not know would be
        shown as text, and one the page knows and the prompt leaves out is
        never proposed."""
        text = PROMPT.read_text(encoding="utf-8")
        section = text.split("## The reply vocabulary", 1)[1]
        verbs = set(re.findall(r"^    ([a-z]+) ", section, re.M))
        self.assertEqual(verbs, {"focus", "open", "filter", "show", "tab", "run", "give", "merge", "task", "ask"})
        reads, changes = section.split("The rest change something", 1)
        self.assertEqual(set(re.findall(r"^    ([a-z]+) ", reads, re.M)), {"focus", "open", "filter", "show", "tab"})
        self.assertIn("nothing happens until the person", re.sub(r"\s+", " ", changes))


class TheToken(unittest.TestCase):
    def test_the_assistant_alone_asks_for_actions_read(self):
        """The token the action mints carries no actions permission unless
        the step asks, so gh run list and gh run view would answer 403 and
        spend turns; every other run asks for nothing new."""
        self.assertIn(ACTIONS_READ, WORKFLOW.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
