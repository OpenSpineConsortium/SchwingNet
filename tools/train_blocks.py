"""The torch side of the trainer's building blocks (src/schwingnet/blocks.py), one function per name.

Each part of training a run can swap has a table here keyed by the names blocks.py allows:
ARCHITECTURES, DENOISERS, NORMALISERS, AUGMENTERS, OPTIMISERS and SAMPLERS, and
tests/test_train_blocks.py fails when a table and its tuple in blocks.py disagree. A new way of
doing a part is one name in blocks.py and one function in the table here; tools/train.py calls
only the tables, so it never changes for one. The samples block has no torch side: which crops a
run sees is decided by schwingnet.blocks.kept before any tensor is made. The prior block's torch
side is PriorHead, a training-only head over one of the feature maps FEATURES lists per architecture, the deepest that keeps CELLS cells across the crop,
which scores the backbone against the crop's projected level map (#228) and leaves the model,
and so every reader of best.pt, as it is.

The denoisers and the normalisers are forward pre-hooks on the model, registered in that order,
so a crop is filtered and then scaled inside the model: the evaluator, the latency tool, the chain
evaluation and the ONNX export all call the model and so all see the crop the trainer saw.

The augment block strong, SyntheX's and FluoroSAM's strong domain randomisation, has a table of
its own, STRONG, of which each crop takes none, one or two transforms (strong); it is last in
AUGMENT_ORDER, so a run that names the other changes and not it draws what it drew before.

Every random draw the blocks make takes the run's own generator, on the CPU, so their draws are
fixed by the seed whatever the device. torchvision's networks draw on their own account too:
mobilenet-v3-small's classifier holds a Dropout and efficientnet-b0 Dropout and StochasticDepth,
which in training draw from the device's global generator, the one seed_everything seeds, so a
run of those two reproduces on the same kind of device, while the three resnets, which draw
nothing of their own, reproduce on any, and so do MONAI's three (densenet121, se-resnet50 and
se-resnext50, #211), which carry no dropout; monai is imported only when one of them is built, so
a run of a torchvision name never loads it. DEFAULT draws nothing beyond what version 1's trainer
drew, so a run naming no block trains to the same weights as before.
"""

import math
import re
import warnings

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
    "densenet121": "class_layers.out.",
    "se-resnet50": "last_linear.",
    "se-resnext50": "last_linear.",
}


def _load_backbone(model, weights, name, rename=lambda state: state):
    """The ImageNet file's weights but the head's; a file of another network is refused. rename
    turns the file's names into the network's where a published file spells them otherwise."""
    if not weights:
        return
    head = HEADS[name]
    state = rename(torch.load(weights, map_location="cpu", weights_only=True))
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
    """The latency candidate: about a thirtieth of resnet18's multiply-adds at the same input (5.5
    against 148 million at 64 px, counted over the convolutions and linear layers); its classifier's
    dropout draws from the device's global generator (the module docstring)."""
    model = models.mobilenet_v3_small(weights=None)
    _load_backbone(model, weights, "mobilenet-v3-small")
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, outputs)
    return model


def efficientnet_b0(outputs, weights):
    """Between the two in cost; its dropout and stochastic depth draw from the device's global
    generator (the module docstring)."""
    model = models.efficientnet_b0(weights=None)
    _load_backbone(model, weights, "efficientnet-b0")
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, outputs)
    return model


def _monai_nets():
    """MONAI's networks, imported by the three names that need them and by nothing else, so a run
    of a torchvision name never loads monai; its import under torch 2.14 warns (twice, from
    monai's dints.py) that torch.jit.interface is deprecated, MONAI's own to mend, so that one
    warning, named by its message, is kept out of a run's log and any other still shows."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r"`torch\.jit\.interface` is deprecated", category=FutureWarning)
        from monai.networks import nets
    return nets


# torchvision's densenet names against MONAI's. The published ImageNet file
# (download.pytorch.org, densenet121-a639ec97.pth) spells a dense layer's modules "norm.1" and
# "conv.2", a state_dict saved from torchvision's model today "norm1" and "conv2", and MONAI nests
# them under "layers" and calls the classifier class_layers.out. MONAI's own loader
# (monai.networks.nets.densenet, _load_state_dict) maps the first spelling when it downloads that
# file; both are mapped here, so either file is read, and a file already in MONAI's names, a
# parent's or a sibling run's, passes through unchanged, since neither pattern matches it.
_DENSE_PUBLISHED = re.compile(r"^(.*denselayer\d+)\.(norm|relu|conv)\.([12])\.(.+)$")
_DENSE_SAVED = re.compile(r"^(.*denselayer\d+)\.(norm|relu|conv)([12])\.(.+)$")


def _densenet_names(state):
    renamed = {}
    for key, value in state.items():
        match = _DENSE_PUBLISHED.match(key) or _DENSE_SAVED.match(key)
        if match:
            block, module, index, rest = match.groups()
            key = f"{block}.layers.{module}{index}.{rest}"
        elif key.startswith("classifier."):
            key = "class_layers.out." + key[len("classifier.") :]
        renamed[key] = value
    return renamed


def densenet121(outputs, weights):
    """MONAI's DenseNet121 in two dimensions, dense connections in place of residual ones: about
    1.6 times resnet18's multiply-adds (231 against 148 million at 64 px, counted over the
    convolutions and linear layers with forward hooks, as docs/research/experiment-framework.md,
    section 3, counts them) in 7 million parameters, fewer than any resnet here (only
    mobilenet-v3-small, 1.5 million, and efficientnet-b0, 4.0 million, are smaller); no dropout, so
    it reproduces on any device. Its ImageNet file is torchvision's densenet121, in either of
    torchvision's spellings (_densenet_names)."""
    model = _monai_nets().DenseNet121(spatial_dims=2, in_channels=3, out_channels=outputs)
    _load_backbone(model, weights, "densenet121", _densenet_names)
    return model


