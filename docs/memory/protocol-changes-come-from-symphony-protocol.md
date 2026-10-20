A change to the claim protocol is made in OpenSpineConsortium/symphony-protocol, whose sync pull request brings it to OpenSpineConsortium/symphony-template and whose release tags a repository made from the template takes by its own workflow, protocol.yml; tools/sdlc_protocol is never edited in place.

tools/sdlc_protocol is a vendored copy of the package sdlc_protocol, and
tools/VENDORED records it: the version and the commit on the first line,
then the sha256 of every copied file. scripts/check.sh runs
`python3 tools/sdlc_protocol/vendoring.py verify tools` before the tests, so
a pull request that edits the copy by hand, adds a file to it or loses one,
and leaves VENDORED as it was, fails the required check, offline. VENDORED
sits in the same tree, so the same pull request could rewrite it to match;
CI therefore clones symphony-protocol, which is public, and names the clone in
SDLC_PROTOCOL, and tests/test_vendored.py compares every file of the copy
with the library's at the commit VENDORED names, failing when they differ
or when the clone has no such commit. A fix to the board, the
coordinator's releases and overlaps, the registry of workers, the protocol
check, the clerk or the push guard is therefore a pull request to
symphony-protocol.

The template itself, OpenSpineConsortium/symphony-template, then receives the
change with nothing done by hand. symphony-protocol's CI runs the template's own
check against the change (the job `downstream (symphony-template)`) before it
merges. A change reaches the consumers in a release, with one exception:
a change the template's own check must answer, a rendered string its tests
pin or a function it calls that changes, comes here first, by a pull
request that vendors the library's branch (symphony-protocol's README, "A
change a consumer must answer"). From 0.4.1 each release waits for the
owner's approval in symphony-protocol's environment release (its
release.yml), and its workflow Sync, which follows the Release run, weekly
and by hand, carries only the newest published release, from the commit
that raised main to its version, never main's head. Sync
vendors that release into the template and opens, or updates, the pull
request from the branch `symphony-protocol/sync`, made with the App Symphony's token so the
template's CI runs on it, with auto-merge on where the repository allows it;
the template's check decides. The same sync reaches coordbench,
symphony-marketplace and symphony-app: symphony-protocol's ecosystem.json lists which
repository takes which modules, and its ECOSYSTEM.md, generated from that
list, maps all five.

So between such a pull request and the release that carries its change,
the template runs ahead of the newest release. From symphony-template#78
(2026-10-14) symphony-protocol's fixes after 0.4.1 were here, recorded as
0.4.1 with their commit; since 2026-10-16 the copy is 0.5.0's, the
version symphony-protocol's main raised that day, which waits for the
owner's approval. Its VENDORED names 0.5.0 and a8e0e56, the last commit
that changed the package before the tag, since symphony-protocol's
scripts/vendor.py records that commit and not the one it copies from, so
the sync of the tag v0.5.0 finds the copy level, opens nothing and closes
a sync pull request still open. A copy made from the template meanwhile
starts on 0.5.0, and its protocol.yml takes no older tag. Until the
owner approves 0.5.0, Sync, weekly and by hand, knows only 0.4.1, the
newest published release, so it opens `symphony-protocol/sync` taking
the template's copy back to 0.4.1, with auto-merge armed. That pull
request is a downgrade: close it each time it comes back, and never
turn it green, by regenerating a fixture or otherwise. The fixture of
the board's Given to workers heading keeps it red meanwhile.

A repository made from the template is not on that list, so no sync pull
request reaches it. Its own .github/workflows/protocol.yml takes each
release instead: symphony-protocol's release.yml tags each version that
reaches its main once the owner approves its release, and the copy's
workflow, weekly and by hand,
vendors the newest tag when it is newer than tools/VENDORED, on the branch
`symphony-protocol/sync`, and opens the pull request with GITHUB_TOKEN, or
an issue linking it where GitHub Actions may not open pull requests. A
push or pull request made with GITHUB_TOKEN starts no workflow, so the run
starts ci.yml on the branch (its workflow_dispatch) for the required
check, and arms auto-merge, which lands it once the check is green where
the repository allows it. tools/protocol_update.py holds what it decides
and says. It reads tags, not releases, so a tag pushed by hand reaches the
copies before any approval (symphony-protocol's README, Releases). By hand
it is
`python3 <symphony-protocol>/scripts/vendor.py <this repository> --consumer OpenSpineConsortium/symphony-template`,
which copies what the template takes, and a pull request; in the template
the same command needs no `--consumer`, since its remote names it.
protocol.yml brings only tools/, so a release that changes what a copy's
tests pin reaches that copy by hand, with the template's answer to the
change copied in (docs/start/protocol.md, step 7): 0.5.0 changes the
board's Given to workers heading, which tests/fixtures/board-STATE.md
pins in a copy made before symphony-template#78.

The template's push guard hook, tools/guard_push.py, calls the library's
simple_commands, push_arguments and refusal itself, never
guard.refused_push, so a guard fix that lives in refused_push's readings
(F21's clone, F24's substitutions, F25's here-document bodies and limits)
does not reach the hook until the shim calls guard.refused_push; that
switch is part of the template's follow-up for 0.5.1
(docs/research/protocol-fixes-after-0-5-0/README.md).

What is this repository's own changes here as usual: the shims
tools/board.py, check_protocol.py, team.py, workers.py and guard_push.py,
the workflows and the hooks. The owner's one-time setup for the sync is
docs/setup/owner-checklist.md, section 6.

Source: symphony-protocol 0.5.0, its ecosystem.json, scripts/vendor.py,
sync.yml and its README's sections "How a change reaches the other
repositories", "The owner's one-time setup for the sync" and "Releases";
this repository's .github/workflows/protocol.yml and
tools/protocol_update.py.
