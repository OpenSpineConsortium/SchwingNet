---
name: verse-masks-on-grid
description: VerSe's 374 chosen masks as lossless int16 copies, carried to the grid's data root as verse_masks_2026_10_29 on 2026-10-29 (SchwingNet #460); use them instead of re-downloading VerSe's float64 files
metadata:
  type: project
  modified: 2026-10-29T14:11:54.838Z
---

On greg's word of 2026-10-29 12:53 UTC ("Make sure to save those masks if that is a better more efficient storage format, you can put in grid"), the thread "Benchmark VerSe heights against fracture grades" carried VerSe's masks to the grid.

- Landing: data root `verse_masks_2026_10_29` (0700, meta/CARRIED), landed and checked 14:11 UTC 2026-10-29 by `schwingnet-fetch-verse_masks_2026_10_29` (request carry-verse-masks-2026-10-29-1410); no job queued.
- Contents: masks/<series>.nii.gz for the 374 series OUT.jsonl chose (/mnt/project-files/gold3-ct/verse-read-2026-10-29/), 365 int16 copies of VerSe's float64 files and 9 integer files as published; MANIFEST.csv (source name, bytes, sha256 per file), to_int16.py, README.md, SHA256SUMS. 378 files, 387,949,238 bytes.
- Lossless: every voxel checked whole and in range, reloaded copy compared voxel and affine for affine; two masks measured by morphometry both ways gave identical rows.
- Why int16: 29 per cent of VerSe's bytes on disk (387,805,416 vs 1,320,467,690) and a quarter of the memory loaded; VerSe's float64 verse602 does not fit 15 GB through scanimport's reader.
- Carrier: bordercall branch claude/project-thread-6vy0yb at 27d84df (never merged; greg may delete it now the landing is checked). Record: SchwingNet grid/carry/verse_masks_2026_10_29.txt (#460, merged 14:08 UTC).
- The 99 series in both releases are carried once; the other copy is in OUT.jsonl.

**Why:** a later thread needing VerSe masks should read these, not fetch 1.43 GB again.
**How to apply:** run morphometry or holdings on the landing with --scheme verse. See [[grid-words-and-counts]], [[morphometry-state]].
