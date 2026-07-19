"""PogoTest servo station entry point (MG996R) — functional test.

Examples:
  python -m host.app --simulate --count 10 --random        # headless sim run
  python -m host.app --simulate --ui                        # interactive HMI (sim)
  python -m host.app --port COM3 --ui                       # live board (functional + OLED)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

# Allow `python host/app.py` as well as `python -m host.app`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from host import hmi as hmi_mod                          # noqa: E402
from host.config import DEFAULT_CONFIG, load_config      # noqa: E402
from host.instrument import SCENARIOS, SerialInstrument, SimInstrument  # noqa: E402
from host.orchestrator import Station                    # noqa: E402
from host.tracelog import TraceLog                       # noqa: E402


def build_hmi(args):
    if args.hmi_port:
        return hmi_mod.SerialHmi(args.hmi_port, args.hmi_baud)
    if args.hmi_console:
        return hmi_mod.ConsoleHmi()
    return hmi_mod.NullHmi()


def make_station(args, cfg) -> Station:
    log = TraceLog(args.log) if args.log else None
    if args.simulate:
        inst = SimInstrument(cfg, scenario=args.scenario, seed=args.seed)
        hmi = build_hmi(args)
    else:
        inst = SerialInstrument(args.port, cfg.station.get("mcu_baud", 115200))
        # OLED is on the same MCU -> push HMI over the instrument link, unless a
        # separate display node was requested.
        hmi = build_hmi(args) if (args.hmi_port or args.hmi_console) else hmi_mod.SharedSerialHmi(inst)
    return Station(cfg, inst, log, hmi)


def _inject(rng) -> str:
    """Pick a per-unit functional condition for --random: mostly good, some faults."""
    r = rng.random()
    if r < 0.75:
        return "good"
    return rng.choice(SCENARIOS[1:])


def run_headless(args, cfg) -> int:
    station = make_station(args, cfg)
    rng = np.random.default_rng(args.seed)
    print(f"PogoTest servo station — DUT {cfg.dut_id} (functional test)\n")
    hdr = f"{'serial':<8} {'final':<5} {'func':<5} {'range°':>7} {'move mA':>8} {'dps':>6} {'fail':<16}"
    print(hdr)
    print("-" * len(hdr))
    try:
        for i in range(1, args.count + 1):
            if args.random and args.simulate:
                station.instrument.scenario = _inject(rng)
            serial = f"{args.serial_prefix}{i:04d}"
            rec = station.run_unit(serial)
            fail = "-" if rec.fail_reason == "-" else f"{rec.fail_reason}:{rec.fail_param}"
            print(f"{rec.serial:<8} {rec.final_result:<5} {rec.functional_result:<5} "
                  f"{rec.range_deg:>7} {rec.move_mA:>8} {rec.speed_dps:>6} {fail:<16}")
    finally:
        station.close()
    print(f"\nTested {station.tested}  Pass {station.passed}  FPY {station.fpy:.1f}%")
    if args.log:
        print(f"Log: {args.log}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="PogoTest MG996R functional servo station")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--simulate", action="store_true", help="run with a simulated instrument")
    p.add_argument("--port", help="board serial port for functional + HMI (implies hardware mode)")
    p.add_argument("--hmi-port", help="separate display node serial port (optional)")
    p.add_argument("--hmi-baud", type=int, default=115200)
    p.add_argument("--hmi-console", action="store_true", help="print HMI frames to stdout")
    p.add_argument("--ui", action="store_true", help="launch the Tkinter station HMI")
    p.add_argument("--count", type=int, default=10)
    p.add_argument("--serial-prefix", default="SN")
    p.add_argument("--scenario", choices=SCENARIOS, default="good",
                   help="forced functional condition (sim)")
    p.add_argument("--random", action="store_true", help="randomize per-unit conditions (sim)")
    p.add_argument("--log", default="logs/log.csv")
    p.add_argument("--seed", type=int, default=None)
    args = p.parse_args(argv)

    # Default to simulation unless a real port was given.
    if not args.port:
        args.simulate = True

    cfg = load_config(args.config)

    if args.ui:
        from host.ui import launch
        return launch(make_station(args, cfg), cfg)
    return run_headless(args, cfg)


if __name__ == "__main__":
    raise SystemExit(main())
