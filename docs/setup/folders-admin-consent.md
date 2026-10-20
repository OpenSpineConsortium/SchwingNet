# Asking your IT to allow the Folders tab

The control panel's Folders tab reads and writes your OneDrive through a Microsoft
app registration, "SymphonyBoard Folders". On a personal Microsoft account it
connects at once. On a work or school account, such as a university's, the
organization may require an administrator's consent before the app can be used.
This page is the request to send that administrator, and the facts behind it.

It is a delegated application: it only ever acts as the person who signs in, on
that person's own files, and can do nothing when nobody is signed in. It is never
granted access to anyone else's files, to mail, or to any administrative power.

## The request to send

Copy the letter below, fill in the blanks, and send it to your IT service desk (at
Wayne State, C&IT: help@wayne.edu, tech.wayne.edu).

> Subject: Admin consent for a Microsoft 365 app on my account, "SymphonyBoard Folders"
>
> Hello,
>
> I would like to use a tool that connects to my own OneDrive for Business, and our
> tenant requires administrator consent before its Microsoft app can be used. Would
> you grant consent for the app below, for my account [your-wsu-email@wayne.edu]?
>
> - Application (client) ID: 463afc21-8bbd-429b-a93d-3d3617966f0b
> - Application name: SymphonyBoard Folders
> - Publisher: Gregory Schwing (OpenSpineConsortium)
> - Permissions requested (Microsoft Graph, delegated): Files.ReadWrite, offline_access
> - Redirect URI: https://openspineconsortium.com/symphony/control/
>
> What the permissions mean:
>
> - Files.ReadWrite (delegated): the app reads and writes files in my own OneDrive,
>   acting as me. It is delegated, not application-level, so it can only ever reach my
>   own files, never another user's, and only while I am signed in.
> - offline_access: the app keeps a refresh token so it can continue syncing the
>   folders I choose when I am not actively signed in. The token is stored as a sealed
>   secret in my own Git repository, never on a server of the developer's.
>
> It requests no access to other users' files, no mail, no calendar, no Teams and no
> administrative permission.
>
> The app's privacy statement, the full list of what it keeps, is at
> https://openspineconsortium.com/symphony/apps-privacy.html.
>
> If org-wide consent is more than you want to grant, user-scoped consent for my
> account alone, or approval of the consent request I can raise from within the app,
> is all I need.
>
> Thank you,
> [your name]

## For the administrator: how to grant it

An administrator can grant it either way.

1. Admin consent URL. Sign in as an administrator and open:

   `https://login.microsoftonline.com/organizations/adminconsent?client_id=463afc21-8bbd-429b-a93d-3d3617966f0b&redirect_uri=https://openspineconsortium.com/symphony/control/`

   Substitute your tenant's domain or ID for `organizations` if your tenant requires
   it. Review the permissions and press Accept.

2. Microsoft Entra admin center. Go to Identity, then Applications, then Enterprise
   applications; find "SymphonyBoard Folders" (or add it by the client ID above); open
   API permissions; press "Grant admin consent". To limit it to specific people, set
   the app to require user assignment and assign only the people who should have it.

If your organization prefers that a user request consent rather than receive it in
advance, the app shows a "needs admin approval" message when the person first connects,
and Microsoft's own flow lets them send the request to an administrator; approving that
request is equivalent.

## The facts behind the request

- Application type: a single-page web application. There is no server of the
  developer's that holds your files. You sign in through Microsoft's own page; the app
  receives the authorization code on its redirect URI and exchanges it for tokens.
- Account types the registration allows: work or school accounts in any organization,
  and personal Microsoft accounts.
- Microsoft Graph delegated permissions, and only these: `Files.ReadWrite`,
  `offline_access`. No application permissions. No `Sites.*`, no `Mail.*`, no
  `User.Read.All`, no directory or administrative scope.
- What it does with them: lists the folders and files of the signed-in user's own
  OneDrive for the Folders tab, and, for the folders the user chooses to track, reads
  and writes those files to keep them in step with a Git repository the user owns.
- Where tokens live: the access token stays in the open browser tab's memory and is
  never written to storage. The refresh token is sealed in the browser with the user's
  Git repository's public key, the way a GitHub secret is sealed, and stored as a secret
  in that repository. A small stateless sign-in service holds the app's client secret and
  exchanges authorization codes for tokens; it never sees the Git repository.
- What it never does: reach any file that is not the signed-in user's own; read mail,
  calendar, Teams or contacts; take any administrative action; or act when nobody is
  signed in, beyond the sync the user set up.

The privacy statement at https://openspineconsortium.com/symphony/apps-privacy.html is
the exhaustive list of what the app keeps; confirm the token-handling wording against
its current version, and your tenant's exact consent process with your administrator,
before relying on this skeleton.
