"""Train the production inspector: a small MobileNetV2 transfer-learning CNN.

The image problem is simple, so the model is small (alpha=0.35, 96x96) — it has
to fit an MCU later (Phase 9). Requires TensorFlow (requirements-vision.txt).

    python -m vision.train --epochs 12
"""
from __future__ import annotations

import argparse
from pathlib import Path

from host.config import DEFAULT_CONFIG, load_config
from vision.dataset import load_manifest


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Train the vision inspector CNN")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--manifest", default="vision/manifest.csv")
    p.add_argument("--epochs", type=int, default=12)
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--out", default="vision/models/servovision.keras")
    args = p.parse_args(argv)

    try:
        import tensorflow as tf
    except ImportError:
        raise SystemExit("TensorFlow not installed. pip install -r requirements-vision.txt")

    cfg = load_config(args.config)
    classes = cfg.vision.classes
    cidx = {c: i for i, c in enumerate(classes)}
    H, W = cfg.vision.image_size

    def make_ds(split, shuffle):
        rows = load_manifest(args.manifest, split=split)
        paths = [r[0] for r in rows]
        labels = [cidx[r[1]] for r in rows]
        ds = tf.data.Dataset.from_tensor_slices((paths, labels))
        if shuffle:
            ds = ds.shuffle(len(paths), seed=13)

        def load(path, label):
            img = tf.io.decode_image(tf.io.read_file(path), channels=3, expand_animations=False)
            img = tf.image.resize(img, [H, W]) / 255.0
            img.set_shape([H, W, 3])
            return img, label

        return ds.map(load, num_parallel_calls=tf.data.AUTOTUNE).batch(args.batch).prefetch(tf.data.AUTOTUNE)

    train_ds = make_ds("train", shuffle=True)
    test_ds = make_ds("test", shuffle=False)

    base = tf.keras.applications.MobileNetV2(
        input_shape=(H, W, 3), include_top=False, weights="imagenet", alpha=0.35)
    base.trainable = False
    model = tf.keras.Sequential([
        base,
        tf.keras.layers.GlobalAveragePooling2D(),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(len(classes), activation="softmax"),
    ])
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    model.fit(train_ds, validation_data=test_ds, epochs=args.epochs)

    loss, acc = model.evaluate(test_ds)
    print(f"test accuracy: {acc:.3f}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    model.save(args.out)
    print(f"saved {args.out}")
    print("next: python -m vision.quantize")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
