import json
from typing import Optional
from sqlalchemy.orm import Session
from models import Setting


def get_setting(db: Session, key: str, default=None):
    row = db.query(Setting).filter(Setting.key == key).first()
    if row is None:
        return default
    return row.value


def set_setting(db: Session, key: str, value: str):
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        row = Setting(key=key, value=value)
        db.add(row)
    db.commit()


def get_roi(db: Session) -> Optional[dict]:
    raw = get_setting(db, "roi")
    if raw:
        return json.loads(raw)
    return None


def set_roi(db: Session, roi: dict):
    set_setting(db, "roi", json.dumps(roi))


def get_rtsp_url(db: Session) -> str:
    return get_setting(db, "rtsp_url", "")


def set_rtsp_url(db: Session, url: str):
    set_setting(db, "rtsp_url", url)


def get_dedup_seconds(db: Session) -> int:
    raw = get_setting(db, "dedup_seconds", "2")
    try:
        return int(raw)
    except ValueError:
        return 2


def set_dedup_seconds(db: Session, seconds: int):
    set_setting(db, "dedup_seconds", str(seconds))
