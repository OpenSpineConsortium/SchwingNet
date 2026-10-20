"""Hold a claude/<issue> pull request to the claim protocol, in CI: a shim.

The check's code now lives in the claim protocol's library,
OpenSpineConsortium/symphony-protocol, vendored here as tools/sdlc_protocol
(tools/VENDORED names the version and the commit). This file stays because
.github/workflows/ci.yml and every copy of the template already made run
"python3 tools/check_protocol.py": it hands the same arguments to
"python3 -m sdlc_protocol check", which reads the event from
GITHUB_EVENT_PATH and the claim file from the checkout as this tool always
did, prints one problem per line and exits 1 on any, and passes a run
outside a pull request event.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sdlc_protocol.cli import main as protocol_main  # noqa: E402


def main(argv=None):
    return protocol_main(["check", *(sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    sys.exit(main())
