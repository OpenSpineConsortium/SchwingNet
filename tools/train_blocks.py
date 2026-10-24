"""The torch side of the trainer's building blocks (src/schwingnet/blocks.py), one function per name.

Each part of training a run can swap has a table here keyed by the names blocks.py allows:
NORMALISERS, AUGMENTERS, OPTIMISERS and SAMPLERS, and tests/test_train_blocks.py fails when a table
and its tuple in blocks.py disagree. A new way of doing a part is one name in blocks.py and one
function in the table here; tools/train.py calls only the tables, so it never changes for one.

Every random draw takes the run's own generator, on the CPU, so a run's draws are fixed by its
seed whatever the device; and DEFAULT draws nothing beyond what version 1's trainer drew, so a run
naming no block trains to the same weights as before.
"""

import math

import torch
from torch import nn
from torch.nn import functional as F

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

# How far each training-time change reaches; small, since each is a picture the C-arm could give.
JITTER_SHIFT = 0.06
JITTER_SCALE = 0.08
GAMMA = (0.7, 1.4)
CONTRAST = (0.8, 1.2)
BRIGHTNESS = 0.08
BLUR_SIGMA = (0.0, 1.0)
NOISE_LEVEL = 0.04


def _uniform(generator, count, low, high):
    return low + (high - low) * torch.rand(count, generator=generator)


def _imagenet_hook(module, args):
    """Scale a grey 0..1 batch by ImageNet's mean and spread, inside the model, so the evaluator,
    the latency tool and the ONNX export, which all call the model, scale it the same way."""
    (batch,) = args
    mean = torch.tensor(IMAGENET_MEAN, dtype=batch.dtype, device=batch.device).view(1, 3, 1, 1)
    std = torch.tensor(IMAGENET_STD, dtype=batch.dtype, device=batch.device).view(1, 3, 1, 1)
    return ((batch - mean) / std,)


def normalise_none(model):
    return model


def normalise_imagenet(model):
    """A forward pre-hook rather than a layer, so the weights' names stay version 1's and every
    checkpoint loads into either kind of model."""
    model.register_forward_pre_hook(_imagenet_hook)
    return model


NORMALISERS = {"none": normalise_none, "imagenet": normalise_imagenet}


def box_jitter(batch, generator):
    """Each crop moved and resized a little, as a tracker's or a detector's box would be: an
    affine resample of the padded crop, its edge repeated where the move uncovers it."""
    count = batch.shape[0]
    scale = 1.0 + _uniform(generator, count, -JITTER_SCALE, JITTER_SCALE)
    shift = _uniform(generator, count * 2, -JITTER_SHIFT, JITTER_SHIFT).view(count, 2) * 2.0
    theta = torch.zeros(count, 2, 3)
    theta[:, 0, 0] = scale
    theta[:, 1, 1] = scale
    theta[:, :, 2] = shift
    grid = F.affine_grid(theta.to(batch.device, batch.dtype), list(batch.shape), align_corners=False)
    return F.grid_sample(batch, grid, mode="bilinear", padding_mode="border", align_corners=False)


def intensity(batch, generator):
    """Gamma, contrast and brightness per crop, the exposure and processing differences between
    one C-arm image and the next; the same on every channel, so a grey crop stays grey."""
    count = batch.shape[0]
    shape = (count, 1, 1, 1)
    gamma = _uniform(generator, count, *GAMMA).view(shape).to(batch.device, batch.dtype)
    contrast = _uniform(generator, count, *CONTRAST).view(shape).to(batch.device, batch.dtype)
    shift = _uniform(generator, count, -BRIGHTNESS, BRIGHTNESS).view(shape).to(batch.device, batch.dtype)
    out = batch.clamp(min=1e-6) ** gamma
    return ((out - 0.5) * contrast + 0.5 + shift).clamp(0.0, 1.0)


