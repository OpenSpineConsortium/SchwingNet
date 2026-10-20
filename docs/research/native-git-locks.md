# Native git locks: the coordinator's one-owner rule as protocol

Source: the thread "Native git locks for the protocol" in the owner's claude.ai Project symphony2, 2026-10-17, started from two of the owner's messages in the thread "Control panel sign-in" (15:27 and 15:29 UTC). It builds on that thread's answer of 15:29, which explained the coordinator's decision and sketched lock refs, three-way merge and Claim Plane's diff check, and on two earlier notes here: git-and-delm-for-verified-results.md (update-ref as compare-and-swap, merge-tree, grite's lease refs) and outside-code-bases.md (Claim Plane's pre-write admission, section 3.3). The probes in section 5 were run in this thread's cloud session on git 2.43.0, and an adversarial review of the first draft, which reran some of them, found three blocking errors and nine smaller ones, all folded in: liveness read by branch rather than by commit, the ends git cannot see, the forced push the compare-and-swap does not stop, and edits that abut.

## 1. The question

The owner asked how the coordinator decided that one thread should own docs/research/symphony-versus-competitors.md and its Claude Doc while another wrote its findings in a file of its own; whether something similar could be handled as coarse-grained locks with native git; and whether fine-grained locks on parts of a file could let two workers edit one file at once, so long as the parts they edit share no dependency. Then: "id like to implement this type of logic into my protocol using native git functionality, either at the coarse or fine grain locking, please compare what im doing to the claude coordinator's approach".

## 2. The answer in short

The coordinator and the protocol hold the same rule, one owner per resource, at different sizes and at different moments. The coordinator applied it to a file, before any work began, by judgement, and nothing detected the clash: it knew of it only because it had written both briefs. The protocol applies it to an issue, at the claim, by an atomic git operation, and for files it only detects and orders: the board's Overlaps section names files two pieces of open work both change, says which lands first, and the second merges main in. So the protocol is pessimistic about issues and optimistic about files; the coordinator was pessimistic about the file.

Both kinds of lock can be built on native git with no server, and the probes below show the pieces work: a lock table kept on one branch, `locks`, moved only by fast-forward pushes, which git accepts from a pusher whose commit descends from the current tip and refuses to anyone who built on an older one, so a push is a compare-and-swap, enforced on GitHub's side once a ruleset blocks forced pushes to that branch; and the claim and its locks pushed together in one atomic push (`--atomic`), so a worker gets the issue and every file it asked for, or nothing. Fine-grained locks name a file and a symbol inside it (a Python function or class, a Markdown section), with a read mode for what the edited code depends on, so two workers editing different functions of one file run at once while one changing a function another depends on waits. Git cannot keep an edit inside its grant or see that two regions depend on each other, so a check compares each pull request's diff with its grant, and the required check on the merged result stays the backstop for meaning.

The recommendation: build it in symphony-protocol behind a switch that is off by default, after 0.5.1 is cut, and measure it as a coordbench arm beside sdlc and a serial arm before turning it on anywhere, since Claim Plane's published gain from the same idea equals running the two features one after the other (outside-code-bases.md, section 3.3). Any run waits for the owner's word and number.

## 3. What the coordinator did

- Resource: one file and one Claude Doc, the competitors notes.
- When: before work, at the moment of writing the second brief.
- How the clash was found: by memory. The coordinator writes every brief, so it knew both threads would touch the same file. No tool found it; a third thread started by someone else would not have been seen.
- Rule: the thread already in the file owns it. The other writes its findings in a new file and hands that file to the owner, who folds it in.
- Why pessimistic there: two branches editing one Markdown file merge cleanly when they touch different lines, but both would rework the same table and summary, so the merge would be clean and the result wrong; and a Claude Doc has no merge at all, the last write replaces the earlier one.
- What it costs: the second thread's work waits on the first for that one file, and the handover is a manual step. What it saves: a conflicted or silently wrong merge, and a lost write to the Doc.

## 4. What the protocol does today

- Resource: one issue. The claim is the first push of `claude/<N>`; a second worker's push of the same name, built from the default branch with a claim commit of its own, is not a fast-forward of the first and is refused, so two workers can never hold one issue. That is already a native git lock, though not a strict create-if-absent: git refuses the non-fast-forward on the client, the push guard refuses a forced push, and GitHub itself would accept a forced one, since the protocol's setup leaves `claude/**` out of every ruleset (docs/agents/PROTOCOL.md, Claim and Release).
- Files: declared, not locked. The claim file lists `## Files to touch`; the board's Overlaps section lists each file more than one piece of open work changes, with the order the work should land, and the coordinator step of the board's run tells each piece once (PROTOCOL.md, Overlaps).
- When the clash is met: at landing. The second piece merges main in after the first lands, resolving any conflict then, and the required check runs on the result.
- Release: by the claim's end (merge, or the coordinator's release after a day without a commit), never by hand per file.
- What it costs: two workers may both rework one table, and the second pays for it at landing; work on a file with no merge (a Claude Doc, a binary, a generated file) can be lost. What it saves: nobody waits before starting.

