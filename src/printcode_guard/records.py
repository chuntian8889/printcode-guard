from typing import List, Optional
from sqlalchemy.orm import Session
from .models import ScanRecord, AlarmRecord


def create_scan_record(
    db: Session,
    order_id: int,
    content: str,
    status: str,
    is_duplicate: bool,
    is_abnormal: bool,
) -> ScanRecord:
    record = ScanRecord(
        order_id=order_id,
        content=content,
        result_status=status,
        is_duplicate=is_duplicate,
        is_abnormal=is_abnormal,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_recent_scans(
    db: Session, order_id: Optional[int] = None, limit: int = 20
) -> List[ScanRecord]:
    q = db.query(ScanRecord).order_by(ScanRecord.id.desc())
    if order_id:
        q = q.filter(ScanRecord.order_id == order_id)
    return q.limit(limit).all()


def get_recent_alarms(
    db: Session, order_id: Optional[int] = None, limit: int = 20
) -> List[AlarmRecord]:
    q = db.query(AlarmRecord).order_by(AlarmRecord.id.desc())
    if order_id:
        q = q.filter(AlarmRecord.order_id == order_id)
    return q.limit(limit).all()


def get_counts(db: Session, order_id: Optional[int] = None) -> dict:
    q = db.query(ScanRecord)
    if order_id:
        q = q.filter(ScanRecord.order_id == order_id)
    total = q.count()
    duplicate = q.filter(ScanRecord.is_duplicate == True).count()
    abnormal = q.filter(ScanRecord.is_abnormal == True).count()
    return {"total": total, "duplicate": duplicate, "abnormal": abnormal}