def _se_net(builder, outputs, weights, name):
    model = builder(spatial_dims=2, in_channels=3, num_classes=outputs)
    _load_backbone(model, weights, name)
    return model


def se_resnet50(outputs, weights):
    """MONAI's SEResNet50, resnet50 in its Caffe layout (the stride in each stage's 1x1
    convolution, where torchvision's resnet50 strides in the 3x3) with a squeeze-and-excitation
    gate on every block: about 2.1 times resnet18's multiply-adds (317 against 148 million at 64
    px, fewer than torchvision's resnet50's 334 despite the gates, since the strided 3x3 runs on a
    quarter of the positions) in 26 million parameters; no dropout, so it reproduces on any device.
    No ImageNet file is read for it but one in MONAI's own names, since its published weights live
    on a third-party site in another naming, so it starts from scratch or from a parent (--init)."""
    return _se_net(_monai_nets().SEResNet50, outputs, weights, "se-resnet50")


def se_resnext50(outputs, weights):
    """MONAI's SEResNext50, se_resnet50's gates on ResNeXt's 32x4d bottlenecks: twice as wide,
    their 3x3 convolutions in 32 groups of 4 and carrying each stage's stride, as torchvision's
    resnets do and se_resnet50's 1x1 does, which is why it costs more and not less: about 2.3
    times resnet18's multiply-adds (348 million at 64 px) in 26 million parameters; the rest as
    se_resnet50."""
    return _se_net(_monai_nets().SEResNext50, outputs, weights, "se-resnext50")


ARCHITECTURES = {
    "resnet18": resnet18,
    "resnet34": resnet34,
    "resnet50": resnet50,
    "mobilenet-v3-small": mobilenet_v3_small,
    "efficientnet-b0": efficientnet_b0,
    "densenet121": densenet121,
    "se-resnet50": se_resnet50,
    "se-resnext50": se_resnext50,
}
# The modules of each architecture whose output is a feature map, the deepest first, where the
# prior block's head may read the backbone: a map still says where in the crop each feature was
# found, which the pooled vector the classifier reads no longer does. The head takes the deepest
# whose map keeps CELLS cells across the crop (PriorHead): on a 64-pixel crop the last map of every
# one of them is 2 by 2, a blend of four positions and no picture of where a level falls, under
# which a head trained to say background everywhere scores the background's share and looks dense.
FEATURES = {
    "resnet18": ("layer4", "layer3", "layer2", "layer1"),
    "resnet34": ("layer4", "layer3", "layer2", "layer1"),
    "resnet50": ("layer4", "layer3", "layer2", "layer1"),
    "mobilenet-v3-small": ("features", "features.8", "features.3", "features.1"),
    "efficientnet-b0": ("features", "features.5", "features.3", "features.2"),
    "densenet121": ("features", "features.denseblock3", "features.denseblock2", "features.denseblock1"),
    "se-resnet50": ("layer4", "layer3", "layer2", "layer1"),
    "se-resnext50": ("layer4", "layer3", "layer2", "layer1"),
}
# The fewest cells the head's map keeps across the crop: FCN-16s's grid on an ImageNet crop, 14 of
# 224, rounded down to a power of two, so a 64-pixel crop reads a stride-8 stage and a 32-pixel
# crop a stride-4 one; fewer cells and the per-pixel supervision is a label with a blur on it.
CELLS = 8
# The value of a map pixel no map labels: every pixel of a crop whose frame has no level map, which
# the prior's loss and its accuracy leave out.
IGNORED = -1

# The library each architecture comes from, for the model card: torchvision has no se-resnet50 and
# lays its densenet121 out unlike MONAI's, so the name alone would send a reader of a checkpoint to
# the wrong class.
LIBRARIES = {
    "resnet18": "torchvision",
    "resnet34": "torchvision",
    "resnet50": "torchvision",
    "mobilenet-v3-small": "torchvision",
    "efficientnet-b0": "torchvision",
    "densenet121": "MONAI",
    "se-resnet50": "MONAI",
    "se-resnext50": "MONAI",
}


def architecture_words(name):
    """The model card's words for an architecture, the library before the name."""
    return f"{LIBRARIES[name]} {name}"


