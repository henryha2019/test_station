/*
 * Bring-up test 4 of 5 -- SSD1306 OLED
 * ---------------------------------------
 * Run after test_i2c_scan confirms 0x3C answers.
 * Requires the Adafruit_SSD1306 and Adafruit_GFX libraries (Library Manager).
 *
 * What it does: draws a border, static text, and a counter that increments
 * once per second. The counter matters more than the static text -- it proves
 * the display is actually being re-drawn, not just showing whatever was in
 * its memory from a previous power-on.
 *
 * If nothing lights up: re-check wiring / re-run test_i2c_scan. Some SSD1306
 * modules use address 0x3D instead of 0x3C -- if the scan found a device at
 * 0x3D, change OLED_ADDR below to match.
 */

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

const int     SDA_PIN   = 14;
const int     SCL_PIN   = 15;
const uint8_t OLED_ADDR = 0x3C;

Adafruit_SSD1306 oled(128, 64, &Wire, -1);

void setup() {
  Serial.begin(115200);
  delay(300);
  Wire.begin(SDA_PIN, SCL_PIN);

  if (!oled.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("OLED not found -- check wiring / address / re-run test_i2c_scan");
    while (true) delay(1000);
  }
  Serial.println("OLED test -- counter should increment once per second on the display.");

  oled.setTextColor(SSD1306_WHITE);
  oled.clearDisplay();
  oled.drawRect(0, 0, 128, 64, SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(8, 8);
  oled.print("OLED OK");
  oled.setCursor(8, 24);
  oled.print("PogoTest bring-up");
  oled.display();
}

void loop() {
  static unsigned long count = 0;
  oled.fillRect(8, 44, 112, 16, SSD1306_BLACK);   // clear only the counter area
  oled.setCursor(8, 44);
  oled.setTextSize(2);
  oled.print(count++);
  oled.display();
  delay(1000);
}
