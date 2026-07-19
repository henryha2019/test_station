"""Vision inspection: turn a frame into a pass/fail at the chosen operating point.

Operating point (defect-recall priority): a unit passes vision ONLY when the
predicted class is the pass class AND P(pass_class) >= ok_threshold. Raising the
threshold rejects more borderline units (retest cost) to let fewer defects
escape — the trade is owned in config/mg996r.json, applied here in one place.

Inference backends:
  * TFLiteVision — the production INT8 CNN, if a model file + tflite runtime exist.
  * MockVision   — the synthimg feature baseline, so the station runs untrained.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from host.config import DutConfig


@dataclass
class VisionResult:
    passed: bool
    cls: str
    confidence: float          # P(predicted class)
    infer_ms: float
    probs: dict = field(default_factory=dict)
    backend: str = ""

    def summary(self) -> str:
        return f"{'PASS' if self.passed else 'FAIL'} {self.cls} ({self.confidence:.0%})"


def _decide(cls: str, probs: dict, cfg: DutConfig) -> bool:
    pok = probs.get(cfg.vision.pass_class, 0.0)
    return cls == cfg.vision.pass_class and pok >= cfg.vision.ok_threshold


class Inspector:
    backend = "base"

    def __init__(self, cfg: DutConfig):
        self.cfg = cfg

    def _predict(self, img: np.ndarray) -> tuple[str, dict]:  # pragma: no cover
        raise NotImplementedError

    def predict(self, img: np.ndarray) -> tuple[str, dict]:
        """Raw (class, {class: prob}) without applying the operating point.
        Used by evaluation to sweep the threshold."""
        return self._predict(img)

    def infer(self, img: np.ndarray) -> VisionResult:
        t0 = time.perf_counter()
        cls, probs = self._predict(img)
        dt = (time.perf_counter() - t0) * 1000.0
        return VisionResult(
            passed=_decide(cls, probs, self.cfg),
            cls=cls,
            confidence=float(probs.get(cls, 0.0)),
            infer_ms=dt,
            probs=probs,
            backend=self.backend,
        )


class MockVision(Inspector):
    backend = "baseline"

    def _predict(self, img: np.ndarray):
        from vision.synthimg import classify_features
        return classify_features(img, self.cfg.vision.classes, self.cfg.vision.pass_class)


class TFLiteVision(Inspector):
    backend = "tflite-int8"

    def __init__(self, cfg: DutConfig):
        super().__init__(cfg)
        try:
            from tflite_runtime.interpreter import Interpreter  # type: ignore
        except Exception:
            from tensorflow.lite import Interpreter  # type: ignore
        self._it = Interpreter(model_path=cfg.vision.model_path)
        self._it.allocate_tensors()
        self._in = self._it.get_input_details()[0]
        self._out = self._it.get_output_details()[0]

    def _predict(self, img: np.ndarray):
        x = img.astype(np.float32) / 255.0
        scale, zero = self._in.get("quantization", (0.0, 0))
        if self._in["dtype"] == np.int8 and scale:
            x = np.clip(np.round(x / scale + zero), -128, 127).astype(np.int8)
        x = x[None, ...]
        self._it.set_tensor(self._in["index"], x)
        self._it.invoke()
        out = self._it.get_tensor(self._out["index"])[0].astype(np.float32)
        oscale, ozero = self._out.get("quantization", (0.0, 0))
        if self._out["dtype"] == np.int8 and oscale:
            out = (out - ozero) * oscale
        out = np.clip(out, 1e-9, None)
        out = out / out.sum()
        classes = self.cfg.vision.classes
        probs = {c: float(out[i]) for i, c in enumerate(classes)}
        return classes[int(np.argmax(out))], probs


def make_inspector(cfg: DutConfig, prefer_model: bool = True) -> Inspector:
    """Use the trained INT8 model if available, else the feature baseline."""
    if prefer_model and cfg.vision.model_path and Path(cfg.vision.model_path).exists():
        try:
            return TFLiteVision(cfg)
        except Exception:
            pass
    return MockVision(cfg)
