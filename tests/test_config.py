import json

import pytest

from host.config import DEFAULT_CONFIG, Limit, load_config


def test_load_default():
    cfg = load_config(DEFAULT_CONFIG)
    assert cfg.dut_id == "MG996R"
    assert "range_deg" in cfg.limits
    assert cfg.vision.pass_class == "OK"
    assert cfg.pwm_us["min"] < cfg.pwm_us["center"] < cfg.pwm_us["max"]


def test_limit_windows():
    lim = Limit(min=100, max=140)
    assert lim.check(120) == (True, "")
    assert lim.check(80) == (False, "low")
    assert lim.check(200) == (False, "high")
    exp = Limit(expect="increasing")
    assert exp.check("increasing")[0] is True
    assert exp.check("decreasing")[0] is False


def test_validate_rejects_bad_pwm(tmp_path):
    data = json.loads(DEFAULT_CONFIG.read_text())
    data["functional"]["pwm_us"]["center"] = 900   # center < min
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_config(f)


def test_validate_rejects_bad_pass_class(tmp_path):
    data = json.loads(DEFAULT_CONFIG.read_text())
    data["vision"]["pass_class"] = "NOPE"
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_config(f)
