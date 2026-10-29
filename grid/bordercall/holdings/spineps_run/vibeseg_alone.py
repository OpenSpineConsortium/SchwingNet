"""Run SPINEPS's spine-finding step (VIBESeg, as spineps.phase_pre.compute_crop calls it) on one input,
with or without fold_patch, and write its mask; for checking fold_patch against SPINEPS's own output.

    vibeseg_alone.py INPUT OUTFILE patched|original [THREADS]"""
import os
import resource
import sys
import time

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main(source, target, mode, threads):
    torch.set_num_threads(threads)
    if mode == "patched":
        import fold_patch
        fold_patch.install()
    from TPTBox import NII
    from TPTBox.segmentation import run_vibeseg
    started = time.time()
    run_vibeseg(NII.load(source, seg=False), target, dataset_id=100, ddevice="cpu")
    print("vibeseg", mode, "seconds", round(time.time() - started), "maxrss_mb",
          resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 4))
