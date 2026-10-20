# Your Claude accounts as Actions secrets: the token wizard

Every Claude run in GitHub Actions draws on one of your Claude accounts
through a subscription token, the output of `claude setup-token`, a
browser sign-in that prints a token good for about a year and saves it
nowhere. By hand, each token goes from that terminal through a clipboard
into a settings page, once per account, and again a year later. The
wizard `python3 scripts/tokens.py` does that part for you, for every
account you have, without the token ever being shown.

## What runs on which secret

| Secret or variable | One per | Read by |
| --- | --- | --- |
| CLAUDE_CODE_OAUTH_TOKEN | repository, or organization | @claude, the workers in Actions and the coordinator workflow of every repository that sees it (docs/setup/claude-action.md) |
| SYMPHONY_CLAUDE_1 to SYMPHONY_CLAUDE_32 | account: one slot each | the workers in Actions on auto or on a slot; a benchmark in Actions, which spreads its agents over slots 1 to 8, one account per job at a time (OpenSpineConsortium/coordbench's bench.yml); any workflow that names a slot. The control panel fills all 32, an organization's pool holding every member's tokens; this wizard fills 1 to 8 |
| SYMPHONY_CLAUDE_ACCOUNTS | the place | the slots in use, as a list such as `1,2,3`; the wizard keeps it equal to the slots whose secret exists. The bench stops a real run on any other word, such as `01` or `9`, so the wizard writes such a list again |
| SYMPHONY_CLAUDE_<slot>_LABEL | slot, optional | nothing; a word of your own so that `status` can say which account a slot is. A variable is readable by anyone who can read the repository's workflows, so never an e-mail address |
| SYMPHONY_CLAUDE_SETTINGS | the place, optional | the workers in Actions, and for main the coordinator, @claude and the assistant: each slot's model, effort, fallback model and whether it resumes by itself, as JSON by slot, which the control panel's token tiles write (below, "Each token's settings") |

A secret on an organization reaches the repositories on its list (GitHub's
"Selected repositories"), or all of them; a repository's own secret or
variable of the same name outranks the organization's. `status` reads the
repositories the wizard names and the ones GitHub lists as seeing the list
of slots or a token. It names each one's own secret of a name the
organization gives it, and its own SYMPHONY_CLAUDE_ACCOUNTS, with the page
to delete it on, where the organization's list reaches it or the wizard
names it: a list made there by hand would hide the one the wizard keeps
from that repository's workflows. The slots are the owner's own accounts: the
project never holds anyone else's credential (docs/setup/crowdsourcing.md),
and the owner decided on 2026-10-13 to run their own several accounts as
one pool.

## One run of the wizard

On your own computer, in a clone, with the GitHub CLI signed in as an admin
of the organization or the repository and Claude Code installed:

```
python3 scripts/tokens.py
```

1. It checks that gh is signed in and, for an organization, that its
   token carries the scope `admin:org`, which organization secrets need;
   if not, it says to run `gh auth refresh -h github.com -s admin:org`
   and stops before any sign-in is spent.
2. It prints the state: each slot that is set, when, and when to renew
   it (a year later), the slots that are free, the list of slots, and
   whether CLAUDE_CODE_OAUTH_TOKEN is set. Nothing but names, dates and
   counts; GitHub gives nobody a secret's value back.
3. It asks which slot to fill (the first free one by default; a set
   slot's number replaces its token). Where claude-swap (cswap) keeps a
   list of accounts on this machine, it shows that list and asks which
   account the slot is for, by cswap's number. Then it asks for a label;
   `y` takes the account's cswap alias where it has a label's shape, and
   Enter leaves the slot with none, since a label is public.
4. Where this machine has Chrome, Edge or Brave (Chrome or Edge under
   C:\Program Files in WSL), it asks which browser
   profile the slot's sign-in opens in: a new profile named "Symphony"
   and the slot's number by default, one of the browser's own by its
   number in the list it shows, or `n` for the default browser (see
   "A browser profile per account" below). Without a profile, it tells
   you to sign in to claude.ai in your browser as the account that slot
   is for, and waits for Enter. The sign-in page that follows
   names the account it approves: if the browser is signed in to another
   of your accounts, sign out there first, or open the link claude prints
   in a private window and sign in as the right one. While
   CLAUDE_CODE_OAUTH_TOKEN is not set, it asks whether the same token
   should be stored under that name too, the one the workflows run on.
5. It settles everything that could fail after the sign-in before it:
   that each repository named is one your login can see, and the
   visibility and the list each secret will be written with; a token
   minted and then not stored would be a year's token lost with the
   process. Then it runs `claude setup-token` behind a pseudo-terminal of
   its own: the browser opens, or the link is printed for you to open,
   you approve the access, and if the page shows a code you paste it at
   claude's prompt, all as if you had run the command yourself. The
   token claude prints is taken out of the output before it reaches your
   screen and shown as
   `sk-ant-oat**-**************** (kept by the wizard, not shown)`.
6. It hands the token to `gh secret set` on a pipe. gh encrypts it on your
   machine with the organization's or the repository's public key and
   sends only the sealed value; the token is never on a command line, in
   a file, in a log or in the wizard's output.
7. It stores the label, reads GitHub's listing back and confirms the
   secret is there, by name and date, and keeps the list of slots equal
   to the slots whose secret exists; then it asks whether there is
   another account.

The same, one step at a time, without questions:

```
python3 scripts/tokens.py status
python3 scripts/tokens.py add --slot 2 --label work
python3 scripts/tokens.py add --also-main
python3 scripts/tokens.py main
python3 scripts/tokens.py remove 2
python3 scripts/tokens.py order 3,1,2
python3 scripts/tokens.py profiles
python3 scripts/tokens.py forget 2
python3 scripts/tokens.py show 2
python3 scripts/tokens.py show main --copy
python3 scripts/tokens.py share coordbench
```

Where the secrets go is read from the clone's origin: a repository of an
organization takes the organization level with that repository on the
list, a personal repository its own level. Say it instead with
`--org ORG --repos NAME,NAME` (the repositories that see the secrets;
`--visibility all` for every repository of the organization) or
`--repo OWNER/NAME`. A secret that exists keeps its visibility and its
list, which grows by what `--repos` names; the wizard takes nothing off
a list.

What it never does: show a token unasked, write one to a file, put one on
a command line, or read one back from GitHub (GitHub cannot); on Windows
it keeps a copy in Credential Manager, which only `show` reads (below). It refuses
an API key on sight, since runs bill nothing here (docs/project.md), and
anything else that is not a token from `claude setup-token`. It refuses to
run for a repository in crowd mode, which holds no Claude token
(docs/setup/crowdsourcing.md).

## A browser profile per account

`claude setup-token` cannot be told which Claude account to approve: the
browser's signed-in account decides. With several accounts, the wizard
gives each slot a browser profile of its own. On Linux, macOS and WSL it
hands claude a small launcher through BROWSER, the variable claude opens
its sign-in link with, and the launcher opens the link in that profile;
the launcher lives in a folder of the run's own and is gone when the
sign-in ends. In a Windows shell it opens the profile first, on a blank
page so that no second sign-in shows, and then starts claude, whose link
Chrome and Edge send to the profile used last; if it lands in another profile, copy the link claude
prints into the right one.
The first time, a new profile shows claude.ai's sign-in page: sign in
there as the slot's account, then Approve. The profile keeps that
sign-in, so every later token for the slot, a year on, is one Approve.

The wizard remembers each slot's profile and its cswap account number in
tokens.json in your own settings folder (`%APPDATA%\symphony` on
Windows, `~/.config/symphony` elsewhere), never in the repository and
never with an address in it, and offers them as the defaults next time.
`add --profile "Profile 2"` opens one sign-in in a profile without
questions. Set SYMPHONY_BROWSER to a Chromium browser's program to use
one the wizard does not find by itself. In WSL the wizard finds Chrome
or Edge under C:\Program Files and names a profile by its folder; the
Windows browser should reach the sign-in's callback in WSL through WSL's
localhost forwarding, which is not yet tried.

cswap's accounts cannot stand in for a sign-in. cswap keeps each
account's interactive login, whose refresh token changes each time it is
used, so a copy in Actions would sign one side out; and it is a full
login, where `claude setup-token` makes a year-long token that can only
run Claude. The wizard reads only cswap's list of accounts, its
sequence.json, and opens none of its credentials.

## Where it runs

Linux, macOS and WSL have the pseudo-terminal the sign-in runs behind;
claude opens the browser where it can and prints the link otherwise, and
in WSL the link is opened in the Windows browser. A Windows shell has no
pseudo-terminal: there claude runs in the same window, keeping its
keyboard, and its output reaches the screen through the wizard on a pipe,
masked as behind a terminal, so the token should be caught and stored by
itself there too: claude 2.1.302 writes to a pipe as to a terminal, its
link opened and no line wrapped, as measured on Linux; the owner's first
Windows run is the test. That needs a console claude can read its
keyboard from (cmd, PowerShell or Windows Terminal); in Git Bash's own
window or an IDE the wizard says so and takes a pasted token instead. A
machine
may have gh but not claude: there, run `claude setup-token` wherever
claude is and give the wizard the token with `add --paste` or
`main --paste`; the wizard takes the paste path by itself when it cannot
run claude, and refuses a paste where Python says it cannot hide what is
typed. In Git Bash's own window (mintty) a hidden prompt may
hang or echo instead, so run the wizard there through winpty, or from
cmd, PowerShell or Windows Terminal. claude is given a terminal 400
columns wide, so it never wraps the token; were it ever to, the cut token
would be refused rather than stored, and the wizard would say that the
screen may show part of it.

With no computer of your own to run it on, run it in a GitHub Codespace
on the repository, from the browser alone: docs/setup/codespace.md, whose
scripts/codespace.sh signs gh in as you and starts the wizard.

## By hand, where the wizard cannot run

Each secret is one page; the values come from `claude setup-token`, run
while signed in to the account the secret is for.

- An organization secret: open
  https://github.com/organizations/{{OWNER}}/settings/secrets/actions,
  press "New organization secret", type the name (SYMPHONY_CLAUDE_1, or
  CLAUDE_CODE_OAUTH_TOKEN), paste the token as the value, set Repository
  access to "Selected repositories", press the gear beside it and tick
  each repository that should see it, then "Add secret".
- A repository secret: open
  https://github.com/{{REPO}}/settings/secrets/actions/new, type the
  name, paste the value, press "Add secret".
- The list of slots: open
  https://github.com/organizations/{{OWNER}}/settings/variables/actions
  (or https://github.com/{{REPO}}/settings/variables/actions for one
  repository), press "New organization variable" (or "New repository
  variable"), name SYMPHONY_CLAUDE_ACCOUNTS, value the slots in use such
  as `1,2,3`, the same repositories as the secrets, "Add variable".

Then `python3 scripts/tokens.py status` says what GitHub lists.

## A copy on your PC

GitHub never gives a secret back, so on Windows the wizard keeps a copy
of each token it stores in Windows Credential Manager, under
`symphony/org:<organization>/<secret>` (or `symphony/repo:<owner>/<name>/<secret>`).
Windows encrypts it under your own Windows sign-in, and only a program
running as you reads it back. `python3 scripts/tokens.py show N` prints
slot N's token, `show main` the workflows' token, and `--copy` puts it on
the clipboard instead, so it never reaches the screen or the terminal's
scrollback; Windows' clipboard history (Win+V) keeps it after you paste,
so clear it there (Clear all), and a clipboard synced across devices sends
it to them. `profiles` says which slots have a copy. `remove N` deletes a
slot's copy along with its secret, and the copy of CLAUDE_CODE_OAUTH_TOKEN
is deleted by hand, as below; `add --no-copy` and `main --no-copy` keep
none. To see or delete a copy by hand: Control Panel, Credential Manager,
Windows Credentials, the entries that start with `symphony/`. A token
stored before 2026-10-17, or on another machine, has no copy: `add --slot N`
mints a new one that does. Elsewhere than Windows no copy is kept.

## Which secrets a benchmark uses

A benchmark in Actions reads only the slots, never CLAUDE_CODE_OAUTH_TOKEN:
coordbench's bench.yml takes `SYMPHONY_CLAUDE_<slot>` for each slot in the
dispatch's "accounts" box, or in SYMPHONY_CLAUDE_ACCOUNTS when the box is
empty, and refuses a real run when one of them is unset or unseen by
coordbench. So:

- To pick the accounts for one run, type the slots in the "accounts" box
  when you press Run workflow, such as `2,3`; only those are used.
- To keep an account away from the benchmarks, give it no slot: an
  account only in CLAUDE_CODE_OAUTH_TOKEN (`main`) serves @claude and the
  workers alone.
- The benchmark's repository must see the slots. A secret on the
  organization reaches only the repositories on its list, so
  `python3 scripts/tokens.py share coordbench` adds coordbench to every
  slot's secret, its label and the list of slots, with no sign-in, and
  `status` then lists it under "seen by". A benchmark run by a cloud
  session itself, as flowbench's pilot is, uses that session's own
  subscription and reads no secret.

## How much each slot has used

The control panel's Tokens page, and the auto mode that picks a slot for
a run, read the branch pool: each slot's latest five-hour and seven-day
use with their resets, and its per-model weekly limits such as Fable.
GitHub never gives a secret back, so these come from three readings
(docs/research/claude-token-pool.md):

- a worker's run in Actions, which reads its own token's windows from
  Claude's answers at no cost;
- the workflow Pool (.github/workflows/pool.yml): Run workflow asks each
  slot for one word and keeps the reading, which spends that one word of
  the window, so it runs only when you ask, never on a schedule;
- `python3 scripts/tokens.py usage` on the machine where cswap keeps your
  accounts: it reads `cswap list --json` and sends each slot's reading,
  by the cswap account the wizard remembered for it. This is the only one
  that sees the Fable limit, since a token from claude setup-token cannot
  read the usage page cswap reads with a full sign-in. `--also coordbench`
  sends the same readings to coordbench's branch pool too, which its
  benchmark's `auto` reads.

`python3 tools/pool.py pick DIR --slots 1,2,3` is the auto mode: the slot
with the least used five-hour window, then seven-day window, passing over
any slot a window holds at 90 percent or more until it resets.

## Which account each worker runs on

A worker in Actions runs on CLAUDE_CODE_OAUTH_TOKEN unless the file
.github/symphony/accounts.json says otherwise:

```
{"default": "main", "workers": {"runner": "auto", "docs": "2", "review": ["3", "5"]}}
```

`main` is CLAUDE_CODE_OAUTH_TOKEN, a number from 1 to 32 is that slot's
SYMPHONY_CLAUDE_<slot>, a list of slots is `auto` over those of them
SYMPHONY_CLAUDE_ACCOUNTS holds (falling back to main only where the list
names `main`), which is how the control panel gives each worker or agent
its own share of the tokens in one repository, and `auto` takes, at the start of each run, the
slot of SYMPHONY_CLAUDE_ACCOUNTS with the most room, so a worker moves to
the next account before the one it was on runs out. A run already going
finishes on its account. Workers of one run are dealt different free
slots, the first the one with the most room. When every slot of the pool is at its limit the
run does nothing and says when the first is free; the next run picks
again. A slot whose secret this repository does not see falls back to
the main token, and the run says so. The workers still need
CLAUDE_CODE_OAUTH_TOKEN set, which turns them on at all.

## Each token's settings

The variable SYMPHONY_CLAUDE_SETTINGS says how each slot's runs go, and
the control panel writes it when a token's tile is set; a slot it does
not name runs as before:

```
{"1": {"model": "claude-fable-5-1", "effort": "high", "fallback": "claude-opus-5-5", "resume": true},
 "2": {"paused": true}, "main": {"effort": "medium"}}
```

- model: the model the slot's runs take in place of the worker's own
  (.github/symphony/workers/); empty, the worker's, else the plan's default.
  It is one of the tile's models, claude-fable-5-1, claude-opus-5-5,
  claude-sonnet-5-5 or claude-haiku-5-5, as is the fallback; any other name
  is left out, since a name no model answers to would fail every run.
- effort: Claude Code's `--effort`, one of low, medium, high, xhigh, max.
- fallback: a lesser model. When a reading shows the model's own weekly
  limit spent (Fable's, say) while the slot's five-hour and seven-day
  windows have room, auto keeps the slot and runs the fallback on it; it
  is also Claude Code's `--fallback-model`, which a run takes when the
  model is busy. A five-hour or seven-day window at its limit holds the
  slot whatever the model, since every model counts against it.
- resume: true, or left out, lets a slot back in once its limit resets,
  at the next run (the schedule runs every six hours); false keeps it out
  of auto, once a reading after resumedAt shows it at its limit, until
  Resume on its tile sets resumedAt anew.
- paused: true keeps the slot out of auto whatever its readings say.
- id: eight hexadecimal digits the Tokens tab gives each token, which stay
  with the token while it is renewed. A worker in Actions labels the issue
  it worked `token:<id>`, so the control panel's leaderboard credits the
  token, and the person it belongs to, with the issues it closed.
- owner: the GitHub login of the person who added the token; the Tokens
  tab lets only that person, or an owner of the organization, change it.

A per-model limit holds a run only of that model's family (the name's
fable, opus, sonnet or haiku); with no model named, any of them holds the
slot, as before. main's model, effort and fallback reach the coordinator
workflow and @claude's (claude.yml, the control panel's assistant included) too, which read them with `pool.py settings --slot main`. Pausing and resuming steer auto; a worker the file
assigns a slot by number keeps it, with that slot's model and effort. A
value that does not hold together, a model the tiles do not offer among
them, is left out with a word in the run's log (tools/pool.py), so no
setting can stop a run or reach Claude's command line as anything but one
of those models or an effort. The variable
says nothing secret, and anyone who can read the workflows can read it.

## Seeing it in the control panel

The control panel's Tokens page, https://openspineconsortium.com/symphony/control/tokens.html,
shows each slot's windows, resets and per-model limits from the branch
pool, whether it is held, and which slot auto would take now. Its "Read
every slot now" starts the workflow Pool, and its assignments open a pull
request that sets .github/symphony/accounts.json. Its "Paste a token
instead" takes a token printed anywhere, seals it in the browser for
GitHub and stores it as the slot's secret.

## Add a Claude account, from the page

The Tokens page's Add a Claude account mints a token on a GitHub Actions
runner, which starts in seconds where a Codespace took minutes
(.github/workflows/token.yml, tools/token_run.py):

1. The page opens an issue on the repository and starts the workflow
   Token with the issue's number and the secrets public key GitHub gives
   for where the slots live, the organization's or the repository's.
2. The run installs Claude Code and runs `claude setup-token` behind a
   pseudo-terminal. With no browser on the runner, claude prints its
   sign-in link and waits for a code; the run posts the link on the issue.
3. The page shows the link as a button. You sign in to claude.ai as the
   account for the slot, press **Authorize**, and paste the code claude.ai
   shows into the page's box; the page posts it on the issue as you, and
   the run deletes that comment once read. The code mints nothing on its
   own: claude's sign-in is PKCE, so only the claude that printed the link
   can exchange it, and only once, and the run takes a code only from the
   person who started it.
4. The run takes the token out of what claude prints with the wizard's own
   mask, seals it for the page's key (tools/sealbox.py, a libsodium sealed
   box in the standard library) and posts only the sealed value. The page
   stores it as the next free SYMPHONY_CLAUDE_<slot>, and as
   CLAUDE_CODE_OAUTH_TOKEN too when that secret is missing, adds the slot
   to SYMPHONY_CLAUDE_ACCOUNTS and closes the issue.

GitHub opens a sealed box made for its key and nobody else can, so the
token is on no page, in no comment and in no log. The run holds no secret
and GITHUB_TOKEN only comments; starting it needs write access here and,
for the page, SymphonyBoard's Actions permission, read and write. In crowd
mode it never runs.

## Renewing and removing

A token lasts about a year. `status` says "renew soon" within a month of
that and "renew now" past it; `add --slot N` for that slot replaces the
token in place, with the slot's label and list kept. `remove N` deletes
the slot's secret and its label, takes it off the list and forgets the
slot's profile and cswap account on this machine; `forget N` does only
the last. `order 3,1,2` rewrites the list of slots in that order, every
slot that is set once: the bench deals its jobs to the slots in the
list's order, one to each in turn (coordbench's plan.py), so the order
says which account takes the first job, not which is used up first; a
slot added later joins the end, and the order stays; delete
CLAUDE_CODE_OAUTH_TOKEN on its page to turn @claude, the workers in
Actions and the coordinator workflow off (docs/setup/claude-action.md).
Deleting or replacing a secret takes the old token out of Actions and
does not revoke it: it stays good until a year after it was made, and
the Claude Code documentation names no page that revokes a setup-token
token on its own (docs/research/token-wizard.md, open items), one more
reason the wizard keeps every token off every screen.
