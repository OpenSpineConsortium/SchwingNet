# Pre-registration: the QA loop with a transformer encoder

Covers: qa_transformer=110404f720cad73f69d0b5c62d5bc94358ad7c3e18a1ab3279813e98bdd7597b

Source: the thread "Try a transformer-based vertebra model", 2026-10-31, on the owner's ask of 04:41 UTC that night: "also please look into a transformer based approach as they say, transformers are all you need". The protocol is the Lab Recipe (artifacts/the-lab-recipe-1t2gvp/index.md, "Pre-register and freeze") and the owner's rule of 2026-10-29 that every deep learning job on the grid runs on a launched flow under a frozen pre-registration. Label: confidential-method; the landmark direction stays private.

This file is frozen. It was written before any job of its plan was queued on the grid. Its one plan, grid/qaloop/qa_transformer.json, is covered by its bytes on the line above. Every departure after the freeze goes in DEVIATIONS.md beside this file, dated, with its reason.

## 1. What this design is

The QA loop's design, docs/research/qa-loop/PREREG.md as frozen with sha256 c588988049e1c983ee551f9d5c1177f0b8c7db8083bf2dfd73bea6a656e9da55, is adopted whole: its question, population and inputs, checkpoints and bars, controller, failures and verdict, analysis plan and known limits (its sections 1 to 6) hold here word for word. That file is frozen and is never edited, so this design is a file of its own, run by the flow under the kind qaloop_tx (flows/qaloop_tx.py, the loop's flow under another kind, grid/qaloop_tx.sbatch).

## 2. The one change

The plan qa_transformer is the loop's plan qa_loop as it stood on main at e16ca41 (sha256 fb9814c62144d10baf87d9ff9d934afeed7bd947fd6320143b476e2044127217), with one word more, architecture=transunet, and its own plan id and purpose line. Every bar, prior, measure, limit, watch setting and the controller are qa_loop's.

architecture=transunet is the auto-anatomist's TransUNet (bordercall #65, vendored at grid/autoanatomist/ by SchwingNet #525): the residual-unet's three strided residual blocks, then four pre-norm transformer layers over the eighth scale's voxels as tokens (a learnt position each, up to four heads, a perceptron twice as wide), added to the bottleneck; the residual-unet's decoder. So the two chains differ in the encoder alone, and their records are read side by side.

## 3. The comparison, stated before the run

The question is whether attention at the bottleneck changes what the loop reaches. The gates that read the network are convergence and anomaly (Dice, named right, probe recall); the fingerprint, presence, real naming and latency read the oracle's landmarks and the namer, not the network, so they are expected to be the same in both chains up to the controller's path. The comparison is descriptive: each chain's verdict and its rounds' measures, with their intervals, beside the other's. No claim that one encoder is better is made unless its interval clears the other's on the same gate rows, and none is made from a chain that ended failed or stopped.

Known limits, beyond those of the loop's PREREG section 6:
- The plan keeps qa_loop's optimiser, learning rate and schedule, which were chosen for the residual U-Net; a transformer often wants a warm-up, so a worse result here may be the schedule's and not the encoder's.
- The learnt positions are tied to the crop's shape, as every architecture's bottleneck is.
- The transformer has more parameters (874,282 against the residual U-Net's 579,230 at these widths under the mask objective), so a gain may be capacity and not attention.

## 4. Freeze

`sha256sum PREREG.md > PREREG.md.sha256` in this folder, both committed with the plan the Covers line names; the launcher refuses a run whose PREREG or plan moved (exit 90), and the job script checks the hash on its node before it reads anything.

First frozen on 2026-10-31, before any job of the plan was queued on the grid.
