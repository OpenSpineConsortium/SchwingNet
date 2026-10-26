---
name: schwingnet-pre-push-gate-duration
description: SchwingNet's pre-push hook re-proves every module (30+ min) on a branch that changed pyproject.toml, and refuses a push with untracked files; batch fixes into one push
metadata:
  type: project
---

SchwingNet's pre-push hook runs the whole beethoven-qa gate. When the branch changed pyproject.toml since it left main (as any branch that lists a new function under [tool.beethoven-qa.unproven] does), the gate says "proof: every module: pyproject.toml changed since <base>, and every proof reads it" and runs CrossHair over all ~120 contracted functions, 4 at a time, 20 s per condition: a push then takes 30 minutes or more in a cloud session, and every later push of the branch takes as long until it merges. The hook also refuses a push while the tree has anything uncommitted, untracked files included (the local .githooks/commit-msg in the coordinator's clone counts), so set such a file aside and put it back after.

**Why:** two pushes in a review round cost an hour of gate time; a thread that pushes, then fixes one review finding and pushes again, waits twice.

**How to apply:** finish the adversarial review and the local gate run (`python -m beethoven_qa gate --module <module>` in the venv) before the push, commit every fix, then push once in the background and open the draft PR when it lands.
