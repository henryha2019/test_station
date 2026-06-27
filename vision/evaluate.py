"""Evaluate the inspector on the held-out test split: confusion matrix,
per-class precision/recall, and the recall-optimized operating point.

The headline number this prints is the one that separates an ATE from a demo:
  "at ok_threshold=T: defect recall = X%, false-reject = Y%"
i.e. how many defects we catch vs how many good units we needlessly retest.

Runs on the feature baseline with zero training; pass --model <int8.tflite> to
score the real CNN.

    python -m vision.evaluate
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from host.config import DEFAULT_CONFIG, load_config  # noqa: E402
from vision.dataset import load_manifest  # noqa: E402
from vision.synthimg import classify_features  # noqa: E402


def _load_img(path, size):
    img = Image.open(path).convert("RGB").resize((size[1], size[0]))
    return np.asarray(img, dtype=np.uint8)


def _predictor(cfg, model_path):
    if model_path and Path(model_path).exists():
        from host.inspection import TFLiteVision
        insp = TFLiteVision(cfg)
        return insp.predict, "tflite-int8"
    return (lambda im: classify_features(im, cfg.vision.classes, cfg.vision.pass_class)), "baseline"


def evaluate(cfg, manifest, model_path=None, out="out"):
    classes = cfg.vision.classes
    pass_cls = cfg.vision.pass_class
    cidx = {c: i for i, c in enumerate(classes)}
    rows = load_manifest(manifest, split="test")
    if not rows:
        raise SystemExit("no test rows — run vision.make_synthetic and vision.dataset first")

    predict, backend = _predictor(cfg, model_path)
    n = len(classes)
    cm = np.zeros((n, n), dtype=int)
    p_ok = np.empty(len(rows))
    pred_ok = np.empty(len(rows), dtype=bool)
    is_defect = np.empty(len(rows), dtype=bool)

    for k, (path, label) in enumerate(rows):
        img = _load_img(path, cfg.vision.image_size)
        pred, probs = predict(img)
        cm[cidx[label]][cidx[pred]] += 1
        p_ok[k] = probs.get(pass_cls, 0.0)
        pred_ok[k] = pred == pass_cls
        is_defect[k] = label != pass_cls

    # classification metrics (argmax)
    per_class = {}
    for c in classes:
        i = cidx[c]
        tp = cm[i, i]
        prec = tp / cm[:, i].sum() if cm[:, i].sum() else 0.0
        rec = tp / cm[i, :].sum() if cm[i, :].sum() else 0.0
        per_class[c] = {"precision": round(float(prec), 4), "recall": round(float(rec), 4)}

    # operating-point analysis (defect detection at a P(OK) threshold)
    def at(thr):
        # a unit passes vision iff predicted OK AND P(OK) >= thr
        passes = pred_ok & (p_ok >= thr)
        defect_caught = (~passes & is_defect).sum()
        defect_total = is_defect.sum()
        ok_rejected = (~passes & ~is_defect).sum()
        ok_total = (~is_defect).sum()
        rec = defect_caught / defect_total if defect_total else 0.0
        fr = ok_rejected / ok_total if ok_total else 0.0
        return rec, fr

    thrs = np.linspace(0, 1, 101)
    curve = np.array([at(t) for t in thrs])  # columns: recall, false_reject
    target = cfg.vision.defect_recall_target
    meeting = np.where(curve[:, 0] >= target)[0]
    rec_thr = float(thrs[meeting[0]]) if len(meeting) else 1.0
    rec_at_target = at(rec_thr)
    cfg_thr = cfg.vision.ok_threshold
    rec_at_cfg = at(cfg_thr)

    metrics = {
        "backend": backend,
        "n_test": len(rows),
        "classes": classes,
        "confusion_matrix": cm.tolist(),
        "per_class": per_class,
        "overall_accuracy": round(float(np.trace(cm) / cm.sum()), 4),
        "operating_point": {
            "configured_threshold": cfg_thr,
            "defect_recall_at_configured": round(float(rec_at_cfg[0]), 4),
            "false_reject_at_configured": round(float(rec_at_cfg[1]), 4),
            "recall_target": target,
            "threshold_for_target": round(rec_thr, 3),
            "defect_recall_at_target": round(float(rec_at_target[0]), 4),
            "false_reject_at_target": round(float(rec_at_target[1]), 4),
        },
    }

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    _plot_cm(cm, classes, backend, out / "confusion_matrix.png")
    _plot_curve(thrs, curve, cfg_thr, target, out / "operating_point.png")
    (out / "vision_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    _print_report(metrics)
    print(f"\nArtifacts: {out}/confusion_matrix.png, {out}/operating_point.png, {out}/vision_metrics.json")
    return metrics


def _plot_cm(cm, classes, backend, path):
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(classes)), classes, rotation=40, ha="right", fontsize=8)
    ax.set_yticks(range(len(classes)), classes, fontsize=8)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"Confusion matrix ({backend})")
    thresh = cm.max() / 2 if cm.max() else 0
    for i in range(len(classes)):
        for j in range(len(classes)):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black", fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)


def _plot_curve(thrs, curve, cfg_thr, target, path):
    fig, ax = plt.subplots(figsize=(6, 4.2))
    ax.plot(curve[:, 1], curve[:, 0], "-", color="#2d6cdf")
    ax.axhline(target, ls="--", color="#b3261e", lw=1, label=f"recall target {target:.0%}")
    ci = int(round(cfg_thr * 100))
    ax.scatter([curve[ci, 1]], [curve[ci, 0]], color="#1b8a3a", zorder=5,
               label=f"ok_threshold={cfg_thr:.2f}")
    ax.set_xlabel("false-reject rate (good units retested)")
    ax.set_ylabel("defect recall (defects caught)")
    ax.set_title("Operating point: recall vs false-reject")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)


def _print_report(m):
    print(f"Vision evaluation ({m['backend']}) — {m['n_test']} test images")
    print(f"  overall accuracy: {m['overall_accuracy']:.1%}")
    print("  per-class  precision / recall")
    for c, v in m["per_class"].items():
        print(f"    {c:<18} {v['precision']:.2f} / {v['recall']:.2f}")
    op = m["operating_point"]
    print(f"\n  HEADLINE @ ok_threshold={op['configured_threshold']:.2f}: "
          f"defect recall = {op['defect_recall_at_configured']:.1%}, "
          f"false-reject = {op['false_reject_at_configured']:.1%}")
    print(f"  to hit {op['recall_target']:.0%} recall -> threshold {op['threshold_for_target']:.2f} "
          f"(false-reject {op['false_reject_at_target']:.1%})")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Evaluate inspector on the test split")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--manifest", default="vision/manifest.csv")
    p.add_argument("--model", default=None, help="path to int8 .tflite (else baseline)")
    p.add_argument("--out", default="out")
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    evaluate(cfg, args.manifest, args.model, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
