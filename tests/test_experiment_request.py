"""A run request from the textbook's panel, the Experiment form or the Claude box: tools/experiments_panel.py
reads both spellings and refuses what data/recipes/ and src/schwingnet/blocks.py do not hold; the Experiment
form is written from those lists and held current; tools/experiment_run.py answers an issue once with the
command, the gate word and the owner's click and refuses a reader; and the workflow runs main's code on its
two events, with the write token in the steps that need it and no expression inside a run block."""

import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


panel = load("experiments_panel")
clerk = load("experiment_run")
CATALOG = panel.block_catalog(ROOT)
RECIPES = [r["name"] for r in panel.recipes(ROOT)]
WORKFLOW = ROOT / ".github" / "workflows" / "experiment.yml"


def lines(*blocks, recipe="none", epochs="20", seed="1", hours="4", marker=True):
    """An issue body as the panel writes it."""
    out = [panel.ISSUE_MARKER] if marker else []
    out += [f"recipe: {recipe}", f"epochs: {epochs}", f"seed: {seed}", f"hours: {hours}"] + [f"block: {b}" for b in blocks]
    return "\n".join(out) + "\n\nRequested from the panel.\n\nThe command this names:\n\n    python3 tools/flow.py run --block x\n"


def form(**sections):
    """An issue body as GitHub renders a form submission: each field as a heading with its value below."""
    return "".join(f"### {key}\n\n{value}\n\n" for key, value in sections.items())


def check(body):
    return panel.check_request(body, ROOT)


def problems(body):
    return check(body)[1]


