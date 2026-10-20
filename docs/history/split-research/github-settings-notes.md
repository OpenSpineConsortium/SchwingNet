# GitHub settings a template cannot copy: what the primary sources say

Research notes for scripts/setup-repo.sh and for the page on what an
organization can preship to every repository it makes. Written 2026-10-09.
Every claim below names its source and the sentence relied on; what could
not be read from a primary source is marked unverified.

## Which paths worked

- docs.github.com: blocked from this sandbox (getaddrinfo ENOTFOUND).
- github.blog: blocked (ENOTFOUND). The 2025-06-16 changelog that
  docs/setup/tiers.md cites could not be re-read; the docs below cover the
  same fact.
- github.com HTML pages (apps/claude/installations/new, github/safe-settings,
  probot/settings): curl got HTTP 403 from the proxy, so no live page was
  probed.
- raw.githubusercontent.com: worked for github/docs (main), github/
  rest-api-description (main, OpenAPI info.version 1.1.4), cli/cli (trunk),
  github/safe-settings (main-enterprise), probot/settings (master),
  repository-settings/app, anthropics/claude-code-action, github/
  ruleset-recipes.
- A sparse clone of github/docs (content/ and data/ only, commit
  be38ec5d78e24172587e61b3c6ff40ace1865c71, 2026-10-09) worked, so the whole
  documentation tree could be grepped. Quotes below are from that commit;
  Liquid variables are resolved from data/variables/product.yml
  (prodname_free_user and prodname_free_team both render "GitHub Free",
  prodname_team "GitHub Team", prodname_ghe_cloud "GitHub Enterprise Cloud",
  prodname_GH_secret_protection "GitHub Secret Protection").
- code.claude.com/docs: worked (WebFetch).
- gh (2.89.0) and claude (2.1.295) are installed; their help text was read.
  gh api in this session answers only repository-scoped endpoints for
  OpenSpineConsortium/symphony-template; search and /orgs endpoints are refused.

## 1. Organization rulesets

