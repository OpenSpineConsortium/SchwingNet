"""The clerk's work, done by code so no Claude usage goes to it: a shim.

The clerk's code (seed, route, next, deal and schema, docs/agents/WORKERS.md)
lives in the claim protocol's library, OpenSpineConsortium/symphony-protocol,
vendored here as tools/sdlc_protocol (tools/VENDORED names the version and
the commit). This file stays because .github/workflows/coordinator.yml,
workers.yml and every copy of the template already made run
"python3 tools/team.py ...": it hands the same arguments to
"python3 -m sdlc_protocol team", which answers with the same one line on
stdout, or one line on stderr and exit 1, as this tool always did.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sdlc_protocol.cli import main as protocol_main  # noqa: E402


def main(argv=None):
    return protocol_main(["team", *(sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    sys.exit(main())
