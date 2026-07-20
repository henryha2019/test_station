/*
 * Bring-up test 2 of 5 -- AS5600 angle encoder
 * ---------------------------------------------
 * Run after test_i2c_scan confirms 0x36 answers. No library needed -- this
 * talks to the AS5600 with raw Wire calls, same register access as the main
 * firmware, so a pass here means the main firmware's angle reading will work.
 *
 * What it prints, once per second:
 *   angle    -- current shaft angle, 0-360 degrees. Turn the shaft by hand
 *               (or command the servo with test_servo_pwm) and confirm this
 *               tracks smoothly with no jumps or dead zones.
 *   AGC      -- automatic gain control, 0-255. This is the single most useful
 *               number for physically aligning the magnet: it should sit
 *               roughly in the middle of its range (~64-192). Pinned near 0
 *               means the magnet is too close/strong; pinned near 255 means
 *               too far/weak. Adjust the air gap (target ~1-2mm) until AGC
 *               settles mid-range across the shaft's full rotation.
 *   magnet   -- OK / TOO WEAK / TOO STRONG / NOT DETECTED, decoded from the
 *               STATUS register. Must read OK before you trust any angle
 *               measurement from this sensor.
 *
 * If the address doesn't answer at all, re-run test_i2c_scan -- this sketch
 * assumes 0x36 is already confirmed present.
 */

#include <Wire.h>

const int     SDA_PIN     = 14;
const int     SCL_PIN     = 15;
const uint8_t AS5600_ADDR = 0x36;

const uint8_t REG_STATUS = 0x0B;
const uint8_t REG_AGC    = 0x1A;
const uint8_t REG_ANGLE  = 0x0E;

int readReg8(uint8_t reg) {
  Wire.beginTransmission(AS5600_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return -1;
  Wire.requestFrom((int)AS5600_ADDR, 1);
  if (Wire.available() < 1) return -1;
  return Wire.read();
}

int readReg16(uint8_t reg) {
  Wire.beginTransmission(AS5600_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return -1;
  Wire.requestFrom((int)AS5600_ADDR, 2);
  if (Wire.available() < 2) return -1;
  uint16_t hi = Wire.read(), lo = Wire.read();
  return (hi << 8) | lo;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Wire.begin(SDA_PIN, SCL_PIN);
  Serial.println();
  Serial.println("AS5600 test -- reading angle/AGC/status once per second.");
}

void loop() {
  int raw = readReg16(REG_ANGLE);
  int agc = readReg8(REG_AGC);
  int status = readReg8(REG_STATUS);

  if (raw < 0 || agc < 0 || status < 0) {
    Serial.println("I2C read failed -- check wiring / re-run test_i2c_scan");
    delay(1000);
    return;
  }

  float angle = (raw & 0x0FFF) * (360.0 / 4096.0);
  bool md = status & 0x20;   // magnet detected
  bool ml = status & 0x10;   // magnet too weak
  bool mh = status & 0x08;   // magnet too strong

  const char* magnetState = !md ? "NOT DETECTED" : mh ? "TOO STRONG" : ml ? "TOO WEAK" : "OK";

  Serial.print("angle=");   Serial.print(angle, 2);
  Serial.print("  AGC=");   Serial.print(agc);
  Serial.print("  magnet="); Serial.println(magnetState);

  delay(300);
}
