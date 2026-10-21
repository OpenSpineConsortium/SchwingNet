"""The run record, the interval, the ledger row and the sbatch text: the flow's pure rules."""

import importlib.util
import json
import math
import sqlite3
import sys
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ValidationError

from schwingnet.flow import (
    JobRecord,
    JobSpec,
    ResultRow,
    RunRecord,
    Stage,
    Step,
    gpu_hours,
    ledger_row,
    result_line,
    run_id,
    wall_hours,
    wilson,
)
from schwingnet.slurm import elapsed_seconds, is_finished, job_id_of, sbatch_script, wall_time

ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 64
COMMIT = "0123abc"
START = "2026-10-21T03:00:00Z"


def load_tool(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def record(**changes: object) -> RunRecord:
    facts: dict[str, object] = {
        "run_id": run_id(COMMIT, SHA, START),
        "code_commit": COMMIT,
        "clean_tree": True,
        "catalog_version": 1,
        "catalog_sha256": SHA,
        "split_disjoint": True,
        "stage": Stage.LEVEL,
        "seed": 1,
        "epochs": 3,
        "started_at": START,
        "mode": "local",
    }
    facts.update(changes)
    return RunRecord.model_validate(facts)


def test_a_run_record_refuses_a_dirty_tree_a_leaky_split_and_a_forged_id() -> None:
    assert record().run_id == run_id(COMMIT, SHA, START)
    with pytest.raises(ValidationError, match="dirty tree"):
        record(clean_tree=False)
    with pytest.raises(ValidationError, match="not disjoint"):
        record(split_disjoint=False)
    with pytest.raises(ValidationError, match="run id"):
        record(run_id="0" * 12)
    assert run_id(COMMIT, SHA, START) != run_id(COMMIT, SHA, "2026-10-21T03:00:01Z")


def test_the_wilson_interval_holds_the_point_and_narrows_with_n() -> None:
    low, high = wilson(0, 10)
    assert low == 0.0 and 0.0 < high < 0.35
    low, high = wilson(10, 10)
    assert high == 1.0 and 0.65 < low < 1.0
    narrow = wilson(500, 1000)
    wide = wilson(5, 10)
    assert narrow[1] - narrow[0] < wide[1] - wide[0]
    assert math.isclose(sum(wilson(50, 100)) / 2, 0.5, abs_tol=0.01)


def jobs() -> tuple[JobRecord, ...]:
    return (
        JobRecord(step=Step.TRAIN, job_id="1", partition="gmsap", hours_requested=4, seconds_used=3600, gpus=1, preemptions=0, exit_code=0),
        JobRecord(step=Step.EVALUATE, job_id="2", partition="gmsap", hours_requested=1, seconds_used=1800, gpus=1, preemptions=1, exit_code=0),
    )


def test_the_spend_is_summed_from_the_jobs_and_the_ledger_row_is_one_line() -> None:
    assert gpu_hours(jobs()) == 1.5
    assert wall_hours(jobs()) == 1.5
    row = ledger_row(record(jobs=jobs()), "level | stage\nsmoke", "results.md")
    assert row.count("|") == 10 and "\n" not in row and "level / stage smoke" in row
    assert "1.50 h wall, 1.50 GPU h" in row


def test_a_result_row_is_stamped_and_its_line_carries_the_interval() -> None:
    row = ResultRow(measure="accuracy", stratum="all levels", correct=9, total=10, persons=3, run_id=run_id(COMMIT, SHA, START), code_commit=COMMIT, clean_tree=True, catalog_sha256=SHA)
    line = result_line(row)
    assert "9/10" in line and "0.900" in line and " to " in line and line.count("|") == 10
    with pytest.raises(ValidationError):
        ResultRow(measure="accuracy", stratum="s", correct=11, total=10, persons=1, run_id=row.run_id, code_commit=COMMIT, clean_tree=True, catalog_sha256=SHA)
    with pytest.raises(ValidationError, match="dirty"):
        ResultRow(measure="accuracy", stratum="s", correct=1, total=10, persons=1, run_id=row.run_id, code_commit=COMMIT, clean_tree=False, catalog_sha256=SHA)


def test_the_sbatch_script_carries_the_grid_rules_and_nothing_secret() -> None:
    job = JobSpec(step=Step.TRAIN, command="python tools/train.py --out /runs/x", partition="gmsap", qos=None, cpus=4, memory_gb=32, gpus=1, hours=2.5, environment="train-gpu")
    text = sbatch_script(job, "/runs/x", "/home/me/schwingnet")
    assert "#SBATCH --time=02:30:00" in text and "#SBATCH --gres=gpu:1" in text
    assert "#SBATCH --chdir=/runs/x" in text and "exec pixi run --locked -e train-gpu python" in text
    cpu = job.model_copy(update={"partition": "reqp", "qos": "requeue", "gpus": 0})
    cpu_text = sbatch_script(cpu, "/runs/x", "/home/me/schwingnet")
    assert "--qos=requeue" in cpu_text and "gres" not in cpu_text
    assert wall_time(0.01) == "00:01:00" and wall_time(25.0) == "25:00:00"
    assert job_id_of("Submitted batch job 123456\n") == "123456" and job_id_of("sbatch: error") is None
    assert elapsed_seconds("1-02:03:04") == 93784 and elapsed_seconds("00:00:30") == 30
    assert is_finished("COMPLETED") and is_finished("CANCELLED by 1234") and not is_finished("RUNNING") and not is_finished("")


def test_the_synthetic_bank_is_learnable_and_repeats_a_frame(tmp_path: Path) -> None:
    bank = load_tool("synthetic_bank")
    counts = bank.write_bank(tmp_path, 120, 6, 1, [])
    assert counts["frames"] == 120
    images = sorted((tmp_path / "images").rglob("*.png"))
    metas = sorted((tmp_path / "meta").glob("*.json"))
    assert len(images) == 120 and len(metas) == 120
    digests = {p.read_bytes() for p in images}
    assert len(digests) == 119, "frame 50 repeats frame 49's bytes under another stem"
    meta = json.loads(metas[0].read_text(encoding="utf-8"))
    assert meta["boxes"] and all(len(b["box"]) == 4 for b in meta["boxes"])
    assert any(p.parent.name == "val" for p in images)


def write_catalog(path: Path, rows: list[tuple[str, str, str]]) -> None:
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE item (sha256 TEXT, person TEXT, part TEXT)")
    db.executemany("INSERT INTO item VALUES (?, ?, ?)", rows)
    db.commit()
    db.close()


def test_the_flow_tool_reads_the_split_and_refuses_a_dirty_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    flow = load_tool("flow")
    clean = tmp_path / "catalog-000003-abcdefabcdef.sqlite"
    write_catalog(clean, [("a" * 64, "p1", "train"), ("b" * 64, "p2", "test")])
    assert flow.split_disjoint(clean) == {"disjoint": True, "persons_in_two_parts": [], "frames_in_two_parts": []}
    assert flow.catalog_facts(clean)[1] == 3
    leaky = tmp_path / "leaky.sqlite"
    write_catalog(leaky, [("a" * 64, "p1", "train"), ("a" * 64, "p2", "test")])
    assert flow.split_disjoint(leaky)["frames_in_two_parts"] == ["a" * 64]
    assert flow.catalog_facts(leaky)[1] == 1
    monkeypatch.setattr(flow, "tree_state", lambda: (COMMIT, False))
    args = flow.parse(["run", "--catalog", str(clean), "--out", str(tmp_path / "runs"), "--epochs", "1"])
    with pytest.raises(flow.FlowError, match="dirty tree"):
        flow.start_record(args)
    monkeypatch.setattr(flow, "tree_state", lambda: (COMMIT, True))
    args = flow.parse(["run", "--catalog", str(leaky), "--out", str(tmp_path / "runs"), "--epochs", "1"])
    with pytest.raises(flow.FlowError, match="not disjoint"):
        flow.start_record(args)
    made, check = flow.start_record(flow.parse(["run", "--catalog", str(clean), "--out", str(tmp_path / "runs"), "--epochs", "2", "--seed", "7"]))
    assert made.catalog_version == 3 and made.epochs == 2 and made.seed == 7 and check["disjoint"]
    plan = flow.job_specs(flow.parse(["plan", "--mode", "slurm", "--hours", "4"]))
    assert [j.step for j in plan] == [Step.TRAIN, Step.EVALUATE] and plan[0].gpus == 1 and plan[0].environment == "train-gpu"
    local = flow.job_specs(flow.parse(["plan", "--mode", "local"]))
    assert local[0].gpus == 0 and local[0].environment == "train-cpu" and local[0].partition == "local"


def test_record_copies_the_small_files_and_appends_one_ledger_row(tmp_path: Path) -> None:
    flow = load_tool("flow")
    run_dir = tmp_path / "runs" / "abc"
    (run_dir / "train" / "witness").mkdir(parents=True)
    (run_dir / "evaluate").mkdir()
    (run_dir / "RUN.json").write_text(record(jobs=jobs()).model_dump_json(), encoding="utf-8")
    (run_dir / "train" / "best.pt").write_bytes(b"weights")
    (run_dir / "train" / "MODEL.md").write_text("card\n", encoding="utf-8")
    (run_dir / "evaluate" / "results.md").write_text("table\n", encoding="utf-8")
    for n in (1, 2, 3):
        (run_dir / "train" / "witness" / f"epoch-{n:02d}.png").write_bytes(b"png")
    into = tmp_path / "docs" / "runs"
    assert flow.main(["record", "--run", str(run_dir), "--into", str(into), "--activity", "smoke", "--verified", "by hand"]) == 0
    assert flow.main(["record", "--run", str(run_dir), "--into", str(into), "--activity", "smoke", "--verified", "by hand"]) == 0
    kept = sorted(str(p.relative_to(into)) for p in into.rglob("*") if p.is_file())
    run_name = record().run_id
    assert kept == [f"{run_name}/RUN.json", f"{run_name}/evaluate/results.md", f"{run_name}/train/MODEL.md", f"{run_name}/train/witness/epoch-01.png", f"{run_name}/train/witness/epoch-03.png"]
    ledger = (tmp_path / "docs" / "LEDGER.md").read_text(encoding="utf-8").splitlines()
    assert ledger[0].startswith("| date |") and len(ledger) == 4 and ledger[2] == ledger[3]