class PriorHead(nn.Module):
    """The level-map head of the prior block (schwingnet.blocks PRIOR): the 3D prior as a second
    supervision. A render's or a registered frame's shard carries a projected level map beside the
    frame, the segmented CT's voxels mapped onto the X-ray, 0 where no vertebra is and 1 to 27 for
    the levels; the head reads one of the backbone's feature maps through a forward hook, the
    deepest that keeps CELLS cells across the crop (FEATURES, chosen by the crop size at the start
    of the run and recorded as the run's prior_stage), names one of 28 classes at every cell with
    a 1 by 1 convolution, repeats each cell over the crop's pixels it covers and scores that
    against the crop's map, so the backbone is asked to keep where each level falls in the crop
    and how the bodies' projections overlap, not only which level the crop centres on. The cells
    are repeated rather than blended since the bilinear upsample's backward is on torch's list of
    kernels that give different sums run to run on CUDA, and the nearest one's is not. The head is
    not part of the model: best.pt, the evaluator, the latency measurement and the ONNX export
    carry the classifier alone, and its own weights go to prior_head.pt beside best.pt."""

    def __init__(self, model, architecture, size, classes):
        super().__init__()
        self.features = None
        self.size = size
        self.stage, self.cells, channels = self._stage(model, architecture)
        self.handle = model.get_submodule(self.stage).register_forward_hook(self._keep)
        self.conv = nn.Conv2d(channels, classes, kernel_size=1)
        self.total, self.batches = 0.0, 0

    def _keep(self, module, args, output):
        self.features = output

    def _stage(self, model, architecture):
        """The deepest stage of FEATURES whose map keeps CELLS cells across the crop, with the
        cells it keeps and its channels, read from one forward of a blank crop with the model as
        it is, so no table of strides or channel counts can go stale; refused in words where no
        stage keeps them, since a head on fewer cells would record a dense prior that is a label."""
        if architecture not in FEATURES:
            raise ArchitectureError(f"{architecture}: no feature map is named for the prior's head (FEATURES)")
        seen = {}
        handles = [
            model.get_submodule(name).register_forward_hook(lambda module, args, output, name=name: seen.__setitem__(name, output))
            for name in FEATURES[architecture]
        ]
        was_training = model.training
        model.eval()
        try:
            with torch.no_grad():
                model(torch.zeros(1, 3, self.size, self.size, device=next(model.parameters()).device))
        except RuntimeError as error:
            # MONAI's densenet121 cannot pool a 16-pixel crop at all; the refusal is the same words.
            raise ArchitectureError(
                f"{architecture} cannot forward a {self.size}-pixel crop ({str(error).splitlines()[0]}); take a larger crop"
            ) from error
        finally:
            model.train(was_training)
            for handle in handles:
                handle.remove()
        for name in FEATURES[architecture]:
            output = seen.get(name)
            if output is not None and output.dim() == 4 and min(output.shape[2:]) >= CELLS:
                return name, (int(output.shape[2]), int(output.shape[3])), int(output.shape[1])
        shallowest = FEATURES[architecture][-1]
        output = seen.get(shallowest)
        given = f"{output.shape[2]} by {output.shape[3]}" if output is not None and output.dim() == 4 else "no feature map"
        raise ArchitectureError(
            f"at {self.size}-pixel crops no stage of {architecture} keeps {CELLS} cells across the crop for"
            f" the prior's head; the shallowest, {shallowest}, gives {given}; take a larger crop"
        )

    def logits(self):
        """The 28-way prediction at every pixel of the crops the model saw last, each cell's
        over the pixels it covers."""
        dense = self.conv(self.features)
        return F.interpolate(dense, size=(self.size, self.size), mode="nearest")

    def loss(self, maps):
        """Cross-entropy over the labelled pixels of the batch's maps, counted into the epoch's
        mean; a batch with no labelled pixel costs nothing, since a mean over none is not a number."""
        if not bool((maps != IGNORED).any()):
            return self.conv.weight.sum() * 0.0
        value = F.cross_entropy(self.logits(), maps, ignore_index=IGNORED)
        self.total += float(value.detach())
        self.batches += 1
        return value

    def mean_and_reset(self):
        """The epoch's mean prior loss over the batches that carried a map, None where none did."""
        mean = self.total / self.batches if self.batches else None
        self.total, self.batches = 0.0, 0
        return mean


def jitter_theta(count, generator):
    """One small move and resize per crop, the draw box_jitter makes, as an affine matrix."""
    scale = 1.0 + _uniform(generator, count, -JITTER_SCALE, JITTER_SCALE)
    shift = _uniform(generator, count * 2, -JITTER_SHIFT, JITTER_SHIFT).view(count, 2) * 2.0
    theta = torch.zeros(count, 2, 3)
    theta[:, 0, 0] = scale
    theta[:, 1, 1] = scale
    theta[:, :, 2] = shift
    return theta


def resample(batch, theta, mode):
    grid = F.affine_grid(theta.to(batch.device, batch.dtype), list(batch.shape), align_corners=False)
    return F.grid_sample(batch, grid, mode=mode, padding_mode="border", align_corners=False)


def box_jitter(batch, generator):
    """Each crop moved and resized a little, as a tracker's or a detector's box would be: an
    affine resample of the padded crop, its edge repeated where the move uncovers it."""
    return resample(batch, jitter_theta(batch.shape[0], generator), "bilinear")


def jitter_with_maps(batch, maps, generator):
    """box_jitter on the crops and the same move on their level maps, sampled nearest so a map
    stays level codes and the ignore mark, so the map still says where each level falls in the
    moved crop; the draw is box_jitter's own, so the crops come out as they would without maps."""
    theta = jitter_theta(batch.shape[0], generator)
    moved = resample(maps.unsqueeze(1).to(batch.dtype), theta, "nearest")
    return resample(batch, theta, "bilinear"), moved.squeeze(1).round().to(maps.dtype)


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


# The strong block's ranges (strong, below, says which are SyntheX's words and which are not). A
# share of the side is of the crop's own side, and a spread or a kernel is in the crop's pixels.
IMPULSE_SHARE = 0.10
AFFINE_SHIFT = 0.10
AFFINE_TURN = 15.0
AFFINE_SHEAR = 10.0
AFFINE_ZOOM = (0.9, 1.1)
LINEAR_ALPHA = (0.6, 1.4)
LOG_GAIN = (0.6, 1.4)
SIGMOID_GAIN = (3.0, 10.0)
SIGMOID_CUTOFF = (0.3, 0.6)
STRONG_BLUR_SIGMA = (0.0, 3.0)
AVERAGE_KERNEL = (2, 7)
BOXES = (1, 4)
BOX_SIDE = (0.05, 0.20)
BOX_SPREAD = 0.5
DROPOUT_SHARE = (0.01, 0.10)
DROPOUT_AREA = (0.02, 0.05)
SHARPEN_ALPHA = (0.0, 1.0)
SHARPEN_LIGHTNESS = (0.75, 1.5)
EMBOSS_ALPHA = (0.0, 1.0)
EMBOSS_STRENGTH = (0.5, 1.5)
MULTIPLY = (0.5, 1.5)
BRIGHTNESS_SHIFT = 0.2
WARP_CELLS = 4
WARP_SHIFT = 0.05
GAUSSIAN_SPREAD = (0.2, 1.0)
WINDOW_WIDTH = (0.2, 1.0)
CLAHE_TILES = 8
CLAHE_CLIP = (2.0, 4.0)
CLAHE_BINS = 256
# SyntheX's "up to two" strong transforms per crop.
STRONG_MOST = 2

