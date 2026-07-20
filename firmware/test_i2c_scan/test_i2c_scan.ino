/*
 * Bring-up test 1 of 5 -- I2C bus scan
 * ------------------------------------
 * Run this FIRST, before anything else. It has no library dependencies beyond
 * Wire, so it will compile and run even if you haven't installed the sensor
 * libraries yet, and it's the fastest way to catch a wiring mistake before
 * chasing it through more complex sketches.
 *
 * What it does: scans every I2C address (1-126) on SDA=GPIO14 / SCL=GPIO15
 * once per second and prints what answers.
 *
 * Expected result once everything is wired per docs/HARDWARE.md:
 *   0x36  AS5600 (angle encoder)
 *   0x3C  SSD1306 (OLED)
 *   0x40  INA219 (current sensor)
 * All three should show up together. If one is missing:
 *   - double-check its VCC/GND/SDA/SCL wiring and that SDA->14, SCL->15
 *     (not the usual ESP32 default of 21/22 -- those are camera pins here)
 *   - make sure no microSD card is inserted (it uses GPIO 2/4/12/13/14/15 and
 *     will fight with this bus)
 *   - if it's the INA219 or an OLED variant with solder-jumper address bits,
 *     confirm the jumpers match the address above
 * If NOTHING shows up at all: SDA/SCL are swapped, or the bus has no pull-ups
 * (most breakout boards include their own, so this is rare), or Wire.begin()
 * picked the wrong pins.
 */

#include <Wire.h>

const int SDA_PIN = 14;
const int SCL_PIN = 15;

void setup() {
  Serial.begin(115200);
  delay(300);
  Wire.begin(SDA_PIN, SCL_PIN);
  Serial.println();
  Serial.println("I2C scan -- SDA=14 SCL=15. Expect 0x36 (AS5600), 0x3C (OLED), 0x40 (INA219).");
}

void loop() {
  Serial.println("--- scanning ---");
  int found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission();
    if (err == 0) {
      Serial.print("  found device at 0x");
      if (addr < 16) Serial.print('0');
      Serial.println(addr, HEX);
      found++;
    }
  }
  if (found == 0) {
    Serial.println("  nothing responded -- check wiring (see header comment above)");
  } else {
    Serial.print("  "); Serial.print(found); Serial.println(" device(s) found");
  }
  delay(1000);
}
