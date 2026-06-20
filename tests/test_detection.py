from datetime import datetime, timedelta
from detection import classify_code


def test_classify_first_valid_code():
    state = {"last_seen": {}, "order_codes": {"A001"}}
    result = classify_code("A001", state, datetime.utcnow())
    assert result["status"] == "ok"
    assert result["is_duplicate"] is False
    assert result["is_abnormal"] is False


def test_classify_duplicate_within_window():
    now = datetime.utcnow()
    state = {"last_seen": {"A001": now - timedelta(seconds=1)}, "order_codes": {"A001"}}
    result = classify_code("A001", state, now)
    assert result["status"] == "duplicate"
    assert result["is_duplicate"] is True


def test_classify_not_in_library():
    state = {"last_seen": {}, "order_codes": {"A001"}}
    result = classify_code("X999", state, datetime.utcnow())
    assert result["status"] == "not_in_library"
    assert result["is_abnormal"] is True
