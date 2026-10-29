# Gold Tier 3 CT

The private page for the gold tier 3 CT dataset (the owner's ask of 2026-10-27 22:49 UTC, thread "Finish scan import and tier counts"), published on 2026-10-28 at https://claude.ai/artifact/XDGjjGKVcdi2xDht7a689w from the gschwing account, private and never shared by link.

- index.html is the published page: template.html with page-data.json and the build's data written in by build_page.py.
- views/ holds one picture per reader-bench study, the front and side projections of its published masks side by side, and <id>r.png for each repaired mask; they are drawn by bordercall's holdings/enhance_views.py from the masks.
- The store is not kept here. The page reads gold3-000001-<hash>-page-copy.zip.json, the store with its grid locations and the anomaly route's notes taken out, zipped and carried as base64 in JSON because an artifact serves no archive type. To publish the page again, build the store (`python3 tools/gold3_ct.py build --root <folder outside the repository>`), then

      python3 artifacts/gold-tier-3-ct-xdgjjg/build_page.py --page-data docs/research/gold3-ct/page-data.json \
        --store <root>/versions/gold3-NNNNNN-<hash>.sqlite --views <enhance_views output> --rep-views <repaired views> \
        --template artifacts/gold-tier-3-ct-xdgjjg/template.html --source "<commits>" --expect-bench 191 --out <folder>

  and publish <folder>/index.html with views/ and the .zip.json beside it, with the capabilities db (rules: root read view, write owner; verdicts read view, write owner; verdicts/{self} write interact), user (scope profile) and downloads. build_page.py needs Pillow, so it runs where the views were drawn, not in this repository's checks, and it refuses to write a page or a store copy that still holds a grid path or a method name.
- The reader verdicts live in the page's own store, one document per reader in the collection verdicts: {reader, items: {item: {verdict, call, note, utc}}}, verdict one of true_anomaly, labelling_error, not_anomaly, needs_ct. Read them with the Artifact database tool (list on verdicts) or the page's "Download the verdicts (JSON)". Nothing yet moves them into the store's qa_review table, so no study is reader confirmed until that step is built.
