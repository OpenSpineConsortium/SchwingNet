# The site's Docs tab and its navigation

Source: the thread "Site docs and navigation" of the project chat, 2026-10-18, from the owner's
message of that day ("i need a continually and automatically updating documentation section on
the website, also the damn control panel isnt even reachable from teh site, make sure all pages
are"). The work is in OpenSpineConsortium/openspineconsortium.github.io, pull requests #29 and
#32.

## What was wrong

- The control panel, /symphony/control/, and the Tokens page were `hidden=True` in the site map
  (`SITE` in the site's tools/build_site.py), so neither was in the header, the Symphony strip or
  the footer; the panel was reached only from a button low on the Symphony page, and the Tokens
  page only from the panel. Two maintainer pages, /beethoven/admin.html and
  /beethoven/storage.html, were in no navigation at all, by design.
- The build's reachability check skipped hidden pages and only noted, never failed on, an HTML
  file on disk outside the site map, so nothing stopped the next page going missing.
- Every build failed: symphony-start's PRIVACY.md (version 11) writes "<your login>", which pandoc
  passed through as an HTML tag, so the live Apps privacy page had lost those words and the
  word-for-word check refused it. Site #29 renders the statements with pandoc's raw_html off; no
  statement uses raw HTML.

## What the site does now

- The control panel and the Tokens page are pills in the Symphony strip and lines in the footer.
  They keep `robots: noindex`, and the build now leaves any noindex page out of the sitemap.
- A Docs tab, /docs/, is written by the same build that writes every other page, from what the
  build already reads, so it cannot fall behind a page: the products with their versions (read
  from the sibling repositories at build time, or from GitHub in the browser for the protocol's
  latest published release and the plugin), every page in the site map, hidden ones included,
  with its description and tags (signs in, reached by a link, kept out of search),
  /docs/buttons.html with every button on every page (read from the bodies, and from a page's own
  script where it makes buttons through a `btn('...')` helper), and /docs/changes.html with each
  product's change notes, the "Version N ..." paragraphs of the privacy statement it ships with.
- What's new also lists the pull requests merged in the last 30 days in the public repositories
  (the site, symphony-start, symphony-protocol, symphony-marketplace), read by the visitor's
  browser from GitHub's public API with no token; it keeps each answer in the tab for ten
  minutes, since GitHub allows 60 unauthenticated reads an hour from one address.
- The build fails when any page in the site map, hidden or not, is more than two clicks from the
  header and footer, and when an HTML file is on disk outside the site map. Pages other threads
  add (the comparison and use-case pages, the panel's Folders page) appear in the Docs tab by
  themselves once they are in `SITE`.

## Decisions and why

- No GitHub Actions workflow rebuilds the site. The build needs beethoven-extension and
  beethoven-vscode (private) and symphony-extension (internal) beside it, which the site's own
  GITHUB_TOKEN cannot read, and a new token was to be avoided. Since every change to the site
  goes through the build, the docs are rewritten with every change; what changes elsewhere
  without a site build (merged pull requests, the protocol's release, the plugin's version) is
  read live in the browser.
- Only public repositories feed What's new, since the site is public; coordbench and flowbench are
  left out because their pull request titles can carry benchmark numbers, which stay unpublished
  until the owner lifts that hold. Beethoven appears only through its version and its privacy
  statement's own change notes, both already on the site.

## What is not covered

- A statement that changes in its own repository reaches the site only at the next site build;
  the build fails until then, which is what showed the stale Beethoven statement 17 on
  2026-10-18.
- Buttons an extension draws in its own popup are not on the site and are not listed.
- The Docs landing page links the two maintainer pages, /beethoven/admin.html and
  /beethoven/storage.html, which no page linked before; both are noindex and work only for those
  the access service allows. The owner asked for every page to be reachable; one word takes them
  back out of the list (`docs_pages` skipping hidden nodes and the two-click check with it).
- An adversarial review of #32 found the live list caching whole pull requests (about 3 MB per
  tab, past which every reload asked GitHub again), stopping at 50 pull requests a repository,
  a shared script's buttons listed on every page that loads it, icon buttons named by their
  glyph, and Symphony for Chrome's change notes, written as one sentence, missed; all are fixed
  in #32's second commit.

## Later the same day: the strip

- Site #35 put the Symphony strip back on the control panel, Tokens and cost pages, which had set
  `strip: no` and so left greg no way back to the other Symphony pages.
- Site #41 then followed greg's ask that only the top bar show, with a tab's pages dropping down
  while the pointer is on the tab, as apple.com does: every page carries every section's strip
  after the header, hidden on a computer with a mouse until a tab is hovered or focused, and laid
  over the page so a full-screen console under it never moves; a phone or tablet, which cannot
  hover, keeps the current section's strip in the page. The mode is chosen by a class the header
  block sets before anything is drawn, so the strip never flashes and vanishes.