## 5. Comparison

| | Coordinator, 2026-10-17 | Protocol today | Protocol with locks (proposed) |
|---|---|---|---|
| Unit | a file and a Doc | an issue | an issue, plus files, symbols or named resources |
| Found by | the author of both briefs | the board, from claim files and diffs | the lock table, at the claim |
| When | before work | after, at landing | before work, all or none |
| Stance on files | pessimistic | optimistic | pessimistic for what is locked, optimistic for the rest |
| Mechanism | judgement | ref create-if-absent for issues; Overlaps for files | the same ref create, plus a fast-forward compare-and-swap on `locks`, in one atomic push |
| Non-git resources | covered by judgement | not covered | a named key such as `doc:<id>` |
| Enforced by | the brief | GitHub (claim), the required check (landing) | GitHub (claim and table), a diff check against the grant, the required check |
| Second worker | writes its own file and hands it over | works, then merges main in | gets nothing and picks other work, or works around the held part and files the rest as a follow-up |
| Needs a central party | yes | no | no |

## 6. What native git gives, as probed

The probes ran in a scratch bare repository and against GitHub from this session (scratchpad script, not kept).

1. Atomic claim and lock. `git push --atomic origin claude/1 <lock commit>:<lock ref>` created both refs. A second worker's `git push --atomic origin claude/2 <its lock commit>:<lock ref>`, whose lock commit did not descend from the first, was refused as non-fast-forward and `claude/2` was not created either: all or none.
2. Compare-and-swap by fast-forward. With the lock ref at a commit marked free, two workers each built a commit on that same tip. The first push was accepted; the second, no longer a fast-forward of the new tip, was refused. Two limits. The non-fast-forward refusal is made by the pushing client; the server only checks, under the ref's lock, that the ref still holds the value it advertised in that same connection. A bare repository's `receive.denyNonFastForwards` is off by default and GitHub accepts a forced push unless a ruleset blocks it, so a push with `--force` or a `+` refspec would replace the whole table. The compare-and-swap is therefore the clients' and the push guard's, and becomes GitHub's own only under a ruleset that blocks forced pushes to `locks` (section 7).
3. No deletion needed. The table moves forward only, a release being one more commit, so nothing ever deletes a ref. That matters here: this session's git proxy refused `git push origin :refs/heads/symphony-locks/probe` (it refuses branch deletion, as the project's constraints record).
4. Custom ref namespaces are out for cloud sessions. A push of a root commit to `refs/symphony/probe` in symphony-template was refused by the session's proxy with HTTP 403, while the same commit pushed to the branch `symphony-locks/probe` was accepted. grite's design, locks under `refs/grite/locks/*`, would therefore not work from a cloud session, the workers this project runs most. The lock table lives on a branch.
5. The probe left one branch, `symphony-locks/probe`, in OpenSpineConsortium/symphony-template, which this session cannot delete; it holds one file, lock.json, and touches nothing else.

## 7. Design: coarse locks

