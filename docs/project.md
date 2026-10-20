# SchwingNet: goal and settings

This file is the project's goal and the settings every account's thin Project shares. It is the one place where the goal is written: CLAUDE.md imports this file into every session, and the claude.ai Projects carry no copy of it. It changes by pull request like everything else.

## Goal

Confidential: this file describes unpublished work with a provisional patent in preparation, and stays in this private repository; nothing of it is copied to a public place. SchwingNet names vertebral levels on intraoperative fluoroscopy; the reported stack and its numbers are spine-program's 01_carm_level_detection (README.md, STATUS.md, docs/MODEL_CARD.md). This project makes a better SchwingNet than the one recorded in spine-program's 01_carm_level_detection, trained and measured between 2026-10-20 and the CNS talk of 2 November 2026 (mini-oral 66629), through Symphony's claim protocol and beethoven-qa's definition of done, so that every number the talk shows is reproduced by a command from a record in this repository. Done is: the existing model's held-out results on C-ArmLSpine with Wilson intervals, its accuracy on anomalous (transitional) spines measured as a stratum of its own with the senior second reader the owner named (Dr Tech, Corewell), a recorded C-arm sweep with the overlay and the measured per-frame latency, ready to show once the provisional is filed (by 30 October), and, once the owner has said what "better" means (which measure, by how much, against which baseline), a pre-registered retraining run on the WSU grid measured the same way. The plan is docs/research/demo-plan.md, whose sections 0 to 7 schedule and cost the measurement and the demo over the existing weights; the retraining step, its spend and the clean encoder rebuild (MODEL_CARD.md 3.3) are added to it by pull request once the owner's measure is stated, and no training job is submitted before that.

## Scope

In scope: the areas this project owns, each in one line; docs/agents/OWNERSHIP.md maps them to workers.

- The retraining, once the owner has stated the measure: the pre-registered plan, the grid jobs through Beethoven (docs/setup/grid.md), the clean encoder rebuild, the split check, the eval gate; every number carries its run id, commit and result file.
- The measurement: held-out C-ArmLSpine, the transitional stratum with two readers, the synthetic anomaly arm with exact truth, never pooled with the real one.
- The demo: the recorded sweep (C-ArmLSpine case134 and case39), the overlay, the measured latency, the slides' figures.
- The quality gate: new code to beethoven-qa's definition of done; the legacy tools of the reported pipeline listed under unproven, never refactored before the talk, since a refactor voids the parity gate.

Out of scope, by decision: what this project does not do, each with the reason, so nobody proposes it again.

