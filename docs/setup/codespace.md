# Setting up from the browser: a Codespace

The two setup steps that needed a computer of your own, the repository's
GitHub settings (scripts/setup-repo.sh) and the Claude tokens the workflows
run on (scripts/tokens.py), also run in a GitHub Codespace, so that the
whole setup happens in browser tabs: no install, no terminal of your own and
no token copied by hand. .devcontainer/devcontainer.json makes the
Codespace, and scripts/codespace.sh is what runs in it.

## The steps

1. Open https://codespaces.new/OWNER/NAME, with your repository's owner and
   name, and press **Create codespace**. The control panel's Tokens page
   links it for the repository it shows.
2. Wait for the Codespace to open. It opens as one terminal, whose profile
   (set in .devcontainer/) starts the setup by itself the first time; if
   VS Code asks whether you trust the folder, press **Trust**, since the
   terminal cannot run until you do. If the setup does not start, type
   `bash scripts/codespace.sh` and press Enter.
3. Sign in to GitHub when asked: gh shows a one-time code and opens
   github.com/login/device in a new tab; paste the code there and press
   **Authorize**. The Codespace's own token cannot change settings or
   secrets, so this sign-in is yours, and it stays in this Codespace only.
4. The settings come next by themselves (the ruleset, auto-merge, the
   labels, secret scanning), on the repository the Codespace is on, which
   GitHub names in GITHUB_REPOSITORY.
5. Then the token wizard: it asks for a slot, a label and whether the same
   token is also `main`; then `claude setup-token` opens claude.ai's
   sign-in in a new tab. Sign in as the account the slot is for and press
   **Authorize**; where claude.ai shows a code instead, paste it into the
   terminal. The token goes straight from claude to GitHub, sealed, and is
   never on the screen. A repository of an organization keeps the tokens as
   the organization's secrets, seen by this repository.
6. When you are done, delete the Codespace at https://github.com/codespaces
   (the three dots beside it, then **Delete**), which also drops the GitHub
   sign-in it held.

## One button: the Tokens page

The Tokens page's Add a Claude account no longer uses a Codespace: it mints
the token on an Actions runner in about a minute (docs/setup/claude-tokens.md,
Add a Claude account, from the page). What follows is the Codespace route it
replaced, which the token devcontainer still serves.

The control panel's Tokens page has "Add with one press", which does the
token part of the above for one account, with nothing to type:

1. The page saves one of your Codespaces secrets, SYMPHONY_GITHUB_HANDOVER,
   which only your own Codespaces on this repository see: the page's own
   GitHub sign-in, sealed in the browser, so the Codespace needs no GitHub
   code of its own.
2. It creates a Codespace on the repository with
   .devcontainer/token/devcontainer.json, which sets SYMPHONY_SETUP=token,
   and opens it in a new tab.
3. The setup task runs `scripts/tokens.py add` for the next free slot with
   that sign-in: claude.ai's sign-in opens in another tab, and you press
   **Authorize** as the account for the slot. The Claude token goes from
   claude to GitHub through gh and is never shown.
4. The page watches the organization's slots; once a new one appears it says
   so and deletes the Codespaces secret and the Codespace. A label, or
   renewing a set slot, stays with "Seal and save the slot" or the full
   setup.

It needs the SymphonyBoard App's account permission Codespaces user secrets
and its repository permission Codespaces, both read and write. Without the
first, the Codespace asks for a one-time GitHub code instead (paste it on
github.com/login/device and press **Authorize**); without the second, the
page opens GitHub's own Codespace page for the repository, where one more
press makes it. A sign-in made with Sign in with GitHub lasts eight hours
whether or not its deletion succeeds; a pasted token lasts as long as you
made it for, and a secret left behind is deleted at
https://github.com/settings/codespaces.

## What it costs and where it runs

A Codespace on a repository of your personal account runs on your account's
free monthly Codespaces hours. On an organization's repository the
organization pays, and only once an owner allows Codespaces for its members
at https://github.com/organizations/ORG/settings/codespaces. The setup takes
minutes on the smallest machine, two cores.

The Codespace starts from GitHub's default image
(mcr.microsoft.com/devcontainers/universal:linux) with no features added, since
GitHub keeps that image on its hosts and stores it free of charge, while an
image with features is built at every start. The image already holds
Python, Node and gh; only Claude Code is installed, once, when the Codespace
is made. No terminal can be shown inside the control panel's own page:
GitHub reaches a Codespace's terminal only through its editor or ssh, and
showing it elsewhere would need a server of ours.

## What is not measured yet

Whether claude.ai's sign-in hands its answer back to `claude setup-token`
in a Codespace opened in the browser, or shows a code to paste, has not
been tried from a cloud session, which cannot open a Codespace; step 5
covers both. The Tokens page's "Add or renew a slot" stays the way to store
a token printed anywhere else.
