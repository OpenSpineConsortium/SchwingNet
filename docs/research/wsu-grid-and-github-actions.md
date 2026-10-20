# The WSU grid and GitHub Actions

What was measured and weighed before Symphony's GitHub Actions were made to run on Wayne State's
grid through Beethoven, and what was built. Written 2026-10-16 in the owner's thread "Symphony on
the WSU grid", from the owner's question of 2026-10-15 23:35 UTC, item 10 of that day's handoff:
"Can I use beethoven to connect my Github actions to the WSU grid and then send results/logs back
to connect Symphony to the WSU grid using Beethoven?", and the owner's note of 23:54 UTC that an
ssh key in a GitHub environment secret could connect to the grid, "especially if the wsu user and
pass was also stored". The owner decided on 2026-10-16 at 00:24 UTC, on the card that put the two
directions side by side: both, the runner on the grid first, then the ssh gate as a second pull
request. Every claim below names what it rests on; what the grid has not yet shown is said so.
The pull requests, both merged on 2026-10-16: OpenSpineConsortium/hpcworker#13, the runner
(tools/grid_runner.sh and its tests; merge d8a03e7), and OpenSpineConsortium/symphony-template#103,
the workflow, docs/setup/grid.md and this note (merge d669562). Where the work stands, what waits on
the owner, the plan for the ssh gate and how the fixes were proven are the three sections before the
sources.

## The answer

Yes, with the connection pointing from the grid out. GitHub's own runners cannot sign in to the
grid, and no credential of the grid's may sit at GitHub nor one of GitHub's reach a workflow's job
beyond that job's own, so Beethoven does what its CI lane already does: a Slurm job on a compute node polls GitHub
over outbound HTTPS. The job serves GitHub's own self-hosted runner, inside GitHub's own runner
image, registered for one GitHub job at a time with a just-in-time credential that the account's gh
sign-in mints on the grid as the registration starts and that GitHub discards once the job has run.
A workflow job that names the runner's labels (`runs-on: [self-hosted, grid]`) then runs on the
node, and GitHub keeps its log and its artifacts as for any job: the results and logs come back the
way every Actions job's do, with nothing of Beethoven's in the workflow and no server of ours. The
runner chain outlives a wall time or a preemption because each job queues its successor first; it
stops registering a margin before its wall time, so a job cut off by the wall time, which GitHub
would report as a lost runner, cannot happen to a job that ends within the margin.

The other direction, GitHub pushing into the grid over ssh, is not first, and the password never
goes to GitHub: Wayne State's ssh and portal ask for a one-time code beside the password, so a
stored password alone does not get in; a key in a GitHub secret is a credential of the grid's at
GitHub, which every writer's workflow can read; and it would run commands on the login node, where
Beethoven's etiquette allows one scheduler call per action and nothing else. What it is good for,
a workflow step that queues one job or reads one file on the grid without a runner waiting in Slurm's
queue, is worth a narrow gate: a key on the grid that accepts one forced command and nothing else,
through hpcworker, used by a workflow from an environment secret, after the owner has tested that
key-only sign-in works from outside the VPN. That is the second pull request.

## What was measured, and where

The grid, from hpcworker's CLAUDE.md ("Grid") and docs/OPEN_QUESTIONS.md, and
framework/profiles/wayne.json:

