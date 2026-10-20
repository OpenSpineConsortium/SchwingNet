python3 scripts/tokens.py stores each Claude account's subscription token as an Actions secret without the token ever being shown or written anywhere; it is pasted only at a hidden prompt, where no terminal can run claude.

A Claude run in Actions needs a subscription token, and there is one per
account: CLAUDE_CODE_OAUTH_TOKEN for @claude, the workers in Actions and
the coordinator workflow, and the pool SYMPHONY_CLAUDE_1 to
SYMPHONY_CLAUDE_8, one account each, with the slots in use in the
variable SYMPHONY_CLAUDE_ACCOUNTS, for a benchmark in Actions
(OpenSpineConsortium/coordbench's bench.yml). By hand each goes from
`claude setup-token` through a clipboard into a settings page. The wizard
runs `claude setup-token` behind a pseudo-terminal of its own, so the
browser sign-in and the keyboard go through, masks the token out of what
claude prints before it reaches the screen, and hands it to `gh secret
set` on a pipe, which encrypts it on the machine; then it reads GitHub's
listing back by name and date, keeps the list of slots equal to the slots
whose secret exists, and takes an optional label per slot, the variable
SYMPHONY_CLAUDE_<slot>_LABEL, so status can say which account is which.
An API key is refused on sight, a crowd repository is refused, a token
cut over two lines is refused rather than stored, and a Windows shell or
a machine without claude takes `add --paste` or `main --paste`, a hidden
prompt. Everything that can fail is tried before the sign-in, since a
token minted and not stored is lost with the process: that each
repository named is visible to the login, each secret's scope, and that
gh's token carries admin:org, which an organization's secrets need. A
repository's own SYMPHONY_CLAUDE_ACCOUNTS hides the organization's list
the wizard keeps, so none is made by hand; status names one, with the
page to delete it on, and reads the list as the bench does, only the
words 1 to 8. Each slot's sign-in can open in a browser profile of its own: claude opens its link with the program BROWSER names, so the wizard hands it a launcher for the one run, and remembers the profile and the slot's cswap account number in tokens.json in the user's settings folder; cswap's logins are never reused, since they rotate and are full logins. On Windows each token stored is also kept in Credential Manager under symphony/<place>/<secret>, which `show N|main [--copy]` reads back (the owner chose it, 2026-10-17); `share REPO,REPO` adds a benchmark's repository to the slots' selected lists, since the bench reads only SYMPHONY_CLAUDE_<slot>, never CLAUDE_CODE_OAUTH_TOKEN. docs/setup/claude-tokens.md is the page, with the by-hand links;
tests/test_tokens.py proves the token never reaches the screen at any
chunk size. From symphony-template's token wizard thread, 2026-10-16.
It also runs from the browser alone in a GitHub Codespace on the
repository (.devcontainer/devcontainer.json, scripts/codespace.sh, docs/setup/codespace.md,
2026-10-18): the Codespace's GITHUB_TOKEN cannot set settings or secrets, so gh
signs in again as the person with a one-time code, then setup-repo.sh and the
wizard run; the sign-in's return to claude in a browser Codespace is not yet measured.
The Tokens page's Add a Claude account mints on an Actions runner instead
(.github/workflows/token.yml, tools/token_run.py, 2026-10-18), since a
Codespace took minutes to start: the run posts claude's sign-in link on an
issue the page opened, takes the code claude.ai shows from the person's
own comment, and posts the token only as a sealed box for the secrets
public key the page gave (tools/sealbox.py, standard library, held to
libsodium by tests/test_sealbox.py), which the page stores as the slot.
