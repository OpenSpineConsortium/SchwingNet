@claude runs in Actions draw on the main account's subscription token, never an API key.

The workflow .github/workflows/claude.yml answers @claude mentions on
issues, pull requests and reviews with a Claude Code session. It
authenticates with the repository secret CLAUDE_CODE_OAUTH_TOKEN, a
subscription OAuth token the main account makes with `claude setup-token`
(docs/setup/claude-action.md): runs spend that account's plan limits, the
five-hour window and the weekly limit, and bill no API. Until the secret
is set the workflow does nothing, quietly. The token is the one secret
beyond the coordinator trigger pair that the repository ever asks for,
and it lives in the repository's Actions settings, never in a file. In
crowd mode (crowd-mode.md) the repository holds no such token and the
job never starts: its condition needs the variable CLAUDE_CROWD not to be
true.

Source: the Claude Code documentation on GitHub Actions and
authentication (code.claude.com/docs), read 2026-10-09.