# The 3 by 3 kernels of sharpen and emboss, imgaug's Sharpen and Emboss matrices split into what
# is fixed and what a drawn lightness or strength multiplies, so the drawn part is a broadcast.
LAPLACE = ((-1.0, -1.0, -1.0), (-1.0, 8.0, -1.0), (-1.0, -1.0, -1.0))
RELIEF = ((-1.0, -1.0, 0.0), (-1.0, 0.0, 1.0), (0.0, 1.0, 1.0))
CORNERS = ((-1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))


def _per_crop(generator, count, low, high, like):
    """One draw per crop, shaped to act on every channel of its crop alike."""
    return _uniform(generator, count, low, high).view(count, 1, 1, 1).to(like.device, like.dtype)


def _ways(generator, count, options, like):
    """Which of a transform's ways, 0 to options - 1, each crop takes, as a column a batch
    compares against."""
    return torch.randint(0, options, (count,), generator=generator).view(count, 1, 1, 1).to(like.device)


def _field(generator, like):
    """One uniform field per crop, shared by its channels, so a grey crop stays grey."""
    count, _, height, width = like.shape
    return torch.rand(count, 1, height, width, generator=generator).to(like.device, like.dtype)


def _rectangles(sides, corners, height, width, device):
    """The pixels inside each crop's rectangles, one mask per crop and rectangle: sides are a
    rectangle's height and width as shares of the crop's, at least a pixel, and corners place it
    anywhere it fits, as shares of the room left; made on the CPU from the CPU's draws."""
    tall = (sides[..., 0] * height).round().clamp(1, height)
    wide = (sides[..., 1] * width).round().clamp(1, width)
    top = (corners[..., 0] * (height - tall + 1)).floor()
    left = (corners[..., 1] * (width - wide + 1)).floor()
    rows = torch.arange(height).view(1, 1, height, 1)
    columns = torch.arange(width).view(1, 1, 1, width)
    down = (rows >= top[..., None, None]) & (rows < (top + tall)[..., None, None])
    across = (columns >= left[..., None, None]) & (columns < (left + wide)[..., None, None])
    return (down & across).to(device)


def _filter3(batch, rows):
    """One fixed 3 by 3 kernel over every channel of every crop alike, the edges repeated."""
    count, channels, height, width = batch.shape
    kernel = torch.tensor(rows, dtype=batch.dtype, device=batch.device).view(1, 1, 3, 3)
    planes = F.pad(batch.reshape(count * channels, 1, height, width), (1, 1, 1, 1), mode="replicate")
    return F.conv2d(planes, kernel).view(count, channels, height, width)


def invert(batch, generator):
    """Max minus x with the maximum 1, SyntheX's inversion and FluoroSAM's; it draws nothing."""
    return (1.0 - batch).clamp(0.0, 1.0)


def impulse_noise(batch, generator):
    """SyntheX's impulse, pepper or salt noise on IMPULSE_SHARE of each crop's pixels, the kind
    drawn per crop: impulse noise sets each hit pixel to 0 or 1 at even odds, pepper to 0, salt
    to 1."""
    count = batch.shape[0]
    kind = _ways(generator, count, 3, batch)
    hit = _field(generator, batch) < IMPULSE_SHARE
    salt = (_field(generator, batch) < 0.5).to(batch.dtype)
    value = torch.where(kind == 0, salt, torch.where(kind == 1, torch.zeros_like(salt), torch.ones_like(salt)))
    return torch.where(hit, value, batch)


def affine_theta(count, generator):
    """One move, turn, shear and zoom per crop as the matrix affine_grid takes: the turn and the
    shear in degrees, the move a share of the side, twice that in the grid's -1 to 1 units, as
    jitter_theta moves it; a turn of a square crop is a turn, which is every crop here."""
    shift = _uniform(generator, count * 2, -AFFINE_SHIFT, AFFINE_SHIFT).view(count, 2) * 2.0
    turn = torch.deg2rad(_uniform(generator, count, -AFFINE_TURN, AFFINE_TURN))
    shear = torch.deg2rad(_uniform(generator, count, -AFFINE_SHEAR, AFFINE_SHEAR))
    zoom = _uniform(generator, count, *AFFINE_ZOOM)
    cos, sin, tan = turn.cos(), turn.sin(), shear.tan()
    theta = torch.zeros(count, 2, 3)
    theta[:, 0, 0] = zoom * cos
    theta[:, 0, 1] = zoom * (cos * tan - sin)
    theta[:, 1, 0] = zoom * sin
    theta[:, 1, 1] = zoom * (sin * tan + cos)
    theta[:, :, 2] = shift
    return theta


def affine(batch, generator):
    """SyntheX's random affine warp, its edge repeated where the warp uncovers it, as box_jitter."""
    return resample(batch, affine_theta(batch.shape[0], generator), "bilinear").clamp(0.0, 1.0)