class TheRequestIsRead(unittest.TestCase):
    def test_the_panels_lines_are_read_and_normalised(self):
        default = CATALOG["defaults"]["normalise"]
        record, found = check(lines("architecture=resnet34", f"normalise={default}", "augment=box-jitter,intensity", hours="6.0", recipe="non-commercial"))
        self.assertEqual(found, [])
        self.assertEqual(record, {"recipe": "non-commercial", "epochs": 20, "seed": 1, "hours": 6.0,
                                  "blocks": ["augment=box-jitter,intensity", "architecture=resnet34"]})
        self.assertEqual(panel.request_lines(record), "recipe: non-commercial\nepochs: 20\nseed: 1\nhours: 6\nblock: augment=box-jitter,intensity\nblock: architecture=resnet34\n")
        self.assertEqual(panel.request_command(record), panel.FLOW_HEAD + " --epochs 20 --seed 1 --hours 6 --recipe non-commercial --block augment=box-jitter,intensity --block architecture=resnet34")
        self.assertTrue(panel.driver_command(record).startswith(panel.DRIVER_HEAD + " --epochs 20 --seed 1 --hours 6 --weights <weights> --recipe non-commercial"))

    def test_the_forms_sections_are_read(self):
        body = form(recipe="none", epochs="20", seed="1", hours="4", architecture="resnet50", augment="- [x] box-jitter\n- [ ] intensity\n- [X] blur",
                    weight_decay="0.0", prior="_No response_", sources="_No response_", note="recipe: junk in a note is prose\nblock: nothing=1")
        record, found = check(body)
        self.assertEqual(found, [])
        self.assertEqual(record["blocks"], ["augment=box-jitter,blur", "architecture=resnet50"])
        self.assertEqual((record["recipe"], record["epochs"], record["seed"], record["hours"]), ("none", 20, 1, 4.0))

    def test_a_setting_given_twice_or_missing_is_a_problem(self):
        twice = lines() + "\nepochs: 30\n"
        self.assertIn("epochs is given twice", problems(twice))
        self.assertEqual(problems("### epochs\n\n20\n\n### note\n\nnothing\n"), ["recipe is missing", "seed is missing", "hours is missing"])
        self.assertEqual(problems("")[:1], ["recipe is missing"])
        self.assertIn("the body has more than 400 lines", problems("x\n" * 500))

    def test_every_way_a_value_does_not_hold_is_named(self):
        cases = {
            lines(recipe="bogus"): "recipe bogus is not none nor one of data/recipes/: " + ", ".join(RECIPES),
            lines(epochs="0"): "epochs is a whole number from 1 to 200, not 0",
            lines(epochs="201"): "epochs is a whole number from 1 to 200, not 201",
            lines(epochs="x"): "epochs is a whole number from 1 to 200, not x",
            lines(seed="-1"): "seed is a whole number, 0 or more, not -1",
            lines(hours="0"): "hours is a number above 0 and at most 48, not 0",
            lines(hours="49"): "hours is a number above 0 and at most 48, not 49",
            lines(hours="1e3"): "hours is a number above 0 and at most 48, not 1e3",
            lines("nothing=1"): "nothing is not a block; the blocks are " + ", ".join(CATALOG["fields"]),
            lines("architecture=vit"): "architecture=vit is not one of " + ", ".join(CATALOG["choices"]["architecture"]),
            lines("augment=fog"): "augment fog is not one of " + ", ".join(CATALOG["options"]["augment"]),
            lines("augment=blur,blur"): "augment names one part twice",
            lines("sources=Vin-Dr"): "sources Vin-Dr is not a source's name (lower-case letters, digits and _)",
            lines("warmup_epochs=1.5"): "warmup_epochs is a whole number, 0 or more, not 1.5",
            lines("weight_decay=abc"): "weight_decay is a plain number, 0 or more, not abc",
            lines("backbone_lr_scale=2"): "backbone_lr_scale is above 0 and at most 1",
            lines("architecture=resnet34", "architecture=resnet50"): "block architecture is named twice",
            lines("architecture"): "block architecture is not KEY=VALUE",
            lines("architecture=resnet34;rm"): "architecture=resnet34;rm holds a character outside letters, digits and . _ , - or is over 80 characters",
            lines("optimiser=adam", "weight_decay=0.1"): "weight_decay is for adamw; adam's would be L2 in the gradient, which this trainer does not offer",
            lines("sources=vindr_pcxr"): "sources=a,b goes with samples=only-sources or drop-sources, and only there",
            lines("per_person=3"): "per_person of 1 or more goes with samples=cap-per-person, and only there",
        }
        if "prior" in CATALOG["choices"]:
            cases[lines("prior_weight=0.5")] = "prior_weight above 0 goes with prior=level-map, and only there"
        for body, expected in cases.items():
            found = problems(body)
            self.assertIn(expected, found, body)
            self.assertIsNone(check(body)[0])

    def test_a_request_that_holds_passes_the_command_line_and_one_that_does_not_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            good, bad = Path(tmp) / "good.txt", Path(tmp) / "bad.txt"
            good.write_text(lines("architecture=resnet34", seed="7"), encoding="utf-8")
            bad.write_text(lines(epochs="999"), encoding="utf-8")
            self.assertEqual(panel.main(["check", "--request", str(good), "--root", str(ROOT)]), 0)
            self.assertEqual(panel.main(["check", "--request", str(bad), "--root", str(ROOT)]), 1)


def parse_form(text):
    """The form's fields as (type, id, label, options, default, value), from its YAML text."""
    fields, field = [], None
    for line in text.splitlines():
        kind = re.match(r"^  - type: (\w+)$", line)
        if kind:
            field = {"type": kind.group(1), "options": [], "default": None, "value": None, "id": None, "label": None}
            fields.append(field)
            continue
        if field is None:
            continue
        for key in ("id", "label"):
            m = re.match(rf"^    (?:  )?{key}: (.+)$", line)
            if m and field[key] is None:
                field[key] = m.group(1)
        m = re.match(r"^        - (?:label: )?(.+)$", line)
        if m:
            field["options"].append(m.group(1))
        m = re.match(r"^      default: (\d+)$", line)
        if m:
            field["default"] = int(m.group(1))
        m = re.match(r'^      value: "(.*)"$', line)
        if m:
            field["value"] = m.group(1)
    return fields


