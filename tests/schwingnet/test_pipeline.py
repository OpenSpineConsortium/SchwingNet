"""The launcher's two rules: one key per flow, code and words, and the newest run decides."""

import hashlib
import json

import pytest
from beethoven_qa.contracts import ViolationError

from schwingnet.pipeline import (
    LIVE_SECONDS,
    RESUME,
    RUN,
    RUN_KEY_LENGTH,
    Beat,
    RunState,
    decide,
    is_live,
    marked_live,
    run_key,
)

# tools/run_code.py's digest of the files a flow runs, which names a launch in place of the commit
CODE = "0123456789abcdef" * 4


def test_the_key_is_the_hash_of_the_canonical_json_of_the_three() -> None:
    words = ["--plan", "grid/sweeps/real.json", "--epochs", "3"]
    text = json.dumps(["sweep", CODE, words], ensure_ascii=True, separators=(",", ":"))
    expected = hashlib.sha256(text.encode("ascii")).hexdigest()[:RUN_KEY_LENGTH]
    assert run_key("sweep", CODE, words) == expected
    assert run_key("sweep", CODE, tuple(words)) == expected
    assert len(expected) == 16


def test_a_change_of_flow_code_or_any_word_names_another_key() -> None:
    first = run_key("bank", CODE, ["--sources", "lumos"])
    assert run_key("bank", CODE, ["--sources", "lumos"]) == first
    assert run_key("catalog", CODE, ["--sources", "lumos"]) != first
    assert run_key("bank", "f" * 64, ["--sources", "lumos"]) != first
    assert run_key("bank", CODE, ["--sources", "vindr_cxr"]) != first
    assert run_key("bank", CODE, ["--sources lumos"]) != first
    assert run_key("bank", CODE, []) != first


def test_what_the_flow_reads_beyond_its_words_is_in_the_key() -> None:
    words = ["--sources", "nih_chestxray14 open_i_chest"]
    first = run_key("bank", CODE, words, ["nih_chestxray14 aa", "open_i_chest not fetched"])
    assert (
        run_key("bank", CODE, words, ("nih_chestxray14 aa", "open_i_chest not fetched")) == first
    )
    assert run_key("bank", CODE, words, ["nih_chestxray14 aa", "open_i_chest bb"]) != first
    text = json.dumps(["bank", CODE, words, ["x"]], ensure_ascii=True, separators=(",", ":"))
    assert (
        run_key("bank", CODE, words, ["x"])
        == hashlib.sha256(text.encode("ascii")).hexdigest()[:16]
    )
    # no reads is the key of the three; a word and a read of the same text never meet
    assert run_key("bank", CODE, words, []) == run_key("bank", CODE, words)
    assert run_key("bank", CODE, ["x"], []) != run_key("bank", CODE, [], ["x"])


def test_a_word_of_any_characters_has_a_key() -> None:
    assert len(run_key("bank", CODE, ["\u00e9t\u00e9", "\ud800", '"', "\n"])) == 16


def test_a_key_needs_a_flow_and_the_code_in_hex() -> None:
    with pytest.raises(ViolationError):
        run_key("", CODE, [])
    with pytest.raises(ViolationError):
        run_key("bank", "abc", [])
    with pytest.raises(ViolationError):
        run_key("bank", "XYZ" * 5, [])
    with pytest.raises(ViolationError):
        run_key("bank", CODE + "0", [])
    assert len(run_key("bank", CODE[:7], [])) == 16, "a commit's length still names a key"


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


def test_a_newest_run_still_running_is_never_resumed() -> None:
    live = RunState("1801", finished=False, successful=False, live=True)
    killed = RunState("1792", finished=False, successful=False)
    assert decide([live, killed]) == (RUN, None)
    assert decide([killed, live]) == (RESUME, "1792")


def test_a_newest_run_whose_parameters_were_never_saved_starts_a_new_run() -> None:
    # The second review of #252, finding 1: killed after Metaflow registered it and before it saved
    # its parameters, a run holds no work, and Metaflow refuses to resume it after registering the
    # resume as one more such run, so each launch of the key that resumed the newest failed in turn
    unsaved = RunState("1802", finished=False, successful=False, parameters_saved=False)
    killed = RunState("1792", finished=False, successful=False)
    assert decide([unsaved]) == (RUN, None)
    assert decide([unsaved, killed]) == (RUN, None)
    assert decide([killed, unsaved]) == (RESUME, "1792")


def test_a_run_a_live_launcher_has_just_registered_counts_as_live_before_its_parameters() -> None:
    unsaved = RunState("1802", finished=False, successful=False, parameters_saved=False)
    killed = RunState("1792", finished=False, successful=False)
    for beat in (Beat("1802", "4242", NOW), Beat("", "4242", NOW)):
        marked = marked_live([unsaved, killed], [beat], "", NOW)
        assert [run.live for run in marked] == [True, False]
        assert [run.parameters_saved for run in marked] == [False, True]
        assert decide(marked) == (RUN, None)


NOW = 1_800_000_000.0


def test_a_beat_is_live_while_fresh_and_from_another_job() -> None:
    assert is_live(Beat("1801", "4242", NOW - 30), "4243", NOW)
    assert is_live(Beat("1801", "", NOW - LIVE_SECONDS), "", NOW)
    # a clock ahead of this one still beats
    assert is_live(Beat("1801", "4242", NOW + 90), "", NOW)
    assert not is_live(Beat("1801", "4242", NOW - LIVE_SECONDS - 1), "4243", NOW)
    # this very job's beat was left by its earlier start, which Slurm ended and queued again
    assert not is_live(Beat("1801", "4242", NOW - 1), "4242", NOW)


def test_the_runs_a_live_beat_names_are_live_and_the_newest_while_a_launcher_starts() -> None:
    newest = RunState("1801", finished=False, successful=False)
    older = RunState("1792", finished=False, successful=False)
    named = marked_live([newest, older], [Beat("1792", "", NOW)], "", NOW)
    assert [run.live for run in named] == [False, True]
    assert named[0][:3] == newest[:3]
    starting = marked_live([newest, older], [Beat("", "4242", NOW)], "", NOW)
    assert [run.live for run in starting] == [True, False]
    gone = [Beat("1801", "", NOW - 3600), Beat("1792", "4242", NOW), Beat("", "4242", NOW)]
    assert [run.live for run in marked_live([newest, older], gone, "4242", NOW)] == [False, False]
    assert marked_live([], [Beat("", "", NOW)], "", NOW) == []


def test_a_live_beat_naming_a_run_the_listing_lacks_marks_the_newest_live() -> None:
    # Two launchers of one key seconds apart: the second lists the runs before the first's resume
    # of the newest is registered and reads the beats after the first's beat has named it.
    newest = RunState("1801", finished=False, successful=False)
    older = RunState("1792", finished=True, successful=True)
    named = marked_live([newest, older], [Beat("1810", "", NOW)], "", NOW)
    assert [run.live for run in named] == [True, False]
    assert decide(named) == (RUN, None)
    stale = [Beat("1810", "", NOW - LIVE_SECONDS - 1)]
    assert decide(marked_live([newest, older], stale, "", NOW)) == (RESUME, "1801")


def test_the_runs_must_hold_together() -> None:
    with pytest.raises(ViolationError):
        decide([RunState("", finished=False, successful=False)])
    with pytest.raises(ViolationError):
        decide([RunState("1", finished=False, successful=True)])
