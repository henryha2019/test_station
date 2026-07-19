from host.config import DEFAULT_CONFIG, load_config
from host.instrument import SimInstrument
from host.orchestrator import Station

CFG = load_config(DEFAULT_CONFIG)


def make_station(scenario="good", seed=0):
    return Station(CFG, SimInstrument(CFG, scenario=scenario, seed=seed))


def test_good_unit_passes():
    rec = make_station("good").run_unit("SN1")
    assert rec.final_result == "PASS"
    assert rec.functional_result == "PASS"
    assert rec.fail_reason == "-"


def test_stalled_fails_functional():
    rec = make_station("stalled", seed=3).run_unit("SN2")
    assert rec.functional_result == "FAIL"
    assert rec.final_result == "FAIL"
    assert rec.fail_reason == "FUNCTIONAL"
    assert rec.fail_param != "-"


def test_reversed_fails_direction():
    rec = make_station("reversed", seed=5).run_unit("SN3")
    assert rec.final_result == "FAIL"
    assert rec.fail_param == "direction"


def test_fpy_tracking():
    st = make_station("good")
    for i in range(5):
        st.run_unit(f"SN{i}")
    assert st.tested == 5
    assert st.passed == 5
    assert st.fpy == 100.0
