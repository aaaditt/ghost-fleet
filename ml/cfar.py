"""Classical baseline: cell-averaging CFAR ship detection on a SAR chip.

For each pixel, compare its VV power with the mean and spread of a background
ring (outside a guard band). Pixels above mean + k * std are target pixels;
connected groups of at least `min_pixels` are detections. No learning, so it
is the yardstick the CNN has to beat.
"""

import numpy as np
from scipy import ndimage


def _box_mean(x, size):
    return ndimage.uniform_filter(x, size=size, mode="reflect")


def detect(chip, k=5.0, guard=7, background=31, min_pixels=3):
    """Return (list of detections, score). Detections: dict(row, col, pixels, peak)."""
    vv = np.nan_to_num(chip[0], nan=0.0).astype(np.float64)
    # Ring statistics = big box minus guard box, via summed means.
    nb, ng = background ** 2, guard ** 2
    s_b, s_g = _box_mean(vv, background) * nb, _box_mean(vv, guard) * ng
    q_b, q_g = _box_mean(vv ** 2, background) * nb, _box_mean(vv ** 2, guard) * ng
    n = nb - ng
    mean = (s_b - s_g) / n
    var = np.maximum((q_b - q_g) / n - mean ** 2, 1e-12)
    z = (vv - mean) / np.sqrt(var)
    mask = z > k
    labels, count = ndimage.label(mask)
    dets = []
    for i in range(1, count + 1):
        rr, cc = np.nonzero(labels == i)
        if len(rr) < min_pixels:
            continue
        j = np.argmax(z[rr, cc])
        dets.append({"row": int(rr[j]), "col": int(cc[j]), "pixels": int(len(rr)), "peak": float(z[rr[j], cc[j]])})
    # Chip-level score for PR curves: strongest z among components big enough.
    score = max((d["peak"] for d in dets), default=float(np.max(z)) if min_pixels <= 1 else 0.0)
    return dets, score


def chip_score(chip, guard=7, background=31, min_pixels=3):
    """Threshold-free score: max z over components of >= min_pixels at a low k (for sweeping)."""
    _, score = detect(chip, k=3.0, guard=guard, background=background, min_pixels=min_pixels)
    return score
