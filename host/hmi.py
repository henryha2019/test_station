"""Station HMI push. Sends one compact status frame per unit to the display.

Frame: HMI,<serial>,<func>,<vision>,<class>,<final>,<fpy_pct>
On the single-board ESP32-CAM the OLED hangs off the same MCU, so the frame goes
out over the *instrument's* serial link (SharedSerialHmi) — no second port.
"""
from __future__ import annotations


def format_frame(serial: str, func: bool, vision: bool, cls: str, final: bool, fpy_pct: float) -> str:
    return "HMI,{},{},{},{},{},{:.1f}".format(
        serial,
        "PASS" if func else "FAIL",
        "PASS" if vision else "FAIL",
        cls,
        "PASS" if final else "FAIL",
        fpy_pct,
    )


class Hmi:
    def push(self, frame: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:
        pass


class NullHmi(Hmi):
    def push(self, frame: str) -> None:
        pass


class ConsoleHmi(Hmi):
    def push(self, frame: str) -> None:
        print("[HMI] " + frame)


class SerialHmi(Hmi):
    """Drives a separate display node on its own serial port (2-board layout)."""

    def __init__(self, port: str, baud: int = 115200):
        import serial
        self._ser = serial.Serial(port, baud, timeout=1.0)

    def push(self, frame: str) -> None:
        self._ser.write((frame + "\n").encode("ascii"))
        self._ser.flush()

    def close(self) -> None:
        try:
            self._ser.close()
        except Exception:
            pass


class SharedSerialHmi(Hmi):
    """Single-board layout: the OLED is on the same MCU as the instrument, so we
    push the HMI frame through the instrument's existing serial link.

    `link` is anything with a send_line(str) method (e.g. SerialInstrument).
    Writes happen after the instrument's RUN completes, so the port is never
    accessed concurrently — no locking needed.
    """

    def __init__(self, link):
        self._link = link

    def push(self, frame: str) -> None:
        self._link.send_line(frame)
