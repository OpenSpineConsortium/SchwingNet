# Handoff: the auto-anatomist screen on gold tier 3, the Colab demo and the second screen's arms

Source: the thread "Restart the auto-anatomist probe", claude.ai project symphony_3, written at about 20:45 UTC on 2026-10-30 on the owner's order of 20:35 UTC to stop, push everything and hand off, with no further check or review. Confidential: it stays in SchwingNet. No secret, token or credential is in it.

## 1. What is merged

- SchwingNet #483 (main 69371c2): the screen as a launched flow, kind autoanatomist (flows/autoanatomist.py, grid/autoanatomist.sbatch, the gate word `autoanatomist <plan>`), under the frozen docs/research/autoanatomist-screen/PREREG.md, with bordercall vendored at afe1952 under grid/autoanatomist/.
- SchwingNet #500 (main 432489a, merged 19:08 UTC): every GPU part of the screen goes to the partition galhp (L40S), AUTOANATOMIST_PARTITION in grid/gate.sh, recorded as item 1 of docs/research/autoanatomist-screen/DEVIATIONS.md; the join's SUMMARY.md now carries the numbers its two plots draw. The PREREG, both plans and the vendored copy are unchanged.
- bordercall #40 (main a87e0b3): the auto-anatomist's blocks, session, calibration and fully latent objective (objective=mask). hpcworker #54 and symphony-template #511: the relays the gate words need.

## 2. The grid, as last read

- First smoke, job 40884715 (18:26 UTC, commit 69371c2): landed on voh5, a Tesla V100 of gvohp; both trials stopped at their first compile ("JaxRuntimeError: INTERNAL: Failed to get configs for: 46 out of 218 instructions", JAX 0.10.2's GPU compiler on Volta). Its report is kept on the grid as logs/AUTOANATOMIST-gold3_latent_smoke-40884715.md.
- Second smoke, job 40885678, sent at 19:12 UTC at commit 432489a by the gate's own resend of a plan that failed on older code; one GPU job on galhp, two trials (lambda_then_w_s1, null_s1) of 150 epochs in series, then the join. Not read since: the owner stopped all checks at 20:35 UTC.
- Next: send `schwingnet-autoanatomist-gold3_latent_smoke` through symphony-template's .github/workflows/grid-accounts.yml (workflow_dispatch on main, action=job, job=schwingnet-autoanatomist-gold3_latent_smoke) and read logs/job-schwingnet-autoanatomist-gold3_latent_smoke.json on symphony-template's branch grid about a minute later. Still queued or running: read it again later. Its report ends in "- exit 0": send `schwingnet-autoanatomist-gold3_latent_screen` (an array of eight trials on galhp and a CPU join), which the owner approved at 18:05 UTC ("assume I approve of whatever you need to get a training run on gold tier data going"). It failed: read its report, fix by pull request with item 2 of DEVIATIONS.md (candidates: XLA flags such as a lower GPU autotune level or Triton's GEMM off, or gmsap's H200), merge, and send the word again, which resends a plan that failed on older code once by itself.
- Since 2026-10-30 16:59 UTC the owner's rule is that a thread sends grid jobs within its agreed work without asking him first (project memory, MEMORY.md); the size rule still holds.

## 3. bordercall PR 48, a draft (branch claude/project-thread-5hj0q5, head 14b13c2)

- The Colab demo of the anneal on a slider (notebooks/anneal_demo.ipynb, autoanatomist/demo.py) with its test on five sets of new phantoms (the owner's ask of 17:11 UTC); main merged in at 58643a2; 14b13c2 trains again on the CPU at the CPU's widths when the GPU cannot compile the network, as the V100 could not and Colab's T4 (also before Ampere) may not. 168 auto-anatomist and demo tests passed after the merge, 70 of them the demo's.
- The four arms of a second screen the owner chose at 16:52 UTC (8e966e4): schedule=cyclic, schedule=adaptive, ladder=overlapping and restraint=abf, each a block that changes nothing unnamed, with 14 tests in tests/test_autoanatomist_arms.py. Under objective=mask the restraint acts on the target vertebra's predicted volume share against the clean mask's (what was promised to the owner).
- Open, not fixed (one review pass, unverified): (1) after a fallback, running setup again prints that it will train on the GPU and the run cell trains the GPU's widths on the CPU; fix: setup's line and WIDTHS also read JAX_PLATFORMS == "cpu", or run_demo sets WHY_CPU. (2) The fallback's notice quotes JAX's note about removed frames, not the error; fix: quote the line GPU_FAILURE matched, and add JAX's two note lines to GPU_STOP in the tests. (3) GPU_FAILURE is searched over every line, so an XLA warning line followed by an unrelated kill is retried on the CPU; fix: match only after the last traceback, never on a negative exit.
- The PR body is stale (68 tests, the Colab link at 1cb0e6d, nothing of the arms or the fallback): update it, then mark ready and merge once the owner wants the arms on main.

## 4. The second screen, not built in SchwingNet

- The first attempt added the arms to the first screen by editing its frozen PREREG, which CI's freeze check (flows/stage_registry.py frozen) refuses; it was withdrawn from #500 and is kept here as [second-screen-wip.patch](second-screen-wip.patch) (git format-patch against 69371c2, without the vendored copy, which tools/bordercall_vendor.py makes again from bordercall 8e966e4): plans gold3_latent_smoke2 (five trials in series) and gold3_latent_screen2 (twelve trials), tools/autoanatomist_plan.py write --plan, the report's and the join's changes, the gate's lists and their tests. Its PREREG section 8 must not be applied.
- The way that passes: the registry holds one PREREG per kind and one script per kind, so the second screen is a new kind (for example autoanatomist2): a line in flows/registry.txt; flows/autoanatomist2.py with its class and prereg_part (KIND is a module constant in flows/autoanatomist.py, used by hold_to_prereg and still_held, so make it overridable); its own sbatch naming `flows/launch.py autoanatomist2` (grid/autoanatomist.sbatch hardcodes docs/research/autoanatomist-screen and the kind); a new PREREG folder, frozen with sha256sum before any send, whose Covers line names the two plans' bytes; bordercall re-vendored at the merged commit that carries the arms; the gate's AUTOANATOMIST_COUNTED and AUTOANATOMIST_AFTER (smoke2 after the first smoke, screen2 after smoke2) for the new word; tests. Send it after the first screen's verdict.

## 5. Open questions for the owner

- The repository of the rendering session (for the 2-D synthetics), asked for and not yet given.

## 6. Files

- The shared project folder autoanatomist/ (the demo's test figure, the lambda-schedule figure answered to the owner's FEP question, the screen's flowchart record) is copied to ../project-files/autoanatomist/.
- Nothing of this thread is left only in a container: the branches above are pushed, the patch is here, and the scratch files of the session were tools for work now committed.
