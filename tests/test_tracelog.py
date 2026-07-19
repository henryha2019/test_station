import csv

from host.tracelog import FIELDS, TraceLog


def test_writes_header_and_rows(tmp_path):
    path = tmp_path / "log.csv"
    with TraceLog(path) as log:
        log.append({"serial": "SN0001", "final_result": "PASS"})
        log.append({"serial": "SN0002", "final_result": "FAIL", "fail_reason": "FUNCTIONAL"})

    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert list(rows[0].keys()) == FIELDS
    assert rows[0]["serial"] == "SN0001"
    assert rows[1]["fail_reason"] == "FUNCTIONAL"
    assert rows[0]["fail_reason"] == ""        # missing keys -> empty


def test_append_does_not_duplicate_header(tmp_path):
    path = tmp_path / "log.csv"
    TraceLog(path).append({"serial": "A"})
    TraceLog(path).append({"serial": "B"})     # reopen, must not re-write header
    text = path.read_text(encoding="utf-8")
    assert text.count("timestamp,serial") == 1
