# PogoTest — one-page writeup (MG996R servo station)

**A fixed end-of-line station that ships an MG996R servo only when it passes both
a functional test and a visual inspection.** Instruments measure; one host
decides and logs every unit by serial number.

## Architecture
- **ESP32-CAM (one board)** — does everything on the bench: commands the servo to
  min/center/max and reports raw readings (actual output angle via AS5600, supply
  current via INA219, sweep timing); serves the camera frame over Wi-Fi
  (`/capture`); and drives the SSD1306 OLED station HMI. Servo PWM on GPIO13; one
  I²C bus (GPIO14/15) shared by OLED + AS5600 + INA219. No pass/fail logic on the
  device. Consolidated from three boards (Uno + ESP32-CAM + ESP32-HMI) to one.
- **Host (Python)** — loads the recipe (`config/mg996r.json`), limit-checks each
  reading, fetches the frame and runs the INT8 CNN, ANDs the two verdicts, logs a
  CSV row, and pushes the verdict back to the OLED over the same serial link.
- On-device inference is the Phase 9 stretch (and wants an ESP32-S3).

## Test coverage & the dual-criteria rationale
The functional test catches a servo that **won't travel its range, stalls
(overcurrent), draws no current (dead), runs backwards, runs slow, or sits off
center** — measured as continuous values against spec windows. Vision catches
**assembly / appearance defects** the functional test is blind to: a missing
horn, a cracked/mis-seated case, a foreign object. Neither subsumes the other — a
servo can move perfectly yet be visually defective, or look fine yet be dead — so
the verdict is their AND. The log records *which* criterion (and which parameter)
failed, which makes the Pareto real.

## Parametric, not go/no-go (the test-engineering point)
Because the functional test reports continuous readings (range_deg, hold_mA,
move_mA, speed_dps, center_off_deg) rather than a single pass bit, the trace log
supports real **process studies**: Cpk per parameter, Pareto by failing
parameter, and Gage-R&R on the analog readings — not just yield.

## The operating point (the headline ML decision)
A missed defect (an *escape*) is more expensive than a false reject (a *retest*).
So vision passes only when the predicted class is `OK` **and** P(OK) ≥ a
threshold; raising the threshold trades retests for fewer escapes. On the
held-out split (baseline inspector, 120 images):

> **At ok_threshold = 0.62: defect recall = 98.9%, false-reject = 0.0%.**

Backed by the confusion matrix (`out/confusion_matrix.png`) and the
recall-vs-false-reject curve (`out/operating_point.png`). The trained MobileNetV2
(`vision/train.py`) drops into the same interface; the operating-point logic is
unchanged.

## Manufacturing metrics
- **FPY** trended over the session (`out/fpy_trend.png`).
- **Failure-mode Pareto** by failing parameter / defect class (`out/pareto.png`).
- **Cycle time** — mean and worst case (`out/cycle_time.png`).

## Repeatability (Gage-R&R style) — proving the tester isn't the variation
One known-good servo, 30 runs: **verdict stable 30/30** while the raw reading
(P(OK)) jitters with σ ≈ 0.022 — the decision is robust to reading noise. One
known-bad servo (missing horn), 30 runs: **30/30 caught, 0 escapes**
(`out/repeatability.png`).

## Reproduce
`python scripts/run_demo.py` regenerates every artifact above with no hardware.
`pytest -q` runs 28 unit tests covering the protocol, recipe/limits, functional
verdict, AND-logic, traceability, and the simulated station.

## TODO for the demo GIF (Phase 10)
Record: a good servo → green; a functionally-fine but visually-defective servo →
red naming **VISION**; a stalled/dead servo → red naming **FUNCTIONAL**. The
`--ui` mode with the inject dropdowns produces exactly this on demand.