- The login node, warrior, is CentOS 7 (bash 4.2, python 3.6), and its banner bans python3 among
  other programs ("terminated on sight"; hpcworker's framework/README.md, "The login node"), so a
  tool run there reads the site profile with the framework's awk reader; the compute nodes are EL7 on
  a 3.10 kernel; Apptainer 1.2.2 is at /wsu/el7/gnu7/apptainer/1.2.2/bin/apptainer behind the module
  apptainer/1.2.2. The worker's queue is reqp with the QoS requeue (preemptible); secp/secondary is
  for short allocations; gmsap and gvohp carry GPUs. The lab's volume is /rs/rs_grp_oschome (CephFS);
  $TMPDIR there is not node-local, so a job's temp goes under /tmp/$USER on the node, which is swept
  while jobs run; IPC goes under /dev/shm.
- The portal, https://ondemand.grid.wayne.edu, sits behind the university's VPN. The ssh port,
  grid.wayne.edu:22, answers from the internet (OpenSSH 7.4; publickey, password and
  keyboard-interactive offered), and a password sign-in there also asks for the Google
  Authenticator code; no sign-in from outside the VPN has been made with a password or a key
  (hpcworker's docs/V12_CONTRACT.md, "Facts", 2026-10-01 and 2026-10-02). Beethoven 12's own key
  gate, a forced command on one line of authorized_keys, is tested against OpenSSH and unproven on
  the grid (framework/README.md, "The browser's key"), and the lab lead's guide asks C&IT whether
  such a key, used from outside the VPN, is acceptable (docs/guides/LAB_LEAD.md); the answer is not
  on record.
- Egress was measured on 2026-09-28 from the compute node asx15: api.anthropic.com answered directly
  (no proxy), claude.ai answered 403 to curl. github.com was not tried from a compute node; the login
  node's clone of a private repository through gh was measured on 2026-10-03 (the CI lane's first
  open question, in docs/OPEN_QUESTIONS.md).
- Claude Code's Remote Control registered from an sbatch job on 2026-09-29 (job 40496445, asx15):
  a long-lived outbound connection from a batch job works there.
- The host's Slurm client runs inside a container on the nodes with the binds measured on asx1 on
  2026-09-28 (lib/adapters/common.sh, hpcw_slurm_in_container): /usr/bin under /opt/host/bin,
  /usr/lib64/slurm, the munge library and socket, /etc/slurm, and an /etc/passwd that adds the slurm
  and munge users. The worker uses them to queue its successor; the runner's container is given none
  of them (The two directions weighed, below).

GitHub's rules for self-hosted runners, read on 2026-10-16 from the github/docs repository's content
files, since docs.github.com is blocked from the cloud session (the paths are the pages'):

- A self-hosted runner should almost never be used for a public repository: a fork's pull request
  could run its code on the runner (actions/reference/security/secure-use.md, "Hardening for
  self-hosted runners").
- Just-in-time runners: the REST API creates an ephemeral runner that performs at most one job and
  is then removed from the repository automatically; the encoded configuration it returns is passed
  to the runner at startup, and reused hardware is to be cleaned between jobs (the same page, "Using
  just-in-time runners"). The endpoint is POST /repos/{owner}/{repo}/actions/runners/generate-jitconfig
  with name, runner_group_id, labels and work_folder; it needs repository administration (the REST
  reference for self-hosted runners). GitHub adds the labels self-hosted, linux and x64 itself.
- A job for a self-hosted runner can wait in the queue for 24 hours before it is cancelled
  (actions/reference/limits.md).
- A runner must be updated within 30 days of a new version when automatic updates are off; the
  runner updates itself otherwise (actions/reference/runners/self-hosted-runners.md).
- The runner application supports Red Hat Enterprise Linux 8 or later, CentOS 8 or later, Debian 10
  or later and Ubuntu 20.04 or later (the same page, "Supported architectures and operating systems"):
  not an EL7 node, hence the container.
- The runner's exit codes, from actions/runner's source (src/Runner.Common/Constants.cs, ReturnCode):
  1 terminated, 2 retryable error, 3 updating, 4 run-once updating, 0 success; an ephemeral runner
  exits after its one job (src/Runner.Listener/Runner.cs), and the configuration it holds is the
  files .runner, .credentials and .credentials_rsaparams in its folder
  (src/Runner.Listener/Configuration/ConfigurationManager.cs). Passing the encoded configuration on
  the command line, as the documented `./run.sh --jitconfig` does, puts a credential in argv, which
  Beethoven's rules forbid; the chain writes the three files itself, mode 0600, from gh's answer in a
  mode-0600 file on the node's disk.
- GitHub's runner image is ghcr.io/actions/actions-runner (actions/runner, images/Dockerfile): Ubuntu
  24.04 (.NET's runtime-deps:8.0-noble) with the runner, git, curl, jq, sudo, the docker client, the
  runner's own node and, since software-properties-common needs it, Ubuntu's python3. Its
  environment sets ACTIONS_RUNNER_PRINT_LOG_TO_STDOUT=1, which would copy the runner's whole trace
  into the chain's log (src/Runner.Common/HostContext.cs), so the chain sets it false. What else it
  carries is read from that file, not measured here.
- A runner told to update downloads the new version and exits with code 3 or 4 for a script to
  restart it (src/Runner.Listener/SelfUpdater.cs,
  src/Misc/layoutroot/run-helper.sh.template); inside a container that
  ends with the listener, and from an image that holds the old version, that cannot finish, so the
  chain stops with the reason and a person installs the new image. GitHub's page says a runner
  updates itself when a job is assigned to it once a new version is out, and that ephemeral runners
  in containers can update again on every release unless registered with config.sh's
  --disableupdate (actions/reference/runners/self-hosted-runners.md, "Runner software updates on
  self-hosted runners"), which generate-jitconfig does not take; how often it happens to the chain
  is not yet measured.

Apptainer: `--no-mount bind-paths`, which keeps the site's own bind paths (the home, the volume) out
of the container, exists since 1.2.0 (its CHANGELOG.md, v1.2.0 of 2023-07-18), so the grid's 1.2.2
has it; whether the site's configuration lets `--home` point at a folder on the node's disk is not
yet measured.

## The two directions weighed

GitHub pushes into the grid. A workflow step opens ssh to the login node with a key held as a
GitHub secret, and the WSU user and password beside it as the owner suggested. What it would give:
a step that runs a command on the grid with no runner waiting in Slurm's queue, from any workflow.
What it needs: a credential of the grid's at GitHub, readable by every writer's workflows
(docs/start/team.md takes the repository's secrets out before anyone else gets Write for the same
reason); a sign-in with no one-time code, since the ssh port answers from the internet but a
password sign-in also asks the Google Authenticator code, which a stored password does not supply,
and whether a key alone signs in from outside the VPN has never been tried; and C&IT's word on a key
used from outside the VPN, the question hpcworker's lab lead guide already asks for Beethoven's own. Beethoven's rules say never a credential on a command line,
in a job file or in a log, and nothing on the login node beyond one scheduler call per action, so
the only form of it that fits is the gate above: a key that may run one forced command, with the
password nowhere.

The grid pulls from GitHub. The CI lane's direction: a job on a compute node reads GitHub with the
account's own gh sign-in and posts back. For Actions, GitHub's own runner does the polling, and the
job's log, artifacts and status land where every job's do. What it needs: gh signed in on the grid
as an administrator of the repository, outbound HTTPS from compute nodes to github.com, api.github.com,
pipelines.actions.githubusercontent.com and ghcr.io, and a container for the runner. What it costs:
a chain of jobs on reqp/requeue, idle most of the time (one registration listening), the margin before
each wall time during which no new job starts, a job queued for up to 24 hours when the chain itself
waits in Slurm's queue, and a GitHub job lost when its chain job is preempted. What it rules out: a
public repository, and any step that needs the scheduler, the home or the lab volume, none of which
the container sees: a job a step queued as the account, or a bind of the home or the volume, would
give every workflow's code all the account holds, its gh sign-in and its Claude login among them. A
workflow that needs more than a small share of one node runs on a chain sized for it (--cpus, --mem,
--gres, a GPU given with --nv); a step that must queue a job or read a file on the grid waits for
the ssh gate, which does each through one forced command.

The decision, on the card of 2026-10-16 00:24 UTC: both, the runner first.

## What was built

In OpenSpineConsortium/hpcworker, merged as hpcworker#13: tools/grid_runner.sh
(--install, --start, --stop, --status on the login node; --pull and --serve inside the jobs),
tools/grid_runner_install.sbatch (one job that pulls the image as a SIF under
/rs/rs_grp_oschome/$USER/hpcworker-runner/image and runs the runner's --version inside it with the
chain's exact flags, so a flag the site refuses is seen there and never in a chain),
tools/grid_runner.sbatch (a chain's job: queue the successor, mint, listen, one GitHub job at a time,
until the margin or STOP), and tools/tests/test_grid_runner.sh with the stand-ins
tools/tests/shim/apptainer and tools/tests/shim/runner-listener beside the extended shim/gh and
shim/slurm: 189 checks against stand-ins (nothing reaches GitHub, a registry, a scheduler or the
grid), among them that no token and no registration ever leaves a job, that the job looks at the
runner once a minute and never faster, that every bind the container gets is on the node's own
disk or the test's folder, that no Apptainer setting of the shell's reaches the container, and that
the chain stops itself with the reason after three jobs in a row that could not serve, on a public
repository and when the runner asks for an update. An adversarial review before the pull requests
were marked ready found faults in the first version (the update and failure paths, the runner's
version read through Apptainer's own lines, Apptainer settings from the shell, --slurm, a fork's
pull request reaching grid.yml); each fix was checked by undoing it and seeing the tests fail. The README's paragraph "A GitHub Actions runner on the grid" and the
section of the same name in docs/OPEN_QUESTIONS.md describe it; CLAUDE.md there carries the rule.

In this repository, merged as #103: .github/workflows/grid.yml (one command, from the workflow's page or another
workflow, on `runs-on: [self-hosted, grid]`, only for an event that names a private repository that
is not a fork and never for a fork's pull request, Python 3.12 set up unless unticked, the output as
the job's log and the artifact grid-<run>-<attempt>, whose prefix a caller may change),
docs/setup/grid.md (how it works, what it takes, the owner's nine steps with their links), the memory fact "The grid runs a job through Beethoven", and this note.

## What is not yet measured

Nothing of it has run on the grid. hpcworker's docs/OPEN_QUESTIONS.md lists each question with the
first test that answers it; in short:

- compute nodes reaching ghcr.io (the image) and github.com, api.github.com and
  pipelines.actions.githubusercontent.com (the runner's long poll);
- `--no-mount bind-paths`, `--home` and `--cleanenv --containall` as the chain uses them, on the
  grid's Apptainer 1.2.2 and under the site's configuration;
- the runner, .NET 8 in an Ubuntu 24.04 image, on an EL7 node's 3.10 kernel;
- whether Slurm at Wayne State exports SLURM_JOB_END_TIME to a batch job (the job's clock; without
  it the margin is read from the start time and --hours);
- the chain: a successor queued from inside a job with `--dependency=afterany:<id>,singleton` on
  reqp/requeue, and a requeued job finding its successor instead of queuing a second;
- how long a GitHub job takes to start on the runner, and whether GitHub holds a job that arrives
  while no runner is online until the next registration;
- actions/setup-python and actions/checkout inside the runner's container on the grid, and the
  node's GPU given to it with --nv;
- how often GitHub asks a just-in-time runner to update, each time stopping the chain until --install
  and --start.

The install job is the first test of the first three; the first chain job and the first Run workflow
press answer the rest.

## Where it meets a Claude Code session on the grid

The owner's other thread of 2026-10-16, "Beethoven worker opening", is after a cloud-enabled Claude
Code session running on the grid worker itself, with Projects, cloud sessions and the grid's own
hardware, from one Beethoven session. The runner and that session meet in four places, and this
note says so, since both are built on the same account:

- The same gh sign-in: the runner's registrations and a session's own GitHub work use the account's
  one gh sign-in on the grid, under the owner's own login, which stays in the home, where the
  runner's container never looks. Nothing the runner writes is where a session reads: its registration lives in mode-0600 files on the node's disk inside the chain's
  job, and its chain folder on the volume holds STOP, status.json, the jobs' logs and a copy of the
  runner's own diagnostic logs when a run ended badly, no credential.
- The same queue: a chain job and a worker job both run on reqp/requeue and count against the
  account's job limits; a chain started with --cpus, --mem or --gres takes that from the same share.
  One chain per repository and account, and one GitHub job at a time on it.
- The same tools: tools/grid_runner.sh lives beside the worker's job template in hpcworker, reads the
  same site profile with the same awk reader (the runtime, the worker queue and the folder beside
  the account's state); a change to the reader or to those fields changes both.
- No Claude credential near the runner, by construction: a session's sign-in lives under $HOME
  (the profile's claude_config_dir), which the runner's container does not mount
  (`--containall --cleanenv --no-mount bind-paths`), and the chain's job files unset the agent
  markers and GITHUB_TOKEN before anything runs. A session on the grid may start, watch and stop a
  chain itself, since those are file work, gh, one squeue and one sbatch on the login node, the same
  calls the CI lane's watcher makes from a job; and a workflow job on the runner may in turn be what
  checks a session's push, since it runs the repository's own check on a node.

## Where it stands on 2026-10-16

Both pull requests are merged, and nothing of the runner has run on the grid yet. What runs it is
the owner's, since it runs under his grid account or changes what a session may not change, and
three steps wait on him, in this order:

1. hpcworker's CI runs the runner's tests only once a step names them, and a session may not change
   a workflow file there. The owner opens
   https://github.com/OpenSpineConsortium/hpcworker/edit/main/.github/workflows/ci.yml, pastes the
   two lines below right after the step that runs `bash tools/tests/test_grid_ci.sh`, indented like
   it, presses "Commit changes...", keeps "Commit directly to the main branch" and presses "Commit
   changes".

   ```yaml
         - name: the grid's Actions runner (tools/grid_runner.sh; Slurm, gh, Apptainer and the runner stood in for)
           run: bash tools/tests/test_grid_runner.sh
   ```

2. Start the runner and run one job: docs/setup/grid.md, steps 1 to 6. The install job is the first
   test of most of what hpcworker's docs/OPEN_QUESTIONS.md lists, and a line starting "STOP:" names
   what the grid refused.
3. The test the ssh gate waits on: whether a key alone signs in from outside the VPN. On his own
   machine, in WSL, `ssh-keygen -t ed25519 -f ~/.ssh/grid_gate_test -N '' -C grid-gate-test`, then
   `cat ~/.ssh/grid_gate_test.pub`. In the grid's shell (https://ondemand.grid.wayne.edu on the VPN,
   the Clusters menu, the shell entry),
   `printf '%s\n' 'restrict,command="echo key-only sign-in works" PASTE' >> ~/.ssh/authorized_keys`,
   with the printed line in place of PASTE. With the VPN off, in WSL,
   `ssh -i ~/.ssh/grid_gate_test -o IdentitiesOnly=yes -o PreferredAuthentications=publickey <AccessID>@grid.wayne.edu`
   with his own AccessID: "key-only sign-in works" means a key alone gets in, and a password or code
   prompt, or "Permission denied", means it does not. Then, in the grid's shell,
   `sed -i '/grid-gate-test/d' ~/.ssh/authorized_keys` takes the test key out again. Beside it, C&IT's
   answer to the first question in section 3 of hpcworker's docs/guides/LAB_LEAD.md, whether a key
   restricted this way and used from outside the VPN is acceptable, if he has one.

A thread that takes this up on another account reads this note, docs/setup/grid.md, and in
hpcworker the README's paragraph "A GitHub Actions runner on the grid" and the section of the same
name in docs/OPEN_QUESTIONS.md; then it asks the owner which of the three steps he has done and what
each printed: the install job's log, the output of `--status`, the page of the first grid.yml run,
step 3's one line. A fault the grid shows is fixed in hpcworker by a pull request whose fix a
mutation proves (below); step 3's answer starts the ssh gate (next).

## Where it stands on 2026-10-17

The owner answered on 2026-10-17, in the thread "Grid ssh gate" of the symphony2 project, with
step 3's output. The restricted test key signed in from his PC with the public key alone and printed
"key-only sign-in works" (the line before it, "PTY allocation request failed", is restrict refusing
a terminal, as it should), so a key alone gets in to grid.wayne.edu from outside the VPN; the thread
takes the test as run with the VPN off, as the step asked. Two things were not as the step said: he
ran it from Git Bash on Windows rather than WSL, which changes nothing about the answer; and the
cleanup `sed` ran on his PC, where there is no authorized_keys, so the test key, which can only print
that one line, stays on the grid until he runs the same `sed` in the grid's shell. C&IT's word on
such a key is still not on record.

Step 1 is done: the owner committed the two CI lines to hpcworker's main as 12e34b2, and its ci run
(https://github.com/OpenSpineConsortium/hpcworker/actions/runs/39057118601) passed. Step 2 is not
yet shown to have worked: the first grid.yml run
(https://github.com/OpenSpineConsortium/symphony-template/actions/runs/39063579109), started
2026-10-17 19:41 UTC, was still queued at 21:11 UTC, which means no runner of the chain had
registered, whether the install job, the chain's start or the chain's job in Slurm's queue is where
it stopped; the install job's log and `--status` say which.

The gate's first `--gate-key` on the grid (22:54 UTC) refused: two folders on the physical path to
the runner's folder, `/.rs/volumes/rs_grp_oschome` (`drwxrwxrwx`, owned by another account,
ay6621) and `/.rs/volumes/rs_grp_oschome/rs_vol_oschome` (`drwxrwxrwx`, root's), are writable by
everyone, not sticky, and only the university can change them. They are the CephFS scaffold folders
hpcworker's docs/guides/LAB_LEAD.md describes, which `browser-key check` has reported as a note
rather than a refusal since 2026-10-02, because the lab's code already runs from under them. The
owner chose the same for the gate ("Match students' key", 2026-10-17): hpcworker#15 reports a folder
above that root or another account owns as a note for the university and refuses nothing for it,
while a folder of the account's own that others may change is still refused. Asking C&IT for
`chmod +t` on the two folders would close the gap for both keys.

The key then went in (23:20 UTC). Two things the setup page had wrong came out of the next steps.
grid.wayne.edu offers only its RSA host key from outside the VPN: `ssh-keyscan -t ed25519` printed
nothing but the server's banner (OpenSSH 7.4), and the plain scan printed one `ssh-rsa` line whose
fingerprint, SHA256:kLTz1xK6anQ1denM+31kDEryQtgan2P76r9aLno+K3s, is the one the login node's
/etc/ssh/ssh_host_rsa_key.pub gives, though the node holds an ed25519 key too; GRID_HOST_KEY is that
RSA line, and docs/setup/grid.md step 3 now says so. And the gate key's private half was made
somewhere other than the computer the test ran on, so the test fell back to the password and one-time
code and the grid's own shell answered "status: command not found": a password sign-in never reaches the
gate, which only the key's own line runs, and a key made afresh on the same computer
replaces the line with `--gate-key`.

With the key made afresh the owner's test from outside printed the chain's state and "HPCW-GRID-GATE
status ok" (2026-10-17, 23:51 UTC): the gate works from outside the VPN. That state also showed why
step 2's grid.yml run stayed queued: the chain's STOP file was written at 19:46 UTC, minutes after it
started, so its job ended with no runner registered, and the chain needs grid.yml's start box (or
`--start`) again. The owner then asked for a wizard ("that was a fucking nightmare to do") and, of the
token wizard too, "how could you do this browser side only?". Every step of the gate can be done from
the grid's own shell, which Open OnDemand opens in a browser: the account's gh there is signed in
already (the runner mints its registration credentials with it), ssh-keygen is there, and the site's
profile holds the host key's fingerprint as it was seen from the internet, so the login node can pick
its own host key with that fingerprint and pin it for GitHub's machine without a scan from outside. So
hpcworker's `grid_runner.sh --gate-setup` (hpcworker, 2026-10-18) does the whole setup in one command
there, and nothing runs on the owner's computer; the only call from outside is grid-gate.yml's own run
from GitHub's machine, which it starts. A first draft that ran on the owner's computer (Python, Git
Bash, one password sign-in) was set aside before it was opened, since it needed the very tools the
owner had no easy way to run.

## The ssh gate, built

Planned on 2026-10-16 (the card of 00:24 UTC chose both directions, the runner first) and built on
2026-10-17 once step 3 showed that a key alone signs in: OpenSpineConsortium/hpcworker's pull request
from claude/grid-ssh-gate-4wx0ul and this repository's from the branch of the same name. A key on the
grid that accepts one forced command and nothing else, through hpcworker, used by a workflow from an
environment secret, with the password nowhere.

- What it is for: a step on GitHub's own runner that starts the chain only when a job needs it, in
  place of a chain kept waiting in Slurm's queue, reads the chain's state into the run's log, and
  ends it. A gate that queued a job of the workflow's own would run the workflow's code under the
  account outside the runner's container, beside the account's gh sign-in and Claude login, which
  the runner was built to rule out; so the gate starts, reads and stops a chain, and every command of
  a workflow's still runs on the runner.
- In hpcworker: tools/grid_gate.sh is the forced command. One change from the plan: the line, not
  the client, names the repository, the site, the runner's folder and the chain's size, so a client
  says one word, start, status or stop, read from SSH_ORIGINAL_COMMAND with no shell evaluating it,
  and a stolen key reaches one chain at the size the owner chose. It refuses any other word or byte, a
  second call for the same repository within 60 seconds (the grid's polling floor), a line --gate-key
  did not write, and, as browser-key's gate does, a clone whose tools/, framework/lib/ or
  framework/profiles/ others may change, or any folder above it that others may change and that is
  not sticky. It runs grid_runner.sh with HPCW_GATE set and the client's GH_TOKEN, GITHUB_TOKEN and
  shell start-up variables gone, takes a chain already queued or running as started, and writes one
  line per call to the chain's gate.log: the time, the word, the address and how it ended, never the
  key. `grid_runner.sh --gate-key '<ed25519 public key>' --repo OWNER/NAME --site S` writes
  `restrict,command="<clone>/tools/grid_gate.sh --site S --runner-dir D --repo OWNER/NAME [size]" ssh-ed25519 <key> hpcw-grid-gate:OWNER/NAME`,
  replacing that repository's earlier line and keeping every other, under browser-key's own lock;
  `--gate-off` takes it out; both run only for a person at a terminal (no agent's variable, no job, no
  forced command), and refuse a home, ~/.ssh or authorized_keys that sshd would ignore or that is a
  link. tools/tests/test_grid_gate.sh, 98 checks, runs at the end of test_grid_runner.sh, so CI's
  existing step runs it; it passes on Ubuntu and in centos:7 under bash 4.2.46. Twenty-two checks were
  each undone in a copy and the tests failed on every one; three lines the mutations showed to be
  redundant were removed instead (a word-length test the exact word list covers, a key-length test
  base64 -d covers under pipefail, a newline fix grep already makes).
- The adversarial review, which ran the line against a real sshd, found one blocker and seven
  should-fixes, all fixed before the pull requests: grid.yml must pass the environment's secret to
  grid-gate.yml by name, or GitHub hands the called workflow an empty string; a key already on another
  authorized_keys line, which sshd uses first, could have run a shell, so --gate-key refuses it; the
  runner's folder, its bin/ and the chain's folder were not judged, so someone who could write there
  could have turned a start into their own code or the gate's write into a planted link's; folders are
  judged through links (stat -L), which the lab volume's own link needs; a start on a chain told to stop
  reported it running; the gate's log had no bound; grid_runner.sh now makes its folders with umask 022,
  and the owner's steps chmod go-w after each pull, since a login node's umask of 002 would leave them
  group-writable; the host key is taken as GitHub's machine sees it, by ssh-keyscan from outside, and
  checked against the grid's own file. Left as they are: a folder above the clone that another account
  owns and only it may write is accepted, as browser-key's check accepts it.
- In this repository: .github/workflows/grid-gate.yml, on workflow_dispatch with the word to choose
  and on workflow_call, runs on GitHub's machine in the environment grid, which only main may deploy
  to; it writes the key from the secret GRID_GATE_KEY to a mode-0600 file under $RUNNER_TEMP (carriage
  returns dropped), runs `ssh -T -i <that file> -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=<GRID_HOST_KEY> <GRID_ACCESS_ID>@grid.wayne.edu <word>`,
  tries once more after 61 seconds when the gate answers with its one-a-minute code, writes the
  gate's words to the run's summary and removes the file. grid.yml gains a start box that runs it with
  start before its job.
- The owner's steps are docs/setup/grid.md, "The ssh gate". Whether each run waits for his approval
  is his to choose there: the environment's required reviewers, left off by default so a run need not
  wait.
- Not yet measured: whether GitHub's machines reach the grid's ssh port as his home connection did,
  whether the forced command's non-login shell finds sbatch and gh (the gate reads /etc/profile's
  PATH when sbatch is missing), and whether every login node behind grid.wayne.edu shows the same
  host key; hpcworker's docs/OPEN_QUESTIONS.md holds each with its first test.

## The gate's setup as a button, 2026-10-18

In the thread "Grid ssh gate" the owner asked for the setup to be a button on the SymphonyBoard site,
in Beethoven, or both, and chose a Beethoven button on a card. The reasons it lives in Beethoven and
not on the site: the key must be made and written into the grid account's authorized_keys from inside
that account, which only a shell on the grid can do, and Beethoven already types lines into the
portal's shell for the student; the site holds no grid sign-in and should not.

- hpcworker#17 (merged) publishes two lines in its contract export, cli.json's grid-gate-setup and
  grid-gate-off: a cd into the lab lead's own hpcworker clone in their home, a pull with
  GIT_TERMINAL_PROMPT=0 and ssh in batch mode so it never stops to ask, then
  `tools/grid_runner.sh --gate-setup` or `--gate-off` for one repository and the site. Its CLAUDE.md
  names the two exceptions this makes to its grid etiquette: git, ssh-keygen and a few gh calls on the
  login node, for one press by a lab lead.
- beethoven-extension#18 (22.0.0) adds *Connect GitHub Actions* and *Remove* under Settings' folded
  *For your lab lead*: the repository (OWNER/NAME) and the clone's folder are checked against the same
  patterns the contract's values carry, the press runs only for an approved account and one at a time,
  waits at most 240 seconds (under the service worker's five-minute event and the portal shell's idle
  limit), and shows one sentence from the tool's own output with a link to grid-gate.yml. The tool's
  check that a person pressed it holds, since the portal's shell is a terminal with no agent's marker.
  Beethoven never sees the key or a GitHub sign-in and keeps nothing of it.
- The privacy statement went to version 17 alone and the agreement stayed at 15, the owner's choice
  ("Statement only"): nothing is typed unless a lab lead presses, so students are not asked to accept
  again.
- A merge to beethoven-extension's main is a Chrome Web Store submission now that the organization's
  CWS_ON_PUSH is publish, so #18 merges only on the owner's word.
- Not yet measured: the press against the real portal shell, and how long the setup takes there; the
  selftest's mock portal and the unit tests hold the lines and the sentences.

## How the fixes were proven, and how to prove the next

The review's fixes were each proven by a mutation: one fix undone in a copy of the checkout, the
runner's tests run, and at least one check seen to fail. A mutation no check catches is a gap in the
tests, as the registration files a job left behind were until the gh stand-in learned to report
them (hpcworker's tools/tests/shim/gh lists them in $SHIM_GH/jit/over).
wsu-grid-and-github-actions-mutations.sh, beside this note, runs the eleven, as
`bash docs/research/wsu-grid-and-github-actions-mutations.sh <hpcworker checkout>`, and exits 1 when
one goes uncaught or no longer applies; on 2026-10-16 it caught every one at hpcworker's merge of #13.
What each undoes:

- version-tail-1: the runner's version read as the last line of its output, which Apptainer's own
  lines can follow;
- no-scrub: the shell's APPTAINER_, SINGULARITY_, APPTAINERENV_ and SINGULARITYENV_ settings let
  through to the container;
- no-env-false: the runner's trace on standard output left on, as the image sets it;
- no-nv: no GPU in the container for a chain started with a gpu --gres;
- no-third-stop: no STOP after three jobs in a row that could not serve;
- no-served: a job that serves leaves that count where it was;
- squeue-ignored: a job run again, when squeue cannot answer, queues a second successor;
- gh-error-as-public: gh's failure read as a public repository, which stops the chain, in place of
  a job that could not serve;
- update-retries: a runner that asks for a newer version started again, in place of a chain that
  stops and says what a person does;
- nojob-counted: a runner that ends with no job run taken for one that ran a job;
- creds-linger: a registration's files left in the runner's home for the next registration.

The runner's tests were also run under the login node's bash and awk, which hpcworker's CI does not
do for them (its centos 7 job runs the framework suite alone): in their final form, on 2026-10-16,
all 189 passed under CentOS 7's bash 4.2.46 and gawk 4.0.2 on the session's own host. Both were
copied out of the centos:7 image with `docker create` and `docker cp`, bash with its libtinfo.so.5,
and a folder put first on PATH held a bash that runs the copied one through the host's own loader,
`exec /lib64/ld-linux-x86-64.so.2 --library-path <the folder holding libtinfo.so.5> <the copied bash> "$@"`,
with awk and gawk as links to the copied gawk; then
`PATH=<that folder>:$PATH bash tools/tests/test_grid_runner.sh`. A run inside a centos:7 container
did not get as far as the tests, since its yum could not resolve vault.centos.org from the cloud
session.

## Sources

- OpenSpineConsortium/hpcworker: CLAUDE.md ("Rules that are not negotiable", "Grid", "This
  repository"), docs/OPEN_QUESTIONS.md ("The grid's CI lane installs main's head"),
  framework/profiles/wayne.json, framework/lib/adapters/common.sh (hpcw_slurm_in_container),
  tools/grid_ci.sh (the CI lane's direction and conventions), tools/tests/test_grid_ci.sh.
- github/docs, content files read on 2026-10-16: actions/reference/security/secure-use.md,
  actions/reference/limits.md, actions/reference/runners/self-hosted-runners.md,
  actions/concepts/runners/self-hosted-runners.md, actions/how-tos/manage-runners/self-hosted-runners
  (add-runners, configure-the-application, remove-runners, manage-access), rest/actions/self-hosted-runners.
- actions/runner: src/Runner.Common/Constants.cs, src/Runner.Listener/Runner.cs,
  src/Runner.Listener/Program.cs, src/Runner.Listener/Configuration/ConfigurationManager.cs,
  src/Runner.Listener/SelfUpdater.cs, src/Runner.Common/HostContext.cs,
  src/Misc/layoutroot/run-helper.sh.template, images/Dockerfile, docs/start/envlinux.md.
- apptainer/apptainer: CHANGELOG.md (v1.2.0, 2023-07-18); apptainer/apptainer-userdocs, branch
  release-1.2: environment_and_metadata.rst (the image's environment, APPTAINERENV_ and --env, and
  which wins).
- The thread "Symphony on the WSU grid" in the Symphony project: the owner's messages of 2026-10-15
  23:35 and 23:54 UTC, the decision card answered at 2026-10-16 00:24 UTC, and the coordinator's
  relays of 00:25 UTC (research notes accumulate in the repository) and 00:29 UTC (the session on
  the grid is the other thread's).
