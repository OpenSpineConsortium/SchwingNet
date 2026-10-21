"""The witness frames: chosen by rule, frozen, held to the catalog; and W&B's key never leaks."""

import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path
from types import ModuleType

import pytest

from schwingnet.witness import (
    LUMBAR,
    ROLE_SWEEP,
    ROLE_TEST,
    ROLE_TRANSITIONAL,
    ROLE_VALIDATION,
    Candidate,
    WitnessRule,
    case_of,
    choose,
    evenly_spaced,
    rank,
    spread,
)

ROOT = Path(__file__).resolve().parents[2]


def load_tool(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"witness_test_{name}", ROOT / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def frame(n: int, person: str, part: str, levels: tuple[str, ...], source: str = "carmlspine") -> Candidate:
    sha = f"{n:064x}"
    return Candidate(sha, person, part, source, levels, f"/bank/{person}/f{n:06d}.png")


def bank() -> tuple[Candidate, ...]:
    """Validation persons with many frames each, the frozen test persons, a film source."""
    frames: list[Candidate] = []
    n = 0
    for p in range(6):
        for f in range(20):
            frames.append(frame(n, f"carmlspine:case{1000 + p}", "validation", (LUMBAR[f % 5], LUMBAR[(f + 1) % 5])))
            n += 1
    for case, levels in (("case42", ("L5", "L6")), ("case121", ("L4",)), ("case136", ("L6", "sacrum")), ("case134", ("L3",)), ("case39", ("L2",)), ("case7", ("L1", "L2"))):
        for f in range(12):
            frames.append(frame(n, f"carmlspine:{case}", "test", levels))
            n += 1
    frames.append(frame(n, "buu:p1", "validation", ("L3",), source="buu"))
    return tuple(frames)


def test_the_rank_and_the_case_are_plain_functions_of_their_inputs() -> None:
    assert rank("s", "a" * 64) == rank("s", "a" * 64) != rank("t", "a" * 64)
    assert case_of("carmlspine:case42") == "case42" and case_of("case42") == "case42"


def test_evenly_spaced_reaches_both_ends() -> None:
    assert evenly_spaced(100, 8)[0] == 0 and evenly_spaced(100, 8)[-1] == 99
    assert evenly_spaced(3, 8) == (0, 1, 2)
    assert evenly_spaced(10, 1) == (0,) and evenly_spaced(0, 8) == () and evenly_spaced(5, 0) == ()


def test_spread_spans_levels_and_persons_before_repeating_one() -> None:
    pool = tuple(c for c in bank() if c.part == "validation" and c.source == "carmlspine")
    chosen = spread(pool, LUMBAR, 12, "salt")
    assert len(chosen) == 12 and len({c.sha256 for c in chosen}) == 12
    assert {c.person for c in chosen} == {f"carmlspine:case{1000 + p}" for p in range(6)}
    for level in LUMBAR:
        assert any(level in c.levels for c in chosen)
    assert spread(pool, LUMBAR, 12, "salt") == chosen, "the same inputs choose the same frames"
    assert spread(pool, LUMBAR, 12, "other") != chosen, "the salt is what orders them"


def test_choose_fills_each_role_from_its_own_part_and_names_what_is_missing() -> None:
    picked, missing = choose(bank(), WitnessRule())
    roles = [role for role, _ in picked]
    assert roles.count(ROLE_VALIDATION) == 24 and roles.count(ROLE_TEST) == 24
    assert all(c.part == "validation" for role, c in picked if role == ROLE_VALIDATION)
    assert all(c.part == "test" for role, c in picked if role != ROLE_VALIDATION)
    assert all(c.source == "carmlspine" for _, c in picked), "another source never fills the C-arm set"
    assert not any(case_of(c.person) in ("case134", "case39") for role, c in picked if role == ROLE_TEST)
    sweep = [c for role, c in picked if role == ROLE_SWEEP]
    assert len(sweep) == 16 and [c.path for c in sweep[:8]] == sorted(c.path for c in sweep[:8])
    transitional = [c for role, c in picked if role == ROLE_TRANSITIONAL]
    assert {case_of(c.person) for c in transitional} == {"case42", "case121", "case136"}
    assert all("L6" in c.levels for c in transitional if case_of(c.person) != "case121")
    assert len({c.sha256 for _, c in picked}) == len(picked)
    assert missing == ()


def test_choose_says_what_a_thin_catalog_cannot_show() -> None:
    thin = tuple(c for c in bank() if case_of(c.person) not in ("case39", "case136"))
    _, missing = choose(thin, WitnessRule())
    assert "sweep: no test frame of case39 in the catalog" in missing
    assert "transitional: no test frame of case136 in the catalog" in missing


def write_catalog(path: Path, frames: tuple[Candidate, ...]) -> None:
    """The three tables the witness reader joins, in the catalog's column names."""
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE shard (name TEXT, manifest TEXT)")
    db.execute("CREATE TABLE item (sha256 TEXT, shard TEXT, path TEXT, source TEXT, person TEXT, part TEXT)")
    db.execute("CREATE TABLE label (item TEXT, shard TEXT, level TEXT)")
    db.execute("INSERT INTO shard VALUES ('s1', '/grid/carmlspine/shards/s1/MANIFEST.json')")
    for c in frames:
        db.execute("INSERT INTO item VALUES (?, 's1', ?, ?, ?, ?)", (c.sha256, Path(c.path).name, c.source, c.person, c.part))
        db.executemany("INSERT INTO label VALUES (?, 's1', ?)", [(c.sha256, level) for level in c.levels])
    db.commit()
    db.close()


def test_a_frozen_list_is_held_to_every_later_catalog(tmp_path: Path) -> None:
    tool = load_tool("witness")
    catalog = tmp_path / "catalog.sqlite"
    write_catalog(catalog, bank())
    document = tool.freeze(catalog, "f" * 64)
    assert len(document["frames"]) == 70 and document["missing"] == []
    assert all(f["path"].startswith("/grid/carmlspine/shards/s1/") for f in document["frames"])
    assert tool.check(json.loads(json.dumps(document)), catalog)["frames"][0]["key"] == document["frames"][0]["key"]
    lost = tmp_path / "lost.sqlite"
    write_catalog(lost, tuple(c for c in bank() if c.sha256 != document["frames"][0]["sha256"]))
    with pytest.raises(tool.WitnessError, match="no longer holds 1 frozen"):
        tool.check(document, lost)
    moved = dict(document, frames=[dict(document["frames"][0], part="test"), *document["frames"][1:]])
    with pytest.raises(tool.WitnessError, match="in their part"):
        tool.check(moved, catalog)


def test_the_wandb_key_is_found_by_name_and_never_printed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = load_tool("wandb_log")
    monkeypatch.delenv("WANDB_API_KEY", raising=False)
    monkeypatch.setattr(tool, "TOKEN_FILE", tmp_path / "token.env")
    monkeypatch.setattr(tool, "NETRC", tmp_path / "netrc")
    assert tool.key_source() == "none"
    run = tmp_path / "run"
    run.mkdir()
    outcome = tool.sync(run)
    assert not outcome["synced"] and "no W&B run" in outcome["why"]
    (run / "wandb" / "wandb" / "offline-run-1-abc-train").mkdir(parents=True)
    outcome = tool.sync(run)
    assert "no W&B key" in outcome["why"] and tool.verdict(outcome).startswith("W&B NOT PUSHED")
    secret = "k" * 40
    (tmp_path / "token.env").write_text(f"WANDB_API_KEY={secret}\n", encoding="utf-8")
    os.chmod(tmp_path / "token.env", 0o644)
    assert tool.key_source() == "file"
    with pytest.raises(PermissionError):
        tool.token_file_env()
    os.chmod(tmp_path / "token.env", 0o600)
    assert tool.token_file_env() == {"WANDB_API_KEY": secret}
    monkeypatch.setenv("WANDB_API_KEY", secret)
    assert tool.key_source() == "env"
    assert secret not in json.dumps(outcome) and secret not in tool.verdict(outcome)


def test_a_step_logged_online_counts_as_pushed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = load_tool("wandb_log")
    monkeypatch.setenv("WANDB_API_KEY", "k" * 40)
    (tmp_path / "wandb-mode.json").write_text(json.dumps({"train": {"step": "train", "mode": "online", "why": None, "url": "https://wandb.ai/e/SchwingNet/runs/x-train"}}), encoding="utf-8")
    outcome = tool.sync(tmp_path)
    assert outcome["synced"] and outcome["urls"] == ["https://wandb.ai/e/SchwingNet/runs/x-train"]
    assert tool.verdict(outcome) == "W&B: pushed https://wandb.ai/e/SchwingNet/runs/x-train"


def test_the_rules_refuse_what_would_put_a_frame_twice() -> None:
    from beethoven_qa.contracts import ViolationError

    one = frame(1, "carmlspine:case1000", "validation", ("L3",))
    twin = Candidate(one.sha256, "carmlspine:case1001", "validation", "carmlspine", ("L3",), "/x")
    with pytest.raises(ViolationError):
        spread((one, twin), LUMBAR, 2, "salt")
    with pytest.raises(ViolationError):
        choose(bank(), WitnessRule(transitional_cases=("case39",)))


def test_spread_stays_fast_on_a_catalog_sized_pool() -> None:
    import time

    pool = tuple(
        frame(n, f"carmlspine:case{n % 400}", "validation", (LUMBAR[n % 5],)) for n in range(20000)
    )
    started = time.monotonic()
    chosen = spread(pool, LUMBAR, 24, "salt")
    assert len(chosen) == 24 and len({c.person for c in chosen}) == 24
    assert time.monotonic() - started < 20


def test_an_error_is_made_safe_for_a_committed_table() -> None:
    tool = load_tool("wandb_log")
    said = tool.plain("bad key " + "a1" * 20 + " | rest\nsecond line")
    assert "[redacted]" in said and "|" not in said and "second" not in said and "a1a1" not in said
