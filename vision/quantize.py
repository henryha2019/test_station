"""Post-training INT8 quantization of the trained CNN, + a latency benchmark.

INT8 is what makes the model deployable on the ESP32-CAM (Phase 9) and speeds up
host inference. We re-check accuracy after quantization and record latency, since
both feed the data/ML story. Requires TensorFlow.

    python -m vision.quantize
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
from PIL import Image

from host.config import DEFAULT_CONFIG, load_config
from vision.dataset import load_manifest


def _load(path, size):
    return np.asarray(Image.open(path).convert("RGB").resize((size[1], size[0])), dtype=np.float32) / 255.0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="INT8-quantize the inspector CNN")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--model", default="vision/models/servovision.keras")
    p.add_argument("--manifest", default="vision/manifest.csv")
    p.add_argument("--out", default="vision/models/servovision_int8.tflite")
    p.add_argument("--rep", type=int, default=100, help="representative samples")
    args = p.parse_args(argv)

    try:
        import tensorflow as tf
    except ImportError:
        raise SystemExit("TensorFlow not installed. pip install -r requirements-vision.txt")

    cfg = load_config(args.config)
    size = cfg.vision.image_size
    train = load_manifest(args.manifest, split="train")
    rep_paths = [r[0] for r in train[: args.rep]]

    def rep_gen():
        for path in rep_paths:
            yield [_load(path, size)[None, ...].astype(np.float32)]

    conv = tf.lite.TFLiteConverter.from_keras_model(tf.keras.models.load_model(args.model))
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = rep_gen
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8
    tflite = conv.convert()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(tflite)
    kb = len(tflite) / 1024
    print(f"saved {out} ({kb:.0f} KB)")

    # Re-evaluate + latency on the test split via the int8 model.
    from host.inspection import TFLiteVision
    cfg.vision.model_path = str(out)
    insp = TFLiteVision(cfg)
    test = load_manifest(args.manifest, split="test")
    correct = 0
    times = []
    for path, label in test:
        img = (_load(path, size) * 255).astype(np.uint8)
        t0 = time.perf_counter()
        pred, _ = insp.predict(img)
        times.append((time.perf_counter() - t0) * 1000)
        correct += int(pred == label)
    times = np.array(times)
    print(f"int8 test accuracy: {correct/len(test):.3f}")
    print(f"latency: mean {times.mean():.2f} ms  p95 {np.percentile(times,95):.2f} ms  (host)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
