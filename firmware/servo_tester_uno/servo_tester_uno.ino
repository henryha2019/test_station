/*
 * PogoTest — Servo functional test instrument (Arduino Uno)
 * --------------------------------------------------------
 * DUT: MG996R (or any 3-wire hobby servo).
 *
 * Role in the station: a generic functional INSTRUMENT. It commands the servo to
 * min / center / max, measures the actual response, and streams the raw readings.
 * It does NOT know the pass/fail limits — the host owns the recipe
 * (config/mg996r.json) and decides the verdict. Classic ATE.
 *
 * Sensors (both on the Uno I2C bus A4=SDA, A5=SCL):
 *   - AS5600 magnetic angle encoder (0x36): actual output-shaft angle.
 *     A diametric magnet on a coupler on the servo horn sits ~1-2 mm over the chip.
 *   - INA219 current sensor (0x40): servo supply current (high-side on V+).
 *
 * Servo PWM signal on D9 (Servo library). Servo POWER comes from a SEPARATE
 * 5-6 V supply (>=2-3 A; MG996R stall ~2.5 A) routed through the INA219, with a
 * common ground to the Uno.
 *
 * Serial protocol (115200 8N1, '\n'-terminated):
 *   HOST -> UNO   UNO -> HOST
 *   "ID?"         "ID,SERVOTEST-UNO,2.0"
 *   "PING"        "PONG"
 *   "RUN"         "MEAS,<key>,<value>"  (one per measurement) ... then "DONE,<ms>"
 *   <unknown>     "ERR,unknown_cmd"
 *
 * Measurements reported: idle_mA, angle_center, hold_mA, angle_min, angle_max,
 *   range_deg, center_off_deg, sweep_ms, speed_dps, move_mA, direction.
 *
 * Requires libraries: Servo (built-in), Adafruit_INA219, Wire (built-in).
 *   AS5600 is read directly over Wire (no extra lib needed).
 */

#include <Wire.h>
#include <Servo.h>
#include <Adafruit_INA219.h>

const uint8_t SERVO_PIN  = 9;
const int     PWM_MIN    = 1000;   // us  -> mirror config/mg996r.json pwm_us
const int     PWM_CENTER = 1500;
const int     PWM_MAX    = 2000;
const int     SETTLE_MS  = 600;
const uint8_t AS5600_ADDR = 0x36;

Servo servo;
Adafruit_INA219 ina219;
String line;

// ---- AS5600 ---------------------------------------------------------------
float readAngleDeg() {
  Wire.beginTransmission(AS5600_ADDR);
  Wire.write(0x0E);                 // ANGLE register (high byte)
  if (Wire.endTransmission(false) != 0) return -1.0;
  Wire.requestFrom((int)AS5600_ADDR, 2);
  if (Wire.available() < 2) return -1.0;
  uint16_t hi = Wire.read();
  uint16_t lo = Wire.read();
  uint16_t raw = ((hi << 8) | lo) & 0x0FFF;   // 12-bit
  return raw * (360.0 / 4096.0);
}

float readCurrent_mA() {
  float mA = ina219.getCurrent_mA();
  return mA < 0 ? -mA : mA;         // magnitude; high-side wiring sign varies
}

void emit(const char* key, float value) {
  Serial.print("MEAS,"); Serial.print(key); Serial.print(','); Serial.println(value, 2);
}
void emitStr(const char* key, const char* value) {
  Serial.print("MEAS,"); Serial.print(key); Serial.print(','); Serial.println(value);
}

// Settle to a target pulse, return peak current observed while moving there.
float moveTo(int us) {
  servo.writeMicroseconds(us);
  unsigned long t0 = millis();
  float peak = 0;
  while (millis() - t0 < SETTLE_MS) {
    float i = readCurrent_mA();
    if (i > peak) peak = i;
    delay(5);
  }
  return peak;
}

void runTest() {
  unsigned long t0 = millis();

  // Idle current (before commanding anything decisive).
  servo.writeMicroseconds(PWM_CENTER);
  delay(150);
  emit("idle_mA", readCurrent_mA());

  // Center: hold current + center angle.
  moveTo(PWM_CENTER);
  float aCenter = readAngleDeg();
  emit("angle_center", aCenter);
  emit("hold_mA", readCurrent_mA());

  // Min.
  moveTo(PWM_MIN);
  float aMin = readAngleDeg();
  emit("angle_min", aMin);

  // Max: time the full min->max sweep and capture peak current.
  unsigned long ts = millis();
  float movePeak = moveTo(PWM_MAX);
  unsigned long sweep = millis() - ts;
  float aMax = readAngleDeg();
  emit("angle_max", aMax);
  emit("move_mA", movePeak);

  float range = fabs(aMax - aMin);
  float mid = (aMin + aMax) / 2.0;
  emit("range_deg", range);
  emit("center_off_deg", fabs(mid - aCenter));
  emit("sweep_ms", (float)sweep);
  emit("speed_dps", sweep > 0 ? range / (sweep / 1000.0) : 0.0);
  emitStr("direction", (aMax >= aMin) ? "increasing" : "decreasing");

  servo.writeMicroseconds(PWM_CENTER);   // park
  Serial.print("DONE,"); Serial.println(millis() - t0);
}

void handle(const String& cmd) {
  if (cmd == "ID?")       Serial.println("ID,SERVOTEST-UNO,2.0");
  else if (cmd == "PING") Serial.println("PONG");
  else if (cmd == "RUN")  runTest();
  else if (cmd.length())  Serial.println("ERR,unknown_cmd");
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  ina219.begin();
  servo.attach(SERVO_PIN);
  servo.writeMicroseconds(PWM_CENTER);
  while (Serial.available()) Serial.read();
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (line.length()) { line.trim(); handle(line); line = ""; }
    } else {
      line += c;
      if (line.length() > 64) line = "";
    }
  }
}
