from host.camera import SimCamera
from host.config import DEFAULT_CONFIG, load_config
from host.inspection import make_inspector
from host.instrument import SimInstrument
from host.orchestrator import Station

CFG = load_config(DEFAULT_CONFIG)


def make_station(scenario="good", dut_class="OK", seed=0):
    return Station(
        CFG,
        SimInstrument(CFG, scenario=scenario, seed=seed),
        SimCamera(CFG, dut_class=dut_class, seed=seed),
        make_inspector(CFG),
    )


def test_good_unit_passes():
    rec = make_station("good", "OK").run_unit("SN1")
    assert rec.final_result == "PASS"
    assert rec.functional_result == "PASS"
    assert rec.vision_result == "PASS"
    assert rec.fail_reason == "-"


def test_stalled_fails_functional():
    rec = make_station("stalled", "OK", seed=3).run_unit("SN2")
    assert rec.functional_result == "FAIL"
    assert rec.final_result == "FAIL"
    assert rec.fail_reason == "FUNCTIONAL"
    assert rec.fail_param != "-"


def test_visual_defect_fails_vision_only():
    rec = make_station("good", "horn_missing", seed=4).run_unit("SN3")
    assert rec.functional_result == "PASS"
    assert rec.vision_result == "FAIL"
    assert rec.final_result == "FAIL"
    assert rec.fail_reason == "VISION"


def test_fpy_tracking():
    st = make_station("good", "OK")
    for i in range(5):
        st.run_unit(f"SN{i}")
    assert st.tested == 5
    assert st.passed == 5
    assert st.fpy == 100.0
