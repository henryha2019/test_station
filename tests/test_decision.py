from dataclasses import dataclass

from host.decision import decide


@dataclass
class F:
    passed: bool


def test_functional_only_verdict():
    assert decide(F(True)).final_pass is True
    assert decide(F(True)).reason == "-"

    assert decide(F(False)).final_pass is False
    assert decide(F(False)).reason == "FUNCTIONAL"
