"""The launcher's two rules: one key per flow, commit and words, and the newest run decides."""

import hashlib
import json

import pytest
from beethoven_qa.contracts import ViolationError

from schwingnet.pipeline import RESUME, RUN, RUN_KEY_LENGTH, RunState, decide, run_key

COMMIT = "0123456789abcdef0123456789abcdef01234567"


def test_the_key_is_the_hash_of_the_canonical_json_of_the_three() -> None:
    words = ["--plan", "grid/sweeps/real.json", "--epochs", "3"]
    text = json.dumps(["sweep", COMMIT, words], ensure_ascii=True, separators=(",", ":"))
    expected = hashlib.sha256(text.encode("ascii")).hexdigest()[:RUN_KEY_LENGTH]
    assert run_key("sweep", COMMIT, words) == expected
    assert run_key("sweep", COMMIT, tuple(words)) == expected
    assert len(expected) == 16


def test_a_change_of_flow_commit_or_any_word_names_another_key() -> None:
    first = run_key("bank", COMMIT, ["--sources", "lumos"])
    assert run_key("bank", COMMIT, ["--sources", "lumos"]) == first
    assert run_key("catalog", COMMIT, ["--sources", "lumos"]) != first
    assert run_key("bank", "f" * 40, ["--sources", "lumos"]) != first
    assert run_key("bank", COMMIT, ["--sources", "vindr_cxr"]) != first
    assert run_key("bank", COMMIT, ["--sources lumos"]) != first
    assert run_key("bank", COMMIT, []) != first


def test_a_word_of_any_characters_has_a_key() -> None:
    assert len(run_key("bank", COMMIT, ["\u00e9t\u00e9", "\ud800", '"', "\n"])) == 16


def test_a_key_needs_a_flow_and_a_commit() -> None:
    with pytest.raises(ViolationError):
        run_key("", COMMIT, [])
    with pytest.raises(ViolationError):
        run_key("bank", "abc", [])
    with pytest.raises(ViolationError):
        run_key("bank", "XYZ" * 5, [])


def test_no_run_yet_starts_one() -> None:
    assert decide([]) == (RUN, None)


def test_a_newest_run_that_did_not_succeed_is_resumed() -> None:
    killed = RunState("1792", finished=False, successful=False)
    failed = RunState("1793", finished=True, successful=False)
    assert decide([killed]) == (RESUME, "1792")
    assert decide([failed, killed]) == (RESUME, "1793")


def test_a_newest_success_starts_a_new_run_whatever_failed_before_it() -> None:
    done = RunState("1800", finished=True, successful=True)
    killed = RunState("1792", finished=False, successful=False)
    assert decide([done, killed]) == (RUN, None)
    assert decide([done]) == (RUN, None)
    # an older success behind a newer failure is no reason to start afresh
    assert decide([killed, done]) == (RESUME, "1792")


def test_the_runs_must_hold_together() -> None:
    with pytest.raises(ViolationError):
        decide([RunState("", finished=False, successful=False)])
    with pytest.raises(ViolationError):
        decide([RunState("1", finished=False, successful=True)])
