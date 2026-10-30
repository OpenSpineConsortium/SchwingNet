# Latent-prior evaluation: test reserve, repeat groups and parts

Written 2026-10-30 by the thread "Plan evaluating latent shape priors against explainable metrics" (bordercall PR 45,
research_notes/latent-shape-prior-evaluation/, where the same files are committed under reserve/). Drawn at SchwingNet
3abc2fa from the gold tier 3 export (sha256 ac95c7c1...). The rule of record is draw_test_reserve.py's docstring;
reserve-report.json pins every input and both outputs by sha256 and gives every count.

greg's rule of 2026-10-30 09:43 UTC is in it: every class belongs to a family, read ribs first (four lumbar, six
lumbar, T13, thoracic rib anomaly; normal; unread); the first run (smoke and screen) trains, validates and tests on
normal spines alone, the ENHANCE.PET normals the masks confirm plus VerSe's read normals whose masks draw L5; each
anomaly stratum lies inside one family and is split across test and train, never validation. greg chose at 10:03
UTC that the full run also trains on the anomaly train part. The rule left both files below byte for byte as they were.

- latent-prior-test-reserve.json: 584 studies, in data/splits/test-persons.json's form plus a "class" key ("person",
  "why", "class"). A run whose checkpoint the evaluation may start from leaves every listed person out of train and
  validation, matching the export's person field by exact string.
  sha256 cd9ddfedebc41789be32e2405c8088615eaf5a94d0a1559f7d04fee473c7cca6
- latent-prior-repeat-groups.json: the 85 units of more than one study (probable repeat scans of one patient), by the
  export's person keys; keep each in one part.
  sha256 a45797c39fe8cacbb9dd1d5db11dd3aee01824b6a9d34be5dc905b983faf91cb
- parts-0.2.jsonl and parts-0.3.jsonl: the evaluation's own part, unit, family, unit family and first-run flag for every
  study at each test share. At 0.2 the first run is 1,060 units (1,157 studies): 732 train, 124 validation, 204 test.
- draw_test_reserve.py: the generator, stdlib Python; rerun it at any new SchwingNet commit before freezing a PREREG.

At 3abc2fa: 424 normal ENHANCE.PET persons reserved, 354 of them confirmed by the masks, so the annealer's pool of
1,155 confirmed normal ENHANCE.PET persons keeps 801 (671 train, 130 validation by the export's part). All fourteen
checks in the report pass.
