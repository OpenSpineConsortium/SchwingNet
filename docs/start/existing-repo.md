# The protocol in a repository you already have

A repository not made from the template takes the protocol in two halves. The symphony plugin from [OpenSpineConsortium/symphony-marketplace](https://github.com/OpenSpineConsortium/symphony-marketplace) brings the Claude Code side to every local session: the skills `/symphony:claim`, `/symphony:remember` and `/symphony:checkpoint`, the command `/symphony:board`, a push guard before every Bash call, a document check after every edit, and the board at session start. The repository brings the files the plugin acts on, which a plugin cannot ship: the board's workflow, the protocol's text, the claim folder and the labels. ORG/NAME is your repository and NAME its clone; bash, on Windows in WSL.

## Steps

1. **Clone the two sources beside your repository, and branch.** symphony-protocol is public; TEMPLATE_OWNER/TEMPLATE_NAME is the template for a member of its enterprise and the public copy for anyone else ([README.md](README.md)), which exists only once the template's owner publishes one; until then, ask the owner for the seven files the `cp` lines below take from it (board.yml, tidy.yml, protocol.yml, board.py, protocol_update.py, check_docs.py and marked_section.py), put them under ../symphony-template at the paths those lines read, and skip the second clone. The branch is made with `--no-track` so that it never takes the default branch as its upstream, since wherever git's push.default is upstream a push of a branch with that upstream writes the default branch, step 7's push included:

   ```bash
   cd ..
   git clone --branch v0.4.0 https://github.com/OpenSpineConsortium/symphony-protocol.git
   gh repo clone TEMPLATE_OWNER/TEMPLATE_NAME symphony-template
   cd NAME
   git switch -c sdlc-setup --no-track
   ```

2. **The library and the board's workflow.** vendor.py copies the protocol's package where the template keeps it, tools/sdlc_protocol, with its record tools/VENDORED; board.yml renders the board with GitHub's own token on every issue and pull request event, and its run is also the coordinator's, which releases idle claims and tells open work that changes the same files; tidy.yml deletes a closed issue's claim branch; and protocol.yml, with tools/protocol_update.py, brings each later release in by pull request:

   ```bash
   python3 ../symphony-protocol/scripts/vendor.py . --consumer OpenSpineConsortium/symphony-template
   mkdir -p .github/workflows
   cp ../symphony-template/.github/workflows/board.yml ../symphony-template/.github/workflows/tidy.yml ../symphony-template/.github/workflows/protocol.yml .github/workflows/
   cp ../symphony-template/tools/board.py ../symphony-template/tools/protocol_update.py tools/
   python3 tools/sdlc_protocol/vendoring.py verify tools
   ```

   You should see `vendor: wrote tools/VENDORED: sdlc-protocol 0.4.0 <commit>, 17 file hashes`, the commit being the one the tag v0.4.0 names (`git -C ../symphony-protocol rev-parse HEAD`), and then `vendored sdlc-protocol 0.4.0 at <its first seven characters>: 17 files match VENDORED`. Later releases come by themselves: protocol.yml vendors each new one on the branch `symphony-protocol/sync` and opens the pull request, or an issue linking it where GitHub Actions may not open one ([protocol.md](protocol.md), step 7). It asks for ci.yml on that branch, which only the template has, so here the run's summary says it could not, and this repository's own checks on the pull request decide.

3. **The protocol's text and the claim folder.** spec/PROTOCOL.md is the protocol in prose with no placeholders, the claim file's shape included, and the skills read it at docs/agents/PROTOCOL.md:

   ```bash
   mkdir -p docs/agents/claims
   cp ../symphony-protocol/spec/PROTOCOL.md docs/agents/PROTOCOL.md
   printf '%s\n' '# Claim files' '' 'One file per claimed issue, docs/agents/claims/N.md, in the shape docs/agents/PROTOCOL.md gives under Claim; the pull request that finishes the issue deletes it.' > docs/agents/claims/README.md
   ```

4. **Tell every session,** in CLAUDE.md, which Claude Code loads at the start of each one; the `@` line imports the protocol whole:

   ```bash
   cat >> CLAUDE.md <<'EOF'

   ## How work is claimed

   @docs/agents/PROTOCOL.md

   Before any work: fetch, read the board with `git fetch origin +refs/heads/board:refs/remotes/origin/board && git show origin/board:STATE.md`, and check the claim on the issue you mean to take. One issue, one branch `claude/<issue>`, one pull request. Never push to the default branch or to another worker's claim branch.
   EOF
   ```

5. **The plugin, for everyone who works here.** These write the marketplace and the plugin into the committed .claude/settings.json, beside whatever it holds; each collaborator runs the second line once after trusting the folder, since a project's setting names the plugin but does not download it:

   ```bash
   claude plugin marketplace add OpenSpineConsortium/symphony-marketplace --scope project
   claude plugin install symphony@symphony-marketplace --scope project
   ```

   You should see symphony in `claude plugin list`, and `/symphony:board` in a new session. Auto-update is off for a marketplace that is not Anthropic's: turn it on under `/plugin`, Marketplaces, symphony-marketplace, Enable auto-update, or take the project preset with `"autoUpdate": true` from the marketplace's README. Just for yourself instead, in a session: `/plugin marketplace add OpenSpineConsortium/symphony-marketplace`, then `/plugin install symphony@symphony-marketplace`, which turns the push guard on in every repository you open.

6. **The labels the board reads:**

   ```bash
   gh label create todo --repo ORG/NAME --color 0e8a16 --description "In the queue, open for a claim"
   gh label create claimed --repo ORG/NAME --color fbca04 --description "A claude/<issue> branch holds it"
   gh label create in-review --repo ORG/NAME --color 1d76db --description "A pull request is open and waiting"
   gh label create blocker --repo ORG/NAME --color b60205 --description "Stops everyone until it is settled"
   LOGIN=$(gh api user --jq .login)
   gh label create "worker:$LOGIN" --repo ORG/NAME --color c5def5 --description "Held by or given to $LOGIN"
   ```

   You should see them at https://github.com/ORG/NAME/labels, the last one the label your own sessions claim under, `worker:` and your GitHub login; another person's is made the same way, with their login. epic and blocked belong to the coordinator's planning, which needs the template's other workflows.

7. **Land it by pull request.** A push of files under .github/workflows/ needs gh's workflow scope; `gh auth refresh -s workflow` adds it if the push is refused. The personal install of step 5 writes no .claude/settings.json; if you took it, leave that path off the first line, since git stages nothing when one path matches no file:

   ```bash
   git add .claude/settings.json .github/workflows/board.yml .github/workflows/tidy.yml .github/workflows/protocol.yml tools docs/agents CLAUDE.md
   git commit -m "Take up the claim protocol"
   git push -u origin sdlc-setup
   gh pr create --fill
   ```

   Until the merge, the Board runs started by the branch and its pull request are skipped, since the job checks out the default branch, which has no tools/board.py yet. Once it is merged, the next issue event runs "Board" (https://github.com/ORG/NAME/actions/workflows/board.yml; `gh workflow run board.yml --repo ORG/NAME` starts one now), and you should see the board at https://github.com/ORG/NAME/blob/board/STATE.md.

8. **Protect the default branch, and only it,** at https://github.com/ORG/NAME/settings/rules: require a pull request and your own checks, and block force pushes and deletions. Never target the branch `board`, which board.yml force-pushes on every change. The template's docs/setup/ruleset-main.json requires a check named "check", which this repository has only if its CI has a job of that name. A private repository needs GitHub Pro, Team or Enterprise for the ruleset to be enforced; on Free it is saved and ignored ([tiers.md](../setup/tiers.md)). Then decide on "Allow GitHub Actions to create and approve pull requests", under Workflow permissions at https://github.com/ORG/NAME/settings/actions. It lets protocol.yml open its pull request itself rather than an issue linking it, but it also lets any workflow approve a pull request, and that approval can stand in for a review a rule requires. So tick it and save only where no rule on the default branch requires an approving review, neither a branch protection rule nor a ruleset, the repository's or its organization's. Where one does, leave it off: protocol.yml's issue then links the pull request, which you open in one press and review as any other. Where the organization or its enterprise holds the box off, only an owner there, or in the organization someone with the "Manage organization Actions policies" permission, can allow it ([github.md](../setup/github.md), section 8).

9. **Claim the first issue.** Open one labelled todo, run `claude` in the clone and paste:

   ```
   Claim issue N with /symphony:claim and carry it to a ready pull request, as docs/agents/PROTOCOL.md says. Where the skill names bash scripts/check.sh, run this repository's own checks instead. Do not merge.
   ```

## What stays different from a copy of the template

- Cloud sessions do not install the plugins a repository declares, so there the push guard and the board at session start are missing, and the ruleset of step 8 is the fence, where the plan enforces it (a Free private repository has none); a Project can add the plugin under Project settings, Plugins. A copy of the template wires the same hooks in its own .claude/settings.json, which cloud sessions do load.
- `/symphony:remember` and `/symphony:checkpoint` act on docs/memory/, tools/marked_section.py and the checkpoint markers in CLAUDE.md, which only the template carries; the block below adds them, with an empty memory index rather than the template's, whose facts are about the template, and the import that makes every session read it. Both skills run `bash scripts/check.sh`, which this repository lacks: run `python3 tools/check_docs.py` and your own checks there, as step 9's prompt says for the claim skill. tools/check_docs.py is different: once it is in tools/, the plugin runs it after every edit under docs/, .claude/, tools/ or .github/ and to CLAUDE.md or README.md, and reports every problem that stands, wherever it is, back to the session (exit 2); the edit stays written. It holds CLAUDE.md to exactly one pair of checkpoint markers, which step 4 does not add, every tracked file in those places to ASCII with LF endings, every `@` import in CLAUDE.md to a file that exists, every tracked file to holding nothing shaped like a common secret, and docs/memory/MEMORY.md, where docs/memory/ exists, to listing each fact file there. So copy it only after the markers are in and those files pass; the markers first, from the clone:

  ```bash
  mkdir -p docs/memory
  printf '%s\n' '# Memory index' '' 'One line per fact under docs/memory/: a dash, the title as a link to its file, a colon and one line; the remember skill adds them.' > docs/memory/MEMORY.md
  printf '%s\n' '' '@docs/memory/MEMORY.md' '' '<!-- cswap:checkpoint:begin -->' '<!-- cswap:checkpoint:end -->' >> CLAUDE.md
  cp ../symphony-template/tools/check_docs.py ../symphony-template/tools/marked_section.py tools/
  python3 tools/check_docs.py
  ```

  You should see `docs ok` and the number of files it read; until then, each problem it prints is one the hook would report after an edit.
- No @claude, workers in Actions, registry of workers, coordinator workflow, coordinator trigger or protocol check in CI: those are the template's workflows and docs ([solo.md](solo.md), [team.md](team.md)). The coordinator's releases and overlap comments are here all the same, since board.yml runs them with the board. Keep one wiring of the hooks: a repository that has the template's hooks and enables the plugin runs each twice.
