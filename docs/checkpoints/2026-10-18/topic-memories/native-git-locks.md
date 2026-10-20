---
name: native-git-locks
description: State of the native git locks work (symphony-protocol#45, draft) and the probe facts it rests on
metadata:
  type: project
  modified: 2026-10-17T17:00:57.898Z
---

greg asked (2026-10-17) for the coordinator's one-owner-per-resource rule as protocol, with native git, coarse or fine-grained. Note: symphony-template docs/research/native-git-locks.md (#148, merged). Code: symphony-protocol#45, branch claude/native-git-locks, draft, all CI green at e66578b; keep it draft until 0.5.1 is cut.

Design: LOCKS.json on branch `locks`, moved by fast-forward pushes (compare-and-swap), taken in one atomic push (--atomic) with claude/N (lease expecting no branch); keys path, path#symbol (Python ast, Markdown headings), path#<top>, scheme:id; read locks for what edited code calls; `locks verify` behind SYMPHONY_LOCKS (off/advise/enforce, default off).

Facts: a cloud session's proxy refuses pushing custom refs (refs/symphony/*: HTTP 403) but accepts branches, and refuses branch deletion, so locks live on a branch and are never deleted. A probe branch symphony-locks/probe in symphony-template waits for greg to delete.

**Why:** two review rounds fixed 20 findings; guard.py follow-ups (atomic push with a lease misread as stray lease; deleting `locks` not refused) are listed in #45.
**How to apply:** after 0.5.1, mark #45 ready and merge once green; then a template PR wires the claim skill, board sweep, protocol check and a ruleset on `locks`. A coordbench locks arm waits for greg's word and run count.
