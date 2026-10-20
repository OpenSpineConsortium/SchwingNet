# Mendeley in the control panel: the plan

The plan of 2026-10-19, in the thread "Control panel sign-in", after the owner chose the Mendeley
app that day for the notebooks' references (docs/research/notebooks.md, where the choice and its
reason, Mendeley's Web Importer, are recorded). Nothing here is built. The rule is that no
Mendeley code is written until the owner has registered the app and put its two values in the
sign-in Worker, and that the Apps' privacy statement describing it is live before the code ships.

The cloud session's proxy refuses dev.mendeley.com, api.mendeley.com, the sign-in Worker and the
site, so nothing below was seen live. The registration form's fields come from the mendeley-cli
package's guide (https://pypi.org/project/mendeley-cli), and the endpoints and flows from
Mendeley's JavaScript SDK (https://npmjs.com/package/@mendeley/api). The Worker's behaviour is
read from its code, symphony-app's signin/worker.js, as it is on 2026-10-19.

## What it does

A notebook's references come today from a citation manager's export, read by `notebook.py refs`
into references.json, one record per reference: key, title, authors, year, doi, venue, url and
uri (tools/notebook.py, `reference`). Mendeley adds a button on the Notebooks tab, "Import from
Mendeley", that fills the same file from the signed-in person's Mendeley library, with no export.

1. The press opens Mendeley's consent page, https://api.mendeley.com/oauth/authorize, with the
   app's client id, scope `all`, a random state and the control panel's own address as the
   redirect, as the Folders tab does for Microsoft.
2. Mendeley sends the person back to the panel with a code. The panel hands the code to the
   sign-in Worker, which exchanges it at https://api.mendeley.com/oauth/token with the client
   secret, the one thing the page cannot hold, and returns the access token. The Worker keeps
   nothing, as it keeps nothing for GitHub or Microsoft.
3. The panel reads https://api.mendeley.com/documents (view all, paged) as the person, maps each
   document to the record above, with the document's Mendeley address as its uri so a citation
   can name where it came from, and writes references.json to the notebook's private repository
   as the person, with the file's sha, as the tab writes notebooks.json.
4. The panel keeps no refresh token: the access token is dropped once the read ends, and the
   next import signs in again, which Mendeley answers without asking once consent is given.
   That keeps nothing of Mendeley's in the browser or on GitHub but the references themselves.

Citations stay Word's own or Zotero's fields, written by tools/docx_cite.py; Mendeley Cite keeps
its citations in an add-in store Mendeley does not document, so nothing writes them.

## The smallest change to the Worker

The Worker already serves any provider listed in its table PROVIDERS through /drive/config,
/drive/connect and /drive/token, with the token endpoint, the two variable names and the scope as
the only differences. So Mendeley is one more entry, tokenUrl
https://api.mendeley.com/oauth/token, id MENDELEY_CLIENT_ID, secret MENDELEY_CLIENT_SECRET, scope
`all`, rather than routes of its own, which keeps the code the Worker's tests already cover. The
brief named /mendeley/login and a callback; the entry does the same with less code, and the
redirect stays the panel's address, which the Worker already insists on. Not yet known, and the
first test once the app is registered: whether Mendeley accepts the PKCE verifier the Worker
sends with the code, or refuses an unknown parameter.

## Elsevier's terms

Mendeley is Elsevier's, so its data falls under the rule of 2026-10-19 for Elsevier's content:
Claude may read it, and it is never made public. The import writes only to a notebook's private
repository, the client secret stays in the Worker's settings, and no Mendeley token is written to
a URL, a log, a repository or the page's storage.

## The privacy statement first

A version of the Apps' privacy statement (symphony-start PRIVACY.md, then the site's page) says,
before the code ships: that the panel and the Worker, neither of them an App, talk to Mendeley
for the person who presses Import; what is read (the library's documents' metadata); where it is
written (references.json in the notebook's repository, as the person); that the Worker sees the
code and the access token once and keeps neither; and that nothing of it reaches the developer.
It takes the next free version when the work starts: 31 describes the Notebooks tab, and the Setup
App's token lending, if the owner says yes to it, may take 32 first.

## The owner's steps, when the owner chooses to start

1. Open https://dev.mendeley.com/myapps.html and sign in with the Mendeley (Elsevier) account.
   Press "Register a new app". Name: SymphonyBoard notebooks. Description: imports a person's
   Mendeley references into their notebook's private repository. Redirect URL:
   https://openspineconsortium.com/symphony/control/ exactly, with the final slash. Press
   "Generate secret" and copy the secret at once, then press "Submit". The field and button names
   are from a third-party guide; the live page may word them differently.
2. Open https://dash.cloudflare.com, then Workers and Pages, the Worker symphony-signin,
   Settings, Variables and Secrets. Press Add: type Secret, name MENDELEY_CLIENT_SECRET, value
   the secret. Press Add again: type Text, name MENDELEY_CLIENT_ID, value the app's id from
   the Mendeley page. Press Deploy. The secret goes into that field and nowhere else.
3. Tell the thread it is done. The code, its tests, the statement's version and the Worker's new
   code then follow in pull requests; the Worker's code is pasted into Cloudflare by the owner,
   as symphony-app's signin/README.md describes for each new version.