def blur(batch, generator):
    """A Gaussian blur of one spread for the batch, from none to about a pixel, as motion and
    focus soften a frame."""
    sigma = float(_uniform(generator, 1, *BLUR_SIGMA))
    if sigma < 0.05:
        return batch
    radius = max(1, math.ceil(2 * sigma))
    steps = torch.arange(-radius, radius + 1, dtype=batch.dtype, device=batch.device)
    line = torch.exp(-(steps**2) / (2 * sigma * sigma))
    line = line / line.sum()
    channels = batch.shape[1]
    across = line.view(1, 1, 1, -1).repeat(channels, 1, 1, 1)
    down = line.view(1, 1, -1, 1).repeat(channels, 1, 1, 1)
    out = F.conv2d(F.pad(batch, (radius, radius, 0, 0), mode="replicate"), across, groups=channels)
    return F.conv2d(F.pad(out, (0, 0, radius, radius), mode="replicate"), down, groups=channels)


def noise(batch, generator):
    """Noise whose spread grows with the square root of the signal, as quantum noise at a
    fluoroscopic dose does; one field per crop, shared by its channels."""
    count, _, height, width = batch.shape
    level = _uniform(generator, count, 0.0, NOISE_LEVEL).view(count, 1, 1, 1)
    field = torch.randn(count, 1, height, width, generator=generator) * level
    return (batch + field.to(batch.device, batch.dtype) * batch.clamp(min=0.0).sqrt()).clamp(0.0, 1.0)


AUGMENTERS = {"box-jitter": box_jitter, "intensity": intensity, "blur": blur, "noise": noise}
AUGMENT_ORDER = ("box-jitter", "intensity", "blur", "noise")


def augment(batch, names, generator):
    """The named changes in their fixed order, whatever order the run named them in."""
    for name in AUGMENT_ORDER:
        if name in names:
            batch = AUGMENTERS[name](batch, generator)
    return batch


def _groups(model, lr, backbone_lr_scale):
    """One group of every parameter at the base rate, as version 1 had, unless the pretrained
    layers take a smaller rate than the new head."""
    if backbone_lr_scale == 1.0:
        return [{"params": list(model.parameters()), "lr": lr}]
    head = [p for name, p in model.named_parameters() if name.startswith("fc.")]
    body = [p for name, p in model.named_parameters() if not name.startswith("fc.")]
    return [{"params": body, "lr": lr * backbone_lr_scale}, {"params": head, "lr": lr}]


def adam(model, lr, blocks):
    return torch.optim.Adam(_groups(model, lr, blocks.backbone_lr_scale), lr=lr)


def adamw(model, lr, blocks):
    return torch.optim.AdamW(_groups(model, lr, blocks.backbone_lr_scale), lr=lr, weight_decay=blocks.weight_decay)


OPTIMISERS = {"adam": adam, "adamw": adamw}


def uniform_order(targets, generator):
    """Every crop once, in a seeded order: version 1's draw, unchanged."""
    return torch.randperm(len(targets), generator=generator)


def balanced_order(targets, generator):
    """As many draws as crops, each crop weighted by the inverse of its level's count, so every
    level present is drawn about equally often; a rare level's crops come round more than once."""
    counts = torch.bincount(targets)
    weights = 1.0 / counts[targets].double()
    return torch.multinomial(weights, len(targets), replacement=True, generator=generator)


SAMPLERS = {"uniform": uniform_order, "balanced": balanced_order}


def loss_function(blocks, targets, levels):
    """Cross-entropy, weighted by the inverse frequency of the training part's levels where the
    run says so; the weights come from schwingnet.blocks.inverse_frequency."""
    if blocks.loss_weights == "none":
        return nn.CrossEntropyLoss()
    from schwingnet.blocks import inverse_frequency

    counts = torch.bincount(targets, minlength=len(levels)).tolist()
    weights = inverse_frequency({name: int(n) for name, n in zip(levels, counts, strict=True)})
    return nn.CrossEntropyLoss(weight=torch.tensor([weights[name] for name in levels], dtype=torch.float32))