def affine_with_maps(batch, maps, generator):
    """affine on the crops and the same warp on their level maps, sampled nearest so a map stays
    level codes and the ignore mark; the draw is affine's own, so the crops come out as without."""
    theta = affine_theta(batch.shape[0], generator)
    moved = resample(maps.unsqueeze(1).to(batch.dtype), theta, "nearest")
    return resample(batch, theta, "bilinear").clamp(0.0, 1.0), moved.squeeze(1).round().to(maps.dtype)


def contrast(batch, generator):
    """One of a linear, a log and a sigmoid contrast curve per crop, SyntheX's three, written on 0
    to 1 as imgaug writes them on a byte: linear about the middle grey, gain times log2(1 + x),
    and 1 / (1 + exp(gain (cutoff - x))); every crop draws every setting, so the draws do not
    depend on which curve it took."""
    count = batch.shape[0]
    kind = _ways(generator, count, 3, batch)
    alpha = _per_crop(generator, count, *LINEAR_ALPHA, batch)
    gain = _per_crop(generator, count, *LOG_GAIN, batch)
    steep = _per_crop(generator, count, *SIGMOID_GAIN, batch)
    cutoff = _per_crop(generator, count, *SIGMOID_CUTOFF, batch)
    x = batch.clamp(0.0, 1.0)
    linear = 0.5 + alpha * (x - 0.5)
    log = gain * torch.log2(1.0 + x)
    sigmoid = torch.sigmoid(steep * (x - cutoff))
    return torch.where(kind == 0, linear, torch.where(kind == 1, log, sigmoid)).clamp(0.0, 1.0)


def gaussian_blur(batch, generator):
    """A Gaussian blur of a spread drawn per crop up to SyntheX's 3 pixels, a far heavier blur
    than the blur block's, crop by crop since each has its own kernel."""
    sigmas = _uniform(generator, batch.shape[0], *STRONG_BLUR_SIGMA).tolist()
    crops = [crop[None] if sigma < 0.05 else _gaussian(crop[None], sigma) for crop, sigma in zip(batch, sigmas, strict=True)]
    return torch.cat(crops).clamp(0.0, 1.0)


def _box_mean(crop, kernel):
    """The mean over a kernel by kernel window about every pixel, the edges repeated; an even
    kernel reaches one pixel further to the right and down, as OpenCV's box filter does."""
    before, after = (kernel - 1) // 2, kernel // 2
    return F.avg_pool2d(F.pad(crop, (before, after, before, after), mode="replicate"), kernel, stride=1)


def average_blur(batch, generator):
    """SyntheX's average blur, a kernel of AVERAGE_KERNEL pixels drawn per crop."""
    low, high = AVERAGE_KERNEL
    kernels = torch.randint(low, high + 1, (batch.shape[0],), generator=generator).tolist()
    return torch.cat([_box_mean(crop[None], kernel) for crop, kernel in zip(batch, kernels, strict=True)])


def box_corruption(batch, generator):
    """SyntheX's boxes corrupted with large noise: BOXES boxes per crop, each side a BOX_SIDE share
    of the crop's, filled with Gaussian noise about the middle grey of spread BOX_SPREAD; every
    crop draws the most boxes there can be and keeps as many as its count, so what it draws does
    not depend on the count."""
    count, _, height, width = batch.shape
    most = BOXES[1]
    boxes = torch.randint(BOXES[0], most + 1, (count,), generator=generator)
    sides = _uniform(generator, count * most * 2, *BOX_SIDE).view(count, most, 2)
    corners = torch.rand(count, most, 2, generator=generator)
    fill = (0.5 + BOX_SPREAD * torch.randn(count, 1, height, width, generator=generator)).clamp(0.0, 1.0)
    kept = (torch.arange(most).view(1, most) < boxes.view(count, 1)).to(batch.device)
    inside = (_rectangles(sides, corners, height, width, batch.device) & kept[..., None, None]).any(dim=1, keepdim=True)
    return torch.where(inside, fill.to(batch.device, batch.dtype), batch)


def dropout(batch, generator):
    """SyntheX's dropout, and FluoroSAM's coarse dropout: per crop either a DROPOUT_SHARE of its
    pixels or one rectangle of a DROPOUT_AREA share of it set to 0, the rectangle's sides each the
    square root of that share of the crop's; every crop draws both ways."""
    count, _, height, width = batch.shape
    by_rectangle = _ways(generator, count, 2, batch) == 1
    share = _per_crop(generator, count, *DROPOUT_SHARE, batch)
    pixels = _field(generator, batch) < share
    side = _uniform(generator, count, *DROPOUT_AREA).sqrt().view(count, 1, 1).expand(count, 1, 2)
    corners = torch.rand(count, 1, 2, generator=generator)
    rectangle = _rectangles(side, corners, height, width, batch.device)
    return torch.where(torch.where(by_rectangle, rectangle, pixels), torch.zeros_like(batch), batch)


def sharpen(batch, generator):
    """imgaug's Sharpen, which SyntheX's name matches: the 3 by 3 kernel of 8 plus the lightness
    at the centre and -1 about it, blended with the crop by alpha."""
    count = batch.shape[0]
    alpha = _per_crop(generator, count, *SHARPEN_ALPHA, batch)
    lightness = _per_crop(generator, count, *SHARPEN_LIGHTNESS, batch)
    sharpened = lightness * batch + _filter3(batch, LAPLACE)
    return ((1.0 - alpha) * batch + alpha * sharpened).clamp(0.0, 1.0)


def emboss(batch, generator):
    """imgaug's Emboss kernel, the crop plus strength times the relief and the two far corners,
    added to the crop by alpha and not blended with it, as SyntheX says, so a flat field
    brightens as the edges carve, until the clamp."""
    count = batch.shape[0]
    alpha = _per_crop(generator, count, *EMBOSS_ALPHA, batch)
    strength = _per_crop(generator, count, *EMBOSS_STRENGTH, batch)
    embossed = batch + strength * _filter3(batch, RELIEF) + _filter3(batch, CORNERS)
    return (batch + alpha * embossed).clamp(0.0, 1.0)