- Anything public before the provisional is filed: no push to a public repository, no preprint, no slide of the method; the talk shows what SchwingNet does, not how (the owner, 2026-10-20).
- A live run at the podium: no laptop latency exists and the CPU path took seconds per frame; the demo is a recording of a causal run with its latency on screen.
- A grid job, a Claude run or a training without the owner's word and the number of jobs; usage credits are never used.
- A settings-as-code app (github/safe-settings, or the Repository Settings App reading .github/settings.yml), decided no on 2026-10-11 (symphony-template#18): it is a dependency with admin rights on every repository it covers, and a server of our own in one case, for settings that Symphony Setup applies for one run from the front door, scripts/setup-repo.sh from a clone, and organization rulesets, secrets and variables for what an organization makes.

## Repositories

- OpenSpineConsortium/SchwingNet, this one: the shared plane for every account and every session; the default branch is main.
- Repositories this project reads, all private, each a record and never changed from here (a change lands as a patch in the claim's pull request, as spine-program's CLAUDE.md says):
  - OpenSpineConsortium/spine-program, folder 01_carm_level_detection: the reported SchwingNet, its STATUS.md numbers, MODEL_CARD.md, the cine demo build plan and the handoff; 02_transitional_naming_truth for the transitional truth file and the frozen G3 split; 07_plain_film_level_id for the CNS manuscript rows.
  - Gregory-Schwing-MD-PhD/spinesurg-ct-nnunet, branch L6_Class: the training and evaluation code (tools/level_prototype.py, tools/eval_gate.py, the slurm/ scripts); the demo tools cine_eval.py and cine_latency.py are untracked there and live as copies in spine-program's 01_carm_level_detection/code/.
  - The grid, Wayne State's, reached through Beethoven's runner chain (docs/setup/grid.md): the corpora under /rs/rs_grp_oschome/go2432/data/, C-ArmLSpine among them; nothing of them is ever copied here.
  - OpenSpineConsortium/beethoven-qa, private, to be taken as a pinned copy under vendor/beethoven-qa once its 6.0.0 is merged and tagged (issue #5; the steps are symphony-template's docs/setup/beethoven-qa.md, symphony-template#280), and OpenSpineConsortium/beethoven-research, whose split check the measurement uses.
- The template's own repositories, four, each owned by the OpenSpineConsortium organization, whose owners merge to its default branch:
  - OpenSpineConsortium/symphony-protocol, public: the claim protocol as a Python library with no dependencies (the board, the protocol check, team mode's clerk, the push guard's rules and the merge gate). It is vendored here under tools/sdlc_protocol, with tools/VENDORED recording the version, the commit and the sha256 of every copied file, and scripts/check.sh fails when the copy differs from that record, or, on CI, which clones the library, from the library's files at that commit. A change to the rules is made there, never here: once the owner has approved and published a release there that carries it, its sync workflow opens the pull request `symphony-protocol/sync` in OpenSpineConsortium/symphony-template with that release's copy, and the template's check decides. A repository made from the template is not on the sync's list; its own .github/workflows/protocol.yml brings each new release in instead, weekly, as a pull request from a branch of the same name, or as an issue linking that pull request where GitHub Actions may not open one. By hand it is `python3 <symphony-protocol>/scripts/vendor.py <this repository> --consumer OpenSpineConsortium/symphony-template` and a pull request. Its ecosystem.json is the one list of which repository takes which modules, and its ECOSYSTEM.md, generated from that list, maps all five repositories.
  - OpenSpineConsortium/coordbench, public: the playground and benchmark that compares ways of coordinating Claude Code agents on CooperBench's tasks, this protocol among them; its sdlc arm runs on the library's merge gate, vendored under coordbench/vendor. It began as experiment/ on OpenSpineConsortium/symphony-template's branch claude/10.
  - OpenSpineConsortium/symphony-marketplace, public: the Claude Code plugin marketplace with one plugin, symphony, which brings the skills, /board and the hooks to a repository not made from this template. .claude/settings.json names the marketplace and enables nothing, since this repository wires the same hooks itself.
  - OpenSpineConsortium/symphony-app, private: the GitHub App SymphonyBoard (slug symphonyboard). Its installation token lets template-init's first commit start the Checks and the Board, which a push with GITHUB_TOKEN cannot, and the symphony-protocol sync opens its pull requests in every consumer with it; its webhook server, where it is run, posts the protocol check as a check run of its own, sdlc/protocol.

## Model and effort

Every account's Project uses the same model and the same effort, so the work reads the same whoever did it. Record the choice here and set it in each Project's settings when you make the Project (docs/setup/claude-project.md).

- Model: not yet chosen.
- Effort: not yet chosen.

## Crowd mode

- Crowd mode: off. To open the project to volunteers who each work on their own Claude account, the owner runs `python3 scripts/crowd.py setup` (docs/setup/crowdsourcing.md), whose pull request turns this line on with the decisions that come with it; from then on the required check holds the repository to them.

## Owners

- Repository owner: OpenSpineConsortium, who merges to main; .github/CODEOWNERS names Gregory-Schwing-MD-PhD, the owner's own login, or in an organization's copy the person who made the copy, because GitHub asks a user or a team for review and never an organization (docs/setup/github.md, section 7).
- Workers: each person's sessions, under the person's GitHub login, and the routines and workers in GitHub Actions the registry .github/symphony/workers/ names (docs/agents/WORKERS.md); none registered yet. Each worker's label is worker:<name>, made when it first needs it.
- The Claude token: the secret CLAUDE_CODE_OAUTH_TOKEN, from one account's `claude setup-token`, on whose plan @claude, the workers in Actions and the coordinator workflow run (docs/setup/claude-action.md); not set until the setup issue's second box is ticked.
