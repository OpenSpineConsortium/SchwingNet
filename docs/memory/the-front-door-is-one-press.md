The front door adopts a repository in one press: install the App, press Create on the form GitHub sends you to, merge the pull request.

The public OpenSpineConsortium/symphony-start is the way in for anyone outside the enterprise, and since 2026-10-11 the install is the request. The App's Setup URL is the adoption form, and GitHub sends whoever installs the App there with `installation_id` in the query string, which the form's Installation field takes; the person presses Create and the pull request is open in their repository within about two minutes, which is the floor GitHub Actions allows.

What the run decides for them, and the two boxes that say otherwise:

- The repository: the installation's one repository with no adoption yet, or the newest created among several, read by id with the App's own JWT so that the public run never learns a name it could print; the name, the owner, the default branch and the requester's login are masked and the issue is answered with "your repository". A guessed installation number gets one answer at one moment whatever is wrong.
- The kind: an empty repository (nothing but what GitHub's "initialize this repository" makes) gets the whole template; one with files gets the protocol alone, which overwrites nothing. The box "The protocol only, even into an empty repository" overrides.
- Sharing: anonymous aggregates on, with the box "Do not share anonymous aggregates" and the switch .github/symphony-metrics.

The form opened on its own takes a repository's name instead, for a repository the install flow did not pass through. The sweep (symphony-start's sweep.yml, every ten minutes) is the fallback for an installation that never reaches the form: it reads the kind from the tree, leaves an installation younger than half an hour and the open requests to the form, and never touches the organization's own repositories. A webhook would make it faster than the form only by seconds, and needs a hosted service holding the App's key, which the owner declined.
