# Handoff: transformer models for the auto-anatomist (2026-10-31)

Source: the thread "Look into a transformer approach" of the claude.ai project, greg's ask of 2026-10-31 04:41 UTC ("also please look into a transformer based approach as they say, transformers are all you need"), handed off at greg's word of 14:24 UTC for local continuation.

## Done, all merged

- Research: docs/research/transformer-vertebra-models.md (SchwingNet #525): Spine-Transformers, UNETR and Swin UNETR, DETR-style level queries, a column transformer, and why the first step is a transformer encoder in the existing auto-anatomist.
- Models: bordercall #65 (merge 5bcd260) adds two architectures to autoanatomist/model.py ARCHITECTURES: `transunet` (three residual blocks, then a 4-layer transformer over the 1/8 tokens, added back to the features) and `unetr` (patch-8 embedding, 6 layers, skips read from layers 2 and 4); 868,766 and 906,334 parameters against the residual U-Net's 579,230 at default widths. Vendored into SchwingNet grid/autoanatomist/ at 5bcd260 by #525.
- QA-loop plan: SchwingNet #529 (merge d629a8c): grid/qaloop/qa_transformer.json is qa_loop.json with `architecture=transunet`, run as its own launched-flow kind `qaloop_tx` (flows/qaloop_tx.py, grid/qaloop_tx.sbatch, flows/registry.txt, tools/run_code.py, grid/gate.sh QALOOP_TX_PLANS and qaloop_kind, tools/qaloop_report.py DESIGNS) under its own frozen docs/research/qa-loop-transformer/PREREG.md, since the loop's PREREG is frozen on main and the registry refuses an edit to it.

## Not done

- `qaloop qa_transformer` has not been sent to the grid. No grid job of this thread exists. It waited on two things: the QA thread's qa_smoke chain 40903176 ending in exit 0 (docs/research/qa-loop/README.md), and GitHub Actions, which refused jobs from about 06:20 UTC for billing until greg reloaded the minutes.
- Unetr has no plan yet; it trains through the same words (`architecture=unetr`) and would need a plan and a PREREG of its own, as qaloop_tx shows.

## Next steps

1. Check the smoke: `job=schwingnet-status` through the route below, or `squeue -u go2432` on the grid. Send qa_transformer only after qa_smoke ended 0 (a broken loop would fail both chains the same way).
2. Send: from a local clone, `bash grid/gate.sh qaloop qa_transformer` on the grid's login node is the word itself; through GitHub it is symphony-template's .github/workflows/grid-accounts.yml, workflow_dispatch on main, inputs action=job, job=schwingnet-qaloop-qa_transformer, request=a label of your own; the answer lands on symphony-template's branch grid at logs/job-schwingnet-qaloop-qa_transformer.json. The chain is six 12-hour links on galhp (or galhp,gmsap once the QA thread's #530 and hpcworker #57 land).
3. Watch: the chain file logs/QALOOP-qa_transformer.chain and $QALOOP_ROOT/qa_transformer/<chain>/ (ENDED.json, the cards), and compare with qa_loop by the comparison PREREG.md section "Comparison" fixed before the run.
