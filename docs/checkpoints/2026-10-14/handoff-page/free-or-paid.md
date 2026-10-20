**Short answer:** no, they are not all free. On public repositories almost all of them are free on every plan. On private repositories it depends on the plan:
- GitHub Free, personal or organization, gets Dependabot and some Actions minutes, but nothing that enforces the gate.
- Pro and Team add rulesets, required checks and reviews, code owners, auto-merge and environments.
- Deployment reviewers, artifact attestations and merge queue need Enterprise Cloud.
- Code scanning, SARIF upload, dependency review, secret scanning and push protection are paid add-ons (GitHub Code Security, GitHub Secret Protection) even on Enterprise Cloud. Only Team and Enterprise can buy them.
- Actions minutes are free on public repositories and on self-hosted runners. On private repositories they are metered beyond a monthly quota.

**How to read the cells:**
- "free" means no charge. In the Pro, Team and Enterprise Cloud columns it means included in the plan.
- "paid: X" means you need X on top of the plan.
- "no" means that plan cannot have it.
- Anything that runs as a workflow also spends Actions minutes in private and internal repositories (see the minutes row). That covers checks, CodeQL, the dependency review action and the workflows rule.
- **Plan prices:** the only ones in the docs come from the plan changes of April 14, 2020: Pro $4 a month, Team $4 per user a month. Whether those are still current is not confirmed. No docs file gives the Enterprise Cloud price, and github.com/pricing could not be read.
- **Internal repositories:** for rulesets, branch protection, required checks and reviews, code owners, auto-merge, merge queue and the dependency graph, the docs name only public and private repositories. Internal repositories are not confirmed for those.

| Feature | Public repositories | Private, personal Free | Private, personal Pro | Private, organization Free | Private, organization Team | Enterprise Cloud (private and internal) |
|---|---|---|---|---|---|---|
| Rulesets and classic branch protection, repository level (bypass list; restrict updates, creations and deletions) | free | no | free (classic protection gets no bypass list or push restriction outside an organization) | no | free | free |
| Required status checks, with the source pinned to an app such as GitHub Actions | free | no | free | no | free | free |
| Required pull request reviews | free | no | free (team-based rules need an organization) | no | free | free |
| Code owners and required code owner review | free | no | free | no | free | free (organization teams only, not enterprise teams) |
| Auto-merge | free | no | free | no | free | free |
| Merge queue | free when an organization owns the repository (personal accounts: not confirmed) | no | no | no | no | free |
| Organization rulesets, and enterprise rulesets | free in Team and Enterprise organizations; no in Free organizations | no (organization feature) | no (organization feature) | no | free, though the docs conflict (some pages say Enterprise only); bypass in branch and tag rulesets: not confirmed | free, plus enterprise-level rulesets |
| Ruleset rule "Require workflows to pass before merging" | free in Enterprise Cloud organizations; Team organizations: not confirmed; no in Free organizations | no | no | no | not confirmed (the rule is in the Enterprise docs only, yet a Free, Pro and Team page uses it) | free |
| Push rulesets (block files by path, extension or size) | no (private and internal only) | no | not confirmed (only Team is named) | no | free | free |
| Actions minutes on standard GitHub-hosted runners. Over quota, per minute: Linux 1-core $0.002, Linux 2-core $0.006, Linux 2-core arm64 $0.005, Windows 2-core $0.010, macOS $0.062. With no payment method, use stops at the quota | free, unlimited | 2,000 a month free, then paid: metered minutes | 3,000 a month free, then paid: metered minutes | 2,000 a month free, then paid: metered minutes | 3,000 a month free, then paid: metered minutes | 50,000 a month free, then paid: metered minutes |
| Self-hosted runners | free | free | free | free | free | free |
| Larger runners. Per minute: x64 $0.006 to $0.552, arm64 from $0.005, GPU from $0.052, macOS from $0.077 | paid: metered minutes, never included (Team and Enterprise Cloud organizations only) | no | no | no | paid: metered minutes from the first minute | paid: metered minutes (static IP addresses only on this plan) |
| Artifact storage, shared with Packages; $0.25 per GB a month over quota | free | 500 MB free, then paid: metered storage | 1 GB free (2 GB on two other pages: the docs conflict), then paid | 500 MB free, then paid | 2 GB free, then paid | 50 GB free, then paid |
| Dependency cache; $0.07 per GB a month above 10 GB | 10 GB per repository free; billing above that: not confirmed | 10 GB per repository free, then paid (you opt in; needs a payment method on file) | 10 GB free, then paid (opt in) | 10 GB free, then paid (opt in) | 10 GB free, then paid (opt in) | 10 GB free, then paid (opt in) |
| Environments, environment secrets, deployment branch and tag rules | free | no | free | no | free | free (environment variables: not confirmed) |
| Deployment protection rules: required reviewers (with prevent self-review), wait timer, custom rules (preview) | free | no | no | no | no | free (admin-bypass switch: not confirmed) |
| Artifact attestations | free (recorded in Sigstore's public transparency log) | no | no | no | no | free (GitHub's own Sigstore instance, no public log) |
| CodeQL code scanning (default or advanced setup, or the CodeQL CLI in another CI), with Copilot Autofix | free (Autofix needs no Copilot plan) | no | no | no | paid: GitHub Code Security | paid: GitHub Code Security, or a GitHub Advanced Security license |
| Uploading third-party SARIF (upload-sarif action or REST API) | free | no | no | no | paid: GitHub Code Security (the API answers 403 without it) | paid: GitHub Code Security |
| Dependency review: pull request diff, dependency-review-action and its API | free (one docs table says no; the gate and the billing page say free) | no | no | no | paid: GitHub Code Security | paid: GitHub Code Security (the action on internal repositories: not confirmed) |
| Dependency graph and SBOM export (dependents listed for public repositories only) | free | free | free | free | free | free |
| Dependabot alerts, including malware alerts | free (custom auto-triage rules too, though one docs table says no) | free | free | free | free (custom auto-triage rules: paid: GitHub Code Security) | free (custom auto-triage rules: paid: GitHub Code Security) |
| Dependabot security and version updates (jobs on standard or self-hosted runners use none of the included minutes) | free | free | free | free | free | free |
| Secret scanning alerts, and partner alerts | free (automatic; partner alerts go to the issuing provider) | no | no | no | paid: GitHub Secret Protection | paid: GitHub Secret Protection |
| Push protection, repository level | free (off until an admin turns it on) | no | no | no | paid: GitHub Secret Protection | paid: GitHub Secret Protection |
| Push protection for users (your own pushes to public repositories) | free, on by default | no | no | no | no | no |
| GitHub Code Security, the add-on, billed per active committer (one who pushed a commit in the last 90 days) | not needed for the rows above (still needed for security campaigns, some security overview views and AI Scan) | no (only Team and Enterprise can buy it) | no | no (move to Team first) | paid: price not in the docs; 30-day trial for eligible organizations without license fees (minutes still billed); free risk assessment of up to 20 repositories every 90 days | paid: metered monthly or a volume license, or a combined GitHub Advanced Security license; price not in the docs; same free risk assessment; trial only when paying by card or PayPal with 300 seats or fewer |
| GitHub Secret Protection, the add-on (adds custom patterns, validity checks, AI-detected secrets), billed per active committer | not needed for scanning or push protection; a Team or Enterprise organization can enable it free on its public repositories alone (Free organizations, and whether that includes custom patterns: not confirmed) | no | no | no | paid: the docs give only the price calculator's example rate, $19 per active committer; 30-day trial without license fees; free secret risk assessment | paid: metered monthly or a volume license; free secret risk assessment |

