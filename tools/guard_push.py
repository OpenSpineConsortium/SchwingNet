"""Refuse a git push the board rules forbid, before it runs: a shim.

Claude Code runs this as a PreToolUse hook on the Bash tool
(.claude/settings.json): the tool call arrives as JSON on stdin, exit
code 2 stops it, and stderr goes back into the session as the reason.
The rules are .claude/rules/board.md's, and their code now lives in the
claim protocol's library, OpenSpineConsortium/symphony-protocol, vendored
here as tools/sdlc_protocol (tools/VENDORED names the version and the
commit). This file stays because the hook and every copy of the template
already made run "python3 tools/guard_push.py".

The rule functions are the library's, re-exported under their old names,
so tests/test_guard_push.py exercises the library's code unchanged. main()
is the library's guard.run written out here, because the tests and any
caller patch this module's branches(), which the library's run() would
not see. Where the vendored library has guard.refused_push, as it has after
0.5.0, main() makes its whole check (whole_reading): until then this hook
read each simple command's words alone, so a push the library refuses for
how bash builds or hands its text, as git pu""sh origin main, bash -c 'git
push origin main' and cat <(git push origin main), passed here. A copy
whose library is older keeps that check (words_alone). Anything the guard
cannot read it lets through rather than wedging the session, save what the
library refuses unread for its length, depth or time; branch protection on
GitHub refuses what matters.

Before a lease push onto claude/N the library's guard, from its 0.5.0,
reads whose claim the branch on origin and the branch pushed carry, from
the claim file docs/agents/claims/N.md, and refuses a lease that would
take another worker's claim (guard.other_holder, its claim_file_reader).
main() hands it that reader when the vendored copy has one, so a copy
whose library is older gains the fence once it vendors that release,
and runs as before until then; a copy made before symphony-template#78
takes the release by hand, with the template's
tests/fixtures/board-STATE.md, whose Given to workers heading the
release changes (docs/start/protocol.md, step 7).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sdlc_protocol import guard  # noqa: E402
from sdlc_protocol.guard import branches, plain_shell, push_arguments, refusal, simple_commands  # noqa: E402,F401


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return guard.PASS
    command = guard.command_of(payload)
    where = guard.where_to_ask(payload, None)
    if hasattr(guard, "refused_push"):
        reason = whole_reading(command, where)
    else:
        reason = words_alone(command, where)
    if reason:
        print(reason, file=sys.stderr)
        return guard.REFUSE
    return guard.PASS


def whole_reading(command, where):
    """The library's full check, as its guard.run makes it (symphony-protocol
    after 0.5.0): every reading of the command, a push judged in each clone
    it may run in, the text handed to a shell read as commands, and a
    command too long or too slow to read refused. branches is looked up here
    at each call, so a test that patches this module's branches is heard."""
    if not guard.may_push(command):
        return None
    return guard.refused_push(command, where, lambda place: branches(place))


def words_alone(command, where):
    """The check a copy whose vendored library has no refused_push, 0.5.0 and
    older, still makes: each simple command's words, judged in where's clone,
    a lease with the claim files when the library reads them."""
    if "push" not in command:
        return None
    pushes = [args for argv in simple_commands(command)
              if (args := push_arguments(argv)) is not None]
    if not pushes:
        return None
    current, default = branches(where)
    reader = getattr(guard, "claim_file_reader", None)
    with_reader = (reader(where),) if reader else ()
    for args in pushes:
        reason = refusal(args, current, default, *with_reader)
        if reason:
            return reason
    return None

if __name__ == "__main__":
    sys.exit(main())
