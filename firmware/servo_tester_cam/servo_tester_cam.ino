/*
 * PogoTest — single-board servo station (AI-Thinker ESP32-CAM as plain MCU)
 * --------------------------------------------------------------------------
 * ONE board does everything:
 *   - drives the MG996R servo (PWM, LEDC) and measures its response
 *   - reads AS5600 angle + INA219 current over I2C
 *   - drives the SSD1306 OLED (station HMI) over the SAME I2C bus
 *   - speaks the functional serial protocol to the host over USB
 *
 * Single-criterion functional test. The host owns the verdict: this board
 * only measures and displays. The camera and Wi-Fi are unused — this sketch
 * never touches them, so it runs unmodified on a plain ESP32 too.
 *
 * Pin budget (microSD MUST stay unused to free these):
 *   Servo PWM .......... GPIO13   (LEDC 50 Hz)
 *   I2C SDA ............ GPIO14   shared by AS5600(0x36) + INA219(0x40) + OLED(0x3C)
 *   I2C SCL ............ GPIO15
 *   USB serial ......... GPIO1/3  (via the programmer base) to the host
 *
 * Power: servo on a SEPARATE 5-6 V >=3 A supply through the INA219, common GND.
 * Never power the servo from the board/USB rail (stall ~2.5 A).
 *
 * Serial protocol (115200 8N1, '\n'):
 *   ID?  -> ID,SERVOTEST-CAM,2.0
 *   PING -> PONG
 *   RUN  -> MEAS,<key>,<val> ... DONE,<ms>
 *   HMI,<serial>,<func>,<final>,<fpy>  -> renders the OLED
 *
 * Libraries: Wire, Adafruit_INA219, Adafruit_SSD1306, Adafruit_GFX.
 */

#include <Wire.h>
#include <Adafruit_INA219.h>
#include <Adafruit_SSD1306.h>

// ---- Peripherals (freed by leaving the SD card unused) --------------------
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

Adafruit_INA219 ina219;
Adafruit_SSD1306 oled(128, 64, &Wire, -1);
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
void handle(const String& cmd) {
  if (cmd == "ID?")            Serial.println("ID,SERVOTEST-CAM,2.0");
  else if (cmd == "PING")      Serial.println("PONG");
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
