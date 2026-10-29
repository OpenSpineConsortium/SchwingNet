"""Hold one fold's prediction in memory at a time when TPTBox's nnU-Net predictor ensembles folds.

TPTBox 1.1.0's nnUNetPredictor.predict_logits_from_preprocessed_data keeps the running sum of the
folds' logits while the next fold's sliding window runs, so with VIBESeg's 73 classes and three folds
two full-volume logit arrays sit beside each tile's forward pass; on CPU that passed the container's
14.3 GB for verse108 and verse649. This replacement writes each fold's logits to a file as they come
and sums them only after the last fold, in the same order, dtype and arithmetic (the first fold, then
+= each later one in half precision, then /= the count), so its output is the original's bit for bit;
a model of one fold is left to the original. install() is called before SPINEPS loads its models.
The folds go to FOLD_PATCH_DIR, else the system's temporary folder: a folder with room for three
folds' logits, several GB on a large field."""
import gc
import os
import tempfile

import numpy as np
import torch

FOLDS = None
_original = None


def _load_fold(predictor, idx, params):
    if predictor.loaded_networks is not None:
        return predictor.loaded_networks[idx]
    from torch._dynamo import OptimizedModule
    target = predictor.network._orig_mod if isinstance(predictor.network, OptimizedModule) else predictor.network
    target.load_state_dict(params)
    return None


def folds_on_disk(self, data, attempts=10, **kwargs):
    if len(self.list_of_parameters) < 2:
        return _original(self, data, attempts=attempts, **kwargs)
    folder = tempfile.mkdtemp(prefix="folds-", dir=os.environ.get("FOLD_PATCH_DIR", FOLDS))
    paths = []
    try:
        with torch.inference_mode():
            for idx, params in enumerate(self.list_of_parameters):
                network = _load_fold(self, idx, params)
                new = self.predict_sliding_window_return_logits(data, network=network, idx=idx, **kwargs).to("cpu")
                path = os.path.join(folder, "fold%d.npy" % idx)
                np.save(path, new.numpy())
                paths.append(path)
                del new
                gc.collect()
            prediction = torch.from_numpy(np.load(paths[0]))
            for path in paths[1:]:
                prediction += torch.from_numpy(np.load(path))
            prediction /= len(paths)
        return prediction
    finally:
        for path in paths:
            os.remove(path)
        os.rmdir(folder)


def install():
    global _original
    from TPTBox.segmentation.nnUnet_utils.predictor import nnUNetPredictor
    if _original is None:
        _original = nnUNetPredictor.predict_logits_from_preprocessed_data
        nnUNetPredictor.predict_logits_from_preprocessed_data = folds_on_disk
