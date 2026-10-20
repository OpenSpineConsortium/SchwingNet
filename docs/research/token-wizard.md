# The token wizard: research notes

Notes of the thread "Claude token setup wizard" (item 11 of the
2026-10-15b handoff), written 2026-10-16 and kept current as the work goes
on, from the thread's own reading and probes: no Claude Doc, artifact or
upload lies behind it. It built scripts/tokens.py, and these notes stay
here so they accumulate in the repository, as the owner asked on
2026-10-16. No line here holds a token
or a credential; a token's shape is written in pieces where it has to be
named. docs/setup/claude-tokens.md is the page for a person who wants to
use the wizard; this file is why it is built the way it is.

## The ask

The owner's handoff message of 2026-10-15 23:35 UTC, item 11: make the
Claude token authentication of Symphony seamless; set up all of the
owner's Claude accounts' long-lived tokens as saved secrets; "a wizard or
something". The standing rule binds hardest here: no API key and no
Claude credential anywhere, so a session never handles a token, and the
wizard runs on the owner's own computer.

## How Claude tokens were taken before (read 2026-10-16)

- One token per account: `claude setup-token`, a browser sign-in in an
  interactive terminal UI, prints a long-lived (about one year)
  subscription token and saves it nowhere (docs/setup/claude-action.md;
  the Claude Code documentation on authentication).
- CLAUDE_CODE_OAUTH_TOKEN, a repository secret, is read by
  .github/workflows/claude.yml, workers.yml and coordinator.yml; every
  Claude run in Actions draws on that one account's plan
  (docs/agents/WORKERS.md, What it costs). It was stored by
  `/install-github-app` (one OAuth flow) or by `bash
  scripts/setup-repo.sh --token`, which runs `gh secret set` at gh's
  hidden prompt after the person ran `claude setup-token` in another
  terminal and copied the token through the clipboard.
- The pool: OpenSpineConsortium/coordbench's .github/workflows/bench.yml
  takes, for a real run, one organization secret SYMPHONY_CLAUDE_<slot>
  per account, slots 1 to 8, named one by one in a chain of fixed names
  (a secret looked up by a computed name would hand the runner every
  secret, which CodeQL flags), runs one job per account at a time in the
  concurrency group of its slot, and reads the slots in use from the
  variable SYMPHONY_CLAUDE_ACCOUNTS, words between commas or blanks,
  each exactly one of 1 to 8, a real run refused on any other
  (bench/cooperbench/actions/plan.py, chosen_accounts). The owner's
  to-do list of 2026-10-15b, item 3, had the owner make each of those
  secrets by hand on the organization's secrets page with "Selected
  repositories" and coordbench ticked.
- The cloud route is retired: COORDBENCH_CLAUDE_TOKEN in a claude.ai
  cloud environment served one cloud session's bench agents; the
  handoff of 2026-10-15b says not to add it to a new account, and the
  coordination experiment now runs its agents as subagents with no token
  anywhere.
- The terms question is the owner's and settled: the owner decided on
  2026-10-13 to run their own several accounts as one pool, knowing the
  terms-of-service question, and that does not change the rule for
  contributors' credentials (CLAUDE.md, Durable decisions). A crowd
  repository holds no Claude token at all (docs/setup/crowdsourcing.md).

## What `claude setup-token` does (Claude Code 2.1.301, read 2026-10-16)

- Its help text has one option, --help: no quiet or raw output, so
  nothing documented prints the token alone, and `claude setup-token |
  gh secret set NAME` would feed gh the whole screen.
