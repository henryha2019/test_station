# AOI Conveyor — build plan (the split-out vision project)

**Goal:** a small **automated optical inspection (AOI) line**: 3D-printed parts
ride a short conveyor, a trigger fires a camera as each part reaches the station,
a CNN classifies good vs defect, and a reject actuator diverts the bad ones — all
logged per part. This is where the **Data/ML + in-line manufacturing** story
lives, split out of the servo tester so each project stays focused.

**Design philosophy (shared):** reliability through subtraction, and the host
owns the verdict. **Reuse first** — the whole vision pipeline already exists in
this repo's `vision/` and moves over almost unchanged.

**Nice closed loop with project #1:** the reject actuator is an **MG996R** — a
servo you validated on the functional tester now does a real job here.

---

## Architecture

```
   part in ──► [ 3D-printed parts on a short BELT ] ──► camera station ──► reject ──► bins
                                                          │  ▲                │
                                    break-beam trigger ───┘  │ JPEG           │ servo flip
                                                             ▼                ▼
                    ┌──────────────────────── HOST PC (Python) ───────────────────────┐
                    │ trigger→capture · INT8 CNN · operating point · verdict · CSV log │
                    │            · commands the reject servo on FAIL                   │
                    └──────────────────────────────────────────────────────────────────┘
```

Instruments (camera, trigger, belt, reject servo) act; the host decides. A frame
is captured **on trigger** (deterministic framing), not streamed continuously.

## What it reuses from `test_station/vision/`
Move these over as the seed — they need no rewrite:
- `synthimg.py` — synthetic parts + feature baseline (re-theme classes to your prints)
- `dataset.py` · `make_synthetic.py` · `capture.py` — labeled tree + stratified split
- `train.py` · `quantize.py` — MobileNetV2 transfer + INT8 PTQ
- `evaluate.py` — confusion matrix + recall-optimized operating point
- `inspection.py` · `camera.py` — runtime inference + capture backends
- `analysis/` — FPY, Pareto, cycle time, Gage R&R (transfer as-is)
Take `config/mg996r.json`'s `vision` block and `requirements-vision.txt` too.

## BOM (keep the belt genuinely simple)
| Part | Qty | Why |
|---|---|---|
| Camera: ESP32-CAM (you have one) **or** USB webcam | 1 | capture; webcam is easier + sharper for host inference |
| 3D-printed parts (OK + deliberate defects) | many | your controllable dataset — print good/bad at will |
| Short belt + 2 rollers (printed) + DC gear motor **or** stepper | 1 | ~20–30 cm; stepper gives clean indexed moves |
| Motor driver (L298N / DRV8825 / TB6612) | 1 | drive the belt |
| IR break-beam / photo-interrupter | 1 | part-arrival trigger at the camera station |
| **MG996R** + diverter arm | 1 | reject actuator (reuse a validated servo) |
| Diffuser shroud + white LEDs | 1 | controlled lighting over the belt (80% of vision success) |
| 5 V supply ≥3 A, common ground | 1 | motor + servo + LEDs |

## Defect taxonomy (pick 2–4, printable on purpose)
`OK`, `short_shot` (missing feature / holes), `warp` (lifted corner), `stringing`
(blobs/whiskers). Print bad variants deliberately so labels are ground-truth.

## Phased milestones (each leaves something demoable)
- **P0 — Dataset first (no belt yet).** Print parts, capture through the shroud by
  hand, build the manifest. *Done:* a clean labeled train/test split on disk.
- **P1 — Model + operating point.** Train the small CNN, evaluate on the held-out
  split. *Done:* "at ok_threshold X: defect recall Y%, false-reject Z%" + confusion
  matrix. (Reuses `train`/`evaluate` verbatim.)
- **P2 — Belt + trigger (static camera).** Belt moves parts; break-beam fires the
  capture. *Done:* each passing part yields exactly one framed image + a verdict.
- **P3 — Reject in the loop.** On FAIL the host commands the MG996R to divert the
  part. *Done:* good parts pass through, bad parts land in the reject bin.
- **P4 — Line metrics.** From the log: **UPH/throughput**, FPY, Pareto by defect,
  precision/recall, and **line-rate vs inference-latency** (the real edge/quant
  justification — the model must keep up with the belt). *Done:* one metrics page.
- **P5 (stretch) — On-device inference** on an ESP32-S3 cam so the camera node
  returns a verdict directly; compare latency/footprint vs host.

**Stop-and-ship points:** after P1 (a measured model), after P3 (a working line),
after P4 (the numbers). No half-built dead end.

## Metrics that close the interview
UPH (throughput) · FPY trend · Pareto by defect class · precision/recall +
operating point · belt-rate vs latency · Gage-R&R (one known part, verdict stable).

## How each discipline reads it
| Track | Pitch |
|---|---|
| **Data / ML** | Self-built printed dataset, quantized CNN, recall-optimized operating point, on-device latency |
| **Manufacturing** | In-line AOI, UPH, serial traceability, yield + defect Pareto, automatic reject |
| **Embedded** | Trigger-on-arrival, belt motion, reject actuation, line-rate vs inference latency |
| **Mechanical** | Belt/roller drive, part fixturing on a moving line, vision lighting enclosure |
