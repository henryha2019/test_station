# Firmware

**One board, functional test + HMI.** The sketch never owns the verdict — the
host does.

| Sketch | Board | Role |
|---|---|---|
| `servo_tester_cam/` | AI-Thinker **ESP32-CAM** (as MCU) | Functional instrument **+** HMI. Commands the MG996R and streams raw readings (AS5600 angle, INA219 current, sweep timing), and renders the verdict on an SSD1306 OLED. |
| `test_i2c_scan/`, `test_as5600/`, `test_ina219/`, `test_oled/`, `test_servo_pwm/` | either board | Standalone bring-up sketches — one per peripheral, no dependency on each other or on `servo_tester_cam`. Run these first; see [docs/RUNBOOK.md](../docs/RUNBOOK.md). These use only GPIO13/14/15 and have no camera code, so they run unmodified on a plain ESP32 too. |

Single-criterion (functional). The main sketch also still contains a camera
`/capture` server (Wi-Fi) that this tester **does not use** — trim it, or just
run a plain ESP32 instead of the ESP32-CAM (the bring-up sketches above already
do).

## Pin map (microSD must stay unused to free 13/14/15)

| Function | Pin |
|---|---|
| Servo PWM (LEDC 50 Hz) | GPIO13 |
| I²C SDA — OLED 0x3C · AS5600 0x36 · INA219 0x40 | GPIO14 |
| I²C SCL | GPIO15 |
| USB serial to host | GPIO1/3 (programmer base) |
| Camera + Wi-Fi `/capture` | fixed AI-Thinker pins |

The standard OLED pins 21/22 are **camera pins on the ESP32-CAM** — that's why the
I²C bus is moved to 14/15.

## Serial protocol (115200 8N1, `\n`-terminated)

| Host → CAM | CAM → Host |
|---|---|
| `ID?` | `ID,SERVOTEST-CAM,2.0` |
| `PING` | `PONG` |
| `RUN` | `MEAS,<key>,<value>` ×N, then `DONE,<elapsed_ms>` |
| `HMI,<serial>,<func>,<final>,<fpy>` | *(renders OLED)* |
| *(unknown)* | `ERR,unknown_cmd` |

Functional + HMI share this one serial link (`SharedSerialHmi` host-side).
Reported keys: `idle_mA`, `angle_center`, `hold_mA`,
`angle_min`, `angle_max`, `move_mA`, `range_deg`, `center_off_deg`, `sweep_ms`,
`speed_dps`, `direction`. The host checks each against the limit windows in
`config/mg996r.json` — the firmware knows no limits.

`angle_center`/`angle_min`/`angle_max` are **relative to the start of each
test** (continuously unwrapped across the AS5600's 0/360 wrap, since this
servo's travel is close to a full turn), not absolute encoder degrees —
`angle_center` reads ~0 by construction. Only the differences (`range_deg`,
`center_off_deg`) are meaningful, which is all the host actually checks.

Wi-Fi (**default STA + mDNS**): the board joins your network and advertises
itself, so the host fetches images at `http://pogotest-cam.local/capture` and
keeps its own internet. Edit `STA_SSID` / `STA_PASS`. Send `IP?` to read the raw
DHCP address if mDNS isn't available on your host. Set `WIFI_USE_SOFTAP 1` to
self-host an AP at `192.168.4.1` instead (host then joins that AP).

Libraries: esp32 core (`esp_camera`, `WiFi`, `esp_http_server`, `Wire`),
`Adafruit_INA219`, `Adafruit_SSD1306`, `Adafruit_GFX`.

The host's `SimInstrument` speaks this exact wire format, so the protocol parser
is exercised with and without hardware.
