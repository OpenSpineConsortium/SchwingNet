---
name: schwingnet-pre-push-gate-duration
description: SchwingNet's pre-push hook re-proves every module (30+ min) when the change reaches every module (since 10.0.0 no longer for an unproven line), and refuses a push with untracked files; batch fixes into one push
metadata:
  type: project
---

SchwingNet's pre-push hook runs the whole beethoven-qa gate. When the branch changed pyproject.toml since it left main (as any branch that lists a new function under [tool.beethoven-qa.unproven] does), the gate says "proof: every module: pyproject.toml changed since <base>, and every proof reads it" and runs CrossHair over all ~120 contracted functions, 4 at a time, 20 s per condition: a push then takes 30 minutes or more in a cloud session, and every later push of the branch takes as long until it merges. The hook also refuses a push while the tree has anything uncommitted, untracked files included (the local .githooks/commit-msg in the coordinator's clone counts), so set such a file aside and put it back after.

Measured 2026-10-26 on #401 (a757a11): every gate step but the symbolic one took 44 s; the symbolic step proves 533 conditions in 17 modules when pyproject.toml changed (533 x 20 s / 4 = about 44 min, the daily full proof on main took 34 min), against 166 conditions for the four modules the branch touched. Most other PRs' gate runs took under a minute. The owner asked why (11:05 UTC). FIXED the same day: beethoven-qa 10.0.0, in SchwingNet main since #413 (19:40 UTC), reads pyproject.toml by its keys, so an unproven entry added or reworded proves nothing; the owner confirmed that rule alone (decision card, option A, 2026-10-27 03:08 UTC). The full proof now comes only from a changed module, pixi.toml/pixi.lock, the pinned copy or another pyproject key. See [[beethoven-qa-10-pyproject-by-key]].

**Why:** two pushes in a review round cost an hour of gate time; a thread that pushes, then fixes one review finding and pushes again, waits twice.

**How to apply:** finish the adversarial review and the local gate run (`python -m beethoven_qa gate --module <module>` in the venv) before the push, commit every fix, then push once in the background and open the draft PR when it lands.