Plans. data/reusables/gated-features/repo-rules.md: "Rulesets are available
in public repositories with GitHub Free and GitHub Free for organizations,
and in public and private repositories with GitHub Pro, GitHub Team, and
GitHub Enterprise Cloud." The organization level is narrower.
content/organizations/managing-organization-settings/
creating-rulesets-for-repositories-in-your-organization.md (versions fpt,
ghec, ghes; permissions line "Organization owners can create rulesets at
the organization level."): "For customers on GitHub Team or GitHub
Enterprise plans you can create rulesets in your organization to control
how users can interact with repositories in your organization."
about-rulesets.md line 17 agrees: "A ruleset is a named list of rules that
applies to a repository or to multiple repositories in an organization for
customers on GitHub Team and GitHub Enterprise plans. You can have up to 75
rulesets per repository, and 75 organization-wide rulesets." The same page
still carries an older sentence (line 23, "For organizations on the GitHub
Enterprise plan, you can set up rulesets at the ... organization level")
behind the feature flag repo-rules-enterprise, which data/features/
repo-rules-enterprise.yml limits to ghec and ghes; that is documentation
lag, not a contradiction of the Team sentence. Answer: Team and Enterprise
Cloud organizations create organization rulesets; a Free organization does
not (the docs never list it). Confidence: high for Team and Enterprise;
high that Free is excluded, by omission from every list.

Do they reach new repositories. data/reusables/organizations/
organization-rulesets-targeting-repositories-step.md: "With your ruleset,
you can choose to target all repositories in your organization or a list of
manually selected repositories. You can also filter by naming convention or
custom properties." and "To target a dynamic list of repositories in your
organization by naming convention, in the "Target repositories" section,
next to "Repository targeting criteria", select Repositories matching a
name." (fnmatch patterns, with include and exclude). The REST schema
repository-ruleset-conditions-repository-name-target says of
repository_name.include: "Array of repository names or patterns to include.
One of these patterns must match for the condition to pass. Also accepts
`~ALL` to include all repositories." No sentence says literally "new
repositories are covered automatically"; "All repositories" and a "dynamic
list" by pattern are evaluated against the organization as it stands, so a
repository made later from the template is covered. Confidence: high by
construction, unverified as an explicit sentence. The reusable also says:
"If a repository is targeted by a ruleset created at the organization
level, only owners of the organization can edit the ruleset. However,
people with admin access to the repository ... can create additional
rulesets at the repository level. The rules in these rulesets will be
aggregated with the rules defined at the organization level."

Can it require the check "check" and a pull request. Yes. The OpenAPI
schema org-rules (POST /orgs/{org}/rulesets, rules[]) lists pull_request and
required_status_checks, both by reference to the same schemas the
repository endpoint uses (repository-rule-pull-request,
repository-rule-required-status-checks), so the parameters are identical to
docs/setup/ruleset-main.json. available-rules-for-rulesets.md lists the two
rules an organization ruleset cannot hold: "Require merge queue ... This
rule is not available for rulesets created at the organization level." and
"Require deployments to succeed before merging ... This rule is not
available for rulesets created at the organization level." For status
checks at that level it notes: "For organization-level status checks, the
app must be installed with the statuses:write permission. Only apps with
this permission are displayed when configuring rulesets at the
organization-level." The check name is typed in by hand
(data/reusables/repositories/rulesets-protections-step.md: "You can enter
the name of each status check you would like to require."); in the API it
is required_status_checks[].context, with integration_id optional.
Confidence: high.

One shape difference for the API. The schema org-ruleset-conditions says:
"The branch and tag rulesets conditions object should contain both
`repository_name` and `ref_name` properties, or both `repository_id` and
`ref_name` properties, or both `repository_property` and `ref_name`
properties." So docs/setup/ruleset-main.json, posted to
/orgs/{org}/rulesets, needs a repository_name condition added, for example
{"repository_name": {"include": ["~ALL"], "exclude": [], "protected":
false}}; the target enum there is branch, tag, push, repository.

Import from JSON. content/organizations/managing-organization-settings/
managing-rulesets-for-repositories-in-your-organization.md: "You can import
a ruleset from another repository or organization using the exported JSON
file from the previous section. This can be useful if you want to apply the
same ruleset to multiple repositories or organizations." Steps
(data/reusables/repositories/import-a-ruleset.md): "Select the New ruleset
dropdown, then click Import a ruleset." "Open the exported JSON file."
"Review the imported ruleset and click Create." Export lives in ruleset
history (data/reusables/repositories/ruleset-history-conceptual.md): "You
can also download a JSON file containing the ruleset's configuration at a
specific iteration. The bypass list of a ruleset is excluded from the
exported JSON file." The feature flag repo-rules-management (import and
export) covers fpt, ghec and ghes 3.19 and later. github/ruleset-recipes
ships organization-level JSON recipes ("Organization ruleset: One Rule to
rule them all"), which shows the import page accepts organization-shaped
files. Whether the organization import page accepts a repository-shaped
file with no repository_name condition and asks for targets: unverified.

## 2. Organization Actions secrets and variables

Plan restriction. data/reusables/actions/
actions-secrets-variables-repository-access.md, included at the top of the
organization sections of both use-secrets.md and use-variables.md (under
content/actions/how-tos/write-workflows/choose-what-workflows-do/), inside
an fpt-only block: "Organization-level secrets and variables are not
accessible by private repositories for GitHub Free. For more information
about upgrading your GitHub subscription, see ..." and, for every plan:
"When creating a secret or variable in an organization, you can use a
policy to limit access by repository. For example, you can grant access to
all repositories, or limit access to only private repositories or a
specified list of repositories." So any organization can define them, and
on GitHub Free only its public repositories can read them; private
repositories read them on Team and Enterprise Cloud. Confidence: high.

REST shape. PUT /orgs/{org}/actions/secrets/{secret_name} requires
encrypted_value, key_id and visibility; "visibility: Which type of
organization repositories have access to the organization secret.
`selected` means only the repositories specified by
`selected_repository_ids` can access the secret." (enum all, private,
selected). POST /orgs/{org}/actions/variables requires name, value and
visibility with the same enum. The gh forms: gh secret set NAME --org ORG
--visibility all|private|selected [--repos a,b]; gh variable set NAME --org
ORG --visibility ...; both default to visibility "private" (gh help:
'(default "private")'; use-secrets.md: "By default, the secret is only
available to private repositories."). On a Free organization that default
makes the secret unreadable everywhere, so a script must pass --visibility
all there.

Does a template copy get them with no step. The policy is by repository
type or by list, not by a snapshot of repositories: "all repositories" and
"only private repositories" cover a repository made later, and "selected"
does not until its id is added (the PUT description points at "Set selected
repositories for an organization secret"). The docs state the policy
semantics but no sentence names new repositories explicitly; confidence
high by construction, unverified as a sentence.

Relevant Claude Code note (code.claude.com/docs/en/github-actions, "Set up
for an organization"): "Store the authentication secret as an
organization-level Actions secret so each repository doesn't need its own
copy" and "For a secret shared across repositories, authenticate with an
API key from the Claude Console rather than an OAuth token, since an OAuth
token is tied to the subscription of the person who ran `claude
setup-token`." For this project, whose rule is no API key, an organization
CLAUDE_CODE_OAUTH_TOKEN simply means every repository draws on the main
account's subscription.

## 3. Repository settings as code

github/safe-settings (README on branch main-enterprise). "`Safe-settings` -
an app to manage policy-as-code and apply repository settings across an
organization." "In `safe-settings`, all the settings are stored centrally in
an `admin` repo within the organization. Unlike the GitHub Repository
Settings App, the settings files cannot be in individual repositories."
Three layers: organization settings in .github/settings.yml ("Currently,
only `rulesets` are supported as `org`-targeted settings."), suborg files
in .github/suborgs, per-repository files in .github/repos. "`Safe-settings`
is designed to run as a service listening for webhook events or as a
scheduled job running on some regular cadence. It can also be triggered
through GitHub Actions." It reacts to repository.created: "If a repository
is created in the org, the settings for the repo - the default settings for
the org, overlaid with settings for the suborg that the repo belongs to,
overlaid with the settings for that specific repo - is applied." What it
needs: your own GitHub App and your own hosting. docs/deploy.md: "Every
deployment will need an App." and "The easiest way to create the Github
App is using the manifest flow"; deployment options are Docker, an AWS
Lambda template, Heroku, Glitch or Kubernetes; the README's install step is
"Install the Safe-Settings GitHub App in your organization with the required
permissions." There is no hosted instance. No GitHub plan is named; the
settings it writes are gated by GitHub's own plan rules (section 1).
Licence ISC. It lives in the github organization on GitHub, but the README
nowhere calls it a supported GitHub product, and repository metadata could
not be read from here; its support status is unverified.

probot/settings, now repository-settings/app (the probot/settings README's
CI badge points at repository-settings/app, and the safe-settings README
links there as "the GitHub Repository Settings App"). README: "This GitHub
App syncs repository settings defined in `.github/settings.yml` to GitHub,
enabling Pull Requests for repository settings." What it needs: an app
installation only. "A hosted version is provided for use with GitHub.com.
Install the app (https://github.com/apps/settings) on your repositories or
entire organization." or self-host (docs/self-host.md). No plan is named.
Its warning: "Note that this app inherently escalates anyone with `push`
permissions to the admin role, since they can push config settings to the
default branch, which will be synced. Use caution when merging PRs and
adding collaborators." It is a community project, not GitHub's. Whether it
can write rulesets (as opposed to branch protection) and whether the
project is still maintained: unverified (the configuration docs were not
read; repository metadata was unreadable from here; the README shows live
CI and Renovate badges).

Neither is a GitHub platform feature. The native equivalents GitHub
documents are organization rulesets (section 1), organization secrets and
variables (section 2), and, for secret scanning and push protection,
organization security configurations: content/code-security/how-tos/
secure-your-secrets/detect-secret-leaks/enable-secret-scanning.md, "If
you're an organization owner, you can enable secret scanning for multiple
repositories at a time using security configurations."

## 4. The REST calls for scripts/setup-repo.sh

All from github/rest-api-description, descriptions/api.github.com/
api.github.com.json, info.version 1.1.4, read on 2026-10-09.

a. Create a repository ruleset. POST /repos/{owner}/{repo}/rulesets
(operationId repos/create-repo-ruleset). Body: required name and
enforcement; target enum branch, tag, push (default branch); enforcement
enum disabled, active, evaluate ("`evaluate` is only available with GitHub
Enterprise"); bypass_actors, an array of {actor_id, actor_type, bypass_mode}
(an empty array is a valid array); conditions.ref_name.include and
.exclude ("Also accepts `~DEFAULT_BRANCH` to include the default branch or
`~ALL` to include all branches."); rules, an array of {type, parameters}.
Responses 201, 404, 422, 500. docs/setup/ruleset-main.json matches the body
exactly: its top level is name, target, enforcement, conditions, rules,
bypass_actors; its deletion and non_fast_forward rules take no parameters;
its pull_request rule carries every required parameter
(dismiss_stale_reviews_on_push, require_code_owner_review,
require_last_push_approval, required_approving_review_count,
required_review_thread_resolution) plus the optional allowed_merge_methods;
its required_status_checks rule carries the two required parameters
(required_status_checks with items {context}, and
strict_required_status_checks_policy) plus the optional
do_not_enforce_on_create. The response object adds id, source_type, source,
current_user_can_bypass, node_id, _links, created_at, updated_at; whether
POST tolerates those read-only fields in a body built from a GET or an
export is unverified, so the script should post the file as it is in the
repository. gh form: gh api repos/{owner}/{repo}/rulesets --input
docs/setup/ruleset-main.json; gh's own help carries that example, and
pkg/cmd/api/api.go switches the method to POST when --input is given and no
--method is passed ("if !opts.RequestMethodPassed && (len(params) > 0 ||
opts.RequestInputFile != "") { method = "POST" }"); passing --method POST
explicitly costs nothing. gh ruleset has only list, view and check, no
create. A second run would create a second ruleset of the same name;
checking GET /repos/{owner}/{repo}/rulesets for the name first is the
script's job (the API's behaviour on a duplicate name is unverified).

b. Auto-delete and auto-merge. PATCH /repos/{owner}/{repo} (operationId
repos/update), body delete_branch_on_merge ("Either `true` to allow
automatically deleting head branches when pull requests are merged, or
`false` to prevent automatic deletion.") and allow_auto_merge ("Either
`true` to allow auto-merge on pull requests, or `false` to disallow
auto-merge."), both boolean, default false. Responses 200, 307, 403, 404,
422. gh form: gh repo edit OWNER/REPO --delete-branch-on-merge
--enable-auto-merge (both flags are in gh 2.89.0's help). The API
currently reports both already true on OpenSpineConsortium/symphony-template.

c. Secret scanning and push protection. Same PATCH, body
security_and_analysis: {"secret_scanning": {"status": "enabled"},
"secret_scanning_push_protection": {"status": "enabled"}}. The schema:
"secret_scanning: Use the `status` property to enable or disable secret
scanning for this repository." and "secret_scanning_push_protection: Use
the `status` property to enable or disable secret scanning push protection
for this repository."; "To use this parameter, you must have admin
permissions for the repository or be an owner or security manager for the
organization that owns the repository."; "You can check which security and
analysis features are currently enabled by using a `GET
/repos/{owner}/{repo}` request." gh form: gh repo edit
--enable-secret-scanning --enable-secret-scanning-push-protection (help:
"Secret scanning must be enabled first"). Where it can succeed, from
data/reusables/gated-features/secret-scanning.md: "Public repositories:
Secret scanning runs automatically for free." "Organization-owned private
and internal repositories: Available with GitHub Secret Protection enabled
on GitHub Team or GitHub Enterprise Cloud." "User-owned repositories:
Available on GitHub Enterprise Cloud with Enterprise Managed Users." and
data/reusables/gated-features/secret-protection.md: "GitHub Secret
Protection is a set of features within GitHub Advanced Security that is
available to the following users: GitHub Team plan users; Enterprise
organizations on GitHub Enterprise Cloud and GitHub Enterprise Server." So
on a public repository the call is at most a no-op for scanning (push
protection on public repositories is a toggle the UI offers free, by the
same reusable's "for free" line; its exact API behaviour there is
unverified), and on a private repository of a Free organization it cannot
succeed. Which error it returns there is unverified: the OpenAPI lists only
the generic 403 forbidden, 404 not_found and 422 validation_failed for the
PATCH, and no documentation page I could read names the status for an
unavailable feature. The script should treat any non-200 on this one call
as "not available on this plan or visibility" and go on. Note on the
repository at hand: GET reports private true, visibility "internal", and
every security_and_analysis status disabled; "internal" is a visibility
GitHub offers only to organizations owned by an enterprise account, so the
organization's actual plan is worth confirming before the script assumes
Free.

d. Labels. POST /repos/{owner}/{repo}/labels (operationId
issues/create-label): "Creates a label for the specified repository with
the given name and color. The name and color parameters are required."
(the schema marks only name required); color: "The hexadecimal color code
for the label, without the leading `#`."; description: "A short description
of the label. Must be 100 characters or fewer." Responses 201, 404, 422
(tools/template_init.py already treats a 422 with code already_exists as
fine). gh form: gh label create NAME --color HEX --description TEXT
--force; help: "Create a new label on GitHub, or update an existing one
with `--force`."; the source (pkg/cmd/label/create.go) POSTs, and on a 422
whose single error is field name, code already_exists, it PATCHes
/repos/{owner}/{repo}/labels/{name} when --force is set, otherwise fails
with "label with name %q already exists; use `--force` to update its color
and description". gh label clone SOURCE-REPO --force copies every label of
another repository and is an alternative when a copy should mirror the
template's own labels.

e. Variables and secrets. gh variable set NAME --body VALUE; help: "-b,
--body string The value for the variable (reads from standard input if not
specified)"; REST POST /repos/{owner}/{repo}/actions/variables with {name,
value}. gh secret set NAME: help "Paste secret value for the current
repository in an interactive prompt"; "gh secret set MYSECRET < myfile.txt";
"-b, --body string The value for the secret (reads from standard input if
not specified)". The source (pkg/cmd/secret/set/set.go, getBody) uses
--body when given, otherwise a password prompt ("Paste your secret:",
Prompter.Password, so nothing is echoed) when a terminal is attached,
otherwise reads all of standard input and strips the trailing newline; so
printf '%s' "$X" | gh secret set NAME and gh secret set NAME < file both
work without echoing, and --body "$X" works but puts the value in the
process argument list. Client-side encryption is confirmed twice: the help
says "Secret values are locally encrypted before being sent to GitHub.",
and the source fetches the repository's public key (getRepoPubKey) and
seals the value with golang.org/x/crypto/nacl/box ("box.SealAnonymous(nil,
secret[:], &peersPubKey, rand)") before the PUT; --no-store prints that
sealed value instead of storing it. The API cannot take plaintext: PUT
/repos/{owner}/{repo}/actions/secrets/{secret_name} requires
encrypted_value ("Value for your secret, encrypted with LibSodium using the
public key retrieved from the Get a repository public key endpoint.") and
key_id.

## 5. Prefilled links for secrets, variables and ruleset import

No such parameter is documented. Grepping the whole github/docs tree
(content/ and data/, commit be38ec5d) for secrets/actions, variables/
actions, settings/rules, rules/new, rulesets/new and rulesets/import finds
nothing; the settings pages are never given as URLs there, let alone with
parameters. The query-parameter prefills GitHub documents are for a new
repository (content/repositories/creating-and-managing-repositories/
creating-a-new-repository.md: "You can use query parameters to pre-fill
form fields when creating a new repository." with name, owner, visibility,
template_owner and template_name, for example
https://github.com/new?owner=avocado-corp&template_owner=avocado-corp&
template_name=octo-repo), for issues, pull requests and releases, for
registering a GitHub App from URL parameters, and for the App install URL
(section 6). Whether the secret, variable or import forms accept an
undocumented parameter was not probed: github.com is unreachable from this
sandbox and the forms need a signed-in administrator. Unverified beyond
"undocumented".

## 6. The Claude GitHub App install link

The plain link is documented. content/apps/sharing-github-apps/
sharing-your-github-app.md: "The URL will look something like
https://github.com/apps/APP-NAME/installations/new, where APP-NAME is the
name of the GitHub App." and "you can include a `state` query parameter in
the installation URL to preserve the state of the application page and
return people back to that state after they install". content/apps/
using-github-apps/installing-a-github-app-from-a-third-party.md: "Select
the location where you want to install the GitHub App. You can select your
personal account or an organization that you are a member of." A
preselecting form exists but with another parameter name. content/apps/
creating-github-apps/about-creating-github-apps/
migrating-oauth-apps-to-github-apps.md: "To pre-select any repositories
your OAuth app had access to, you can append `/permissions` and query
parameters to the install URL." "`suggested_target_id`: The ID of the user
or organization that is installing your GitHub App. This parameter is
required." "`repository_ids[]`: The repository IDs to select for the
installation. If omitted, all repositories are selected. The maximum number
of repositories that can be pre-selected is 100." Example given:
https://github.com/apps/YOUR_APP_NAME/installations/new/permissions?
suggested_target_id=ID_OF_USER_OR_ORG&repository_ids[]=REPO_A_ID. The form
target_id= appears nowhere in the docs (the only matches are inside
suggested_target_id and a cookie name), so it is unverified and the
documented spelling should be used. For this organization the ids from GET
/repos/OpenSpineConsortium/symphony-template are owner.id 285817514 and
repository id 1411163972, so the documented link would be
https://github.com/apps/claude/installations/new/permissions?
suggested_target_id=285817514&repository_ids[]=1411163972. Not probed live
(github.com returned 403 through this sandbox's proxy).

## 7. claude setup-token

Help text of the installed binary (claude 2.1.295, /opt/node22/bin/claude
-> /opt/claude-code/bin/claude): "Usage: claude setup-token [options]" /
"Set up a long-lived authentication token (requires Claude subscription)" /
"Options: -h, --help". Nothing else; no flag for quiet or raw output.
code.claude.com/docs/en/authentication, section "Generate a long-lived
token": "The command opens the same browser authorization flow as /login,
and the token prints to the terminal after you approve access in the
browser. It does not save the token anywhere; copy it and set it as the
CLAUDE_CODE_OAUTH_TOKEN environment variable wherever you want to
authenticate" and "This token authenticates with your Claude subscription
and requires a Pro, Max, Team, or Enterprise plan. It can only make model
requests". It does not print the token alone on stdout. The binary's own
strings show the success screen is an interactive terminal UI: "This will
guide you through long-lived (1-year) auth token setup for your Claude
account. Claude subscription required.", then "Long-lived authentication
token created successfully!", "Your OAuth token (valid for ...):", the
token on its own line, "Store this token securely. You won't be able to see
it again." and "Use this token by setting: export
CLAUDE_CODE_OAUTH_TOKEN=<token>". So claude setup-token | gh secret set
NAME would feed those lines, not the bare token, and the flow needs a
browser and sometimes a pasted code; piping is not supported by anything
documented (unverified whether the UI even renders without a terminal).
The documented one-command path is /install-github-app inside Claude Code
(code.claude.com/docs/en/github-actions): "Claude Code installs the GitHub
App, adds your authentication secret, and prepares the workflow pull
request for you", it needs gh installed and signed in ("install the GitHub
CLI and authenticate it with `gh auth login`"), and "Claude Code saves the
credential as a repository secret, named `ANTHROPIC_API_KEY` for an API key
or `CLAUDE_CODE_OAUTH_TOKEN` for a subscription token." The by-hand path
for a script is: run claude setup-token in a terminal, copy the token, then
gh secret set CLAUDE_CODE_OAUTH_TOKEN, which prompts with a hidden password
prompt (section 4e). The same docs note that setup-token and
/install-github-app "enforce only `forceLoginMethod`, so they can mint a
token in a different organization" when managed settings pin one.
