"""Station HMI push. Sends one compact status frame per unit to the display node.

Frame: HMI,<serial>,<func>,<vision>,<class>,<final>,<fpy_pct>  (see esp32_hmi.ino)
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