class TheForm(unittest.TestCase):
    def test_the_form_is_written_from_the_lists_and_is_current(self):
        text = (ROOT / panel.FORM).read_text(encoding="utf-8")
        self.assertEqual(panel.form_text(CATALOG, RECIPES), text)
        self.assertEqual(panel.stale(ROOT), [])
        self.assertIn('labels: ["experiment"]', text)
        fields = [f for f in parse_form(text) if f["type"] != "markdown"]
        ids = [f["id"] for f in fields]
        self.assertEqual(ids, ["recipe", "epochs", "seed", "hours"] + CATALOG["fields"] + ["note"])
        self.assertEqual(len(set(ids)), len(ids))
        for f in fields:
            self.assertEqual(f["label"], f["id"], "the heading the validator reads is the key")
        by_id = {f["id"]: f for f in fields}
        self.assertEqual(by_id["recipe"]["options"], ["none"] + RECIPES)
        self.assertEqual(by_id["recipe"]["default"], 0)
        for name, choices in CATALOG["choices"].items():
            self.assertEqual(by_id[name]["type"], "dropdown", name)
            self.assertEqual(by_id[name]["options"], choices, name)
            self.assertEqual(choices[by_id[name]["default"]], CATALOG["defaults"][name], name)
        self.assertEqual(by_id["augment"]["type"], "checkboxes")
        self.assertEqual(by_id["augment"]["options"], CATALOG["options"]["augment"])
        for name in CATALOG["numbers"] + CATALOG["counts"]:
            self.assertEqual(by_id[name]["type"], "input", name)
            self.assertEqual(by_id[name]["value"], panel.word_of(CATALOG["defaults"][name]), name)
        self.assertEqual(by_id["note"]["type"], "textarea")

    def test_a_submission_of_the_form_reads_back_as_the_request(self):
        fields = [f for f in parse_form((ROOT / panel.FORM).read_text(encoding="utf-8")) if f["type"] != "markdown"]

        def rendered(changes):
            parts = {}
            for f in fields:
                if f["id"] in changes:
                    parts[f["id"]] = changes[f["id"]]
                elif f["type"] == "dropdown":
                    parts[f["id"]] = f["options"][f["default"]]
                elif f["type"] == "checkboxes":
                    parts[f["id"]] = "\n".join(f"- [ ] {o}" for o in f["options"])
                else:
                    parts[f["id"]] = f["value"] if f["value"] is not None else "_No response_"
            return form(**parts)

        record, found = check(rendered({}))
        self.assertEqual(found, [])
        self.assertEqual(record, {"recipe": "none", "epochs": 20, "seed": 1, "hours": 4.0, "blocks": []})
        record, found = check(rendered({"architecture": "resnet34", "epochs": "7", "augment": "- [x] blur\n- [ ] noise"}))
        self.assertEqual(found, [])
        self.assertEqual((record["epochs"], record["blocks"]), (7, ["augment=blur", "architecture=resnet34"]))
        self.assertIn("architecture=vit is not one of", " ".join(problems(rendered({"architecture": "vit"}))))


def issue(body, association="OWNER", labels=("experiment",), number=250):
    return {"number": number, "body": body, "author_association": association, "labels": [{"name": n} for n in labels]}