The table. One branch, `locks`, beside `board`, whose tree holds one file, LOCKS.json: a sorted list of entries, each a resource key, a mode (write or read), the claim number and the worker. Every change is one commit whose message says what changed ("#12 (greg) takes src/a.py write"). The branch starts with the first acquisition, a root commit; two first acquisitions race like any other, and the second is refused.

Acquire. A worker fetches `locks`, checks that no live entry conflicts with what it wants, writes a new commit on the tip it read, and pushes it, at the claim in the same `--atomic` push as `claude/<N>`, later on its own. The client reads which ref was refused: a refused `claude/<N>` means another worker holds the issue, and the worker picks another; a refused `locks` alone means the table moved, so it fetches again and rechecks, retrying if what it wants is still free. A worker never waits while holding locks: refused at the claim, it picks other work; refused when it asks for more mid-work, it finishes what it holds and files the rest as a new issue that names the holder's, which is the coordinator's handover written as a rule. No worker waiting while holding means no deadlock, and the all-or-none push means no half-acquired set.

Release. An entry belongs to its claim's issue number and is live while that claim is: the branch `claude/<N>` exists on origin and its head is not yet in the default branch. Liveness is read by the branch, not by a commit, because the protocol lets a worker rebase its own claim and push it with a lease, which gives the claim commit a new sha. A merge commit puts the head in the default branch, and a release renames the branch away, so both end the entry, readable with `git ls-remote` and one fetch, no API call. Git alone cannot see three ends: an issue closed without a merge, whose branch tidy.yml deletes only later; a squash merge, whose head never enters the default branch, where the repository does not delete head branches; and a release whose rename GitHub refuses, which leaves the branch in place. The board's run, which reads the issues anyway, counts an entry dead in all three: its issue closed, or its claim counted released. It removes dead entries with one fast-forward commit, and any acquirer may count a dead entry as free and drop it in its own commit, so a lock never outlives its claim by more than one board run.

A dead entry is only ever removed, never revived. Taking a key held by a dead entry removes that entry in the same commit, so when a release is undone (the label claimed put back and the branch renamed back), the returning claim has whatever entries no one has swept, and must take again, and may be refused, any that another claim took meanwhile. A new claim of the same issue inherits the entries left under its number and takes them under its own worker's name with its first acquisition.

What GitHub must add. A ruleset on `locks` that blocks forced pushes and deletions is required before the switch goes to enforce, since without it the compare-and-swap is only the clients' good behaviour (section 6). The template's setup holds every shipped ruleset to the default branch (docs/setup/github.md, tests/test_setup_repo.py), so this ruleset is a change to both. Any ruleset that targets all branches, such as one requiring pull requests everywhere, would refuse every push to `locks`.

Trust. The table is trusted to everyone who may write the repository: anyone who can fast-forward `locks` can drop another claim's entry. That is the same trust the protocol already places in claim branches and the board, and the diff check below catches a lock taken away and then used.

## 8. Design: fine-grained locks

Keys. `path` is the whole file. `path#name` is one symbol: for Python, a top-level function or class, or `Class.method`, its span from its first decorator to its last line, read with the standard library's ast; for Markdown, a section by its heading, to the next heading of the same or a higher level. `path#<top>` is everything in the file outside the named symbols: imports, blank lines between definitions, the end of the file. Any other file takes whole-file keys only. A key that is not a path, such as `doc:a1cb9900`, names a resource outside git and is always whole.

Conflict. Two keys meet when they name the same path and either is the whole file, or they name the same symbol, or one symbol contains the other (`Class` and `Class.method`). Two entries conflict when their keys meet, at least one is a write, and they belong to different claims.

Dependencies. A write lock on a symbol comes with read locks on what that symbol's code names: other symbols of the same file it calls or reads, and symbols it imports from the repository's own Python modules (`from pkg.mod import f` read as `pkg/mod.py#f`). So a worker editing `g`, which calls `f`, holds a read on `f`, and a worker who wants to change `f` is refused until `g`'s claim lands; two workers both reading `f` do not conflict. This is the owner's "as long as the two parts share no dependency", made checkable for direct references. It does not see dynamic calls, a caller nobody is editing, or a dependency through data; the required check on the merged result catches those, as it does today.

