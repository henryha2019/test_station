/*
 * PogoTest — Station HMI (ESP32 + display)
 * ----------------------------------------
 * Phase 7. A dedicated indicator node so the rig becomes a "station": the
 * operator reads the full verdict here without looking at the PC. Keeping the
 * HMI on a SEPARATE ESP32 (not the ESP32-CAM) leaves the camera's pins free.
 *
 * The host pushes one compact status frame per cycle over USB serial:
 *   "HMI,<serial>,<func PASS|FAIL>,<vision PASS|FAIL>,<class>,<final PASS|FAIL>,<fpy_pct>"
 * Example:
 *   HMI,SN0007,PASS,FAIL,horn_missing,FAIL,92.3
 *
 * This sketch targets a 128x64 SSD1306 OLED on I2C (SDA=21, SCL=22). Swap the
 * draw routine for your panel (TFT_eSPI, etc.) — the parsing stays the same.
 * Requires the Adafruit_SSD1306 + Adafruit_GFX libraries.
 */

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_W 128
#define SCREEN_H 64
Adafruit_SSD1306 display(SCREEN_W, SCREEN_H, &Wire, -1);

String line;

struct Status {
  String serial = "----";
  String elec   = "----";
  String vision = "----";
  String cls    = "----";
  String fin    = "----";
  String fpy    = "--";
} st;

void render() {
  display.clearDisplay();

  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print("SN ");
  display.print(st.serial);
  display.setCursor(86, 0);
  display.print("FPY");
  display.print(st.fpy);

  display.setCursor(0, 14);
  display.print("FUNC ");
  display.print(st.elec);
  display.setCursor(0, 24);
  display.print("VIS  ");
  display.print(st.vision);
  display.setCursor(0, 34);
  display.print(st.cls);

  // Big final verdict banner.
  display.setTextSize(2);
  display.setCursor(0, 48);
  display.print(st.fin);

  display.display();
}

void parse(const String &msg) {
  // HMI,serial,elec,vision,class,final,fpy
  if (!msg.startsWith("HMI,")) return;
  String f[6];
  int idx = 0, start = 4;          // skip "HMI,"
  for (int i = 4; i <= msg.length() && idx < 6; i++) {
    if (i == msg.length() || msg.charAt(i) == ',') {
      f[idx++] = msg.substring(start, i);
      start = i + 1;
    }
  }
  st.serial = f[0];
  st.elec   = f[1];
  st.vision = f[2];
  st.cls    = f[3];
  st.fin    = f[4];
  st.fpy    = f[5];
  render();
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  display.setTextColor(SSD1306_WHITE);
  st = Status();
  render();
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (line.length() > 0) { line.trim(); parse(line); line = ""; }
    } else {
      line += c;
      if (line.length() > 120) line = "";
    }
  }
}
