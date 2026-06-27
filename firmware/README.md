# Firmware

Two independent nodes. Neither owns the verdict — the host does.

| Sketch | Board | Role |
|---|---|---|
| `servo_tester_uno/` | Arduino Uno | Functional instrument. Commands the MG996R to min/center/max and streams raw readings (AS5600 angle, INA219 current, sweep timing). |
| `esp32_hmi/` | ESP32 + SSD1306 OLED | Station HMI. Renders the per-unit verdict pushed by the host. |

The ESP32-CAM has **no sketch in v2.0** — it streams JPEG over Wi-Fi (stock `CameraWebServer` example, `/capture` endpoint) and the host runs inference. On-device INT8 inference is Phase 9 (stretch).

## Uno serial protocol (115200 8N1, `\n`-terminated)

| Host → Uno | Uno → Host |
|---|---|
| `ID?` | `ID,SERVOTEST-UNO,2.0` |
| `PING` | `PONG` |
| `RUN` | `MEAS,<key>,<value>` ×N, then `DONE,<elapsed_ms>` |
| *(unknown)* | `ERR,unknown_cmd` |

Reported measurement keys: `idle_mA`, `angle_center`, `hold_mA`, `angle_min`,
`angle_max`, `move_mA`, `range_deg`, `center_off_deg`, `sweep_ms`, `speed_dps`,
`direction`. The host checks each against the limit windows in
`config/mg996r.json` — the firmware itself knows no limits.

Libraries: `Servo` (built-in), `Wire` (built-in), `Adafruit_INA219`. AS5600 is
read directly over I²C (no extra library).

The host's `SimInstrument` speaks this exact wire format, so the protocol parser
is exercised with and without hardware.
