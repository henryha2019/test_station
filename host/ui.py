"""Tkinter station HMI: Start button, big PASS/FAIL, functional result, FPY.

Single-criterion (functional). In simulation it exposes a fault injector so you
can demonstrate failures live: e.g. a stalled servo -> FAIL (FUNCTIONAL).
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .config import DutConfig
from .instrument import SCENARIOS, SimInstrument
from .orchestrator import Station

GREEN, RED, GREY = "#1b8a3a", "#b3261e", "#888888"


class StationUI:
    def __init__(self, root: tk.Tk, station: Station, cfg: DutConfig):
        self.root = root
        self.station = station
        self.cfg = cfg
        self.counter = 0
        self.is_sim = isinstance(station.instrument, SimInstrument)

        root.title(f"PogoTest — {cfg.dut_id}")
        root.configure(bg="#111111")
        root.geometry("460x540")

        tk.Label(root, text="POGOTEST · SERVO STATION", fg="#dddddd", bg="#111111",
                 font=("Segoe UI", 14, "bold")).pack(pady=(14, 2))
        tk.Label(root, text=f"DUT {cfg.dut_id}  ·  functional test",
                 fg=GREY, bg="#111111", font=("Segoe UI", 9)).pack()

        self.verdict = tk.Label(root, text="READY", fg="#ffffff", bg=GREY,
                                font=("Segoe UI", 40, "bold"), width=12, height=2)
        self.verdict.pack(pady=16, padx=16, fill="x")

        self.serial_lbl = tk.Label(root, text="SN ----", fg="#dddddd", bg="#111111",
                                   font=("Consolas", 13))
        self.serial_lbl.pack()

        self.func_lbl = tk.Label(root, text="FUNCTIONAL  —", fg=GREY, bg="#111111",
                                 font=("Consolas", 12))
        self.func_lbl.pack(pady=(10, 0))
        self.meas_lbl = tk.Label(root, text="", fg="#9a9a9a", bg="#111111",
                                 font=("Consolas", 10))
        self.meas_lbl.pack()

        if self.is_sim:
            box = tk.LabelFrame(root, text="inject (sim)", fg="#aaaaaa", bg="#111111",
                                font=("Segoe UI", 9))
            box.pack(pady=12, padx=16, fill="x")
            self.func_var = tk.StringVar(value="good")
            tk.Label(box, text="functional", fg="#cccccc", bg="#111111").grid(row=0, column=0, sticky="w", padx=6, pady=4)
            ttk.Combobox(box, textvariable=self.func_var, values=SCENARIOS, width=20,
                         state="readonly").grid(row=0, column=1, padx=6)

        self.start = tk.Button(root, text="START  ▶", command=self.run,
                               font=("Segoe UI", 16, "bold"), bg="#2d6cdf", fg="white",
                               activebackground="#1d4fb0", relief="flat", height=2)
        self.start.pack(pady=16, padx=16, fill="x")

        self.footer = tk.Label(root, text="tested 0   pass 0   FPY 0.0%",
                               fg="#bbbbbb", bg="#111111", font=("Consolas", 11))
        self.footer.pack(side="bottom", pady=10)

        root.bind("<Return>", lambda e: self.run())

    def run(self):
        if self.is_sim:
            self.station.instrument.scenario = self.func_var.get()
        self.counter += 1
        serial = f"SN{self.counter:04d}"
        rec = self.station.run_unit(serial)

        passed = rec.final_result == "PASS"
        self.verdict.configure(text=rec.final_result, bg=GREEN if passed else RED)
        self.serial_lbl.configure(text=f"SN {serial}")

        f_ok = rec.functional_result == "PASS"
        param = "" if rec.fail_param == "-" else f"  [{rec.fail_param}]"
        self.func_lbl.configure(text=f"FUNCTIONAL  {rec.functional_result}{param}",
                                fg=GREEN if f_ok else RED)
        self.meas_lbl.configure(
            text=f"range {rec.range_deg}°  move {rec.move_mA}mA  {rec.speed_dps}dps  {rec.direction}")
        self.footer.configure(
            text=f"tested {self.station.tested}   pass {self.station.passed}   FPY {self.station.fpy:.1f}%")


def launch(station: Station, cfg: DutConfig) -> int:
    root = tk.Tk()
    StationUI(root, station, cfg)
    try:
        root.mainloop()
    finally:
        station.close()
    return 0
