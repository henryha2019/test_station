/*
 * Bring-up test 3 of 5 -- INA219 current sensor
 * ------------------------------------------------
 * Run after test_i2c_scan confirms 0x40 answers.
 * Requires the Adafruit_INA219 library (Library Manager -> "Adafruit INA219").
 *
 * Wiring reminder (see docs/HARDWARE.md / docs/servo_tester_schematic.svg):
 *   servo supply (+) -> INA219 Vin+
 *   INA219 Vin-      -> servo red wire (V+)
 *   servo supply (-) and servo black wire -> common ground
 * INA219 measures whatever current flows from Vin+ to Vin- -- i.e. it's
 * wired IN SERIES with the servo's power feed, not just tapped across it.
 *
 * What it prints once per second: bus voltage (should read ~5-6V once the
 * servo supply is on), current in mA (near 0 with the servo idle/unplugged,
 * jumping to the hundreds of mA if you command it to move with
 * test_servo_pwm), and power in mW.
 *
 * If bus voltage reads ~0V: the servo supply isn't connected/switched on, or
 * Vin+/Vin- are swapped with the actual power path.
 * If current never moves off ~0mA even while the servo is visibly working:
 * the servo's red wire isn't actually routed through Vin-, it's tied straight
 * to the supply.
 */

#include <Wire.h>
#include <Adafruit_INA219.h>

const int SDA_PIN = 14;
const int SCL_PIN = 15;

Adafruit_INA219 ina219;

void setup() {
  Serial.begin(115200);
  delay(300);
  Wire.begin(SDA_PIN, SCL_PIN);
  Serial.println();
  if (!ina219.begin(&Wire)) {
    Serial.println("INA219 not found at 0x40 -- check wiring / re-run test_i2c_scan");
    while (true) delay(1000);
  }
  Serial.println("INA219 test -- reading bus voltage / current / power once per second.");
}

void loop() {
  float busVoltage = ina219.getBusVoltage_V();
  float current_mA = ina219.getCurrent_mA();
  float power_mW    = ina219.getPower_mW();

  Serial.print("bus=");     Serial.print(busVoltage, 2); Serial.print("V");
  Serial.print("  current="); Serial.print(current_mA, 1); Serial.print("mA");
  Serial.print("  power=");   Serial.print(power_mW, 1);   Serial.println("mW");

  delay(300);
}
