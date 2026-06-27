"""Capture real shroud images from the ESP32-CAM into the labeled dataset tree.

Labels are baked into the path (vision/data/<class>/<class>_NNNN.png) so the
manifest builder needs no manual relabeling. Stage one DUT condition, run with
the matching --class, repeat.

    python -m vision.capture --class OK --count 200
    python -m vision.capture --class horn_missing --count 200
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from PIL import Image

from host.config import DEFAULT_CONFIG, load_config
from host.camera import EspCamCamera
from vision.synthimg import CLASSES


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Capture labeled images from the ESP32-CAM")
    p.add_argument("--class", dest="cls", required=True, choices=CLASSES)
    p.add_argument("--count", type=int, default=200)
    p.add_argument("--url", default=None, help="override ESP32-CAM /capture URL")
    p.add_argument("--out", default="vision/data")
    p.add_argument("--interval", type=float, default=0.3, help="seconds between frames")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    cam = EspCamCamera(args.url or cfg.vision.espcam_url, cfg.vision.image_size)
    d = Path(args.out) / args.cls
    d.mkdir(parents=True, exist_ok=True)
    existing = len(list(d.glob(f"{args.cls}_*.png")))

    print(f"capturing {args.count} '{args.cls}' frames -> {d} (Ctrl-C to stop)")
    for i in range(args.count):
        frame = cam.capture()
        idx = existing + i
        Image.fromarray(frame, "RGB").save(d / f"{args.cls}_{idx:04d}.png")
        print(f"  {idx:04d}", end="\r", flush=True)
        time.sleep(args.interval)
    print(f"\ndone: {args.count} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