**What it means for Symphony:**
- **Your organization as it is:** Enterprise Cloud already includes, in private and internal repositories at no extra charge, every rule, review, environment, attestation and Dependabot row above. That includes merge queue, deployment reviewers and 50,000 Actions minutes a month. What costs extra there is code scanning, SARIF upload and dependency review (GitHub Code Security), and secret scanning and push protection (GitHub Secret Protection). All of these are free on your public repositories: symphony-protocol, coordbench, symphony-marketplace and symphony-start.
- **An adopter on GitHub Free with a private repository** gets Dependabot, the dependency graph, self-hosted runners and 2,000 minutes a month, but nothing that enforces the gate. There are no rulesets or branch protection, so no required check, and no auto-merge, code owners, environments, attestations or scanning. Pro or Team brings back the gate and environments. Deployment reviewers and attestations need Enterprise Cloud, and scanning needs Team plus an add-on. Making the repository public gives all of it for free.
- **Design choices it supports:**
  - Making the repositories workers change public (question 10). On a public repository almost every row is free on any plan, with unlimited standard-runner minutes. The exceptions are organization rulesets and the workflows rule (Team or Enterprise organizations only) and larger runners (always billed).
  - Basing the gate on a required status check pinned to GitHub Actions rather than on the workflows rule, since every repository that can have rulesets can have that check.
  - In repositories that stay private or internal, such as the template, keeping SARIF as a workflow artifact unless Code Security is bought.

