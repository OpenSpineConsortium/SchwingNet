# spine-program student onboarding

Oct 13, 2026 - @Someone

## What you are joining

You will work on spine-program, one private GitHub repository (OpenSpineConsortium/spine-program) that holds Greg's spine imaging research as 13 numbered project folders, and you will do the work through Claude, one task at a time. Each folder is self-contained: its own CLAUDE.md (the working context Claude reads), README.md, DATA.md (where the data is on the grid), TODO.md, STATUS.md and MEMORY.md. Nothing in the repository is imaging data; the data lives on the Wayne State grid.

Work is organised as GitHub issues. Every issue names its folder in its title, for example "Task: 04\_openspinetoolkit, CT-1, fix the canal-closing regression". A board (the file STATE.md on the branch named board, rewritten automatically) shows which issues are free, which are claimed and by whom. You take one issue, Claude claims it for you, does the work on a branch of its own, and finishes with a pull request that Greg merges. You never edit the main branch and never merge.

| Folder | What it is | Who works it |
| --- | --- | --- |
| 03\_ctspinopelvic1k\_dataset | CTSpinoPelvic1K release v11, the dataset article, Zenodo and Hugging Face | student |
| 04\_openspinetoolkit | OpenSpineToolkit's v11 defects and their one-hour tests; blocks 05 | student |
| 05\_ct\_morphometry\_parity | the spinopelvic estimator, the level atlas, 3-D to 2-D parity | student |
| 06\_transitional\_ct\_census | the harvest over 21,622 CTs, the registry, the review tree | student |
| 10\_data\_platform\_grid | 211 data sources, the Ceph migration, identity and leakage, grid rules | student |
| 11\_students\_grid\_access | Beethoven, onboarding, the lab recipe | mixed |
| 12\_website\_pacs\_demo | the public site, the PACS demo, the level-service client | student |
| 01, 02, 07, 08, 09, 99 | the C-arm path, the transitional truth file, plain films, renders, the clinical QI paper, the archive | Greg first |

You may read every folder. "Greg first" governs who takes an issue there, not who reads: an issue labelled greg-first, or in a Greg-first folder, is yours only after Greg hands it to you with a comment on the issue naming you, or by removing the label.

## Accounts you need

Five things, all free except Claude. Ask for the grid account first, since it takes the longest.

| What | Who provides it | What you do | Cost |
| --- | --- | --- | --- |
| GitHub account with Write on OpenSpineConsortium/spine-program | Greg invites your GitHub login | Make a GitHub account if you have none, send Greg the login, accept the invitation e-mail | Free |
| Claude Pro or Max | You | Subscribe at claude.ai with your own account; Claude Code is not in the Free plan | Pro about US$20 a month, paid by you |
| Wayne State grid account | Wayne State C&IT | Request it at tech.wayne.edu/kb/high-performance-computing, naming Gregory Schwing as sponsor; about two business days; questions to hpc@wayne.edu | Free |
| The grid's sign-in code (Google Authenticator) | You, once | Install Google Authenticator on your phone, connect GlobalProtect (protect.wayne.edu) once, open ondemand.grid.wayne.edu, Interactive Apps, 2FA Setup, scan the code. Beethoven walks you through it too | Free |
| Beethoven invitation and grid approval | Greg | Send Greg the Google address your Chrome is signed in to; Greg adds it to the testers group and adds your AccessID to the lab volume's access list | Free |

Two authenticator apps will be on your phone: Google Authenticator holds the grid's code, Microsoft Authenticator approves every other Wayne State sign-in, GlobalProtect included. Data credentials (VinDr-SpineXR, BUU-LSPINE, PhysioNet) are needed only by tasks that say so, and the issue tells you where to ask.

## Set up your Claude Project (once)

A Project is your own front door to the repository: every thread you open in it starts from a fresh clone of main and reads the repository's rules, board and memory from the clone. It takes about five minutes once the GitHub invitation is accepted.

1. Sign in at https://claude.ai/code with your Claude Pro or Max account and create a Project. Call it spine-program.
2. Connect your GitHub account when asked, then add OpenSpineConsortium/spine-program as the Project's only repository. The Claude GitHub App is already installed on it.
3. Leave the Project's instructions, description and memory blank. Everything Claude needs is in the repository, so nothing you type there can drift from what Greg's own threads read.
4. Where the Project's settings offer plugins, add symphony from symphony-marketplace. If they do not, start each thread by typing /board.
5. Open a first thread and type /board. The board that prints is the live state of the repository: the Queue, the claims, the pull requests and the overlaps.

A Project belongs to one account and cannot be shared, so you and Greg each have your own; the repository is the one thing you share, and both sides see the same issues, branches and pull requests.

If you would rather work from your own computer: clone the repository, open its top folder in Claude Code, run `claude plugin install symphony@symphony-marketplace --scope project` once, then use /board and /claim the same way. On Windows, `python3 --version` must print a version in Git Bash, or the plugin's push guard silently does nothing.

## Set up the grid and Beethoven (once)

