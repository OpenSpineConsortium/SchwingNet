# Connect the grid to GitHub

Oct 14, 2026 - @Someone

For Ashley: how a Beethoven session on the Wayne State grid gets and pushes OpenSpineConsortium/spine-program and your own repositories, in four steps of about ten minutes.

## What this sets up

Your Beethoven session already reaches GitHub: it cloned your two public repositories from the compute node. What it lacks is a login, so it cannot read the private [spine-program](https://github.com/OpenSpineConsortium/spine-program) repository or push to anything. The fix is one personal access token from your own GitHub account, stored in a file in your grid home that git reads by itself. You have Write access on spine-program already (checked 2026-10-14).

Three rules, from the repository's own:

- You type the token yourself, into an editor. It never goes on a command line, into a job script, into a chat with Claude, or into any file of a repository. Claude on the grid must not see it, and the session was right to refuse handling it.
- The Claude GitHub App links the session offered are for sessions on claude.ai, not for git on the grid. Skip them.
- Run these commands in the terminal of your Beethoven session (a compute node), not on the login node, where git has not been tested yet.

## Step 1: make the token on github.com

One classic token with the `repo` scope covers spine-program and your own repositories at once.

1. Sign in to github.com as aschehr and open [Generate new token (classic)](https://github.com/settings/tokens/new). If GitHub asks you to confirm your password, do so.
2. Note: `grid git`. Expiration: 90 days, or longer if you prefer; GitHub e-mails you before it expires, and a new token means repeating steps 1 and 2 only.
3. Under Select scopes tick the box `repo` (the top one; its sub-boxes tick themselves). Nothing else.
4. Click Generate token. The token is shown once, starting with `ghp_`. Keep this browser tab open until step 2 is done; copying it into a password manager is fine, copying it into a chat is not.

If the page says the organization does not allow classic tokens, make a fine-grained one instead at [Generate new fine-grained token](https://github.com/settings/personal-access-tokens/new): Resource owner OpenSpineConsortium, Only select repositories, spine-program, Repository permissions Contents, Issues and Pull requests each set to Read and write, then Generate. A fine-grained token has one owner, so your own repositories need a second one with Resource owner aschehr; the section on your own repositories says how to store two.

## Step 2: store it on the grid

In your Beethoven session, open a terminal on the compute node (the panel's terminal, or ask Claude to open a shell and then type the commands yourself). The token goes into a file only you can read, and git is told to read it from there.

1. Make the private folder and open the file in an editor:

```
mkdir -p ~/.beethoven && chmod 700 ~/.beethoven
nano ~/.beethoven/git-credentials
```

2. Type one line into the editor, with your token in place of the placeholder, then save (Ctrl-O, Enter) and leave (Ctrl-X):

```
https://aschehr:ghp_PASTE_THE_TOKEN_HERE@github.com
```

3. Lock the file and point git at it:

```
chmod 600 ~/.beethoven/git-credentials
git config --global credential.helper "store --file ~/.beethoven/git-credentials"
git config --global user.name aschehr
git config --global user.email 288196632+aschehr@users.noreply.github.com
```

The last two lines set the name and the no-reply address GitHub gives your account on your commits, so no personal e-mail enters the repository. You can now close the GitHub tab from step 1.

## Step 3: clone spine-program and check it worked

Clone into your own folder on the lab volume, not under `hpcworker`, whose run folders the framework empties. Replace `<AccessID>` with your grid login (the one Beethoven signs you in with).

```
git clone https://github.com/OpenSpineConsortium/spine-program /rs/rs_grp_oschome/<AccessID>/spine-program
cd /rs/rs_grp_oschome/<AccessID>/spine-program && git log -1 --oneline
```

The clone prints Receiving objects and ends without asking for a username; the log line is the latest commit on main. That is the whole test: git found the token in the file and GitHub accepted it. From then on `git pull`, `git push -u origin claude/<issue>` and the rest of the claim protocol work from this clone, and Claude in your Beethoven session can run them with the prompt in the repository's README under [How a student starts](https://github.com/OpenSpineConsortium/spine-program#how-a-student-starts), with `aschehr` as the worker name.

Two things to know about this clone:

- Each folder's `results/`, `figures/`, `manuscripts/` and `regulatory/` are links to `/rs/rs_grp_oschome/shared/spine-program/archive/`, which Greg fills once with a script; until he has, those links point at nothing and the files are read from git history as [ARCHIVE.md](https://github.com/OpenSpineConsortium/spine-program/blob/main/ARCHIVE.md) says.
- Issue [19](https://github.com/OpenSpineConsortium/spine-program/issues/19) is the task that records what you have just measured; if you want a first task, that is the one, and most of its answer is already in your hands.

## Step 4: push to your own repositories

With a classic token nothing more is needed: the two clones your session already made push once their remote uses HTTPS, which a public clone does. In each one:

```
git remote -v
git push origin HEAD
```

If `git remote -v` shows `git@github.com:` instead of `https://github.com/`, switch it: `git remote set-url origin https://github.com/aschehr/OpenSpineToolbox` (and the same for the other repository).

With two fine-grained tokens, the credential file holds one line per token and git must be told which is which by the repository name, since both lines carry the same host and user. Put them in as

```
https://aschehr:TOKEN_FOR_ORG@github.com/OpenSpineConsortium
https://aschehr:TOKEN_FOR_YOU@github.com/aschehr
```

and run `git config --global credential.useHttpPath true`, so git matches on the path as well as the host.

## If something refuses

| What you see | What it means | What to do |
| --- | --- | --- |
| `Username for 'https://github.com':` | git did not find the file | Check the helper line: `git config --global credential.helper` must print `store --file ~/.beethoven/git-credentials`; check the file's one line has no spaces |
| `remote: Repository not found` on spine-program | the token cannot see the private repository | A classic token: the organization may require you to authorize it, under Configure SSO on the [tokens page](https://github.com/settings/tokens); a fine-grained token: its resource owner must be OpenSpineConsortium and it may wait for Greg's approval under the organization's settings |
| `remote: Permission to ... denied` | the token can read but not write | Classic: the `repo` scope is missing; fine-grained: Contents must be Read and write |
| `remote: Invalid username or token` | the token was mistyped or has expired | Make a new one (step 1) and replace the line in the file (step 2) |
| `Permission denied` on `/rs/rs_grp_oschome/...` | your AccessID is not on the lab volume's access list | Tell Greg; it is a one-line change on his side |
| the command is killed at once | you are on the login node, not a compute node | Run it inside the Beethoven session's terminal instead |

Anything else: copy the exact message into the project chat, with the token itself and your AccessID left out, and Claude or Greg answers there.
