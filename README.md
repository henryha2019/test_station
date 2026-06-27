# PogoTest — dual-criteria servo test station (MG996R)

A fixed-station end-of-line tester that ships a servo only when it passes **both**
a functional test **and** a visual inspection:

```
PASS = functional(travel · current · speed · direction)  AND  vision(assembly / appearance defect)
```

An Arduino Uno is the functional instrument — it commands the **MG996R** to
min/center/max and measures the actual response (output angle via an AS5600
encoder, supply current via an INA219, sweep timing). An ESP32-CAM provides the
image, a small INT8 CNN classifies visual defects, and a Python host orchestrates
the cycle, **owns the verdict**, and logs every unit by serial number. A separate
ESP32 + display is the station HMI.

**Design philosophy: reliability through subtraction.** Instruments measure; the
host decides. The servo's own 3-pin plug mates a header in the fixture — no pogo
pins needed for this DUT.

> **Runs today with no hardware.** A simulation backend speaks the real Uno wire
> protocol and a synthetic-image path drives the vision pipeline, so the whole
> station — verdict logic, traceability, metrics, repeatability — is demoable on
> any machine. Attach the Uno + sensors + ESP32-CAM and the same code drives real
> silicon.

---

## Architecture

```
        ┌──────────────────────── HOST PC (Python) ────────────────────────┐
        │ orchestrator · limits/config · CNN inference · AND-verdict · CSV  │
        └──────┬───────────────────────┬───────────────────────┬───────────┘
               │ USB serial            │ Wi-Fi (JPEG)          │ USB serial
        ┌──────▼──────┐         ┌───────▼───────┐        ┌──────▼───────┐
        │ ARDUINO UNO │         │  ESP32-CAM    │        │ ESP32 + OLED │
        │ servo func. │         │  /capture     │        │ station HMI  │
        │ + AS5600    │         │  (v2.1: INT8) │        │              │
        │ + INA219    │         └───────────────┘        └──────────────┘
        └──────┬──────┘
               │ D9 PWM · I²C sensors · ext 5–6V
        ┌──────▼─────────────────────────────────┐
        │ FIXTURE: servo nest · clamp · MG996R    │
        │  + horn→magnet coupler over AS5600      │
        │  + camera mount + diffuser shroud       │
        └─────────────────────────────────────────┘
```

**Two decisions, locked:**
1. **CNN runs on the host** (v2.0) for fast iteration and a bigger model budget.
   On-device ESP32-CAM inference is the Phase 9 stretch.
2. **The host owns the verdict.** The Uno reports raw readings; the CAM provides
   an image; the host limit-checks the readings, ANDs the two results, and logs.
   Classic ATE.

See **[docs/HARDWARE.md](docs/HARDWARE.md)** for the BOM, wiring, and fixturing.

---

## Quickstart (simulation, no hardware)

```bash
pip install -r requirements.txt          # numpy, pillow, matplotlib (+ pyserial for hw)

python scripts/run_demo.py               # full pipeline -> artifacts in out/
```

Run pieces individually:

```bash
python -m host.app --simulate --count 20 --random     # headless station session
python -m host.app --simulate --ui                    # interactive Tkinter HMI
python -m host.app --simulate --scenario stalled      # force a functional fault
python -m host.app --simulate --dut-class horn_missing  # force a visual defect

python -m vision.make_synthetic --per-class 300       # dataset (Phase 4)
python -m vision.dataset                              # train/test manifest
python -m vision.evaluate                             # metrics + plots (Phase 5)

python -m analysis.metrics                            # FPY / Pareto / cycle time
python -m analysis.repeatability                      # Gage R&R (Phase 8)

pytest -q                                             # 28 unit tests
```

The interactive UI has *inject* dropdowns (functional fault + visual defect) so
you can demo the AND logic live: e.g. **functional PASS + missing horn → final
FAIL (VISION)**, or **stalled servo → final FAIL (FUNCTIONAL)**.

Functional fault scenarios (sim): `good`, `no_response`, `stalled`,
`out_of_range`, `reversed`, `slow`, `offcenter`.
Vision classes: `OK`, `horn_missing`, `case_defect`, `foreign_object`.

