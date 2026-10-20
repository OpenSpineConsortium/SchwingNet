"""template_init fills every placeholder outside the workflows, removes the
marker folder, leaves the workflows alone, and does nothing the second time;
in an organization's copy CODEOWNERS names the user who made it. The
placeholders are assembled at run time so this file survives an init of the
repository it lives in, and the tests that read the template's own files run
in the template alone."""

import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import template_init  # noqa: E402
from template_init import placeholder  # noqa: E402

# A repository made from the template runs these tests too, with the files
# some of them read already changed: its CLAUDE.md block is empty, and in
# crowd mode its checkpoint skill is another file. Those tests run in the
# template alone, where .template/ still is, as tests/test_crowd.py does.
IN_TEMPLATE = (ROOT / ".template" / "PENDING").is_file()
template_only = unittest.skipUnless(IN_TEMPLATE, "reads the template's own files, which a copy has changed")

P = {name: placeholder(name) for name in template_init.PLACEHOLDER_NAMES}
README = f"# {P['PROJECT_NAME']}\n\nClone {P['REPO']}; the default branch is {P['DEFAULT_BRANCH']}.\n"
LICENSE = f"MIT License\n\nCopyright (c) {P['YEAR']} {P['OWNER']}\n"
CODEOWNERS = f"* @{P['CODE_OWNER']}\n"
HOOK = f"#!/usr/bin/env bash\nprintf '%s\\n' \"{P['DEFAULT_BRANCH']}\"\n"
# A workflow that carries a placeholder anyway: the run must leave it as it
# is, since GITHUB_TOKEN could not push the change.
WORKFLOW = f"on:\n  push:\n    branches: [\"{P['DEFAULT_BRANCH']}\"]\n"
INIT_WORKFLOW = "on:\n  push:\n"
PLAIN = "nothing to fill here\r\nwith CRLF kept\r\n"
BINARY = bytes(range(256))


