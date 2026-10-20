# Writing

- Plain prose that says why, in comments, commit messages, pull requests and documents alike. What the code does is read from the code.
- Short functions; names that read as English.
- No emoji in code, output or documents. ASCII and LF in everything under .claude/, docs/, tools/ and .github/; prefer ASCII elsewhere.
- No new dependencies: Python 3.12 or later with its standard library, plain bash, and GitHub's own actions and anthropics/claude-code-action, pinned to a major tag. A proposal to add one is an issue first.
- Nothing refers to a file that does not exist.
- In conversation, put a fact worth keeping on its own line tagged `Decision:` or `Constraint:`, so the checkpoint skill and `cswap checkpoint write` keep it word for word; the rest of a session is inferred and may be lost.
