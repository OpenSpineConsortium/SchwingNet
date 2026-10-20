# A low-latency interactive sandbox for the Symphony demo

Source: the thread "Capabilities demo and sandbox", 2026-10-20, from the owner's ask to build docs/start/capabilities.md into a full demo "perhaps even a google collab or some sort of cloud interactive sandbox environment", researched how to make one "super low latency, quick, and easy, maybe a github sandbox". GitHub's documentation was read from the github/docs repository on raw.githubusercontent.com, since docs.github.com is blocked from the cloud session; Pyodide's and JupyterLite's from their GitHub repositories. A line marked inferred rests on no source read.

## The answer in short

- The demo needs no Claude at all. The claim protocol's guarantees, a second claim refused, the push guard's refusals and the board, run in plain git and Python against a local bare repository, which applies the same non-fast-forward rule GitHub does. So no sandbox holds a Claude credential or an API key, as the project requires, and none has anything to spend.
- Built on 2026-10-20: `bash scripts/demo.sh` (about one second, offline), a third dev container configuration, `.devcontainer/demo/devcontainer.json`, beside the setup one and .devcontainer/token/, for a Codespace, and `docs/start/demo.ipynb` for Colab, which clones the public symphony-protocol at v0.5.1 and runs the same three parts. tests/test_demo.py runs the script in the required check.
- The binding limit is visibility, not speed. symphony-template is internal, so every sandbox that opens it, Codespaces, Colab and Binder alike, serves only people GitHub lets read it. A stranger's one-click demo has to open the public symphony-protocol; that is a change in that repository, proposed below and not made here.

## The options compared

| Option | First wait | Account | Real git | Private or internal repository |
| --- | --- | --- | --- | --- |
| scripts/demo.sh in a clone | about 1 s (measured in the cloud session) | none | yes | needs the clone |
| GitHub Codespaces, default image | about 45 s to a few minutes cold; 10 to 30 s with a prebuild (third-party reports, below) | GitHub | yes | only people with read access whom the organization's settings allow |
| Google Colab | seconds once a runtime connects (inferred) | Google; GitHub authorization for a private repository | yes on its Ubuntu VM (inferred) | each user ticks "Include Private Repos" and authorizes |
| Binder (mybinder.org) | 10 to 15 s with a cached image, up to about 3 min otherwise, longer after each new commit | none (inferred) | yes (inferred) | not supported |
| Pyodide or JupyterLite on a static page | about 0.5 to 1.3 s to load Pyodide's 5 to 7 MB core | none | no: subprocess cannot start git | not applicable |
| github.dev | instant | GitHub | no terminal, no compute | yes |
| Gitpod (now Ona), StackBlitz, Replit | varies | yes | Ona yes; StackBlitz's Python is experimental WASI | poor fit: moving product, Node first, or import by copy |

Sources:

