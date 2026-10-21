"""The causal tracker of the recorded sweep: what frame t shows, from frames 0 to t only.

docs/research/demo-plan.md, section 1: the tracker is causal, so the recording is what a live run
would have shown. Each frame brings boxes, each with the level stage's probabilities over the
levels; a box joins the track it overlaps most (intersection over union, greedy, highest first),
a track's probabilities are an exponential moving average of its boxes', a track unseen for a few
frames ends, and a track whose best level is below the abstain threshold shows "?" rather than a
guess. Nothing here reads a later frame, and the same frames in the same order give the same tracks.
"""

from dataclasses import dataclass

from beartype import beartype
from beethoven_qa.contracts import ensure, require

Box = tuple[float, float, float, float]

ABSTAIN = "?"
MATCH_IOU = 0.3
SMOOTHING = 0.5
ABSTAIN_BELOW = 0.5
MAX_MISSES = 3


def _well_formed(box: Box) -> bool:
    x0, y0, x1, y1 = box
    return x0 <= x1 and y0 <= y1


@beartype
@require(lambda a, b: _well_formed(a) and _well_formed(b), "boxes are x0 <= x1 and y0 <= y1")
@ensure(lambda result: 0.0 <= result <= 1.0, "an overlap is a fraction")
def iou(a: Box, b: Box) -> float:
    """Intersection over union of two boxes; zero when either has no area."""
    width = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = width * height
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    if union <= 0.0:
        return 0.0
    return min(1.0, max(0.0, inter / union))


@beartype
@require(
    lambda tracks, boxes: all(_well_formed(b) for b in tracks + boxes), "boxes are well formed"
)
@require(lambda threshold: 0.0 < threshold <= 1.0, "a threshold is a fraction above zero")
@ensure(lambda result: len({t for t, _ in result}) == len(result), "a track takes at most one box")
@ensure(lambda result: len({b for _, b in result}) == len(result), "a box joins at most one track")
@ensure(
    lambda result, tracks, boxes: all(
        0 <= t < len(tracks) and 0 <= b < len(boxes) for t, b in result
    ),
    "indices are in range",
)
def match(
    tracks: list[Box], boxes: list[Box], threshold: float = MATCH_IOU
) -> list[tuple[int, int]]:
    """Pairs (track, box) by greedy overlap, highest first, each at the threshold or above.

    Ties break by the lower track index, then the lower box index, so the pairing never depends
    on anything but the boxes.
    """
    candidates = sorted(
        ((iou(t, b), ti, bi) for ti, t in enumerate(tracks) for bi, b in enumerate(boxes)),
        key=lambda c: (-c[0], c[1], c[2]),
    )
    taken_tracks: set[int] = set()
    taken_boxes: set[int] = set()
    pairs = []
    for overlap, ti, bi in candidates:
        if overlap < threshold or ti in taken_tracks or bi in taken_boxes:
            continue
        pairs.append((ti, bi))
        taken_tracks.add(ti)
        taken_boxes.add(bi)
    return pairs


@beartype
@require(
    lambda previous, current: len(previous) == len(current) > 0, "the same levels on both sides"
)
@require(lambda alpha: 0.0 < alpha <= 1.0, "a weight is a fraction above zero")
@ensure(lambda result, current: len(result) == len(current), "one probability per level")
def smooth(previous: list[float], current: list[float], alpha: float = SMOOTHING) -> list[float]:
    """The moving average: alpha of the new frame's probabilities, the rest of the track's."""
    return [alpha * c + (1.0 - alpha) * p for p, c in zip(previous, current, strict=True)]


@beartype
@require(
    lambda probabilities, levels: len(probabilities) == len(levels) > 0, "one probability per level"
)
@require(lambda threshold: 0.0 <= threshold <= 1.0, "a threshold is a fraction")
@ensure(
    lambda result, levels: result[0] in levels or result[0] == ABSTAIN,
    "a level or the abstain mark",
)
def label_of(
    probabilities: list[float], levels: list[str], threshold: float = ABSTAIN_BELOW
) -> tuple[str, float]:
    """The best level and its probability, or the abstain mark where the best is too unsure."""
    best = max(range(len(probabilities)), key=lambda i: (probabilities[i], -i))
    probability = probabilities[best]
    return (levels[best] if probability >= threshold else ABSTAIN), probability


@dataclass(frozen=True)
class Track:
    """One vertebra followed across frames: its id, its last box, its smoothed probabilities."""

    ident: int
    box: Box
    probabilities: tuple[float, ...]
    misses: int = 0


@dataclass(frozen=True)
class Shown:
    """What the overlay draws for one track on one frame."""

    ident: int
    box: Box
    level: str
    probability: float


@dataclass(frozen=True)
class Tracker:
    """The tracker between frames: the tracks so far and the next free track id."""

    tracks: tuple[Track, ...] = ()
    next_ident: int = 1


@beartype
@require(
    lambda boxes, probabilities: len(boxes) == len(probabilities),
    "one row of probabilities per box",
)
@require(
    lambda state, boxes: all(_well_formed(b) for b in [t.box for t in state.tracks] + boxes),
    "boxes are well formed",
)
@require(lambda levels: len(levels) > 0, "at least one level")
@require(
    lambda state, probabilities, levels: (
        all(len(row) == len(levels) for row in probabilities)
        and all(len(t.probabilities) == len(levels) for t in state.tracks)
    ),
    "one probability per level, in every row and every track",
)
@require(
    lambda state: len({t.ident for t in state.tracks}) == len(state.tracks), "track ids are unique"
)
@require(
    lambda state: all(t.ident < state.next_ident for t in state.tracks), "the next id is unused"
)
@require(
    lambda state: all(0 <= t.misses <= MAX_MISSES for t in state.tracks), "misses within the limit"
)
@ensure(
    lambda result: len({t.ident for t in result[0].tracks}) == len(result[0].tracks),
    "track ids are unique",
)
@ensure(lambda result, boxes: len(result[1]) == len(boxes), "every box this frame is shown")
@ensure(
    lambda result: all(t.misses <= MAX_MISSES for t in result[0].tracks),
    "a track unseen too long has ended",
)
def step(
    state: Tracker, boxes: list[Box], probabilities: list[list[float]], levels: list[str]
) -> tuple[Tracker, list[Shown]]:
    """One frame of the tracker: match, smooth, start and end tracks, and say what is shown.

    Returns the tracker after this frame and what the overlay draws, one per box in the boxes'
    order. Only this frame and the tracks so far are read.
    """
    tracks, next_ident = list(state.tracks), state.next_ident
    pairs = dict((bi, ti) for ti, bi in match([t.box for t in tracks], boxes))
    updated: dict[int, Track] = {}
    shown = []
    for bi, box in enumerate(boxes):
        if bi in pairs:
            old = tracks[pairs[bi]]
            track = Track(old.ident, box, tuple(smooth(list(old.probabilities), probabilities[bi])))
        else:
            track = Track(next_ident, box, tuple(probabilities[bi]))
            next_ident += 1
        updated[track.ident] = track
        level, probability = label_of(list(track.probabilities), levels)
        shown.append(Shown(track.ident, box, level, probability))
    matched = set(pairs.values())
    for ti, old in enumerate(tracks):
        if ti not in matched and old.misses < MAX_MISSES:
            updated[old.ident] = Track(old.ident, old.box, old.probabilities, old.misses + 1)
    return Tracker(tuple(updated.values()), next_ident), shown
