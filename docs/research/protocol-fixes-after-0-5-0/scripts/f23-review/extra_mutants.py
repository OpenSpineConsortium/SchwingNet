"""Mutants of F23's new code that the lane does not hold, judged by the
lane's own catchers: python3.12 extra_mutants.py [traces|all] [names...]."""
import sys
from unittest import mock

from sdlc_protocol import coordinator
from sdlc_protocol.adapters import github
from validation import mutants

ORIGINAL = mutants.ORIGINAL_RELEASE_ONE


def refused_reread_put_back(api, snap, key, now):
    """github.release_one as the library has it, but after a 4xx a re-read
    GitHub refuses puts the labels back, as if a refusal settled it."""
    release = snap.releases[key]
    names, put_on = coordinator.labels_released(snap, key), coordinator.labels_put_on(snap, key)
    taken_off = []
    try:
        for name in names:
            if github.take_label_off(api, key, name):
                taken_off.append(name)
    except github.GitHubError as problem:
        return (f"#{key}: not released, taking the labels off failed: {problem}{github.github_words(problem)}" + github.put_back(api, key, taken_off))
    refused = github.put_labels_on(api, key, put_on, taken_off)
    if refused:
        return refused
    text = coordinator.release_text(snap, key, github.holding(api, snap.default_branch, release.sha))
    lost = ""
    try:
        released_at = (api.post(f"/repos/{api.repo}/issues/{key}/comments", {"body": text}) or {}).get("created_at")
    except github.GitHubError as problem:
        try:
            released_at = github.landed_release(api, key, release)
        except github.GitHubError as unread:
            if github.wrote_nothing(problem):
                return (f"#{key}: not released, the comment failed: {problem}{github.github_words(problem)}" + github.put_back(api, key, taken_off, put_on))
            return github.unsettled(snap, key, names, put_on, problem, unread)
        if not released_at and not github.wrote_nothing(problem):
            return github.not_listed(snap, key, names, put_on, problem)
        if not released_at:
            return (f"#{key}: not released, the comment failed: {problem}{github.github_words(problem)}" + github.put_back(api, key, taken_off, put_on))
        lost = f" (GitHub's answer to the comment was lost, {problem}, but the comment is there)"
    coordinator.after_release(snap, key, released_at or now.isoformat(), names, put_on)
    return f"#{key}: claim released, idle since {release.last_commit}{lost}"


ORIGINAL_UNSETTLED = github.unsettled
ORIGINAL_LANDED = github.landed_release


def reread_skipped_after_a_refusal(api, snap, key, now):
    """After a 4xx, no re-read: the labels go back at once."""
    state = {}
    original_post = api.post

    def post(path, body):
        try:
            return original_post(path, body)
        except github.GitHubError as problem:
            state["problem"] = problem
            raise

    def landed(api_, key_, release):
        problem = state.get("problem")
        if problem is not None and github.wrote_nothing(problem):
            return ""
        return ORIGINAL_LANDED(api_, key_, release)
    with mock.patch.object(api, "post", post), mock.patch.object(github, "landed_release", landed):
        return ORIGINAL(api, snap, key, now)


def not_listed_counted(snap, key, names, put_on, problem):
    coordinator.after_release(snap, key, "2099-01-01T00:00:00Z", names, put_on)
    return f"#{key}: claim released though none listed: {problem}"


def labels_left_put_back_free(snap, key, names, put_on, problem, why):
    return f"#{key}: labels left, snapshot not updated: {problem}; {why}"


EXTRA = {
    "a refusal's refused re-read put back": mutants.Mutant(
        github, "release_one", refused_reread_put_back, "G3L",
        "after a 4xx, a re-read GitHub refuses leaves the labels as the release left them"),
    "the re-read skipped after a refusal": mutants.Mutant(
        github, "release_one", reread_skipped_after_a_refusal, "G3L",
        "after a 4xx, the issue's comments are read before the labels go back"),
    "a 500 taken for a refusal": mutants.Mutant(
        github, "wrote_nothing", lambda problem: problem.status is not None and 400 <= problem.status <= 500, "G3L",
        "a 500 may come after the write"),
    "an unlisted release counted": mutants.Mutant(
        github, "not_listed", not_listed_counted, "G3L", "not_listed counts no release"),
    "labels_left not shown on the snapshot": mutants.Mutant(
        github, "labels_left", labels_left_put_back_free, "G9",
        "labels_left brings the snapshot's labels up to date"),
    "a lost comment found and ignored after a server error": mutants.Mutant(
        github, "wrote_nothing", lambda problem: True, "G3L", "placeholder"),
}


def main(argv):
    which, names = argv[0], argv[1:] or list(EXTRA)
    mutants.MUTANTS.update(EXTRA)
    catchers = mutants.LANES[:1] if which == "traces" else mutants.CATCHERS
    plain, verdicts = mutants.run_lane(names, catchers)
    for v in verdicts:
        if v.caught:
            print(f"caught   {v.mutant}: {v.guarantee} in {v.search!r}, {v.seconds:.1f} s; {v.detail}")
            print(f"         trace: {', '.join(str(step) for step in v.trace)[:600]}")
        else:
            print(f"SLIPPED  {v.mutant}: no catcher of {[c.name for c in catchers]} caught it ({v.seconds:.1f} s)")
        sys.stdout.flush()


EXTRA["F20's mutant as it was on main"] = mutants.Mutant(
    github, "landed_release", mutants.landed_release_finding_none_unread, "G3L",
    "a run that cannot read whether its release comment stands leaves the labels as the release left them (F20)")


if __name__ == "__main__":
    main(sys.argv[1:])
