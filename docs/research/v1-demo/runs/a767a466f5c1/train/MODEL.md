# SchwingNet v1, level stage

- Run: a767a466f5c1 (commit 11546b7e534e56ce89676da17034c1ede65caaaf, catalog sha256 9051dd4f7b35)
- Stage: level classifier over truth boxes; the detector stage is not in this checkpoint.
- Architecture: torchvision resnet18, 27-way head, crops 64x64, pad 0.15.
- Initial weights: none (from scratch).
- Seed 1; epochs 4; batch 64; device cpu.
- Training crops 4840 from 54 persons; validation crops 546 from 6 persons; no test row was read.
- Best epoch 2: validation accuracy 0.993 (0.981 to 0.997, n=546).
- Checkpoint best.pt sha256 c9e4712f8ccf1b8ab22bf38f86d39e48a86dc5a1b4f77405b4ca36d0c9c0c8e2; wall time 134 s.
- Levels: C1, C2, C3, C4, C5, C6, C7, T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, L1, L2, L3, L4, L5, L6, sacrum; transitional T13, L6.

Every number above is reproduced by tools/flow.py run with the same catalog, commit and seed.
