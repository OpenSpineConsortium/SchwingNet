# Workers

One small JSON file per worker that runs here on its own: a routine on someone's Claude account, or runs in GitHub Actions on this repository's Claude token. The file is named for the worker, `<name>.json`, and docs/agents/WORKERS.md says what a worker is and how the coordinator and the workers share the repository. A person needs no file: their sessions take their GitHub login as their name, and a file of kind `session` only gives them an area.

Add one with the "Add a worker" issue form, which opens the pull request that adds the file and answers with what to do next, or add the file by hand in a pull request of its own. `bash scripts/check.sh` holds every file here to the rules below (`python3 tools/workers.py check`), and nothing here is ever a credential.

```
{
  "name": "nightly",
  "runs": "actions",
  "about": "Small fixes from the queue, between people's sessions.",
  "area": ["docs/", "src/**/*.py"],
  "lands": "owner",
  "model": "",
  "max_turns": 80,
  "rounds": 6,
  "account": ""
}
```

- name: lower case letters, digits and inner dashes, up to 39; the worker's label is `worker:<name>` and its claim files say `- Worker: <name>`. Name a routine or a worker in Actions after its job, never after anyone's GitHub login, so it never shares a name with a person's sessions.
- runs: `actions` (the workers workflow runs it on this repository's Claude token), `routine` (a routine on someone's Claude account, made with the prompt docs/agents/routines/worker.md gives) or `session` (a person's own sessions).
- about: one line on what it is for.
- area: paths or globs relative to the root; a path ending in `/` takes everything under it, `**` any run of folders. A worker takes the work given to it, then, unclaimed blockers before queued work, the lowest-numbered issue whose "Files likely touched" all fall in its area or that names no files. Empty means anywhere.
- lands: `owner` (the owner merges each pull request) or `auto-merge` (GitHub merges it once the required check is green, where auto-merge is allowed).
- model, max_turns, rounds: for a worker in Actions, the model (empty for the action's default), the turns one run may take (1 to 500) and the runs it may take in a row before the schedule picks up the rest (1 to 50).
- account: a note of whose Claude account runs a routine or whose sessions these are, for the people reading the board; never a credential.