- The binary's strings give the screens: "This will guide you through
  long-lived (1-year) auth token setup for your Claude account.",
  "Browser didn't open? Use the url below to sign in", "Paste code here
  if prompted >", "Long-lived authentication token created
  successfully!", "Your OAuth token (valid for", the token on a line of
  its own, "Store this token securely. You won't be able to see it
  again." and "Use this token by setting: export
  CLAUDE_CODE_OAUTH_TOKEN=<token>", so the token appears twice. The
  token's head is sk-, ant-, oat, two digits and a dash, then letters,
  digits, underscores and dashes.
- Run behind a pseudo-terminal in the session's container, with nobody
  signing in and the process stopped after eight seconds, so that no
  token existed: the UI renders (the Claude Code banner, the guide
  line, the sign-in link as an OSC 8 hyperlink with the plain URL beside
  it, "Hold Shift while selecting to use your terminal's native copy",
  "Paste code here if prompted >"). Claude Code 2.1's renderer places
  each word by its column (CSI n G before every word) and ends a line
  with two carriage returns and a newline; a token is one word, so it
  comes whole between a column code and a line end. The sign-in link
  carried code=true with platform.claude.com's code callback, the flow
  where the page shows a code to paste. The renderer also turns on
  bracketed paste, focus events and keyboard-protocol queries, which the
  person's terminal answers on standard input: the wizard forwards the
  keyboard raw for that reason. On Linux claude opens the link with
  xdg-open and prints it when that fails.

## What gh does (gh 2.89.0's help text, read 2026-10-16)

- `gh secret set NAME` with no --body reads the value from standard
  input when none is a terminal (the help: "reads from standard input
  if not specified"), encrypts it locally and sends the sealed value; so
  the value need never be on a command line.
- An organization secret's visibility defaults to "private": a write
  with no --visibility would quietly set that on an existing secret, and
  --repos replaces the list rather than adding to it; so the wizard
  always sends the visibility, keeping an existing secret's own, and
  sends the union of the existing list and the one named. The lists
  come from orgs/{org}/actions/secrets/{name}/repositories and
  .../variables/{name}/repositories.
- `gh secret list --json` gives name, numSelectedRepos,
  selectedReposURL, updatedAt and visibility; `gh variable list --json`
  those plus createdAt and value; GitHub never gives a secret's value
  back, so the check after a store is by name and by GitHub's own date,
  before and after.
- Organization secrets need gh's token to carry admin:org, which `gh auth
  login` does not grant by default; `gh auth status` lists an OAuth
  token's scopes quoted, and the wizard looks there before any sign-in
  is spent.
- `gh auth status` could not be read in the session's container (its
  token is the proxy's), so the scopes line's form is from gh's source
  and the fixture in tests/test_tokens.py, not from a live run.

## Design: why a pseudo-terminal, and why these names

- The seamless route is the one with no clipboard: run `claude
  setup-token` for the person, take the token out of its output, hand it
  to gh. The output is an interactive UI that needs a terminal, so the
  wizard forks it behind a pseudo-terminal of its own (Python's pty and
  termios, standard library), sets the child's window to 400 columns so
  the token is never wrapped, forwards the keyboard raw, and runs every
  chunk of output through a masker before it reaches the screen. The
  masker keeps a tail that may be a token's start until the rest comes
  and keeps the last characters shown for matching, so a token cut at any
  byte, one character at a time included, is still caught whole; the
  tests cut a frame at every size from 1 to 47 and a few larger.
  util-linux's script(1) was considered and dropped: it copies the
  session to the terminal itself, so the token would show, and macOS's
  differs in syntax.
- gh's hidden prompt stays as the fallback (`add --paste`, `main
  --paste`), for a Windows shell, which has no pseudo-terminal, and for a
  machine with gh but no claude; a pasted export line is accepted and an
  API key refused, and a window where Python's getpass cannot hide the
  input (it warns so and would echo) is refused.
- The names are the consumers' names, unchanged: CLAUDE_CODE_OAUTH_TOKEN
  and SYMPHONY_CLAUDE_1 to 8 with SYMPHONY_CLAUDE_ACCOUNTS. One new
  convention, optional: SYMPHONY_CLAUDE_<slot>_LABEL, a variable holding
  a word of the owner's own, since GitHub shows nothing of a secret but
  its name and date and the owner has several accounts to tell apart at
  renewal time; a variable is readable by anyone who reads the
  repository's workflows, so the page says never an e-mail address.
- Organization secrets, not GitHub "environment" secrets: bench.yml's
  run-real jobs do not run inside its environment bench (only the
  approve job waits there), so an environment secret would reach none of
  them; the owner's "environment secrets" of the ask are read as the
  Actions secrets the workflows name.
- The variable SYMPHONY_CLAUDE_ACCOUNTS is kept equal to the slots whose
  secret exists, since a slot named there with no secret makes
  plan.py refuse a real run, and a secret not named there is idle.
- Crowd mode is refused the way scripts/setup-repo.sh refuses it: the
  clone's mode line in docs/project.md, then each named repository's
  variable CLAUDE_CROWD, read before any write; a read that fails for a
  reason other than 404 stops the wizard rather than guessing.

## Checks

- tests/test_tokens.py: the masker at every chunk size, in Ink's form and
  in the 2.1 renderer's placed-words form; the mint with a fake claude
  behind the real pseudo-terminal (the fake reports it saw a terminal of
  400 columns, no COLUMNS from the shell, and the code typed); the store
  through the fake gh, in the process and as a command, with the token
  on gh's standard input, once, and on no call's command line; the paste
  path; the API-key refusal; the crowd refusals; status, remove, the
  place options before and after the command and the pairings refused
  before any call, the origin's reading, the scope check, and that
  neither the script nor the test file holds a secret's shape.
- `bash scripts/check.sh` passes, the filled copies included: a crowd
  copy runs these tests with its own mode line saying on, so the tests
  read a project file of their own.
- The probes, the wrap fuzz and the mutants that the thread and its
  reviewers ran are kept in docs/research/token-wizard-checks/, each with
  the commit it was written against and what it showed there.

## The adversarial review (2026-10-16) and what changed for it

A reviewer with the diff, gh 2.89.0's source and Claude Code's
documentation, and probes of its own, found no path by which a token of
the known shape reaches the screen, a command line, a file, a log, an
error message, gh's arguments or a child's environment, and twelve
things to fix, none of them must-fix. All twelve are fixed on the branch:

- The masker gave up holding a tail longer than 400 characters and
  printed it raw, token included, where claude's output ran on with no
  break after the token (a contrived output, but the one invariant).
  Now a run that reaches the chunk's end is held only while it is short
  enough to be a token still arriving; a longer one is masked as it is
  and refused afterwards by its length, so it is never shown and never
  stored.
- `gh auth status` fails when any account of any host gh knows is stale,
  and lists the hosts in its config's order, so a working github.com
  login beside an old one read as "not signed in", and the scopes read
  could be another host's; and "admin:org" was matched as a substring,
  which admin:org_hook satisfies. Now the wizard asks `gh auth status
  --hostname github.com --active` once (an older gh without --active is
  asked for the host alone), and reads the quoted scopes exactly.
- The reads that could fail (the list an existing secret reaches, which
  needs admin:org on that path; a repository name the login cannot see)
  ran after the token was minted, so a failure there lost a year's token
  with the process, with no way to revoke it. Now every repository named
  is read and every secret's and variable's scope is settled before the
  sign-in, and the writes take what was settled.
- The only defence against a token wrapped over two lines was the
  400-column window; a library that reads COLUMNS from the environment
  would wrap at the shell's width, and the first piece would be stored
  as the token with the rest printed in the clear. Now the child's
  environment carries no COLUMNS or LINES; a run of a token's characters
  that begins the line after a masked token is taken for the rest of a
  cut token and the mint refused, saying the screen may show part of it;
  and a captured token shorter than 60 characters is refused as a piece.
  Whether Claude Code's renderer honours the window it is given is still
  only inferred (open items). The second pass found the run's check
  incomplete (below).
- The page said a token can be revoked at claude.ai under Settings,
  which nothing verified; it now says what the documentation says, that
  deleting the secret does not revoke the token, and names no page.
- `--org X --repos a,b --visibility all` was accepted and the repositories
  silently dropped; it is refused, as gh refuses it.
- The pairings of options that cannot go together were found after a
  `gh auth status` round trip, with exit 1; they are found before any
  call, with exit 2, as the docstring promised.
- The terminal was restored with TCSADRAIN, which keeps keys typed between
  claude's end and the restore for the wizard's next question, and the
  modes claude turns on (bracketed paste, focus and mouse events, its
  keyboard protocol) were left on after a claude killed mid-screen. Now
  TCSAFLUSH, and a reset sequence written after claude ends.
- claude installed by Claude Code's own installer lives at
  ~/.claude/local/claude behind a shell alias, invisible to PATH; the
  wizard looks there too.
- Only the oat shape was masked, so another key claude might echo (an API
  key from the environment) would reach the screen; every sk-ant- shape
  is masked now and only the oat kind kept.
- Tests added: `main`, an existing secret keeping its visibility, the
  hold limit, the cut token, the other shape, the status read's flags
  and the fallback, admin:org_hook, the usage errors as a process, and
  the whole add run asserting the token is on no call's command line and
  on gh's standard input once.
- The page's step 7 described an order the wizard does not follow, named
  a bare `--paste` that the parser has only on `add` and `main`, and the
  wizard printed the sign-in note twice; all three fixed, and the Git
  Bash window named.

## The second review pass (2026-10-16) and what changed for it

The same reviewer read the fixes: eleven of the twelve were right and
complete, the check for a token cut over two lines was not, and the page
claimed two things the code did not hold. Fixed on the branch:

- The cut-token check missed the realistic cut. It wanted 20 characters
  or more of the token on the next line, while a token of about 108
  characters wrapped at a width of 90 to 108 leaves a rest of 1 to 19,
  and the 60-character floor let the first piece through; a rest begun
  by blanks or by a code other than a cursor move was missed too. The
  tests cut at 50 characters, below the floor, so they proved nothing
  about the check. Now the rest is known by where it stands, not by its
  length: a run of a token's characters alone on the line after the
  masked part, past blanks and any terminal code, ending with its line.
  claude prints the token last on its line, and a word of claude's is
  followed by a blank or by the code that places the next word, so a
  word is never taken for a rest. The tests cut at 40, 50 and 79
  characters and before the last one, in Ink's form and in the
  renderer's placed form, indented and after a hyperlink code; a fuzz
  of every width from 20 to 419 columns, three token lengths, both forms
  and four chunk sizes (9,600 runs) stored no wrong token and refused
  nothing at 400 columns or wider. The exact length of a setup-token
  token would close every width at once, but neither the documentation
  nor the binary's own pattern for it (20 characters or more after its
  head) pins it, so it is not guessed.
- A run past the hold limit that came in pieces was refused as a cut
  token, with the wrong words; what follows such a run is no longer
  watched, so it is refused by its length.
- A word of 20 characters or more at the start of the line after the
  token was taken for a cut; a word followed by a blank is not.
- The page said the wizard refuses a paste in Git Bash's own window;
  getpass there takes the console's path and may hang or echo rather
  than warn, so the page says that.
- After a store, a failure in the label, the read-back or the list of
  slots ended with gh's error alone, though the token was stored; the
  error now says the token was sent, and to run status before storing
  another.
- Left as they are: the terminal reset leaves the alternate screen alone,
  which claude setup-token is not known to use, and is written only when
  the keyboard is a terminal; claude is looked for on PATH and at
  ~/.claude/local/claude, and the native installer's ~/.local/bin is on
  PATH where it is installed.

## After the merge (symphony-template#100)

The follow-up and its adversarial review, 2026-10-16. The bench's own
reader was read from coordbench's bench/cooperbench/actions/plan.py
(parse_list and chosen_accounts) that day.

- A repository's own variable outranks the organization's of the same
  name, as its own secret does, and the 2026-10-15b to-do list told the
  owner to make SYMPHONY_CLAUDE_ACCOUNTS by hand as coordbench's own
  variable; the wizard keeps the organization's list, which such a
  variable would hide from bench.yml. `status` now names a repository's
  own SYMPHONY_CLAUDE_ACCOUNTS with the slots it names and the page to
  delete it on, as it named a repository's own secrets already. The
  wizard does not delete it, since it changes only the place it was
  given. The to-do list's step now says to run the wizard and to delete
  such a variable if it was made.
- `status` reads the own secrets and variables of every repository the
  options name and of every one GitHub lists as seeing the list of slots
  or a token secret of selected visibility, so a run from a clone of
  symphony-template that names no repository still reads coordbench's.
  A repository that sees them through "all repositories" is not listed by
  GitHub and is read only when named. A repository found on a listing is
  told only of its own of the names the organization gives it: one the
  organization's list does not reach keeps its own list, its only one,
  and is not told to delete it. Each listing is asked for once per state,
  since a write is always followed by a new state.
- The bench splits the list on commas and blanks and refuses a real run
  on any word that is not exactly 1 to 8. The wizard read numbers, so
  `01,02` named slots 1 and 2 to it, the list was left as it was, and the
  bench refused the run while `status` showed a good list. A slot is now
  a word looked up among 1 to 8 (slot_number), for the list and the slot
  question alike, which also ends two tracebacks: a superscript two
  passed isdigit() and failed int(), and int() refuses more than 4,300
  digits. A list with any other word is written again on the next add or
  remove, and `status` says it stops the bench's real runs.
- What a person typed into a variable never reaches the terminal as
  written: a list is printed as the slots it names, and a label made by
  hand on the variables page is printed only when it is a word of the
  label's shape. The label check uses fullmatch, since `$` let a label
  ending in a newline through.
- The wizard's closing status was printed from the check's read, made
  before the list was written, so the owner's first run would have
  printed SYMPHONY_CLAUDE_ACCOUNTS as written and then as not set; the
  closing status reads everything again.
- Two review passes; their mutants (the raw value printed, the failed
  read not caught, only the named repositories read, the labels raw, the
  list compared by slots, a reader by int(), match for fullmatch, names
  compared by case, the closing status not read again, every repository
  told of every name, no listing cache, no rewrite note, the secrets'
  listings not read, a failed listing silent, repositories told apart by
  case) each fail the tests.

## A browser profile per slot and cswap's accounts (2026-10-17)

The owner ran the wizard in Windows PowerShell on 2026-10-17 and asked
whether it could use the accounts claude-swap (cswap) already holds, so
they need not sign in again, or sign in for them, or do it from the
command line. Read for the answer, in the thread "Beyond cooperation",
from the programs themselves:

- cswap 0.27.2 (PyPI claude-swap, github.com/realiti4/claude-swap) keeps
  each account's interactive OAuth login, an access token with a
  refresh token that rotates on use, in the keychain or its encrypted
  backups, and its list of accounts in sequence.json under
  ~/.local/share/claude-swap on Linux and WSL (XDG_DATA_HOME where set,
  moved there from ~/.claude-swap-backup) and ~/.claude-swap-backup on
  Windows and macOS: per account its email, organizationName,
  organizationUuid and an optional alias. Reusing a cswap login in
  Actions would sign one side out at the first refresh, and it is a full
  login, not the inference-only token setup-token makes; so it is not
  reused, and only sequence.json is read.
- Claude Code 2.1.302, Linux and Windows builds alike (the npm packages
  @anthropic-ai/claude-code-linux-x64 and -win32-x64, read with
  strings): `claude setup-token` takes no option naming an account; its
  OAuth flow shows the manual link and opens the automatic one, whose
  redirect is a localhost callback, with its URL opener, which starts the
  program BROWSER names, with the link as its argument, when BROWSER is
  set (else rundll32 url,OpenURL on Windows and xdg-open on Linux). So a
  launcher named by BROWSER receives the link without the wizard reading
  claude's screen. On Windows that does not hold for a batch file: the
  review found that the npm build's opener wraps the link in literal
  quotes and runs a .cmd through cmd.exe (cross-spawn), and batch
  argument parsing cuts the link at its first = or &, so Chrome would be
  given a broken link in the right profile while claude thought it
  opened; the native binary's opener passes the link bare, which a
  batch file cuts the same way.

What was built: the wizard finds Chrome, Edge or Brave where each
installer puts it (or SYMPHONY_BROWSER), lists the browser's profiles
from its Local State where it can read it, and hands claude a launcher
that opens the link with --profile-directory, written for the one run
into a private temporary folder and removed after; cswap's accounts are
shown by number, the alias offered as the label unless it is not a
label's shape (an address never is); the profile's folder name and the
cswap number per slot are kept in tokens.json in the user's settings
folder, outside the repository. A Windows shell, which has no
pseudo-terminal, gets no launcher: the wizard starts the browser in the
slot's profile at claude.ai, waits two seconds, then starts claude
setup-token in a console of its own, so the link goes to the profile
used last, and takes the token at the hidden prompt, asking again on an
empty paste and checking before claude starts that the prompt can hide
what is typed. tests/test_tokens.py runs the POSIX launcher end to end
with a fake claude that opens BROWSER as the real one does.

The review of 2026-10-17 also found, and the same pull request fixed: a
browser path outside ASCII crashed the wizard (now refused, with "answer
n"); a sequence.json whose sequence was not a list crashed it; Enter at
the label question published the cswap alias (now `y` takes it and Enter
means none, and the account question names the remembered account so a
renumbering in cswap shows); and a paste with a line break left the rest
of the token in a Windows console's input, where the next question would
echo it (now drained).

After the merge, the template's filled copy failed one run in two on
"browser-report.json was never written" (found by the thread on the
protocol fixes toward 0.5.1). The launcher started the browser in the
background under nohup, on claude's terminal; when claude ended, the
terminal's hangup reached the browser in the moment before nohup could
ignore it. Under load it failed 11 runs in 30. The launcher now ignores
the hangup itself before it forks the browser, which inherits that, and
the same loop then failed none in 100 under load; a real browser started
as claude exits had the same exposure, so the fix is in the launcher,
not the test.

The owner's first run on Windows (2026-10-17): the window claude ran in
closed when claude ended, before the token could be copied, and the
profile opened at claude.ai showed a second sign-in beside claude's own.
Read with claude 2.1.302's output on a pipe and its keyboard a terminal:
it starts, opens its link and prints the sign-in screens with no line
wrapped. So a Windows shell now runs claude in the same window with its
output on a pipe through the mask, and the token is caught as behind a
pseudo-terminal, with no copying; the profile opens on a blank page. The
owner asked to keep a copy of each token to show again later and chose
Windows Credential Manager on a card; the session's permission check
refused writing that code, so it waits on the owner. The list of slots now
keeps its order, which the bench deals jobs in (coordbench's plan.py, one
job to each slot in turn), and `order`, `profiles` and `forget` came with
it.

Not measured, since no session runs Windows or a real browser: whether
claude's keyboard works in a Windows console while its output is piped;
whether Chrome on Windows sends claude's link to the profile just opened, as it
sends external links to the profile used last; whether Chrome makes a new profile for a --profile-directory folder that
does not exist yet, as it is documented to; and the callback from a
Windows browser into WSL, which depends on WSL's localhost forwarding.
The owner's first run on Windows is the test.

## The copy in Credential Manager and the benchmarks (2026-10-17)

The owner's first Windows run stored slot 1 (runners) and
CLAUDE_CODE_OAUTH_TOKEN on the organization, seen by symphony-template,
renew by 2027-10-17. Asked to get a token back on demand, the owner chose
on a decision card to keep a copy in Windows Credential Manager, and then
said in their own words to build it and the show command. The copy is
written through advapi32's CredWriteW from ctypes (no new dependency), a
generic credential with CRED_PERSIST_LOCAL_MACHINE, so it never roams to
another machine with the Windows profile, and the value in UTF-16, as
cmdkey and PowerShell write one. The structure's layout is tested against
Windows' 64-bit CREDENTIALW (80 bytes, the blob pointer at 40, UserName
at 72), and the calls against a fake advapi32; no Windows machine ran it
in this thread, so the owner's next run is the test. A copy that fails
costs only the copy, since it is written after the secret is stored.

The same message asked that the benchmarks get these tokens. coordbench's
bench.yml reads SYMPHONY_CLAUDE_<slot> for the slots in its "accounts"
input, else SYMPHONY_CLAUDE_ACCOUNTS, and its plan job refuses a slot
whose secret is unset or unseen; it never reads CLAUDE_CODE_OAUTH_TOKEN.
The status showed slot 1 seen by symphony-template alone, so coordbench
could not use it. `share` adds repositories to the selected lists of
every slot, label and the list through the organization's
secrets/{name}/repositories/{id} endpoint, with no new sign-in. flowbench's
pilot runs inside a cloud session on that session's subscription and
reads no secret; a later benchmark run in Actions, such as the standalone
agents the grant's figures need, reads the slots the same way.

## Open items

- tools/crowd_check.py's SECRET_NAMES does not name SYMPHONY_CLAUDE_1 to
  8, so an organization pool secret that reaches a crowd repository would
  pass the crowd check; the wizard refuses to put one there, the by-hand
  path does not. A pull request of its own, with ci.yml's values job
  naming the eight.
- An environment's own secret or variable outranks the repository's and
  the organization's, and `status` reads no environment; none of the
  repositories uses one for the slots yet (the bench's environment named
  bench is not built).
- Nothing warns a year later: `status` says "renew soon" and "renew now",
  and only when run. A scheduled workflow could list the secrets' dates
  on GITHUB_TOKEN and open an issue; not built.
- No page of claude.ai or of Claude Code's documentation that revokes a
  setup-token token on its own is known: the documentation says the
  command saves the token nowhere, and that /logout removes and revokes
  the credential a sign-in wrote. The page says deleting the secret does
  not revoke the token.
- The real sign-in through the wizard has not been run end to end, since
  no session may hold a credential: the owner's first run is the test,
  and a token claude prints in a form the masker does not know would
  reach the screen as claude prints it, which the page says. Whether the
  renderer wraps at the 400-column window the wizard gives it is
  inferred from Node reading the terminal's size; the cut-token refusal
  and the length floor stand behind that inference. Python's getpass
  under Git Bash's own window (mintty) may hang or echo; the page says to
  use winpty or another terminal there, unverified here.