- Codespaces links (`codespaces.new/OWNER/REPO`, `?quickstart=1`, the badge) and the "Share a deep link" option: github/docs content/codespaces/setting-up-your-project-for-codespaces/setting-up-your-repository/facilitating-quick-creation-and-resumption-of-codespaces.md. The page does not name the `devcontainer_path` parameter the capabilities page's link uses; it is the parameter GitHub's own deep links carry (inferred, see the owner's check below).
- Several configurations, one level under .devcontainer/, all offered in the create page's dropdown with `.devcontainer/devcontainer.json` preselected: content/codespaces/setting-up-your-project-for-codespaces/adding-a-dev-container-configuration/introduction-to-dev-containers.md. This is why adding the demo configuration leaves the setup Codespace of docs/setup/codespace.md as it was.
- Prebuilds run as Actions workflows on the owner's minutes, are suggested when creation takes over 2 minutes, and their storage is billed: content/codespaces/prebuilding-your-codespaces/about-github-codespaces-prebuilds.md.
- Billing: personal Free accounts get 120 core-hours and 15 GB-month a month, Pro 180 and 20; an organization gets none and pays only where it allows it, else the creator's quota pays: content/billing/concepts/product-billing/github-codespaces.md.
- Who may open one: content/codespaces/troubleshooting/troubleshooting-creation-and-deletion-of-codespaces.md.
- Lifecycle commands (postCreateCommand once, postStartCommand each start, postAttachCommand each attach): the dev container specification, devcontainers/spec docs/specs/devcontainer-reference.md.
- Cold-start figures: no GitHub figure exists; third-party reports at https://www.pgxn.org/dist/pg_durable/docs/CODESPACES_PREBUILDS.html and https://jacar.es/en/programming-with-github-codespaces/.
- Colab from GitHub and private repositories: googlecolab/colabtools notebooks/colab-github-demo.ipynb; Python 3.12 since 2025-08-27: https://developers.google.com/colab/release-notes.
- Pyodide's limits: pyodide/pyodide docs/usage/wasm-constraints.md; its load time: https://blog.pyodide.org/posts/0.23-release/. JupyterLite runs as static files: jupyterlite/jupyterlite README.md. isomorphic-git is git in JavaScript: isomorphic-git/isomorphic-git README.md.
- Binder: no private repositories, https://book.the-turing-way.org/communication/binder/zero-to-binder; start times, https://discourse.jupyter.org/t/variable-startup-times-with-a-rstudio-based-binder-example/9172.
- github.dev has no compute: content/codespaces/the-githubdev-web-based-editor.md.

## What was chosen, and why

1. **The script first.** Every sandbox below runs it, a reader with a clone needs nothing else, and the required check keeps it true. It writes only in a temporary folder and sets GIT_CONFIG_GLOBAL=/dev/null so it never reads or changes the reader's git settings.
2. **A Codespace for members.** The demo configuration uses Microsoft's Python 3.12 image, which has git, and runs the script on attach, so the terminal shows the demo when it opens. No prebuild: the image is stock and the script needs no install, so a prebuild would add Actions minutes and storage for little (inferred; add one if creation passes two minutes, as GitHub advises). Nothing in it asks for a sign-in, unlike the setup Codespace, which runs the token wizard.
3. **Colab for a notebook.** The notebook depends on nothing in the template: it clones the public library and carries its own board snapshot, so the same file works unchanged from symphony-protocol.
4. **No zero-wait page yet.** Pyodide would load in about a second, but git does not run in the browser, so the race would have to be simulated or rebuilt on isomorphic-git, and the guard reads git. A page on openspineconsortium.com is the Control panel sign-in thread's file to change, so it waits for that thread and the owner's word.

## What would make it one click for anyone

- Move or copy demo.ipynb into the public symphony-protocol, with an "Open in Colab" badge in its README (`https://colab.research.google.com/github/OpenSpineConsortium/symphony-protocol/blob/main/<path>`), and a `.devcontainer/devcontainer.json` there so a Codespace and Binder open it too. Binder then gives a demo with no account at all. That is a pull request in symphony-protocol, a public repository, so it is the owner's to approve.
- Later, a Pyodide page on the site for the board alone, which needs no git: edit the snapshot, see STATE.md change, in about a second.

## Checks the owner makes once

- Open the demo Codespace link on docs/start/capabilities.md and confirm the create page shows "Symphony demo" as the configuration; if it shows "Symphony setup", the `devcontainer_path` parameter was not honoured, and the link is rebuilt from the repository's Code button, Codespaces tab, the "..." menu, "New with options", then "Share a deep link".
- Open the Colab link and confirm it asks for GitHub authorization with private repositories and then runs; whether Colab's authorization covers an internal repository is inferred, not tested, and if the organization restricts third-party (OAuth) app access, Colab sees none of its repositories until an owner approves Colab under the organization's Settings, Third-party access.

## Follow-up: living documents for end users (2026-10-20)

The owner's follow-up the same day asked for something more end-user than a developer's sandbox: niche examples that use the specific features, a learn-by-doing tutorial for students and new users, the sandboxes baked into a professional documentation site, documentation kept current by the code as Javadoc comments are, and the accumulated unit tests linked from the docs. What was built, and why:

- Four lessons under docs/learn/ (a claim, the push guard, the board's sections, Overlaps), told as a course's students and teaching assistant, each command followed by the output it promises. tools/living_docs.py runs them in the required check, which is the doctest idea applied to shell lessons: an output that changes fails the pull request that changed it, so the lessons describe the vendored release and not the release they were written against.
- Each block runs in a bash of its own from the practice folder because a notebook's %%bash cells do; that one rule makes the generated Colab notebook the same commands as the page, and `check` refuses a notebook that drifts. The notebooks clone the public library at the vendored tag, so they need no access to the template.
- The Reference page is made from docstrings and script comments, the Javadoc equivalent available with the standard library alone (the writing rule allows no new dependency, which rules out Sphinx, MkDocs and pdoc), and `check` fails an undocumented module.
- The tests: every test any pull request added accumulates in tests/ (36 files and 1,128 tests on 2026-10-20), run by ci.yml on every pull request and push and rerunnable from its Run workflow button; the site's Tests page shows the results of the run that built it.
- Hosting: GitHub Pages from docs.yml, gated by the variable SYMPHONY_DOCS so a copy that never turns Pages on sees no failed run. The owner chose members-only Pages on this internal repository over a public home for now.
- Colab and the internal repository, from the owner's screenshot of the authorization page: the page Colab opened asked for the scope public_repo, and OpenSpineConsortium showed a Grant button not yet pressed. A public_repo token cannot read an internal repository, so Colab answers 404. Opening the notebook through File, Open notebook, GitHub with "Include private repos" ticked asks for the scope repo instead, and the organization must be granted on that page (inferred from GitHub's OAuth scopes; not yet confirmed by the owner).
