"""Bring each new release of the claim protocol into this repository: what
.github/workflows/protocol.yml decides, and every text it posts.

The template takes each release of OpenSpineConsortium/symphony-protocol by
that library's own sync, but a repository made from the template is on no
sync list (docs/project.md), so its copy, tools/sdlc_protocol with the
record tools/VENDORED, would stay at the release it was made with. The
workflow runs weekly and by hand: it clones the library, asks this script
whether the library's newest release tag is newer than the version VENDORED
records, vendors that tag with the library's own scripts/vendor.py on the
branch symphony-protocol/sync and offers it as a pull request, or, where
the repository does not let GitHub Actions open one, as an issue whose link
opens it in one press. This repository's check decides, as it does on any
pull request. The workflow runs only git, gh and this script, so what it
decides and says is tested here.

  plan --library DIR                 the step's outputs: needed, tag,
                                     recorded and recorded_commit
  title --tag TAG                    the pull request's title
  message --tag TAG                  the commit message
  body --tag TAG --recorded V --from COMMIT
                                     the pull request's body
  issue-title --tag TAG              the issue's title, where no pull
                                     request may be opened
  issue-body --tag TAG --recorded V --url URL
                                     the issue's body, with the link that
                                     opens the pull request
  closing --recorded V               the comment that closes an update the
                                     default branch no longer needs
  marker                             the line both bodies start with, by
                                     which the next run finds the issue
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from sdlc_protocol import vendoring  # noqa: E402

LIBRARY = "OpenSpineConsortium/symphony-protocol"
LIBRARY_URL = f"https://github.com/{LIBRARY}"
BRANCH = "symphony-protocol/sync"
MARKER = "<!-- symphony-protocol: update -->"
RECORD = TOOLS / "VENDORED"
RELEASE_TAG = re.compile(r"^v([0-9]+)\.([0-9]+)\.([0-9]+)$")


def version_of(tag):
    """The three numbers of a release tag vX.Y.Z, or None for any other tag."""
    match = RELEASE_TAG.match(tag or "")
    return tuple(int(part) for part in match.groups()) if match else None


def newest_release(tags):
    """The newest release tag among the tags, by version, or None."""
    return max((tag for tag in tags if version_of(tag)), key=version_of, default=None)


def is_newer(tag, recorded):
    """Whether the release tag is newer than the version the copy records.
    A copy ahead of every release, vendored from the library's main by
    hand, is never taken back to one."""
    recorded_numbers = version_of("v" + recorded)
    return recorded_numbers is None or version_of(tag) > recorded_numbers


def release_tags(library):
    found = subprocess.run(["git", "tag", "--list", "v*"], cwd=library, capture_output=True, text=True, check=True)
    return found.stdout.split()


def plan(library, record):
    """What the workflow does next, as its step's outputs: whether the
    copy needs the newest release, which tag that is, and the version and
    commit the record says the copy is now."""
    recorded, commit, _ = vendoring.parse_record(Path(record).read_text(encoding="ascii"))
    tag = newest_release(release_tags(library))
    needed = bool(tag) and is_newer(tag, recorded)
    return {"needed": "true" if needed else "false", "tag": tag or "", "recorded": recorded,
            "recorded_commit": commit}


def version_in(tag):
    return tag[1:] if tag.startswith("v") else tag


def title(tag):
    return f"Bring in symphony-protocol {version_in(tag)}"


def message(tag):
    return (
        f"{title(tag)}\n\n"
        f"The claim protocol's copy under tools/sdlc_protocol and its record\n"
        f"tools/VENDORED, vendored from the release tag {tag} of\n"
        f"{LIBRARY} with its scripts/vendor.py by\n"
        f".github/workflows/protocol.yml.\n"
    )


def body(tag, recorded, recorded_commit):
    version = version_in(tag)
    return (
        f"{MARKER}\n"
        f"This brings the claim protocol's copy, tools/sdlc_protocol with its record tools/VENDORED, from "
        f"symphony-protocol {recorded} to {version}: the [release notes]({LIBRARY_URL}/releases/tag/{tag}) and "
        f"[every change since the copy's commit]({LIBRARY_URL}/compare/{recorded_commit}...{tag}).\n\n"
        f".github/workflows/protocol.yml made it with the library's own scripts/vendor.py and nothing else, and "
        f"pushes the branch again when a newer release comes out. This repository's check decides: where "
        f"auto-merge is allowed, the pull request lands by itself once the check is green, and otherwise it "
        f"waits for a merge.\n\n"
        f"A change to the copy made here fails the check, since tools/VENDORED records every file's hash: a "
        f"change to the protocol is made in {LIBRARY} and arrives with its next release.\n"
    )


def issue_title(tag):
    return f"symphony-protocol {version_in(tag)} is ready to bring in"


def issue_body(tag, recorded, url):
    return (
        f"{MARKER}\n"
        f"The branch {BRANCH} holds the claim protocol's copy at symphony-protocol {version_in(tag)}, newer than "
        f"the {recorded} the default branch carries ([release notes]({LIBRARY_URL}/releases/tag/{tag})). This "
        f"repository does not let GitHub Actions open a pull request, so .github/workflows/protocol.yml left "
        f"this issue instead: [open the pull request]({url}), and this repository's check decides. The next run "
        f"closes this issue once the default branch carries the release.\n"
    )


def closing(recorded):
    return (
        f"The default branch already carries symphony-protocol {recorded}, no older than the newest release, so "
        f"this update "
        f"is no longer needed.\n"
    )


def outputs(found):
    return "".join(f"{key}={value}\n" for key, value in found.items())


def main(argv=None):
    parser = argparse.ArgumentParser(description="What protocol.yml decides and posts.")
    parser.add_argument("command", choices=("plan", "title", "message", "body", "issue-title", "issue-body",
                                            "closing", "marker"))
    parser.add_argument("--library")
    parser.add_argument("--tag")
    parser.add_argument("--recorded")
    parser.add_argument("--from", dest="recorded_commit")
    parser.add_argument("--url")
    args = parser.parse_args(argv)
    texts = {
        "plan": lambda: outputs(plan(args.library, RECORD)),
        "title": lambda: title(args.tag) + "\n",
        "message": lambda: message(args.tag),
        "body": lambda: body(args.tag, args.recorded, args.recorded_commit),
        "issue-title": lambda: issue_title(args.tag) + "\n",
        "issue-body": lambda: issue_body(args.tag, args.recorded, args.url),
        "closing": lambda: closing(args.recorded),
        "marker": lambda: MARKER + "\n",
    }
    needs = {"plan": ("library",), "title": ("tag",), "message": ("tag",),
             "body": ("tag", "recorded", "recorded_commit"), "issue-title": ("tag",),
             "issue-body": ("tag", "recorded", "url"), "closing": ("recorded",), "marker": ()}
    missing = [name for name in needs[args.command] if not getattr(args, name)]
    if missing:
        parser.error(f"{args.command} needs " + ", ".join("--from" if n == "recorded_commit" else f"--{n}"
                                                            for n in missing))
    sys.stdout.write(texts[args.command]())
    return 0


if __name__ == "__main__":
    sys.exit(main())
