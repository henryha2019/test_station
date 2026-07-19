# Firmware

**One board does it all** (except the CNN, which runs on the host). The sketch
never owns the verdict — the host does.

| Sketch | Board | Role |
|---|---|---|
| `servo_tester_cam/` | AI-Thinker **ESP32-CAM** | Functional instrument **+** camera **+** HMI. Commands the MG996R, streams raw readings (AS5600 angle, INA219 current, sweep timing), serves the camera frame over Wi-Fi (`GET /capture`) for the host CNN, and renders the verdict on an SSD1306 OLED. |

The host fetches `/capture` and runs the INT8 CNN; on-device inference is the
Phase 9 stretch (and wants an ESP32-S3, not this board).

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
| `HMI,<serial>,<func>,<vision>,<class>,<final>,<fpy>` | *(renders OLED)* |
| *(unknown)* | `ERR,unknown_cmd` |

Functional + HMI share this one serial link (`SharedSerialHmi` host-side); the
image comes over Wi-Fi. Reported keys: `idle_mA`, `angle_center`, `hold_mA`,
`angle_min`, `angle_max`, `move_mA`, `range_deg`, `center_off_deg`, `sweep_ms`,
`speed_dps`, `direction`. The host checks each against the limit windows in
`config/mg996r.json` — the firmware knows no limits.

Wi-Fi (**default STA + mDNS**): the board joins your network and advertises
itself, so the host fetches images at `http://pogotest-cam.local/capture` and
keeps its own internet. Edit `STA_SSID` / `STA_PASS`. Send `IP?` to read the raw
DHCP address if mDNS isn't available on your host. Set `WIFI_USE_SOFTAP 1` to
self-host an AP at `192.168.4.1` instead (host then joins that AP).

Libraries: esp32 core (`esp_camera`, `WiFi`, `esp_http_server`, `Wire`),
`Adafruit_INA219`, `Adafruit_SSD1306`, `Adafruit_GFX`.

The host's `SimInstrument` speaks this exact wire format, so the protocol parser
is exercised with and without hardware.
