# The first prompt for the next account

Written on the owner's word of 2026-10-30 at 20:24 UTC ("please write the first prompt for the new account"). Paste the text below as the first message of the new account's session, with OpenSpineConsortium/SchwingNet and OpenSpineConsortium/bordercall attached.

---

Continue the thread "Run morphometry on gold tier 3 masks" (claude.ai project symphony_5, handed off on 2026-10-30 at 20:30 UTC). Work in OpenSpineConsortium/SchwingNet and OpenSpineConsortium/bordercall on the existing branch claude/project-thread-gv744i in both. Its draft pull requests are SchwingNet #501 and bordercall #49. Do not start new branches for this work.

Read these first, in this order:

1. SchwingNet docs/checkpoints/2026-10-30-morphometry-lines/HANDOFF.md, on that branch. Its section 3 is the work, in order.
2. bordercall research_notes/morphometry/handoff.md, entry of 20:30 UTC, on that branch, and the research note's section "Carrying the lines onto FleXray's X-rays".
3. bordercall research_notes/morphometry/session-2026-10-30/README.md. This holds the old session's own files:
   - environments/fxr-venv.txt is the FleXray 1.0.2 environment that Live needs;
   - scratchpad/mutx/ is the mutant harness;
   - MANIFEST.tsv lists every file, pushed or not.
4. My standing rules: SchwingNet docs/checkpoints/2026-10-30-morphometry-lines/memory/ and docs/checkpoints/2026-10-29-final/memory/.

These holds stand until I lift them:

- Send no grid job, read no grid report and make no plot. My count of 14:33 UTC, "Three: enhance, verse, covariates", is held until I finish a resynthesis.
- Every grid job needs my word and the number of jobs, and the size rule applies.
- Never run archived code.
- Test what a change touches before pushing.
- Nothing public, and no usage credits.
- Ask me before merging anything.

Start here:

a. SchwingNet #501:
   - read its CI and fix what fails;
   - run `bash scripts/check.sh` in a throwaway copy;
   - write an adversarial review of the gate fixes and the merge into the body's "## Adversarial review" section;
   - only then ask me about marking it ready.
b. bordercall #49:
   - build the FleXray environment from environments/fxr-venv.txt;
   - run morphoview's three test modules with Live;
   - run mutants over projection.py, shapes.py and the project command;
   - write an adversarial review, then fix what holds up.
c. Settle the two cameras. bordercall's main now holds autoanatomist/project.py, on nanoDRR 0.1.7. Our camera, morphoview/projection.py, is FleXray 1.0.2 on nanoDRR 0.1.5. Find out which nanoDRR SchwingNet's renders run on, then make the two one camera held to one record.

Then do the rest of the handoff's section 3. Tell me what you find before any step that cannot be undone.
