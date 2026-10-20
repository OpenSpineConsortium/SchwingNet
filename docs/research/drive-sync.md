# A repository that tracks Google Drive or OneDrive files

Source: the thread "Word revisions from OneDrive" in the project symphony2, 2026-10-18,
answering three of the owner's messages that day. The first asked for GitHub connected to
OneDrive, kept in sync, with new comments starting work. The second asked to do the shortcut in
https://startupceo.com/2026/04/ai-shortcut-how-to-collaborate-on-claude-projects-without-a-teams-or-enterprise-license
"way better", given Claude's integration with Google Drive and OneDrive. The third: "I want to
one-click authorize and literally create a repo which tracks certain files/folders from my
onedrive/google drive that i choose in the browser". This note is the design, what this pull
request builds of it, and what waits on the owner's clicks and on other threads. The Word side
is docs/research/word-revisions-from-onedrive.md and docs/setup/word-revisions.md.

## The article's shortcut, and what Symphony already does better

The article (read 2026-10-18) shares one Claude context across separate Pro accounts with no
Teams plan. A shared Drive folder holds three Google Docs (ProjectContext, WorkingConventions,
ChangeLog). Each member's Project instructions tell Claude to read them, and each member connects
the Drive connector. A weekly prompt harvests decisions, a "context owner" pastes them in by hand,
and the article names its own limits: the connector is read-only, nothing is in real time, memory
is not shared, and upkeep is manual.

A Symphony repository is that idea already, without the hand work. CLAUDE.md, docs/project.md and
docs/memory/ are the context every session loads, on any account. A fact lands by pull request,
in the same change as the work it came from, so no harvest or context owner is needed. The board
shows who is doing what in real time, and the workers in Actions write as well as read. What the
article has that Symphony lacked is that the people who never open GitHub work in Drive or
OneDrive. This design brings their folder to the repository and their comments to the board.

## The flow the owner asked for

One tab of the control console, Folders, at https://openspineconsortium.com/symphony/control/
(a tab, not a page of its own, since 2026-10-18), signed in with GitHub as every panel page is:

1. Connect Google Drive, or Connect OneDrive: one press, the provider's own consent screen, back
   to the page.
2. Pick: OneDrive's own File Picker v8 chooses the files and folders to track. For Google Drive
   there is no picker without an API key, which the owner declined (below).
3. Create the repository: the page opens GitHub's own "new repository from a template" form,
   https://github.com/new?template_owner=OpenSpineConsortium&template_name=symphony-template,
   named and pressed by the person. That keeps the rule that a new repository's first commit is
   the owner's, and needs no Administration permission for SymphonyBoard, which the decisions
   keep off it. The adoption runs as it does from the front door.
4. Track: the page writes .github/symphony/drive.json (the provider, the folder in the repository,
   the picked items' ids and names) and saves the drive's refresh token as the repository's secret
   SYMPHONY_DRIVE_REFRESH, both through the App. Then it starts the first sync.

From then on .github/workflows/drive-sync.yml keeps the two in step every half hour, and the
page's Sync now button runs it at once. The half-hourly run starts only where the repository
variable SYMPHONY_DRIVE is `on`, which Track is to set (2026-10-20): the template's sync offers
the workflow to every adopted repository, most track no drive, and on a private repository GitHub
bills each run as a whole minute, about 1,440 a month, while a job its `if` skips costs nothing.
Sync now, and every start papers.yml makes, runs whatever the variable says. A new comment in a document becomes a task on the board,
a worker answers it as tracked changes, and the revised file goes back to the drive as soon as
its pull request merges: papers.yml starts the sync on any push that changes a document. A merge
GITHUB_TOKEN makes starts no workflow, so such a revision waits for the half-hourly run.

## What this pull request builds

- tools/drive_sync.py, standard library only. It reads both providers through their REST APIs,
  with each folder walked to six levels, and decides each file's move from three things: the
  drive's version, the default branch's copy and the last run's record (state.json on the branch
  drive-state). A file that changed only in the drive comes down on the pull request drive/sync,
  which merges by itself once green. One that changed only here goes up in place. One that changed
  on both goes up beside the drive's as "<name> (Symphony revisions)", and the drive's comes down,
  so nothing is lost. A pulled file waits for its merge, so it is neither pulled twice nor pushed
  back. A native Google file comes down exported (Doc as .docx, Sheet as .xlsx, Slides as .pptx).
  It takes no upload, so its revision goes beside it. A Google file's version includes a hash of
  its Drive comments, since a comment on a Google Doc changes no version of the file. A redirect,
  such as Graph's download, is followed without the token. A drive's names are cleaned to single
  path segments.
