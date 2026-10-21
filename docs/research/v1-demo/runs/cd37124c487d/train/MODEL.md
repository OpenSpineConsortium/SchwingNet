# SchwingNet v1, level stage

- Run: cd37124c487d (commit cf0d3f03d5d974d84e7d026a993ba14503664878, catalog sha256 5adfe5ec5715)
- Stage: level classifier over truth boxes; the detector stage is not in this checkpoint.
- Architecture: torchvision resnet18, 27-way head, crops 64x64, pad 0.15.
- Initial weights: none (from scratch).
- Seed 1; epochs 4; batch 64; device cpu.
- Training crops 2728 from 34 persons; validation crops 472 from 6 persons; no test row was read.
- Best epoch 4: validation accuracy 0.996 (0.985 to 0.999, n=472).
- Checkpoint best.pt sha256 9fdffa7cf6308d5a88477f9ba12ff05012f9f532fd8ccf9ecff3b9067bcc0e6e; wall time 88 s.
- Levels: C1, C2, C3, C4, C5, C6, C7, T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, L1, L2, L3, L4, L5, L6, sacrum; transitional T13, L6.

Every number above is reproduced by tools/flow.py run with the same catalog, commit and seed.
