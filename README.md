# PogoTest — MG996R functional test station

A fixed-station end-of-line tester that ships an MG996R servo only when its
**functional response is within spec**:

```
PASS = functional( travel · current · speed · direction · centering )
```

An ESP32-CAM (used here as a plain MCU) commands the servo to min/center/max and
measures the actual response — output angle via an **AS5600** magnetic encoder,
supply current via an **INA219**, and sweep timing. A Python host loads the recipe,
**limit-checks every reading**, **owns the verdict**, logs each unit by serial
number, and drives an **SSD1306 OLED** station HMI over the same serial link.

**Design philosophy: reliability through subtraction.** Instruments measure; the
host decides. The servo's own 3-pin plug mates a header in the fixture — no pogo
pins for this DUT.

> **Visual inspection has been split into its own project.** This tester is
> single-criterion (functional). The visual-inspection pipeline (dataset → CNN →
> operating point) is being spun out into a dedicated **conveyor AOI** project —
> see [docs/AOI_CONVEYOR_PLAN.md](docs/AOI_CONVEYOR_PLAN.md).

> **Runs today with no hardware.** A simulation backend speaks the board's wire
> protocol, so the whole station — limit-checking, traceability, metrics,
> repeatability — is demoable on any machine.

---

## Architecture

```
        ┌──────────────── HOST PC (Python) ────────────────┐
        │ orchestrator · limits/config · verdict · CSV log  │
        └────────────────────────┬──────────────────────────┘
                                 │ USB serial (func + HMI)
                ┌────────────────▼─────────────────┐
                │      ESP32-CAM  (as MCU)          │
                │  servo PWM · AS5600 · INA219 · OLED│
                └────────────────┬──────────────────┘
                  GPIO13 PWM · I²C 14/15 · ext 5–6 V (servo)
                ┌────────────────▼─────────────────┐
                │ FIXTURE: servo nest · clamp · DUT │
                │  + horn→magnet coupler over AS5600│
                └───────────────────────────────────┘
```

**Locked decision — the host owns the verdict.** The board reports only raw
readings (`MEAS,<key>,<value>` … `DONE`). The host compares each to the recipe's
spec window and decides PASS/FAIL. Classic ATE: instruments measure, host decides.

See **[docs/HARDWARE.md](docs/HARDWARE.md)** for the BOM, wiring, and fixturing.

---

## Quickstart (simulation, no hardware)

```bash
pip install -r requirements.txt          # numpy, matplotlib (+ pyserial for hw)

python scripts/run_demo.py               # full pipeline -> artifacts in out/
```

Run pieces individually:

```bash
python -m host.app --simulate --count 20 --random     # headless station session
python -m host.app --simulate --ui                    # interactive Tkinter HMI
python -m host.app --simulate --scenario stalled      # force a functional fault

python -m analysis.metrics                            # FPY / Pareto / cycle time
python -m analysis.repeatability                      # Gage R&R

pytest -q                                             # 28 unit tests
```

The UI has an *inject* dropdown so you can demo failures live, e.g. **stalled
servo → FAIL (FUNCTIONAL)**. Functional fault scenarios (sim): `good`,
`no_response`, `stalled`, `out_of_range`, `reversed`, `slow`, `offcenter`.

## Bring-up on real hardware

1. Wire per [docs/HARDWARE.md](docs/HARDWARE.md): servo → GPIO13, AS5600 + INA219 +
   OLED on I²C 14/15, **leave microSD unused**, servo on a separate 5–6 V supply,
   common ground.
2. Flash `firmware/servo_tester_cam/` to the ESP32-CAM (needs `Adafruit_INA219`,
   `Adafruit_SSD1306`). It runs the functional test + OLED HMI on the one board.
3. Edit `config/mg996r.json` → `station.mcu_port` and the functional limit
   windows (tune to your golden-sample population).
4. Run the live station (one port; the OLED is driven over that same link):
   ```bash
   python -m host.app --port COM3 --ui
   ```

---

## Example results (simulated)

From `python scripts/run_demo.py`:

| Artifact | Result |
|---|---|
| Station session | 44 units, FPY 63.6%, failure Pareto by parameter |
| Dominant fault (Pareto) | `FUNC:direction`, then `range_deg`, `speed_dps`, `hold_mA` |
| **Repeatability (Gage R&R)** | known-good verdict **stable 30/30**; `range_deg` σ≈5° within spec [100,140]; known-bad (stalled) **30/30 caught, 0 escapes** |
| Cycle time (host, sim) | sub-ms (real cycle is dominated by servo settle time) |

Parametric, not go/no-go: because the log stores continuous readings
(`range_deg, hold_mA, move_mA, speed_dps, center_off_deg`), it supports real
process studies — **Cpk per parameter, Pareto by failing parameter, Gage R&R on
the analog readings** — not just yield. Artifacts land in `out/`. See
[docs/WRITEUP.md](docs/WRITEUP.md) for the one-page summary.

---

## Repo layout

```
config/mg996r.json      DUT recipe: PWM profile + functional limit windows
firmware/servo_tester_cam   ESP32-CAM: commands servo, reads sensors, drives OLED
host/                   orchestrator · instrument · functional · decision · csv · ui
analysis/               metrics (FPY/Pareto/cycle time) · repeatability (Gage R&R)
scripts/run_demo.py     one-command end-to-end simulated demo
tests/                  pytest unit tests (run with no hardware)
```

## Phase status

| Phase | Scope | State |
|---|---|---|
| 1 Functional MVP | board commands servo + measures + serial protocol | ✅ firmware + sim |
| 2 Host + traceability | orchestrator, config, CSV, Tkinter UI | ✅ |
| 3 Fixture | servo nest, poka-yoke, coaxial AS5600 coupler | ⬜ mechanical (CAD) |
| 8 Metrics | FPY, Pareto, cycle time, Gage R&R | ✅ |
| 10 Writeup | one-pager + GIF | ✅ docs/WRITEUP.md (GIF TODO) |
| — Vision | dataset · CNN · operating point | ➡ split into a separate AOI project ([plan](docs/AOI_CONVEYOR_PLAN.md)) |

## How each discipline reads it

| Track | Pitch |
|---|---|
| **Test Eng** | Parametric EOL functional test; limit windows, coverage, FPY, Gage-R&R repeatability |
| **Mechanical** | Servo nest 3-2-1 + poka-yoke, coaxial AS5600 magnet coupling |
| **Manufacturing** | EOL station, serial traceability, yield + Pareto by parameter, cycle time |
| **Firmware / Embedded** | Servo PWM + I²C sensors, test state machine + serial protocol, OLED HMI |
| **Data / ML** | → the **conveyor AOI** project ([plan](docs/AOI_CONVEYOR_PLAN.md)) |
