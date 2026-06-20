import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
import cv2
from camera import Camera
from models import AlarmRecord


SCREENSHOT_DIR = Path(__file__).resolve().parents[2] / "private-data" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def save_alarm(
    db: Session,
    order_id: int,
    alarm_type: str,
    content: str,
    camera: Optional[Camera],
) -> AlarmRecord:
    screenshot_path = None
    if camera:
        frame = camera.get_frame()
        if frame is not None:
            filename = (
                f"{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
                f"_{alarm_type}.jpg"
            )
            screenshot_path = str(SCREENSHOT_DIR / filename)
            cv2.imwrite(screenshot_path, frame)

    alarm = AlarmRecord(
        order_id=order_id,
        alarm_type=alarm_type,
        content=content,
        screenshot_path=screenshot_path,
    )
    db.add(alarm)
    db.commit()
    db.refresh(alarm)
    return alarm
