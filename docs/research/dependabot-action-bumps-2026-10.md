# Three Dependabot action bumps, checked before merging

The thread "Dependabot action updates", 2026-10-18, on symphony-template #111, #112 and #113,
opened by Dependabot on 2026-10-16. Source: each action's own repository, cloned from github.com
on 2026-10-18 (action.yml at each major tag, the README's "what's new" and "breaking changes"
sections, and the commit log between the majors), and the template's workflows on main at
131be74. Every workflow an adoption copies is the template's own file, so the uses below are
every use in an adopted repository too.

## actions/upload-artifact 4 to 7 (#111)

Used in grid.yml at v4 with name, path and retention-days; claude.yml, coordinator.yml, pool.yml
and workers.yml already use v7. v5 and v6 move the runtime to Node 24, which needs runner
2.327.1 or later; v7 adds the input archive, default true, which keeps the old behaviour of
zipping what is uploaded. No input grid.yml passes changed. The grid's runner is GitHub's own
image, and its chain stops by itself when GitHub asks for a newer runner than the image holds
(docs/setup/grid.md), so it never runs below the version GitHub accepts. Safe.

## actions/setup-python 5 to 7 (#112)

Used in grid.yml with python-version "3.12". v6 moves to Node 24 (runner 2.327.1, as above) and
adds pip-version; v7 moves the internals to ESM, removes the pip-install input added in 6.x and
drops end-of-life Pythons; 3.12 is not one. ci.yml's comment named v5 as the version to swap
in, and now names v7. Safe.

## actions/create-github-app-token 1 to 3 (#113)

Used in template-init.yml with app-id and private-key, under continue-on-error. v2 removes the
underscore inputs app_id and private_key, which the template never used; v3 moves to Node 24
and handles a proxy only where NODE_USE_ENV_PROXY is set, which matters only on a self-hosted
runner behind a proxy, and template-init runs on ubuntu-latest. Later 3.x releases add
client-id and mark app-id deprecated, still read as the fallback (main.js reads client-id, else
app-id), so the run gives a deprecation warning and works; the output token is unchanged. Safe;
moving to client-id would need the App's client id beside SDLC_APP_ID and is left for a change
of its own.