def _pool(crops, kind):
    """One of the four poolings over 2 by 2 cells, each cell's value given back to its four
    pixels, so the size is kept; an odd side's last row or column is repeated first. The median
    of four is the mean of the middle two, as numpy's is."""
    count, channels, height, width = crops.shape
    padded = F.pad(crops, (0, width % 2, 0, height % 2), mode="replicate")
    rows, columns = padded.shape[-2] // 2, padded.shape[-1] // 2
    cells = padded.view(count, channels, rows, 2, columns, 2).permute(0, 1, 2, 4, 3, 5).reshape(count, channels, rows, columns, 4)
    if kind == 0:
        pooled = cells.mean(dim=-1)
    elif kind == 1:
        pooled = cells.amax(dim=-1)
    elif kind == 2:
        pooled = cells.amin(dim=-1)
    else:
        pooled = cells.sort(dim=-1).values[..., 1:3].mean(dim=-1)
    return pooled.repeat_interleave(2, dim=-2).repeat_interleave(2, dim=-1)[..., :height, :width]


def pooling(batch, generator):
    """SyntheX's pooling, one of average, max, min and median drawn per crop."""
    kinds = torch.randint(0, 4, (batch.shape[0],), generator=generator)
    out = batch.clone()
    for kind in range(4):
        chosen = (kinds == kind).nonzero().flatten().to(batch.device)
        if len(chosen):
            out[chosen] = _pool(batch[chosen], kind)
    return out


def multiply(batch, generator):
    """SyntheX's multiply of MULTIPLY times, or its brightness change, a shift of up to
    BRIGHTNESS_SHIFT, the way drawn per crop; every crop draws both settings."""
    count = batch.shape[0]
    by_shift = _ways(generator, count, 2, batch) == 1
    factor = _per_crop(generator, count, *MULTIPLY, batch)
    shift = _per_crop(generator, count, -BRIGHTNESS_SHIFT, BRIGHTNESS_SHIFT, batch)
    return torch.where(by_shift, batch + shift, batch * factor).clamp(0.0, 1.0)


def warp_grid(count, height, width, generator):
    """Where each pixel of a warped crop is read from: the identity grid plus a coarse field of
    offsets, WARP_CELLS by WARP_CELLS per crop of up to WARP_SHIFT of the side, upsampled
    bicubically to the crop so the warp bends smoothly between its cells, as a piecewise affine
    warp does at its control points; made on the CPU, so it is the same on any device."""
    offsets = _uniform(generator, count * 2 * WARP_CELLS * WARP_CELLS, -WARP_SHIFT, WARP_SHIFT)
    offsets = offsets.view(count, 2, WARP_CELLS, WARP_CELLS) * 2.0
    smooth = F.interpolate(offsets, size=(height, width), mode="bicubic", align_corners=True)
    identity = F.affine_grid(torch.eye(2, 3).expand(count, 2, 3), [count, 1, height, width], align_corners=False)
    return identity + smooth.permute(0, 2, 3, 1)


def _sample(batch, grid, mode):
    grid = grid.to(batch.device, batch.dtype)
    return F.grid_sample(batch, grid, mode=mode, padding_mode="border", align_corners=False)


def piecewise_warp(batch, generator):
    """SyntheX's piecewise affine distortion, as a smooth random warp (warp_grid)."""
    count, _, height, width = batch.shape
    return _sample(batch, warp_grid(count, height, width, generator), "bilinear").clamp(0.0, 1.0)


def piecewise_warp_with_maps(batch, maps, generator):
    """piecewise_warp on the crops and the same warp on their level maps, sampled nearest; the
    draw is piecewise_warp's own, so the crops come out as without maps."""
    count, _, height, width = batch.shape
    grid = warp_grid(count, height, width, generator)
    moved = _sample(maps.unsqueeze(1).to(batch.dtype), grid, "nearest")
    return _sample(batch, grid, "bilinear").clamp(0.0, 1.0), moved.squeeze(1).round().to(maps.dtype)


def gaussian_contrast(batch, generator):
    """FluoroSAM's Gaussian contrast: each pixel passed through a Gaussian of a centre anywhere in
    0 to 1 and a GAUSSIAN_SPREAD spread, drawn per crop, and the crop rescaled to 0 to 1, so the
    grey levels near the centre come out bright and those far from it dark; a crop the curve
    leaves flat keeps the curve's value."""
    count = batch.shape[0]
    centre = _per_crop(generator, count, 0.0, 1.0, batch)
    spread = _per_crop(generator, count, *GAUSSIAN_SPREAD, batch)
    curve = torch.exp(-0.5 * ((batch - centre) / spread) ** 2)
    low = curve.amin(dim=(1, 2, 3), keepdim=True)
    high = curve.amax(dim=(1, 2, 3), keepdim=True)
    rescaled = (curve - low) / (high - low).clamp(min=1e-6)
    return torch.where(high - low > 1e-6, rescaled, curve).clamp(0.0, 1.0)


def windowing(batch, generator):
    """FluoroSAM's random windowing: a window a WINDOW_WIDTH share of the range wide, set anywhere
    it fits inside 0 to 1, the crop clipped to it and stretched over 0 to 1, as a viewer's window
    and level would show it."""
    count = batch.shape[0]
    width = _per_crop(generator, count, *WINDOW_WIDTH, batch)
    low = _per_crop(generator, count, 0.0, 1.0, batch) * (1.0 - width)
    return ((batch - low) / width).clamp(0.0, 1.0)


