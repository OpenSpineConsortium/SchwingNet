# Deviations from FleXray's recipe and from PREREG.md

Source: the thread "Reproduce the FluXray dataset", 2026-10-29. The first heading lists where the reproduction cannot do what the FleXray paper (arXiv 2609.26756v2) did, each fixed in PREREG.md beside this file before any image was rendered and before any number was read, with its reason. The second lists every departure of the run from PREREG.md after its freeze, dated, in the order it was decided; a departure decided after a number was read says so.

## From the paper's recipe, fixed at the freeze

1. The filter's segmenter. The paper scores each edit with a U-Net trained on raw DRRs alone, which was not released. FleXray's member flux000, trained on no enhanced DRRs but on real X-rays too, is the nearest released stand-in and scores the paired filter here (README section 2). The share of edits it drops is reported against the paper's about 4 percent, and a very different share says the stand-in reads differently, so the kept set is not FluXray's.
2. The seeds. The paper gives none. Each edit's seed is schwingnet.realism.seed_for(subject, grid pose, arm), a digest, so a rerun draws the same noise; two arms are run so that what the noise alone moves is measured and a word that changes with the arm is not reported as a result.
3. The scale. FluXray holds 138,063 images; the reproduction draws 100 subjects and 4 poses each by a recorded seed, 400 samples and 800 edits, the plan's figure of 2026-10-26 (README section 7). So each pose group of the filter holds about 9 edits in place of about 1,534, and its q0.98 cut-off is noisier; the dropped share is read as description only.
4. The size compared. The paper edited at 1024 and stored FluXray at 256; the reproduction edits at 1024 and compares at 256, since nothing larger of FluXray exists.
5. The bars. The Lab Recipe asks that each bar come from a published value or a power calculation. The AUC lower bound of 0.6 and the MMD q of 0.05 are conventions this programme fixed on 2026-10-25 and 2026-10-26 and shares with the DRR domain-gap study; the geometry's 1 pixel is one pixel of FleXray's canvas; and 100 subjects is not a powered size. All were fixed before any number, and the report says so beside them.
6. Not in this count. The owner's count of 2026-10-29 02:35 UTC is three fetches and two GPU jobs, the edit and the statistics. No comparison with real X-rays or fluoroscopy is made (the DRR domain-gap study makes it), and the adapter's stages, lora and eval, are refused by the flow until they have a count of their own and are ported to the pipeline.

## From PREREG.md, after the freeze

None yet.
