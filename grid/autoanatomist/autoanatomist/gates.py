"""Soft gates and soft morphology in JAX, differentiable in their thresholds, widths and radii.

A hard threshold of a CT at a Hounsfield level, or a binary dilation by a ball, has no gradient
in the level or the radius, so nothing can be learnt or analysed through them. Each gate here is
the smooth form whose limit is the hard one:

- soft_threshold(x, t, width) = sigmoid((x - t) / width), the step at t as width goes to 0;
- soft_band(x, lo, hi, width), inside lo to hi (the canal's -50 to 50 HU of scanimport.intensity);
- soft_dilate(m, radius, tau, edge): a smoothed maximum over a ball, tau times the log of the mean
  of exp((m(p + q) - phi(q)) / tau) over offsets q, where phi(q) = softplus((|q| - radius) / edge)
  is near 0 inside the ball, where the radius exceeds |q| by much more than edge, and grows linearly
  outside it. tau sets how hard the maximum is and edge how sharp the ball's rim is: the defaults
  (tau 0.05, edge 0.5 voxels) give a soft cone rather than a ball, a lone voxel dilated by a radius
  of 2 reading 0.97 at its centre, 0.86 one voxel out, 0.53 at the square root of 3 and 0.30 at 2,
  while the tests' tau 0.004 and edge 0.01 give the ball (0.99 inside it, 0.29 at a voxel exactly
  at the radius, where the softplus is log 2, which is why the tests take radii between the grid's
  distances). As both go to 0 it is the hard dilation by the ball, within tau log N of it for a
  ball of N voxels plus what the rim leaves (a softplus of width edge is not 0 at the voxels
  nearest the radius, so the tests allow 0.01 for it beside tau log N) once the rim is narrow
  beside the gaps between voxels' distances, and a constant mask is left as it is at every tau.
  It is differentiable in the radius through the rim.
  soft_erode is its dual, 1 - soft_dilate(1 - m), and opening and closing compose them;
- gaussian_blur(m, sigma), separable, differentiable in sigma, the other smoothing the design
  notes name.

The Hounsfield levels are scanimport.intensity's, imported from it with their sources there: the
body's outline at -500 HU, bone at 200 HU, the floor of an edge at 130 HU, the canal's contents at
-50 to 50 HU; the ladder uses the 200 HU level. Kernel sizes are fixed when a function is traced, so a radius or a sigma is bounded
by the `max_radius` or `max_sigma` given in voxels; the tests hold each gate to its hard limit and
its gradients to finite differences.
"""
from __future__ import annotations

import math

import jax
import jax.numpy as jnp

from scanimport.intensity import AIR_BODY_HU, BONE_FLOOR_HU, BONE_HU, CANAL_HU  # noqa: F401


def soft_threshold(x, t, width):
    return jax.nn.sigmoid((x - t) / width)


def soft_band(x, lo, hi, width):
    return soft_threshold(x, lo, width) * (1.0 - soft_threshold(x, hi, width))


def rim_penalty(radius, max_radius: int, edge, spacing=1.0):
    """phi on a (2R + 1)^3 grid of offsets, R = max_radius voxels: softplus((|q| - radius) / edge),
    |q| and the radius in millimetres (offsets times spacing)."""
    R = int(max_radius)
    ticks = jnp.arange(-R, R + 1, dtype=jnp.result_type(radius, float)) * spacing
    d = jnp.sqrt(ticks[:, None, None] ** 2 + ticks[None, :, None] ** 2 + ticks[None, None, :] ** 2)
    return jax.nn.softplus((d - radius) / edge)


def conv3(x, kernel):
    """x (batch, X, Y, Z) correlated with a (k, k, k) kernel, the batch kept, 'VALID'."""
    lhs = x[:, None]
    rhs = kernel[None, None]
    return jax.lax.conv_general_dilated(lhs, rhs.astype(x.dtype), (1, 1, 1), "VALID",
                                        dimension_numbers=("NCDHW", "OIDHW", "NCDHW"))[:, 0]


def soft_dilate(m, radius, tau=0.05, edge=0.5, max_radius: int = 4, spacing=1.0):
    """The smoothed maximum of m (batch, X, Y, Z), values in [0, 1], over a soft ball of `radius`
    millimetres (the module's docstring), taken over the part of the ball inside the volume, so a
    constant is kept up to the volume's edges and the hard limit is the dilation that pads with 0.

    Computed as 1 + tau log(sum_q k(q) exp((m(p + q) - 1) / tau) / sum_q k(q)), both sums over the
    offsets that stay inside the volume, k = exp(-(phi - min phi) / tau), which cannot overflow
    for m in [0, 1]. Far from any mask the terms are exp(-1 / tau), which float32 holds for tau of
    0.012 or more, so take tau of 0.02 or more in float32 and float64 for a harder maximum; a sum
    that underflows all the same is floored at the dtype's smallest normal number, so the result
    stays finite."""
    R = int(max_radius)
    phi = rim_penalty(radius, R, edge, spacing)
    k = jnp.exp(-(phi - jnp.min(phi)) / tau)
    pad = ((0, 0), (R, R), (R, R), (R, R))
    e = jnp.pad(jnp.exp((m - 1.0) / tau), pad)
    inside = jnp.pad(jnp.ones_like(m[:1]), pad)
    tiny = jnp.finfo(e.dtype).tiny
    total = jnp.maximum(conv3(e, k), tiny)
    mass = jnp.maximum(conv3(inside, k), tiny)
    return 1.0 + tau * (jnp.log(total) - jnp.log(mass))


def soft_erode(m, radius, tau=0.05, edge=0.5, max_radius: int = 4, spacing=1.0):
    """The dual of soft_dilate, 1 - soft_dilate(1 - m), over the same part of the ball inside the
    volume, so its hard limit is the erosion that pads with 1."""
    return 1.0 - soft_dilate(1.0 - m, radius, tau, edge, max_radius, spacing)


def soft_open(m, radius, **kw):
    return soft_dilate(soft_erode(m, radius, **kw), radius, **kw)


def soft_close(m, radius, **kw):
    return soft_erode(soft_dilate(m, radius, **kw), radius, **kw)


def gaussian_kernel(sigma, max_sigma: float):
    """A normalised 1-D Gaussian of `sigma` voxels on 2 ceil(3 max_sigma) + 1 taps."""
    R = int(math.ceil(3.0 * max_sigma))
    t = jnp.arange(-R, R + 1, dtype=jnp.result_type(sigma, float))
    k = jnp.exp(-0.5 * (t / jnp.maximum(sigma, 1e-3)) ** 2)
    return k / jnp.sum(k), R


def gaussian_blur(m, sigma, max_sigma: float = 3.0):
    """m (batch, X, Y, Z) blurred by a Gaussian of `sigma` voxels along each axis in turn, the
    edge value carried outward (scipy.ndimage's 'nearest')."""
    k, R = gaussian_kernel(sigma, max_sigma)
    out = m
    for axis in (1, 2, 3):
        pad = [(0, 0)] * 4
        pad[axis] = (R, R)
        p = jnp.pad(out, pad, mode="edge")
        shape = [1, 1, 1]
        shape[axis - 1] = 2 * R + 1
        out = conv3(p, k.reshape(shape))
    return out
