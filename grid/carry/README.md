# Carried folders

A carried folder is a set of files that a cloud session can hand on only through GitHub, brought onto the grid's data root by the gate word `fetch <id>` (grid/gate.sh, word_fetch_carried). The first was the Claude project "symphony_4"'s shared folder, which does not follow the owner to another account's project: "no please push these to the grid to the new project to fine there" (the owner, 2026-10-28 17:24 UTC).

The session puts the files on a branch of a private repository, as a history of its own whose last commit holds the folder alone, with a file SHA256SUMS at its top that lists every other file. A pull request then adds `<id>.txt` here, one line per value:

- `repo`: the repository, OWNER/NAME.
- `branch`: the branch the files ride on.
- `commit`: the branch's commit to land, all 40 hex digits; the word refuses a branch that has moved.
- `files` and `bytes`: how many plain files the commit's tree holds, SHA256SUMS among them, and their bytes, as `git ls-tree -r -l` counts them.
- `manifest`: the sha256 of SHA256SUMS.

Lines that start with # say what the folder is. Once the record is on main, `fetch <id>` fetches the commit with git on the login node, through gh's own sign-in, into a git copy under the data root, checks the commit, the counts, SHA256SUMS and every file against it, and only then puts the folder in place as the landing `<id>` (0700) with meta/CARRIED, the line "carried <commit> <files> <bytes> <time> <repo> <branch>". It is a copy and no computation, so no job is queued. The size rule decides first: twice the bytes and a fiftieth more, for the git copy that lasts until the folder is in place, must fit the room after what the running fetches owe, and the rule's lock is held until the folder is in place. A later send checks the landing against SHA256SUMS again and fetches nothing; a landing of that name that holds no carry of the commit is refused, never overwritten.

After the landing is checked, the branch may be deleted on GitHub: it is a carrier and is never merged.
