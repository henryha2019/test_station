# Hardware · Wiring · Fixturing (MG996R Servo Test Station · Single-Board ESP32-CAM)

DUT = **MG996R servo**. Verdict = **functional test** (single criterion).
**One AI-Thinker ESP32-CAM does it all**: servo functional test + I2C sensors
(AS5600 / INA219) + OLED display.
Principle: **the board only measures/displays; the host makes the verdict; all
nodes share a common ground.**

> Wiring overview: **[wiring_mg996r.svg](wiring_mg996r.svg)** · Detailed
> schematic: **[servo_tester_schematic.svg](servo_tester_schematic.svg)** ·
> Physical layout (illustrative, pre-measurement): **[servo_tester_physical_layout.svg](servo_tester_physical_layout.svg)**
>
> Note: this station is a **pure functional** test. The ESP32-CAM is used only
> as an MCU (servo functional test + I2C sensors + OLED) — the on-board camera
> and `GET /capture` are **not used**. A plain ESP32 works just as well.

---

## 1. Bill of materials (BOM)

| Part | Qty | Purpose | Notes |
|---|---|---|---|
| **ESP32-CAM (AI-Thinker) + programmer base** | 1 | Single-board core: drives servo PWM, reads sensors, drives OLED | You already have this (ESP-32S/OV2640) |
| **AS5600 magnetic encoder module + diametric magnet** | 1 | Measures **actual output angle** (I2C 0x36) | Mounted coaxially on the servo shaft |
| **INA219 current sensor module** | 1 | Measures servo **current** (I2C 0x40) | High-side measurement |
| **SSD1306 OLED 128x64 (I2C)** | 1 | Station HMI, shows the verdict (I2C 0x3C) | Shares the I2C bus with the sensors |
| **5-6V power supply >=3A** | 1 | Powers the servo | MG996R stall current is ~2.5A — **do not power it from the board/USB** |
| 3-pin female header | 1 | Mates the servo's plug (power/ground/signal) | Servo ships with a standard 3-pin male plug |
| White LEDs + current-limiting resistors | a few | Diffuser shroud lighting, 5V, always on | |
| Jumper wires / terminal blocks | as needed | | |
| 3D-printed parts | one set | Servo nest + magnet coupler + AS5600 mount + camera/board bracket + diffuser shroud | See section 3 |

> **Parts you don't need (cut by subtraction)**: no Arduino Uno, no separate HMI
> ESP32 — both roles are consolidated onto the ESP32-CAM. The servo has its own
> 3-pin plug, so **no pogo pins** are needed either.

---

## 2. Wiring (single board)

The ESP32-CAM is **3.3V logic**, so the whole I2C bus runs at 3.3V — the AS5600
and OLED are happiest this way, with no level shifting needed.

### 2.1 Pin assignment (important: **do not fit a microSD card**, or GPIO 13/14/15 are unavailable)

| Function | ESP32-CAM pin |
|---|---|
| **Servo PWM** (LEDC 50Hz) | **GPIO13** |
| **I2C SDA** (OLED + AS5600 + INA219) | **GPIO14** |
| **I2C SCL** | **GPIO15** |
| Serial (functional test + HMI frames) | GPIO1/3 -> programmer base USB -> host |
| Camera + Wi-Fi | Fixed AI-Thinker pins (do not touch) |

> Note: the usual OLED pins 21/22 are the **camera pins** on the ESP32-CAM, so
> I2C must move to **14/15**.

### 2.2 I2C bus (three devices on one bus, addresses don't collide)

| Module | VCC | GND | SDA | SCL | Address |
|---|---|---|---|---|---|
| SSD1306 OLED | 3V3 | GND | GPIO14 | GPIO15 | 0x3C |
| AS5600 | 3V3 | GND | GPIO14 | GPIO15 | 0x36 |
| INA219 | 3V3 | GND | GPIO14 | GPIO15 | 0x40 |

(Put a 4.7k pull-up from SDA and from SCL to 3V3; many modules already include one.)

### 2.3 Servo (current measured through INA219, high side)

The servo has 3 wires: **signal (orange/yellow) -> GPIO13**; **power
(red) -> through INA219 to 5-6V positive**; **ground (brown/black) -> common
ground**.

| Current path | Connection |
|---|---|
| 5-6V (+) | -> INA219 `Vin+` |
| INA219 `Vin-` | -> servo power wire (red) |
| 5-6V (-) | -> common ground |

### 2.4 Power and common ground (critical)

```
Host USB ── programmer base ── ESP32-CAM   (board + camera + Wi-Fi powered from USB 5V)

Separate 5-6V ─┬── servo (through INA219)
(>=3A)         └── lighting LEDs

* All GND nets tied together (board, supply, INA219, AS5600, OLED, servo) = common ground
* The servo supply must be independent from the board/USB supply, so stall current
  doesn't brown out the camera/Wi-Fi
```

### 2.5 How the host gets both measurements and HMI

- **Measurements + HMI**: USB serial (`config -> station.mcu_port`, 115200).
  Functional results come up over serial; the host sends `HMI,...` frames back
  down the **same serial link** to drive the OLED (`SharedSerialHmi`).
- **Camera**: not used by this pure functional test. The ESP32-CAM's camera and
  Wi-Fi `/capture` sit idle; the firmware still includes the camera service (it
  can be stripped, or you can just use a plain ESP32 instead).

---

## 3. Fixturing (nest / mounting)

See **[servo_tester_physical_layout.svg](servo_tester_physical_layout.svg)** for
an illustrative sketch of how the pieces below sit relative to each other — it's
drawn before any physical measurement, so treat it as a layout intent, not a
dimensioned drawing.

Functional-test accuracy depends on **shaft-to-encoder concentricity**.

1. **Servo nest (3-2-1 locating + poka-yoke)**: print a pocket matching the
   MG996R's outline (approx. 40.7 x 19.7 x 42.9mm), seating against the
   underside, two sides, and one end. Add an **asymmetric feature** (poka-yoke)
   so the servo can't be seated backwards. A **manual toggle clamp** holds the
   servo down (manual is the most reliable choice for v2.0).

2. **Coaxial angle measurement (the key mechanical detail)**: print a
   **coupler** that mates the servo's output spline, with a **diametric
   magnet** glued to its top face. Mount the AS5600 board directly above (or
   below) the shaft, magnet centered on the chip, with an **air gap of
   ~1-2mm**. As the servo rotates, the AS5600 reads the true output angle
   directly, giving you travel, direction, and center offset.

3. **DUT contact**: mount a **3-pin female header** on the fixture; once the
   servo is seated, plug its lead into the header. No pogo pins required.

4. **Board and OLED**: mount the ESP32 (or ESP32-CAM used as a plain MCU) and
   the sensor wiring in an electronics tray next to the nest. The **OLED**
   sits on the front panel, facing the operator.

> The rendered diagrams are **illustrative**, drawn to match the real board
> outlines — not photographs. For exact pinouts, refer to each module's
> datasheet (AI-Thinker ESP32-CAM, AS5600, INA219, SSD1306, MG996R).

---

## 4. Where this maps into the software

- Command positions / limit windows: `config/mg996r.json -> functional`
- Serial port / I2C addresses: `config/mg996r.json -> station`
- Firmware: `firmware/servo_tester_cam/` (single board: functional test + OLED HMI)
- Bring up the simulator first with `python -m host.app --simulate --ui`, then
  switch to real hardware with `python -m host.app --port COM3 --ui`
  (functional test and HMI share the one serial port).
