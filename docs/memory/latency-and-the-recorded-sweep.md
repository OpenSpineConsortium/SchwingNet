Latency, ONNX parity and the recorded sweep (task #13): tools/latency.py and tools/sweep.py, the rules in src/schwingnet/latency.py and sweep.py, the grid jobs in grid/run-latency-sweep.sh.

- A latency number exists only for a runtime whose parity passed for the same ONNX file (labels equal, probabilities within 1e-5, on validation crops); the budget is 97 ms, one frame of C-ArmLSpine's 10.3 fps sweeps, and "real-time" means p95 strictly under it.
- Each arm writes latency/<arm>.json in the run directory; evaluate/latency.json is the fastest arm whose parity holds, under the keys the evaluation page of #12 reads.
- Version 1 has no detector, so a sweep's boxes are truth boxes, written one JSON line per frame, and the overlay says so on every frame.
- tests/test_latency_tools.py runs only in the train-cpu environment (`pixi run -e train-cpu python -m unittest tests.test_latency_tools`); under plain python3 it skips.
- docs/research/latency-and-sweep/README.md holds the dry run, the grid commands and the resource estimate.
