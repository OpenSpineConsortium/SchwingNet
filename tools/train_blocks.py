"""The torch side of the trainer's building blocks (src/schwingnet/blocks.py), one function per name.

Each part of training a run can swap has a table here keyed by the names blocks.py allows:
ARCHITECTURES, DENOISERS, NORMALISERS, AUGMENTERS, OPTIMISERS and SAMPLERS, and
tests/test_train_blocks.py fails when a table and its tuple in blocks.py disagree. A new way of
doing a part is one name in blocks.py and one function in the table here; tools/train.py calls
only the tables, so it never changes for one. The samples block has no torch side: which crops a
run sees is decided by schwingnet.blocks.kept before any tensor is made.

The denoisers and the normalisers are forward pre-hooks on the model, registered in that order,
so a crop is filtered and then scaled inside the model: the evaluator, the latency tool, the chain
evaluation and the ONNX export all call the model and so all see the crop the trainer saw.

Every random draw takes the run's own generator, on the CPU, so a run's draws are fixed by its
seed whatever the device; and DEFAULT draws nothing beyond what version 1's trainer drew, so a run
naming no block trains to the same weights as before.
"""

import math

import torch
from torch import nn
from torch.nn import functional as F
from torchvision import models

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
# The one spread a gaussian denoise block smooths at: under a pixel, the quantum noise's scale and
# not the cortex's; a wider one is a new name, never a setting, so a run's record names it whole.
DENOISE_SIGMA = 0.7

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


def _gaussian(batch, sigma):
    """A separable Gaussian blur of one spread over the batch, its edges repeated; ONNX exports
    the two convolutions and the pads as they are."""
    radius = max(1, math.ceil(2 * sigma))
    # The kernel is made of plain numbers, so the export carries it as a constant: a kernel
    # computed from the batch's shape is one of unknown shape to the TorchScript exporter.
    weights = [math.exp(-(k * k) / (2 * sigma * sigma)) for k in range(-radius, radius + 1)]
    total = sum(weights)
    line = torch.tensor([w / total for w in weights], dtype=batch.dtype, device=batch.device)
    channels = int(batch.shape[1])
    across = line.view(1, 1, 1, -1).repeat(channels, 1, 1, 1)
    down = line.view(1, 1, -1, 1).repeat(channels, 1, 1, 1)
    out = F.conv2d(F.pad(batch, (radius, radius, 0, 0), mode="replicate"), across, groups=channels)
    return F.conv2d(F.pad(out, (0, 0, radius, radius), mode="replicate"), down, groups=channels)


def _median3(batch):
    """A 3 by 3 median per pixel, the edges repeated: nine shifted views of the padded crop sorted
    along a new axis and the middle one taken, so the ONNX export is slices and a sort, which the
    TorchScript exporter carries where an unfold or a median op would not."""
    height, width = int(batch.shape[-2]), int(batch.shape[-1])
    padded = F.pad(batch, (1, 1, 1, 1), mode="replicate")
    views = [padded[..., dy : dy + height, dx : dx + width] for dy in range(3) for dx in range(3)]
    return torch.stack(views, dim=-1).sort(dim=-1).values[..., 4]


def _gaussian_hook(module, args):
    (batch,) = args
    return (_gaussian(batch, DENOISE_SIGMA),)


def _median_hook(module, args):
    (batch,) = args
    return (_median3(batch),)


def denoise_none(model):
    return model


def denoise_gaussian(model):
    model.register_forward_pre_hook(_gaussian_hook)
    return model


def denoise_median(model):
    model.register_forward_pre_hook(_median_hook)
    return model


DENOISERS = {"none": denoise_none, "gaussian": denoise_gaussian, "median": denoise_median}


class ArchitectureError(ValueError):
    """A weights file that is not the named architecture's, said in words."""


# The parameter names of each architecture's head, the one layer the level stage replaces: the
# ImageNet file is loaded without it, and backbone_lr_scale gives everything else a smaller rate.
HEADS = {
    "resnet18": "fc.",
    "resnet34": "fc.",
    "resnet50": "fc.",
    "mobilenet-v3-small": "classifier.3.",
    "efficientnet-b0": "classifier.1.",
}


def _load_backbone(model, weights, name):
    """The ImageNet file's weights but the head's; a file of another network is refused."""
    if not weights:
        return
    head = HEADS[name]
    state = torch.load(weights, map_location="cpu", weights_only=True)
    state = {k: v for k, v in state.items() if not k.startswith(head)}
    try:
        missing, unexpected = model.load_state_dict(state, strict=False)
    except RuntimeError as error:
        # The names fit and the shapes do not: a file of a sibling network (resnet50's into resnet18)
        raise ArchitectureError(f"{weights}: not a {name} state_dict ({str(error).splitlines()[0]})") from error
    if unexpected or [k for k in missing if not k.startswith(head)]:
        raise ArchitectureError(f"{weights}: not a {name} state_dict ({unexpected} {missing})")


def _resnet(name, outputs, weights):
    model = getattr(models, name)(weights=None)
    _load_backbone(model, weights, name)
    model.fc = nn.Linear(model.fc.in_features, outputs)
    return model


def resnet18(outputs, weights):
    return _resnet("resnet18", outputs, weights)


def resnet34(outputs, weights):
    return _resnet("resnet34", outputs, weights)


def resnet50(outputs, weights):
    return _resnet("resnet50", outputs, weights)


def mobilenet_v3_small(outputs, weights):
    """The latency candidate: a tenth of resnet18's multiply-adds at the same input."""
    model = models.mobilenet_v3_small(weights=None)
    _load_backbone(model, weights, "mobilenet-v3-small")
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, outputs)
    return model


def efficientnet_b0(outputs, weights):
    model = models.efficientnet_b0(weights=None)
    _load_backbone(model, weights, "efficientnet-b0")
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, outputs)
    return model


ARCHITECTURES = {
    "resnet18": resnet18,
    "resnet34": resnet34,
    "resnet50": resnet50,
    "mobilenet-v3-small": mobilenet_v3_small,
    "efficientnet-b0": efficientnet_b0,
}


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
    return _gaussian(batch, sigma)


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


def _groups(model, lr, blocks):
    """One group of every parameter at the base rate, as version 1 had, unless the pretrained
    layers take a smaller rate than the new head, whose names HEADS gives per architecture."""
    if blocks.backbone_lr_scale == 1.0:
        return [{"params": list(model.parameters()), "lr": lr}]
    prefix = HEADS[blocks.architecture]
    head = [p for name, p in model.named_parameters() if name.startswith(prefix)]
    body = [p for name, p in model.named_parameters() if not name.startswith(prefix)]
    return [{"params": body, "lr": lr * blocks.backbone_lr_scale}, {"params": head, "lr": lr}]


def adam(model, lr, blocks):
    return torch.optim.Adam(_groups(model, lr, blocks), lr=lr)


def adamw(model, lr, blocks):
    return torch.optim.AdamW(_groups(model, lr, blocks), lr=lr, weight_decay=blocks.weight_decay)


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