- .github/workflows/drive-sync.yml. First it queues the comments of what is already on the default
  branch. Then it syncs, opens or updates drive/sync, asks for the check there and arms auto-merge.
  It uses GITHUB_TOKEN alone, as protocol.yml does, and ends at once with no drive connected.
- .github/workflows/papers.yml and `tools/docx_review.py watch`. A document is one task for good,
  found by a marker in the issue body, which also lists the comments seen so far. Each comment is
  keyed by its author, date and words, since Word renumbers comment ids on every save. New comments
  are told on the issue, which is reopened or labelled todo again, and the workers are woken.
  Claude's own comments, the answers, queue nothing.
- An adversarial review before the pull request found ten faults, each fixed with a test where
  one can be written:
  - a drive/sync pull request left open after the drive moved on, which merged late and was then
    pushed back over the drive (now every run rebuilds or closes it, and a copy the sync once
    staged is never taken for a revision);
  - files kept by path, so a rename or two files of one name mixed them up (now by the drive's id);
  - a reopened task still labelled in-review;
  - an outsider's issue taken for a document's task (now only the workflows' own, or a writer's);
  - a removed comments marker spamming the issue;
  - one unreadable document stopping the sync;
  - a failed pull request never retried;
  - a 4 MB conflict that stalled a file;
  - a network error that lost the state;
  - the two workflows racing.
- Tests: tests/test_drive_sync.py (each decision, a round trip against a drive in memory, both
  providers' calls) and tests/test_docx_review.py (watch, renumbering).

## Three fixes after the sign-in thread's review (2026-10-18)

The thread "OneDrive sync fixes" fixed three faults the Control panel sign-in thread's review found:

- One picked item the drive would no longer list, deleted or unshared, failed the whole run, since
  the listing ran outside the per-file handling. Now each item is listed on its own: one that fails
  is named in the summary and the others sync. While any item is unlisted the run forgets no file, moves none to a new
  path and gives no new file the path of a file it kept, since an unseen file may only sit in the
  item that failed. A run
  that can list none of the items still fails.
- The folder gate took any plain name, so drive.json naming scripts or tools would let whoever may
  edit the drive's folder replace the repository's own check scripts through drive/sync, which
  merges by itself. Now `tools/drive_sync.py folder` refuses a folder whose top already exists on
  the default branch, file or folder, unless drive-state says the sync keeps it: state.json now
  records its folder, and a state from before that counts only where the folder holds files and
  every one of them is one the sync brought in. To take back a folder the sync kept before, the
  owner deletes the branch drive-state, as the refusal says. Records of another folder are dropped, so a changed folder starts
  afresh. The Folders page (site #37) refuses the same before Track.
- A refused call printed up to 200 bytes of the answer into the Actions log, public on a public
  repository, and a drive's message can name a file or a person. Now only the answer's error code
  is printed (the sign-in service's error, Graph's error.code, Google's error.status), and only
  where it is a short token.

## What other threads build, and the owner's clicks

The sign-in service (symphony-app/signin, the Control panel sign-in thread's) takes two routes. Both
keep nothing, as its GitHub sign-in does:

- POST /drive/connect, {provider, code, code_verifier, redirect_uri}: exchanges the consent code,
  with the client secret it holds, and returns the refresh token to the page, which seals it
  straight into the repository's secret.
- POST /drive/token, {provider, refresh_token}: returns an access token for the run. The client
  secrets stay in Cloudflare, so no repository holds one.

The panel's Folders page is the site's and the same thread's. Every page that signs in is a
SymphonyBoard Callback URL, which is the owner's click. Saving a repository secret needs
SymphonyBoard's Secrets permission, the grant already waiting on the owner for the Tokens page.
The Apps' privacy statement gains what the page and the service handle before either ships
(11 was the Assistant's and 12 is the beyond cooperation thread's, so the Folders page takes the
next free version, or shares 13 with the Dependencies section).

The owner's one-time clicks, given with their links when the page is built:

- Google: the owner chose "No key" on 2026-10-18, asked whether to allow a Picker key restricted to
  openspineconsortium.com. So the Google Picker, which needs a browser API key, is out, and no
  Google API key is made. OneDrive, whose File Picker needs no key, is built first. Google Drive
  waits for a route with no key. The one known is a list the page draws itself from the Drive API.
  That needs a scope wider than drive.file (drive.readonly to list, drive to write back), which
  Google counts as restricted and verifies, with a security assessment, before strangers may
  consent. That route is the owner's call and is not built. When it is chosen, the clicks are a
  Cloud project with the Drive API on, an OAuth client of type "Web application" whose redirect
  URI is https://openspineconsortium.com/symphony/control/, and a consent screen published
  "In production", since in Testing a refresh token lapses after seven days.
- Microsoft: an app registration for "Accounts in any organizational directory and personal
  Microsoft accounts", a web redirect URI of https://openspineconsortium.com/symphony/control/
  (the console that holds the Folders tab), a client secret into Cloudflare, and the delegated
  scopes Files.ReadWrite and offline_access. Done: the registration is SymphonyBoard Folders
  (client id 463afc21-8bbd-429b-a93d-3d3617966f0b), and on 2026-10-18 OneDrive Connect on the
  Folders tab worked end to end with the owner's personal Microsoft account (the coordinator's
  word to the thread "Organize a whole OneDrive" that day). It is not approved for Wayne State's
  tenant.

## Limits and what is not yet known

- OneDrive at WSU: a university tenant often lets users consent only to apps from a verified
  publisher, so the owner's WSU account may need IT's consent or a verified publisher (a free
  Microsoft partner ID). Not settled: SymphonyBoard Folders is not approved for WSU, and WSU's
  own consent policy is untried. A personal Microsoft account has no such gate, and it is the one
  that works. Where neither goes, the owner's own computer is the fallback (word-revisions-from-onedrive.md), with no stored
  login.
- Files.ReadWrite reaches all of the person's files, though the run reads only the picked items.
  Graph's Files.ReadWrite.Selected grants only "several hours" after each selection (Graph's
  permission reference, read 2026-10-18), too short for a sync.
- A Microsoft refresh token lasts 90 days. The run cannot write a secret, so it cannot keep the
  rotated one, and the person presses Connect again about every 90 days. The page shows when.
  Google's lasts until it goes unused for six months.
- drive.file grants only what the person picks in the Picker, so with no key it grants nothing
  useful. That is why Google Drive waits.
- Comments: a native Google Doc's comments are expected in its .docx export, which is not yet
  checked. Comments made in Drive's preview of a .docx file stay outside the file, so the tasks see
  only comments made in Word or in Docs' Office editing.
- Graph's simple upload takes 4 MB. A larger file stays in the repository and is named in the
  run's summary until an upload session is built. A file the drive drops stays in the repository.
- Every half hour costs a private repository about 1,440 Actions minutes a month. A public one is
  free. A push from the drive itself would need the service to take Google's or Graph's change
  notifications and dispatch the run, which it cannot do without holding a GitHub token, so the
  schedule is the fallback and Sync now the button.
- The first connection, the owner's personal OneDrive, worked on 2026-10-18. A sync of real files is the next
  test.
