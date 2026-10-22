The programme that carries the segmented CTs to X-ray (counting prior, renders, COBRA, harmonisation, the anomaly screener, the corner format) is docs/research/xr-from-3d/README.md with issues #56 to #70.

- The X-ray annotation format is four corners per body in a fixed order (superior-left, superior-right, inferior-right, inferior-left, head up), the level from catalog.LEVELS, the column call and findings once per image, every reader named, COCO keypoints as the export (docs/research/xr-annotation-format.md).
- Anomalies are labelled on CT and carried to X-ray: readers' column calls (scan, column, reader) feed tools/chain_stats.py --columns, and odds come only from collections screened whole.
- The counting prior's settings (scale, weight, margin) are chosen on validation frames only (tools/chain_eval.py).
- Variables beside the images come from tools/covariates.py, aggregates only, ages as decades.
- COBRA is CC BY-NC 4.0; commercial use is the owner's lawyer question.
- The screener (#64) runs over NHANES II's unannotated films first, the owner's choice of 2026-10-22; BUU-LSPINE is held (3,600 AP and lateral pairs), not requested.
