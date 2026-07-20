/*
 * PogoTest — single-board servo station (AI-Thinker ESP32-CAM)
 * -----------------------------------------------------------
 * ONE board does everything except the CNN:
 *   - drives the MG996R servo (PWM, LEDC) and measures its response
 *   - reads AS5600 angle + INA219 current over I2C
 *   - drives the SSD1306 OLED (station HMI) over the SAME I2C bus
 *   - serves the camera frame over Wi-Fi (GET /capture) for the host CNN
 *   - speaks the functional serial protocol to the host over USB
 *
 * The CNN runs on the HOST (it fetches /capture). The host still owns the
 * verdict: this board only measures, images, and displays.
 *
 * Pin budget (camera occupies most GPIO; microSD MUST stay unused to free these):
 *   Servo PWM .......... GPIO13   (LEDC 50 Hz)
 *   I2C SDA ............ GPIO14   shared by AS5600(0x36) + INA219(0x40) + OLED(0x3C)
 *   I2C SCL ............ GPIO15
 *   USB serial ......... GPIO1/3  (via the programmer base) to the host
 *   Camera ............. fixed AI-Thinker pins (do not touch)
 *
 * Power: servo on a SEPARATE 5-6 V >=3 A supply through the INA219, common GND.
 * Never power the servo from the board/USB rail (stall ~2.5 A).
 *
 * Serial protocol (115200 8N1, '\n'):
 *   ID?  -> ID,SERVOTEST-CAM,2.0
 *   PING -> PONG
 *   IP?  -> IP,<addr>        (Wi-Fi address; see startWifi / mDNS below)
 *   RUN  -> MEAS,<key>,<val> ... DONE,<ms>
 *   HMI,<serial>,<func>,<final>,<fpy>  -> renders the OLED
 *
 * Libraries: esp32 core (esp_camera, WiFi, esp_http_server, Wire),
 *            Adafruit_INA219, Adafruit_SSD1306, Adafruit_GFX.
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <ESPmDNS.h>
#include "esp_http_server.h"
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <Adafruit_SSD1306.h>

// ---- AI-Thinker ESP32-CAM camera pins (do not change) --------------------
#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

// ---- Our peripherals (freed by leaving the SD card unused) ----------------
const int      SERVO_PIN  = 13;
const int      SDA_PIN    = 14;
const int      SCL_PIN    = 15;
const int      SERVO_CH   = 4;       // LEDC channel
const int      PWM_MIN    = 1000;    // us — mirror config/mg996r.json pwm_us
const int      PWM_CENTER = 1500;
const int      PWM_MAX    = 2000;
const int      SETTLE_MS  = 1200;    // must comfortably exceed a full-range sweep time;
                                      // mirror config/mg996r.json functional.settle_ms
const uint8_t  AS5600_ADDR = 0x36;

// ---- Wi-Fi ----------------------------------------------------------------
// Default STA: join your network so the host PC keeps its own internet. The
// DHCP IP isn't fixed, so we also publish mDNS -> the host reaches the camera at
//   http://pogotest-cam.local/capture
// (send "IP?" over serial to read the raw DHCP address if mDNS isn't available).
// Set WIFI_USE_SOFTAP to 1 to instead self-host an AP at 192.168.4.1.
#define WIFI_USE_SOFTAP 0
const char* STA_SSID  = "YOUR_WIFI";        // <-- edit
const char* STA_PASS  = "YOUR_PASSWORD";    // <-- edit
const char* MDNS_HOST = "pogotest-cam";     // -> pogotest-cam.local
const char* AP_SSID   = "PogoTest-CAM";
const char* AP_PASS   = "pogotest123";

Adafruit_INA219 ina219;
Adafruit_SSD1306 oled(128, 64, &Wire, -1);
httpd_handle_t cam_httpd = NULL;
String line;

// =========================================================================
// Servo (LEDC) — write a microsecond pulse at 50 Hz
// =========================================================================
void servoWriteUS(int us) {
  uint32_t duty = (uint32_t)((double)us / 20000.0 * 65535.0);  // 20 ms period, 16-bit
  ledcWrite(SERVO_CH, duty);
}

// =========================================================================
// Sensors
// =========================================================================
float readAngleDeg() {                               // raw AS5600 reading, 0-360, -1 = I2C error
  Wire.beginTransmission(AS5600_ADDR);
  Wire.write(0x0E);                                  // ANGLE register (high byte)
  if (Wire.endTransmission(false) != 0) return -1.0;
  Wire.requestFrom((int)AS5600_ADDR, 2);
  if (Wire.available() < 2) return -1.0;
  uint16_t hi = Wire.read(), lo = Wire.read();
  uint16_t raw = ((hi << 8) | lo) & 0x0FFF;          // 12-bit
  return raw * (360.0 / 4096.0);
}

float readCurrent_mA() {
  float mA = ina219.getCurrent_mA();
  return mA < 0 ? -mA : mA;                          // magnitude
}

// The MG996R used here travels close to a full turn (per-unit spec), so a
// single-point angle_min/angle_max sample can land on opposite sides of the
// AS5600's 0/360 wrap and corrupt range_deg (e.g. reading 5 degrees of travel
// when the shaft actually moved 355). Track angle continuously during each
// move and unwrap it instead: each new sample is compared to the previous
// one, and any jump greater than 180 degrees is assumed to be a wrap (not
// real motion) and folded back. This is only valid if the shaft can't
// actually move more than 180 degrees between two consecutive samples --
// true here since speed_dps is spec'd well under 1000 deg/s and samples are
// taken every few milliseconds. angle_center/angle_min/angle_max below are
// therefore relative to the start of the test (angle_center reads ~0 by
// construction), not absolute encoder positions -- only their differences
// (range_deg, center_off_deg) are meaningful, which is all the host checks.
float g_unwrapped    = 0;   // accumulated angle since resetAngleTracking(), deg
float g_lastRawAngle = -1;  // last raw (0-360) AS5600 sample this test, -1 = none yet

void resetAngleTracking() {
  g_unwrapped = 0;
  g_lastRawAngle = -1;
}

float sampleAngleUnwrapped() {
  float raw = readAngleDeg();
  if (raw < 0) return g_unwrapped;            // I2C read failed; skip this sample
  if (g_lastRawAngle < 0) {                   // first good sample since the last reset
    g_lastRawAngle = raw;
    return g_unwrapped;
  }
  float delta = raw - g_lastRawAngle;
  if (delta > 180.0)  delta -= 360.0;
  if (delta < -180.0) delta += 360.0;
  g_unwrapped += delta;
  g_lastRawAngle = raw;
  return g_unwrapped;
}

struct MoveResult { float peak_mA; float angleDeg; };

MoveResult moveTo(int us) {          // settle, return peak current + unwrapped angle
  servoWriteUS(us);
  unsigned long t0 = millis();
  float peak = 0;
  float angle = g_unwrapped;
  while (millis() - t0 < SETTLE_MS) {
    float i = readCurrent_mA();
    if (i > peak) peak = i;
    angle = sampleAngleUnwrapped();
    delay(5);
  }
  return MoveResult{peak, angle};
}

// =========================================================================
// Functional test sequence -> MEAS/DONE
// =========================================================================
void emit(const char* k, float v) {
  Serial.print("MEAS,"); Serial.print(k); Serial.print(','); Serial.println(v, 2);
}
void emitStr(const char* k, const char* v) {
  Serial.print("MEAS,"); Serial.print(k); Serial.print(','); Serial.println(v);
}

void runTest() {
  unsigned long t0 = millis();

  servoWriteUS(PWM_CENTER); delay(150);
  emit("idle_mA", readCurrent_mA());

  resetAngleTracking();                              // zero the unwrap reference at center
  MoveResult center = moveTo(PWM_CENTER);
  emit("angle_center", center.angleDeg);
  emit("hold_mA", readCurrent_mA());

  MoveResult minR = moveTo(PWM_MIN);
  emit("angle_min", minR.angleDeg);

  unsigned long ts = millis();
  MoveResult maxR = moveTo(PWM_MAX);
  unsigned long sweep = millis() - ts;
  emit("angle_max", maxR.angleDeg);
  emit("move_mA", maxR.peak_mA);

  float range = fabs(maxR.angleDeg - minR.angleDeg);
  float mid = (minR.angleDeg + maxR.angleDeg) / 2.0;
  emit("range_deg", range);
  emit("center_off_deg", fabs(mid - center.angleDeg));
  emit("sweep_ms", (float)sweep);
  emit("speed_dps", sweep > 0 ? range / (sweep / 1000.0) : 0.0);
  emitStr("direction", (maxR.angleDeg >= minR.angleDeg) ? "increasing" : "decreasing");

  servoWriteUS(PWM_CENTER);                          // park
  Serial.print("DONE,"); Serial.println(millis() - t0);
}

// =========================================================================
// OLED HMI — render a status frame pushed by the host
// =========================================================================
void renderHMI(const String& msg) {
  // HMI,serial,func,final,fpy
  String f[4];
  int idx = 0, start = 4;
  for (int i = 4; i <= (int)msg.length() && idx < 4; i++) {
    if (i == (int)msg.length() || msg.charAt(i) == ',') {
      f[idx++] = msg.substring(start, i); start = i + 1;
    }
  }
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setCursor(0, 0);  oled.print("SN "); oled.print(f[0]);
  oled.setCursor(86, 0); oled.print("FPY"); oled.print(f[3]);
  oled.setCursor(0, 18); oled.print("FUNC "); oled.print(f[1]);
  oled.setTextSize(2);
  oled.setCursor(0, 44); oled.print(f[2]);
  oled.display();
}

// =========================================================================
// Camera + HTTP /capture
// =========================================================================
bool startCamera() {
  camera_config_t c;
  c.ledc_channel = LEDC_CHANNEL_0;        // camera XCLK uses LEDC ch 0 (servo uses 4)
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM;  c.pin_d1 = Y3_GPIO_NUM;  c.pin_d2 = Y4_GPIO_NUM;
  c.pin_d3 = Y5_GPIO_NUM;  c.pin_d4 = Y6_GPIO_NUM;  c.pin_d5 = Y7_GPIO_NUM;
  c.pin_d6 = Y8_GPIO_NUM;  c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM; c.pin_pclk = PCLK_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM; c.pin_href = HREF_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM; c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_pwdn = PWDN_GPIO_NUM; c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.frame_size = FRAMESIZE_QVGA;          // 320x240; host resizes to model size
  c.pixel_format = PIXFORMAT_JPEG;
  c.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.jpeg_quality = 12;
  c.fb_count = psramFound() ? 2 : 1;
  return esp_camera_init(&c) == ESP_OK;
}

static esp_err_t capture_handler(httpd_req_t* req) {
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) { httpd_resp_send_500(req); return ESP_FAIL; }
  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  esp_err_t res = httpd_resp_send(req, (const char*)fb->buf, fb->len);
  esp_camera_fb_return(fb);
  return res;
}

void startServer() {
  httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
  httpd_uri_t uri = { .uri = "/capture", .method = HTTP_GET, .handler = capture_handler, .user_ctx = NULL };
  if (httpd_start(&cam_httpd, &cfg) == ESP_OK) httpd_register_uri_handler(cam_httpd, &uri);
}

String wifiIP() {
#if WIFI_USE_SOFTAP
  return WiFi.softAPIP().toString();
#else
  return WiFi.localIP().toString();
#endif
}

void startWifi() {
#if WIFI_USE_SOFTAP
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASS);            // host joins this AP; image at 192.168.4.1
#else
  WiFi.mode(WIFI_STA);
  WiFi.begin(STA_SSID, STA_PASS);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(250);  // ~10 s
  if (MDNS.begin(MDNS_HOST)) MDNS.addService("http", "tcp", 80);  // pogotest-cam.local
#endif
  Serial.print("IP,"); Serial.println(wifiIP());
}

// =========================================================================
void handle(const String& cmd) {
  if (cmd == "ID?")            Serial.println("ID,SERVOTEST-CAM,2.0");
  else if (cmd == "PING")      Serial.println("PONG");
  else if (cmd == "IP?")       { Serial.print("IP,"); Serial.println(wifiIP()); }
  else if (cmd == "RUN")       runTest();
  else if (cmd.startsWith("HMI,")) renderHMI(cmd);
  else if (cmd.length())       Serial.println("ERR,unknown_cmd");
}

void setup() {
  Serial.begin(115200);

  // Servo PWM.
  ledcSetup(SERVO_CH, 50, 16);
  ledcAttachPin(SERVO_PIN, SERVO_CH);
  servoWriteUS(PWM_CENTER);

  // I2C bus: sensors + OLED.
  Wire.begin(SDA_PIN, SCL_PIN);
  ina219.begin(&Wire);
  if (oled.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    oled.setTextColor(SSD1306_WHITE);
    oled.clearDisplay(); oled.setCursor(0, 0); oled.print("PogoTest CAM"); oled.display();
  }

  // Camera + Wi-Fi (STA + mDNS by default) + /capture server.
  startCamera();
  startWifi();
  startServer();

  while (Serial.available()) Serial.read();
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (line.length()) { line.trim(); handle(line); line = ""; }
    } else {
      line += c;
      if (line.length() > 160) line = "";
    }
  }
}