Beethoven is a Chrome extension that starts a Claude Code worker in your own grid account, as a Slurm job, and opens it in claude.ai. It is how your Claude reaches the data. The first time takes about ten minutes plus the wait for a compute node; the full guides are 11\_students\_grid\_access/docs/beethoven/guides/INSTALL.md and USE.md in the repository.

1. Wait for the grid account (section 2) and for Greg's note that your AccessID is on the lab volume's access list. Without that entry every lab path answers Permission denied.
2. Set up the grid's sign-in code if you have none: GlobalProtect on, ondemand.grid.wayne.edu, Interactive Apps, 2FA Setup, scan into Google Authenticator. Beethoven's panel offers the same steps.
3. Open the Beethoven invitation in Chrome, signed in to the Google account it was sent to, and click Add to Chrome, then Add extension. Pin it with the puzzle icon.
4. On the welcome page read the terms, tick the box and click Agree and continue. When the panel says One small download, once, install the helper for your system (no administrator needed; your computer warns once because it is unsigned, which is expected). If your computer refuses it, click Use GlobalProtect instead.
5. Sign in to the grid in the panel: your AccessID, your password, then the six-digit code from Google Authenticator (not Microsoft Authenticator). The panel says This computer is set up.
6. Read Where your work goes, tick the box and click Connect. A Claude tab opens: sign in with your own Claude account, approve, and paste the code it shows into the panel.
7. The panel says In line for a computer, then You're online. Click Open my session. That session is Claude Code running on a compute node in your account.

