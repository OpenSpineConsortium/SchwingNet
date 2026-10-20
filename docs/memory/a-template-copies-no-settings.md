"Use this template" copies files only; the owner sets the GitHub side with scripts/setup-repo.sh, or scripts/crowd.py setup for a crowd repository, and an organization on Team or above can preship the rules and the secrets.

A copy of the template arrives with no ruleset, no toggle, no label, no
secret and no variable, and only a person with admin rights can set them.
tools/template_init.py makes the labels and opens the setup issue on the
first push; the rest is one run of `bash scripts/setup-repo.sh` from a clone
with gh signed in, which a cloud session cannot do: gh is installed there,
but its GitHub proxy refuses gh's GraphQL commands, and the session has no
admin rights. A crowd repository (crowd-mode.md) takes
`python3 scripts/crowd.py setup` instead, which keeps auto-merge off and
stores no token; setup-repo.sh refuses to run there.
The token comes only from the owner's own `claude setup-token`, pasted at
gh's hidden prompt, or from `/install-github-app`. An organization can set
some of it once for every repository it makes: organization rulesets (GitHub
Team or Enterprise; import docs/setup/ruleset-org.json), organization
Actions secrets and variables (any plan, but a Free organization's private
repositories cannot read them; gh needs `--visibility all`) and its workflow
permissions, whose "Allow GitHub Actions to create and approve pull
requests" a new repository inherits; setup-repo.sh turns that on, and where
the organization or its enterprise holds it off, GitHub refuses the change
with 409 and only an owner there, or in the organization someone with the
"Manage organization Actions policies" permission, can allow it. Settings
as code needs an app, a new dependency, so it is an issue first. The steps
and the plan each needs: docs/setup/owner-checklist.md.
