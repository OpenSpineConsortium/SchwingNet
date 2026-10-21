"""The causal tracker of the recorded sweep (schwingnet.sweep): matching, smoothing, abstaining, ending."""

import pytest
from icontract import ViolationError

from schwingnet.sweep import ABSTAIN, MAX_MISSES, Tracker, iou, label_of, match, smooth, step

LEVELS = ["L1", "L2", "L3"]
A = (0.1, 0.1, 0.3, 0.3)
B = (0.1, 0.4, 0.3, 0.6)


def test_overlap_of_a_box_with_itself_is_one_and_with_a_disjoint_box_zero() -> None:
    assert iou(A, A) == 1.0
    assert iou(A, B) == 0.0


def test_half_a_box_overlaps_by_a_half() -> None:
    assert iou((0.0, 0.0, 1.0, 1.0), (0.0, 0.0, 0.5, 1.0)) == pytest.approx(0.5)


def test_a_box_without_area_overlaps_nothing() -> None:
    assert iou((0.2, 0.2, 0.2, 0.2), (0.2, 0.2, 0.2, 0.2)) == 0.0


def test_a_malformed_box_is_refused() -> None:
    with pytest.raises(ViolationError):
        iou((0.3, 0.1, 0.1, 0.3), A)


def test_boxes_join_the_tracks_they_overlap_whatever_their_order() -> None:
    moved_a = (0.11, 0.1, 0.31, 0.3)
    moved_b = (0.1, 0.41, 0.3, 0.61)
    assert sorted(match([A, B], [moved_b, moved_a])) == [(0, 1), (1, 0)]


def test_a_box_too_far_from_every_track_joins_none() -> None:
    assert match([A], [B]) == []


def test_smoothing_weighs_the_new_frame_by_alpha() -> None:
    assert smooth([1.0, 0.0], [0.0, 1.0], 0.5) == [0.5, 0.5]
    assert smooth([1.0, 0.0], [0.0, 1.0], 1.0) == [0.0, 1.0]


def test_a_confident_level_is_shown_and_an_unsure_one_abstains() -> None:
    assert label_of([0.1, 0.8, 0.1], LEVELS) == ("L2", 0.8)
    assert label_of([0.4, 0.3, 0.3], LEVELS)[0] == ABSTAIN


def test_one_wrong_frame_does_not_flip_a_steady_track() -> None:
    state = Tracker()
    for _ in range(3):
        state, shown = step(state, [A], [[0.0, 1.0, 0.0]], LEVELS)
    state, shown = step(state, [A], [[0.0, 0.2, 0.8]], LEVELS)
    assert shown[0].level == "L2"
    assert shown[0].ident == 1


def test_a_new_box_starts_a_new_track() -> None:
    state, _ = step(Tracker(), [A], [[1.0, 0.0, 0.0]], LEVELS)
    state, shown = step(state, [A, B], [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]], LEVELS)
    assert [s.ident for s in shown] == [1, 2]
    assert state.next_ident == 3


def test_a_track_unseen_too_long_ends() -> None:
    state, _ = step(Tracker(), [A], [[1.0, 0.0, 0.0]], LEVELS)
    for _ in range(MAX_MISSES):
        state, _ = step(state, [], [], LEVELS)
        assert len(state.tracks) == 1
    state, _ = step(state, [], [], LEVELS)
    assert state.tracks == ()


def test_the_same_frames_give_the_same_tracks() -> None:
    def replay() -> list[tuple[int, str]]:
        state, out = Tracker(), []
        for probs in ([[0.9, 0.1, 0.0]], [[0.2, 0.7, 0.1]], [[0.1, 0.1, 0.8]]):
            state, shown = step(state, [A], probs, LEVELS)
            out += [(s.ident, s.level) for s in shown]
        return out

    assert replay() == replay()


def test_a_tracker_whose_next_id_is_taken_is_refused() -> None:
    from schwingnet.sweep import Track

    with pytest.raises(ViolationError):
        step(Tracker((Track(3, A, (1.0, 0.0, 0.0)),), 2), [A], [[1.0, 0.0, 0.0]], LEVELS)