Why `<top>` matters. Git's three-way merge conflicts when two changed regions touch or overlap. Two workers who each add a new function at the end of one file change adjacent lines and conflict, though neither touched a named symbol; both need `<top>`, so the second waits, which is correct. Two workers editing the bodies of two different functions change regions separated by at least the lines between them, and merge cleanly.

Edges. Git's merge also conflicts when two changed regions only abut: a review of this note's first draft changed `f`'s last line on one branch and inserted a line just after `f` on another, and `git merge-tree` reported a conflict though the two keys do not meet. An insertion just after a symbol's last line, or just before its first, therefore touches both that symbol and `<top>`, and needs both. Two edits that each stay inside their own region but meet at its edge, such as a function's last line and the blank line after it, can still conflict; locks do not prevent that, and the merge-tree test before landing finds it, to be resolved by the second as today.

Checking the grant. Git cannot keep an edit inside a region, so a check reads the pull request's diff: `git diff -U0` from the merge base, each hunk mapped to the symbols of the base version it falls in (an insertion to the symbol whose body it lands inside, else `<top>`, both at an edge), and each key so touched must be one the claim holds for writing. With the switch at advise the check prints what is not covered; at enforce it fails the protocol check. A pull request that is no claim's, from a fork or from any other branch, holds no grant: at enforce it fails when it touches a key a live claim holds, and passes when it touches only what nobody holds, so locks bind every pull request and not only claims. Before landing, `git merge-tree --write-tree` against main tests the textual merge without a checkout (Git 2.38 or later), as the git-and-DeLM note proposes.

What git's own hunk headers give. `git diff` names the enclosing function in each hunk header, by a built-in pattern for a language once .gitattributes sets the file's diff driver (`*.py diff=python`), else by a default rule, the last earlier line that starts with a letter, `_` or `$`; that is enough to detect an overlap by function in any of those languages, but it gives no span, so it can show where a hunk is and not what a grant covers. The design uses ast for Python and headings for Markdown, and the whole file elsewhere.

## 9. The switch and the order of work

- `SYMPHONY_LOCKS`, or the file `.github/symphony-locks`, set to off (the default), advise or enforce. Off changes nothing in any copy.
- In symphony-protocol: a module `locks.py` with the keys, the symbols, the table and its rules as pure functions, the git side in the bare-git adapter, a CLI `python3 -m sdlc_protocol locks` with status, plan, acquire, release and verify, tests on scratch repositories, and a section of spec/PROTOCOL.md. Built on its own branch as a draft and kept off main until 0.5.1 is cut, since the protocol fixes toward 0.5.1 are changing main now; it never touches the release or its approval gate.
- Then, in the template, by its own pull request once a release carries it: the claim skill's push made atomic with the locks, the board's run sweeping dead entries and showing the table, the protocol check running verify, and the ruleset on `locks` in scripts/setup-repo.sh.
- Then a coordbench arm, sdlc-locks beside sdlc and a serial arm on the same pairs, measuring pass, wall time, the share of work serialized and refusals; it waits for the owner's word and the number of runs.

## 10. Open questions

- Whether pessimistic locks gain anything on CooperBench beyond serialization, which Claude Code agents declaring their own files and symbols, with no oracle context, will show; Claim Plane's study used a planner with the gold patches' regions.
- How often a worker's declared files miss what it ends up touching, so that verify refuses work after it is done; the mid-work acquisition and the handover rule are the answer on paper and need the measurement.
- Starvation: refusing rather than waiting rules out deadlock, but a long-held lock, a read on a function others want to change held a day by an idle claim or longer by finished work waiting for its merge, refuses every writer meanwhile, and nothing yet queues them in order.
- Whether one table on one branch becomes a hot spot with many workers; per-resource branches would spread it at the cost of a branch per file in every listing.
