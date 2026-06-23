from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from printcode_guard.models import Base, ScanRecord
from printcode_guard.detection import classify_code


def test_classify_first_valid_code():
    state = {"order_codes": {"A001"}}
    result = classify_code("A001", state, datetime.utcnow())
    assert result["status"] == "ok"
    assert result["is_duplicate"] is False
    assert result["is_abnormal"] is False
    assert result["should_record"] is True


def test_classify_same_code_twice_triggers_duplicate():
    """连续扫描同一码 -> 第二次触发全局重码报警。"""
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(ScanRecord(order_id=1, content="A001", result_status="ok"))
    db.commit()

    state = {"order_codes": {"A001"}}
    result = classify_code("A001", state, datetime.utcnow(), db)
    assert result["status"] == "duplicate"
    assert result["is_duplicate"] is True
    assert result["is_abnormal"] is True
    assert result["alarm_type"] == "duplicate"


def test_classify_global_duplicate_from_database():
    """数据库里已经存在该二维码 -> 全局重码报警。"""
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(ScanRecord(order_id=1, content="A001", result_status="ok"))
    db.commit()

    state = {"order_codes": {"A001"}}
    result = classify_code("A001", state, datetime.utcnow(), db)
    assert result["status"] == "duplicate"
    assert result["is_duplicate"] is True
    assert result["is_abnormal"] is True
    assert result["alarm_type"] == "duplicate"


def test_classify_not_in_library():
    state = {"order_codes": {"A001"}}
    result = classify_code("X999", state, datetime.utcnow())
    assert result["status"] == "not_in_library"
    assert result["is_abnormal"] is True


def test_classify_empty_library_skips_library_check():
    """码库为空时，不触发 not_in_library，方便第一阶段不接上游数据直接测试。"""
    state = {"order_codes": set()}
    result = classify_code("A001", state, datetime.utcnow())
    assert result["status"] == "ok"
    assert result["is_abnormal"] is False
