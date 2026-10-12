"""A procedurally drawn source picture for the trailer (no third-party artwork): dusk over water, layered hills, stars and a low sun."""
import numpy as np


def dusk(w=1920, h=1080, seed=7):
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, h)[:, None, None]
    x = np.linspace(0, 1, w)[None, :, None]
    horizon = 0.62
    top, mid, low = np.array([18, 16, 58.]), np.array([142, 62, 120.]), np.array([255, 170, 120.])
    t = np.clip(y / horizon, 0, 1)
    sky = np.where(t < .6, top + (mid - top) * (t / .6), mid + (low - mid) * ((t - .6) / .4))
    img = np.broadcast_to(sky, (h, w, 3)).copy()
    # stars
    ys, xs = rng.integers(0, int(h * .38), 420), rng.integers(0, w, 420)
    img[ys, xs] = 255 * rng.uniform(.5, 1, (420, 1))
    # sun
    X, Y = np.meshgrid(np.linspace(0, 1, w) * w / h, np.linspace(0, 1, h))
    cx, cy = 0.66 * w / h, horizon - 0.07
    d = np.hypot(X - cx, Y - cy)
    glow = np.exp(-(d / .22) ** 2)[..., None]
    img = img + glow * np.array([120, 70, 20.])
    img = np.where((d < .075)[..., None], np.array([255, 236, 190.]), img)
    # layered hills
    xx = np.linspace(0, 1, w)
    for i, (base, amp, col) in enumerate([(.60, .05, (96, 44, 104)), (.64, .06, (62, 30, 86)), (.69, .07, (34, 20, 62))]):
        ph = rng.uniform(0, 6.28, 3)
        prof = base + amp * (np.sin(xx * 5 + ph[0]) * .5 + np.sin(xx * 11 + ph[1]) * .3 + np.sin(xx * 23 + ph[2]) * .12)
        mask = (np.linspace(0, 1, h)[:, None] > prof[None, :])[..., None]
        img = np.where(mask & (np.linspace(0, 1, h)[:, None, None] < horizon + .12 + i * .02), np.array(col, float), img)
    # water: mirror the upper scene, ripple it, darken
    wy0 = int(h * (horizon + .07))
    n = h - wy0
    refl = img[wy0 - n:wy0][::-1].copy() if wy0 - n >= 0 else np.pad(img[:wy0][::-1], ((0, n - wy0), (0, 0), (0, 0)), mode="edge")
    rows = np.arange(n)
    shift = (np.sin(rows * .35) * (4 + rows * .05)).astype(int)
    refl = np.stack([np.roll(refl[i], shift[i], axis=0) for i in range(n)])
    fade = np.linspace(.85, .35, n)[:, None, None]
    img[wy0:] = refl * fade + np.array([10, 18, 50.]) * (1 - fade)
    img += rng.normal(0, 2.0, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)
