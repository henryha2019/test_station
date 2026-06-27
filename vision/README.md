# Vision pipeline

A small INT8 CNN classifies the servo into one taxonomy class; the host turns
that into a vision pass/fail at a recall-optimized operating point.

Taxonomy (`config/mg996r.json → vision.classes`): `OK`, `horn_missing`,
`case_defect`, `foreign_object`. `OK` is the only pass class.

## Flow

```
capture.py / make_synthetic.py  ->  vision/data/<class>/*.png   (labels in the path)
dataset.py                      ->  vision/manifest.csv         (stratified train/test split)
train.py                        ->  vision/models/servovision.keras   (MobileNetV2, alpha=0.35, 96x96)
quantize.py                     ->  vision/models/servovision_int8.tflite  (PTQ + latency)
evaluate.py                     ->  out/confusion_matrix.png, operating_point.png, vision_metrics.json
```

## Two backends, one interface
`host/inspection.py` loads `servovision_int8.tflite` if it exists (and a tflite
runtime is available), otherwise it falls back to the **feature baseline** in
`synthimg.py`. So the station — and `evaluate.py` — run end-to-end before any
training. Swap real captures + a trained model in later with zero code changes
elsewhere.

## Synthetic stand-in
`synthimg.py` renders labeled servo scenes (body / horn / foreign object with
jitter and noise) and provides the baseline classifier. It exists so the *whole
project* is demoable on any machine. For production, point `capture.py` at the
ESP32-CAM and delete `vision/data/`; the directory layout and class names are
identical.

## Operating point
Defect-recall priority: a unit passes vision only when predicted `OK` **and**
P(OK) ≥ `ok_threshold`. Raise the threshold to cut escapes at the cost of more
retests. `evaluate.py` sweeps the threshold, reports recall/false-reject at the
configured value, and finds the threshold meeting the recall target.

## Phase 9 (stretch): on-device
The INT8 `.tflite` is sized to fit an MCU. Porting it to TFLite-Micro on the
ESP32-CAM makes the camera node return a vision verdict directly; the host just
ANDs it. Compare on-device latency/footprint against host inference.
