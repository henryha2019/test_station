from host.config import DEFAULT_CONFIG, load_config
from host.functional import evaluate

CFG = load_config(DEFAULT_CONFIG)

GOOD = {
    "idle_mA": 8.0, "hold_mA": 25.0, "move_mA": 350.0,
    "range_deg": 300.0, "center_off_deg": 3.0, "speed_dps": 400.0,
    "direction": "increasing",
}


def test_good_passes():
    res = evaluate(dict(GOOD), CFG)
    assert res.passed
    assert res.fail_param == "-"


def test_range_too_small_fails():
    m = dict(GOOD, range_deg=100.0)
    res = evaluate(m, CFG)
    assert not res.passed
    assert any(f.param == "range_deg" and f.kind == "low" for f in res.failures)


def test_overcurrent_fails():
    m = dict(GOOD, move_mA=1200.0, hold_mA=900.0)
    res = evaluate(m, CFG)
    assert not res.passed
    assert any(f.param == "move_mA" and f.kind == "high" for f in res.failures)


def test_reversed_direction_fails():
    m = dict(GOOD, direction="decreasing")
    res = evaluate(m, CFG)
    assert not res.passed
    assert any(f.param == "direction" and f.kind == "mismatch" for f in res.failures)


def test_missing_measurement_is_a_failure():
    m = dict(GOOD)
    del m["speed_dps"]
    res = evaluate(m, CFG)
    assert not res.passed
    assert any(f.param == "speed_dps" for f in res.failures)
