"""The auto-anatomist: a network that places a vertebra's measurement landmarks in a CT crop,
trained with the vertebra's mask as privileged information and then weaned off it, so that at
the end it reads the CT alone.

The privileged information is the mask: in training the network is given the target vertebra's
mask and every vertebra's beside the CT, which a test-time CT never comes with (learning using
privileged information, Vapnik and Vashist, Neural Networks 22, 2009; generalized distillation,
Lopez-Paz, Bottou, Schoelkopf and Vapnik, ICLR 2016). Two encoders of one architecture read the
two: E_ct the CT crop, E_mask the mask channels after the degradation ladder has taken them down
by lambda (ladder.py). At every scale the decoder reads the fusion

    F = (1 - w) F_ct + w F_mask,

w the fusion weight, 1 at the start of training and 0 at the end (ladder.Schedule), so the head
is first trained on what the mask makes plain and then handed over to the CT's features, which
the feature-matching loss ||F_ct - stopgrad(F_mask)||^2 (train.py) pulls toward the mask's all
along. That is the owner's pasted design (the homotopy and the feature matching), in the form
generalized distillation gives it; the architecture's sizes are this module's choices.

The head gives one heatmap per landmark (specs.landmarks: the two ends of each chord), read by
the soft-argmax, integral regression: the landmark is the heatmap's expected position, which is
differentiable and finer than its grid, and its spread is the heatmap's covariance about that
position. The values come from the landmarks by the measurements' own rules (specs.values), so a
reported value and the line drawn for it never disagree, and each value's uncertainty is the
delta method: var(v) = sum over its points of J S J', J the value's gradient in the point and S
the point's covariance, the points' errors taken as independent. Whether the spread is a
calibrated error is for train.py's spread loss and a held-out check to say; untrained, it is not.

ct_only is the path a raw CT takes at test time: E_ct and the decoder, no mask, jitted by the
caller (train.timing measures it).

The objective is a block too (Config.objective, blocks.py's objective). landmarks is the design
above. mask is the fully latent objective of the owner's ask of 2026-10-30 ("start with one of the
fully latent space approaches", since the morphometrics code's state was not known): the decoder's
two logits at the half scale are the privileged channels themselves, the target vertebra's mask and
every vertebra's, so the mask is both what the ladder takes down and what the network must give
back, the feature-matching term pulls the CT's features to the mask's as before, and nothing is
measured anywhere, no oracle and no landmark. A name head (NameHead) reads each crop's level name
off the bottleneck, the deepest fused features pooled to one vector a crop, which is the latent a
later shape prior is fit on, so the chain's two questions, which vertebra and how many, are asked
of the network's own representation. What the annealer leaves is then read on a held-out CT by
the CT-only path's Dice, surface distance and names right against the mask it never saw
(train.evaluate_masks). Under it the model's call gives the logits, the latent, the name logits and
the two branches' features, and read() gives the logits as they are.

The network itself is a block (the owner's ask of 2026-10-29: the final architecture is not
chosen): ARCHITECTURES names each one, blocks.py's architecture word chooses it, and Model builds
its two encoders and its decoder from the entry, so a new architecture is one entry here and one
value in the table. The frame every entry keeps is the fusion above: an encoder gives features at
a half, a quarter and an eighth of the crop, the same shapes from either branch, and a decoder
reads the fused three and gives one heatmap logit per landmark at the half scale.

- residual-unet, the smoke run's: three strided residual blocks an encoder (Block), the decoder
  up from the eighth with the fused features of each scale beside.
- plain-unet: the same layout with plain blocks, two convolutions and no residual.
- probe: the framework's test piece, a model whose answer is known before it trains. Its mask
  branch has no parameter: the target channel under a fixed window round the body (PROBE_WINDOW_MM,
  which leaves the processes out), pooled to the three scales. Its CT branch has two, a soft
  threshold sigmoid((c - tau) / sigma) of the normalised CT channel c (HU over HU_SCALE), the
  same pooling after it, so the only thing it can learn is where bone begins. Its decoder has
  none: each landmark's logit is PROBE_GATE times the half-scale blob plus PROBE_TILT_PER_MM
  times the voxel's millimetres along the landmark's direction (landmark_directions: right +x,
  anterior +y, superior +z and their opposites), so the soft-argmax lands near the body's
  extreme in that direction, a few millimetres inside it, where the oracle's chord end lies for
  the end-plates and the height and does not for the canal, whose error is large and fixed. So:
  the mask branch's error is one number a run reproduces to the bit, with no seed in it; the
  feature-matching loss teaches the CT branch, since at lambda 1 the ladder's own soft threshold
  of the CT at BONE_HU and THRESHOLD_WIDTH_HU is what the mask branch shows, and the CT branch's
  optimum there is (tau, sigma) = (BONE_HU, THRESHOLD_WIDTH_HU) over HU_SCALE exactly, a zero of
  the feature loss; earlier on the ladder it is the threshold that best tells the phantom's bone
  (trabecular 230 HU, cortex 800) from its disc (90) and soft tissue (40), between the two; and
  every term of the loss, the calibration, the naming layer, the session and the search run over
  it as over any network. tests/test_autoanatomist_probe.py holds these.
- transunet: TransUNet (Chen et al., arXiv 2102.04306, 2021) in 3-D: the residual-unet's three
  strided blocks, then TRANSUNET_DEPTH transformer layers over the eighth scale's voxels as tokens,
  added to them, so the bottleneck, which the name head and the latent read, sees the whole crop at
  once; the residual-unet's decoder.
- unetr: UNETR (Hatamizadeh et al., WACV 2022) at this crop's size: the crop cut into 8-voxel
  patches, each a token, through UNETR_DEPTH transformer layers with no convolution between; the
  half and the quarter scales are read off the layers a third and two thirds up, resized and refined
  by one residual block each; the residual-unet's decoder. Of the five it leans least on locality.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence, Tuple

import jax
import jax.numpy as jnp
import numpy as np
from flax import nnx

from schwingcheck import chain as CH

from . import crops, gates, ladder
from .specs import SEVEN, landmarks, values

HU_RANGE = (-1000.0, 3000.0)        # the CT is clipped here and divided by HU_SCALE: air -1, dense cortex 1 to 2
HU_SCALE = 1000.0


NORMALISE = ("clip", "clip-zscore")
DEFAULT_ARCHITECTURE = "residual-unet"
OBJECTIVES = ("landmarks", "mask")
MASK_CHANNELS = 2                   # the privileged channels the mask objective gives back: the target's and every vertebra's

# The probe's constants (the module's docstring): the window round the body in the crop's local
# millimetres (x to the right, y anterior, z up; the crop's centre is SHIFT_MM in front of the
# canal's centre, the body in front of that and the arch and the processes behind), the logit a
# voxel in the blob has over one outside, the logit a millimetre along a landmark's direction adds,
# and where the CT branch's threshold and width start, in the normalised CT's units.
PROBE_WINDOW_MM = ((-32.0, 32.0), (-12.0, 40.0), (-20.0, 20.0))
PROBE_GATE = 20.0
PROBE_TILT_PER_MM = 1.0
PROBE_START = (0.0, 0.2)
PROBE_OPTIMUM = (gates.BONE_HU / HU_SCALE, ladder.THRESHOLD_WIDTH_HU / HU_SCALE)
PROBE_WIDTH_FLOOR = 0.01
# Each landmark's direction in the crop's frame (x right, y anterior, z up): the body's corners for
# the end-plates' ends and the posterior height's, where the oracle's chord ends lie; the body's
# posterior wall for the canal's anterior wall, which it is; and no direction, the blob's centre,
# for the canal's other walls, which lie in no body and the probe does not read.
R2 = 0.5 ** 0.5
DIRECTIONS = {"endplate.right": (R2, 0.0, R2), "endplate.left": (-R2, 0.0, R2),
              "endplate_depth.posterior": (0.0, -R2, R2), "endplate_depth.anterior": (0.0, R2, R2),
              "endplate_lower.right": (R2, 0.0, -R2), "endplate_lower.left": (-R2, 0.0, -R2),
              "endplate_lower_depth.posterior": (0.0, -R2, -R2), "endplate_lower_depth.anterior": (0.0, R2, -R2),
              "h_post.superior": (0.0, -R2, R2), "h_post.inferior": (0.0, -R2, -R2),
              "canal_ap.anterior": (0.0, -1.0, 0.0)}


@dataclass(frozen=True)
class Config:
    """The network's sizes: the measurements it places (their landmarks are its outputs), the
    encoders' widths at the three scales (a half, a quarter and an eighth of the crop), the crop
    it reads (crops.SHAPE at crops.SPACING_MM unless given), group norm's groups, how the CT
    channel is scaled (normalise: clip, the HU clipped to HU_RANGE over HU_SCALE; clip-zscore,
    the same then standardised crop by crop; blocks.py's normalise), the architecture, one of
    ARCHITECTURES (blocks.py's architecture), and the objective, one of OBJECTIVES (blocks.py's
    objective): landmarks, one heatmap logit per landmark, or mask, one logit per privileged
    channel, which the probe cannot give."""
    keys: Tuple[str, ...] = tuple(SEVEN)
    widths: Tuple[int, int, int] = (16, 32, 64)
    shape: Tuple[int, int, int] = crops.SHAPE
    spacing: float = crops.SPACING_MM
    groups: int = 8
    normalise: str = "clip"
    architecture: str = DEFAULT_ARCHITECTURE
    objective: str = "landmarks"

    def __post_init__(self):
        if self.normalise not in NORMALISE:
            raise ValueError("normalise takes %s, not %r" % (" or ".join(NORMALISE), self.normalise))
        if self.architecture not in ARCHITECTURES:
            raise ValueError("architecture takes %s, not %r" % (", ".join(ARCHITECTURES), self.architecture))
        if self.objective not in OBJECTIVES:
            raise ValueError("objective takes %s, not %r" % (" or ".join(OBJECTIVES), self.objective))
        if self.objective == "mask" and self.architecture == "probe":
            raise ValueError("the probe's decoder reads landmarks, so it takes no mask objective")

    @property
    def n_landmarks(self) -> int:
        return len(landmarks(self.keys))

    @property
    def n_outputs(self) -> int:
        """The decoder's logits at the half scale: one per landmark, or one per privileged channel."""
        return MASK_CHANNELS if self.objective == "mask" else self.n_landmarks


def ct_input(hu, normalise: str = "clip"):
    """The CT channel as the encoder reads it: (batch, X, Y, Z, 1) in HU to a unit scale, clipped;
    under clip-zscore each crop is then standardised to mean 0 and spread 1."""
    c = jnp.clip(hu, *HU_RANGE) / HU_SCALE
    if normalise == "clip-zscore":
        mean = jnp.mean(c, axis=(1, 2, 3), keepdims=True)
        sd = jnp.std(c, axis=(1, 2, 3), keepdims=True)
        c = (c - mean) / (sd + 1e-3)
    return c


class Block(nnx.Module):
    """Two 3x3x3 convolutions, each with group norm, and a residual, the first strided when the
    block halves the scale."""

    def __init__(self, cin: int, cout: int, groups: int, stride: int, rngs: nnx.Rngs):
        g = max(1, min(groups, cout))
        self.conv1 = nnx.Conv(cin, cout, (3, 3, 3), strides=stride, padding="SAME", rngs=rngs)
        self.norm1 = nnx.GroupNorm(cout, num_groups=g, rngs=rngs)
        self.conv2 = nnx.Conv(cout, cout, (3, 3, 3), padding="SAME", rngs=rngs)
        self.norm2 = nnx.GroupNorm(cout, num_groups=g, rngs=rngs)
        self.skip = nnx.Conv(cin, cout, (1, 1, 1), strides=stride, rngs=rngs) if (cin != cout or stride != 1) else None

    def __call__(self, x):
        h = nnx.gelu(self.norm1(self.conv1(x)))
        h = self.norm2(self.conv2(h))
        return nnx.gelu(h + (x if self.skip is None else self.skip(x)))


class PlainBlock(nnx.Module):
    """The same two convolutions with group norm and no residual: the plain-unet's block, so the
    search can tell what the residual buys."""

    def __init__(self, cin: int, cout: int, groups: int, stride: int, rngs: nnx.Rngs):
        g = max(1, min(groups, cout))
        self.conv1 = nnx.Conv(cin, cout, (3, 3, 3), strides=stride, padding="SAME", rngs=rngs)
        self.norm1 = nnx.GroupNorm(cout, num_groups=g, rngs=rngs)
        self.conv2 = nnx.Conv(cout, cout, (3, 3, 3), padding="SAME", rngs=rngs)
        self.norm2 = nnx.GroupNorm(cout, num_groups=g, rngs=rngs)

    def __call__(self, x):
        h = nnx.gelu(self.norm1(self.conv1(x)))
        return nnx.gelu(self.norm2(self.conv2(h)))


class Encoder(nnx.Module):
    """Three strided blocks: features at a half, a quarter and an eighth of the crop."""

    def __init__(self, cin: int, widths: Sequence[int], groups: int, rngs: nnx.Rngs, block=Block):
        w0, w1, w2 = widths
        self.b1 = block(cin, w0, groups, 2, rngs)
        self.b2 = block(w0, w1, groups, 2, rngs)
        self.b3 = block(w1, w2, groups, 2, rngs)

    def __call__(self, x) -> List[jnp.ndarray]:
        f1 = self.b1(x)
        f2 = self.b2(f1)
        return [f1, f2, self.b3(f2)]


def upsample_to(x, like):
    """x (batch, X, Y, Z, C) resized trilinearly to like's spatial shape."""
    return jax.image.resize(x, like.shape[:4] + x.shape[4:], "trilinear")


class Decoder(nnx.Module):
    """Up from the eighth to the half scale with the fused features of each scale beside, then
    one heatmap logit per landmark at the half scale."""

    def __init__(self, widths: Sequence[int], n_landmarks: int, groups: int, rngs: nnx.Rngs, block=Block):
        w0, w1, w2 = widths
        self.up2 = block(w2 + w1, w1, groups, 1, rngs)
        self.up1 = block(w1 + w0, w0, groups, 1, rngs)
        self.head = nnx.Conv(w0, n_landmarks, (1, 1, 1), rngs=rngs)

    def __call__(self, feats: Sequence[jnp.ndarray]):
        f1, f2, f3 = feats
        h = self.up2(jnp.concatenate([upsample_to(f3, f2), f2], -1))
        h = self.up1(jnp.concatenate([upsample_to(h, f1), f1], -1))
        return self.head(h)


N_NAMES = len(CH.NAMES)                 # the level names a crop can be given: naming.NAMES, the chain's


class NameHead(nnx.Module):
    """The mask objective's name head: the bottleneck (batch, x, y, z, C), the deepest fused features,
    pooled to one vector a crop by its mean over the voxels, which is the latent a later shape prior
    reads, then a hidden layer of the same width and one logit per level name (naming.NAMES), so a
    crop's name is read off what the network keeps of its vertebra and nothing is measured."""

    def __init__(self, width: int, n_names: int, rngs: nnx.Rngs):
        self.hidden = nnx.Linear(width, width, rngs=rngs)
        self.out = nnx.Linear(width, n_names, rngs=rngs)

    def __call__(self, bottleneck) -> Tuple[jnp.ndarray, jnp.ndarray]:
        latent = jnp.mean(bottleneck, axis=(1, 2, 3))
        return latent, self.out(jax.nn.relu(self.hidden(latent)))


def heatmap_grid(crop_shape: Sequence[int], spacing: float, heat_shape: Sequence[int]) -> np.ndarray:
    """The crop's local millimetres of each heatmap voxel's centre, (N, 3): the crop's extent
    divided evenly into the heatmap's voxels, centred as the crop is (crops.CropFrame)."""
    ticks = []
    for n, m in zip(crop_shape, heat_shape):
        step = n * spacing / m
        ticks.append((np.arange(m) - (m - 1) / 2.0) * step)
    return np.stack(np.meshgrid(*ticks, indexing="ij"), -1).reshape(-1, 3)


def soft_argmax(logits, grid):
    """Each landmark's expected position and covariance under the softmax of its heatmap:
    logits (batch, X, Y, Z, K), grid (X Y Z, 3); returns (batch, K, 3) and (batch, K, 3, 3)."""
    b, k = logits.shape[0], logits.shape[-1]
    p = jax.nn.softmax(logits.reshape(b, -1, k), axis=1)                   # (batch, N, K)
    g = jnp.asarray(grid, logits.dtype)
    mean = jnp.einsum("bnk,ni->bki", p, g)
    d = g[None, :, None, :] - mean[:, None]                                # (batch, N, K, 3)
    cov = jnp.einsum("bnk,bnki,bnkj->bkij", p, d, d)
    return mean, cov


def value_sigma(points, cov, keys: Sequence[str]):
    """Each value's standard deviation by the delta method, (batch, M): the value's gradient in
    each point, from specs.values, against the point's covariance, the points independent."""
    jac = jax.vmap(jax.jacfwd(lambda P: values(P, keys, jnp)))(points)      # (batch, M, K, 3)
    var = jnp.einsum("bmki,bkij,bmkj->bm", jac, cov, jac)
    return jnp.sqrt(jnp.maximum(var, 0.0))


# --- the probe ---------------------------------------------------------------------------------------


def landmark_directions(keys: Sequence[str]) -> np.ndarray:
    """Each landmark's direction in the crop's frame, (K, 3), from DIRECTIONS; zero for a landmark
    it does not name."""
    return np.array([DIRECTIONS.get(name, (0.0, 0.0, 0.0)) for name in landmarks(keys)], np.float32)


def probe_window(shape: Sequence[int], spacing: float) -> np.ndarray:
    """1 at the crop's voxels within PROBE_WINDOW_MM, 0 elsewhere, (X, Y, Z)."""
    grid = heatmap_grid(shape, spacing, shape).reshape(tuple(shape) + (3,))
    inside = np.ones(tuple(shape), bool)
    for axis, (lo, hi) in enumerate(PROBE_WINDOW_MM):
        inside &= (grid[..., axis] >= lo) & (grid[..., axis] <= hi)
    return inside.astype(np.float32)


def pooled(x):
    """x (batch, X, Y, Z, C) averaged over 2x2x2 windows at stride 2, the last window padded as a
    strided SAME convolution pads, so the probe's scales are the other architectures'."""
    window, strides = (1, 2, 2, 2, 1), (1, 2, 2, 2, 1)
    total = jax.lax.reduce_window(x, 0.0, jax.lax.add, window, strides, "SAME")
    count = jax.lax.reduce_window(jnp.ones_like(x), 0.0, jax.lax.add, window, strides, "SAME")
    return total / count


def probe_features(blob, window) -> List[jnp.ndarray]:
    """The blob (batch, X, Y, Z) under the window, as one channel at the three scales."""
    x = (blob * window)[..., None]
    f1 = pooled(x)
    f2 = pooled(f1)
    return [f1, f2, pooled(f2)]


class ProbeEncoder(nnx.Module):
    """The probe's encoder (the module's docstring): the mask branch reads the target channel as
    it is; the CT branch reads its soft threshold of the normalised CT channel, the two parameters
    tau and sigma, sigma held above PROBE_WIDTH_FLOOR."""

    def __init__(self, cfg: Config, branch: str, rngs: nnx.Rngs):
        self.shape, self.spacing = tuple(cfg.shape), float(cfg.spacing)
        self.learns = branch == "ct"
        if self.learns:
            self.tau = nnx.Param(jnp.float32(PROBE_START[0]))
            self.sigma = nnx.Param(jnp.float32(PROBE_START[1]))

    def threshold(self) -> Tuple[float, float]:
        """The CT branch's threshold and width as they stand, in the normalised CT's units."""
        return float(self.tau.value), float(jnp.maximum(self.sigma.value, PROBE_WIDTH_FLOOR))

    def __call__(self, x) -> List[jnp.ndarray]:
        channel = x[..., 0]
        if self.learns:
            channel = jax.nn.sigmoid((channel - self.tau.value) / jnp.maximum(self.sigma.value, PROBE_WIDTH_FLOOR))
        return probe_features(channel, jnp.asarray(probe_window(self.shape, self.spacing)))


class ProbeDecoder(nnx.Module):
    """The probe's decoder: no parameter; each landmark's logit is the half-scale blob times the
    gate plus the tilt along the landmark's direction, so a voxel outside the blob has none and
    the blob's extreme in that direction has the most. It passes no gradient back, so the CT
    branch learns from the privileged branch alone, through the feature-matching term, which is
    the path the probe tests."""

    def __init__(self, cfg: Config, rngs: nnx.Rngs):
        self.shape, self.spacing, self.keys = tuple(cfg.shape), float(cfg.spacing), tuple(cfg.keys)

    def __call__(self, feats: Sequence[jnp.ndarray]):
        f1 = jax.lax.stop_gradient(feats[0])
        heat = tuple(f1.shape[1:4])
        grid = heatmap_grid(self.shape, self.spacing, heat)                              # (N, 3)
        tilt = (grid @ landmark_directions(self.keys).T).reshape(heat + (-1,))          # (X, Y, Z, K)
        return f1 * (PROBE_GATE + PROBE_TILT_PER_MM * jnp.asarray(tilt, f1.dtype)[None])


# --- the transformers --------------------------------------------------------------------------------

# The transformers' sizes, this module's choices: the encoder's tokens are the eighth scale's voxels,
# one token each, of width widths[2]; a layer is pre-norm self-attention over every token and a
# two-layer perceptron TRANSFORMER_MLP times as wide; the heads are the most of TRANSFORMER_HEADS
# that divide the width. TransUNet puts TRANSUNET_DEPTH layers after two convolutional blocks;
# UNETR is attention from the patches up, UNETR_DEPTH layers, the half and the quarter scales read
# off its earlier layers.
TRANSFORMER_HEADS = 4
TRANSFORMER_MLP = 2
TRANSUNET_DEPTH = 4
UNETR_DEPTH = 6
UNETR_PATCH = 8
POSITION_INIT_SD = 0.02


def eighth_of(shape: Sequence[int]) -> Tuple[int, int, int]:
    """The eighth scale's voxels of a crop, as three strided SAME convolutions give them."""
    return tuple(-(-int(n) // 8) for n in shape)


def scale_of(shape: Sequence[int], factor: int) -> Tuple[int, ...]:
    """A crop's voxels at 1/factor, rounded up as strided SAME convolutions round."""
    return tuple(-(-int(n) // factor) for n in shape)


def heads_for(width: int) -> int:
    """The most heads, up to TRANSFORMER_HEADS, that divide the width evenly."""
    return next(h for h in range(min(TRANSFORMER_HEADS, width), 0, -1) if width % h == 0)


class Attention(nnx.Module):
    """Multi-head self-attention over a sequence (batch, N, D): every token reads every other, so a
    feature at one vertebra's voxel can depend on the whole crop at once, which a convolution's
    receptive field reaches only through depth."""

    def __init__(self, width: int, rngs: nnx.Rngs):
        self.heads = heads_for(width)
        self.qkv = nnx.Linear(width, 3 * width, rngs=rngs)
        self.out = nnx.Linear(width, width, rngs=rngs)

    def __call__(self, x):
        b, n, d = x.shape
        h = self.heads
        q, k, v = jnp.split(self.qkv(x).reshape(b, n, 3, h, d // h), 3, axis=2)
        q, k, v = (t[:, :, 0].transpose(0, 2, 1, 3) for t in (q, k, v))          # (batch, heads, N, d / heads)
        weights = jax.nn.softmax(jnp.einsum("bhnc,bhmc->bhnm", q, k) / jnp.sqrt(d // h), axis=-1)
        mixed = jnp.einsum("bhnm,bhmc->bhnc", weights, v).transpose(0, 2, 1, 3).reshape(b, n, d)
        return self.out(mixed)


class TransformerLayer(nnx.Module):
    """One pre-norm transformer layer: self-attention and a perceptron, each with a residual."""

    def __init__(self, width: int, rngs: nnx.Rngs):
        self.norm1 = nnx.LayerNorm(width, rngs=rngs)
        self.attention = Attention(width, rngs)
        self.norm2 = nnx.LayerNorm(width, rngs=rngs)
        self.fc1 = nnx.Linear(width, TRANSFORMER_MLP * width, rngs=rngs)
        self.fc2 = nnx.Linear(TRANSFORMER_MLP * width, width, rngs=rngs)

    def __call__(self, x):
        x = x + self.attention(self.norm1(x))
        return x + self.fc2(nnx.gelu(self.fc1(self.norm2(x))))


class Tokens(nnx.Module):
    """A volume (batch, X, Y, Z, D) as tokens with a learnt position each, through a stack of
    layers; gives every layer's output back as a volume of the same shape."""

    def __init__(self, grid: Sequence[int], width: int, depth: int, rngs: nnx.Rngs):
        self.grid = tuple(int(n) for n in grid)
        n = int(np.prod(self.grid))
        self.position = nnx.Param(POSITION_INIT_SD * jax.random.normal(rngs.params(), (1, n, width)))
        self.layers = nnx.List([TransformerLayer(width, rngs) for _ in range(depth)])
        self.norm = nnx.LayerNorm(width, rngs=rngs)

    def __call__(self, x) -> List[jnp.ndarray]:
        b, d = x.shape[0], x.shape[-1]
        t = x.reshape(b, -1, d) + self.position.value
        outs = []
        for layer in self.layers:
            t = layer(t)
            outs.append(t)
        outs[-1] = self.norm(outs[-1])
        return [o.reshape((b,) + self.grid + (d,)) for o in outs]


class TransUNetEncoder(nnx.Module):
    """TransUNet's encoder (Chen et al., 2021, in 3-D): two strided residual blocks give the half and
    the quarter scales, a third the eighth, and TRANSUNET_DEPTH transformer layers over the eighth's
    voxels as tokens add the whole crop's context to it, the residual kept so the convolutional
    features pass through."""

    def __init__(self, cfg: Config, branch: str, rngs: nnx.Rngs):
        w0, w1, w2 = cfg.widths
        self.b1 = Block(1 if branch == "ct" else 2, w0, cfg.groups, 2, rngs)
        self.b2 = Block(w0, w1, cfg.groups, 2, rngs)
        self.b3 = Block(w1, w2, cfg.groups, 2, rngs)
        self.tokens = Tokens(eighth_of(cfg.shape), w2, TRANSUNET_DEPTH, rngs)

    def __call__(self, x) -> List[jnp.ndarray]:
        f1 = self.b1(x)
        f2 = self.b2(f1)
        f3 = self.b3(f2)
        return [f1, f2, f3 + self.tokens(f3)[-1]]


class UNETREncoder(nnx.Module):
    """UNETR's encoder (Hatamizadeh et al., WACV 2022, at this crop's size): the crop cut into
    UNETR_PATCH-voxel cubes, each a token of width widths[2] by one strided convolution, then
    UNETR_DEPTH transformer layers and nothing convolutional between; the eighth scale is the last
    layer, the quarter the one two thirds up and the half the one a third up, each resized to its scale
    and refined by one residual block, so attention alone carries the crop to the bottleneck."""

    def __init__(self, cfg: Config, branch: str, rngs: nnx.Rngs):
        w0, w1, w2 = cfg.widths
        self.shape = tuple(cfg.shape)
        self.embed = nnx.Conv(1 if branch == "ct" else 2, w2, (UNETR_PATCH,) * 3, strides=UNETR_PATCH,
                              padding="SAME", rngs=rngs)
        self.tokens = Tokens(scale_of(cfg.shape, UNETR_PATCH), w2, UNETR_DEPTH, rngs)
        self.to_half = Block(w2, w0, cfg.groups, 1, rngs)
        self.to_quarter = Block(w2, w1, cfg.groups, 1, rngs)

    def __call__(self, x) -> List[jnp.ndarray]:
        layers = self.tokens(self.embed(x))
        b, d = x.shape[0], layers[0].shape[-1]
        early, middle, last = layers[len(layers) // 3 - 1], layers[2 * len(layers) // 3 - 1], layers[-1]
        half = jax.image.resize(early, (b,) + scale_of(self.shape, 2) + (d,), "trilinear")
        quarter = jax.image.resize(middle, (b,) + scale_of(self.shape, 4) + (d,), "trilinear")
        return [self.to_half(half), self.to_quarter(quarter), last]


def unet_decoder(cfg: Config, rngs: nnx.Rngs) -> nnx.Module:
    return Decoder(cfg.widths, cfg.n_outputs, cfg.groups, rngs, block=Block)


# --- the architectures -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Architecture:
    """One network the model spot takes: its name, what it is, and how an encoder (for the branch
    "ct", reading one channel, or "mask", reading two) and the decoder are built from a Config."""
    name: str
    what: str
    encoder: Callable[[Config, str, nnx.Rngs], nnx.Module]
    decoder: Callable[[Config, nnx.Rngs], nnx.Module]


def unet(block) -> Tuple[Callable, Callable]:
    def encoder(cfg: Config, branch: str, rngs: nnx.Rngs) -> nnx.Module:
        return Encoder(1 if branch == "ct" else 2, cfg.widths, cfg.groups, rngs, block=block)

    def decoder(cfg: Config, rngs: nnx.Rngs) -> nnx.Module:
        return Decoder(cfg.widths, cfg.n_outputs, cfg.groups, rngs, block=block)

    return encoder, decoder


ARCHITECTURES: Dict[str, Architecture] = {
    "residual-unet": Architecture("residual-unet", "three strided residual blocks an encoder, the decoder up from the "
                                  "eighth with the fused features beside; the smoke run's", *unet(Block)),
    "plain-unet": Architecture("plain-unet", "the same layout with plain blocks: two convolutions, no residual",
                               *unet(PlainBlock)),
    "probe": Architecture("probe", "the framework's probe: a windowed blob of the mask or of a learnt soft threshold "
                          "of the CT, read at the body's extremes; its answer is known before it trains",
                          ProbeEncoder, ProbeDecoder),
    "transunet": Architecture("transunet", "TransUNet: two strided residual blocks, a third to the eighth and four "
                              "transformer layers over its voxels as tokens; the residual-unet's decoder",
                              TransUNetEncoder, unet_decoder),
    "unetr": Architecture("unetr", "UNETR: the crop in 8-voxel patches as tokens through six transformer layers, the "
                          "half and the quarter read off the earlier layers; the residual-unet's decoder",
                          UNETREncoder, unet_decoder),
}


def count_parameters(model: nnx.Module) -> int:
    """How many numbers the model learns."""
    return int(sum(int(np.prod(np.shape(v))) for v in jax.tree.leaves(nnx.state(model, nnx.Param))))


class Model(nnx.Module):
    """The two encoders, the decoder and the reading of its heatmaps (the module's docstring),
    built from the architecture the Config names."""

    def __init__(self, cfg: Config, rngs: nnx.Rngs):
        self.cfg = cfg
        arch = ARCHITECTURES[cfg.architecture]
        self.ct = arch.encoder(cfg, "ct", rngs)
        self.mask = arch.encoder(cfg, "mask", rngs)
        self.decoder = arch.decoder(cfg, rngs)
        self.names = NameHead(cfg.widths[2], N_NAMES, rngs) if cfg.objective == "mask" else None

    def features(self, hu, masks) -> Tuple[List[jnp.ndarray], List[jnp.ndarray]]:
        return self.ct(ct_input(hu, self.cfg.normalise)), self.mask(masks)

    def read(self, logits) -> Dict[str, jnp.ndarray]:
        """Landmarks, their covariances, the values and their deltas from the heatmap logits; under
        the mask objective the logits themselves, one per privileged channel."""
        if self.cfg.objective == "mask":
            return {"logits": logits}
        grid = heatmap_grid(self.cfg.shape, self.cfg.spacing, logits.shape[1:4])
        points, cov = soft_argmax(logits, grid)
        return {"points": points, "cov": cov, "values": values(points, self.cfg.keys, jnp),
                "sigma": value_sigma(points, cov, self.cfg.keys)}

    def __call__(self, hu, masks, w) -> Dict[str, object]:
        """The fused pass: hu (batch, X, Y, Z, 1) in HU, masks (batch, X, Y, Z, 2) already down
        the ladder, w the fusion weight; the reading of the decoder's logits and both encoders'
        features."""
        f_ct, f_mask = self.features(hu, masks)
        fused = [(1.0 - w) * a + w * b for a, b in zip(f_ct, f_mask)]
        out = self.read(self.decoder(fused))
        if self.names is not None:
            out["latent"], out["name_logits"] = self.names(fused[2])
        out["f_ct"], out["f_mask"] = f_ct, f_mask
        return out

    def ct_only(self, hu) -> Dict[str, jnp.ndarray]:
        """The test-time path: the CT alone, E_ct and the decoder, which is the fused pass at w 0
        without computing the mask's branch."""
        f_ct = self.ct(ct_input(hu, self.cfg.normalise))
        out = self.read(self.decoder(f_ct))
        if self.names is not None:
            out["latent"], out["name_logits"] = self.names(f_ct[2])
        return out