def write(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


def tree_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def tiny_tree(root):
    write(root, "README.md", README)
    write(root, "LICENSE", LICENSE)
    write(root, ".github/CODEOWNERS", CODEOWNERS)
    write(root, ".github/workflows/ci.yml", WORKFLOW)
    write(root, ".github/workflows/template-init.yml", INIT_WORKFLOW)
    write(root, ".claude/hooks/session-start.sh", HOOK)
    write(root, ".template/PENDING", "not initialised\n")
    write(root, "docs/plain.md", PLAIN)
    write(root, "data/blob.bin", BINARY)
    write(root, ".git/config", f"[remote]\n\turl = {P['REPO']}\n")


def run_init(root, extra=()):
    # No event unless a test passes one: on CI, GITHUB_EVENT_PATH names the
    # check's own event, which must not leak into these runs.
    held = io.StringIO()
    with redirect_stdout(held):
        code = template_init.main(["--repo", "octo/widgets", "--default-branch", "main", "--year", "2026", "--root", str(root), "--event", "", *extra])
    return code, held.getvalue().splitlines()


def push_event(owner_type, sender_login="mona", sender_type="User", full_name="octo/widgets"):
    """The parts of a push event code_owner reads."""
    return {
        "repository": {"full_name": full_name, "owner": {"login": full_name.partition("/")[0], "type": owner_type}},
        "sender": {"login": sender_login, "type": sender_type},
    }


class Values(unittest.TestCase):
    def test_mapping(self):
        mapping = template_init.values("octo/widgets", "main", 2026)
        self.assertEqual(mapping[P["PROJECT_NAME"]], "widgets")
        self.assertEqual(mapping[P["REPO"]], "octo/widgets")
        self.assertEqual(mapping[P["OWNER"]], "octo")
        self.assertEqual(mapping[P["CODE_OWNER"]], "octo")
        self.assertEqual(mapping[P["DEFAULT_BRANCH"]], "main")
        self.assertEqual(mapping[P["YEAR"]], "2026")

    def test_a_code_owner_given_replaces_the_owner_in_codeowners_only(self):
        mapping = template_init.values("octo/widgets", "main", 2026, "mona")
        self.assertEqual(mapping[P["CODE_OWNER"]], "mona")
        self.assertEqual(mapping[P["OWNER"]], "octo")

    def test_a_bad_repo_is_refused(self):
        for bad in ("widgets", "octo/", "/widgets", "a/b/c"):
            with self.assertRaises(template_init.InitError):
                template_init.values(bad, "main", 2026)

    def test_this_file_and_the_tool_carry_no_placeholder(self):
        for path in (ROOT / "tools" / "template_init.py", Path(__file__)):
            text = path.read_text(encoding="utf-8")
            for marker in P.values():
                self.assertNotIn(marker, text, path.name)

    def test_the_workflows_carry_no_placeholder(self):
        # The run never writes them, so a placeholder there would stay forever.
        folder = ROOT / ".github" / "workflows"
        files = sorted(folder.glob("*.yml"))
        self.assertTrue(files)
        for path in files:
            text = path.read_text(encoding="utf-8")
            for marker in P.values():
                self.assertNotIn(marker, text, path.name)


class CodeOwner(unittest.TestCase):
    """GitHub asks a user or a team for review, never an organization, so
    an organization's copy names the user whose push made it."""

    def test_a_personal_copy_names_its_owner(self):
        self.assertEqual(template_init.code_owner("octo/widgets", push_event("User", "octo")), "octo")

    def test_an_organizations_copy_names_the_user_who_made_it(self):
        self.assertEqual(template_init.code_owner("octo/widgets", push_event("Organization")), "mona")

    def test_an_organizations_copy_made_by_an_app_names_nobody(self):
        self.assertIsNone(template_init.code_owner("octo/widgets", push_event("Organization", "maker[bot]", "Bot")))

    def test_without_an_event_or_with_another_repositorys_the_owner_stays(self):
        self.assertEqual(template_init.code_owner("octo/widgets", {}), "octo")
        self.assertEqual(template_init.code_owner("octo/widgets", push_event("Organization", full_name="octo/other")), "octo")

    def test_the_repository_is_matched_without_regard_to_case(self):
        self.assertEqual(template_init.code_owner("octo/widgets", push_event("Organization", full_name="Octo/Widgets")), "mona")

    def test_read_event_reads_a_json_object_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "event.json"
            path.write_text(json.dumps(push_event("Organization")))
            self.assertEqual(template_init.read_event(str(path)), push_event("Organization"))
            path.write_text("[1, 2]")
            self.assertEqual(template_init.read_event(str(path)), {})
            path.write_text("not json")
            self.assertEqual(template_init.read_event(str(path)), {})
            self.assertEqual(template_init.read_event(str(Path(folder) / "missing.json")), {})
        self.assertEqual(template_init.read_event(""), {})

    def init_with(self, event):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tiny_tree(root)
            path = root.parent / (root.name + "-event.json")
            path.write_text(json.dumps(event))
            try:
                code, lines = run_init(root, ["--event", str(path)])
            finally:
                path.unlink()
            return code, lines, (root / ".github" / "CODEOWNERS").read_text(), (root / "LICENSE").read_text()

    def test_an_organizations_copy_gets_a_codeowners_github_resolves(self):
        code, lines, codeowners, license_text = self.init_with(push_event("Organization"))
        self.assertEqual(code, 0)
        self.assertEqual(codeowners, "* @mona\n")
        self.assertEqual(license_text, "MIT License\n\nCopyright (c) 2026 octo\n")
        self.assertNotIn(template_init.NO_CODE_OWNER_NOTE, lines)

    def test_an_organizations_copy_made_by_an_app_keeps_the_owner_and_says_so(self):
        code, lines, codeowners, _ = self.init_with(push_event("Organization", "maker[bot]", "Bot"))
        self.assertEqual(code, 0)
        self.assertEqual(codeowners, "* @octo\n")
        self.assertIn(template_init.NO_CODE_OWNER_NOTE, lines)
        self.assertIn("docs/setup/github.md", template_init.NO_CODE_OWNER_NOTE)

    def test_the_repositorys_own_codeowners_never_names_the_bare_owner(self):
        # In the template the line carries the code owner's placeholder; in a
        # copy, a login. Either way never the owner's placeholder, which an
        # organization's copy would turn into a line GitHub cannot resolve.
        text = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
        self.assertNotIn("@" + P["OWNER"], text)


class Checkpoint(unittest.TestCase):
    """The template's own repository keeps a real checkpoint for whoever
    continues its work; a new copy starts blank instead of inheriting it."""

    def test_a_new_copy_starts_with_the_blank_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tiny_tree(root)
            (root / ".claude" / "session.md").write_text("# Session checkpoint\n\nWork on claude/10.\n")
            code, lines = run_init(root)
            self.assertEqual(code, 0)
            self.assertEqual((root / ".claude" / "session.md").read_text(), template_init.BLANK_CHECKPOINT)
            self.assertIn(".claude/session.md: reset to a blank checkpoint", lines)

    def test_a_blank_checkpoint_is_left_alone(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tiny_tree(root)
            (root / ".claude" / "session.md").write_text(template_init.BLANK_CHECKPOINT)
            code, lines = run_init(root)
            self.assertNotIn(".claude/session.md: reset to a blank checkpoint", lines)


BEGIN, END = template_init.marked_section.MARK_BEGIN, template_init.marked_section.MARK_END
INTRO = "## Session checkpoint (kept by cswap)\n\nRead `.claude/session.md` first.\n\n"
TEMPLATE_BLOCK = (BEGIN + "\n" + INTRO + "### Durable decisions\n- The template's own decision.\n"
                  "### Constraints\n- The template's own constraint.\n" + END)
EMPTY_BLOCK = BEGIN + "\n" + INTRO + template_init.BLANK_LISTS + "\n" + END
CLAUDE_TEXT = "# {name}\n\nThe project's own instructions.\n\n{block}\n"
FILLED_LISTS = "### Durable decisions\n- A decision of the template's.\n### Constraints\n- A constraint of the template's."


def with_filled_lists(text):
    """CLAUDE.md as the template has it, its checkpoint block's lists holding
    an item each, whatever they hold in the repository the tests run in: a
    copy's are already empty. The heading and the intro are the file's own."""
    begin = text.index(BEGIN)
    end = text.index(END, begin) + len(END)
    head = text[begin:text.index("\n### ", begin) + 1]
    return text[:begin] + head + FILLED_LISTS + "\n" + END + text[end:]


class CheckpointBlock(unittest.TestCase):
    """The decisions and constraints at the end of CLAUDE.md are the
    template's; a copy keeps the block's heading and intro and starts with
    both lists empty, in the shape the checkpoint skill writes."""

    def init_with(self, text, newline="\n"):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tiny_tree(root)
            write(root, "CLAUDE.md", text.replace("\n", newline))
            code, lines = run_init(root)
            after = (root / "CLAUDE.md").read_bytes().decode("utf-8")
            again = run_init(root)[1]
        return code, lines, after, again

    def test_a_copy_starts_with_the_empty_lists_and_keeps_the_rest(self):
        code, lines, after, again = self.init_with(CLAUDE_TEXT.format(name="x", block=TEMPLATE_BLOCK))
        self.assertEqual(code, 0)
        self.assertEqual(after, CLAUDE_TEXT.format(name="x", block=EMPTY_BLOCK))
        self.assertIn("CLAUDE.md: checkpoint block emptied of the template's decisions and constraints", lines)
        self.assertEqual(again, [])

    def test_the_empty_form_is_one_line_per_list(self):
        self.assertEqual(template_init.BLANK_LISTS,
                         "### Durable decisions\n- (none recorded)\n### Constraints\n- (none recorded)")

    @template_only
    def test_the_empty_form_is_the_checkpoint_skills(self):
        # Crowd mode ships its own checkpoint skill (docs/setup/crowd/checkpoint-skill.md),
        # which never edits the block, so only the template's names the empty form.
        skill = (ROOT / ".claude" / "skills" / "checkpoint" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`### Durable decisions` and `### Constraints`, each followed by one `- ` line per item, "
                      "or `- (none recorded)`", skill)

    def test_a_crlf_file_stays_crlf(self):
        _, _, after, _ = self.init_with(CLAUDE_TEXT.format(name="x", block=TEMPLATE_BLOCK), newline="\r\n")
        self.assertEqual(after, CLAUDE_TEXT.format(name="x", block=EMPTY_BLOCK).replace("\n", "\r\n"))

    def test_a_file_without_the_markers_is_left_alone(self):
        text = "# x\n\nNo checkpoint block here.\n"
        _, lines, after, _ = self.init_with(text)
        self.assertEqual(after, text)
        self.assertFalse([line for line in lines if line.startswith("CLAUDE.md:")])

    def empties_to_the_skills_shape(self, text):
        """reset_checkpoint_block changes a file holding this text, keeps all
        outside the block and the block's own heading and intro, and ends the
        block with the empty lists."""
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "CLAUDE.md").write_text(text, encoding="utf-8")
            self.assertEqual(template_init.reset_checkpoint_block(Path(folder)), ["CLAUDE.md"])
            after = (Path(folder) / "CLAUDE.md").read_text(encoding="utf-8")
        begin = text.index(BEGIN)
        end = text.index(END, begin) + len(END)
        head = text[begin:text.index("\n### ", begin) + 1]
        self.assertTrue(head.startswith(BEGIN + "\n## Session checkpoint (kept by cswap)\n\n"))
        self.assertTrue(head.endswith("\n\n"))
        self.assertEqual(after, text[:begin] + head + template_init.BLANK_LISTS + "\n" + END + text[end:])

    def test_the_repositorys_block_holding_items_empties_to_the_skills_shape(self):
        self.empties_to_the_skills_shape(with_filled_lists((ROOT / "CLAUDE.md").read_text(encoding="utf-8")))

    @template_only
    def test_the_templates_own_block_empties_to_the_skills_shape(self):
        self.empties_to_the_skills_shape((ROOT / "CLAUDE.md").read_text(encoding="utf-8"))


class Init(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        tiny_tree(self.root)
        self.code, self.lines = run_init(self.root)

    def tearDown(self):
        self.folder.cleanup()

    def test_exits_0_and_fills_every_placeholder_outside_the_workflows(self):
        self.assertEqual(self.code, 0)
        self.assertEqual((self.root / "README.md").read_text(), "# widgets\n\nClone octo/widgets; the default branch is main.\n")
        self.assertEqual((self.root / "LICENSE").read_text(), "MIT License\n\nCopyright (c) 2026 octo\n")
        self.assertEqual((self.root / ".github" / "CODEOWNERS").read_text(), "* @octo\n")
        self.assertEqual((self.root / ".claude" / "hooks" / "session-start.sh").read_text(), "#!/usr/bin/env bash\nprintf '%s\\n' \"main\"\n")
        for path, data in tree_bytes(self.root).items():
            if path.startswith(".git/") or path.startswith(".github/workflows/"):
                continue
            for marker in P.values():
                self.assertNotIn(marker.encode(), data, path)

    def test_leaves_the_workflows_as_they_are(self):
        self.assertEqual((self.root / ".github" / "workflows" / "ci.yml").read_text(), WORKFLOW)
        self.assertEqual((self.root / ".github" / "workflows" / "template-init.yml").read_text(), INIT_WORKFLOW)

    def test_removes_the_marker_folder_only(self):
        self.assertFalse((self.root / ".template").exists())
        self.assertEqual(template_init.REMOVED, (".template",))

    def test_leaves_everything_else_alone(self):
        self.assertEqual((self.root / "docs" / "plain.md").read_bytes(), PLAIN.encode())
        self.assertEqual((self.root / "data" / "blob.bin").read_bytes(), BINARY)
        self.assertEqual((self.root / ".git" / "config").read_text(), f"[remote]\n\turl = {P['REPO']}\n")

    def test_prints_each_changed_or_deleted_path_and_the_note_once(self):
        self.assertEqual(self.lines, [
            ".claude/hooks/session-start.sh: filled",
            ".github/CODEOWNERS: filled",
            "LICENSE: filled",
            "README.md: filled",
            "(workflows are left as they are: GITHUB_TOKEN may not write them)",
            ".template/: deleted",
        ])

    def test_a_second_run_changes_nothing(self):
        before = tree_bytes(self.root)
        code, lines = run_init(self.root)
        self.assertEqual(code, 0)
        self.assertEqual(lines, [])
        self.assertEqual(tree_bytes(self.root), before)

    def test_api_flags_without_a_token_exit_1(self):
        import os
        from contextlib import redirect_stderr
        saved = os.environ.pop("GITHUB_TOKEN", None)
        held = io.StringIO()
        try:
            with redirect_stderr(held):
                code, _ = run_init(self.root, ["--create-labels"])
        finally:
            if saved is not None:
                os.environ["GITHUB_TOKEN"] = saved
        self.assertEqual(code, 1)
        self.assertIn("GITHUB_TOKEN", held.getvalue())


class Labels(unittest.TestCase):
    def test_the_six_labels_and_their_colours(self):
        self.assertEqual(
            [(name, color) for name, color, _ in template_init.LABELS],
            [("todo", "0e8a16"), ("claimed", "fbca04"), ("in-review", "1d76db"), ("blocker", "b60205"),
             ("epic", "8b5cf6"), ("blocked", "e99695")],
        )

    def test_the_labels_are_the_protocols_word_for_word(self):
        sys.path.insert(0, str(ROOT / "tools"))
        from sdlc_protocol import labels
        self.assertEqual(template_init.LABELS, labels.LABELS)

    def test_already_exists_reads_the_422(self):
        self.assertTrue(template_init.already_exists({"errors": [{"resource": "Label", "code": "already_exists"}]}))
        self.assertFalse(template_init.already_exists({"errors": [{"code": "invalid"}]}))
        self.assertFalse(template_init.already_exists(None))

    def test_the_setup_issue_links_the_nine_pages(self):
        body = template_init.setup_issue_body("octo/widgets", "main")
        for page in ("docs/setup/github.md", "docs/setup/claude-action.md", "docs/setup/claude-project.md", "docs/agents/routines/worker.md", "docs/agents/WORKERS.md", "docs/agents/routines/coordinator.md", "docs/project.md", "docs/agents/OWNERSHIP.md", "docs/setup/tiers.md"):
            self.assertIn(f"https://github.com/octo/widgets/blob/main/{page}", body)
        self.assertIn("bash scripts/check.sh", body)
        self.assertIn("ruleset-main.json", body)
        self.assertIn("/install-github-app", body)
        self.assertIn("https://github.com/octo/widgets/blob/main/.github/CODEOWNERS", body)
        self.assertEqual(body.count("- [ ]"), 6)

    def test_the_setup_issue_points_a_crowd_project_at_crowd_py_before_the_boxes(self):
        body = template_init.setup_issue_body("octo/widgets", "main")
        first = body.splitlines()[0]
        self.assertIn("python3 scripts/crowd.py setup", first)
        self.assertIn("https://github.com/octo/widgets/blob/main/docs/setup/crowdsourcing.md", first)

    def test_the_setup_issue_opens_with_the_one_command_and_links_every_settings_page(self):
        body = template_init.setup_issue_body("octo/widgets", "main")
        self.assertTrue(body.splitlines()[2].startswith("- [ ] Run `bash scripts/setup-repo.sh` once from your clone, with gh signed in; or by hand:"))
        settings = "https://github.com/octo/widgets/settings"
        for page in (f"{settings}/rules", f"{settings})", f"{settings}/actions)", f"{settings}/security_analysis",
                     "https://github.com/octo/widgets/labels", f"{settings}/secrets/actions/new",
                     "https://github.com/octo/widgets/issues/new?template=worker.yml", template_init.APP_INSTALL):
            self.assertIn(page, body)
        # The by-hand path names each setting setup-repo.sh turns on, as
        # the settings pages label it.
        for setting in ("Automatically delete head branches", "Allow auto-merge",
                        "Allow GitHub Actions to create and approve pull requests"):
            self.assertIn(f'"{setting}"', body.splitlines()[2])
        for target in re.findall(r"\]\(([^)]+)\)", body):
            self.assertTrue(target.startswith("https://"), target)

    def test_the_app_link_preselects_the_owner_and_the_repository(self):
        link = template_init.app_install_link(285817514, 1411163972)
        self.assertEqual(link, "https://github.com/apps/claude/installations/new/permissions?suggested_target_id=285817514&repository_ids[]=1411163972")
        self.assertIn(f"[install the app]({link})", template_init.setup_issue_body("octo/widgets", "main", link))


class FakeRequest:
    """Stands in for template_init.request: answers by method and path, and
    remembers every call; a path it has no answer for is a 404."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, token, method, path, body=None, params=None):
        self.calls.append((method, path, body))
        return self.answers.get((method, path), (404, None))


class SetupIssue(unittest.TestCase):
    OPENED = (201, {"number": 1})
    REPO = (200, {"id": 1411163972, "owner": {"id": 285817514}})

    def open_with(self, answers):
        fake = FakeRequest({("GET", "/repos/octo/widgets/issues"): (200, []), ("POST", "/repos/octo/widgets/issues"): self.OPENED, **answers})
        with patch.object(template_init, "request", fake):
            line = template_init.open_setup_issue("t", "octo/widgets", "main")
        posted = [body for method, path, body in fake.calls if method == "POST"]
        return line, fake.calls, posted[0]["body"] if posted else None

    def test_one_get_of_the_repository_gives_the_preselected_install_link(self):
        line, calls, body = self.open_with({("GET", "/repos/octo/widgets"): self.REPO})
        self.assertEqual(line, "issue #1: opened")
        self.assertEqual([(m, p) for m, p, _ in calls], [("GET", "/repos/octo/widgets/issues"), ("GET", "/repos/octo/widgets"), ("POST", "/repos/octo/widgets/issues")])
        self.assertIn(template_init.app_install_link(285817514, 1411163972), body)

    def test_a_failed_get_falls_back_to_the_plain_install_link(self):
        for answer in ((404, None), (200, {"id": 1}), (200, "not json we expect")):
            line, _, body = self.open_with({("GET", "/repos/octo/widgets"): answer})
            self.assertEqual(line, "issue #1: opened")
            self.assertIn(f"[install the app]({template_init.APP_INSTALL})", body)
            self.assertNotIn("suggested_target_id", body)

    def test_an_open_setup_issue_is_not_opened_again(self):
        fake = FakeRequest({("GET", "/repos/octo/widgets/issues"): (200, [{"number": 4, "title": template_init.SETUP_ISSUE_TITLE}])})
        with patch.object(template_init, "request", fake):
            self.assertEqual(template_init.open_setup_issue("t", "octo/widgets", "main"), "issue #4: exists")
        self.assertEqual(len(fake.calls), 1)


if __name__ == "__main__":
    unittest.main()
