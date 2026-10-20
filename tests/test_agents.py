"""tools/agents.py: the agent format, the registry and the import."""

import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import agents  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

AGENT = """---
name: lint-fixer
description: Fixes lint findings in one pull request.
tools: Read, Edit, Bash(git:*)
model: sonnet
---

Fix the lint findings.
"""


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def opener_for(text, seen=None):
    def opener(request, timeout=None):
        if seen is not None:
            seen.append(request.full_url)
        return FakeResponse(text.encode("utf-8"))
    return opener


class Repository(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        shutil.copytree(ROOT / ".claude" / "agents", self.root / ".claude" / "agents")
        (self.root / ".github" / "symphony" / "workers").mkdir(parents=True)
        shutil.copy(ROOT / agents.REGISTRY, self.root / agents.REGISTRY)

    def registry(self):
        return json.loads((self.root / agents.REGISTRY).read_text())


class TheTemplatesAgents(unittest.TestCase):
    def test_the_template_holds_together(self):
        self.assertEqual(agents.check(ROOT), [])

    def test_it_brings_one_agent_for_each_purpose(self):
        purposes = {a["purpose"] for a in agents.listing(ROOT)}
        self.assertTrue({"review", "develop", "test"} <= purposes)

    def test_none_runs_on_its_own_until_someone_switches_it_on(self):
        self.assertEqual(agents.runs_on(ROOT, "pull_request"), [])


class ReadingAnAgent(unittest.TestCase):
    def test_a_good_file(self):
        agent = agents.read_agent(AGENT, imported=True)
        self.assertEqual(agent["tools"], ["Read", "Edit", "Bash(git:*)"])
        self.assertEqual(agent["model"], "sonnet")

    def test_a_tools_list_in_yaml_form(self):
        text = AGENT.replace("tools: Read, Edit, Bash(git:*)", "tools:\n  - Read\n  - Grep")
        self.assertEqual(agents.read_agent(text)["tools"], ["Read", "Grep"])

    def test_every_agent_must_list_its_tools(self):
        text = AGENT.replace("tools: Read, Edit, Bash(git:*)\n", "")
        for imported in (False, True):
            with self.subTest(imported=imported), self.assertRaisesRegex(agents.AgentError, "tools must list"):
                agents.read_agent(text, imported=imported)

    def test_an_import_carries_only_the_plain_keys(self):
        for extra in ("hooks:\n  PreToolUse: x\n", "mcpServers:\n  - x\n", "permissionMode: bypassPermissions\n",
                      "permissionMode: bypassPermissions # x\n", "permissionMode: >-\n  bypassPermissions\n",
                      "skills: x\n"):
            with self.subTest(extra=extra), self.assertRaises(agents.AgentError):
                agents.read_agent(AGENT.replace("model: sonnet\n", "model: sonnet\n" + extra), imported=True)

    def test_spellings_yaml_reads_as_other_keys_are_refused(self):
        for extra in ('"hooks":\n  x: y\n', "'mcpServers': {}\n", "<<: {hooks: x}\n"):
            with self.subTest(extra=extra), self.assertRaisesRegex(agents.AgentError, "plain key"):
                agents.read_agent(AGENT.replace("model: sonnet\n", "model: sonnet\n" + extra))

    def test_an_indented_rule_does_not_end_the_front_matter(self):
        text = AGENT.replace("model: sonnet\n", "model: sonnet\ncolor: |\n  ---\npermissionMode: bypassPermissions\n")
        with self.assertRaises(agents.AgentError):
            agents.read_agent(text, imported=True)

    def test_a_quote_in_a_tool_is_refused(self):
        with self.assertRaisesRegex(agents.AgentError, "not a tool"):
            agents.read_agent(AGENT.replace("Bash(git:*)", 'Bash(echo "x")'))

    def test_bad_names_and_models(self):
        for old, new in (("name: lint-fixer", "name: Lint_Fixer"), ("model: sonnet", "model: gpt-5"),
                         ("---\nname", "name")):
            with self.subTest(new=new), self.assertRaises(agents.AgentError):
                agents.read_agent(AGENT.replace(old, new, 1))

    def test_typography_is_made_plain_and_the_rest_refused(self):
        self.assertIn("'s", agents.plain_text("it’s"))
        with self.assertRaisesRegex(agents.AgentError, "not ASCII"):
            agents.plain_text("a rocket \U0001F680")


class Importing(Repository):
    def test_a_github_source_is_read_from_raw_and_recorded(self):
        seen = []
        name = agents.import_agent(self.root, "someone/agents/review/lint.md@v1", opener=opener_for(AGENT, seen))
        self.assertEqual(name, "lint-fixer")
        self.assertEqual(seen, ["https://raw.githubusercontent.com/someone/agents/v1/review/lint.md"])
        entry = self.registry()["agents"]["lint-fixer"]
        self.assertEqual(entry["purpose"], "develop")
        self.assertEqual(entry["source"], "someone/agents/review/lint.md@v1")
        self.assertEqual(agents.check(self.root), [])

    def test_it_takes_another_name(self):
        agents.import_agent(self.root, "https://example.com/a.md", name="mine", purpose="review",
                            opener=opener_for(AGENT))
        self.assertIn("name: mine", (self.root / ".claude/agents/mine.md").read_text())
        self.assertEqual(agents.check(self.root), [])

    def test_a_name_already_taken_from_elsewhere_is_refused(self):
        with self.assertRaisesRegex(agents.AgentError, "already here"):
            agents.import_agent(self.root, "https://example.com/r.md",
                                opener=opener_for(AGENT.replace("lint-fixer", "reviewer")))

    def test_a_workers_name_is_refused(self):
        (self.root / ".github/symphony/workers/lint-fixer.json").write_text("{}")
        with self.assertRaisesRegex(agents.AgentError, "also a worker"):
            agents.import_agent(self.root, "https://example.com/a.md", opener=opener_for(AGENT))

    def test_a_dotted_path_is_refused(self):
        with self.assertRaisesRegex(agents.AgentError, r"\.\."):
            agents.import_agent(self.root, "o/r/../../evil/repo/HEAD/a.md", opener=opener_for(AGENT))

    def test_an_agent_in_a_subfolder_fails_the_check(self):
        (self.root / ".claude/agents/x").mkdir()
        (self.root / ".claude/agents/x/evil.md").write_text(AGENT)
        self.assertTrue(any("directly under" in p for p in agents.check(self.root)))

    def test_plain_http_is_refused(self):
        with self.assertRaisesRegex(agents.AgentError, "https"):
            agents.import_agent(self.root, "http://example.com/a.md", opener=opener_for(AGENT))

    def test_a_hand_edit_fails_the_check_until_owned(self):
        agents.import_agent(self.root, "https://example.com/a.md", opener=opener_for(AGENT))
        path = self.root / ".claude/agents/lint-fixer.md"
        path.write_text(path.read_text() + "More.\n")
        self.assertTrue(any("changed since it was imported" in p for p in agents.check(self.root)))
        agents.own_agent(self.root, "lint-fixer")
        self.assertEqual(agents.check(self.root), [])

    def test_update_takes_the_source_again(self):
        agents.import_agent(self.root, "https://example.com/a.md", opener=opener_for(AGENT))
        agents.update_agent(self.root, "lint-fixer", opener=opener_for(AGENT.replace("Fix the", "Fix all the")))
        self.assertIn("Fix all the", (self.root / ".claude/agents/lint-fixer.md").read_text())
        self.assertEqual(agents.check(self.root), [])

    def test_remove(self):
        agents.import_agent(self.root, "https://example.com/a.md", opener=opener_for(AGENT))
        agents.remove_agent(self.root, "lint-fixer")
        self.assertFalse((self.root / ".claude/agents/lint-fixer.md").exists())
        self.assertEqual(agents.check(self.root), [])


class TheRegistry(Repository):
    def write(self, data):
        (self.root / agents.REGISTRY).write_text(json.dumps(data))

    def test_an_agent_file_with_no_entry_fails(self):
        (self.root / ".claude/agents/stray.md").write_text(AGENT.replace("lint-fixer", "stray"))
        self.assertTrue(any("not in" in p for p in agents.check(self.root)))

    def test_a_worker_runs_under_one_agent(self):
        (self.root / ".github/symphony/workers/nightly.json").write_text("{}")
        data = self.registry()
        data["agents"]["developer"]["workers"] = ["nightly"]
        self.write(data)
        self.assertEqual(agents.check(self.root), [])
        self.assertEqual(agents.for_worker(self.root, "nightly"), "developer")
        data["agents"]["tester"]["workers"] = ["nightly"]
        self.write(data)
        self.assertTrue(any("runs under both" in p for p in agents.check(self.root)))

    def test_an_unregistered_worker_and_a_bad_setting_fail(self):
        data = self.registry()
        data["agents"]["developer"]["workers"] = ["ghost"]
        data["agents"]["reviewer"]["runs"] = "always"
        data["agents"]["tester"]["colour"] = "red"
        self.write(data)
        problems = "\n".join(agents.check(self.root))
        for word in ("ghost", "runs must be", "colour"):
            self.assertIn(word, problems)

    def test_runs_on_pull_request(self):
        data = self.registry()
        data["agents"]["reviewer"]["runs"] = "pull_request"
        self.write(data)
        self.assertEqual(agents.runs_on(self.root, "pull_request"), ["reviewer"])


class ForTheBenchmarks(unittest.TestCase):
    def test_export_is_what_claude_agents_reads(self):
        exported = agents.export("reviewer", ROOT)
        self.assertEqual(list(exported), ["reviewer"])
        self.assertIn("prompt", exported["reviewer"])
        self.assertIn("Read", exported["reviewer"]["tools"])
        self.assertNotIn("model", exported["reviewer"])

    def test_allowed_tools_is_one_word(self):
        self.assertTrue(agents.allowed_tools(ROOT, "reviewer").startswith("Read,Grep,Glob"))


if __name__ == "__main__":
    unittest.main()
