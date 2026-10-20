# The token wizard's checks: probes, fuzz and mutants

Kept from the thread "Claude token setup wizard", 2026-10-16, when the
owner asked that every piece of work, intermediate or final, be in git
before the threads move to another account. These are the scripts the
thread and its reviewers ran against scripts/tokens.py while building it
(symphony-template#100 and #105); what they found and what changed for it
is in [../token-wizard.md](../token-wizard.md), under the two review
passes and "After the merge". No Claude Doc, artifact or upload lies
behind them. No script holds a token: every stand-in token is built from
pieces, and none signs in.

## How to run one

Each script takes one argument, the tree of the commit it was written
against, and reads this repository's own tree when given none:

    mkdir /tmp/wizard-c157d99
    git archive c157d99 | tar -x -C /tmp/wizard-c157d99
    python3 -I docs/research/token-wizard-checks/first_review_masker_probe.py /tmp/wizard-c157d99

Against a later commit a probe may fail where the wizard's functions
changed shape; that is the history, not a fault. gh is always a stand-in
(the tests' tests/fake_gh.py or a class in the script), so no call
reaches GitHub.

## The scripts

| Script | Commit | What it showed there |
| --- | --- | --- |
| prototype_capture.py, prototype_fake_claude.py | none, 2026-10-15 | The first capture behind a pseudo-terminal, against the fake only: the token masked twice and found once, the code typed reaching the child, the 500-column window seen. |
| real_claude_screen_probe.py | c157d99 | The real claude setup-token's first screen, stopped by its process id after eight seconds, before any sign-in; what it showed for Claude Code 2.1.301 is in token-wizard.md. It needs claude on PATH. |
| first_review_masker_probe.py | c157d99 | Case D: a token followed by more than 400 token characters in pieces reached the screen; case F: a token wrapped at 60 columns was captured as 60 characters with the rest shown. |
| first_review_renderer_probe.py | c157d99 | The placed-words frame masked at every chunk size from 1 to 59, 100 and 4096, and a token line repainted five times. |
| first_review_mint_probe.py | c157d99 | A token printed last with no newline captured and masked; bracketed paste left on. |
| first_review_logic_probe.py | c157d99 | admin:org_hook passed the scope check, a listing with an inactive account first was refused, --repo with --repos failed only after a gh call, and --repos was dropped beside --visibility all. |
| first_review_getpass_probe.py | none | Run by hand in a window to see whether Python's hidden prompt hides; prints only the length typed. |
| second_review_masker_probe.py | 5a65e4f | A wrap leaving fewer than 20 characters, or a rest after blanks or a terminal code, was stored as the token; the over-limit run gave the wrong words; a long word after the token read as a cut. |
| second_review_mint_pty_probe.py | 5a65e4f | On a pseudo-terminal the modes come back, the reset follows the last mask, and no key typed after claude ended is left for the next question. |
| second_review_options_process_probe.py | 5a65e4f | Each pairing of options as a process from scratch clones: the ones that need no gh exit 2 with no call. |
| wrap_fuzz.py | 2b289d9 and every commit since | Every width from 20 to 419 columns, three token lengths, both forms, four chunk sizes (9,600 runs): no wrong token stored, nothing refused at 400 columns or wider. |
| followup_review_parity.py | 41c6545 | The wizard read 01,02, 1,2,9, 1,2,junk and a superscript two as slots and left them, where the bench refuses each. |
| followup_review_paths.py | 41c6545 | A failed read was printed and status went on; a repository's own list with terminal codes printed only its slots; hand-made labels printed their codes. |
| followup_review_mutate.py | 41c6545 | Three mutants survived (the raw value printed, no try around the read, a failure that stops status). |
| followup_second_review_closing_status.py | 37142b0 | The closing status showed the list as it was before the run wrote it: "not set" on the owner's first run. |
| followup_second_review_count_calls.py | 37142b0 | One status made 23 gh calls where 13 would do. |
| followup_second_review_mutate.py | 37142b0 | Five new behaviours had no test. |
| run_mutants.py | 3675c99, main's scripts/tokens.py | The base passes and all sixteen mutants of the follow-up fail the tests. |

Run again in their committed form on 2026-10-17, from this folder on main
as of 172520d with Python 3.12: wrap_fuzz.py printed "bad: 0" (6,404 stored
right, 3,196 refused), and run_mutants.py passed the base and caught all
sixteen mutants.

## What was left out, and why

- The thread's patch scripts and diffs, the check logs and the pull
  request bodies: their results are the commits of #100 and #105 and the
  pull requests themselves.
- Two probes of the second pass: an in-process options probe whose patch
  of ROOT did not reach the origin's reading (a default argument), so the
  process version above replaced it; and a mint probe that typed the code
  before mint() and hung, since tty.setraw flushes keys typed before it,
  so the typed-ahead probe above replaced it.
- A first screen probe that stopped every claude setup-token on the
  machine by name; the one above stops its own child by process id.
- The reviewers' reports, which are tool output; their findings are
  written in token-wizard.md.
- Third-party copies, fetched again by their links when needed: gh
  2.89.0's source from https://raw.githubusercontent.com/cli/cli/v2.89.0/
  (pkg/cmd/auth/status/status.go, pkg/cmd/secret/set/set.go and http.go,
  pkg/cmd/secret/list/list.go, pkg/cmd/variable/set/set.go and http.go,
  pkg/cmd/variable/list/list.go, internal/config/config.go and
  auth_config.go); Claude Code's https://code.claude.com/docs/en/authentication.md
  and https://code.claude.com/docs/en/github-actions.md; GitHub's
  documentation from the github/docs repository's content files on
  raw.githubusercontent.com (secrets, variables and their precedence);
  coordbench's bench/cooperbench/actions/plan.py; and the strings of the
  claude binary, read with strings(1).