**Sources** (all paths in github/docs, read from main on 2026-10-13):
- Rulesets and classic branch protection: data/reusables/gated-features/repo-rules.md; data/reusables/gated-features/protected-branches.md; content/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches.md
- Required status checks: content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets.md; content/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches.md
- Required pull request reviews: data/reusables/pull_requests/required-reviews-for-prs-summary.md; content/get-started/learning-about-github/githubs-plans.md
- Code owners: data/reusables/gated-features/code-owners.md; content/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners.md
- Auto-merge: data/reusables/gated-features/auto-merge.md
- Merge queue: data/reusables/gated-features/merge-queue.md; data/features/repo-rules-merge-queue.yml
- Organization and enterprise rulesets: content/organizations/managing-organization-settings/creating-rulesets-for-repositories-in-your-organization.md; content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets.md; data/features/enterprise-code-rulesets.yml
- Require workflows to pass before merging: data/features/repo-rules-required-workflows.yml; content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets.md; content/code-security/how-tos/secure-at-scale/configure-organization-security/configure-specific-tools/enforce-dependency-review.md
- Push rulesets: data/reusables/gated-features/repo-rules.md; data/features/push-rule-delegated-bypass.yml
- Actions minutes: content/billing/concepts/product-billing/github-actions.md; data/reusables/billing/actions-included-quotas.md; data/reusables/billing/actions-standard-runner-prices.md
- Self-hosted runners: content/actions/concepts/runners/self-hosted-runners.md; content/billing/concepts/product-billing/github-actions.md
- Larger runners: data/reusables/actions/larger-runner-permissions.md; content/billing/reference/actions-runner-pricing.md; content/actions/how-tos/manage-runners/larger-runners/manage-larger-runners.md
- Artifact storage: data/reusables/billing/actions-included-quotas.md; content/billing/concepts/product-billing/github-packages.md; content/billing/concepts/product-billing/github-actions.md
- Dependency cache: content/actions/reference/workflows-and-actions/dependency-caching.md; content/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository.md
- Environments, environment secrets and branch rules: data/reusables/gated-features/environments.md; content/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments.md; content/actions/reference/workflows-and-actions/deployments-and-environments.md
- Deployment protection rules: content/actions/reference/workflows-and-actions/deployments-and-environments.md; data/reusables/actions/custom-deployment-protection-rules-availability.md; content/get-started/learning-about-github/githubs-plans.md
- Artifact attestations: data/reusables/gated-features/attestations.md; content/actions/concepts/security/artifact-attestations.md
- CodeQL code scanning, CodeQL CLI and Copilot Autofix: data/reusables/gated-features/code-scanning.md; data/reusables/code-scanning/licensing-note.md; content/code-security/concepts/code-scanning/autofix-for-code-scanning.md
- Third-party SARIF upload: data/reusables/code-scanning/upload-sarif-ghas.md; content/code-security/reference/code-scanning/sarif-files/troubleshoot-sarif-uploads/ghas-required.md; src/rest/data/fpt-2022-11-28/code-scanning.json
- Dependency review: data/reusables/gated-features/dependency-review.md; content/code-security/concepts/supply-chain-security/dependency-review.md; content/billing/concepts/product-billing/github-advanced-security.md; content/get-started/learning-about-github/about-github-advanced-security.md (the conflicting table)
- Dependency graph and SBOM export: data/reusables/gated-features/dependency-graph.md; content/code-security/concepts/supply-chain-security/dependency-graph.md; content/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/export-dependencies-as-sbom.md
- Dependabot alerts and malware alerts: data/reusables/gated-features/dependabot-alerts.md; data/reusables/gated-features/dependabot-malware-alerts.md; data/reusables/gated-features/dependabot-custom-auto-triage-rules.md
- Dependabot security and version updates: data/reusables/gated-features/dependabot-security-updates.md; data/reusables/gated-features/dependabot-version-updates.md; content/code-security/concepts/supply-chain-security/dependabot-on-actions.md
- Secret scanning and partner alerts: data/reusables/gated-features/secret-scanning.md; data/reusables/gated-features/secret-scanning-partner-alerts.md
- Push protection, repository level: content/code-security/concepts/secret-security/push-protection.md; content/get-started/learning-about-github/about-github-advanced-security.md
- Push protection for users: data/reusables/gated-features/push-protection-for-users.md
- GitHub Code Security: content/get-started/learning-about-github/about-github-advanced-security.md; content/billing/concepts/product-billing/github-advanced-security.md; content/code-security/tutorials/trialing-github-advanced-security/trial-advanced-security.md; content/code-security/concepts/code-scanning/risk-assessment.md
- GitHub Secret Protection: data/reusables/gated-features/secret-protection.md; content/code-security/how-tos/secure-at-scale/configure-organization-security/configure-specific-tools/estimate-price.md; content/code-security/how-tos/secure-at-scale/configure-organization-security/configure-specific-tools/protect-your-secrets.md; data/reusables/gated-features/secret-risk-assessment-report.md
- Plan prices: content/get-started/learning-about-github/faq-about-changes-to-githubs-plans.md; content/get-started/learning-about-github/githubs-plans.md
