The sample index (tools/sample_index.py, grid/run-samples.sh): samples.sqlite under the data root's _samples/<run>/ pairs every held file with its format, size, shape, DICOM header and sidecar rows, and marks it annotated or not; it never leaves the grid, only MANIFEST.json and MANIFEST.md do.

- Roots come from data/reproduce/sources.json (raw locations of sources on disk), data/sources/ grid paths and every data-root folder without a leading underscore; a file belongs to the deepest root.
- DICOM headers are kept whole for projection images and the first slice of each cross-sectional series; sample_header gives each slice its series' header; ALL_SLICES=1 keeps every slice.
- Joins are by reduced name, digit runs of five or more, and DICOM UIDs or PatientID; a key more than twenty files carry names none. The link says which way it met.
- NHANES II is the owner's large unannotated X-ray set for the screener (#64), his word of 2026-10-21.
- The research and queries: docs/research/data-manifest/README.md.
- The first run (2026-10-22): 140 groups, 7,008,826 files, 7.3 TB, in docs/research/data-manifest/MANIFEST.md; the scan took 64 tasks of 8 to 97 minutes, the merge 5 hours and the manifest's queries another 5 (job 40703320), so the report step stays its own job (grid/run-samples.sh) and `samples` sent again starts a new census.
