import pytest

from host import protocol as p


def test_meas_roundtrip_float():
    line = p.build_meas("range_deg", 119.8)
    assert line == "MEAS,range_deg,119.800"
    key, val = p.parse_meas(line)
    assert key == "range_deg"
    assert abs(val - 119.8) < 1e-6


def test_meas_roundtrip_string():
    line = p.build_meas("direction", "increasing")
    key, val = p.parse_meas(line)
    assert key == "direction"
    assert val == "increasing"


def test_parse_id():
    info = p.parse_id("ID,SERVOTEST-UNO,2.0")
    assert info.name == "SERVOTEST-UNO"
    assert info.version == "2.0"


def test_parse_done():
    assert p.parse_done("DONE,1820") == 1820


@pytest.mark.parametrize("bad", ["MEAS,onlyonefield", "NOPE", "DONE", "ID,x"])
def test_bad_lines_raise(bad):
    with pytest.raises(ValueError):
        if bad.startswith("MEAS"):
            p.parse_meas(bad)
        elif bad.startswith("DONE"):
            p.parse_done(bad)
        else:
            p.parse_id(bad)