Every later day is two clicks: open Beethoven, click Connect or Open my session. If a panel state looks wrong (stuck on Connecting to Claude, or the grid didn't accept the code), the panel may be wrong and the grid right: open More, Copy debug log, and send it to Greg rather than retrying many times, since three refused codes lock you out for fifteen minutes.

## Every task

One issue at a time, claimed by Claude in a thread of your Project, finished as a pull request that Greg merges. Each issue's title names the folder it belongs to, and that folder's CLAUDE.md, README.md, DATA.md, TODO.md and STATUS.md are what Claude reads before changing anything.

1. Open a new thread in your Project and type /board. Pick from the Queue an issue labelled todo that the board shows unclaimed, in one of the student folders (03, 04, 05, 06, 10, 12), and not labelled greg-first. An issue the board's Given to workers section names you on comes first. A folder marked Greg-only is yours only after Greg hands the issue out with a comment naming your login.
2. Paste this prompt, with the issue number in place of N and your GitHub login in place of login:

```
Claim issue N with the claim skill and carry it to a ready pull request, as docs/agents/PROTOCOL.md says; work on the branch claude/N, not this session's own branch. If the push of claude/N is refused, another session holds the issue: say so in one line and stop. Do not merge.
gh issue and gh pr are refused here, so add the labels, post the plan and open the draft pull request with your GitHub tools or gh api (repos/OpenSpineConsortium/spine-program/issues/N/labels, repos/OpenSpineConsortium/spine-program/issues/N/comments, repos/OpenSpineConsortium/spine-program/pulls). Mark the pull request ready with your GitHub tool update_pull_request (draft false), not gh api, which cannot change a draft; if you have no such tool, say so and stop before you delete the claim file.
My worker name is my GitHub login, login: the label worker:login and the claim file's Worker line.
```

3. Claude pushes the branch claude/N with a claim file (that push is the claim; if the name is taken, someone else has the issue), labels the issue claimed and worker:login, posts the plan on the issue, and opens a draft pull request that says Closes #N. Then it works, pushing as it goes.
4. Read what Claude reports, answer its questions in the thread, and ask it to check anything that looks too neat. The work starts from the issue's acceptance lines, not from TODO.md step 1.
5. When the work is done Claude deletes the claim file, marks the pull request ready and labels the issue in-review. Greg merges, and the merge closes the issue. If the board comments main moved on the pull request, tell Claude to bring main in.

Push at least once a day while you hold an issue: a branch with no commit for 24 hours is released by the board's own run, and the issue goes back to the Queue. If you are stopping for longer, say so on the issue. No research happens without an issue; if a TODO step has none, ask Greg to open one.

Each folder's results, figures, manuscripts and regulatory folders are not in the repository since 2026-10-13: they live on the grid under /rs/rs\_grp\_oschome/shared/spine-program/archive/, and the repository holds a link to them in each folder. In a Beethoven session the link opens; in a Project thread Claude reads such a file from git history, and a task that must change one brings it back into the branch first. ARCHIVE.md at the repository's root says how.

## Tasks that need the grid

A Project thread has the clone and GitHub and nothing else: no grid, no ssh, no sbatch. So a task that touches data runs in two places, the Project thread for the plan, the job script and the pull request, and your Beethoven session for the jobs. Until issue 19 settles whether the grid can reach GitHub, files travel between them through a clone on your own computer.

1. In the Project thread, paste this prompt in place of the first line of the usual one, followed by the same two lines:

```
Claim issue N with the claim skill, write the plan, the job script and the draft pull request, then stop at the first step that needs the grid or another repository and say exactly what to run where. Do not merge.
```

2. On your computer, in a POSIX shell (Git Bash, WSL, macOS or Linux Terminal; never PowerShell, which breaks the stream), check out the branch claude/N and ship only the paths the issue needs to a folder of yours on the lab volume. The folder must exist and must not be under your hpcworker folder, which the framework empties:

```
git fetch origin claude/N && git checkout claude/N
ssh grid 'mkdir -p /rs/rs_grp_oschome/<AccessID>/work/N'
git archive HEAD <paths> | ssh grid 'tar -x -C /rs/rs_grp_oschome/<AccessID>/work/N'
ssh grid "echo $(git rev-parse HEAD) >> /rs/rs_grp_oschome/<AccessID>/work/N/SHIPPED_COMMITS.txt"
```

3. In your Beethoven session, tell Claude where the files are and what the thread said to run. It submits the job with sbatch from that folder (sbatch -D, partition reqp with qos requeue, the shared python at /rs/rs\_grp\_oschome/go2432/envs/spineps212 unless the issue says otherwise), writes the job id and an estimated finish time, and stops. Nothing runs on the login node: every computation, render, plot and download is a job, even a one-minute one.
4. When the job ends, Claude in the Beethoven session reads the output and the summary files. Large outputs stay on the lab volume; small results (a table, a count, a log excerpt) go back to the branch through your clone, each number with the path of the file it came from, and the job ids go in the pull request.
5. Back in the Project thread, give Claude the results and let it finish the pull request.

What stays private stays on the grid or in this repository: ship only what the issue needs, and nothing of the lab's data or code goes anywhere public.

## Your first task: issue 19

Issue 19 (https://github.com/OpenSpineConsortium/spine-program/issues/19) measures whether the grid can reach GitHub and whether git survives on the login node. It is the right first task because it needs no data, exercises every piece of the setup above, and its answer decides whether your later tasks need the laptop step at all: if a compute node can read this repository with your token, a Beethoven session can clone spine-program and run the whole protocol on the grid in one place.

1. Make a fine-grained personal access token on your own GitHub account (Settings, Developer settings, Fine-grained tokens) with read access to Contents on OpenSpineConsortium/spine-program only. In your Beethoven session, save it as one line in $HOME/.beethoven/github\_token with mode 600. It never goes on a command line, into a job's --export, into a log or into any file of the repository.
2. In a Project thread, claim issue 19 with the grid prompt from the previous section. Claude writes the plan, the job script and the draft pull request, then stops and tells you what to run where.
3. Ship the job script to a folder of yours on the lab volume with the git archive line, or save it there from the Beethoven session with an editor (never a heredoc).
4. In the Beethoven session, submit the ten-minute job and, by hand, run the two login-node commands the issue names in that order, stopping if the first is killed. Record each outcome as completed, or killed with the message.
5. Bring the exit codes, the job id and the first lines of output back to the Project thread. Claude writes them into STATUS.md section D with values withheld (no hostname, AccessID or token value), updates the files the issue's acceptance lines name, and opens the follow-on issue if the token read worked.

The issue runs under your account, never Greg's, and the AccessID is withheld in everything written back.

## Rules that matter

The repository's root CLAUDE.md carries twelve standing rules and each folder's CLAUDE.md restates them with its own traps; Claude reads them in every thread. The ones that most often catch a new person:

- One issue at a time, one branch claude/N, one pull request. Never push to main or to another worker's branch; Greg merges.
- Every number, date and path names the file it came from. What no file records is written "not recorded", never guessed.
- Check against something outside the computation. The recurring failure here is a number that is wrong but plausible; render the mask, compare with a published value, test a tidy explanation before believing it.
- Nothing runs on the login node. Every computation is an sbatch job; record a job before cancelling it.
- No token, password or key on a command line, in a job file, in a log or in any file of the repository. Tokens are read from files with mode 600.
- No student name, username or personal e-mail in any file of the repository. Your GitHub login on the worker label and the claim file is working metadata and is fine.
- Nothing from the lab's private code or data goes public, and nothing from the private repositories is quoted in a talk or upload without Greg's word.
- Two vertebra label schemes exist and mixing them raises no error; call the toolkit's labels\_for, never a fixed map. Held out means never seen by the model or any ancestor.
- Never the French-derived word for where data came from; write origin, lineage or source. Version numbers are whole integers.

Where the long form lives, all in the repository:

| Topic | File |
| --- | --- |
| The standing rules and the map of the thirteen folders | CLAUDE.md |
| How work is claimed, released and finished | docs/agents/PROTOCOL.md |
| How a student starts, the prompts, choosing a folder | README.md, section How a student starts |
| The grid, the shared python, how code reaches the worker | 11\_students\_grid\_access/STUDENT\_ENV.md |
| Installing and using Beethoven | 11\_students\_grid\_access/docs/beethoven/guides/INSTALL.md and USE.md |
| The lab method a student's work follows | 11\_students\_grid\_access/code/student\_projects\_3f1cf04/RECIPE.md |
| Each folder's goal, data paths, ordered steps and results | the folder's CLAUDE.md, README.md, DATA.md, TODO.md, STATUS.md |

When something is unclear, ask on the issue; a question on the issue is part of the work and nothing is lost by asking.
