DICOM banks and leak checks: where DICOM is decoded, how NIH ChestX-ray14 is verified, when the leak checks run, where tests with optional dependencies go, and one CrossHair flake.

- DICOM decoding lives only in the train environment (pydicom and the pylibjpeg decoders); the default environment, which the gate runs in, never imports them.
- NIH ChestX-ray14 is verified against the Academic Torrents piece hashes, because NIH publishes no checksum for its archives.
- The leak checks (issue #9) run as grid/run-leaks.sh after stage 3 has finished, not inside grid/run-xray-chain.sh, since the array is sized by the shards on the volume (grid/README.md, The leak checks).
- The gate refuses a skipped test under tests/schwingnet, pytest.importorskip included, so a test that needs an optional dependency (numpy, Pillow, pydicom) goes under tests/ as a unittest module that skips where the dependency is missing, as tests/test_leaks_pipeline.py does.
- A CrossHair counterexample on catalog.changed_keys appeared once on CI and passed on the rerun; read a second failure there as real before calling it a flake again.