## Bring-up on real hardware

1. Wire it up per [docs/HARDWARE.md](docs/HARDWARE.md) (servo→D9, AS5600+INA219 on
   I²C, servo power on a separate 5–6 V supply, common ground).
2. Flash `firmware/servo_tester_uno/` to the Uno (needs `Adafruit_INA219`).
3. Flash `firmware/esp32_hmi/` to the HMI ESP32; flash stock `CameraWebServer`
   to the ESP32-CAM.
4. Edit `config/mg996r.json` → `station.uno_port`, `vision.espcam_url`, and the
   functional limit windows (tune to your golden-sample population).
5. Capture a dataset, then train + quantize:
   ```bash
   pip install -r requirements-vision.txt
   python -m vision.capture --class OK --count 200     # repeat per class
   python -m vision.dataset && python -m vision.train && python -m vision.quantize
   ```
6. Run the live station:
   ```bash
   python -m host.app --port COM3 --hmi-port COM5 --ui
   ```

---

## Example results (simulated baseline)

From `python scripts/run_demo.py` (synthetic data + feature-baseline inspector;
the trained CNN replaces the baseline with identical interfaces):

| Artifact | Result |
|---|---|
| Vision accuracy (held-out, 120 imgs) | **99.2%** |
| **Operating point** @ `ok_threshold=0.62` | **defect recall 98.9%, false-reject 0.0%** |
| Station session | 43 units, FPY 60.5%, failure Pareto by parameter |
| Cycle time (host, sim) | mean 1.4 ms, p95 1.7 ms |
| **Repeatability** | known-good verdict **stable 30/30**; P(OK) σ=0.022; known-bad **30/30 caught, 0 escapes** |

The recall-vs-false-reject curve and confusion matrix land in `out/`. See
[docs/WRITEUP.md](docs/WRITEUP.md) for the one-page portfolio summary.

---

## Repo layout

```
config/mg996r.json      DUT recipe: PWM profile, functional limit windows, vision op-point
firmware/               Uno servo-test instrument · ESP32 HMI sketch
host/                   orchestrator, instrument, functional, camera, inspection, decision, csv, ui
vision/                 synthimg · capture · make_synthetic · dataset · train · evaluate · quantize
analysis/               metrics (FPY/Pareto/cycle time) · repeatability (Gage R&R)
scripts/run_demo.py     one-command end-to-end simulated demo
tests/                  28 pytest unit tests (run with no hardware)
```

## Phase status (vs build plan)

| Phase | Scope | State |
|---|---|---|
| 1 Functional MVP | Uno commands servo + measures + serial protocol | ✅ firmware + sim |
| 2 Host + traceability | orchestrator, config, CSV, Tkinter UI | ✅ |
| 3 Fixture + shroud | servo nest, poka-yoke, AS5600 coupler, shroud | ⬜ mechanical (CAD) |
| 4 Dataset | capture + labeled tree + split | ✅ tooling (+ synthetic) |
| 5 Train + evaluate | small CNN, confusion matrix, op-point | ✅ eval; train needs TF + data |
| 6 Quantize + AND | INT8 + live dual-criteria verdict | ✅ AND live; quant needs TF |
| 7 HMI display | ESP32 + OLED station indicator | ✅ firmware + host push |
| 8 Metrics | FPY, Pareto, cycle time, Gage R&R | ✅ |
| 9 Edge inference | on-device ESP32-CAM INT8 | ⬜ stretch |
| 10 Writeup | one-pager + GIF | ✅ docs/WRITEUP.md (GIF TODO) |

## How each discipline reads it

| Track | Pitch |
|---|---|
| **Test Eng** | Dual-criteria EOL test; parametric limits, coverage, FPY, Gage-R&R repeatability |
| **Mechanical** | Servo nest 3-2-1 + poka-yoke, coaxial AS5600 coupling, vision lighting enclosure |
| **Manufacturing** | EOL inspection station, serial traceability, yield + Pareto, cycle time |
| **Firmware** | Servo command/measure state machine + serial protocol, I²C sensors, ESP32 HMI |
| **Data / ML** | Self-built dataset, quantized CNN, recall-optimized operating point, edge latency |
