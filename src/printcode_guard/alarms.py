import datetime
from typing import Optional
from sqlalchemy.orm import Session
from .models import AlarmRecord


def save_alarm(
    db: Session,
    order_id: int,
    alarm_type: str,
    content: str,
    screenshot_path: Optional[str] = None,
) -> AlarmRecord:
    alarm = AlarmRecord(
        order_id=order_id,
        alarm_type=alarm_type,
        content=content,
        alarm_at=datetime.datetime.utcnow(),
        screenshot_path=screenshot_path,
    )
    db.add(alarm)
    db.commit()
    db.refresh(alarm)
    return alarm
