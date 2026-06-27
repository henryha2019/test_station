from dataclasses import dataclass

from host.decision import decide


@dataclass
class F:
    passed: bool


@dataclass
class V:
    passed: bool


def test_truth_table():
    assert decide(F(True), V(True)).final_pass is True
    assert decide(F(True), V(True)).reason == "-"

    assert decide(F(False), V(True)).final_pass is False
    assert decide(F(False), V(True)).reason == "FUNCTIONAL"

    assert decide(F(True), V(False)).final_pass is False
    assert decide(F(True), V(False)).reason == "VISION"

    assert decide(F(False), V(False)).final_pass is False
    assert decide(F(False), V(False)).reason == "FUNCTIONAL+VISION"
