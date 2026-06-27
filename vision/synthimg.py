"""Synthetic servo imagery + a feature-baseline classifier.

Why synthetic: it lets the *entire* vision path — dataset, evaluation,
quantization integration, the live AND-verdict — run with zero hardware and zero
training, so the project is demoable on any machine. Swap in real shroud captures
(vision/capture.py) and a trained CNN for production; the taxonomy and interfaces
are identical.

Scene model (an MG996R seated in the nest, viewed through the diffuser shroud):
  - case   : large gray rectangle (the servo body)
  - horn   : a bright insert near the case top (the output horn / spline)
  - faults :
      OK             : case centered on the datums, horn present, nothing foreign
      case_defect    : case shifted / misaligned (cracked or mis-seated body)
      horn_missing   : the horn pocket is empty (dark)
      foreign_object : an OK scene plus a stray (red) object

The baseline classifier reads three interpretable features (case offset, horn
brightness, redness) and softmaxes them. It is deliberately simple — the real
model is the CNN — but it produces a genuine, non-trivial confusion matrix on
these images, which is what the rest of the pipeline consumes.
"""
from __future__ import annotations

import numpy as np

# Canonical taxonomy. Keep in sync with config/mg996r.json -> vision.classes.
CLASSES = ["OK", "horn_missing", "case_defect", "foreign_object"]
PASS_CLASS = "OK"


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render(class_name: str, size=(96, 96), rng: np.random.Generator | None = None) -> np.ndarray:
    """Render one labeled scene -> uint8 (H, W, 3)."""
    if rng is None:
        rng = np.random.default_rng()
    H, W = int(size[0]), int(size[1])
    img = np.full((H, W, 3), 28, dtype=np.float32)
    img += rng.normal(0, 4, img.shape)  # sensor/background noise

    # Servo body geometry (fractions of frame).
    hh, hw = 0.50 * H, 0.50 * W
    ht, hl = 0.30 * H, 0.25 * W

    # Small seating jitter even for good units (real fixtures aren't perfect).
    ht += rng.normal(0, 0.012 * H)
    hl += rng.normal(0, 0.012 * W)

    if class_name == "case_defect":
        # Body off the datums; sometimes only slightly (near the decision line).
        mag = rng.uniform(0.09, 0.20)
        ang = rng.uniform(0, 2 * np.pi)
        hl += np.cos(ang) * mag * W
        ht += np.sin(ang) * mag * H

    _rect(img, ht, hl, hh, hw, color=(150, 152, 150), rng=rng)

    # Horn insert near body top-left.
    pt, pl = ht + 0.06 * H, hl + 0.06 * W
    ph, pw = 0.14 * H, 0.16 * W
    if class_name == "horn_missing":
        val = rng.uniform(26, 70)                 # empty dark pocket
        _rect(img, pt, pl, ph, pw, color=(val, val, val), rng=rng)
    else:
        v = rng.uniform(205, 240)
        _rect(img, pt, pl, ph, pw, color=(v, v, v * 0.96), rng=rng)

    if class_name == "foreign_object":
        # Stray red object somewhere in frame; size varies (some small/ambiguous).
        s = rng.uniform(0.08, 0.16)
        ot = rng.uniform(0.05, 0.85 - s) * H
        ol = rng.uniform(0.05, 0.85 - s) * W
        _rect(img, ot, ol, s * H, s * W,
              color=(rng.uniform(170, 230), rng.uniform(10, 45), rng.uniform(10, 45)), rng=rng)

    return np.clip(img, 0, 255).astype(np.uint8)


def _rect(img, top, left, h, w, color, rng):
    H, W = img.shape[:2]
    t, l = int(round(top)), int(round(left))
    b, r = int(round(top + h)), int(round(left + w))
    t, l = max(0, t), max(0, l)
    b, r = min(H, b), min(W, r)
    if b <= t or r <= l:
        return
    patch = np.empty((b - t, r - l, 3), dtype=np.float32)
    for c in range(3):
        patch[:, :, c] = color[c] + rng.normal(0, 5, (b - t, r - l))
    img[t:b, l:r, :] = patch


# --------------------------------------------------------------------------- #
# Feature-baseline classifier
# --------------------------------------------------------------------------- #
def _features(img: np.ndarray):
    a = img.astype(np.float32)
    H, W = a.shape[:2]
    gray = a.mean(axis=2)

    # Body mask -> centroid -> offset from frame center.
    mask = gray > 100
    ys, xs = np.nonzero(mask)
    if xs.size > 0:
        cx, cy = xs.mean(), ys.mean()
    else:
        cx, cy = W / 2.0, H / 2.0
    offset = float(np.hypot((cx - W / 2.0) / W, (cy - H / 2.0) / H))

    # Horn brightness, sampled RELATIVE to the detected body (so a misaligned
    # body whose horn moved with it isn't mistaken for a missing horn).
    px = cx - 0.11 * W
    py = cy - 0.12 * H
    half = 0.05
    x0, x1 = int(px - half * W), int(px + half * W)
    y0, y1 = int(py - half * H), int(py + half * H)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(W, x1), min(H, y1)
    region = gray[y0:y1, x0:x1]
    horn_mean = float(region.mean()) if region.size else 0.0

    # Redness -> foreign object count.
    redness = a[..., 0] - 0.5 * (a[..., 1] + a[..., 2])
    foreign = float((redness > 80).sum())

    return offset, horn_mean, foreign


def classify_features(img: np.ndarray, classes=CLASSES, pass_class=PASS_CLASS):
    """Return (pred_class, {class: prob}). Probabilities are a softmax over
    interpretable anomaly scores, so sweeping a threshold on P(OK) is meaningful
    for choosing the operating point."""
    offset, horn_mean, foreign = _features(img)

    score = {
        "OK": 3.0,
        "case_defect": min(12.0, 7.0 * max(0.0, (offset - 0.06) / 0.06)),
        "horn_missing": min(12.0, 7.0 * max(0.0, (120.0 - horn_mean) / 120.0)),
        "foreign_object": min(12.0, foreign / 15.0),
    }
    s = np.array([score.get(c, 0.0) for c in classes], dtype=np.float64)
    s -= s.max()
    e = np.exp(s)
    p = e / e.sum()
    probs = {c: float(p[i]) for i, c in enumerate(classes)}
    pred = classes[int(np.argmax(p))]
    return pred, probs
