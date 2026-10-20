# Why Symphony does not ride a signed-in OneDrive session

Source: the Control panel sign-in thread, 2026-10-18; the owner's questions in
that thread (whether a page or a Chrome extension could "borrow your signed-in
WSU session to read OneDrive behind WSU's back", and what the difference in
power would be). No external document.

## The question

The Folders tab reads and writes a person's OneDrive. On a personal Microsoft
account it connects at once; on a work or school account such as Wayne State's,
the tenant requires an administrator's consent first
(docs/setup/folders-admin-consent.md). The question was whether the control
panel's web page, or a companion Chrome extension, could instead borrow the
person's already signed-in WSU browser session and read OneDrive through it, so
that the Folders tab would work without waiting on C&IT.

## The decision: no, and no spec for it

Symphony does not do this, and this note is deliberately not a build plan: it
names no cookie, header or request sequence that would carry it out. It is the
record of why the approach is off the table, so a later session does not reopen
it.

## Why it is off the table

Each of the following is reason enough on its own.

1. A web page cannot do it at all. The control panel is a page served from
   openspineconsortium.com. The browser's same-origin policy keeps it from
   reading another origin's cookies or making credentialed calls to Microsoft
   Graph or SharePoint as the signed-in user, and modern cookie partitioning and
   SameSite defaults close the same door. So the "page borrows the session" form
   is not a thing we chose against; the browser forbids it.

2. A Chrome extension could reach the session, but must not. An extension
   granted broad cookie and host permissions over Microsoft's sign-in and
   storage origins could, in principle, read the session and act as the user
   behind the tenant's controls. That is exactly what the admin-consent gate
   exists to prevent: it is how Wayne State governs which applications may act
   on its accounts, alongside conditional access and app governance. Using a
   person's authenticated session to reach the tenant outside a sanctioned app
   circumvents those controls. It breaks Microsoft's and the university's terms;
   it is the kind of broad, credential-adjacent access the Chrome Web Store
   rejects and removes, since a reviewer reads it as deceiving the sign-in
   boundary rather than as a single, least-privilege purpose; and it is against
   Symphony's and Beethoven's own first rule, which is never to read, borrow or
   relay a person's credential or session and never to act behind a provider's
   access boundary. The product's whole posture is to act as the person's own
   sanctioned tools, not in place of them.

3. It would put the person's account at risk and would not last. Riding the
   session adds a token-theft surface the person did not ask for, and it would
   flag or break their account the moment WSU tightened conditional access. It
   trades a one-time consent request for a standing liability.

The auto-mode guard stopped the research down this road, reading the searches as
an attempt to weaken or bypass an access control. That was the system working as
intended, and a sign the approach was already outside the line.

## What we do instead

Three sanctioned routes reach the same value without borrowing anyone's session:

- Admin consent for the Folders app. The person's IT grants the delegated,
  least-privilege "SymphonyBoard Folders" app (Files.ReadWrite and
  offline_access), and the tab works as designed. The request to send is
  docs/setup/folders-admin-consent.md.
- The catalog route. The person's own Claude Microsoft 365 connector, which
  Wayne State has already approved, reads the drive and writes a catalog.json to
  the drive-catalog branch of a private repository; the Folders tab reads that
  catalog from the repository with the person's GitHub token and draws the same
  explorer. No Microsoft session is borrowed, because the person's own approved
  tool did the reading (privacy statement version 26, symphony-start#65;
  docs/memory/drive-organizer.md).
- Ask in claude.ai. The Ask in claude.ai button opens a question, with the
  page's context, on the person's own Claude account, rather than reaching into
  the drive from the page.

Each is the person acting as themselves through a tool their institution has
sanctioned, which is the difference that matters: the same reach, inside the
boundary rather than around it.
