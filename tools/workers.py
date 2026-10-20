"""The registry of workers, read offline: a shim.

A worker is anything that claims issues here, a person's sessions, a
routine on someone's Claude account or runs in GitHub Actions on this
repository's Claude token, and the registry is one small JSON file per
worker under .github/symphony/workers/ (docs/agents/WORKERS.md). The
registry's rules live in the claim protocol's library,
OpenSpineConsortium/symphony-protocol, vendored here as
tools/sdlc_protocol (tools/VENDORED names the version and the commit);
this file hands its arguments to "python3 -m sdlc_protocol workers", so a
workflow, scripts/check.sh and a person all run the same check:

  python3 tools/workers.py check                  every file holds together
  python3 tools/workers.py list --runs actions    the names, as a JSON list
  python3 tools/workers.py get NAME SETTING       one setting of one worker
  python3 tools/workers.py from-form --body FILE  the "Add a worker" answers
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sdlc_protocol.cli import main as protocol_main  # noqa: E402


def main(argv=None):
    return protocol_main(["workers", *(sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    sys.exit(main())
