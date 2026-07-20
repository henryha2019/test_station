# Runbook: from a bare board to a calibrated test station

This is the step-by-step path from "nothing flashed yet" to "the station is
making trustworthy PASS/FAIL calls on a real MG996R." Follow it in order --
each stage exists to catch a specific class of problem before it can hide
inside a more complicated one.

```
0. Prerequisites
1. Flash + read the 5 bring-up sketches, one peripheral at a time
2. Flash the integrated firmware, smoke-test it over the serial monitor
3. Run the host against --simulate (no hardware) as a software sanity check
4. Run the host against the real board
5. Calibrate config/mg996r.json against your actual servo
6. Run the full demo / analysis pipeline
7. Troubleshooting
```

Don't skip straight to step 2. The bring-up sketches have no dependencies on
each other or on the main firmware, so when something's wrong they tell you
*which wire* is wrong instead of leaving you debugging a 300-line integrated
sketch with five things that could each be the culprit.

---

## 0. Prerequisites

**Arduino toolchain**
1. Install the Arduino IDE (2.x) or arduino-cli.
2. Add the ESP32 board package: File -> Preferences -> Additional Board
   Manager URLs -> `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`,
   then Tools -> Board -> Boards Manager -> install "esp32 by Espressif Systems".
3. Install libraries via Library Manager (Tools -> Manage Libraries):
   - `Adafruit INA219`
   - `Adafruit SSD1306`
   - `Adafruit GFX Library` (pulled in automatically by the SSD1306 library,
     but install explicitly if it isn't)
   These three are only needed for the sketches that use them
   (`test_ina219`, `test_oled`, `servo_tester_cam`). `test_i2c_scan`,
   `test_as5600`, and `test_servo_pwm` need nothing beyond the ESP32 core.

**Board selection**
- If flashing the AI-Thinker ESP32-CAM: Tools -> Board -> ESP32 Arduino ->
  "AI Thinker ESP32-CAM".
- If flashing a plain ESP32 dev board instead: Tools -> Board -> ESP32
  Arduino -> "ESP32 Dev Module". All six sketches -- the five bring-up ones
  (i2c_scan, as5600, ina219, oled, servo_pwm) and the integrated firmware
  (`servo_tester_cam.ino`) -- use only GPIO13/14/15 and no camera or Wi-Fi
  code, so they run unmodified on either board; see
  [firmware/README.md](../firmware/README.md) for the pin map.

**Python host**
```bash
pip install -r requirements-dev.txt      # numpy, pillow, matplotlib, pyserial, pytest
pytest -q                                # confirm the software side is healthy: 24 passed
```

---

## 1. Bring-up sketches (flash and read each one before moving on)

Each sketch lives in its own folder under `firmware/` (Arduino requires this
-- the sketch name must match its folder name) and streams readable text to
the Serial Monitor at **115200 baud**. Read the comment block at the top of
each `.ino` for what a pass looks like; the summary here is just the order
and the headline pass/fail signal.

**Before you flash anything on the ESP32-CAM**: connect the programmer base,
hold/short the boot pin (IO0 to GND -- most programmer bases have a button
for this) while you press Upload, then release it and press reset once the
upload finishes. A plain ESP32 dev board with onboard USB-serial doesn't need
this dance -- just select the port and upload.

| # | Sketch | Confirms | Pass signal |
|---|---|---|---|
| 1 | `firmware/test_i2c_scan/` | AS5600 + OLED + INA219 wiring, all in one shot | `0x36`, `0x3C`, `0x40` all listed every scan |
| 2 | `firmware/test_as5600/` | Angle encoder + magnet alignment | `angle` tracks smoothly when you turn the shaft by hand; `magnet=OK`; `AGC` roughly mid-range (~64-192) |
| 3 | `firmware/test_ina219/` | Current sensor + servo power wiring | `bus` reads ~5-6V once the servo supply is on; `current` jumps from ~0 to nonzero when the servo is loaded/moving |
| 4 | `firmware/test_oled/` | Display wiring | border + text draw, and the counter visibly increments once per second |
| 5 | `firmware/test_servo_pwm/` | Servo signal wiring + power | shaft visibly sweeps to three distinct positions (MIN / CENTER / MAX) every 2 seconds, and MIN/MAX are the physical extremes, not the same spot |

Run #1 first -- it needs no libraries and confirms three of the four
peripherals' wiring before you've even installed anything beyond the ESP32
core. If it doesn't find a device you expect, fix that before moving to the
sketch that talks to it specifically.

**This is also when you mechanically align the AS5600.** Run `test_as5600`
while you hold the magnet coupler where you plan to mount it and adjust the
air gap (target ~1-2mm) until `AGC` sits mid-range and `magnet=OK` across the
shaft's full rotation, not just at one position.

Sketch #5 (servo PWM) is a good moment to eyeball the servo's *actual* travel
before you've committed to any wiring beyond power+signal -- note roughly how
far it swings. You'll need real numbers here in step 5 (calibration) anyway.

---

## 2. Flash the integrated firmware and smoke-test it

1. Open `firmware/servo_tester_cam/servo_tester_cam.ino`, flash it the same
   way as the bring-up sketches.
2. Open the Serial Monitor at 115200 baud, line ending "Newline".
3. Type each of these and confirm the response (see
   [firmware/README.md](../firmware/README.md) for the full protocol table):

   | Type | Expect |
   |---|---|
   | `ID?` | `ID,SERVOTEST-CAM,2.0` |
   | `PING` | `PONG` |
   | `RUN` | a block of `MEAS,<key>,<value>` lines, ending in `DONE,<ms>` |

   If `RUN` hangs or times out, the servo or a sensor isn't answering --
   go back and re-run the specific bring-up sketch for the piece that's
   missing from the MEAS output.
4. `RUN`'s output will very likely show FAIL-shaped numbers at this point
   even on a perfectly healthy servo -- `config/mg996r.json`'s limits are
   placeholders until you calibrate them in step 5. That's expected here;
   don't chase it yet.

---

## 3. Host sanity check (no hardware required)

Before touching the real port, confirm the software side works end to end in
simulation:

```bash
python scripts/run_demo.py              # full pipeline, no hardware -> out/
python -m host.app --simulate --ui      # interactive HMI, inject faults from the dropdown
```

If either of these fails, it's a software problem independent of your
hardware -- fix it here first so you're not debugging two things at once
later.

---

## 4. First run against real hardware

1. Edit `config/mg996r.json -> station.mcu_port` to your board's COM port
   (Windows Device Manager -> Ports, or `python -m serial.tools.list_ports`).
2. ```bash
   python -m host.app --port COM3 --ui
   ```
   The OLED should light up with a boot message, and pressing Start in the
   Tkinter window should run one full cycle and show a verdict.
3. It will very likely show **FAIL** right now even for a good servo -- same
   reason as step 2.4: the limits in `config/mg996r.json` are wide
   placeholders, not your actual servo's numbers yet. Move to step 5.

---

## 5. Calibration (the step that makes the verdict trustworthy)

`config/mg996r.json`'s `functional.limits` ship as **uncalibrated
placeholders** -- wide enough that a healthy extended-travel MG996R
(the "180 degrees each way" variant) should mostly land inside them, but not
tight enough to reliably catch a marginal unit yet. This mirrors the
project's own Gage-R&R philosophy: don't guess the spec window, measure it.

1. Run a servo you're confident is healthy through 20-30 cycles and keep the
   trace log:
   ```bash
   python -m host.app --port COM3 --count 30 --log logs/calibration.csv
   ```
2. Look at the spread of each measured column in `logs/calibration.csv`
   (`range_deg`, `hold_mA`, `move_mA`, `speed_dps`, `center_off_deg`) --
   `python -m analysis.repeatability` (see step 6) will print mean/sd/min/max
   for `range_deg` and `move_mA` directly; for the others, open the CSV in
   a spreadsheet or a quick pandas one-liner.
3. Set each limit in `config/mg996r.json -> functional.limits` to comfortably
   bracket what you actually measured (a common rule of thumb: mean +/- 4-6
   standard deviations, or mean +/- (max-min) with a bit of headroom), not
   the placeholder values.
4. If `speed_dps` reads suspiciously low relative to what the servo visually
   does, `functional.settle_ms` (mirrored as `SETTLE_MS` in the firmware) may
   be set much longer than the servo's actual full-sweep time -- see the
   `speed_dps` comment in `config/mg996r.json` for why, and consider trimming
   both down together (they must be changed as a pair).
5. If `direction` always reads the opposite of `expect` in the config, that's
   not a fault -- it just means the magnet is mounted with the opposite
   sense from what was assumed. Flip `functional.limits.direction.expect` to
   match reality once, rather than treating every unit as a wiring failure.
6. Re-run `python -m host.app --port COM3 --ui` on the same known-good servo
   and confirm it now reads PASS. Then run a servo you know is actually bad
   (or force a fault, e.g. block the horn from moving) and confirm it FAILs
   for the right reason.

---

## 6. Full test / demo / analysis pipeline

```bash
python scripts/run_demo.py                          # simulated, artifacts -> out/
python -m analysis.metrics --log logs/calibration.csv     # FPY / Pareto / cycle time
python -m analysis.repeatability --runs 30                # Gage R&R against real config (sim)
pytest -q                                            # 24 unit tests
```

`analysis.repeatability` runs against the **simulator**, not live hardware --
it's there to validate the *decision logic and reporting* are stable, not to
replace running real repeat cycles on the actual servo (that's step 5).

---

## 7. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `test_i2c_scan` finds nothing | SDA/SCL swapped, wrong pins (21/22 instead of 14/15), or a microSD card is inserted (frees GPIO 2/4/12/13/14/15 only when absent) |
| `test_i2c_scan` finds some but not all three addresses | check that specific device's VCC/GND and address (INA219/OLED variants sometimes have solder-jumper address bits) |
| AS5600 `angle` jumps erratically or `magnet` isn't `OK` | air gap wrong (target ~1-2mm), magnet off-axis, or wrong magnet type (needs diametric, not axial) |
| Board resets/browns out when the servo moves | servo is powered from USB/board rail instead of its own 5-6V >=3A supply, or grounds aren't actually common |
| `RUN` times out with no `DONE` | one of servo/AS5600/INA219 isn't answering -- re-run the matching bring-up sketch |
| Healthy servo reads FAIL on `range_deg`/`speed_dps`/etc. | limits are still the shipped placeholders -- do step 5 (calibration) |
| `direction` always fails on an otherwise-good servo | magnet mounted with the opposite rotational sense -- flip `expect` in config, see step 5.5 |
| ESP32-CAM won't enter flashing mode | IO0 not held low during the start of upload, or a bad/underpowered USB cable -- programmer-base boot buttons are notoriously finicky, hold it a beat longer than feels necessary |
