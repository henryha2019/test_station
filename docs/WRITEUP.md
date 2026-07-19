# PogoTest — one-page writeup (MG996R functional station)

**A fixed end-of-line station that ships an MG996R servo only when its measured
functional response is within spec.** Instruments measure; one host decides and
logs every unit by serial number.

*(Single-criterion. Visual inspection was split into a separate conveyor-AOI
project; its pipeline is parked under `vision/` — see docs/AOI_CONVEYOR_PLAN.md.)*

## Architecture
- **ESP32-CAM (used as a plain MCU)** — commands the servo to min/center/max and
  reports raw readings: actual output angle via an AS5600 magnetic encoder,
  supply current via an INA219, and sweep timing. No pass/fail logic on the
  device. Servo PWM on GPIO13; one I²C bus (GPIO14/15) shared by the AS5600,
  INA219 and the SSD1306 OLED.
- **Host (Python)** — loads the recipe (`config/mg996r.json`), limit-checks each
  reading, decides PASS/FAIL, logs a CSV row, and pushes the verdict to the OLED
  over the same serial link.

## Test coverage
The functional test catches a servo that **won't travel its range, stalls
(overcurrent), draws no current (dead), runs backwards, runs slow, or sits off
center** — each measured as a continuous value against a spec window. The log
records *which parameter* failed, which makes the Pareto real.

## Parametric, not go/no-go (the test-engineering point)
Because the test reports continuous readings (`range_deg, hold_mA, move_mA,
speed_dps, center_off_deg`) rather than a single pass bit, the trace log supports
real **process studies**: Cpk per parameter, Pareto by failing parameter, and
Gage-R&R on the analog readings — not just yield.

## Manufacturing metrics
- **FPY** trended over the session (`out/fpy_trend.png`).
- **Failure-mode Pareto** by failing parameter (`out/pareto.png`).
- **Cycle time** — mean and worst case (`out/cycle_time.png`).

## Repeatability (Gage-R&R style) — proving the tester isn't the variation
One known-good servo, 30 runs: **verdict stable 30/30** while the raw reading
(`range_deg`) jitters with σ ≈ 5° well inside the [100,140] spec — the decision is
robust to reading noise. One known-bad servo (stalled), 30 runs: **30/30 caught,
0 escapes** (`out/repeatability.png`).

## Reproduce
`python scripts/run_demo.py` regenerates every artifact above with no hardware.
`pytest -q` runs 28 unit tests covering the protocol, recipe/limits, functional
verdict, traceability, and the simulated station.

## TODO for the demo GIF (Phase 10)
Record: a good servo → green; a stalled / dead / reversed servo → red naming the
failing parameter. `--ui` with the inject dropdown produces this on demand.
