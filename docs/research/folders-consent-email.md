# The consent email to Wayne State C&IT

Source: the project thread on the owner's request of 2026-10-19 for an email asking Wayne State C&IT for tenant admin consent to the Entra app "SymphonyBoard Folders" (client id 463afc21-8bbd-429b-a93d-3d3617966f0b). It was written as a draft in the owner's WSU Outlook through the Microsoft 365 connector and never sent by a session; the owner sends it.

What it is: the letter in docs/setup/folders-admin-consent.md (symphony-template#229), addressed to help@wayne.edu, the C&IT address that letter names, with three changes the owner asked for or the state called for:

- It asks for consent on behalf of Wayne State, since the owner is not a tenant administrator.
- It gives the reason in the owner's terms: keeping the AIDaS grant work continuous in one tracked place, and keeping it in the university's own OneDrive to protect confidential information under the owner's IRB. It names no dataset, no internal tool and no protocol detail, and says nothing of the IRB's scope.
- It says the in-screen consent request was already submitted, and puts approving that pending request first among the ways to grant it (Entra admin center, Enterprise applications, Admin consent requests), with the admin consent URL and user assignment to one account as the alternatives.

The permissions, the redirect URI and the privacy statement's link are the letter's, unchanged: delegated Files.ReadWrite and offline_access only.
