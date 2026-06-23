from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class OrderCreate(BaseModel):
    name: str


class OrderOut(BaseModel):
    id: int
    name: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class CodeOut(BaseModel):
    id: int
    content: str
    scanned: bool

    class Config:
        from_attributes = True


class ScanRecordOut(BaseModel):
    id: int
    content: str
    read_at: datetime
    result_status: str
    is_duplicate: bool
    is_abnormal: bool

    class Config:
        from_attributes = True


class AlarmRecordOut(BaseModel):
    id: int
    alarm_type: str
    content: str
    alarm_at: datetime
    screenshot_path: Optional[str]

    class Config:
        from_attributes = True


class StatusResponse(BaseModel):
    current_order: Optional[OrderOut]
    scanner_device: Optional[str]
    scanner_online: bool
    scanner_error: Optional[str]
    buzzer_backend: Optional[str]
    is_running: bool
    total_scanned: int
    duplicate_count: int
    abnormal_count: int
    latest_code: Optional[str]
    alarm_active: bool


class ScannerDevicePayload(BaseModel):
    device: Optional[str] = None


class ROI(BaseModel):
    x: int
    y: int
    w: int
    h: int