class TheClerk(unittest.TestCase):
    def decide(self, iss, action="opened", label=None, actor=None):
        return clerk.decide(iss, ROOT, "OpenSpineConsortium/SchwingNet", action, label, actor)

    def test_a_writer_is_answered_and_a_reader_refused(self):
        held = self.decide(issue(lines("architecture=resnet34")))
        self.assertEqual(held["action"], "record")
        for association in ("NONE", "CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", None):
            refused = self.decide(issue(lines(), association))
            self.assertEqual(refused["action"], "refuse", association)
            self.assertTrue(refused["comment"].startswith(clerk.REFUSED))
            self.assertIn("Nothing was recorded", refused["comment"])

    def test_the_answer_names_the_lines_the_commands_the_word_and_the_click(self):
        held = self.decide(issue(lines("architecture=resnet34", seed="2", hours="6")))
        comment = held["comment"]
        self.assertTrue(comment.startswith(clerk.MARKER + "\n"))
        self.assertEqual(held["request"], "recipe: none\nepochs: 20\nseed: 2\nhours: 6\nblock: architecture=resnet34\n")
        self.assertIn(held["request"], comment)
        self.assertIn(held["command"], comment)
        self.assertIn(panel.DRIVER_HEAD + " --epochs 20 --seed 2 --hours 6 --weights <weights> --block architecture=resnet34", comment)
        self.assertIn("`schwingnet-experiment-250`", comment)
        self.assertIn(clerk.GATE_WORKFLOW, comment)
        self.assertIn("choose the action `job`, write `schwingnet-experiment-250` under job", comment)
        self.assertIn("bash ~/SchwingNet/grid/gate.sh experiment 250", comment)
        self.assertIn("`250.request` on the branch `experiments`", comment)
        self.assertIn("Nothing is queued by this comment", comment)
        self.assertEqual(held["title"], "Experiment: architecture=resnet34, 20 epochs")

    def test_an_invalid_request_lists_every_problem_and_records_nothing(self):
        bad = self.decide(issue(lines("architecture=vit", epochs="999")))
        self.assertEqual(bad["action"], "invalid")
        self.assertTrue(bad["comment"].startswith(clerk.REFUSED))
        self.assertIn("epochs is a whole number from 1 to 200, not 999", bad["comment"])
        self.assertIn("architecture=vit is not one of", bad["comment"])
        self.assertIn("Nothing was recorded", bad["comment"])
        self.assertNotIn("request", bad)
        empty = self.decide(issue("Please run something.", labels=("experiment",)))
        self.assertEqual(empty["action"], "invalid")
        self.assertIn("carries no request this workflow reads", empty["comment"])

    def test_a_form_submission_without_the_label_is_still_a_request(self):
        # The form names the label experiment, which GitHub puts on only where the label exists; the
        # sections say what the issue is, and the workflow puts the label on when it records. A line
        # that looks like a setting in an unlabelled issue of any other shape is nobody's request.
        body = ("### recipe\n\nnone\n\n### epochs\n\n12\n\n### seed\n\n3\n\n### hours\n\n2\n\n"
                "### architecture\n\nresnet34\n\n### note\n\nFrom the form, with no label in the repository.\n")
        done = self.decide(issue(body, labels=()))
        self.assertEqual(done["action"], "record", done)
        self.assertIn("block: architecture=resnet34", done["request"])
        self.assertEqual(self.decide(issue("A question about the panel.\n\nseed: 3\n", labels=()))["action"], "skip")

    def test_other_events_labels_and_issues_are_skipped(self):
        self.assertEqual(self.decide(issue(lines()), "labeled", "todo")["action"], "skip")
        self.assertEqual(self.decide(issue(lines()), "labeled", "experiment")["action"], "record")
        self.assertEqual(self.decide(issue(lines()), "edited")["action"], "skip")
        self.assertEqual(self.decide(issue("A task.", labels=("todo",)))["action"], "skip")
        self.assertEqual(self.decide(issue(lines(), labels=()))["action"], "record", "the marker alone names a request")
        self.assertEqual(self.decide(issue(lines(marker=False), labels=()))["action"], "skip")

    def test_a_dispatch_is_the_actors_whatever_the_issues_author(self):
        held = self.decide(issue(lines("optimiser=adamw"), association="NONE"), actor="someone")
        self.assertEqual(held["action"], "record")
        self.assertIn("asked for by someone (Run as me in the textbook)", held["comment"])

    def test_the_dispatchs_inputs_become_the_issue_or_are_refused_whole(self):
        env = {"INPUT_RECIPE": "none", "INPUT_EPOCHS": "12", "INPUT_SEED": "3", "INPUT_HOURS": "2.5", "INPUT_BLOCKS": "architecture=resnet34  optimiser=adamw"}
        title, body = clerk.request_from_inputs(env, ROOT)
        self.assertEqual(title, "Experiment: optimiser=adamw architecture=resnet34, 12 epochs")
        self.assertTrue(body.startswith(panel.ISSUE_MARKER + "\nrecipe: none\nepochs: 12\nseed: 3\nhours: 2.5\nblock: architecture=resnet34\nblock: optimiser=adamw\n"))
        self.assertEqual(check(body)[1], [])
        with self.assertRaises(SystemExit) as why:
            clerk.request_from_inputs(dict(env, INPUT_EPOCHS="0", INPUT_BLOCKS="nothing=1"), ROOT)
        self.assertIn("epochs is a whole number", str(why.exception))
        self.assertIn("nothing is not a block", str(why.exception))

    def test_plan_writes_the_comment_the_request_the_readme_and_the_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "event.json").write_text(json.dumps({"action": "opened", "issue": issue(lines("architecture=resnet34"))}), encoding="utf-8")
            outputs = tmp / "outputs"
            os.environ["GITHUB_OUTPUT"] = str(outputs)
            try:
                code = clerk.main(["plan", "--event", str(tmp / "event.json"), "--repo", "OpenSpineConsortium/SchwingNet", "--comment", str(tmp / "c.md"),
                                   "--request", str(tmp / "r.txt"), "--readme", str(tmp / "README.md"), "--root", str(ROOT)])
            finally:
                del os.environ["GITHUB_OUTPUT"]
            self.assertEqual(code, 0)
            self.assertEqual(outputs.read_text(encoding="utf-8"), "action=record\nissue=250\ntitle=Experiment: architecture=resnet34, 20 epochs\n")
            self.assertTrue((tmp / "c.md").read_text(encoding="utf-8").startswith(clerk.MARKER))
            self.assertEqual((tmp / "r.txt").read_text(encoding="utf-8"), "recipe: none\nepochs: 20\nseed: 1\nhours: 4\nblock: architecture=resnet34\n")
            self.assertIn("schwingnet-experiment-<issue>", (tmp / "README.md").read_text(encoding="utf-8"))
            with self.assertRaises(SystemExit):
                clerk.main(["plan", "--repo", "r", "--comment", "c", "--request", "r", "--readme", "m"])


class TheWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_it_runs_on_the_two_events_with_the_five_inputs(self):
        self.assertIn("  issues:\n    types: [opened, labeled]\n  workflow_dispatch:\n    inputs:\n", self.text)
        for name in clerk.INPUTS:
            self.assertIn(f"      {name}:\n", self.text)
        self.assertIn("github.event_name == 'workflow_dispatch' || github.event.action == 'opened' || github.event.label.name == 'experiment'", self.text)
        self.assertIn("github.event.repository.fork == false", self.text)
        self.assertIn("  group: experiment-${{ github.event.issue.number || github.run_id }}", self.text)

    def test_the_token_writes_only_where_it_must_and_main_s_code_alone_runs(self):
        self.assertIn("\npermissions:\n  contents: read\n", self.text)
        self.assertIn("    permissions:\n      contents: write\n      issues: write\n", self.text)
        self.assertRegex(self.text, r"uses: actions/checkout@[0-9a-f]{40} # v")
        self.assertIn("persist-credentials: false", self.text)
        self.assertNotIn("secrets.", self.text)
        self.assertNotIn("ref: ${{", self.text, "the checkout is main's, the event's default")

    def test_the_steps_run_the_clerk_answer_once_hold_and_record(self):
        for command in ("python3 tools/experiment_run.py request --body", "python3 tools/experiment_run.py plan --issue-json", "--actor \"$ACTOR\"",
                        "python3 tools/experiment_run.py plan --event \"$GITHUB_EVENT_PATH\"", 'startswith("<!-- schwingnet-experiment:")',
                        "--add-label experiment,owner-act", '"$commit:refs/heads/experiments"', "x-access-token:${GH_TOKEN}@github.com/${REPO}.git",
                        "git ls-tree -r --name-only", "--label experiment --title"):
            self.assertIn(command, self.text, command)
        self.assertIn("if: steps.plan.outputs.action == 'record' && steps.answer.outputs.answered != 'yes'", self.text)

    def test_no_expression_is_written_into_a_run_block(self):
        block, indent = False, 0
        for line in self.text.splitlines():
            if re.match(r"^\s+run: \|", line):
                block, indent = True, len(line) - len(line.lstrip())
                continue
            if block and line.strip() and (len(line) - len(line.lstrip())) <= indent:
                block = False
            if block:
                self.assertNotIn("${{", line, line)

    def test_the_gate_the_readme_and_the_brief_name_the_word(self):
        gate = (ROOT / "grid" / "gate.sh").read_text(encoding="utf-8")
        self.assertIn("  experiment) word_experiment ;;", gate)
        self.assertIn("experiment-driver.sbatch", gate)
        self.assertIn("| `experiment <issue>` |", (ROOT / "grid" / "README.md").read_text(encoding="utf-8"))
        brief = (ROOT / ".github" / "symphony" / "research.md").read_text(encoding="utf-8")
        self.assertIn("experiment <issue>", brief)
        self.assertIn("labelled experiment", brief)


if __name__ == "__main__":
    unittest.main()
