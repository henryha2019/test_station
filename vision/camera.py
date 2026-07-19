"""Camera transport. Returns an RGB uint8 frame sized for the model.

Backends:
  * SimCamera     — renders a synthetic shroud view of a chosen DUT condition.
  * EspCamCamera  — pulls a JPEG from the ESP32-CAM's /capture endpoint.
"""
from __future__ import annotations

import numpy as np

from host.config import DutConfig


class Camera:
    def capture(self) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:
        pass


class SimCamera(Camera):
    """Renders the DUT's visual condition (one of the vision classes)."""

    def __init__(self, cfg: DutConfig, dut_class: str = "OK", seed: int | None = None):
        from vision import synthimg
        self._render = synthimg.render
        self.cfg = cfg
        self.dut_class = dut_class
        self.rng = np.random.default_rng(seed)

    def capture(self) -> np.ndarray:
        return self._render(self.dut_class, self.cfg.vision.image_size, self.rng)


class EspCamCamera(Camera):
    def __init__(self, url: str, image_size=(96, 96), timeout: float = 4.0):
        self.url = url
        self.image_size = (int(image_size[0]), int(image_size[1]))
        self.timeout = timeout

    def capture(self) -> np.ndarray:
        import io
        import urllib.request
        from PIL import Image

        with urllib.request.urlopen(self.url, timeout=self.timeout) as resp:
            data = resp.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        # (W, H) for PIL resize; image_size is (H, W).
        img = img.resize((self.image_size[1], self.image_size[0]))
        return np.asarray(img, dtype=np.uint8)
