/*
 * Bring-up test 5 of 5 -- servo PWM
 * ------------------------------------
 * No I2C, no libraries beyond the ESP32 core -- this can run before any
 * sensor is wired up at all, to confirm the servo itself moves and that
 * GPIO13 is actually reaching its signal wire.
 *
 * What it does: sweeps the servo MIN -> CENTER -> MAX -> CENTER on a 2-second
 * step, printing the commanded pulse width each time. Watch the horn/output
 * shaft and confirm it visibly moves to a different position at each step
 * (not just twitches) and that MIN/MAX are the physical extremes, not the
 * same position twice.
 *
 * IMPORTANT: power the servo from its own separate 5-6V >=3A supply per
 * docs/HARDWARE.md, never from USB -- stall current is ~2.5A. If the servo
 * doesn't move at all, check power first (a brown-out here can also crash the
 * board), then check the signal wire is actually on GPIO13.
 */

const int SERVO_PIN  = 13;
const int SERVO_CH   = 4;      // LEDC channel
const int PWM_MIN    = 1000;   // us
const int PWM_CENTER = 1500;
const int PWM_MAX    = 2000;

void writeUS(int us) {
  uint32_t duty = (uint32_t)((double)us / 20000.0 * 65535.0);   // 20ms period, 16-bit
  ledcWrite(SERVO_CH, duty);
  Serial.print("commanded "); Serial.print(us); Serial.println(" us");
}

void setup() {
  Serial.begin(115200);
  delay(300);
  ledcSetup(SERVO_CH, 50, 16);
  ledcAttachPin(SERVO_PIN, SERVO_CH);
  Serial.println();
  Serial.println("Servo PWM test -- watch the shaft move to each position.");
  writeUS(PWM_CENTER);
  delay(1000);
}

void loop() {
  writeUS(PWM_MIN);    delay(2000);
  writeUS(PWM_CENTER); delay(2000);
  writeUS(PWM_MAX);    delay(2000);
  writeUS(PWM_CENTER); delay(2000);
}