def _tile_maps(levels, area, limits):
    """Each tile's equaliser, in whole counts as OpenCV's CLAHE keeps them, so it is exact on any
    device: the tile's histogram clipped at its limit, the excess spread evenly over the bins and
    the remainder one each over bins a step apart from the first, its running sum over the tile's
    pixels. levels holds each plane's pixels as their tile times CLAHE_BINS plus their grey level,
    and limits one clip limit per plane."""
    planes = levels.shape[0]
    cells = CLAHE_TILES * CLAHE_TILES
    offsets = torch.arange(planes, device=levels.device).view(planes, 1) * (cells * CLAHE_BINS)
    counts = torch.bincount((levels.reshape(planes, -1) + offsets).flatten(), minlength=planes * cells * CLAHE_BINS)
    counts = counts.view(planes, cells, CLAHE_BINS)
    clipped = torch.minimum(counts, limits.view(planes, 1, 1))
    excess = (counts - clipped).sum(dim=-1, keepdim=True)
    clipped = clipped + excess // CLAHE_BINS
    remainder = excess % CLAHE_BINS
    step = (CLAHE_BINS // remainder.clamp(min=1)).clamp(min=1)
    bins = torch.arange(CLAHE_BINS, device=levels.device).view(1, 1, CLAHE_BINS)
    clipped = clipped + ((bins % step == 0) & (bins // step < remainder)).long()
    return clipped.cumsum(dim=-1).to(torch.float64) / area


def _tile_places(size, tile, device):
    """For each row (or column) of pixels, the two nearest tile centres and the weight of the
    second, which bilinear interpolation between the tiles' maps takes; past the outer centres the
    nearest tile's map alone."""
    place = ((torch.arange(size, device=device, dtype=torch.float64) + 0.5) / tile - 0.5).clamp(0, CLAHE_TILES - 1)
    first = place.floor().long()
    return first, (first + 1).clamp(max=CLAHE_TILES - 1), place - first


def clahe(batch, generator):
    """FluoroSAM's CLAHE histogram equalisation, written in torch: CLAHE_TILES by CLAHE_TILES tiles
    of CLAHE_BINS grey levels, a clip limit drawn per crop in CLAHE_CLIP times the tile's mean
    count per level, at least one count, as OpenCV's clipLimit reads, and each pixel's level mapped
    by the four nearest tiles' equalisers, bilinear between them; a side that is no multiple of
    the tiles is padded by repeating its edge and cut back after."""
    count, channels, height, width = batch.shape
    clip = _uniform(generator, count, *CLAHE_CLIP)
    tall, wide = -(-height // CLAHE_TILES) * CLAHE_TILES, -(-width // CLAHE_TILES) * CLAHE_TILES
    padded = F.pad(batch, (0, wide - width, 0, tall - height), mode="replicate")
    planes = count * channels
    levels = (padded.clamp(0.0, 1.0) * (CLAHE_BINS - 1)).round().long().view(planes, tall, wide)
    tile_tall, tile_wide = tall // CLAHE_TILES, wide // CLAHE_TILES
    area = tile_tall * tile_wide
    rows = torch.arange(tall, device=batch.device) // tile_tall
    columns = torch.arange(wide, device=batch.device) // tile_wide
    tiles = (rows.view(tall, 1) * CLAHE_TILES + columns.view(1, wide)).view(1, tall, wide)
    limits = (clip * area / CLAHE_BINS).floor().clamp(min=1).long().repeat_interleave(channels).to(batch.device)
    maps = _tile_maps(tiles * CLAHE_BINS + levels, area, limits).view(planes, -1)
    top, bottom, down = _tile_places(tall, tile_tall, batch.device)
    left, right, across = _tile_places(wide, tile_wide, batch.device)

    def mapped(tile_rows, tile_columns):
        cell = tile_rows.view(tall, 1) * CLAHE_TILES + tile_columns.view(1, wide)
        return maps.gather(1, (cell.view(1, tall, wide) * CLAHE_BINS + levels).view(planes, -1)).view(planes, tall, wide)

    down, across = down.view(1, tall, 1), across.view(1, 1, wide)
    upper = (1 - across) * mapped(top, left) + across * mapped(top, right)
    lower = (1 - across) * mapped(bottom, left) + across * mapped(bottom, right)
    out = ((1 - down) * upper + down * lower).to(batch.dtype).view(count, channels, tall, wide)
    return out[..., :height, :width].clamp(0.0, 1.0)


STRONG = {
    "invert": invert,
    "impulse-noise": impulse_noise,
    "affine": affine,
    "contrast": contrast,
    "gaussian-blur": gaussian_blur,
    "average-blur": average_blur,
    "box-corruption": box_corruption,
    "dropout": dropout,
    "sharpen": sharpen,
    "emboss": emboss,
    "pooling": pooling,
    "multiply": multiply,
    "piecewise-warp": piecewise_warp,
    "gaussian-contrast": gaussian_contrast,
    "windowing": windowing,
    "clahe": clahe,
}
STRONG_ORDER = tuple(STRONG)
# The two strong transforms that move a crop's pixels, and so its level map with it.
STRONG_WARPS = {"affine": affine_with_maps, "piecewise-warp": piecewise_warp_with_maps}


def strong_picks(count, generator):
    """The strong transforms each crop takes, in the order it takes them: how many, none, one or
    two alike, and which, uniformly without replacement, the first few of a random order of all of
    them drawn per crop."""
    how_many = torch.randint(0, STRONG_MOST + 1, (count,), generator=generator).tolist()
    orders = torch.rand(count, len(STRONG_ORDER), generator=generator).argsort(dim=1).tolist()
    return [tuple(STRONG_ORDER[i] for i in order[:n]) for order, n in zip(orders, how_many, strict=True)]


def _strong(batch, maps, generator):
    """The strong block on a batch, and on its level maps where it has them: each crop's picks
    (strong_picks), the crops that take one transform at one turn done together, the turns in
    order and the transforms in STRONG_ORDER within a turn, so the draws are fixed by the picks
    and do not depend on whether the maps are there."""
    picks = strong_picks(batch.shape[0], generator)
    batch = batch.clone()
    maps = None if maps is None else maps.clone()
    for turn in range(STRONG_MOST):
        for name in STRONG_ORDER:
            chosen = [n for n, pick in enumerate(picks) if len(pick) > turn and pick[turn] == name]
            if not chosen:
                continue
            index = torch.tensor(chosen, device=batch.device)
            if maps is not None and name in STRONG_WARPS:
                batch[index], maps[index] = STRONG_WARPS[name](batch[index], maps[index], generator)
            else:
                batch[index] = STRONG[name](batch[index], generator)
    return batch, maps


def strong(batch, generator):
    """SyntheX's strong domain randomisation, its image-level transforms (Gao, Killeen et al.,
    "Synthetic data accelerates the development of generalizable learning-based algorithms for
    X-ray image analysis", Nat Mach Intell 5:294, 2023, Methods, read on PubMed Central as
    PMC10959504), with the ones FluoroSAM adds (Killeen et al., MICCAI 2025, paper 5042, which
    names coarse dropout, inversion, blurring, Gaussian contrast adjustment, random windowing and
    CLAHE). SyntheX "only randomly concatenated up to two strong domain randomization methods
    during each training iteration"; here each crop draws how many, none, one or two alike, and
    which, without replacement, from STRONG_ORDER (strong_picks), every draw from the run's
    generator on the CPU, so a run reproduces on any device.

    The ranges in SyntheX's own words: inversion as max minus x; impulse, pepper or salt noise on
    10 percent of the pixels; a Gaussian blur of spread 3, which the block draws up to; an average
    blur of kernel 2 to 7; dropout of 1 to 10 percent of the pixels or of one rectangle of 2 to 5
    percent of the image; a multiply of 50 to 150 percent or a brightness change; and an emboss
    added rather than blended. SyntheX names the rest with no range. The contrast curves, sharpen
    and emboss take theirs from imgaug's augmenters of the same names (LinearContrast,
    LogContrast, SigmoidContrast, Sharpen, Emboss), whose names SyntheX's match, though the paper
    does not say it used imgaug, and whose curves and kernels they write on 0 to 1; the affine's
    move, turn, shear and zoom, the boxes' count, size and noise, the brightness change's shift,
    the pooling's 2 by 2 cells and the warp's grid are this module's, chosen mild enough to leave
    a level readable. FluoroSAM gives no range either, so the Gaussian contrast's spread, the
    window's width and CLAHE's clip limit are this module's too, and CLAHE's 8 by 8 tiles are
    OpenCV's default. Both papers randomise simulated images to carry training to real ones; here
    it is a test of robustness on real frames. Only the two warps move a crop's level map
    (strong_with_maps)."""
    return _strong(batch, None, generator)[0]


def strong_with_maps(batch, maps, generator):
    """strong on crops that carry level maps: the affine and the piecewise warp move each map with
    its crop, nearest, and the rest leave it; the crops come out as they would without maps."""
    return _strong(batch, maps, generator)


AUGMENTERS = {"box-jitter": box_jitter, "intensity": intensity, "blur": blur, "noise": noise, "strong": strong}
AUGMENT_ORDER = ("box-jitter", "intensity", "blur", "noise", "strong")


def augment(batch, names, generator):
    """The named changes in their fixed order, whatever order the run named them in; strong is
    last, so the four before it draw what they drew before it was named."""
    for name in AUGMENT_ORDER:
        if name in names:
            batch = AUGMENTERS[name](batch, generator)
    return batch


def augment_with_maps(batch, maps, names, generator):
    """augment on crops that carry level maps: the box jitter and the strong block's two warps
    move each map with its crop, and the other changes, which alter intensity alone, leave the
    maps as they are."""
    for name in AUGMENT_ORDER:
        if name not in names:
            continue
        if name == "box-jitter":
            batch, maps = jitter_with_maps(batch, maps, generator)
        elif name == "strong":
            batch, maps = strong_with_maps(batch, maps, generator)
        else:
            batch = AUGMENTERS[name](batch, generator)
    return batch, maps


def _groups(model, lr, blocks, extra=()):
    """One group of every parameter at the base rate, as version 1 had, unless the pretrained
    layers take a smaller rate than the new head, whose names HEADS gives per architecture; the
    extra parameters, the prior head's, are new as the head is and train at its rate."""
    extra = list(extra)
    if blocks.backbone_lr_scale == 1.0:
        return [{"params": list(model.parameters()) + extra, "lr": lr}]
    prefix = HEADS[blocks.architecture]
    head = [p for name, p in model.named_parameters() if name.startswith(prefix)]
    body = [p for name, p in model.named_parameters() if not name.startswith(prefix)]
    return [{"params": body, "lr": lr * blocks.backbone_lr_scale}, {"params": head + extra, "lr": lr}]


def adam(model, lr, blocks, extra=()):
    return torch.optim.Adam(_groups(model, lr, blocks, extra), lr=lr)


def adamw(model, lr, blocks, extra=()):
    return torch.optim.AdamW(_groups(model, lr, blocks, extra), lr=lr, weight_decay=blocks.weight_decay)


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
